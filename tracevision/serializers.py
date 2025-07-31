import json
from rest_framework import serializers
from .models import TraceSession


class TraceVisionProcessesSerializer(serializers.ModelSerializer):
    class Meta:
        model = TraceSession
        fields = "__all__"
        read_only_fields = ['id', 'user']
