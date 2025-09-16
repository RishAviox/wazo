"""
Video generation module for TraceVision overlay highlights.
Adapted from WAZO.py to work with Django models and Azure Blob Storage.
"""

import json
import logging
import os
import tempfile
import uuid
from typing import Dict, Optional

import cv2
import numpy as np
import pandas as pd
import requests
from django.core.files.storage import default_storage

from .models import TraceClipReel, TraceObject, TracePlayer

logger = logging.getLogger(__name__)


def extract_relative_path_from_azure_url(azure_url: str) -> str:
    """
    Extract relative path from Azure Blob Storage URL.

    Args:
        azure_url: Full Azure Blob Storage URL

    Returns:
        str: Relative path for use with default_storage.open()
    """
    if not azure_url.startswith("https://"):
        return azure_url

    # URL format: https://account.blob.core.windows.net/container/path
    url_parts = azure_url.split('/')

    # Find the container name in the URL
    container_index = None
    for i, part in enumerate(url_parts):
        if part.endswith('.blob.core.windows.net'):
            container_index = i + 1
            break

    if container_index and container_index < len(url_parts):
        container_name = url_parts[container_index]
        # Extract path after container name
        relative_path = '/'.join(url_parts[container_index:])

        # Handle different containers based on Django settings
        from django.conf import settings
        django_container = getattr(settings, 'AZURE_CONTAINER_NAME', 'media')

        if container_name == django_container:
            # Same container as Django settings - remove container name from path
            path_after_container = '/'.join(url_parts[container_index + 1:])
            logger.info(
                f"Using Django container '{django_container}', path: {path_after_container}")
            return path_after_container
        else:
            # Different container - keep full path with container name
            logger.info(
                f"Using different container '{container_name}', full path: {relative_path}")
            return relative_path
    else:
        logger.warning(f"Could not extract path from Azure URL: {azure_url}")
        return azure_url


class TrackingDataCache:
    """Cache tracking data to avoid re-downloading for multiple clip reels"""

    def __init__(self):
        self.cache = {}

    def get_tracking_data(self, tracking_blob_url: str, video_start_time_ms: int = 0) -> pd.DataFrame:
        """Get tracking data with caching"""
        cache_key = f"{tracking_blob_url}_{video_start_time_ms}"

        if cache_key not in self.cache:
            self.cache[cache_key] = load_tracking_data_from_storage(
                tracking_blob_url, video_start_time_ms
            )

        return self.cache[cache_key]

    def clear_cache(self):
        """Clear the cache"""
        self.cache.clear()


def load_tracking_data_from_storage(tracking_blob_url: str, video_start_time_ms: int = 0) -> pd.DataFrame:
    """
    Load tracking data from Azure Blob Storage or local storage.

    Args:
        tracking_blob_url: Azure blob URL or local file path for tracking data
        video_start_time_ms: Video start time offset (usually 0)

    Returns:
        pandas.DataFrame: Tracking data in same format as original function
    """
    try:
        logger.info(f"Loading tracking data from storage: {tracking_blob_url}")

        # Handle different storage types based on DEBUG setting
        from django.conf import settings

        if tracking_blob_url.startswith("https://"):
            # Full Azure Blob URL - extract the relative path
            relative_path = extract_relative_path_from_azure_url(
                tracking_blob_url)
            logger.info(f"Relative path: {relative_path}")
            response = default_storage.open(relative_path)
            logger.info(f"Response of the {tracking_blob_url}: {response}")

        elif settings.DEBUG and not tracking_blob_url.startswith("https"):
            # Local development - handle file path properly
            if tracking_blob_url.startswith('/media/'):
                # Remove leading /media/ for local storage
                file_path = tracking_blob_url[7:]  # Remove '/media/'
            elif tracking_blob_url.startswith('media/'):
                # Already has media/ prefix
                file_path = tracking_blob_url
            else:
                # Assume it's already a relative path
                file_path = tracking_blob_url

            logger.info(f"Using local tracking file path: {file_path}")
            response = default_storage.open(file_path)
        else:
            # Production - Azure Blob Storage with relative path
            response = default_storage.open(tracking_blob_url)

        tracking_data_obj = json.load(response)
        response.close()

        # Convert to pandas DataFrame (same format as original WAZO.py)
        tracking_df = pd.DataFrame(
            tracking_data_obj["spotlights"],
            columns=["time_off", "x", "y", "w", "h"],
        )

        # Use time_off directly as video time (same as original)
        tracking_df["video_time_ms"] = tracking_df["time_off"]

        logger.info(f"Loaded tracking data with {len(tracking_df)} spotlights")
        return tracking_df

    except Exception as e:
        logger.error(
            f"Error loading tracking data from {tracking_blob_url}: {e}")
        return pd.DataFrame()  # Return empty DataFrame on error


def download_video_from_storage(video_blob_url: str, temp_dir: Optional[str] = None) -> str:
    """Download video from Azure Blob or local storage to temporary file for OpenCV processing"""
    if temp_dir is None:
        temp_dir = tempfile.gettempdir()

    # Generate temporary filename
    temp_filename = f"temp_video_{uuid.uuid4().hex}.mp4"
    temp_path = os.path.join(temp_dir, temp_filename)

    try:
        logger.info(f"Downloading video from storage: {video_blob_url}")

        # Handle different storage types based on DEBUG setting
        from django.conf import settings

        if video_blob_url.startswith("https://"):
            # Full Azure Blob URL - extract the relative path
            relative_path = extract_relative_path_from_azure_url(video_blob_url)
            response = default_storage.open(relative_path)

        elif settings.DEBUG and not video_blob_url.startswith("https"):
            # Local development - handle file path properly
            if video_blob_url.startswith('/media/'):
                # Remove leading /media/ for local storage
                file_path = video_blob_url[7:]  # Remove '/media/'
            elif video_blob_url.startswith('media/'):
                # Already has media/ prefix
                file_path = video_blob_url
            else:
                # Assume it's already a relative path
                file_path = video_blob_url

            logger.info(f"Using local file path: {file_path}")
            response = default_storage.open(file_path)
        else:
            # Production - Azure Blob Storage with relative path
            response = default_storage.open(video_blob_url)

        with open(temp_path, 'wb') as f:
            f.write(response.read())
        response.close()
        # temp_path = "./media/videos/4299999/4299999_video.mp4"
        if os.path.exists(temp_path):
            logger.info(f"{'=='*50}\n\n{temp_path}\n\n{'=='*50}")
        else:
            logger.warning(f"Video file not found: {temp_path}")

        logger.info(f"Downloaded video to temporary file: {temp_path}")
        return temp_path

    except Exception as e:
        logger.error(f"Error downloading video from {video_blob_url}: {e}")
        raise


def add_bbox_overlay_to_frame(
    frame, video_time_ms, tracking_df, object_id, w, h, overlay_tolerance, player_name
):
    """
    Add a clean, non-sparkling border circle around the player's feet
    WITHOUT overlapping the player (masking inside bounding box).
    Adapted from WAZO.py
    """
    logger.debug(f"Adding overlay for {object_id} at time {video_time_ms}ms")
    cur_index = (tracking_df["video_time_ms"] - video_time_ms).abs().idxmin()
    cur_track_time = tracking_df.iloc[cur_index]["video_time_ms"]

    if np.abs(cur_track_time - video_time_ms) <= overlay_tolerance:
        # Convert normalized coords to pixel coords
        cur_x = tracking_df.loc[cur_index]["x"] * w / 1000
        cur_y = tracking_df.loc[cur_index]["y"] * h / 1000
        head_y = cur_y - \
            (tracking_df.loc[cur_index]["h"] * h / 1000) * 0.5 - 10
        # Slight upward shift
        foot_y = cur_y + \
            (tracking_df.loc[cur_index]["h"] * h / 1000) * 0.5 - 10
        rotation_angle = 360
        ellipse_width = int(tracking_df.loc[cur_index]["w"] * w / 1000 / 0.5)
        ellipse_height = int(tracking_df.loc[cur_index]["h"] * h / 1000 / 3)

        # ---- Create transparent overlay (no sparkle) ----
        overlay = np.zeros_like(frame, dtype=np.uint8)
        alpha_mask = np.zeros(
            (frame.shape[0], frame.shape[1]), dtype=np.float32)

        # Draw ellipse border on mask (solid)
        cv2.ellipse(alpha_mask, (int(cur_x), int(foot_y)),
                    (ellipse_width, ellipse_height),
                    rotation_angle, 0, 360, 1.0, 4, lineType=cv2.LINE_AA)

        # No blur or normalization -> crisp border

        # ---- MASK OUT PLAYER AREA ----
        player_h = tracking_df.loc[cur_index]["h"] * h / 1000
        player_w = tracking_df.loc[cur_index]["w"] * w / 1000
        x1 = max(0, int(cur_x - player_w / 2))
        x2 = min(w, int(cur_x + player_w / 2))
        y1 = max(0, int(cur_y - player_h / 2))
        y2 = min(h, int(cur_y + player_h / 2))

        player_mask = np.ones_like(alpha_mask, dtype=np.float32)
        player_mask[y1:y2, x1:x2] = 0.0
        # it will blend with the ground colour!
        player_mask = cv2.GaussianBlur(player_mask, (25, 25), 10)
        alpha_mask *= player_mask

        # ---- Apply alpha to color ----
        color = np.zeros_like(frame, dtype=np.float32)
        color[:] = (255, 255, 255)  # White border (can change)

        for c in range(3):
            overlay[:, :, c] = (alpha_mask * color[:, :, c]).astype(np.uint8)

        inv_alpha = 1.0 - alpha_mask[..., None]
        frame = (frame * inv_alpha + overlay).astype(np.uint8)

        # ---- Draw object label ----
        if object_id is not None:
            cv2.putText(frame, player_name,
                        (int(cur_x - 20), int(head_y)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

    return frame


def create_video_with_tracking_overlay(
    video_time_min_ms,
    video_time_max_ms,
    dict_tracking_df,
    text_str,
    video_filepath,
    out_video_filepath,
    player_name,
):
    """
    Create a video with tracking overlay for a specified time range.
    Adapted from WAZO.py
    """
    logger.info(
        f"Creating video with tracking overlay from {video_time_min_ms}ms to {video_time_max_ms}ms")

    # Find relevant tracking data for the specified time range:
    use_tracking_df = {}
    for object_id in dict_tracking_df:
        mask_df = (
            dict_tracking_df[object_id]["video_time_ms"] >= video_time_min_ms
        ) & (dict_tracking_df[object_id]["video_time_ms"] <= video_time_max_ms)
        if mask_df.sum() == 0:
            logger.warning(
                f"No tracking data found for {object_id} during time range")
            continue
        use_tracking_df[object_id] = (
            dict_tracking_df[object_id].loc[mask_df, :].reset_index(drop=True)
        )

    # Get input video capture and properties:
    cap = cv2.VideoCapture(video_filepath)
    fps = cap.get(cv2.CAP_PROP_FPS)
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    logger.info(f"Video properties - fps: {fps}, width: {w}, height: {h}")

    # Set up output video writer:
    sav = cv2.VideoWriter(
        out_video_filepath,
        cv2.VideoWriter_fourcc(*"mp4v"),
        fps,
        (w, h),
        True,
    )

    # For each tracking data point, create a frame with the tracking overlay:
    overlay_tolerance = 1 / fps * 2 * 1000
    logger.info(f"Seeking to video time: {video_time_min_ms}ms")
    cap.set(cv2.CAP_PROP_POS_MSEC, video_time_min_ms)
    ret, frm = cap.read()

    # Check if frame was read successfully
    if not ret or frm is None:
        logger.error(f"Failed to read frame at time {video_time_min_ms}ms")
        cap.release()
        sav.release()
        return

    logger.info(f"Successfully read first frame, shape: {frm.shape}")
    cur_video_time = cap.get(cv2.CAP_PROP_POS_MSEC)
    logger.info(f"Current video time: {cur_video_time}ms")

    while cur_video_time <= video_time_max_ms:
        # Ensure frame is in RGB format (3 channels)
        if len(frm.shape) == 2:  # Grayscale
            frm = cv2.cvtColor(frm, cv2.COLOR_GRAY2BGR)
        elif frm.shape[2] == 4:  # RGBA
            frm = cv2.cvtColor(frm, cv2.COLOR_RGBA2BGR)

        # Add bounding box overlay to current frame:
        for object_id, tracking_df in use_tracking_df.items():
            if tracking_df.empty:
                continue
            frm = add_bbox_overlay_to_frame(
                frm,
                cur_video_time,
                tracking_df,
                object_id,
                w,
                h,
                overlay_tolerance,
                player_name,
            )

        if text_str is not None:
            cv2.putText(
                frm,
                text_str,
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                1,
                (0, 255, 0),
                2,
            )

        # Write frame to output video:
        sav.write(frm)
        # Get the next frame:+
        ret, frm = cap.read()
        if not ret or frm is None:
            logger.info(f"End of video reached at time {cur_video_time}ms")
            break
        cur_video_time = cap.get(cv2.CAP_PROP_POS_MSEC)

    # Close input and output videos:
    sav.release()
    cap.release()
    logger.info(f"Video generation completed: {out_video_filepath}")


def create_clip_reel_overlay_video(clip_reel: TraceClipReel, tracking_cache: Optional[TrackingDataCache] = None) -> str:
    """
    Create overlay video for a single TraceClipReel object.

    Args:
        clip_reel: TraceClipReel instance
        tracking_cache: TrackingDataCache instance for performance

    Returns:
        str: Path to generated video file
    """
    if tracking_cache is None:
        tracking_cache = TrackingDataCache()

    logger.info(f"Creating overlay video for clip reel {clip_reel.id}")

    # Get session and video file
    session = clip_reel.session
    video_file_url = session.blob_video_url or session.video_url

    if not video_file_url:
        raise ValueError(
            f"No video URL available for session {session.session_id}")

    # Download video from storage to temporary file
    temp_video_path = download_video_from_storage(video_file_url)

    try:
        # Get involved players and their tracking data
        # involved_players = clip_reel.involved_players.all()
        tracking_data = {}

        # for player in involved_players:
        # Get TraceObject for this player in this session
        trace_object = TraceObject.objects.filter(
            session=session,
            player=clip_reel.primary_player
        ).first()

        if trace_object and trace_object.tracking_blob_url:
            # Load tracking data with caching
            player_tracking_df = tracking_cache.get_tracking_data(
                trace_object.tracking_blob_url
            )

            logger.info(
                f"Tracking Data Df is downloaded with the URL: {trace_object.tracking_blob_url}, {player_tracking_df}")

            if not player_tracking_df.empty:
                tracking_data[clip_reel.primary_player.object_id] = player_tracking_df
                logger.info(
                    f"Loaded tracking data for player {clip_reel.primary_player.object_id}")
            else:
                logger.warning(
                    f"No tracking data found for player {clip_reel.primary_player.object_id}")

        if not tracking_data:
            raise ValueError(
                f"No tracking data found for any involved players in clip reel {clip_reel.id}")

        # Create text string from highlight tags
        text_str = " | ".join(clip_reel.tags or [])
        # if involved_players:
        #     player_names = [p.object_id for p in involved_players]
        #     text_str += f" | {', '.join(player_names)}"

        player_name = clip_reel.primary_player.user.name
        if not player_name:
            player_name = clip_reel.primary_player.name

        # Create temporary output file
        with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as temp_file:
            output_path = temp_file.name

        # Generate video using existing function
        create_video_with_tracking_overlay(
            video_time_min_ms=clip_reel.start_ms,
            video_time_max_ms=clip_reel.start_ms + clip_reel.duration_ms,
            dict_tracking_df=tracking_data,
            text_str=text_str,
            video_filepath=temp_video_path,
            out_video_filepath=output_path,
            player_name=player_name,
        )

        return output_path

    finally:
        # Clean up temporary video file
        # if os.path.exists(temp_video_path):
        #     os.unlink(temp_video_path)
        logger.info("TODO: Cleanup code to remove the file from local storage")


def upload_video_to_storage(video_file_path: str, clip_reel: TraceClipReel) -> str:
    """
    Upload generated video to Azure Blob Storage with robust retry logic and error handling.
    Based on the same patterns as download_video_and_save_to_azure_blob.
    """
    try:
        # Generate blob path
        session_id = clip_reel.session.session_id
        highlight_id = clip_reel.highlight.highlight_id
        video_type = clip_reel.video_type

        from tracevision.utils import TraceVisionStoragePaths
        blob_path = TraceVisionStoragePaths.get_highlight_video_path(
            session_id, highlight_id, video_type)

        # Ensure blob path is clean and valid
        blob_path = blob_path.replace('//', '/').strip('/')
        logger.info(f"Uploading video to storage: {blob_path}")

        # Validate file exists and get properties
        if not os.path.exists(video_file_path):
            raise FileNotFoundError(f"Video file not found: {video_file_path}")

        file_size = os.path.getsize(video_file_path)
        if file_size == 0:
            raise ValueError("Video file is empty")

        logger.info(f"Video file size: {file_size / (1024*1024):.1f} MB")

        # Determine content type
        content_type = "video/mp4"
        if video_file_path.lower().endswith('.mp4'):
            content_type = "video/mp4"
        elif video_file_path.lower().endswith('.avi'):
            content_type = "video/avi"
        elif video_file_path.lower().endswith('.mov'):
            content_type = "video/quicktime"

        # Handle different storage types based on DEBUG setting
        from django.conf import settings

        # Check if we're using Azure Blob Storage (regardless of DEBUG setting)
        if hasattr(settings, 'AZURE_CONNECTION_STRING') and settings.AZURE_CONNECTION_STRING:
            # Azure Blob Storage - use robust upload
            logger.info("Using robust Azure Blob Storage upload")
            return upload_video_to_azure_blob_robust(video_file_path, blob_path, content_type, file_size)
        else:
            # Local development - use default_storage
            logger.info("Using local storage (default_storage)")
            with open(video_file_path, 'rb') as video_file:
                saved_path = default_storage.save(blob_path, video_file)
            storage_url = default_storage.url(saved_path)
            logger.info(f"Video uploaded to local storage: {storage_url}")
            return storage_url

    except Exception as e:
        logger.error(f"Error uploading video to storage: {e}")
        raise


def upload_video_to_azure_blob_robust(video_file_path: str, blob_path: str, content_type: str, file_size: int) -> str:
    """
    Robust upload to Azure Blob Storage with retry logic, using shared code from tasks.py.
    """
    from azure.storage.blob import BlobServiceClient, BlobType, ContentSettings
    from azure.core.exceptions import ResourceExistsError
    from django.conf import settings
    import time

    blob_service_client = None
    blob_client = None

    # Retry blob client creation for network issues
    for client_attempt in range(3):
        try:
            blob_service_client = BlobServiceClient.from_connection_string(
                settings.AZURE_CONNECTION_STRING)
            blob_client = blob_service_client.get_blob_client(
                container=settings.AZURE_CONTAINER_NAME, blob=blob_path)
            logger.info(
                f"Successfully created blob client on attempt {client_attempt + 1}")
            break
        except Exception as client_error:
            if client_attempt < 2:
                logger.warning(
                    f"Blob client creation attempt {client_attempt + 1} failed: {client_error}. Retrying...")
                time.sleep(5)
            else:
                logger.error(
                    f"Failed to create blob client after 3 attempts: {client_error}")
                raise client_error

    if not blob_client:
        raise Exception("Failed to create blob client")

    upload_success = False
    max_retries = 1  # Start with 1 attempt for primary method
    retry_delay = 10

    # Progress callback for upload monitoring
    def progress_callback(current, total):
        if total and total > 0:
            percentage = (current / total) * 100
            uploaded_mb = current / (1024 * 1024)
            total_mb = total / (1024 * 1024)
            logger.info(
                f"Upload progress: {percentage:.1f}% ({uploaded_mb:.1f}MB / {total_mb:.1f}MB)")

    # Try primary upload method first
    for attempt in range(max_retries):
        try:
            with open(video_file_path, 'rb') as data:
                # Try with progress callback first
                try:
                    upload_options = {
                        'data': data,
                        'blob_type': BlobType.BLOCKBLOB,
                        'overwrite': True,
                        'content_settings': ContentSettings(content_type=content_type),
                        'max_concurrency': 2,
                        'length': file_size,
                        'timeout': 7200,  # 2 hours timeout for large files
                        'progress_hook': progress_callback,
                    }

                    logger.info(
                        f"Starting upload attempt {attempt + 1} with progress tracking...")
                    blob_client.upload_blob(**upload_options)
                except TypeError as progress_error:
                    if "progress_callback" in str(progress_error):
                        logger.warning(
                            "Progress callback failed, retrying without progress tracking...")
                        # Reset file pointer
                        data.seek(0)
                        # Upload without progress callback
                        upload_options_simple = {
                            'data': data,
                            'blob_type': BlobType.BLOCKBLOB,
                            'overwrite': True,
                            'content_settings': ContentSettings(content_type=content_type),
                            'max_concurrency': 2,
                            'length': file_size,
                            'timeout': 7200,
                        }
                        blob_client.upload_blob(**upload_options_simple)
                    else:
                        raise progress_error

            upload_success = True
            logger.info(
                f"Successfully uploaded video to Azure on attempt {attempt + 1}")
            break

        except Exception as e:
            error_str = str(e).lower()
            logger.warning(f"Upload attempt {attempt + 1} failed: {e}")

            # Check for specific network errors
            if any(keyword in error_str for keyword in ['dns', 'resolve', 'connection', 'network', 'timeout']):
                logger.warning(
                    "Network-related error detected, will retry with longer delay...")
                # Longer backoff for network issues
                wait_time = retry_delay * (3 ** attempt)
            else:
                # Standard exponential backoff
                wait_time = retry_delay * (2 ** attempt)

            if attempt < max_retries - 1:
                logger.info(f"Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
            else:
                # Try alternative upload methods as last resort
                logger.info("Attempting alternative upload methods...")

                # Try direct upload first (simplest method)
                try:
                    logger.info("Trying direct upload method...")
                    upload_success = upload_video_direct(
                        blob_client, video_file_path, content_type, file_size)
                    if upload_success:
                        logger.info("Direct upload successful!")
                        break
                except Exception as direct_error:
                    logger.warning(f"Direct upload failed: {direct_error}")

                # Try chunked upload for large files (lower threshold for better reliability)
                if file_size > 10 * 1024 * 1024:  # For files larger than 10MB
                    try:
                        logger.info("Trying chunked upload method...")
                        upload_success = upload_video_chunked(
                            blob_client, video_file_path, content_type, file_size)
                        if upload_success:
                            logger.info("Chunked upload successful!")
                            break
                    except Exception as chunked_error:
                        logger.error(
                            f"Chunked upload also failed: {chunked_error}")

                logger.error(
                    f"All upload methods failed: {e}", exc_info=True, stack_info=True)
                raise e

    if not upload_success:
        raise Exception("Failed to upload video after all retry attempts")

    # Return the Azure Blob URL
    storage_url = f"https://{settings.AZURE_ACCOUNT_NAME}.blob.core.windows.net/{settings.AZURE_CONTAINER_NAME}/{blob_path}"
    logger.info(f"Video uploaded successfully: {storage_url}")
    return storage_url


def upload_video_direct(blob_client, file_path, content_type, file_size):
    """
    Simple direct upload without any special configurations.
    Uses the same pattern as tasks.py upload_file_direct.
    """
    try:
        from azure.storage.blob import BlobType, ContentSettings

        with open(file_path, 'rb') as data:
            blob_client.upload_blob(
                data=data,
                blob_type=BlobType.BLOCKBLOB,
                overwrite=True,
                content_settings=ContentSettings(content_type=content_type)
            )
        logger.info(
            f"Successfully uploaded {file_size / (1024*1024):.1f} MB using direct method")
        return True
    except Exception as e:
        logger.error(f"Direct upload failed: {e}")
        return False


def upload_video_chunked(blob_client, file_path, content_type, file_size, chunk_size=2*1024*1024):
    """
    Upload large files using chunked approach for better reliability.
    Uses the same pattern as tasks.py upload_large_file_chunked.
    """
    try:
        from azure.storage.blob import BlobBlock
        from azure.core.exceptions import ResourceExistsError
        import time
        import base64

        # Clear any existing blocks first
        try:
            blob_client.delete_blob(delete_snapshots='include')
            logger.info("Cleared existing blob before chunked upload")
        except Exception as clear_error:
            logger.info(f"No existing blob to clear: {clear_error}")

        # Start the block blob upload
        block_ids = []
        block_number = 0
        total_uploaded = 0

        with open(file_path, 'rb') as file_data:
            while True:
                chunk = file_data.read(chunk_size)
                if not chunk:
                    break

                # Generate unique block ID
                block_id = base64.b64encode(
                    f"block-{block_number:06d}-{int(time.time())}".encode()).decode()
                block_ids.append(BlobBlock(block_id=block_id))

                # Upload the chunk with retry logic
                chunk_uploaded = False
                for chunk_attempt in range(3):
                    try:
                        # Validate chunk before upload
                        if not chunk or len(chunk) == 0:
                            logger.warning(
                                f"Chunk {block_number} is empty, skipping...")
                            break

                        # Ensure block_id is properly formatted
                        if not block_id or len(block_id) == 0:
                            logger.error(
                                f"Invalid block_id for chunk {block_number}")
                            break

                        # Add small delay between chunks to avoid rate limiting
                        if block_number > 0:
                            time.sleep(0.1)

                        blob_client.stage_block(block_id, chunk)
                        chunk_uploaded = True
                        total_uploaded += len(chunk)
                        break
                    except Exception as chunk_error:
                        if chunk_attempt < 2:
                            logger.warning(
                                f"Chunk {block_number} upload attempt {chunk_attempt + 1} failed: {chunk_error}. Retrying...")
                            # Exponential backoff
                            time.sleep(2 ** chunk_attempt)
                        else:
                            logger.error(
                                f"Chunk {block_number} upload failed after 3 attempts: {chunk_error}")
                            raise chunk_error

                if not chunk_uploaded:
                    logger.error(f"Failed to upload chunk {block_number}")
                    return False

                block_number += 1
                # Log progress every 10 chunks
                if block_number % 10 == 0:
                    percentage = (total_uploaded / file_size) * 100
                    uploaded_mb = total_uploaded / (1024 * 1024)
                    total_mb = file_size / (1024 * 1024)
                    logger.info(
                        f"Chunked upload progress: {percentage:.1f}% ({uploaded_mb:.1f}MB / {total_mb:.1f}MB)")

        # Commit the block list
        if block_ids:
            logger.info(f"Committing {len(block_ids)} blocks...")
            blob_client.commit_block_list(block_ids)
            logger.info(
                f"Successfully uploaded {file_size / (1024*1024):.1f} MB using chunked method")
            return True
        else:
            logger.error("No blocks to commit")
            return False

    except Exception as e:
        logger.error(f"Chunked upload failed: {e}")
        return False
