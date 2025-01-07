from .models import *
from rest_framework import serializers

class DailyWellnessUserResponseSerializer(serializers.ModelSerializer):
    class Meta:
        model = DailyWellnessUserResponse
        fields = ['id', 'user', 'response', 'created_on', 'updated_on']

class RPEUserResponseSerializer(serializers.ModelSerializer):
    class Meta:
        model = RPEUserResponse
        fields = ['id', 'user', 'response', 'created_on', 'updated_on']