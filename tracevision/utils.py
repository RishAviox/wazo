import webcolors
import logging
from typing import Dict, Tuple, Optional

logger = logging.getLogger(__name__)


def get_hex_from_color_name(color_name):
    try:
        return webcolors.name_to_hex(color_name.lower())
    except ValueError:
        return None  # or return a default like "#000000"


def calculate_metrics_from_spotlight_file(file_path: str, field_length_m: float = 105.0, field_width_m: float = 68.0) -> Tuple[Dict[str, str], Dict[str, str]]:
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
            field_length_m=field_length_m, field_width_m=field_width_m)
        spotlights = calculator.load_spotlight_data(file_path)

        if not spotlights:
            logger.error(f"No spotlight data found in {file_path}")
            return calculator._get_empty_athletic_metrics(), calculator._get_empty_football_metrics()

        logger.info(
            f"Calculating metrics from {len(spotlights)} tracking points")

        athletic_metrics = calculator.calculate_gps_athletic_skills(spotlights)
        football_metrics = calculator.calculate_gps_football_abilities(
            spotlights)

        return athletic_metrics, football_metrics

    except Exception as e:
        logger.exception(f"Error calculating metrics from {file_path}: {e}")
        # Return empty metrics on error
        from .spotlight_metrics_calculator import SpotlightMetricsCalculator
        calculator = SpotlightMetricsCalculator(
            field_length_m=field_length_m, field_width_m=field_width_m)
        return calculator._get_empty_athletic_metrics(), calculator._get_empty_football_metrics()


def format_metrics_for_display(athletic_metrics: Dict[str, str], football_metrics: Dict[str, str]) -> str:
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


def save_metrics_to_cards(user, athletic_metrics: Dict[str, str], football_metrics: Dict[str, str], game=None):
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
            defaults={
                'metrics': athletic_metrics,
                'updated_on': timezone.now()
            }
        )

        # Save GPS Football Abilities
        gps_football, created = GPSFootballAbilities.objects.update_or_create(
            user=user,
            game=game,
            defaults={
                'metrics': football_metrics,
                'updated_on': timezone.now()
            }
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
            return f"sessions/{session_id}/videos/processed/{session_id}_{video_type}.mp4"

    @staticmethod
    def get_highlight_video_path(session_id: str, highlight_id: str, video_type: str) -> str:
        """Get path for highlight video files."""
        return f"sessions/{session_id}/videos/highlights/{highlight_id}_{video_type}.mp4"

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
            return f"sessions/{session_id}/data/analytics/team_stats/combined_stats.json"

    @staticmethod
    def get_heatmap_path(session_id: str, player_id: str) -> str:
        """Get path for player heatmap data."""
        return f"sessions/{session_id}/data/analytics/heatmaps/{player_id}_heatmap.json"

    @staticmethod
    def get_thumbnail_path(session_id: str, highlight_id: str, thumbnail_type: str = "thumbnail") -> str:
        """Get path for thumbnail images."""
        return f"sessions/{session_id}/thumbnails/{highlight_id}_{thumbnail_type}.jpg"

    @staticmethod
    def get_export_path(session_id: str, export_type: str, file_extension: str = "json") -> str:
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
        if not all([session.match_start_time, session.first_half_end_time,
                   session.second_half_start_time, session.match_end_time]):
            logger.warning(
                f"Session {session.session_id} missing timeline data. Cannot convert game time.")
            return 0

        # Convert timeline strings to seconds
        def time_to_seconds(time_str):
            """Convert HH:MM:SS or MM:SS to total seconds"""
            try:
                parts = time_str.split(':')
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
        video_second_half_start = time_to_seconds(
            session.second_half_start_time)
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
            f"  First half: 0-{first_half_end_game_minute:.1f} min (video: {session.match_start_time} to {session.first_half_end_time})")
        logger.info(
            f"  Half time: {first_half_end_game_minute:.1f}-{second_half_start_game_minute:.1f} min (video: {session.first_half_end_time} to {session.second_half_start_time})")
        logger.info(
            f"  Second half: {second_half_start_game_minute:.1f}-{second_half_end_game_minute:.1f} min (video: {session.second_half_start_time} to {session.match_end_time})")

        if game_minute <= 45:  # First half (0-45 min game time)
            # Map game time proportionally within first half video duration
            progress = game_minute / 45.0  # 0.0 to 1.0
            video_time_seconds = video_match_start + \
                (first_half_game_duration * progress)
            logger.info(
                f"  First half: {game_minute}/45 = {progress:.3f} progress")

        else:
            minutes_into_second_half = game_minute - 45
            seconds_into_second_half = minutes_into_second_half * 60 + game_second

            second_half_video_duration = video_match_end - video_second_half_start
            second_half_game_duration = 45 * 60  # Standard 45 minutes for second half

            # Calculate the time ratio (how much video time per game time)
            time_ratio = second_half_video_duration / second_half_game_duration

            # Map game time to video time using the calculated ratio
            game_time_into_second_half = (game_minute - 45) * 60 + game_second
            video_time_seconds = video_second_half_start + \
                (game_time_into_second_half * time_ratio)

            # For extra time beyond normal match duration, add additional time
            if game_minute > 90:
                extra_minutes = game_minute - 90
                video_time_seconds += extra_minutes * 60
                logger.info(f"    Extra time: +{extra_minutes} min")

        # Convert to milliseconds
        video_time_milliseconds = int(video_time_seconds * 1000)

        logger.info(
            f"Converted game time {game_minute}:{game_second:02d} to video time {video_time_seconds:.2f}s ({video_time_milliseconds}ms)")

        return video_time_milliseconds

    except Exception as e:
        logger.exception(
            f"Error converting game time {game_minute}:{game_second} to video milliseconds: {e}")
        return 0


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
        if not all([session.match_start_time, session.first_half_end_time,
                   session.second_half_start_time, session.match_end_time]):
            logger.warning(
                f"Session {session.session_id} missing timeline data. Cannot determine half.")
            return None

        # Convert timeline strings to seconds
        def time_to_seconds(time_str):
            """Convert HH:MM:SS or MM:SS to total seconds"""
            try:
                parts = time_str.split(':')
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
        video_second_half_start = time_to_seconds(
            session.second_half_start_time)
        video_match_end = time_to_seconds(session.match_end_time)

        # Calculate actual game half durations from video timeline
        first_half_game_duration = video_first_half_end - video_match_start
        half_time_duration = video_second_half_start - video_first_half_end
        second_half_game_duration = video_match_end - video_second_half_start

        # Calculate the actual game minute when first half ends (based on video timeline)
        first_half_end_game_minute = first_half_game_duration / 60.0  # Convert to minutes
        second_half_start_game_minute = first_half_end_game_minute + \
            (half_time_duration / 60.0)
        second_half_end_game_minute = second_half_start_game_minute + \
            (second_half_game_duration / 60.0)

        # Determine which half the event occurs in based on actual timeline
        if game_minute <= first_half_end_game_minute:
            return 1  # First half
        elif game_minute <= second_half_end_game_minute:
            return 2  # Second half
        else:
            return 2  # Extra time is considered part of second half

    except Exception as e:
        logger.exception(
            f"Error determining half for game minute {game_minute}: {e}")
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
                parts = time_str.split(':')
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
        video_second_half_start = time_to_seconds(
            session.second_half_start_time)
        video_match_end = time_to_seconds(session.match_end_time)

        # Calculate actual game half durations from video timeline
        first_half_game_duration = video_first_half_end - video_match_start
        half_time_duration = video_second_half_start - video_first_half_end
        second_half_game_duration = video_match_end - video_second_half_start

        # Calculate the actual game minute when first half ends (based on video timeline)
        first_half_end_game_minute = first_half_game_duration / 60.0  # Convert to minutes
        second_half_start_game_minute = first_half_end_game_minute + \
            (half_time_duration / 60.0)
        second_half_end_game_minute = second_half_start_game_minute + \
            (second_half_game_duration / 60.0)

        return {
            'video_match_start': video_match_start,
            'video_first_half_end': video_first_half_end,
            'video_second_half_start': video_second_half_start,
            'video_match_end': video_match_end,
            'first_half_game_duration': first_half_game_duration,
            'half_time_duration': half_time_duration,
            'second_half_game_duration': second_half_game_duration,
            'first_half_end_game_minute': first_half_end_game_minute,
            'second_half_start_game_minute': second_half_start_game_minute,
            'second_half_end_game_minute': second_half_end_game_minute
        }

    except Exception as e:
        logger.exception(
            f"Error extracting timeline data from session {session.session_id}: {e}")
        return None
