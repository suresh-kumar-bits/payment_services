# app.py - Main Application Entry Point (Simplified)
from flask import Flask, jsonify
from flask_cors import CORS
from datetime import datetime
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import Config
from utils.logger import get_logger
from api.routes.health import health_bp
from api.routes.payments import bp as payments_bp
from api.routes.metrics import metrics_bp
from api.middleware.error_handler import register_error_handlers

# Initialize logger
logger = get_logger(__name__)

def create_app():
    """Application factory pattern"""
    
    # Create Flask app
    app = Flask(__name__)
    app.config.from_object(Config)
    
    # Enable CORS
    CORS(app, resources={r"/api/*": {"origins": "*"}})
    
    # Register blueprints
    app.register_blueprint(health_bp)
    app.register_blueprint(payments_bp)
    app.register_blueprint(metrics_bp)
    
    # Register error handlers
    register_error_handlers(app)
    
    # Root endpoint
    @app.route('/')
    def root():
        return jsonify({
            'service': Config.SERVICE_NAME,
            'version': Config.SERVICE_VERSION,
            'status': 'running',
            'timestamp': datetime.utcnow().isoformat(),
            'endpoints': {
                'health': '/health',
                'payments': '/v1/payments',
                'charge': '/v1/payments/charge',
                'metrics': '/metrics'
            }
        })
    
    # Log startup
    logger.info(f"{Config.SERVICE_NAME} v{Config.SERVICE_VERSION} initialized")
    
    return app

# Create app instance
app = create_app()

if __name__ == '__main__':
    # Run the application
    app.run(
        host='0.0.0.0',
        port=Config.SERVICE_PORT,
        debug=Config.DEBUG
    )