import logging
import requests
from typing import Dict, List, Optional, Any

from tracevision.spotlight_metrics_calculator import SpotlightMetricsCalculator

logger = logging.getLogger(__name__)


def count_defensive_actions(highlights: List[Dict]) -> Dict[str, float]:
    """Count defensive actions from highlights"""
    actions = {
        'blocks': 0, 'tackles_attempted': 0, 'tackles_won': 0, 'clearances': 0,
        'interceptions': 0, 'interventions': 0, 'recoveries': 0,
        'aerial_duels_total': 0, 'aerial_duels_won': 0, 'ground_duels_total': 0,
        'ground_duels_won': 0, 'loose_ball_duels': 0, 'shots_blocked': 0,
        'aerial_clearances': 0, 'defensive_line_support': 0, 'mistakes': 0, 'own_goals': 0
    }

    for highlight in highlights:
        tags = highlight.get('tags', [])
        # Estimate defensive actions based on tags and context
        if 'defensive' in tags or 'tackle' in tags:
            actions['tackles_attempted'] += 1
            actions['tackles_won'] += 1  # Assume successful if tracked
        if 'interception' in tags:
            actions['interceptions'] += 1
        if 'recovery' in tags or 'regain' in tags:
            actions['recoveries'] += 1

    # Calculate success rates
    actions['tackle_success_rate'] = (
        actions['tackles_won'] / actions['tackles_attempted'] * 100) if actions['tackles_attempted'] > 0 else 0
    actions['aerial_duel_success_rate'] = (
        actions['aerial_duels_won'] / actions['aerial_duels_total'] * 100) if actions['aerial_duels_total'] > 0 else 0
    actions['ground_duel_success_rate'] = (
        actions['ground_duels_won'] / actions['ground_duels_total'] * 100) if actions['ground_duels_total'] > 0 else 0

    return actions


def count_attacking_actions(highlights: List[Dict]) -> Dict[str, int]:
    """Count attacking actions from highlights"""
    actions = {
        'goals': 0, 'shots': 0, 'assists': 0, 'offsides': 0,
        'key_passes': 0, 'shots_in_pa': 0, 'shots_outside_pa': 0,
        'shots_blocked': 0, 'take_ons': 0, 'crosses': 0,
        'pressure_controls': 0, 'final_third_passes': 0
    }

    for highlight in highlights:
        tags = highlight.get('tags', [])
        # Analyze tags to increment counters based on TraceVision's tagging
        if 'goal' in tags:
            actions['goals'] += 1
        if 'shot' in tags:
            actions['shots'] += 1
        if 'assist' in tags:
            actions['assists'] += 1
        if 'cross' in tags:
            actions['crosses'] += 1
        if 'touch-chain' in tags:
            actions['key_passes'] += 1  # Estimate key passes from touch chains
        if 'dribble' in tags or 'take-on' in tags:
            actions['take_ons'] += 1

    return actions


def calculate_passing_stats(highlights: List[Dict]) -> Dict[str, float]:
    """
    Estimate passing stats from TraceVision highlights.
    Pass = change of possession from one player to another within consecutive highlights of the same team.
    """
    completed = 0
    attempted = 0

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
        self.spotlight_calculator = SpotlightMetricsCalculator()

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
            player_objects = session.trace_objects.filter(type='player')

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
                            'side': player_obj.side,
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
            player_obj: TraceObject instance for the player

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
                session, player_obj.object_id)

            # Calculate different metric categories
            gps_athletic_metrics = self._calculate_gps_athletic_skills(
                tracking_data)
            gps_football_metrics = self._calculate_gps_football_abilities(
                tracking_data, player_highlights)
            attacking_metrics = self._calculate_attacking_skills(
                player_highlights, tracking_data, session)
            defensive_metrics = self._calculate_defensive_skills(
                player_highlights, tracking_data, session)
            rpe_metrics = self._calculate_rpe_metrics(
                tracking_data, player_highlights)

            # Determine match duration for context
            match_duration = self._estimate_match_duration(session)

            return {
                'gps_athletic_skills': gps_athletic_metrics,
                'gps_football_abilities': gps_football_metrics,
                'attacking_skills': attacking_metrics,
                'defensive_skills': defensive_metrics,
                'rpe_metrics': rpe_metrics,
                'match_duration_minutes': match_duration,
                'tracking_data_points': len(tracking_data)
            }

        except Exception as e:
            self.logger.exception(
                f"Error calculating player metrics for {player_obj.object_id}: {e}")
            return None

    def _get_player_tracking_data(self, player_obj) -> List[List[float]]:
        """
        Extract tracking data for a player from TraceObject

        Returns:
            list: Tracking data points as [time_ms, x, y, w, h]
        """
        try:
            if player_obj.tracking_data:
                # Check format - could be direct list or wrapped in 'spotlights'
                if isinstance(player_obj.tracking_data, dict) and 'spotlights' in player_obj.tracking_data:
                    return player_obj.tracking_data['spotlights']
                elif isinstance(player_obj.tracking_data, list):
                    return player_obj.tracking_data

            # If no tracking data in object, try to fetch from URL (fallback)
            if player_obj.tracking_url:
                return self._fetch_tracking_data_from_url(player_obj.tracking_url)

            return []

        except Exception as e:
            self.logger.exception(
                f"Error getting tracking data for {player_obj.object_id}: {e}")
            return []

    def _fetch_tracking_data_from_url(self, tracking_url: str, timeout: int = 10) -> List[List[float]]:
        """
        Fetch tracking data from URL as fallback
        """
        try:
            response = requests.get(tracking_url, timeout=timeout)
            response.raise_for_status()
            data = response.json()

            if isinstance(data, dict) and 'spotlights' in data:
                return data['spotlights']
            elif isinstance(data, list):
                return data

            return []

        except Exception as e:
            self.logger.exception(
                f"Error fetching tracking data from {tracking_url}: {e}")
            return []

    def _get_player_highlights(self, session, object_id: str) -> List[Dict]:
        """
        Get all highlights/events involving a specific player
        """
        try:
            highlights = []

            # Get highlights where this player is involved
            for highlight in session.highlights.all():
                # Check if player is in the highlight objects
                for highlight_obj in highlight.highlight_objects.all():
                    if highlight_obj.trace_object.object_id == object_id:
                        highlights.append({
                            'highlight_id': highlight.highlight_id,
                            'start_offset': highlight.start_offset,
                            'duration': highlight.duration,
                            'tags': highlight.tags or [],
                            'video_id': highlight.video_id,
                            'objects': [ho.trace_object.object_id for ho in highlight.highlight_objects.all()]
                        })
                        break

            return highlights

        except Exception as e:
            self.logger.exception(
                f"Error getting player highlights for {object_id}: {e}")
            return []

    def _calculate_gps_athletic_skills(self, tracking_data: List[List[float]]) -> Dict[str, str]:
        """
        Calculate GPS Athletic Skills metrics from movement data
        """
        try:
            if not tracking_data or len(tracking_data) < 2:
                return self.spotlight_calculator._get_empty_athletic_metrics()

            # Use the specialized spotlight calculator for better accuracy
            return self.spotlight_calculator.calculate_gps_athletic_skills(tracking_data)

        except Exception as e:
            self.logger.exception(
                f"Error calculating GPS athletic skills: {e}")
            return self.spotlight_calculator._get_empty_athletic_metrics()

    def _calculate_gps_football_abilities(self, tracking_data: List[List[float]], highlights: List[Dict]) -> Dict[str, str]:
        """
        Calculate GPS Football Abilities metrics

        Args:
            tracking_data: Player tracking data [time_ms, x, y, w, h]
            highlights: List of highlight objects with tags and object info
        """
        try:
            if not tracking_data:
                return self.spotlight_calculator._get_empty_football_metrics()

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

            # Use the specialized spotlight calculator for better accuracy
            # Pass highlights and objects for ball detection
            return self.spotlight_calculator.calculate_gps_football_abilities(tracking_data, highlights, objects)

        except Exception as e:
            self.logger.exception(
                f"Error calculating GPS football abilities: {e}")
            return self.spotlight_calculator._get_empty_football_metrics()

    def _calculate_attacking_skills(self, highlights: List[Dict], tracking_data: List[List[float]], session) -> Dict[str, str]:
        """
        Calculate Attacking Skills metrics from highlights and events

        Expected format:
        {"Goals": "0", "Shots": "0", "Assists": "0", "Passing": "9/19 (47%)", ...}
        """
        try:
            # Count different types of attacking actions from highlights
            attacking_actions = count_attacking_actions(highlights)

            # Calculate passing statistics
            passing_stats = calculate_passing_stats(highlights, session)

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
        Calculate Video Card Defensive metrics

        Expected format:
        {"Blocks": "0", "Tackles": "1/1 (100%)", "Clearances": "0", ...}
        """
        try:
            # Count defensive actions from highlights
            defensive_actions = count_defensive_actions(highlights)

            # Calculate defensive passing stats
            defensive_passing = calculate_passing_stats(
                highlights, tracking_data)

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

    def _calculate_rpe_metrics(self, tracking_data: List[List[float]], highlights: List[Dict]) -> Dict[str, str]:
        """
        Calculate RPE (Rate of Perceived Exertion) metrics based on activity intensity

        Expected format:
        {"Fatigue": "100.0", "Recovery": "20.0", "Intensity": "100.0", "Readiness": "54.0"}
        """
        try:
            if not tracking_data:
                return {"Fatigue": "0.0", "Recovery": "0.0", "Intensity": "0.0", "Readiness": "0.0"}

            # Use SpotlightMetricsCalculator for movement analysis
            movement_data = self.spotlight_calculator._analyze_movement(
                tracking_data)
            distance_zones = self.spotlight_calculator._calculate_distance_zones(
                tracking_data)
            acceleration_data = self.spotlight_calculator._calculate_acceleration_metrics(
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
            for trace_obj in session.trace_objects.all():
                if trace_obj.tracking_data:
                    tracking_data = trace_obj.tracking_data
                    if isinstance(tracking_data, dict) and 'spotlights' in tracking_data:
                        tracking_data = tracking_data['spotlights']
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
            if not tracking_data or len(tracking_data < 2):
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
        """Count attacking actions from highlights"""

        actions = {
            'goals': 0, 'shots': 0, 'assists': 0, 'offsides': 0,
            'key_passes': 0, 'shots_in_pa': 0, 'shots_outside_pa': 0,
            'shots_blocked': 0, 'take_ons': 0, 'crosses': 0,
            'pressure_controls': 0, 'final_third_passes': 0
        }

        for highlight in highlights:
            tags = highlight.get('tags', [])

        return actions

    def _calculate_passing_stats(self, highlights: List[Dict], session) -> Dict[str, int]:
        """Calculate passing statistics from highlights"""
        completed = 0
        attempted = 0

        percentage = (completed / attempted * 100) if attempted > 0 else 0

        return {
            'completed': completed,
            'attempted': attempted,
            'percentage': percentage
        }
