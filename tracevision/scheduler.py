import logging
import os
from django.conf import settings
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from django_apscheduler.jobstores import DjangoJobStore, register_events

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


def process_trace_sessions():
    """
    Process all TraceSession objects and update their status from TraceVision API.
    Create database notifications when status changes to "completed".
    """
    # Query all sessions that are not already processed or in error state
    sessions = TraceSession.objects.exclude(
        status__in=["processed", "process_error"])

    if not sessions.exists():
        logger.info("All sessions are already processed or in final state.")
        return

    logger.info(f"Found {sessions.count()} sessions to process")

    # Initialize service
    tracevision_service = TraceVisionService()

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
                result_data = tracevision_service.get_session_result(session)
                if result_data:
                    session.result = result_data
                    session.save()
                    logger.info(
                        f"Saved result data for {new_status} session {session.session_id}")
                else:
                    logger.error(
                        f"Failed to fetch result for {new_status} session {session.session_id}")

        except Exception as e:
            logger.exception(
                f"Error processing session {session.session_id}: {e}")


# Scheduler for processing trace sessions, started in apps.py
scheduler = BackgroundScheduler()


def start_scheduler():
    """
    Start the TraceVision scheduler with configurable intervals.
    Development: Every minute
    Production: Every 2 hours
    """
    try:
        pass
        # Check if we're in development or production
        # is_development = settings.DEBUG == True

        # if is_development:
        #     # Development: Run every minute for testing
        #     trigger = CronTrigger(minute="*")  # Every minute
        #     interval_description = "every minute"
        #     logger.info("Starting scheduler in DEVELOPMENT mode")
        # else:
        #     # Production: Run every 2 hours
        #     trigger = CronTrigger(hour="*/2")  # Every 2 hours
        #     interval_description = "every 2 hours"
        #     logger.info("Starting scheduler in PRODUCTION mode")

        # scheduler.add_jobstore(DjangoJobStore(), "default")

        # # Add the job with appropriate trigger
        # scheduler.add_job(
        #     process_trace_sessions,
        #     trigger=trigger,
        #     id='trace_session_processor',
        #     max_instances=1,
        #     replace_existing=True
        # )

        # register_events(scheduler)
        # scheduler.start()

        # logger.info(
        #     f"✅ TraceVision scheduler started successfully - running {interval_description}")
        # logger.info(f"📋 Total jobs in scheduler: {len(scheduler.get_jobs())}")

        # # Log next run time
        # job = scheduler.get_job('trace_session_processor')
        # if job:
        #     logger.info(f"⏰ Next run time: {job.next_run_time}")

    except Exception as e:
        logger.error(f"❌ Failed to start scheduler: {e}")
        raise


def get_scheduler_status():
    """
    Get the current status of the scheduler.
    Returns a dictionary with scheduler information.
    """
    try:
        status = {
            'running': scheduler.running,
            'total_jobs': len(scheduler.get_jobs()),
            'jobs': []
        }

        for job in scheduler.get_jobs():
            job_info = {
                'id': job.id,
                'name': job.name,
                'func': str(job.func),
                'next_run_time': str(job.next_run_time) if job.next_run_time else 'None',
                'trigger': str(job.trigger)
            }
            status['jobs'].append(job_info)

        return status

    except Exception as e:
        logger.error(f"Error getting scheduler status: {e}")
        return {'error': str(e)}
