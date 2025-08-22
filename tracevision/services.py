import logging
import requests
from datetime import datetime, timedelta
from django.core.cache import cache
from django.conf import settings
from django.db import models

logger = logging.getLogger(__name__)



class TraceVisionService:
    """
    Service layer for TraceVision API operations and caching.
    Handles all external API calls and caching logic.
    """


    def __init__(self):
        self.customer_id = int(settings.TRACEVISION_CUSTOMER_ID)
        self.api_key = settings.TRACEVISION_API_KEY
        self.graphql_url = settings.TRACEVISION_GRAPHQL_URL


        # Cache timeouts
        self.status_cache_timeout = getattr(
            settings, 'TRACEVISION_STATUS_CACHE_TIMEOUT', 300)
        self.result_cache_timeout = getattr(
            settings, 'TRACEVISION_RESULT_CACHE_TIMEOUT', 1800)

    def get_session_status(self, session, force_refresh=False):
        """
        Get session status with caching support.

        Args:
            session: TraceSession instance
            force_refresh: Whether to bypass cache

        Returns:
            dict: Status data or None if failed
        """
        if force_refresh:
            logger.info(
                f"Force refreshing cache for session {session.session_id}")
            self._clear_cache_for_session(session.session_id)
        else:
            # Check cache first
            cached_data = self._get_cached_status_data(session.session_id)
            if cached_data:
                logger.info(
                    f"Using cached status data for session {session.session_id}")
                return cached_data

        # Fetch from API
        logger.info(
            f"Fetching status from TraceVision API for session {session.session_id}")
        status_data = self._query_tracevision_status(session)

        if status_data:
            # Cache the response
            self._cache_status_data(session.session_id, status_data)
            return status_data

        return None

    def get_session_result(self, session):
        """
        Get session result data with caching support.

        Args:
            session: TraceSession instance

        Returns:
            dict: Result data or None if failed
        """
        # Check cache first
        cached_result = self._get_cached_result_data(session.session_id)
        if cached_result:
            logger.info(
                f"Using cached result data for session {session.session_id}")
            return cached_result

        # Fetch from API
        logger.info(
            f"Fetching result from TraceVision API for session {session.session_id}")
        result_data = self._fetch_session_result(session)

        if result_data:
            # Cache the result
            self._cache_result_data(session.session_id, result_data)
            return result_data

        return None

    def _get_cached_status_data(self, session_id):
        """Get cached status data for a session."""
        cache_key = f"tracevision_status_{session_id}"
        cached_data = cache.get(cache_key)

        if cached_data:
            # Check if cache is still valid
            cache_timestamp = datetime.fromisoformat(
                cached_data.get('cache_timestamp', '1970-01-01T00:00:00'))
            if datetime.now() - cache_timestamp < timedelta(seconds=self.status_cache_timeout):
                cached_data['cached'] = True
                return cached_data

        return None

    def _cache_status_data(self, session_id, data):
        """Cache status data for a session."""
        cache_key = f"tracevision_status_{session_id}"
        cache.set(cache_key, data, self.status_cache_timeout)
        logger.info(
            f"Cached status data for session {session_id} with TTL {self.status_cache_timeout}s")

    def _get_cached_result_data(self, session_id):
        """Get cached result data for a session."""
        cache_key = f"tracevision_result_{session_id}"
        return cache.get(cache_key)

    def _cache_result_data(self, session_id, data):
        """Cache result data for a session."""
        cache_key = f"tracevision_result_{session_id}"
        cache.set(cache_key, data, self.result_cache_timeout)
        logger.info(
            f"Cached result data for session {session_id} with TTL {self.result_cache_timeout}s")

    def _clear_cache_for_session(self, session_id):
        """Clear all cached data for a specific session."""
        # Clear status cache
        status_cache_key = f"tracevision_status_{session_id}"
        cache.delete(status_cache_key)

        # Clear result cache
        result_cache_key = f"tracevision_result_{session_id}"
        cache.delete(result_cache_key)

        logger.info(f"Cleared all cache for session {session_id}")

    def _query_tracevision_status(self, session):
        """Query TraceVision API for session status update."""
        try:
            status_payload = {
                "query": """
                    query ($token: CustomerToken!, $session_id: Int!) {
                        session(token: $token, session_id: $session_id) {
                            session_id type status
                        }
                    }
                """,
                "variables": {
                    "token": {"customer_id": self.customer_id, "token": self.api_key},
                    "session_id": int(session.session_id),
                },
            }

            res = requests.post(self.graphql_url, headers={
                                "Content-Type": "application/json"}, json=status_payload)

            if res.status_code != 200:
                logger.info(
                    f"Failed to retrieve status for session {session.session_id}: {res.status_code}")
                return None

            # logger.info(f"Status data: {res.json()}")
            # Save the res.json() response to a file in the root directory with the session_response_id
            # import os
            # import json

            # --------------------Use only for local testing --------------
            # try:
            #     response_json = res.json()
            #     session_response_id = session.session_id
            #     filename = f"tracevision_session_{session_response_id}.json"
            #     root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            #     file_path = os.path.join(root_dir, filename)
            #     with open(file_path, "w", encoding="utf-8") as f:
            #         json.dump(response_json, f, ensure_ascii=False, indent=2)
            #     logger.info(f"Saved TraceVision session response to {file_path}")
            # except Exception as e:
            #     logger.exception(f"Failed to save TraceVision session response for session {session.session_id}: {e}")
            # --------------------Use only for local testing--------------

            data = res.json().get("data", {}).get("session", {})

            if not data.get("status"):
                logger.error(
                    f"No status data returned for session {session.session_id}")
                return None

            return data

        except Exception as e:
            logger.exception(
                f"Error querying TraceVision status for session {session.session_id}: {e}")
            return None

    def _fetch_session_result(self, session):
        """Fetch session result data from TraceVision API."""

        """
            query GetFullSessionResult($sessionId: ID!) {  
                sessionResult(session_id: $sessionId) {  
                    highlights {  
                    highlight_id  
                    video_id  
                    start_offset  
                    duration  
                    side  
                    tags  
                    objects {  
                        object_id  
                        type  
                        side  
                    }  
                    video_stream  
                    }  
                    objects {  
                    object_id  
                    type  
                    side  
                    tracking_url  
                    }  
                }  
            } 
        """
        try:
            result_payload = {
                "query": """
                    query ($token: CustomerToken!, $session_id: Int!) {
                        sessionResult(token: $token, session_id: $session_id) {
                            highlights {
                                highlight_id
                                video_id
                                start_offset
                                duration
                                objects {
                                    object_id
                                    type
                                    side
                                    appearance_fv
                                    color_fv
                                    tracking_url
                                    role
                                }
                                tags
                                video_stream
                            }
                            objects {
                                object_id
                                type
                                side
                                appearance_fv
                                color_fv
                                role
                                tracking_url
                            }
                            events {
                                event_id
                                start_time
                                event_time
                                end_time
                                type
                                bbox {
                                    x
                                    y
                                }
                                longitude
                                latitude
                                objects {
                                    object_id
                                    type
                                    side
                                    appearance_fv
                                    color_fv
                                    tracking_url
                                    role
                                }
                                shape_id
                                shape_version
                                direction
                                confidence
                            }
                        }
                    }
                """,
                "variables": {
                    "token": {"customer_id": self.customer_id, "token": self.api_key},
                    "session_id": int(session.session_id),
                },
            }

            result_response = requests.post(self.graphql_url, headers={
                                            "Content-Type": "application/json"}, json=result_payload)
            result_data = result_response.json().get("data", {}).get("sessionResult")

            if result_response.status_code == 200 and result_data:
                logger.info(
                    f"Successfully fetched result data for session {session.session_id}")
                return result_data
            else:
                logger.error(
                    f"Failed to fetch result for session {session.session_id}")
                return None

        except Exception as e:
            logger.exception(
                f"Error fetching result data for session {session.session_id}: {e}")
            return None


class TraceVisionStatsService:
    """
    Service for calculating player and team performance statistics from tracking data
    Generates comprehensive performance metrics for post-match analysis
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # Configuration constants for calculations
        self.SPRINT_SPEED_THRESHOLD = 7.0  # m/s - speed above which is considered sprinting
        self.SPRINT_DURATION_MIN = 1.0      # seconds - minimum duration for a sprint
        self.PIXEL_TO_METER_RATIO = 0.1    # Approximate conversion (adjust based on field size)
        self.FRAME_RATE = 30                # FPS - frames per second for time calculations
    
    def calculate_session_stats(self, session):
        """
        Calculate comprehensive statistics for an entire session
        
        Args:
            session: TraceSession instance
            
        Returns:
            dict: Calculation results with success status and details
        """
        try:
            self.logger.info(f"Starting stats calculation for session {session.session_id}")
            
            # Get all player objects from the session
            player_objects = session.trace_objects.filter(type='player')
            
            if not player_objects.exists():
                return {
                    'success': False,
                    'error': 'No player objects found',
                    'session_id': session.session_id
                }
            
            # Calculate individual player stats
            player_stats_results = []
            for obj in player_objects:
                try:
                    stats = self._calculate_player_stats(session, obj)
                    if stats:
                        player_stats_results.append(stats)
                        self.logger.info(f"Calculated stats for {obj.object_id}")
                except Exception as e:
                    self.logger.exception(f"Error calculating stats for {obj.object_id}: {e}")
            
            # Calculate team-level stats
            team_stats = self._calculate_team_stats(session, player_stats_results)
            
            # Create session-level stats
            session_stats = self._create_session_stats(session, player_stats_results, team_stats)
            
            self.logger.info(f"Stats calculation completed for session {session.session_id}: "
                           f"{len(player_stats_results)} players processed")
            
            return {
                'success': True,
                'player_stats_count': len(player_stats_results),
                'team_stats': team_stats,
                'session_stats': session_stats,
                'session_id': session.session_id
            }
            
        except Exception as e:
            self.logger.exception(f"Error in session stats calculation for {session.session_id}: {e}")
            return {
                'success': False,
                'error': str(e),
                'session_id': session.session_id
            }
    
    def _calculate_player_stats(self, session, trace_object):
        """
        Calculate comprehensive stats for a single player object
        
        Args:
            session: TraceSession instance
            trace_object: TraceObject instance
            
        Returns:
            TraceVisionPlayerStats instance or None if failed
        """
        try:
            from .models import TraceVisionPlayerStats
            
            # Get tracking data for this player
            tracking_data = self._get_player_tracking_data(trace_object)
            
            if not tracking_data:
                self.logger.warning(f"No tracking data found for {trace_object.object_id}")
                return None
            
            # Calculate basic movement stats
            distance_stats = self._calculate_distance_stats(tracking_data)
            speed_stats = self._calculate_speed_stats(tracking_data)
            sprint_stats = self._calculate_sprint_stats(tracking_data)
            position_stats = self._calculate_position_stats(tracking_data)
            
            # Generate heatmap data
            heatmap_data = self._generate_heatmap_data(tracking_data)
            
            # Calculate performance metrics
            performance_score = self._calculate_performance_score(
                distance_stats, speed_stats, sprint_stats, position_stats
            )
            
            stamina_rating = self._calculate_stamina_rating(speed_stats, sprint_stats)
            work_rate = self._calculate_work_rate(distance_stats, speed_stats)
            
            # Determine side from object_id
            side = self._extract_side_from_object_id(trace_object.object_id)
            
            # Create or update player stats
            stats, created = TraceVisionPlayerStats.objects.update_or_create(
                session=session,
                object_id=trace_object.object_id,
                defaults={
                    'side': side,
                    
                    # Movement stats
                    'total_distance_meters': distance_stats['total_distance'],
                    'avg_speed_mps': speed_stats['avg_speed'],
                    'max_speed_mps': speed_stats['max_speed'],
                    'total_time_seconds': distance_stats['total_time'],
                    
                    # Sprint stats
                    'sprint_count': sprint_stats['sprint_count'],
                    'sprint_distance_meters': sprint_stats['sprint_distance'],
                    'sprint_time_seconds': sprint_stats['sprint_time'],
                    
                    # Position stats
                    'avg_position_x': position_stats['avg_x'],
                    'avg_position_y': position_stats['avg_y'],
                    'position_variance': position_stats['variance'],
                    
                    # Performance metrics
                    'heatmap_data': heatmap_data,
                    'performance_score': performance_score,
                    'stamina_rating': stamina_rating,
                    'work_rate': work_rate,
                    
                    'calculation_method': 'standard',
                    'calculation_version': '1.0'
                }
            )
            
            if created:
                self.logger.info(f"Created new stats for {trace_object.object_id}")
            else:
                self.logger.info(f"Updated existing stats for {trace_object.object_id}")
            
            return stats
            
        except Exception as e:
            self.logger.exception(f"Error calculating stats for {trace_object.object_id}: {e}")
            return None
    
    def _extract_side_from_object_id(self, object_id):
        """Extract side (home/away) from object_id"""
        try:
            if '_' in object_id:
                side = object_id.split('_')[0]
            elif '-' in object_id:
                side = object_id.split('-')[0]
            else:
                side = 'unknown'
            
            return side.lower()
        except:
            return 'unknown'
    
    def _get_player_tracking_data(self, trace_object):
        """Get tracking data for a specific player object"""
        try:
            # Check if we have tracking data in the JSON field
            if trace_object.tracking_data:
                # If it's the raw TraceVision format with 'spotlights', extract the array
                if isinstance(trace_object.tracking_data, dict) and 'spotlights' in trace_object.tracking_data:
                    return trace_object.tracking_data['spotlights']
                # If it's already a list of points, return as is
                elif isinstance(trace_object.tracking_data, list):
                    return trace_object.tracking_data
                else:
                    return None
            
            # If no tracking data available, return None
            return None
            
        except Exception as e:
            self.logger.exception(f"Error getting tracking data for {trace_object.object_id}: {e}")
            return None
    
    def _calculate_distance_stats(self, tracking_data):
        """Calculate distance-related statistics"""
        try:
            total_distance = 0.0
            total_time = 0.0
            
            for i in range(1, len(tracking_data)):
                prev_point = tracking_data[i-1]
                curr_point = tracking_data[i]
                
                # Calculate distance between consecutive points
                dx = curr_point[1] - prev_point[1]  # x difference
                dy = curr_point[2] - prev_point[2]  # y difference
                
                # Convert to meters using pixel ratio
                distance = ((dx**2 + dy**2)**0.5) * self.PIXEL_TO_METER_RATIO
                total_distance += distance
                
                # Calculate time difference (convert to seconds)
                time_diff = (curr_point[0] - prev_point[0]) / 1000.0  # ms to seconds
                total_time += time_diff
            
            return {
                'total_distance': total_distance,
                'total_time': total_time,
                'avg_speed': total_distance / total_time if total_time > 0 else 0.0
            }
            
        except Exception as e:
            self.logger.exception(f"Error calculating distance stats: {e}")
            return {'total_distance': 0.0, 'total_time': 0.0, 'avg_speed': 0.0}
    
    def _calculate_speed_stats(self, tracking_data):
        """Calculate speed-related statistics"""
        try:
            speeds = []
            
            for i in range(1, len(tracking_data)):
                prev_point = tracking_data[i-1]
                curr_point = tracking_data[i]
                
                # Calculate distance
                dx = curr_point[1] - prev_point[1]
                dy = curr_point[2] - prev_point[2]
                distance = ((dx**2 + dy**2)**0.5) * self.PIXEL_TO_METER_RATIO
                
                # Calculate time
                time_diff = (curr_point[0] - prev_point[0]) / 1000.0
                
                if time_diff > 0:
                    speed = distance / time_diff
                    speeds.append(speed)
            
            if speeds:
                return {
                    'avg_speed': sum(speeds) / len(speeds),
                    'max_speed': max(speeds),
                    'min_speed': min(speeds),
                    'speed_variance': self._calculate_variance(speeds)
                }
            else:
                return {'avg_speed': 0.0, 'max_speed': 0.0, 'min_speed': 0.0, 'speed_variance': 0.0}
                
        except Exception as e:
            self.logger.exception(f"Error calculating speed stats: {e}")
            return {'avg_speed': 0.0, 'max_speed': 0.0, 'min_speed': 0.0, 'speed_variance': 0.0}
    
    def _calculate_sprint_stats(self, tracking_data):
        """Calculate sprint-related statistics"""
        try:
            sprints = []
            current_sprint = None
            
            for i in range(1, len(tracking_data)):
                prev_point = tracking_data[i-1]
                curr_point = tracking_data[i]
                
                # Calculate speed for this segment
                dx = curr_point[1] - prev_point[1]
                dy = curr_point[2] - prev_point[2]
                distance = ((dx**2 + dy**2)**0.5) * self.PIXEL_TO_METER_RATIO
                time_diff = (curr_point[0] - prev_point[0]) / 1000.0
                
                if time_diff > 0:
                    speed = distance / time_diff
                    
                    # Check if this is a sprint
                    if speed >= self.SPRINT_SPEED_THRESHOLD:
                        if current_sprint is None:
                            # Start new sprint
                            current_sprint = {
                                'start_time': prev_point[0],
                                'start_distance': sum([
                                    ((tracking_data[j][1] - tracking_data[j-1][1])**2 + 
                                     (tracking_data[j][2] - tracking_data[j-1][2])**2)**0.5 * self.PIXEL_TO_METER_RATIO
                                    for j in range(1, i)
                                ])
                            }
                    else:
                        if current_sprint is not None:
                            # End current sprint
                            current_sprint['end_time'] = prev_point[0]
                            current_sprint['duration'] = (current_sprint['end_time'] - current_sprint['start_time']) / 1000.0
                            
                            # Only count sprints that meet minimum duration
                            if current_sprint['duration'] >= self.SPRINT_DURATION_MIN:
                                sprints.append(current_sprint)
                            
                            current_sprint = None
            
            # Handle case where sprint continues to end of data
            if current_sprint is not None:
                current_sprint['end_time'] = tracking_data[-1][0]
                current_sprint['duration'] = (current_sprint['end_time'] - current_sprint['start_time']) / 1000.0
                if current_sprint['duration'] >= self.SPRINT_DURATION_MIN:
                    sprints.append(current_sprint)
            
            # Calculate sprint statistics
            sprint_count = len(sprints)
            sprint_distance = sum([
                ((tracking_data[sprint['end_time']][1] - tracking_data[sprint['start_time']][1])**2 + 
                 (tracking_data[sprint['end_time']][2] - tracking_data[sprint['start_time']][2])**2)**0.5 * self.PIXEL_TO_METER_RATIO
                for sprint in sprints
            ])
            sprint_time = sum([sprint['duration'] for sprint in sprints])
            
            return {
                'sprint_count': sprint_count,
                'sprint_distance': sprint_distance,
                'sprint_time': sprint_time,
                'sprint_details': sprints
            }
            
        except Exception as e:
            self.logger.exception(f"Error calculating sprint stats: {e}")
            return {'sprint_count': 0, 'sprint_distance': 0.0, 'sprint_time': 0.0, 'sprint_details': []}
    
    def _calculate_position_stats(self, tracking_data):
        """Calculate position-related statistics"""
        try:
            x_coords = [point[1] for point in tracking_data]
            y_coords = [point[2] for point in tracking_data]
            
            avg_x = sum(x_coords) / len(x_coords)
            avg_y = sum(y_coords) / len(y_coords)
            
            # Calculate variance (movement range)
            x_variance = self._calculate_variance(x_coords)
            y_variance = self._calculate_variance(y_coords)
            total_variance = (x_variance + y_variance) / 2
            
            return {
                'avg_x': avg_x,
                'avg_y': avg_y,
                'variance': total_variance,
                'x_range': max(x_coords) - min(x_coords),
                'y_range': max(y_coords) - min(y_coords)
            }
            
        except Exception as e:
            self.logger.exception(f"Error calculating position stats: {e}")
            return {'avg_x': 0.0, 'avg_y': 0.0, 'variance': 0.0, 'x_range': 0.0, 'y_range': 0.0}
    
    def _generate_heatmap_data(self, tracking_data):
        """Generate heatmap grid data for visualization"""
        try:
            # Create a 20x20 grid (400 cells) for heatmap
            grid_size = 20
            heatmap = [[0 for _ in range(grid_size)] for _ in range(grid_size)]
            
            for point in tracking_data:
                x, y = point[1], point[2]
                
                # Convert 0-1000 coordinates to grid coordinates
                grid_x = int((x / 1000.0) * grid_size)
                grid_y = int((y / 1000.0) * grid_size)
                
                # Ensure coordinates are within bounds
                grid_x = max(0, min(grid_size - 1, grid_x))
                grid_y = max(0, min(grid_size - 1, grid_y))
                
                # Increment heatmap value
                heatmap[grid_y][grid_x] += 1
            
            return {
                'grid_size': grid_size,
                'data': heatmap,
                'max_value': max(max(row) for row in heatmap),
                'total_points': len(tracking_data)
            }
            
        except Exception as e:
            self.logger.exception(f"Error generating heatmap data: {e}")
            return {'grid_size': 20, 'data': [], 'max_value': 0, 'total_points': 0}
    
    def _calculate_performance_score(self, distance_stats, speed_stats, sprint_stats, position_stats):
        """Calculate overall performance score (0-100)"""
        try:
            # Weighted scoring system
            distance_score = min(distance_stats['total_distance'] / 10000.0 * 25, 25)  # Max 25 points for distance
            speed_score = min(speed_stats['max_speed'] / 10.0 * 25, 25)               # Max 25 points for speed
            sprint_score = min(sprint_stats['sprint_count'] / 10.0 * 25, 25)         # Max 25 points for sprints
            position_score = min(position_stats['variance'] / 100.0 * 25, 25)        # Max 25 points for movement
            
            total_score = distance_score + speed_score + sprint_score + position_score
            
            return min(total_score, 100.0)  # Cap at 100
            
        except Exception as e:
            self.logger.exception(f"Error calculating performance score: {e}")
            return 0.0
    
    def _calculate_stamina_rating(self, speed_stats, sprint_stats):
        """Calculate stamina rating based on speed consistency and sprint patterns"""
        try:
            # Base stamina on speed variance (lower variance = better stamina)
            speed_consistency = max(0, 10 - speed_stats.get('speed_variance', 0))
            
            # Boost stamina for multiple sprints
            sprint_bonus = min(sprint_stats.get('sprint_count', 0) * 2, 20)
            
            stamina = speed_consistency + sprint_bonus
            
            return min(stamina, 100.0)  # Cap at 100
            
        except Exception as e:
            self.logger.exception(f"Error calculating stamina rating: {e}")
            return 0.0
    
    def _calculate_work_rate(self, distance_stats, speed_stats):
        """Calculate work rate based on distance and speed"""
        try:
            # Work rate = distance * average speed
            work_rate = distance_stats['total_distance'] * speed_stats['avg_speed']
            
            # Normalize to 0-100 scale
            normalized_rate = min(work_rate / 1000.0, 100.0)
            
            return normalized_rate
            
        except Exception as e:
            self.logger.exception(f"Error calculating work rate: {e}")
            return 0.0
    
    def _calculate_variance(self, values):
        """Calculate variance of a list of values"""
        try:
            if not values:
                return 0.0
            
            mean = sum(values) / len(values)
            squared_diff_sum = sum((x - mean) ** 2 for x in values)
            variance = squared_diff_sum / len(values)
            
            return variance
            
        except Exception as e:
            self.logger.exception(f"Error calculating variance: {e}")
            return 0.0
    
    def _calculate_team_stats(self, session, player_stats_list):
        """Calculate aggregated team statistics"""
        try:
            team_stats = {
                'home': {'players': [], 'total_distance': 0, 'avg_speed': 0, 'total_sprints': 0},
                'away': {'players': [], 'total_distance': 0, 'avg_speed': 0, 'total_sprints': 0}
            }
            
            for stats in player_stats_list:
                side = stats.side
                if side in team_stats:
                    team_stats[side]['players'].append(stats)
                    team_stats[side]['total_distance'] += stats.total_distance_meters
                    team_stats[side]['total_sprints'] += stats.sprint_count
            
            # Calculate averages
            for side in ['home', 'away']:
                if team_stats[side]['players']:
                    player_count = len(team_stats[side]['players'])
                    team_stats[side]['avg_speed'] = team_stats[side]['total_distance'] / player_count if player_count > 0 else 0
                    team_stats[side]['avg_distance_per_player'] = team_stats[side]['total_distance'] / player_count if player_count > 0 else 0
            
            return team_stats
            
        except Exception as e:
            self.logger.exception(f"Error calculating team stats: {e}")
            return {}
    
    def _create_session_stats(self, session, player_stats_list, team_stats):
        """Create session-level statistics"""
        try:
            from .models import TraceVisionSessionStats
            
            # Calculate data quality metrics
            total_tracking_points = sum([
                len(stats.session.trace_objects.filter(
                    object_id=stats.object_id
                ).first().tracking_data or [])
                for stats in player_stats_list
            ])
            
            # Estimate data coverage (simplified calculation)
            data_coverage = min(100.0, (total_tracking_points / 1000.0) * 100)  # Normalize to percentage
            
            # Calculate quality score based on various factors
            quality_score = self._calculate_data_quality_score(session, player_stats_list, total_tracking_points)
            
            # Create or update session stats
            session_stats, created = TraceVisionSessionStats.objects.update_or_create(
                session=session,
                defaults={
                    'home_team_stats': team_stats.get('home', {}),
                    'away_team_stats': team_stats.get('away', {}),
                    'total_tracking_points': total_tracking_points,
                    'data_coverage_percentage': data_coverage,
                    'quality_score': quality_score,
                    'processing_status': 'completed',
                    'processing_errors': []
                }
            )
            
            return session_stats
            
        except Exception as e:
            self.logger.exception(f"Error creating session stats: {e}")
            return None
    
    def _calculate_data_quality_score(self, session, player_stats_list, total_tracking_points):
        """Calculate overall data quality score"""
        try:
            score = 0.0
            
            # Base score from tracking points
            if total_tracking_points >= 1000:
                score += 30
            elif total_tracking_points >= 500:
                score += 20
            elif total_tracking_points >= 100:
                score += 10
            
            # Score from player coverage
            expected_players = 22  # 11 per team
            actual_players = len(player_stats_list)
            player_coverage = (actual_players / expected_players) * 100
            score += min(player_coverage * 0.4, 40)  # Max 40 points for player coverage
            
            # Score from data completeness
            complete_stats = sum(1 for stats in player_stats_list if stats.total_distance_meters > 0)
            completeness_score = (complete_stats / len(player_stats_list)) * 100 if player_stats_list else 0
            score += min(completeness_score * 0.3, 30)  # Max 30 points for completeness
            
            return min(score, 100.0)  # Cap at 100
            
        except Exception as e:
            self.logger.exception(f"Error calculating data quality score: {e}")
            return 0.0


class TraceVisionAggregationService:
    """Compute CSV-equivalent aggregates and store them in DB."""
    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def compute_all(self, session):
        """Compute all aggregates for a session in one shot."""
        results = {}
        results['coach_report'] = self._compute_coach_report(session)
        results['touch_leaderboard'] = self._compute_touch_leaderboard(session)
        results['possession_segments'] = self._compute_possessions(session)
        results['clips'] = self._compute_clips(session)
        results['passes'] = self._compute_passes(session)
        results['passing_network'] = self._compute_passing_network(session)
        return results

    def _compute_coach_report(self, session):
        from .models import TraceCoachReportTeam
        # Basic totals based on highlights and simple heuristics
        highlights = session.highlights.all().values('tags', 'start_offset', 'duration')
        side_to_passes = {'home': 0, 'away': 0}
        side_to_possession_ms = {'home': 0, 'away': 0}
        for h in highlights:
            tags = h['tags'] or []
            if 'touch' in tags:
                # possession by tag side if present else infer later
                if 'home' in tags:
                    side_to_possession_ms['home'] += h['duration'] or 0
                if 'away' in tags:
                    side_to_possession_ms['away'] += h['duration'] or 0
            if 'touch-chain' in tags:
                if 'home' in tags:
                    side_to_passes['home'] += 1
                if 'away' in tags:
                    side_to_passes['away'] += 1
        # Upsert for both sides
        for side in ['home', 'away']:
            TraceCoachReportTeam.objects.update_or_create(
                session=session, side=side,
                defaults={
                    'goals': 0,  # not provided by TraceVision
                    'shots': 0,  # not provided by TraceVision
                    'passes': side_to_passes[side],
                    'possession_time_s': (side_to_possession_ms[side] / 1000.0)
                }
            )
        return True

    def _compute_touch_leaderboard(self, session):
        from .models import TraceTouchLeaderboard, TraceHighlight, TraceHighlightObject
        # Count touches per object_id - SQLite compatible approach
        touch_highlights = TraceHighlight.objects.filter(session=session)
        counts = {}
        for h in touch_highlights:
            # Check if 'touch' is in tags (SQLite compatible)
            if h.tags and 'touch' in h.tags:
                objs = h.highlight_objects.all().select_related('trace_object')
                # If no explicit objects, we cannot attribute; skip
                for ho in objs:
                    oid = ho.trace_object.object_id
                    side = ho.trace_object.side
                    counts.setdefault((oid, side), 0)
                    counts[(oid, side)] += 1
        # Upsert
        for (oid, side), c in counts.items():
            TraceTouchLeaderboard.objects.update_or_create(
                session=session, object_id=oid,
                defaults={'object_side': side, 'touches': c}
            )
        return True

    def _compute_possessions(self, session):
        from .models import TracePossessionSegment, TraceHighlight
        # Build contiguous segments of touch/touch-chain by side using highlights timeline
        hs = list(TraceHighlight.objects.filter(session=session).values('start_offset', 'duration', 'tags'))
        # Convert to events with side
        events = []
        for h in hs:
            start = h['start_offset'] or 0
            end = start + (h['duration'] or 0)
            tags = h['tags'] or []
            side = 'home' if 'home' in tags else 'away' if 'away' in tags else None
            if side and 'touch' in tags:
                events.append((start, end, side))
        # Sort and merge per side
        for side in ['home', 'away']:
            side_events = sorted([e for e in events if e[2] == side])
            merged = []
            for s, e, _ in side_events:
                if not merged or s > merged[-1][1] + 1000:  # 1s gap threshold
                    merged.append([s, e, 1])
                else:
                    merged[-1][1] = max(merged[-1][1], e)
                    merged[-1][2] += 1
            for s, e, cnt in merged:
                TracePossessionSegment.objects.create(
                    session=session, side=side, start_ms=s, end_ms=e,
                    count=cnt, start_clock=self._ms_to_clock(s), end_clock=self._ms_to_clock(e),
                    duration_s=(e - s) / 1000.0
                )
        return True

    def _compute_clips(self, session):
        from .models import TraceClipReel, TraceHighlight
        hs = TraceHighlight.objects.filter(session=session)
        for h in hs:
            side = 'home' if 'home' in (h.tags or []) else 'away' if 'away' in (h.tags or []) else ''
            # one row per highlight-object if present, else one per highlight
            objs = h.highlight_objects.all().select_related('trace_object')
            if objs:
                for ho in objs:
                    TraceClipReel.objects.update_or_create(
                        session=session, event_id=h.highlight_id, object_id=ho.trace_object.object_id,
                        defaults={
                            'video_id': h.video_id,
                            'event_type': 'touch',
                            'side': side,
                            'start_ms': h.start_offset,
                            'duration_ms': h.duration,
                            'start_clock': self._ms_to_clock(h.start_offset),
                            'end_clock': self._ms_to_clock(h.start_offset + h.duration),
                            'label': f"Touch{side}",
                            'tags': h.tags or [],
                            'video_stream': h.video_stream or ''
                        }
                    )
            else:
                TraceClipReel.objects.update_or_create(
                    session=session, event_id=h.highlight_id, object_id=None,
                    defaults={
                        'video_id': h.video_id,
                        'event_type': 'touch',
                        'side': side,
                        'start_ms': h.start_offset,
                        'duration_ms': h.duration,
                        'start_clock': self._ms_to_clock(h.start_offset),
                        'end_clock': self._ms_to_clock(h.start_offset + h.duration),
                        'label': f"Touch{side}",
                        'tags': h.tags or [],
                        'video_stream': h.video_stream or ''
                    }
                )
        return True

    def _compute_passes(self, session):
        # Derive naive passes from consecutive touch highlights by same side and different object_id
        from .models import TracePass, TraceHighlight
        # SQLite compatible approach - filter in Python
        all_highlights = list(TraceHighlight.objects.filter(session=session).order_by('start_offset'))
        hs = [h for h in all_highlights if h.tags and 'touch' in h.tags]
        # Prepare object involvement per highlight
        h_objs = {}
        for h in hs:
            obj_ids = [ho.trace_object.object_id for ho in h.highlight_objects.all().select_related('trace_object')]
            side = 'home' if 'home' in (h.tags or []) else 'away' if 'away' in (h.tags or []) else None
            h_objs[h.highlight_id] = {'objs': obj_ids, 'side': side, 'start': h.start_offset, 'dur': h.duration}
        # Build transitions
        for i in range(1, len(hs)):
            prev = h_objs.get(hs[i-1].highlight_id)
            curr = h_objs.get(hs[i].highlight_id)
            if not prev or not curr:
                continue
            if prev['side'] and curr['side'] and prev['side'] == curr['side'] and prev['objs'] and curr['objs']:
                # Create a pass from last toucher to first next toucher
                TracePass.objects.create(
                    session=session,
                    side=curr['side'],
                    from_object_id=prev['objs'][-1],
                    to_object_id=curr['objs'][0],
                    start_ms=curr['start'],
                    duration_ms=curr['dur'] or 0
                )
        return True

    def _compute_passing_network(self, session):
        from django.db.models import Count
        from .models import TracePass, TracePassingNetwork
        qs = TracePass.objects.filter(session=session).values('side', 'from_object_id', 'to_object_id').annotate(c=Count('id'))
        for row in qs:
            TracePassingNetwork.objects.update_or_create(
                session=session,
                side=row['side'],
                from_object_id=row['from_object_id'],
                to_object_id=row['to_object_id'],
                defaults={'passes_count': row['c']}
            )
        return True

    def _ms_to_clock(self, ms):
        s = int(ms / 1000)
        m, s = divmod(s, 60)
        h, m = divmod(m, 60)
        if h:
            return f"{h}:{m:02d}:{s:02d}.{int(ms%1000):03d}"
        return f"{m}:{s:02d}.{int(ms%1000):03d}"
