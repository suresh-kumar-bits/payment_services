# api/routes/metrics.py - Metrics Routes
from flask import Blueprint, jsonify
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from services.payment_service import PaymentService
from utils.logger import get_logger

logger = get_logger(__name__)
metrics_bp = Blueprint('metrics', __name__)

@metrics_bp.route('/metrics', methods=['GET'])
def get_metrics():
    """Get service metrics for monitoring"""
    try:
        metrics = PaymentService.get_metrics()
        return jsonify(metrics), 200
        
    except Exception as e:
        logger.error(f"Error fetching metrics: {e}")
        return jsonify({'error': 'Failed to retrieve metrics'}), 500

@metrics_bp.route('/metrics/prometheus', methods=['GET'])
def get_prometheus_metrics():
    """Get metrics in Prometheus format"""
    try:
        metrics = PaymentService.get_metrics()
        
        # Format metrics for Prometheus
        prometheus_format = []
        
        # Payment counts by status
        for status, count in metrics.get('payments_by_status', {}).items():
            prometheus_format.append(
                f'payment_total{{status="{status}"}} {count}'
            )
        
        # Payment counts by method
        for method, count in metrics.get('payments_by_method', {}).items():
            prometheus_format.append(
                f'payment_method_total{{method="{method}"}} {count}'
            )
        
        # Average payment amount
        avg_amount = metrics.get('average_payment_amount', 0)
        prometheus_format.append(f'payment_average_amount {avg_amount}')
        
        # Total revenue
        total_revenue = metrics.get('total_revenue', 0)
        prometheus_format.append(f'payment_total_revenue {total_revenue}')
        
        return '\n'.join(prometheus_format), 200, {'Content-Type': 'text/plain'}
        
    except Exception as e:
        logger.error(f"Error formatting Prometheus metrics: {e}")
        return 'Error generating metrics', 500