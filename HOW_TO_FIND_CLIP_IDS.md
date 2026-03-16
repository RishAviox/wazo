# How to Find Valid Clip IDs

There are several API endpoints you can use to find valid `clip_id` values for sharing:

## Method 1: List All Clip Reels (Paginated)

**Endpoint:** `GET /api/vision/clip-reels/`

**Example:**
```bash
curl --location 'http://127.0.0.1:8003/api/vision/clip-reels/' \
  --header 'Authorization: Bearer YOUR_TOKEN'
```

**Response:**
```json
{
  "count": 100,
  "next": "http://127.0.0.1:8003/api/vision/clip-reels/?page=2",
  "previous": null,
  "results": [
    {
      "id": 108,
      "highlight_id": "18",
      "event_type": "goal",
      "video_url": "...",
      "primary_player": {...}
    },
    ...
  ]
}
```

**Extract clip IDs:**
```bash
curl 'http://127.0.0.1:8003/api/vision/clip-reels/' \
  -H 'Authorization: Bearer YOUR_TOKEN' \
  | jq '.results[].id'
```

---

## Method 2: Get Clip Reels for a Specific Session

**Endpoint:** `GET /api/vision/sessions/{session_id}/highlights/`

This returns highlights with their associated clip reels.

**Example:**
```bash
curl --location 'http://127.0.0.1:8003/api/vision/sessions/123/highlights/' \
  --header 'Authorization: Bearer YOUR_TOKEN'
```

**Extract clip IDs:**
```bash
curl 'http://127.0.0.1:8003/api/vision/sessions/123/highlights/' \
  -H 'Authorization: Bearer YOUR_TOKEN' \
  | jq '.results[].clip_reels[].id'
```

---

## Method 3: Get Clip Reels Shared With You (Grouped by Sharer)

**Endpoint:** `GET /api/vision/clip-reels/shared-with-me/`

**Description:** Returns all clip reels that have been shared with the logged-in user, grouped by the user who shared them.

**Example:**
```bash
curl --location 'http://127.0.0.1:8003/api/vision/clip-reels/shared-with-me/' \
  --header 'Authorization: Bearer YOUR_TOKEN'
```

**Response Format:**
```json
[
  {
    "shared_by": {
      "id": "uuid",
      "name": "Ilay GAT",
      "phone_no": "",
      "role": "Player",
      "jersey_number": 11
    },
    "clip_reels": [
      {
        "trace_vision_id": 1,
        "highlight_id": 10,
        "clip_id": 55,
        "url": "https://example.com/video.mp4",
        "ratio": "original",
        "event_type": "goal",
        "event_name": "Goal at 19:00",
        "label": "Goal - Home",
        "primary_player": {...},
        "shared_at": "2026-01-16T11:30:00Z",
        "can_comment": true,
        "can_write_note": true,
        "can_share": true
      }
    ]
  }
]
```


## Method 4: Get Clip Reels You've Shared

**Endpoint:** `GET /api/vision/clip-reels/shared-by-me/`

**Example:**
```bash
curl --location 'http://127.0.0.1:8003/api/vision/clip-reels/shared-by-me/' \
  --header 'Authorization: Bearer YOUR_TOKEN'
```

---

## Method 5: Get a Specific Clip Reel

**Endpoint:** `GET /api/vision/clip-reels/{clip_id}/`

Verify a clip ID exists:

**Example:**
```bash
curl --location 'http://127.0.0.1:8003/api/vision/clip-reels/108/' \
  --header 'Authorization: Bearer YOUR_TOKEN'
```

If the clip exists, you'll get full details. If not, you'll get a 404 error.

---

## Quick Reference Commands

### Get first 5 clip IDs
```bash
curl 'http://127.0.0.1:8003/api/vision/clip-reels/' \
  -H 'Authorization: Bearer YOUR_TOKEN' \
  | jq '.results[:5] | .[] | {id: .id, highlight_id: .highlight_id, event_type: .event_type}'
```

### Get clip IDs for a specific player
```bash
curl 'http://127.0.0.1:8003/api/vision/clip-reels/' \
  -H 'Authorization: Bearer YOUR_TOKEN' \
  | jq '.results[] | select(.primary_player.id == "PLAYER_ID") | .id'
```

### Check if a clip ID is valid
```bash
curl -I 'http://127.0.0.1:8003/api/vision/clip-reels/108/' \
  -H 'Authorization: Bearer YOUR_TOKEN'
# Returns 200 if valid, 404 if not
```

---

## Common Workflow

1. **List available sessions:**
   ```bash
   GET /api/vision/sessions/{session_id}/highlights/
   ```

2. **Browse clip reels in the response** - each highlight contains `clip_reels` array

3. **Pick a clip_id** from the results

4. **Share the clip:**
   ```bash
   POST /api/vision/highlights/share/
   {
     "clip_id": 108,
     "user_ids": ["user-uuid"],
     "can_comment": true
   }
   ```
