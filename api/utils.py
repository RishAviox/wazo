from django.conf import settings
from django.db import transaction
from django.core.files.base import ContentFile
from django.utils import timezone

import secrets
import requests
from PIL import Image
import base64
import jwt


from .models import OTPStore


def create_token(user):
    return jwt.encode({
            'id': user.phone_no,
            'exp': timezone.now() + timezone.timedelta(hours=24),
            'iat': timezone.now()
        }, settings.SECRET_KEY, algorithm='HS256')

# generate, store and send otp
def generate_and_send_otp(phone_no):
    otp_number = secrets.randbelow(1000000) + 100000 # 6 digit 
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
        

def get_content_type(ext):
    """Return the MIME type based on file extension."""
    return {
        'jpeg': 'image/jpeg',
        'jpg': 'image/jpeg',
        'png': 'image/png'
    }.get(ext.lower(), 'application/octet-stream')  # Default to binary file type if unknown


def convert_base64_to_file(base64_string):
    try:
        # Split the base64 string on ';base64,' and validate its parts
        format, imgstr = base64_string.split(';base64,')
        ext = format.split('/')[-1]  # Extracts the extension (png, jpeg, etc.)
        content_type = get_content_type(ext)
        data = base64.b64decode(imgstr) 
    except (ValueError, IndexError, base64.binascii.Error) as e:
        return None, None, f"Invalid base64 string: {e}"
    
    # Return a ContentFile if decoding is successful
    return ContentFile(data, name='temp.' + ext), content_type, None
        
def is_valid_image_extension(file):
    return file.name.lower().endswith(('.png', '.jpg', '.jpeg'))

def is_valid_image_content_type(file):
    return file.content_type in ['image/png', 'image/jpeg']

def is_valid_image(file):
    try:
        with Image.open(file) as img:
            img.verify()  # Verify that it is an image
        return True
    except (IOError, SyntaxError) as e:
        print(f"Invalid image file: {e}")  # Not an image, or corrupted
        return False

def is_valid_image_size(file, MAX_IMAGE_SIZE):
    if file.size > MAX_IMAGE_SIZE:
        return False
    return True