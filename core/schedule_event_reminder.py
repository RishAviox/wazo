import requests
from django.conf import settings
from django.utils import timezone
from datetime import datetime, timedelta
        
        
def schedule_event_reminder_notification(instance, notification_type):
    url = settings.WAJO_NOTIFICATIONS_API_URL + "/schedule-delayed"
    headers = {
        'Content-Type': 'application/json'
    }
    
    if notification_type == "OneTimeEventReminder":
        #  Calculate the "notification time" = event_start_time - 30 minutes
        notification_time = instance.date - timedelta(minutes=30)
        delay_seconds = (notification_time - timezone.now()).total_seconds()

        payload = {
            'data':{
                "phone_no": instance.user_id,
                "event": instance.event
            },
            'notificationType': notification_type,
            'delaySeconds': delay_seconds,
            'jobId': f"{instance.user_id}_{instance.id}"
        }
    elif notification_type == "RecurringEventReminder":
        start_date = instance.date - timedelta(minutes=30)
        payload = {
            'data':{
                "phone_no": instance.user_id,
                "event": instance.event
            },
            'notificationType': notification_type,
            "startDate": start_date.isoformat(),
            "frequency": instance.frequency,
            "jobId": f"{instance.user_id}_{instance.id}_{instance.frequency}"
        }    
    try:
        response = requests.post(url, headers=headers, json=payload)
        print(response.text)
    except Exception as e:
        print("Failed to schedule event reminder notification: ", e)
        