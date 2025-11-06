# database_setup.py - Database Setup and Initialization
import csv
import os
import psycopg2
from datetime import datetime
import logging
from config import Config

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Use configuration from config.py
DB_HOST = Config.DB_HOST
DB_NAME = Config.DB_NAME
DB_USER = Config.DB_USER
DB_PASS = Config.DB_PASS
DB_PORT = Config.DB_PORT
# Allow the CSV path to be provided via environment variable so the K8s Job
# can mount the CSV at /data/rhfd_payments.csv and set PAYMENTS_CSV_PATH.
PAYMENTS_CSV = os.getenv('PAYMENTS_CSV_PATH', 'rhfd_payments.csv')

# If not found at the configured path, also try the common mount path used in the
# k8s Job (mounted ConfigMap at /data/rhfd_payments.csv).
ALT_CSV_PATH = '/data/rhfd_payments.csv'
if not os.path.exists(PAYMENTS_CSV) and os.path.exists(ALT_CSV_PATH):
    logger.info(f"PAYMENTS_CSV not found at {PAYMENTS_CSV}; using {ALT_CSV_PATH}")
    PAYMENTS_CSV = ALT_CSV_PATH

# SQL Schema
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

-- Idempotency Keys Table
CREATE TABLE idempotency_keys (
    key_hash VARCHAR(64) PRIMARY KEY,
    request_path VARCHAR(255) NOT NULL,
    response_status INTEGER,
    response_data JSONB,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
    expires_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW() + INTERVAL '24 hours'
);

-- Payment Refunds Table
CREATE TABLE payment_refunds (
    refund_id SERIAL PRIMARY KEY,
    payment_id INTEGER NOT NULL REFERENCES payments(payment_id),
    refund_amount NUMERIC(10, 2) NOT NULL,
    reason TEXT,
    status VARCHAR(50) DEFAULT 'PENDING',
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()
);

-- Payment Receipts Table
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
            logger.info("Successfully connected to PostgreSQL")
            logger.info(f"   Host: {DB_HOST}:{DB_PORT}, Database: {DB_NAME}")
            return conn
        except psycopg2.OperationalError as e:
            if attempt < max_retries - 1:
                logger.warning(f"Connection attempt {attempt + 1} failed. Retrying in {retry_delay} seconds...")
                import time
                time.sleep(retry_delay)
            else:
                logger.error(f"Failed to connect after {max_retries} attempts")
                logger.error(f"Error: {e}")
                return None
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return None

def setup_database(conn):
    """Creates the tables and loads initial data."""
    cursor = conn.cursor()
    try:
        # Create Tables
        logger.info("Creating database schema...")
        cursor.execute(CREATE_TABLES_SQL)
        logger.info("Database schema created successfully")
        
        # Check if data already exists
        cursor.execute("SELECT COUNT(*) FROM payments")
        existing_count = cursor.fetchone()[0]
        
        if existing_count > 0:
            logger.info(f"Database already contains {existing_count} payment records")
            conn.commit()
            return
        
        # Load Data
        if not os.path.exists(PAYMENTS_CSV):
            logger.warning(f"Warning: CSV file '{PAYMENTS_CSV}' not found. Skipping data load.")
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
            logger.info(f"Successfully loaded {rows_inserted} payment records")
            
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
            logger.info(f"Payment Statistics: Total={stats[0]}, Success={stats[1]}, Failed={stats[2]}, Pending={stats[3]}")

    except Exception as e:
        logger.error(f"Error during setup: {e}")
        conn.rollback()
        raise
    finally:
        cursor.close()

if __name__ == "__main__":
    logger.info("Starting Payment Service Database Setup")
    logger.info("-" * 50)
    
    conn = create_connection()
    if conn:
        try:
            setup_database(conn)
            logger.info("-" * 50)
            logger.info("Database setup completed successfully!")
            logger.info("Payment Service is ready for API operations")
        finally:
            conn.close()
    else:
        logger.error("Could not establish database connection")
        logger.error("Please ensure PostgreSQL is running on port 5433")
        exit(1)