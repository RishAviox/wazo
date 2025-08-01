import logging
import requests

from django.conf import settings
from apscheduler.schedulers.background import BackgroundScheduler
from django_apscheduler.jobstores import DjangoJobStore, register_events

from tracevision.models import TraceSession

logger = logging.getLogger(__name__)

def process_trace_sessions():
    CUSTOMER_ID = int(settings.TRACEVISION_CUSTOMER_ID)
    API_KEY = settings.TRACEVISION_API_KEY
    GRAPHQL_URL = settings.TRACEVISION_GRAPHQL_URL

    sessions = TraceSession.objects.exclude(status__in=["processed", "process_error"])
    if not sessions.exists():
        logger.info("All sessions are already processed.")
        return

    for session in sessions:
        try:
            logger.info(f"Checking session status for ID: {session.session_id}")
            status_payload = {
                "query": """
                    query ($token: CustomerToken!, $session_id: Int!) {
                        session(token: $token, session_id: $session_id) {
                            session_id type status
                        }
                    }
                """,
                "variables": {
                    "token": {"customer_id": CUSTOMER_ID, "token": API_KEY},
                    "session_id": int(session.session_id),
                },
            }

            res = requests.post(GRAPHQL_URL, headers={"Content-Type": "application/json"}, json=status_payload)
            data = res.json().get("data", {}).get("session", {})

            if res.status_code != 200 or not data.get("status"):
                logger.error(f"Failed to retrieve status for session {session.session_id}")
                continue

            session_status = data["status"]

            if session_status == "processed":
                logger.info(f"Session {session.session_id} is processed. Fetching result...")

                result_payload = {
                    "query": """
                        query ($token: CustomerToken!, $session_id: Int!) {
                            sessionResult(token: $token, session_id: $session_id) {
                                objects { object_id type side tracking_url }
                                highlights { highlight_id video_id start_offset duration tags video_stream }
                            }
                        }
                    """,
                    "variables": {
                        "token": {"customer_id": CUSTOMER_ID, "token": API_KEY},
                        "session_id": int(session.session_id),
                    },
                }

                result_response = requests.post(GRAPHQL_URL, headers={"Content-Type": "application/json"}, json=result_payload)
                result_data = result_response.json().get("data", {}).get("sessionResult")

                if result_response.status_code != 200 or not result_data:
                    logger.error(f"Failed to fetch result for session {session.session_id}")
                    continue

                session.status = session_status
                session.result = result_data
                session.save()
                logger.info(f"Session {session.session_id} marked as processed and saved.")

            else:
                session.status = session_status
                session.save()
                logger.info(f"Updated session {session.session_id} status to {session_status}")

        except Exception as e:
            logger.exception(f"Error processing session {session.session_id}: {e}")


# Scheduler for processing trace sessions, started in apps.py
scheduler = BackgroundScheduler()

def start_scheduler():
    scheduler.add_jobstore(DjangoJobStore(), "default")
    scheduler.add_job(
        process_trace_sessions,
        trigger='interval',
        hours=2,
        id='trace_session_processor',
        max_instances=1,
        replace_existing=True
    )
    register_events(scheduler)
    scheduler.start()

