import os
import django
import uuid

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'wajo_backend.settings_dev')
os.environ.setdefault('DJANGO_DATABASE', 'docker')
django.setup()

from accounts.models import WajoUser
from tracevision.models import TraceClipReel, TraceClipReelShare

session_id = "1"

print(f"--- DEBUG START ---")
print(f"Total Clip Reels in DB: {TraceClipReel.objects.count()}")
print(f"Total Clip Reels for session {session_id}: {TraceClipReel.objects.filter(session_id=session_id).count()}")

print(f"\nTotal Shares in DB: {TraceClipReelShare.objects.count()}")
print(f"Total Active Shares in DB: {TraceClipReelShare.objects.filter(is_active=True).count()}")

print(f"\nRecent 10 Shares:")
for share in TraceClipReelShare.objects.order_by('-shared_at')[:10]:
    print(f" - Share ID: {share.id}, From: {share.shared_by.name}, To: {share.shared_with.name}, Session: {share.clip_reel.session_id if share.clip_reel else 'N/A'}")

print(f"--- DEBUG END ---")
