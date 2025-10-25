# api/routes/health.py - Health Check Routes
from flask import Blueprint, jsonify
from datetime import datetime
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from database.connection import db
from config import Config
from utils.logger import get_logger

logger = get_logger(__name__)
health_bp = Blueprint('health', __name__)

@health_bp.route('/health', methods=['GET'])
def health_check():
    """Service health check endpoint"""
    health_status = {
        'service': Config.SERVICE_NAME,
        'version': Config.SERVICE_VERSION,
        'status': 'UP',
        'timestamp': datetime.utcnow().isoformat()
    }
    
    # Check database connectivity
    try:
        with db.get_db_cursor() as cursor:
            cursor.execute("SELECT 1")
            health_status['database_status'] = 'UP'
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        health_status['database_status'] = 'DOWN'
        health_status['status'] = 'DEGRADED'
    
    # Check external services (optional)
    health_status['dependencies'] = check_dependencies()
    
    status_code = 200 if health_status['database_status'] == 'UP' else 503
    return jsonify(health_status), status_code

@health_bp.route('/ready', methods=['GET'])
def readiness_check():
    """Kubernetes readiness probe"""
    try:
        # Check if service is ready to accept traffic
        with db.get_db_cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM payments")
            return jsonify({'ready': True}), 200
    except:
        return jsonify({'ready': False}), 503

@health_bp.route('/live', methods=['GET'])
def liveness_check():
    """Kubernetes liveness probe"""
    # Simple check to see if service is alive
    return jsonify({'alive': True}), 200

def check_dependencies():
    """Check status of dependent services"""
    dependencies = {}
    
    # You can add checks for external services here
    # For now, we'll just return a placeholder
    dependencies['trip_service'] = 'UNKNOWN'
    dependencies['notification_service'] = 'UNKNOWN'
    
    return dependencies