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
        
        if settings.DEBUG:
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
            # Production - Azure Blob Storage
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
        logger.error(f"Error loading tracking data from {tracking_blob_url}: {e}")
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
        
        if settings.DEBUG:
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
            # Production - Azure Blob Storage
            response = default_storage.open(video_blob_url)
        
        with open(temp_path, 'wb') as f:
            f.write(response.read())
        response.close()
        
        logger.info(f"Downloaded video to temporary file: {temp_path}")
        return temp_path
        
    except Exception as e:
        logger.error(f"Error downloading video from {video_blob_url}: {e}")
        raise


def add_bbox_overlay_to_frame(
    frame, video_time_ms, tracking_df, object_id, w, h, overlay_tolerance
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
            cv2.putText(frame, object_id,
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
):
    """
    Create a video with tracking overlay for a specified time range.
    Adapted from WAZO.py
    """
    logger.info(f"Creating video with tracking overlay from {video_time_min_ms}ms to {video_time_max_ms}ms")
    
    # Find relevant tracking data for the specified time range:
    use_tracking_df = {}
    for object_id in dict_tracking_df:
        mask_df = (
            dict_tracking_df[object_id]["video_time_ms"] >= video_time_min_ms
        ) & (dict_tracking_df[object_id]["video_time_ms"] <= video_time_max_ms)
        if mask_df.sum() == 0:
            logger.warning(f"No tracking data found for {object_id} during time range")
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
        # Get the next frame:
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
        raise ValueError(f"No video URL available for session {session.session_id}")
    
    # Download video from storage to temporary file
    temp_video_path = download_video_from_storage(video_file_url)
    
    try:
        # Get involved players and their tracking data
        involved_players = clip_reel.involved_players.all()
        tracking_data = {}
        
        for player in involved_players:
            # Get TraceObject for this player in this session
            trace_object = TraceObject.objects.filter(
                session=session,
                player=player
            ).first()
            
            if trace_object and trace_object.tracking_blob_url:
                # Load tracking data with caching
                player_tracking_df = tracking_cache.get_tracking_data(
                    trace_object.tracking_blob_url
                )
                
                if not player_tracking_df.empty:
                    tracking_data[player.object_id] = player_tracking_df
                    logger.info(f"Loaded tracking data for player {player.object_id}")
                else:
                    logger.warning(f"No tracking data found for player {player.object_id}")
        
        if not tracking_data:
            raise ValueError(f"No tracking data found for any involved players in clip reel {clip_reel.id}")
        
        # Create text string from highlight tags
        text_str = " | ".join(clip_reel.tags or [])
        if involved_players:
            player_names = [p.object_id for p in involved_players]
            text_str += f" | {', '.join(player_names)}"
        
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
        )
        
        return output_path
        
    finally:
        # Clean up temporary video file
        if os.path.exists(temp_video_path):
            os.unlink(temp_video_path)


def upload_video_to_storage(video_file_path: str, clip_reel: TraceClipReel) -> str:
    """Upload generated video to Azure Blob Storage or local storage"""
    try:
        # Generate blob path
        session_id = clip_reel.session.session_id
        highlight_id = clip_reel.highlight.highlight_id
        video_type = clip_reel.video_type
        
        blob_path = f"highlight_videos/{session_id}/{highlight_id}_{video_type}.mp4"
        
        logger.info(f"Uploading video to storage: {blob_path}")
        
        # Upload to storage (Azure Blob or local based on DEBUG setting)
        with open(video_file_path, 'rb') as video_file:
            saved_path = default_storage.save(blob_path, video_file)
        
        # Return the storage URL
        storage_url = default_storage.url(saved_path)
        logger.info(f"Video uploaded successfully: {storage_url}")
        return storage_url
        
    except Exception as e:
        logger.error(f"Error uploading video to storage: {e}")
        raise
