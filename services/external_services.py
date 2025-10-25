# services/external_services.py - Inter-service Communication
import requests
from typing import Optional, Dict, Tuple
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import Config
from utils.logger import get_logger

logger = get_logger(__name__)

class ExternalServices:
    """Handle communication with other microservices"""
    
    TIMEOUT = 5  # seconds
    
    @staticmethod
    def validate_trip_completion(trip_id: int) -> Tuple[bool, Optional[Dict]]:
        """
        Validate if a trip is completed by calling Trip Service
        
        Args:
            trip_id: Trip ID to validate
        
        Returns:
            Tuple of (is_completed, trip_data)
        """
        try:
            url = f"{Config.TRIP_SERVICE_URL}/v1/trips/{trip_id}"
            response = requests.get(url, timeout=ExternalServices.TIMEOUT)
            
            if response.status_code == 200:
                trip_data = response.json()
                is_completed = trip_data.get('status') == 'COMPLETED'
                
                logger.info(f"Trip {trip_id} validation: status={trip_data.get('status')}")
                return is_completed, trip_data
            else:
                logger.warning(f"Trip service returned {response.status_code} for trip {trip_id}")
                return False, None
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Error calling Trip Service: {e}")
            # In development, return mock data if service is unavailable
            if Config.DEBUG:
                logger.warning("Using mock trip data in DEBUG mode")
                mock_data = {
                    'trip_id': trip_id,
                    'status': 'COMPLETED',
                    'distance': 10.5,
                    'surge_multiplier': 1.0
                }
                return True, mock_data
            return False, None
    
    @staticmethod
    def send_payment_notification(notification_data: Dict) -> bool:
        """
        Send payment notification via Notification Service
        
        Args:
            notification_data: Notification payload
        
        Returns:
            True if notification sent successfully
        """
        try:
            url = f"{Config.NOTIFICATION_SERVICE_URL}/v1/notifications"
            response = requests.post(
                url, 
                json=notification_data, 
                timeout=ExternalServices.TIMEOUT
            )
            
            if response.status_code in [200, 201, 202]:
                logger.info(f"Notification sent for payment {notification_data.get('payment_id')}")
                return True
            else:
                logger.warning(f"Notification service returned {response.status_code}")
                return False
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Error sending notification: {e}")
            # Don't fail the payment if notification fails
            return False
    
    @staticmethod
    def get_rider_info(rider_id: int) -> Optional[Dict]:
        """
        Get rider information from Rider Service
        
        Args:
            rider_id: Rider ID
        
        Returns:
            Rider information dictionary or None
        """
        try:
            url = f"{Config.RIDER_SERVICE_URL}/v1/riders/{rider_id}"
            response = requests.get(url, timeout=ExternalServices.TIMEOUT)
            
            if response.status_code == 200:
                return response.json()
            return None
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching rider info: {e}")
            return None
    
    @staticmethod
    def get_driver_info(driver_id: int) -> Optional[Dict]:
        """
        Get driver information from Driver Service
        
        Args:
            driver_id: Driver ID
        
        Returns:
            Driver information dictionary or None
        """
        try:
            url = f"{Config.DRIVER_SERVICE_URL}/v1/drivers/{driver_id}"
            response = requests.get(url, timeout=ExternalServices.TIMEOUT)
            
            if response.status_code == 200:
                return response.json()
            return None
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching driver info: {e}")
            return None
    
    @staticmethod
    def simulate_payment_gateway(payment_data: Dict) -> Dict:
        """
        Simulate external payment gateway processing
        
        Args:
            payment_data: Payment information
        
        Returns:
            Gateway response with status
        """
        import random
        
        # Simulate different outcomes based on payment method
        method = payment_data.get('method')
        
        if method == 'CASH':
            # Cash payments are always successful
            return {
                'status': 'SUCCESS',
                'gateway_id': f"GW-{random.randint(100000, 999999)}",
                'message': 'Cash payment recorded'
            }
        elif method in ['CARD', 'WALLET', 'UPI']:
            # Electronic payments have 80% success rate (configurable)
            success_rate = 0.8
            if random.random() < success_rate:
                return {
                    'status': 'SUCCESS',
                    'gateway_id': f"GW-{random.randint(100000, 999999)}",
                    'message': 'Payment processed successfully'
                }
            else:
                return {
                    'status': 'FAILED',
                    'error_code': random.choice(['INSUFFICIENT_FUNDS', 'CARD_DECLINED', 'GATEWAY_ERROR']),
                    'message': 'Payment processing failed'
                }
        else:
            return {
                'status': 'PENDING',
                'message': 'Payment method not supported'
            }