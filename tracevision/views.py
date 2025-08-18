import logging
import requests
from datetime import datetime

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status as http_status
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.permissions import IsAuthenticated
from django.conf import settings

from tracevision.models import TraceSession, TracePlayer
from tracevision.serializers import TraceVisionProcessesSerializer, TraceVisionProcessSerializer, TraceSessionListSerializer
from tracevision.services import TraceVisionService

logger = logging.getLogger()

CUSTOMER_ID = int(settings.TRACEVISION_CUSTOMER_ID)
API_KEY = settings.TRACEVISION_API_KEY
GRAPHQL_URL = settings.TRACEVISION_GRAPHQL_URL


class TraceVisionProcessesList(ListAPIView):
    serializer_class = TraceSessionListSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return TraceSession.objects.filter(user=self.request.user).order_by('-updated_at', '-created_at')
    
    def get_paginated_response(self, data):
        """
        Override to add custom response format
        """
        response = super().get_paginated_response(data)
        response.data['success'] = True
        return response


class TraceVisionProcessDetail(RetrieveAPIView):
    serializer_class = TraceVisionProcessesSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return TraceSession.objects.filter(user=self.request.user)


class TraceVisionProcessView(APIView):
    """
    API endpoint to trigger TraceVision session creation and video processing
    for a given TraceSession instance according to Figma requirements.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            data = {}
            # Add form data
            for key, value in request.data.items():
                data[key] = value

            if request.FILES:
                # Merge files into data, but handle the case where video_file might be in FILES
                for key, file_obj in request.FILES.items():
                    data[key] = file_obj
                    logger.info(f"Merged file {key}: {type(file_obj)}")

            serializer = TraceVisionProcessSerializer(data=data)
            if not serializer.is_valid():
                logger.error(
                    f"Serializer validation failed: {serializer.errors}")
                return Response({
                    "error": "Validation failed",
                    "details": serializer.errors
                }, status=http_status.HTTP_400_BAD_REQUEST)

            # Extract validated data
            video_link = serializer.validated_data.get('video_link')
            video_file = serializer.validated_data.get('video_file')
            home_team = serializer.validated_data['home_team_name']
            away_team = serializer.validated_data['away_team_name']
            home_color = serializer.validated_data['home_team_jersey_color']
            away_color = serializer.validated_data['away_team_jersey_color']
            final_score_str = serializer.validated_data['final_score']
            start_time = serializer.validated_data.get('start_time')
            
            # Parse the final score to get individual team scores
            home_score, away_score = map(int, final_score_str.split('-'))

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
                        "customer_id": CUSTOMER_ID,
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
                            }
                        },
                        "capabilities": ["tracking", "highlights"]
                    }
                }
            }

            session_response = requests.post(
                GRAPHQL_URL, headers={"Content-Type": "application/json"}, json=session_payload)
            session_json = session_response.json()
            logger.debug("Session response: %s", session_json)

            if session_response.status_code != 200 or not session_json.get("data", {}).get("createSession", {}).get("success"):
                return Response({
                    "error": "TraceVision session creation failed",
                    "details": session_json
                }, status=http_status.HTTP_400_BAD_REQUEST)

            session_id = session_json["data"]["createSession"]["session"]["session_id"]

            # Handle video processing based on input type
            if video_link:
                # Import video using the provided link
                logger.info("Importing video from link...")
                import_video_payload = {
                    "query": """
                        mutation ($token: CustomerToken!, $session_id: Int!, $video: ImportVideoInput!, $start_time: DateTime) {
                            importVideo(token: $token, session_id: $session_id, video: $video, start_time: $start_time) {
                                success
                                error
                            }
                        }
                    """,
                    "variables": {
                        "token": {
                            "customer_id": CUSTOMER_ID,
                            "token": API_KEY
                        },
                        "session_id": session_id,
                        "video": {
                            "type": "url",
                            "via_url": {
                                "url": video_link
                            }
                        },
                        "start_time": start_time.isoformat() if start_time else None
                    }
                }

                import_response = requests.post(GRAPHQL_URL, headers={
                                                "Content-Type": "application/json"}, json=import_video_payload)
                import_json = import_response.json()
                logger.info("Video import response: %s", import_json)

                if import_response.status_code != 200 or not import_json.get("data", {}).get("importVideo", {}).get("success"):
                    return Response({
                        "error": "Video import failed",
                        "details": import_json
                    }, status=http_status.HTTP_400_BAD_REQUEST)

                video_url_for_db = video_link

            else:
                logger.info("Processing video file upload...")
                # Get upload URL for file
                upload_payload = {
                    "query": """
                        mutation ($token: CustomerToken!, $session_id: Int!, $video_name: String!) {
                            uploadVideo(token: $token, session_id: $session_id, video_name: $video_name) {
                                success
                                error
                                upload_url
                            }
                        }
                    """,
                    "variables": {
                        "token": {
                            "customer_id": CUSTOMER_ID,
                            "token": API_KEY
                        },
                        "session_id": session_id,
                        "video_name": video_file.name
                    }
                }

                upload_response = requests.post(
                    GRAPHQL_URL, headers={"Content-Type": "application/json"}, json=upload_payload)
                upload_json = upload_response.json()
                logger.debug("Upload URL response: %s", upload_json)

                if upload_response.status_code != 200 or not upload_json.get("data", {}).get("uploadVideo", {}).get("success"):
                    return Response({
                        "error": "Failed to get video upload URL",
                        "details": upload_json
                    }, status=http_status.HTTP_400_BAD_REQUEST)

                upload_url = upload_json["data"]["uploadVideo"]["upload_url"]

                # Upload video file
                logger.info("Uploading video file to TraceVision...")
                put_response = requests.put(
                    upload_url, headers={"Content-Type": "video/mp4"}, data=video_file.read())

                if put_response.status_code != 200:
                    return Response({
                        "error": "Video upload failed",
                        "status_code": put_response.status_code,
                        "text": put_response.text
                    }, status=http_status.HTTP_400_BAD_REQUEST)

                video_url_for_db = upload_url

            # Save session to DB
            logger.info("Saving session data to DB...")
            session = TraceSession.objects.create(
                user=request.user,
                session_id=session_id,
                match_date=datetime.now().date(),
                home_team=home_team,
                away_team=away_team,
                home_score=home_score,
                away_score=away_score,
                video_url=video_url_for_db,
                status="waiting_for_data"  # Set initial status
            )

            return Response({
                "success": True,
                "id": session.id,
                "session_id": session.session_id,
                "message": "TraceVision session created and video processing started successfully",
                "video_source": "link" if video_link else "file_upload"
            }, status=http_status.HTTP_201_CREATED)

        except Exception as e:
            logger.exception(
                f"Error while processing TraceVision request: {str(e)}")
            return Response({
                "error": "Internal server error",
                "details": str(e)
            }, status=http_status.HTTP_500_INTERNAL_SERVER_ERROR)


class TraceVisionProcessResultView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            session = TraceSession.objects.get(id=pk, user=request.user)
            return Response(session.result, status=http_status.HTTP_200_OK)
        except TraceSession.DoesNotExist:
            return Response({"error": "Session not found"}, status=http_status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.exception(
                f"Error while fetching TraceVision result: {str(e)}")
            return Response({"error": "Internal server error"}, status=http_status.HTTP_500_INTERNAL_SERVER_ERROR)


class TraceVisionPollStatusView(APIView):
    """
    API endpoint to actively poll TraceVision API for latest session status and data.
    This is used when user refreshes the app to get real-time updates.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            # Get the session for the authenticated user
            session = TraceSession.objects.get(id=pk, user=request.user)

            # Check if user wants to force refresh cache
            force_refresh = request.query_params.get(
                'force_refresh', 'false').lower() == 'true'

            # Initialize service
            tracevision_service = TraceVisionService()

            # Get status data (with caching)
            status_data = tracevision_service.get_session_status(
                session, force_refresh=force_refresh)

            if not status_data:
                return Response({
                    "error": "Failed to retrieve status from TraceVision API",
                    "session_id": session.session_id
                }, status=http_status.HTTP_500_INTERNAL_SERVER_ERROR)

            new_status = status_data.get("status")
            previous_status = session.status

            # Update session status if it has changed
            if new_status and new_status != previous_status:
                session.status = new_status
                session.save()
                logger.info(
                    f"Updated session {session.session_id} status from {previous_status} to {new_status}")

                # If status changed to completed, fetch and save result data
                if new_status == "completed":
                    result_data = tracevision_service.get_session_result(
                        session)
                    if result_data:
                        session.result = result_data
                        session.save()
                        logger.info(
                            f"Updated result data for completed session {session.session_id}")

            # Prepare response data
            response_data = {
                "success": True,
                "id": session.id,
                "session_id": session.session_id,
                "status": session.status,
                "previous_status": previous_status,
                "status_updated": new_status != previous_status if new_status else False,
                "result": session.result,
                "match_date": session.match_date,
                "home_team": session.home_team,
                "away_team": session.away_team,
                "home_score": session.home_score,
                "away_score": session.away_score,
                "video_url": session.video_url,
                # "cached": status_data.get('cached', False),
                # "cache_timestamp": datetime.now().isoformat()
            }

            return Response(response_data, status=http_status.HTTP_200_OK)

        except TraceSession.DoesNotExist:
            return Response({"error": "Session not found"}, status=http_status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.exception(
                f"Error while polling TraceVision status: {str(e)}")
            return Response({"error": "Internal server error"}, status=http_status.HTTP_500_INTERNAL_SERVER_ERROR)


class TraceVisionSchedulerStatusView(APIView):
    """
    API endpoint to check the status of the TraceVision scheduler.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            from tracevision.scheduler import get_scheduler_status

            status = get_scheduler_status()

            if 'error' in status:
                return Response({
                    "error": "Failed to get scheduler status",
                    "details": status["error"]
                }, status=http_status.HTTP_500_INTERNAL_SERVER_ERROR)

            # Add environment info
            import os
            env = "development" if settings.DEBUG else "production"

            response_data = {
                "success": True,
                "scheduler_running": status['running'],
                "total_jobs": status['total_jobs'],
                "jobs": status['jobs'],
                "environment": env,
                "interval": "every minute" if env.lower() == 'development' else "every 2 hours",
                "timestamp": datetime.now().isoformat()
            }

            return Response(response_data, status=http_status.HTTP_200_OK)

        except Exception as e:
            logger.exception(
                f"Error while checking scheduler status: {str(e)}")
            return Response({
                "error": "Internal server error",
                "details": str(e)
            }, status=http_status.HTTP_500_INTERNAL_SERVER_ERROR)
