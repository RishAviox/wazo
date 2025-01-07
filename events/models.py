from django.db import models
import os
from django.core.exceptions import ValidationError
import pandas as pd

from accounts.models import WajoUser
from core.soft_delete import WajoModel


# Recurring Events Table
FREQUENCY_CHOICES = [
    ('Daily', 'Daily'),
    ('Weekly', 'Weekly'),
    ('Monthly', 'Monthly'),
    ('Yearly', 'Yearly'),
]
class RecurringEvents(WajoModel):
    user = models.ForeignKey(WajoUser, on_delete=models.CASCADE, related_name='recurring_events')
    event_type = models.CharField(max_length=50, null=True, blank=True)
    event = models.TextField(null=True, blank=True)
    date = models.DateTimeField(null=True, blank=True)
    source = models.CharField(max_length=150, null=True, blank=True)
    frequency = models.CharField(
                            max_length=15,
                            choices=FREQUENCY_CHOICES,
                            default='Daily'
                        )

    created_on = models.DateTimeField(auto_now_add=True)
    updated_on = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Recurring Event"
        verbose_name_plural = "Recurring Events"

    def __str__(self):
        return self.user.phone_no
    

# One-Off Events Table
class OneTimeEvents(WajoModel):
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
    


# MatchEventsData to upload .xlsx file
"""
File will contain many sheets of Match Events.
1. Send JSON of particular event(ex. Goal) for Video Player.
2. On File upload, calculate metrics for screens 7,8,9
"""

def validate_file_extension(value):
    ext = os.path.splitext(value.name)[1]  # [0] returns path + filename
    valid_extensions = ['.xlsx']
    if not ext.lower() in valid_extensions:
        raise ValidationError('Unsupported file extension. Allowed extensions: .xlsx')

def match_events_data_file_path(instnace, filename):
    # MEDIA_ROOT / uploads/match_events_data_file/<filename>
    return 'uploads/match_events_data_file/{0}'.format(filename)

DATA_FILE_TYPES = [
    ('BEPRO', 'BEPRO'),
    ('GPS', 'GPS'),
]
class MatchEventsDataFile(WajoModel):
    name = models.CharField(max_length=50, null=True, blank=True)
    _type = models.CharField(choices=DATA_FILE_TYPES, max_length=10, default='BEPRO')
    file = models.FileField(upload_to=match_events_data_file_path, validators=[validate_file_extension])
    notes = models.TextField(null=True, blank=True)

    created_on = models.DateTimeField(auto_now_add=True)
    updated_on = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Match Events Data File"
        verbose_name_plural = "Match Events Data Files"

    def __str__(self):
        return self.file.name
    
    def get_data(self):
        event_data = pd.read_excel(self.file.path, sheet_name='EventData_137183')
        return event_data