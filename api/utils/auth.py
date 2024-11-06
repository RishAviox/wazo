from django.conf import settings
from django.db import transaction
from django.utils import timezone

import secrets
import requests
import jwt
from django.conf import settings


from api.models import OTPStore


def generate_access_token(user):
    payload = {
        'id': user.phone_no,
        'exp': timezone.now() + settings.JWT_ACCESS_TOKEN_EXPIRATION,  # Short-lived
        'iat': timezone.now(),
        'token_type': 'access',
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm='HS256')

def generate_refresh_token(user):
    payload = {
        'id': user.phone_no,
        'exp': timezone.now() + settings.JWT_REFRESH_TOKEN_EXPIRATION,  # Long-lived
        'iat': timezone.now(),
        'token_type': 'refresh',
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm='HS256')




# generate, store and send otp
def generate_and_send_otp(phone_no):
    otp_number = secrets.randbelow(900000) + 100000 # 6 digit 
    otp = OTPStore(data=str(otp_number), phone_no=phone_no)
    otp.save()

    # send OTP via API call
    headers = {
        'Content-Type': 'application/json'
    }
    data = {
        "number": phone_no,
        "OTP": str(otp_number)
    }
    print(data)
    if not settings.DEBUG:
        response = requests.post(settings.WAJO_OTP_SERVICE_URL, headers=headers, json=data)
        print(response.text)
    return otp


def validate_otp(phone_no, input_otp):
    """
        Prevent race conditions with atomic and select_for_update() for row level locking
        Reference: https://docs.djangoproject.com/en/5.0/topics/db/transactions/
    """
    with transaction.atomic(): 
        try:
            otp = OTPStore.objects.select_for_update().filter(phone_no=phone_no).latest('created_on')
            if otp.is_valid() and otp.data == input_otp:
                otp.is_used = True
                otp.save()
                return True
            else:
                return False
        except OTPStore.DoesNotExist:
            return False
        