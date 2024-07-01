from django.db import models
from .user import WajoUser

# Recurring Events Table
class RecurringEvents(models.Model):
    user = models.ForeignKey(WajoUser, on_delete=models.CASCADE, related_name='recurring_events')
    event_type = models.CharField(max_length=50, null=True, blank=True)
    event = models.TextField(null=True, blank=True)
    date = models.DateTimeField(null=True, blank=True)
    source = models.CharField(max_length=150, null=True, blank=True)

    created_on = models.DateTimeField(auto_now_add=True)
    updated_on = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Recurring Event"
        verbose_name_plural = "Recurring Events"

    def __str__(self):
        return self.user.phone_no
    

# One-Off Events Table
class OneTimeEvents(models.Model):
    user = models.ForeignKey(WajoUser, on_delete=models.CASCADE, related_name='one_time_events')
    event_type = models.CharField(max_length=50, null=True, blank=True)
    event = models.TextField(null=True, blank=True)
    date = models.DateTimeField(null=True, blank=True)
    source = models.CharField(max_length=150, null=True, blank=True)

    created_on = models.DateTimeField(auto_now_add=True)
    updated_on = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "One Time Event"
        verbose_name_plural = "One Time Events"

    def __str__(self):
        return self.user.phone_no