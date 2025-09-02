import os
import json
import math
import logging
from typing import Dict, List, Any
from django.core.files.storage import default_storage
from django.core.cache import cache
from django.conf import settings

logger = logging.getLogger(__name__)


def clear_spotlight_data_cache(object_id: str, session_id: str) -> bool:
    """
    Clear cached spotlight data for a specific object.
    
    Args:
        object_id: TraceObject object_id
        session_id: TraceSession session_id
        
    Returns:
        bool: True if cache was cleared, False otherwise
    """
    try:
        cache_key = f"spotlight_data_{session_id}_{object_id}"
        cache.delete(cache_key)
        logger.info(f"Cleared spotlight data cache for {object_id} in session {session_id}")
        return True
    except Exception as e:
        logger.exception(f"Error clearing spotlight cache for {object_id}: {e}")
        return False


class SpotlightMetricsCalculator:
    """
    Calculate performance metrics from TraceVision spotlight tracking data
    
    This class now supports dynamic field dimensions from TraceSession objects.
    Field dimensions are used to calculate accurate distance measurements and scaling factors.
    
    Examples:
        # Using default FIFA standard dimensions (105m x 68m)
        calculator = SpotlightMetricsCalculator()
        
        # Using custom dimensions
        calculator = SpotlightMetricsCalculator(field_length_m=91.0, field_width_m=55.0)
        
        # Using dimensions from a TraceSession
        calculator = SpotlightMetricsCalculator.from_trace_session(trace_session)
    """

    def __init__(self, field_length_m: float = 105.0, field_width_m: float = 68.0):
        # Field dimensions from TraceSession (default to standard FIFA pitch size)
        self.FIELD_LENGTH_M = field_length_m
        self.FIELD_WIDTH_M = field_width_m

        # Using average of length and width for more balanced scaling
        self.SCALE_FACTOR = (self.FIELD_LENGTH_M +
                             self.FIELD_WIDTH_M) / 2000.0  # meters per unit

        # Maximum realistic speeds for filtering outliers
        self.MAX_REALISTIC_SPEED_MPS = 12.0  # 43.2 km/h - maximum human sprint speed

        # Speed thresholds (m/s)
        self.WALKING_THRESHOLD = 2.0     # < 2.0 m/s
        self.JOGGING_THRESHOLD = 4.0     # 2.0 - 4.0 m/s
        self.RUNNING_THRESHOLD = 5.5     # 4.0 - 5.5 m/s
        self.SPRINTING_THRESHOLD = 7.0   # > 5.5 m/s
        self.HIGH_INTENSITY_THRESHOLD = 6.5  # > 6.5 m/s

        # Acceleration thresholds (m/s²)
        self.HIGH_ACCEL_THRESHOLD = 2.5
        self.MAX_ACCEL_THRESHOLD = 4.0

        # Football-specific thresholds
        self.KICK_POWER_THRESHOLD = 8.0
        self.DRIBBLE_MIN_DURATION = 3.0
        self.DRIBBLE_MAX_SPEED = 4.0

    @classmethod
    def from_trace_session(cls, trace_session):
        """
        Create a SpotlightMetricsCalculator instance from a TraceSession object
        
        Args:
            trace_session: TraceSession instance with pitch_size field
            
        Returns:
            SpotlightMetricsCalculator instance with field dimensions from the session
            
        Example:
            # Get calculator with field dimensions from session
            session = TraceSession.objects.get(id=session_id)
            calculator = SpotlightMetricsCalculator.from_trace_session(session)
            
            # The calculator will now use the correct field dimensions for accurate calculations
        """
        if hasattr(trace_session, 'pitch_size') and trace_session.pitch_size:
            field_length = trace_session.pitch_size.get('length', 105.0)
            field_width = trace_session.pitch_size.get('width', 68.0)
        else:
            # Fallback to default FIFA standard dimensions
            field_length = 105.0
            field_width = 68.0
            
        return cls(field_length_m=field_length, field_width_m=field_width)

    def get_field_dimensions(self) -> Dict[str, float]:
        """
        Get the current field dimensions being used by this calculator
        
        Returns:
            dict: Field dimensions with 'length' and 'width' keys in meters
        """
        return {
            'length': self.FIELD_LENGTH_M,
            'width': self.FIELD_WIDTH_M,
            'scale_factor': self.SCALE_FACTOR
        }

    def load_spotlight_data(self, file_path: str) -> List[List[float]]:
        """
        Load spotlight tracking data from JSON file

        Args:
            file_path: Path to the spotlight JSON file

        Returns:
            List of tracking points [time_off, x, y, w, h]
        """
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)

            spotlights = data.get('spotlights', [])
            logger.info(
                f"Loaded {len(spotlights)} spotlight tracking points from {file_path}")

            return spotlights

        except Exception as e:
            logger.exception(
                f"Error loading spotlight data from {file_path}: {e}")
            return []

    def load_spotlight_data_from_azure_blob(self, blob_url: str, cache_key: str = None) -> List[List[float]]:
        """
        Load spotlight tracking data from Azure blob URL with caching support

        Args:
            blob_url: Azure blob URL to the tracking data JSON file (or local file path in dev)
            cache_key: Optional cache key for caching the data

        Returns:
            List of tracking points [time_off, x, y, w, h]
        """
        try:
            # Check cache first if cache_key is provided
            if cache_key:
                cached_data = cache.get(cache_key)
                if cached_data is not None:
                    logger.debug(f"Retrieved spotlight data from cache for key: {cache_key}")
                    return cached_data

            # Check if we're in development mode (local file storage)
            if settings.DEBUG and not hasattr(settings, 'AZURE_CUSTOM_DOMAIN'):
                logger.info(f"Development mode detected - reading from local file: {blob_url}")
                
                # Convert blob URL to local file path
                if blob_url.startswith('/media/'):
                    local_file_path = os.path.join(settings.MEDIA_ROOT, blob_url[7:])  # Remove '/media/'
                else:
                    local_file_path = blob_url
                
                if os.path.exists(local_file_path):
                    with open(local_file_path, 'r') as f:
                        data = json.load(f)
                    
                    # Extract spotlights data
                    if isinstance(data, dict) and 'spotlights' in data:
                        spotlights = data['spotlights']
                    elif isinstance(data, list):
                        spotlights = data
                    else:
                        logger.warning(f"Unexpected data format in local file {local_file_path}")
                        return []
                    
                    # Cache the data if cache_key is provided
                    if cache_key and spotlights:
                        cache.set(cache_key, spotlights, timeout=3600)  # Cache for 1 hour
                        logger.debug(f"Cached spotlight data with key: {cache_key}")
                    
                    logger.info(f"Successfully loaded {len(spotlights)} spotlight tracking points from local file")
                    return spotlights
                else:
                    logger.warning(f"Local file not found: {local_file_path}")
                    return []
            
            # Production mode - download from Azure blob storage
            logger.info(f"Loading spotlight data from Azure blob: {blob_url}")
            
            # Use Django's default storage to download the file
            if default_storage.exists(blob_url):
                # Read the file content
                with default_storage.open(blob_url, 'r') as f:
                    data = json.load(f)
                
                # Extract spotlights data
                if isinstance(data, dict) and 'spotlights' in data:
                    spotlights = data['spotlights']
                elif isinstance(data, list):
                    spotlights = data
                else:
                    logger.warning(f"Unexpected data format in blob {blob_url}")
                    return []
                
                # Cache the data if cache_key is provided
                if cache_key and spotlights:
                    cache.set(cache_key, spotlights, timeout=3600)  # Cache for 1 hour
                    logger.debug(f"Cached spotlight data with key: {cache_key}")
                
                logger.info(f"Successfully loaded {len(spotlights)} spotlight tracking points from Azure blob")
                return spotlights
            else:
                logger.error(f"Blob file not found: {blob_url}")
                return []
                
        except Exception as e:
            logger.exception(f"Error loading spotlight data from {blob_url}: {e}")
            return []

    def calculate_gps_athletic_skills(self, spotlights: List[List[float]]) -> Dict[str, str]:
        """
        Calculate GPS Athletic Skills metrics from spotlight data

        Expected output format:
        {"Jogging": "3.6 km", "Walking": "2.9 km", "Play Time": "80 min", 
         "Top Speed": "28 km/h", "Int. Speed": "65 Km/h", ...}
        """
        try:
            if not spotlights or len(spotlights) < 2:
                return self._get_empty_athletic_metrics()

            # Calculate movement data
            movement_data = self._analyze_movement(spotlights)
            distance_zones = self._calculate_distance_zones(spotlights)
            acceleration_data = self._calculate_acceleration_metrics(
                spotlights)

            # Calculate play time
            total_time_seconds = (
                spotlights[-1][0] - spotlights[0][0]) / 1000.0
            play_time_minutes = int(total_time_seconds / 60.0)

            # Calculate athletic skills score
            athletic_score = self._calculate_athletic_skills_score(
                movement_data, distance_zones, acceleration_data
            )

            return {
                "Play Time": f"{play_time_minutes} min",
                "Distance Covered": f"{movement_data['total_distance_km']:.1f} km",
                "Session Volume": f"{movement_data['total_distance_km']:.1f} km",
                "Top Speed": f"{movement_data['max_speed_kmh']:.0f} km/h",
                "Int. Speed": f"{movement_data['avg_speed_kmh']:.0f} Km/h",
                "Walking": f"{distance_zones['walking_km']:.1f} km",
                "Jogging": f"{distance_zones['jogging_km']:.1f} km",
                "High Int. Run": f"{distance_zones['high_intensity_count']}|{distance_zones['high_intensity_km']:.2f} km",
                "Max Int. Run": f"{distance_zones['max_intensity_km']:.1f} km",
                "Session Intensity": f"{acceleration_data['session_intensity']:.0f} m",
                "High Int. Acceleration": f"{acceleration_data['high_accel_count']}|{acceleration_data['high_accel_distance_km']:.1f} km",
                "High Int. Deceleration": f"{acceleration_data['high_decel_count']}|{acceleration_data['high_decel_distance_km']:.1f} km",
                "Max Int. Acceleration": f"{acceleration_data['max_accel_count']}|{acceleration_data['max_accel_distance_m']:.0f} m",
                "Max Int. Deceleration": f"{acceleration_data['max_decel_count']}|{acceleration_data['max_decel_distance_m']:.0f} m",
                "Session Int. Acceleration": f"{acceleration_data['session_accel_intensity']:.0f} ",
                "Athletic Skills": f"{athletic_score:.1f}"
            }

        except Exception as e:
            logger.exception(f"Error calculating GPS athletic skills: {e}")
            return self._get_empty_athletic_metrics()

    def calculate_gps_football_abilities(self, spotlights: List[List[float]], highlights: List[Dict] = None, objects: List[Dict] = None) -> Dict[str, str]:
        """
        Calculate GPS Football Abilities metrics from spotlight data

        Args:
            spotlights: Player tracking data [time_off, x, y, w, h]
            highlights: List of highlight objects with tags and object info
            objects: List of tracked objects with type, side, tracking_url

        Expected format:
        {"Dribbling": "24|320 m", "Play Time": "80 min", "Kick Power": "84 km/h", 
         "Power Kicks": "5 ", "Session Volume": "7500 ", ...}

        Note: Kick power and kick counts are only calculated when ball tracking data is available.
        Without ball data, these metrics will be 0.
        """
        try:
            if not spotlights or len(spotlights) < 2:
                return self._get_empty_football_metrics()

            # Calculate movement and football-specific data
            movement_data = self._analyze_movement(spotlights)
            football_actions = self._analyze_football_actions(spotlights)
            kick_metrics = self._estimate_kick_metrics(
                spotlights, highlights, objects)
            dribbling_metrics = self._estimate_dribbling_metrics(spotlights)

            # Calculate play time
            total_time_seconds = (
                spotlights[-1][0] - spotlights[0][0]) / 1000.0
            play_time_minutes = int(total_time_seconds / 60.0)

            # Calculate football skills score
            football_score = self._calculate_football_skills_score(
                movement_data, kick_metrics, dribbling_metrics
            )

            # Extract kick power, handling the note field if present
            kick_power = kick_metrics.get('avg_kick_power_kmh', 0)
            if isinstance(kick_power, dict):
                kick_power = kick_power.get('avg_kick_power_kmh', 0)

            # Get note about kick metrics
            kick_note = kick_metrics.get('note', 'No kick data available')

            return {
                "Play Time": f"{play_time_minutes} min",
                "Session Volume": f"{int(movement_data['total_distance_m'])} ",
                "Session Intensity": f"{football_actions['avg_intensity']:.0f} ",
                "Football Skills": football_score,
                "Kick Power": f"{kick_power:.0f} km/h",
                "Power Kicks": f"{kick_metrics['power_kicks']} ",
                "High Int. Kicks": f"{kick_metrics['high_intensity_kicks']} ",
                "Med. Int. Kicks": f"{kick_metrics['medium_intensity_kicks']} ",
                "Low Int. Kicks": f"{kick_metrics['low_intensity_kicks']} ",
                "Dribbling": f"{dribbling_metrics['dribble_count']}|{dribbling_metrics['dribble_distance_m']:.0f} m",
                "Max. Intensity Run": f"{football_actions['max_intensity_runs']} ",
                "Note": kick_note
            }

        except Exception as e:
            logger.exception(f"Error calculating GPS football abilities: {e}")
            return self._get_empty_football_metrics()

    def _analyze_movement(self, spotlights: List[List[float]]) -> Dict[str, float]:
        """Analyze basic movement statistics"""
        try:
            total_distance = 0.0
            speeds = []

            for i in range(1, len(spotlights)):
                prev_point = spotlights[i-1]
                curr_point = spotlights[i]

                # Calculate distance in meters
                distance = self._calculate_distance_meters(
                    prev_point, curr_point)
                total_distance += distance

                # Calculate speed in m/s
                time_diff = (curr_point[0] - prev_point[0]
                             ) / 1000.0  # ms to seconds
                if time_diff > 0:
                    speed_mps = distance / time_diff
                    # Filter out unrealistic speeds (likely tracking errors)
                    if speed_mps <= self.MAX_REALISTIC_SPEED_MPS:
                        speeds.append(speed_mps)

            avg_speed_mps = sum(speeds) / len(speeds) if speeds else 0
            max_speed_mps = max(speeds) if speeds else 0

            return {
                'total_distance_m': total_distance,
                'total_distance_km': total_distance / 1000.0,
                'avg_speed_mps': avg_speed_mps,
                'avg_speed_kmh': avg_speed_mps * 3.6,
                'max_speed_mps': max_speed_mps,
                'max_speed_kmh': max_speed_mps * 3.6,
                'speeds': speeds
            }

        except Exception as e:
            logger.exception(f"Error analyzing movement: {e}")
            return {'total_distance_m': 0, 'total_distance_km': 0, 'avg_speed_mps': 0,
                    'avg_speed_kmh': 0, 'max_speed_mps': 0, 'max_speed_kmh': 0, 'speeds': []}

    def _calculate_distance_meters(self, point1: List[float], point2: List[float]) -> float:
        """Calculate distance between two points in meters"""
        try:
            # Points format: [time_ms, x, y, w, h]
            dx = (point2[1] - point1[1]) * \
                self.SCALE_FACTOR  # Convert to meters
            dy = (point2[2] - point1[2]) * \
                self.SCALE_FACTOR  # Convert to meters

            return math.sqrt(dx**2 + dy**2)

        except Exception:
            return 0.0

    def _calculate_distance_zones(self, spotlights: List[List[float]]) -> Dict[str, float]:
        """Calculate distance covered in different intensity zones"""
        try:
            walking_distance = 0.0
            jogging_distance = 0.0
            running_distance = 0.0
            high_intensity_distance = 0.0
            max_intensity_distance = 0.0

            high_intensity_count = 0
            max_intensity_count = 0

            for i in range(1, len(spotlights)):
                prev_point = spotlights[i-1]
                curr_point = spotlights[i]

                distance = self._calculate_distance_meters(
                    prev_point, curr_point)
                time_diff = (curr_point[0] - prev_point[0]) / 1000.0

                if time_diff > 0:
                    speed_mps = distance / time_diff

                    # Filter out unrealistic speeds
                    if speed_mps > self.MAX_REALISTIC_SPEED_MPS:
                        speed_mps = 0  # Treat as stationary

                    if speed_mps < self.WALKING_THRESHOLD:
                        walking_distance += distance
                    elif speed_mps < self.JOGGING_THRESHOLD:
                        jogging_distance += distance
                    elif speed_mps < self.RUNNING_THRESHOLD:
                        running_distance += distance
                    elif speed_mps < self.SPRINTING_THRESHOLD:
                        high_intensity_distance += distance
                        high_intensity_count += 1
                    else:
                        max_intensity_distance += distance
                        max_intensity_count += 1

            return {
                'walking_km': walking_distance / 1000.0,
                'jogging_km': jogging_distance / 1000.0,
                'running_km': running_distance / 1000.0,
                'high_intensity_km': high_intensity_distance / 1000.0,
                'max_intensity_km': max_intensity_distance / 1000.0,
                'high_intensity_count': high_intensity_count,
                'max_intensity_count': max_intensity_count
            }

        except Exception as e:
            logger.exception(f"Error calculating distance zones: {e}")
            return {'walking_km': 0, 'jogging_km': 0, 'running_km': 0, 'high_intensity_km': 0,
                    'max_intensity_km': 0, 'high_intensity_count': 0, 'max_intensity_count': 0}

    def _calculate_acceleration_metrics(self, spotlights: List[List[float]]) -> Dict[str, float]:
        """Calculate acceleration and deceleration metrics"""
        try:
            accelerations = []
            high_accel_count = 0
            high_decel_count = 0
            max_accel_count = 0
            max_decel_count = 0

            high_accel_distance = 0.0
            high_decel_distance = 0.0
            max_accel_distance = 0.0
            max_decel_distance = 0.0

            # Calculate speeds first
            speeds = []
            distances = []

            for i in range(1, len(spotlights)):
                distance = self._calculate_distance_meters(
                    spotlights[i-1], spotlights[i])
                time_diff = (spotlights[i][0] - spotlights[i-1][0]) / 1000.0

                distances.append(distance)

                if time_diff > 0:
                    speed = distance / time_diff
                    speeds.append(speed)
                else:
                    speeds.append(0)

            # Calculate accelerations
            for i in range(1, len(speeds)):
                prev_speed = speeds[i-1]
                curr_speed = speeds[i]

                time_diff = (spotlights[i+1][0] - spotlights[i][0]) / 1000.0
                if time_diff > 0:
                    acceleration = (curr_speed - prev_speed) / time_diff
                    accelerations.append(acceleration)

                    distance_segment = distances[i] if i < len(
                        distances) else 0

                    # Count high intensity accelerations/decelerations
                    if acceleration > self.HIGH_ACCEL_THRESHOLD:
                        high_accel_count += 1
                        high_accel_distance += distance_segment
                    elif acceleration < -self.HIGH_ACCEL_THRESHOLD:
                        high_decel_count += 1
                        high_decel_distance += distance_segment

                    if acceleration > self.MAX_ACCEL_THRESHOLD:
                        max_accel_count += 1
                        max_accel_distance += distance_segment
                    elif acceleration < -self.MAX_ACCEL_THRESHOLD:
                        max_decel_count += 1
                        max_decel_distance += distance_segment

            avg_intensity = sum(abs(a) for a in accelerations) / \
                len(accelerations) if accelerations else 0
            session_intensity = avg_intensity * 20  # Scaled for display
            session_accel_intensity = avg_intensity * 30  # Scaled differently

            return {
                'session_intensity': session_intensity,
                'session_accel_intensity': session_accel_intensity,
                'high_accel_count': high_accel_count,
                'high_decel_count': high_decel_count,
                'max_accel_count': max_accel_count,
                'max_decel_count': max_decel_count,
                'high_accel_distance_km': high_accel_distance / 1000.0,
                'high_decel_distance_km': high_decel_distance / 1000.0,
                'max_accel_distance_m': max_accel_distance,
                'max_decel_distance_m': max_decel_distance
            }

        except Exception as e:
            logger.exception(f"Error calculating acceleration metrics: {e}")
            return {'session_intensity': 0, 'session_accel_intensity': 0, 'high_accel_count': 0,
                    'high_decel_count': 0, 'max_accel_count': 0, 'max_decel_count': 0,
                    'high_accel_distance_km': 0, 'high_decel_distance_km': 0,
                    'max_accel_distance_m': 0, 'max_decel_distance_m': 0}

    def _analyze_football_actions(self, spotlights: List[List[float]]) -> Dict[str, float]:
        """Analyze football-specific movement patterns"""
        try:
            intensities = []
            max_intensity_runs = 0
            current_high_intensity_duration = 0

            for i in range(1, len(spotlights)):
                distance = self._calculate_distance_meters(
                    spotlights[i-1], spotlights[i])
                time_diff = (spotlights[i][0] - spotlights[i-1][0]) / 1000.0

                if time_diff > 0:
                    speed = distance / time_diff
                    intensities.append(speed)

                    if speed > self.HIGH_INTENSITY_THRESHOLD:
                        current_high_intensity_duration += time_diff
                    else:
                        if current_high_intensity_duration > 3.0:  # 3+ seconds of high intensity
                            max_intensity_runs += 1
                        current_high_intensity_duration = 0

            # Handle case where high intensity continues to end
            if current_high_intensity_duration > 3.0:
                max_intensity_runs += 1

            avg_intensity = sum(intensities) / \
                len(intensities) if intensities else 0

            return {
                'avg_intensity': avg_intensity * 10,  # Scaled for display
                'max_intensity_runs': max_intensity_runs
            }

        except Exception as e:
            logger.exception(f"Error analyzing football actions: {e}")
            return {'avg_intensity': 0, 'max_intensity_runs': 0}

    def _estimate_kick_metrics(self, spotlights: List[List[float]], highlights: List[Dict] = None, objects: List[Dict] = None) -> Dict[str, int]:
        """
        Calculate kick metrics from ball tracking data when available

        Args:
            spotlights: Player tracking data [time_off, x, y, w, h]
            highlights: List of highlight objects with tags and object info
            objects: List of tracked objects with type, side, tracking_url

        Note: Kick metrics are only calculated when ball objects are available.
        Without ball data, we return default/empty values.
        """
        try:
            # Check if we have ball tracking data
            has_ball_data = False
            if objects:
                for obj in objects:
                    if obj.get('type') == 'ball':
                        has_ball_data = True
                        break

            # Also check highlights for ball-related events
            if highlights:
                for highlight in highlights:
                    if highlight.get('object_type') == 'ball':
                        has_ball_data = True
                        break

            # If no ball data available, return empty metrics
            if not has_ball_data:
                return {
                    'power_kicks': 0,
                    'high_intensity_kicks': 0,
                    'medium_intensity_kicks': 0,
                    'low_intensity_kicks': 0,
                    'avg_kick_power_kmh': 0,
                    'note': 'No ball tracking data available for kick metrics'
                }

            # TODO: Implement actual ball velocity analysis when ball tracking data is available
            # This would involve:
            # 1. Loading ball tracking data from tracking_url
            # 2. Analyzing ball velocity changes (acceleration/deceleration)
            # 3. Detecting sudden velocity spikes (kicks)
            # 4. Measuring actual kick power from ball speed

            # For now, return placeholder values when ball data exists
            return {
                'power_kicks': 0,
                'high_intensity_kicks': 0,
                'medium_intensity_kicks': 0,
                'low_intensity_kicks': 0,
                'avg_kick_power_kmh': 0,
                'note': 'Ball data available but kick analysis not yet implemented'
            }

        except Exception as e:
            logger.exception(f"Error calculating kick metrics: {e}")
            return {
                'power_kicks': 0,
                'high_intensity_kicks': 0,
                'medium_intensity_kicks': 0,
                'low_intensity_kicks': 0,
                'avg_kick_power_kmh': 0,
                'note': 'Error calculating kick metrics'
            }

    def _analyze_ball_tracking_data(self, ball_tracking_url: str) -> Dict[str, Any]:
        """
        Analyze ball tracking data to calculate actual kick metrics

        Args:
            ball_tracking_url: URL to ball tracking data

        Returns:
            dict: Ball analysis results with kick metrics
        """
        try:
            # TODO: Implement ball tracking data analysis
            # This would involve:
            # 1. Fetching ball tracking data from URL
            # 2. Analyzing ball velocity changes
            # 3. Detecting sudden acceleration (kicks)
            # 4. Measuring actual kick power from ball speed

            # For now, return placeholder data
            return {
                'ball_data_available': True,
                'note': 'Ball tracking analysis not yet implemented'
            }

        except Exception as e:
            logger.exception(f"Error analyzing ball tracking data: {e}")
            return {
                'ball_data_available': False,
                'note': f'Error analyzing ball data: {str(e)}'
            }

    def _estimate_dribbling_metrics(self, spotlights: List[List[float]]) -> Dict[str, float]:
        """Estimate dribbling metrics from movement patterns"""
        try:
            dribble_count = 0
            total_dribble_distance = 0.0

            # Look for periods of controlled movement (moderate speed with direction changes)
            i = 0
            while i < len(spotlights) - 10:  # Need at least 10 points for analysis
                # Check if next 3 seconds show dribbling pattern
                start_time = spotlights[i][0]
                dribble_window = []
                j = i

                # Collect points within 3-second window
                while j < len(spotlights) and (spotlights[j][0] - start_time) <= 3000:
                    dribble_window.append(spotlights[j])
                    j += 1

                if len(dribble_window) >= 5:  # Enough points to analyze
                    if self._is_dribbling_sequence(dribble_window):
                        dribble_count += 1
                        # Calculate distance during this dribble
                        dribble_distance = sum(
                            self._calculate_distance_meters(
                                dribble_window[k], dribble_window[k+1])
                            for k in range(len(dribble_window)-1)
                        )
                        total_dribble_distance += dribble_distance

                        i = j  # Skip past this dribble sequence
                    else:
                        i += 5  # Move forward a bit
                else:
                    i += 5

            return {
                'dribble_count': dribble_count,
                'dribble_distance_m': total_dribble_distance
            }

        except Exception as e:
            logger.exception(f"Error estimating dribbling metrics: {e}")
            return {'dribble_count': 0, 'dribble_distance_m': 0}

    def _is_dribbling_sequence(self, window: List[List[float]]) -> bool:
        """Check if a sequence of points represents dribbling"""
        try:
            speeds = []
            direction_changes = 0

            for i in range(1, len(window)):
                distance = self._calculate_distance_meters(
                    window[i-1], window[i])
                time_diff = (window[i][0] - window[i-1][0]) / 1000.0

                if time_diff > 0:
                    speed = distance / time_diff
                    speeds.append(speed)

            # Check for direction changes
            for i in range(2, len(window)):
                prev_dx = window[i-1][1] - window[i-2][1]
                curr_dx = window[i][1] - window[i-1][1]
                prev_dy = window[i-1][2] - window[i-2][2]
                curr_dy = window[i][2] - window[i-1][2]

                # Detect direction change
                if (prev_dx * curr_dx < 0) or (prev_dy * curr_dy < 0):
                    direction_changes += 1

            avg_speed = sum(speeds) / len(speeds) if speeds else 0

            # Dribbling criteria: moderate speed, multiple direction changes
            return (1.0 < avg_speed < self.DRIBBLE_MAX_SPEED and
                    direction_changes >= 2 and
                    len(window) >= 5)

        except Exception:
            return False

    def _get_speed_at_index(self, spotlights: List[List[float]], index: int) -> float:
        """Get speed at a specific index"""
        try:
            if index <= 0 or index >= len(spotlights):
                return 0.0

            distance = self._calculate_distance_meters(
                spotlights[index-1], spotlights[index])
            time_diff = (spotlights[index][0] -
                         spotlights[index-1][0]) / 1000.0

            return distance / time_diff if time_diff > 0 else 0.0

        except Exception:
            return 0.0

    def _calculate_athletic_skills_score(self, movement_data: Dict, distance_zones: Dict, accel_data: Dict) -> float:
        """Calculate overall athletic skills score (0-10)"""
        try:
            # Weighted scoring
            distance_score = min(
                movement_data['total_distance_km'] / 12.0 * 3, 3)
            speed_score = min(movement_data['max_speed_kmh'] / 35.0 * 3, 3)
            intensity_score = min(
                distance_zones['high_intensity_km'] / 2.0 * 2, 2)
            accel_score = min(accel_data['session_intensity'] / 100.0 * 2, 2)

            total_score = distance_score + speed_score + intensity_score + accel_score
            return min(total_score, 10.0)

        except Exception:
            return 0.0

    def _calculate_football_skills_score(self, movement_data: Dict, kick_metrics: Dict, dribbling_metrics: Dict) -> float:
        """Calculate overall football skills score (0-10)"""
        try:
            movement_score = min(movement_data['avg_speed_mps'] / 5.0 * 3, 3)
            kick_score = min(
                (kick_metrics['power_kicks'] + kick_metrics['high_intensity_kicks']) / 5.0 * 3, 3)
            dribble_score = min(
                dribbling_metrics['dribble_count'] / 10.0 * 2, 2)
            distance_score = min(
                movement_data['total_distance_km'] / 10.0 * 2, 2)

            total_score = movement_score + kick_score + dribble_score + distance_score
            return min(total_score, 10.0)

        except Exception:
            return 0.0

    def _get_empty_athletic_metrics(self) -> Dict[str, str]:
        """Return empty GPS Athletic Skills metrics"""
        return {
            "Play Time": "0 min", "Distance Covered": "0.0 km", "Session Volume": "0.0 km",
            "Top Speed": "0 km/h", "Int. Speed": "0 Km/h", "Walking": "0.0 km",
            "Jogging": "0.0 km", "High Int. Run": "0|0.00 km", "Max Int. Run": "0.0 km",
            "Session Intensity": "0 m", "High Int. Acceleration": "0|0.0 km",
            "High Int. Deceleration": "0|0.0 km", "Max Int. Acceleration": "0|0 m",
            "Max Int. Deceleration": "0|0 m", "Session Int. Acceleration": "0 ",
            "Athletic Skills": "0.0"
        }

    def _get_empty_football_metrics(self) -> Dict[str, str]:
        """Return empty GPS Football Abilities metrics"""
        return {
            "Play Time": "0 min", "Session Volume": "0 ", "Session Intensity": "0 ",
            "Football Skills": 0.0, "Kick Power": "0 km/h", "Power Kicks": "0 ",
            "High Int. Kicks": "0 ", "Med. Int. Kicks": "0 ", "Low Int. Kicks": "0 ",
            "Dribbling": "0|0 m", "Max. Intensity Run": "0 ",
            "Note": "No kick data available"
        }
