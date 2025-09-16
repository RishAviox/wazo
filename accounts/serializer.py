from .models import *
from rest_framework import serializers
import re

def custom_phone_number_validator(value):
    if not re.match(r'^\+?1?\d{9,15}$', value):
        raise serializers.ValidationError("Invalid phone number format. Please use a valid international phone number format.")

class WajoUserSerializer(serializers.ModelSerializer):
    picture = serializers.SerializerMethodField()
    players = serializers.SerializerMethodField()

    class Meta:
        model = WajoUser
        fields = [
            'phone_no',
            'picture',
            'selected_language',
            'name',
            'nickname',
            'gender',
            'dob',
            'primary_sport',
            'role',
            'wake_up_time',
            'sleep_time',
            'created_on',
            'updated_on',
            'coach',
            'players',
        ]
        extra_kwargs = {
            'phone_no': {'required': True, 'validators': [custom_phone_number_validator]},
        }

    def validate_phone_no(self, value):
        if WajoUser.objects.filter(phone_no=value).exists():
            raise serializers.ValidationError("A user with this phone number already exists.")
        return value
    
    def get_picture(self, obj):
        if not obj.picture or str(obj.picture.url).endswith('null'):
            return "https://cdn-icons-png.flaticon.com/512/8847/8847419.png"
        return obj.picture.url
    
    def get_players(self, obj):
        # Return full player details only if the user is a Coach
        try:
            if obj.role.lower() != 'coach':
                return None
        except:
            return None
        return [
            {
                "phone_no": player.phone_no,
                "picture": player.picture.url if player.picture else "https://cdn-icons-png.flaticon.com/512/8847/8847419.png",
                "selected_language": player.selected_language,
                "name": player.name,
                "nickname": player.nickname,
                "gender": player.gender,
                "dob": player.dob,
                "primary_sport": player.primary_sport,
                "role": player.role,
                "wake_up_time": player.wake_up_time,
                "sleep_time": player.sleep_time,
                "created_on": player.created_on,
                "updated_on": player.updated_on,
            }
            for player in obj.players.all()
        ]


class UserRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserRequest
        fields = ['user', 'request_type', 'description', 'status', 'requested_at', 'processed_at', 'admin_notes']
        read_only_fields = ['requested_at', 'status', 'processed_at']
