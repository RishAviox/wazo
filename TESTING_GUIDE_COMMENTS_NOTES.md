# Testing Guide: Comments and Notes in Shared-With-Me Endpoint

This guide shows you how to manually test the comments and notes functionality in the shared-with-me endpoint.

## Prerequisites

- Docker server running on `http://127.0.0.1:8003`
- Authentication token (Bearer token)
- A clip reel ID to test with
- A trace session ID

## Step-by-Step Testing Process

### Step 1: Get Your Authentication Token

First, you need to log in and get your authentication token. Replace with your actual credentials:

```bash
# Login to get token
curl --location 'http://127.0.0.1:8003/api/auth/login/' \
--header 'Content-Type: application/json' \
--data '{
    "phone_no": "your_phone_number",
    "password": "your_password"
}'
```

**Response will include:**
```json
{
    "access": "your_access_token_here",
    "refresh": "your_refresh_token_here"
}
```

Save the `access` token - you'll use it in all subsequent requests.

---

### Step 2: Find a Clip Reel to Test

You need a clip reel ID. You can get this from the shared-with-me endpoint or from the highlights endpoint.

```bash
# Get shared clip reels for a session
curl --location 'http://127.0.0.1:8003/api/vision/clip-reels/shared-with-me/<trace_session_id>/' \
--header 'Authorization: Bearer YOUR_TOKEN_HERE'
```

**Note the `clip_id` from the response** - you'll use this for adding comments and notes.

---

### Step 3: Add a Comment to the Clip Reel

Use the comments endpoint to add a comment:

```bash
# Add a PUBLIC comment
curl --location 'http://127.0.0.1:8003/api/vision/clip-reels/<clip_id>/comments/' \
--header 'Authorization: Bearer YOUR_TOKEN_HERE' \
--header 'Content-Type: application/json' \
--data '{
    "content": "Great play! This shows excellent positioning.",
    "visibility": "public"
}'
```

**Or add a PRIVATE comment:**

```bash
# Add a PRIVATE comment
curl --location 'http://127.0.0.1:8003/api/vision/clip-reels/<clip_id>/comments/' \
--header 'Authorization: Bearer YOUR_TOKEN_HERE' \
--header 'Content-Type: application/json' \
--data '{
    "content": "This is a private note for the coach.",
    "visibility": "private"
}'
```

**Expected Response:**
```json
{
    "id": 123,
    "content": "Great play! This shows excellent positioning.",
    "visibility": "public",
    "author": {
        "id": "uuid",
        "name": "Your Name"
    },
    "created_at": "2026-02-17T..."
}
```

---

### Step 4: Add a Note to the Clip Reel

Use the notes endpoint to add a note:

```bash
# Add a note (notes are private by default)
curl --location 'http://127.0.0.1:8003/api/vision/clip-reels/<clip_id>/notes/' \
--header 'Authorization: Bearer YOUR_TOKEN_HERE' \
--header 'Content-Type: application/json' \
--data '{
    "content": "Need to work on footwork in this situation."
}'
```

**To share the note with a coach:**

```bash
# Add a note and share with a specific coach
curl --location 'http://127.0.0.1:8003/api/vision/clip-reels/<clip_id>/notes/' \
--header 'Authorization: Bearer YOUR_TOKEN_HERE' \
--header 'Content-Type: application/json' \
--data '{
    "content": "Coach, please review my positioning here.",
    "share_with_coach_id": "coach_uuid_here"
}'
```

**Or share with all team coaches:**

```bash
# Add a note and share with team coaches
curl --location 'http://127.0.0.1:8003/api/vision/clip-reels/<clip_id>/notes/' \
--header 'Authorization: Bearer YOUR_TOKEN_HERE' \
--header 'Content-Type: application/json' \
--data '{
    "content": "Team coaches, what do you think about this play?",
    "share_with_team_coaches": true
}'
```

**Expected Response:**
```json
{
    "message": "Note created successfully",
    "note": {
        "id": 456,
        "content": "Need to work on footwork in this situation.",
        "author": {
            "id": "uuid",
            "name": "Your Name"
        },
        "is_shared": false,
        "created_at": "2026-02-17T..."
    }
}
```

---

### Step 5: Verify Comments and Notes in Shared-With-Me Endpoint

Now test the shared-with-me endpoint to see both comments and notes:

```bash
# Get shared clip reels with comments and notes
curl --location 'http://127.0.0.1:8003/api/vision/clip-reels/shared-with-me/<trace_session_id>/' \
--header 'Authorization: Bearer YOUR_TOKEN_HERE'
```

**Expected Response:**
```json
[
  {
    "shared_by": {
      "id": "uuid",
      "name": "Player Name",
      "role": "Player"
    },
    "clip_reels": [
      {
        "clip_id": 107,
        "event_name": "Touch at 12:34",
        "url": "https://...",
        "can_comment": true,
        "can_write_note": true,
        "comments": [
          {
            "id": 123,
            "author": {
              "name": "Your Name"
            },
            "content": "Great play! This shows excellent positioning.",
            "visibility": "public",
            "likes_count": 0,
            "replies_count": 0
          }
        ],
        "notes": [
          {
            "id": 456,
            "author": {
              "name": "Your Name"
            },
            "content": "Need to work on footwork in this situation.",
            "is_shared": false,
            "shared_with_count": 0
          }
        ]
      }
    ]
  }
]
```

---

## Quick Test Script

Here's a complete example with placeholder values:

```bash
# 1. Set your variables
TOKEN="your_access_token_here"
CLIP_ID="107"
SESSION_ID="6474094"
BASE_URL="http://127.0.0.1:8003"

# 2. Add a comment
curl --location "$BASE_URL/api/vision/clip-reels/$CLIP_ID/comments/" \
--header "Authorization: Bearer $TOKEN" \
--header 'Content-Type: application/json' \
--data '{
    "content": "Testing comment functionality!",
    "visibility": "public"
}'

# 3. Add a note
curl --location "$BASE_URL/api/vision/clip-reels/$CLIP_ID/notes/" \
--header "Authorization: Bearer $TOKEN" \
--header 'Content-Type: application/json' \
--data '{
    "content": "Testing note functionality!"
}'

# 4. Verify in shared-with-me endpoint
curl --location "$BASE_URL/api/vision/clip-reels/shared-with-me/$SESSION_ID/" \
--header "Authorization: Bearer $TOKEN"
```

---

## Important Notes

### Comments Visibility Rules:
- **Public comments**: Visible to everyone with access to the clip reel
- **Private comments**: Only visible to the clip reel owner and the comment author

### Notes Visibility Rules:
- **Default**: Notes are private, only visible to the author
- **Shared notes**: Visible to users/groups they're shared with
- **Team coaches**: If shared with team coaches, all coaches on the author's team can see it
- **Player's coach**: If shared with player's coach, the assigned coach can see it

### Testing Different Scenarios:

1. **Test as the author**: You should see all your own comments and notes
2. **Test as a recipient**: You should only see:
   - Public comments
   - Notes shared with you
3. **Test with no data**: If a clip reel has no comments/notes, you'll see empty arrays:
   ```json
   {
     "comments": [],
     "notes": []
   }
   ```

---

## Troubleshooting

**Empty response?**
- Check that the clip reel is actually shared with you
- Verify the trace_session_id is correct
- Make sure you're using the right authentication token

**Don't see your comment/note?**
- Check the visibility/sharing settings
- Verify you're testing with the correct user
- Private comments are only visible to owner and author
- Notes are only visible if shared or you're the author
