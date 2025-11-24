import logging
import traceback
import requests

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings

from .models import MatchDataTracevision, TraceSession, TracePlayer

# Configure logger for this module
logger = logging.getLogger()

# Constants from settings
CUSTOMER_ID = settings.TRACEVISION_CUSTOMER_ID
API_KEY = settings.TRACEVISION_API_KEY
GRAPHQL_URL = settings.TRACEVISION_GRAPHQL_URL


@receiver(post_save, sender=MatchDataTracevision)
def upload_video_and_create_trace_data(sender, instance, created, **kwargs):
    """
    Signal handler triggered after a MatchDataTracevision instance is saved.

    If a new instance is created with an associated video, this function:
    - Creates a session on TraceVision
    - Retrieves a video upload URL
    - Uploads the video
    - Saves session and player info to local database
    """
    if not created or not instance.video:
        return

    try:
        trace_data = instance.data or {}

        # Extract match and team metadata
        match_date = trace_data.get("match_date")
        start_time = trace_data.get("start_time")
        home_team = trace_data.get("home_team", "Home")
        away_team = trace_data.get("away_team", "Away")
        home_color = trace_data.get("home_color", "#0000ff")
        away_color = trace_data.get("away_color", "#ff0000")
        home_score = trace_data.get("home_score", 0)
        away_score = trace_data.get("away_score", 0)
        players = trace_data.get("players", [])

        # Step 1: Create TraceVision Session
        logger.info("Step 1: Creating session on TraceVision...")
        session_payload = {
            "query": """
                mutation ($token: CustomerToken!, $sessionData: SessionCreateInput!) {
                    createSession(token: $token, sessionData: $sessionData) {
                        session { session_id }
                        success
                        error
                    }
                }
            """,
            "variables": {
                "token": {"customer_id": int(CUSTOMER_ID), "token": API_KEY},
                "sessionData": {
                    "type": "soccer_game",
                    "game_info": {
                        "home_team": {
                            "name": home_team,
                            "score": home_score,
                            "color": home_color,
                        },
                        "away_team": {
                            "name": away_team,
                            "score": away_score,
                            "color": away_color,
                        },
                        "start_time": start_time,
                    },
                    "capabilities": ["tracking", "highlights"],
                },
            },
        }

        session_response = requests.post(
            GRAPHQL_URL,
            headers={"Content-Type": "application/json"},
            json=session_payload,
        )
        session_json = session_response.json()

        logger.debug("Session creation response: %s", session_json)
        print(session_json)

        if session_response.status_code != 200 or not session_json.get("data", {}).get(
            "createSession", {}
        ).get("success"):
            logger.error("Session creation failed: %s", session_json)
            return

        session_id = session_json["data"]["createSession"]["session"]["session_id"]

        # Step 2: Get video upload URL
        logger.info("Step 2: Requesting video upload URL...")
        upload_payload = {
            "query": """
                mutation ($token: CustomerToken!, $session_id: Int!, $video_name: String!, $start_time: DateTime) {
                    uploadVideo(token: $token, session_id: $session_id, video_name: $video_name, start_time: $start_time) {
                        upload_url
                        success
                        error
                    }
                }
            """,
            "variables": {
                "token": {"customer_id": int(CUSTOMER_ID), "token": API_KEY},
                "session_id": session_id,
                "video_name": instance.video.name,
                "start_time": start_time,
            },
        }

        upload_response = requests.post(
            GRAPHQL_URL,
            headers={"Content-Type": "application/json"},
            json=upload_payload,
        )
        upload_json = upload_response.json()

        logger.debug("Upload URL response: %s", upload_json)

        if upload_response.status_code != 200 or not upload_json.get("data", {}).get(
            "uploadVideo", {}
        ).get("success"):
            logger.error("Failed to get upload URL: %s", upload_json)
            return

        upload_url = upload_json["data"]["uploadVideo"]["upload_url"]

        # Step 3: Upload the video using PUT request
        logger.info("Step 3: Uploading video to TraceVision...")
        with instance.video.open("rb") as video_file:
            upload_result = requests.put(
                upload_url, headers={"Content-Type": "video/mp4"}, data=video_file
            )

        if upload_result.status_code != 200:
            logger.error(
                "Video upload failed (%s): %s",
                upload_result.status_code,
                upload_result.text,
            )
            return

        # Step 4: Save TraceSession to local DB
        logger.info("Saving TraceSession to local database...")
        session = TraceSession.objects.create(
            match_data=instance,
            session_id=session_id,
            match_date=match_date,
            home_team=home_team,
            away_team=away_team,
            home_score=home_score,
            away_score=away_score,
        )

        # Step 5: Save players linked to session
        TracePlayer.objects.bulk_create(
            [
                TracePlayer(
                    name=player.get("name"),
                    jersey_number=player.get("jersey_number"),
                    position=player.get("position"),
                    team=player.get("team"),
                    session=session,
                )
                for player in players
            ]
        )

        logger.info("Trace session, video, and player data saved successfully.")

    except Exception as e:
        logger.exception(
            "Unhandled exception during TraceVision processing:\n%s",
            traceback.format_exc(),
        )
