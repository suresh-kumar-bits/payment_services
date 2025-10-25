# services/idempotency_service.py - Idempotency Management
import hashlib
import json
from datetime import datetime
from typing import Optional, Tuple
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database.connection import db
from utils.logger import get_logger

logger = get_logger(__name__)

class IdempotencyService:
    """Handle idempotency for payment operations"""
    
    @staticmethod
    def generate_hash(key: str) -> str:
        """Generate SHA256 hash for idempotency key"""
        return hashlib.sha256(key.encode()).hexdigest()
    
    @staticmethod
    def check_idempotency(key_hash: str) -> Optional[Tuple[dict, int]]:
        """
        Check if an idempotency key exists
        
        Args:
            key_hash: Hashed idempotency key
        
        Returns:
            Tuple of (response_data, status_code) if exists, None otherwise
        """
        try:
            query = """
                SELECT response_data, response_status 
                FROM idempotency_keys 
                WHERE key_hash = %s AND expires_at > NOW()
            """
            
            with db.get_db_cursor() as cursor:
                cursor.execute(query, (key_hash,))
                result = cursor.fetchone()
                
                if result:
                    response_data = result[0] if isinstance(result[0], dict) else json.loads(result[0])
                    status_code = result[1]
                    logger.info(f"Idempotency hit for key hash: {key_hash[:16]}...")
                    return response_data, status_code
                
                return None
                
        except Exception as e:
            logger.error(f"Error checking idempotency: {e}")
            return None
    
    @staticmethod
    def store_idempotency(key_hash: str, request_path: str, 
                         response_data: dict, status_code: int) -> bool:
        """
        Store idempotency key with response
        
        Args:
            key_hash: Hashed idempotency key
            request_path: API endpoint path
            response_data: Response data to cache
            status_code: HTTP status code
        
        Returns:
            True if stored successfully
        """
        try:
            query = """
                INSERT INTO idempotency_keys 
                (key_hash, request_path, response_status, response_data, created_at, expires_at)
                VALUES (%s, %s, %s, %s, %s, NOW() + INTERVAL '24 hours')
                ON CONFLICT (key_hash) DO NOTHING
            """
            
            with db.get_db_cursor(commit=True) as cursor:
                cursor.execute(query, (
                    key_hash,
                    request_path,
                    status_code,
                    json.dumps(response_data),
                    datetime.utcnow()
                ))
                
                logger.info(f"Stored idempotency key: {key_hash[:16]}...")
                return True
                
        except Exception as e:
            logger.error(f"Error storing idempotency key: {e}")
            return False
    
    @staticmethod
    def cleanup_expired_keys() -> int:
        """
        Clean up expired idempotency keys
        
        Returns:
            Number of keys deleted
        """
        try:
            query = "DELETE FROM idempotency_keys WHERE expires_at < NOW()"
            
            with db.get_db_cursor(commit=True) as cursor:
                cursor.execute(query)
                deleted_count = cursor.rowcount
                
                if deleted_count > 0:
                    logger.info(f"Cleaned up {deleted_count} expired idempotency keys")
                
                return deleted_count
                
        except Exception as e:
            logger.error(f"Error cleaning up idempotency keys: {e}")
            return 0