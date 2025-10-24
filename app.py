from flask import Flask, jsonify, request
import psycopg2
import psycopg2.extras
import os
from dotenv import load_dotenv
import json
import hashlib
import requests
from datetime import datetime
import logging
from functools import wraps
import time

# --- Initialization ---
load_dotenv()
app = Flask(__name__)

# Configure logging for monitoring (Task 6)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# --- Configuration ---
DB_HOST = os.getenv("DB_HOST", "payment_db")  # Changed to match docker service name
DB_NAME = os.getenv("DB_NAME", "postgres")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASS = os.getenv("DB_PASS", "Superb#915")
DB_PORT = os.getenv("DB_PORT", "5433")

# Inter-service URLs (configure these based on your other services)
TRIP_SERVICE_URL = os.getenv("TRIP_SERVICE_URL", "http://trip-service:8081")
NOTIFICATION_SERVICE_URL = os.getenv("NOTIFICATION_SERVICE_URL", "http://notification-service:8084")

# --- Rate Limiting Decorator (Task 3) ---
def rate_limit(max_calls=10, time_window=60):
    def decorator(f):
        calls = []
        @wraps(f)
        def wrapper(*args, **kwargs):
            now = time.time()
            # Remove old calls outside the time window
            calls[:] = [call for call in calls if call > now - time_window]
            if len(calls) >= max_calls:
                logger.warning(f"Rate limit exceeded for {request.remote_addr}")
                return jsonify({"error": "Rate limit exceeded"}), 429
            calls.append(now)
            return f(*args, **kwargs)
        return wrapper
    return decorator

# --- Database Connection Helper ---
def get_db_connection():
    """Establishes a connection to the PostgreSQL database."""
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASS,
            port=DB_PORT
        )
        return conn
    except Exception as e:
        logger.error(f"Database connection error: {e}")
        return None

# --- Helper Functions ---
def generate_idempotency_hash(key):
    """Generate a hash for idempotency key"""
    return hashlib.sha256(key.encode()).hexdigest()

def validate_trip_completion(trip_id):
    """Call Trip Service to validate if trip is completed"""
    try:
        response = requests.get(f"{TRIP_SERVICE_URL}/v1/trips/{trip_id}", timeout=5)
        if response.status_code == 200:
            trip_data = response.json()
            return trip_data.get('status') == 'COMPLETED', trip_data
        return False, None
    except Exception as e:
        logger.error(f"Error calling Trip Service: {e}")
        return False, None

def calculate_fare(trip_data):
    """Calculate fare based on trip data"""
    base_fare = 5.0  # Base fare
    distance = trip_data.get('distance', 0)
    rate_per_km = 2.5  # Rate per kilometer
    surge_multiplier = trip_data.get('surge_multiplier', 1.0)
    
    fare = (base_fare + (distance * rate_per_km)) * surge_multiplier
    return round(fare, 2)

# --- API Endpoints ---

# 1. Health Check (Task 6: Monitoring)
@app.route('/health', methods=['GET'])
def health_check():
    """Returns the service status and checks database connectivity."""
    db_status = "DOWN"
    conn = get_db_connection()
    try:
        if conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1;")
            cursor.close()
            db_status = "UP"
    except Exception as e:
        logger.error(f"Health check DB error: {e}")
        db_status = "DOWN"
    finally:
        if conn:
            conn.close()
    
    return jsonify({
        "service": "Payment Service",
        "status": "UP",
        "database_status": db_status,
        "timestamp": datetime.utcnow().isoformat()
    }), 200 if db_status == "UP" else 503

# 2. Get all payments with filtering
@app.route('/v1/payments', methods=['GET'])
def get_payments():
    """Get all payments with optional filtering"""
    trip_id = request.args.get('trip_id')
    status = request.args.get('status')
    method = request.args.get('method')
    limit = request.args.get('limit', 100)
    offset = request.args.get('offset', 0)
    
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 503
    
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        query = "SELECT * FROM payments WHERE 1=1"
        params = []
        
        if trip_id:
            query += " AND trip_id = %s"
            params.append(trip_id)
        if status:
            query += " AND status = %s"
            params.append(status)
        if method:
            query += " AND method = %s"
            params.append(method)
        
        query += " ORDER BY created_at DESC LIMIT %s OFFSET %s"
        params.extend([limit, offset])
        
        cursor.execute(query, params)
        payments = cursor.fetchall()
        
        # Convert datetime objects to strings
        for payment in payments:
            if payment.get('created_at'):
                payment['created_at'] = payment['created_at'].isoformat()
        
        cursor.close()
        return jsonify({"payments": payments, "count": len(payments)}), 200
        
    except Exception as e:
        logger.error(f"Error fetching payments: {e}")
        return jsonify({"error": "Internal server error"}), 500
    finally:
        if conn:
            conn.close()

# 3. Get payment by ID
@app.route('/v1/payments/<int:payment_id>', methods=['GET'])
def get_payment(payment_id):
    """Get a specific payment by ID"""
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 503
    
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute("SELECT * FROM payments WHERE payment_id = %s", (payment_id,))
        payment = cursor.fetchone()
        cursor.close()
        
        if not payment:
            return jsonify({"error": "Payment not found"}), 404
        
        if payment.get('created_at'):
            payment['created_at'] = payment['created_at'].isoformat()
        
        return jsonify(payment), 200
        
    except Exception as e:
        logger.error(f"Error fetching payment {payment_id}: {e}")
        return jsonify({"error": "Internal server error"}), 500
    finally:
        if conn:
            conn.close()

# 4. Process Payment (Idempotent) - Main endpoint
@app.route('/v1/payments/charge', methods=['POST'])
@rate_limit(max_calls=100, time_window=60)
def process_charge():
    """
    Process payment for a trip. Implements idempotency.
    Expected payload:
    {
        "idempotency_key": "unique-key",
        "trip_id": 123,
        "method": "CARD",
        "rider_id": 456,
        "driver_id": 789
    }
    """
    data = request.json
    
    # Validate required fields
    required_fields = ['idempotency_key', 'trip_id', 'method']
    for field in required_fields:
        if field not in data:
            return jsonify({"error": f"Missing required field: {field}"}), 400
    
    idempotency_key = data.get('idempotency_key')
    key_hash = generate_idempotency_hash(idempotency_key)
    
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 503
    
    try:
        cursor = conn.cursor()
        
        # Check for idempotency
        cursor.execute(
            "SELECT response_data, response_status FROM idempotency_keys WHERE key_hash = %s",
            (key_hash,)
        )
        result = cursor.fetchone()
        
        if result:
            # Return cached response
            response_data = result[0]
            status_code = result[1]
            logger.info(f"Idempotency hit for key: {idempotency_key}")
            return jsonify(response_data), status_code
        
        # Validate trip completion (Inter-service communication)
        trip_id = data.get('trip_id')
        is_completed, trip_data = validate_trip_completion(trip_id)
        
        if not is_completed:
            error_response = {
                "error": "Cannot process payment for incomplete trip",
                "trip_id": trip_id
            }
            return jsonify(error_response), 400
        
        # Calculate fare
        amount = calculate_fare(trip_data) if trip_data else data.get('amount', 0)
        
        # Process payment (simulate payment gateway)
        method = data.get('method')
        
        # Simulate different payment outcomes based on method
        if method == 'CASH':
            payment_status = 'SUCCESS'  # Cash is always successful
        elif method in ['CARD', 'WALLET', 'UPI']:
            # Simulate 80% success rate for electronic payments
            import random
            payment_status = 'SUCCESS' if random.random() > 0.2 else 'FAILED'
        else:
            payment_status = 'PENDING'
        
        # Generate payment reference
        reference = f"PAY-{datetime.utcnow().strftime('%Y%m%d')}-{key_hash[:8]}"
        
        # Get next payment_id
        cursor.execute("SELECT COALESCE(MAX(payment_id), 0) + 1 FROM payments")
        payment_id = cursor.fetchone()[0]
        
        # Insert payment record
        cursor.execute(
            """INSERT INTO payments (payment_id, trip_id, amount, method, status, reference, created_at)
               VALUES (%s, %s, %s, %s, %s, %s, %s)""",
            (payment_id, trip_id, amount, method, payment_status, reference, datetime.utcnow())
        )
        
        # Prepare response
        response_data = {
            "payment_id": payment_id,
            "trip_id": trip_id,
            "amount": amount,
            "method": method,
            "status": payment_status,
            "reference": reference,
            "message": f"Payment {payment_status.lower()}",
            "timestamp": datetime.utcnow().isoformat()
        }
        
        status_code = 201 if payment_status == 'SUCCESS' else 202
        
        # Store idempotency key
        cursor.execute(
            """INSERT INTO idempotency_keys (key_hash, request_path, response_status, response_data, created_at)
               VALUES (%s, %s, %s, %s, %s)""",
            (key_hash, request.path, status_code, json.dumps(response_data), datetime.utcnow())
        )
        
        conn.commit()
        
        # Log the transaction
        logger.info(f"Payment processed: {payment_id} for trip {trip_id} - Status: {payment_status}")
        
        # Send notification (async in production)
        try:
            notification_payload = {
                "type": "payment",
                "payment_id": payment_id,
                "rider_id": data.get('rider_id'),
                "driver_id": data.get('driver_id'),
                "status": payment_status
            }
            requests.post(f"{NOTIFICATION_SERVICE_URL}/v1/notifications", 
                        json=notification_payload, timeout=2)
        except:
            pass  # Don't fail payment if notification fails
        
        return jsonify(response_data), status_code
        
    except Exception as e:
        logger.error(f"Error processing payment: {e}")
        if conn:
            conn.rollback()
        return jsonify({"error": "Payment processing failed", "details": str(e)}), 500
    finally:
        if conn:
            conn.close()

# 5. Process Refund (Idempotent)
@app.route('/v1/payments/<int:payment_id>/refund', methods=['POST'])
@rate_limit(max_calls=50, time_window=60)
def process_refund(payment_id):
    """Process refund for a payment"""
    data = request.json or {}
    idempotency_key = data.get('idempotency_key', f"refund-{payment_id}")
    key_hash = generate_idempotency_hash(idempotency_key)
    
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 503
    
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # Check idempotency
        cursor.execute(
            "SELECT response_data, response_status FROM idempotency_keys WHERE key_hash = %s",
            (key_hash,)
        )
        result = cursor.fetchone()
        
        if result:
            return jsonify(result['response_data']), result['response_status']
        
        # Fetch original payment
        cursor.execute("SELECT * FROM payments WHERE payment_id = %s", (payment_id,))
        payment = cursor.fetchone()
        
        if not payment:
            return jsonify({"error": "Payment not found"}), 404
        
        if payment['status'] != 'SUCCESS':
            return jsonify({"error": "Can only refund successful payments"}), 400
        
        # Process refund (simulate)
        refund_amount = data.get('amount', payment['amount'])
        
        # Update payment status to REFUNDED
        cursor.execute(
            "UPDATE payments SET status = 'REFUNDED' WHERE payment_id = %s",
            (payment_id,)
        )
        
        response_data = {
            "payment_id": payment_id,
            "refund_amount": float(refund_amount),
            "status": "REFUNDED",
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Store idempotency
        cursor.execute(
            """INSERT INTO idempotency_keys (key_hash, request_path, response_status, response_data, created_at)
               VALUES (%s, %s, %s, %s, %s)""",
            (key_hash, request.path, 200, json.dumps(response_data), datetime.utcnow())
        )
        
        conn.commit()
        
        logger.info(f"Refund processed for payment: {payment_id}")
        return jsonify(response_data), 200
        
    except Exception as e:
        logger.error(f"Error processing refund: {e}")
        if conn:
            conn.rollback()
        return jsonify({"error": "Refund processing failed"}), 500
    finally:
        if conn:
            conn.close()

# 6. Payment Receipt Generation
@app.route('/v1/payments/<int:payment_id>/receipt', methods=['GET'])
def generate_receipt(payment_id):
    """Generate receipt for a payment"""
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 503
    
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute("SELECT * FROM payments WHERE payment_id = %s", (payment_id,))
        payment = cursor.fetchone()
        cursor.close()
        
        if not payment:
            return jsonify({"error": "Payment not found"}), 404
        
        receipt = {
            "receipt_id": f"RCP-{payment['reference']}",
            "payment_id": payment['payment_id'],
            "trip_id": payment['trip_id'],
            "amount": float(payment['amount']),
            "method": payment['method'],
            "status": payment['status'],
            "reference": payment['reference'],
            "created_at": payment['created_at'].isoformat() if payment['created_at'] else None,
            "generated_at": datetime.utcnow().isoformat()
        }
        
        return jsonify(receipt), 200
        
    except Exception as e:
        logger.error(f"Error generating receipt: {e}")
        return jsonify({"error": "Receipt generation failed"}), 500
    finally:
        if conn:
            conn.close()

# 7. Metrics endpoint for monitoring
@app.route('/metrics', methods=['GET'])
def get_metrics():
    """Get service metrics for monitoring"""
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 503
    
    try:
        cursor = conn.cursor()
        
        metrics = {}
        
        # Total payments by status
        cursor.execute("""
            SELECT status, COUNT(*) as count 
            FROM payments 
            GROUP BY status
        """)
        status_counts = dict(cursor.fetchall())
        
        # Total payments by method
        cursor.execute("""
            SELECT method, COUNT(*) as count 
            FROM payments 
            GROUP BY method
        """)
        method_counts = dict(cursor.fetchall())
        
        # Average payment amount
        cursor.execute("SELECT AVG(amount) FROM payments WHERE status = 'SUCCESS'")
        avg_amount = cursor.fetchone()[0]
        
        cursor.close()
        
        metrics = {
            "payments_by_status": status_counts,
            "payments_by_method": method_counts,
            "average_payment_amount": float(avg_amount) if avg_amount else 0,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        return jsonify(metrics), 200
        
    except Exception as e:
        logger.error(f"Error fetching metrics: {e}")
        return jsonify({"error": "Metrics fetch failed"}), 500
    finally:
        if conn:
            conn.close()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8082, debug=False)