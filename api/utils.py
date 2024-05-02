import secrets
import requests
from django.conf import settings
from django.db import transaction

from .models import OTPStore


# generate, store and send otp
def generate_and_send_otp(user):
    otp_number = secrets.randbelow(1000000) + 100000 # 6 digit 
    otp = OTPStore(data=str(otp_number), user=user)
    otp.save()

    # send OTP via API call
    headers = {
        'Content-Type': 'application/json'
    }
    data = {
        "number": user.phone_no,
        "OTP": str(otp_number)
    }
    response = requests.post(settings.WAJO_OTP_SERVICE_URL, headers=headers, json=data)
    print(response.text)
    return otp


def validate_otp(user, input_otp):
    """
        Prevent race conditions with atomic and select_for_update() for row level locking
        Reference: https://docs.djangoproject.com/en/5.0/topics/db/transactions/
    """
    with transaction.atomic(): 
        try:
            otp = OTPStore.objects.select_for_update().filter(user=user).latest('created_on')
            if otp.is_valid() and otp.data == input_otp:
                otp.is_used = True
                otp.save()
                return True
            else:
                return False
        except OTPStore.DoesNotExist:
            return False