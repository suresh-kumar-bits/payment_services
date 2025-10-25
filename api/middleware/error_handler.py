# api/middleware/error_handler.py - Error Handling Middleware
from flask import jsonify
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from utils.logger import get_logger

logger = get_logger(__name__)

def register_error_handlers(app):
    """Register error handlers for the application"""
    
    @app.errorhandler(400)
    def bad_request(error):
        """Handle bad request errors"""
        return jsonify({
            'error': 'Bad Request',
            'message': str(error),
            'status_code': 400
        }), 400
    
    @app.errorhandler(404)
    def not_found(error):
        """Handle not found errors"""
        return jsonify({
            'error': 'Not Found',
            'message': 'The requested resource was not found',
            'status_code': 404
        }), 404
    
    @app.errorhandler(429)
    def rate_limit_exceeded(error):
        """Handle rate limit errors"""
        return jsonify({
            'error': 'Too Many Requests',
            'message': 'Rate limit exceeded. Please try again later.',
            'status_code': 429
        }), 429
    
    @app.errorhandler(500)
    def internal_server_error(error):
        """Handle internal server errors"""
        logger.error(f"Internal server error: {error}")
        return jsonify({
            'error': 'Internal Server Error',
            'message': 'An unexpected error occurred',
            'status_code': 500
        }), 500
    
    @app.errorhandler(503)
    def service_unavailable(error):
        """Handle service unavailable errors"""
        return jsonify({
            'error': 'Service Unavailable',
            'message': 'The service is temporarily unavailable',
            'status_code': 503
        }), 503
    
    @app.errorhandler(Exception)
    def handle_unexpected_error(error):
        """Handle all other unexpected errors"""
        logger.error(f"Unexpected error: {error}")
        return jsonify({
            'error': 'Unexpected Error',
            'message': 'An unexpected error occurred',
            'status_code': 500
        }), 500