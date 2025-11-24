import logging
import os
import json
from typing import Dict, List
from django.core.files.storage import default_storage
from django.core.cache import cache
from django.conf import settings

logger = logging.getLogger(__name__)


def _download_tracking_data_from_azure_blob(
    blob_url: str, cache_key: str = None
) -> List[List[float]]:
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
        if settings.DEBUG and not hasattr(settings, "AZURE_CUSTOM_DOMAIN"):
            logger.info(
                f"Development mode detected - reading from local file: {blob_url}"
            )

            # Convert blob URL to local file path
            if blob_url.startswith("/media/"):
                # Remove /media/ prefix and join with MEDIA_ROOT
                local_file_path = os.path.join(
                    settings.MEDIA_ROOT, blob_url[7:]
                )  # Remove '/media/'
            else:
                # Assume it's already a local path
                local_file_path = blob_url

            if os.path.exists(local_file_path):
                with open(local_file_path, "r") as f:
                    data = json.load(f)

                # Extract spotlights data
                if isinstance(data, dict) and "spotlights" in data:
                    tracking_data = data["spotlights"]
                elif isinstance(data, list):
                    tracking_data = data
                else:
                    logger.warning(
                        f"Unexpected data format in local file {local_file_path}"
                    )
                    return []

                # Cache the data if cache_key is provided
                if cache_key and tracking_data:
                    cache.set(
                        cache_key, tracking_data, timeout=3600
                    )  # Cache for 1 hour

                logger.info(
                    f"Successfully loaded {len(tracking_data)} tracking points from local file"
                )
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
            with default_storage.open(relative_path, "r") as f:
                data = json.load(f)

            # Extract spotlights data
            if isinstance(data, dict) and "spotlights" in data:
                tracking_data = data["spotlights"]
            elif isinstance(data, list):
                tracking_data = data
            else:
                logger.warning(f"Unexpected data format in blob {blob_url}")
                return []

            # Cache the data if cache_key is provided
            if cache_key and tracking_data:
                cache.set(cache_key, tracking_data, timeout=3600)  # Cache for 1 hour

            logger.info(
                f"Successfully downloaded {len(tracking_data)} tracking points from Azure blob"
            )
            return tracking_data
        else:
            logger.error(
                f"Blob file not found: {relative_path} (original URL: {blob_url})"
            )
            return []

    except Exception as e:
        logger.exception(f"Error downloading tracking data from {blob_url}: {e}")
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
            f"Cleared tracking data cache for player {player_id} in session {session_id}"
        )
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
            f"Cache clearing for session {session_id} would require cache backend support"
        )
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
        if settings.DEBUG and not hasattr(settings, "AZURE_CUSTOM_DOMAIN"):
            import os

            # Convert blob URL to local file path
            if trace_object.tracking_blob_url.startswith("/media/"):
                # Remove /media/ prefix and join with MEDIA_ROOT
                local_file_path = os.path.join(
                    # Remove '/media/'
                    settings.MEDIA_ROOT,
                    trace_object.tracking_blob_url[7:],
                )
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
            f"Error checking tracking data availability for player {player_obj.object_id}: {e}"
        )
        return False


def calculate_passing_stats(highlights: List[Dict]) -> Dict[str, float]:
    """
    Estimate passing stats from TraceVision highlights using both event types and tags.
    Pass = change of possession from one player to another within consecutive highlights of the same team.
    """
    completed = 0
    attempted = 0

    # Count passes using both event types and tags
    for highlight in highlights:
        event_type = highlight.get("event_type", "")
        tags = highlight.get("tags", [])

        if event_type == "pass" or "pass" in tags:
            attempted += 1
            # Assume completed if tracked (could be improved with metadata)
            completed += 1
        elif event_type == "touch-chain" or "touch-chain" in tags:
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
