# services/payment_service.py - Business Logic Layer
import json
import hashlib
from datetime import datetime
from typing import Dict, Optional, Tuple, List
import psycopg2.extras
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database.connection import db
from utils.logger import get_logger
from config import Config

logger = get_logger(__name__)

class PaymentService:
    """Core payment business logic"""
    
    @staticmethod
    def calculate_fare(trip_data: Dict) -> float:
        """
        Calculate fare based on trip data
        
        Args:
            trip_data: Dictionary containing trip information
        
        Returns:
            Calculated fare amount
        """
        base_fare = Config.BASE_FARE
        distance = trip_data.get('distance', 0)
        rate_per_km = Config.RATE_PER_KM
        surge_multiplier = trip_data.get('surge_multiplier', 1.0)
        
        fare = (base_fare + (distance * rate_per_km)) * surge_multiplier
        return round(fare, 2)
    
    @staticmethod
    def get_all_payments(filters: Dict = None) -> Tuple[List[Dict], int]:
        """
        Get all payments with optional filtering
        
        Args:
            filters: Dictionary containing filter parameters
        
        Returns:
            Tuple of (payments list, total count)
        """
        filters = filters or {}
        
        query = "SELECT * FROM payments WHERE 1=1"
        params = []
        
        # Build query with filters
        if filters.get('trip_id'):
            query += " AND trip_id = %s"
            params.append(filters['trip_id'])
        
        if filters.get('status'):
            query += " AND status = %s"
            params.append(filters['status'])
        
        if filters.get('method'):
            query += " AND method = %s"
            params.append(filters['method'])
        
        # Add pagination
        query += " ORDER BY created_at DESC LIMIT %s OFFSET %s"
        params.extend([
            filters.get('limit', 100),
            filters.get('offset', 0)
        ])
        
        try:
            payments = db.execute_query_dict(query, params)
            
            # Convert datetime to string for JSON serialization
            for payment in payments:
                if payment.get('created_at'):
                    payment['created_at'] = payment['created_at'].isoformat()
                if payment.get('updated_at'):
                    payment['updated_at'] = payment['updated_at'].isoformat()
            
            return payments, len(payments)
        except Exception as e:
            logger.error(f"Error fetching payments: {e}")
            raise
    
    @staticmethod
    def get_payment_by_id(payment_id: int) -> Optional[Dict]:
        """Get a specific payment by ID"""
        try:
            query = "SELECT * FROM payments WHERE payment_id = %s"
            payment = db.execute_query_dict(query, (payment_id,), fetch_one=True)
            
            if payment and payment.get('created_at'):
                payment['created_at'] = payment['created_at'].isoformat()
            
            return payment
        except Exception as e:
            logger.error(f"Error fetching payment {payment_id}: {e}")
            raise
    
    @staticmethod
    def create_payment(payment_data: Dict) -> Dict:
        """
        Create a new payment record
        
        Args:
            payment_data: Payment information
        
        Returns:
            Created payment record
        """
        try:
            # Generate reference
            reference = f"PAY-{datetime.utcnow().strftime('%Y%m%d')}-{payment_data.get('idempotency_hash', '')[:8]}"
            
            # Get next payment_id
            with db.get_db_cursor() as cursor:
                cursor.execute("SELECT COALESCE(MAX(payment_id), 0) + 1 FROM payments")
                payment_id = cursor.fetchone()[0]
            
            # Insert payment
            query = """
                INSERT INTO payments 
                (payment_id, trip_id, amount, method, status, reference, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING *
            """
            
            with db.get_db_cursor(commit=True, cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                cursor.execute(query, (
                    payment_id,
                    payment_data['trip_id'],
                    payment_data['amount'],
                    payment_data['method'],
                    payment_data['status'],
                    reference,
                    datetime.utcnow()
                ))
                payment = cursor.fetchone()
            
            logger.info(f"Payment created: {payment_id} for trip {payment_data['trip_id']}")
            
            return {
                'payment_id': payment['payment_id'],
                'trip_id': payment['trip_id'],
                'amount': float(payment['amount']),
                'method': payment['method'],
                'status': payment['status'],
                'reference': payment['reference'],
                'created_at': payment['created_at'].isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error creating payment: {e}")
            raise
    
    @staticmethod
    def process_refund(payment_id: int, refund_amount: Optional[float] = None) -> Dict:
        """
        Process a refund for a payment
        
        Args:
            payment_id: Payment ID to refund
            refund_amount: Optional partial refund amount
        
        Returns:
            Refund information
        """
        try:
            # Get original payment
            payment = PaymentService.get_payment_by_id(payment_id)
            if not payment:
                raise ValueError(f"Payment {payment_id} not found")
            
            if payment['status'] != 'SUCCESS':
                raise ValueError(f"Can only refund successful payments")
            
            # Use original amount if refund amount not specified
            refund_amount = refund_amount or payment['amount']
            
            # Update payment status
            with db.get_db_cursor(commit=True) as cursor:
                cursor.execute(
                    "UPDATE payments SET status = 'REFUNDED', updated_at = %s WHERE payment_id = %s",
                    (datetime.utcnow(), payment_id)
                )
                
                # Record refund in refunds table
                cursor.execute(
                    """INSERT INTO payment_refunds (payment_id, refund_amount, status, created_at)
                       VALUES (%s, %s, 'SUCCESS', %s)""",
                    (payment_id, refund_amount, datetime.utcnow())
                )
            
            logger.info(f"Refund processed for payment {payment_id}: ${refund_amount}")
            
            return {
                'payment_id': payment_id,
                'refund_amount': float(refund_amount),
                'status': 'REFUNDED',
                'timestamp': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error processing refund: {e}")
            raise
    
    @staticmethod
    def generate_receipt(payment_id: int) -> Dict:
        """Generate a receipt for a payment"""
        try:
            payment = PaymentService.get_payment_by_id(payment_id)
            if not payment:
                raise ValueError(f"Payment {payment_id} not found")
            
            receipt = {
                'receipt_id': f"RCP-{payment['reference']}",
                'payment_id': payment['payment_id'],
                'trip_id': payment['trip_id'],
                'amount': float(payment['amount']),
                'method': payment['method'],
                'status': payment['status'],
                'reference': payment['reference'],
                'created_at': payment.get('created_at'),
                'generated_at': datetime.utcnow().isoformat()
            }
            
            # Store receipt in database
            with db.get_db_cursor(commit=True) as cursor:
                cursor.execute(
                    """INSERT INTO payment_receipts (payment_id, receipt_number, receipt_data, generated_at)
                       VALUES (%s, %s, %s, %s)
                       ON CONFLICT (payment_id) DO UPDATE SET generated_at = EXCLUDED.generated_at""",
                    (payment_id, receipt['receipt_id'], json.dumps(receipt), datetime.utcnow())
                )
            
            return receipt
            
        except Exception as e:
            logger.error(f"Error generating receipt: {e}")
            raise
    
    @staticmethod
    def get_metrics() -> Dict:
        """Get service metrics"""
        try:
            metrics = {}
            
            # Payment counts by status
            query = "SELECT status, COUNT(*) as count FROM payments GROUP BY status"
            status_results = db.execute_query(query)
            metrics['payments_by_status'] = dict(status_results)
            
            # Payment counts by method
            query = "SELECT method, COUNT(*) as count FROM payments GROUP BY method"
            method_results = db.execute_query(query)
            metrics['payments_by_method'] = dict(method_results)
            
            # Average payment amount
            query = "SELECT AVG(amount) FROM payments WHERE status = 'SUCCESS'"
            avg_result = db.execute_query(query)[0][0]
            metrics['average_payment_amount'] = float(avg_result) if avg_result else 0
            
            # Total revenue
            query = "SELECT SUM(amount) FROM payments WHERE status = 'SUCCESS'"
            total_result = db.execute_query(query)[0][0]
            metrics['total_revenue'] = float(total_result) if total_result else 0
            
            metrics['timestamp'] = datetime.utcnow().isoformat()
            
            return metrics
            
        except Exception as e:
            logger.error(f"Error fetching metrics: {e}")
            raise