import re
import os
import uuid
import logging
import tempfile
import webcolors
import subprocess
from azure.storage.blob import (
    BlobServiceClient,
    generate_blob_sas,
    BlobSasPermissions,
)

from django.db.models import Q
from django.conf import settings
from django.utils import timezone
from urllib.parse import urlparse, parse_qs
from datetime import datetime, timedelta
from typing import Dict, Tuple, Optional
from django.core.files.storage import default_storage


from cards.models import GPSAthleticSkills, GPSFootballAbilities
from tracevision.models import TracePlayer, TraceHighlight, TraceClipReel, TraceHighlightObject, TraceObject

logger = logging.getLogger(__name__)



def normalize_multilingual_data(match_data):
    """
    Normalize the multilingual match data into a structured format.
    
    Args:
        match_data (dict): Raw multilingual data with 'en' and 'he' sections
        
    Returns:
        dict: Normalized data structure with teams and players
    """
    normalized = {
        "teams": [],
        "players": []
    }
    
    # Extract team names
    en_data = match_data.get("en", {})
    he_data = match_data.get("he", {})
    
    en_summary = en_data.get("Match_summary", {})
    he_summary = he_data.get("Match_summary", {})
    
    # Normalize team data
    home_team = {
        "name": {
            "en": en_summary.get("match_home_team", ""),
            "he": he_summary.get("match_home_team", "")
        },
        "side": "home",
        "players": []
    }
    
    away_team = {
        "name": {
            "en": en_summary.get("match_away_team", ""),
            "he": he_summary.get("match_away_team", "")
        },
        "side": "away",
        "players": []
    }
    
    normalized["teams"] = [home_team, away_team]
    
    # Normalize player data from starting lineups, replacements, and bench
    for section in ["starting_lineups", "replacements", "bench"]:
        en_section = en_data.get(section, {})
        he_section = he_data.get(section, {})
        
        # Process each team
        for team_key_en in en_section.keys():
            # Find corresponding Hebrew team key
            team_key_he = None
            for he_key in he_section.keys():
                if _teams_match(team_key_en, he_key, en_summary, he_summary):
                    team_key_he = he_key
                    break
            
            if not team_key_he:
                continue
            
            # Determine team side
            team_side = "home" if team_key_en == en_summary.get("match_home_team") else "away"
            
            # Get players for this team
            en_players = en_section[team_key_en]
            he_players = he_section[team_key_he]
            
            # Process each player by jersey number
            for jersey_num in en_players.keys():
                if jersey_num not in he_players:
                    continue
                
                en_player = en_players[jersey_num]
                he_player = he_players[jersey_num]
                
                # Extract player data
                player_data = {
                    "jersey_number": int(jersey_num),
                    "team_side": team_side,
                    "name": {
                        "en": en_player.get("name", ""),
                        "he": he_player.get("name", "")
                    },
                    "role": {
                        "en": en_player.get("role", ""),
                        "he": he_player.get("role", "")
                    },
                    "goals": [],
                    "cards": en_player.get("cards", 0),
                    "source": section
                }
                
                # Extract goals with video times
                en_goals = en_player.get("goals", [])
                he_video_goals = he_player.get("video_goal", [])
                
                for idx, goal_minute in enumerate(en_goals):
                    video_time = he_video_goals[idx] if idx < len(he_video_goals) else None
                    player_data["goals"].append({
                        "minute": str(goal_minute),
                        "video_time": video_time
                    })
                
                # Add substitution info if applicable
                if section == "starting_lineups":
                    player_data["sub_off_minute"] = en_player.get("sub_off_minute", 0)
                elif section == "replacements":
                    player_data["replacer_minute"] = en_player.get("replacer_minute", 0)
                
                normalized["players"].append(player_data)
    
    return normalized


def _teams_match(en_team, he_team, en_summary, he_summary):
    """Check if English and Hebrew team names correspond to the same team."""
    en_home = en_summary.get("match_home_team", "")
    he_home = he_summary.get("match_home_team", "")
    en_away = en_summary.get("match_away_team", "")
    he_away = he_summary.get("match_away_team", "")
    
    if en_team == en_home and he_team == he_home:
        return True
    if en_team == en_away and he_team == he_away:
        return True
    return False


def _create_goal_highlight(session, trace_player, player_data, goal, aggregation_service):
    """Create a highlight for a goal event."""
    minute = goal["minute"]
    video_time = goal.get("video_time")
    
    # Create unique highlight ID
    highlight_id = f"excel-goal-{session.session_id}-{minute}-{trace_player.object_id}"
    
    # Check if highlight already exists
    if TraceHighlight.objects.filter(highlight_id=highlight_id).exists():
        logger.info(f"Highlight {highlight_id} already exists, skipping")
        return None, 0
    
    # Create event metadata
    event_metadata = {
        "scorer": player_data["name"]["en"] or player_data["name"]["he"],
        "scorer_name": player_data["name"],
        "minute": minute,
        "video_time": video_time,
        "team": player_data["team_side"],
        "jersey_number": player_data["jersey_number"]
    }
    
    # Create TraceHighlight
    highlight = TraceHighlight.objects.create(
        highlight_id=highlight_id,
        video_id=0,
        start_offset=0,  # Will be calculated from video_time if needed
        duration=15000,  # 15 seconds for goals
        tags=[player_data["team_side"], "goal", minute],
        video_stream=session.video_url,
        event_type="goal",
        source="excel_import",
        match_time=f"{minute}:00",
        video_time=video_time,
        half=1 if int(minute) <= 45 else 2,  # Simple half determination
        event_metadata=event_metadata,
        session=session,
        player=trace_player
    )
    
    # Calculate performance impact
    highlight.performance_impact = highlight.calculate_performance_impact()
    highlight.team_impact = abs(highlight.performance_impact) * 0.5
    highlight.save()
    
    # Create highlight-object relationship
    trace_object = TraceObject.objects.filter(
        session=session, player=trace_player
    ).first()
    
    if trace_object:
        TraceHighlightObject.objects.create(
            highlight=highlight,
            trace_object=trace_object,
            player=trace_player
        )
    
    # Create TraceClipReel entries (6 variations)
    clip_reels_count = _create_clip_reels_for_highlight(
        highlight, session, trace_player, player_data["team_side"], aggregation_service
    )
    
    logger.info(
        f"Created goal highlight {highlight_id} for {player_data['name']['en']} at {minute}'"
    )
    
    return highlight, clip_reels_count


def _create_card_highlight(session, trace_player, player_data, aggregation_service):
    """Create a highlight for a card event."""
    # For now, create a generic card highlight (minute unknown from current data)
    # This can be enhanced when card minute data is available
    
    highlight_id = f"excel-card-{session.session_id}-{trace_player.object_id}"
    
    # Check if highlight already exists
    if TraceHighlight.objects.filter(highlight_id=highlight_id).exists():
        logger.info(f"Highlight {highlight_id} already exists, skipping")
        return None, 0
    
    # Create event metadata
    event_metadata = {
        "player": player_data["name"]["en"] or player_data["name"]["he"],
        "player_name": player_data["name"],
        "card_type": "yellow",  # Default, can be enhanced
        "team": player_data["team_side"],
        "jersey_number": player_data["jersey_number"]
    }
    
    # Create TraceHighlight
    highlight = TraceHighlight.objects.create(
        highlight_id=highlight_id,
        video_id=0,
        start_offset=0,
        duration=8000,  # 8 seconds for cards
        tags=[player_data["team_side"], "yellow_card", "card"],
        video_stream=session.video_url,
        event_type="yellow_card",
        source="excel_import",
        match_time="00:00",  # Unknown for now
        event_metadata=event_metadata,
        session=session,
        player=trace_player
    )
    
    # Calculate performance impact
    highlight.performance_impact = highlight.calculate_performance_impact()
    highlight.team_impact = abs(highlight.performance_impact) * 0.5
    highlight.save()
    
    # Create highlight-object relationship
    trace_object = TraceObject.objects.filter(
        session=session, player=trace_player
    ).first()
    
    if trace_object:
        TraceHighlightObject.objects.create(
            highlight=highlight,
            trace_object=trace_object,
            player=trace_player
        )
    
    # Create TraceClipReel entries
    clip_reels_count = _create_clip_reels_for_highlight(
        highlight, session, trace_player, player_data["team_side"], aggregation_service
    )
    
    logger.info(
        f"Created card highlight {highlight_id} for {player_data['name']['en']}"
    )
    
    return highlight, clip_reels_count


def update_player_language_metadata(session, normalized_data):
    """
    Update TracePlayer language_metadata with multilingual names and roles.
    Also maps WajoUsers to TracePlayers when creating new players.
    
    Args:
        session: TraceSession instance
        normalized_data: Normalized multilingual data
        
    Returns:
        dict: Update statistics
    """
    from accounts.models import WajoUser
    
    updated_count = 0
    not_found_count = 0
    update_details = []
    
    for player_data in normalized_data["players"]:
        logger.info(f"Processing player {player_data}")
        try:
            # Find TracePlayer by team and jersey number
            team = session.home_team if player_data["team_side"] == "home" else session.away_team
            jersey_number = player_data["jersey_number"]
            
            trace_player = TracePlayer.objects.filter(
                session=session,
                team=team,
                jersey_number=jersey_number
            ).first()
            
            if not trace_player:
                # Try finding by object_id pattern
                object_id = f"{player_data['team_side']}_{jersey_number}"
                trace_player = TracePlayer.objects.filter(
                    session=session,
                    object_id=object_id
                ).first()
            
            if trace_player:
                # Update language_metadata
                if not trace_player.language_metadata:
                    trace_player.language_metadata = {}
                
                # Update English data
                if player_data["name"]["en"]:
                    if "en" not in trace_player.language_metadata:
                        trace_player.language_metadata["en"] = {}
                    trace_player.language_metadata["en"]["name"] = player_data["name"]["en"]
                    if player_data["role"]["en"]:
                        trace_player.language_metadata["en"]["role"] = player_data["role"]["en"]
                
                # Update Hebrew data
                if player_data["name"]["he"]:
                    if "he" not in trace_player.language_metadata:
                        trace_player.language_metadata["he"] = {}
                    trace_player.language_metadata["he"]["name"] = player_data["name"]["he"]
                    if player_data["role"]["he"]:
                        trace_player.language_metadata["he"]["role"] = player_data["role"]["he"]
                
                # Update primary name field (use English if available, else Hebrew)
                if player_data["name"]["en"]:
                    trace_player.name = player_data["name"]["en"]
                elif player_data["name"]["he"]:
                    trace_player.name = player_data["name"]["he"]
                
                # Map to WajoUser if not already mapped
                wajo_user_mapped = False
                if not trace_player.user:
                    # Try to find matching WajoUser
                    wajo_user = None
                    
                    # Try to find by jersey number and team first
                    wajo_user = WajoUser.objects.filter(
                        jersey_number=jersey_number,
                        team=team
                    ).first()
                    
                    if not wajo_user:
                        # Try to find by name similarity and team
                        # Use first name from either English or Hebrew
                        first_name = None
                        if player_data["name"]["en"]:
                            first_name = player_data["name"]["en"].split()[0]
                        elif player_data["name"]["he"]:
                            first_name = player_data["name"]["he"].split()[0]
                        
                        if first_name:
                            wajo_user = WajoUser.objects.filter(
                                team=team,
                                name__icontains=first_name
                            ).first()
                    
                    if wajo_user:
                        trace_player.user = wajo_user
                        wajo_user_mapped = True
                        logger.info(
                            f"Mapped existing TracePlayer #{jersey_number} to WajoUser: {wajo_user.phone_no}"
                        )
                
                trace_player.save()
                updated_count += 1
                
                update_details.append({
                    "jersey_number": jersey_number,
                    "team_side": player_data["team_side"],
                    "name_en": player_data["name"]["en"],
                    "name_he": player_data["name"]["he"],
                    "mapped_to_user": trace_player.user.phone_no if trace_player.user else None,
                    "user_mapped_now": wajo_user_mapped
                })
                
                logger.info(
                    f"Updated player #{jersey_number} ({player_data['team_side']}): "
                    f"EN={player_data['name']['en']}, HE={player_data['name']['he']}"
                    f"{' - Mapped to WajoUser: ' + trace_player.user.phone_no if wajo_user_mapped else ''}"
                )
            else:
                # Create new TracePlayer if not found
                object_id = f"{player_data['team_side']}_{jersey_number}"
                
                # Determine primary name (use English if available, else Hebrew)
                primary_name = player_data["name"]["en"] or player_data["name"]["he"] or f"Player {jersey_number}"
                
                # Build language_metadata
                language_metadata = {}
                if player_data["name"]["en"]:
                    language_metadata["en"] = {"name": player_data["name"]["en"]}
                    if player_data["role"]["en"]:
                        language_metadata["en"]["role"] = player_data["role"]["en"]
                
                if player_data["name"]["he"]:
                    language_metadata["he"] = {"name": player_data["name"]["he"]}
                    if player_data["role"]["he"]:
                        language_metadata["he"]["role"] = player_data["role"]["he"]
                
                # Determine position from role (use English role if available, else Hebrew, else "Unknown")
                position = player_data["role"]["en"] or player_data["role"]["he"] or "Unknown"
                
                # Try to find matching WajoUser to map to this TracePlayer
                # Following the same logic as map_player_to_trace_player in tasks.py
                wajo_user = None
                
                # Try to find by jersey number and team first
                wajo_user = WajoUser.objects.filter(
                    jersey_number=jersey_number,
                    team=team
                ).first()
                
                if not wajo_user:
                    # Try to find by name similarity and team
                    # Use first name from either English or Hebrew
                    first_name = None
                    if player_data["name"]["en"]:
                        first_name = player_data["name"]["en"].split()[0]
                    elif player_data["name"]["he"]:
                        first_name = player_data["name"]["he"].split()[0]
                    
                    if first_name:
                        wajo_user = WajoUser.objects.filter(
                            team=team,
                            name__icontains=first_name
                        ).first()
                
                # Create the new TracePlayer
                trace_player = TracePlayer.objects.create(
                    object_id=object_id,
                    name=primary_name,
                    jersey_number=jersey_number,
                    position=position,
                    team=team,
                    session=session,
                    user=wajo_user,  # Map to WajoUser if found
                    language_metadata=language_metadata
                )
                
                updated_count += 1
                
                update_details.append({
                    "jersey_number": jersey_number,
                    "team_side": player_data["team_side"],
                    "name_en": player_data["name"]["en"],
                    "name_he": player_data["name"]["he"],
                    "created": True,
                    "mapped_to_user": wajo_user.phone_no if wajo_user else None
                })
                
                logger.info(
                    f"Created new player #{jersey_number} ({player_data['team_side']}): "
                    f"EN={player_data['name']['en']}, HE={player_data['name']['he']}"
                    f"{' - Mapped to WajoUser: ' + wajo_user.phone_no if wajo_user else ''}"
                )
        
        except Exception as e:
            logger.error(f"Error updating player {player_data}: {e}", exc_info=True)
            continue
    
    return {
        "updated_count": updated_count,
        "not_found_count": not_found_count,
        "total_players": len(normalized_data["players"]),
        "update_details": update_details
    }


def create_highlights_from_normalized_data(session, normalized_data):
    """
    Create TraceHighlight and TraceClipReel entries for goals and cards.
    
    Args:
        session: TraceSession instance
        normalized_data: Normalized multilingual data
        
    Returns:
        dict: Creation statistics
    """
    from tracevision.services import TraceVisionAggregationService
    
    highlights_created = 0
    clip_reels_created = 0
    errors = []
    
    aggregation_service = TraceVisionAggregationService()
    
    for player_data in normalized_data["players"]:
        try:
            # Find TracePlayer
            team = session.home_team if player_data["team_side"] == "home" else session.away_team
            jersey_number = player_data["jersey_number"]
            
            trace_player = TracePlayer.objects.filter(
                session=session,
                team=team,
                jersey_number=jersey_number
            ).first()
            
            if not trace_player:
                object_id = f"{player_data['team_side']}_{jersey_number}"
                trace_player = TracePlayer.objects.filter(
                    session=session,
                    object_id=object_id
                ).first()
            
            if not trace_player:
                logger.warning(
                    f"Skipping highlights for player #{jersey_number} - not found"
                )
                continue
            
            # Create highlights for goals
            for goal in player_data["goals"]:
                try:
                    highlight, clip_reels = _create_goal_highlight(
                        session, trace_player, player_data, goal, aggregation_service
                    )
                    if highlight:
                        highlights_created += 1
                        clip_reels_created += clip_reels
                except Exception as e:
                    error_msg = f"Error creating goal highlight: {e}"
                    logger.error(error_msg, exc_info=True)
                    errors.append(error_msg)
            
            # Create highlights for cards (if cards > 0)
            if player_data.get("cards", 0) > 0:
                try:
                    highlight, clip_reels = _create_card_highlight(
                        session, trace_player, player_data, aggregation_service
                    )
                    if highlight:
                        highlights_created += 1
                        clip_reels_created += clip_reels
                except Exception as e:
                    error_msg = f"Error creating card highlight: {e}"
                    logger.error(error_msg, exc_info=True)
                    errors.append(error_msg)
        
        except Exception as e:
            error_msg = f"Error processing player {player_data}: {e}"
            logger.error(error_msg, exc_info=True)
            errors.append(error_msg)
            continue
    
    return {
        "highlights_created": highlights_created,
        "clip_reels_created": clip_reels_created,
        "errors": errors
    }


def _create_clip_reels_for_highlight(highlight, session, trace_player, team_side, aggregation_service):
    """
    Create 6 TraceClipReel entries for a highlight (3 tag combinations × 2 ratios).
    Similar to the logic in TraceVisionAggregationService._compute_clips.
    Uses video_time from highlight if available, with 40-second buffer before and after.
    """
    clip_reels_created = 0
    
    # Get involved players
    highlight_objects = highlight.highlight_objects.all().select_related("trace_object", "player")
    involved_players = [ho.player for ho in highlight_objects if ho.player]
    if not involved_players and trace_player:
        involved_players = [trace_player]
    
    primary_player = involved_players[0] if involved_players else None
    
    # Determine event type from highlight
    event_type = highlight.event_type or "touch"
    
    # Calculate start_ms and duration_ms based on video_time if available
    start_ms = highlight.start_offset
    duration_ms = highlight.duration
    
    if highlight.video_time and highlight.video_time.strip():
        try:
            # Parse video_time (format: "mm:ss" or "hh:mm:ss")
            time_parts = highlight.video_time.strip().split(":")
            
            if len(time_parts) == 2:  # mm:ss format
                minutes, seconds = map(int, time_parts)
                video_time_ms = (minutes * 60 + seconds) * 1000
            elif len(time_parts) == 3:  # hh:mm:ss format
                hours, minutes, seconds = map(int, time_parts)
                video_time_ms = (hours * 3600 + minutes * 60 + seconds) * 1000
            else:
                # Invalid format, use default
                video_time_ms = None
            
            if video_time_ms is not None and video_time_ms > 0:
                # Add 40 seconds (40000ms) buffer before the event
                buffer_ms = 40000
                start_ms = max(0, video_time_ms - buffer_ms)  # Ensure non-negative
                
                # Duration includes the original duration plus 40 seconds after
                # Total: 40s before + original duration + 40s after
                duration_ms = highlight.duration + (2 * buffer_ms)
                
                logger.info(
                    f"Using video_time {highlight.video_time} for clip reel: "
                    f"start_ms={start_ms}, duration_ms={duration_ms}"
                )
        except (ValueError, AttributeError) as e:
            logger.warning(f"Failed to parse video_time '{highlight.video_time}': {e}")
            # Fall back to using highlight.start_offset and highlight.duration
    
    # Define clip reel configurations
    clip_reel_configs = [
        {
            "ratio": "original",
            "tags": ["without_name_overlay", "without_circle_overlay"],
            "is_default": True,
            "video_type": None,
        },
        {
            "ratio": "9:16",
            "tags": ["without_name_overlay", "without_circle_overlay"],
            "is_default": True,
            "video_type": None,
        },
        {
            "ratio": "original",
            "tags": ["with_name_overlay", "without_circle_overlay"],
            "is_default": False,
            "video_type": None,
        },
        {
            "ratio": "9:16",
            "tags": ["with_name_overlay", "without_circle_overlay"],
            "is_default": False,
            "video_type": None,
        },
        {
            "ratio": "original",
            "tags": ["with_name_overlay", "with_circle_overlay"],
            "is_default": False,
            "video_type": None,
        },
        {
            "ratio": "9:16",
            "tags": ["with_name_overlay", "with_circle_overlay"],
            "is_default": False,
            "video_type": None,
        },
    ]
    
    for config in clip_reel_configs:
        sorted_tags = sorted(config["tags"])
        
        # Check if clip reel already exists with exact same config
        tag_filters = Q()
        for tag in config["tags"]:
            tag_filters &= Q(tags__contains=tag)
        
        clip_reel = (
            TraceClipReel.objects.filter(
                highlight=highlight,
                ratio=config["ratio"],
            )
            .filter(tag_filters)
            .first()
        )
        
        # Verify exact tag match
        if clip_reel:
            existing_tags = sorted(clip_reel.tags) if clip_reel.tags else []
            if existing_tags == sorted_tags:
                # Already exists, just ensure involved players are set
                if involved_players:
                    clip_reel.involved_players.set(involved_players)
                continue
        
        # Create new clip reel
        defaults = {
            "session": session,
            "event_id": highlight.highlight_id,
            "event_type": event_type,
            "side": team_side,
            "start_ms": start_ms,
            "duration_ms": duration_ms,
            "start_clock": aggregation_service._ms_to_clock(start_ms),
            "end_clock": aggregation_service._ms_to_clock(start_ms + duration_ms),
            "primary_player": primary_player,
            "label": f"{event_type.title()} - {team_side.title()}",
            "description": f"{event_type.title()} event for {team_side} team",
            "tags": config["tags"],
            "ratio": config["ratio"],
            "is_default": config["is_default"],
            "video_type": config["video_type"],
            "video_stream": highlight.video_stream or "",
            "generation_status": "pending",
            "video_variant_name": aggregation_service._get_video_variant_name(
                tags=config["tags"],
                ratio=config["ratio"],
                primary_player=primary_player,
            ),
            "generation_metadata": {
                "highlight_id": highlight.highlight_id,
                "video_id": highlight.video_id,
                "involved_players_count": len(involved_players),
                "created_from_excel": True,
                "tags": config["tags"],
                "ratio": config["ratio"],
                "video_time": highlight.video_time if highlight.video_time else None,
            },
        }
        
        clip_reel = TraceClipReel.objects.create(
            highlight=highlight,
            **defaults,
        )
        
        # Add involved players
        if involved_players:
            clip_reel.involved_players.set(involved_players)
        
        clip_reels_created += 1
    
    return clip_reels_created


def make_json_serializable(obj):
    """
    Recursively convert non-JSON-serializable objects (time, datetime, etc.) to strings.
    """
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    elif isinstance(obj, time):
        return obj.strftime("%H:%M:%S")
    elif isinstance(obj, pd.Timestamp):
        return obj.isoformat()
    elif isinstance(obj, dict):
        return {key: make_json_serializable(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [make_json_serializable(item) for item in obj]
    elif pd.isna(obj) or obj is pd.NA or obj is pd.NaT:
        return None
    elif isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
        return None
    else:
        return obj


def parse_goals_value(value):
    """
    Parse goals value and return list of goal minutes.
    Can be: "⚽ 19, 23, 61, 80" or "⚽ 14" or "—" or empty or list
    """
    if value is None or value == "" or value == "—" or (isinstance(value, float) and math.isnan(value)):
        return []
    
    if isinstance(value, list):
        # If value is already a list, filter out empty/"—" and non-numeric values, and return cleaned list as strings
        return [str(g).strip() for g in value if g and str(g).strip() and str(g).strip() != "—" and re.match(r"^\d+$", str(g).strip())]
    
    if isinstance(value, str):
        value = value.strip()
        if value == "" or value == "—":
            return []
        # Extract all numbers (comma-separated), handles emoji like "⚽ 19, 23, 61, 80"
        numbers = re.findall(r"\d+", value)
        return numbers
    
    # If it's a single number
    try:
        int(value)
        return 1
    except:
        return 0


def parse_video_goal_value(value):
    """
    Normalize/parse a list of video goal times, returning a list of strings in "mm:ss" or "hh:mm:ss" format.
    Can handle values like "⚽ 18:16,23,61,80", "13:08", "13", "13:00 minute", "80:05 min", single time, lists, etc.
    Removes extra characters/icons, converts "N" to "N:00" where fitting.
    """

    # Helper to clean and normalize an individual time value
    def clean_and_normalize_time(timestr):
        if not isinstance(timestr, str):
            timestr = str(timestr)

        # Remove icons, words ("minute", "min", "mintue", etc.), and whitespace
        timestr = re.sub(r'[^\d:]', '', timestr).strip()
        if not timestr:
            return None

        # Find all numbers/groups as separated by colons
        segments = timestr.split(":")

        # Case 1: Only a number ("13" => "13:00")
        if len(segments) == 1 and re.match(r'^\d+$', segments[0]):
            mm = int(segments[0])
            if 0 <= mm <= 120:  # reasonable minute range
                return f"{mm:02d}:00"
            else:
                return None

        # Case 2: "mm:ss"
        if len(segments) == 2:
            mm, ss = segments
            if mm.isdigit() and ss.isdigit():
                mm, ss = int(mm), int(ss)
                if 0 <= mm < 180 and 0 <= ss < 60:
                    return f"{mm:02d}:{ss:02d}"

        # Case 3: "hh:mm:ss"
        if len(segments) == 3:
            hh, mm, ss = segments
            if hh.isdigit() and mm.isdigit() and ss.isdigit():
                hh, mm, ss = int(hh), int(mm), int(ss)
                if 0 <= mm < 60 and 0 <= ss < 60 and 0 <= hh < 24:
                    return f"{hh:02d}:{mm:02d}:{ss:02d}"

        return None

    # Canonicalize input
    if value is None or value == "" or value == "—" or (isinstance(value, float) and math.isnan(value)):
        return []

    # If value is a list, flatten and process elements as str
    if isinstance(value, list):
        items = value
    else:
        # If a string, split on comma (for typical user entry)
        items = [s.strip() for s in str(value).split(",") if s.strip() and s.strip() != "—"]

    result = []
    for item in items:
        cleaned = clean_and_normalize_time(item)
        if cleaned:
            result.append(cleaned)
    return result


def parse_sub_off_minute(value):
    """
    Parse substitution off minute value.
    Returns the minute number or 0 if not substituted.
    """
    if value is None or value == "" or value == "—" or (isinstance(value, float) and math.isnan(value)):
        return 0
    
    if isinstance(value, (int, float)):
        return int(value)
    
    if isinstance(value, str):
        value = value.strip()
        if value == "" or value == "—":
            return 0
        # Extract first number
        match = re.search(r"\d+", value)
        if match:
            return int(match.group())
    
    return 0


def parse_cards_value(value):
    """
    Parse cards value. Returns 0 if no cards, or count if multiple cards mentioned.
    """
    if value is None or value == "" or value == "—" or (isinstance(value, float) and math.isnan(value)):
        return 0
    
    if isinstance(value, str):
        value = value.strip()
        if value == "" or value == "—":
            return 0
        # Count occurrences of "Yellow" or "Red" or Hebrew equivalents
        # For now, if there's any text, count as 1 (can be enhanced)
        return 1 if value else 0
    
    return 0


def extract_multilingual_match_data(excel_file_path):
    """
    Extract multilingual match data from Excel file with _en and _he sheets.
    
    Args:
        excel_file_path (str): Path to the Excel file
        
    Returns:
        dict: Multilingual match data in the format:
        {
            "en": {
                "Match_summary": {...},
                "starting_lineups": {
                    "Team Name": {
                        "1": {"name": "...", "role": "...", ...},
                        ...
                    }
                }
            },
            "he": {
                "Match_summary": {...},
                "starting_lineups": {
                    "Team Name (Hebrew)": {
                        "1": {"name": "...", "role": "...", ...},
                        ...
                    }
                }
            }
        }
    """
    try:
        # Convert Path object to string if needed
        excel_file_path = str(excel_file_path)
        
        # Check if file exists
        if not os.path.exists(excel_file_path):
            raise FileNotFoundError(f"Excel file not found: {excel_file_path}")
        
        # Read all sheets from Excel file
        excel_data = pd.read_excel(excel_file_path, sheet_name=None)
        
        result = {
            "en": {
                "Match_summary": {},
                "starting_lineups": {},
                "replacements": {},
                "bench": {},
                "coaches": {},
                "referees": []
            },
            "he": {
                "Match_summary": {},
                "starting_lineups": {},
                "replacements": {},
                "bench": {},
                "coaches": {},
                "referees": []
            }
        }
        
        # ===== Parse Match_Summary_en =====
        if "Match_Summary_en" in excel_data:
            summary_df = excel_data["Match_Summary_en"]
            summary_df = summary_df.where(pd.notna(summary_df), None)
            if not summary_df.empty:
                summary_dict = summary_df.iloc[0].to_dict()
                # Log available columns for debugging
                logger.debug(f"Match_Summary_en columns: {list(summary_dict.keys())}")
                
                # Clean and structure match summary
                # Map all available columns - use exact column names from Excel
                def safe_get(d, key, default=""):
                    """Safely get value from dict, handling None and NaN"""
                    val = d.get(key)
                    if val is None or pd.isna(val):
                        return default
                    return val
                
                def safe_int(d, key, default=0):
                    """Safely get integer value"""
                    val = d.get(key)
                    if val is None or pd.isna(val):
                        return default
                    try:
                        return int(float(val))
                    except (ValueError, TypeError):
                        return default
                
                # Map actual Excel column names to JSON keys
                # Excel columns: 'Match Id', 'Competition', 'Date', 'Kickoff Time', etc.
                # Handle time objects properly
                def safe_get_time(d, key, default=""):
                    """Safely get time value and convert to string"""
                    val = d.get(key)
                    if val is None or pd.isna(val):
                        return default
                    if isinstance(val, time):
                        return val.strftime("%H:%M:%S")
                    return str(val)
                
                result["en"]["Match_summary"] = {
                    "match_id": str(safe_get(summary_dict, "Match Id", "")),
                    "match_venue": str(safe_get(summary_dict, "Competition", "")),
                    "match_date": str(safe_get(summary_dict, "Date", "")),
                    "match_time": safe_get_time(summary_dict, "Kickoff Time", ""),
                    "match_location": str(safe_get(summary_dict, "Stadium", "")),
                    "match_address": str(safe_get(summary_dict, "Address", "")),
                    "match_home_team": str(safe_get(summary_dict, "Home Team", "")),
                    "match_away_team": str(safe_get(summary_dict, "Away Team", "")),
                    "match_half_time_score": str(safe_get(summary_dict, "Half-Time Score", "")),
                    "match_full_time_score": str(safe_get(summary_dict, "Full-Time Score", "")),
                    "match_home_goals": safe_int(summary_dict, "Home Goals", 0),
                    "match_away_goals": safe_int(summary_dict, "Away Goals", 0),
                    "match_age_group": str(safe_get(summary_dict, "Age Group", "")),
                    "match_game_format": str(safe_get(summary_dict, "Game Format", "")),
                    "match_field_length": str(safe_get(summary_dict, "Field Length (m)", "")),
                    "match_field_width": str(safe_get(summary_dict, "Field Width (m)", "")),
                    "match_goal_size": str(safe_get(summary_dict, "Goal Size (m)", "")),
                    "match_ball_size": str(safe_get(summary_dict, "Ball Size", "")),
                    "match_half_length": str(safe_get(summary_dict, "Half Length (Minutes)", "")),
                    "match_official_break_time": str(safe_get(summary_dict, "Official Break Time", "")),
                }
        
        # ===== Parse Match_Summary_he =====
        if "Match_Summary_he" in excel_data:
            summary_df = excel_data["Match_Summary_he"]
            summary_df = summary_df.where(pd.notna(summary_df), None)
            if not summary_df.empty:
                summary_dict = summary_df.iloc[0].to_dict()
                # Map Hebrew column names to English keys, but keep Hebrew values
                # Handle time objects properly
                def safe_get_time_he(d, key, default=""):
                    """Safely get time value and convert to string"""
                    val = d.get(key)
                    if val is None or pd.isna(val):
                        return default
                    if isinstance(val, time):
                        return val.strftime("%H:%M:%S")
                    return str(val)
                
                # Use English keys, but extract Hebrew values from Hebrew columns
                result["he"]["Match_summary"] = {
                    "match_id": str(safe_get(summary_dict, "מזהה משחק", "")),
                    "match_date": str(safe_get(summary_dict, "תאריך", "")),
                    "match_time": safe_get_time_he(summary_dict, "שעת פתיחה", ""),
                    "match_location": str(safe_get(summary_dict, "אצטדיון", "")),
                    "match_address": str(safe_get(summary_dict, "כתובת", "")),
                    "match_venue": str(safe_get(summary_dict, "תחרות", "")),  # No trailing space
                    "match_home_team": str(safe_get(summary_dict, "קבוצה ביתית", "")),
                    "match_away_team": str(safe_get(summary_dict, "קבוצה אורחת", "")),
                    "match_half_time_score": str(safe_get(summary_dict, "תוצאת מחצית", "")),
                    "match_full_time_score": str(safe_get(summary_dict, "תוצאת סיום", "")),
                    "match_home_goals": safe_int(summary_dict, "שערי בית", 0),
                    "match_away_goals": safe_int(summary_dict, "שערי חוץ", 0),
                    "match_age_group": str(safe_get(summary_dict, "קבוצת גיל", "")),
                    "match_game_format": str(safe_get(summary_dict, "פורמט משחק", "")),
                    "match_field_length": str(safe_get(summary_dict, "אורך מגרש (מ')", "")),
                    "match_field_width": str(safe_get(summary_dict, "רוחב מגרש (מ')", "")),
                    "match_goal_size": str(safe_get(summary_dict, "גודל שער (מ')", "")),
                    "match_ball_size": str(safe_get(summary_dict, "גודל כדור", "")),
                    "match_half_length": str(safe_get(summary_dict, "אורך מחצית (דקות)", "")),
                    "match_official_break_time": str(safe_get(summary_dict, "הפסקה רשמית (דקות)", "")),
                }
        
        # ===== Parse Starting_Lineups_en =====
        if "Starting_Lineups_en" in excel_data:
            lineups_df = excel_data["Starting_Lineups_en"]
            lineups_df = lineups_df.where(pd.notna(lineups_df), None)
            
            # Log column names for debugging
            logger.debug(f"Starting_Lineups_en columns: {list(lineups_df.columns)}")
            
            # Group by team
            for _, row in lineups_df.iterrows():
                # Try multiple possible column name variations
                team = row.get("Team") or row.get("team") or row.get("TEAM")
                number = row.get("Number") or row.get("number") or row.get("NUMBER") or row.get("No.") or row.get("No")
                name = row.get("Name") or row.get("name") or row.get("NAME") or row.get("Player Name")
                
                # Skip invalid rows
                if not team or pd.isna(team) or (isinstance(team, str) and team.strip() in ["", "no.", "Team"]):
                    continue
                if not number or pd.isna(number):
                    continue
                if not name or pd.isna(name) or (isinstance(name, str) and name.strip() in ["", "GOALS TABLE", "CARD TABLE", "name", "Name", "NAME"]):
                    continue
                
                team = str(team).strip()
                # Handle Number as float (e.g., 1.0, 4.0) - convert to int then string
                try:
                    number = str(int(float(number))) if not pd.isna(number) else None
                except (ValueError, TypeError):
                    continue
                name = str(name).strip()
                
                if team not in result["en"]["starting_lineups"]:
                    result["en"]["starting_lineups"][team] = {}
                
                # Get other fields - try multiple column name variations
                role = row.get("Role") or row.get("role") or row.get("ROLE") or row.get("Position")
                if pd.isna(role) or role is None:
                    role = "—"
                else:
                    role = str(role).strip()
                
                goals = parse_goals_value(row.get("Goals") or row.get("goals") or row.get("GOALS"))
                video_goal = parse_video_goal_value(row.get("VideoGoal") or row.get("video_goal") or row.get("Video Goal"))
                sub_off_minute = parse_sub_off_minute(row.get("SubOffMinute") or row.get("sub_off_minute") or row.get("Sub Off Minute"))
                cards = parse_cards_value(row.get("Cards") or row.get("cards") or row.get("CARDS"))
                
                result["en"]["starting_lineups"][team][number] = {
                    "name": name,
                    "role": role,
                    "goals": goals,
                    "video_goal": video_goal,
                    "sub_off_minute": sub_off_minute,
                    "cards": cards,
                }
        
        # ===== Parse Starting_Lineups_he =====
        if "Starting_Lineups_he" in excel_data:
            lineups_df = excel_data["Starting_Lineups_he"]
            lineups_df = lineups_df.where(pd.notna(lineups_df), None)
            
            # Log column names for debugging
            logger.debug(f"Starting_Lineups_he columns: {list(lineups_df.columns)}")
            
            # Hebrew column names: קבוצה (Team), מס' (Number), שם שחקן (Player Name), תפקיד (Role), 
            # שערים (Goals), שער_וידאו (Video Goal), דקה יציאה (Exit Minute), כרטיסים (Cards)
            # Try to find columns with flexible matching
            def get_hebrew_column(row, possible_names):
                """Try to get column value using multiple possible Hebrew names"""
                for name in possible_names:
                    if name in row:
                        val = row[name]
                        if val is not None and not pd.isna(val):
                            return val
                return None
            
            for _, row in lineups_df.iterrows():
                # Try multiple possible column name variations
                team = get_hebrew_column(row, ["קבוצה", "קבוצה "])  # Team
                number = get_hebrew_column(row, ["מס'", "מספר", "מס"])  # Number
                name = get_hebrew_column(row, ["שם שחקן", "שם", "שם השחקן"])  # Player Name
                
                # Skip invalid rows
                if not team or (isinstance(team, str) and team.strip() in ["", "no.", "קבוצה"]):
                    continue
                if not number:
                    continue
                if not name or (isinstance(name, str) and name.strip() in ["", "GOALS TABLE", "CARD TABLE", "שם שחקן"]):
                    continue
                
                team = str(team).strip()
                try:
                    number = str(int(float(number))) if number is not None else None
                except (ValueError, TypeError):
                    continue
                name = str(name).strip()
                
                if team not in result["he"]["starting_lineups"]:
                    result["he"]["starting_lineups"][team] = {}
                
                # Get other fields - try multiple column name variations
                role = get_hebrew_column(row, ["תפקיד", "תפקיד "])
                if role is None or pd.isna(role):
                    role = "—"
                else:
                    role = str(role).strip()
                
                goals = parse_goals_value(get_hebrew_column(row, ["שערים", "שער"]))
                video_goal = parse_video_goal_value(get_hebrew_column(row, ["שער_וידאו", "שער וידאו", "וידאו שער"]))
                sub_off_minute = parse_sub_off_minute(get_hebrew_column(row, ["דקה יציאה", "דקת יציאה", "יציאה"]))
                cards = parse_cards_value(get_hebrew_column(row, ["כרטיסים", "כרטיס"]))
                
                # Use English keys for player data structure (consistent with example)
                result["he"]["starting_lineups"][team][number] = {
                    "name": name,
                    "role": role,
                    "goals": goals,
                    "video_goal": video_goal,
                    "sub_off_minute": sub_off_minute,
                    "cards": cards,
                }
        
        # ===== Parse Replacements_en =====
        if "Replacements_en" in excel_data:
            replacements_df = excel_data["Replacements_en"]
            replacements_df = replacements_df.where(pd.notna(replacements_df), None)
            
            for _, row in replacements_df.iterrows():
                team = row.get("Team")
                number = row.get("Number")
                name = row.get("Name")
                
                if not team or pd.isna(team) or (isinstance(team, str) and team.strip() in ["", "Team"]):
                    continue
                if not number or pd.isna(number):
                    continue
                if not name or pd.isna(name) or (isinstance(name, str) and name.strip() in ["", "Name"]):
                    continue
                
                team = str(team).strip()
                try:
                    number = str(int(float(number)))
                except (ValueError, TypeError):
                    continue
                name = str(name).strip()
                
                if team not in result["en"]["replacements"]:
                    result["en"]["replacements"][team] = {}
                
                role = row.get("Role", "—")
                if pd.isna(role) or role is None:
                    role = "—"
                else:
                    role = str(role).strip()
                
                goals = parse_goals_value(row.get("Goals"))
                replacer_minute = parse_sub_off_minute(row.get("ReplacerMinute"))
                
                result["en"]["replacements"][team][number] = {
                    "name": name,
                    "role": role,
                    "goals": goals,
                    "replacer_minute": replacer_minute,
                }
        
        # ===== Parse Replacements_he =====
        if "Replacements_he" in excel_data:
            replacements_df = excel_data["Replacements_he"]
            replacements_df = replacements_df.where(pd.notna(replacements_df), None)
            
            for _, row in replacements_df.iterrows():
                team = get_hebrew_column(row, ["קבוצה", "קבוצה "])
                number = get_hebrew_column(row, ["מס'", "מספר", "מס"])
                name = get_hebrew_column(row, ["שם", "שם שחקן"])
                
                if not team or (isinstance(team, str) and team.strip() in ["", "קבוצה"]):
                    continue
                if not number:
                    continue
                if not name or (isinstance(name, str) and name.strip() in ["", "שם"]):
                    continue
                
                team = str(team).strip()  # Hebrew team name
                try:
                    number = str(int(float(number)))
                except (ValueError, TypeError):
                    continue
                name = str(name).strip()  # Hebrew player name
                
                if team not in result["he"]["replacements"]:
                    result["he"]["replacements"][team] = {}
                
                role = get_hebrew_column(row, ["תפקיד", "תַפְקִיד"])
                if role is None or pd.isna(role):
                    role = "—"
                else:
                    role = str(role).strip()  # Hebrew role
                
                goals = parse_goals_value(get_hebrew_column(row, ["מטרות", "שערים"]))
                replacer_minute = parse_sub_off_minute(get_hebrew_column(row, ["דקת כניסה", "דקה כניסה"]))
                
                # Use English keys, Hebrew values
                result["he"]["replacements"][team][number] = {
                    "name": name,  # Hebrew name
                    "role": role,  # Hebrew role
                    "goals": goals,
                    "replacer_minute": replacer_minute,
                }
        
        # ===== Parse Bench_en =====
        if "Bench_en" in excel_data:
            bench_df = excel_data["Bench_en"]
            bench_df = bench_df.where(pd.notna(bench_df), None)
            
            for _, row in bench_df.iterrows():
                team = row.get("Team")
                number = row.get("Number")
                name = row.get("Name")
                
                if not team or pd.isna(team) or (isinstance(team, str) and team.strip() in ["", "Team"]):
                    continue
                if not number or pd.isna(number):
                    continue
                if not name or pd.isna(name) or (isinstance(name, str) and name.strip() in ["", "Name"]):
                    continue
                
                team = str(team).strip()
                try:
                    number = str(int(float(number)))
                except (ValueError, TypeError):
                    continue
                name = str(name).strip()
                
                if team not in result["en"]["bench"]:
                    result["en"]["bench"][team] = {}
                
                result["en"]["bench"][team][number] = {
                    "name": name,
                }
        
        # ===== Parse Bench_he =====
        if "Bench_he" in excel_data:
            bench_df = excel_data["Bench_he"]
            bench_df = bench_df.where(pd.notna(bench_df), None)
            
            for _, row in bench_df.iterrows():
                team = get_hebrew_column(row, ["קבוצה", "קבוצה "])
                number = get_hebrew_column(row, ["מס'", "מספר", "מס"])
                name = get_hebrew_column(row, ["שם", "שם שחקן"])
                
                if not team or (isinstance(team, str) and team.strip() in ["", "קבוצה"]):
                    continue
                if not number:
                    continue
                if not name or (isinstance(name, str) and name.strip() in ["", "שם"]):
                    continue
                
                team = str(team).strip()  # Hebrew team name
                try:
                    number = str(int(float(number)))
                except (ValueError, TypeError):
                    continue
                name = str(name).strip()  # Hebrew player name
                
                if team not in result["he"]["bench"]:
                    result["he"]["bench"][team] = {}
                
                # Use English keys, Hebrew values
                result["he"]["bench"][team][number] = {
                    "name": name,  # Hebrew name
                }
        
        # ===== Parse Coaches_en =====
        if "Coaches_en" in excel_data:
            coaches_df = excel_data["Coaches_en"]
            coaches_df = coaches_df.where(pd.notna(coaches_df), None)
            
            for _, row in coaches_df.iterrows():
                team = row.get("Team")
                coach_name = row.get("Coach Name")
                role = row.get("Role")
                
                if not team or pd.isna(team) or (isinstance(team, str) and team.strip() in ["", "Team"]):
                    continue
                if not coach_name or pd.isna(coach_name):
                    continue
                
                team = str(team).strip()
                coach_name = str(coach_name).strip()
                role = str(role).strip() if role and not pd.isna(role) else ""
                
                if team not in result["en"]["coaches"]:
                    result["en"]["coaches"][team] = []
                
                result["en"]["coaches"][team].append({
                    "name": coach_name,
                    "role": role,
                })
        
        # ===== Parse Coaches_he =====
        if "Coaches_he" in excel_data:
            coaches_df = excel_data["Coaches_he"]
            coaches_df = coaches_df.where(pd.notna(coaches_df), None)
            
            for _, row in coaches_df.iterrows():
                team = get_hebrew_column(row, ["קבוצה", "קבוצה "])
                coach_name = get_hebrew_column(row, ["שם המאמן", "מאמן"])
                role = get_hebrew_column(row, ["תפקיד"])
                
                if not team or (isinstance(team, str) and team.strip() in ["", "קבוצה"]):
                    continue
                if not coach_name:
                    continue
                
                team = str(team).strip()  # Hebrew team name
                coach_name = str(coach_name).strip()  # Hebrew coach name
                role = str(role).strip() if role and not pd.isna(role) else ""  # Hebrew role
                
                if team not in result["he"]["coaches"]:
                    result["he"]["coaches"][team] = []
                
                # Use English keys, Hebrew values
                result["he"]["coaches"][team].append({
                    "name": coach_name,  # Hebrew name
                    "role": role,  # Hebrew role
                })
        
        # ===== Parse Referees_en =====
        if "Referees_en" in excel_data:
            referees_df = excel_data["Referees_en"]
            referees_df = referees_df.where(pd.notna(referees_df), None)
            
            for _, row in referees_df.iterrows():
                position = row.get("Position")
                name = row.get("Name")
                
                if not position or pd.isna(position):
                    continue
                if not name or pd.isna(name):
                    continue
                
                position = str(position).strip()
                name = str(name).strip()
                
                result["en"]["referees"].append({
                    "position": position,
                    "name": name,
                })
        
        # ===== Parse Referees_he =====
        if "Referees_he" in excel_data:
            referees_df = excel_data["Referees_he"]
            referees_df = referees_df.where(pd.notna(referees_df), None)
            
            for _, row in referees_df.iterrows():
                position = get_hebrew_column(row, ["תפקיד"])
                name = get_hebrew_column(row, ["שם"])
                
                if not position:
                    continue
                if not name:
                    continue
                
                position = str(position).strip()  # Hebrew position
                name = str(name).strip()  # Hebrew name
                
                # Use English keys, Hebrew values
                result["he"]["referees"].append({
                    "position": position,  # Hebrew position
                    "name": name,  # Hebrew name
                })
        
        # Convert to JSON-serializable format
        result = make_json_serializable(result)
        
        # Validate structure
        logger.info("Validating extracted data structure...")
        validation_errors = []
        
        # Check English structure
        if not result.get("en"):
            validation_errors.append("Missing 'en' key in result")
        else:
            if "Match_summary" not in result["en"]:
                validation_errors.append("Missing 'Match_summary' in 'en'")
            if "starting_lineups" not in result["en"]:
                validation_errors.append("Missing 'starting_lineups' in 'en'")
            if "replacements" not in result["en"]:
                validation_errors.append("Missing 'replacements' in 'en'")
            if "bench" not in result["en"]:
                validation_errors.append("Missing 'bench' in 'en'")
            if "coaches" not in result["en"]:
                validation_errors.append("Missing 'coaches' in 'en'")
            if "referees" not in result["en"]:
                validation_errors.append("Missing 'referees' in 'en'")
        
        # Check Hebrew structure
        if not result.get("he"):
            validation_errors.append("Missing 'he' key in result")
        else:
            if "Match_summary" not in result["he"]:
                validation_errors.append("Missing 'Match_summary' in 'he'")
            if "starting_lineups" not in result["he"]:
                validation_errors.append("Missing 'starting_lineups' in 'he'")
            if "replacements" not in result["he"]:
                validation_errors.append("Missing 'replacements' in 'he'")
            if "bench" not in result["he"]:
                validation_errors.append("Missing 'bench' in 'he'")
            if "coaches" not in result["he"]:
                validation_errors.append("Missing 'coaches' in 'he'")
            if "referees" not in result["he"]:
                validation_errors.append("Missing 'referees' in 'he'")
        
        if validation_errors:
            logger.warning(f"Validation warnings: {', '.join(validation_errors)}")
        else:
            logger.info("✓ Data structure validation passed")
        
        # Save to JSON file in the data directory
        try:
            excel_dir = os.path.dirname(excel_file_path)
            excel_basename = os.path.basename(excel_file_path)
            json_filename = os.path.splitext(excel_basename)[0] + "_multilingual.json"
            
            # Save in the same directory as Excel file (data directory)
            json_file_path = os.path.join(excel_dir, json_filename)
            
            with open(json_file_path, "w", encoding="utf-8") as f:
                json.dump(result, f, indent=4, ensure_ascii=False)
            
            logger.info(f"Multilingual match data saved to JSON file: {json_file_path}")
            print(f"\n✓ Multilingual JSON file saved successfully at: {json_file_path}")
            print(f"  File size: {os.path.getsize(json_file_path)} bytes")
            
            # Print summary of what was extracted
            en_teams = len(result.get("en", {}).get("starting_lineups", {}))
            he_teams = len(result.get("he", {}).get("starting_lineups", {}))
            en_players = sum(len(players) for players in result.get("en", {}).get("starting_lineups", {}).values())
            he_players = sum(len(players) for players in result.get("he", {}).get("starting_lineups", {}).values())
            en_replacements = sum(len(players) for players in result.get("en", {}).get("replacements", {}).values())
            he_replacements = sum(len(players) for players in result.get("he", {}).get("replacements", {}).values())
            en_bench = sum(len(players) for players in result.get("en", {}).get("bench", {}).values())
            he_bench = sum(len(players) for players in result.get("he", {}).get("bench", {}).values())
            en_coaches = sum(len(coaches) for coaches in result.get("en", {}).get("coaches", {}).values())
            he_coaches = sum(len(coaches) for coaches in result.get("he", {}).get("coaches", {}).values())
            en_referees = len(result.get("en", {}).get("referees", []))
            he_referees = len(result.get("he", {}).get("referees", []))
            
            print(f"\n  Extracted Summary:")
            print(f"    English:")
            print(f"      - Match Summary: {'✓' if result.get('en', {}).get('Match_summary') else '✗'}")
            print(f"      - Starting Lineups: {en_teams} teams, {en_players} players")
            print(f"      - Replacements: {en_replacements} players")
            print(f"      - Bench: {en_bench} players")
            print(f"      - Coaches: {en_coaches} coaches")
            print(f"      - Referees: {en_referees} referees")
            print(f"    Hebrew:")
            print(f"      - Match Summary: {'✓' if result.get('he', {}).get('Match_summary') else '✗'}")
            print(f"      - Starting Lineups: {he_teams} teams, {he_players} players")
            print(f"      - Replacements: {he_replacements} players")
            print(f"      - Bench: {he_bench} players")
            print(f"      - Coaches: {he_coaches} coaches")
            print(f"      - Referees: {he_referees} referees")
            
        except Exception as e:
            logger.warning(
                f"Failed to save multilingual data to JSON file: {e}",
                exc_info=True
            )
        
        return result
        
    except Exception as e:
        logger.error(
            f"Error extracting multilingual match data from Excel file {excel_file_path}: {e}",
            exc_info=True,
            stack_info=True,
        )
        raise




def parse_time_to_seconds(time_str: str) -> int:
    """Parse time string (HH:MM:SS or MM:SS) to total seconds."""
    if not time_str:
        return None
    try:
        parts = time_str.split(":")
        if len(parts) == 3:
            hours, minutes, seconds = map(int, parts)
            return hours * 3600 + minutes * 60 + seconds
        elif len(parts) == 2:
            minutes, seconds = map(int, parts)
            return minutes * 60 + seconds
        else:
            logger.warning(
                f"Invalid time format '{time_str}'. Expected HH:MM:SS or MM:SS"
            )
            return None
    except ValueError:
        logger.warning(f"Could not parse time '{time_str}'. Expected HH:MM:SS or MM:SS")
        return None


def is_highlight_in_game_time(
    highlight: dict,
    game_start_time: int,
    first_half_end_time: int,
    second_half_start_time: int,
    game_end_time: int,
) -> bool:
    """Check if highlight occurs during actual game time."""
    start_offset = highlight.get("start_offset", 0)
    # Convert milliseconds to seconds
    highlight_time_seconds = start_offset / 1000

    # Filter 1: Before game start time
    if game_start_time is not None and highlight_time_seconds < game_start_time:
        return False

    # Filter 2: Between first half end and second half start (half-time)
    if (
        first_half_end_time is not None
        and second_half_start_time is not None
        and first_half_end_time <= highlight_time_seconds < second_half_start_time
    ):
        return False

    # Filter 3: After game end time
    if game_end_time is not None and highlight_time_seconds > game_end_time:
        return False

    return True


def filter_highlights_by_game_time(
    highlights: list,
    game_start_time: int,
    first_half_end_time: int,
    second_half_start_time: int,
    game_end_time: int,
):
    """Filter highlights based on game time constraints."""
    if not any(
        [game_start_time, first_half_end_time, second_half_start_time, game_end_time]
    ):
        logger.info("No game time filters provided - using all highlights")
        return highlights

    original_count = len(highlights)
    filtered_highlights = [
        h
        for h in highlights
        if is_highlight_in_game_time(
            h,
            game_start_time,
            first_half_end_time,
            second_half_start_time,
            game_end_time,
        )
    ]
    filtered_count = len(filtered_highlights)
    removed_count = original_count - filtered_count

    logger.info(f"Game time filtering applied:")
    logger.info(f"  Original highlights: {original_count}")
    logger.info(f"  Filtered highlights: {filtered_count}")
    logger.info(f"  Removed highlights: {removed_count}")

    if game_start_time is not None:
        logger.info(f"  Game start: {game_start_time}s")
    if first_half_end_time is not None:
        logger.info(f"  First half end: {first_half_end_time}s")
    if second_half_start_time is not None:
        logger.info(f"  Second half start: {second_half_start_time}s")
    if game_end_time is not None:
        logger.info(f"  Game end: {game_end_time}s")

    return filtered_highlights


def ms_to_clock(ms: int) -> str:
    """Convert milliseconds to clock format (MM:SS)."""
    total_seconds = ms // 1000
    minutes = total_seconds // 60
    seconds = total_seconds % 60
    return f"{minutes:02d}:{seconds:02d}"


def get_hex_from_color_name(color_name):
    try:
        return webcolors.name_to_hex(color_name.lower())
    except ValueError:
        return None  # or return a default like "#000000"


def calculate_metrics_from_spotlight_file(
    file_path: str, field_length_m: float = 105.0, field_width_m: float = 68.0
) -> Tuple[Dict[str, str], Dict[str, str]]:
    """
    Calculate GPS Athletic Skills and GPS Football Abilities from a spotlight JSON file

    Args:
        file_path: Path to the spotlight JSON file (e.g., "11.json")
        field_length_m: Field length in meters (default: 105.0 - FIFA standard)
        field_width_m: Field width in meters (default: 68.0 - FIFA standard)

    Returns:
        Tuple of (athletic_metrics, football_metrics)

    Example:
        athletic, football = calculate_metrics_from_spotlight_file("c:/path/to/11.json")
        print("Athletic Skills:", athletic)
        print("Football Abilities:", football)

        # With custom field dimensions
        athletic, football = calculate_metrics_from_spotlight_file("c:/path/to/11.json", 91.0, 55.0)
    """
    try:
        from .spotlight_metrics_calculator import SpotlightMetricsCalculator

        calculator = SpotlightMetricsCalculator(
            field_length_m=field_length_m, field_width_m=field_width_m
        )
        spotlights = calculator.load_spotlight_data(file_path)

        if not spotlights:
            logger.error(f"No spotlight data found in {file_path}")
            return (
                calculator._get_empty_athletic_metrics(),
                calculator._get_empty_football_metrics(),
            )

        logger.info(f"Calculating metrics from {len(spotlights)} tracking points")

        athletic_metrics = calculator.calculate_gps_athletic_skills(spotlights)
        football_metrics = calculator.calculate_gps_football_abilities(spotlights)

        return athletic_metrics, football_metrics

    except Exception as e:
        logger.exception(f"Error calculating metrics from {file_path}: {e}")
        # Return empty metrics on error
        from .spotlight_metrics_calculator import SpotlightMetricsCalculator

        calculator = SpotlightMetricsCalculator(
            field_length_m=field_length_m, field_width_m=field_width_m
        )
        return (
            calculator._get_empty_athletic_metrics(),
            calculator._get_empty_football_metrics(),
        )


def format_metrics_for_display(
    athletic_metrics: Dict[str, str], football_metrics: Dict[str, str]
) -> str:
    """
    Format calculated metrics for display

    Args:
        athletic_metrics: GPS Athletic Skills metrics
        football_metrics: GPS Football Abilities metrics

    Returns:
        Formatted string for display
    """
    output = []

    output.append("=== GPS Athletic Skills Metrics ===")
    for key, value in athletic_metrics.items():
        output.append(f"{key}: {value}")

    output.append("\n=== GPS Football Abilities Metrics ===")
    for key, value in football_metrics.items():
        output.append(f"{key}: {value}")

    return "\n".join(output)


def save_metrics_to_cards(
    user, athletic_metrics: Dict[str, str], football_metrics: Dict[str, str], game=None
):
    """
    Save calculated metrics to GPS card models

    Args:
        user: WajoUser instance
        athletic_metrics: GPS Athletic Skills metrics
        football_metrics: GPS Football Abilities metrics
        game: Game instance (optional)
    """
    try:
        # Save GPS Athletic Skills
        gps_athletic, created = GPSAthleticSkills.objects.update_or_create(
            user=user,
            game=game,
            defaults={"metrics": athletic_metrics, "updated_on": timezone.now()},
        )

        # Save GPS Football Abilities
        gps_football, created = GPSFootballAbilities.objects.update_or_create(
            user=user,
            game=game,
            defaults={"metrics": football_metrics, "updated_on": timezone.now()},
        )

        logger.info(f"Saved GPS metrics for user {user.id}")
        return True

    except Exception as e:
        logger.exception(f"Error saving GPS metrics: {e}")
        return False


class TraceVisionStoragePaths:
    """
    Centralized class for managing Azure Blob Storage file paths for TraceVision.
    """

    @staticmethod
    def get_session_video_path(session_id: str, video_type: str = "original") -> str:
        """Get path for session video files."""
        if video_type == "original":
            return f"sessions/{session_id}/videos/original/{session_id}_video.mp4"
        else:
            return (
                f"sessions/{session_id}/videos/processed/{session_id}_{video_type}.mp4"
            )

    @staticmethod
    def get_highlight_video_path(
        session_id: str,
        highlight_id: str,
        video_type: str,
        event_id: str = None,
        ratio: str = None,
    ) -> str:
        """
        Get path for highlight video files.

        Args:
            session_id: Session ID
            highlight_id: Highlight ID
            video_type: Video type (e.g., "original", "with_overlay")
            event_id: Event ID (optional, for unique naming)
            ratio: Video ratio (e.g., "original", "9:16") (optional, for unique naming)

        Returns:
            str: Blob path in format: sessions/{session_id}/videos/highlights/{event_id}_{video_type}_{ratio}.mp4
        """
        # Build filename components
        filename_parts = []

        if event_id:
            filename_parts.append(event_id)
        else:
            filename_parts.append(
                highlight_id
            )  # Fallback to highlight_id if event_id not provided

        filename_parts.append(video_type)

        if ratio:
            # Replace ":" with "_" for filename compatibility (e.g., "9:16" -> "9_16")
            ratio_safe = ratio.replace(":", "_")
            filename_parts.append(ratio_safe)

        filename = "_".join(filename_parts) + ".mp4"

        return f"sessions/{session_id}/videos/highlights/{filename}"

    @staticmethod
    def get_tracking_data_path(session_id: str, object_id: str) -> str:
        """Get path for tracking data files."""
        return f"sessions/{session_id}/data/tracking/{object_id}_tracking_data.json"

    @staticmethod
    def get_session_result_path(session_id: str) -> str:
        """Get path for session result data."""
        return f"sessions/{session_id}/data/{session_id}_result.json"

    @staticmethod
    def get_player_stats_path(session_id: str, player_id: str = None) -> str:
        """Get path for player statistics."""
        if player_id:
            return f"sessions/{session_id}/data/analytics/player_stats/{player_id}_stats.json"
        else:
            return f"sessions/{session_id}/data/analytics/player_stats/all_players_stats.json"

    @staticmethod
    def get_team_stats_path(session_id: str, team_side: str = None) -> str:
        """Get path for team statistics."""
        if team_side:
            return f"sessions/{session_id}/data/analytics/team_stats/{team_side}_team_stats.json"
        else:
            return (
                f"sessions/{session_id}/data/analytics/team_stats/combined_stats.json"
            )

    @staticmethod
    def get_heatmap_path(session_id: str, player_id: str) -> str:
        """Get path for player heatmap data."""
        return f"sessions/{session_id}/data/analytics/heatmaps/{player_id}_heatmap.json"

    @staticmethod
    def get_thumbnail_path(
        session_id: str, highlight_id: str, thumbnail_type: str = "thumbnail"
    ) -> str:
        """Get path for thumbnail images."""
        return f"sessions/{session_id}/thumbnails/{highlight_id}_{thumbnail_type}.jpg"

    @staticmethod
    def get_export_path(
        session_id: str, export_type: str, file_extension: str = "json"
    ) -> str:
        """Get path for exported files."""
        return f"exports/{session_id}/{export_type}/{session_id}_{export_type}.{file_extension}"

    @staticmethod
    def get_temp_path(session_id: str, temp_file_name: str) -> str:
        """Get path for temporary processing files."""
        return f"temp/processing/{session_id}/{temp_file_name}"


def convert_game_time_to_video_milliseconds(session, game_minute, game_second=0):
    """
    Convert game time (minute:second) to video milliseconds using session timeline data.

    This function handles the complex mapping between game time and video time by considering:
    - Video start delay (match_start_time)
    - First half duration and end time
    - Half time break duration
    - Second half start time

    Args:
        session (TraceSession): Session with timeline data
        game_minute (int): Game minute (0-90+)
        game_second (int): Game second (0-59)

    Returns:
        int: Milliseconds from video start, or 0 if conversion fails
    """
    try:
        if not session or game_minute is None:
            return 0

        # Validate that we have the required timeline data
        if not all(
            [
                session.match_start_time,
                session.first_half_end_time,
                session.second_half_start_time,
                session.match_end_time,
            ]
        ):
            logger.warning(
                f"Session {session.session_id} missing timeline data. Cannot convert game time."
            )
            return 0

        # Convert timeline strings to seconds
        def time_to_seconds(time_str):
            """Convert HH:MM:SS or MM:SS to total seconds"""
            try:
                parts = time_str.split(":")
                if len(parts) == 3:  # HH:MM:SS
                    hours, minutes, seconds = map(int, parts)
                    return hours * 3600 + minutes * 60 + seconds
                elif len(parts) == 2:  # MM:SS
                    minutes, seconds = map(int, parts)
                    return minutes * 60 + seconds
                else:
                    return 0
            except (ValueError, IndexError):
                logger.warning(f"Invalid time format: {time_str}")
                return 0

        # Get video timeline in seconds
        video_match_start = time_to_seconds(session.match_start_time)
        video_first_half_end = time_to_seconds(session.first_half_end_time)
        video_second_half_start = time_to_seconds(session.second_half_start_time)
        video_match_end = time_to_seconds(session.match_end_time)

        # First half game duration = time from match start to first half end
        first_half_game_duration = video_first_half_end - video_match_start

        # Half time break duration = time from first half end to second half start
        half_time_duration = video_second_half_start - video_first_half_end

        # Second half game duration = time from second half start to match end
        second_half_game_duration = video_match_end - video_second_half_start

        # Use standard football timing: first half 0-45 min, second half 45-90+ min
        first_half_end_game_minute = 45.0  # Standard first half ends at 45 minutes
        second_half_start_game_minute = 45.0  # Second half starts at 45 minutes
        second_half_end_game_minute = 90.0  # Standard second half ends at 90 minutes

        logger.info(f"Session {session.session_id} timeline analysis:")
        logger.info(
            f"  First half: 0-{first_half_end_game_minute:.1f} min (video: {session.match_start_time} to {session.first_half_end_time})"
        )
        logger.info(
            f"  Half time: {first_half_end_game_minute:.1f}-{second_half_start_game_minute:.1f} min (video: {session.first_half_end_time} to {session.second_half_start_time})"
        )
        logger.info(
            f"  Second half: {second_half_start_game_minute:.1f}-{second_half_end_game_minute:.1f} min (video: {session.second_half_start_time} to {session.match_end_time})"
        )

        if game_minute <= 45:  # First half (0-45 min game time)
            # Map game time proportionally within first half video duration
            progress = game_minute / 45.0  # 0.0 to 1.0
            video_time_seconds = video_match_start + (
                first_half_game_duration * progress
            )
            logger.info(f"  First half: {game_minute}/45 = {progress:.3f} progress")

        else:
            minutes_into_second_half = game_minute - 45
            seconds_into_second_half = minutes_into_second_half * 60 + game_second

            second_half_video_duration = video_match_end - video_second_half_start
            second_half_game_duration = 45 * 60  # Standard 45 minutes for second half

            # Calculate the time ratio (how much video time per game time)
            time_ratio = second_half_video_duration / second_half_game_duration

            # Map game time to video time using the calculated ratio
            game_time_into_second_half = (game_minute - 45) * 60 + game_second
            video_time_seconds = video_second_half_start + (
                game_time_into_second_half * time_ratio
            )

            # For extra time beyond normal match duration, add additional time
            if game_minute > 90:
                extra_minutes = game_minute - 90
                video_time_seconds += extra_minutes * 60
                logger.info(f"    Extra time: +{extra_minutes} min")

        # Convert to milliseconds
        video_time_milliseconds = int(video_time_seconds * 1000)

        logger.info(
            f"Converted game time {game_minute}:{game_second:02d} to video time {video_time_seconds:.2f}s ({video_time_milliseconds}ms)"
        )

        return video_time_milliseconds

    except Exception as e:
        logger.exception(
            f"Error converting game time {game_minute}:{game_second} to video milliseconds: {e}"
        )
        return 0


def determine_game_half_from_highlight_offset(
    start_offset_ms,
    match_start_time,
    first_half_end_time,
    second_half_start_time,
    match_end_time,
):
    """
    Determine which half a highlight belongs to based on its start offset and session timing data.

    Args:
        start_offset_ms (int): Highlight start offset in milliseconds
        match_start_time (str): Match start time in HH:MM:SS or MM:SS format
        first_half_end_time (str): First half end time in HH:MM:SS or MM:SS format
        second_half_start_time (str): Second half start time in HH:MM:SS or MM:SS format
        match_end_time (str): Match end time in HH:MM:SS or MM:SS format

    Returns:
        int: Half number (1 or 2), or None if cannot determine
    """
    try:
        if start_offset_ms is None or start_offset_ms < 0:
            return None

        # Convert timeline strings to seconds
        def time_to_seconds(time_str):
            """Convert HH:MM:SS or MM:SS to total seconds"""
            if not time_str:
                return None
            try:
                parts = time_str.split(":")
                if len(parts) == 3:  # HH:MM:SS
                    hours, minutes, seconds = map(int, parts)
                    return hours * 3600 + minutes * 60 + seconds
                elif len(parts) == 2:  # MM:SS
                    minutes, seconds = map(int, parts)
                    return minutes * 60 + seconds
                else:
                    return None
            except (ValueError, IndexError):
                logger.warning(f"Invalid time format: {time_str}")
                return None

        # Convert highlight offset to seconds
        highlight_time_seconds = start_offset_ms / 1000.0

        # Get timeline in seconds
        video_match_start = time_to_seconds(match_start_time) if match_start_time else 0
        video_first_half_end = (
            time_to_seconds(first_half_end_time) if first_half_end_time else None
        )
        video_second_half_start = (
            time_to_seconds(second_half_start_time) if second_half_start_time else None
        )
        video_match_end = time_to_seconds(match_end_time) if match_end_time else None

        # If we don't have enough timing data, return None
        if video_first_half_end is None or video_second_half_start is None:
            logger.warning("Insufficient timing data to determine half")
            return None

        # Determine which half the highlight occurs in
        if highlight_time_seconds < video_first_half_end:
            return 1  # First half
        elif highlight_time_seconds < video_second_half_start:
            return None  # Half-time break
        else:
            return 2  # Second half

    except Exception as e:
        logger.exception(
            f"Error determining half for highlight offset {start_offset_ms}: {e}"
        )
        return None


def determine_game_half_from_minute(session, game_minute):
    """
    Determine which half a game minute falls into based on session timeline data.

    Args:
        session (TraceSession): Session with timeline data
        game_minute (int): Game minute (0-90+)

    Returns:
        int: Half number (1 or 2), or None if cannot determine
    """
    try:
        if not session or game_minute is None:
            return None

        # Validate that we have the required timeline data
        if not all(
            [
                session.match_start_time,
                session.first_half_end_time,
                session.second_half_start_time,
                session.match_end_time,
            ]
        ):
            logger.warning(
                f"Session {session.session_id} missing timeline data. Cannot determine half."
            )
            return None

        # Convert timeline strings to seconds
        def time_to_seconds(time_str):
            """Convert HH:MM:SS or MM:SS to total seconds"""
            try:
                parts = time_str.split(":")
                if len(parts) == 3:  # HH:MM:SS
                    hours, minutes, seconds = map(int, parts)
                    return hours * 3600 + minutes * 60 + seconds
                elif len(parts) == 2:  # MM:SS
                    minutes, seconds = map(int, parts)
                    return minutes * 60 + seconds
                else:
                    return 0
            except (ValueError, IndexError):
                logger.warning(f"Invalid time format: {time_str}")
                return 0

        # Get video timeline in seconds
        video_match_start = time_to_seconds(session.match_start_time)
        video_first_half_end = time_to_seconds(session.first_half_end_time)
        video_second_half_start = time_to_seconds(session.second_half_start_time)
        video_match_end = time_to_seconds(session.match_end_time)

        # Calculate actual game half durations from video timeline
        first_half_game_duration = video_first_half_end - video_match_start
        half_time_duration = video_second_half_start - video_first_half_end
        second_half_game_duration = video_match_end - video_second_half_start

        # Calculate the actual game minute when first half ends (based on video timeline)
        first_half_end_game_minute = (
            first_half_game_duration / 60.0
        )  # Convert to minutes
        second_half_start_game_minute = first_half_end_game_minute + (
            half_time_duration / 60.0
        )
        second_half_end_game_minute = second_half_start_game_minute + (
            second_half_game_duration / 60.0
        )

        # Determine which half the event occurs in based on actual timeline
        if game_minute <= first_half_end_game_minute:
            return 1  # First half
        elif game_minute <= second_half_end_game_minute:
            return 2  # Second half
        else:
            return 2  # Extra time is considered part of second half

    except Exception as e:
        logger.exception(f"Error determining half for game minute {game_minute}: {e}")
        return None


def extract_timeline_data(session):
    """
    Extract timeline data from session for time conversion functions.

    Args:
        session (TraceSession): Session with timeline data

    Returns:
        dict: Timeline data with video times in seconds
    """
    try:
        if not session:
            return None

        # Convert timeline strings to seconds
        def time_to_seconds(time_str):
            """Convert HH:MM:SS or MM:SS to total seconds"""
            try:
                parts = time_str.split(":")
                if len(parts) == 3:  # HH:MM:SS
                    hours, minutes, seconds = map(int, parts)
                    return hours * 3600 + minutes * 60 + seconds
                elif len(parts) == 2:  # MM:SS
                    minutes, seconds = map(int, parts)
                    return minutes * 60 + seconds
                else:
                    return 0
            except (ValueError, IndexError):
                logger.warning(f"Invalid time format: {time_str}")
                return 0

        # Get video timeline in seconds
        video_match_start = time_to_seconds(session.match_start_time)
        video_first_half_end = time_to_seconds(session.first_half_end_time)
        video_second_half_start = time_to_seconds(session.second_half_start_time)
        video_match_end = time_to_seconds(session.match_end_time)

        # Calculate actual game half durations from video timeline
        first_half_game_duration = video_first_half_end - video_match_start
        half_time_duration = video_second_half_start - video_first_half_end
        second_half_game_duration = video_match_end - video_second_half_start

        # Calculate the actual game minute when first half ends (based on video timeline)
        first_half_end_game_minute = (
            first_half_game_duration / 60.0
        )  # Convert to minutes
        second_half_start_game_minute = first_half_end_game_minute + (
            half_time_duration / 60.0
        )
        second_half_end_game_minute = second_half_start_game_minute + (
            second_half_game_duration / 60.0
        )

        return {
            "video_match_start": video_match_start,
            "video_first_half_end": video_first_half_end,
            "video_second_half_start": video_second_half_start,
            "video_match_end": video_match_end,
            "first_half_game_duration": first_half_game_duration,
            "half_time_duration": half_time_duration,
            "second_half_game_duration": second_half_game_duration,
            "first_half_end_game_minute": first_half_end_game_minute,
            "second_half_start_game_minute": second_half_start_game_minute,
            "second_half_end_game_minute": second_half_end_game_minute,
        }

    except Exception as e:
        logger.exception(
            f"Error extracting timeline data from session {session.session_id}: {e}"
        )
        return None


def cleanup_temp_files(temp_files):
    """
    Clean up temporary files from server storage.

    Args:
        temp_files (list): List of temporary file paths to clean up
    """
    for temp_file in temp_files:
        if temp_file and os.path.exists(temp_file):
            try:
                os.unlink(temp_file)
                logger.info(f"Cleaned up temporary file: {temp_file}")
            except Exception as e:
                logger.warning(f"Failed to clean up temporary file {temp_file}: {e}")


def check_duplicate_game(
    video_url=None, home_team=None, away_team=None, match_date=None
):
    """
    Check if a game already exists based on video_url or (home_team, away_team, match_date).

    Args:
        video_url (str, optional): Video URL to check
        home_team (Team, optional): Home team instance
        away_team (Team, optional): Away team instance
        match_date (date, optional): Match date

    Returns:
        TraceSession or None: Existing session if duplicate found, None otherwise
    """
    from tracevision.models import TraceSession

    # Check by video_url (exact match)
    if video_url:
        existing_session = TraceSession.objects.filter(
            video_url=video_url
        ).exclude(status="process_error").first()
        if existing_session:
            logger.info(f"Duplicate found by video_url: {video_url}")
            return existing_session

    # Check by (home_team, away_team, match_date)
    if home_team and away_team and match_date:
        existing_session = TraceSession.objects.filter(
            home_team=home_team, away_team=away_team, match_date=match_date
        ).exclude(status="process_error").first()
        if existing_session:
            logger.info(
                f"Duplicate found by teams and date: {home_team} vs {away_team} on {match_date}"
            )
            return existing_session

    return None


def get_viewer_team(user):
    """
    Extract viewer's team from user object.

    Args:
        user: WajoUser instance

    Returns:
        Team or None: User's team if they are a player
    """
    if user and hasattr(user, "team") and user.team:
        return user.team
    return None


def determine_viewer_perspective(viewer_team, session):
    """
    Determine if viewer is home or away team based on session teams.

    Args:
        viewer_team (Team): Viewer's team
        session (TraceSession): Session with home_team and away_team

    Returns:
        str: 'home' if viewer is home team, 'away' if away team, None if no match
    """
    if not viewer_team or not session:
        return None

    if session.home_team and viewer_team.id == session.home_team.id:
        return "home"
    elif session.away_team and viewer_team.id == session.away_team.id:
        return "away"

    return None


def transform_side_by_perspective(side, viewer_perspective):
    """
    Transform side ('home'/'away') to 'team'/'opponent' based on viewer's perspective.
    - If viewer is home: 'home' → 'team', 'away' → 'opponent'
    - If viewer is away: 'away' → 'team', 'home' → 'opponent'
    - If no match: return original side

    Args:
        side (str): Original side ('home' or 'away')
        viewer_perspective (str): Viewer's perspective ('home' or 'away')

    Returns:
        str: Transformed side ('team', 'opponent', or original)
    """
    if not side or not viewer_perspective:
        return side

    side_lower = side.lower()
    perspective_lower = viewer_perspective.lower()

    if side_lower == perspective_lower:
        return "team"
    elif (side_lower == "home" and perspective_lower == "away") or (
        side_lower == "away" and perspective_lower == "home"
    ):
        return "opponent"

    return side


def get_or_create_canonical_game(home_team, away_team, match_date, game_type="match"):
    """
    Get or create a canonical Game instance for the given teams and date.

    Args:
        home_team (Team): Home team instance
        away_team (Team): Away team instance
        match_date (date): Match date
        game_type (str): Game type ('match' or 'training'), default 'match'

    Returns:
        Game: Canonical game instance
    """
    from games.models import Game

    # Generate game ID from teams and date using hash to ensure uniqueness
    # Format: Hash of HOME_TEAM_ID_AWAY_TEAM_ID_YYYYMMDD (truncated to 10 chars)
    import hashlib
    
    home_id = "".join(c for c in str(home_team.id).upper() if c.isalnum())[:5]
    away_id = "".join(c for c in str(away_team.id).upper() if c.isalnum())[:5]
    date_str = match_date.strftime("%Y%m%d")
    # Create a unique string combining all identifiers
    unique_string = f"{home_id}_{away_id}_{date_str}"
    # Generate hash and take first 10 characters (alphanumeric only)
    hash_obj = hashlib.md5(unique_string.encode())
    hash_hex = hash_obj.hexdigest()
    # Take first 10 alphanumeric characters from hash
    game_id = "".join(c for c in hash_hex if c.isalnum())[:10].upper()

    # Try to get existing game (including soft-deleted ones)
    game, created = Game.all_objects.get_or_create(
        id=game_id,
        defaults={
            "type": game_type,
            "name": f"{home_team.name} vs {away_team.name}",
            "date": match_date,
        },
    )

    # If the game was soft-deleted previously, restore it
    if hasattr(game, "restore") and game.is_deleted:
        game.restore()

    # Ensure teams are linked
    if home_team not in game.teams.all():
        game.teams.add(home_team)
    if away_team not in game.teams.all():
        game.teams.add(away_team)

    if created:
        logger.info(f"Created new canonical game: {game_id}")
    else:
        logger.info(f"Using existing canonical game: {game_id}")

    return game


def download_excel_file_from_storage(blob_url: str) -> str:
    """
    Download Excel file from Azure Blob storage to a temporary file.

    Args:
        blob_url (str): Azure blob URL or local file path

    Returns:
        str: Path to temporary Excel file
    """
    temp_file_path = None
    try:
        # Check if we're in development mode (local file storage)
        if settings.DEBUG and not hasattr(settings, "AZURE_CUSTOM_DOMAIN"):
            logger.info(
                f"Development mode detected - reading from local file: {blob_url}"
            )

            # Convert blob URL to local file path
            if blob_url.startswith("/media/"):
                # Remove /media/ prefix and join with MEDIA_ROOT
                local_file_path = os.path.join(
                    settings.MEDIA_ROOT, blob_url[7:]
                )  # Remove '/media/'
            else:
                # Assume it's already a local path
                local_file_path = blob_url

            if os.path.exists(local_file_path):
                logger.info(f"Using local Excel file: {local_file_path}")
                return local_file_path
            else:
                raise FileNotFoundError(
                    f"Local Excel file not found: {local_file_path}"
                )

        # Production mode - download from Azure blob storage
        logger.info(f"Downloading Excel file from Azure blob: {blob_url}")

        # Extract relative path from full blob URL for default_storage operations
        if blob_url.startswith("https://"):
            # Extract relative path from full Azure blob URL
            # URL format: https://videostoragewajo.blob.core.windows.net/media/sessions/...
            # We need: sessions/...
            if "/media/" in blob_url:
                relative_path = blob_url.split("/media/", 1)[1]
            else:
                raise ValueError(f"Unexpected blob URL format: {blob_url}")
        else:
            # Already a relative path
            relative_path = blob_url

        logger.info(f"Using relative path for storage operations: {relative_path}")

        # Use Django's default storage to download the file
        with default_storage.open(relative_path, "rb") as blob_file:
            # Create a temporary file
            with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as temp_file:
                temp_file.write(blob_file.read())
                temp_file_path = temp_file.name

        logger.info(f"Successfully downloaded Excel file to: {temp_file_path}")
        return temp_file_path

    except Exception as e:
        # Clean up temporary file if it was created but an error occurred
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.unlink(temp_file_path)
                logger.info(f"Cleaned up temporary file after error: {temp_file_path}")
            except Exception as cleanup_error:
                logger.warning(
                    f"Failed to clean up temporary file {temp_file_path} after error: {cleanup_error}"
                )

        logger.error(f"Error downloading Excel file from {blob_url}: {e}")
        raise


def get_or_create_azure_sas_token(blob_url: str, validity_days: int = 1) -> str:
    """
    Get or create Azure SAS token for a blob URL.
    Checks if existing token is valid, otherwise generates a new one.

    Args:
        blob_url: Azure blob URL (with or without existing SAS token)
        validity_days: Number of days the SAS token should be valid (default: 3)

    Returns:
        str: Blob URL with valid SAS token
    """
    try:
        parsed_url = urlparse(blob_url)
        query_params = parse_qs(parsed_url.query)

        # Check if SAS token exists and is still valid
        if "sig" in query_params and "se" in query_params:
            try:
                expiry_str = query_params["se"][0]
                expiry_time = datetime.fromisoformat(expiry_str.replace("Z", "+00:00"))
                # Check if token expires in less than 1 day (regenerate if close to expiry)
                if expiry_time > datetime.now(expiry_time.tzinfo) + timedelta(days=1):
                    logger.debug(f"Existing SAS token is valid until {expiry_time}")
                    return blob_url
                else:
                    logger.info(
                        f"Existing SAS token expires soon ({expiry_time}), regenerating"
                    )
            except (ValueError, KeyError) as e:
                logger.warning(
                    f"Could not parse existing SAS token expiry: {e}, regenerating"
                )

        # Generate new SAS token
        logger.info(
            f"Generating new SAS token for blob URL (validity: {validity_days} days)"
        )

        # Extract blob path from URL
        url_parts = blob_url.split("/")
        container_index = None
        for i, part in enumerate(url_parts):
            if part.endswith(".blob.core.windows.net"):
                container_index = i + 1
                break

        if not container_index or container_index >= len(url_parts):
            raise ValueError(
                f"Could not extract container and blob path from URL: {blob_url}"
            )

        container_name = url_parts[container_index]
        blob_path = "/".join(url_parts[container_index + 1 :])
        # Remove query parameters if any
        if "?" in blob_path:
            blob_path = blob_path.split("?")[0]

        # Get Azure storage credentials from Django settings
        connection_string = getattr(settings, "AZURE_CONNECTION_STRING", None)

        # Extract from connection string if available
        account_name = None
        account_key = None
        if connection_string:
            match = re.search(r"AccountName=([^;]+)", connection_string)
            if match:
                account_name = match.group(1)
            match = re.search(r"AccountKey=([^;]+)", connection_string)
            if match:
                account_key = match.group(1)

        if not account_name or not account_key:
            raise ValueError(
                "Azure account name and key not configured. "
                "Set AZURE_ACCOUNT_NAME and AZURE_ACCOUNT_KEY in Django settings"
            )

        # Get blob client for URL construction
        if connection_string:
            blob_service_client = BlobServiceClient.from_connection_string(
                connection_string
            )
        else:
            account_url = f"https://{account_name}.blob.core.windows.net"
            blob_service_client = BlobServiceClient(
                account_url=account_url, credential=account_key
            )

        blob_client = blob_service_client.get_blob_client(
            container=container_name, blob=blob_path
        )

        # Set expiry time
        expiry_time = datetime.utcnow() + timedelta(days=validity_days)

        # Generate SAS token with read permissions
        sas_token = generate_blob_sas(
            account_name=account_name,
            container_name=container_name,
            blob_name=blob_path,
            account_key=account_key,
            permission=BlobSasPermissions(read=True),
            expiry=expiry_time,
        )

        # Construct URL with SAS token
        blob_url_with_sas = f"{blob_client.url}?{sas_token}"

        logger.info(f"Generated SAS token valid until {expiry_time}:{sas_token}")
        return blob_url_with_sas

    except Exception as e:
        logger.error(f"Error generating SAS token: {e}")
        # Return original URL if SAS token generation fails
        return blob_url


def get_video_fps(blob_url: str) -> float:
    """
    Get the frame rate of a video from Azure blob URL.

    Args:
        blob_url: Azure blob URL (will add SAS token if needed)

    Returns:
        float: Frame rate (FPS), or 30.0 as default if detection fails
    """
    try:
        import subprocess

        blob_url_with_sas = get_or_create_azure_sas_token(blob_url)

        # Use ffprobe to get video FPS
        cmd = [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=r_frame_rate",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            blob_url_with_sas,
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0 and result.stdout.strip():
            # Parse frame rate (format: "30/1" or "29.97/1")
            fps_str = result.stdout.strip()
            if "/" in fps_str:
                num, den = map(float, fps_str.split("/"))
                fps = num / den if den > 0 else 30.0
            else:
                fps = float(fps_str)
            logger.info(f"Detected video FPS: {fps:.2f}")
            return fps
    except Exception as e:
        logger.warning(f"Could not detect FPS: {e}, using default 30.0")

    return 30.0  # Default FPS


def extract_video_segment_from_azure(
    blob_url: str,
    start_time_ms: int,
    duration_ms: int,
    output_path: Optional[str] = None,
    temp_dir: Optional[str] = None,
    reencode_for_cfr: bool = True,
) -> Tuple[str, int]:
    """
    Extract a video segment from Azure Blob Storage using ffmpeg.
    The segment video will start at 00:00, so tracking data needs to be normalized.

    Args:
        blob_url: Azure blob URL (will add SAS token if needed)
        start_time_ms: Start time in milliseconds
        duration_ms: Duration in milliseconds
        output_path: Optional output file path
        temp_dir: Optional temporary directory
        reencode_for_cfr: If True, re-encode to ensure constant frame rate (prevents timing drift)

    Returns:
        Tuple[str, int]: (segment_video_path, time_offset_ms)
            - segment_video_path: Path to extracted segment video
            - time_offset_ms: Offset to normalize tracking data (start_time_ms)
    """
    try:
        if temp_dir is None:
            temp_dir = tempfile.gettempdir()

        # Get or create SAS token for streamable access
        blob_url_with_sas = get_or_create_azure_sas_token(blob_url)

        # Generate output path if not provided
        if output_path is None:
            output_filename = f"segment_{uuid.uuid4().hex}.mp4"
            output_path = os.path.join(temp_dir, output_filename)

        # Convert milliseconds to seconds for ffmpeg
        start_time_sec = start_time_ms / 1000.0
        duration_sec = duration_ms / 1000.0

        logger.info(
            f"Extracting segment: {start_time_sec:.2f}s, duration: {duration_sec:.2f}s"
        )
        logger.info(f"From: {blob_url[:80]}...")

        if reencode_for_cfr:
            # Re-encode to ensure constant frame rate and accurate timestamps
            # This prevents timing drift issues when matching frames to tracking data
            logger.info(f"Re-encoding to constant frame rate for accurate timing...")
            fps = get_video_fps(blob_url)

            cmd = [
                "ffmpeg",
                "-loglevel",
                "error",
                "-ss",
                str(start_time_sec),
                "-i",
                blob_url_with_sas,
                "-t",
                str(duration_sec),
                "-c:v",
                "libx264",
                "-preset",
                "ultrafast",  # Fast encoding for segments
                "-crf",
                "23",  # Good quality
                "-r",
                str(int(fps)),  # Use detected FPS
                "-vsync",
                "cfr",  # Constant frame rate
                "-c:a",
                "copy",  # Copy audio if present
                "-avoid_negative_ts",
                "make_zero",
                "-y",  # Overwrite output file
                output_path,
            ]
        else:
            # Fast copy mode (may have timing drift issues)
            # -ss before -i: fast seeking (seeks in input)
            # -t: duration
            # -c copy: copy codecs (fast, no re-encoding)
            # -avoid_negative_ts make_zero: reset timestamps to start at 0
            cmd = [
                "ffmpeg",
                "-loglevel",
                "error",
                "-ss",
                str(start_time_sec),
                "-i",
                blob_url_with_sas,
                "-t",
                str(duration_sec),
                "-c",
                "copy",
                "-avoid_negative_ts",
                "make_zero",
                "-y",  # Overwrite output file
                output_path,
            ]

        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=300  # 5 minute timeout
        )

        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg failed to extract segment: {result.stderr}")

        if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
            raise RuntimeError("Extracted segment file is empty or doesn't exist")

        file_size_mb = os.path.getsize(output_path) / (1024 * 1024)
        logger.info(
            f"Successfully extracted segment: {output_path} ({file_size_mb:.2f} MB)"
        )

        # Return segment path and time offset (segment starts at 00:00, so offset is start_time_ms)
        return output_path, start_time_ms

    except subprocess.TimeoutExpired:
        logger.error(f"ffmpeg timeout while extracting segment from {blob_url}")
        raise RuntimeError("Video segment extraction timed out")
    except Exception as e:
        logger.error(f"Error extracting video segment: {e}")
        raise
