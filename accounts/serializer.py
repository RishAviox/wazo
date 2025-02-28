from .models import *
from rest_framework import serializers
import re

def custom_phone_number_validator(value):
    if not re.match(r'^\+?1?\d{9,15}$', value):
        raise serializers.ValidationError("Invalid phone number format. Please use a valid international phone number format.")

class WajoUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = WajoUser
        fields = '__all__'
        extra_kwargs = {
            'phone_no': {'required': True, 'validators': [custom_phone_number_validator]},
        }

    def validate_phone_no(self, value):
        if WajoUser.objects.filter(phone_no=value).exists():
            raise serializers.ValidationError("A user with this phone number already exists.")
        return value


class UserRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserRequest
        fields = ['user', 'request_type', 'description', 'status', 'requested_at', 'processed_at', 'admin_notes']
        read_only_fields = ['requested_at', 'status', 'processed_at']
