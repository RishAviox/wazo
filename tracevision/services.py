import logging
import requests
from datetime import datetime, timedelta
from django.core.cache import cache
from django.conf import settings
from django.db import models

from tracevision.models import TraceClipReel, TraceHighlight, TracePlayer, TracePossessionSegment, TracePossessionStats
from tracevision.utils import filter_highlights_by_game_time, parse_time_to_seconds

logger = logging.getLogger(__name__)


def save_possession_calculation_results(session, team_possession_data, player_possession_data):
    """
    Save possession calculation results from your existing functions to the database.
    Uses the unified TracePossessionStats model with single metrics JSON field.
    Creates multiple rows per session: 1 per team + 1 per player.

    Args:
        session: TraceSession instance
        team_possession_data: dict with team possession stats
        player_possession_data: dict with player involvement stats

    Returns:
        dict: Save results with success status
    """
    try:
        # from .models import TracePossessionStats, TracePlayer, TracePossessionSegment
        logger = logging.getLogger(__name__)

        saved_team_stats = []
        saved_player_stats = []

        # Save team possession stats (1 row per team)
        for side, team_data in team_possession_data.items():
            team = session.home_team if side == 'home' else session.away_team
            if not team:
                continue

            team_stats, created = TracePossessionStats.objects.update_or_create(
                session=session,
                possession_type='team',
                team=team,
                side=side,
                defaults={
                    'metrics': team_data  # Store all team data in single JSON field
                }
            )
            saved_team_stats.append(team_stats)

        # Save player possession involvement stats (1 row per player)
        for player_id, player_data in player_possession_data.items():
            try:
                # Extract jersey number from player_id (format: team_side_jersey)
                jersey_number = int(player_id.split('_')[-1])
                team_side = player_id.split('_')[0]

                # Find player by jersey number and team side
                # Get the team object first
                team = session.home_team if team_side == 'home' else session.away_team
                if not team:
                    logger.warning(f"No team found for side {team_side}")
                    continue

                try:
                    player = session.trace_players.get(
                        jersey_number=jersey_number,
                        team=team
                    )
                except TracePlayer.DoesNotExist:
                    logger.warning(
                        f"Player {player_id} (jersey {jersey_number}, team {team.name}) not found in database, skipping")
                    continue

                player_stats, created = TracePossessionStats.objects.update_or_create(
                    session=session,
                    possession_type='player',
                    player=player,
                    defaults={
                        'team': player.team,  # Set the team field
                        'side': team_side,    # Set the side field
                        'metrics': player_data  # Store cleaned player data
                    }
                )
                saved_player_stats.append(player_stats)

            except Exception as e:
                logger.warning(
                    f"Error saving player possession stats for player {player_id}: {e}")
                continue

        return {
            'success': True,
            'team_stats_saved': len(saved_team_stats),
            'player_stats_saved': len(saved_player_stats),
            'session_id': session.session_id
        }

    except Exception as e:
        logger.exception(f"Error saving possession calculation results: {e}")
        return {
            'success': False,
            'error': str(e),
            'session_id': session.session_id
        }


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


class TraceVisionAggregationService:
    """Compute CSV-equivalent aggregates and store them in DB."""

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def compute_all(self, session):
        """Compute all aggregates for a session in one shot."""
        results = {}
        # results['coach_report'] = self._compute_coach_report(session)
        # results['touch_leaderboard'] = self._compute_touch_leaderboard(session)
        results['possession_segments'] = self._compute_possessions(session)
        results['clips'] = self._compute_clips(session)
        # results['passes'] = self._compute_passes(session)
        # results['passing_network'] = self._compute_passing_network(session)
        return results

    def _ms_to_clock(self, ms):
        s = int(ms / 1000)
        m, s = divmod(s, 60)
        h, m = divmod(m, 60)
        if h:
            return f"{h}:{m:02d}:{s:02d}.{int(ms % 1000):03d}"
        return f"{m}:{s:02d}.{int(ms % 1000):03d}"

    def _get_video_variant_name(self, video_type, primary_player):
        """Generate a descriptive name for the video variant"""
        if video_type == 'original':
            return 'Original View'
        elif video_type == 'with_overlay':
            return 'With Overlay'
        elif video_type == 'zoomed_player' and primary_player:
            return f'Focused on {primary_player.name}'
        elif video_type == 'zoomed_team':
            return 'Team View'
        elif video_type == 'tactical_view':
            return 'Tactical View'
        elif video_type == 'slow_motion':
            return 'Slow Motion'
        elif video_type == 'multi_angle':
            return 'Multi-Angle'
        else:
            return video_type.replace('_', ' ').title()

    def _compute_clips(self, session):
        # from .models import TraceClipReel, TraceHighlight
        hs = TraceHighlight.objects.filter(session=session)

        for h in hs:
            side = 'home' if 'home' in (
                h.tags or []) else 'away' if 'away' in (h.tags or []) else ''

            # Get all players involved in this highlight
            highlight_objects = h.highlight_objects.all(
            ).select_related('trace_object', 'player')
            involved_players = [
                ho.player for ho in highlight_objects if ho.player]
            primary_player = involved_players[0] if involved_players else None

            # Determine event type from tags
            event_type = 'touch'  # default
            if h.tags:
                if 'pass' in h.tags:
                    event_type = 'pass'
                elif 'shot' in h.tags:
                    event_type = 'shot'
                elif 'goal' in h.tags:
                    event_type = 'goal'
                elif 'tackle' in h.tags:
                    event_type = 'tackle'

            # Create clip reel entries for different video types
            video_types_to_create = ['with_overlay']

            for video_type in video_types_to_create:
                clip_reel, _ = TraceClipReel.objects.update_or_create(
                    highlight=h,
                    video_type=video_type,
                    defaults={
                        'session': session,
                        'event_id': h.highlight_id,
                        'event_type': event_type,
                        'side': side,
                        'start_ms': h.start_offset,
                        'duration_ms': h.duration,
                        'start_clock': self._ms_to_clock(h.start_offset),
                        'end_clock': self._ms_to_clock(h.start_offset + h.duration),
                        'primary_player': primary_player,
                        'label': f"{event_type.title()} - {side.title()}",
                        'description': f"{event_type.title()} event for {side} team",
                        'tags': h.tags or [],
                        'video_stream': h.video_stream or '',
                        'generation_status': 'pending',
                        'video_variant_name': self._get_video_variant_name(video_type, primary_player),
                        'generation_metadata': {
                            'highlight_id': h.highlight_id,
                            'video_id': h.video_id,
                            'involved_players_count': len(involved_players),
                            'created_from_aggregation': True
                        }
                    }
                )

                # Add all involved players to the many-to-many relationship
                if involved_players:
                    clip_reel.involved_players.set(involved_players)
        return True

    def _compute_possessions(self, session):
        """Compute possession metrics using highlights from session.result.highlights"""
        # from .utils import parse_time_to_seconds, filter_highlights_by_game_time

        try:
            self.logger.info(
                f"Starting possession calculation for session {session.session_id}")

            # Get highlights from session result
            if not session.result or 'highlights' not in session.result:
                self.logger.warning(
                    f"No highlights found in session {session.session_id} result")
                return False

            highlights = session.result['highlights']
            if not highlights:
                self.logger.warning(
                    f"Empty highlights list for session {session.session_id}")
                return False

            # Parse session timing fields to seconds
            game_start_time = parse_time_to_seconds(
                session.match_start_time) if session.match_start_time else None
            first_half_end_time = parse_time_to_seconds(
                session.first_half_end_time) if session.first_half_end_time else None
            second_half_start_time = parse_time_to_seconds(
                session.second_half_start_time) if session.second_half_start_time else None
            game_end_time = parse_time_to_seconds(
                session.match_end_time) if session.match_end_time else None

            # Filter highlights by game time
            filtered_highlights = filter_highlights_by_game_time(
                highlights, game_start_time, first_half_end_time,
                second_half_start_time, game_end_time
            )

            if not filtered_highlights:
                self.logger.warning(
                    f"No highlights remain after game time filtering for session {session.session_id}")
                return False

            # Calculate possession metrics
            possession_results = self._calculate_possession_metrics(
                filtered_highlights, session)

            # Save possession_results to a JSON file (for debugging/analysis, not for testing)
            # output_dir = "./tracevision"
            # os.makedirs(output_dir, exist_ok=True)
            # output_path = os.path.join(
            #     output_dir, f"possession_results_{session.session_id}.json")
            # try:
            #     with open(output_path, "w") as f:
            #         json.dump(possession_results, f, indent=2)
            #     self.logger.info(f"Possession results saved to {output_path}")
            # except Exception as e:
            #     self.logger.warning(
            #         f"Failed to save possession results to {output_path}: {e}")

            # Save results to database
            save_result = save_possession_calculation_results(
                session,
                possession_results['team_metrics'],
                possession_results['player_metrics']
            )

            if save_result['success']:
                # Create possession segments using the same data as possession stats
                segments_result = self._create_possession_segments_from_calculation(
                    session, filtered_highlights, possession_results
                )
                if segments_result:
                    self.logger.info(f"Successfully created possession segments for session {session.session_id}")
                else:
                    self.logger.warning(f"Failed to create possession segments for session {session.session_id}")
                
                self.logger.info(
                    f"Successfully computed and saved possession metrics for session {session.session_id}")
                return True
            else:
                self.logger.error(
                    f"Failed to save possession metrics for session {session.session_id}: {save_result.get('error')}")
                return False

        except Exception as e:
            self.logger.exception(
        f"Error computing possession metrics for session {session.session_id}: {e}")
            return False

    def _calculate_possession_metrics(self, highlights, session):
        """Calculate possession metrics based on possession.py logic"""
        # Filter only possession chains (touch-chain tags)
        chains = [h for h in highlights if 'touch-chain' in h.get('tags', [])]

        if not chains:
            self.logger.warning("No possession chains found in highlights")
            return {'team_metrics': {'home': {}, 'away': {}}, 'player_metrics': {}}

        # Sort chains by start time
        chains = sorted(chains, key=lambda x: x['start_offset'])

        # Group consecutive chains by the same team into possessions
        possessions = self._group_chains_into_possessions(chains)

        # Calculate team-level metrics
        team_metrics = self._calculate_team_metrics_from_possessions(
            possessions)

        # Calculate player-level metrics
        player_metrics = self._calculate_player_metrics_from_possessions(
            possessions, session)

        return {
            'team_metrics': team_metrics,
            'player_metrics': player_metrics
        }

    def _group_chains_into_possessions(self, chains):
        """Group consecutive touch-chains by the same team into possessions"""
        possessions = []
        current_possession = None

        for chain in chains:
            tags = chain.get('tags', [])
            team_side = None
            if 'home' in tags:
                team_side = 'home'
            elif 'away' in tags:
                team_side = 'away'

            if not team_side:
                continue

            # If this is the first chain or different team, start new possession
            if current_possession is None or current_possession['team'] != team_side:
                # Save previous possession if exists
                if current_possession is not None:
                    possessions.append(current_possession)

                # Start new possession
                current_possession = {
                    'team': team_side,
                    'chains': [chain],
                    'start_ms': chain['start_offset'],
                    'end_ms': chain['start_offset'] + chain['duration'],
                    'total_duration_ms': chain['duration'],
                    'total_touches': len(chain.get('objects', [])),
                    'players_involved': set()
                }
            else:
                # Same team - add to current possession
                current_possession['chains'].append(chain)
                current_possession['end_ms'] = chain['start_offset'] + \
                    chain['duration']
                current_possession['total_duration_ms'] = current_possession['end_ms'] - \
                    current_possession['start_ms']
                current_possession['total_touches'] += len(
                    chain.get('objects', []))

            # Track players involved in this possession
            for obj in chain.get('objects', []):
                if obj.get('object_id'):
                    current_possession['players_involved'].add(
                        obj['object_id'])

        # Add the last possession
        if current_possession is not None:
            possessions.append(current_possession)

        return possessions

    def _calculate_team_metrics_from_possessions(self, possessions):
        """Calculate team-level metrics from grouped possessions"""
        team_metrics = {'home': {}, 'away': {}}

        # Group possessions by team
        team_possessions = {'home': [], 'away': []}
        for possession in possessions:
            team_possessions[possession['team']].append(possession)

        # Calculate metrics for each team
        for team_side in ['home', 'away']:
            team_poss = team_possessions[team_side]
            if not team_poss:
                team_metrics[team_side] = self._get_empty_team_metrics()
                continue

            # Basic metrics (keep in milliseconds)
            total_duration_ms = sum(p['total_duration_ms'] for p in team_poss)
            possession_count = len(team_poss)
            avg_duration_ms = total_duration_ms / \
                possession_count if possession_count > 0 else 0

            # Calculate passes (touches - 1 per possession)
            total_touches = sum(p['total_touches'] for p in team_poss)
            total_passes = max(total_touches - possession_count, 0)
            avg_passes = total_passes / possession_count if possession_count > 0 else 0

            # Longest possession (keep in milliseconds)
            longest_possession_ms = max(
                p['total_duration_ms'] for p in team_poss)

            # Calculate turnovers (number of times this team lost possession)
            turnovers = self._calculate_team_turnovers(possessions, team_side)

            team_metrics[team_side] = {
                'possession_time_ms': round(total_duration_ms, 1),
                'possession_count': possession_count,
                'avg_duration_ms': round(avg_duration_ms, 1),
                'avg_passes': round(avg_passes, 2),
                'longest_possession_ms': round(longest_possession_ms, 1),
                'turnovers': turnovers,
                'total_touches': total_touches,
                'total_passes': total_passes
            }

        # Calculate possession percentages
        total_possession_time_ms = sum(
            team_metrics[side]['possession_time_ms'] for side in team_metrics)
        if total_possession_time_ms > 0:
            for team_side in team_metrics:
                team_metrics[team_side]['possession_percentage'] = round(
                    (team_metrics[team_side]['possession_time_ms'] /
                     total_possession_time_ms) * 100, 1
                )

        return team_metrics

    def _calculate_team_turnovers(self, possessions, team_side):
        """Calculate turnovers for a specific team"""
        turnovers = 0
        for i, possession in enumerate(possessions):
            if possession['team'] == team_side:
                # Check if next possession is by different team
                if i + 1 < len(possessions) and possessions[i + 1]['team'] != team_side:
                    turnovers += 1
        return turnovers

    def _calculate_player_metrics_from_possessions(self, possessions, session):
        """Calculate player-level possession metrics from grouped possessions"""
        # Get all players in the session
        players = session.trace_players.all()
        player_metrics = {}

        # Group possessions by team for percentage calculations
        team_possessions = {'home': [], 'away': []}
        for possession in possessions:
            team_possessions[possession['team']].append(possession)

        for player in players:
            # Create player_id in format: <team_side>_<jersey_number>
            team_side = 'home' if 'home' in player.team_name.lower() else 'away'
            player_id = f"{team_side}_{player.jersey_number}"

            # Find possessions where this player was involved
            player_possessions = []
            for possession in possessions:
                if player.object_id in possession['players_involved']:
                    player_possessions.append(possession)

            if not player_possessions:
                player_metrics[player_id] = self._get_empty_player_metrics(
                    player, player_id, team_side)
                continue

            # Calculate player-specific metrics (keep in milliseconds)
            total_duration_ms = sum(p['total_duration_ms']
                                    for p in player_possessions)
            involvement_count = len(player_possessions)
            avg_duration_ms = total_duration_ms / \
                involvement_count if involvement_count > 0 else 0

            # Calculate touches in possessions
            total_touches = sum(p['total_touches'] for p in player_possessions)
            avg_touches = total_touches / involvement_count if involvement_count > 0 else 0

            # Calculate involvement percentage for player's team
            team_poss = team_possessions[team_side]
            team_possession_count = len(team_poss)
            involvement_percentage = 0
            if team_possession_count > 0:
                involvement_percentage = round(
                    (involvement_count / team_possession_count) * 100, 1)

            player_metrics[player_id] = {
                'involvement_count': involvement_count,
                'total_duration_ms': round(total_duration_ms, 1),
                'avg_duration_ms': round(avg_duration_ms, 1),
                'total_touches': total_touches,
                'avg_touches': round(avg_touches, 2),
                'involvement_percentage': involvement_percentage
            }

        return player_metrics

    def _get_empty_team_metrics(self):
        """Return empty team metrics structure"""
        return {
            'possession_time_ms': 0,
            'possession_count': 0,
            'avg_duration_ms': 0,
            'avg_passes': 0,
            'longest_possession_ms': 0,
            'turnovers': 0,
            'total_touches': 0,
            'total_passes': 0,
            'possession_percentage': 0
        }

    def _get_empty_player_metrics(self, player, player_id, team_side):
        """Return empty player metrics structure"""
        return {
            'involvement_count': 0,
            'total_duration_ms': 0,
            'avg_duration_ms': 0,
            'total_touches': 0,
            'avg_touches': 0,
            'involvement_percentage': 0
        }


    def _create_possession_segments_from_calculation(self, session, highlights, possession_results):
        """Create possession segments using the same data as possession calculation"""
        try:
            self.logger.info(f"Creating possession segments from calculation for session {session.session_id}")
            
            # Clear existing segments for this session
            TracePossessionSegment.objects.filter(session=session).delete()
            
            # Filter only possession chains (touch-chain tags)
            chains = [h for h in highlights if 'touch-chain' in h.get('tags', [])]
            
            if not chains:
                self.logger.warning(f"No possession chains found for session {session.session_id}")
                return False
            
            # Sort chains by start time
            chains = sorted(chains, key=lambda x: x['start_offset'])
            
            # Group consecutive chains by the same team into possessions
            possessions = self._group_chains_into_possessions(chains)
            
            # Create segments for each possession
            segments_created = 0
            cumulative_team_metrics = {'home': {}, 'away': {}}
            cumulative_player_metrics = {}
            
            for i, possession in enumerate(possessions):
                team_side = possession['team']
                
                # Calculate cumulative metrics up to this possession
                cumulative_team_metrics[team_side] = self._calculate_cumulative_team_metrics_for_segment(
                    possessions[:i+1], team_side, session, possessions
                )
                
                # Calculate player metrics for this possession
                player_metrics = self._calculate_player_metrics_for_possession(
                    possession, session, cumulative_player_metrics
                )
                
                # Filter out players with all zero metrics to save space
                filtered_player_metrics = {
                    player_id: metrics for player_id, metrics in player_metrics.items()
                    if any(metrics.get(key, 0) != 0 for key in ['involvement_count', 'total_duration_ms', 'total_touches'])
                }
                
                # Find the highlight that corresponds to this possession
                # Use the first chain in the possession to find the highlight
                highlight = None
                if possession['chains']:
                    first_chain = possession['chains'][0]
                    # Try to find the highlight by start_offset
                    highlight = session.highlights.filter(
                        start_offset=first_chain['start_offset']
                    ).first()
                
                # Create segment
                segment = TracePossessionSegment.objects.create(
                    session=session,
                    side=team_side,
                    start_ms=possession['start_ms'],
                    end_ms=possession['end_ms'],
                    count=len(possession['chains']),  # Number of chains in this possession
                    start_clock=self._ms_to_clock(possession['start_ms']),
                    end_clock=self._ms_to_clock(possession['end_ms']),
                    duration_s=possession['total_duration_ms'] / 1000.0,  # Convert ms to seconds
                    highlight=highlight,  # Link to the highlight
                    team_metrics=cumulative_team_metrics[team_side],
                    player_metrics=filtered_player_metrics  # Only non-zero player metrics
                )
                segments_created += 1
                
                self.logger.debug(f"Created segment {segments_created} for {team_side} team with {len(possession['chains'])} chains")
            
            self.logger.info(f"Successfully created {segments_created} possession segments for session {session.session_id}")
            return True
            
        except Exception as e:
            self.logger.exception(f"Error creating possession segments for session {session.session_id}: {e}")
            return False

    def _calculate_cumulative_team_metrics_for_segment(self, possessions_up_to_now, team_side, session, all_possessions):
        """Calculate cumulative team metrics up to a specific possession"""
        team_possessions = [p for p in possessions_up_to_now if p['team'] == team_side]
        
        if not team_possessions:
            return self._get_empty_team_metrics()
        
        # Calculate cumulative metrics
        total_duration_ms = sum(p['total_duration_ms'] for p in team_possessions)
        possession_count = len(team_possessions)
        avg_duration_ms = total_duration_ms / possession_count if possession_count > 0 else 0
        
        # Calculate touches and passes
        total_touches = sum(p['total_touches'] for p in team_possessions)
        total_passes = max(total_touches - possession_count, 0)
        avg_passes = total_passes / possession_count if possession_count > 0 else 0
        
        # Calculate turnovers using the FULL possession list, not just up to now
        turnovers = self._calculate_team_turnovers(all_possessions, team_side)
        
        # Calculate longest possession
        longest_possession_ms = max(p['total_duration_ms'] for p in team_possessions) if team_possessions else 0
        
        # Calculate possession percentage using full data
        total_all_teams_duration = sum(p['total_duration_ms'] for p in all_possessions)
        possession_percentage = (total_duration_ms / total_all_teams_duration * 100) if total_all_teams_duration > 0 else 0
        
        return {
            'possession_count': possession_count,
            'possession_time_ms': total_duration_ms,
            'avg_duration_ms': avg_duration_ms,
            'total_touches': total_touches,
            'total_passes': total_passes,
            'avg_passes': avg_passes,
            'turnovers': turnovers,
            'longest_possession_ms': longest_possession_ms,
            'possession_percentage': possession_percentage
        }

    def _calculate_player_metrics_for_possession(self, possession, session, cumulative_player_metrics):
        """Calculate player metrics for a specific possession"""
        player_metrics = {}
        
        # Get all players in the session
        players = session.trace_players.all()
        
        for player in players:
            team_side = 'home' if 'home' in player.team_name.lower() else 'away'
            player_id = f"{team_side}_{player.jersey_number}"
            
            # Check if this player was involved in this possession
            if player.object_id in possession['players_involved']:
                # Update cumulative metrics
                if player_id not in cumulative_player_metrics:
                    cumulative_player_metrics[player_id] = {
                        'involvement_count': 0,
                        'total_duration_ms': 0,
                        'total_touches': 0
                    }
                
                cumulative_player_metrics[player_id]['involvement_count'] += 1
                cumulative_player_metrics[player_id]['total_duration_ms'] += possession['total_duration_ms']
                cumulative_player_metrics[player_id]['total_touches'] += possession['total_touches']
            
            # Calculate current metrics
            if player_id in cumulative_player_metrics:
                cum_metrics = cumulative_player_metrics[player_id]
                involvement_count = cum_metrics['involvement_count']
                total_duration_ms = cum_metrics['total_duration_ms']
                total_touches = cum_metrics['total_touches']
                
                avg_duration_ms = total_duration_ms / involvement_count if involvement_count > 0 else 0
                avg_touches = total_touches / involvement_count if involvement_count > 0 else 0
                
                # Calculate involvement percentage (simplified - would need total team possessions)
                involvement_percentage = 0  # This would need to be calculated with total team possessions
                
                player_metrics[player_id] = {
                    'involvement_count': involvement_count,
                    'total_duration_ms': total_duration_ms,
                    'avg_duration_ms': avg_duration_ms,
                    'total_touches': total_touches,
                    'avg_touches': avg_touches,
                    'involvement_percentage': involvement_percentage
                }
            else:
                # Player not involved yet
                player_metrics[player_id] = {
                    'involvement_count': 0,
                    'total_duration_ms': 0,
                    'avg_duration_ms': 0,
                    'total_touches': 0,
                    'avg_touches': 0,
                    'involvement_percentage': 0
                }
        
        return player_metrics

    def _compute_possession_segments(self, session):
        """Compute possession segments for each highlight with touch-chain tags"""
        try:
            self.logger.info(f"Starting possession segments calculation for session {session.session_id}")
            
            # Get highlights with touch-chain tags, ordered by start_offset
            highlights = session.highlights.filter(
                tags__contains=['touch-chain']
            ).order_by('start_offset')
            
            if not highlights.exists():
                self.logger.warning(f"No touch-chain highlights found for session {session.session_id}")
                return False
            
            # Clear existing segments for this session
            TracePossessionSegment.objects.filter(session=session).delete()
            
            # Calculate segments for each highlight
            segments_created = 0
            for highlight in highlights:
                # Determine team side from highlight tags
                team_side = self._get_team_side_from_highlight(highlight)
                if not team_side:
                    continue
                
                # Calculate cumulative metrics up to this highlight
                segment_metrics = self._calculate_highlight_segment_metrics(
                    highlight, highlights, team_side, session
                )
                
                # Create segment with both team and player data
                segment = TracePossessionSegment.objects.create(
                session=session,
                    highlight=highlight,
                    side=team_side,
                    start_ms=highlight.start_offset,
                    end_ms=highlight.start_offset + highlight.duration,
                    team_metrics=segment_metrics['team'],
                    player_metrics=segment_metrics['player']
                )
                segments_created += 1
                
                self.logger.debug(f"Created segment for highlight {highlight.highlight_id}: {team_side} team")
            
            self.logger.info(f"Successfully created {segments_created} possession segments for session {session.session_id}")
            return True

        except Exception as e:
            self.logger.exception(f"Error computing possession segments for session {session.session_id}: {e}")
            return False

    def _get_team_side_from_highlight(self, highlight):
        """Extract team side from highlight tags"""
        tags = highlight.tags or []
        if 'home' in tags:
            return 'home'
        elif 'away' in tags:
            return 'away'
            return None

    def _calculate_highlight_segment_metrics(self, current_highlight, all_highlights, team_side, session):
        """Calculate cumulative possession metrics up to this highlight"""
        
        # Get all previous highlights of the same team up to this point
        previous_highlights = all_highlights.filter(
            start_offset__lte=current_highlight.start_offset,
            tags__contains=[team_side]
        ).order_by('start_offset')
        
        # Calculate cumulative team metrics
        team_metrics = self._calculate_cumulative_team_metrics(previous_highlights, team_side, session)
        
        # Calculate player metrics for this specific highlight's player
        player_metrics = self._calculate_player_highlight_metrics(current_highlight, session)
        
        return {
            'team': team_metrics,
            'player': player_metrics
        }

    def _calculate_cumulative_team_metrics(self, highlights, team_side, session):
        """Calculate cumulative team metrics from highlights"""
        
        if not highlights.exists():
            return self._get_empty_team_metrics()
        
        # Group consecutive highlights into possessions
        possessions = self._group_highlights_into_possessions(highlights, team_side)
        
        # Calculate metrics from possessions
        total_duration_ms = sum(p['duration_ms'] for p in possessions)
        possession_count = len(possessions)
        avg_duration_ms = total_duration_ms / possession_count if possession_count > 0 else 0
        
        # Calculate touches and passes
        total_touches = sum(p['touches'] for p in possessions)
        total_passes = max(total_touches - possession_count, 0)
        avg_passes = total_passes / possession_count if possession_count > 0 else 0
        
        # Calculate turnovers (number of times possession was lost)
        turnovers = self._calculate_turnovers_from_highlights(highlights, team_side)
        
        # Calculate possession percentage (need total game time)
        total_game_time_ms = self._get_total_game_time_ms(session)
        possession_percentage = (total_duration_ms / total_game_time_ms * 100) if total_game_time_ms > 0 else 0
        
        return {
            'possession_percentage': round(possession_percentage, 1),
            'turnovers': turnovers,
            'total_passes': total_passes,
            'total_touches': total_touches,
            'possession_count': possession_count,
            'possession_time_ms': round(total_duration_ms, 1),
            'avg_duration_ms': round(avg_duration_ms, 1),
            'avg_passes': round(avg_passes, 2),
            'longest_possession_ms': round(max(p['duration_ms'] for p in possessions), 1) if possessions else 0
        }

    def _calculate_player_highlight_metrics(self, highlight, session):
        """Calculate player metrics for a specific highlight"""
        
        if not highlight.player:
            return self._get_empty_highlight_player_metrics()
        
        # Get all possessions this player was involved in up to this point
        player_highlights = session.highlights.filter(
            player=highlight.player,
            start_offset__lte=highlight.start_offset,
            tags__contains=['touch-chain']
        ).order_by('start_offset')
        
        # Calculate player involvement
        involvement_count = player_highlights.count()
        total_touches = sum(len(h.tags or []) for h in player_highlights)  # Approximate touches
        avg_touches = total_touches / involvement_count if involvement_count > 0 else 0
        
        # Calculate involvement percentage
        team_side = self._get_team_side_from_highlight(highlight)
        team_highlights = session.highlights.filter(
            tags__contains=[team_side],
            start_offset__lte=highlight.start_offset
        ).count()
        involvement_percentage = (involvement_count / team_highlights * 100) if team_highlights > 0 else 0
        
        return {
            'involvement_count': involvement_count,
            'total_touches': total_touches,
            'avg_touches': round(avg_touches, 2),
            'involvement_percentage': round(involvement_percentage, 1)
        }

    def _group_highlights_into_possessions(self, highlights, team_side):
        """Group consecutive highlights into possession chains"""
        possessions = []
        current_possession = None
        
        for highlight in highlights:
            if current_possession is None:
                # Start new possession
                current_possession = {
                    'duration_ms': highlight.duration,
                    'touches': len(highlight.tags or []),
                    'start_ms': highlight.start_offset
                }
            else:
                # Check if this highlight continues the possession
                time_gap = highlight.start_offset - (current_possession['start_ms'] + current_possession['duration_ms'])
                if time_gap <= 5000:  # 5 second gap threshold
                    # Continue possession
                    current_possession['duration_ms'] += highlight.duration
                    current_possession['touches'] += len(highlight.tags or [])
                else:
                    # Save current possession and start new one
                    possessions.append(current_possession)
                    current_possession = {
                        'duration_ms': highlight.duration,
                        'touches': len(highlight.tags or []),
                        'start_ms': highlight.start_offset
                    }
        
        # Add the last possession
        if current_possession:
            possessions.append(current_possession)
        
        return possessions

    def _calculate_turnovers_from_highlights(self, highlights, team_side):
        """Calculate turnovers from highlight sequence"""
        turnovers = 0
        highlights_list = list(highlights)
        
        for i, highlight in enumerate(highlights_list):
            if i + 1 < len(highlights_list):
                next_highlight = highlights_list[i + 1]
                # Check if next highlight is from different team
                next_team_side = self._get_team_side_from_highlight(next_highlight)
                if next_team_side and next_team_side != team_side:
                    turnovers += 1
        
        return turnovers

    def _get_total_game_time_ms(self, session):
        """Get total game time in milliseconds"""
        # from .utils import parse_time_to_seconds
        
        if session.match_start_time and session.match_end_time:
            start_seconds = parse_time_to_seconds(session.match_start_time)
            end_seconds = parse_time_to_seconds(session.match_end_time)
            return (end_seconds - start_seconds) * 1000
        return 90 * 60 * 1000  # Default 90 minutes

    def _get_empty_team_metrics(self):
        """Return empty team metrics structure"""
        return {
            'possession_percentage': 0.0,
            'turnovers': 0,
            'total_passes': 0,
            'total_touches': 0,
            'possession_count': 0,
            'possession_time_ms': 0.0,
            'avg_duration_ms': 0.0,
            'avg_passes': 0.0,
            'longest_possession_ms': 0.0
        }

    def _get_empty_highlight_player_metrics(self):
        """Return empty player metrics structure for highlights"""
        return {
            'involvement_count': 0,
            'total_touches': 0,
            'avg_touches': 0.0,
            'involvement_percentage': 0.0
        }

    def validate_segment_totals(self, session):
        """Validate that segment totals match final possession stats"""
        try:
            # from .models import TracePossessionStats, TracePossessionSegment
            
            # Get final possession stats
            final_team_stats = TracePossessionStats.objects.filter(
                session=session,
                possession_type='team'
            )
            
            # Calculate totals from segments
            segments = TracePossessionSegment.objects.filter(session=session)
            
            for team_stat in final_team_stats:
                team_side = team_stat.side
                team_segments = segments.filter(side=team_side)
                
                # Calculate cumulative totals
                cumulative_turnovers = sum(s.team_metrics.get('turnovers', 0) for s in team_segments)
                cumulative_passes = sum(s.team_metrics.get('total_passes', 0) for s in team_segments)
                cumulative_touches = sum(s.team_metrics.get('total_touches', 0) for s in team_segments)
                
                # Validate
                final_metrics = team_stat.metrics
                assert cumulative_turnovers == final_metrics.get('turnovers', 0), f"Turnovers mismatch for {team_side}"
                assert cumulative_passes == final_metrics.get('total_passes', 0), f"Passes mismatch for {team_side}"
                assert cumulative_touches == final_metrics.get('total_touches', 0), f"Touches mismatch for {team_side}"
                
            self.logger.info(f"Segment validation passed for session {session.session_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Segment validation failed for session {session.session_id}: {e}")
            return False



    # def _compute_coach_report(self, session):
    #     from .models import TraceCoachReportTeam
    #     # Basic totals based on highlights and simple heuristics
    #     highlights = session.highlights.all().values('tags', 'start_offset', 'duration')
    #     side_to_passes = {'home': 0, 'away': 0}
    #     side_to_possession_ms = {'home': 0, 'away': 0}
    #     for h in highlights:
    #         tags = h['tags'] or []
    #         if 'touch' in tags:
    #             # possession by tag side if present else infer later
    #             if 'home' in tags:
    #                 side_to_possession_ms['home'] += h['duration'] or 0
    #             if 'away' in tags:
    #                 side_to_possession_ms['away'] += h['duration'] or 0
    #         if 'touch-chain' in tags:
    #             if 'home' in tags:
    #                 side_to_passes['home'] += 1
    #             if 'away' in tags:
    #                 side_to_passes['away'] += 1
    #     # Upsert for both sides
    #     for side in ['home', 'away']:
    #         TraceCoachReportTeam.objects.update_or_create(
    #             session=session, side=side,
    #             defaults={
    #                 'goals': 0,  # not provided by TraceVision
    #                 'shots': 0,  # not provided by TraceVision
    #                 'passes': side_to_passes[side],
    #                 'possession_time_s': (side_to_possession_ms[side] / 1000.0)
    #             }
    #         )
    #     return True

    # def _compute_touch_leaderboard(self, session):
    #     from .models import TraceTouchLeaderboard, TraceHighlight, TraceHighlightObject
    #     # Count touches per player - SQLite compatible approach
    #     touch_highlights = TraceHighlight.objects.filter(session=session)
    #     counts = {}
    #     for h in touch_highlights:
    #         # Check if 'touch' is in tags (SQLite compatible)
    #         if h.tags and 'touch' in h.tags:
    #             objs = h.highlight_objects.all().select_related('trace_object', 'player')
    #             # If no explicit objects, we cannot attribute; skip
    #             for ho in objs:
    #                 if ho.player:
    #                     player = ho.player
    #                     side = ho.trace_object.side if ho.trace_object else 'unknown'
    #                     counts.setdefault((player, side), 0)
    #                     counts[(player, side)] += 1
    #     # Upsert
    #     for (player, side), c in counts.items():
    #         TraceTouchLeaderboard.objects.update_or_create(
    #             session=session, player=player,
    #             defaults={'object_side': side, 'touches': c}
    #         )
    #     return True

    # def _compute_passes(self, session):
    #     # Derive naive passes from consecutive touch highlights by same side and different players
    #     from .models import TracePass, TraceHighlight
    #     # SQLite compatible approach - filter in Python
    #     all_highlights = list(TraceHighlight.objects.filter(
    #         session=session).order_by('start_offset'))
    #     hs = [h for h in all_highlights if h.tags and 'touch' in h.tags]
    #     # Prepare player involvement per highlight
    #     h_players = {}
    #     for h in hs:
    #         players = [ho.player for ho in h.highlight_objects.all(
    #         ).select_related('trace_object', 'player') if ho.player]
    #         side = 'home' if 'home' in (
    #             h.tags or []) else 'away' if 'away' in (h.tags or []) else None
    #         h_players[h.highlight_id] = {
    #             'players': players, 'side': side, 'start': h.start_offset, 'dur': h.duration}
    #     # Build transitions
    #     for i in range(1, len(hs)):
    #         prev = h_players.get(hs[i-1].highlight_id)
    #         curr = h_players.get(hs[i].highlight_id)
    #         if not prev or not curr:
    #             continue
    #         if prev['side'] and curr['side'] and prev['side'] == curr['side'] and prev['players'] and curr['players']:
    #             # Create a pass from last toucher to first next toucher
    #             TracePass.objects.create(
    #                 session=session,
    #                 side=curr['side'],
    #                 from_player=prev['players'][-1],
    #                 to_player=curr['players'][0],
    #                 start_ms=curr['start'],
    #                 duration_ms=curr['dur'] or 0
    #             )
    #     return True

    # def _compute_passing_network(self, session):
    #     from django.db.models import Count
    #     from .models import TracePass, TracePassingNetwork
    #     qs = TracePass.objects.filter(session=session).values(
    #         'side', 'from_player', 'to_player').annotate(c=Count('id'))
    #     for row in qs:
    #         TracePassingNetwork.objects.update_or_create(
    #             session=session,
    #             side=row['side'],
    #             from_player_id=row['from_player'],
    #             to_player_id=row['to_player'],
    #             defaults={'passes_count': row['c']}
    #         )
    #     return True

    # def convert_game_time_to_video_milliseconds(self, session, game_minute, game_second=0):
    #     """
    #     Convert game time (minute:second) to video milliseconds using session timeline data.

    #     This method delegates to the centralized utility function in utils.py.

    #     Args:
    #         session (TraceSession): Session with timeline data
    #         game_minute (int): Game minute (0-90+)
    #         game_second (int): Game second (0-59)

    #     Returns:
    #         int: Milliseconds from video start, or 0 if conversion fails
    #     """
    #     from .utils import convert_game_time_to_video_milliseconds as utils_convert
    #     return utils_convert(session, game_minute, game_second)


# class TraceVisionStatsService:
#     """
#     Service for calculating player and team performance statistics from tracking data
#     Generates comprehensive performance metrics for post-match analysis
#     """

#     def __init__(self):
#         self.logger = logging.getLogger(__name__)

#         # Configuration constants for calculations
#         # m/s - speed above which is considered sprinting
#         self.SPRINT_SPEED_THRESHOLD = 7.0
#         self.SPRINT_DURATION_MIN = 1.0      # seconds - minimum duration for a sprint
#         # Approximate conversion (adjust based on field size)
#         self.PIXEL_TO_METER_RATIO = 0.1
#         self.FRAME_RATE = 30                # FPS - frames per second for time calculations

#     def calculate_session_stats(self, session):
#         """
#         Calculate comprehensive statistics for an entire session

#         Args:
#             session: TraceSession instance

#         Returns:
#             dict: Calculation results with success status and details
#         """
#         try:
#             self.logger.info(
#                 f"Starting stats calculation for session {session.session_id}")

#             # Get all trace players from the session
#             trace_players = session.trace_players.all()

#             if not trace_players.exists():
#                 return {
#                     'success': False,
#                     'error': 'No trace players found',
#                     'session_id': session.session_id
#                 }

#             # Calculate individual player stats
#             player_stats_results = []
#             for player in trace_players:
#                 try:
#                     stats = self._calculate_player_stats(session, player)
#                     if stats:
#                         player_stats_results.append(stats)
#                         self.logger.info(
#                             f"Calculated stats for {player.object_id}")
#                 except Exception as e:
#                     self.logger.exception(
#                         f"Error calculating stats for {player.object_id}: {e}")

#             # Calculate team-level stats
#             team_stats = self._calculate_team_stats(
#                 session, player_stats_results)

#             # Create session-level stats
#             session_stats = self._create_session_stats(
#                 session, player_stats_results, team_stats)

#             self.logger.info(f"Stats calculation completed for session {session.session_id}: "
#                              f"{len(player_stats_results)} players processed")

#             return {
#                 'success': True,
#                 'player_stats_count': len(player_stats_results),
#                 'team_stats': team_stats,
#                 'session_stats': session_stats,
#                 'session_id': session.session_id
#             }

#         except Exception as e:
#             self.logger.exception(
#                 f"Error in session stats calculation for {session.session_id}: {e}")
#             return {
#                 'success': False,
#                 'error': str(e),
#                 'session_id': session.session_id
#             }

#     def _calculate_player_stats(self, session, trace_player):
#         """
#         Calculate comprehensive stats for a single trace player

#         Args:
#             session: TraceSession instance
#             trace_player: TracePlayer instance

#         Returns:
#             TraceVisionPlayerStats instance or None if failed
#         """
#         try:
#             from .models import TraceVisionPlayerStats

#             # Get tracking data for this player
#             tracking_data = self._get_player_tracking_data(trace_player)

#             if not tracking_data:
#                 self.logger.warning(
#                     f"No tracking data found for {trace_player.object_id}")
#                 return None

#             # Calculate basic movement stats
#             distance_stats = self._calculate_distance_stats(tracking_data)
#             speed_stats = self._calculate_speed_stats(tracking_data)
#             sprint_stats = self._calculate_sprint_stats(tracking_data)
#             position_stats = self._calculate_position_stats(tracking_data)

#             # Generate heatmap data
#             heatmap_data = self._generate_heatmap_data(tracking_data)

#             # Calculate performance metrics
#             performance_score = self._calculate_performance_score(
#                 distance_stats, speed_stats, sprint_stats, position_stats
#             )

#             stamina_rating = self._calculate_stamina_rating(
#                 speed_stats, sprint_stats)
#             work_rate = self._calculate_work_rate(distance_stats, speed_stats)

#             # Determine side from object_id
#             side = self._extract_side_from_object_id(trace_player.object_id)

#             # Create or update player stats
#             stats, created = TraceVisionPlayerStats.objects.update_or_create(
#                 session=session,
#                 player=trace_player,
#                 defaults={
#                     'side': side,

#                     # Movement stats
#                     'total_distance_meters': distance_stats['total_distance'],
#                     'avg_speed_mps': speed_stats['avg_speed'],
#                     'max_speed_mps': speed_stats['max_speed'],
#                     'total_time_seconds': distance_stats['total_time'],

#                     # Sprint stats
#                     'sprint_count': sprint_stats['sprint_count'],
#                     'sprint_distance_meters': sprint_stats['sprint_distance'],
#                     'sprint_time_seconds': sprint_stats['sprint_time'],

#                     # Position stats
#                     'avg_position_x': position_stats['avg_x'],
#                     'avg_position_y': position_stats['avg_y'],
#                     'position_variance': position_stats['variance'],

#                     # Performance metrics
#                     'heatmap_data': heatmap_data,
#                     'performance_score': performance_score,
#                     'stamina_rating': stamina_rating,
#                     'work_rate': work_rate,

#                     'calculation_method': 'standard',
#                     'calculation_version': '1.0'
#                 }
#             )

#             if created:
#                 self.logger.info(
#                     f"Created new stats for {trace_player.object_id}")
#             else:
#                 self.logger.info(
#                     f"Updated existing stats for {trace_player.object_id}")

#             return stats

#         except Exception as e:
#             self.logger.exception(
#                 f"Error calculating stats for {trace_player.object_id}: {e}")
#             return None

#     def _extract_side_from_object_id(self, object_id):
#         """Extract side (home/away) from object_id"""
#         try:
#             if '_' in object_id:
#                 side = object_id.split('_')[0]
#             elif '-' in object_id:
#                 side = object_id.split('-')[0]
#             else:
#                 side = 'unknown'

#             return side.lower()
#         except:
#             return 'unknown'

#     def _get_player_tracking_data(self, trace_player):
#         """Get tracking data for a specific trace player"""
#         try:
#             # Get the trace object associated with this player
#             trace_object = trace_player.trace_objects.filter(
#                 session=trace_player.session).first()

#             if not trace_object:
#                 self.logger.warning(
#                     f"No trace object found for player {trace_player.object_id}")
#                 return None

#             # Check if we have tracking data in the JSON field
#             if trace_object.tracking_data:
#                 # If it's the raw TraceVision format with 'spotlights', extract the array
#                 if isinstance(trace_object.tracking_data, dict) and 'spotlights' in trace_object.tracking_data:
#                     return trace_object.tracking_data['spotlights']
#                 # If it's already a list of points, return as is
#                 elif isinstance(trace_object.tracking_data, list):
#                     return trace_object.tracking_data
#                 else:
#                     return None

#             # If no tracking data available, return None
#             return None

#         except Exception as e:
#             self.logger.exception(
#                 f"Error getting tracking data for {trace_player.object_id}: {e}")
#             return None

#     def _calculate_distance_stats(self, tracking_data):
#         """Calculate distance-related statistics"""
#         try:
#             total_distance = 0.0
#             total_time = 0.0

#             for i in range(1, len(tracking_data)):
#                 prev_point = tracking_data[i-1]
#                 curr_point = tracking_data[i]

#                 # Calculate distance between consecutive points
#                 dx = curr_point[1] - prev_point[1]  # x difference
#                 dy = curr_point[2] - prev_point[2]  # y difference

#                 # Convert to meters using pixel ratio
#                 distance = ((dx**2 + dy**2)**0.5) * self.PIXEL_TO_METER_RATIO
#                 total_distance += distance

#                 # Calculate time difference (convert to seconds)
#                 time_diff = (curr_point[0] - prev_point[0]
#                              ) / 1000.0  # ms to seconds
#                 total_time += time_diff

#             return {
#                 'total_distance': total_distance,
#                 'total_time': total_time,
#                 'avg_speed': total_distance / total_time if total_time > 0 else 0.0
#             }

#         except Exception as e:
#             self.logger.exception(f"Error calculating distance stats: {e}")
#             return {'total_distance': 0.0, 'total_time': 0.0, 'avg_speed': 0.0}

#     def _calculate_speed_stats(self, tracking_data):
#         """Calculate speed-related statistics"""
#         try:
#             speeds = []

#             for i in range(1, len(tracking_data)):
#                 prev_point = tracking_data[i-1]
#                 curr_point = tracking_data[i]

#                 # Calculate distance
#                 dx = curr_point[1] - prev_point[1]
#                 dy = curr_point[2] - prev_point[2]
#                 distance = ((dx**2 + dy**2)**0.5) * self.PIXEL_TO_METER_RATIO

#                 # Calculate time
#                 time_diff = (curr_point[0] - prev_point[0]) / 1000.0

#                 if time_diff > 0:
#                     speed = distance / time_diff
#                     speeds.append(speed)

#             if speeds:
#                 return {
#                     'avg_speed': sum(speeds) / len(speeds),
#                     'max_speed': max(speeds),
#                     'min_speed': min(speeds),
#                     'speed_variance': self._calculate_variance(speeds)
#                 }
#             else:
#                 return {'avg_speed': 0.0, 'max_speed': 0.0, 'min_speed': 0.0, 'speed_variance': 0.0}

#         except Exception as e:
#             self.logger.exception(f"Error calculating speed stats: {e}")
#             return {'avg_speed': 0.0, 'max_speed': 0.0, 'min_speed': 0.0, 'speed_variance': 0.0}

#     def _calculate_sprint_stats(self, tracking_data):
#         """Calculate sprint-related statistics"""
#         try:
#             sprints = []
#             current_sprint = None

#             for i in range(1, len(tracking_data)):
#                 prev_point = tracking_data[i-1]
#                 curr_point = tracking_data[i]

#                 # Calculate speed for this segment
#                 dx = curr_point[1] - prev_point[1]
#                 dy = curr_point[2] - prev_point[2]
#                 distance = ((dx**2 + dy**2)**0.5) * self.PIXEL_TO_METER_RATIO
#                 time_diff = (curr_point[0] - prev_point[0]) / 1000.0

#                 if time_diff > 0:
#                     speed = distance / time_diff

#                     # Check if this is a sprint
#                     if speed >= self.SPRINT_SPEED_THRESHOLD:
#                         if current_sprint is None:
#                             # Start new sprint
#                             current_sprint = {
#                                 'start_time': prev_point[0],
#                                 'start_distance': sum([
#                                     ((tracking_data[j][1] - tracking_data[j-1][1])**2 +
#                                      (tracking_data[j][2] - tracking_data[j-1][2])**2)**0.5 * self.PIXEL_TO_METER_RATIO
#                                     for j in range(1, i)
#                                 ])
#                             }
#                     else:
#                         if current_sprint is not None:
#                             # End current sprint
#                             current_sprint['end_time'] = prev_point[0]
#                             current_sprint['duration'] = (
#                                 current_sprint['end_time'] - current_sprint['start_time']) / 1000.0

#                             # Only count sprints that meet minimum duration
#                             if current_sprint['duration'] >= self.SPRINT_DURATION_MIN:
#                                 sprints.append(current_sprint)

#                             current_sprint = None

#             # Handle case where sprint continues to end of data
#             if current_sprint is not None:
#                 current_sprint['end_time'] = tracking_data[-1][0]
#                 current_sprint['duration'] = (
#                     current_sprint['end_time'] - current_sprint['start_time']) / 1000.0
#                 if current_sprint['duration'] >= self.SPRINT_DURATION_MIN:
#                     sprints.append(current_sprint)

#             # Calculate sprint statistics
#             sprint_count = len(sprints)
#             sprint_distance = sum([
#                 ((tracking_data[sprint['end_time']][1] - tracking_data[sprint['start_time']][1])**2 +
#                  (tracking_data[sprint['end_time']][2] - tracking_data[sprint['start_time']][2])**2)**0.5 * self.PIXEL_TO_METER_RATIO
#                 for sprint in sprints
#             ])
#             sprint_time = sum([sprint['duration'] for sprint in sprints])

#             return {
#                 'sprint_count': sprint_count,
#                 'sprint_distance': sprint_distance,
#                 'sprint_time': sprint_time,
#                 'sprint_details': sprints
#             }

#         except Exception as e:
#             self.logger.exception(f"Error calculating sprint stats: {e}")
#             return {'sprint_count': 0, 'sprint_distance': 0.0, 'sprint_time': 0.0, 'sprint_details': []}

#     def _calculate_position_stats(self, tracking_data):
#         """Calculate position-related statistics"""
#         try:
#             x_coords = [point[1] for point in tracking_data]
#             y_coords = [point[2] for point in tracking_data]

#             avg_x = sum(x_coords) / len(x_coords)
#             avg_y = sum(y_coords) / len(y_coords)

#             # Calculate variance (movement range)
#             x_variance = self._calculate_variance(x_coords)
#             y_variance = self._calculate_variance(y_coords)
#             total_variance = (x_variance + y_variance) / 2

#             return {
#                 'avg_x': avg_x,
#                 'avg_y': avg_y,
#                 'variance': total_variance,
#                 'x_range': max(x_coords) - min(x_coords),
#                 'y_range': max(y_coords) - min(y_coords)
#             }

#         except Exception as e:
#             self.logger.exception(f"Error calculating position stats: {e}")
#             return {'avg_x': 0.0, 'avg_y': 0.0, 'variance': 0.0, 'x_range': 0.0, 'y_range': 0.0}

#     def _generate_heatmap_data(self, tracking_data):
#         """Generate heatmap grid data for visualization"""
#         try:
#             # Create a 20x20 grid (400 cells) for heatmap
#             grid_size = 20
#             heatmap = [[0 for _ in range(grid_size)] for _ in range(grid_size)]

#             for point in tracking_data:
#                 x, y = point[1], point[2]

#                 # Convert 0-1000 coordinates to grid coordinates
#                 grid_x = int((x / 1000.0) * grid_size)
#                 grid_y = int((y / 1000.0) * grid_size)

#                 # Ensure coordinates are within bounds
#                 grid_x = max(0, min(grid_size - 1, grid_x))
#                 grid_y = max(0, min(grid_size - 1, grid_y))

#                 # Increment heatmap value
#                 heatmap[grid_y][grid_x] += 1

#             return {
#                 'grid_size': grid_size,
#                 'data': heatmap,
#                 'max_value': max(max(row) for row in heatmap),
#                 'total_points': len(tracking_data)
#             }

#         except Exception as e:
#             self.logger.exception(f"Error generating heatmap data: {e}")
#             return {'grid_size': 20, 'data': [], 'max_value': 0, 'total_points': 0}


#     def _calculate_performance_score(self, distance_stats, speed_stats, sprint_stats, position_stats):
#         """Calculate overall performance score (0-100)"""
#         try:
#             # Weighted scoring system
#             # Max 25 points for distance
#             distance_score = min(
#                 distance_stats['total_distance'] / 10000.0 * 25, 25)
#             # Max 25 points for speed
#             speed_score = min(speed_stats['max_speed'] / 10.0 * 25, 25)
#             # Max 25 points for sprints
#             sprint_score = min(sprint_stats['sprint_count'] / 10.0 * 25, 25)
#             # Max 25 points for movement
#             position_score = min(position_stats['variance'] / 100.0 * 25, 25)

#             total_score = distance_score + speed_score + sprint_score + position_score

#             return min(total_score, 100.0)  # Cap at 100

#         except Exception as e:
#             self.logger.exception(f"Error calculating performance score: {e}")
#             return 0.0

#     def _calculate_stamina_rating(self, speed_stats, sprint_stats):
#         """Calculate stamina rating based on speed consistency and sprint patterns"""
#         try:
#             # Base stamina on speed variance (lower variance = better stamina)
#             speed_consistency = max(
#                 0, 10 - speed_stats.get('speed_variance', 0))

#             # Boost stamina for multiple sprints
#             sprint_bonus = min(sprint_stats.get('sprint_count', 0) * 2, 20)

#             stamina = speed_consistency + sprint_bonus

#             return min(stamina, 100.0)  # Cap at 100

#         except Exception as e:
#             self.logger.exception(f"Error calculating stamina rating: {e}")
#             return 0.0

#     def _calculate_work_rate(self, distance_stats, speed_stats):
#         """Calculate work rate based on distance and speed"""
#         try:
#             # Work rate = distance * average speed
#             work_rate = distance_stats['total_distance'] * \
#                 speed_stats['avg_speed']

#             # Normalize to 0-100 scale
#             normalized_rate = min(work_rate / 1000.0, 100.0)

#             return normalized_rate

#         except Exception as e:
#             self.logger.exception(f"Error calculating work rate: {e}")
#             return 0.0

#     def _calculate_variance(self, values):
#         """Calculate variance of a list of values"""
#         try:
#             if not values:
#                 return 0.0

#             mean = sum(values) / len(values)
#             squared_diff_sum = sum((x - mean) ** 2 for x in values)
#             variance = squared_diff_sum / len(values)

#             return variance

#         except Exception as e:
#             self.logger.exception(f"Error calculating variance: {e}")
#             return 0.0

#     def _calculate_team_stats(self, session, player_stats_list):
#         """Calculate aggregated team statistics"""
#         try:
#             team_stats = {
#                 'home': {'players': [], 'total_distance': 0, 'avg_speed': 0, 'total_sprints': 0},
#                 'away': {'players': [], 'total_distance': 0, 'avg_speed': 0, 'total_sprints': 0}
#             }

#             for stats in player_stats_list:
#                 side = stats.side
#                 if side in team_stats:
#                     team_stats[side]['players'].append(stats)
#                     team_stats[side]['total_distance'] += stats.total_distance_meters
#                     team_stats[side]['total_sprints'] += stats.sprint_count

#             # Calculate averages
#             for side in ['home', 'away']:
#                 if team_stats[side]['players']:
#                     player_count = len(team_stats[side]['players'])
#                     team_stats[side]['avg_speed'] = team_stats[side]['total_distance'] / \
#                         player_count if player_count > 0 else 0
#                     team_stats[side]['avg_distance_per_player'] = team_stats[side]['total_distance'] / \
#                         player_count if player_count > 0 else 0

#             return team_stats

#         except Exception as e:
#             self.logger.exception(f"Error calculating team stats: {e}")
#             return {}

#     def _create_session_stats(self, session, player_stats_list, team_stats):
#         """Create session-level statistics"""
#         try:
#             from .models import TraceVisionSessionStats

#             # Calculate data quality metrics
#             total_tracking_points = 0
#             for stats in player_stats_list:
#                 # Get tracking data from the player's trace object
#                 trace_object = stats.player.trace_objects.filter(
#                     session=session).first()
#                 if trace_object and trace_object.tracking_data:
#                     if isinstance(trace_object.tracking_data, dict) and 'spotlights' in trace_object.tracking_data:
#                         total_tracking_points += len(
#                             trace_object.tracking_data['spotlights'])
#                     elif isinstance(trace_object.tracking_data, list):
#                         total_tracking_points += len(
#                             trace_object.tracking_data)

#             # Estimate data coverage (simplified calculation)
#             # Normalize to percentage
#             data_coverage = min(100.0, (total_tracking_points / 1000.0) * 100)

#             # Calculate quality score based on various factors
#             quality_score = self._calculate_data_quality_score(
#                 session, player_stats_list, total_tracking_points)

#             # Create or update session stats
#             session_stats, created = TraceVisionSessionStats.objects.update_or_create(
#                 session=session,
#                 defaults={
#                     'home_team_stats': team_stats.get('home', {}),
#                     'away_team_stats': team_stats.get('away', {}),
#                     'total_tracking_points': total_tracking_points,
#                     'data_coverage_percentage': data_coverage,
#                     'quality_score': quality_score,
#                     'processing_status': 'completed',
#                     'processing_errors': []
#                 }
#             )

#             return session_stats

#         except Exception as e:
#             self.logger.exception(f"Error creating session stats: {e}")
#             return None

#     def _calculate_data_quality_score(self, session, player_stats_list, total_tracking_points):
#         """Calculate overall data quality score"""
#         try:
#             score = 0.0

#             # Base score from tracking points
#             if total_tracking_points >= 1000:
#                 score += 30
#             elif total_tracking_points >= 500:
#                 score += 20
#             elif total_tracking_points >= 100:
#                 score += 10

#             # Score from player coverage
#             expected_players = 22  # 11 per team
#             actual_players = len(player_stats_list)
#             player_coverage = (actual_players / expected_players) * 100
#             # Max 40 points for player coverage
#             score += min(player_coverage * 0.4, 40)

#             # Score from data completeness
#             complete_stats = sum(
#                 1 for stats in player_stats_list if stats.total_distance_meters > 0)
#             completeness_score = (
#                 complete_stats / len(player_stats_list)) * 100 if player_stats_list else 0
#             # Max 30 points for completeness
#             score += min(completeness_score * 0.3, 30)

#             return min(score, 100.0)  # Cap at 100

#         except Exception as e:
#             self.logger.exception(f"Error calculating data quality score: {e}")
#             return 0.0
