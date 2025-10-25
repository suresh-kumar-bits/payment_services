# utils/helpers.py - Helper Utility Functions
from datetime import datetime
import hashlib
import uuid

def generate_reference_number(prefix="PAY"):
    """
    Generate unique reference number
    
    Args:
        prefix: Prefix for the reference number
    
    Returns:
        Unique reference string
    """
    timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S')
    unique_id = str(uuid.uuid4())[:8].upper()
    return f"{prefix}-{timestamp}-{unique_id}"

def validate_payment_method(method):
    """
    Validate payment method
    
    Args:
        method: Payment method string
    
    Returns:
        True if valid, False otherwise
    """
    valid_methods = ['CARD', 'WALLET', 'UPI', 'CASH']
    return method in valid_methods

def validate_payment_status(status):
    """
    Validate payment status
    
    Args:
        status: Payment status string
    
    Returns:
        True if valid, False otherwise
    """
    valid_statuses = ['SUCCESS', 'FAILED', 'PENDING', 'REFUNDED']
    return status in valid_statuses

def format_currency(amount):
    """
    Format amount as currency
    
    Args:
        amount: Numeric amount
    
    Returns:
        Formatted currency string
    """
    return f"${amount:.2f}"

def calculate_processing_fee(amount, method):
    """
    Calculate payment processing fee based on method
    
    Args:
        amount: Transaction amount
        method: Payment method
    
    Returns:
        Processing fee amount
    """
    fees = {
        'CARD': 0.029,  # 2.9%
        'WALLET': 0.015,  # 1.5%
        'UPI': 0.005,  # 0.5%
        'CASH': 0.0  # No fee for cash
    }
    
    fee_rate = fees.get(method, 0.0)
    return round(amount * fee_rate, 2)

def is_valid_trip_id(trip_id):
    """
    Validate trip ID
    
    Args:
        trip_id: Trip ID to validate
    
    Returns:
        True if valid, False otherwise
    """
    return isinstance(trip_id, int) and trip_id > 0

def parse_datetime_string(date_string):
    """
    Parse datetime string in various formats
    
    Args:
        date_string: String representation of datetime
    
    Returns:
        datetime object or None if parsing fails
    """
    formats = [
        '%Y-%m-%d %H:%M:%S',
        '%Y-%m-%dT%H:%M:%S',
        '%Y-%m-%d',
        '%d/%m/%Y %H:%M:%S',
        '%d-%m-%Y %H:%M:%S'
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(date_string, fmt)
        except ValueError:
            continue
    
    return None