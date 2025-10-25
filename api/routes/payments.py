# api/routes/payments.py - Payment Routes
from flask import Blueprint, jsonify, request
from datetime import datetime
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from services.payment_service import PaymentService
from services.idempotency_service import IdempotencyService
from services.external_services import ExternalServices
from api.middleware.rate_limiter import rate_limit
from utils.logger import get_logger

logger = get_logger(__name__)
payments_bp = Blueprint('payments', __name__, url_prefix='/v1')

@payments_bp.route('/payments', methods=['GET'])
def get_payments():
    """Get all payments with optional filtering"""
    try:
        # Extract query parameters
        filters = {
            'trip_id': request.args.get('trip_id', type=int),
            'status': request.args.get('status'),
            'method': request.args.get('method'),
            'limit': request.args.get('limit', 100, type=int),
            'offset': request.args.get('offset', 0, type=int)
        }
        
        # Remove None values
        filters = {k: v for k, v in filters.items() if v is not None}
        
        # Get payments
        payments, count = PaymentService.get_all_payments(filters)
        
        return jsonify({
            'payments': payments,
            'count': count,
            'limit': filters.get('limit', 100),
            'offset': filters.get('offset', 0)
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting payments: {e}")
        return jsonify({'error': 'Failed to retrieve payments'}), 500

@payments_bp.route('/payments/<int:payment_id>', methods=['GET'])
def get_payment(payment_id):
    """Get a specific payment by ID"""
    try:
        payment = PaymentService.get_payment_by_id(payment_id)
        
        if not payment:
            return jsonify({'error': 'Payment not found'}), 404
        
        return jsonify(payment), 200
        
    except Exception as e:
        logger.error(f"Error getting payment {payment_id}: {e}")
        return jsonify({'error': 'Failed to retrieve payment'}), 500

@payments_bp.route('/payments/charge', methods=['POST'])
@rate_limit(max_calls=50, time_window=60)
def process_charge():
    """
    Process payment for a trip (Idempotent)
    
    Request body:
    {
        "idempotency_key": "unique-key",
        "trip_id": 123,
        "method": "CARD",
        "rider_id": 456,
        "driver_id": 789
    }
    """
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['idempotency_key', 'trip_id', 'method']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        # Generate idempotency hash
        key_hash = IdempotencyService.generate_hash(data['idempotency_key'])
        
        # Check for idempotent request
        cached_result = IdempotencyService.check_idempotency(key_hash)
        if cached_result:
            response_data, status_code = cached_result
            logger.info(f"Returning cached response for idempotency key")
            return jsonify(response_data), status_code
        
        # Validate trip completion
        trip_id = data['trip_id']
        is_completed, trip_data = ExternalServices.validate_trip_completion(trip_id)
        
        if not is_completed:
            error_response = {
                'error': 'Cannot process payment for incomplete trip',
                'trip_id': trip_id,
                'trip_status': trip_data.get('status') if trip_data else 'UNKNOWN'
            }
            return jsonify(error_response), 400
        
        # Calculate fare
        amount = PaymentService.calculate_fare(trip_data) if trip_data else data.get('amount', 0)
        
        # Process payment through gateway
        gateway_response = ExternalServices.simulate_payment_gateway({
            'method': data['method'],
            'amount': amount
        })
        
        # Create payment record
        payment_data = {
            'trip_id': trip_id,
            'amount': amount,
            'method': data['method'],
            'status': gateway_response['status'],
            'idempotency_hash': key_hash
        }
        
        payment = PaymentService.create_payment(payment_data)
        
        # Prepare response
        response_data = {
            'payment_id': payment['payment_id'],
            'trip_id': payment['trip_id'],
            'amount': payment['amount'],
            'method': payment['method'],
            'status': payment['status'],
            'reference': payment['reference'],
            'message': f"Payment {payment['status'].lower()}",
            'timestamp': datetime.utcnow().isoformat()
        }
        
        status_code = 201 if payment['status'] == 'SUCCESS' else 202
        
        # Store idempotency
        IdempotencyService.store_idempotency(
            key_hash,
            request.path,
            response_data,
            status_code
        )
        
        # Send notification (async)
        notification_data = {
            'type': 'payment',
            'payment_id': payment['payment_id'],
            'rider_id': data.get('rider_id'),
            'driver_id': data.get('driver_id'),
            'status': payment['status']
        }
        ExternalServices.send_payment_notification(notification_data)
        
        return jsonify(response_data), status_code
        
    except Exception as e:
        logger.error(f"Error processing payment: {e}")
        return jsonify({'error': 'Payment processing failed', 'details': str(e)}), 500

@payments_bp.route('/payments/<int:payment_id>/refund', methods=['POST'])
@rate_limit(max_calls=20, time_window=60)
def process_refund(payment_id):
    """Process refund for a payment"""
    try:
        data = request.get_json() or {}
        
        # Generate idempotency key if not provided
        idempotency_key = data.get('idempotency_key', f'refund-{payment_id}-{datetime.utcnow().isoformat()}')
        key_hash = IdempotencyService.generate_hash(idempotency_key)
        
        # Check idempotency
        cached_result = IdempotencyService.check_idempotency(key_hash)
        if cached_result:
            response_data, status_code = cached_result
            return jsonify(response_data), status_code
        
        # Process refund
        refund_amount = data.get('amount')
        refund = PaymentService.process_refund(payment_id, refund_amount)
        
        # Store idempotency
        IdempotencyService.store_idempotency(
            key_hash,
            request.path,
            refund,
            200
        )
        
        return jsonify(refund), 200
        
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error processing refund: {e}")
        return jsonify({'error': 'Refund processing failed'}), 500

@payments_bp.route('/payments/<int:payment_id>/receipt', methods=['GET'])
def generate_receipt(payment_id):
    """Generate receipt for a payment"""
    try:
        receipt = PaymentService.generate_receipt(payment_id)
        return jsonify(receipt), 200
        
    except ValueError as e:
        return jsonify({'error': str(e)}), 404
    except Exception as e:
        logger.error(f"Error generating receipt: {e}")
        return jsonify({'error': 'Receipt generation failed'}), 500