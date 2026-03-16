"""
Quick diagnostic to check why shared highlights aren't appearing.

Run this to debug:
    python debug_shared_highlights.py
"""

import os
import sys
import django

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'wazo.settings')
django.setup()

from tracevision.models import TraceClipReelShare, TraceHighlight
from accounts.models import WajoUser

# Get the logged-in user (replace with actual user ID from token)
user_id = "e18f2355-d6ba-4d31-8a07-3661aab95081"  # From your token
user = WajoUser.objects.get(id=user_id)

print(f"\n{'='*70}")
print(f"  DEBUGGING SHARED HIGHLIGHTS")
print(f"  User: {user.name or user.email} (Role: {user.role})")
print(f"{'='*70}\n")

# Get all active shares for this user
shares = TraceClipReelShare.objects.filter(
    shared_with=user,
    is_active=True
).select_related('clip_reel', 'highlight', 'highlight__session')

print(f"Total active shares: {shares.count()}\n")

# Group by session
sessions = {}
for share in shares:
    session_id = share.highlight.session.id
    if session_id not in sessions:
        sessions[session_id] = []
    sessions[session_id].append(share)

print(f"Shares across {len(sessions)} sessions:\n")

for session_id, session_shares in sessions.items():
    print(f"Session {session_id}:")
    highlight_ids = set()
    clip_ids = []
    
    for share in session_shares:
        highlight_ids.add(share.highlight.id)
        clip_ids.append(share.clip_reel.id)
        print(f"  - Highlight {share.highlight.id}, Clip {share.clip_reel.id}")
    
    print(f"  Summary: {len(highlight_ids)} highlights, {len(clip_ids)} clips\n")

# Test the query that the view uses
print(f"\n{'='*70}")
print(f"  TESTING VIEW QUERY")
print(f"{'='*70}\n")

from django.db.models import Q

for session_id in sessions.keys():
    print(f"Session {session_id}:")
    
    # This is the query the view uses
    shared_filter = Q(reel_shares__shared_with=user, reel_shares__is_active=True)
    
    highlights = TraceHighlight.objects.filter(
        session_id=session_id
    ).filter(shared_filter).distinct()
    
    print(f"  Highlights with shared filter: {highlights.count()}")
    for hl in highlights:
        print(f"    - Highlight {hl.id}: {hl.event_type}")
    
    print()

print(f"\n{'='*70}")
print(f"  RECOMMENDATION")
print(f"{'='*70}\n")

if sessions:
    session_id = list(sessions.keys())[0]
    print(f"Call: GET /api/vision/highlights/{session_id}/")
    print(f"This should show {len(sessions[session_id])} shared clips")
else:
    print("No active shares found!")
