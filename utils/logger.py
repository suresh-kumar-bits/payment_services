# utils/logger.py - Logging Configuration
import logging
import sys
from datetime import datetime
import json
from flask import request  # <-- IMPORT 'request' TO GET HEADERS

class JsonFormatter(logging.Formatter):
    """JSON formatter for structured logging"""
    
    def format(self, record):
        log_obj = {
            'timestamp': datetime.utcnow().isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno
        }
        
        # --- THIS IS THE NEW CODE ---
        # Add correlation ID from request header if it exists
        try:
            log_obj['correlation_id'] = request.headers.get('X-Correlation-ID', 'not-set')
        except RuntimeError:
            # This handles logs outside of a request context (e.g., app startup)
            log_obj['correlation_id'] = 'app-startup'
        # --- END OF NEW CODE ---

        if hasattr(record, 'extra'):
            log_obj.update(record.extra)
        
        if record.exc_info:
            log_obj['exception'] = self.formatException(record.exc_info)
        
        return json.dumps(log_obj)

def get_logger(name=None):
    """Get a configured logger instance"""
    from config import Config
    
    logger = logging.getLogger(name or __name__)
    
    if not logger.handlers:
        # Check if LOG_LEVEL is set in Config, default to INFO
        log_level = getattr(Config, 'LOG_LEVEL', 'INFO').upper()
        logger.setLevel(getattr(logging, log_level, logging.INFO))
        
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        
        # Use JSON formatter for production, simple for development
        if Config.DEBUG:
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
        else:
            formatter = JsonFormatter()
        
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
    
    return logger