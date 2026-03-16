import os
import django
import uuid

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'wajo_backend.settings_dev')
os.environ.setdefault('DJANGO_DATABASE', 'docker')
django.setup()

from accounts.models import WajoUser
from tracevision.models import TraceClipReelShare

print(f"--- USERS WITH SHARES RECEIVED ---")
recipient_ids = TraceClipReelShare.objects.filter(is_active=True).values_list('shared_with_id', flat=True).distinct()
for rid in recipient_ids:
    if rid:
        user = WajoUser.objects.filter(id=rid).first()
        if user:
            print(f"User Name: {user.name}, ID: {user.id}, Role: {user.role}")
        else:
            print(f"User ID: {rid} NOT FOUND in WajoUser")
    else:
        print("Share found with recipient_id=None (Public share?)")

print(f"--- DEBUG END ---")
