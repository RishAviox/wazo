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
        
        calculator = SpotlightMetricsCalculator(field_length_m=field_length_m, field_width_m=field_width_m)
        spotlights = calculator.load_spotlight_data(file_path)
        
        if not spotlights:
            logger.error(f"No spotlight data found in {file_path}")
            return calculator._get_empty_athletic_metrics(), calculator._get_empty_football_metrics()
        
        logger.info(f"Calculating metrics from {len(spotlights)} tracking points")
        
        athletic_metrics = calculator.calculate_gps_athletic_skills(spotlights)
        football_metrics = calculator.calculate_gps_football_abilities(spotlights)
        
        return athletic_metrics, football_metrics
        
    except Exception as e:
        logger.exception(f"Error calculating metrics from {file_path}: {e}")
        # Return empty metrics on error
        from .spotlight_metrics_calculator import SpotlightMetricsCalculator
        calculator = SpotlightMetricsCalculator(field_length_m=field_length_m, field_width_m=field_width_m)
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