# TraceClipReel Comment System API Documentation

## Overview
This document provides comprehensive API documentation for the TraceClipReel comment system, including sharing, commenting, liking, replying, captions, and private notes functionality.

## Base URL
```
http://your-domain.com/api/tracevision/
```

## Authentication
All endpoints require authentication using JWT token or session authentication.

### Headers
```
Authorization: Bearer <your_jwt_token>
Content-Type: application/json
```

## Table of Contents
1. [Clip Reel Sharing APIs](#clip-reel-sharing-apis)
2. [Comment APIs](#comment-apis)
3. [Reply APIs](#reply-apis)
4. [Like/Unlike APIs](#likeunlike-apis)
5. [Caption APIs](#caption-apis)
6. [Note APIs](#note-apis)
7. [Error Codes](#error-codes)
8. [Usage Examples](#usage-examples)

---

## Clip Reel Sharing APIs

### 1. Share Clip Reel with User

Share a clip reel with another user, granting them access and optional commenting permission.

**Endpoint:** `POST /api/tracevision/clip-reels/{id}/share/`

**Permission:** Only reel owner can share

**Request Body:**
```json
{
  "shared_with_id": "user-uuid-here",
  "can_comment": true
}
```

**Response (201 Created):**
```json
{
  "message": "Reel shared successfully",
  "data": {
    "id": 1,
    "clip_reel": 5,
    "highlight": 10,
    "shared_by": {
      "id": "uuid",
      "name": "John Doe",
      "phone_no": "+1234567890",
      "role": "Player",
      "picture": null,
      "jersey_number": 10
    },
    "shared_with_user": {
      "id": "uuid2",
      "name": "Jane Smith",
      "phone_no": "+0987654321",
      "role": "Player",
      "picture": null,
      "jersey_number": 7
    },
    "can_comment": true,
    "shared_at": "2024-01-15T10:30:00Z",
    "is_active": true
  }
}
```

**cURL Example:**
```bash
curl -X POST "http://your-domain.com/api/tracevision/clip-reels/5/share/" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "shared_with_id": "550e8400-e29b-41d4-a716-446655440000",
    "can_comment": true
  }'
```

**Error Responses:**
- `400 Bad Request`: Cannot share with yourself
- `403 Forbidden`: Only owner can share the reel
- `404 Not Found`: Clip reel not found

---

### 2. List Reel Shares

View all users a clip reel has been shared with.

**Endpoint:** `GET /api/tracevision/clip-reels/{id}/shares/`

**Permission:** Only reel owner

**Response (200 OK):**
```json
{
  "shares": [
    {
      "id": 1,
      "shared_with_user": {
        "id": "uuid",
        "name": "Jane Smith",
        "phone_no": "+0987654321",
        "role": "Player"
      },
      "can_comment": true,
      "shared_at": "2024-01-15T10:30:00Z",
      "is_active": true
    }
  ]
}
```

**cURL Example:**
```bash
curl -X GET "http://your-domain.com/api/tracevision/clip-reels/5/shares/" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

---

### 3. Revoke Share Access

Revoke a user's access to a clip reel.

**Endpoint:** `DELETE /api/tracevision/clip-reels/{id}/shares/{share_id}/`

**Permission:** Only reel owner

**Response (200 OK):**
```json
{
  "message": "Share revoked successfully"
}
```

**cURL Example:**
```bash
curl -X DELETE "http://your-domain.com/api/tracevision/clip-reels/5/shares/1/" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

---

### 4. List Reels Shared With Me

Get all clip reels that have been shared with the current user.

**Endpoint:** `GET /api/tracevision/clip-reels/shared-with-me/`

**Permission:** Authenticated user

**Response (200 OK):**
```json
{
  "clip_reels": [
    {
      "id": 5,
      "session": 10,
      "highlight": 15,
      "event_type": "goal",
      "video_url": "https://...",
      "caption": "Amazing goal!",
      "created_at": "2024-01-15T10:00:00Z"
    }
  ]
}
```

**cURL Example:**
```bash
curl -X GET "http://your-domain.com/api/tracevision/clip-reels/shared-with-me/" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

---

## Comment APIs

### 5. Add Comment to Clip Reel

Add a public or private comment to a clip reel.

**Endpoint:** `POST /api/tracevision/clip-reels/{id}/comments/`

**Permission:** User must have access and can_comment permission

**Request Body:**
```json
{
  "content": "Great play! Really impressed with the positioning.",
  "visibility": "public",
  "mentions": [
    {
      "user_id": "uuid-here",
      "username": "JohnDoe"
    }
  ]
}
```

**Visibility Options:**
- `public`: Visible to all users with reel access
- `private`: Visible only to reel owner and comment author

**Response (201 Created):**
```json
{
  "message": "Comment added successfully",
  "data": {
    "id": 1,
    "clip_reel": 5,
    "highlight": 10,
    "author": {
      "id": "uuid",
      "name": "John Doe",
      "phone_no": "+1234567890",
      "role": "Coach",
      "picture": null
    },
    "content": "Great play! Really impressed with the positioning.",
    "visibility": "public",
    "parent_comment": null,
    "mentions": [
      {
        "user_id": "uuid-here",
        "username": "JohnDoe"
      }
    ],
    "is_edited": false,
    "is_deleted": false,
    "likes_count": 0,
    "replies_count": 0,
    "is_liked": false,
    "created_at": "2024-01-15T11:00:00Z",
    "updated_at": "2024-01-15T11:00:00Z"
  }
}
```

**cURL Example:**
```bash
curl -X POST "http://your-domain.com/api/tracevision/clip-reels/5/comments/" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "Great play! Really impressed with the positioning.",
    "visibility": "public",
    "mentions": []
  }'
```

---

### 6. List Comments on Clip Reel

Get all comments on a clip reel (filtered by visibility and access).

**Endpoint:** `GET /api/tracevision/clip-reels/{id}/comments/`

**Permission:** User must have reel access

**Query Parameters:**
- None (automatically filters based on user permissions)

**Response (200 OK):**
```json
{
  "comments": [
    {
      "id": 1,
      "author": {
        "id": "uuid",
        "name": "John Doe",
        "phone_no": "+1234567890",
        "role": "Coach"
      },
      "content": "Great play!",
      "visibility": "public",
      "likes_count": 5,
      "replies_count": 2,
      "is_liked": true,
      "created_at": "2024-01-15T11:00:00Z"
    }
  ]
}
```

**cURL Example:**
```bash
curl -X GET "http://your-domain.com/api/tracevision/clip-reels/5/comments/" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

---

### 7. Edit Comment

Edit an existing comment (creates edit history entry).

**Endpoint:** `PATCH /api/tracevision/comments/{id}/`

**Permission:** Only comment author

**Request Body:**
```json
{
  "content": "Updated comment content",
  "mentions": []
}
```

**Response (200 OK):**
```json
{
  "message": "Comment updated successfully",
  "data": {
    "id": 1,
    "content": "Updated comment content",
    "is_edited": true,
    "updated_at": "2024-01-15T12:00:00Z"
  }
}
```

**cURL Example:**
```bash
curl -X PATCH "http://your-domain.com/api/tracevision/comments/1/" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "Updated comment content"
  }'
```

---

### 8. Delete Comment

Soft delete a comment (preserves data, marks as deleted).

**Endpoint:** `DELETE /api/tracevision/comments/{id}/`

**Permission:** Only comment author

**Response (200 OK):**
```json
{
  "message": "Comment deleted successfully"
}
```

**cURL Example:**
```bash
curl -X DELETE "http://your-domain.com/api/tracevision/comments/1/" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

---

## Reply APIs

### 9. Add Reply to Comment

Add a threaded reply to an existing comment.

**Endpoint:** `POST /api/tracevision/comments/{id}/reply/`

**Permission:** User must have comment access and can_comment permission

**Request Body:**
```json
{
  "content": "I agree! The timing was perfect.",
  "visibility": "public"
}
```

**Response (201 Created):**
```json
{
  "message": "Reply added successfully",
  "data": {
    "id": 2,
    "parent_comment": 1,
    "author": {
      "id": "uuid",
      "name": "Jane Smith"
    },
    "content": "I agree! The timing was perfect.",
    "created_at": "2024-01-15T11:30:00Z"
  }
}
```

**cURL Example:**
```bash
curl -X POST "http://your-domain.com/api/tracevision/comments/1/reply/" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "I agree! The timing was perfect.",
    "visibility": "public"
  }'
```

---

### 10. List Replies to Comment

Get all replies to a specific comment.

**Endpoint:** `GET /api/tracevision/comments/{id}/replies/`

**Permission:** User must have access to parent comment

**Response (200 OK):**
```json
{
  "replies": [
    {
      "id": 2,
      "parent_comment": 1,
      "author": {
        "id": "uuid",
        "name": "Jane Smith"
      },
      "content": "I agree! The timing was perfect.",
      "likes_count": 2,
      "created_at": "2024-01-15T11:30:00Z"
    }
  ]
}
```

**cURL Example:**
```bash
curl -X GET "http://your-domain.com/api/tracevision/comments/1/replies/" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

---

## Like/Unlike APIs

### 11. Like Comment

Like a comment.

**Endpoint:** `POST /api/tracevision/comments/{id}/like/`

**Permission:** User must have access to comment

**Response (201 Created):**
```json
{
  "message": "Comment liked successfully",
  "likes_count": 6
}
```

**cURL Example:**
```bash
curl -X POST "http://your-domain.com/api/tracevision/comments/1/like/" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

**Error Response (400):**
```json
{
  "error": "You have already liked this comment."
}
```

---

### 12. Unlike Comment

Remove like from a comment.

**Endpoint:** `DELETE /api/tracevision/comments/{id}/like/`

**Permission:** User must have previously liked the comment

**Response (200 OK):**
```json
{
  "message": "Comment unliked successfully",
  "likes_count": 5
}
```

**cURL Example:**
```bash
curl -X DELETE "http://your-domain.com/api/tracevision/comments/1/like/" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

---

## Caption APIs

### 13. Add/Update Caption

Add or update the caption for a clip reel.

**Endpoint:** `PATCH /api/tracevision/clip-reels/{id}/caption/`

**Permission:** Only reel owner

**Request Body:**
```json
{
  "caption": "My best goal of the season! Thanks to the team for the assist."
}
```

**Response (200 OK):**
```json
{
  "message": "Caption updated successfully",
  "data": {
    "caption": "My best goal of the season! Thanks to the team for the assist."
  }
}
```

**cURL Example:**
```bash
curl -X PATCH "http://your-domain.com/api/tracevision/clip-reels/5/caption/" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "caption": "My best goal of the season! Thanks to the team for the assist."
  }'
```

---

## Note APIs

### 14. Create Private Note

Create a private note on a clip reel (Players and Coaches only).

**Endpoint:** `POST /api/tracevision/clip-reels/{id}/notes/`

**Permission:** User must be Player or Coach

**Request Body:**
```json
{
  "content": "Focus on improving positioning in similar situations. Good awareness but timing could be better."
}
```

**Response (201 Created):**
```json
{
  "message": "Note created successfully",
  "data": {
    "id": 1,
    "clip_reel": 5,
    "highlight": 10,
    "author": {
      "id": "uuid",
      "name": "Coach Mike",
      "role": "Coach"
    },
    "content": "Focus on improving positioning in similar situations.",
    "is_deleted": false,
    "is_shared": false,
    "shared_with_count": 0,
    "created_at": "2024-01-15T13:00:00Z"
  }
}
```

**cURL Example:**
```bash
curl -X POST "http://your-domain.com/api/tracevision/clip-reels/5/notes/" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "Focus on improving positioning in similar situations."
  }'
```

---

### 15. List Notes on Clip Reel

Get all notes on a clip reel that the user has access to.

**Endpoint:** `GET /api/tracevision/clip-reels/{id}/notes/`

**Permission:** User must have access to view the notes

**Response (200 OK):**
```json
{
  "notes": [
    {
      "id": 1,
      "author": {
        "id": "uuid",
        "name": "Coach Mike",
        "role": "Coach"
      },
      "content": "Focus on improving positioning.",
      "is_shared": true,
      "shared_with_count": 2,
      "created_at": "2024-01-15T13:00:00Z"
    }
  ]
}
```

**cURL Example:**
```bash
curl -X GET "http://your-domain.com/api/tracevision/clip-reels/5/notes/" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

---

### 16. Edit Note

Edit an existing note.

**Endpoint:** `PATCH /api/tracevision/notes/{id}/`

**Permission:** Only note author

**Request Body:**
```json
{
  "content": "Updated note content with more details."
}
```

**Response (200 OK):**
```json
{
  "message": "Note updated successfully",
  "data": {
    "id": 1,
    "content": "Updated note content with more details.",
    "updated_at": "2024-01-15T14:00:00Z"
  }
}
```

**cURL Example:**
```bash
curl -X PATCH "http://your-domain.com/api/tracevision/notes/1/" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "Updated note content with more details."
  }'
```

---

### 17. Delete Note

Soft delete a note.

**Endpoint:** `DELETE /api/tracevision/notes/{id}/`

**Permission:** Only note author

**Response (200 OK):**
```json
{
  "message": "Note deleted successfully"
}
```

**cURL Example:**
```bash
curl -X DELETE "http://your-domain.com/api/tracevision/notes/1/" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

---

### 18. Share Note with User or Group

Share a note with a specific user or group of users.

**Endpoint:** `POST /api/tracevision/notes/{id}/share/`

**Permission:** Only note author

**Request Body (Share with specific user):**
```json
{
  "shared_with_user_id": "user-uuid-here"
}
```

**Request Body (Share with group):**
```json
{
  "shared_with_group": "team_coaches"
}
```

**Group Options:**
- `team_coaches`: All coaches of the author's team
- `player_coach`: Author's assigned coach(es)

**Response (201 Created):**
```json
{
  "message": "Note shared successfully",
  "data": {
    "id": 1,
    "note": 1,
    "shared_by": {
      "id": "uuid",
      "name": "Coach Mike"
    },
    "shared_with_user_details": {
      "id": "uuid2",
      "name": "John Doe",
      "role": "Player"
    },
    "shared_with_group": null,
    "shared_at": "2024-01-15T14:30:00Z",
    "is_active": true
  }
}
```

**cURL Example (Share with user):**
```bash
curl -X POST "http://your-domain.com/api/tracevision/notes/1/share/" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "shared_with_user_id": "550e8400-e29b-41d4-a716-446655440000"
  }'
```

**cURL Example (Share with group):**
```bash
curl -X POST "http://your-domain.com/api/tracevision/notes/1/share/" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "shared_with_group": "team_coaches"
  }'
```

---

### 19. Revoke Note Share

Revoke access to a shared note.

**Endpoint:** `DELETE /api/tracevision/notes/{id}/shares/{share_id}/`

**Permission:** Only note author

**Response (200 OK):**
```json
{
  "message": "Note share revoked successfully"
}
```

**cURL Example:**
```bash
curl -X DELETE "http://your-domain.com/api/tracevision/notes/1/shares/5/" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

---

## Error Codes

### Common HTTP Status Codes

| Status Code | Description |
|-------------|-------------|
| 200 | OK - Request successful |
| 201 | Created - Resource created successfully |
| 400 | Bad Request - Invalid request data |
| 401 | Unauthorized - Authentication required |
| 403 | Forbidden - Insufficient permissions |
| 404 | Not Found - Resource not found |
| 500 | Internal Server Error - Server error |

### Error Response Format

```json
{
  "error": "Error message description",
  "details": {
    "field_name": ["Specific error details"]
  }
}
```

### Common Error Messages

**Authentication Errors:**
- `Authentication credentials were not provided.`
- `Invalid token.`

**Permission Errors:**
- `You don't have permission to comment on this reel.`
- `Only the reel owner can share it.`
- `Only the comment author can edit it.`
- `Only Players and Coaches can create notes.`

**Validation Errors:**
- `Cannot share with yourself.`
- `You have already liked this comment.`
- `Must specify either a user or a group to share with.`
- `Cannot share with both a user and a group.`

---

## Usage Examples

### Example 1: Complete Comment Flow

```bash
# 1. Share reel with another user
curl -X POST "http://your-domain.com/api/tracevision/clip-reels/5/share/" \
  -H "Authorization: Bearer TOKEN" \
  -d '{"shared_with_id": "uuid", "can_comment": true}'

# 2. Shared user adds a comment
curl -X POST "http://your-domain.com/api/tracevision/clip-reels/5/comments/" \
  -H "Authorization: Bearer TOKEN2" \
  -d '{"content": "Great play!", "visibility": "public"}'

# 3. Owner likes the comment
curl -X POST "http://your-domain.com/api/tracevision/comments/1/like/" \
  -H "Authorization: Bearer TOKEN"

# 4. Owner adds a reply
curl -X POST "http://your-domain.com/api/tracevision/comments/1/reply/" \
  -H "Authorization: Bearer TOKEN" \
  -d '{"content": "Thanks!", "visibility": "public"}'
```

### Example 2: Coach Note Workflow

```bash
# 1. Coach creates private note
curl -X POST "http://your-domain.com/api/tracevision/clip-reels/5/notes/" \
  -H "Authorization: Bearer COACH_TOKEN" \
  -d '{"content": "Work on positioning"}'

# 2. Coach shares note with player
curl -X POST "http://your-domain.com/api/tracevision/notes/1/share/" \
  -H "Authorization: Bearer COACH_TOKEN" \
  -d '{"shared_with_user_id": "player-uuid"}'

# 3. Coach shares note with all team coaches
curl -X POST "http://your-domain.com/api/tracevision/notes/1/share/" \
  -H "Authorization: Bearer COACH_TOKEN" \
  -d '{"shared_with_group": "team_coaches"}'
```

### Example 3: Caption Management

```bash
# 1. Player adds caption to their reel
curl -X PATCH "http://your-domain.com/api/tracevision/clip-reels/5/caption/" \
  -H "Authorization: Bearer PLAYER_TOKEN" \
  -d '{"caption": "My best goal this season!"}'

# 2. Player updates caption
curl -X PATCH "http://your-domain.com/api/tracevision/clip-reels/5/caption/" \
  -H "Authorization: Bearer PLAYER_TOKEN" \
  -d '{"caption": "Updated: Best goal ever!"}'
```

---

## Access Control Summary

### Clip Reel Access
- **Owner**: Full access (share, comment, caption, view all comments)
- **Shared Users**: Access based on share permissions (view, optionally comment)
- **Others**: No access

### Comment Visibility
- **Public Comments**: Visible to all users with reel access
- **Private Comments**: Visible only to author and reel owner

### Note Visibility
- **Author**: Always visible
- **Shared Users**: Visible when explicitly shared
- **Group Shares**: Visible to all team coaches or player's assigned coach

### Permissions Matrix

| Action | Owner | Shared User (can_comment) | Shared User (no comment) | Other |
|--------|-------|---------------------------|--------------------------|-------|
| View Reel | ✅ | ✅ | ✅ | ❌ |
| Share Reel | ✅ | ❌ | ❌ | ❌ |
| Add Caption | ✅ | ❌ | ❌ | ❌ |
| Add Comment | ✅ | ✅ | ❌ | ❌ |
| View Public Comments | ✅ | ✅ | ✅ | ❌ |
| View Private Comments | ✅ (all) | ❌ | ❌ | ❌ |
| Edit Own Comment | ✅ | ✅ | ✅ | ✅ |
| Like Comment | ✅ | ✅ | ✅ | ❌ |
| Create Note | ✅ (if Player/Coach) | ✅ (if Player/Coach) | ✅ (if Player/Coach) | ❌ |
| View Own Notes | ✅ | ✅ | ✅ | ✅ |
| View Shared Notes | ✅ (if shared) | ✅ (if shared) | ✅ (if shared) | ✅ (if shared) |

---

## Best Practices

1. **Always check response status codes** - Don't assume success
2. **Handle 403 errors gracefully** - User may not have required permissions
3. **Use pagination** - For listing endpoints with many results
4. **Validate mentions** - Ensure mentioned users have reel access
5. **Rate limiting** - Be mindful of API rate limits on write operations
6. **Soft deletes** - Remember deleted items are preserved, not removed
7. **Edit history** - All comment edits are tracked and can be audited
8. **Share management** - Regularly review and revoke unnecessary shares

---

## Support

For issues, questions, or feature requests, please contact the development team or create an issue in the project repository.

**Version:** 1.0  
**Last Updated:** January 2024

