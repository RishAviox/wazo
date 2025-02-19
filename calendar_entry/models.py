from django.core.exceptions import ValidationError
from django.db import models

from accounts.models import WajoUser


class CalendarEventEntry(models.Model):

    FREQUENCY_CHOICES = (
        ('Daily', 'Daily'),
        ('Weekly', 'Weekly'),
        ('Monthly', 'Monthly'),
        ('Yearly', 'Yearly'),
        ('Custom', 'Custom'),
        ('None', 'None')
    )

    user = models.ForeignKey(WajoUser, on_delete=models.CASCADE, related_name='calendar_events')
    category = models.CharField(max_length=30)
    sub_category = models.CharField(max_length=30)
    detail = models.TextField(max_length=1000)
    title = models.CharField(max_length=250)
    date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    location = models.CharField(max_length=250)
    repeat = models.CharField(max_length=15, choices=FREQUENCY_CHOICES)
    custom_repeat = models.JSONField(default=dict, blank=True)
    participants = models.CharField(max_length=250)
    notes = models.TextField(max_length=1000, blank=True, null=True)

    class Meta:
        verbose_name_plural = "Calendar Event Entries"

    def __str__(self):
        return f"{self.category} / {self.sub_category}"


class CalendarGoalEntry(models.Model):

    user = models.ForeignKey(WajoUser, on_delete=models.CASCADE, related_name='calendar_goals')
    category = models.CharField(max_length=30)
    title = models.CharField(max_length=250)
    start_date = models.DateField()
    end_date = models.DateField()
    notes = models.TextField(max_length=1000)

    class Meta:
        verbose_name_plural = "Calendar Goal Entries"

    def __str__(self):
        return f"{self.category} / {self.title}" 
