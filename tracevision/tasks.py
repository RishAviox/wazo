import logging
from celery import shared_task
from django.conf import settings

from tracevision.models import TraceSession
from tracevision.services import TraceVisionService
from tracevision.notification_service import NotificationService

logger = logging.getLogger(__name__)


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
                        f"Session {session.session_id} {status_description}. Creating silent notification.")

                    # Create silent notification for both statuses
                    create_silent_notification(session)

                    # Fetch and save result data for both statuses (may contain error details for process_error)
                    result_data = tracevision_service.get_session_result(
                        session)
                    if result_data:
                        session.result = result_data
                        session.save()
                        logger.info(
                            f"Saved result data for {new_status} session {session.session_id}")
                    else:
                        logger.error(
                            f"Failed to fetch result for {new_status} session {session.session_id}")

                processed_count += 1

            except Exception as e:
                error_count += 1
                logger.exception(
                    f"Error processing session {session.session_id}: {e}")

        return f"Processed {processed_count} sessions, {error_count} errors"

    except Exception as e:
        logger.exception(f"Error in process_trace_sessions_task: {e}")
        raise
