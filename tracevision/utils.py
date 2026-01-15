import re
import os
import uuid
import json
import logging
import math
import tempfile
import webcolors
import subprocess
import pandas as pd
from azure.storage.blob import (
    BlobServiceClient,
    generate_blob_sas,
    BlobSasPermissions,
)

from django.db.models import Q
from django.conf import settings
from django.utils import timezone
from urllib.parse import urlparse, parse_qs
from datetime import datetime, timedelta, date, time
from typing import Dict, Tuple, Optional
from django.core.files.storage import default_storage


from accounts.models import WajoUser
from cards.models import GPSAthleticSkills, GPSFootballAbilities
from tracevision.models import (
    TracePlayer,
    TraceHighlight,
    TraceClipReel,
    TraceHighlightObject,
    TraceObject,
)

logger = logging.getLogger(__name__)


def create_wajo_user(team, jersey_number, user_data: dict, user_role: str = "Player"):
    """
    Create a WajoUser for the given role (Player, Coach, Referee, etc.).
    Fills in available details from user_data.
    
    Args:
        team: Team instance (required for Players and Coaches, None for Referees)
        jersey_number: Jersey number (required for Players, None for Coaches/Referees)
        user_data: Dict with multilingual name data, e.g., {"name": {"en": "...", "he": "..."}, "role": {"en": "...", "he": "..."}}
        user_role: Role type - "Player", "Coach", "Referee", etc.
    
    Returns:
        WajoUser instance
    """
    if user_role == "Player":
        if not team:
            raise ValueError("Team must be provided to create WajoUser for Player role")
        if jersey_number is None:
            raise ValueError("Jersey number must be provided to create WajoUser for Player role")
    elif user_role == "Coach":
        if not team:
            raise ValueError("Team must be provided to create WajoUser for Coach role")
        # jersey_number should be None for coaches
        jersey_number = None
    elif user_role == "Referee":
        # Referees don't have team or jersey_number
        team = None
        jersey_number = None
    
    if not user_data:
        user_data = {"name": {"en": "", "he": ""}, "role": {"en": "", "he": ""}}
    
    # Determine primary name (use English if available, else Hebrew, else default)
    name_en = user_data.get("name", {}).get("en", "").strip()
    name_he = user_data.get("name", {}).get("he", "").strip()
    
    if user_role == "Player":
        primary_name = name_en or name_he or f"Player {jersey_number}"
    elif user_role == "Coach":
        primary_name = name_en or name_he or "Coach"
    elif user_role == "Referee":
        primary_name = name_en or name_he or "Referee"
    else:
        primary_name = name_en or name_he or user_role
    
    # Build language_metadata
    language_metadata = {}
    if name_en:
        language_metadata["en"] = {"name": name_en}
        role_en = user_data.get("role", {}).get("en", "").strip()
        if role_en:
            language_metadata["en"]["role"] = role_en
    
    if name_he:
        language_metadata["he"] = {"name": name_he}
        role_he = user_data.get("role", {}).get("he", "").strip()
        if role_he:
            language_metadata["he"]["role"] = role_he
    
    # Create the WajoUser
    # For coaches and referees, phone_no should be None (they don't have phone numbers from Excel)
    user = WajoUser.objects.create(
        name=primary_name,
        jersey_number=jersey_number,
        team=team,
        phone_no=None,  # Explicitly set to None for coaches/referees (and players without phone numbers)
        language_metadata=language_metadata,
        is_registered=False,
        created_via="EXCEL",
        role=user_role,
        selected_language="en",
    )

    return user



def get_localized_name(obj, user_language=None, field_name="name"):
    """
    Get localized name from an object based on user's language preference.

    Args:
        obj: Object with language_metadata field (Game, Team, or TracePlayer)
        user_language: User's language preference ('en' or 'he'), defaults to 'en'
        field_name: Field name to extract from language_metadata (default: 'name')

    Returns:
        str: Localized name, or fallback to obj.name/obj.field_name if not available
    """
    if not obj:
        return None

    # Default to 'en' if language not provided
    if not user_language:
        user_language = "en"

    # Normalize language code
    user_language = user_language.lower()
    if user_language not in ["en", "he"]:
        user_language = "en"

    # Try to get from language_metadata
    if hasattr(obj, "language_metadata") and obj.language_metadata:
        lang_data = obj.language_metadata.get(user_language)

        # Handle different structures:
        # 1. Direct value: {'en': 'Team Name', 'he': 'שם קבוצה'}
        if isinstance(lang_data, str) and lang_data.strip():
            return lang_data

        # 2. Nested dict: {'en': {'name': 'Team Name'}, 'he': {'name': 'שם קבוצה'}}
        if isinstance(lang_data, dict) and lang_data:
            value = lang_data.get(field_name)
            # Check if value exists and is not None/empty
            if value is not None:
                # If it's a string, check it's not empty after stripping
                if isinstance(value, str):
                    if value.strip():
                        return value
                else:
                    # Non-string value (number, etc.) - return as is
                    return value

    # Fallback to default field - always return the actual field value
    if hasattr(obj, field_name):
        field_value = getattr(obj, field_name, None)
        if field_value is not None:
            return field_value
    if hasattr(obj, "name"):
        name_value = getattr(obj, "name", None)
        if name_value is not None:
            return name_value

    return None


def get_localized_game_name(game, user_language=None):
    """Get localized Game name based on user's language preference."""
    return get_localized_name(game, user_language, field_name="name")


def get_localized_team_name(team, user_language=None):
    """Get localized Team name based on user's language preference."""
    if not team:
        return None

    # Default to 'en' if language not provided
    if not user_language:
        user_language = "en"

    # Normalize language code
    user_language = user_language.lower()
    if user_language not in ["en", "he"]:
        user_language = "en"

    # Try language_metadata first
    if hasattr(team, "language_metadata") and team.language_metadata:
        lang_data = team.language_metadata.get(user_language)

        # Handle different structures
        # 1. Direct value: {'en': 'Team Name', 'he': 'שם קבוצה'}
        if isinstance(lang_data, str) and lang_data.strip():
            return lang_data

        # 2. Nested dict: {'en': {'name': 'Team Name'}, 'he': {'name': 'שם קבוצה'}}
        if isinstance(lang_data, dict) and lang_data:
            value = lang_data.get("name")
            # Check if value exists and is not None/empty
            if value is not None:
                # If it's a string, check it's not empty after stripping
                if isinstance(value, str):
                    if value.strip():
                        return value
                else:
                    # Non-string value (number, etc.) - return as is
                    return value

    # Fallback to team.name - always return the actual field value
    if hasattr(team, "name"):
        name_value = getattr(team, "name", None)
        if name_value is not None:
            return name_value

    return None


def get_localized_player_name(player, user_language=None):
    """Get localized TracePlayer name based on user's language preference."""
    return get_localized_name(player, user_language, field_name="name")


def normalize_multilingual_data(match_data):
    """
    Normalize the multilingual match data into a structured format.

    Args:
        match_data (dict): Raw multilingual data with 'en' and 'he' sections

    Returns:
        dict: Normalized data structure with teams and players
    """
    normalized = {"teams": [], "players": []}

    # Extract team names
    en_data = match_data.get("en", {})
    he_data = match_data.get("he", {})

    en_summary = en_data.get("Match_summary", {})
    he_summary = he_data.get("Match_summary", {})  # Fixed typo: was "MatcMaih_summary"

    # Normalize team data
    home_team = {
        "name": {
            "en": en_summary.get("match_home_team", ""),
            "he": he_summary.get("match_home_team", ""),
        },
        "side": "home",
        "players": [],
    }

    away_team = {
        "name": {
            "en": en_summary.get("match_away_team", ""),
            "he": he_summary.get("match_away_team", ""),
        },
        "side": "away",
        "players": [],
    }

    normalized["teams"] = [home_team, away_team]

    # Normalize player data from starting lineups
    en_starting = en_data.get("starting_lineups", {})
    he_starting = he_data.get("starting_lineups", {})
    
    for team_key_en in en_starting.keys():
        # Find corresponding Hebrew team key
        team_key_he = None
        for he_key in he_starting.keys():
            if _teams_match(team_key_en, he_key, en_summary, he_summary):
                team_key_he = he_key
                break

        if not team_key_he:
            continue

        # Determine team side
        team_side = (
            "home" if team_key_en == en_summary.get("match_home_team") else "away"
        )

        # Get players for this team
        en_players = en_starting[team_key_en]
        he_players = he_starting[team_key_he]

        # Process each player by jersey number
        for jersey_num in en_players.keys():
            if jersey_num not in he_players:
                continue

            en_player = en_players[jersey_num]
            he_player = he_players[jersey_num]

            # Extract goals with video times
            en_goals = en_player.get("goals", [])
            he_video_goals = he_player.get("video_goal", [])
            goals_list = []
            for idx, goal_minute in enumerate(en_goals):
                video_time = (
                    he_video_goals[idx] if idx < len(he_video_goals) else None
                )
                goals_list.append(
                    {"minute": str(goal_minute), "video_time": video_time}
                )

            # Extract player data
            player_data = {
                "jersey_number": int(jersey_num),
                "team_side": team_side,
                "name": {
                    "en": en_player.get("name", ""),
                    "he": he_player.get("name", ""),
                },
                "role": {
                    "en": en_player.get("role", ""),
                    "he": he_player.get("role", ""),
                },
                "goals": goals_list,
                "cards": en_player.get("cards", []),  # Now a list of card events
                "sub_off_minutes": en_player.get("sub_off_minutes", []),  # Now a list
                "source": "starting_lineups",
            }

            normalized["players"].append(player_data)

    # Normalize player data from replacements (now a list)
    en_replacements = en_data.get("replacements", {})
    he_replacements = he_data.get("replacements", {})
    
    for team_key_en in en_replacements.keys():
        # Find corresponding Hebrew team key
        team_key_he = None
        for he_key in he_replacements.keys():
            if _teams_match(team_key_en, he_key, en_summary, he_summary):
                team_key_he = he_key
                break

        if not team_key_he:
            continue

        # Determine team side
        team_side = (
            "home" if team_key_en == en_summary.get("match_home_team") else "away"
        )

        # Get players for this team (now lists)
        en_players_list = en_replacements[team_key_en]
        he_players_list = he_replacements[team_key_he]

        # Process each replacement player
        for en_player in en_players_list:
            jersey_num = en_player.get("jersey_number")
            
            # Find corresponding Hebrew player by jersey number
            he_player = None
            for hp in he_players_list:
                if hp.get("jersey_number") == jersey_num:
                    he_player = hp
                    break
            
            if not he_player:
                he_player = {"name": "", "role": "", "goals": [], "replacer_minutes": []}

            # Extract goals with video times
            en_goals = en_player.get("goals", [])
            goals_list = []
            for goal_minute in en_goals:
                goals_list.append(
                    {"minute": str(goal_minute), "video_time": None}
                )

            # Extract player data
            player_data = {
                "jersey_number": int(jersey_num),
                "team_side": team_side,
                "name": {
                    "en": en_player.get("name", ""),
                    "he": he_player.get("name", ""),
                },
                "role": {
                    "en": en_player.get("role", ""),
                    "he": he_player.get("role", ""),
                },
                "goals": goals_list,
                "cards": [],  # Replacements typically don't have cards in the sheet
                "replacer_minutes": en_player.get("replacer_minutes", []),  # List of minutes
                "source": "replacements",
            }

            normalized["players"].append(player_data)
    
    # Normalize bench players (simple, no sub/goal info typically)
    en_bench = en_data.get("bench", {})
    he_bench = he_data.get("bench", {})
    
    for team_key_en in en_bench.keys():
        # Find corresponding Hebrew team key
        team_key_he = None
        for he_key in he_bench.keys():
            if _teams_match(team_key_en, he_key, en_summary, he_summary):
                team_key_he = he_key
                break

        if not team_key_he:
            continue

        # Determine team side
        team_side = (
            "home" if team_key_en == en_summary.get("match_home_team") else "away"
        )

        # Get players for this team
        en_players = en_bench[team_key_en]
        he_players = he_bench[team_key_he]

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
                    "he": he_player.get("name", ""),
                },
                "role": {
                    "en": "",
                    "he": "",
                },
                "goals": [],
                "cards": [],
                "source": "bench",
            }

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


def _create_goal_highlight(
    session, trace_player, player_data, goal, aggregation_service
):
    """Create a highlight for a goal event."""
    minute = goal["minute"]
    video_time = goal.get("video_time")

    # Create unique highlight ID
    highlight_id = f"excel-goal-{session.session_id}-{minute}-{trace_player.id}"

    # Check if highlight already exists
    if TraceHighlight.objects.filter(highlight_id=highlight_id).exists():
        logger.info(f"Highlight {highlight_id} already exists, skipping")
        return None, 0

    # Calculate start_offset from video_time if available
    start_offset = 0
    if video_time:
        try:
            # Parse video_time (format: MM:SS or HH:MM:SS)
            video_seconds = parse_time_to_seconds(video_time)
            if video_seconds is not None:
                start_offset = video_seconds * 1000  # Convert to milliseconds
        except Exception as e:
            logger.warning(
                f"Failed to parse video_time '{video_time}' for goal at {minute}': {e}"
            )

    # If video_time not available, try to calculate from match_time
    if start_offset == 0 and session.match_start_time:
        try:
            minute_int = int(str(minute).replace("'", "").replace("min", "").strip())
            start_offset = convert_game_time_to_video_milliseconds(
                session, minute_int, 0
            )
        except Exception as e:
            logger.warning(f"Failed to calculate start_offset from match_time: {e}")

    # Create event metadata
    event_metadata = {
        "scorer": player_data["name"]["en"] or player_data["name"]["he"],
        "scorer_name": player_data["name"],
        "minute": minute,
        "video_time": video_time,
        "team": player_data["team_side"],
        "jersey_number": player_data["jersey_number"],
    }

    # Determine half from minute
    try:
        minute_int = int(str(minute).replace("'", "").replace("min", "").strip())
        half = 1 if minute_int <= 45 else 2
    except (ValueError, TypeError):
        half = 1  # Default to first half

    # Create TraceHighlight
    highlight = TraceHighlight.objects.create(
        highlight_id=highlight_id,
        video_id=0,
        start_offset=start_offset,
        duration=15000,  # 15 seconds for goals
        tags=[player_data["team_side"], "goal", minute],
        video_stream=session.video_url,
        event_type="goal",
        source="excel_import",
        match_time=f"{minute}:00",
        video_time=video_time,
        half=half,
        event_metadata=event_metadata,
        session=session,
        player=trace_player,
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
            highlight=highlight, trace_object=trace_object, player=trace_player
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
        "jersey_number": player_data["jersey_number"],
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
        player=trace_player,
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
            highlight=highlight, trace_object=trace_object, player=trace_player
        )

    # Create TraceClipReel entries
    clip_reels_count = _create_clip_reels_for_highlight(
        highlight, session, trace_player, player_data["team_side"], aggregation_service
    )

    logger.info(
        f"Created card highlight {highlight_id} for {player_data['name']['en']}"
    )

    return highlight, clip_reels_count


def update_player_language_metadata(session, normalized_data, generate_tokens=False):
    """
    Update TracePlayer language_metadata with multilingual names and roles.
    Optionally generates account creation tokens for unmapped players.

    Args:
        session: TraceSession instance
        normalized_data: Normalized multilingual data
        generate_tokens: If True, generate account_creation_token for players without one

    Returns:
        dict: Update statistics including tokens_generated and created_count
    """
    updated_count = 0
    created_count = 0
    update_details = []

    players_list = normalized_data.get("players", [])
    logger.info(f"Processing {len(players_list)} players from normalized data")
    
    if not players_list:
        logger.warning("No players found in normalized_data['players'] - check normalize_multilingual_data function")
        return {
            "updated_count": 0,
            "created_count": 0,
            "tokens_generated": 0,
            "total_players": 0,
            "update_details": [],
        }

    for player_data in players_list:
        logger.info(f"Processing player {player_data}")
        try:
            # Find TracePlayer by team and jersey number
            team = (
                session.home_team
                if player_data["team_side"] == "home"
                else session.away_team
            )
            jersey_number = player_data["jersey_number"]

            if not team:
                logger.warning(
                    f"No team found for side {player_data['team_side']} in session {session.id}"
                )
                continue

            # Find TracePlayer by team and jersey_number (across all sessions)
            trace_player = TracePlayer.objects.filter(
                team=team, jersey_number=jersey_number
            ).first()

            if trace_player:
                # Update existing player
                # Update language_metadata
                if not trace_player.language_metadata:
                    trace_player.language_metadata = {}

                # Update English data
                if player_data["name"]["en"]:
                    if "en" not in trace_player.language_metadata:
                        trace_player.language_metadata["en"] = {}
                    trace_player.language_metadata["en"]["name"] = player_data["name"][
                        "en"
                    ]
                    if player_data["role"]["en"]:
                        trace_player.language_metadata["en"]["role"] = player_data[
                            "role"
                        ]["en"]

                # Update Hebrew data
                if player_data["name"]["he"]:
                    if "he" not in trace_player.language_metadata:
                        trace_player.language_metadata["he"] = {}
                    trace_player.language_metadata["he"]["name"] = player_data["name"][
                        "he"
                    ]
                    if player_data["role"]["he"]:
                        trace_player.language_metadata["he"]["role"] = player_data[
                            "role"
                        ]["he"]

                # Update primary name field (use English if available, else Hebrew)
                if player_data["name"]["en"]:
                    trace_player.name = player_data["name"]["en"]
                elif player_data["name"]["he"]:
                    trace_player.name = player_data["name"]["he"]

                # Update position if role is provided
                if player_data["role"]["en"] or player_data["role"]["he"]:
                    position = player_data["role"]["en"] or player_data["role"]["he"]
                    trace_player.position = position

                trace_player.save()

                # Add session to player's sessions if not already present
                if session not in trace_player.sessions.all():
                    trace_player.sessions.add(session)

                updated_count += 1

                update_details.append(
                    {
                        "jersey_number": jersey_number,
                        "team_side": player_data["team_side"],
                        "name_en": player_data["name"]["en"],
                        "name_he": player_data["name"]["he"],
                        "player_id": trace_player.id,
                    }
                )

                logger.info(
                    f"Updated player #{jersey_number} ({player_data['team_side']}): "
                    f"EN={player_data['name']['en']}, HE={player_data['name']['he']}"
                )
            else:
                # Create new TracePlayer if not found
                object_id = f"{player_data['team_side']}_{jersey_number}"

                # Determine primary name (use English if available, else Hebrew)
                primary_name = (
                    player_data["name"]["en"]
                    or player_data["name"]["he"]
                    or f"Player {jersey_number}"
                )

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
                position = (
                    player_data["role"]["en"] or player_data["role"]["he"] or "Unknown"
                )

                # Create the new TracePlayer
                trace_player = TracePlayer.objects.create(
                    object_id=object_id,
                    name=primary_name,
                    jersey_number=jersey_number,
                    position=position,
                    team=team,
                    user=None,  # No user mapping - token-based flow only
                    language_metadata=language_metadata,
                )

                # Add session to player's sessions
                trace_player.sessions.add(session)

                created_count += 1

                update_details.append(
                    {
                        "jersey_number": jersey_number,
                        "team_side": player_data["team_side"],
                        "name_en": player_data["name"]["en"],
                        "name_he": player_data["name"]["he"],
                        "created": True,
                        "player_id": trace_player.id,
                    }
                )

                logger.info(
                    f"Created new player #{jersey_number} ({player_data['team_side']}): "
                    f"EN={player_data['name']['en']}, HE={player_data['name']['he']}"
                )

            # Check for existing WajoUser and map/create if needed
            # Use team + jersey_number as the primary identifier (not name, to avoid duplicates)
            if not trace_player.user:
                existing_user = WajoUser.objects.filter(
                    team=team, jersey_number=jersey_number, role="Player"
                ).first()
                
                if existing_user:
                    trace_player.user = existing_user
                    trace_player.save(update_fields=["user"])
                    logger.debug(
                        f"Mapped existing WajoUser {existing_user.id} to TracePlayer #{jersey_number}"
                    )
                else:
                    # Create new WajoUser
                    user_data = {
                        "name": {
                            "en": player_data.get("name", {}).get("en", ""),
                            "he": player_data.get("name", {}).get("he", ""),
                        },
                        "role": {
                            "en": player_data.get("role", {}).get("en", ""),
                            "he": player_data.get("role", {}).get("he", ""),
                        },
                    }
                    try:
                        new_user = create_wajo_user(
                            team=team,
                            jersey_number=jersey_number,
                            user_data=user_data,
                            user_role="Player"
                        )
                        trace_player.user = new_user
                        trace_player.save(update_fields=["user"])
                        logger.debug(
                            f"Created new WajoUser {new_user.id} and mapped to TracePlayer #{jersey_number}"
                        )
                    except Exception as e:
                        logger.error(
                            f"Failed to create WajoUser for player #{jersey_number}: {e}",
                            exc_info=True
                        )
            
        except Exception as e:
            logger.error(f"Error updating player {player_data}: {e}", exc_info=True)
            continue

    return {
        "updated_count": updated_count,
        "created_count": created_count,
        "total_players": len(normalized_data["players"]),
        "update_details": update_details,
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
            team = (
                session.home_team
                if player_data["team_side"] == "home"
                else session.away_team
            )
            jersey_number = player_data["jersey_number"]

            # Find TracePlayer by team and jersey_number (across all sessions)
            trace_player = TracePlayer.objects.filter(
                team=team, jersey_number=jersey_number
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
        "errors": errors,
    }


def _create_clip_reels_for_highlight(
    highlight, session, trace_player, team_side, aggregation_service
):
    """
    Create 6 TraceClipReel entries for a highlight (3 tag combinations × 2 ratios).
    Similar to the logic in TraceVisionAggregationService._compute_clips.
    Uses video_time from highlight if available, with 40-second buffer before and after.
    """
    clip_reels_created = 0

    # Get involved players
    highlight_objects = highlight.highlight_objects.all().select_related(
        "trace_object", "player"
    )
    involved_players = [ho.player for ho in highlight_objects if ho.player]
    if not involved_players and trace_player:
        involved_players = [trace_player]

    primary_player = involved_players[0] if involved_players else None

    # Determine event type from highlight
    event_type = highlight.event_type or "touch"

    # Calculate start_ms and duration_ms based on video_time if available
    # Use highlight.start_offset (which was calculated from video_time in _create_goal_highlight)
    start_ms = highlight.start_offset
    duration_ms = highlight.duration

    # If video_time is available, recalculate with buffer for clip reels
    if highlight.video_time and highlight.video_time.strip():
        try:
            # Use the same parse_time_to_seconds function for consistency
            video_seconds = parse_time_to_seconds(highlight.video_time)
            if video_seconds is not None and video_seconds > 0:
                video_time_ms = video_seconds * 1000
                # Start 30 seconds before the goal
                buffer_before_ms = 30000
                start_ms = max(0, video_time_ms - buffer_before_ms)  # Ensure non-negative

                # Duration: 30s before + 40s after = 70s total, capped at 80s (1m 20s)
                duration_after_ms = 40000
                max_duration_ms = 80000  # 1 minute 20 seconds
                duration_ms = buffer_before_ms + duration_after_ms

                logger.debug(
                    f"Using video_time {highlight.video_time} for clip reel: "
                    f"start_ms={start_ms}, duration_ms={duration_ms}"
                )
            else:
                # If parsing failed, use highlight.start_offset (which may have been calculated from match_time)
                logger.debug(
                    f"Using highlight.start_offset {highlight.start_offset}ms for clip reel "
                    f"(video_time parsing returned None or 0)"
                )
        except Exception as e:
            logger.warning(f"Failed to parse video_time '{highlight.video_time}' for clip reel: {e}")
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
        # start_ms: 30 seconds before the goal time
        # duration_ms: 70 seconds total (30s before + 40s after the goal)
        # end_ms: start_ms + duration_ms (40 seconds after the goal time)
        end_ms = start_ms + duration_ms
        defaults = {
            "session": session,
            "event_id": highlight.highlight_id,
            "event_type": event_type,
            "side": team_side,
            "start_ms": start_ms,
            "duration_ms": duration_ms,
            "start_clock": aggregation_service._ms_to_clock(start_ms),
            "end_clock": aggregation_service._ms_to_clock(end_ms),
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
    if (
        value is None
        or value == ""
        or value == "—"
        or (isinstance(value, float) and math.isnan(value))
    ):
        return []

    if isinstance(value, list):
        # If value is already a list, filter out empty/"—" and non-numeric values, and return cleaned list as strings
        return [
            str(g).strip()
            for g in value
            if g
            and str(g).strip()
            and str(g).strip() != "—"
            and re.match(r"^\d+$", str(g).strip())
        ]

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
        timestr = re.sub(r"[^\d:]", "", timestr).strip()
        if not timestr:
            return None

        # Find all numbers/groups as separated by colons
        segments = timestr.split(":")

        # Case 1: Only a number ("13" => "13:00")
        if len(segments) == 1 and re.match(r"^\d+$", segments[0]):
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
    if (
        value is None
        or value == ""
        or value == "—"
        or (isinstance(value, float) and math.isnan(value))
    ):
        return []

    # If value is a list, flatten and process elements as str
    if isinstance(value, list):
        items = value
    else:
        # If a string, split on comma (for typical user entry)
        items = [
            s.strip() for s in str(value).split(",") if s.strip() and s.strip() != "—"
        ]

    result = []
    for item in items:
        cleaned = clean_and_normalize_time(item)
        if cleaned:
            result.append(cleaned)
    return result


def parse_sub_off_minute(value):
    """
    Parse substitution off minute value.
    Returns list of minutes if multiple substitutions, or empty list if no substitution.
    
    Args:
        value: SubOffMinute value like "54" or "24, 69" or "—"
    
    Returns:
        list: List of minutes [54] or [24, 69] or []
    """
    if (
        value is None
        or value == ""
        or value == "—"
        or (isinstance(value, float) and math.isnan(value))
    ):
        return []

    if isinstance(value, (int, float)):
        return [int(value)]

    if isinstance(value, str):
        value = value.strip()
        if value == "" or value == "—":
            return []
        # Extract all numbers (comma-separated for multiple subs)
        numbers = re.findall(r"\d+", value)
        return [int(num) for num in numbers] if numbers else []

    return []


def parse_cards_value(value):
    """
    Parse cards value and return list of card events with type and minute.
    
    Args:
        value: Card value like "Yellow 41'" or "Red 27'" or "Yellow 41', Yellow 62'"
    
    Returns:
        list: List of card events [{"type": "yellow", "minute": 41}, ...]
    """
    if (
        value is None
        or value == ""
        or value == "—"
        or (isinstance(value, float) and math.isnan(value))
    ):
        return []

    if isinstance(value, str):
        value = value.strip()
        if value == "" or value == "—":
            return []
        
        cards = []
        # Split by comma for multiple cards
        card_parts = [part.strip() for part in value.split(",")]
        
        for card_part in card_parts:
            # Parse "Yellow 41'" or "Red 27'" format
            # Also support Hebrew: "כרטיס צהוב 41'" or "כרטיס אדום 27'"
            card_type = None
            minute = None
            
            # Extract card type (case insensitive)
            if "yellow" in card_part.lower() or "צהוב" in card_part:
                card_type = "yellow"
            elif "red" in card_part.lower() or "אדום" in card_part:
                card_type = "red"
            
            # Extract minute (find first number)
            minute_match = re.search(r"(\d+)", card_part)
            if minute_match:
                minute = int(minute_match.group(1))
            
            if card_type and minute:
                cards.append({"type": card_type, "minute": minute})
            elif card_type:
                # Card without minute - use 0 as placeholder
                cards.append({"type": card_type, "minute": 0})
        
        return cards

    return []


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
                "referees": [],
            },
            "he": {
                "Match_summary": {},
                "starting_lineups": {},
                "replacements": {},
                "bench": {},
                "coaches": {},
                "referees": [],
            },
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
                    "match_half_time_score": str(
                        safe_get(summary_dict, "Half-Time Score", "")
                    ),
                    "match_full_time_score": str(
                        safe_get(summary_dict, "Full-Time Score", "")
                    ),
                    "match_home_goals": safe_int(summary_dict, "Home Goals", 0),
                    "match_away_goals": safe_int(summary_dict, "Away Goals", 0),
                    "match_age_group": str(safe_get(summary_dict, "Age Group", "")),
                    "match_game_format": str(safe_get(summary_dict, "Game Format", "")),
                    "match_field_length": str(
                        safe_get(summary_dict, "Field Length (m)", "")
                    ),
                    "match_field_width": str(
                        safe_get(summary_dict, "Field Width (m)", "")
                    ),
                    "match_goal_size": str(safe_get(summary_dict, "Goal Size (m)", "")),
                    "match_ball_size": str(safe_get(summary_dict, "Ball Size", "")),
                    "match_half_length": str(
                        safe_get(summary_dict, "Half Length (Minutes)", "")
                    ),
                    "match_official_break_time": str(
                        safe_get(summary_dict, "Official Break Time", "")
                    ),
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
                    "match_venue": str(
                        safe_get(summary_dict, "תחרות", "")
                    ),  # No trailing space
                    "match_home_team": str(safe_get(summary_dict, "קבוצה ביתית", "")),
                    "match_away_team": str(safe_get(summary_dict, "קבוצה אורחת", "")),
                    "match_half_time_score": str(
                        safe_get(summary_dict, "תוצאת מחצית", "")
                    ),
                    "match_full_time_score": str(
                        safe_get(summary_dict, "תוצאת סיום", "")
                    ),
                    "match_home_goals": safe_int(summary_dict, "שערי בית", 0),
                    "match_away_goals": safe_int(summary_dict, "שערי חוץ", 0),
                    "match_age_group": str(safe_get(summary_dict, "קבוצת גיל", "")),
                    "match_game_format": str(safe_get(summary_dict, "פורמט משחק", "")),
                    "match_field_length": str(
                        safe_get(summary_dict, "אורך מגרש (מ')", "")
                    ),
                    "match_field_width": str(
                        safe_get(summary_dict, "רוחב מגרש (מ')", "")
                    ),
                    "match_goal_size": str(safe_get(summary_dict, "גודל שער (מ')", "")),
                    "match_ball_size": str(safe_get(summary_dict, "גודל כדור", "")),
                    "match_half_length": str(
                        safe_get(summary_dict, "אורך מחצית (דקות)", "")
                    ),
                    "match_official_break_time": str(
                        safe_get(summary_dict, "הפסקה רשמית (דקות)", "")
                    ),
                }

        # ===== Parse Starting_Lineups_en =====
        if "Starting_Lineups_en" in excel_data:
            lineups_df = excel_data["Starting_Lineups_en"]
            lineups_df = lineups_df.where(pd.notna(lineups_df), None)

            # Log column names for debugging
            logger.debug(f"Starting_Lineups_en columns: {list(lineups_df.columns)}")
            
            # Check if Cards column exists
            has_cards_column = any(col in lineups_df.columns for col in ["Cards", "cards", "CARDS"])
            if not has_cards_column:
                logger.info("Starting_Lineups_en: 'Cards' column not found, will use empty cards list for all players")

            # Group by team
            for _, row in lineups_df.iterrows():
                # Try multiple possible column name variations
                team = row.get("Team") or row.get("team") or row.get("TEAM")
                number = (
                    row.get("Number")
                    or row.get("number")
                    or row.get("NUMBER")
                    or row.get("No.")
                    or row.get("No")
                )
                name = (
                    row.get("Name")
                    or row.get("name")
                    or row.get("NAME")
                    or row.get("Player Name")
                )

                # Skip invalid rows
                if (
                    not team
                    or pd.isna(team)
                    or (isinstance(team, str) and team.strip() in ["", "no.", "Team"])
                ):
                    continue
                if not number or pd.isna(number):
                    continue
                if (
                    not name
                    or pd.isna(name)
                    or (
                        isinstance(name, str)
                        and name.strip()
                        in ["", "GOALS TABLE", "CARD TABLE", "name", "Name", "NAME"]
                    )
                ):
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
                role = (
                    row.get("Role")
                    or row.get("role")
                    or row.get("ROLE")
                    or row.get("Position")
                )
                if pd.isna(role) or role is None:
                    role = "—"
                else:
                    role = str(role).strip()

                goals = parse_goals_value(
                    row.get("Goals") or row.get("goals") or row.get("GOALS")
                )
                video_goal = parse_video_goal_value(
                    row.get("VideoGoal")
                    or row.get("video_goal")
                    or row.get("Video Goal")
                )
                sub_off_minutes = parse_sub_off_minute(
                    row.get("SubOffMinute")
                    or row.get("sub_off_minute")
                    or row.get("Sub Off Minute")
                )
                
                # Parse cards - handle missing column gracefully
                if has_cards_column:
                    cards_value = row.get("Cards") or row.get("cards") or row.get("CARDS")
                    cards = parse_cards_value(cards_value)
                else:
                    cards = []  # Empty list if column not present

                result["en"]["starting_lineups"][team][number] = {
                    "name": name,
                    "role": role,
                    "goals": goals,
                    "video_goal": video_goal,
                    "sub_off_minutes": sub_off_minutes,
                    "cards": cards,
                }

        # ===== Parse Starting_Lineups_he =====
        if "Starting_Lineups_he" in excel_data:
            lineups_df = excel_data["Starting_Lineups_he"]
            lineups_df = lineups_df.where(pd.notna(lineups_df), None)

            # Log column names for debugging
            logger.debug(f"Starting_Lineups_he columns: {list(lineups_df.columns)}")
            
            # Check if Cards column exists (Hebrew versions)
            has_cards_column_he = any(col in lineups_df.columns for col in ["כרטיסים", "כרטיס", "Cards", "cards"])
            if not has_cards_column_he:
                logger.info("Starting_Lineups_he: 'Cards' (כרטיסים) column not found, will use empty cards list for all players")

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
                name = get_hebrew_column(
                    row, ["שם שחקן", "שם", "שם השחקן"]
                )  # Player Name

                # Skip invalid rows
                if not team or (
                    isinstance(team, str) and team.strip() in ["", "no.", "קבוצה"]
                ):
                    continue
                if not number:
                    continue
                if not name or (
                    isinstance(name, str)
                    and name.strip() in ["", "GOALS TABLE", "CARD TABLE", "שם שחקן"]
                ):
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
                video_goal = parse_video_goal_value(
                    get_hebrew_column(row, ["שער_וידאו", "שער וידאו", "וידאו שער"])
                )
                sub_off_minutes = parse_sub_off_minute(
                    get_hebrew_column(row, ["דקה יציאה", "דקת יציאה", "יציאה"])
                )
                
                # Parse cards - handle missing column gracefully
                if has_cards_column_he:
                    cards_value = get_hebrew_column(row, ["כרטיסים", "כרטיס", "Cards", "cards"])
                    cards = parse_cards_value(cards_value)
                else:
                    cards = []  # Empty list if column not present

                # Use English keys for player data structure (consistent with example)
                result["he"]["starting_lineups"][team][number] = {
                    "name": name,
                    "role": role,
                    "goals": goals,
                    "video_goal": video_goal,
                    "sub_off_minutes": sub_off_minutes,
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

                if (
                    not team
                    or pd.isna(team)
                    or (isinstance(team, str) and team.strip() in ["", "Team"])
                ):
                    continue
                if not number or pd.isna(number):
                    continue
                if (
                    not name
                    or pd.isna(name)
                    or (isinstance(name, str) and name.strip() in ["", "Name"])
                ):
                    continue

                team = str(team).strip()
                try:
                    number = str(int(float(number)))
                except (ValueError, TypeError):
                    continue
                name = str(name).strip()

                if team not in result["en"]["replacements"]:
                    result["en"]["replacements"][team] = []

                role = row.get("Role", "—")
                if pd.isna(role) or role is None:
                    role = "—"
                else:
                    role = str(role).strip()

                goals = parse_goals_value(row.get("Goals"))
                replacer_minutes = parse_sub_off_minute(row.get("ReplacerMinute"))

                result["en"]["replacements"][team].append({
                    "jersey_number": number,
                    "name": name,
                    "role": role,
                    "goals": goals,
                    "replacer_minutes": replacer_minutes,
                })

        # ===== Parse Replacements_he =====
        if "Replacements_he" in excel_data:
            replacements_df = excel_data["Replacements_he"]
            replacements_df = replacements_df.where(pd.notna(replacements_df), None)

            for _, row in replacements_df.iterrows():
                team = get_hebrew_column(row, ["קבוצה", "קבוצה "])
                number = get_hebrew_column(row, ["מס'", "מספר", "מס"])
                name = get_hebrew_column(row, ["שם", "שם שחקן"])

                if not team or (
                    isinstance(team, str) and team.strip() in ["", "קבוצה"]
                ):
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
                    result["he"]["replacements"][team] = []

                role = get_hebrew_column(row, ["תפקיד", "תַפְקִיד"])
                if role is None or pd.isna(role):
                    role = "—"
                else:
                    role = str(role).strip()  # Hebrew role

                goals = parse_goals_value(get_hebrew_column(row, ["מטרות", "שערים"]))
                replacer_minutes = parse_sub_off_minute(
                    get_hebrew_column(row, ["דקת כניסה", "דקה כניסה"])
                )

                # Use English keys, Hebrew values
                result["he"]["replacements"][team].append({
                    "jersey_number": number,
                    "name": name,  # Hebrew name
                    "role": role,  # Hebrew role
                    "goals": goals,
                    "replacer_minutes": replacer_minutes,
                })

        # ===== Parse Bench_en =====
        if "Bench_en" in excel_data:
            bench_df = excel_data["Bench_en"]
            bench_df = bench_df.where(pd.notna(bench_df), None)

            for _, row in bench_df.iterrows():
                team = row.get("Team")
                number = row.get("Number")
                name = row.get("Name")

                if (
                    not team
                    or pd.isna(team)
                    or (isinstance(team, str) and team.strip() in ["", "Team"])
                ):
                    continue
                if not number or pd.isna(number):
                    continue
                if (
                    not name
                    or pd.isna(name)
                    or (isinstance(name, str) and name.strip() in ["", "Name"])
                ):
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

                if not team or (
                    isinstance(team, str) and team.strip() in ["", "קבוצה"]
                ):
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

                if (
                    not team
                    or pd.isna(team)
                    or (isinstance(team, str) and team.strip() in ["", "Team"])
                ):
                    continue
                if not coach_name or pd.isna(coach_name):
                    continue

                team = str(team).strip()
                coach_name = str(coach_name).strip()
                role = str(role).strip() if role and not pd.isna(role) else ""

                if team not in result["en"]["coaches"]:
                    result["en"]["coaches"][team] = []

                result["en"]["coaches"][team].append(
                    {
                        "name": coach_name,
                        "role": role,
                    }
                )

        # ===== Parse Coaches_he =====
        if "Coaches_he" in excel_data:
            coaches_df = excel_data["Coaches_he"]
            coaches_df = coaches_df.where(pd.notna(coaches_df), None)

            for _, row in coaches_df.iterrows():
                team = get_hebrew_column(row, ["קבוצה", "קבוצה "])
                coach_name = get_hebrew_column(row, ["שם המאמן", "מאמן"])
                role = get_hebrew_column(row, ["תפקיד"])

                if not team or (
                    isinstance(team, str) and team.strip() in ["", "קבוצה"]
                ):
                    continue
                if not coach_name:
                    continue

                team = str(team).strip()  # Hebrew team name
                coach_name = str(coach_name).strip()  # Hebrew coach name
                role = (
                    str(role).strip() if role and not pd.isna(role) else ""
                )  # Hebrew role

                if team not in result["he"]["coaches"]:
                    result["he"]["coaches"][team] = []

                # Use English keys, Hebrew values
                result["he"]["coaches"][team].append(
                    {
                        "name": coach_name,  # Hebrew name
                        "role": role,  # Hebrew role
                    }
                )

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

                result["en"]["referees"].append(
                    {
                        "position": position,
                        "name": name,
                    }
                )

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
                result["he"]["referees"].append(
                    {
                        "position": position,  # Hebrew position
                        "name": name,  # Hebrew name
                    }
                )

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
            # excel_dir = os.path.dirname(excel_file_path)
            # excel_basename = os.path.basename(excel_file_path)
            # json_filename = os.path.splitext(excel_basename)[0] + "_multilingual.json"

            # Save in the same directory as Excel file (data directory)
            # json_file_path = os.path.join(excel_dir, json_filename)

            # with open(json_file_path, "w", encoding="utf-8") as f:
            #     json.dump(result, f, indent=4, ensure_ascii=False)

            # logger.info(f"Multilingual match data saved to JSON file: {json_file_path}")
            # print(f"\n✓ Multilingual JSON file saved successfully at: {json_file_path}")
            # print(f"  File size: {os.path.getsize(json_file_path)} bytes")

            # Print summary of what was extracted
            en_teams = len(result.get("en", {}).get("starting_lineups", {}))
            he_teams = len(result.get("he", {}).get("starting_lineups", {}))
            en_players = sum(
                len(players)
                for players in result.get("en", {}).get("starting_lineups", {}).values()
            )
            he_players = sum(
                len(players)
                for players in result.get("he", {}).get("starting_lineups", {}).values()
            )
            en_replacements = sum(
                len(players)
                for players in result.get("en", {}).get("replacements", {}).values()
            )
            he_replacements = sum(
                len(players)
                for players in result.get("he", {}).get("replacements", {}).values()
            )
            en_bench = sum(
                len(players)
                for players in result.get("en", {}).get("bench", {}).values()
            )
            he_bench = sum(
                len(players)
                for players in result.get("he", {}).get("bench", {}).values()
            )
            en_coaches = sum(
                len(coaches)
                for coaches in result.get("en", {}).get("coaches", {}).values()
            )
            he_coaches = sum(
                len(coaches)
                for coaches in result.get("he", {}).get("coaches", {}).values()
            )
            en_referees = len(result.get("en", {}).get("referees", []))
            he_referees = len(result.get("he", {}).get("referees", []))

            print(f"\n  Extracted Summary:")
            print(f"    English:")
            print(
                f"      - Match Summary: {'✓' if result.get('en', {}).get('Match_summary') else '✗'}"
            )
            print(f"      - Starting Lineups: {en_teams} teams, {en_players} players")
            print(f"      - Replacements: {en_replacements} players")
            print(f"      - Bench: {en_bench} players")
            print(f"      - Coaches: {en_coaches} coaches")
            print(f"      - Referees: {en_referees} referees")
            print(f"    Hebrew:")
            print(
                f"      - Match Summary: {'✓' if result.get('he', {}).get('Match_summary') else '✗'}"
            )
            print(f"      - Starting Lineups: {he_teams} teams, {he_players} players")
            print(f"      - Replacements: {he_replacements} players")
            print(f"      - Bench: {he_bench} players")
            print(f"      - Coaches: {he_coaches} coaches")
            print(f"      - Referees: {he_referees} referees")

        except Exception as e:
            logger.warning(
                f"Failed to save multilingual data to JSON file: {e}", exc_info=True
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
        existing_session = (
            TraceSession.objects.filter(video_url=video_url)
            .exclude(status="process_error")
            .first()
        )
        if existing_session:
            logger.info(f"Duplicate found by video_url: {video_url}")
            return existing_session

    # Check by (home_team, away_team, match_date)
    if home_team and away_team and match_date:
        existing_session = (
            TraceSession.objects.filter(
                home_team=home_team, away_team=away_team, match_date=match_date
            )
            .exclude(status="process_error")
            .first()
        )
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
        return "home"
    elif (side_lower == "home" and perspective_lower == "away") or (
        side_lower == "away" and perspective_lower == "home"
    ):
        return "away"

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


def generate_game_timeline(normalized_data, session):
    """
    Generate minute-by-minute game timeline with all events (substitutions, goals, cards).
    
    Args:
        normalized_data: Normalized multilingual data from normalize_multilingual_data
        session: TraceSession instance
    
    Returns:
        list: Timeline events sorted by minute, with separate entries for each team
        [
            {
                "minute": 24,
                "event_type": "substitution",
                "event_value": "up",  # or "down", "goal", "yellow", "red"
                "player_name": "Rian GRAYEB",
                "player_jersey_number": 11,
                "player_team_name": "Maccabi Ahi Nazareth",
                "team_side": "away",  # or "home"
                "language": {"en": "...", "he": "..."}  # multilingual data
                "replaced_by": {...}  # (optional) For "down" events, who came on
                "replaced_player": {...}  # (optional) For "up" events, who went off
            },
            ...
        ]
    """
    timeline = []
    
    # Get team names from session
    home_team_name = session.home_team.name if session.home_team else "Home Team"
    away_team_name = session.away_team.name if session.away_team else "Away Team"
    
    # Build player lookup: {team_side: {jersey_number: player_data}}
    players_by_team = {"home": {}, "away": {}}
    
    # Track substitutions by minute and team for pairing
    # Format: {team_side: {minute: {"up": [players], "down": [players]}}}
    substitutions_by_minute = {"home": {}, "away": {}}
    
    for player_data in normalized_data.get("players", []):
        team_side = player_data.get("team_side", "home")
        jersey_number = player_data.get("jersey_number")
        if team_side in players_by_team and jersey_number:
            players_by_team[team_side][jersey_number] = player_data
    
    # Process substitutions from starting lineups (sub off events)
    for player_data in normalized_data.get("players", []):
        if player_data.get("source") != "starting_lineups":
            continue
        
        team_side = player_data.get("team_side", "home")
        team_name = home_team_name if team_side == "home" else away_team_name
        jersey_number = player_data.get("jersey_number")
        sub_off_minutes = player_data.get("sub_off_minutes", [])
        
        for minute in sub_off_minutes:
            if minute > 0:
                timeline.append({
                    "minute": minute,
                    "event_type": "substitution",
                    "event_value": "down",
                    "player_name": player_data.get("name", {}).get("en", ""),
                    "player_jersey_number": jersey_number,
                    "player_team_name": team_name,
                    "team_side": team_side,
                    "language": {
                        "en": player_data.get("name", {}).get("en", ""),
                        "he": player_data.get("name", {}).get("he", "")
                    }
                })
    
    # Process substitutions from replacements (sub in/out events)
    # Important: For replacement players with multiple minutes [24, 69]:
    # - First minute (index 0) = UP (coming on)
    # - Second minute (index 1) = DOWN (going off)
    # - Third minute (index 2) = UP again (coming on)
    # Pattern: even index (0,2,4...) = UP, odd index (1,3,5...) = DOWN
    for player_data in normalized_data.get("players", []):
        if player_data.get("source") != "replacements":
            continue
        
        team_side = player_data.get("team_side", "home")
        team_name = home_team_name if team_side == "home" else away_team_name
        jersey_number = player_data.get("jersey_number")
        replacer_minutes = player_data.get("replacer_minutes", [])
        
        # Process each minute with alternating up/down pattern
        for idx, minute in enumerate(replacer_minutes):
            if minute > 0:
                # Even index (0, 2, 4...) = UP, Odd index (1, 3, 5...) = DOWN
                event_value = "up" if idx % 2 == 0 else "down"
                
                timeline.append({
                    "minute": minute,
                    "event_type": "substitution",
                    "event_value": event_value,
                    "player_name": player_data.get("name", {}).get("en", ""),
                    "player_jersey_number": jersey_number,
                    "player_team_name": team_name,
                    "team_side": team_side,
                    "language": {
                        "en": player_data.get("name", {}).get("en", ""),
                        "he": player_data.get("name", {}).get("he", "")
                    }
                })
    
    # Process goals
    for player_data in normalized_data.get("players", []):
        team_side = player_data.get("team_side", "home")
        team_name = home_team_name if team_side == "home" else away_team_name
        jersey_number = player_data.get("jersey_number")
        goals = player_data.get("goals", [])
        
        for goal in goals:
            try:
                minute_str = str(goal.get("minute", "0")).replace("'", "").replace("min", "").strip()
                minute = int(minute_str) if minute_str.isdigit() else 0
                
                if minute > 0:
                    timeline.append({
                        "minute": minute,
                        "event_type": "goal",
                        "event_value": "goal",
                        "player_name": player_data.get("name", {}).get("en", ""),
                        "player_jersey_number": jersey_number,
                        "player_team_name": team_name,
                        "team_side": team_side,
                        "video_time": goal.get("video_time"),
                        "language": {
                            "en": player_data.get("name", {}).get("en", ""),
                            "he": player_data.get("name", {}).get("he", "")
                        }
                    })
            except (ValueError, TypeError):
                continue
    
    # Process cards
    for player_data in normalized_data.get("players", []):
        team_side = player_data.get("team_side", "home")
        team_name = home_team_name if team_side == "home" else away_team_name
        jersey_number = player_data.get("jersey_number")
        cards = player_data.get("cards", [])
        
        for card in cards:
            minute = card.get("minute", 0)
            card_type = card.get("type", "yellow")
            
            if minute > 0:
                timeline.append({
                    "minute": minute,
                    "event_type": "card",
                    "event_value": card_type,  # "yellow" or "red"
                    "player_name": player_data.get("name", {}).get("en", ""),
                    "player_jersey_number": jersey_number,
                    "player_team_name": team_name,
                    "team_side": team_side,
                    "language": {
                        "en": player_data.get("name", {}).get("en", ""),
                        "he": player_data.get("name", {}).get("he", "")
                    }
                })
    
    # Build substitution pairing: match "up" and "down" events at same minute
    # Group substitutions by minute and team
    for event in timeline:
        if event["event_type"] == "substitution":
            team_side = event["team_side"]
            minute = event["minute"]
            event_value = event["event_value"]
            
            if minute not in substitutions_by_minute[team_side]:
                substitutions_by_minute[team_side][minute] = {"up": [], "down": []}
            
            substitutions_by_minute[team_side][minute][event_value].append(event)
    
    # Pair up and down substitutions at same minute for same team
    # Use a smarter pairing algorithm that considers:
    # 1. Match ups and downs at the same minute
    # 2. Don't pair the same event twice
    # 3. Handle cases where there are more ups than downs or vice versa
    for team_side in ["home", "away"]:
        for minute, subs in substitutions_by_minute[team_side].items():
            ups = subs["up"]
            downs = subs["down"]
            
            # Track which events have been paired
            paired_ups = set()
            paired_downs = set()
            
            # If we have both ups and downs at this minute, try to pair them
            if ups and downs:
                # Simple pairing: match in order (first up with first down, etc.)
                # This works for most common cases
                min_count = min(len(ups), len(downs))
                
                for i in range(min_count):
                    up_event = ups[i]
                    down_event = downs[i]
                    
                    # Check if not already paired
                    up_id = id(up_event)
                    down_id = id(down_event)
                    
                    if up_id not in paired_ups and down_id not in paired_downs:
                        # Add cross-references
                        up_event["replaced_player"] = {
                            "name": down_event["player_name"],
                            "jersey_number": down_event["player_jersey_number"]
                        }
                        down_event["replaced_by"] = {
                            "name": up_event["player_name"],
                            "jersey_number": up_event["player_jersey_number"]
                        }
                        
                        paired_ups.add(up_id)
                        paired_downs.add(down_id)
    
    # Sort timeline by minute, then by team_side (home first, then away), then by event_type
    # Order: substitutions (down first, then up), goals, cards
    def sort_key(event):
        minute = event["minute"]
        team_order = 0 if event["team_side"] == "home" else 1
        
        # Event type order: substitution down, substitution up, goal, card
        if event["event_type"] == "substitution":
            if event["event_value"] == "down":
                event_order = 0
            else:  # up
                event_order = 1
        elif event["event_type"] == "goal":
            event_order = 2
        else:  # card
            event_order = 3
        
        return (minute, team_order, event_order)
    
    timeline.sort(key=sort_key)
    
    logger.info(f"Generated game timeline with {len(timeline)} events")
    
    return timeline


def format_game_timeline_summary(timeline, language="en"):
    """
    Format game timeline into human-readable summary.
    
    Args:
        timeline: Game timeline from generate_game_timeline()
        language: Language for display ("en" or "he")
    
    Returns:
        str: Formatted timeline summary
    """
    if not timeline:
        return "No timeline events available."
    
    summary_lines = ["=== Game Timeline ===\n"]
    
    current_minute = None
    for event in timeline:
        minute = event["minute"]
        
        # Add minute header if changed
        if minute != current_minute:
            summary_lines.append(f"\n--- Minute {minute}' ---")
            current_minute = minute
        
        # Get player name in preferred language
        player_name = event.get("language", {}).get(language, event["player_name"])
        jersey = event["player_jersey_number"]
        team = event["player_team_name"]
        
        # Format based on event type
        if event["event_type"] == "substitution":
            if event["event_value"] == "down":
                if "replaced_by" in event:
                    replaced_by = event["replaced_by"]
                    summary_lines.append(
                        f"  🔻 SUB OFF: #{jersey} {player_name} ({team}) "
                        f"→ Replaced by #{replaced_by['jersey_number']} {replaced_by['name']}"
                    )
                else:
                    summary_lines.append(
                        f"  🔻 SUB OFF: #{jersey} {player_name} ({team})"
                    )
            else:  # up
                if "replaced_player" in event:
                    replaced = event["replaced_player"]
                    summary_lines.append(
                        f"  🔺 SUB ON: #{jersey} {player_name} ({team}) "
                        f"→ Replacing #{replaced['jersey_number']} {replaced['name']}"
                    )
                else:
                    summary_lines.append(
                        f"  🔺 SUB ON: #{jersey} {player_name} ({team})"
                    )
        
        elif event["event_type"] == "goal":
            video_time = event.get("video_time", "")
            video_str = f" [Video: {video_time}]" if video_time else ""
            summary_lines.append(
                f"  ⚽ GOAL: #{jersey} {player_name} ({team}){video_str}"
            )
        
        elif event["event_type"] == "card":
            card_type = event["event_value"].upper()
            card_emoji = "🟨" if event["event_value"] == "yellow" else "🟥"
            summary_lines.append(
                f"  {card_emoji} {card_type} CARD: #{jersey} {player_name} ({team})"
            )
    
    return "\n".join(summary_lines)


def process_excel_and_create_players(session_id):
    """
    Process Excel file from TraceSession and:
    1. Extract multilingual data using extract_multilingual_match_data
    2. Update Game and Team multilingual data using update_trace_session_multilingual_data
    3. Create/update TracePlayer instances (using team + jersey_number)
    4. Create highlights for goals from Excel data (using game_time and video_time)
    5. Calculate and store goal statistics in TraceVisionSessionStats

    Args:
        session_id (int): TraceSession ID

    Returns:
        dict: Result with success status and details
    """
    try:
        from tracevision.models import (
            TraceSession,
            TracePlayer,
            TraceVisionSessionStats,
        )
        from tracevision.tasks import update_trace_session_multilingual_data
        from tracevision.utils import create_highlights_from_normalized_data
        from django.db import transaction

        # Get session
        try:
            # Note: basic_game_stats is a FileField, not a relation, so don't use select_related for it
            session = TraceSession.objects.select_related(
                "home_team", "away_team", "game"
            ).get(id=session_id)
        except TraceSession.DoesNotExist:
            error_msg = f"TraceSession with ID {session_id} not found"
            logger.error(error_msg)
            return {"success": False, "error": error_msg}

        # Check if Excel file exists
        if not session.basic_game_stats:
            error_msg = f"Session {session_id} has no basic_game_stats file"
            logger.warning(error_msg)
            return {"success": False, "error": error_msg}

        # Download Excel file from storage
        logger.info(f"Downloading Excel file for session {session_id}")
        try:
            excel_file_path = download_excel_file_from_storage(
                session.basic_game_stats.url
            )
        except Exception as e:
            error_msg = f"Failed to download Excel file: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {"success": False, "error": error_msg}

        # Step 1: Extract multilingual data using existing method
        try:
            logger.info(f"Extracting multilingual data from Excel file")
            match_data = extract_multilingual_match_data(excel_file_path)
        except Exception as e:
            error_msg = f"Failed to extract multilingual data: {str(e)}"
            logger.error(error_msg, exc_info=True)
            try:
                if os.path.exists(excel_file_path):
                    os.unlink(excel_file_path)
            except Exception as e:
                logger.error(f"Failed to unlink the file due to the: {e}")
                pass
            return {"success": False, "error": error_msg}
        

        # Step 2: Update TraceSession multilingual data (updates Game and Team) using existing method
        try:
            update_trace_session_multilingual_data(match_data, session_id)
            logger.info(f"Updated multilingual data for session {session_id}")
        except Exception as e:
            logger.warning(
                f"Failed to update multilingual data: {str(e)}", exc_info=True
            )

        # Step 3: Process players and create highlights
        players_created = 0
        players_updated = 0
        tokens_generated = 0
        highlights_created = 0

        # Goal statistics
        home_goals = 0
        away_goals = 0
        home_first_half_goals = 0
        home_second_half_goals = 0
        away_first_half_goals = 0
        away_second_half_goals = 0
        player_goals = {}  # {player_id: goal_count}
        game_timeline = []  # Initialize here for proper scope

        try:
            with transaction.atomic():
                # Get normalized player data
                normalized_data = normalize_multilingual_data(match_data)
                
                # Debug: Log normalized data structure
                logger.info(
                    f"Normalized data: {len(normalized_data.get('players', []))} players found"
                )
                if normalized_data.get("players"):
                    logger.debug(
                        f"First few players: {normalized_data['players'][:3]}"
                    )

                # Step 3: Update/create players and generate tokens using existing method
                logger.info(
                    "Updating player language metadata and generating tokens..."
                )
                player_result = update_player_language_metadata(
                    session, normalized_data, generate_tokens=True
                )
                players_created = player_result.get("created_count", 0)
                players_updated = player_result.get("updated_count", 0)
                tokens_generated = player_result.get("tokens_generated", 0)
                logger.info(
                    f"Player processing complete: {players_created} created, {players_updated} updated, "
                    f"{tokens_generated} tokens generated"
                )

                # Step 4: Calculate goal statistics from normalized data
                # Build a mapping of (team_side, jersey_number) -> player_id for goal tracking
                player_id_map = {}  # {(team_side, jersey_number): player_id}
                for detail in player_result.get("update_details", []):
                    player_id = detail.get("player_id")
                    jersey_number = detail.get("jersey_number")
                    team_side = detail.get("team_side")
                    if player_id and jersey_number and team_side:
                        player_id_map[(team_side, jersey_number)] = player_id

                # Calculate goal statistics
                for player_data in normalized_data.get("players", []):
                    try:
                        team_side = player_data.get("team_side", "home")
                        team = (
                            session.home_team
                            if team_side == "home"
                            else session.away_team
                        )
                        jersey_number = player_data.get("jersey_number")

                        if not team or not jersey_number:
                            continue

                        # Get player_id from map
                        player_id = player_id_map.get((team_side, jersey_number))
                        if not player_id:
                            # Fallback: try to find TracePlayer directly (using team + jersey_number, not session)
                            trace_player = TracePlayer.objects.filter(
                                team=team, jersey_number=jersey_number
                            ).first()
                            if trace_player:
                                player_id = trace_player.id
                                # Ensure player is added to this session's M2M relationship
                                if session not in trace_player.sessions.all():
                                    trace_player.sessions.add(session)
                            else:
                                continue

                        # Process goals for this player
                        goals = player_data.get("goals", [])
                        player_goal_count = len(goals)
                        if player_goal_count > 0:
                            player_goals[player_id] = player_goal_count

                            # Count goals by team and half
                            for goal in goals:
                                try:
                                    minute = int(
                                        goal.get("minute", "0")
                                        .replace("'", "")
                                        .replace("min", "")
                                        .strip()
                                    )
                                    if team_side == "home":
                                        home_goals += 1
                                        if minute <= 45:
                                            home_first_half_goals += 1
                                        else:
                                            home_second_half_goals += 1
                                    else:
                                        away_goals += 1
                                        if minute <= 45:
                                            away_first_half_goals += 1
                                        else:
                                            away_second_half_goals += 1
                                except (ValueError, TypeError):
                                    # If minute parsing fails, count as first half
                                    if team_side == "home":
                                        home_goals += 1
                                        home_first_half_goals += 1
                                    else:
                                        away_goals += 1
                                        away_first_half_goals += 1

                    except Exception as e:
                        logger.error(
                            f"Error calculating goal statistics for player {player_data}: {str(e)}",
                            exc_info=True,
                        )
                        continue

                # Step 5: Process coaches and referees from match_data
                coaches_created = 0
                referees_created = 0
                
                try:
                    from games.models import Game
                    
                    en_data = match_data.get("en", {})
                    he_data = match_data.get("he", {})
                    
                    # Helper function to match team by name
                    def find_team_by_name(team_name):
                        """Find team by matching name in English or Hebrew."""
                        if not team_name:
                            return None
                        team_name = team_name.strip()
                        
                        # Check direct name match
                        if team_name == session.home_team.name:
                            return session.home_team
                        if team_name == session.away_team.name:
                            return session.away_team
                        
                        # Check language_metadata
                        for team in [session.home_team, session.away_team]:
                            if team.language_metadata:
                                en_name = team.language_metadata.get("en", {}).get("name", "").strip()
                                he_name = team.language_metadata.get("he", {}).get("name", "").strip()
                                if team_name == en_name or team_name == he_name:
                                    return team
                        return None
                    
                    # Process coaches
                    en_coaches = en_data.get("coaches", {})
                    he_coaches = he_data.get("coaches", {})
                    
                    for team_name_en, coaches_list_en in en_coaches.items():
                        team = find_team_by_name(team_name_en)
                        if not team:
                            # Try Hebrew team names
                            for he_team_name in he_coaches.keys():
                                team = find_team_by_name(he_team_name)
                                if team:
                                    break
                        
                        if not team:
                            logger.warning(f"Could not find team for coach team name: {team_name_en}")
                            continue
                        
                        # Get corresponding Hebrew coaches list
                        coaches_list_he = []
                        for he_team_name, coaches_list_he_candidate in he_coaches.items():
                            if find_team_by_name(he_team_name) == team:
                                coaches_list_he = coaches_list_he_candidate
                                break
                        if not coaches_list_he and team_name_en in he_coaches:
                            coaches_list_he = he_coaches[team_name_en]
                        
                        # Process each coach
                        for idx, coach_en in enumerate(coaches_list_en):
                            coach_he = coaches_list_he[idx] if idx < len(coaches_list_he) else {}
                            coach_name_en = coach_en.get("name", "").strip()
                            coach_name_he = coach_he.get("name", "").strip() if coach_he else ""
                            
                            if not coach_name_en and not coach_name_he:
                                continue
                            
                            # Check if coach already exists (by name, regardless of team)
                            existing_coach = WajoUser.objects.filter(role="Coach").filter(
                                Q(name=coach_name_en) | Q(name=coach_name_he) |
                                Q(language_metadata__en__name=coach_name_en) |
                                Q(language_metadata__he__name=coach_name_he)
                            ).first() if (coach_name_en or coach_name_he) else None
                            
                            if not existing_coach:
                                # Create new coach
                                user_data = {
                                    "name": {"en": coach_name_en, "he": coach_name_he},
                                    "role": {"en": coach_en.get("role", "Coach"), "he": coach_he.get("role", "מאמן") if coach_he else ""},
                                }
                                try:
                                    new_coach = create_wajo_user(team=team, jersey_number=None, user_data=user_data, user_role="Coach")
                                    coaches_created += 1
                                    # Map coach to team via M2M relationship
                                    if new_coach not in team.coach.all():
                                        team.coach.add(new_coach)
                                    logger.debug(f"Created coach: {coach_name_en or coach_name_he} for team {team.name}")
                                except Exception as e:
                                    logger.error(f"Failed to create coach {coach_name_en or coach_name_he}: {e}", exc_info=True)
                            else:
                                # Coach exists - update team assignment and map to team
                                if existing_coach.team != team:
                                    existing_coach.team = team
                                    existing_coach.save(update_fields=["team"])
                                
                                # Ensure coach is mapped to team via M2M relationship
                                if existing_coach not in team.coach.all():
                                    team.coach.add(existing_coach)
                                    logger.debug(f"Mapped existing coach {existing_coach.name} to team {team.name}")
                    
                    # Process referees
                    en_referees = en_data.get("referees", [])
                    he_referees = he_data.get("referees", [])
                    game = session.game
                    
                    if game:
                        for idx, referee_en in enumerate(en_referees):
                            referee_he = he_referees[idx] if idx < len(he_referees) else {}
                            referee_name_en = referee_en.get("name", "").strip()
                            referee_name_he = referee_he.get("name", "").strip() if referee_he else ""
                            
                            if not referee_name_en and not referee_name_he:
                                continue
                            
                            # Check if referee already exists (by name only, no team)
                            existing_referee = WajoUser.objects.filter(role="Referee").filter(
                                Q(name=referee_name_en) | Q(name=referee_name_he) |
                                Q(language_metadata__en__name=referee_name_en) |
                                Q(language_metadata__he__name=referee_name_he)
                            ).first() if (referee_name_en or referee_name_he) else None
                            
                            if not existing_referee:
                                # Create new referee
                                user_data = {
                                    "name": {"en": referee_name_en, "he": referee_name_he},
                                    "role": {"en": referee_en.get("position", "Referee"), "he": referee_he.get("position", "שופט") if referee_he else ""},
                                }
                                try:
                                    new_referee = create_wajo_user(team=None, jersey_number=None, user_data=user_data, user_role="Referee")
                                    referees_created += 1
                                    # Map referee to game via M2M relationship
                                    if new_referee not in game.referees.all():
                                        game.referees.add(new_referee)
                                    logger.debug(f"Created referee: {referee_name_en or referee_name_he}")
                                except Exception as e:
                                    logger.error(f"Failed to create referee {referee_name_en or referee_name_he}: {e}", exc_info=True)
                            else:
                                # Referee exists - ensure mapped to game
                                if existing_referee not in game.referees.all():
                                    game.referees.add(existing_referee)
                                    logger.debug(f"Mapped existing referee {existing_referee.name} to game {game.id}")
                    else:
                        logger.warning(f"Session {session_id} has no associated game, skipping referee assignment")
                    
                    logger.info(f"Coaches and referees processing complete: {coaches_created} coaches created, {referees_created} referees created")
                except Exception as e:
                    logger.warning(f"Failed to process coaches and referees: {str(e)}", exc_info=True)
                
                # Step 6: Create highlights from normalized data using existing method
                try:
                    highlight_result = create_highlights_from_normalized_data(
                        session, normalized_data
                    )
                    highlights_created = highlight_result.get("highlights_created", 0)
                    clip_reels_created = highlight_result.get("clip_reels_created", 0)
                    errors = highlight_result.get("errors", [])
                    
                    if errors:
                        logger.warning(
                            f"Some highlights failed to create: {errors}"
                        )
                    
                    logger.info(
                        f"Created {highlights_created} highlights and {clip_reels_created} clip reels from Excel data"
                    )
                    
                    # Verification: Check if we should have created highlights but didn't
                    total_goals = sum(
                        len(player_data.get("goals", []))
                        for player_data in normalized_data.get("players", [])
                    )
                    total_cards = sum(
                        1 for player_data in normalized_data.get("players", [])
                        if player_data.get("cards", 0) > 0
                    )
                    expected_highlights = total_goals + total_cards
                    
                    if expected_highlights > 0 and highlights_created == 0:
                        logger.warning(
                            f"Expected to create {expected_highlights} highlights (goals: {total_goals}, cards: {total_cards}) "
                            f"but created 0. This may indicate an issue with highlight creation."
                        )
                    elif highlights_created < expected_highlights:
                        logger.info(
                            f"Created {highlights_created} highlights out of {expected_highlights} expected "
                            f"(some may already exist or failed to create)"
                        )
                        
                except Exception as e:
                    logger.error(
                        f"Failed to create highlights: {str(e)}", exc_info=True
                    )
                    # Don't fail the entire task, but log the error prominently
                    # Highlights can be created later via the API endpoint if needed

                # Step 7: Generate game timeline
                game_timeline = []
                try:
                    logger.info("Generating game timeline...")
                    game_timeline = generate_game_timeline(normalized_data, session)
                    logger.info(f"Generated {len(game_timeline)} timeline events")
                except Exception as e:
                    logger.warning(f"Failed to generate game timeline: {str(e)}", exc_info=True)
                
                # Step 8: Update or create TraceVisionSessionStats with goal statistics, starting_lineups, replacements, and timeline
                try:
                    session_stats, stats_created = (
                        TraceVisionSessionStats.objects.get_or_create(
                            session=session,
                            defaults={
                                "home_team_stats": {},
                                "away_team_stats": {},
                                "possession_data": {},
                                "tactical_analysis": {},
                            },
                        )
                    )

                    # Separate player goals by team
                    home_player_goals = {}
                    away_player_goals = {}

                    for pid, count in player_goals.items():
                        try:
                            player = TracePlayer.objects.get(id=pid)
                            if player.team == session.home_team:
                                home_player_goals[str(pid)] = count
                            elif player.team == session.away_team:
                                away_player_goals[str(pid)] = count
                        except TracePlayer.DoesNotExist:
                            continue

                    # Extract starting_lineups and replacements from match_data for stats
                    en_data = match_data.get("en", {})
                    he_data = match_data.get("he", {})
                    en_summary = en_data.get("Match_summary", {})
                    he_summary = he_data.get("Match_summary", {})
                    
                    # Get team names (use English for stats, but we can include both languages)
                    home_team_name_en = en_summary.get("match_home_team", "")
                    away_team_name_en = en_summary.get("match_away_team", "")
                    home_team_name_he = he_summary.get("match_home_team", "")
                    away_team_name_he = he_summary.get("match_away_team", "")
                    
                    # Extract starting_lineups and replacements for home team
                    starting_lineups_data = en_data.get("starting_lineups", {})
                    replacements_data = en_data.get("replacements", {})
                    home_starting_lineups = starting_lineups_data.get(home_team_name_en, {})
                    home_replacements = replacements_data.get(home_team_name_en, {})
                    
                    # Extract starting_lineups and replacements for away team
                    away_starting_lineups = starting_lineups_data.get(away_team_name_en, {})
                    away_replacements = replacements_data.get(away_team_name_en, {})
                    
                    # Also include Hebrew data for completeness
                    he_starting_lineups_data = he_data.get("starting_lineups", {})
                    he_replacements_data = he_data.get("replacements", {})
                    home_starting_lineups_he = he_starting_lineups_data.get(home_team_name_he, {})
                    home_replacements_he = he_replacements_data.get(home_team_name_he, {})
                    away_starting_lineups_he = he_starting_lineups_data.get(away_team_name_he, {})
                    away_replacements_he = he_replacements_data.get(away_team_name_he, {})

                    # Update home team stats
                    home_stats = session_stats.home_team_stats or {}
                    home_stats.update(
                        {
                            "total_goals": home_goals,
                            "first_half_goals": home_first_half_goals,
                            "second_half_goals": home_second_half_goals,
                            "player_goals": home_player_goals,
                            "starting_lineups": {
                                "en": home_starting_lineups,
                                "he": home_starting_lineups_he
                            },
                            "replacements": {
                                "en": home_replacements,
                                "he": home_replacements_he
                            }
                        }
                    )
                    session_stats.home_team_stats = home_stats

                    # Update away team stats
                    away_stats = session_stats.away_team_stats or {}
                    away_stats.update(
                        {
                            "total_goals": away_goals,
                            "first_half_goals": away_first_half_goals,
                            "second_half_goals": away_second_half_goals,
                            "player_goals": away_player_goals,
                            "starting_lineups": {
                                "en": away_starting_lineups,
                                "he": away_starting_lineups_he
                            },
                            "replacements": {
                                "en": away_replacements,
                                "he": away_replacements_he
                            }
                        }
                    )
                    session_stats.away_team_stats = away_stats
                    
                    # Store game timeline in tactical_analysis
                    tactical_analysis = session_stats.tactical_analysis or {}
                    tactical_analysis["game_timeline"] = game_timeline
                    session_stats.tactical_analysis = tactical_analysis

                    session_stats.save(
                        update_fields=["home_team_stats", "away_team_stats", "tactical_analysis"]
                    )
                    logger.info(
                        f"Updated goal statistics in TraceVisionSessionStats for session {session_id}"
                    )
                except Exception as e:
                    logger.warning(
                        f"Failed to update goal statistics: {str(e)}", exc_info=True
                    )

                # Step 9: Update Game model with game_info (scores, lineups, replacements, coaches, referees, timeline)
                try:
                    game = session.game
                    if game:
                        from games.models import Game
                        
                        # Build goals array with player details
                        def build_goals_array(normalized_data, team_side, language="en"):
                            """Build goals array for a specific team in specified language."""
                            goals_array = []
                            for player_data in normalized_data.get("players", []):
                                if player_data.get("team_side") != team_side:
                                    continue
                                
                                player_goals_list = player_data.get("goals", [])
                                jersey_number = player_data.get("jersey_number")
                                player_name = player_data.get("name", {}).get(language, "")
                                # Fallback to other language if current language name is empty
                                if not player_name:
                                    other_lang = "he" if language == "en" else "en"
                                    player_name = player_data.get("name", {}).get(other_lang, "")
                                
                                for goal in player_goals_list:
                                    try:
                                        minute_str = str(goal.get("minute", "0")).replace("'", "").replace("min", "").strip()
                                        minute = int(minute_str) if minute_str.isdigit() else 0
                                        half = 1 if minute <= 45 else 2
                                        
                                        goals_array.append({
                                            "player_name": player_name,
                                            "jersey": jersey_number,
                                            "half": half,
                                            "goaltime": minute_str
                                        })
                                    except (ValueError, TypeError):
                                        continue
                            
                            # Sort goals by goaltime
                            goals_array.sort(key=lambda x: int(x.get("goaltime", "0")) if x.get("goaltime", "0").isdigit() else 0)
                            return goals_array
                        
                        # Build game_info structure
                        game_info = {
                            "en": {"home": {}, "away": {}},
                            "he": {"home": {}, "away": {}}
                        }
                        
                        en_data = match_data.get("en", {})
                        he_data = match_data.get("he", {})
                        
                        # Get team names from match_data
                        en_summary = en_data.get("Match_summary", {})
                        he_summary = he_data.get("Match_summary", {})
                        home_team_name_en = en_summary.get("match_home_team", "")
                        away_team_name_en = en_summary.get("match_away_team", "")
                        home_team_name_he = he_summary.get("match_home_team", "")
                        away_team_name_he = he_summary.get("match_away_team", "")
                        
                        # Process for each language
                        for lang in ["en", "he"]:
                            lang_data = en_data if lang == "en" else he_data
                            
                            lang_summary = en_summary if lang == "en" else he_summary
                            
                            # Get team names for this language
                            home_name = home_team_name_en if lang == "en" else home_team_name_he
                            away_name = away_team_name_en if lang == "en" else away_team_name_he
                            
                            # Extract starting_lineups with all details (name, role, goals, video_goal, sub_off_minute, cards)
                            starting_lineups_data = lang_data.get("starting_lineups", {})
                            home_starting_lineups = starting_lineups_data.get(home_name, {})
                            away_starting_lineups = starting_lineups_data.get(away_name, {})
                            
                            # Extract replacements with all details (name, role, goals, replacer_minute)
                            replacements_data = lang_data.get("replacements", {})
                            home_replacements = replacements_data.get(home_name, {})
                            away_replacements = replacements_data.get(away_name, {})
                            
                            # Extract coaches
                            coaches_data = lang_data.get("coaches", {})
                            home_coaches = coaches_data.get(home_name, [])
                            away_coaches = coaches_data.get(away_name, [])
                            
                            # Build home goals array with language-specific player names
                            home_goals_array = build_goals_array(normalized_data, "home", language=lang)
                            
                            # Log for debugging
                            logger.debug(
                                f"Storing game_info for {lang} - home: {len(home_starting_lineups)} starting_lineups, "
                                f"{len(home_replacements)} replacements, {len(home_coaches)} coaches"
                            )
                            
                            game_info[lang]["home"] = {
                                "total_score": home_goals,
                                "first_half_score": home_first_half_goals,
                                "second_half_score": home_second_half_goals,
                                "goals": home_goals_array,
                                "starting_lineups": home_starting_lineups,  # Full structure with all player details
                                "replacements": home_replacements,  # Full structure with all replacement details
                                "coaches": home_coaches
                            }
                            
                            # Build away goals array with language-specific player names
                            away_goals_array = build_goals_array(normalized_data, "away", language=lang)
                            
                            # Log for debugging
                            logger.debug(
                                f"Storing game_info for {lang} - away: {len(away_starting_lineups)} starting_lineups, "
                                f"{len(away_replacements)} replacements, {len(away_coaches)} coaches"
                            )
                            
                            game_info[lang]["away"] = {
                                "total_score": away_goals,
                                "first_half_score": away_first_half_goals,
                                "second_half_score": away_second_half_goals,
                                "goals": away_goals_array,
                                "starting_lineups": away_starting_lineups,  # Full structure with all player details
                                "replacements": away_replacements,  # Full structure with all replacement details
                                "coaches": away_coaches
                            }
                            
                            # Add referees (shared, not per team) - add to both home and away for consistency
                            referees = lang_data.get("referees", [])
                            game_info[lang]["home"]["referees"] = referees
                            game_info[lang]["away"]["referees"] = referees
                        
                        # Validate and update game with game_info
                        # Ensure starting_lineups and replacements are properly structured
                        home_lineup_count = 0
                        away_lineup_count = 0
                        home_replacement_count = 0
                        away_replacement_count = 0
                        
                        for lang in ["en", "he"]:
                            for team_side in ["home", "away"]:
                                team_info = game_info[lang][team_side]
                                
                                # Verify starting_lineups structure (should be dict with jersey numbers as keys)
                                if not isinstance(team_info.get("starting_lineups"), dict):
                                    logger.warning(
                                        f"Starting lineups for {lang}/{team_side} is not a dict, converting to empty dict"
                                    )
                                    team_info["starting_lineups"] = {}
                                else:
                                    # Count for logging (only count once per language, use English)
                                    if lang == "en":
                                        if team_side == "home":
                                            home_lineup_count = len(team_info["starting_lineups"])
                                        else:
                                            away_lineup_count = len(team_info["starting_lineups"])
                                
                                # Verify replacements structure (should be dict with jersey numbers as keys)
                                if not isinstance(team_info.get("replacements"), dict):
                                    logger.warning(
                                        f"Replacements for {lang}/{team_side} is not a dict, converting to empty dict"
                                    )
                                    team_info["replacements"] = {}
                                else:
                                    # Count for logging (only count once per language, use English)
                                    if lang == "en":
                                        if team_side == "home":
                                            home_replacement_count = len(team_info["replacements"])
                                        else:
                                            away_replacement_count = len(team_info["replacements"])
                        
                        # Add game timeline to game_info
                        game_info["timeline"] = game_timeline
                        
                        # Update game with game_info
                        game.game_info = game_info
                        game.save(update_fields=["game_info"])
                        logger.info(
                            f"Updated game_info for game {game.id} with scores, lineups "
                            f"({home_lineup_count} home, {away_lineup_count} away), "
                            f"replacements ({home_replacement_count} home, {away_replacement_count} away), "
                            f"coaches, referees, and {len(game_timeline)} timeline events"
                        )
                    else:
                        logger.warning(f"Session {session_id} has no associated game, skipping game_info update")
                except Exception as e:
                    logger.warning(
                        f"Failed to update game_info: {str(e)}", exc_info=True
                    )

                logger.info(
                    f"Processed Excel data for session {session_id}: "
                    f"{players_created} players created, {players_updated} players updated, "
                    f"{tokens_generated} tokens generated, {highlights_created} highlights created, "
                    f"{coaches_created} coaches created, {referees_created} referees created, "
                    f"{home_goals} home goals, {away_goals} away goals, "
                    f"{len(game_timeline)} timeline events"
                )
        except Exception as e:
            error_msg = f"Error processing players: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {"success": False, "error": error_msg}

        finally:
            # Clean up temp file
            try:
                if os.path.exists(excel_file_path):
                    os.unlink(excel_file_path)
            except Exception as e:
                logger.warning(f"Failed to delete temp file {excel_file_path}: {e}")

        return {
            "success": True,
            "session_id": session_id,
            "players_created": players_created,
            "players_updated": players_updated,
            "tokens_generated": tokens_generated,
            "highlights_created": highlights_created,
            "coaches_created": coaches_created,
            "referees_created": referees_created,
            "timeline_events": len(game_timeline),
            "goal_statistics": {
                "home_goals": home_goals,
                "away_goals": away_goals,
                "home_first_half_goals": home_first_half_goals,
                "home_second_half_goals": home_second_half_goals,
                "away_first_half_goals": away_first_half_goals,
                "away_second_half_goals": away_second_half_goals,
                "player_goals": player_goals,
            },
            "message": "Excel data processed successfully. Players can now create accounts using their tokens.",
        }

    except Exception as e:
        error_msg = f"Unexpected error processing Excel data: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return {"success": False, "error": error_msg}


def reprocess_game_timeline_only(session_id):
    """
    Reprocess and update ONLY the game timeline from Excel data.
    Preserves all other game_info data (scores, lineups, replacements, coaches, referees).
    
    This is a lightweight operation that:
    1. Downloads Excel from session.basic_game_stats_excel
    2. Extracts and normalizes multilingual data
    3. Generates timeline using generate_game_timeline()
    4. Updates game.game_info["timeline"] only
    
    Args:
        session_id (int): TraceSession ID
        
    Returns:
        dict: Result with success status and timeline event count
    """
    from tracevision.models import TraceSession
    
    try:
        # Get session
        session = TraceSession.objects.select_related("game", "home_team", "away_team").get(id=session_id)
        logger.info(f"Reprocessing timeline for session {session_id} ({session.session_id})")
        
        # Check if session has Excel file
        if not session.basic_game_stats:
            error_msg = "Session has no basic_game_stats file"
            logger.warning(f"{error_msg} for session {session_id}")
            return {"success": False, "error": error_msg}
        
        # Check if session has associated game
        if not session.game:
            error_msg = "Session has no associated game"
            logger.warning(f"{error_msg} for session {session_id}")
            return {"success": False, "error": error_msg}
        
        # Download Excel file from Azure
        excel_file_path = None
        try:
            logger.info(f"Downloading Excel file from {session.basic_game_stats.url}")
            excel_file_path = download_excel_file_from_storage(session.basic_game_stats.url)
            logger.info(f"Excel file downloaded to {excel_file_path}")
        except Exception as e:
            error_msg = f"Failed to download Excel file: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {"success": False, "error": error_msg}
        
        try:
            # Extract multilingual match data
            logger.info("Extracting multilingual match data from Excel...")
            match_data = extract_multilingual_match_data(excel_file_path)
            logger.info(f"Extracted match data with {len(match_data.get('en', {}).get('starting_lineups', {}))} starting lineups")
            
            # Normalize multilingual data
            logger.info("Normalizing multilingual data...")
            normalized_data = normalize_multilingual_data(match_data)
            logger.info(f"Normalized data for {len(normalized_data.get('players', []))} players")
            
            # Generate game timeline
            logger.info("Generating game timeline...")
            game_timeline = generate_game_timeline(normalized_data, session)
            logger.info(f"Generated {len(game_timeline)} timeline events")
            
            # Update game.game_info["timeline"] only, preserving all other data
            game = session.game
            existing_game_info = game.game_info if game.game_info else {}
            
            # Preserve all existing data and update only timeline
            existing_game_info["timeline"] = game_timeline
            game.game_info = existing_game_info
            game.save(update_fields=["game_info"])
            
            logger.info(
                f"Successfully updated timeline for session {session_id}: "
                f"{len(game_timeline)} timeline events saved to game {game.id}"
            )
            
            return {
                "success": True,
                "session_id": session_id,
                "session_string_id": session.session_id,
                "game_id": game.id,
                "timeline_events": len(game_timeline),
                "message": f"Timeline reprocessed successfully with {len(game_timeline)} events"
            }
            
        finally:
            # Clean up temp file
            if excel_file_path and os.path.exists(excel_file_path):
                try:
                    os.unlink(excel_file_path)
                    logger.debug(f"Cleaned up temp Excel file: {excel_file_path}")
                except Exception as e:
                    logger.warning(f"Failed to clean up temp file {excel_file_path}: {e}")
    
    except TraceSession.DoesNotExist:
        error_msg = f"Session with ID {session_id} not found"
        logger.error(error_msg)
        return {"success": False, "error": error_msg}
    except Exception as e:
        error_msg = f"Unexpected error reprocessing timeline: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return {"success": False, "error": error_msg}
