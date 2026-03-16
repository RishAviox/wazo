#!/usr/bin/env python3
"""
Debug script to check why the shared-with-me endpoint returns empty results.
"""

import os
import sys
import django

# Setup Django environment
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'wajo_backend.settings')
django.setup()

from tracevision.models import TraceClipReelShare, TraceSession
from accounts.models import WajoUser

# Get a share
share = TraceClipReelShare.objects.filter(is_active=True).select_related(
    'clip_reel__session', 'shared_with'
).first()

if not share:
    print("No shares found")
    sys.exit(1)

session = share.clip_reel.session
user = share.shared_with

print(f"Share Info:")
print(f"  - Clip Reel ID: {share.clip_reel.id}")
print(f"  - Session DB ID: {session.id}")
print(f"  - Session TraceVision ID: {session.session_id}")
print(f"  - Shared with: {user.name} (ID: {user.id})")
print()

# Now check what the query returns
print("Testing the query used in the endpoint:")
print(f"  clip_reel__session_id={session.session_id}")
print()

shares_by_session_id = TraceClipReelShare.objects.filter(
    shared_with=user,
    is_active=True,
    clip_reel__session_id=session.session_id
)

print(f"Results: {shares_by_session_id.count()} share(s) found")

if shares_by_session_id.count() == 0:
    print("\n❌ The filter is not working!")
    print("   Checking what session_id values exist in the database...")
    
    # Check all sessions
    all_sessions = TraceSession.objects.all()[:5]
    print(f"\n   Sample sessions:")
    for s in all_sessions:
        print(f"     - DB ID: {s.id}, session_id: '{s.session_id}' (type: {type(s.session_id).__name__})")
    
    # Check the specific session
    print(f"\n   Current session:")
    print(f"     - DB ID: {session.id}")
    print(f"     - session_id: '{session.session_id}' (type: {type(session.session_id).__name__})")
    print(f"     - session_id repr: {repr(session.session_id)}")
    
    # Try filtering by the database ID instead
    print(f"\n   Trying filter by database ID (session__id={session.id}):")
    shares_by_db_id = TraceClipReelShare.objects.filter(
        shared_with=user,
        is_active=True,
        clip_reel__session__id=session.id
    )
    print(f"   Results: {shares_by_db_id.count()} share(s) found")
else:
    print("✅ Query is working correctly!")
    for s in shares_by_session_id:
        print(f"  - Share ID: {s.id}, Clip Reel: {s.clip_reel.id}")
