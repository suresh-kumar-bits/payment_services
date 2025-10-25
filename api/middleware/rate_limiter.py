# api/middleware/rate_limiter.py - Rate Limiting Middleware
import time
from functools import wraps
from flask import jsonify, request
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from utils.logger import get_logger

logger = get_logger(__name__)

class RateLimiter:
    """Simple in-memory rate limiter"""
    
    def __init__(self):
        self.calls = {}
    
    def is_allowed(self, key: str, max_calls: int, time_window: int) -> bool:
        """
        Check if request is allowed based on rate limit
        
        Args:
            key: Unique identifier (e.g., IP address)
            max_calls: Maximum number of calls allowed
            time_window: Time window in seconds
        
        Returns:
            True if request is allowed, False otherwise
        """
        now = time.time()
        
        # Clean old entries for this key
        if key in self.calls:
            self.calls[key] = [
                call_time for call_time in self.calls[key]
                if call_time > now - time_window
            ]
        else:
            self.calls[key] = []
        
        # Check if limit exceeded
        if len(self.calls[key]) >= max_calls:
            return False
        
        # Add current call
        self.calls[key].append(now)
        return True
    
    def cleanup(self):
        """Clean up old entries from all keys"""
        now = time.time()
        for key in list(self.calls.keys()):
            self.calls[key] = [
                call_time for call_time in self.calls[key]
                if call_time > now - 3600  # Keep last hour
            ]
            if not self.calls[key]:
                del self.calls[key]

# Global rate limiter instance
limiter = RateLimiter()

def rate_limit(max_calls=10, time_window=60):
    """
    Decorator for rate limiting endpoints
    
    Args:
        max_calls: Maximum number of calls allowed
        time_window: Time window in seconds
    """
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            # Use IP address as key
            key = request.remote_addr or 'unknown'
            
            if not limiter.is_allowed(key, max_calls, time_window):
                logger.warning(f"Rate limit exceeded for {key}")
                return jsonify({
                    'error': 'Rate limit exceeded',
                    'message': f'Maximum {max_calls} requests per {time_window} seconds'
                }), 429
            
            return f(*args, **kwargs)
        return wrapper
    return decorator