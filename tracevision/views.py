import logging
import requests
import json

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status as http_status
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.permissions import IsAuthenticated

from django.conf import settings

from .models import TraceSession, TracePlayer
from .serializers import TraceVisionProcessesSerializer

logger = logging.getLogger()

CUSTOMER_ID = settings.TRACEVISION_CUSTOMER_ID
API_KEY = settings.TRACEVISION_API_KEY
GRAPHQL_URL = settings.TRACEVISION_GRAPHQL_URL


class TraceVisionProcessesList(ListAPIView):
    serializer_class = TraceVisionProcessesSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return TraceSession.objects.filter(user=self.request.user)


class TraceVisionProcessDetail(RetrieveAPIView):
    serializer_class = TraceVisionProcessesSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return TraceSession.objects.filter(user=self.request.user)


class TraceVisionProcessView(APIView):
    """
    API endpoint to trigger TraceVision session creation and video upload
    for a given MatchDataTracevision instance.
    """

    def post(self, request):
        try:
            trace_data = json.loads(request.data.get('data'))

            # Extract metadata
            match_date = trace_data.get("match_date")
            start_time = trace_data.get("start_time")
            home_team = trace_data.get("home_team", "Home")
            away_team = trace_data.get("away_team", "Away")
            home_color = trace_data.get("home_color", "#0000ff")
            away_color = trace_data.get("away_color", "#ff0000")
            home_score = trace_data.get("home_score", 0)
            away_score = trace_data.get("away_score", 0)
            players = trace_data.get("players", [])

            # Validate and fetch video file
            if "video" not in request.FILES:
                return Response({"error": "Video file not provided"}, status=http_status.HTTP_400_BAD_REQUEST)

            video_file = request.FILES["video"]
            video_file_name = video_file.name

            # Step 1: Create TraceVision session
            logger.info("Creating TraceVision session...")
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
                    "token": {
                        "customer_id": int(CUSTOMER_ID),
                        "token": API_KEY
                    },
                    "sessionData": {
                        "type": "soccer_game",
                        "game_info": {
                            "home_team": {
                                "name": home_team,
                                "score": home_score,
                                "color": home_color
                            },
                            "away_team": {
                                "name": away_team,
                                "score": away_score,
                                "color": away_color
                            },
                            "start_time": start_time
                        },
                        "capabilities": ["tracking", "highlights"]
                    }
                }
            }

            session_response = requests.post(GRAPHQL_URL, headers={"Content-Type": "application/json"}, json=session_payload)
            session_json = session_response.json()
            logger.debug("Session response: %s", session_json)

            if session_response.status_code != 200 or not session_json.get("data", {}).get("createSession", {}).get("success"):
                return Response({"error": "TraceVision session creation failed", "details": session_json}, status=http_status.HTTP_400_BAD_REQUEST)

            session_id = session_json["data"]["createSession"]["session"]["session_id"]

            # Step 2: Get upload URL
            logger.info("Getting upload URL...")
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
                    "token": {
                        "customer_id": int(CUSTOMER_ID),
                        "token": API_KEY
                    },
                    "session_id": session_id,
                    "video_name": video_file_name,
                    "start_time": start_time
                }
            }

            upload_response = requests.post(GRAPHQL_URL, headers={"Content-Type": "application/json"}, json=upload_payload)
            upload_json = upload_response.json()
            logger.debug("Upload URL response: %s", upload_json)

            if upload_response.status_code != 200 or not upload_json.get("data", {}).get("uploadVideo", {}).get("success"):
                return Response({"error": "Failed to get video upload URL", "details": upload_json}, status=http_status.HTTP_400_BAD_REQUEST)

            upload_url = upload_json["data"]["uploadVideo"]["upload_url"]

            # Step 3: Upload video
            logger.info("Uploading video to TraceVision...")
            put_response = requests.put(upload_url, headers={"Content-Type": "video/mp4"}, data=video_file.read())

            if put_response.status_code != 200:
                return Response({
                    "error": "Video upload failed",
                    "status_code": put_response.status_code,
                    "text": put_response.text
                }, status=http_status.HTTP_400_BAD_REQUEST)

            # Step 4: Save session and players to DB
            logger.info("Saving session and player data to DB...")
            session = TraceSession.objects.create(
                user=request.user,
                session_id=session_id,
                match_date=match_date,
                home_team=home_team,
                away_team=away_team,
                home_score=home_score,
                away_score=away_score,
                video_url=upload_url
            )

            TracePlayer.objects.bulk_create([
                TracePlayer(
                    name=player.get("name"),
                    jersey_number=player.get("jersey_number"),
                    position=player.get("position"),
                    team=player.get("team"),
                    session=session
                )
                for player in players
            ])

            return Response({"success": True, "session_id": session_id}, status=http_status.HTTP_201_CREATED)

        except Exception as e:
            logger.exception(f"Error while processing TraceVision request: {str(e)}")
            return Response({"error": "Internal server error"}, status=http_status.HTTP_500_INTERNAL_SERVER_ERROR)
