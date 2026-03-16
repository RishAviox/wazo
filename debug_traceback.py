import os
import django
import uuid
import traceback

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'wajo_backend.settings_dev')
os.environ.setdefault('DJANGO_DATABASE', 'docker')
django.setup()

from accounts.models import WajoUser
from tracevision.models import TraceClipReelShare
from tracevision.serializers import SharedWithMeGroupSerializer
from itertools import groupby
from operator import attrgetter

user_id_str = "0b02a749-43a2-4cbe-b4dc-f19ba726f00c" # Amit Shimon
session_id = "36"

print(f"--- SIMULATING VIEW FOR SESSION {session_id} ---")
try:
    user = WajoUser.objects.get(id=user_id_str)
    print(f"User: {user}")
    
    shares = (
        TraceClipReelShare.objects.filter(
            shared_with=user, 
            is_active=True,
            clip_reel__session_id=session_id
        )
        .select_related("clip_reel", "highlight", "shared_by", "clip_reel__primary_player")
        .order_by("shared_by__id", "-shared_at")
    )
    
    print(f"Found {shares.count()} shares")
    
    grouped_shares = []
    for shared_by_user, user_shares in groupby(shares, key=attrgetter("shared_by")):
        user_shares_list = list(user_shares)
        grouped_shares.append({
            "shared_by": shared_by_user,
            "clip_reels": user_shares_list
        })
    
    print(f"Grouped into {len(grouped_shares)} groups")
    
    # Mock request for context
    class MockRequest:
        def __init__(self, user):
            self.user = user

    serializer = SharedWithMeGroupSerializer(
        grouped_shares, many=True, context={"request": MockRequest(user)}
    )
    
    print("Serializing...")
    data = serializer.data
    print("Serialization successful!")
    # print(data)

except Exception as e:
    print("\n--- ERROR DETECTED ---")
    print(f"Exception Type: {type(e).__name__}")
    print(f"Exception Message: {str(e)}")
    traceback.print_exc()

print(f"--- DEBUG END ---")
