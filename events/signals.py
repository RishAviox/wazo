from django.db.models.signals import post_save
from django.dispatch import receiver

from core.schedule_event_reminder import schedule_event_reminder_notification

from .models import OneTimeEvents, RecurringEvents

            
"""
Events are added through Chatbot-admin, 
but sometimes the events are added through ADMIN Dashboard.
"""
@receiver(post_save, sender=OneTimeEvents, weak=False)
def schedule_reminder_for_one_time_events(sender, instance, created, **kwargs):
    print("[Signal triggered]: Schedule reminder for OneTimeEvent 30 minutes before the event time.")
    try:
        # schedule event reminder notification before 30 minutes
        schedule_event_reminder_notification(
            instance=instance,
            notification_type='OneTimeEventReminder',
        )
    except Exception as e:
        print(f"Failed to schedule one time event reminder: {e}")
        
        
@receiver(post_save, sender=RecurringEvents, weak=False)
def schedule_reminder_for_recurring_events(sender, instance, created, **kwargs):
    print("[Signal triggered]: Schedule reminder for RecurringEvent 30 minutes before the event time.")
    try:
        # schedule event reminder notification before 30 minutes
        schedule_event_reminder_notification(
            instance=instance,
            notification_type='RecurringEventReminder',
        )
    except Exception as e:
        print(f"Failed to schedule recurring event reminder: {e}")