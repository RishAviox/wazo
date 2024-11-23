from .models import *
from rest_framework import serializers

class OneTimeEventsSerializer(serializers.ModelSerializer):
    class Meta:
        model = OneTimeEvents
        fields = "__all__"

class RecurringEventsSerializer(serializers.ModelSerializer):
    class Meta:
        model = RecurringEvents
        fields = "__all__"
