#!/usr/bin/env python3
"""
Script to find clip reel IDs for testing.
"""

import os
import sys
import django

# Setup Django environment
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'wajo_backend.settings')
django.setup()

from tracevision.models import TraceClipReel, TraceClipReelShare
from accounts.models import WajoUser

print("=" * 80)
print("FINDING CLIP REEL IDs FOR TESTING")
print("=" * 80)
print()

# Get all users
users = WajoUser.objects.all()[:5]
print(f"Available Users:")
print("-" * 80)
for user in users:
    print(f"  - {user.name or user.email} (ID: {user.id}, Role: {user.role})")
print()

# Get shared clip reels
shares = TraceClipReelShare.objects.filter(is_active=True).select_related(
    'clip_reel', 'clip_reel__session', 'shared_with', 'shared_by'
)[:10]

if shares.exists():
    print(f"Shared Clip Reels (for testing):")
    print("-" * 80)
    
    for i, share in enumerate(shares, 1):
        print(f"\n{i}. Clip Reel ID: {share.clip_reel.id}")
        print(f"   Session ID: {share.clip_reel.session.session_id}")
        print(f"   Shared by: {share.shared_by.name or share.shared_by.email}")
        print(f"   Shared with: {share.shared_with.name or share.shared_with.email}")
        print(f"   URL: {share.clip_reel.video_url or 'N/A'}")
        
        # Show curl command example
        if i == 1:
            print()
            print("   📝 Example curl commands for this clip reel:")
            print(f"   # Add a comment:")
            print(f"   curl --location 'http://127.0.0.1:8003/api/vision/clip-reels/{share.clip_reel.id}/comments/' \\")
            print(f"   --header 'Authorization: Bearer YOUR_TOKEN' \\")
            print(f"   --header 'Content-Type: application/json' \\")
            print(f"   --data '{{\"content\": \"Great play!\", \"visibility\": \"public\"}}'")
            print()
            print(f"   # Add a note:")
            print(f"   curl --location 'http://127.0.0.1:8003/api/vision/clip-reels/{share.clip_reel.id}/notes/' \\")
            print(f"   --header 'Authorization: Bearer YOUR_TOKEN' \\")
            print(f"   --header 'Content-Type: application/json' \\")
            print(f"   --data '{{\"content\": \"Need to improve positioning.\"}}'")
            print()
            print(f"   # View in shared-with-me:")
            print(f"   curl --location 'http://127.0.0.1:8003/api/vision/clip-reels/shared-with-me/{share.clip_reel.session.session_id}/' \\")
            print(f"   --header 'Authorization: Bearer YOUR_TOKEN'")
else:
    print("❌ No shared clip reels found in the database.")
    print()
    
    # Show all clip reels
    all_reels = TraceClipReel.objects.all()[:5]
    if all_reels.exists():
        print("All Clip Reels (not necessarily shared):")
        print("-" * 80)
        for reel in all_reels:
            print(f"  - Clip Reel ID: {reel.id}, Session: {reel.session.session_id}")

print()
print("=" * 80)
