import logging
from notifications.models import Notification
from django.conf import settings

logger = logging.getLogger(__name__)

class NotificationService:
    """
    Service class for creating database notifications.
    Replaces FCM service for better Flutter compatibility.
    """
    
    def __init__(self):
        self.initialized = True
        logger.info("Notification service initialized - using database notifications")
    
    def is_available(self):
        """Check if notification service is available."""
        return self.initialized
    
    def create_silent_notification(self, user, device, session_data):
        """
        Create a silent notification in the database.
        
        Args:
            user: User instance
            device: WajoUserDevice instance
            session_data: Dictionary containing session information
            
        Returns:
            Notification: Created notification instance or None if failed
        """
        try:
            # Create a silent notification (no title/body, just data in postback)
            notification = Notification.objects.create(
                user=user,
                device=device,
                title="",  # Empty title for silent notification
                body="",   # Empty body for silent notification
                postback=f"session_completed:{session_data.get('session_id')}:{session_data.get('status')}:{session_data.get('match_date')}:{session_data.get('home_team')}:{session_data.get('away_team')}:{session_data.get('home_score')}:{session_data.get('away_score')}"
            )
            
            logger.info(f"Silent notification created for device {device.fcm_token} for session {session_data.get('session_id')}")
            return notification
            
        except Exception as e:
            logger.exception(f"Error creating silent notification for device {device.fcm_token}: {e}")
            return None
    
    def create_notification(self, user, device, title, body, postback=""):
        """
        Create a regular notification in the database.
        
        Args:
            user: User instance
            device: WajoUserDevice instance
            title: Notification title
            body: Notification body
            postback: Optional postback data
            
        Returns:
            Notification: Created notification instance or None if failed
        """
        try:
            notification = Notification.objects.create(
                user=user,
                device=device,
                title=title,
                body=body,
                postback=postback
            )
            
            logger.info(f"Notification created for device {device.fcm_token}: {title}")
            return notification
            
        except Exception as e:
            logger.exception(f"Error creating notification for device {device.fcm_token}: {e}")
            return None
    
    def create_silent_notification_for_all_devices(self, user, session_data):
        """
        Create silent notifications for all devices of a user.
        
        Args:
            user: User instance
            session_data: Dictionary containing session information
            
        Returns:
            list: List of created notification instances
        """
        try:
            user_devices = user.wajouserdevice_set.all()
            notifications = []
            
            for device in user_devices:
                notification = self.create_silent_notification(user, device, session_data)
                if notification:
                    notifications.append(notification)
            
            logger.info(f"Created silent notifications for {len(notifications)} devices of user {user.phone_no}")
            return notifications
            
        except Exception as e:
            logger.exception(f"Error creating silent notifications for all devices of user {user.phone_no}: {e}")
            return []
    
    def create_notification_for_all_devices(self, user, title, body, postback=""):
        """
        Create a notification for all devices of a user.
        
        Args:
            user: User instance
            title: Notification title
            body: Notification body
            postback: Optional postback data
            
        Returns:
            list: List of created notification instances
        """
        try:
            user_devices = user.wajouserdevice_set.all()
            notifications = []
            
            for device in user_devices:
                notification = self.create_notification(user, device, title, body, postback)
                if notification:
                    notifications.append(notification)
            
            logger.info(f"Created notifications for {len(notifications)} devices of user {user.phone_no}")
            return notifications
            
        except Exception as e:
            logger.exception(f"Error creating notifications for all devices of user {user.phone_no}: {e}")
            return []
    
    def mark_notification_as_read(self, notification_id, user):
        """
        Mark a notification as read.
        
        Args:
            notification_id: ID of the notification
            user: User instance
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            notification = Notification.objects.get(id=notification_id, user=user)
            notification.is_read = True
            notification.save()
            
            logger.info(f"Marked notification {notification_id} as read for user {user.phone_no}")
            return True
            
        except Notification.DoesNotExist:
            logger.warning(f"Notification {notification_id} not found for user {user.phone_no}")
            return False
        except Exception as e:
            logger.exception(f"Error marking notification {notification_id} as read: {e}")
            return False
    
    def get_unread_notifications(self, user, device, limit=10):
        """
        Get unread notifications for a specific device.
        
        Args:
            user: User instance
            device: WajoUserDevice instance
            limit: Maximum number of notifications to return
            
        Returns:
            QuerySet: Unread notifications
        """
        try:
            notifications = device.notifications.filter(is_read=False).order_by('-created_on')[:limit]
            return notifications
            
        except Exception as e:
            logger.exception(f"Error getting unread notifications for device {device.fcm_token}: {e}")
            return []
