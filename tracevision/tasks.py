import re
import os
import math
import json
import time
import logging
import requests
import tempfile
import mimetypes
from celery import shared_task
from django.conf import settings
from django.db import transaction
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from azure.storage.blob import BlobServiceClient, BlobType, ContentSettings
from django.db.models import Q

from tracevision.services import TraceVisionService
from tracevision.notification_service import NotificationService
from tracevision.models import (
    TraceSession,
    TraceObject,
    TraceHighlight,
    TraceHighlightObject,
    TracePlayer,
    PlayerUserMapping,
)
from tracevision.utils import (
    TraceVisionStoragePaths,
    cleanup_temp_files,
    determine_game_half_from_highlight_offset,
    download_excel_file_from_storage,
    parse_time_to_seconds,
    extract_video_segment_from_azure,
)

logger = logging.getLogger(__name__)


def should_include_highlight(highlight_data, session, player_map):
    """
    Determine if a highlight should be included based on relevance criteria.

    Args:
        highlight_data: Highlight data from TraceVision API
        session: TraceSession instance
        player_map: Dictionary mapping object_id to TracePlayer

    Returns:
        bool: True if highlight should be included, False otherwise
    """

    # Must have valid timing data
    start_offset = highlight_data.get("start_offset", 0)
    duration = highlight_data.get("duration", 0)
    if start_offset < 0 or duration <= 0:
        logger.debug(
            f"Filtered out highlight {highlight_data.get('highlight_id')} - invalid timing"
        )
        return False

    # Exclude highlights with very short duration (less than 1 second)
    if duration < 1000:  # 1000ms = 1 second
        logger.debug(
            f"Filtered out highlight {highlight_data.get('highlight_id')} - too short ({duration}ms)"
        )
        return False

    # Check if highlight is within game time bounds (if session has timing data)
    if (
        session.match_start_time
        and session.match_end_time
        and session.first_half_end_time
        and session.second_half_start_time
    ):
        game_start_ms = (
            parse_time_to_seconds(session.match_start_time) * 1000
            if session.match_start_time
            else 0
        )
        game_end_ms = (
            parse_time_to_seconds(session.match_end_time) * 1000
            if session.match_end_time
            else float("inf")
        )
        first_half_end_ms = (
            parse_time_to_seconds(session.first_half_end_time) * 1000
            if session.first_half_end_time
            else float("inf")
        )
        second_half_start_ms = (
            parse_time_to_seconds(session.second_half_start_time) * 1000
            if session.second_half_start_time
            else 0
        )

        # Check if highlight is before game start
        if start_offset < game_start_ms:
            logger.debug(
                f"Filtered out highlight {highlight_data.get('highlight_id')} - before game start"
            )
            return False

        # Check if highlight is after game end
        if start_offset > game_end_ms:
            logger.debug(
                f"Filtered out highlight {highlight_data.get('highlight_id')} - after game end"
            )
            return False

        # Check if highlight is during half-time break
        if first_half_end_ms <= start_offset < second_half_start_ms:
            logger.debug(
                f"Filtered out highlight {highlight_data.get('highlight_id')} - during half-time"
            )
            return False

    # Exclude highlights with suspicious or invalid data
    highlight_id = highlight_data.get("highlight_id", "")
    if not highlight_id or highlight_id.strip() == "":
        logger.debug("Filtered out highlight - no highlight_id")
        return False

    return True


def clean_record(record: dict) -> dict:
    cleaned = {}
    for k, v in record.items():
        if v is None or (isinstance(v, float) and math.isnan(v)):
            cleaned[k] = None

        elif k.lower() == "goals":
            # Always a list of integers
            if v in (None, "", []):
                cleaned[k] = []
            elif isinstance(v, str):
                # Extract all numbers (remove quotes/min etc.)
                minutes = re.findall(r"\d+", v)
                cleaned[k] = [int(m) for m in minutes]
            elif isinstance(v, list):
                # Convert possible ["16'", "77'"] → [16, 77]
                cleaned[k] = [
                    int(re.sub(r"\D", "", str(m))) for m in v if str(m).strip()
                ]
            else:
                cleaned[k] = [int(v)] if str(v).isdigit() else []

        elif k.lower() == "cards":
            # Always null if missing
            if v in (None, "", []):
                cleaned[k] = None
            else:
                cleaned[k] = str(v).strip()

        else:
            cleaned[k] = v
    return cleaned


def get_full_azure_blob_url(file_path: str) -> str:
    """
    Generate full Azure blob URL for a given file path.

    Args:
        file_path: The file path in Azure blob storage

    Returns:
        str: Full Azure blob URL
    """
    try:
        if hasattr(settings, "AZURE_CUSTOM_DOMAIN") and settings.AZURE_CUSTOM_DOMAIN:
            return f"https://{settings.AZURE_CUSTOM_DOMAIN}/media/{file_path}"
        else:
            logger.warning(
                "AZURE_CUSTOM_DOMAIN not configured, using default_storage.url()"
            )
            return default_storage.url(file_path)
    except Exception as e:
        logger.exception(f"Error generating Azure blob URL for {file_path}: {e}")
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
                f"Tracking data already downloaded for object {trace_object.object_id}"
            )
            return {
                "success": True,
                "processed": trace_object.tracking_processed,
                "azure_blob_url": trace_object.tracking_blob_url,
                "message": "Already downloaded",
            }

        logger.info(
            f"Fetching tracking data for object {trace_object.object_id} from: {trace_object.tracking_url}"
        )
        response = requests.get(trace_object.tracking_url, timeout=timeout)
        response.raise_for_status()

        tracking_data = response.json()

        # Create proper file path structure for Azure blob storage
        session_id = trace_object.session.session_id
        file_path = TraceVisionStoragePaths.get_tracking_data_path(
            session_id, trace_object.object_id
        )

        # Create ContentFile with the JSON data
        json_content = json.dumps(tracking_data, indent=2)
        file_content = ContentFile(json_content.encode("utf-8"))

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
            count = (
                len(tracking_data.get("spotlights", []))
                if isinstance(tracking_data, dict)
                else len(tracking_data)
            )
            logger.info(
                f"Successfully processed tracking data for {trace_object.object_id}: {count} points, saved to {blob_url}"
            )
        except Exception:
            logger.info(
                f"Successfully processed tracking data for {trace_object.object_id}, saved to {blob_url}"
            )

        return {
            "success": True,
            "processed": trace_object.tracking_processed,
            "azure_blob_url": blob_url,
            "message": "Downloaded and uploaded successfully",
        }

    except requests.exceptions.RequestException as e:
        logger.error(
            f"Failed to fetch tracking data for {trace_object.object_id} from {trace_object.tracking_url}: {e}",
            exc_info=True,
            stack_info=True,
        )
        return {
            "success": False,
            "data": [],
            "blob_url": None,
            "error": f"Network error: {str(e)}",
        }
    except Exception as e:
        logger.error(
            f"Error processing tracking data for {trace_object.object_id}: {e}",
            exc_info=True,
            stack_info=True,
        )
        return {
            "success": False,
            "data": [],
            "blob_url": None,
            "error": f"Processing error: {str(e)}",
        }


def upload_file_direct(blob_client, file_path, content_type, file_size):
    """
    Simple direct upload without any special configurations.
    """
    try:
        with open(file_path, "rb") as data:
            blob_client.upload_blob(
                data=data,
                blob_type=BlobType.BLOCKBLOB,
                overwrite=True,
                content_settings=ContentSettings(content_type=content_type),
            )
        logger.info(
            f"Successfully uploaded {file_size / (1024*1024*1024):.2f} GB using direct method"
        )
        return True
    except Exception as e:
        logger.error(f"Direct upload failed: {e}", exc_info=True, stack_info=True)
        return False


def upload_large_file_chunked(
    blob_client, file_path, content_type, file_size, chunk_size=2 * 1024 * 1024
):
    """
    Upload large files using chunked approach for better reliability.
    """
    try:
        import base64
        from azure.storage.blob import BlobBlock
        from azure.core.exceptions import ResourceExistsError

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
                            logger.error(
                                f"Invalid block_id for chunk {block_number}",
                                exc_info=True,
                                stack_info=True,
                            )
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
                                f"Chunk {block_number} upload attempt {chunk_attempt + 1} failed: {chunk_error}. Retrying..."
                            )
                            # Exponential backoff
                            time.sleep(2**chunk_attempt)
                        else:
                            logger.error(
                                f"Chunk {block_number} upload failed after 3 attempts: {chunk_error}",
                                exc_info=True,
                                stack_info=True,
                            )
                            raise chunk_error

                if not chunk_uploaded:
                    raise Exception(
                        f"Failed to upload chunk {block_number}",
                        exc_info=True,
                        stack_info=True,
                    )

                block_number += 1
                total_uploaded += len(chunk)

                # Log progress
                percentage = (total_uploaded / file_size) * 100
                uploaded_mb = total_uploaded / (1024 * 1024)
                total_mb = file_size / (1024 * 1024)
                logger.info(
                    f"Chunked upload progress: {percentage:.1f}% ({uploaded_mb:.1f}MB / {total_mb:.1f}MB)"
                )

        # Commit the blocks
        if block_ids:
            blob_client.commit_block_list(block_ids)
            logger.info(
                f"Successfully uploaded {file_size / (1024*1024*1024):.2f} GB using chunked method"
            )
            return True
        else:
            logger.error("No blocks to commit", exc_info=True, stack_info=True)
            return False

    except Exception as e:
        logger.error(f"Chunked upload failed: {e}", exc_info=True, stack_info=True)
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
            logger.info(f"Video already downloaded for session {session.session_id}")
            return {
                "success": True,
                "blob_url": session.blob_video_url,
                "message": "Already downloaded",
            }

        logger.info(
            f"Downloading video for session {session.session_id} from: {session.video_url}"
        )

        # Download the video stream
        response = requests.get(
            session.video_url, stream=True, timeout=max(timeout, 600)
        )
        response.raise_for_status()

        # # Validate content type
        content_type = response.headers.get("content-type", "")
        file_extension = mimetypes.guess_extension(content_type) or ".mp4"
        # content_type = "video/mp4"
        # file_extension = ".mp4"
        blob_path = TraceVisionStoragePaths.get_session_video_path(
            session.session_id, "original"
        )

        # Ensure blob path is clean and valid
        blob_path = blob_path.replace("//", "/").strip("/")
        logger.info(f"Blob path: {blob_path}")

        # Create temp file and stream content to it
        with tempfile.NamedTemporaryFile(
            delete=False, suffix=file_extension
        ) as tmp_file:
            temp_file_path = tmp_file.name
            total_size = 0
            chunk_count = 0

            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    tmp_file.write(chunk)
                    total_size += len(chunk)
                    chunk_count += 1
                    if chunk_count % 1000 == 0:
                        logger.info(
                            f"Downloaded {total_size / (1024*1024):.1f} MB for session {session.session_id}"
                        )

        logger.info(f"Download complete. Total size: {total_size / (1024*1024):.1f} MB")

        # Upload to Azure Blob Storage using SDK with retry logic
        blob_service_client = None
        blob_client = None

        # Retry blob client creation for network issues
        for client_attempt in range(3):
            try:
                logger.info(
                    f'AZURE_CONNECTION_STRING Found : {"Found" if settings.AZURE_CONNECTION_STRING else "Not Found"}'
                )
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
                        f"Failed to create blob client after 3 attempts: {client_error}",
                        exc_info=True,
                        stack_info=True,
                    )
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
                    f"Upload progress: {percentage:.1f}% ({uploaded_mb:.1f}MB / {total_mb:.1f}MB)"
                )

        for attempt in range(max_retries):
            try:
                # Validate file exists and get size
                if not os.path.exists(temp_file_path):
                    raise FileNotFoundError(f"Video file not found: {temp_file_path}")

                file_size = os.path.getsize(temp_file_path)
                if file_size == 0:
                    raise ValueError("Video file is empty")

                logger.info(
                    f"{'=='*50}\n\nVideo File Size: {file_size / (1024*1024*1024):.2f} GB\n\n{'=='*50}"
                )

                with open(temp_file_path, "rb") as data:
                    # Try with progress callback first
                    try:
                        upload_options = {
                            "data": data,
                            "blob_type": BlobType.BLOCKBLOB,
                            "overwrite": True,
                            "content_settings": ContentSettings(
                                content_type=content_type
                            ),
                            "max_concurrency": 2,  # Reduced for stability with large files
                            "length": file_size,
                            "timeout": 7200,  # 2 hours timeout for very large files
                            "progress_hook": progress_callback,  # Add progress tracking
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
                    for keyword in [
                        "dns",
                        "resolve",
                        "connection",
                        "network",
                        "timeout",
                    ]
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
                        upload_success = upload_file_direct(
                            blob_client, temp_file_path, content_type, file_size
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
                            upload_success = upload_large_file_chunked(
                                blob_client, temp_file_path, content_type, file_size
                            )
                            if upload_success:
                                logger.info("Chunked upload successful!")
                                break
                        except Exception as chunked_error:
                            logger.error(f"Chunked upload also failed: {chunked_error}")

                    logger.error(
                        f"All upload methods failed: {e}",
                        exc_info=True,
                        stack_info=True,
                    )
                    raise e

        # Clean up temp file
        # try:
        #     os.remove(temp_file_path)
        # except Exception as e:
        #     logger.warning(f"Failed to delete temp file {temp_file_path}: {e}")

        if not upload_success:
            return {
                "success": False,
                "blob_url": None,
                "error": "Upload failed after retries",
            }

        # Get full blob URL
        blob_url = f"{blob_client.url}"
        session.blob_video_url = blob_url
        session.save()

        return {
            "success": True,
            "blob_url": blob_url,
            "message": "Downloaded and uploaded successfully",
            "file_size_mb": os.path.getsize(temp_file_path) / (1024 * 1024),
        }

    except requests.exceptions.RequestException as e:
        logger.error(
            f"Failed to download video for session {session_id}: {e}",
            exc_info=True,
            stack_info=True,
        )
        return {
            "success": False,
            "blob_url": None,
            "error": f"Download error: {str(e)}",
        }

    except Exception as e:
        logger.error(f"Unexpected error processing session {session_id}: {e}")
        return {
            "success": False,
            "blob_url": None,
            "error": f"Internal error: {str(e)}",
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
                f"Result data already uploaded for session {session.session_id}"
            )
            return {
                "success": True,
                "blob_url": session.result_blob_url,
                "message": "Already uploaded",
            }

        logger.info(
            f"Uploading result data for session {session.session_id} to Azure blob"
        )

        # Create proper file path structure for Azure blob storage
        file_path = TraceVisionStoragePaths.get_session_result_path(session.session_id)

        # Create ContentFile with the JSON data
        json_content = json.dumps(result_data, indent=2, ensure_ascii=False)
        file_content = ContentFile(json_content.encode("utf-8"))

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
            f"Size: {data_size_kb:.2f} KB, saved to {blob_url}"
        )

        return {
            "success": True,
            "blob_url": blob_url,
            "message": "Uploaded successfully",
            "data_size_kb": data_size_kb,
        }

    except Exception as e:
        logger.error(
            f"Error uploading result data for session {session.session_id}: {e}",
            exc_info=True,
            stack_info=True,
        )
        return {"success": False, "blob_url": None, "error": f"Upload error: {str(e)}"}


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
                f"Starting to parse session data for session {session.session_id}"
            )

            session.trace_objects.all().delete()
            session.highlights.all().delete()

            # Get or create TracePlayer objects
            objects_data = result_data.get("objects", [])
            player_map = {}

            logger.info(f"Processing {len(objects_data)} objects to get/create players")

            for obj_data in objects_data:
                object_id = obj_data.get("object_id")
                side = obj_data.get("side", "")
                team = None
                jersey_number = 0

                if object_id:
                    # Parse object_id to extract team and jersey number
                    if object_id.startswith("away_"):
                        team = session.away_team
                        try:
                            jersey_number = int(object_id.split("_")[1])
                        except (ValueError, IndexError):
                            jersey_number = 0
                    elif object_id.startswith("home_"):
                        team = session.home_team
                        try:
                            jersey_number = int(object_id.split("_")[1])
                        except (ValueError, IndexError):
                            jersey_number = 0
                    else:
                        # Fallback to side field if object_id doesn't match expected pattern
                        team = (
                            session.home_team
                            if side.lower() == "home"
                            else session.away_team
                        )
                        jersey_number = obj_data.get("jersey_number", 0)

                # Extract player information from object data
                player_name = obj_data.get("name", f"Player {object_id}")
                position = obj_data.get("position", "Unknown")

                # Validate that we have a team assigned
                if not team:
                    logger.warning(
                        f"Could not determine team for object_id: {object_id}, skipping player"
                    )
                    continue

                # Check if player already exists for this team and jersey_number (across all sessions)
                # This matches the Excel processing logic which uses team + jersey_number
                existing_player = TracePlayer.objects.filter(
                    team=team, jersey_number=jersey_number
                ).first()

                if existing_player:
                    # Use existing player from any session
                    trace_player = existing_player

                    # Update object_id if it's different
                    if trace_player.object_id != object_id:
                        trace_player.object_id = object_id
                        trace_player.save(update_fields=["object_id"])

                    # Update player name only if it starts with "Player" (default/generated name)
                    # This ensures we don't overwrite manually set names from Excel
                    current_name = existing_player.name or ""
                    if current_name.startswith("Player"):
                        # Get name from WajoUser if player is mapped, otherwise leave empty
                        if existing_player.user and existing_player.user.name:
                            updated_name = existing_player.user.name
                        else:
                            updated_name = ""

                        # Update the name if it's different
                        if current_name != updated_name:
                            existing_player.name = updated_name
                            existing_player.save(update_fields=["name"])
                            logger.info(
                                f"Updated player {object_id} name from '{current_name}' to '{updated_name}' (mapped: {existing_player.user is not None})"
                            )

                    # Add session to player's sessions if not already present
                    if session not in trace_player.sessions.all():
                        trace_player.sessions.add(session)

                    logger.info(
                        f"Using existing player (team: {team.name}, jersey: {jersey_number}, object_id: {object_id})"
                    )
                else:
                    # Create new player
                    team_name = team.name if hasattr(team, "name") else str(team)
                    logger.info(
                        f"Creating new player (object_id: {object_id}, team: {team_name}, jersey: {jersey_number})"
                    )

                    trace_player = TracePlayer.objects.create(
                        object_id=object_id,
                        name=player_name,
                        jersey_number=jersey_number,
                        position=position,
                        team=team,
                        user=None,  # Will be mapped later via account creation with token
                    )

                    # Add session to player's sessions
                    trace_player.sessions.add(session)

                player_map[object_id] = trace_player

            logger.info(f"Processed {len(player_map)} players (existing + new)")

            # Step 2: Create TraceObject objects linked to players
            trace_objects = []
            logger.info(f"Creating trace objects for {len(objects_data)} objects")

            for obj_data in objects_data:
                object_id = obj_data.get("object_id")
                player = player_map.get(object_id)

                if player:
                    # Create TraceObject linked to the player
                    trace_object = TraceObject(
                        object_id=object_id,
                        type=obj_data.get("type", ""),
                        side=obj_data.get("side", ""),
                        appearance_fv=obj_data.get("appearance_fv"),
                        color_fv=obj_data.get("color_fv"),
                        tracking_url=obj_data.get("tracking_url", ""),
                        role=obj_data.get("role"),
                        session=session,
                        player=player,  # Link to TracePlayer instead of user
                    )
                    trace_objects.append(trace_object)

            # Bulk create objects
            if trace_objects:
                created_objects = TraceObject.objects.bulk_create(trace_objects)
                logger.info(f"Created {len(created_objects)} trace objects")

                # Download tracking data for each object
                logger.info(
                    f"Downloading tracking data for {len(created_objects)} objects"
                )
                updated_objects = []

                for trace_object in created_objects:
                    try:
                        if trace_object.tracking_url:
                            result = fetch_tracking_data_and_save_to_azure_blob(
                                trace_object
                            )
                            if result["success"]:
                                logger.info(
                                    f"Successfully downloaded tracking data for {trace_object.object_id}"
                                )
                                updated_objects.append(trace_object)
                            else:
                                logger.warning(
                                    f"Failed to download tracking data for {trace_object.object_id}: {result.get('error', 'Unknown error')}"
                                )
                        else:
                            logger.warning(
                                f"No tracking URL for object {trace_object.object_id}"
                            )
                    except Exception as e:
                        logger.exception(
                            f"Exception downloading tracking data for {trace_object.object_id}: {e}"
                        )

                logger.info(
                    f"Successfully downloaded tracking data for {len(updated_objects)}/{len(created_objects)} objects"
                )

            # Step 3: Create TraceHighlight objects linked to players
            highlights_data = result_data.get("highlights", [])
            trace_highlights = []
            highlight_objects_bulk = []

            logger.info(f"Processing {len(highlights_data)} highlights")

            # Filter highlights to remove non-related videos
            filtered_highlights = []
            for highlight_data in highlights_data:
                # Apply filtering criteria
                if should_include_highlight(highlight_data, session, player_map):
                    filtered_highlights.append(highlight_data)
                else:
                    logger.debug(
                        f"Filtered out highlight {highlight_data.get('highlight_id')} - not relevant"
                    )

            logger.info(
                f"After filtering: {len(filtered_highlights)} relevant highlights out of {len(highlights_data)}"
            )

            for highlight_data in filtered_highlights:
                # Try to find the primary player involved in this highlight
                highlight_objects = highlight_data.get("objects", [])
                primary_player = None

                # Get the first player from the highlight objects
                if highlight_objects:
                    first_object_id = highlight_objects[0].get("object_id")
                    primary_player = player_map.get(first_object_id)

                # Calculate which half this highlight belongs to
                half = determine_game_half_from_highlight_offset(
                    highlight_data.get("start_offset", 0),
                    session.match_start_time,
                    session.first_half_end_time,
                    session.second_half_start_time,
                    session.match_end_time,
                )

                # Create TraceHighlight linked to player
                trace_highlight = TraceHighlight(
                    highlight_id=highlight_data.get("highlight_id"),
                    video_id=highlight_data.get("video_id", 0),
                    start_offset=highlight_data.get("start_offset", 0),
                    duration=highlight_data.get("duration", 0),
                    tags=highlight_data.get("tags", []),
                    video_stream=highlight_data.get("video_stream", ""),
                    event_type="touch",  # Default for TraceVision highlights
                    source="tracevision",
                    session=session,
                    player=primary_player,  # Link to TracePlayer instead of user
                    half=half,  # Set the calculated half
                )
                trace_highlights.append(trace_highlight)

            # Bulk create highlights
            if trace_highlights:
                created_highlights = TraceHighlight.objects.bulk_create(
                    trace_highlights
                )
                logger.info(f"Created {len(created_highlights)} trace highlights")

                # Create highlight-object relationships
                for i, highlight_data in enumerate(filtered_highlights):
                    highlight_objects = highlight_data.get("objects", [])
                    created_highlight = created_highlights[i]

                    for obj_data in highlight_objects:
                        object_id = obj_data.get("object_id")
                        if object_id in player_map:
                            player = player_map[object_id]
                            # Find the corresponding trace object
                            trace_object = TraceObject.objects.filter(
                                session=session, object_id=object_id
                            ).first()

                            if trace_object:
                                highlight_objects_bulk.append(
                                    TraceHighlightObject(
                                        highlight=created_highlight,
                                        trace_object=trace_object,
                                        player=player,  # Link to TracePlayer
                                    )
                                )

                if highlight_objects_bulk:
                    TraceHighlightObject.objects.bulk_create(highlight_objects_bulk)
                    logger.info(
                        f"Created {len(highlight_objects_bulk)} highlight-object relationships"
                    )

            logger.info(
                f"Successfully parsed and stored all session data for session {session.session_id}"
            )
            return True

    except Exception as e:
        logger.exception(
            f"Error parsing session data for session {session.session_id}: {e}"
        )
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
                "Notification service not available, cannot create notification",
                exc_info=True,
                stack_info=True,
            )
            return

        # Prepare session data for notification
        session_data = {
            "session_id": session.session_id,
            "status": session.status,
            "match_date": session.match_date,
            "home_team": session.home_team,
            "away_team": session.away_team,
            "home_score": session.home_score,
            "away_score": session.away_score,
        }

        # Create silent notifications for all devices of the user
        notifications = notification_service.create_silent_notification_for_all_devices(
            session.user, session_data
        )

        if notifications:
            logger.info(
                f"Created {len(notifications)} silent notifications for user {session.user.phone_no} for session {session.session_id}"
            )
        else:
            logger.warning(
                f"No devices found or failed to create notifications for user {session.user.phone_no}"
            )

    except Exception as e:
        logger.exception(
            f"Error in create_silent_notification for session {session.session_id}: {e}"
        )


@shared_task
def process_excel_and_create_players_task(session_id):
    """
    Celery task to process Excel file and create/update players, highlights, and statistics.
    This task runs after session creation and before video download.

    Args:
        session_id (int): TraceSession ID

    Returns:
        dict: Task result with success status and details
    """
    from tracevision.utils import process_excel_and_create_players

    try:
        result = process_excel_and_create_players(session_id)
        logger.info(
            f"Excel processing task completed for session {session_id}: {result}"
        )
        return result
    except Exception as e:
        error_msg = f"Error in Excel processing task for session {session_id}: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return {"success": False, "error": error_msg}


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
                status__in=["processed", "process_error"]
            )
        else:
            sessions = TraceSession.objects.filter(id=trace_session_id)

        if not sessions.exists():
            logger.info("All sessions are already processed or in final state.")
            return f"No sessions to process"

        logger.info(f"Found {sessions.count()} sessions to process")

        # Initialize service
        tracevision_service = TraceVisionService()
        processed_count = 0
        error_count = 0

        for session in sessions:
            try:
                logger.info(
                    f"Checking session status for ID: {session.id} | {session.session_id}"
                )

                # Query TraceVision API for status update using service
                status_data = tracevision_service.get_session_status(
                    session, force_refresh=True
                )

                if not status_data:
                    continue

                new_status = status_data["status"]
                previous_status = session.status

                # Update session status
                session.status = new_status
                session.save()

                logger.info(
                    f"Updated session {session.session_id} status from {previous_status} to {new_status}"
                )

                # Handle final status changes (processed or process_error)
                if new_status in ["processed", "process_error"]:
                    # Check if we need to process this session
                    should_process = False

                    # Normal processing - old status was not processed, new status is processed
                    if previous_status != "processed" and new_status == "processed":
                        should_process = True
                        logger.info(
                            f"Normal processing: Session {session.session_id} transitioning from {previous_status} to {new_status}"
                        )

                    # Recovery processing - old status was processed but no objects/highlights exist
                    elif previous_status == "processed" and new_status == "processed":
                        # Check if objects or highlights exist for this session
                        objects_count = session.trace_objects.count()
                        highlights_count = session.highlights.count()

                        if objects_count == 0 and highlights_count == 0:
                            should_process = True
                            logger.info(
                                f"Recovery processing: Session {session.session_id} was processed but has no objects ({objects_count}) or highlights ({highlights_count}). Reprocessing..."
                            )

                    if should_process:
                        status_description = (
                            "processed"
                            if new_status == "processed"
                            else "encountered process error"
                        )
                        logger.info(
                            f"Session {session.session_id} {status_description}."
                        )

                        # Fetch and save result data for both statuses (may contain error details for process_error)
                        result_data = tracevision_service.get_session_result(session)
                        if result_data:
                            # Upload result data to Azure blob instead of storing in database
                            upload_result = upload_result_data_to_azure_blob(
                                session, result_data
                            )

                            if upload_result["success"]:
                                logger.info(
                                    f"Result data uploaded successfully for session {session.session_id}"
                                )
                            else:
                                logger.error(
                                    f"Failed to upload result data for session {session.session_id}: {upload_result.get('error')}",
                                    exc_info=True,
                                    stack_info=True,
                                )

                            # For processed sessions, parse and store structured data
                            if new_status == "processed":
                                logger.info(
                                    f"Parsing structured data for session {session.session_id}"
                                )
                                parsing_success = parse_and_store_session_data(
                                    session, result_data
                                )

                                if parsing_success:
                                    logger.info(
                                        f"Successfully parsed structured data for session {session.session_id}"
                                    )
                                    # Only save session and create notification if parsing was successful
                                    session.save()
                                    create_silent_notification(session)

                                    # Enqueue player-to-user mapping task
                                    try:
                                        map_players_to_users_task.delay(
                                            session.session_id
                                        )
                                        logger.info(
                                            f"Queued player-to-user mapping for session {session.session_id}"
                                        )
                                    except Exception as e:
                                        logger.exception(
                                            f"Failed to enqueue player mapping for session {session.session_id}: {e}"
                                        )

                                    # Enqueue Excel highlights processing FIRST (before other calculations)
                                    try:
                                        process_excel_match_highlights_task.delay(
                                            session.session_id
                                        )
                                        logger.info(
                                            f"Queued Excel highlights processing for session {session.session_id}"
                                        )
                                    except Exception as e:
                                        logger.exception(
                                            f"Failed to enqueue Excel highlights processing for session {session.session_id}: {e}"
                                        )

                                    # # Enqueue aggregates computation (idempotent)
                                    try:
                                        compute_aggregates_task.delay(
                                            session.session_id
                                        )
                                        logger.info(
                                            f"Queued aggregates computation for session {session.session_id}"
                                        )
                                    except Exception as e:
                                        logger.exception(
                                            f"Failed to enqueue aggregates for session {session.session_id}: {e}"
                                        )
                                else:
                                    logger.error(
                                        f"Failed to parse structured data for session {session.session_id}. Not updating session status."
                                    )
                                    # Don't update the session status if parsing failed
                                    session.status = previous_status
                                    session.save()
                                    continue
                            else:
                                # For process_error, just save the result data
                                session.save()
                                create_silent_notification(session)

                            logger.info(
                                f"Saved result data for {new_status} session {session.session_id}"
                            )
                        else:
                            logger.error(
                                f"Failed to fetch result for {new_status} session {session.session_id}",
                                exc_info=True,
                                stack_info=True,
                            )

                            # Don't update status if we couldn't fetch result data
                            session.status = previous_status
                            session.save()
                            continue
                    else:
                        logger.info(
                            f"Skipping processing for session {session.session_id} - no processing needed"
                        )

                processed_count += 1

            except Exception as e:
                error_count += 1
                logger.error(
                    f"Error processing session {session.session_id}: {e}",
                    exc_info=True,
                    stack_info=True,
                )

        return f"Processed {processed_count} sessions, {error_count} errors"

    except Exception as e:
        logger.exception(f"Error in process_trace_sessions_task: {e}")
        raise


@shared_task
def compute_aggregates_task(session_id, only_possession_segments=False):
    """
    Compute CSV-equivalent aggregates in background and store them in DB.

    Args:
        session_id (str): Session ID to process
        only_possession_segments (bool): If True, only compute possession segments (skip clips)
    """
    try:
        from tracevision.services import TraceVisionAggregationService

        # Get the session
        try:
            session = TraceSession.objects.get(session_id=session_id)
        except TraceSession.DoesNotExist:
            error_msg = f"Session with ID {session_id} not found"
            logger.error(error_msg)
            return {"success": False, "error": error_msg}

        if session.status != "processed":
            msg = f"Session {session_id} not processed yet"
            logger.warning(msg)
            return {"success": False, "error": msg}

        agg = TraceVisionAggregationService()

        if only_possession_segments:
            result = agg.compute_possession_segments_only(session)
            logger.info(f"Computed possession segments only for session {session_id}")
        else:
            result = agg.compute_all(session)
            logger.info(f"Computed aggregates for session {session_id}")

            # Trigger overlay highlights generation for clip reels
            try:
                generate_overlay_highlights_task.delay(session_id)
                logger.info(
                    f"Queued overlay highlights generation for session {session_id}"
                )
            except Exception as e:
                logger.exception(
                    f"Failed to enqueue overlay highlights generation for session {session_id}: {e}"
                )

        return {"success": True, "details": {k: True for k in result.keys()}}
    except Exception as e:
        logger.error(
            f"Error computing aggregates for session {session_id}: {e}",
            exc_info=True,
            stack_info=True,
        )
        return {"success": False, "error": str(e)}


@shared_task
def map_players_to_users_task(session_id=None, user_id=None, game_id=None):
    """
    Map TracePlayer objects to WajoUser objects based on jersey numbers, names, etc.
    This task runs after session processing to link players to actual users.

    Args:
        session_id (str, optional): Session ID to process (existing behavior)
        user_id (str, optional): User phone_no to map players for all their games (new)
        game_id (str, optional): Game ID to map all unmapped players in this game (new)

    Returns:
        dict: Task results with success status and mapping details
    """
    try:
        from accounts.models import WajoUser
        from teams.models import Team
        from games.models import Game, GameUserRole

        # Determine which mode to run in
        session = None  # Initialize session variable
        if game_id:
            # Mode 3: Map all unmapped players in a specific game
            try:
                game = Game.objects.get(id=game_id)
                if not game.trace_session:
                    error_msg = f"Game {game_id} has no TraceSession"
                    logger.error(error_msg)
                    return {"success": False, "error": error_msg}
                session = game.trace_session
                # Use reverse M2M relationship: find players in this session that are unmapped
                unmapped_players = session.players.filter(user__isnull=True)
            except Game.DoesNotExist:
                error_msg = f"Game with ID {game_id} not found"
                logger.error(error_msg)
                return {"success": False, "error": error_msg}
        elif user_id:
            # Mode 2: Map all players for games where this user has GameUserRole
            try:
                user = WajoUser.objects.get(phone_no=user_id)
                user_games = Game.objects.filter(game_roles__user=user)
                sessions = TraceSession.objects.filter(game__in=user_games)
                # Use reverse M2M relationship: find players in any of these sessions that are unmapped
                # Get all players from all sessions and filter for unmapped ones
                unmapped_players = TracePlayer.objects.filter(
                    sessions__in=sessions, user__isnull=True
                ).distinct()
            except WajoUser.DoesNotExist:
                error_msg = f"User with ID {user_id} not found"
                logger.error(error_msg)
                return {"success": False, "error": error_msg}
        elif session_id:
            # Mode 1: Map players for specific session (existing behavior)
            try:
                session = TraceSession.objects.get(session_id=session_id)
                # Use reverse M2M relationship: find players in this session that are unmapped
                unmapped_players = session.players.filter(user__isnull=True)
            except TraceSession.DoesNotExist:
                error_msg = f"Session with ID {session_id} not found"
                logger.error(error_msg)
                return {"success": False, "error": error_msg}
        else:
            error_msg = "Must provide session_id, user_id, or game_id"
            logger.error(error_msg)
            return {"success": False, "error": error_msg}

        if session_id:
            logger.info(f"Starting player-to-user mapping for session: {session_id}")
        elif user_id:
            logger.info(f"Starting player-to-user mapping for user: {user_id}")
        elif game_id:
            logger.info(f"Starting player-to-user mapping for game: {game_id}")

        if not unmapped_players.exists():
            if session_id:
                logger.info(f"No unmapped players found for session {session_id}")
            elif user_id:
                logger.info(f"No unmapped players found for user {user_id}")
            elif game_id:
                logger.info(f"No unmapped players found for game {game_id}")
            return {
                "success": True,
                "message": "No unmapped players found",
                "mapped_count": 0,
            }

        logger.info(f"Found {unmapped_players.count()} unmapped players to process")

        mapped_count = 0
        mapping_details = []

        for player in unmapped_players:
            try:
                # Log player details for debugging
                team_name = (
                    player.team.name
                    if hasattr(player.team, "name")
                    else str(player.team)
                )
                logger.info(
                    f"Attempting to map player: {player.object_id} (jersey: {player.jersey_number}, team: {team_name})"
                )

                # Strategy 1: Try to match by jersey number and team
                # This matches: trace_player.team + trace_player.jersey_number == user.team + user.jersey_number
                if player.jersey_number and player.team:
                    matching_user = WajoUser.objects.filter(
                        jersey_number=player.jersey_number, team=player.team
                    ).first()

                    if matching_user:
                        # Safety check: Ensure player is not already mapped to another user
                        # One TracePlayer can only be mapped to one WajoUser
                        if player.user and player.user != matching_user:
                            logger.warning(
                                f"TracePlayer {player.object_id} is already mapped to user {player.user.phone_no}. "
                                f"Cannot map to {matching_user.phone_no}. Skipping."
                            )
                            continue

                        # Skip if already mapped to the same user
                        if player.user == matching_user:
                            logger.info(
                                f"TracePlayer {player.object_id} is already mapped to user {matching_user.phone_no}. Skipping."
                            )
                            continue

                        player.user = matching_user
                        player.save()
                        mapped_count += 1
                        # Create mapping history record
                        PlayerUserMapping.objects.create(
                            trace_player=player,
                            wajo_user=matching_user,
                            mapped_by=None,  # Automatic task mapping
                            mapping_source="task",
                        )
                        mapping_details.append(
                            {
                                "player_id": player.object_id,
                                "player_name": player.name,
                                "jersey_number": player.jersey_number,
                                "mapped_to_user": matching_user.phone_no,
                                "method": "jersey_number_and_team",
                            }
                        )
                        logger.info(
                            f"Mapped player {player.name} ({player.jersey_number}) to user {matching_user.phone_no}"
                        )
                        continue

                # Strategy 2: Try to match by name and team (fuzzy matching)
                if player.name and player.team:
                    # Simple name matching - you can enhance this with fuzzy matching
                    matching_user = WajoUser.objects.filter(
                        name__icontains=player.name.split()[0],  # First name
                        team=player.team,
                    ).first()

                    if matching_user:
                        # Safety check: Ensure player is not already mapped to another user
                        # One TracePlayer can only be mapped to one WajoUser
                        if player.user and player.user != matching_user:
                            logger.warning(
                                f"TracePlayer {player.object_id} is already mapped to user {player.user.phone_no}. "
                                f"Cannot map to {matching_user.phone_no}. Skipping."
                            )
                            continue

                        # Skip if already mapped to the same user
                        if player.user == matching_user:
                            logger.info(
                                f"TracePlayer {player.object_id} is already mapped to user {matching_user.phone_no}. Skipping."
                            )
                            continue

                        player.user = matching_user
                        player.save()
                        mapped_count += 1
                        # Create mapping history record
                        PlayerUserMapping.objects.create(
                            trace_player=player,
                            wajo_user=matching_user,
                            mapped_by=None,  # Automatic task mapping
                            mapping_source="task",
                        )
                        mapping_details.append(
                            {
                                "player_id": player.object_id,
                                "player_name": player.name,
                                "jersey_number": player.jersey_number,
                                "mapped_to_user": matching_user.phone_no,
                                "method": "name_and_team",
                            }
                        )
                        logger.info(
                            f"Mapped player {player.name} to user {matching_user.phone_no} by name"
                        )
                        continue

                # Strategy 3: If session has only one user, map all unmapped players to that user
                # Only applies when we have a single session (session_id or game_id mode)
                # Note: Outer condition already ensures player.user is None, so no need for additional checks
                if session and session.user and not player.user:
                    # Check if this is a single-player session
                    total_players = session.players.count()
                    if total_players == 1:
                        # One TracePlayer can only be mapped to one WajoUser
                        # Since we already checked not player.user, we can safely map
                        player.user = session.user
                        player.save()
                        mapped_count += 1
                        # Create mapping history record
                        PlayerUserMapping.objects.create(
                            trace_player=player,
                            wajo_user=session.user,
                            mapped_by=None,  # Automatic task mapping
                            mapping_source="task",
                        )
                        mapping_details.append(
                            {
                                "player_id": player.object_id,
                                "player_name": player.name,
                                "jersey_number": player.jersey_number,
                                "mapped_to_user": session.user.phone_no,
                                "method": "single_player_session",
                            }
                        )
                        logger.info(
                            f"Mapped single player {player.name} to session user {session.user.phone_no}"
                        )

            except Exception as e:
                logger.exception(f"Error mapping player {player.object_id}: {e}")

        logger.info(
            f"Successfully mapped {mapped_count}/{unmapped_players.count()} players to users"
        )

        result = {
            "success": True,
            "total_players": unmapped_players.count(),
            "mapped_count": mapped_count,
            "unmapped_count": unmapped_players.count() - mapped_count,
            "mapping_details": mapping_details,
            "message": f"Mapped {mapped_count} players to users",
        }

        if session_id:
            result["session_id"] = session_id
        if user_id:
            result["user_id"] = user_id
        if game_id:
            result["game_id"] = game_id

        return result

    except Exception as e:
        if session_id:
            error_msg = (
                f"Error in map_players_to_users_task for session {session_id}: {str(e)}"
            )
        elif user_id:
            error_msg = (
                f"Error in map_players_to_users_task for user {user_id}: {str(e)}"
            )
        elif game_id:
            error_msg = (
                f"Error in map_players_to_users_task for game {game_id}: {str(e)}"
            )
        else:
            error_msg = f"Error in map_players_to_users_task: {str(e)}"
        logger.exception(error_msg)
        return {"success": False, "error": error_msg}


@shared_task
def auto_map_user_to_player_task(user_phone_no):
    """
    Automatically map a WajoUser to TracePlayer(s) when user is created/updated
    with jersey_number and team.

    This task:
    1. Finds TracePlayers with matching jersey_number and team
    2. If multiple TracePlayers exist in both teams, uses team.name to match
    3. Maps the user to the appropriate TracePlayer(s)
    4. Logs if a TracePlayer is already mapped to another user

    Args:
        user_phone_no (str): Phone number (primary key) of the WajoUser

    Returns:
        dict: Task results with success status and mapping details
    """
    try:
        from accounts.models import WajoUser

        logger.info(f"Starting auto-mapping for user: {user_phone_no}")

        # Get the user
        try:
            user = WajoUser.objects.select_related("team").get(phone_no=user_phone_no)
        except WajoUser.DoesNotExist:
            error_msg = f"User with phone_no '{user_phone_no}' not found"
            logger.error(error_msg)
            return {"success": False, "error": error_msg}

        # Check if user has jersey_number and team (required for auto-mapping)
        if not user.jersey_number or not user.team:
            logger.info(
                f"User {user_phone_no} does not have jersey_number or team. Skipping auto-mapping."
            )
            return {
                "success": True,
                "message": "User does not have jersey_number or team. Skipping auto-mapping.",
                "mapped_count": 0,
            }

        # Find TracePlayers with matching jersey_number and team
        matching_players = (
            TracePlayer.objects.filter(
                jersey_number=user.jersey_number,
                team=user.team,
                user__isnull=True,
            )
            .select_related("team")
            .prefetch_related("sessions")
        )

        if not matching_players.exists():
            logger.info(
                f"No unmapped TracePlayers found for user {user_phone_no} "
                f"(jersey: {user.jersey_number}, team: {user.team.id})"
            )
            return {
                "success": True,
                "message": "No matching unmapped players found",
                "mapped_count": 0,
            }

        # If multiple players exist, use name and team to match
        # Since player can be in multiple sessions, we check across all sessions
        mapped_count = 0
        mapping_details = []

        for player in matching_players:
            try:
                # Check if there are players with same jersey in both teams across any session
                # This handles edge cases where same jersey exists in both home and away teams
                players_in_both_teams = False
                player_sessions = player.sessions.all()

                for session in player_sessions:
                    if session.home_team and session.away_team:
                        # Use reverse M2M relationship for better query efficiency
                        home_players = session.players.filter(
                            jersey_number=user.jersey_number,
                            team=session.home_team,
                            user__isnull=True,
                        )
                        away_players = session.players.filter(
                            jersey_number=user.jersey_number,
                            team=session.away_team,
                            user__isnull=True,
                        )

                        if home_players.exists() and away_players.exists():
                            players_in_both_teams = True
                            break  # Found a session with both teams having same jersey

                # If players exist in both teams, use player name and team to match
                if players_in_both_teams:
                    # First check: Match player name with WajoUser name
                    name_matches = False
                    if player.name and user.name:
                        # Try to match first name (case-insensitive)
                        player_first_name = (
                            player.name.split()[0].lower()
                            if player.name.split()
                            else ""
                        )
                        user_first_name = (
                            user.name.split()[0].lower() if user.name.split() else ""
                        )

                        # Check if first names match
                        if (
                            player_first_name
                            and user_first_name
                            and player_first_name == user_first_name
                        ):
                            name_matches = True
                        # Also check if player name contains user name or vice versa (for partial matches)
                        elif (
                            player.name.lower() in user.name.lower()
                            or user.name.lower() in player.name.lower()
                        ):
                            name_matches = True

                    # If name doesn't match, skip this player
                    if not name_matches:
                        logger.info(
                            f"Skipping player {player.id} - name mismatch: "
                            f"player name '{player.name}' != user name '{user.name}'"
                        )
                        continue

                    # Second check: Match player team with WajoUser team
                    if player.team.id != user.team.id:
                        logger.info(
                            f"Skipping player {player.id} - team mismatch: "
                            f"player team '{player.team.id}' != user team '{user.team.id}'"
                        )
                        continue

                    # Both name and team match - this is the correct player
                    logger.info(
                        f"Found matching player {player.id} by name and team: "
                        f"name '{player.name}' matches '{user.name}', team '{player.team.id}' matches '{user.team.id}'"
                    )

                # Note: We already filtered for user__isnull=True, so player should be unmapped
                # But double-check as a safety measure
                if player.user:
                    logger.warning(
                        f"TracePlayer {player.id} is already mapped to user {player.user.phone_no}. "
                        f"Cannot auto-map to {user_phone_no}. Skipping."
                    )
                    # Log this action (but don't create mapping record since we didn't map)
                    PlayerUserMapping.objects.create(
                        trace_player=player,
                        wajo_user=user,
                        mapped_by=None,  # Automatic mapping, no user performed it
                        mapping_source="task",
                        notes=f"Auto-mapping attempted but player already mapped to {player.user.phone_no}",
                    )
                    continue

                # Perform the mapping
                player.user = user
                player.save(update_fields=["user"])

                # Create mapping history record (without mapped_by since it's automatic)
                PlayerUserMapping.objects.create(
                    trace_player=player,
                    wajo_user=user,
                    mapped_by=None,  # Automatic mapping
                    mapping_source="task",
                )

                mapped_count += 1
                mapping_details.append(
                    {
                        "player_id": player.id,
                        "player_name": player.name,
                        "jersey_number": player.jersey_number,
                        "team": (
                            player.team.name if player.team.name else player.team.id
                        ),
                        "session_id": session.session_id,
                    }
                )

                logger.info(
                    f"Auto-mapped TracePlayer {player.id} ({player.name}) to user {user_phone_no} "
                    f"(jersey: {user.jersey_number}, team: {user.team.id})"
                )

            except Exception as e:
                logger.exception(f"Error mapping player {player.id}: {e}")

        logger.info(
            f"Successfully auto-mapped {mapped_count}/{matching_players.count()} players to user {user_phone_no}"
        )

        return {
            "success": True,
            "total_players": matching_players.count(),
            "mapped_count": mapped_count,
            "unmapped_count": matching_players.count() - mapped_count,
            "mapping_details": mapping_details,
            "message": f"Auto-mapped {mapped_count} players to user",
            "user_phone_no": user_phone_no,
        }

    except Exception as e:
        error_msg = (
            f"Error in auto_map_user_to_player_task for user {user_phone_no}: {str(e)}"
        )
        logger.exception(error_msg)
        return {"success": False, "error": error_msg}


@shared_task
def generate_overlay_highlights_task(
    session_id=None,
    clip_reel_ids=None,
    video_types=None,
    ratios=None,
    is_default=None,
    tags=None,
    batch_size=5,
):
    """
    Generate overlay highlight videos for TraceClipReel objects based on filters.
    Processes clip reels session-wise to avoid redundant video downloads.

    Args:
        session_id (str, optional): Process specific session
        clip_reel_ids (list, optional): Process specific clip reels
        video_types (list, optional): List of video types to process (deprecated, kept for backward compatibility)
        ratios (list, optional): List of ratios to process (default: ["original", "9:16"])
            Valid values: "original" (Horizontal), "9:16" (Vertical)
        is_default (bool, optional): Filter by is_default flag (default: True - only process default clip reels)
        tags (list, optional): Filter by tags. Each tag in list must be present in clip_reel.tags
            Example: ["with_name_overlay", "with_circle_overlay"]
        batch_size (int): Number of clips to process in parallel (default: 5)

    Returns:
        dict: Task results with success status and details
    """
    try:
        from .video_generator import (
            TrackingDataCache,
            create_clip_reel_overlay_video,
            upload_video_to_storage,
        )
        from .models import TraceClipReel, TraceSession
        from django.db.models import Prefetch, Q

        # Set default is_default filter (True by default - only process default clip reels)
        if is_default is None:
            is_default = True

        # Set default ratios if not provided
        if ratios is None:
            ratios = ["original", "9:16"]

        # Build base filter for clip reels
        clip_reel_filter = {
            "generation_status__in": ["pending", "failed"],
        }

        # Add is_default filter
        clip_reel_filter["is_default"] = is_default

        # Add ratio filter
        clip_reel_filter["ratio__in"] = ratios

        # Add video_type filter if provided (for backward compatibility)
        # If None, don't filter by video_type (allows None values)
        if video_types is not None:
            clip_reel_filter["video_type__in"] = video_types

        # Add tag filters if provided
        tag_filters = None
        if tags:
            tag_filters = Q()
            for tag in tags:
                tag_filters &= Q(tags__contains=tag)

        logger.info(
            f"Filtering clip reels: is_default={is_default}, ratios={ratios}, "
            f"video_types={video_types}, tags={tags}"
        )

        if session_id:
            clip_reel_filter["session__session_id"] = session_id
        if clip_reel_ids:
            clip_reel_filter["id__in"] = clip_reel_ids

        # Build queryset for clip reels
        clip_reel_queryset = TraceClipReel.objects.filter(**clip_reel_filter)

        # Apply tag filters if provided
        if tag_filters:
            clip_reel_queryset = clip_reel_queryset.filter(tag_filters)

        clip_reel_queryset = clip_reel_queryset.select_related(
            "highlight"
        ).prefetch_related("involved_players")

        # Get sessions with prefetched clip reels using database-level grouping
        session_filter = {
            "clip_reels__generation_status__in": ["pending", "failed"],
            "clip_reels__is_default": is_default,
            "clip_reels__ratio__in": ratios,
        }
        if video_types is not None:
            session_filter["clip_reels__video_type__in"] = video_types

        sessions = (
            TraceSession.objects.filter(**session_filter)
            .prefetch_related(
                Prefetch(
                    "clip_reels",
                    queryset=clip_reel_queryset,
                    to_attr="pending_clip_reels",
                )
            )
            .distinct()
        )

        logger.info(f"Sessions: {sessions}")

        # Convert to sessions_data format, only including sessions with clip reels
        sessions_data = {}
        total_clip_reels = 0

        for session in sessions:
            if session.pending_clip_reels:  # Only include sessions with clip reels
                logger.info(
                    f"TraceClipReel: {session.pending_clip_reels} for session: {session.session_id}"
                )
                sessions_data[session.session_id] = {
                    "session": session,
                    "clip_reels": session.pending_clip_reels,
                }
                total_clip_reels += len(session.pending_clip_reels)

        if not sessions_data:
            logger.info("No clip reels to process")
            return {"success": True, "message": "No clip reels to process"}

        logger.info(
            f"Found {len(sessions_data)} sessions with {total_clip_reels} total clip reels to process"
        )

        # Initialize tracking data cache
        tracking_cache = TrackingDataCache()

        # Track all temporary files for cleanup
        temp_files_to_cleanup = []

        total_processed = 0
        total_failed = 0
        all_results = []

        # Process each session
        for session_key, session_data in sessions_data.items():
            session = session_data["session"]
            session_clip_reels = session_data["clip_reels"]

            logger.info(
                f"Processing session {session_key} with {len(session_clip_reels)} clip reels"
            )

            try:
                if session.blob_video_url:
                    logger.info(f"Session video available: {session.blob_video_url}")
                    # We'll extract segments per clip reel instead of downloading full video
                    session_video_url = session.blob_video_url
                else:
                    logger.error(f"No video URL available for session {session_key}")
                    # Mark all clip reels for this session as failed
                    for clip_reel in session_clip_reels:
                        clip_reel.mark_generation_failed("No video URL available")
                        total_failed += 1
                        all_results.append(
                            {
                                "clip_reel_id": str(clip_reel.id),
                                "highlight_id": clip_reel.highlight.highlight_id,
                                "video_type": clip_reel.video_type,
                                "status": "failed",
                                "error": "No video URL available",
                            }
                        )
                    continue

                # Process all clip reels for this session
                session_processed = 0
                session_failed = 0

                for clip_reel in session_clip_reels:
                    try:
                        logger.info(
                            f"Processing clip reel {clip_reel.id} for highlight {clip_reel.highlight.highlight_id}"
                        )

                        # Mark as generating
                        clip_reel.mark_generation_started()

                        # Extract video segment for this clip ree

                        segment_video_path, time_offset_ms = (
                            extract_video_segment_from_azure(
                                blob_url=session_video_url,
                                start_time_ms=clip_reel.start_ms,
                                duration_ms=clip_reel.duration_ms,
                            )
                        )
                        temp_files_to_cleanup.append(segment_video_path)

                        logger.info(
                            f"Extracted segment: {segment_video_path}, "
                            f"time offset: {time_offset_ms}ms"
                        )

                        # Determine overlay settings based on tags
                        ratio = clip_reel.ratio
                        tags = clip_reel.tags or []

                        # Determine overlay settings from tags
                        show_player_name = "with_name_overlay" in tags
                        with_circle = "with_circle_overlay" in tags
                        add_overlay = show_player_name or with_circle

                        logger.info(
                            f"Clip reel {clip_reel.id} (event_id={clip_reel.event_id}): "
                            f"ratio={ratio}, tags={tags}, "
                            f"show_player_name={show_player_name}, with_circle={with_circle}, add_overlay={add_overlay}"
                        )

                        # Generate overlay video using the segment video
                        # Pass time_offset_ms to normalize tracking data
                        # Aspect ratio is determined inside create_clip_reel_overlay_video from clip_reel.ratio
                        temp_video_path = create_clip_reel_overlay_video(
                            clip_reel,
                            tracking_cache,
                            session_video_path=segment_video_path,
                            time_offset_ms=time_offset_ms,
                            add_overlay=add_overlay,
                        )
                        temp_files_to_cleanup.append(temp_video_path)

                        # Clean up segment video after processing
                        if os.path.exists(segment_video_path):
                            os.unlink(segment_video_path)
                            temp_files_to_cleanup.remove(segment_video_path)

                        # Upload to storage
                        video_blob_url = upload_video_to_storage(
                            temp_video_path, clip_reel
                        )

                        # Calculate video file size
                        video_size_mb = os.path.getsize(temp_video_path) / (1024 * 1024)

                        # Mark as completed
                        clip_reel.mark_generation_completed(
                            video_url=video_blob_url,
                            video_size_mb=video_size_mb,
                            video_duration_seconds=clip_reel.duration_ms / 1000.0,
                        )

                        # Clean up the generated overlay video immediately
                        if os.path.exists(temp_video_path):
                            os.unlink(temp_video_path)
                            temp_files_to_cleanup.remove(temp_video_path)

                        session_processed += 1
                        all_results.append(
                            {
                                "clip_reel_id": str(clip_reel.id),
                                "highlight_id": clip_reel.highlight.highlight_id,
                                "video_type": clip_reel.video_type,
                                "status": "completed",
                                "video_url": video_blob_url,
                                "video_size_mb": video_size_mb,
                            }
                        )

                        logger.info(f"Successfully processed clip reel {clip_reel.id}")

                    except Exception as e:
                        logger.exception(
                            f"Error processing clip reel {clip_reel.id}: {e}"
                        )
                        clip_reel.mark_generation_failed(str(e))
                        session_failed += 1
                        all_results.append(
                            {
                                "clip_reel_id": str(clip_reel.id),
                                "highlight_id": clip_reel.highlight.highlight_id,
                                "video_type": clip_reel.video_type,
                                "status": "failed",
                                "error": str(e),
                            }
                        )

                # No need to clean up session video as we're using segments per clip reel

                total_processed += session_processed
                total_failed += session_failed

                logger.info(
                    f"Completed session {session_key}: {session_processed} processed, {session_failed} failed"
                )

            except Exception as e:
                logger.exception(f"Error processing session {session_key}: {e}")
                # Mark all remaining clip reels for this session as failed
                for clip_reel in session_clip_reels:
                    if clip_reel.generation_status == "generating":
                        clip_reel.mark_generation_failed(
                            f"Session processing error: {str(e)}"
                        )
                        total_failed += 1
                        all_results.append(
                            {
                                "clip_reel_id": str(clip_reel.id),
                                "highlight_id": clip_reel.highlight.highlight_id,
                                "video_type": clip_reel.video_type,
                                "status": "failed",
                                "error": f"Session processing error: {str(e)}",
                            }
                        )

        # Clear tracking cache
        tracking_cache.clear_cache()

        # Clean up any remaining temporary files
        cleanup_temp_files(temp_files_to_cleanup)

        logger.info(
            f"Overlay highlights generation completed. Processed: {total_processed}, Failed: {total_failed}"
        )

        return {
            "success": True,
            "processed": total_processed,
            "failed": total_failed,
            "total": total_processed + total_failed,
            "sessions_processed": len(sessions_data),
            "results": all_results,
        }

    except Exception as e:
        logger.exception(f"Error in generate_overlay_highlights_task: {e}")
        # Clean up any remaining temporary files on error
        if "temp_files_to_cleanup" in locals():
            cleanup_temp_files(temp_files_to_cleanup)
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
            logger.warning(
                f"Invalid team name: '{excel_team_name}'. Defaulting to 'away'."
            )
            return "away"

        excel_team_clean = excel_team_name.strip().lower()

        # Try exact match first
        if home_team_name and excel_team_clean == home_team_name.lower():
            return "home"
        elif away_team_name and excel_team_clean == away_team_name.lower():
            return "away"

        # Try partial match (in case of slight differences)
        if home_team_name and home_team_name.lower() in excel_team_clean:
            return "home"
        elif away_team_name and away_team_name.lower() in excel_team_clean:
            return "away"

        # Try reverse partial match
        if home_team_name and excel_team_clean in home_team_name.lower():
            return "home"
        elif away_team_name and excel_team_clean in away_team_name.lower():
            return "away"

        # If no match found, log warning and default to 'away'
        logger.warning(
            f"Could not determine team side for '{excel_team_name}'. "
            f"Session teams: home='{home_team_name}', away='{away_team_name}'. "
            f"Defaulting to 'away'."
        )
        return "away"

    except Exception as e:
        logger.error(
            f"Error determining team side for '{excel_team_name}': {e}",
            exc_info=True,
            stack_info=True,
        )
        return "away"


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
        if ":" in time_input:
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


def sync_language_field(obj, lang, field, value):
    """
    Safely sync any multilingual field into language_metadata JSON.

    Example:
        sync_language_field(team, "en", "name", "Maccabi Haifa")
        sync_language_field(team, "he", "name", "מכבי חיפה")
        sync_language_field(team, "en", "short_name", "MHA")
    """
    if not value:
        return

    if not obj.language_metadata:
        obj.language_metadata = {}

    if lang not in obj.language_metadata:
        obj.language_metadata[lang] = {}

    if obj.language_metadata[lang].get(field) != value:
        obj.language_metadata[lang][field] = value
        obj.save(update_fields=["language_metadata"])


def resolve_game(existing_game, en_name, he_name):
    """
    Resolve Game using TraceSession.game first.
    """
    if existing_game:
        sync_language_field(existing_game, "en", "name", en_name)
        sync_language_field(existing_game, "he", "name", he_name)
        return existing_game

    from games.models import Game

    game = Game.objects.filter(
        Q(name=en_name)
        | Q(name=he_name)
        | Q(language_metadata__en__name=en_name)
        | Q(language_metadata__he__name=he_name)
    ).first()

    if not game:
        game = Game.objects.create(name=en_name or he_name)

    sync_language_field(game, "en", "name", en_name)
    sync_language_field(game, "he", "name", he_name)

    return game


def resolve_team(existing_team, en_name, he_name):
    """
    Resolve team using TraceSession FK first.
    Create or find only if FK is missing.
    """
    # 1️⃣ FK exists → update language names
    if existing_team:
        sync_language_field(existing_team, "en", "name", en_name)
        sync_language_field(existing_team, "he", "name", he_name)
        return existing_team

    # 2️⃣ Search existing teams
    from teams.models import Team

    team = Team.objects.filter(
        Q(name=en_name)
        | Q(name=he_name)
        | Q(language_metadata__en__name=en_name)
        | Q(language_metadata__he__name=he_name)
    ).first()

    # 3️⃣ Create if not found
    if not team:
        team = Team.objects.create(name=en_name or he_name)

    sync_language_field(team, "en", "name", en_name)
    sync_language_field(team, "he", "name", he_name)

    return team


def update_trace_session_multilingual_data(match_data, session_id):
    """
    Update TraceSession, Team, and Game multilingual data using FK-first logic.
    """
    try:
        session = TraceSession.objects.select_related(
            "home_team", "away_team", "game"
        ).get(id=session_id)

        # --- Extract team names ---
        en_home = (
            match_data.get("en", {}).get("Match_summary", {}).get("match_home_team")
        )
        he_home = (
            match_data.get("he", {}).get("Match_summary", {}).get("match_home_team")
        )

        en_away = (
            match_data.get("en", {}).get("Match_summary", {}).get("match_away_team")
        )
        he_away = (
            match_data.get("he", {}).get("Match_summary", {}).get("match_away_team")
        )

        # --- Extract game names ---
        en_game = f"{en_home} vs {en_away}" if en_home and en_away else None
        he_game = f"{he_home} vs {he_away}" if he_home and he_away else None

        # --- Resolve Teams ---
        session.home_team = resolve_team(session.home_team, en_home, he_home)
        session.away_team = resolve_team(session.away_team, en_away, he_away)

        # --- Resolve Game ---
        session.game = resolve_game(session.game, en_game, he_game)

        # --- Save FK updates ---
        session.save(update_fields=["home_team", "away_team", "game"])

    except TraceSession.DoesNotExist:
        logger.error(f"TraceSession not found: {session_id}")

    except Exception as e:
        logger.exception(
            f"Failed to update multilingual data for TraceSession {session_id}"
        )


@shared_task
def process_excel_match_highlights_task(session_id, excel_file_path=None):
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

        # # Check if session is processed
        # if session.status != "processed":
        #     error_msg = f"Session {session_id} is not processed yet. Current status: {session.status}"
        #     logger.warning(error_msg)
        #     return {"success": False, "error": error_msg}

        # Determine Excel file path and download if needed
        temp_excel_path = None
        temp_files_to_cleanup = []  # Track all temporary files for cleanup

        try:
            if not excel_file_path:
                if not session.basic_game_stats:
                    error_msg = f"No Excel file provided and session {session_id} has no basic_game_stats file"
                    logger.error(error_msg)
                    return {"success": False, "error": error_msg}

                # Download Excel file from Azure Blob storage
                logger.info(
                    f"Downloading Excel file from session's basic_game_stats: {session.basic_game_stats.url}"
                )
                temp_excel_path = download_excel_file_from_storage(
                    session.basic_game_stats.url
                )
                excel_file_path = temp_excel_path
                temp_files_to_cleanup.append(temp_excel_path)
            else:
                # Use provided file path (for testing or direct file access)
                logger.info(f"Using provided Excel file path: {excel_file_path}")

            # Process the new Excel file with the new language extraction function
            try:
                from tracevision.utils import extract_multilingual_match_data

                match_data = extract_multilingual_match_data(excel_file_path)
                # Read the json file for now
                # match_data = os.path.join( os.path.dirname(__file__), "./data", "Gmae_Match_Detail Template_multilingual.json")
                # with open(match_data, "r", encoding="utf-8") as f:
                # match_data = json.load(f)
                logger.info(f"Successfully parsed Excel file: {excel_file_path}")
            except Exception as e:
                error_msg = f"Failed to process Excel file: {str(e)}"
                logger.error(error_msg, stack_info=True, exc_info=True)
                return {"success": False, "error": error_msg}

            # Update TraceSession, Game, and Team multilingual data
            logger.info(f"Updating multilingual data for session {session_id}...")
            try:
                update_trace_session_multilingual_data(match_data, session.id)
                logger.info("Successfully updated session multilingual data")
            except Exception as e:
                logger.error(
                    f"Error updating session multilingual data: {e}", exc_info=True
                )

        except Exception as e:
            # If there's an error during setup, clean up and re-raise
            cleanup_temp_files(temp_files_to_cleanup)
            raise

        # Normalize multilingual data and update players
        logger.info(f"Normalizing multilingual data...")
        try:
            from tracevision.utils import (
                normalize_multilingual_data,
                update_player_language_metadata,
                create_highlights_from_normalized_data,
            )

            normalized_data = normalize_multilingual_data(match_data)
            logger.info(
                f"Normalized data for {len(normalized_data['players'])} players"
            )

            # Update TracePlayer language_metadata
            logger.info(f"Updating TracePlayer language metadata...")
            player_update_result = update_player_language_metadata(
                session, normalized_data
            )
            logger.info(
                f"Player metadata updates: {player_update_result['updated_count']}/{player_update_result['total_players']} players updated"
            )

            # Create highlights and clip reels for goals and cards
            logger.info(f"Creating highlights from normalized data...")
            highlight_result = create_highlights_from_normalized_data(
                session, normalized_data
            )
            logger.info(
                f"Created {highlight_result['highlights_created']} highlights and "
                f"{highlight_result['clip_reels_created']} clip reels"
            )

        except Exception as e:
            error_msg = f"Error in multilingual processing: {e}"
            logger.error(error_msg, exc_info=True)
            return {"success": False, "error": error_msg}
        # Write match_data to a JSON file with proper spacing
        # output_json_path = None
        # try:
        #     output_dir = os.path.dirname(excel_file_path)
        #     output_json_path = os.path.join(
        #         output_dir, f"{session_id}_parsed_match_data.json")
        #     with open(output_json_path, "w", encoding="utf-8") as f:
        #         json.dump(match_data, f, indent=2, ensure_ascii=False)
        #     logger.info(f"Parsed match data written to {output_json_path}")
        #     # Add JSON file to cleanup list if it's in a temporary directory
        #     if temp_excel_path and output_json_path.startswith(os.path.dirname(temp_excel_path)):
        #         temp_files_to_cleanup.append(output_json_path)
        # except Exception as e:
        #     logger.error(f"Failed to write match_data to JSON: {e}")

        # Clean up all temporary files before returning
        cleanup_temp_files(temp_files_to_cleanup)

        result = {
            "success": True,
            "session_id": session_id,
            "player_updates": player_update_result,
            "highlights_created": highlight_result.get("highlights_created", 0),
            "clip_reels_created": highlight_result.get("clip_reels_created", 0),
            "errors": highlight_result.get("errors", []),
            "match_data_summary": {
                "total_players": len(normalized_data.get("players", [])),
                "total_teams": len(normalized_data.get("teams", [])),
                "players_updated": player_update_result.get("updated_count", 0),
                "players_not_found": player_update_result.get("not_found_count", 0),
            },
        }
        return result

    except Exception as e:
        # Clean up temporary files even if there's an error
        cleanup_temp_files(temp_files_to_cleanup)
        error_msg = f"Error in process_excel_match_highlights_task for session {session_id}: {str(e)}"
        logger.exception(error_msg)
        return {"success": False, "error": error_msg}
    # selected_language = models.CharField(max_length=15)
    # fcm_token = models.CharField(max_length=255)
    # we have WajoUserDevice to store FCM tokens