import json
from rest_framework import serializers
from .models import MatchDataTracevision


class MatchDataTracevisionSerializer(serializers.ModelSerializer):
    user = serializers.ReadOnlyField(source='user.id')
    data = serializers.JSONField()

    class Meta:
        model = MatchDataTracevision
        fields = ['id', 'user', 'data', 'video']
        read_only_fields = ['id', 'user']

    def validate_data(self, value):
        if isinstance(value, str):
            try:
                return json.loads(value)
            except json.JSONDecodeError as e:
                raise serializers.ValidationError("Invalid JSON format.") from e
        return value
