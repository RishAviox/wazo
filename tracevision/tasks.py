import re
import os
import json
import logging
import time
import requests
import mimetypes
import tempfile
import pandas as pd
from datetime import datetime, timedelta
from celery import shared_task
from django.db import transaction
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from azure.storage.blob import BlobServiceClient, BlobType, ContentSettings

from tracevision.models import TraceSession, TraceObject, TraceHighlight, TraceHighlightObject, TracePlayer
from tracevision.services import TraceVisionService
from tracevision.notification_service import NotificationService
from django.conf import settings

from tracevision.utils import TraceVisionStoragePaths

logger = logging.getLogger(__name__)


def get_full_azure_blob_url(file_path: str) -> str:
    """
    Generate full Azure blob URL for a given file path.

    Args:
        file_path: The file path in Azure blob storage

    Returns:
        str: Full Azure blob URL
    """
    try:
        if hasattr(settings, 'AZURE_CUSTOM_DOMAIN') and settings.AZURE_CUSTOM_DOMAIN:
            return f"https://{settings.AZURE_CUSTOM_DOMAIN}/media/{file_path}"
        else:
            logger.warning(
                "AZURE_CUSTOM_DOMAIN not configured, using default_storage.url()")
            return default_storage.url(file_path)
    except Exception as e:
        logger.exception(
            f"Error generating Azure blob URL for {file_path}: {e}")
        return default_storage.url(file_path)


def fetch_tracking_data_and_save_to_azure_blob(trace_object, timeout=30):
    """
    Fetch tracking data from TraceObject's tracking_url, upload to Azure Blob Storage,
    and save the blob URL back to the TraceObject.

    Args:
        trace_object (TraceObject): TraceObject instance with tracking_url
        timeout (int): Request timeout in seconds

    Returns:
        dict: Result containing success status, data, and blob_url
    """
    try:
        # Check if already downloaded to prevent duplicates
        if trace_object.tracking_blob_url:
            logger.info(
                f"Tracking data already downloaded for object {trace_object.object_id}")
            return {
                'success': True,
                'processed': trace_object.tracking_processed,
                'azure_blob_url': trace_object.tracking_blob_url,
                'message': 'Already downloaded'
            }

        logger.info(
            f"Fetching tracking data for object {trace_object.object_id} from: {trace_object.tracking_url}")
        response = requests.get(trace_object.tracking_url, timeout=timeout)
        response.raise_for_status()

        tracking_data = response.json()

        # Create proper file path structure for Azure blob storage
        session_id = trace_object.session.session_id
        file_path = TraceVisionStoragePaths.get_tracking_data_path(
            session_id, trace_object.object_id)

        # Create ContentFile with the JSON data
        json_content = json.dumps(tracking_data, indent=2)
        file_content = ContentFile(json_content.encode('utf-8'))

        # Save to Azure Blob Storage
        logger.info(f"Uploading tracking data to Azure blob: {file_path}")
        saved_path = default_storage.save(file_path, file_content)

        # Generate the full URL for the blob
        # blob_url = get_full_azure_blob_url(saved_path)
        blob_url = default_storage.url(saved_path)
        # Update the TraceObject with the data and URL
        trace_object.tracking_blob_url = blob_url
        trace_object.save()

        # Log success with data size
        try:
            count = len(tracking_data.get('spotlights', [])) if isinstance(
                tracking_data, dict) else len(tracking_data)
            logger.info(
                f"Successfully processed tracking data for {trace_object.object_id}: {count} points, saved to {blob_url}")
        except Exception:
            logger.info(
                f"Successfully processed tracking data for {trace_object.object_id}, saved to {blob_url}")

        return {
            'success': True,
            'processed': trace_object.tracking_processed,
            'azure_blob_url': blob_url,
            'message': 'Downloaded and uploaded successfully'
        }

    except requests.exceptions.RequestException as e:
        logger.error(
            f"Failed to fetch tracking data for {trace_object.object_id} from {trace_object.tracking_url}: {e}")
        return {
            'success': False,
            'data': [],
            'blob_url': None,
            'error': f"Network error: {str(e)}"
        }
    except Exception as e:
        logger.error(
            f"Error processing tracking data for {trace_object.object_id}: {e}")
        return {
            'success': False,
            'data': [],
            'blob_url': None,
            'error': f"Processing error: {str(e)}"
        }


def upload_file_direct(blob_client, file_path, content_type, file_size):
    """
    Simple direct upload without any special configurations.
    """
    try:
        with open(file_path, 'rb') as data:
            blob_client.upload_blob(
                data=data,
                blob_type=BlobType.BLOCKBLOB,
                overwrite=True,
                content_settings=ContentSettings(content_type=content_type)
            )
        logger.info(
            f"Successfully uploaded {file_size / (1024*1024*1024):.2f} GB using direct method")
        return True
    except Exception as e:
        logger.error(f"Direct upload failed: {e}")
        return False


def upload_large_file_chunked(blob_client, file_path, content_type, file_size, chunk_size=2*1024*1024):
    """
    Upload large files using chunked approach for better reliability.
    """
    try:
        import base64
        from azure.storage.blob import BlobBlock
        from azure.core.exceptions import ResourceExistsError

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
                    raise Exception(f"Failed to upload chunk {block_number}")

                block_number += 1
                total_uploaded += len(chunk)

                # Log progress
                percentage = (total_uploaded / file_size) * 100
                uploaded_mb = total_uploaded / (1024 * 1024)
                total_mb = file_size / (1024 * 1024)
                logger.info(
                    f"Chunked upload progress: {percentage:.1f}% ({uploaded_mb:.1f}MB / {total_mb:.1f}MB)")

        # Commit the blocks
        if block_ids:
            blob_client.commit_block_list(block_ids)
            logger.info(
                f"Successfully uploaded {file_size / (1024*1024*1024):.2f} GB using chunked method")
            return True
        else:
            logger.error("No blocks to commit")
            return False

    except Exception as e:
        logger.error(f"Chunked upload failed: {e}")
        return False


@shared_task
def download_video_and_save_to_azure_blob(session_id, timeout=1200):
    """
    Download video from TraceSession's video_url, upload to Azure Blob Storage,
    and save the blob URL back to the TraceSession.
    """
    try:
        session = TraceSession.objects.get(id=session_id)

        if session.blob_video_url:
            logger.info(
                f"Video already downloaded for session {session.session_id}")
            return {
                'success': True,
                'blob_url': session.blob_video_url,
                'message': 'Already downloaded'
            }

        logger.info(
            f"Downloading video for session {session.session_id} from: {session.video_url}")

        # Download the video stream
        response = requests.get(
            session.video_url, stream=True, timeout=max(timeout, 600))
        response.raise_for_status()

        # # Validate content type
        content_type = response.headers.get('content-type', '')
        file_extension = mimetypes.guess_extension(content_type) or '.mp4'
        # content_type = "video/mp4"
        # file_extension = ".mp4"
        blob_path = TraceVisionStoragePaths.get_session_video_path(
            session.session_id, "original")

        # Ensure blob path is clean and valid
        blob_path = blob_path.replace('//', '/').strip('/')
        logger.info(f"Blob path: {blob_path}")

        # Create temp file and stream content to it
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_extension) as tmp_file:
            temp_file_path = tmp_file.name
            total_size = 0
            chunk_count = 0

            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    tmp_file.write(chunk)
                    total_size += len(chunk)
                    chunk_count += 1
                    if chunk_count % 1000 == 0:
                        logger.info(f"Downloaded {total_size / (1024*1024):.1f} MB for session {session.session_id}")

        logger.info(f"Download complete. Total size: {total_size / (1024*1024):.1f} MB")

        # Upload to Azure Blob Storage using SDK with retry logic
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
        max_retries = 1
        retry_delay = 10

        # temp_file_path = "video.mp4"

        # Progress callback for upload monitoring
        def progress_callback(current, total):
            if total and total > 0:
                percentage = (current / total) * 100
                uploaded_mb = current / (1024 * 1024)
                total_mb = total / (1024 * 1024)
                logger.info(
                    f"Upload progress: {percentage:.1f}% ({uploaded_mb:.1f}MB / {total_mb:.1f}MB)")

        for attempt in range(max_retries):
            try:
                # Validate file exists and get size
                if not os.path.exists(temp_file_path):
                    raise FileNotFoundError(
                        f"Video file not found: {temp_file_path}")

                file_size = os.path.getsize(temp_file_path)
                if file_size == 0:
                    raise ValueError("Video file is empty")

                logger.info(
                    f"{'=='*50}\n\nVideo File Size: {file_size / (1024*1024*1024):.2f} GB\n\n{'=='*50}")

                with open(temp_file_path, 'rb') as data:
                    # Try with progress callback first
                    try:
                        upload_options = {
                            'data': data,
                            'blob_type': BlobType.BLOCKBLOB,
                            'overwrite': True,
                            'content_settings': ContentSettings(content_type=content_type),
                            'max_concurrency': 2,  # Reduced for stability with large files
                            'length': file_size,
                            'timeout': 7200,  # 2 hours timeout for very large files
                            'progress_hook': progress_callback,  # Add progress tracking
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
                        upload_success = upload_file_direct(
                            blob_client, temp_file_path, content_type, file_size)
                        if upload_success:
                            logger.info("Direct upload successful!")
                            break
                    except Exception as direct_error:
                        logger.warning(f"Direct upload failed: {direct_error}")

                    # Try chunked upload for large files (lower threshold for better reliability)
                    if file_size > 10 * 1024 * 1024:  # For files larger than 10MB
                        try:
                            logger.info("Trying chunked upload method...")
                            upload_success = upload_large_file_chunked(
                                blob_client, temp_file_path, content_type, file_size)
                            if upload_success:
                                logger.info("Chunked upload successful!")
                                break
                        except Exception as chunked_error:
                            logger.error(
                                f"Chunked upload also failed: {chunked_error}")

                    logger.error(
                        f"All upload methods failed: {e}", exc_info=True, stack_info=True)
                    raise e

        # Clean up temp file
        # try:
        #     os.remove(temp_file_path)
        # except Exception as e:
        #     logger.warning(f"Failed to delete temp file {temp_file_path}: {e}")

        if not upload_success:
            return {
                'success': False,
                'blob_url': None,
                'error': "Upload failed after retries"
            }

        # Get full blob URL
        blob_url = f"{blob_client.url}"
        session.blob_video_url = blob_url
        session.save()

        return {
            'success': True,
            'blob_url': blob_url,
            'message': 'Downloaded and uploaded successfully',
            'file_size_mb': os.path.getsize(temp_file_path) / (1024 * 1024)
        }

    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to download video for session {session_id}: {e}")
        return {
            'success': False,
            'blob_url': None,
            'error': f"Download error: {str(e)}"
        }

    except Exception as e:
        logger.error(f"Unexpected error processing session {session_id}: {e}")
        return {
            'success': False,
            'blob_url': None,
            'error': f"Internal error: {str(e)}"
        }


def upload_result_data_to_azure_blob(session, result_data):
    """
    Upload session result data JSON to Azure Blob Storage and save the blob URL.

    Args:
        session (TraceSession): The session instance
        result_data (dict): Result data from TraceVision API

    Returns:
        dict: Result containing success status, blob_url, and message
    """
    try:
        # Check if already uploaded to prevent duplicates
        if session.result_blob_url:
            logger.info(
                f"Result data already uploaded for session {session.session_id}")
            return {
                'success': True,
                'blob_url': session.result_blob_url,
                'message': 'Already uploaded'
            }

        logger.info(
            f"Uploading result data for session {session.session_id} to Azure blob")

        # Create proper file path structure for Azure blob storage
        file_path = TraceVisionStoragePaths.get_session_result_path(
            session.session_id)

        # Create ContentFile with the JSON data
        json_content = json.dumps(result_data, indent=2, ensure_ascii=False)
        file_content = ContentFile(json_content.encode('utf-8'))

        # Save to Azure Blob Storage
        logger.info(f"Uploading result data to Azure blob: {file_path}")
        saved_path = default_storage.save(file_path, file_content)

        # Generate the full URL for the blob
        blob_url = default_storage.url(saved_path)

        # Update the TraceSession with the blob URL
        session.result_blob_url = blob_url
        session.save()

        # Log success with data size
        data_size_kb = len(json_content) / 1024
        logger.info(
            f"Successfully uploaded result data for session {session.session_id}: "
            f"Size: {data_size_kb:.2f} KB, saved to {blob_url}")

        return {
            'success': True,
            'blob_url': blob_url,
            'message': 'Uploaded successfully',
            'data_size_kb': data_size_kb
        }

    except Exception as e:
        logger.error(
            f"Error uploading result data for session {session.session_id}: {e}")
        return {
            'success': False,
            'blob_url': None,
            'error': f"Upload error: {str(e)}"
        }


def parse_and_store_session_data(session, result_data):
    """
    Parse session result data and store in structured models using atomic transactions.
    Gets or creates TracePlayer objects (avoids duplicates across all sessions), then creates all other data based on players.

    Team mapping logic:
    - Parses object_id patterns: away_<jersey_number> or home_<jersey_number>
    - Maps away_* to session.away_team, home_* to session.home_team
    - Extracts jersey number from object_id for accurate player matching
    - Checks for existing players by object_id and team across ALL sessions to avoid duplicates

    Args:
        session (TraceSession): The session instance
        result_data (dict): Result data from TraceVision API

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        with transaction.atomic():
            logger.info(
                f"Starting to parse session data for session {session.session_id}")

            session.trace_objects.all().delete()
            session.highlights.all().delete()

            # Get or create TracePlayer objects
            objects_data = result_data.get('objects', [])
            player_map = {}

            logger.info(
                f"Processing {len(objects_data)} objects to get/create players")

            for obj_data in objects_data:
                object_id = obj_data.get('object_id')
                side = obj_data.get('side', '')
                team = None
                jersey_number = 0

                if object_id:
                    # Parse object_id to extract team and jersey number
                    if object_id.startswith('away_'):
                        team = session.away_team
                        try:
                            jersey_number = int(object_id.split('_')[1])
                        except (ValueError, IndexError):
                            jersey_number = 0
                    elif object_id.startswith('home_'):
                        team = session.home_team
                        try:
                            jersey_number = int(object_id.split('_')[1])
                        except (ValueError, IndexError):
                            jersey_number = 0
                    else:
                        # Fallback to side field if object_id doesn't match expected pattern
                        team = session.home_team if side.lower() == 'home' else session.away_team
                        jersey_number = obj_data.get('jersey_number', 0)

                # Extract player information from object data
                player_name = obj_data.get('name', f'Player {object_id}')
                position = obj_data.get('position', 'Unknown')

                # Validate that we have a team assigned
                if not team:
                    logger.warning(
                        f"Could not determine team for object_id: {object_id}, skipping player")
                    continue

                # Check if player already exists for this object_id and team (across all sessions)
                existing_player = TracePlayer.objects.filter(
                    object_id=object_id,
                    team=team
                ).first()

                if existing_player:
                    # Use existing player from any session
                    trace_player = existing_player
                    logger.info(
                        f"Using existing player {object_id} (jersey: {jersey_number}, team: {team.name}) from session {existing_player.session.session_id}")
                else:
                    # Create new player
                    team_name = team.name if hasattr(
                        team, 'name') else str(team)
                    logger.info(
                        f"Creating new player {object_id} for team {team_name} with jersey number {jersey_number}")

                    trace_player = TracePlayer.objects.create(
                        object_id=object_id,
                        name=player_name,
                        jersey_number=jersey_number,
                        position=position,
                        session=session,
                        team=team,
                        user=None  # Will be mapped later via Celery task
                    )

                player_map[object_id] = trace_player

            logger.info(
                f"Processed {len(player_map)} players (existing + new)")

            # Step 2: Create TraceObject objects linked to players
            trace_objects = []
            logger.info(
                f"Creating trace objects for {len(objects_data)} objects")

            for obj_data in objects_data:
                object_id = obj_data.get('object_id')
                player = player_map.get(object_id)

                if player:
                    # Create TraceObject linked to the player
                    trace_object = TraceObject(
                        object_id=object_id,
                        type=obj_data.get('type', ''),
                        side=obj_data.get('side', ''),
                        appearance_fv=obj_data.get('appearance_fv'),
                        color_fv=obj_data.get('color_fv'),
                        tracking_url=obj_data.get('tracking_url', ''),
                        role=obj_data.get('role'),
                        session=session,
                        player=player,  # Link to TracePlayer instead of user
                    )
                    trace_objects.append(trace_object)

            # Bulk create objects
            if trace_objects:
                created_objects = TraceObject.objects.bulk_create(
                    trace_objects)
                logger.info(f"Created {len(created_objects)} trace objects")

                # Download tracking data for each object
                logger.info(
                    f"Downloading tracking data for {len(created_objects)} objects")
                updated_objects = []

                for trace_object in created_objects:
                    try:
                        if trace_object.tracking_url:
                            result = fetch_tracking_data_and_save_to_azure_blob(
                                trace_object)
                            if result['success']:
                                logger.info(
                                    f"Successfully downloaded tracking data for {trace_object.object_id}")
                                updated_objects.append(trace_object)
                            else:
                                logger.warning(
                                    f"Failed to download tracking data for {trace_object.object_id}: {result.get('error', 'Unknown error')}")
                        else:
                            logger.warning(
                                f"No tracking URL for object {trace_object.object_id}")
                    except Exception as e:
                        logger.exception(
                            f"Exception downloading tracking data for {trace_object.object_id}: {e}")

                logger.info(
                    f"Successfully downloaded tracking data for {len(updated_objects)}/{len(created_objects)} objects")

            # Step 3: Create TraceHighlight objects linked to players
            highlights_data = result_data.get('highlights', [])
            trace_highlights = []
            highlight_objects_bulk = []

            logger.info(f"Processing {len(highlights_data)} highlights")

            for highlight_data in highlights_data:
                # Try to find the primary player involved in this highlight
                highlight_objects = highlight_data.get('objects', [])
                primary_player = None

                # Get the first player from the highlight objects
                if highlight_objects:
                    first_object_id = highlight_objects[0].get('object_id')
                    primary_player = player_map.get(first_object_id)

                # Create TraceHighlight linked to player
                trace_highlight = TraceHighlight(
                    highlight_id=highlight_data.get('highlight_id'),
                    video_id=highlight_data.get('video_id', 0),
                    start_offset=highlight_data.get('start_offset', 0),
                    duration=highlight_data.get('duration', 0),
                    tags=highlight_data.get('tags', []),
                    video_stream=highlight_data.get('video_stream', ''),
                    event_type='touch',  # Default for TraceVision highlights
                    source='tracevision',
                    session=session,
                    player=primary_player  # Link to TracePlayer instead of user
                )
                trace_highlights.append(trace_highlight)

            # Bulk create highlights
            if trace_highlights:
                created_highlights = TraceHighlight.objects.bulk_create(
                    trace_highlights)
                logger.info(
                    f"Created {len(created_highlights)} trace highlights")

                # Create highlight-object relationships
                for i, highlight_data in enumerate(highlights_data):
                    highlight_objects = highlight_data.get('objects', [])
                    created_highlight = created_highlights[i]

                    for obj_data in highlight_objects:
                        object_id = obj_data.get('object_id')
                        if object_id in player_map:
                            player = player_map[object_id]
                            # Find the corresponding trace object
                            trace_object = TraceObject.objects.filter(
                                session=session,
                                object_id=object_id
                            ).first()

                            if trace_object:
                                highlight_objects_bulk.append(TraceHighlightObject(
                                    highlight=created_highlight,
                                    trace_object=trace_object,
                                    player=player  # Link to TracePlayer
                                ))

                if highlight_objects_bulk:
                    TraceHighlightObject.objects.bulk_create(
                        highlight_objects_bulk)
                    logger.info(
                        f"Created {len(highlight_objects_bulk)} highlight-object relationships")

            logger.info(
                f"Successfully parsed and stored all session data for session {session.session_id}")
            return True

    except Exception as e:
        logger.exception(
            f"Error parsing session data for session {session.session_id}: {e}")
        return False


def create_silent_notification(session):
    """
    Create a silent notification in the database for the user when session processing is completed.
    This replaces FCM push notifications for better Flutter compatibility.

    Args:
        session: TraceSession instance
    """
    try:
        # Initialize notification service
        notification_service = NotificationService()

        if not notification_service.is_available():
            logger.error(
                "Notification service not available, cannot create notification")
            return

        # Prepare session data for notification
        session_data = {
            "session_id": session.session_id,
            "status": session.status,
            "match_date": session.match_date,
            "home_team": session.home_team,
            "away_team": session.away_team,
            "home_score": session.home_score,
            "away_score": session.away_score
        }

        # Create silent notifications for all devices of the user
        notifications = notification_service.create_silent_notification_for_all_devices(
            session.user, session_data
        )

        if notifications:
            logger.info(
                f"Created {len(notifications)} silent notifications for user {session.user.phone_no} for session {session.session_id}")
        else:
            logger.warning(
                f"No devices found or failed to create notifications for user {session.user.phone_no}")

    except Exception as e:
        logger.exception(
            f"Error in create_silent_notification for session {session.session_id}: {e}")


@shared_task
def process_trace_sessions_task(trace_session_id=None):
    """
    Celery task to process all TraceSession objects and update their status from TraceVision API.
    Create database notifications when status changes to "completed".
    """
    try:
        # Query all sessions that are not already processed or in error state
        if not trace_session_id:
            sessions = TraceSession.objects.exclude(
                status__in=["processed", "process_error"])
        else:
            sessions = TraceSession.objects.filter(id=trace_session_id)

        if not sessions.exists():
            logger.info(
                "All sessions are already processed or in final state.")
            return f"No sessions to process"

        logger.info(f"Found {sessions.count()} sessions to process")

        # Initialize service
        tracevision_service = TraceVisionService()
        processed_count = 0
        error_count = 0

        for session in sessions:
            try:
                logger.info(
                    f"Checking session status for ID: {session.id} | {session.session_id}")

                # Query TraceVision API for status update using service
                status_data = tracevision_service.get_session_status(
                    session, force_refresh=True)

                if not status_data:
                    continue

                new_status = status_data["status"]
                previous_status = session.status

                # Update session status
                session.status = new_status
                session.save()

                logger.info(
                    f"Updated session {session.session_id} status from {previous_status} to {new_status}")

                # Handle final status changes (processed or process_error)
                if new_status in ["processed", "process_error"] and previous_status != new_status:
                    status_description = "processed" if new_status == "processed" else "encountered process error"
                    logger.info(
                        f"Session {session.session_id} {status_description}.")

                    # Fetch and save result data for both statuses (may contain error details for process_error)
                    result_data = tracevision_service.get_session_result(
                        session)
                    if result_data:
                        # Upload result data to Azure blob instead of storing in database
                        upload_result = upload_result_data_to_azure_blob(
                            session, result_data)

                        if upload_result['success']:
                            logger.info(
                                f"Result data uploaded successfully for session {session.session_id}")
                        else:
                            logger.error(
                                f"Failed to upload result data for session {session.session_id}: {upload_result.get('error')}")

                        # For processed sessions, parse and store structured data
                        if new_status == "processed":
                            logger.info(
                                f"Parsing structured data for session {session.session_id}")
                            parsing_success = parse_and_store_session_data(
                                session, result_data)

                            if parsing_success:
                                logger.info(
                                    f"Successfully parsed structured data for session {session.session_id}")
                                # Only save session and create notification if parsing was successful
                                session.save()
                                create_silent_notification(session)

                                # Enqueue player-to-user mapping task
                                try:
                                    from tracevision.tasks import map_players_to_users_task
                                    map_players_to_users_task.delay(
                                        session.session_id)
                                    logger.info(
                                        f"Queued player-to-user mapping for session {session.session_id}")
                                except Exception as e:
                                    logger.exception(
                                        f"Failed to enqueue player mapping for session {session.session_id}: {e}")

                                # Enqueue Excel highlights processing FIRST (before other calculations)
                                try:
                                    from tracevision.tasks import process_excel_match_highlights_task
                                    process_excel_match_highlights_task.delay(
                                        session.session_id)
                                    logger.info(
                                        f"Queued Excel highlights processing for session {session.session_id}")
                                except Exception as e:
                                    logger.exception(
                                        f"Failed to enqueue Excel highlights processing for session {session.session_id}: {e}")

                                # Enqueue aggregates computation (idempotent)
                                try:
                                    from tracevision.tasks import compute_aggregates_task
                                    compute_aggregates_task.delay(
                                        session.session_id)
                                    logger.info(
                                        f"Queued aggregates computation for session {session.session_id}")
                                except Exception as e:
                                    logger.exception(
                                        f"Failed to enqueue aggregates for session {session.session_id}: {e}")

                                # Enqueue card metrics calculation (tracking data already downloaded inline)
                                try:
                                    calculate_card_metrics_task.delay(
                                        session.session_id)
                                    logger.info(
                                        f"Queued card metrics calculation for session {session.session_id}")
                                except Exception as e:
                                    logger.exception(
                                        f"Failed to enqueue card metrics calculation for session {session.session_id}: {e}")
                            else:
                                logger.error(
                                    f"Failed to parse structured data for session {session.session_id}. Not updating session status.")
                                # Don't update the session status if parsing failed
                                session.status = previous_status
                                session.save()
                                continue
                        else:
                            # For process_error, just save the result data
                            session.save()
                            create_silent_notification(session)

                        logger.info(
                            f"Saved result data for {new_status} session {session.session_id}")
                    else:
                        logger.error(
                            f"Failed to fetch result for {new_status} session {session.session_id}")

                        # Don't update status if we couldn't fetch result data
                        session.status = previous_status
                        session.save()
                        continue

                processed_count += 1

            except Exception as e:
                error_count += 1
                logger.exception(
                    f"Error processing session {session.session_id}: {e}")

        return f"Processed {processed_count} sessions, {error_count} errors"

    except Exception as e:
        logger.exception(f"Error in process_trace_sessions_task: {e}")
        raise


@shared_task
def calculate_player_stats_task(session_id):
    """
    Celery task to calculate comprehensive player performance statistics from TraceVision data.
    This task runs after session processing is completed and generates all performance metrics.

    Args:
        session_id (str): Session ID to calculate stats for

    Returns:
        dict: Task results with success status and details
    """
    try:
        from tracevision.services import TraceVisionStatsService

        # Get the session
        try:
            session = TraceSession.objects.get(session_id=session_id)
        except TraceSession.DoesNotExist:
            error_msg = f"Session with ID {session_id} not found"
            logger.error(error_msg)
            return {"success": False, "error": error_msg}

        logger.info(
            f"Starting player stats calculation for session: {session_id}")

        # Check if session is processed
        if session.status != "processed":
            error_msg = f"Session {session_id} is not processed yet. Current status: {session.status}"
            logger.warning(error_msg)
            return {"success": False, "error": error_msg}

        # Check if session has trace players
        if not session.trace_players.exists():
            error_msg = f"Session {session_id} has no trace players. Run data parsing first."
            logger.warning(error_msg)
            return {"success": False, "error": error_msg}

        # Initialize stats service
        stats_service = TraceVisionStatsService()

        # Calculate all statistics
        result = stats_service.calculate_session_stats(session)

        if result['success']:
            logger.info(f"Successfully calculated stats for session {session_id}: "
                        f"{result['player_stats_count']} players processed")

            # Create success notification
            create_silent_notification(session)

            return {
                "success": True,
                "session_id": session_id,
                "player_stats_count": result['player_stats_count'],
                "team_stats": result['team_stats'],
                "session_stats": result['session_stats'],
                "message": f"Stats calculation completed for {result['player_stats_count']} players"
            }
        else:
            error_msg = f"Stats calculation failed for session {session_id}: {result.get('error', 'Unknown error')}"
            logger.error(error_msg)
            return {"success": False, "error": error_msg}

    except Exception as e:
        error_msg = f"Error in calculate_player_stats_task for session {session_id}: {str(e)}"
        logger.exception(error_msg)
        return {"success": False, "error": error_msg}


@shared_task
def compute_aggregates_task(session_id):
    """Compute CSV-equivalent aggregates in background and store them in DB."""
    try:
        from tracevision.services import TraceVisionAggregationService
        # Get the session
        try:
            session = TraceSession.objects.get(session_id=session_id)
        except TraceSession.DoesNotExist:
            error_msg = f"Session with ID {session_id} not found"
            logger.error(error_msg)
            return {"success": False, "error": error_msg}

        if session.status != 'processed':
            msg = f"Session {session_id} not processed yet"
            logger.warning(msg)
            return {"success": False, "error": msg}

        agg = TraceVisionAggregationService()
        result = agg.compute_all(session)
        logger.info(f"Computed aggregates for session {session_id}")

        # Trigger overlay highlights generation for clip reels
        try:
            from tracevision.tasks import generate_overlay_highlights_task
            generate_overlay_highlights_task.delay(session_id)
            logger.info(
                f"Queued overlay highlights generation for session {session_id}")
        except Exception as e:
            logger.exception(
                f"Failed to enqueue overlay highlights generation for session {session_id}: {e}")

        return {"success": True, "details": {k: True for k in result.keys()}}
    except Exception as e:
        logger.exception(
            f"Error computing aggregates for session {session_id}: {e}")
        return {"success": False, "error": str(e)}


@shared_task
def reconcile_aggregates_for_processed_sessions(lookback_hours=24, batch_limit=50):
    """Scan recently processed sessions and ensure aggregates exist; enqueue if missing."""
    try:
        from django.utils import timezone
        from datetime import timedelta
        from tracevision.models import TraceCoachReportTeam

        cutoff = timezone.now() - timedelta(hours=lookback_hours)
        qs = TraceSession.objects.filter(
            status='processed', updated_at__gte=cutoff).order_by('-updated_at')[:batch_limit]
        enqueued = 0
        for session in qs:
            # If no coach report rows exist, assume aggregates missing and enqueue
            if not TraceCoachReportTeam.objects.filter(session=session).exists():
                compute_aggregates_task.delay(session.session_id)
                enqueued += 1
        return {"success": True, "checked": qs.count(), "enqueued": enqueued}
    except Exception as e:
        logger.exception(f"Error reconciling aggregates: {e}")
        return {"success": False, "error": str(e)}


@shared_task
def calculate_card_metrics_task(session_id, user_mapping=None):
    """
    Calculate card metrics (GPS Athletic/Football, Attacking, Defensive, RPE) 
    from TraceVision session data and update card models.

    Args:
        session_id (str): TraceSession ID to process
        user_mapping (dict, optional): Mapping of object_id to WajoUser ID
            Format: {"home_1": user_id, "away_2": user_id, ...}

    Returns:
        dict: Task results with success status and details
    """
    try:
        from tracevision.metrics_calculator import TraceVisionMetricsCalculator
        from tracevision.models import TraceSession
        from accounts.models import WajoUser
        from cards.models import AttackingSkills, VideoCardDefensive, GPSAthleticSkills, GPSFootballAbilities
        from games.models import Game
        from django.utils import timezone

        # Get the session
        try:
            session = TraceSession.objects.get(session_id=session_id)
        except TraceSession.DoesNotExist:
            error_msg = f"Session with ID {session_id} not found"
            logger.error(error_msg)
            return {"success": False, "error": error_msg}

        logger.info(
            f"Starting card metrics calculation for session {session_id}")

        # Check if session is processed
        if session.status != "processed":
            error_msg = f"Session {session_id} is not processed yet. Current status: {session.status}"
            logger.warning(error_msg)
            return {"success": False, "error": error_msg}

        # Initialize metrics calculator
        calculator = TraceVisionMetricsCalculator()

        # Calculate metrics for all players in session
        metrics_result = calculator.calculate_metrics_for_session(session)

        if not metrics_result['success']:
            logger.error(
                f"Failed to calculate metrics for session {session_id}")
            return {"success": False, "error": "Metrics calculation failed", "details": metrics_result}

        # Save metrics to card models - only for mapped users
        saved_metrics = []
        errors = []
        skipped_unmapped = []

        for player_metrics in metrics_result['metrics_calculated']:
            try:
                object_id = player_metrics['object_id']
                side = player_metrics['side']
                metrics = player_metrics['metrics']

                # Find the trace player to check if they're mapped to a user
                try:
                    trace_player = session.trace_players.get(
                        object_id=object_id)
                    user = trace_player.user

                    # Skip if player is not mapped to a user
                    if not user:
                        skipped_unmapped.append({
                            'object_id': object_id,
                            'player_name': trace_player.name,
                            'jersey_number': trace_player.jersey_number,
                            'reason': 'Player not mapped to user'
                        })
                        logger.info(
                            f"Skipping metrics calculation for unmapped player {object_id} ({trace_player.name})")
                        continue

                except TracePlayer.DoesNotExist:
                    # If trace player doesn't exist, skip this player
                    logger.warning(
                        f"TracePlayer not found for object_id {object_id}, skipping")
                    skipped_unmapped.append({
                        'object_id': object_id,
                        'reason': 'TracePlayer not found'
                    })
                    continue

                game_id = f"TV_{session.session_id}"
                game, _ = Game.objects.get_or_create(
                    id=game_id,
                    defaults={
                        'type': 'match',
                        'name': f"TraceVision Session {session.session_id}",
                        'date': session.match_date,
                    }
                )

                # Save Attacking Skills metrics
                if 'attacking_skills' in metrics:
                    AttackingSkills.objects.update_or_create(
                        user=user,
                        game=game,
                        defaults={
                            'metrics': metrics['attacking_skills'],
                            'updated_on': timezone.now()
                        }
                    )
                    saved_metrics.append(
                        f"AttackingSkills for {object_id} ({trace_player.name})")

                # Save Defensive Skills metrics
                if 'defensive_skills' in metrics:
                    VideoCardDefensive.objects.update_or_create(
                        user=user,
                        game=game,
                        defaults={
                            'metrics': metrics['defensive_skills'],
                            'updated_on': timezone.now()
                        }
                    )
                    saved_metrics.append(
                        f"VideoCardDefensive for {object_id} ({trace_player.name})")

                # Save GPS Athletic Skills metrics
                if 'gps_athletic_skills' in metrics:
                    GPSAthleticSkills.objects.update_or_create(
                        user=user,
                        game=game,
                        defaults={
                            'metrics': metrics['gps_athletic_skills'],
                            'updated_on': timezone.now()
                        }
                    )
                    saved_metrics.append(
                        f"GPSAthleticSkills for {object_id} ({trace_player.name})")

                # Save GPS Football Abilities metrics
                if 'gps_football_abilities' in metrics:
                    GPSFootballAbilities.objects.update_or_create(
                        user=user,
                        game=game,
                        defaults={
                            'metrics': metrics['gps_football_abilities'],
                            'updated_on': timezone.now()
                        }
                    )
                    saved_metrics.append(
                        f"GPSFootballAbilities for {object_id} ({trace_player.name})")

                logger.info(
                    f"Saved metrics for player {object_id} ({trace_player.name}) -> user: {user.phone_no}")

            except Exception as e:
                error_msg = f"Error saving metrics for {object_id}: {str(e)}"
                logger.exception(error_msg)
                errors.append(error_msg)

        # Create success notification if any metrics were saved
        if saved_metrics:
            try:
                create_silent_notification(session)
            except Exception as e:
                logger.exception(
                    f"Error creating notification for session {session_id}: {e}")

        result = {
            "success": True,
            "session_id": session_id,
            "total_players": len(metrics_result['metrics_calculated']),
            "mapped_players_processed": len(saved_metrics),
            "unmapped_players_skipped": len(skipped_unmapped),
            "metrics_saved": saved_metrics,
            "skipped_unmapped": skipped_unmapped,
            "errors": errors,
            "calculation_details": metrics_result
        }

        logger.info(f"Card metrics calculation completed for session {session_id}. "
                    f"Total players: {len(metrics_result['metrics_calculated'])}, "
                    f"Mapped players processed: {len(saved_metrics)}, "
                    f"Unmapped players skipped: {len(skipped_unmapped)}, "
                    f"Errors: {len(errors)}")

        return result

    except Exception as e:
        error_msg = f"Error in calculate_card_metrics_task for session {session_id}: {str(e)}"
        logger.exception(error_msg)
        return {"success": False, "error": error_msg}


@shared_task
def bulk_calculate_card_metrics_task(session_ids=None, lookback_days=7):
    """
    Bulk calculate card metrics for multiple sessions.
    Useful for backfilling metrics or processing multiple sessions at once.

    Args:
        session_ids (list, optional): Specific session IDs to process
        lookback_days (int): Days to look back for unprocessed sessions

    Returns:
        dict: Bulk processing results
    """
    try:
        from django.utils import timezone
        from datetime import timedelta
        from tracevision.models import TraceSession

        if session_ids:
            # Process specific sessions
            sessions = TraceSession.objects.filter(
                session_id__in=session_ids, status='processed')
            logger.info(
                f"Bulk processing {len(session_ids)} specific sessions")
        else:
            # Find recent processed sessions
            cutoff = timezone.now() - timedelta(days=lookback_days)
            sessions = TraceSession.objects.filter(
                status='processed',
                updated_at__gte=cutoff
            ).order_by('-updated_at')
            logger.info(
                f"Bulk processing sessions from last {lookback_days} days")

        if not sessions.exists():
            return {"success": True, "message": "No sessions found to process"}

        # Process each session
        results = []
        total_processed = 0
        total_errors = 0

        for session in sessions:
            try:
                # Enqueue individual task
                result = calculate_card_metrics_task.delay(session.session_id)
                results.append({
                    'session_id': session.session_id,
                    'task_id': result.id,
                    'status': 'enqueued'
                })
                total_processed += 1

            except Exception as e:
                logger.exception(
                    f"Error enqueuing metrics calculation for session {session.session_id}: {e}")
                results.append({
                    'session_id': session.session_id,
                    'status': 'error',
                    'error': str(e)
                })
                total_errors += 1

        return {
            "success": True,
            "total_sessions": sessions.count(),
            "processed": total_processed,
            "errors": total_errors,
            "results": results
        }

    except Exception as e:
        error_msg = f"Error in bulk_calculate_card_metrics_task: {str(e)}"
        logger.exception(error_msg)
        return {"success": False, "error": error_msg}


@shared_task
def map_players_to_users_task(session_id):
    """
    Map TracePlayer objects to WajoUser objects based on jersey numbers, names, etc.
    This task runs after session processing to link players to actual users.

    Args:
        session_id (str): Session ID to process

    Returns:
        dict: Task results with success status and mapping details
    """
    try:
        from accounts.models import WajoUser
        from teams.models import Team

        # Get the session
        try:
            session = TraceSession.objects.get(session_id=session_id)
        except TraceSession.DoesNotExist:
            error_msg = f"Session with ID {session_id} not found"
            logger.error(error_msg)
            return {"success": False, "error": error_msg}

        logger.info(
            f"Starting player-to-user mapping for session: {session_id}")

        # Get all unmapped players in this session
        unmapped_players = session.trace_players.filter(user__isnull=True)

        if not unmapped_players.exists():
            logger.info(f"No unmapped players found for session {session_id}")
            return {"success": True, "message": "No unmapped players found", "mapped_count": 0}

        logger.info(
            f"Found {unmapped_players.count()} unmapped players to process")

        mapped_count = 0
        mapping_details = []

        for player in unmapped_players:
            try:
                # Log player details for debugging
                team_name = player.team.name if hasattr(
                    player.team, 'name') else str(player.team)
                logger.info(
                    f"Attempting to map player: {player.object_id} (jersey: {player.jersey_number}, team: {team_name})")

                # Strategy 1: Try to match by jersey number and team
                if player.jersey_number and player.team:
                    matching_user = WajoUser.objects.filter(
                        jersey_number=player.jersey_number,
                        team=player.team
                    ).first()

                    if matching_user:
                        player.user = matching_user
                        player.save()
                        mapped_count += 1
                        mapping_details.append({
                            'player_id': player.object_id,
                            'player_name': player.name,
                            'jersey_number': player.jersey_number,
                            'mapped_to_user': matching_user.phone_no,
                            'method': 'jersey_number_and_team'
                        })
                        logger.info(
                            f"Mapped player {player.name} ({player.jersey_number}) to user {matching_user.phone_no}")
                        continue

                # Strategy 2: Try to match by name and team (fuzzy matching)
                if player.name and player.team:
                    # Simple name matching - you can enhance this with fuzzy matching
                    matching_user = WajoUser.objects.filter(
                        name__icontains=player.name.split()[0],  # First name
                        team=player.team
                    ).first()

                    if matching_user:
                        player.user = matching_user
                        player.save()
                        mapped_count += 1
                        mapping_details.append({
                            'player_id': player.object_id,
                            'player_name': player.name,
                            'jersey_number': player.jersey_number,
                            'mapped_to_user': matching_user.phone_no,
                            'method': 'name_and_team'
                        })
                        logger.info(
                            f"Mapped player {player.name} to user {matching_user.phone_no} by name")
                        continue

                # Strategy 3: If session has only one user, map all unmapped players to that user
                if session.user and not player.user:
                    # Check if this is a single-player session
                    total_players = session.trace_players.count()
                    if total_players == 1:
                        player.user = session.user
                        player.save()
                        mapped_count += 1
                        mapping_details.append({
                            'player_id': player.object_id,
                            'player_name': player.name,
                            'jersey_number': player.jersey_number,
                            'mapped_to_user': session.user.phone_no,
                            'method': 'single_player_session'
                        })
                        logger.info(
                            f"Mapped single player {player.name} to session user {session.user.phone_no}")

            except Exception as e:
                logger.exception(
                    f"Error mapping player {player.object_id}: {e}")

        logger.info(
            f"Successfully mapped {mapped_count}/{unmapped_players.count()} players to users")

        # Trigger card metrics calculation for newly mapped players
        if mapped_count > 0:
            try:
                calculate_card_metrics_task.delay(session_id)
                logger.info(
                    f"Queued card metrics calculation for session {session_id} after mapping {mapped_count} players")
            except Exception as e:
                logger.exception(
                    f"Failed to enqueue card metrics calculation for session {session_id}: {e}")

        return {
            "success": True,
            "session_id": session_id,
            "total_players": unmapped_players.count(),
            "mapped_count": mapped_count,
            "unmapped_count": unmapped_players.count() - mapped_count,
            "mapping_details": mapping_details,
            "message": f"Mapped {mapped_count} players to users"
        }

    except Exception as e:
        error_msg = f"Error in map_players_to_users_task for session {session_id}: {str(e)}"
        logger.exception(error_msg)
        return {"success": False, "error": error_msg}


@shared_task
def calculate_metrics_for_unmapped_players_task(session_id=None, lookback_days=7):
    """
    Calculate card metrics for players that were previously unmapped but are now mapped.
    This task can be run periodically or triggered when new player mappings are created.

    Args:
        session_id (str, optional): Specific session ID to process
        lookback_days (int): Days to look back for sessions with unmapped players

    Returns:
        dict: Task results with success status and details
    """
    try:
        from django.utils import timezone
        from datetime import timedelta
        from tracevision.models import TraceSession, TracePlayer

        if session_id:
            # Process specific session
            sessions = TraceSession.objects.filter(
                session_id=session_id, status='processed')
            logger.info(
                f"Processing specific session {session_id} for unmapped player metrics")
        else:
            # Find recent sessions with unmapped players
            cutoff = timezone.now() - timedelta(days=lookback_days)
            sessions = TraceSession.objects.filter(
                status='processed',
                updated_at__gte=cutoff
            ).order_by('-updated_at')
            logger.info(
                f"Processing sessions from last {lookback_days} days for unmapped player metrics")

        if not sessions.exists():
            return {"success": True, "message": "No sessions found to process"}

        total_processed = 0
        total_errors = 0
        results = []

        for session in sessions:
            try:
                # Find players that are now mapped but might not have metrics calculated
                newly_mapped_players = session.trace_players.filter(
                    user__isnull=False,
                    # You could add additional criteria here to identify players that need metrics
                )

                if newly_mapped_players.exists():
                    # Trigger card metrics calculation for this session
                    result = calculate_card_metrics_task.delay(
                        session.session_id)
                    results.append({
                        'session_id': session.session_id,
                        'mapped_players_count': newly_mapped_players.count(),
                        'task_id': result.id,
                        'status': 'enqueued'
                    })
                    total_processed += 1
                    logger.info(
                        f"Queued metrics calculation for session {session.session_id} with {newly_mapped_players.count()} mapped players")

            except Exception as e:
                logger.exception(
                    f"Error processing session {session.session_id}: {e}")
                results.append({
                    'session_id': session.session_id,
                    'status': 'error',
                    'error': str(e)
                })
                total_errors += 1

        return {
            "success": True,
            "total_sessions": sessions.count(),
            "processed": total_processed,
            "errors": total_errors,
            "results": results
        }

    except Exception as e:
        error_msg = f"Error in calculate_metrics_for_unmapped_players_task: {str(e)}"
        logger.exception(error_msg)
        return {"success": False, "error": error_msg}


@shared_task
def generate_overlay_highlights_task(session_id=None, clip_reel_ids=None, batch_size=5):
    """
    Generate overlay highlight videos for TraceClipReel objects with video_type='with_overlay' and status='pending'.

    Args:
        session_id (str, optional): Process specific session
        clip_reel_ids (list, optional): Process specific clip reels
        batch_size (int): Number of clips to process in parallel (default: 5)

    Returns:
        dict: Task results with success status and details
    """
    try:
        from .video_generator import TrackingDataCache, create_clip_reel_overlay_video, upload_video_to_storage
        from .models import TraceClipReel

        # Query target clip reels
        clip_reels = TraceClipReel.objects.filter(
            video_type='with_overlay',
            generation_status__in=['pending', 'failed'],
            primary_player__user__isnull=False,
        ).select_related('session', 'highlight').prefetch_related('involved_players')

        if session_id:
            clip_reels = clip_reels.filter(session__session_id=session_id)
        if clip_reel_ids:
            clip_reels = clip_reels.filter(id__in=clip_reel_ids)

        if not clip_reels.exists():
            logger.info("No clip reels to process")
            return {"success": True, "message": "No clip reels to process"}

        logger.info(f"Found {clip_reels.count()} clip reels to process")

        # Initialize tracking data cache
        tracking_cache = TrackingDataCache()

        processed_count = 0
        failed_count = 0
        results = []

        for clip_reel in clip_reels:
            try:
                logger.info(
                    f"Processing clip reel {clip_reel.id} for highlight {clip_reel.highlight.highlight_id}")

                # Mark as generating
                clip_reel.mark_generation_started()

                # Generate overlay video
                temp_video_path = create_clip_reel_overlay_video(
                    clip_reel, tracking_cache
                )

                # Upload to storage
                video_blob_url = upload_video_to_storage(
                    temp_video_path, clip_reel
                )

                # Calculate video file size
                video_size_mb = os.path.getsize(
                    temp_video_path) / (1024 * 1024)

                # Mark as completed
                clip_reel.mark_generation_completed(
                    video_url=video_blob_url,
                    video_size_mb=video_size_mb,
                    video_duration_seconds=clip_reel.duration_ms / 1000.0
                )

                # Clean up temporary file
                os.unlink(temp_video_path)

                processed_count += 1
                results.append({
                    'clip_reel_id': str(clip_reel.id),
                    'highlight_id': clip_reel.highlight.highlight_id,
                    'video_type': clip_reel.video_type,
                    'status': 'completed',
                    'video_url': video_blob_url,
                    'video_size_mb': video_size_mb
                })

                logger.info(f"Successfully processed clip reel {clip_reel.id}")

            except Exception as e:
                logger.exception(
                    f"Error processing clip reel {clip_reel.id}: {e}")
                clip_reel.mark_generation_failed(str(e))
                failed_count += 1
                results.append({
                    'clip_reel_id': str(clip_reel.id),
                    'highlight_id': clip_reel.highlight.highlight_id,
                    'video_type': clip_reel.video_type,
                    'status': 'failed',
                    'error': str(e)
                })

        # Clear tracking cache
        tracking_cache.clear_cache()

        logger.info(
            f"Overlay highlights generation completed. Processed: {processed_count}, Failed: {failed_count}")

        return {
            "success": True,
            "processed": processed_count,
            "failed": failed_count,
            "total": processed_count + failed_count,
            "results": results
        }

    except Exception as e:
        logger.exception(f"Error in generate_overlay_highlights_task: {e}")
        return {"success": False, "error": str(e)}


def determine_team_side(excel_team_name, session):
    """
    Determine if an Excel team name belongs to home or away team based on TraceSession
    
    Args:
        excel_team_name (str): Team name from Excel data
        session (TraceSession): The session with home_team and away_team
        
    Returns:
        str: 'home' or 'away'
    """
    try:
        # Get team names from session
        home_team_name = session.home_team.name if session.home_team else None
        away_team_name = session.away_team.name if session.away_team else None
        
        if not excel_team_name or not isinstance(excel_team_name, str):
            logger.warning(f"Invalid team name: '{excel_team_name}'. Defaulting to 'away'.")
            return 'away'
        
        excel_team_clean = excel_team_name.strip().lower()
        
        # Try exact match first
        if home_team_name and excel_team_clean == home_team_name.lower():
            return 'home'
        elif away_team_name and excel_team_clean == away_team_name.lower():
            return 'away'
        
        # Try partial match (in case of slight differences)
        if home_team_name and home_team_name.lower() in excel_team_clean:
            return 'home'
        elif away_team_name and away_team_name.lower() in excel_team_clean:
            return 'away'
        
        # Try reverse partial match
        if home_team_name and excel_team_clean in home_team_name.lower():
            return 'home'
        elif away_team_name and excel_team_clean in away_team_name.lower():
            return 'away'
        
        # If no match found, log warning and default to 'away'
        logger.warning(f"Could not determine team side for '{excel_team_name}'. "
                      f"Session teams: home='{home_team_name}', away='{away_team_name}'. "
                      f"Defaulting to 'away'.")
        return 'away'
        
    except Exception as e:
        logger.error(f"Error determining team side for '{excel_team_name}': {e}")
        return 'away'


def parse_excel_match_data(excel_file_path, session):
    """
    Parse Excel file containing match data and extract events (goals, cards, etc.)
    
    Args:
        excel_file_path (str): Path to the Excel file
        session (TraceSession): The session to determine team sides
        
    Returns:
        dict: Parsed match data with events
    """
    try:
        # Read all sheets from Excel file
        excel_data = pd.read_excel(excel_file_path, sheet_name=None)
        
        match_data = {
            'match_summary': {},
            'starting_lineups': [],
            'replacements': [],
            'bench': [],
            'coaches': [],
            'referees': [],
            'events': [],
            'player_mappings': {}  # New field for player name mappings
        }
        
        # Parse Match Summary sheet
        if 'Match Summary' in excel_data:
            summary_df = excel_data['Match Summary']
            if not summary_df.empty:
                match_data['match_summary'] = summary_df.iloc[0].to_dict()
        
        # Parse Starting Lineups sheet
        if 'Starting Lineups' in excel_data:
            lineups_df = excel_data['Starting Lineups']
            # Replace NaN values with None (which becomes null in JSON)
            lineups_df = lineups_df.fillna('')
            match_data['starting_lineups'] = lineups_df.to_dict('records')
        
        # Parse Replacements sheet
        if 'Replacements' in excel_data:
            replacements_df = excel_data['Replacements']
            # Replace NaN values with empty strings
            replacements_df = replacements_df.fillna('')
            match_data['replacements'] = replacements_df.to_dict('records')
        
        # Parse Bench sheet
        if 'Bench' in excel_data:
            bench_df = excel_data['Bench']
            # Replace NaN values with empty strings
            bench_df = bench_df.fillna('')
            match_data['bench'] = bench_df.to_dict('records')
        
        # Parse Coaches sheet
        if 'Coaches' in excel_data:
            coaches_df = excel_data['Coaches']
            # Replace NaN values with empty strings
            coaches_df = coaches_df.fillna('')
            match_data['coaches'] = coaches_df.to_dict('records')
        
        # Parse Referees sheet
        if 'Referees' in excel_data:
            referees_df = excel_data['Referees']
            # Replace NaN values with empty strings
            referees_df = referees_df.fillna('')
            match_data['referees'] = referees_df.to_dict('records')
        
        # Create player mappings from all player data
        player_mappings = {}
        
        # Map starting lineups
        for player in match_data['starting_lineups']:
            # Skip invalid entries (empty values, headers, etc.)
            if (not player.get('Team') or 
                not player.get('Number') or 
                not player.get('Name') or
                player.get('Name').strip() in ['', 'GOALS TABLE', 'CARD TABLE', 'name', 'card colour'] or
                player.get('Team').strip() in ['', 'no.']):
                continue
                
            # Determine team side by comparing with session teams
            team_side = determine_team_side(player['Team'], session)
            jersey_number = int(player['Number'])
            player_name = player['Name'].strip()
            
            # Skip if player name is empty or invalid
            if not player_name or len(player_name) < 2:
                continue
            
            # Create mapping key
            mapping_key = f"{team_side}_{jersey_number}"
            player_mappings[mapping_key] = {
                'name': player_name,
                'jersey_number': jersey_number,
                'team_side': team_side,
                'team_name': player['Team'],
                'role': player.get('Role', '') or '',
                'source': 'starting_lineup'
            }
        
        # Map replacements
        for player in match_data['replacements']:
            # Skip invalid entries (empty values, headers, etc.)
            if (not player.get('Team') or 
                not player.get('Number') or 
                not player.get('Name') or
                player.get('Name').strip() in ['', 'GOALS TABLE', 'CARD TABLE', 'name', 'card colour'] or
                player.get('Team').strip() in ['', 'no.']):
                continue
                
            team_side = determine_team_side(player['Team'], session)
            jersey_number = int(player['Number'])
            player_name = player['Name'].strip()
            
            # Skip if player name is empty or invalid
            if not player_name or len(player_name) < 2:
                continue
            
            # Create mapping key
            mapping_key = f"{team_side}_{jersey_number}"
            if mapping_key not in player_mappings:  # Only add if not already in starting lineup
                player_mappings[mapping_key] = {
                    'name': player_name,
                    'jersey_number': jersey_number,
                    'team_side': team_side,
                    'team_name': player['Team'],
                    'role': player.get('Role', '') or '',
                    'source': 'replacement'
                }
        
        # Map bench players
        for player in match_data['bench']:
            # Skip invalid entries (empty values, headers, etc.)
            if (not player.get('Team') or 
                not player.get('Number') or 
                not player.get('Name') or
                player.get('Name').strip() in ['', 'GOALS TABLE', 'CARD TABLE', 'name', 'card colour'] or
                player.get('Team').strip() in ['', 'no.']):
                continue
                
            team_side = determine_team_side(player['Team'], session)
            jersey_number = int(player['Number'])
            player_name = player['Name'].strip()
            
            # Skip if player name is empty or invalid
            if not player_name or len(player_name) < 2:
                continue
            
            # Create mapping key
            mapping_key = f"{team_side}_{jersey_number}"
            if mapping_key not in player_mappings:  # Only add if not already mapped
                player_mappings[mapping_key] = {
                    'name': player_name,
                    'jersey_number': jersey_number,
                    'team_side': team_side,
                    'team_name': player['Team'],
                    'role': '',
                    'source': 'bench'
                }
        
        match_data['player_mappings'] = player_mappings
        
        # Extract events from match data
        events = []
        
        # TODO: Process the 'Starting Lineups' sheet to generates the Events for goals, cards and replacements
        # +++++++++++++++++++++++++++++++++++++Events processing code blocks++++++++++++++++++++++++++++++++++++
        # Extract goals from match summary
        # if 'Home Goals' in match_data['match_summary']:
        #     home_goals = match_data['match_summary'].get('Home Goals', '')
        #     if pd.notna(home_goals) and home_goals:
        #         goals = parse_goals_from_text(str(home_goals), 'home')
        #         events.extend(goals)
        
        # if 'Away Goals' in match_data['match_summary']:
        #     away_goals = match_data['match_summary'].get('Away Goals', '')
        #     if pd.notna(away_goals) and away_goals:
        #         goals = parse_goals_from_text(str(away_goals), 'away')
        #         events.extend(goals)
        
        # Extract cards from starting lineups
        # for player in match_data['starting_lineups']:
        #     # Skip invalid entries
        #     if (not player.get('Team') or 
        #         not player.get('Number') or 
        #         not player.get('Name') or
        #         player.get('Name').strip() in ['', 'GOALS TABLE', 'CARD TABLE', 'name', 'card colour'] or
        #         player.get('Team').strip() in ['', 'no.']):
        #         continue
                
        #     if 'Cards' in player and player['Cards'] and player['Cards'].strip():
        #         cards = parse_cards_from_text(str(player['Cards']), player, 'starting', session)
        #         events.extend(cards)
        # +++++++++++++++++++++++++++++++++++++Events processing code blocks end++++++++++++++++++++++++++++++++++++
        
        match_data['events'] = events
        
        logger.info(f"Parsed {len(events)} events and {len(player_mappings)} player mappings from Excel file")
        return match_data
        
    except Exception as e:
        logger.error(f"Error parsing Excel file {excel_file_path}: {e}")
        raise


def parse_goals_from_text(goals_text, team_side):
    """
    Parse goals from text like "LEVI Omri 16', 77'" or "MENACHEM Ofek 56', 85'"
    
    Args:
        goals_text (str): Text containing goal information
        team_side (str): 'home' or 'away'
        
    Returns:
        list: List of goal events
    """
    events = []
    
    # Pattern to match player name and minutes: "NAME 16', 77'"
    pattern = r'([A-Z\s]+?)\s+(\d+)(?:\'|min)'
    matches = re.findall(pattern, goals_text)
    
    for match in matches:
        player_name = match[0].strip()
        minute = int(match[1])
        match_time = parse_match_time(minute)
        
        events.append({
            'type': 'goal',
            'player_name': player_name,
            'minute': minute,
            'match_time': match_time,
            'team_side': team_side,
            'event_metadata': {
                'scorer': player_name,
                'minute': minute,
                'match_time': match_time,
                'team_side': team_side
            }
        })
    
    return events


def parse_cards_from_text(cards_text, player_data, player_type, session):
    """
    Parse cards from text like "Yellow 41'" or "Red 27'"
    
    Args:
        cards_text (str): Text containing card information
        player_data (dict): Player information from lineup
        player_type (str): 'starting' or 'replacement'
        session (TraceSession): The session to determine team sides
        
    Returns:
        list: List of card events
    """
    events = []
    
    # Pattern to match card type and minute: "Yellow 41'" or "Red 27'"
    pattern = r'(Yellow|Red)\s+(\d+)(?:\'|min)'
    matches = re.findall(pattern, cards_text)
    
    for match in matches:
        card_type = match[0].lower()
        minute = int(match[1])
        match_time = parse_match_time(minute)
        
        # Determine team side using session teams
        team_side = determine_team_side(player_data.get('Team', ''), session)
        
        events.append({
            'type': f'{card_type}_card',
            'player_name': player_data.get('Name', 'Unknown'),
            'jersey_number': player_data.get('Number', 0),
            'minute': minute,
            'match_time': match_time,
            'team_side': team_side,
            'event_metadata': {
                'player': player_data.get('Name', 'Unknown'),
                'jersey_number': player_data.get('Number', 0),
                'card_type': card_type,
                'minute': minute,
                'match_time': match_time,
                'team_side': team_side,
                'player_type': player_type
            }
        })
    
    return events


def update_trace_player_names(session, player_mappings):
    """
    Update TracePlayer names from Excel data mappings
    
    Args:
        session (TraceSession): The session to update
        player_mappings (dict): Player mappings from Excel data
        
    Returns:
        dict: Update results with counts and details
    """
    try:
        updated_count = 0
        not_found_count = 0
        update_details = []
        
        for mapping_key, player_data in player_mappings.items():
            try:
                # Find TracePlayer by object_id pattern
                trace_player = TracePlayer.objects.filter(
                    session=session,
                    object_id=mapping_key
                ).first()
                
                if trace_player:
                    # Update player name and other details
                    old_name = trace_player.name
                    trace_player.name = player_data['name']
                    trace_player.position = player_data.get('role', trace_player.position)
                    trace_player.save()
                    
                    updated_count += 1
                    update_details.append({
                        'object_id': mapping_key,
                        'old_name': old_name,
                        'new_name': player_data['name'],
                        'jersey_number': player_data['jersey_number'],
                        'team_side': player_data['team_side'],
                        'source': player_data['source']
                    })
                    
                    logger.info(f"Updated player {mapping_key}: '{old_name}' -> '{player_data['name']}'")
                else:
                    not_found_count += 1
                    logger.warning(f"TracePlayer not found for mapping key: {mapping_key}")
                    
            except Exception as e:
                logger.error(f"Error updating player {mapping_key}: {e}")
                continue
        
        return {
            'updated_count': updated_count,
            'not_found_count': not_found_count,
            'total_mappings': len(player_mappings),
            'update_details': update_details
        }
        
    except Exception as e:
        logger.error(f"Error in update_trace_player_names: {e}")
        return {
            'updated_count': 0,
            'not_found_count': 0,
            'total_mappings': len(player_mappings),
            'update_details': [],
            'error': str(e)
        }


def map_player_to_trace_player(player_name, jersey_number, team_side, session):
    """
    Map Excel player data to TracePlayer objects based on name, jersey number, and team
    
    Args:
        player_name (str): Player name from Excel
        jersey_number (int): Jersey number from Excel
        team_side (str): 'home' or 'away'
        session (TraceSession): The session to search in
        
    Returns:
        TracePlayer or None: Matching TracePlayer object
    """
    try:
        # Get the team based on side
        team = session.home_team if team_side == 'home' else session.away_team
        
        # Try to find by jersey number and team first
        trace_player = TracePlayer.objects.filter(
            session=session,
            jersey_number=jersey_number,
            team=team
        ).first()
        
        if trace_player:
            return trace_player
        
        # Try to find by name similarity and team
        trace_player = TracePlayer.objects.filter(
            session=session,
            team=team,
            name__icontains=player_name.split()[0]  # First name match
        ).first()
        
        if trace_player:
            return trace_player
        
        # Try to find by object_id pattern (home_X or away_X)
        object_id_pattern = f"{team_side}_{jersey_number}"
        trace_object = TraceObject.objects.filter(
            session=session,
            object_id=object_id_pattern
        ).first()
        
        if trace_object and trace_object.player:
            return trace_object.player
        
        logger.warning(f"Could not map player {player_name} (#{jersey_number}) from {team_side} team")
        return None
        
    except Exception as e:
        logger.error(f"Error mapping player {player_name}: {e}")
        return None


def parse_match_time(time_input):
    """
    Parse various time formats and return MM:SS format
    
    Args:
        time_input: Can be int (minutes), str "MM:SS", or str "MM'"
        
    Returns:
        str: Time in MM:SS format
    """
    if isinstance(time_input, int):
        # Just minutes, default to :00 seconds
        return f"{time_input:02d}:00"
    elif isinstance(time_input, str):
        if ':' in time_input:
            # Already in MM:SS format
            return time_input
        elif "'" in time_input:
            # Format like "16'" or "77'"
            minute = int(time_input.replace("'", ""))
            return f"{minute:02d}:00"
        else:
            # Assume it's just minutes
            minute = int(time_input)
            return f"{minute:02d}:00"
    return "00:00"


def convert_match_time_to_milliseconds(match_time, half=None):
    """
    Convert match time (MM:SS format) to video milliseconds
    
    Args:
        match_time (str): Match time in MM:SS format (e.g., "16:30", "77:15")
        half (int, optional): Match half (1 or 2)
        
    Returns:
        int: Milliseconds from video start
    """
    try:
        if not match_time:
            return 0
            
        # Parse MM:SS format
        parts = match_time.split(':')
        minutes = int(parts[0])
        seconds = int(parts[1]) if len(parts) > 1 else 0
        
        # Convert to total seconds
        total_seconds = minutes * 60 + seconds
        
        # Convert to milliseconds
        return total_seconds * 1000
        
    except (ValueError, IndexError):
        logger.warning(f"Invalid match_time format: {match_time}")
        return 0


def convert_minute_to_milliseconds(minute, half=None):
    """
    Convert match minute to video milliseconds (legacy function for backward compatibility)
    
    Args:
        minute (int): Match minute
        half (int, optional): Match half (1 or 2)
        
    Returns:
        int: Milliseconds from video start
    """
    # Convert minutes to milliseconds
    # Assuming 45 minutes per half for calculation
    if half and half == 2:
        # Second half starts at 45 minutes
        return (45 + minute) * 60 * 1000
    else:
        # First half or no half specified
        return minute * 60 * 1000


@shared_task
def process_excel_match_highlights_task(session_id, excel_file_path="./HapoelAko_vs_MaccabiHaifa_AllInfo.xlsx"):
    """
    Process Excel match data and create highlights for goals, cards, and other events
    
    Args:
        session_id (str): TraceSession ID
        excel_file_path (str, optional): Path to Excel file. If None, uses session's basic_game_stats
        
    Returns:
        dict: Task results with success status and details
    """
    try:
        # Get the session
        try:
            session = TraceSession.objects.get(session_id=session_id)
        except TraceSession.DoesNotExist:
            error_msg = f"Session with ID {session_id} not found"
            logger.error(error_msg)
            return {"success": False, "error": error_msg}
        
        logger.info(f"Starting Excel highlights processing for session: {session_id}")
        
        # Check if session is processed
        if session.status != "processed":
            error_msg = f"Session {session_id} is not processed yet. Current status: {session.status}"
            logger.warning(error_msg)
            return {"success": False, "error": error_msg}
        
        # Determine Excel file path
        if not excel_file_path:
            if not session.basic_game_stats:
                error_msg = f"No Excel file provided and session {session_id} has no basic_game_stats file"
                logger.error(error_msg)
                return {"success": False, "error": error_msg}
            excel_file_path = session.basic_game_stats.path
        
        # Parse Excel data
        try:
            match_data = parse_excel_match_data(excel_file_path, session)
        except Exception as e:
            error_msg = f"Failed to parse Excel file: {str(e)}"
            logger.error(error_msg)
            return {"success": False, "error": error_msg}
        # Update TracePlayer names from Excel data
        logger.info(f"Updating TracePlayer names from Excel data...")
        player_update_result = update_trace_player_names(session, match_data.get('player_mappings', {}))
        
        logger.info(f"Player name updates: {player_update_result['updated_count']}/{player_update_result['total_mappings']} players updated")
        
        # Process events and create highlights
        import json
        import os

        # Write match_data to a JSON file with proper spacing
        output_dir = os.path.dirname(excel_file_path)
        output_json_path = os.path.join(output_dir, f"{session_id}_parsed_match_data.json")
        try:
            with open(output_json_path, "w", encoding="utf-8") as f:
                json.dump(match_data, f, indent=2, ensure_ascii=False)
            logger.info(f"Parsed match data written to {output_json_path}")
        except Exception as e:
            logger.error(f"Failed to write match_data to JSON: {e}")
        
        events_processed = 0
        highlights_created = 0
        errors = []
        
        # with transaction.atomic():
        #     for event in match_data.get('events', []):
        #         try:
        #             # Map player to TracePlayer
        #             trace_player = map_player_to_trace_player(
        #                 event['player_name'],
        #                 event.get('jersey_number', 0),
        #                 event['team_side'],
        #                 session
        #             )
                    
        #             if not trace_player:
        #                 logger.warning(f"Skipping event for unmapped player: {event['player_name']}")
        #                 continue
                    
        #             # Convert match time to milliseconds
        #             start_offset = convert_match_time_to_milliseconds(
        #                 event['match_time'],
        #                 event.get('half')
        #             )
                    
        #             # Determine highlight duration based on event type
        #             duration = 10000  # 10 seconds default
        #             if event['type'] == 'goal':
        #                 duration = 15000  # 15 seconds for goals
        #             elif event['type'] in ['red_card', 'yellow_card']:
        #                 duration = 8000   # 8 seconds for cards
                    
        #             # Create unique highlight ID
        #             highlight_id = f"excel-{event['type']}-{session_id}-{event['match_time'].replace(':', '')}-{trace_player.object_id}"
                    
        #             # Check if highlight already exists
        #             if TraceHighlight.objects.filter(highlight_id=highlight_id).exists():
        #                 logger.info(f"Highlight {highlight_id} already exists, skipping")
        #                 continue
                    
        #             # Create TraceHighlight
        #             highlight = TraceHighlight.objects.create(
        #                 highlight_id=highlight_id,
        #                 video_id=0,  # Will be updated with actual video ID
        #                 start_offset=start_offset,
        #                 duration=duration,
        #                 tags=[event['team_side'], event['type'], f"{event['match_time']}"],
        #                 video_stream=session.video_url,
        #                 event_type=event['type'],
        #                 source='excel_import',
        #                 match_time=event['match_time'],
        #                 half=1 if event['minute'] <= 45 else 2,
        #                 event_metadata=event['event_metadata'],
        #                 session=session,
        #                 player=trace_player
        #             )
                    
        #             # Calculate performance impact
        #             highlight.performance_impact = highlight.calculate_performance_impact()
        #             highlight.team_impact = abs(highlight.performance_impact) * 0.5  # Team impact is half of player impact
        #             highlight.save()
                    
        #             # Create highlight-object relationship if trace object exists
        #             trace_object = TraceObject.objects.filter(
        #                 session=session,
        #                 player=trace_player
        #             ).first()
                    
        #             if trace_object:
        #                 TraceHighlightObject.objects.create(
        #                     highlight=highlight,
        #                     trace_object=trace_object,
        #                     player=trace_player
        #                 )
                    
        #             highlights_created += 1
        #             events_processed += 1
                    
        #             logger.info(f"Created highlight {highlight_id} for {event['type']} by {event['player_name']} at {event['match_time']}")
                    
        #         except Exception as e:
        #             error_msg = f"Error processing event {event}: {str(e)}"
        #             logger.error(error_msg)
        #             errors.append(error_msg)
        #             continue
        
        # Update session with Excel processing status
        session.result['excel_highlights_processed'] = True
        session.result['excel_highlights_count'] = highlights_created
        session.result['excel_events_processed'] = events_processed
        session.save()
        
        # Note: Player stats recalculation is handled by the main process_trace_sessions_task flow
        
        result = {
            "success": True,
            "session_id": session_id,
            "events_processed": events_processed,
            "highlights_created": highlights_created,
            "player_updates": player_update_result,
            "errors": errors,
            "match_data_summary": {
                "total_events": len(match_data.get('events', [])),
                "goals": len([e for e in match_data.get('events', []) if e['type'] == 'goal']),
                "cards": len([e for e in match_data.get('events', []) if e['type'] in ['yellow_card', 'red_card']]),
                "total_player_mappings": len(match_data.get('player_mappings', {})),
            }
        }
        
        # logger.info(f"Excel highlights processing completed for session {session_id}. "
        #            f"Events processed: {events_processed}, Highlights created: {highlights_created}, "
        #            f"Players updated: {player_update_result['updated_count']}")
        
        return result
        
    except Exception as e:
        error_msg = f"Error in process_excel_match_highlights_task for session {session_id}: {str(e)}"
        logger.exception(error_msg)
        return {"success": False, "error": error_msg}
