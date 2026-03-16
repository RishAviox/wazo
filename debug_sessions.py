import os
import django
import uuid

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'wajo_backend.settings_dev')
os.environ.setdefault('DJANGO_DATABASE', 'docker')
django.setup()

from tracevision.models import TraceClipReel, TraceClipReelShare

print(f"--- SESSIONS IN CLIP REELS ---")
sessions = TraceClipReel.objects.values_list('session_id', flat=True).distinct()
for sid in sessions:
    count = TraceClipReel.objects.filter(session_id=sid).count()
    print(f"Session ID: {sid}, Clip Reel Count: {count}")

print(f"\n--- SESSIONS IN SHARES ---")
share_sessions = TraceClipReelShare.objects.values_list('clip_reel__session_id', flat=True).distinct()
for sid in share_sessions:
    count = TraceClipReelShare.objects.filter(clip_reel__session_id=sid).count()
    print(f"Session ID: {sid}, Share Count: {count}")

print(f"--- DEBUG END ---")
