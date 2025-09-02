import os
import json
import logging
import requests
import mimetypes
import tempfile
from celery import shared_task
from django.db import transaction
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile

from tracevision.models import TraceSession, TraceObject, TraceHighlight, TraceHighlightObject
from tracevision.services import TraceVisionService
from tracevision.notification_service import NotificationService
from django.conf import settings

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
        file_name = f"{trace_object.object_id}_tracking_data.json"
        file_path = f"tracking_data/{session_id}/{file_name}"

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


@shared_task
def download_video_and_save_to_azure_blob(session_id, timeout=300):
    """
    Download video from TraceSession's video_url, upload to Azure Blob Storage,
    and save the blob URL back to the TraceSession.

    Args:
        session_id (int): TraceSession ID
        timeout (int): Request timeout in seconds (default 5 minutes for video)

    Returns:
        dict: Result containing success status, blob_url, and message
    """
    try:
        # Get the session from the database
        session = TraceSession.objects.get(id=session_id)

        # Check if already downloaded to prevent duplicates
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

        # Download video with streaming to handle large files
        response = requests.get(
            session.video_url, timeout=timeout, stream=True)
        response.raise_for_status()

        # Get content type and file extension
        content_type = response.headers.get('content-type', '')
        file_extension = mimetypes.guess_extension(content_type) or '.mp4'

        # Create proper file path structure for Azure blob storage
        file_name = f"{session.session_id}_video{file_extension}"
        file_path = f"videos/{session.session_id}/{file_name}"

        # Save to Azure Blob Storage with streaming
        logger.info(f"Uploading video to Azure blob: {file_path}")

        # Create a temporary file to store the video
        temp_file_path = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=file_extension) as temp_file:
                temp_file_path = temp_file.name
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        temp_file.write(chunk)
                temp_file.flush()

            # Read the temporary file and upload to blob storage
            with open(temp_file_path, 'rb') as video_file:
                file_content = ContentFile(video_file.read())
                saved_path = default_storage.save(file_path, file_content)

        finally:
            # Clean up temporary file with proper error handling
            if temp_file_path and os.path.exists(temp_file_path):
                try:
                    os.unlink(temp_file_path)
                except (OSError, PermissionError) as e:
                    logger.warning(
                        f"Could not delete temporary file {temp_file_path}: {e}")
                    # On Windows, sometimes files are still locked, try again after a short delay
                    import time
                    time.sleep(0.1)
                    try:
                        os.unlink(temp_file_path)
                    except (OSError, PermissionError):
                        logger.warning(
                            f"Failed to delete temporary file {temp_file_path} after retry")

        # Generate the full URL for the blob
        blob_url = default_storage.url(saved_path)

        # Update the TraceSession with the blob URL
        session.blob_video_url = blob_url
        session.save()

        # Log success with file size
        file_size_mb = os.path.getsize(
            saved_path) / (1024 * 1024) if os.path.exists(saved_path) else 0
        logger.info(
            f"Successfully downloaded video for session {session.session_id}: "
            f"Size: {file_size_mb:.2f} MB, saved to {blob_url}")

        return {
            'success': True,
            'blob_url': blob_url,
            'message': 'Downloaded and uploaded successfully',
            'file_size_mb': file_size_mb
        }

    except requests.exceptions.RequestException as e:
        logger.error(
            f"Failed to download video for session {session.session_id} from {session.video_url}: {e}")
        return {
            'success': False,
            'blob_url': None,
            'error': f"Network error: {str(e)}"
        }
    except Exception as e:
        logger.error(
            f"Error processing video for session {session.session_id}: {e}")
        return {
            'success': False,
            'blob_url': None,
            'error': f"Processing error: {str(e)}"
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
        file_name = f"{session.session_id}_result_data.json"
        file_path = f"session_results/{session.session_id}/{file_name}"

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

            # Clear existing data to avoid duplicates
            session.trace_objects.all().delete()
            session.highlights.all().delete()

            # Parse and create objects first
            objects_data = result_data.get('objects', [])
            trace_objects = []

            logger.info(f"Processing {len(objects_data)} objects")

            for obj_data in objects_data:
                # Create TraceObject
                trace_object = TraceObject(
                    object_id=obj_data.get('object_id'),
                    type=obj_data.get('type', ''),
                    side=obj_data.get('side', ''),
                    appearance_fv=obj_data.get('appearance_fv'),
                    color_fv=obj_data.get('color_fv'),
                    tracking_url=obj_data.get('tracking_url', ''),
                    role=obj_data.get('role'),
                    session=session,
                    user=session.user,
                )

                trace_objects.append(trace_object)

            # Bulk create objects first
            if trace_objects:
                created_objects = TraceObject.objects.bulk_create(
                    trace_objects)
                logger.info(f"Created {len(created_objects)} trace objects")

                # Now download tracking data for each object and update with blob URLs
                logger.info(
                    f"Downloading tracking data for {len(created_objects)} objects")
                updated_objects = []

                for trace_object in created_objects:
                    try:
                        # Download tracking data and get blob URL
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

                # Build object map for linking highlights to objects
                object_map = {obj.object_id: obj for obj in created_objects}

            # Parse and create highlights
            highlights_data = result_data.get('highlights', [])
            trace_highlights = []
            highlight_objects_bulk = []

            logger.info(f"Processing {len(highlights_data)} highlights")

            for highlight_data in highlights_data:
                # Create TraceHighlight
                trace_highlight = TraceHighlight(
                    highlight_id=highlight_data.get('highlight_id'),
                    video_id=highlight_data.get('video_id', 0),
                    start_offset=highlight_data.get('start_offset', 0),
                    duration=highlight_data.get('duration', 0),
                    tags=highlight_data.get('tags', []),
                    video_stream=highlight_data.get('video_stream', ''),
                    session=session,
                    user=session.user
                )
                trace_highlights.append(trace_highlight)

            # Bulk create highlights
            if trace_highlights:
                created_highlights = TraceHighlight.objects.bulk_create(
                    trace_highlights)
                logger.info(
                    f"Created {len(created_highlights)} trace highlights")

                # # Create highlight-object relationships
                # highlight_map = {h.highlight_id: h for h in created_highlights}

                for i, highlight_data in enumerate(highlights_data):
                    highlight_objects = highlight_data.get('objects', [])
                    created_highlight = created_highlights[i]

                    for obj_data in highlight_objects:
                        object_id = obj_data.get('object_id')
                        if object_id in object_map:
                            highlight_objects_bulk.append(TraceHighlightObject(
                                highlight=created_highlight,
                                trace_object=object_map[object_id]
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
def process_trace_sessions_task():
    """
    Celery task to process all TraceSession objects and update their status from TraceVision API.
    Create database notifications when status changes to "completed".
    """
    try:
        # Query all sessions that are not already processed or in error state
        sessions = TraceSession.objects.exclude(
            status__in=["processed", "process_error"])
        # sessions = TraceSession.objects.filter(id=trace_session_id)

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

        # Check if session has trace objects
        if not session.trace_objects.exists():
            error_msg = f"Session {session_id} has no trace objects. Run data parsing first."
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
        from cards.models import AttackingSkills, VideoCardDefensive, RPEMetrics, GPSAthleticSkills, GPSFootballAbilities
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

        # Save metrics to card models
        saved_metrics = []
        errors = []

        for player_metrics in metrics_result['metrics_calculated']:
            try:
                object_id = player_metrics['object_id']
                side = player_metrics['side']
                metrics = player_metrics['metrics']

                # Determine user - either from mapping or session user (for single player)
                if user_mapping and object_id in user_mapping:
                    try:
                        user = WajoUser.objects.get(id=user_mapping[object_id])
                    except WajoUser.DoesNotExist:
                        logger.warning(
                            f"User not found for object_id {object_id}, using session user")
                        user = session.user
                else:
                    user = session.user

                # Create/find associated game instance
                # Generate a unique game ID based on session info
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
                    saved_metrics.append(f"AttackingSkills for {object_id}")

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
                    saved_metrics.append(f"VideoCardDefensive for {object_id}")

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
                    saved_metrics.append(f"GPSAthleticSkills for {object_id}")

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
                        f"GPSFootballAbilities for {object_id}")

                logger.info(
                    f"Saved metrics for player {object_id} (user: {user.phone_no})")

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
            "players_processed": len(metrics_result['metrics_calculated']),
            "metrics_saved": saved_metrics,
            "errors": errors,
            "calculation_details": metrics_result
        }

        logger.info(f"Card metrics calculation completed for session {session_id}. "
                    f"Processed {len(metrics_result['metrics_calculated'])} players, "
                    f"saved {len(saved_metrics)} metric sets")

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
