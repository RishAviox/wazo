import logging
import requests
import os
import json
from typing import Dict, List, Optional, Any
from django.core.files.storage import default_storage
from django.core.cache import cache
from django.conf import settings
from tracevision.spotlight_metrics_calculator import SpotlightMetricsCalculator

logger = logging.getLogger(__name__)


def _download_tracking_data_from_azure_blob(blob_url: str, cache_key: str = None) -> List[List[float]]:
    """
    Download tracking data from Azure blob URL with caching support.
    In development mode, reads from local file system.

    Args:
        blob_url: Azure blob URL to download tracking data from (or local file path in dev)
        cache_key: Optional cache key for caching the data

    Returns:
        List of tracking data points as [time_ms, x, y, w, h]
    """
    try:
        # Check cache first if cache_key is provided
        if cache_key:
            cached_data = cache.get(cache_key)
            if cached_data is not None:
                return cached_data

        # Check if we're in development mode (local file storage)
        if settings.DEBUG and not hasattr(settings, 'AZURE_CUSTOM_DOMAIN'):
            logger.info(
                f"Development mode detected - reading from local file: {blob_url}")

            # Convert blob URL to local file path
            if blob_url.startswith('/media/'):
                # Remove /media/ prefix and join with MEDIA_ROOT
                local_file_path = os.path.join(
                    settings.MEDIA_ROOT, blob_url[7:])  # Remove '/media/'
            else:
                # Assume it's already a local path
                local_file_path = blob_url

            if os.path.exists(local_file_path):
                with open(local_file_path, 'r') as f:
                    data = json.load(f)

                # Extract spotlights data
                if isinstance(data, dict) and 'spotlights' in data:
                    tracking_data = data['spotlights']
                elif isinstance(data, list):
                    tracking_data = data
                else:
                    logger.warning(
                        f"Unexpected data format in local file {local_file_path}")
                    return []

                # Cache the data if cache_key is provided
                if cache_key and tracking_data:
                    cache.set(cache_key, tracking_data,
                              timeout=3600)  # Cache for 1 hour

                logger.info(
                    f"Successfully loaded {len(tracking_data)} tracking points from local file")
                return tracking_data
            else:
                logger.warning(f"Local file not found: {local_file_path}")
                return []

        # Production mode - download from Azure blob storage
        logger.info(f"Downloading tracking data from Azure blob: {blob_url}")

        # Extract relative path from full blob URL for default_storage operations
        if blob_url.startswith("https://"):
            # Extract relative path from full Azure blob URL
            # URL format: https://videostoragewajo.blob.core.windows.net/media/sessions/...
            # We need: sessions/...
            if "/media/" in blob_url:
                relative_path = blob_url.split("/media/", 1)[1]
            else:
                logger.error(f"Unexpected blob URL format: {blob_url}")
                return []
        else:
            # Already a relative path
            relative_path = blob_url

        logger.info(f"Using relative path for storage operations: {relative_path}")

        # Use Django's default storage to download the file
        if default_storage.exists(relative_path):
            # Read the file content
            with default_storage.open(relative_path, 'r') as f:
                data = json.load(f)

            # Extract spotlights data
            if isinstance(data, dict) and 'spotlights' in data:
                tracking_data = data['spotlights']
            elif isinstance(data, list):
                tracking_data = data
            else:
                logger.warning(f"Unexpected data format in blob {blob_url}")
                return []

            # Cache the data if cache_key is provided
            if cache_key and tracking_data:
                cache.set(cache_key, tracking_data,
                          timeout=3600)  # Cache for 1 hour

            logger.info(
                f"Successfully downloaded {len(tracking_data)} tracking points from Azure blob")
            return tracking_data
        else:
            logger.error(f"Blob file not found: {relative_path} (original URL: {blob_url})")
            return []

    except Exception as e:
        logger.exception(
            f"Error downloading tracking data from {blob_url}: {e}")
        return []


def clear_tracking_data_cache(player_id: str, session_id: str) -> bool:
    """
    Clear cached tracking data for a specific player.

    Args:
        player_id: TracePlayer object_id or player identifier
        session_id: TraceSession session_id

    Returns:
        bool: True if cache was cleared, False otherwise
    """
    try:
        cache_key = f"tracking_data_{session_id}_{player_id}"
        cache.delete(cache_key)
        logger.info(
            f"Cleared tracking data cache for player {player_id} in session {session_id}")
        return True
    except Exception as e:
        logger.exception(f"Error clearing cache for player {player_id}: {e}")
        return False


def clear_session_tracking_data_cache(session_id: str) -> int:
    """
    Clear all cached tracking data for a specific session.

    Args:
        session_id: TraceSession session_id

    Returns:
        int: Number of cache keys cleared
    """
    try:
        # This is a simplified approach - in production you might want to use
        # a more sophisticated cache key pattern matching
        cache_pattern = f"tracking_data_{session_id}_*"
        # Note: Django's cache framework doesn't support pattern deletion by default
        # You might need to implement this differently based on your cache backend
        logger.info(
            f"Cache clearing for session {session_id} would require cache backend support")
        return 0
    except Exception as e:
        logger.exception(f"Error clearing session cache for {session_id}: {e}")
        return 0


def is_tracking_data_available_in_azure(player_obj) -> bool:
    """
    Check if tracking data is available in Azure blob storage for a player.

    Args:
        player_obj: TracePlayer instance

    Returns:
        bool: True if tracking data is available in Azure blob storage
    """
    try:
        # Get tracking data from the player's associated trace object
        trace_object = player_obj.trace_objects.first()
        if not trace_object or not trace_object.tracking_blob_url:
            return False

        # In development mode, check local file system
        if settings.DEBUG and not hasattr(settings, 'AZURE_CUSTOM_DOMAIN'):
            import os

            # Convert blob URL to local file path
            if trace_object.tracking_blob_url.startswith('/media/'):
                # Remove /media/ prefix and join with MEDIA_ROOT
                local_file_path = os.path.join(
                    # Remove '/media/'
                    settings.MEDIA_ROOT, trace_object.tracking_blob_url[7:])
            else:
                # Assume it's already a local path
                local_file_path = trace_object.tracking_blob_url

            exists = os.path.exists(local_file_path)
            return exists

        # Production mode - check Azure blob storage
        # Extract relative path from full blob URL for default_storage operations
        blob_url = trace_object.tracking_blob_url
        if blob_url.startswith("https://"):
            # Extract relative path from full Azure blob URL
            if "/media/" in blob_url:
                relative_path = blob_url.split("/media/", 1)[1]
            else:
                logger.error(f"Unexpected blob URL format: {blob_url}")
                return False
        else:
            # Already a relative path
            relative_path = blob_url
        
        return default_storage.exists(relative_path)

    except Exception as e:
        logger.exception(
            f"Error checking tracking data availability for player {player_obj.object_id}: {e}")
        return False


def count_defensive_actions(highlights: List[Dict]) -> Dict[str, float]:
    """Count defensive actions from highlights using both event types and tags"""
    actions = {
        'blocks': 0, 'tackles_attempted': 0, 'tackles_won': 0, 'clearances': 0,
        'interceptions': 0, 'interventions': 0, 'recoveries': 0,
        'aerial_duels_total': 0, 'aerial_duels_won': 0, 'ground_duels_total': 0,
        'ground_duels_won': 0, 'loose_ball_duels': 0, 'shots_blocked': 0,
        'aerial_clearances': 0, 'defensive_line_support': 0, 'mistakes': 0, 'own_goals': 0
    }

    for highlight in highlights:
        event_type = highlight.get('event_type', '')
        tags = highlight.get('tags', [])
        metadata = highlight.get('event_metadata', {})
        
        # Use both event_type and tags in the same condition
        if event_type == 'tackle' or 'defensive' in tags or 'tackle' in tags:
            actions['tackles_attempted'] += 1
            # Assume successful if tracked (could be improved with metadata)
            actions['tackles_won'] += 1
        elif event_type == 'save' or 'save' in tags:
            actions['shots_blocked'] += 1
        elif event_type == 'foul' or 'foul' in tags:
            # Check if it's a defensive action (could be in metadata)
            if metadata.get('defensive_action', False):
                actions['interventions'] += 1
        
        # Check for specific defensive actions in metadata or tags
        if metadata.get('interception', False) or 'interception' in tags:
            actions['interceptions'] += 1
        if metadata.get('clearance', False) or 'clearance' in tags:
            actions['clearances'] += 1
        if metadata.get('recovery', False) or 'recovery' in tags or 'regain' in tags:
            actions['recoveries'] += 1
        if metadata.get('aerial_duel', False) or 'aerial_duel' in tags:
            actions['aerial_duels_total'] += 1
            if metadata.get('aerial_duel_won', False):
                actions['aerial_duels_won'] += 1
        if metadata.get('ground_duel', False) or 'ground_duel' in tags:
            actions['ground_duels_total'] += 1
            if metadata.get('ground_duel_won', False):
                actions['ground_duels_won'] += 1
        if metadata.get('loose_ball_duel', False) or 'loose_ball_duel' in tags:
            actions['loose_ball_duels'] += 1
        if metadata.get('aerial_clearance', False) or 'aerial_clearance' in tags:
            actions['aerial_clearances'] += 1
        if metadata.get('defensive_line_support', False) or 'defensive_line_support' in tags:
            actions['defensive_line_support'] += 1
        if metadata.get('mistake', False) or 'mistake' in tags:
            actions['mistakes'] += 1
        if metadata.get('own_goal', False) or 'own_goal' in tags:
            actions['own_goals'] += 1

    # Calculate success rates
    actions['tackle_success_rate'] = (
        actions['tackles_won'] / actions['tackles_attempted'] * 100) if actions['tackles_attempted'] > 0 else 0
    actions['aerial_duel_success_rate'] = (
        actions['aerial_duels_won'] / actions['aerial_duels_total'] * 100) if actions['aerial_duels_total'] > 0 else 0
    actions['ground_duel_success_rate'] = (
        actions['ground_duels_won'] / actions['ground_duels_total'] * 100) if actions['ground_duels_total'] > 0 else 0

    return actions


def count_attacking_actions(highlights: List[Dict]) -> Dict[str, int]:
    """Count attacking actions from highlights using both event types and tags"""
    actions = {
        'goals': 0, 'shots': 0, 'assists': 0, 'offsides': 0,
        'key_passes': 0, 'shots_in_pa': 0, 'shots_outside_pa': 0,
        'shots_blocked': 0, 'take_ons': 0, 'crosses': 0,
        'pressure_controls': 0, 'final_third_passes': 0
    }

    for highlight in highlights:
        event_type = highlight.get('event_type', '')
        tags = highlight.get('tags', [])
        metadata = highlight.get('event_metadata', {})
        
        # Use both event_type and tags in the same condition
        if event_type == 'goal' or 'goal' in tags:
            actions['goals'] += 1
        elif event_type == 'shot' or 'shot' in tags:
            actions['shots'] += 1
            # Check if shot is in penalty area (could be in metadata)
            if metadata.get('in_penalty_area', False):
                actions['shots_in_pa'] += 1
            else:
                actions['shots_outside_pa'] += 1
        elif event_type == 'pass' or 'touch-chain' in tags:
            actions['key_passes'] += 1
            # Check if it's a final third pass (could be in metadata)
            if metadata.get('final_third', False):
                actions['final_third_passes'] += 1
        elif event_type == 'offside' or 'offside' in tags:
            actions['offsides'] += 1
        elif event_type == 'foul' or 'foul' in tags:
            # Check if it's a take-on attempt (could be in metadata)
            if metadata.get('take_on', False) or 'dribble' in tags or 'take-on' in tags:
                actions['take_ons'] += 1
        
        # Check for assists in metadata or tags
        if metadata.get('assist', False) or 'assist' in tags:
            actions['assists'] += 1
        
        # Check for crosses in metadata or tags
        if metadata.get('cross', False) or 'cross' in tags:
            actions['crosses'] += 1
        
        # Check for pressure control in metadata
        if metadata.get('pressure_control', False):
            actions['pressure_controls'] += 1

    return actions


def calculate_passing_stats(highlights: List[Dict]) -> Dict[str, float]:
    """
    Estimate passing stats from TraceVision highlights using both event types and tags.
    Pass = change of possession from one player to another within consecutive highlights of the same team.
    """
    completed = 0
    attempted = 0

    # Count passes using both event types and tags
    for highlight in highlights:
        event_type = highlight.get('event_type', '')
        tags = highlight.get('tags', [])
        
        if event_type == 'pass' or 'pass' in tags:
            attempted += 1
            # Assume completed if tracked (could be improved with metadata)
            completed += 1
        elif event_type == 'touch-chain' or 'touch-chain' in tags:
            # Touch chains indicate successful passes
            attempted += 1
            completed += 1

    # If no direct passes found, analyze touch chains for possession changes
    if attempted == 0:
        # Filter for touch-chain highlights (possession sequences)
        chains = [h for h in highlights if "touch-chain" in h.get("tags", [])]

        # Sort chains by start time to ensure chronological order
        chains.sort(key=lambda h: h.get("start_offset", 0))

        prev_player = None
        prev_side = None

        for h in chains:
            objs = h.get("objects", [])
            if not objs:
                continue

            # TraceVision returns objects like [{"object_id": "away_15", "type": "player", ...}]
            player_id = objs[0].get("object_id")
            side = objs[0].get("side")

            # If the same team retained the ball and player changed → count as pass
            if prev_player and prev_side == side:
                if player_id != prev_player:
                    attempted += 1
                    completed += 1  # assume completed since chain continues

            prev_player = player_id
            prev_side = side

    percentage = (completed / attempted * 100) if attempted > 0 else 0.0

    return {
        "completed": completed,
        "attempted": attempted,
        "percentage": round(percentage, 2),
    }


def calculate_game_rating(attacking_actions: Dict, passing_stats: Dict, play_time: int) -> float:
    """Calculate overall game rating for attacking performance"""
    try:
        base_rating = 6.0  # Base rating

        # Add points for positive actions
        base_rating += attacking_actions.get('goals', 0) * 1.0
        base_rating += attacking_actions.get('assists', 0) * 0.8
        base_rating += attacking_actions.get('shots', 0) * 0.2
        base_rating += attacking_actions.get('key_passes', 0) * 0.3

        # Add points for passing accuracy
        if passing_stats['attempted'] > 0:
            passing_bonus = (passing_stats['percentage'] - 70) / 30.0
            base_rating += max(0, passing_bonus * 0.5)

        # Adjust for play time
        if play_time < 45:
            base_rating *= (play_time / 45.0)

        return min(max(base_rating, 1.0), 10.0)

    except Exception:
        return 6.0


def calculate_defensive_game_rating(defensive_actions: Dict, play_time: int) -> float:
    """Calculate game rating for defensive performance"""
    try:
        base_rating = 6.0

        # Add points for defensive actions
        base_rating += defensive_actions.get('tackles_won', 0) * 0.3
        base_rating += defensive_actions.get('interceptions', 0) * 0.4
        base_rating += defensive_actions.get('clearances', 0) * 0.2
        base_rating += defensive_actions.get('recoveries', 0) * 0.1

        # Deduct points for mistakes
        base_rating -= defensive_actions.get('mistakes', 0) * 0.5
        base_rating -= defensive_actions.get('own_goals', 0) * 2.0

        # Adjust for play time
        if play_time < 45:
            base_rating *= (play_time / 45.0)

        return min(max(base_rating, 1.0), 10.0)

    except Exception:
        return 6.0


class TraceVisionMetricsCalculator:
    """
    Service to calculate performance metrics from TraceVision data
    and update corresponding card models
    """

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        # Don't create spotlight_calculator here - create it per session with correct field dimensions

    def clear_player_cache(self, player_obj) -> bool:
        """
        Clear cached tracking data for a specific player.

        Args:
            player_obj: TracePlayer instance for the player

        Returns:
            bool: True if cache was cleared successfully
        """
        try:
            return clear_tracking_data_cache(
                player_obj.object_id,
                player_obj.session.session_id
            )
        except Exception as e:
            self.logger.exception(
                f"Error clearing cache for player {player_obj.object_id}: {e}")
            return False

    def clear_session_cache(self, session) -> int:
        """
        Clear cached tracking data for all players in a session.

        Args:
            session: TraceSession instance

        Returns:
            int: Number of players whose cache was cleared
        """
        try:
            cleared_count = 0
            player_objects = session.trace_players.all()

            for player_obj in player_objects:
                if self.clear_player_cache(player_obj):
                    cleared_count += 1

            self.logger.info(
                f"Cleared cache for {cleared_count}/{player_objects.count()} players in session {session.session_id}")
            return cleared_count

        except Exception as e:
            self.logger.exception(
                f"Error clearing session cache for {session.session_id}: {e}")
            return 0

    def calculate_metrics_for_session(self, session) -> Dict[str, Any]:
        """
        Main method to calculate all metrics for a TraceVision session

        Args:
            session: TraceSession instance

        Returns:
            dict: Results of metric calculations
        """
        try:
            self.logger.info(
                f"Starting metrics calculation for session {session.session_id}")

            results = {
                'success': False,
                'session_id': session.session_id,
                'metrics_calculated': [],
                'errors': []
            }

            # Get all player objects from session
            player_objects = session.trace_players.all()

            if not player_objects.exists():
                results['errors'].append('No player objects found in session')
                return results

            # Process each player
            for player_obj in player_objects:
                try:
                    player_metrics = self._calculate_player_metrics(
                        session, player_obj)
                    if player_metrics:
                        results['metrics_calculated'].append({
                            'object_id': player_obj.object_id,
                            'side': player_obj.team.name if player_obj.team else 'unknown',
                            'metrics': player_metrics
                        })
                except Exception as e:
                    self.logger.exception(
                        f"Error calculating metrics for {player_obj.object_id}: {e}")
                    results['errors'].append(
                        f"Player {player_obj.object_id}: {str(e)}")

            results['success'] = len(results['metrics_calculated']) > 0

            self.logger.info(f"Metrics calculation completed for session {session.session_id}. "
                             f"Processed {len(results['metrics_calculated'])} players")

            return results

        except Exception as e:
            self.logger.exception(
                f"Error in calculate_metrics_for_session: {e}")
            return {
                'success': False,
                'session_id': session.session_id,
                'error': str(e)
            }

    def _calculate_player_metrics(self, session, player_obj) -> Optional[Dict[str, Any]]:
        """
        Calculate all performance metrics for a single player

        Args:
            session: TraceSession instance
            player_obj: TracePlayer instance for the player

        Returns:
            dict: Calculated metrics or None if failed
        """
        try:
            # Get player tracking data
            tracking_data = self._get_player_tracking_data(player_obj)
            if not tracking_data:
                self.logger.warning(
                    f"No tracking data for {player_obj.object_id}")
                return None

            # Get player highlights/events
            player_highlights = self._get_player_highlights(
                session, player_obj)

            # Calculate different metric categories
            gps_athletic_metrics = self._calculate_gps_athletic_skills(
                tracking_data, session)
            gps_football_metrics = self._calculate_gps_football_abilities(
                tracking_data, player_highlights, session)
            attacking_metrics = self._calculate_attacking_skills(
                player_highlights, tracking_data, session)
            defensive_metrics = self._calculate_defensive_skills(
                player_highlights, tracking_data, session)
            disciplinary_metrics = self._count_disciplinary_actions(player_highlights)
            rpe_metrics = self._calculate_rpe_metrics(
                tracking_data, player_highlights, session)

            # Determine match duration for context
            match_duration = self._estimate_match_duration(session)

            data = {
                'gps_athletic_skills': gps_athletic_metrics,
                'gps_football_abilities': gps_football_metrics,
                'attacking_skills': attacking_metrics,
                'defensive_skills': defensive_metrics,
                'disciplinary_actions': disciplinary_metrics,
                'rpe_metrics': rpe_metrics,
                'match_duration_minutes': match_duration,
                'tracking_data_points': len(tracking_data)
            }

            logger.info(f"Calculate Player Metrics: {data}")
            return data

        except Exception as e:
            self.logger.exception(
                f"Error calculating player metrics for {player_obj.object_id}: {e}")
            return None

    def _get_player_tracking_data(self, player_obj) -> List[List[float]]:
        """
        Extract tracking data for a player from TracePlayer using Azure blob storage with caching.

        Returns:
            list: Tracking data points as [time_ms, x, y, w, h]
        """
        try:
            # Generate cache key for this player's tracking data
            cache_key = f"tracking_data_{player_obj.session.session_id}_{player_obj.object_id}"

            # Get tracking data from the player's associated trace object
            trace_object = player_obj.trace_objects.first()
            if not trace_object:
                self.logger.warning(
                    f"No trace object found for player {player_obj.object_id}")
                return []

            # First, try to get from Azure blob URL (preferred method)
            if trace_object.tracking_blob_url:
                return _download_tracking_data_from_azure_blob(
                    trace_object.tracking_blob_url,
                    cache_key
                )

            # Fallback to original tracking_url if blob URL is not available
            elif trace_object.tracking_url:
                self.logger.warning(
                    f"Using fallback tracking_url for {player_obj.object_id} - blob URL not available")
                return self._fetch_tracking_data_from_url(trace_object.tracking_url, cache_key=cache_key)

            else:
                self.logger.warning(
                    f"No tracking data available for {player_obj.object_id}")
            return []

        except Exception as e:
            self.logger.exception(
                f"Error getting tracking data for {player_obj.object_id}: {e}")
            return []

    def _fetch_tracking_data_from_url(self, tracking_url: str, timeout: int = 10, cache_key: str = None) -> List[List[float]]:
        """
        Fetch tracking data from URL as fallback with optional caching
        """
        try:
            # Check cache first if cache_key is provided
            if cache_key:
                cached_data = cache.get(cache_key)
                if cached_data is not None:
                    return cached_data

            self.logger.info(
                f"Fetching tracking data from URL: {tracking_url}")
            response = requests.get(tracking_url, timeout=timeout)
            response.raise_for_status()
            data = response.json()

            tracking_data = []
            if isinstance(data, dict) and 'spotlights' in data:
                tracking_data = data['spotlights']
            elif isinstance(data, list):
                tracking_data = data

            # Cache the data if cache_key is provided
            if cache_key and tracking_data:
                cache.set(cache_key, tracking_data,
                          timeout=3600)  # Cache for 1 hour

            return tracking_data

        except Exception as e:
            self.logger.exception(
                f"Error fetching tracking data from {tracking_url}: {e}")
            return []

    def _get_player_highlights(self, session, player_obj) -> List[Dict]:
        """
        Get all highlights/events involving a specific player using efficient Django queries
        """
        try:
            # Use Django ORM to get highlights where this player is involved
            highlights_queryset = session.highlights.filter(
                highlight_objects__player=player_obj
            ).select_related('player').prefetch_related('highlight_objects__player__team').distinct()

            highlights = []
            for highlight in highlights_queryset:
                # Get all players involved in this highlight
                highlight_objects = highlight.highlight_objects.select_related('player__team').all()
                
                highlights.append({
                    'highlight_id': highlight.highlight_id,
                    'start_offset': highlight.start_offset,
                    'duration': highlight.duration,
                    'tags': highlight.tags or [],
                    'video_id': highlight.video_id,
                    'event_type': highlight.event_type,
                    'source': highlight.source,
                    'match_time': highlight.match_time,
                    'half': highlight.half,
                    'event_metadata': highlight.event_metadata or {},
                    'performance_impact': highlight.performance_impact,
                    'team_impact': highlight.team_impact,
                    'video_stream': highlight.video_stream,
                    'objects': [{
                        'object_id': ho.player.object_id if ho.player else 'unknown',
                        'side': ho.player.team.name if ho.player and ho.player.team else 'unknown',
                        'type': 'player',
                        'player_name': ho.player.name if ho.player else 'unknown'
                    } for ho in highlight_objects]
                })

            return highlights

        except Exception as e:
            self.logger.exception(
                f"Error getting player highlights for {player_obj.object_id}: {e}")
            return []

    def get_player_highlights_queryset(self, session, player_obj):
        """
        Get highlights queryset for a specific player - can be used for further filtering
        
        Args:
            session: TraceSession instance
            player_obj: TracePlayer instance
            
        Returns:
            QuerySet: Filtered highlights queryset
        """
        try:
            return session.highlights.filter(
                highlight_objects__player=player_obj
            ).select_related('player').prefetch_related('highlight_objects__player__team').distinct()
        except Exception as e:
            self.logger.exception(f"Error getting highlights queryset for {player_obj.object_id}: {e}")
            return session.highlights.none()

    def get_player_highlights_by_event_type(self, session, player_obj, event_type):
        """
        Get highlights for a specific player filtered by event type
        
        Args:
            session: TraceSession instance
            player_obj: TracePlayer instance
            event_type: Event type to filter by (e.g., 'goal', 'yellow_card', 'red_card')
            
        Returns:
            QuerySet: Filtered highlights queryset
        """
        try:
            return self.get_player_highlights_queryset(session, player_obj).filter(
                event_type=event_type
            )
        except Exception as e:
            self.logger.exception(f"Error getting {event_type} highlights for {player_obj.object_id}: {e}")
            return session.highlights.none()

    def get_player_highlights_by_time_range(self, session, player_obj, start_minute=None, end_minute=None):
        """
        Get highlights for a specific player filtered by time range
        
        Args:
            session: TraceSession instance
            player_obj: TracePlayer instance
            start_minute: Start minute filter (optional)
            end_minute: End minute filter (optional)
            
        Returns:
            QuerySet: Filtered highlights queryset
        """
        try:
            queryset = self.get_player_highlights_queryset(session, player_obj)
            
            if start_minute is not None:
                # Convert minute to milliseconds for start_offset comparison
                start_offset = start_minute * 60 * 1000
                queryset = queryset.filter(start_offset__gte=start_offset)
            
            if end_minute is not None:
                # Convert minute to milliseconds for start_offset comparison
                end_offset = end_minute * 60 * 1000
                queryset = queryset.filter(start_offset__lte=end_offset)
            
            return queryset
        except Exception as e:
            self.logger.exception(f"Error getting time-filtered highlights for {player_obj.object_id}: {e}")
            return session.highlights.none()

    def _calculate_gps_athletic_skills(self, tracking_data: List[List[float]], session) -> Dict[str, str]:
        """
        Calculate GPS Athletic Skills metrics from movement data
        """
        try:
            if not tracking_data or len(tracking_data) < 2:
                # Create calculator with session field dimensions for empty metrics
                spotlight_calculator = SpotlightMetricsCalculator.from_trace_session(
                    session)
                return spotlight_calculator._get_empty_athletic_metrics()

            # Create calculator with session field dimensions
            spotlight_calculator = SpotlightMetricsCalculator.from_trace_session(
                session)

            # Use the specialized spotlight calculator for better accuracy
            return spotlight_calculator.calculate_gps_athletic_skills(tracking_data)

        except Exception as e:
            self.logger.exception(
                f"Error calculating GPS athletic skills: {e}")
            # Create calculator with session field dimensions for empty metrics
            spotlight_calculator = SpotlightMetricsCalculator.from_trace_session(
                session)
            return spotlight_calculator._get_empty_athletic_metrics()

    def _calculate_gps_football_abilities(self, tracking_data: List[List[float]], highlights: List[Dict], session) -> Dict[str, str]:
        """
        Calculate GPS Football Abilities metrics

        Args:
            tracking_data: Player tracking data [time_ms, x, y, w, h]
            highlights: List of highlight objects with tags and object info
            session: TraceSession instance for field dimensions
        """
        try:
            if not tracking_data:
                # Create calculator with session field dimensions for empty metrics
                spotlight_calculator = SpotlightMetricsCalculator.from_trace_session(
                    session)
                return spotlight_calculator._get_empty_football_metrics()

            # Extract objects from highlights to check for ball tracking data
            objects = []
            if highlights:
                for highlight in highlights:
                    if 'object_id' in highlight and 'object_type' in highlight:
                        objects.append({
                            'type': highlight.get('object_type'),
                            'side': highlight.get('side'),
                            'tracking_url': highlight.get('tracking_url')
                        })

            # Create calculator with session field dimensions
            spotlight_calculator = SpotlightMetricsCalculator.from_trace_session(
                session)

            return spotlight_calculator.calculate_gps_football_abilities(tracking_data, highlights, objects)

        except Exception as e:
            self.logger.exception(
                f"Error calculating GPS football abilities: {e}")
            # Create calculator with session field dimensions for empty metrics
            spotlight_calculator = SpotlightMetricsCalculator.from_trace_session(
                session)
            return spotlight_calculator._get_empty_football_metrics()

    def _calculate_attacking_skills(self, highlights: List[Dict], tracking_data: List[List[float]], session) -> Dict[str, str]:
        """
        Calculate Attacking Skills metrics from highlights and events using both event types and tags

        Expected format:
        {"Goals": "0", "Shots": "0", "Assists": "0", "Passing": "9/19 (47%)", ...}
        """
        try:
            # Count different types of attacking actions from highlights using both event types and tags
            attacking_actions = self._count_attacking_actions(highlights)

            # Calculate passing statistics using both event types and tags
            passing_stats = self._calculate_passing_stats(highlights, session)

            # Estimate play time
            play_time_minutes = self._estimate_player_play_time(tracking_data)
            total_match_time = self._estimate_match_duration(session)

            # Calculate game rating (simplified)
            game_rating = calculate_game_rating(
                attacking_actions, passing_stats, play_time_minutes)

            metrics = {
                "Goals": str(attacking_actions.get('goals', 0)),
                "Shots": str(attacking_actions.get('shots', 0)),
                "Assists": str(attacking_actions.get('assists', 0)),
                "Offside": str(attacking_actions.get('offsides', 0)),
                "Key Passes": str(attacking_actions.get('key_passes', 0)),
                "Shots in PA": str(attacking_actions.get('shots_in_pa', 0)),
                "Shots Outside PA": str(attacking_actions.get('shots_outside_pa', 0)),
                "Shots Blocked": str(attacking_actions.get('shots_blocked', 0)),
                "Take-ons": str(attacking_actions.get('take_ons', 0)),
                "Crossing": str(attacking_actions.get('crosses', 0)),
                "Control Under Pressure": str(attacking_actions.get('pressure_controls', 0)),
                "Passing": f"{passing_stats['completed']}/{passing_stats['attempted']} ({passing_stats['percentage']:.0f}%)" if passing_stats['attempted'] > 0 else "0/0 (0%)",
                "Final 1/3 Pass": str(attacking_actions.get('final_third_passes', 0)),
                "Play Time": f"{play_time_minutes}/{total_match_time} min",
                "Game Rating": f"{game_rating:.1f}"
            }

            return metrics

        except Exception as e:
            self.logger.exception(f"Error calculating attacking skills: {e}")
            return self._get_empty_attacking_metrics()

    def _calculate_defensive_skills(self, highlights: List[Dict], tracking_data: List[List[float]], session) -> Dict[str, str]:
        """
        Calculate Video Card Defensive metrics using both event types and tags

        Expected format:
        {"Blocks": "0", "Tackles": "1/1 (100%)", "Clearances": "0", ...}
        """
        try:
            # Count defensive actions from highlights using both event types and tags
            defensive_actions = count_defensive_actions(highlights)

            # Calculate defensive passing stats using both event types and tags
            defensive_passing = calculate_passing_stats(highlights)

            # Estimate play time
            play_time_minutes = self._estimate_player_play_time(tracking_data)
            total_match_time = self._estimate_match_duration(session)

            # Calculate game rating
            game_rating = calculate_defensive_game_rating(
                defensive_actions, play_time_minutes)

            metrics = {
                "Blocks": str(defensive_actions.get('blocks', 0)),
                "Tackles": f"{defensive_actions.get('tackles_won', 0)}/{defensive_actions.get('tackles_attempted', 0)} ({defensive_actions.get('tackle_success_rate', 0):.0f}%)" if defensive_actions.get('tackles_attempted', 0) > 0 else "0/0 (0%)",
                "Clearances": str(defensive_actions.get('clearances', 0)),
                "Interceptions": str(defensive_actions.get('interceptions', 0)),
                "Interventions": str(defensive_actions.get('interventions', 0)),
                "Recoveries": str(defensive_actions.get('recoveries', 0)),
                "Aerial Duels": f"{defensive_actions.get('aerial_duels_won', 0)}/{defensive_actions.get('aerial_duels_total', 0)} ({defensive_actions.get('aerial_duel_success_rate', 0):.0f}%)" if defensive_actions.get('aerial_duels_total', 0) > 0 else "0/0 (0%)",
                "Ground Duels": f"{defensive_actions.get('ground_duels_won', 0)}/{defensive_actions.get('ground_duels_total', 0)} ({defensive_actions.get('ground_duel_success_rate', 0):.0f}%)" if defensive_actions.get('ground_duels_total', 0) > 0 else "0/0 (0%)",
                "Loose Ball Duels": str(defensive_actions.get('loose_ball_duels', 0)),
                "Shots Blocked": str(defensive_actions.get('shots_blocked', 0)),
                "Aerial Clearances": str(defensive_actions.get('aerial_clearances', 0)),
                "Defensive Area Passes": f"{defensive_passing['completed']}/{defensive_passing['attempted']} ({defensive_passing['percentage']:.0f}%)" if defensive_passing['attempted'] > 0 else "0/0 (0%)",
                "Defensive Line Support": str(defensive_actions.get('defensive_line_support', 0)),
                "Mistakes": str(defensive_actions.get('mistakes', 0)),
                "Own Goals": str(defensive_actions.get('own_goals', 0)),
                "Play time": f"{play_time_minutes}/{total_match_time} min",
                "Game Rating": f"{game_rating:.1f}"
            }

            return metrics

        except Exception as e:
            self.logger.exception(f"Error calculating defensive skills: {e}")
            return self._get_empty_defensive_metrics()

    def _calculate_rpe_metrics(self, tracking_data: List[List[float]], highlights: List[Dict], session=None) -> Dict[str, str]:
        """
        Calculate RPE (Rate of Perceived Exertion) metrics based on activity intensity

        Expected format:
        {"Fatigue": "100.0", "Recovery": "20.0", "Intensity": "100.0", "Readiness": "54.0"}
        """
        try:
            if not tracking_data:
                return {"Fatigue": "0.0", "Recovery": "0.0", "Intensity": "0.0", "Readiness": "0.0"}

            # Create spotlight calculator with session field dimensions
            if session:
                spotlight_calculator = SpotlightMetricsCalculator.from_trace_session(
                    session)
            else:
                spotlight_calculator = SpotlightMetricsCalculator()

            # Use SpotlightMetricsCalculator for movement analysis
            movement_data = spotlight_calculator._analyze_movement(
                tracking_data)
            distance_zones = spotlight_calculator._calculate_distance_zones(
                tracking_data)
            acceleration_data = spotlight_calculator._calculate_acceleration_metrics(
                tracking_data)

            # Calculate intensity metrics from movement
            intensity_metrics = self._calculate_intensity_from_movement(
                tracking_data, movement_data, distance_zones, acceleration_data)

            # Estimate fatigue based on high-intensity periods and duration
            fatigue_score = self._estimate_fatigue_score(
                tracking_data, intensity_metrics)

            # Estimate recovery based on low-intensity periods
            recovery_score = self._estimate_recovery_score(
                tracking_data, intensity_metrics)

            # Overall intensity score
            intensity_score = intensity_metrics['overall_intensity_score']

            # Calculate readiness as combination of other factors
            readiness_score = self._calculate_readiness_score(
                fatigue_score, recovery_score, intensity_score)

            return {
                "Fatigue": f"{fatigue_score:.1f}",
                "Recovery": f"{recovery_score:.1f}",
                "Intensity": f"{intensity_score:.1f}",
                "Readiness": f"{readiness_score:.1f}"
            }

        except Exception as e:
            self.logger.exception(f"Error calculating RPE metrics: {e}")
            return {"Fatigue": "0.0", "Recovery": "0.0", "Intensity": "0.0", "Readiness": "0.0"}

    def _calculate_intensity_from_movement(self, tracking_data: List[List[float]], movement_data: Dict, distance_zones: Dict, acceleration_data: Dict) -> Dict[str, float]:
        """Calculate intensity metrics using SpotlightMetricsCalculator data"""
        try:
            # Use the data already calculated by SpotlightMetricsCalculator
            overall_intensity_score = acceleration_data.get(
                'session_accel_intensity', 0)

            # Calculate intensity based on high-intensity movement
            high_intensity_ratio = distance_zones.get(
                'high_intensity_km', 0) / max(movement_data.get('total_distance_km', 1), 1)
            max_intensity_ratio = distance_zones.get(
                'max_intensity_km', 0) / max(movement_data.get('total_distance_km', 1), 1)

            return {
                'overall_intensity_score': overall_intensity_score,
                'high_intensity_ratio': high_intensity_ratio,
                'max_intensity_ratio': max_intensity_ratio,
                'avg_speed_mps': movement_data.get('avg_speed_mps', 0),
                'max_speed_mps': movement_data.get('max_speed_mps', 0)
            }

        except Exception as e:
            self.logger.exception(
                f"Error calculating intensity from movement: {e}")
            return {'overall_intensity_score': 0, 'high_intensity_ratio': 0, 'max_intensity_ratio': 0, 'avg_speed_mps': 0, 'max_speed_mps': 0}

    def _estimate_fatigue_score(self, tracking_data: List[List[float]], intensity_metrics: Dict) -> float:
        """Estimate fatigue score based on intensity and duration"""
        try:
            if not tracking_data:
                return 0.0

            # Calculate fatigue based on high-intensity periods
            high_intensity_ratio = intensity_metrics.get(
                'high_intensity_ratio', 0)
            max_intensity_ratio = intensity_metrics.get(
                'max_intensity_ratio', 0)

            # Fatigue increases with high-intensity activity
            fatigue_score = (high_intensity_ratio * 60) + \
                (max_intensity_ratio * 40)

            # Cap at 100
            return min(fatigue_score, 100.0)

        except Exception as e:
            self.logger.exception(f"Error estimating fatigue score: {e}")
            return 0.0

    def _estimate_recovery_score(self, tracking_data: List[List[float]], intensity_metrics: Dict) -> float:
        """Estimate recovery score based on low-intensity periods"""
        try:
            if not tracking_data:
                return 0.0

            # Recovery is inverse to fatigue
            fatigue_score = self._estimate_fatigue_score(
                tracking_data, intensity_metrics)
            recovery_score = max(0, 100 - fatigue_score)

            return recovery_score

        except Exception as e:
            self.logger.exception(f"Error estimating recovery score: {e}")
            return 0.0

    def _calculate_readiness_score(self, fatigue_score: float, recovery_score: float, intensity_score: float) -> float:
        """Calculate readiness score as combination of other factors"""
        try:
            recovery_factor = recovery_score / 100.0
            # Cap intensity factor
            intensity_factor = min(intensity_score / 100.0, 1.0)

            # Formula: (recovery * 0.7) + (intensity * 0.3)
            readiness_score = (recovery_factor * 70) + (intensity_factor * 30)

            return min(readiness_score, 100.0)

        except Exception as e:
            self.logger.exception(f"Error calculating readiness score: {e}")
            return 0.0

    def _estimate_match_duration(self, session) -> int:
        """Estimate total match duration in minutes"""
        try:
            # Default to 90 minutes if we can't determine
            if hasattr(session, 'duration_minutes'):
                return session.duration_minutes

            # Try to infer from tracking data timestamps
            max_time_ms = 0
            for player_obj in session.trace_players.all():
                # Get tracking data using the proper method
                tracking_data = self._get_player_tracking_data(player_obj)
                if tracking_data and len(tracking_data) > 0:
                    last_time = tracking_data[-1][0]
                    max_time_ms = max(max_time_ms, last_time)

            if max_time_ms > 0:
                return int(max_time_ms / (1000 * 60))  # Convert to minutes

            return 90  # Default match duration

        except Exception as e:
            self.logger.exception(f"Error estimating match duration: {e}")
            return 90

    def _estimate_player_play_time(self, tracking_data: List[List[float]]) -> int:
        """Estimate how long player was on field based on tracking data"""
        try:
            if not tracking_data or len(tracking_data) < 2:
                return 0

            total_time_ms = tracking_data[-1][0] - tracking_data[0][0]
            return int(total_time_ms / (1000 * 60))  # Convert to minutes

        except Exception as e:
            self.logger.exception(f"Error estimating player play time: {e}")
            return 0

    def _get_empty_attacking_metrics(self) -> Dict[str, str]:
        """Return empty Attacking Skills metrics"""
        return {
            "Goals": "0", "Shots": "0", "Assists": "0", "Offside": "0",
            "Key Passes": "0", "Shots in PA": "0", "Shots Outside PA": "0",
            "Shots Blocked": "0", "Take-ons": "0", "Crossing": "0",
            "Control Under Pressure": "0", "Passing": "0/0 (0%)",
            "Final 1/3 Pass": "0", "Play Time": "0/90 min", "Game Rating": "0.0"
        }

    def _get_empty_defensive_metrics(self) -> Dict[str, str]:
        """Return empty Defensive Skills metrics"""
        return {
            "Blocks": "0", "Tackles": "0/0 (0%)", "Clearances": "0",
            "Interceptions": "0", "Interventions": "0", "Recoveries": "0",
            "Aerial Duels": "0/0 (0%)", "Ground Duels": "0/0 (0%)",
            "Loose Ball Duels": "0", "Shots Blocked": "0", "Aerial Clearances": "0",
            "Defensive Area Passes": "0/0 (0%)", "Defensive Line Support": "0",
            "Mistakes": "0", "Own Goals": "0", "Play time": "0/90 min", "Game Rating": "0.0"
        }


    def _count_attacking_actions(self, highlights: List[Dict]) -> Dict[str, int]:
        """Count attacking actions from highlights using both event types and tags"""
        actions = {
            'goals': 0, 'shots': 0, 'assists': 0, 'offsides': 0,
            'key_passes': 0, 'shots_in_pa': 0, 'shots_outside_pa': 0,
            'shots_blocked': 0, 'take_ons': 0, 'crosses': 0,
            'pressure_controls': 0, 'final_third_passes': 0
        }

        for highlight in highlights:
            event_type = highlight.get('event_type', '')
            tags = highlight.get('tags', [])
            metadata = highlight.get('event_metadata', {})
            
            # Count goals - check both event_type and tags
            if event_type == 'goal' or 'goal' in tags:
                actions['goals'] += 1
                self.logger.info(f"Goal found: event_type={event_type}, tags={tags}, metadata={metadata}")
            
            # Count shots
            elif event_type == 'shot' or 'shot' in tags:
                actions['shots'] += 1
                # Check if shot is in penalty area
                if metadata.get('in_penalty_area', False):
                    actions['shots_in_pa'] += 1
                else:
                    actions['shots_outside_pa'] += 1
            
            # Count assists
            elif metadata.get('assist', False) or 'assist' in tags:
                actions['assists'] += 1
            
            # Count offsides
            elif event_type == 'offside' or 'offside' in tags:
                actions['offsides'] += 1
            
            # Count key passes
            elif event_type == 'pass' or 'key_pass' in tags or 'pass' in tags:
                actions['key_passes'] += 1
                # Check if it's a final third pass
                if metadata.get('final_third', False) or 'final_third' in tags:
                    actions['final_third_passes'] += 1
            
            # Count take-ons/dribbles
            elif event_type == 'dribble' or 'take_on' in tags or 'dribble' in tags:
                actions['take_ons'] += 1
            
            # Count crosses
            elif event_type == 'cross' or 'cross' in tags:
                actions['crosses'] += 1
            
            # Count pressure controls
            elif metadata.get('pressure_control', False) or 'pressure_control' in tags:
                actions['pressure_controls'] += 1
            
            # Count shots blocked (defensive action but tracked in attacking highlights)
            elif event_type == 'save' or 'shot_blocked' in tags:
                actions['shots_blocked'] += 1

        self.logger.info(f"Attacking actions counted: {actions}")
        return actions

    def _calculate_passing_stats(self, highlights: List[Dict], session) -> Dict[str, int]:
        """Calculate passing statistics from highlights using both event types and tags"""
        completed = 0
        attempted = 0

        for highlight in highlights:
            event_type = highlight.get('event_type', '')
            tags = highlight.get('tags', [])
            metadata = highlight.get('event_metadata', {})
            
            # Count passes - check both event_type and tags
            if event_type == 'pass' or 'pass' in tags or 'touch-chain' in tags:
                attempted += 1
                # Assume completed if tracked (could be improved with metadata)
                completed += 1
                self.logger.info(f"Pass found: event_type={event_type}, tags={tags}")
            
            # Count touch chains as successful passes
            elif event_type == 'touch-chain' or 'touch-chain' in tags:
                attempted += 1
                completed += 1

        percentage = (completed / attempted * 100) if attempted > 0 else 0
        self.logger.info(f"Passing stats: {completed}/{attempted} ({percentage:.1f}%)")

        return {
            'completed': completed,
            'attempted': attempted,
            'percentage': percentage
        }

    def _count_disciplinary_actions(self, highlights: List[Dict]) -> Dict[str, int]:
        """Count disciplinary actions (cards) from highlights"""
        actions = {
            'yellow_cards': 0,
            'red_cards': 0,
            'total_cards': 0
        }

        for highlight in highlights:
            event_type = highlight.get('event_type', '')
            tags = highlight.get('tags', [])
            metadata = highlight.get('event_metadata', {})
            
            # Count cards - check both event_type and tags
            if event_type == 'card' or 'card' in tags or 'yellow_card' in tags or 'red_card' in tags:
                actions['total_cards'] += 1
                
                # Check card type from event_type, tags, or metadata
                if event_type == 'yellow_card' or 'yellow' in tags or metadata.get('card_type', '').lower() == 'yellow':
                    actions['yellow_cards'] += 1
                    self.logger.info(f"Yellow card found: event_type={event_type}, tags={tags}, metadata={metadata}")
                elif event_type == 'red_card' or 'red' in tags or metadata.get('card_type', '').lower() == 'red':
                    actions['red_cards'] += 1
                    self.logger.info(f"Red card found: event_type={event_type}, tags={tags}, metadata={metadata}")
                else:
                    # Default to yellow if type is unclear
                    actions['yellow_cards'] += 1
                    self.logger.info(f"Card found (defaulting to yellow): event_type={event_type}, tags={tags}, metadata={metadata}")

        self.logger.info(f"Disciplinary actions counted: {actions}")
        return actions
