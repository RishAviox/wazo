from accounts.models import WajoUser
from tracevision.models import TraceClipReel, TraceClipReelShare

user_id = "90bd4190-bbf5-4b60-8fdf-39b10f23b7ab"
session_id = "1"

print(f"--- DEBUG START ---")
print(f"Checking user: {user_id}")
user = WajoUser.objects.filter(id=user_id).first()
if user:
    print(f"User found: {user.name} (Role: {getattr(user, 'role', 'N/A')}, Email: {user.email})")
else:
    print("User NOT found")

print(f"\nChecking active shares for User ID {user_id} and session_id {session_id}")
shares = TraceClipReelShare.objects.filter(
    shared_with_id=user_id,
    is_active=True,
    clip_reel__session_id=session_id
)
print(f"Found {shares.count()} active shares for session {session_id}")
for share in shares:
    print(f" - Share ID: {share.id}, Reel ID: {share.clip_reel_id}, Shared By: {share.shared_by} ({share.shared_by.id})")

print(f"\nChecking ALL active shares for User ID {user_id}")
all_shares = TraceClipReelShare.objects.filter(shared_with_id=user_id, is_active=True)
print(f"Found {all_shares.count()} total active shares for this user")

# Print unique session IDs in shares
sessions_in_shares = TraceClipReelShare.objects.filter(
    shared_with_id=user_id, 
    is_active=True
).values_list('clip_reel__session_id', flat=True).distinct()
print(f"Sessions with shares for this user: {list(sessions_in_shares)}")

print(f"--- DEBUG END ---")
