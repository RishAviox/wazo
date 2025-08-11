import logging
import os
from pyfcm import FCMNotification
from django.conf import settings

logger = logging.getLogger(__name__)

class FCMService:
    """
    Service class for Firebase Cloud Messaging operations.
    Handles initialization with different credential methods and message sending.
    """
    
    def __init__(self):
        self.fcm = None
        self.initialized = False
        self._initialize_fcm()
    
    def _initialize_fcm(self):
        """Initialize FCM with available credentials."""
        try:
            # Method 1: Try service account file
            if hasattr(settings, 'FCM_SERVICE_ACCOUNT_FILE') and settings.FCM_SERVICE_ACCOUNT_FILE:
                if os.path.exists(settings.FCM_SERVICE_ACCOUNT_FILE):
                    self.fcm = FCMNotification(
                        service_account_file=settings.FCM_SERVICE_ACCOUNT_FILE,
                        project_id=settings.FCM_PROJECT_ID
                    )
                    self.initialized = True
                    logger.info("FCM initialized with service account file")
                    return
                else:
                    logger.warning(f"FCM service account file not found: {settings.FCM_SERVICE_ACCOUNT_FILE}")
            
            # Method 2: Try environment variable for service account
            gcp_credentials = os.getenv('GCP_CREDENTIALS')
            if gcp_credentials and hasattr(settings, 'FCM_PROJECT_ID'):
                try:
                    import json
                    from google.oauth2 import service_account
                    
                    credentials_dict = json.loads(gcp_credentials)
                    credentials = service_account.Credentials.from_service_account_info(
                        credentials_dict, 
                        scopes=['https://www.googleapis.com/auth/firebase.messaging']
                    )
                    
                    self.fcm = FCMNotification(
                        service_account_file=None,
                        credentials=credentials,
                        project_id=settings.FCM_PROJECT_ID
                    )
                    self.initialized = True
                    logger.info("FCM initialized with GCP credentials from environment")
                    return
                except Exception as e:
                    logger.warning(f"Failed to initialize FCM with GCP credentials: {e}")
            
            # Method 3: Fallback to legacy API key
            if hasattr(settings, 'FCM_SERVER_KEY') and settings.FCM_SERVER_KEY:
                self.fcm = FCMNotification(api_key=settings.FCM_SERVER_KEY)
                self.initialized = True
                logger.info("FCM initialized with legacy API key (deprecated)")
                return
            
            # Method 4: No credentials available
            logger.error("No FCM credentials available. Please configure FCM_SERVICE_ACCOUNT_FILE and FCM_PROJECT_ID or FCM_SERVER_KEY")
            self.initialized = False
            
        except Exception as e:
            logger.exception(f"Failed to initialize FCM: {e}")
            self.initialized = False
    
    def is_available(self):
        """Check if FCM is properly initialized."""
        return self.initialized and self.fcm is not None
    
    def send_data_message(self, fcm_token, data_payload):
        """
        Send a data-only message to a single device.
        
        Args:
            fcm_token: FCM token of the target device
            data_payload: Dictionary of data to send
            
        Returns:
            dict: FCM response or None if failed
        """
        if not self.is_available():
            logger.error("FCM not initialized")
            return None
        
        try:
            # Ensure all values are strings (FCM requirement)
            string_data = {k: str(v) for k, v in data_payload.items()}
            
            # Send data-only message
            response = self.fcm.notify(
                fcm_token=fcm_token,
                data_payload=string_data
            )
            
            logger.info(f"FCM data message sent to {fcm_token}")
            return response
            
        except Exception as e:
            logger.exception(f"Error sending FCM data message to {fcm_token}: {e}")
            return None
    
    def send_notification_with_data(self, fcm_token, notification_title, notification_body, data_payload=None):
        """
        Send a notification message with optional data payload.
        
        Args:
            fcm_token: FCM token of the target device
            notification_title: Title of the notification
            notification_body: Body of the notification
            data_payload: Optional dictionary of data to send
            
        Returns:
            dict: FCM response or None if failed
        """
        if not self.is_available():
            logger.error("FCM not initialized")
            return None
        
        try:
            kwargs = {
                'fcm_token': fcm_token,
                'notification_title': notification_title,
                'notification_body': notification_body
            }
            
            if data_payload:
                # Ensure all values are strings
                string_data = {k: str(v) for k, v in data_payload.items()}
                kwargs['data_payload'] = string_data
            
            response = self.fcm.notify(**kwargs)
            
            logger.info(f"FCM notification sent to {fcm_token}")
            return response
            
        except Exception as e:
            logger.exception(f"Error sending FCM notification to {fcm_token}: {e}")
            return None
    
    def send_to_topic(self, topic_name, notification_body, data_payload=None):
        """
        Send a message to devices subscribed to a topic.
        
        Args:
            topic_name: Name of the topic
            notification_body: Body of the notification
            data_payload: Optional dictionary of data to send
            
        Returns:
            dict: FCM response or None if failed
        """
        if not self.is_available():
            logger.error("FCM not initialized")
            return None
        
        try:
            kwargs = {
                'topic_name': topic_name,
                'notification_body': notification_body
            }
            
            if data_payload:
                string_data = {k: str(v) for k, v in data_payload.items()}
                kwargs['data_payload'] = string_data
            
            response = self.fcm.notify(**kwargs)
            
            logger.info(f"FCM topic message sent to {topic_name}")
            return response
            
        except Exception as e:
            logger.exception(f"Error sending FCM topic message to {topic_name}: {e}")
            return None
    
    def validate_token(self, fcm_token):
        """
        Validate an FCM token by attempting to send a test message.
        
        Args:
            fcm_token: FCM token to validate
            
        Returns:
            bool: True if token is valid, False otherwise
        """
        if not self.is_available():
            return False
        
        try:
            # Send a minimal test message
            response = self.fcm.notify(
                fcm_token=fcm_token,
                data_payload={"test": "validation"}
            )
            
            # Check if message was sent successfully
            if response and response.get('success') == 1:
                return True
            elif response and response.get('failure') == 1:
                # Check for specific error types
                for result in response.get('results', []):
                    if result.get('error') in ['NotRegistered', 'InvalidRegistration']:
                        return False
                return True  # Other errors might be temporary
            return False
            
        except Exception as e:
            logger.warning(f"Error validating FCM token {fcm_token}: {e}")
            return False
