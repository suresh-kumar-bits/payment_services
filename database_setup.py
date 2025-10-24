import csv
import os
import psycopg2
from dotenv import load_dotenv
from datetime import datetime
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Configuration ---
load_dotenv()

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_NAME = os.getenv("DB_NAME", "postgres")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASS = os.getenv("DB_PASS", "Superb#915")
DB_PORT = os.getenv("DB_PORT", "5433")
PAYMENTS_CSV = "rhfd_payments.csv"

# --- SQL Schema (Task 2: Database Design) ---
CREATE_TABLES_SQL = """
-- Drop existing tables if needed (for development)
DROP TABLE IF EXISTS idempotency_keys CASCADE;
DROP TABLE IF EXISTS payment_receipts CASCADE;
DROP TABLE IF EXISTS payment_refunds CASCADE;
DROP TABLE IF EXISTS payments CASCADE;

-- Core Payments Table
CREATE TABLE payments (
    payment_id INTEGER PRIMARY KEY,
    trip_id INTEGER NOT NULL,
    amount NUMERIC(10, 2) NOT NULL,
    method VARCHAR(50) NOT NULL CHECK (method IN ('CARD', 'WALLET', 'UPI', 'CASH')),
    status VARCHAR(50) NOT NULL CHECK (status IN ('SUCCESS', 'FAILED', 'PENDING', 'REFUNDED')),
    reference VARCHAR(100) UNIQUE NOT NULL,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()
);

-- Idempotency Keys Table (Critical for Task 3)
CREATE TABLE idempotency_keys (
    key_hash VARCHAR(64) PRIMARY KEY,
    request_path VARCHAR(255) NOT NULL,
    response_status INTEGER,
    response_data JSONB,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
    expires_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW() + INTERVAL '24 hours'
);

-- Payment Refunds Table (for tracking refund history)
CREATE TABLE payment_refunds (
    refund_id SERIAL PRIMARY KEY,
    payment_id INTEGER NOT NULL REFERENCES payments(payment_id),
    refund_amount NUMERIC(10, 2) NOT NULL,
    reason TEXT,
    status VARCHAR(50) DEFAULT 'PENDING',
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()
);

-- Payment Receipts Table (for receipt generation)
CREATE TABLE payment_receipts (
    receipt_id SERIAL PRIMARY KEY,
    payment_id INTEGER NOT NULL REFERENCES payments(payment_id),
    receipt_number VARCHAR(100) UNIQUE NOT NULL,
    generated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
    receipt_data JSONB
);

-- Create indexes for better performance
CREATE INDEX idx_payments_trip_id ON payments(trip_id);
CREATE INDEX idx_payments_status ON payments(status);
CREATE INDEX idx_payments_method ON payments(method);
CREATE INDEX idx_payments_created_at ON payments(created_at);
CREATE INDEX idx_idempotency_expires ON idempotency_keys(expires_at);
CREATE INDEX idx_refunds_payment_id ON payment_refunds(payment_id);

-- Create a view for payment analytics
CREATE OR REPLACE VIEW payment_analytics AS
SELECT 
    DATE(created_at) as payment_date,
    method,
    status,
    COUNT(*) as payment_count,
    SUM(amount) as total_amount,
    AVG(amount) as avg_amount,
    MIN(amount) as min_amount,
    MAX(amount) as max_amount
FROM payments
GROUP BY DATE(created_at), method, status
ORDER BY payment_date DESC;

-- Function to clean up expired idempotency keys
CREATE OR REPLACE FUNCTION cleanup_expired_idempotency_keys()
RETURNS void AS $$
BEGIN
    DELETE FROM idempotency_keys WHERE expires_at < NOW();
END;
$$ LANGUAGE plpgsql;
"""

def create_connection():
    """Connects to the PostgreSQL database with retry logic."""
    max_retries = 5
    retry_delay = 2
    
    for attempt in range(max_retries):
        try:
            conn = psycopg2.connect(
                host=DB_HOST,
                database=DB_NAME,
                user=DB_USER,
                password=DB_PASS,
                port=DB_PORT
            )
            logger.info("✅ Successfully connected to PostgreSQL")
            return conn
        except psycopg2.OperationalError as e:
            if attempt < max_retries - 1:
                logger.warning(f"Database connection attempt {attempt + 1} failed. Retrying in {retry_delay} seconds...")
                import time
                time.sleep(retry_delay)
            else:
                logger.error(f"❌ Failed to connect after {max_retries} attempts")
                logger.error(f"Error: {e}")
                return None
        except Exception as e:
            logger.error(f"❌ Unexpected error: {e}")
            return None

def setup_database(conn):
    """Creates the tables and loads initial data."""
    cursor = conn.cursor()
    try:
        # Create Tables
        logger.info("Creating database schema...")
        cursor.execute(CREATE_TABLES_SQL)
        logger.info("✅ Database schema created successfully")
        
        # Check if data already exists
        cursor.execute("SELECT COUNT(*) FROM payments")
        existing_count = cursor.fetchone()[0]
        
        if existing_count > 0:
            logger.info(f"ℹ️ Database already contains {existing_count} payment records")
            conn.commit()
            return
        
        # Load Data
        if not os.path.exists(PAYMENTS_CSV):
            logger.warning(f"⚠️ CSV file '{PAYMENTS_CSV}' not found. Skipping data load.")
            conn.commit()
            return

        logger.info(f"Loading data from {PAYMENTS_CSV}...")
        with open(PAYMENTS_CSV, 'r', newline='') as f:
            reader = csv.DictReader(f)
            
            insert_query = """
            INSERT INTO payments 
            (payment_id, trip_id, amount, method, status, reference, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (payment_id) DO NOTHING;
            """
            
            rows_inserted = 0
            for row in reader:
                # Parse the datetime string
                created_at = None
                if row['created_at']:
                    try:
                        created_at = datetime.strptime(row['created_at'], '%Y-%m-%d %H:%M:%S')
                    except ValueError:
                        created_at = datetime.now()
                
                cursor.execute(insert_query, (
                    int(row['payment_id']),
                    int(row['trip_id']),
                    float(row['amount']),
                    row['method'],
                    row['status'],
                    row['reference'],
                    created_at
                ))
                rows_inserted += 1
            
            conn.commit()
            logger.info(f"✅ Successfully loaded {rows_inserted} payment records")
            
            # Display statistics
            cursor.execute("""
                SELECT 
                    COUNT(*) as total,
                    COUNT(CASE WHEN status = 'SUCCESS' THEN 1 END) as success,
                    COUNT(CASE WHEN status = 'FAILED' THEN 1 END) as failed,
                    COUNT(CASE WHEN status = 'PENDING' THEN 1 END) as pending
                FROM payments
            """)
            stats = cursor.fetchone()
            logger.info(f"📊 Payment Statistics: Total={stats[0]}, Success={stats[1]}, Failed={stats[2]}, Pending={stats[3]}")
            
            # Method distribution
            cursor.execute("""
                SELECT method, COUNT(*) as count
                FROM payments
                GROUP BY method
                ORDER BY count DESC
            """)
            method_stats = cursor.fetchall()
            logger.info("📊 Payment Methods:")
            for method, count in method_stats:
                logger.info(f"   - {method}: {count}")

    except Exception as e:
        logger.error(f"❌ Error during setup: {e}")
        conn.rollback()
        raise
    finally:
        cursor.close()

def verify_setup(conn):
    """Verify the database setup is correct."""
    cursor = conn.cursor()
    try:
        # Check tables exist
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_type = 'BASE TABLE'
        """)
        tables = [row[0] for row in cursor.fetchall()]
        
        required_tables = ['payments', 'idempotency_keys', 'payment_refunds', 'payment_receipts']
        missing_tables = set(required_tables) - set(tables)
        
        if missing_tables:
            logger.error(f"❌ Missing tables: {missing_tables}")
            return False
        
        logger.info(f"✅ All required tables exist: {required_tables}")
        
        # Check indexes
        cursor.execute("""
            SELECT indexname 
            FROM pg_indexes 
            WHERE schemaname = 'public'
        """)
        indexes = [row[0] for row in cursor.fetchall()]
        logger.info(f"✅ Created {len(indexes)} indexes for performance optimization")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Verification failed: {e}")
        return False
    finally:
        cursor.close()

def add_sample_idempotency_keys(conn):
    """Add some sample idempotency keys for testing."""
    cursor = conn.cursor()
    try:
        # Add a test idempotency key
        test_key = {
            "key_hash": "test_hash_12345",
            "request_path": "/v1/payments/charge",
            "response_status": 201,
            "response_data": '{"payment_id": 999, "status": "SUCCESS", "message": "Test payment"}'
        }
        
        cursor.execute("""
            INSERT INTO idempotency_keys (key_hash, request_path, response_status, response_data)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (key_hash) DO NOTHING
        """, (test_key["key_hash"], test_key["request_path"], 
              test_key["response_status"], test_key["response_data"]))
        
        conn.commit()
        logger.info("✅ Added sample idempotency key for testing")
        
    except Exception as e:
        logger.warning(f"Could not add sample idempotency key: {e}")
        conn.rollback()
    finally:
        cursor.close()

if __name__ == "__main__":
    logger.info("🚀 Starting Payment Service Database Setup")
    logger.info("-" * 50)
    
    conn = create_connection()
    if conn:
        try:
            setup_database(conn)
            
            if verify_setup(conn):
                add_sample_idempotency_keys(conn)
                logger.info("-" * 50)
                logger.info("✅ Database setup completed successfully!")
                logger.info("🚀 Payment Service is ready for API operations")
            else:
                logger.error("❌ Database verification failed")
                
        finally:
            conn.close()
    else:
        logger.error("❌ Could not establish database connection")
        logger.error("Please ensure PostgreSQL is running and credentials are correct")
        exit(1)