import webcolors
import logging
from typing import Dict, Tuple

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
