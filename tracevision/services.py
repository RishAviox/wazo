import logging
import json
import requests
from datetime import datetime, timedelta
from django.core.cache import cache
from django.core.files.storage import default_storage
from django.conf import settings
from django.db.models import Q

from tracevision.models import (
    TraceClipReel,
    TraceHighlight,
    TracePlayer,
    TracePossessionSegment,
    TracePossessionStats,
)
from tracevision.utils import filter_highlights_by_game_time, parse_time_to_seconds

logger = logging.getLogger(__name__)


def save_possession_calculation_results(
    session, team_possession_data, player_possession_data
):
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
            team = session.home_team if side == "home" else session.away_team
            if not team:
                continue

            team_stats, created = TracePossessionStats.objects.update_or_create(
                session=session,
                possession_type="team",
                team=team,
                side=side,
                defaults={
                    "metrics": team_data  # Store all team data in single JSON field
                },
            )
            saved_team_stats.append(team_stats)

        # Save player possession involvement stats (1 row per player)
        for player_id, player_data in player_possession_data.items():
            try:
                # Extract jersey number from player_id (format: team_side_jersey)
                jersey_number = int(player_id.split("_")[-1])
                team_side = player_id.split("_")[0]

                # Find player by jersey number and team side
                # Get the team object first
                team = session.home_team if team_side == "home" else session.away_team
                if not team:
                    logger.warning(f"No team found for side {team_side}")
                    continue

                try:
                    player = session.players.get(
                        jersey_number=jersey_number, team=team
                    )
                except TracePlayer.DoesNotExist:
                    logger.warning(
                        f"Player {player_id} (jersey {jersey_number}, team {team.name}) not found in database, skipping"
                    )
                    continue

                player_stats, created = TracePossessionStats.objects.update_or_create(
                    session=session,
                    possession_type="player",
                    player=player,
                    defaults={
                        "team": player.team,  # Set the team field
                        "side": team_side,  # Set the side field
                        "metrics": player_data,  # Store cleaned player data
                    },
                )
                saved_player_stats.append(player_stats)

            except Exception as e:
                logger.warning(
                    f"Error saving player possession stats for player {player_id}: {e}"
                )
                continue

        return {
            "success": True,
            "team_stats_saved": len(saved_team_stats),
            "player_stats_saved": len(saved_player_stats),
            "session_id": session.session_id,
        }

    except Exception as e:
        logger.exception(f"Error saving possession calculation results: {e}")
        return {"success": False, "error": str(e), "session_id": session.session_id}


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
            settings, "TRACEVISION_STATUS_CACHE_TIMEOUT", 300
        )
        self.result_cache_timeout = getattr(
            settings, "TRACEVISION_RESULT_CACHE_TIMEOUT", 1800
        )

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
            logger.info(f"Force refreshing cache for session {session.session_id}")
            self._clear_cache_for_session(session.session_id)
        else:
            # Check cache first
            cached_data = self._get_cached_status_data(session.session_id)
            if cached_data:
                logger.info(
                    f"Using cached status data for session {session.session_id}"
                )
                return cached_data

        # Fetch from API
        logger.info(
            f"Fetching status from TraceVision API for session {session.session_id}"
        )
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
            logger.info(f"Using cached result data for session {session.session_id}")
            return cached_result

        # Fetch from API
        logger.info(
            f"Fetching result from TraceVision API for session {session.session_id}"
        )
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
                cached_data.get("cache_timestamp", "1970-01-01T00:00:00")
            )
            if datetime.now() - cache_timestamp < timedelta(
                seconds=self.status_cache_timeout
            ):
                cached_data["cached"] = True
                return cached_data

        return None

    def _cache_status_data(self, session_id, data):
        """Cache status data for a session."""
        cache_key = f"tracevision_status_{session_id}"
        cache.set(cache_key, data, self.status_cache_timeout)
        logger.info(
            f"Cached status data for session {session_id} with TTL {self.status_cache_timeout}s"
        )

    def _get_cached_result_data(self, session_id):
        """Get cached result data for a session."""
        cache_key = f"tracevision_result_{session_id}"
        return cache.get(cache_key)

    def _cache_result_data(self, session_id, data):
        """Cache result data for a session."""
        cache_key = f"tracevision_result_{session_id}"
        cache.set(cache_key, data, self.result_cache_timeout)
        logger.info(
            f"Cached result data for session {session_id} with TTL {self.result_cache_timeout}s"
        )

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

            res = requests.post(
                self.graphql_url,
                headers={"Content-Type": "application/json"},
                json=status_payload,
            )

            if res.status_code != 200:
                logger.info(
                    f"Failed to retrieve status for session {session.session_id}: {res.status_code}"
                )
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
                    f"No status data returned for session {session.session_id}"
                )
                return None

            return data

        except Exception as e:
            logger.exception(
                f"Error querying TraceVision status for session {session.session_id}: {e}"
            )
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

            result_response = requests.post(
                self.graphql_url,
                headers={"Content-Type": "application/json"},
                json=result_payload,
            )
            result_data = result_response.json().get("data", {}).get("sessionResult")

            if result_response.status_code == 200 and result_data:
                logger.info(
                    f"Successfully fetched result data for session {session.session_id}"
                )
                return result_data
            else:
                logger.error(f"Failed to fetch result for session {session.session_id}")
                return None

        except Exception as e:
            logger.exception(
                f"Error fetching result data for session {session.session_id}: {e}"
            )
            return None

    @staticmethod
    def import_game_video(session_id, video_link, start_time=None):
        """
        Import video from URL to TraceVision session.

        Args:
            session_id: TraceVision session ID
            video_link: URL to the video file
            start_time: Optional start time of the video (datetime)

        Returns:
            str: video_url_for_db (the video_link)

        Raises:
            Exception: If import fails
        """
        customer_id = int(settings.TRACEVISION_CUSTOMER_ID)
        api_key = settings.TRACEVISION_API_KEY
        graphql_url = settings.TRACEVISION_GRAPHQL_URL

        logger.info(f"Importing video from link for session {session_id}...")
        import_video_payload = {
            "query": """
                mutation ($token: CustomerToken!, $session_id: Int!, $video: ImportVideoInput!, $start_time: DateTime) {
                    importVideo(token: $token, session_id: $session_id, video: $video, start_time: $start_time) {
                        success
                        error
                    }
                }
            """,
            "variables": {
                "token": {"customer_id": customer_id, "token": api_key},
                "session_id": session_id,
                "video": {"type": "url", "via_url": {"url": video_link}},
                "start_time": start_time.isoformat() if start_time else None,
            },
        }

        import_response = requests.post(
            graphql_url,
            headers={"Content-Type": "application/json"},
            json=import_video_payload,
        )

        import_json = import_response.json()
        logger.info(f"Video import response: {import_json}")

        if import_response.status_code != 200 or not import_json.get("data", {}).get(
            "importVideo", {}
        ).get("success"):
            error_msg = (
                import_json.get("data", {})
                .get("importVideo", {})
                .get("error", "Unknown error")
            )
            raise Exception(f"Video import failed: {error_msg}")

        return video_link

    @staticmethod
    def upload_game_video(session_id, video_file):
        """
        Upload video file to TraceVision session.

        Args:
            session_id: TraceVision session ID
            video_file: Video file object to upload

        Returns:
            str: video_url_for_db (the upload_url)

        Raises:
            Exception: If upload fails
        """
        customer_id = int(settings.TRACEVISION_CUSTOMER_ID)
        api_key = settings.TRACEVISION_API_KEY
        graphql_url = settings.TRACEVISION_GRAPHQL_URL

        logger.info(f"Processing video file upload for session {session_id}...")

        # Get upload URL for file
        upload_payload = {
            "query": """
                mutation ($token: CustomerToken!, $session_id: Int!, $video_name: String!) {
                    uploadVideo(token: $token, session_id: $session_id, video_name: $video_name) {
                        success
                        error
                        upload_url
                    }
                }
            """,
            "variables": {
                "token": {"customer_id": customer_id, "token": api_key},
                "session_id": session_id,
                "video_name": video_file.name,
            },
        }

        upload_response = requests.post(
            graphql_url,
            headers={"Content-Type": "application/json"},
            json=upload_payload,
        )
        upload_json = upload_response.json()
        logger.debug(f"Upload URL response: {upload_json}")

        if upload_response.status_code != 200 or not upload_json.get("data", {}).get(
            "uploadVideo", {}
        ).get("success"):
            error_msg = (
                upload_json.get("data", {})
                .get("uploadVideo", {})
                .get("error", "Unknown error")
            )
            raise Exception(f"Failed to get video upload URL: {error_msg}")

        upload_url = upload_json["data"]["uploadVideo"]["upload_url"]

        # Upload video file
        logger.info("Uploading video file to TraceVision...")
        # Reset file pointer to beginning in case it was read before
        if hasattr(video_file, "seek"):
            video_file.seek(0)
        put_response = requests.put(
            upload_url, headers={"Content-Type": "video/mp4"}, data=video_file.read()
        )

        if put_response.status_code != 200:
            raise Exception(
                f"Video upload failed: status_code={put_response.status_code}, "
                f"text={put_response.text}"
            )

        return upload_url


class TraceVisionAggregationService:
    """Compute CSV-equivalent aggregates and store them in DB."""

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def _fetch_result_data_from_blob(self, session):
        """
        Fetch session result data from Azure blob storage using result_blob_url.

        Args:
            session: TraceSession instance with result_blob_url

        Returns:
            dict: Result data containing highlights and other session data, or None if failed
        """
        try:
            if not session.result_blob_url:
                self.logger.warning(
                    f"No result_blob_url found for session {session.session_id}"
                )
                return None

            blob_url = session.result_blob_url
            self.logger.info(
                f"Fetching result data from Azure blob for session {session.session_id}: {blob_url}"
            )

            # Extract relative path from full blob URL for default_storage operations
            if blob_url.startswith("https://"):
                # Extract relative path from full Azure blob URL
                # URL format: https://videostoragewajo.blob.core.windows.net/media/sessions/...
                # We need: sessions/...
                if "/media/" in blob_url:
                    relative_path = blob_url.split("/media/", 1)[1]
                else:
                    self.logger.error(f"Unexpected blob URL format: {blob_url}")
                    return None
            else:
                # Already a relative path
                relative_path = blob_url

            self.logger.info(
                f"Using relative path for storage operations: {relative_path}"
            )

            # Use Django's default storage to download the file
            if default_storage.exists(relative_path):
                # Read the file content
                with default_storage.open(relative_path, "r") as f:
                    result_data = json.load(f)

                self.logger.info(
                    f"Successfully fetched result data from Azure blob for session {session.session_id}"
                )
                return result_data
            else:
                self.logger.error(
                    f"Blob file not found: {relative_path} (original URL: {blob_url})"
                )
                return None

        except Exception as e:
            self.logger.exception(
                f"Error fetching result data from blob for session {session.session_id}: {e}"
            )
            return None

    def compute_all(self, session):
        """Compute all aggregates for a session in one shot."""
        results = {}
        # results['coach_report'] = self._compute_coach_report(session)
        # results['touch_leaderboard'] = self._compute_touch_leaderboard(session)
        results["possession_segments"] = self._compute_possessions(session)
        results["clips"] = self._compute_clips(session)
        # results['passes'] = self._compute_passes(session)
        # results['passing_network'] = self._compute_passing_network(session)
        return results

    def compute_possession_segments_only(self, session):
        """Compute only possession segments for a session (skip clips and other aggregates)."""
        results = {}
        results["possession_segments"] = self._compute_possessions(session)
        return results

    def _ms_to_clock(self, ms):
        s = int(ms / 1000)
        m, s = divmod(s, 60)
        h, m = divmod(m, 60)
        if h:
            return f"{h}:{m:02d}:{s:02d}.{int(ms % 1000):03d}"
        return f"{m}:{s:02d}.{int(ms % 1000):03d}"

    def _get_video_variant_name(self, tags=None, ratio=None, primary_player=None):
        """
        Generate a descriptive name for the video variant based on tags and ratio.

        Args:
            tags: List of tags (e.g., ["with_name_overlay", "with_circle_overlay"])
            ratio: Video ratio (e.g., "original", "9:16", "1:1")
            primary_player: Optional primary player object

        Returns:
            str: Descriptive name for the video variant
        """
        if not tags:
            tags = []

        # Build name parts based on tags
        name_parts = []

        # Determine overlay type from tags
        has_name_overlay = "with_name_overlay" in tags
        has_circle_overlay = "with_circle_overlay" in tags

        if not has_name_overlay and not has_circle_overlay:
            name_parts.append("Original")
        else:
            overlay_parts = []
            if has_name_overlay:
                overlay_parts.append("Name")
            if has_circle_overlay:
                overlay_parts.append("Circle")
            name_parts.append("With " + " & ".join(overlay_parts))

        # Add ratio information
        if ratio:
            if ratio == "9:16":
                name_parts.append("Vertical")
            elif ratio == "1:1":
                name_parts.append("Square")
            # "original" ratio doesn't need a suffix

        return " ".join(name_parts) if name_parts else "Video"

    def _compute_clips(self, session):
        # from .models import TraceClipReel, TraceHighlight
        hs = TraceHighlight.objects.filter(session=session)

        for h in hs:
            side = (
                "home"
                if "home" in (h.tags or [])
                else "away" if "away" in (h.tags or []) else ""
            )

            # Get all players involved in this highlight
            highlight_objects = h.highlight_objects.all().select_related(
                "trace_object", "player"
            )
            involved_players = [ho.player for ho in highlight_objects if ho.player]
            primary_player = involved_players[0] if involved_players else None

            # Determine event type from tags
            event_type = "touch"  # default
            if h.tags:
                if "pass" in h.tags:
                    event_type = "pass"
                elif "shot" in h.tags:
                    event_type = "shot"
                elif "goal" in h.tags:
                    event_type = "goal"
                elif "tackle" in h.tags:
                    event_type = "tackle"

            # Create 6 clip reel entries: 3 tag combinations × 2 ratios
            # Tag combinations:
            # 1. without_name_overlay, without_circle_overlay (default=True for both ratios)
            # 2. with_name_overlay, without_circle_overlay (default=False)
            # 3. with_name_overlay, with_circle_overlay (default=False)
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

                tag_filters = Q()
                for tag in config["tags"]:
                    tag_filters &= Q(
                        tags__contains=tag
                    )  # Check if array contains this string value

                clip_reel = (
                    TraceClipReel.objects.filter(
                        highlight=h,
                        ratio=config["ratio"],
                    )
                    .filter(tag_filters)
                    .first()
                )

                # Verify exact tag match (order-independent) - ensures no extra tags
                if clip_reel:
                    existing_tags = sorted(clip_reel.tags) if clip_reel.tags else []
                    if existing_tags == sorted_tags:
                        # Clip reel with exact same config already exists, skip
                        # Just ensure involved players are set and continue
                        if involved_players:
                            clip_reel.involved_players.set(involved_players)
                        continue

                # Clip reel doesn't exist or tags don't match exactly, create new one
                defaults = {
                    "session": session,
                    "event_id": h.highlight_id,
                    "event_type": event_type,
                    "side": side,
                    "start_ms": h.start_offset,
                    "duration_ms": h.duration,
                    "start_clock": self._ms_to_clock(h.start_offset),
                    "end_clock": self._ms_to_clock(h.start_offset + h.duration),
                    "primary_player": primary_player,
                    "label": f"{event_type.title()} - {side.title()}",
                    "description": f"{event_type.title()} event for {side} team",
                    "tags": config["tags"],
                    "ratio": config["ratio"],
                    "is_default": config["is_default"],
                    "video_type": config["video_type"],
                    "video_stream": h.video_stream or "",
                    "generation_status": "pending",
                    "video_variant_name": (
                        self._get_video_variant_name(
                            tags=config["tags"],
                            ratio=config["ratio"],
                            primary_player=primary_player,
                        )
                        if hasattr(self, "_get_video_variant_name")
                        else ""
                    ),
                    "generation_metadata": {
                        "highlight_id": h.highlight_id,
                        "video_id": h.video_id,
                        "involved_players_count": len(involved_players),
                        "created_from_aggregation": True,
                        "tags": config["tags"],
                        "ratio": config["ratio"],
                    },
                }

                # Create new clip reel
                clip_reel = TraceClipReel.objects.create(
                    highlight=h,
                    **defaults,
                )

                # Add all involved players to the many-to-many relationship
                if involved_players:
                    clip_reel.involved_players.set(involved_players)
        return True

    def _compute_possessions(self, session):
        """Compute possession metrics using highlights from session result data stored in Azure blob storage"""
        # from .utils import parse_time_to_seconds, filter_highlights_by_game_time

        try:
            self.logger.info(
                f"Starting possession calculation for session {session.session_id}"
            )

            # Fetch result data from Azure blob storage
            result_data = self._fetch_result_data_from_blob(session)
            if not result_data:
                self.logger.warning(
                    f"Failed to fetch result data from blob for session {session.session_id}"
                )
                return False

            # Get highlights from result data
            if "highlights" not in result_data:
                self.logger.warning(
                    f"No highlights found in result data for session {session.session_id}"
                )
                return False

            highlights = result_data["highlights"]
            if not highlights:
                self.logger.warning(
                    f"Empty highlights list for session {session.session_id}"
                )
                return False

            # Parse session timing fields to seconds
            game_start_time = (
                parse_time_to_seconds(session.match_start_time)
                if session.match_start_time
                else None
            )
            first_half_end_time = (
                parse_time_to_seconds(session.first_half_end_time)
                if session.first_half_end_time
                else None
            )
            second_half_start_time = (
                parse_time_to_seconds(session.second_half_start_time)
                if session.second_half_start_time
                else None
            )
            game_end_time = (
                parse_time_to_seconds(session.match_end_time)
                if session.match_end_time
                else None
            )

            # Filter highlights by game time
            filtered_highlights = filter_highlights_by_game_time(
                highlights,
                game_start_time,
                first_half_end_time,
                second_half_start_time,
                game_end_time,
            )

            if not filtered_highlights:
                self.logger.warning(
                    f"No highlights remain after game time filtering for session {session.session_id}"
                )
                return False

            # Calculate possession metrics
            possession_results = self._calculate_possession_metrics(
                filtered_highlights, session
            )

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
                possession_results["team_metrics"],
                possession_results["player_metrics"],
            )

            if save_result["success"]:
                # Create possession segments using the same data as possession stats
                segments_result = self._create_possession_segments_from_calculation(
                    session, filtered_highlights, possession_results
                )
                if segments_result:
                    self.logger.info(
                        f"Successfully created possession segments for session {session.session_id}"
                    )
                else:
                    self.logger.warning(
                        f"Failed to create possession segments for session {session.session_id}"
                    )

                self.logger.info(
                    f"Successfully computed and saved possession metrics for session {session.session_id}"
                )
                return True
            else:
                self.logger.error(
                    f"Failed to save possession metrics for session {session.session_id}: {save_result.get('error')}"
                )
                return False

        except Exception as e:
            self.logger.exception(
                f"Error computing possession metrics for session {session.session_id}: {e}"
            )
            return False

    def _calculate_possession_metrics(self, highlights, session):
        """Calculate possession metrics based on possession.py logic"""
        # Filter only possession chains (touch-chain tags)
        chains = [h for h in highlights if "touch-chain" in h.get("tags", [])]

        if not chains:
            self.logger.warning("No possession chains found in highlights")
            return {"team_metrics": {"home": {}, "away": {}}, "player_metrics": {}}

        # Sort chains by start time
        chains = sorted(chains, key=lambda x: x["start_offset"])

        # Group consecutive chains by the same team into possessions
        possessions = self._group_chains_into_possessions(chains)

        # Calculate team-level metrics
        team_metrics = self._calculate_team_metrics_from_possessions(possessions)

        # Calculate player-level metrics
        player_metrics = self._calculate_player_metrics_from_possessions(
            possessions, session
        )

        return {"team_metrics": team_metrics, "player_metrics": player_metrics}

    def _group_chains_into_possessions(self, chains):
        """Group consecutive touch-chains by the same team into possessions"""
        possessions = []
        current_possession = None

        for chain in chains:
            tags = chain.get("tags", [])
            team_side = None
            if "home" in tags:
                team_side = "home"
            elif "away" in tags:
                team_side = "away"

            if not team_side:
                continue

            # If this is the first chain or different team, start new possession
            if current_possession is None or current_possession["team"] != team_side:
                # Save previous possession if exists
                if current_possession is not None:
                    possessions.append(current_possession)

                # Start new possession
                current_possession = {
                    "team": team_side,
                    "chains": [chain],
                    "start_ms": chain["start_offset"],
                    "end_ms": chain["start_offset"] + chain["duration"],
                    "total_duration_ms": chain["duration"],
                    "total_touches": len(chain.get("objects", [])),
                    "players_involved": set(),
                }
            else:
                # Same team - add to current possession
                current_possession["chains"].append(chain)
                current_possession["end_ms"] = chain["start_offset"] + chain["duration"]
                current_possession["total_duration_ms"] = (
                    current_possession["end_ms"] - current_possession["start_ms"]
                )
                current_possession["total_touches"] += len(chain.get("objects", []))

            # Track players involved in this possession
            for obj in chain.get("objects", []):
                if obj.get("object_id"):
                    current_possession["players_involved"].add(obj["object_id"])

        # Add the last possession
        if current_possession is not None:
            possessions.append(current_possession)

        return possessions

    def _calculate_team_metrics_from_possessions(self, possessions):
        """Calculate team-level metrics from grouped possessions"""
        team_metrics = {"home": {}, "away": {}}

        # Group possessions by team
        team_possessions = {"home": [], "away": []}
        for possession in possessions:
            team_possessions[possession["team"]].append(possession)

        # Calculate metrics for each team
        for team_side in ["home", "away"]:
            team_poss = team_possessions[team_side]
            if not team_poss:
                team_metrics[team_side] = self._get_empty_team_metrics()
                continue

            # Basic metrics (keep in milliseconds)
            total_duration_ms = sum(p["total_duration_ms"] for p in team_poss)
            possession_count = len(team_poss)
            avg_duration_ms = (
                total_duration_ms / possession_count if possession_count > 0 else 0
            )

            # Calculate passes (touches - 1 per possession)
            total_touches = sum(p["total_touches"] for p in team_poss)
            total_passes = max(total_touches - possession_count, 0)
            avg_passes = total_passes / possession_count if possession_count > 0 else 0

            # Longest possession (keep in milliseconds)
            longest_possession_ms = max(p["total_duration_ms"] for p in team_poss)

            # Calculate turnovers (number of times this team lost possession)
            turnovers = self._calculate_team_turnovers(possessions, team_side)

            team_metrics[team_side] = {
                "possession_time_ms": round(total_duration_ms, 1),
                "possession_count": possession_count,
                "avg_duration_ms": round(avg_duration_ms, 1),
                "avg_passes": round(avg_passes, 2),
                "longest_possession_ms": round(longest_possession_ms, 1),
                "turnovers": turnovers,
                "total_touches": total_touches,
                "total_passes": total_passes,
            }

        # Calculate possession percentages
        total_possession_time_ms = sum(
            team_metrics[side]["possession_time_ms"] for side in team_metrics
        )
        if total_possession_time_ms > 0:
            for team_side in team_metrics:
                team_metrics[team_side]["possession_percentage"] = round(
                    (
                        team_metrics[team_side]["possession_time_ms"]
                        / total_possession_time_ms
                    )
                    * 100,
                    1,
                )

        return team_metrics

    def _calculate_team_turnovers(self, possessions, team_side):
        """Calculate turnovers for a specific team"""
        turnovers = 0
        for i, possession in enumerate(possessions):
            if possession["team"] == team_side:
                # Check if next possession is by different team
                if i + 1 < len(possessions) and possessions[i + 1]["team"] != team_side:
                    turnovers += 1
        return turnovers

    def _calculate_player_metrics_from_possessions(self, possessions, session):
        """Calculate player-level possession metrics from grouped possessions"""
        # Get all players in the session
        players = session.players.all()
        player_metrics = {}

        # Group possessions by team for percentage calculations
        team_possessions = {"home": [], "away": []}
        for possession in possessions:
            team_possessions[possession["team"]].append(possession)

        for player in players:
            # Create player_id in format: <team_side>_<jersey_number>
            team_side = "home" if "home" in player.team_name.lower() else "away"
            player_id = f"{team_side}_{player.jersey_number}"

            # Find possessions where this player was involved
            player_possessions = []
            for possession in possessions:
                if player.object_id in possession["players_involved"]:
                    player_possessions.append(possession)

            if not player_possessions:
                player_metrics[player_id] = self._get_empty_player_metrics(
                    player, player_id, team_side
                )
                continue

            # Calculate player-specific metrics (keep in milliseconds)
            total_duration_ms = sum(p["total_duration_ms"] for p in player_possessions)
            involvement_count = len(player_possessions)
            avg_duration_ms = (
                total_duration_ms / involvement_count if involvement_count > 0 else 0
            )

            # Calculate touches in possessions
            total_touches = sum(p["total_touches"] for p in player_possessions)
            avg_touches = (
                total_touches / involvement_count if involvement_count > 0 else 0
            )

            # Calculate involvement percentage for player's team
            team_poss = team_possessions[team_side]
            team_possession_count = len(team_poss)
            involvement_percentage = 0
            if team_possession_count > 0:
                involvement_percentage = round(
                    (involvement_count / team_possession_count) * 100, 1
                )

            player_metrics[player_id] = {
                "involvement_count": involvement_count,
                "total_duration_ms": round(total_duration_ms, 1),
                "avg_duration_ms": round(avg_duration_ms, 1),
                "total_touches": total_touches,
                "avg_touches": round(avg_touches, 2),
                "involvement_percentage": involvement_percentage,
            }

        return player_metrics

    def _get_empty_team_metrics(self):
        """Return empty team metrics structure"""
        return {
            "possession_time_ms": 0,
            "possession_count": 0,
            "avg_duration_ms": 0,
            "avg_passes": 0,
            "longest_possession_ms": 0,
            "turnovers": 0,
            "total_touches": 0,
            "total_passes": 0,
            "possession_percentage": 0,
        }

    def _get_empty_player_metrics(self, player, player_id, team_side):
        """Return empty player metrics structure"""
        return {
            "involvement_count": 0,
            "total_duration_ms": 0,
            "avg_duration_ms": 0,
            "total_touches": 0,
            "avg_touches": 0,
            "involvement_percentage": 0,
        }

    def _create_possession_segments_from_calculation(
        self, session, highlights, possession_results
    ):
        """Create possession segments using the same data as possession calculation"""
        try:
            self.logger.info(
                f"Creating possession segments from calculation for session {session.session_id}"
            )

            # Clear existing segments for this session
            TracePossessionSegment.objects.filter(session=session).delete()

            # Filter only possession chains (touch-chain tags)
            chains = [h for h in highlights if "touch-chain" in h.get("tags", [])]

            if not chains:
                self.logger.warning(
                    f"No possession chains found for session {session.session_id}"
                )
                return False

            # Sort chains by start time
            chains = sorted(chains, key=lambda x: x["start_offset"])

            # Group consecutive chains by the same team into possessions
            possessions = self._group_chains_into_possessions(chains)

            # Create segments for each possession
            segments_created = 0
            cumulative_team_metrics = {"home": {}, "away": {}}
            cumulative_player_metrics = {}

            for i, possession in enumerate(possessions):
                team_side = possession["team"]

                # Calculate cumulative metrics up to this possession
                cumulative_team_metrics[team_side] = (
                    self._calculate_cumulative_team_metrics_for_segment(
                        possessions[: i + 1], team_side, session, possessions
                    )
                )

                # Calculate player metrics for this possession
                player_metrics = self._calculate_player_metrics_for_possession(
                    possession, session, cumulative_player_metrics
                )

                # Filter out players with all zero metrics to save space
                filtered_player_metrics = {
                    player_id: metrics
                    for player_id, metrics in player_metrics.items()
                    if any(
                        metrics.get(key, 0) != 0
                        for key in [
                            "involvement_count",
                            "total_duration_ms",
                            "total_touches",
                        ]
                    )
                }

                # Find the highlight that corresponds to this possession
                # Use the first chain in the possession to find the highlight
                highlight = None
                if possession["chains"]:
                    first_chain = possession["chains"][0]
                    # Try to find the highlight by start_offset
                    highlight = session.highlights.filter(
                        start_offset=first_chain["start_offset"]
                    ).first()

                # Create segment
                segment = TracePossessionSegment.objects.create(
                    session=session,
                    side=team_side,
                    start_ms=possession["start_ms"],
                    end_ms=possession["end_ms"],
                    count=len(
                        possession["chains"]
                    ),  # Number of chains in this possession
                    start_clock=self._ms_to_clock(possession["start_ms"]),
                    end_clock=self._ms_to_clock(possession["end_ms"]),
                    duration_s=possession["total_duration_ms"]
                    / 1000.0,  # Convert ms to seconds
                    highlight=highlight,  # Link to the highlight
                    team_metrics=cumulative_team_metrics[team_side],
                    player_metrics=filtered_player_metrics,  # Only non-zero player metrics
                )
                segments_created += 1

                self.logger.debug(
                    f"Created segment {segments_created} for {team_side} team with {len(possession['chains'])} chains"
                )

            self.logger.info(
                f"Successfully created {segments_created} possession segments for session {session.session_id}"
            )
            return True

        except Exception as e:
            self.logger.exception(
                f"Error creating possession segments for session {session.session_id}: {e}"
            )
            return False

    def _calculate_cumulative_team_metrics_for_segment(
        self, possessions_up_to_now, team_side, session, all_possessions
    ):
        """Calculate cumulative team metrics up to a specific possession"""
        team_possessions = [p for p in possessions_up_to_now if p["team"] == team_side]

        if not team_possessions:
            return self._get_empty_team_metrics()

        # Calculate cumulative metrics
        total_duration_ms = sum(p["total_duration_ms"] for p in team_possessions)
        possession_count = len(team_possessions)
        avg_duration_ms = (
            total_duration_ms / possession_count if possession_count > 0 else 0
        )

        # Calculate touches and passes
        total_touches = sum(p["total_touches"] for p in team_possessions)
        total_passes = max(total_touches - possession_count, 0)
        avg_passes = total_passes / possession_count if possession_count > 0 else 0

        # Calculate turnovers using the FULL possession list, not just up to now
        turnovers = self._calculate_team_turnovers(all_possessions, team_side)

        # Calculate longest possession
        longest_possession_ms = (
            max(p["total_duration_ms"] for p in team_possessions)
            if team_possessions
            else 0
        )

        # Calculate possession percentage using full data
        total_all_teams_duration = sum(p["total_duration_ms"] for p in all_possessions)
        possession_percentage = (
            (total_duration_ms / total_all_teams_duration * 100)
            if total_all_teams_duration > 0
            else 0
        )

        return {
            "possession_count": possession_count,
            "possession_time_ms": total_duration_ms,
            "avg_duration_ms": avg_duration_ms,
            "total_touches": total_touches,
            "total_passes": total_passes,
            "avg_passes": avg_passes,
            "turnovers": turnovers,
            "longest_possession_ms": longest_possession_ms,
            "possession_percentage": possession_percentage,
        }

    def _calculate_player_metrics_for_possession(
        self, possession, session, cumulative_player_metrics
    ):
        """Calculate player metrics for a specific possession"""
        player_metrics = {}

        # Get all players in the session
        players = session.players.all()

        for player in players:
            team_side = "home" if "home" in player.team_name.lower() else "away"
            player_id = f"{team_side}_{player.jersey_number}"

            # Check if this player was involved in this possession
            if player.object_id in possession["players_involved"]:
                # Update cumulative metrics
                if player_id not in cumulative_player_metrics:
                    cumulative_player_metrics[player_id] = {
                        "involvement_count": 0,
                        "total_duration_ms": 0,
                        "total_touches": 0,
                    }

                cumulative_player_metrics[player_id]["involvement_count"] += 1
                cumulative_player_metrics[player_id]["total_duration_ms"] += possession[
                    "total_duration_ms"
                ]
                cumulative_player_metrics[player_id]["total_touches"] += possession[
                    "total_touches"
                ]

            # Calculate current metrics
            if player_id in cumulative_player_metrics:
                cum_metrics = cumulative_player_metrics[player_id]
                involvement_count = cum_metrics["involvement_count"]
                total_duration_ms = cum_metrics["total_duration_ms"]
                total_touches = cum_metrics["total_touches"]

                avg_duration_ms = (
                    total_duration_ms / involvement_count
                    if involvement_count > 0
                    else 0
                )
                avg_touches = (
                    total_touches / involvement_count if involvement_count > 0 else 0
                )

                # Calculate involvement percentage (simplified - would need total team possessions)
                involvement_percentage = (
                    0  # This would need to be calculated with total team possessions
                )

                player_metrics[player_id] = {
                    "involvement_count": involvement_count,
                    "total_duration_ms": total_duration_ms,
                    "avg_duration_ms": avg_duration_ms,
                    "total_touches": total_touches,
                    "avg_touches": avg_touches,
                    "involvement_percentage": involvement_percentage,
                }
            else:
                # Player not involved yet
                player_metrics[player_id] = {
                    "involvement_count": 0,
                    "total_duration_ms": 0,
                    "avg_duration_ms": 0,
                    "total_touches": 0,
                    "avg_touches": 0,
                    "involvement_percentage": 0,
                }

        return player_metrics

    def _compute_possession_segments(self, session):
        """Compute possession segments for each highlight with touch-chain tags"""
        try:
            self.logger.info(
                f"Starting possession segments calculation for session {session.session_id}"
            )

            # Get highlights with touch-chain tags, ordered by start_offset
            highlights = session.highlights.filter(
                tags__contains=["touch-chain"]
            ).order_by("start_offset")

            if not highlights.exists():
                self.logger.warning(
                    f"No touch-chain highlights found for session {session.session_id}"
                )
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
                    team_metrics=segment_metrics["team"],
                    player_metrics=segment_metrics["player"],
                )
                segments_created += 1

                self.logger.debug(
                    f"Created segment for highlight {highlight.highlight_id}: {team_side} team"
                )

            self.logger.info(
                f"Successfully created {segments_created} possession segments for session {session.session_id}"
            )
            return True

        except Exception as e:
            self.logger.exception(
                f"Error computing possession segments for session {session.session_id}: {e}"
            )
            return False

    def _get_team_side_from_highlight(self, highlight):
        """Extract team side from highlight tags"""
        tags = highlight.tags or []
        if "home" in tags:
            return "home"
        elif "away" in tags:
            return "away"
            return None

    def _calculate_highlight_segment_metrics(
        self, current_highlight, all_highlights, team_side, session
    ):
        """Calculate cumulative possession metrics up to this highlight"""

        # Get all previous highlights of the same team up to this point
        previous_highlights = all_highlights.filter(
            start_offset__lte=current_highlight.start_offset, tags__contains=[team_side]
        ).order_by("start_offset")

        # Calculate cumulative team metrics
        team_metrics = self._calculate_cumulative_team_metrics(
            previous_highlights, team_side, session
        )

        # Calculate player metrics for this specific highlight's player
        player_metrics = self._calculate_player_highlight_metrics(
            current_highlight, session
        )

        return {"team": team_metrics, "player": player_metrics}

    def _calculate_cumulative_team_metrics(self, highlights, team_side, session):
        """Calculate cumulative team metrics from highlights"""

        if not highlights.exists():
            return self._get_empty_team_metrics()

        # Group consecutive highlights into possessions
        possessions = self._group_highlights_into_possessions(highlights, team_side)

        # Calculate metrics from possessions
        total_duration_ms = sum(p["duration_ms"] for p in possessions)
        possession_count = len(possessions)
        avg_duration_ms = (
            total_duration_ms / possession_count if possession_count > 0 else 0
        )

        # Calculate touches and passes
        total_touches = sum(p["touches"] for p in possessions)
        total_passes = max(total_touches - possession_count, 0)
        avg_passes = total_passes / possession_count if possession_count > 0 else 0

        # Calculate turnovers (number of times possession was lost)
        turnovers = self._calculate_turnovers_from_highlights(highlights, team_side)

        # Calculate possession percentage (need total game time)
        total_game_time_ms = self._get_total_game_time_ms(session)
        possession_percentage = (
            (total_duration_ms / total_game_time_ms * 100)
            if total_game_time_ms > 0
            else 0
        )

        return {
            "possession_percentage": round(possession_percentage, 1),
            "turnovers": turnovers,
            "total_passes": total_passes,
            "total_touches": total_touches,
            "possession_count": possession_count,
            "possession_time_ms": round(total_duration_ms, 1),
            "avg_duration_ms": round(avg_duration_ms, 1),
            "avg_passes": round(avg_passes, 2),
            "longest_possession_ms": (
                round(max(p["duration_ms"] for p in possessions), 1)
                if possessions
                else 0
            ),
        }

    def _calculate_player_highlight_metrics(self, highlight, session):
        """Calculate player metrics for a specific highlight"""

        if not highlight.player:
            return self._get_empty_highlight_player_metrics()

        # Get all possessions this player was involved in up to this point
        player_highlights = session.highlights.filter(
            player=highlight.player,
            start_offset__lte=highlight.start_offset,
            tags__contains=["touch-chain"],
        ).order_by("start_offset")

        # Calculate player involvement
        involvement_count = player_highlights.count()
        total_touches = sum(
            len(h.tags or []) for h in player_highlights
        )  # Approximate touches
        avg_touches = total_touches / involvement_count if involvement_count > 0 else 0

        # Calculate involvement percentage
        team_side = self._get_team_side_from_highlight(highlight)
        team_highlights = session.highlights.filter(
            tags__contains=[team_side], start_offset__lte=highlight.start_offset
        ).count()
        involvement_percentage = (
            (involvement_count / team_highlights * 100) if team_highlights > 0 else 0
        )

        return {
            "involvement_count": involvement_count,
            "total_touches": total_touches,
            "avg_touches": round(avg_touches, 2),
            "involvement_percentage": round(involvement_percentage, 1),
        }

    def _group_highlights_into_possessions(self, highlights, team_side):
        """Group consecutive highlights into possession chains"""
        possessions = []
        current_possession = None

        for highlight in highlights:
            if current_possession is None:
                # Start new possession
                current_possession = {
                    "duration_ms": highlight.duration,
                    "touches": len(highlight.tags or []),
                    "start_ms": highlight.start_offset,
                }
            else:
                # Check if this highlight continues the possession
                time_gap = highlight.start_offset - (
                    current_possession["start_ms"] + current_possession["duration_ms"]
                )
                if time_gap <= 5000:  # 5 second gap threshold
                    # Continue possession
                    current_possession["duration_ms"] += highlight.duration
                    current_possession["touches"] += len(highlight.tags or [])
                else:
                    # Save current possession and start new one
                    possessions.append(current_possession)
                    current_possession = {
                        "duration_ms": highlight.duration,
                        "touches": len(highlight.tags or []),
                        "start_ms": highlight.start_offset,
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
            "possession_percentage": 0.0,
            "turnovers": 0,
            "total_passes": 0,
            "total_touches": 0,
            "possession_count": 0,
            "possession_time_ms": 0.0,
            "avg_duration_ms": 0.0,
            "avg_passes": 0.0,
            "longest_possession_ms": 0.0,
        }

    def _get_empty_highlight_player_metrics(self):
        """Return empty player metrics structure for highlights"""
        return {
            "involvement_count": 0,
            "total_touches": 0,
            "avg_touches": 0.0,
            "involvement_percentage": 0.0,
        }

    def validate_segment_totals(self, session):
        """Validate that segment totals match final possession stats"""
        try:
            # from .models import TracePossessionStats, TracePossessionSegment

            # Get final possession stats
            final_team_stats = TracePossessionStats.objects.filter(
                session=session, possession_type="team"
            )

            # Calculate totals from segments
            segments = TracePossessionSegment.objects.filter(session=session)

            for team_stat in final_team_stats:
                team_side = team_stat.side
                team_segments = segments.filter(side=team_side)

                # Calculate cumulative totals
                cumulative_turnovers = sum(
                    s.team_metrics.get("turnovers", 0) for s in team_segments
                )
                cumulative_passes = sum(
                    s.team_metrics.get("total_passes", 0) for s in team_segments
                )
                cumulative_touches = sum(
                    s.team_metrics.get("total_touches", 0) for s in team_segments
                )

                # Validate
                final_metrics = team_stat.metrics
                assert cumulative_turnovers == final_metrics.get(
                    "turnovers", 0
                ), f"Turnovers mismatch for {team_side}"
                assert cumulative_passes == final_metrics.get(
                    "total_passes", 0
                ), f"Passes mismatch for {team_side}"
                assert cumulative_touches == final_metrics.get(
                    "total_touches", 0
                ), f"Touches mismatch for {team_side}"

            self.logger.info(
                f"Segment validation passed for session {session.session_id}"
            )
            return True

        except Exception as e:
            self.logger.error(
                f"Segment validation failed for session {session.session_id}: {e}"
            )
            return False