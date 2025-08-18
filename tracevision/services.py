import logging
import requests
from datetime import datetime, timedelta
from django.core.cache import cache
from django.conf import settings

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
                            objects { object_id type side tracking_url }
                            highlights { highlight_id video_id start_offset duration tags video_stream }
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
