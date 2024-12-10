from rest_framework import serializers

from .models import TrainingCardData

class TrainingCardDataSerializer(serializers.ModelSerializer):
    # Explicitly declare fields to customize JSON keys
    FirstDropdown = serializers.CharField(source='first_dropdown')
    SecondDropdown = serializers.CharField(source='second_dropdown')
    Topic = serializers.CharField(source='topic')
    VideoLink = serializers.CharField(source='video_link')
    Type = serializers.CharField(source='_type')

    class Meta:
        model = TrainingCardData
        fields = ['FirstDropdown', 'SecondDropdown', 'Topic', 'VideoLink', 'Type']