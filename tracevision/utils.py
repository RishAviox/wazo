import os
import webcolors
import logging
from typing import Dict, Tuple

logger = logging.getLogger(__name__)


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
        from cards.models import GPSAthleticSkills, GPSFootballAbilities
        from django.utils import timezone

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
        session_id: str, highlight_id: str, video_type: str
    ) -> str:
        """Get path for highlight video files."""
        return (
            f"sessions/{session_id}/videos/highlights/{highlight_id}_{video_type}.mp4"
        )

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
        existing_session = TraceSession.objects.filter(video_url=video_url).first()
        if existing_session:
            logger.info(f"Duplicate found by video_url: {video_url}")
            return existing_session

    # Check by (home_team, away_team, match_date)
    if home_team and away_team and match_date:
        existing_session = TraceSession.objects.filter(
            home_team=home_team, away_team=away_team, match_date=match_date
        ).first()
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

    # Generate game ID from teams and date
    # Format: HOME_TEAM_ID_AWAY_TEAM_ID_YYYYMMDD
    home_id = "".join(c for c in str(home_team.id).upper() if c.isalnum())[:5]
    away_id = "".join(c for c in str(away_team.id).upper() if c.isalnum())[:5]
    date_str = match_date.strftime("%Y%m%d")
    game_id = f"{home_id}_{away_id}_{date_str}"[:10]  # Max 10 chars

    # Try to get existing game
    game, created = Game.objects.get_or_create(
        id=game_id,
        defaults={
            "type": game_type,
            "name": f"{home_team.name} vs {away_team.name}",
            "date": match_date,
        },
    )

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
        from django.core.files.storage import default_storage
        from django.conf import settings
        import tempfile
        import os

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
