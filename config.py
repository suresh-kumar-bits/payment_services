# config.py - Configuration Management
import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    """Application configuration"""
    
    # Flask Configuration
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
    DEBUG = os.getenv('DEBUG', 'False').lower() == 'true'
    TESTING = os.getenv('TESTING', 'False').lower() == 'true'
    
    # Service Configuration
    SERVICE_NAME = os.getenv('SERVICE_NAME', 'payment-service')
    SERVICE_PORT = int(os.getenv('SERVICE_PORT', 8082))
    SERVICE_VERSION = os.getenv('SERVICE_VERSION', '1.0.0')
    API_PREFIX = os.getenv('API_PREFIX', '/v1')
    
    # Database Configuration
    DB_HOST = os.getenv('DB_HOST', 'localhost')
    DB_PORT = int(os.getenv('DB_PORT', 5433))
    DB_NAME = os.getenv('DB_NAME', 'postgres')
    DB_USER = os.getenv('DB_USER', 'postgres')
    DB_PASS = os.getenv('DB_PASS', 'Superb#915')
    
    # Inter-service URLs
    TRIP_SERVICE_URL = os.getenv('TRIP_SERVICE_URL', 'http://trip-service:8081')
    NOTIFICATION_SERVICE_URL = os.getenv('NOTIFICATION_SERVICE_URL', 'http://notification-service:8084')
    RIDER_SERVICE_URL = os.getenv('RIDER_SERVICE_URL', 'http://rider-service:8079')
    DRIVER_SERVICE_URL = os.getenv('DRIVER_SERVICE_URL', 'http://driver-service:8080')
    
    # Rate Limiting
    RATE_LIMIT_ENABLED = os.getenv('RATE_LIMIT_ENABLED', 'True').lower() == 'true'
    RATE_LIMIT_DEFAULT = os.getenv('RATE_LIMIT_DEFAULT', '100 per hour')
    RATE_LIMIT_CHARGE = os.getenv('RATE_LIMIT_CHARGE', '50 per hour')
    RATE_LIMIT_REFUND = os.getenv('RATE_LIMIT_REFUND', '20 per hour')
    
    # Business Rules
    BASE_FARE = float(os.getenv('BASE_FARE', 5.0))
    RATE_PER_KM = float(os.getenv('RATE_PER_KM', 2.5))
    SURGE_MULTIPLIERS = {
        'LOW': float(os.getenv('SURGE_MULTIPLIER_LOW', 1.0)),
        'MEDIUM': float(os.getenv('SURGE_MULTIPLIER_MEDIUM', 1.2)),
        'HIGH': float(os.getenv('SURGE_MULTIPLIER_HIGH', 1.5))
    }
    CANCELLATION_FEE = float(os.getenv('CANCELLATION_FEE', 3.0))
    
    # Idempotency
    IDEMPOTENCY_KEY_TTL = int(os.getenv('IDEMPOTENCY_KEY_TTL', 86400))  # 24 hours
    
    # Logging
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    
    @classmethod
    def get_database_uri(cls):
        """Get database connection URI"""
        return f"postgresql://{cls.DB_USER}:{cls.DB_PASS}@{cls.DB_HOST}:{cls.DB_PORT}/{cls.DB_NAME}"