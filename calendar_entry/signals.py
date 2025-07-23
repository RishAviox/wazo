from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import CalendarEventEntry
from django.conf import settings
from datetime import timedelta
from django.utils import timezone
import requests
from datetime import datetime
 
@receiver(post_save, sender=CalendarEventEntry, weak=False)
def schedule_rpe_reminder_signal(sender, instance, created, **kwargs):
    if not created:
        return
    category = (instance.category or "").lower()
    sub_category = (instance.sub_category or "").lower()
 
    if not (category in ["match", "training"] or sub_category in ["match", "training"]):
        print(f"Skipping RPE scheduling. Not Match or Training: category={category}, sub_category={sub_category}")
        return
 
    if not instance.end_time or not instance.date:
        print(f"Skipping RPE scheduling. Missing end_time or date")
        return
 
    try:
        print(f"[Signal Triggered]: Event created for user {instance.user.phone_no} - {instance.title}")
        url = settings.WAJO_NOTIFICATIONS_API_URL + "/schedule-delayed"
        headers = {
            'Content-Type': 'application/json'
        }
        
        #  Calculate the "notification time" = event_end_time + 30 minutes
        today = timezone.localdate()  # Or use instance.date if you have one
        end_datetime = datetime.combine(today, instance.end_time)
        end_datetime = timezone.make_aware(end_datetime, timezone.get_current_timezone())

        notification_time = end_datetime + timedelta(minutes=30)
        delay_seconds = (notification_time - timezone.now()).total_seconds()
        
        payload = {
            'data':{
                "phone_no": instance.user_id,
                "event": instance.title
            },
            'notificationType': "RPESubmissionReminder",
            'delaySeconds': delay_seconds,
            'jobId': f"{instance.user_id}_{instance.id}"
        } 
        try:
            response = requests.post(url, headers=headers, json=payload)
            print(response.text)
            print(f"RPE Submission Reminder scheduled. Job ID: {payload['jobId']} | Time: {notification_time}")
        except Exception as e:
            print("Failed to schedule event reminder notification: ", e)
        
    except Exception as e:
        print(f"Error scheduling RPE reminder: {str(e)}")