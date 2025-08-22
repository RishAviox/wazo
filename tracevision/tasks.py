import logging
import requests
from celery import shared_task
from django.db import transaction
from django.db.models import Q

from tracevision.models import TraceSession, TraceObject, TraceHighlight, TraceHighlightObject, TrackingData
from tracevision.services import TraceVisionService
from tracevision.notification_service import NotificationService

logger = logging.getLogger(__name__)


def fetch_tracking_data_from_url(tracking_url, timeout=30):
    """
    Fetch tracking data from the provided URL.
    
    Args:
        tracking_url (str): URL to fetch tracking data from
        timeout (int): Request timeout in seconds
        
    Returns:
        list: Parsed tracking data points or empty list if failed
    """
    try:
        logger.info(f"Fetching tracking data from: {tracking_url}")
        response = requests.get(tracking_url, timeout=timeout)
        response.raise_for_status()
        
        tracking_data = response.json()
        # Log basic shape safely (TraceVision returns an object with 'spotlights')
        try:
            count = len(tracking_data.get('spotlights', [])) if isinstance(tracking_data, dict) else len(tracking_data)
            logger.info(f"Successfully fetched tracking payload, points={count}")
        except Exception:
            logger.info("Successfully fetched tracking payload")
        return tracking_data
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to fetch tracking data from {tracking_url}: {e}")
        return []
    except Exception as e:
        logger.error(f"Error parsing tracking data from {tracking_url}: {e}")
        return []


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
            logger.info(f"Starting to parse session data for session {session.session_id}")
            
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
                    tracking_data=[]  # Will be populated below
                )
                
                # Do not fetch or persist per-point tracking here. We keep tracking_url for on-demand use.
                
                trace_objects.append(trace_object)
            
            # Bulk create objects
            if trace_objects:
                created_objects = TraceObject.objects.bulk_create(trace_objects)
                logger.info(f"Created {len(created_objects)} trace objects")
                
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
                created_highlights = TraceHighlight.objects.bulk_create(trace_highlights)
                logger.info(f"Created {len(created_highlights)} trace highlights")
                
                # Create highlight-object relationships
                highlight_map = {h.highlight_id: h for h in created_highlights}
                
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
                    TraceHighlightObject.objects.bulk_create(highlight_objects_bulk)
                    logger.info(f"Created {len(highlight_objects_bulk)} highlight-object relationships")
            
            logger.info(f"Successfully parsed and stored all session data for session {session.session_id}")
            return True
            
    except Exception as e:
        logger.exception(f"Error parsing session data for session {session.session_id}: {e}")
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


@shared_task(bind=True, name='tracevision.process_trace_sessions')
def process_trace_sessions_task(self):
    """
    Celery task to process all TraceSession objects and update their status from TraceVision API.
    Create database notifications when status changes to "completed".
    """
    try:
        # Query all sessions that are not already processed or in error state
        sessions = TraceSession.objects.exclude(
            status__in=["processed", "process_error"])

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
                    result_data = tracevision_service.get_session_result(session)
                    if result_data:
                        session.result = result_data
                        
                        # For processed sessions, parse and store structured data
                        if new_status == "processed":
                            logger.info(f"Parsing structured data for session {session.session_id}")
                            parsing_success = parse_and_store_session_data(session, result_data)
                            
                            if parsing_success:
                                logger.info(f"Successfully parsed structured data for session {session.session_id}")
                                # Only save session and create notification if parsing was successful
                                session.save()
                                create_silent_notification(session)

                                # Enqueue aggregates computation (idempotent)
                                try:
                                    from tracevision.tasks import compute_aggregates_task
                                    compute_aggregates_task.delay(session.session_id)
                                    logger.info(f"Queued aggregates computation for session {session.session_id}")
                                except Exception as e:
                                    logger.exception(f"Failed to enqueue aggregates for session {session.session_id}: {e}")
                            else:
                                logger.error(f"Failed to parse structured data for session {session.session_id}. Not updating session status.")
                                # Don't update the session status if parsing failed
                                session.status = previous_status
                                session.save()
                                continue
                        else:
                            # For process_error, just save the result data
                            session.save()
                            create_silent_notification(session)
                        
                        logger.info(f"Saved result data for {new_status} session {session.session_id}")
                    else:
                        logger.error(f"Failed to fetch result for {new_status} session {session.session_id}")
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


@shared_task(bind=True, name='tracevision.reprocess_session_data')
def reprocess_session_data_task(self, session_id=None, force_reprocess=False):
    """
    Celery task to reprocess/test the parsing of session data for already processed sessions.
    Useful for testing new parsing functionality or reprocessing sessions that failed parsing.
    
    Args:
        session_id (str, optional): Specific session ID to reprocess. If None, reprocess all eligible sessions.
        force_reprocess (bool): If True, reprocess even if structured data already exists.
    
    Returns:
        str: Status message
    """
    try:
        if session_id:
            # Process a specific session
            try:
                session = TraceSession.objects.get(session_id=session_id)
                sessions = [session]
                logger.info(f"Reprocessing specific session: {session_id}")
            except TraceSession.DoesNotExist:
                error_msg = f"Session with ID {session_id} not found"
                logger.error(error_msg)
                return error_msg
        else:
            # Find sessions that are processed but might need data parsing
            if force_reprocess:
                sessions = TraceSession.objects.filter(status="processed")
                logger.info("Force reprocessing all processed sessions")
            else:
                # Find sessions that are processed but have no structured data
                sessions = TraceSession.objects.filter(
                    status="processed"
                ).filter(
                    Q(trace_objects__isnull=True) | Q(highlights__isnull=True)
                ).distinct()
                logger.info("Reprocessing sessions without structured data")

        if not sessions:
            return "No sessions found to reprocess"

        logger.info(f"Found {len(sessions)} sessions to reprocess")

        processed_count = 0
        error_count = 0
        skipped_count = 0

        for session in sessions:
            try:
                logger.info(f"Reprocessing session: {session.session_id}")
                
                # Check if session has result data
                if not session.result:
                    logger.warning(f"Session {session.session_id} has no result data. Fetching from API...")
                    tracevision_service = TraceVisionService()
                    result_data = tracevision_service.get_session_result(session)
                    
                    if not result_data:
                        logger.error(f"Failed to fetch result data for session {session.session_id}")
                        error_count += 1
                        continue
                    
                    session.result = result_data
                    session.save()
                    logger.info(f"Fetched and saved result data for session {session.session_id}")
                else:
                    result_data = session.result

                # Check if structured data already exists (unless force_reprocess is True)
                if not force_reprocess:
                    has_objects = session.trace_objects.exists()
                    has_highlights = session.highlights.exists()
                    
                    if has_objects and has_highlights:
                        logger.info(f"Session {session.session_id} already has structured data. Skipping.")
                        skipped_count += 1
                        continue

                # Parse and store structured data
                logger.info(f"Parsing structured data for session {session.session_id}")
                parsing_success = parse_and_store_session_data(session, result_data)
                
                if parsing_success:
                    logger.info(f"Successfully reprocessed session {session.session_id}")
                    processed_count += 1
                else:
                    logger.error(f"Failed to reprocess session {session.session_id}")
                    error_count += 1

            except Exception as e:
                error_count += 1
                logger.exception(f"Error reprocessing session {session.session_id}: {e}")

        result_msg = f"Reprocessed {processed_count} sessions, {error_count} errors, {skipped_count} skipped"
        logger.info(result_msg)
        return result_msg

    except Exception as e:
        logger.exception(f"Error in reprocess_session_data_task: {e}")
        raise


@shared_task(bind=True, name='tracevision.test_single_session_parsing')
def test_single_session_parsing_task(self, session_id):
    """
    Celery task specifically for testing the parsing function on a single session.
    This task will not modify the original session data and will provide detailed logging.
    
    Args:
        session_id (str): Session ID to test parsing on
    
    Returns:
        dict: Detailed results of the parsing test
    """
    try:
        # Get the session
        try:
            session = TraceSession.objects.get(session_id=session_id)
        except TraceSession.DoesNotExist:
            error_msg = f"Session with ID {session_id} not found"
            logger.error(error_msg)
            return {"success": False, "error": error_msg}

        logger.info(f"Testing parsing for session: {session_id}")
        
        # Check if session has result data
        if not session.result:
            logger.warning(f"Session {session.session_id} has no result data. Fetching from API...")
            tracevision_service = TraceVisionService()
            result_data = tracevision_service.get_session_result(session)
            
            if not result_data:
                error_msg = f"Failed to fetch result data for session {session.session_id}"
                logger.error(error_msg)
                return {"success": False, "error": error_msg}
        else:
            result_data = session.result

        # Count existing data before test
        existing_objects = session.trace_objects.count()
        existing_highlights = session.highlights.count()
        existing_tracking_data = TrackingData.objects.filter(trace_object__session=session).count()

        logger.info(f"Before test - Objects: {existing_objects}, Highlights: {existing_highlights}, Tracking Data: {existing_tracking_data}")

        # Test the parsing function
        parsing_success = parse_and_store_session_data(session, result_data)
        
        # Count data after test
        new_objects = session.trace_objects.count()
        new_highlights = session.highlights.count()
        new_tracking_data = TrackingData.objects.filter(trace_object__session=session).count()

        logger.info(f"After test - Objects: {new_objects}, Highlights: {new_highlights}, Tracking Data: {new_tracking_data}")

        result = {
            "success": parsing_success,
            "session_id": session_id,
            "before": {
                "objects": existing_objects,
                "highlights": existing_highlights,
                "tracking_data": existing_tracking_data
            },
            "after": {
                "objects": new_objects,
                "highlights": new_highlights,
                "tracking_data": new_tracking_data
            },
            "created": {
                "objects": new_objects - existing_objects,
                "highlights": new_highlights - existing_highlights,
                "tracking_data": new_tracking_data - existing_tracking_data
            }
        }

        if parsing_success:
            logger.info(f"Successfully tested parsing for session {session_id}: {result}")
        else:
            logger.error(f"Failed to test parsing for session {session_id}")

        return result

    except Exception as e:
        error_msg = f"Error testing session {session_id}: {str(e)}"
        logger.exception(error_msg)
        return {"success": False, "error": error_msg}


@shared_task(bind=True, name='tracevision.calculate_player_stats')
def calculate_player_stats_task(self, session_id):
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
        
        logger.info(f"Starting player stats calculation for session: {session_id}")
        
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


@shared_task(bind=True, name='tracevision.recalculate_player_stats')
def recalculate_player_stats_task(self, session_id, force_recalculate=False):
    """
    Celery task to recalculate player statistics for an existing session.
    Useful for testing new calculation algorithms or fixing data issues.
    
    Args:
        session_id (str): Session ID to recalculate stats for
        force_recalculate (bool): If True, recalculate even if stats already exist
        
    Returns:
        dict: Task results with success status and details
    """
    try:
        from tracevision.services import TraceVisionStatsService
        from tracevision.models import TraceVisionPlayerStats
        
        # Get the session
        try:
            session = TraceSession.objects.get(session_id=session_id)
        except TraceSession.DoesNotExist:
            error_msg = f"Session with ID {session_id} not found"
            logger.error(error_msg)
            return {"success": False, "error": error_msg}
        
        logger.info(f"Starting player stats recalculation for session: {session_id}")
        
        # Check if stats already exist (unless force_recalculate is True)
        if not force_recalculate and TraceVisionPlayerStats.objects.filter(session=session).exists():
            existing_stats_count = TraceVisionPlayerStats.objects.filter(session=session).count()
            logger.info(f"Session {session_id} already has {existing_stats_count} player stats. "
                       f"Use force_recalculate=True to override.")
            return {
                "success": False,
                "error": f"Stats already exist for {existing_stats_count} players. Use force_recalculate=True to override.",
                "existing_stats_count": existing_stats_count
            }
        
        # Clear existing stats if force_recalculate is True
        if force_recalculate:
            deleted_count = TraceVisionPlayerStats.objects.filter(session=session).delete()[0]
            logger.info(f"Deleted {deleted_count} existing player stats for session {session_id}")
        
        # Initialize stats service
        stats_service = TraceVisionStatsService()
        
        # Calculate all statistics
        result = stats_service.calculate_session_stats(session)
        
        if result['success']:
            logger.info(f"Successfully recalculated stats for session {session_id}: "
                       f"{result['player_stats_count']} players processed")
            
            return {
                "success": True,
                "session_id": session_id,
                "player_stats_count": result['player_stats_count'],
                "team_stats": result['team_stats'],
                "session_stats": result['session_stats'],
                "message": f"Stats recalculation completed for {result['player_stats_count']} players",
                "force_recalculated": force_recalculate
            }
        else:
            error_msg = f"Stats recalculation failed for session {session_id}: {result.get('error', 'Unknown error')}"
            logger.error(error_msg)
            return {"success": False, "error": error_msg}
            
    except Exception as e:
        error_msg = f"Error in recalculate_player_stats_task for session {session_id}: {str(e)}"
        logger.exception(error_msg)
        return {"success": False, "error": error_msg}


@shared_task(bind=True, name='tracevision.compute_aggregates')
def compute_aggregates_task(self, session_id):
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
        logger.exception(f"Error computing aggregates for session {session_id}: {e}")
        return {"success": False, "error": str(e)}


@shared_task(bind=True, name='tracevision.reconcile_aggregates_for_processed_sessions')
def reconcile_aggregates_for_processed_sessions(self, lookback_hours=24, batch_limit=50):
    """Scan recently processed sessions and ensure aggregates exist; enqueue if missing."""
    try:
        from django.utils import timezone
        from datetime import timedelta
        from tracevision.models import TraceCoachReportTeam

        cutoff = timezone.now() - timedelta(hours=lookback_hours)
        qs = TraceSession.objects.filter(status='processed', updated_at__gte=cutoff).order_by('-updated_at')[:batch_limit]
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