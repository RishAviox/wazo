# Multilingual Data Processing Update Summary

## Overview
This update adds comprehensive multilingual (English/Hebrew) support for player data, goals, and cards processing from Excel files.

## Changes Made

### 1. Model Updates (`tracevision/models.py`)

#### TracePlayer Model
- **Changed**: `language_data` → `language_metadata` (renamed for consistency)
- **Purpose**: Store multilingual player names and roles
- **Structure**:
  ```json
  {
    "en": {
      "name": "Player Name",
      "role": "GK"
    },
    "he": {
      "name": "שם שחקן",
      "role": "שוער"
    }
  }
  ```

#### TraceHighlight Model
- **Added**: `video_time` field (CharField, max_length=8)
- **Purpose**: Store actual video timestamp when event occurred (e.g., "18:16")
- **Usage**: Differentiates from `match_time` (game clock) vs actual video time

### 2. New Module (`tracevision/multilingual_processing.py`)

Created a comprehensive module for processing multilingual Excel data:

#### Key Functions:

1. **`normalize_multilingual_data(match_data)`**
   - Normalizes English and Hebrew data into unified structure
   - Extracts player data from starting_lineups, replacements, and bench
   - Maps goals with video timestamps
   - Returns structured data with teams and players

2. **`update_player_language_metadata(session, normalized_data)`**
   - Updates TracePlayer.language_metadata with en/he names and roles
   - Finds players by team + jersey_number
   - Updates primary name field (prefers English, falls back to Hebrew)
   - Returns update statistics

3. **`create_highlights_from_normalized_data(session, normalized_data)`**
   - Creates TraceHighlight for goals (when goals > 0)
   - Creates TraceHighlight for cards (when cards > 0)
   - Creates 6 TraceClipReel variations per highlight:
     - 2 ratios: original, 9:16
     - 3 tag combinations: without overlays, with name, with name+circle
   - Returns creation statistics

4. **`_create_goal_highlight()`**
   - Creates goal highlight with event_metadata
   - Sets video_time from Excel data
   - Creates TraceHighlightObject relationship
   - Generates 6 clip reel variations

5. **`_create_card_highlight()`**
   - Creates card highlight (when cards > 0)
   - Similar structure to goal highlights
   - Generates 6 clip reel variations

6. **`_create_clip_reels_for_highlight()`**
   - Creates 6 TraceClipReel entries per highlight
   - Follows same pattern as TraceVisionAggregationService._compute_clips
   - Prevents duplicates by checking existing tags and ratio

### 3. Task Updates (`tracevision/tasks.py`)

#### Updated `process_excel_match_highlights_task`:
- Calls `update_trace_session_multilingual_data()` to update session/game/team names
- Normalizes multilingual data from Excel
- Updates TracePlayer language_metadata
- Creates highlights and clip reels for goals and cards
- Returns comprehensive statistics

#### New Result Structure:
```python
{
    "success": True,
    "session_id": "...",
    "player_updates": {
        "updated_count": 22,
        "not_found_count": 0,
        "total_players": 22,
        "update_details": [...]
    },
    "highlights_created": 9,
    "clip_reels_created": 54,
    "errors": [],
    "match_data_summary": {
        "total_players": 22,
        "total_teams": 2,
        "players_updated": 22,
        "players_not_found": 0
    }
}
```

## Data Flow

```
Excel File (multilingual)
    ↓
extract_multilingual_match_data()
    ↓
normalize_multilingual_data()
    ↓
    ├─→ update_player_language_metadata()
    │   └─→ TracePlayer.language_metadata updated
    │
    └─→ create_highlights_from_normalized_data()
        ├─→ Goals (if goals > 0)
        │   ├─→ TraceHighlight created
        │   └─→ 6 TraceClipReel variations
        │
        └─→ Cards (if cards > 0)
            ├─→ TraceHighlight created
            └─→ 6 TraceClipReel variations
```

## Database Migrations Required

### Step 1: Create Migrations
Run inside Docker container:
```bash
sudo docker exec -it wajo-app bash
python manage.py makemigrations tracevision
```

### Step 2: Apply Migrations
```bash
python manage.py migrate tracevision
```

Expected migrations:
1. Rename `TracePlayer.language_data` to `language_metadata`
2. Add `TraceHighlight.video_time` field

## Usage Example

```python
from tracevision.tasks import process_excel_match_highlights_task

# Process Excel file for a session
result = process_excel_match_highlights_task.delay(
    session_id="12345",
    excel_file_path="/path/to/excel.xlsx"  # Optional, uses session.basic_game_stats if None
)

# Result will contain:
# - Player language metadata updates (en/he names and roles)
# - Highlights created for goals and cards
# - 6 clip reel variations per highlight
# - Comprehensive statistics
```

## Key Features

### 1. Multilingual Support
- ✅ English and Hebrew player names
- ✅ English and Hebrew team names
- ✅ English and Hebrew roles
- ✅ Stored in `language_metadata` JSONField

### 2. Smart Player Matching
- ✅ Match by team + jersey_number
- ✅ Fallback to object_id pattern (home_X, away_X)
- ✅ Updates existing TracePlayer records

### 3. Event Processing
- ✅ Goals: Only when goals array has entries
- ✅ Cards: Only when cards > 0
- ✅ Video timestamps: Stored in `video_time` field
- ✅ Match time vs video time differentiation

### 4. Clip Reel Generation
- ✅ 6 variations per highlight (3 tag combos × 2 ratios)
- ✅ Prevents duplicates
- ✅ Sets involved players
- ✅ Follows existing service pattern

## Testing

### Test with Sample Data
```bash
# Inside Docker container
python manage.py shell

from tracevision.models import TraceSession
from tracevision.tasks import process_excel_match_highlights_task

session = TraceSession.objects.get(session_id="YOUR_SESSION_ID")
result = process_excel_match_highlights_task(
    session_id=session.session_id,
    excel_file_path="/path/to/Gmae_Match_Detail Template_multilingual.json"
)

print(result)
```

### Verify Results
```python
# Check player metadata
from tracevision.models import TracePlayer

players = TracePlayer.objects.filter(session=session)
for player in players:
    print(f"{player.jersey_number}: {player.language_metadata}")

# Check highlights
from tracevision.models import TraceHighlight

highlights = TraceHighlight.objects.filter(session=session, source="excel_import")
print(f"Total highlights: {highlights.count()}")

# Check clip reels
from tracevision.models import TraceClipReel

clip_reels = TraceClipReel.objects.filter(session=session)
print(f"Total clip reels: {clip_reels.count()}")
```

## Notes

1. **Backward Compatibility**: The field rename from `language_data` to `language_metadata` requires a migration
2. **Video Time**: New field `video_time` stores actual video timestamps from Excel
3. **Clip Reels**: Uses same pattern as existing `TraceVisionAggregationService._compute_clips`
4. **Error Handling**: Comprehensive error handling with detailed logging
5. **Cleanup**: Temporary files are cleaned up automatically

## Next Steps

1. ✅ Run migrations in Docker
2. ✅ Test with sample multilingual Excel file
3. ✅ Verify player metadata updates
4. ✅ Verify highlights and clip reels creation
5. ✅ Monitor logs for any issues

## Files Modified

- `tracevision/models.py` - Added fields to TracePlayer and TraceHighlight
- `tracevision/tasks.py` - Updated process_excel_match_highlights_task
- `tracevision/multilingual_processing.py` - New module (created)
- `MULTILINGUAL_UPDATE_SUMMARY.md` - This file (created)
