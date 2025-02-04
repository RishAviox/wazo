from rest_framework import serializers

from calendar_entry.models import CalendarEventEntry, CalendarGoalEntry


class CalendarEventCreateSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(read_only=True)
    user_id = serializers.CharField()

    class Meta:
        model = CalendarEventEntry
        fields = ('id', 'user_id', 'category', 'sub_category', 'detail', 'title', 'date', 'start_time', 'end_time',
                  'location', 'repeat', 'participants', 'notes', 'custom_repeat')

    def validate(self, data):
        # If repeat is custom, ensure custom_repeat_days and custom_repeat_times are provided
        if data.get('repeat') == 'Custom':
            custom_repeat = data.get('custom_repeat')
            if not custom_repeat:
                raise serializers.ValidationError("Custom repeat values are required")
            if not custom_repeat.get('days') or not custom_repeat.get('times'):
                raise serializers.ValidationError("For Custom repeat, both days and times must be provided.")
            
        return data


class CalendarEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = CalendarEventEntry
        exclude = ('user',)

    
    def validate(self, data):
        # If repeat is custom, ensure custom_repeat_days and custom_repeat_times are provided
        if data.get('repeat') == 'Custom':
            custom_repeat = data.get('custom_repeat')
            if not custom_repeat:
                raise serializers.ValidationError("Custom repeat values are required")
            if not custom_repeat.get('days') or not custom_repeat.get('times'):
                raise serializers.ValidationError("For Custom repeat, both days and times must be provided.")
            
        return data


class CalendarGoalCreateSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(read_only=True)
    user_id = serializers.CharField()

    class Meta:
        model = CalendarGoalEntry
        fields = ('id', 'user_id', 'category', 'title', 'start_date', 'end_date', 'notes')


class CalendarGoalSerializer(serializers.ModelSerializer):
    class Meta:
        model = CalendarGoalEntry
        exclude = ('user',)
