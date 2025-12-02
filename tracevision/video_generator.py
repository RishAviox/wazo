"""
Video generation module for TraceVision overlay highlights.
Adapted from WAZO.py to work with Django models and Azure Blob Storage.
"""

import json
import logging
import os
import subprocess
import tempfile
import uuid
from datetime import datetime, timedelta
from typing import Optional, Tuple
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

import cv2
import numpy as np
import pandas as pd
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
    url_parts = azure_url.split("/")

    # Find the container name in the URL
    container_index = None
    for i, part in enumerate(url_parts):
        if part.endswith(".blob.core.windows.net"):
            container_index = i + 1
            break

    if container_index and container_index < len(url_parts):
        container_name = url_parts[container_index]
        # Extract path after container name
        relative_path = "/".join(url_parts[container_index:])

        # Handle different containers based on Django settings
        from django.conf import settings

        django_container = getattr(settings, "AZURE_CONTAINER_NAME", "media")

        if container_name == django_container:
            # Same container as Django settings - remove container name from path
            path_after_container = "/".join(url_parts[container_index + 1 :])
            logger.info(
                f"Using Django container '{django_container}', path: {path_after_container}"
            )
            return path_after_container
        else:
            # Different container - keep full path with container name
            logger.info(
                f"Using different container '{container_name}', full path: {relative_path}"
            )
            return relative_path
    else:
        logger.warning(f"Could not extract path from Azure URL: {azure_url}")
        return azure_url


class TrackingDataCache:
    """Cache tracking data to avoid re-downloading for multiple clip reels"""

    def __init__(self):
        self.cache = {}

    def get_tracking_data(
        self,
        tracking_blob_url: str,
        video_start_time_ms: int = 0,
        time_offset_ms: int = 0,
    ) -> pd.DataFrame:
        """Get tracking data with caching"""
        cache_key = f"{tracking_blob_url}_{video_start_time_ms}_{time_offset_ms}"

        if cache_key not in self.cache:
            self.cache[cache_key] = load_tracking_data_from_storage(
                tracking_blob_url, video_start_time_ms, time_offset_ms
            )

        return self.cache[cache_key]

    def clear_cache(self):
        """Clear the cache"""
        self.cache.clear()


def load_tracking_data_from_storage(
    tracking_blob_url: str, video_start_time_ms: int = 0, time_offset_ms: int = 0
) -> pd.DataFrame:
    """
    Load tracking data from Azure Blob Storage or local storage.
    Normalizes tracking data timing for segment videos.

    Args:
        tracking_blob_url: Azure blob URL or local file path for tracking data
        video_start_time_ms: Video start time offset (deprecated, use time_offset_ms)
        time_offset_ms: Time offset to normalize tracking data (segment start time in original video)

    Returns:
        pandas.DataFrame: Normalized tracking data (starts at 0ms for segment videos)
    """
    try:
        logger.info(f"Loading tracking data from storage: {tracking_blob_url}")

        # Handle different storage types based on DEBUG setting
        from django.conf import settings

        if tracking_blob_url.startswith("https://"):
            # Full Azure Blob URL - extract the relative path
            relative_path = extract_relative_path_from_azure_url(tracking_blob_url)
            logger.info(f"Relative path: {relative_path}")
            response = default_storage.open(relative_path)
            logger.info(f"Response of the {tracking_blob_url}: {response}")

        elif settings.DEBUG and not tracking_blob_url.startswith("https"):
            # Local development - handle file path properly
            if tracking_blob_url.startswith("/media/"):
                # Remove leading /media/ for local storage
                file_path = tracking_blob_url[7:]  # Remove '/media/'
            elif tracking_blob_url.startswith("media/"):
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

        # Use time_off directly as video time
        tracking_df["video_time_ms"] = tracking_df["time_off"]

        # Normalize timing for segment videos (segment starts at 00:00) and Subtract the offset so tracking times align with segment start
        if time_offset_ms > 0:
            tracking_df["video_time_ms"] = tracking_df["video_time_ms"] - time_offset_ms
            # Filter out negative times
            tracking_df = tracking_df[tracking_df["video_time_ms"] >= 0].copy()
            logger.info(
                f"Normalized tracking data with offset {time_offset_ms}ms, {len(tracking_df)} points remaining"
            )

        logger.info(f"Loaded tracking data with {len(tracking_df)} spotlights")
        return tracking_df

    except Exception as e:
        logger.error(f"Error loading tracking data from {tracking_blob_url}: {e}")
        return pd.DataFrame()  # Return empty DataFrame on error


def download_video_from_storage(
    video_blob_url: str, temp_dir: Optional[str] = None
) -> str:
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
            if video_blob_url.startswith("/media/"):
                # Remove leading /media/ for local storage
                file_path = video_blob_url[7:]  # Remove '/media/'
            elif video_blob_url.startswith("media/"):
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

        # with open(temp_path, 'wb') as f:
        #     f.write(response.read())
        # response.close()
        with open(temp_path, "wb") as f:
            # Optimized 2MB chunks for large video files (3-4GB)
            chunk_size = 2 * 1024 * 1024  # 2MB chunks (2,097,152 bytes)
            total_bytes = 0
            last_logged_mb = 0

            while True:
                chunk = response.read(chunk_size)
                if not chunk:
                    break
                f.write(chunk)
                total_bytes += len(chunk)

                # Log progress every 200MB
                current_mb = total_bytes / (1024 * 1024)
                if int(current_mb) - last_logged_mb >= 200:
                    last_logged_mb = int(current_mb)
                    logger.info(f"Downloaded {current_mb:.1f} MB of video file")

            logger.info(
                f"Video download completed: {total_bytes / (1024 * 1024):.1f} MB total"
            )
        response.close()
        # temp_path = "./media/video_data/test_video.mp4"
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
    frame,
    video_time_ms,
    tracking_df,
    object_id,
    w,
    h,
    overlay_tolerance,
    player_name,
    with_circle=True,
    show_player_name=True,
):
    """
    Add a clean, non-sparkling border circle around the player's feet
    WITHOUT overlapping the player (masking inside bounding box).
    Adapted from WAZO.py

    Note: tracking_df should contain normalized video_time_ms (starts at 0ms for segment videos).
    video_time_ms is the current frame time in the segment video (also normalized, starting from 0ms).

    Args:
        with_circle: If True, draw circle/ellipse overlay around player
        show_player_name: If True, display player name text overlay
    """
    # Find closest tracking data point for current frame time
    cur_index = (tracking_df["video_time_ms"] - video_time_ms).abs().idxmin()
    cur_track_time = tracking_df.iloc[cur_index]["video_time_ms"]

    if np.abs(cur_track_time - video_time_ms) <= overlay_tolerance:
        # Convert normalized coords to pixel coords
        cur_x = tracking_df.loc[cur_index]["x"] * w / 1000
        cur_y = tracking_df.loc[cur_index]["y"] * h / 1000
        head_y = cur_y - (tracking_df.loc[cur_index]["h"] * h / 1000) * 0.5 - 10
        # Slight upward shift
        foot_y = cur_y + (tracking_df.loc[cur_index]["h"] * h / 1000) * 0.5 - 10
        rotation_angle = 360
        ellipse_width = int(tracking_df.loc[cur_index]["w"] * w / 1000 / 0.5)
        ellipse_height = int(tracking_df.loc[cur_index]["h"] * h / 1000 / 3)

        # ---- Create transparent overlay (circle) ----
        if with_circle:
            overlay = np.zeros_like(frame, dtype=np.uint8)
            alpha_mask = np.zeros((frame.shape[0], frame.shape[1]), dtype=np.float32)

            # Draw ellipse border on mask (solid)
            cv2.ellipse(
                alpha_mask,
                (int(cur_x), int(foot_y)),
                (ellipse_width, ellipse_height),
                rotation_angle,
                0,
                360,
                1.0,
                4,
                lineType=cv2.LINE_AA,
            )

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

        # ---- Draw object label (player name) ----
        if show_player_name and player_name is not None:
            cv2.putText(
                frame,
                player_name,
                (int(cur_x - 20), int(head_y)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (255, 255, 255),
                2,
            )

    return frame


def crop_frame_to_square(
    frame, video_time_ms, tracking_df, w, h, overlay_tolerance, padding_ratio=0.1
):
    """
    Crop frame to 1:1 (square) Instagram ratio, centered on the tracked player.
    No zooming, stretching, or compression - just a square crop from the original frame.

    Args:
        frame: Input frame (numpy array)
        video_time_ms: Current video time in milliseconds
        tracking_df: DataFrame with tracking data
        w: Original frame width
        h: Original frame height
        overlay_tolerance: Time tolerance for matching tracking data
        padding_ratio: Not used (kept for compatibility)

    Returns:
        tuple: (cropped_frame, new_width, new_height)
    """
    # Always use fixed crop size = smaller dimension (no zooming)
    crop_size = min(w, h)

    if tracking_df.empty:
        # If no tracking data, return center crop
        x_start = (w - crop_size) // 2
        y_start = (h - crop_size) // 2
        cropped = frame[y_start : y_start + crop_size, x_start : x_start + crop_size]
        return cropped, crop_size, crop_size

    # Find matching tracking data
    cur_index = (tracking_df["video_time_ms"] - video_time_ms).abs().idxmin()
    cur_track_time = tracking_df.iloc[cur_index]["video_time_ms"]

    if np.abs(cur_track_time - video_time_ms) > overlay_tolerance:
        # If no matching tracking data, return center crop
        x_start = (w - crop_size) // 2
        y_start = (h - crop_size) // 2
        cropped = frame[y_start : y_start + crop_size, x_start : x_start + crop_size]
        return cropped, crop_size, crop_size

    # Convert normalized coords to pixel coords
    cur_x = tracking_df.loc[cur_index]["x"] * w / 1000
    cur_y = tracking_df.loc[cur_index]["y"] * h / 1000

    # Calculate crop center (player position)
    center_x = int(cur_x)
    center_y = int(cur_y)

    # Calculate crop boundaries, centered on player, ensuring they stay within frame
    x_start = center_x - crop_size // 2
    y_start = center_y - crop_size // 2

    # Adjust if crop goes outside frame boundaries
    if x_start < 0:
        x_start = 0
    elif x_start + crop_size > w:
        x_start = w - crop_size

    if y_start < 0:
        y_start = 0
    elif y_start + crop_size > h:
        y_start = h - crop_size

    # Crop the frame (no resizing - direct crop)
    cropped = frame[y_start : y_start + crop_size, x_start : x_start + crop_size]

    logger.debug(
        f"Cropped frame to {crop_size}x{crop_size} centered on player at ({center_x}, {center_y}), crop region: ({x_start}, {y_start})"
    )

    return cropped, crop_size, crop_size


def crop_frame_to_aspect_ratio(
    frame, video_time_ms, tracking_df, w, h, overlay_tolerance, aspect_ratio="9:16"
):
    """
    Crop frame to specified aspect ratio, centered on tracked player.

    Args:
        frame: Input frame (numpy array)
        video_time_ms: Current video time in milliseconds
        tracking_df: DataFrame with tracking data
        w: Original frame width
        h: Original frame height
        overlay_tolerance: Time tolerance for matching tracking data
        aspect_ratio: Aspect ratio string like "9:16", "1:1", "16:9", etc.

    Returns:
        tuple: (cropped_frame, new_width, new_height)
    """
    # Parse aspect ratio
    try:
        ratio_parts = aspect_ratio.split(":")
        if len(ratio_parts) != 2:
            raise ValueError(f"Invalid aspect ratio format: {aspect_ratio}")
        ratio_w, ratio_h = float(ratio_parts[0]), float(ratio_parts[1])
        target_ratio = ratio_w / ratio_h
    except Exception as e:
        logger.warning(f"Invalid aspect ratio '{aspect_ratio}', using 9:16: {e}")
        target_ratio = 9.0 / 16.0

    # Calculate crop dimensions based on aspect ratio
    frame_ratio = w / h

    if target_ratio > frame_ratio:
        # Target is wider - crop height
        crop_h = int(w / target_ratio)
        crop_w = w
    else:
        # Target is taller - crop width
        crop_w = int(h * target_ratio)
        crop_h = h

    # Ensure crop doesn't exceed frame dimensions
    crop_w = min(crop_w, w)
    crop_h = min(crop_h, h)

    # Get player position for centering
    center_x = w // 2
    center_y = h // 2

    if not tracking_df.empty:
        # Find matching tracking data
        cur_index = (tracking_df["video_time_ms"] - video_time_ms).abs().idxmin()
        cur_track_time = tracking_df.iloc[cur_index]["video_time_ms"]

        if np.abs(cur_track_time - video_time_ms) <= overlay_tolerance:
            # Convert normalized coords to pixel coords
            cur_x = tracking_df.loc[cur_index]["x"] * w / 1000
            cur_y = tracking_df.loc[cur_index]["y"] * h / 1000
            center_x = int(cur_x)
            center_y = int(cur_y)

    # Calculate crop boundaries, centered on player
    x_start = center_x - crop_w // 2
    y_start = center_y - crop_h // 2

    # Adjust if crop goes outside frame boundaries
    if x_start < 0:
        x_start = 0
    elif x_start + crop_w > w:
        x_start = w - crop_w

    if y_start < 0:
        y_start = 0
    elif y_start + crop_h > h:
        y_start = h - crop_h

    # Crop the frame (no resizing - direct crop)
    cropped = frame[y_start : y_start + crop_h, x_start : x_start + crop_w]

    logger.debug(
        f"Cropped frame to {crop_w}x{crop_h} ({aspect_ratio}) centered on player at ({center_x}, {center_y}), crop region: ({x_start}, {y_start})"
    )

    return cropped, crop_w, crop_h


def convert_to_browser_friendly(input_video_path: str, fps: float) -> str:
    """Convert video to browser/Flutter-friendly H.264 format using ffmpeg."""
    try:
        # Check ffmpeg availability
        subprocess.run(
            ["ffmpeg", "-version"], capture_output=True, timeout=5, check=True
        )
    except (
        FileNotFoundError,
        subprocess.TimeoutExpired,
        subprocess.CalledProcessError,
    ):
        logger.warning("ffmpeg not available, skipping browser-friendly conversion")
        return input_video_path

    temp_output = input_video_path + ".h264.mp4"
    try:
        cmd = [
            "ffmpeg",
            "-loglevel",
            "error",
            "-i",
            input_video_path,
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "23",
            "-pix_fmt",
            "yuv420p",
            "-profile:v",
            "baseline",
            "-level",
            "3.1",
            "-movflags",
            "+faststart",
            "-vsync",
            "cfr",
            "-r",
            str(int(fps)),
            "-an",
            "-f",
            "mp4",
            "-y",
            temp_output,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if (
            result.returncode == 0
            and os.path.exists(temp_output)
            and os.path.getsize(temp_output) > 0
        ):
            os.remove(input_video_path)
            os.rename(temp_output, input_video_path)
            logger.info(f"Video converted to browser-friendly H.264 format")
            return input_video_path
        else:
            if os.path.exists(temp_output):
                os.remove(temp_output)
            raise RuntimeError(f"ffmpeg conversion failed: {result.stderr}")
    except Exception as e:
        if os.path.exists(temp_output):
            os.remove(temp_output)
        logger.error(f"Browser-friendly conversion failed: {e}")
        raise


def create_video_with_tracking_overlay(
    video_time_min_ms,
    video_time_max_ms,
    dict_tracking_df,
    text_str,
    video_filepath,
    out_video_filepath,
    player_name,
    add_overlay=True,
    aspect_ratio=None,
    with_circle=True,
    show_player_name=True,
):
    """
    Create a video with tracking overlay for a specified time range.
    Adapted from WAZO.py

    Note: This function assumes the input video is a segment that starts at 0ms.
    Tracking data should be normalized (subtract start_offset) before calling this function.

    Args:
        video_time_min_ms: Start time in milliseconds (typically 0 for segment videos)
        video_time_max_ms: End time in milliseconds (duration of segment)
        dict_tracking_df: Dictionary of tracking data DataFrames keyed by object_id (already normalized)
        text_str: Optional text overlay string
        video_filepath: Input video file path (segment video starting at 0ms)
        out_video_filepath: Output video file path
        player_name: Player name for label overlay
        add_overlay: If True, add tracking overlay and player labels. If False, process frames without overlay.
        aspect_ratio: Aspect ratio string like "9:16", "1:1", or None for original (no crop)
        with_circle: If True, draw circle/ellipse overlay around player
        show_player_name: If True, display player name text overlay
    """
    logger.info(
        f"Creating video with tracking overlay from {video_time_min_ms}ms to {video_time_max_ms}ms"
    )

    # Find relevant tracking data for the specified time range:
    use_tracking_df = {}
    for object_id in dict_tracking_df:
        # TODO: Remove this after testing, Debug: show original tracking data range
        original_min = dict_tracking_df[object_id]["video_time_ms"].min()
        original_max = dict_tracking_df[object_id]["video_time_ms"].max()
        logger.debug(
            f"Tracking data for {object_id}: range {original_min:.2f}ms to {original_max:.2f}ms (normalized)"
        )

        mask_df = (
            dict_tracking_df[object_id]["video_time_ms"] >= video_time_min_ms
        ) & (dict_tracking_df[object_id]["video_time_ms"] <= video_time_max_ms)
        if mask_df.sum() == 0:
            logger.warning(
                f"No tracking data found for {object_id} during time range {video_time_min_ms}ms to {video_time_max_ms}ms"
            )
            continue
        use_tracking_df[object_id] = (
            dict_tracking_df[object_id].loc[mask_df, :].reset_index(drop=True)
        )
        filtered_min = use_tracking_df[object_id]["video_time_ms"].min()
        filtered_max = use_tracking_df[object_id]["video_time_ms"].max()
        logger.debug(
            f"Filtered tracking data for {object_id}: {len(use_tracking_df[object_id])} points, range {filtered_min:.2f}ms to {filtered_max:.2f}ms"
        )

    # Get input video capture and properties:
    cap = cv2.VideoCapture(video_filepath)
    fps = cap.get(cv2.CAP_PROP_FPS)
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    logger.info(f"Video properties - fps: {fps}, width: {w}, height: {h}")

    # Check if video properties are valid
    if not cap.isOpened():
        raise ValueError(f"Failed to open video file: {video_filepath}")

    if fps is None or fps <= 0:
        logger.warning(f"Invalid FPS ({fps}), using default FPS of 30")
        fps = 30.0

    if w <= 0 or h <= 0:
        raise ValueError(f"Invalid video dimensions: {w}x{h}")

    # Determine output dimensions based on aspect ratio
    output_w = w
    output_h = h

    if aspect_ratio:
        # Calculate output dimensions for the aspect ratio
        try:
            ratio_parts = aspect_ratio.split(":")
            ratio_w, ratio_h = float(ratio_parts[0]), float(ratio_parts[1])
            target_ratio = ratio_w / ratio_h
            frame_ratio = w / h

            if target_ratio > frame_ratio:
                # Target is wider - crop height
                output_h = int(w / target_ratio)
                output_w = w
            else:
                # Target is taller - crop width
                output_w = int(h * target_ratio)
                output_h = h

            output_w = min(output_w, w)
            output_h = min(output_h, h)
            if aspect_ratio == "9:16":
                logger.info(
                    f"Vertical video (9:16) generation: "
                    f"Original frame: {w}x{h}, Output size: {output_w}x{output_h} "
                    f"(cropping to vertical format, centered on tracked player)"
                )
            elif aspect_ratio == "1:1":
                logger.info(
                    f"Square video (1:1) generation: "
                    f"Original frame: {w}x{h}, Output size: {output_w}x{output_h} "
                    f"(cropping to square format, centered on tracked player)"
                )
            else:
                logger.info(
                    f"Aspect ratio {aspect_ratio} enabled: output size will be {output_w}x{output_h}"
                )
        except Exception as e:
            logger.warning(
                f"Invalid aspect ratio '{aspect_ratio}', using original dimensions: {e}"
            )
            aspect_ratio = None

    # Set up output video writer:
    sav = cv2.VideoWriter(
        out_video_filepath,
        cv2.VideoWriter_fourcc(*"mp4v"),
        fps,
        (output_w, output_h),
        True,
    )

    # For each tracking data point, create a frame with the tracking overlay:
    overlay_tolerance = 1 / fps * 2 * 1000

    # Get actual first frame timestamp to detect any offset
    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
    ret, frm = cap.read()

    # Check if frame was read successfully
    if not ret or frm is None:
        logger.error(f"Failed to read first frame")
        cap.release()
        sav.release()
        return

    # Get actual timestamp of first frame (may have small offset due to keyframe alignment)
    first_frame_time_ms = cap.get(cv2.CAP_PROP_POS_MSEC)
    logger.info(f"Successfully read first frame, shape: {frm.shape}")
    logger.info(f"First frame actual timestamp: {first_frame_time_ms:.2f}ms")

    # Calculate frame time offset (segment should start at 0ms, but may have small offset)
    # We'll normalize all frame times by subtracting this offset
    time_offset = first_frame_time_ms
    if abs(time_offset) > 50:  # If offset is significant, warn
        logger.warning(f"First frame has significant offset: {time_offset:.2f}ms")
        logger.warning(
            "This may cause timing drift. Consider re-encoding segment with constant frame rate."
        )
    else:
        logger.debug(f"Frame timestamp offset is minimal: {time_offset:.2f}ms")

    # Use actual frame timestamps for accurate matching, but normalize to segment start (0ms)
    cur_video_time = first_frame_time_ms - time_offset  # Should be ~0ms
    logger.info(f"Starting at normalized time: {cur_video_time:.2f}ms")

    while cur_video_time <= video_time_max_ms:
        # Ensure frame is in RGB format (3 channels)
        if len(frm.shape) == 2:  # Grayscale
            frm = cv2.cvtColor(frm, cv2.COLOR_GRAY2BGR)
        elif frm.shape[2] == 4:  # RGBA
            frm = cv2.cvtColor(frm, cv2.COLOR_RGBA2BGR)

        # Add bounding box overlay to current frame (only if add_overlay is True):
        if add_overlay:
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
                    with_circle=with_circle,
                    show_player_name=show_player_name,
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

        # Crop to aspect ratio if specified
        if aspect_ratio:
            # Get primary tracking data for cropping (use first available)
            primary_tracking_df = None
            if use_tracking_df:
                primary_tracking_df = next(iter(use_tracking_df.values()))

            if aspect_ratio == "1:1":
                # Use square crop function for 1:1
                frm, cropped_w, cropped_h = crop_frame_to_square(
                    frm,
                    cur_video_time,
                    (
                        primary_tracking_df
                        if primary_tracking_df is not None
                        else pd.DataFrame()
                    ),
                    w,
                    h,
                    overlay_tolerance,
                )
            else:
                # Use aspect ratio crop function for other ratios (e.g., 9:16)
                if aspect_ratio == "9:16":
                    logger.debug(
                        f"Frame {cur_video_time:.2f}ms: Cropping to 9:16 vertical format "
                        f"centered on player"
                    )
                frm, cropped_w, cropped_h = crop_frame_to_aspect_ratio(
                    frm,
                    cur_video_time,
                    (
                        primary_tracking_df
                        if primary_tracking_df is not None
                        else pd.DataFrame()
                    ),
                    w,
                    h,
                    overlay_tolerance,
                    aspect_ratio,
                )

        # Write frame to output video:
        sav.write(frm)
        # Get the next frame:+
        ret, frm = cap.read()
        if not ret or frm is None:
            logger.info(f"End of video reached at time: {cur_video_time:.2f}ms")
            break

        # Get actual frame timestamp and normalize to segment start (0ms)
        actual_frame_time = cap.get(cv2.CAP_PROP_POS_MSEC)
        cur_video_time = actual_frame_time - time_offset  # Normalize to segment start

    # Close input and output videos:
    sav.release()
    cap.release()

    # Validate output file
    if (
        not os.path.exists(out_video_filepath)
        or os.path.getsize(out_video_filepath) == 0
    ):
        raise ValueError(f"Output video file is empty or missing: {out_video_filepath}")

    # Log completion with aspect ratio info
    if aspect_ratio:
        if aspect_ratio == "9:16":
            logger.info(
                f"Vertical video (9:16) generation completed: {out_video_filepath} "
                f"(Final output: {output_w}x{output_h} pixels)"
            )
        else:
            logger.info(
                f"Video generation completed with aspect ratio {aspect_ratio}: {out_video_filepath} "
                f"(Final output: {output_w}x{output_h} pixels)"
            )
    else:
        logger.info(
            f"Video generation completed (original format): {out_video_filepath} "
            f"(Final output: {output_w}x{output_h} pixels)"
        )

    # Convert to browser/Flutter-friendly format
    try:
        out_video_filepath = convert_to_browser_friendly(out_video_filepath, fps)
        if aspect_ratio == "9:16":
            logger.info("Vertical video converted to browser-friendly H.264 format")
    except Exception as e:
        logger.error(f"Browser-friendly conversion failed: {e}")
        raise RuntimeError(f"Failed to convert video to browser-friendly format: {e}")

    return out_video_filepath


def create_clip_reel_overlay_video(
    clip_reel: TraceClipReel,
    tracking_cache: Optional[TrackingDataCache] = None,
    session_video_path: Optional[str] = None,
    time_offset_ms: int = 0,
    add_overlay: bool = True,
) -> str:
    """
    Create overlay video for a single TraceClipReel object.
    Aspect ratio is determined from clip_reel.ratio.

    Args:
        clip_reel: TraceClipReel instance (contains tags and ratio)
        tracking_cache: TrackingDataCache instance for performance
        session_video_path: Optional path to already downloaded session video
        time_offset_ms: Time offset to normalize tracking data (segment start time in original video)
        add_overlay: If True, add tracking overlay and player labels. If False, process frames without overlay.

    Returns:
        str: Path to generated video file
    """
    if tracking_cache is None:
        tracking_cache = TrackingDataCache()

    # Get ratio and tags from clip_reel
    ratio = clip_reel.ratio
    tags = clip_reel.tags or []

    # Determine overlay settings from tags
    show_player_name = "with_name_overlay" in tags
    with_circle = "with_circle_overlay" in tags

    # If add_overlay is explicitly False, override tag settings
    if not add_overlay:
        show_player_name = False
        with_circle = False
    else:
        # add_overlay should be True if either overlay is enabled
        add_overlay = show_player_name or with_circle

    # Determine aspect ratio for cropping based on clip_reel.ratio
    # If ratio is "original", no crop (aspect_ratio = None)
    # If ratio is "9:16", crop to 9:16 vertical format
    # If ratio is "1:1", crop to 1:1 square format
    aspect_ratio = None
    if ratio == "9:16":
        aspect_ratio = "9:16"
        logger.info(
            f"Vertical video generation enabled for clip reel {clip_reel.id}: "
            f"Will crop to 9:16 aspect ratio (vertical format)"
        )
    elif ratio == "1:1":
        aspect_ratio = "1:1"
        logger.info(
            f"Square video generation enabled for clip reel {clip_reel.id}: "
            f"Will crop to 1:1 aspect ratio (square format)"
        )
    else:
        # ratio == "original" or any other value
        aspect_ratio = None
        logger.info(
            f"Original video format for clip reel {clip_reel.id}: "
            f"No cropping will be applied (maintaining original aspect ratio)"
        )

    logger.info(
        f"Creating video for clip reel {clip_reel.id} (event_id={clip_reel.event_id}): "
        f"ratio={ratio}, tags={tags}, add_overlay={add_overlay}, "
        f"show_player_name={show_player_name}, with_circle={with_circle}, aspect_ratio={aspect_ratio}"
    )

    # Get session and video file
    session = clip_reel.session

    # Use provided session video path if available, otherwise download
    if session_video_path and os.path.exists(session_video_path):
        temp_video_path = session_video_path
        logger.info(f"Using provided session video path: {session_video_path}")
    else:
        video_file_url = session.blob_video_url or session.video_url

        if not video_file_url:
            raise ValueError(f"No video URL available for session {session.session_id}")

        # Download video from storage to temporary file
        temp_video_path = download_video_from_storage(video_file_url)

    try:
        # Get tracking data only if overlay is needed
        tracking_data = {}
        player_name = "Unknown Player"
        text_str = None

        if add_overlay:
            # Get involved players and their tracking data for overlay
            trace_object = TraceObject.objects.filter(
                session=session, player=clip_reel.primary_player
            ).first()

            logger.info(
                f"Looking for TraceObject for session {session.id}, player {clip_reel.primary_player.id if clip_reel.primary_player else 'None'}"
            )
            logger.info(f"Found TraceObject: {trace_object}")
            if trace_object:
                logger.info(
                    f"TraceObject tracking_blob_url: {trace_object.tracking_blob_url}"
                )

            if trace_object and trace_object.tracking_blob_url:
                # Load tracking data with caching and normalize for segment video
                player_tracking_df = tracking_cache.get_tracking_data(
                    trace_object.tracking_blob_url, time_offset_ms=time_offset_ms
                )

                logger.info(
                    f"Tracking Data Df is downloaded with the URL: {trace_object.tracking_blob_url}, {player_tracking_df}"
                )

                if not player_tracking_df.empty:
                    tracking_data[clip_reel.primary_player.object_id] = (
                        player_tracking_df
                    )
                    logger.info(
                        f"Loaded tracking data for player {clip_reel.primary_player.object_id}"
                    )
                else:
                    logger.warning(
                        f"No tracking data found for player {clip_reel.primary_player.object_id}"
                    )

            if not tracking_data:
                raise ValueError(
                    f"No tracking data found for any involved players in clip reel {clip_reel.id}. "
                    f"Tracking data is required for overlay generation (tags: {tags})"
                )

            # Create text string from highlight tags
            text_str = " | ".join(clip_reel.tags or [])

            # Handle case where primary_player exists but user might be None
            if clip_reel.primary_player and clip_reel.primary_player.user:
                player_name = clip_reel.primary_player.user.name
                if not player_name:
                    player_name = clip_reel.primary_player.name
            elif clip_reel.primary_player:
                player_name = clip_reel.primary_player.name
        elif aspect_ratio:
            # For videos with aspect ratio crop but no overlay, we still need player info for centering
            if clip_reel.primary_player:
                trace_object = TraceObject.objects.filter(
                    session=session, player=clip_reel.primary_player
                ).first()

                if trace_object and trace_object.tracking_blob_url:
                    # Load tracking data for cropping (but no overlay)
                    player_tracking_df = tracking_cache.get_tracking_data(
                        trace_object.tracking_blob_url, time_offset_ms=time_offset_ms
                    )
                    if not player_tracking_df.empty:
                        tracking_data[clip_reel.primary_player.object_id] = (
                            player_tracking_df
                        )
                        logger.info(
                            f"Loaded tracking data for vertical crop centering (no overlay)"
                        )

        # Create temporary output file
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as temp_file:
            output_path = temp_file.name

        # Generate video using existing function
        logger.info(
            f"Starting video generation for clip reel {clip_reel.id} "
            f"(event_id={clip_reel.event_id}, ratio={ratio}, tags={tags}): "
            f"overlay={'enabled' if add_overlay else 'disabled'}, "
            f"show_player_name={show_player_name}, with_circle={with_circle}, "
            f"aspect_ratio={aspect_ratio or 'original (no crop)'}"
        )

        create_video_with_tracking_overlay(
            video_time_min_ms=0,  # Segment starts at 00:00
            video_time_max_ms=clip_reel.duration_ms,  # Duration from segment start
            dict_tracking_df=tracking_data,
            text_str=text_str,
            video_filepath=temp_video_path,
            out_video_filepath=output_path,
            player_name=player_name,
            add_overlay=add_overlay,
            aspect_ratio=aspect_ratio,
            with_circle=with_circle,
            show_player_name=show_player_name,
        )

        # Log successful generation with file info
        file_size_mb = os.path.getsize(output_path) / (1024 * 1024)
        logger.info(
            f"Successfully generated video for clip reel {clip_reel.id} "
            f"(event_id={clip_reel.event_id}): "
            f"file={output_path}, size={file_size_mb:.2f}MB, "
            f"tags={tags}, ratio={ratio}, aspect_ratio={aspect_ratio or 'original'}, "
            f"show_player_name={show_player_name}, with_circle={with_circle}"
        )

        return output_path

    finally:
        # Clean up temporary video file only if we downloaded it ourselves
        # (not if it was provided as session_video_path)
        if (
            not session_video_path
            and "temp_video_path" in locals()
            and os.path.exists(temp_video_path)
        ):
            os.unlink(temp_video_path)
            logger.info(f"Cleaned up temporary video file: {temp_video_path}")


def upload_video_to_storage(video_file_path: str, clip_reel: TraceClipReel) -> str:
    """
    Upload generated video to Azure Blob Storage with robust retry logic and error handling.
    Based on the same patterns as download_video_and_save_to_azure_blob.
    """
    try:
        # Generate blob path with event_id, video_type, and ratio for unique naming
        session_id = clip_reel.session.session_id
        highlight_id = clip_reel.highlight.highlight_id
        video_type = (
            clip_reel.video_type or "original"
        )  # Use "original" as fallback if None
        event_id = clip_reel.event_id
        ratio = clip_reel.ratio

        from tracevision.utils import TraceVisionStoragePaths

        blob_path = TraceVisionStoragePaths.get_highlight_video_path(
            session_id=session_id,
            highlight_id=highlight_id,
            video_type=video_type,
            event_id=event_id,
            ratio=ratio,
        )

        # Ensure blob path is clean and valid
        blob_path = blob_path.replace("//", "/").strip("/")
        logger.info(
            f"Uploading video to storage: {blob_path} "
            f"(event_id={event_id}, video_type={video_type}, ratio={ratio})"
        )

        # Validate file exists and get properties
        if not os.path.exists(video_file_path):
            raise FileNotFoundError(f"Video file not found: {video_file_path}")

        file_size = os.path.getsize(video_file_path)
        if file_size == 0:
            raise ValueError("Video file is empty")

        logger.info(f"Video file size: {file_size / (1024*1024):.1f} MB")

        # Determine content type
        content_type = "video/mp4"
        if video_file_path.lower().endswith(".mp4"):
            content_type = "video/mp4"
        elif video_file_path.lower().endswith(".avi"):
            content_type = "video/avi"
        elif video_file_path.lower().endswith(".mov"):
            content_type = "video/quicktime"

        # Handle different storage types based on DEBUG setting
        from django.conf import settings

        # Check if we're using Azure Blob Storage (regardless of DEBUG setting)
        if (
            hasattr(settings, "AZURE_CONNECTION_STRING")
            and settings.AZURE_CONNECTION_STRING
        ):
            # Azure Blob Storage - use robust upload
            logger.info("Using robust Azure Blob Storage upload")
            return upload_video_to_azure_blob_robust(
                video_file_path, blob_path, content_type, file_size
            )
        else:
            # Local development - use default_storage
            logger.info("Using local storage (default_storage)")
            with open(video_file_path, "rb") as video_file:
                saved_path = default_storage.save(blob_path, video_file)
            storage_url = default_storage.url(saved_path)
            logger.info(f"Video uploaded to local storage: {storage_url}")
            return storage_url

    except Exception as e:
        logger.error(f"Error uploading video to storage: {e}")
        raise


def upload_video_to_azure_blob_robust(
    video_file_path: str, blob_path: str, content_type: str, file_size: int
) -> str:
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
                settings.AZURE_CONNECTION_STRING
            )
            blob_client = blob_service_client.get_blob_client(
                container=settings.AZURE_CONTAINER_NAME, blob=blob_path
            )
            logger.info(
                f"Successfully created blob client on attempt {client_attempt + 1}"
            )
            break
        except Exception as client_error:
            if client_attempt < 2:
                logger.warning(
                    f"Blob client creation attempt {client_attempt + 1} failed: {client_error}. Retrying..."
                )
                time.sleep(5)
            else:
                logger.error(
                    f"Failed to create blob client after 3 attempts: {client_error}"
                )
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
                f"Upload progress: {percentage:.1f}% ({uploaded_mb:.1f}MB / {total_mb:.1f}MB)"
            )

    # Try primary upload method first
    for attempt in range(max_retries):
        try:
            with open(video_file_path, "rb") as data:
                # Try with progress callback first
                try:
                    upload_options = {
                        "data": data,
                        "blob_type": BlobType.BLOCKBLOB,
                        "overwrite": True,
                        "content_settings": ContentSettings(content_type=content_type),
                        "max_concurrency": 2,
                        "length": file_size,
                        "timeout": 7200,  # 2 hours timeout for large files
                        "progress_hook": progress_callback,
                    }

                    logger.info(
                        f"Starting upload attempt {attempt + 1} with progress tracking..."
                    )
                    blob_client.upload_blob(**upload_options)
                except TypeError as progress_error:
                    if "progress_callback" in str(progress_error):
                        logger.warning(
                            "Progress callback failed, retrying without progress tracking..."
                        )
                        # Reset file pointer
                        data.seek(0)
                        # Upload without progress callback
                        upload_options_simple = {
                            "data": data,
                            "blob_type": BlobType.BLOCKBLOB,
                            "overwrite": True,
                            "content_settings": ContentSettings(
                                content_type=content_type
                            ),
                            "max_concurrency": 2,
                            "length": file_size,
                            "timeout": 7200,
                        }
                        blob_client.upload_blob(**upload_options_simple)
                    else:
                        raise progress_error

            upload_success = True
            logger.info(
                f"Successfully uploaded video to Azure on attempt {attempt + 1}"
            )
            break

        except Exception as e:
            error_str = str(e).lower()
            logger.warning(f"Upload attempt {attempt + 1} failed: {e}")

            # Check for specific network errors
            if any(
                keyword in error_str
                for keyword in ["dns", "resolve", "connection", "network", "timeout"]
            ):
                logger.warning(
                    "Network-related error detected, will retry with longer delay..."
                )
                # Longer backoff for network issues
                wait_time = retry_delay * (3**attempt)
            else:
                # Standard exponential backoff
                wait_time = retry_delay * (2**attempt)

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
                        blob_client, video_file_path, content_type, file_size
                    )
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
                            blob_client, video_file_path, content_type, file_size
                        )
                        if upload_success:
                            logger.info("Chunked upload successful!")
                            break
                    except Exception as chunked_error:
                        logger.error(f"Chunked upload also failed: {chunked_error}")

                logger.error(
                    f"All upload methods failed: {e}", exc_info=True, stack_info=True
                )
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

        with open(file_path, "rb") as data:
            blob_client.upload_blob(
                data=data,
                blob_type=BlobType.BLOCKBLOB,
                overwrite=True,
                content_settings=ContentSettings(content_type=content_type),
            )
        logger.info(
            f"Successfully uploaded {file_size / (1024*1024):.1f} MB using direct method"
        )
        return True
    except Exception as e:
        logger.error(f"Direct upload failed: {e}")
        return False


def upload_video_chunked(
    blob_client, file_path, content_type, file_size, chunk_size=2 * 1024 * 1024
):
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
            blob_client.delete_blob(delete_snapshots="include")
            logger.info("Cleared existing blob before chunked upload")
        except Exception as clear_error:
            logger.info(f"No existing blob to clear: {clear_error}")

        # Start the block blob upload
        block_ids = []
        block_number = 0
        total_uploaded = 0

        with open(file_path, "rb") as file_data:
            while True:
                chunk = file_data.read(chunk_size)
                if not chunk:
                    break

                # Generate unique block ID
                block_id = base64.b64encode(
                    f"block-{block_number:06d}-{int(time.time())}".encode()
                ).decode()
                block_ids.append(BlobBlock(block_id=block_id))

                # Upload the chunk with retry logic
                chunk_uploaded = False
                for chunk_attempt in range(3):
                    try:
                        # Validate chunk before upload
                        if not chunk or len(chunk) == 0:
                            logger.warning(
                                f"Chunk {block_number} is empty, skipping..."
                            )
                            break

                        # Ensure block_id is properly formatted
                        if not block_id or len(block_id) == 0:
                            logger.error(f"Invalid block_id for chunk {block_number}")
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
                                f"Chunk {block_number} upload attempt {chunk_attempt + 1} failed: {chunk_error}. Retrying..."
                            )
                            # Exponential backoff
                            time.sleep(2**chunk_attempt)
                        else:
                            logger.error(
                                f"Chunk {block_number} upload failed after 3 attempts: {chunk_error}"
                            )
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
                        f"Chunked upload progress: {percentage:.1f}% ({uploaded_mb:.1f}MB / {total_mb:.1f}MB)"
                    )

        # Commit the block list
        if block_ids:
            logger.info(f"Committing {len(block_ids)} blocks...")
            blob_client.commit_block_list(block_ids)
            logger.info(
                f"Successfully uploaded {file_size / (1024*1024):.1f} MB using chunked method"
            )
            return True
        else:
            logger.error("No blocks to commit")
            return False

    except Exception as e:
        logger.error(f"Chunked upload failed: {e}")
        return False
