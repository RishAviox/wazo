import logging
import requests
from datetime import datetime
from django.db.models import JSONField   # Postgres native
from tracevision.models import TraceClipReel, TraceSession
from teams.models import Team
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status as http_status
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.permissions import IsAuthenticated
from django.conf import settings
from tracevision.tasks import download_video_and_save_to_azure_blob, generate_overlay_highlights_task
from datetime import datetime 
from datetime import timedelta


from tracevision.models import TraceSession, TracePlayer
from tracevision.serializers import TraceVisionProcessesSerializer, TraceVisionProcessSerializer, TraceSessionListSerializer, TraceClipReelSerializer, CoachViewSpecificTeamPlayersSerializer
from tracevision.services import TraceVisionService
from teams.models import Team


from rest_framework.pagination import PageNumberPagination


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

            serializer = TraceVisionProcessSerializer(data=request.data)
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
            # Get age_group with SENIOR as fallback
            age_group = serializer.validated_data.get('age_group') or 'SENIOR'
            
            # Handle custom pitch dimensions
            pitch_length = serializer.validated_data.get('pitch_length')
            pitch_width = serializer.validated_data.get('pitch_width')
            match_start_time = serializer.validated_data.get('match_start_time')
            first_half_end_time = serializer.validated_data.get('first_half_end_time')
            second_half_start_time = serializer.validated_data.get('second_half_start_time')
            match_end_time = serializer.validated_data.get('match_end_time')
            basic_game_stats = serializer.validated_data.get('basic_game_stats')
            print(type(basic_game_stats))
            
            # Set pitch size (custom or default based on age group)
            if pitch_length and pitch_width:
                pitch_size = {'length': pitch_length, 'width': pitch_width}
            else:
                # Use default pitch size for the age group
                from tracevision.models import TraceSession
                pitch_size = TraceSession.DEFAULT_PITCH_SIZES.get(age_group, TraceSession.DEFAULT_PITCH_SIZES['SENIOR'])
            
            # Parse the final score to get individual team scores
            home_score, away_score = map(int, final_score_str.split('-'))

            logger.info("Getting or creating Team objects...")          
            # Get or create home team using name and jersey color as unique identifier
            home_team_obj, _ = Team.objects.get_or_create(
                name=home_team,
                jersey_color=home_color,
                defaults={
                    'name': home_team,
                    'jersey_color': home_color
                }
            )
            
            # Get or create team
            away_team_obj, _ = Team.objects.get_or_create(
                name=away_team,
                jersey_color=away_color,
                defaults={
                    'name': away_team,
                    'jersey_color': away_color
                }
            )

            # Step 2: Create TraceVision session
            logger.info("Creating TraceVision session...")
            # session_payload = {
            #     "query": """
            #         mutation ($token: CustomerToken!, $sessionData: SessionCreateInput!) {
            #             createSession(token: $token, sessionData: $sessionData) {
            #                 session { session_id }
            #                 success
            #                 error
            #             }
            #         }
            #     """,
            #     "variables": {
            #         "token": {
            #             "customer_id": CUSTOMER_ID,
            #             "token": API_KEY
            #         },
            #         "sessionData": {
            #             "type": "soccer_game",
            #             "game_info": {
            #                 "home_team": {
            #                     "name": home_team,
            #                     "score": home_score,
            #                     "color": home_color
            #                 },
            #                 "away_team": {
            #                     "name": away_team,
            #                     "score": away_score,
            #                     "color": away_color
            #                 }
            #             },
            #             "capabilities": ["tracking", "highlights"]
            #         }
            #     }
            # }

            # session_response = requests.post(
            #     GRAPHQL_URL, headers={"Content-Type": "application/json"}, json=session_payload)
            # session_json = session_response.json()
            # logger.debug("Session response: %s", session_json)
             
            # if session_response.status_code != 200 or not session_json.get("data", {}).get("createSession", {}).get("success"):
            #     return Response({
            #         "error": "TraceVision session creation failed",
            #         "details": session_json
            #     }, status=http_status.HTTP_400_BAD_REQUEST)

            # session_id = session_json["data"]["createSession"]["session"]["session_id"]

            # # Handle video processing based on input type
            # if video_link:
            #     # Import video using the provided link
            #     logger.info("Importing video from link...")
            #     import_video_payload = {
            #         "query": """
            #             mutation ($token: CustomerToken!, $session_id: Int!, $video: ImportVideoInput!, $start_time: DateTime) {
            #                 importVideo(token: $token, session_id: $session_id, video: $video, start_time: $start_time) {
            #                     success
            #                     error
            #                 }
            #             }
            #         """,
            #         "variables": {
            #             "token": {
            #                 "customer_id": CUSTOMER_ID,
            #                 "token": API_KEY
            #             },
            #             "session_id": session_id,
            #             "video": {
            #                 "type": "url",
            #                 "via_url": {
            #                     "url": video_link
            #                 }
            #             },
            #             "start_time": start_time.isoformat() if start_time else None
            #         }
            #     }

            #     import_response = requests.post(GRAPHQL_URL, headers={
            #                                     "Content-Type": "application/json"}, json=import_video_payload)
            #     import_json = import_response.json()
            #     logger.info("Video import response: %s", import_json)

            #     if import_response.status_code != 200 or not import_json.get("data", {}).get("importVideo", {}).get("success"):
            #         return Response({
            #             "error": "Video import failed",
            #             "details": import_json
            #         }, status=http_status.HTTP_400_BAD_REQUEST)

            #     video_url_for_db = video_link
            # else:
            #     logger.info("Processing video file upload...")
            #     # Get upload URL for file
            #     upload_payload = {
            #         "query": """
            #             mutation ($token: CustomerToken!, $session_id: Int!, $video_name: String!) {
            #                 uploadVideo(token: $token, session_id: $session_id, video_name: $video_name) {
            #                     success
            #                     error
            #                     upload_url
            #                 }
            #             }
            #         """,
            #         "variables": {
            #             "token": {
            #                 "customer_id": CUSTOMER_ID,
            #                 "token": API_KEY
            #             },
            #             "session_id": session_id,
            #             "video_name": video_file.name
            #         }
            #     }

            #     upload_response = requests.post(
            #         GRAPHQL_URL, headers={"Content-Type": "application/json"}, json=upload_payload)
            #     upload_json = upload_response.json()
            #     logger.debug("Upload URL response: %s", upload_json)

            #     if upload_response.status_code != 200 or not upload_json.get("data", {}).get("uploadVideo", {}).get("success"):
            #         return Response({
            #             "error": "Failed to get video upload URL",
            #             "details": upload_json
            #         }, status=http_status.HTTP_400_BAD_REQUEST)

            #     upload_url = upload_json["data"]["uploadVideo"]["upload_url"]

            #     # Upload video file
            #     logger.info("Uploading video file to TraceVision...")
            #     put_response = requests.put(
            #         upload_url, headers={"Content-Type": "video/mp4"}, data=video_file.read())

            #     if put_response.status_code != 200:
            #         return Response({
            #             "error": "Video upload failed",
            #             "status_code": put_response.status_code,
            #             "text": put_response.text
            #         }, status=http_status.HTTP_400_BAD_REQUEST)

            #     video_url_for_db = upload_url

                    

            # Save session to DB
            logger.info("Saving session data to DB...")
            session = TraceSession.objects.create(
                user=request.user,
                session_id="session_id",
                match_date=datetime.now().date(),
                home_team=home_team_obj,
                away_team=away_team_obj,
                home_score=home_score,
                away_score=away_score,
                age_group=age_group,
                pitch_size=pitch_size,
                final_score=final_score_str,
                start_time=start_time,
                video_url="video_url_for_db",
                status="waiting_for_data", # Set initial status
                match_start_time=match_start_time,
                first_half_end_time=first_half_end_time,
                second_half_start_time=second_half_start_time,
                match_end_time=match_end_time,
                basic_game_stats=basic_game_stats,
            )

            download_video_and_save_to_azure_blob.delay(session.id)

            return Response({
                "success": True,
                "id": session.id,
                "session_id": session.session_id,
                "age_group": session.age_group,
                "pitch_size": session.pitch_size,
                "pitch_dimensions": session.get_pitch_dimensions(),
                "message": "TraceVision session created and video processing started successfully",
                "video_source": "link" if video_link else "file_upload",
                "match_start_time": match_start_time,
                "first_half_end_time": first_half_end_time,
                "second_half_start_time": second_half_start_time,
                "match_end_time": match_end_time,
                "basic_game_stats": session.basic_game_stats.url if session.basic_game_stats else None
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
                if new_status == "processed":
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
                "home_team": session.home_team.name if session.home_team else None,
                "away_team": session.away_team.name if session.away_team else None,
                "home_score": session.home_score,
                "away_score": session.away_score,
                "home_team_jersey_color": session.home_team.jersey_color if session.home_team else None,
                "away_team_jersey_color": session.away_team.jersey_color if session.away_team else None,
                "age_group": session.age_group,
                "pitch_size": session.pitch_size,
                "pitch_dimensions": session.get_pitch_dimensions(),
                "final_score": session.final_score,
                "start_time": session.start_time,
                "video_url": session.video_url,
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


class TraceVisionSessionResultView(APIView):
    """
    API endpoint to get TraceVision session result using GraphQL query.
    This is a testing endpoint that will be converted to a Celery task in the future.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            # Get the session for the authenticated user
            session = TraceSession.objects.get(id=pk, user=request.user)

            # Initialize service
            tracevision_service = TraceVisionService()

            # Get session result data
            result_data = tracevision_service.get_session_result(session)

            if not result_data:
                return Response({
                    "error": "Failed to retrieve session result from TraceVision API",
                    "session_id": session.session_id,
                    "details": "No result data available. Session may not be completed yet."
                }, status=http_status.HTTP_404_NOT_FOUND)

            # Prepare response data
            response_data = {
                "success": True,
                "session_id": session.session_id,
                "session_status": session.status,
                "result": result_data,
                "metadata": {
                    "home_team": session.home_team.name if session.home_team else None,
                    "away_team": session.away_team.name if session.away_team else None,
                    "home_score": session.home_score,
                    "away_score": session.away_score,
                    "home_team_jersey_color": session.home_team.jersey_color if session.home_team else None,
                    "away_team_jersey_color": session.away_team.jersey_color if session.away_team else None,
                    "age_group": session.age_group,
                    "pitch_size": session.pitch_size,
                    "pitch_dimensions": session.get_pitch_dimensions(),
                    "final_score": session.final_score,
                    "start_time": session.start_time,
                    "match_date": session.match_date,
                    "video_url": session.video_url,
                    "fetched_at": datetime.now().isoformat()
                }
            }

            return Response(response_data, status=http_status.HTTP_200_OK)

        except TraceSession.DoesNotExist:
            return Response({
                "error": "Session not found",
                "details": "No TraceVision session found with the given ID for this user"
            }, status=http_status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.exception(f"Error while fetching TraceVision session result: {str(e)}")
            return Response({
                "error": "Internal server error",
                "details": str(e)
            }, status=http_status.HTTP_500_INTERNAL_SERVER_ERROR)


class TraceVisionPlayerStatsView(APIView):
    """
    API endpoint to manage and retrieve player performance statistics.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        """
        Trigger player stats calculation for a session
        """
        try:
            # Get the session for the authenticated user
            session = TraceSession.objects.get(id=pk, user=request.user)
            
            # Check if session is processed
            if session.status != "processed":
                return Response({
                    "error": "Session is not processed yet",
                    "details": f"Current status: {session.status}. Wait for processing to complete."
                }, status=http_status.HTTP_400_BAD_REQUEST)
            
            # Check if session has trace objects
            if not session.trace_objects.exists():
                return Response({
                    "error": "No trace objects found",
                    "details": "Session must have trace objects before calculating stats."
                }, status=http_status.HTTP_400_BAD_REQUEST)
            
            # Trigger async stats calculation
            from tracevision.tasks import calculate_player_stats_task
            task = calculate_player_stats_task.delay(session.session_id)
            
            return Response({
                "success": True,
                "message": "Player stats calculation started",
                "task_id": task.id,
                "session_id": session.session_id,
                "status": "processing"
            }, status=http_status.HTTP_202_ACCEPTED)
                
        except TraceSession.DoesNotExist:
            return Response({
                "error": "Session not found",
                "details": "No TraceVision session found with the given ID for this user"
            }, status=http_status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.exception(f"Error starting stats calculation for session {pk}: {str(e)}")
            return Response({
                "error": "Internal server error",
                "details": str(e)
            }, status=http_status.HTTP_500_INTERNAL_SERVER_ERROR)

    def get(self, request, pk):
        """
        Get player performance statistics for a session
        """
        try:
            # Get the session for the authenticated user
            session = TraceSession.objects.get(id=pk, user=request.user)
            
            # Get player stats
            from tracevision.models import TraceVisionPlayerStats
            player_stats = TraceVisionPlayerStats.objects.filter(
                session=session
            ).order_by('-performance_score')
            
            if not player_stats.exists():
                return Response({
                    "success": False,
                    "error": "No player stats found",
                    "details": "Player statistics have not been calculated yet. Use POST to trigger calculation."
                }, status=http_status.HTTP_404_NOT_FOUND)
            
            # Get session stats
            from tracevision.models import TraceVisionSessionStats
            session_stats = TraceVisionSessionStats.objects.filter(session=session).first()
            
            # Format player stats for response
            stats_data = []
            for stats in player_stats:
                stats_data.append({
                    'object_id': stats.object_id,
                    'side': stats.side,
                    
                    # Movement stats
                    'total_distance_meters': stats.total_distance_meters,
                    'avg_speed_mps': stats.avg_speed_mps,
                    'max_speed_mps': stats.max_speed_mps,
                    'total_time_seconds': stats.total_time_seconds,
                    'distance_per_minute': stats.distance_per_minute,
                    
                    # Sprint stats
                    'sprint_count': stats.sprint_count,
                    'sprint_distance_meters': stats.sprint_distance_meters,
                    'sprint_time_seconds': stats.sprint_time_seconds,
                    'sprint_percentage': stats.sprint_percentage,
                    
                    # Position stats
                    'avg_position_x': stats.avg_position_x,
                    'avg_position_y': stats.avg_position_y,
                    'position_variance': stats.position_variance,
                    
                    # Performance metrics
                    'performance_score': stats.performance_score,
                    'stamina_rating': stats.stamina_rating,
                    'work_rate': stats.work_rate,
                    
                    # Metadata
                    'calculation_method': stats.calculation_method,
                    'calculation_version': stats.calculation_version,
                    'last_calculated': stats.last_calculated.isoformat() if stats.last_calculated else None
                })
            
            # Format session stats
            session_stats_data = None
            if session_stats:
                session_stats_data = {
                    'total_tracking_points': session_stats.total_tracking_points,
                    'data_coverage_percentage': session_stats.data_coverage_percentage,
                    'quality_score': session_stats.quality_score,
                    'processing_status': session_stats.processing_status,
                    'home_team_stats': session_stats.home_team_stats,
                    'away_team_stats': session_stats.away_team_stats
                }
            
            return Response({
                "success": True,
                "session_id": session.session_id,
                "player_stats_count": len(stats_data),
                "player_stats": stats_data,
                "session_stats": session_stats_data,
                "fetched_at": datetime.now().isoformat()
            }, status=http_status.HTTP_200_OK)
                
        except TraceSession.DoesNotExist:
            return Response({
                "error": "Session not found",
                "details": "No TraceVision session found with the given ID for this user"
            }, status=http_status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.exception(f"Error getting player stats for session {pk}: {str(e)}")
            return Response({
                "error": "Internal server error",
                "details": str(e)
            }, status=http_status.HTTP_500_INTERNAL_SERVER_ERROR)


class TraceVisionPlayerStatsDetailView(APIView):
    """
    API endpoint to get detailed statistics for a specific player in a session.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, pk, player_id):
        """
        Get detailed performance statistics for a specific player
        """
        try:
            # Get the session for the authenticated user
            session = TraceSession.objects.get(id=pk, user=request.user)
            
            # Get player stats
            from tracevision.models import TraceVisionPlayerStats
            try:
                player_stats = TraceVisionPlayerStats.objects.get(
                    session=session,
                    player_id=player_id
                )
            except TraceVisionPlayerStats.DoesNotExist:
                return Response({
                    "error": "Player stats not found",
                    "details": f"No statistics found for player {player_id} in session {session.session_id}"
                }, status=http_status.HTTP_404_NOT_FOUND)
            
            # Get heatmap data
            heatmap_data = player_stats.heatmap_data
            
            # Format detailed response
            detailed_stats = {
                'player_id': player_stats.player.id,
                'player_name': player_stats.player.name,
                'team_id': player_stats.team.id,
                'team_name': player_stats.team.name,
                'jersey_number': player_stats.player_mapping.jersey_number,
                'side': player_stats.player_mapping.side,
                
                # Comprehensive movement analysis
                'movement_analysis': {
                    'total_distance_meters': player_stats.total_distance_meters,
                    'total_time_seconds': player_stats.total_time_seconds,
                    'distance_per_minute': player_stats.distance_per_minute,
                    'avg_speed_mps': player_stats.avg_speed_mps,
                    'max_speed_mps': player_stats.max_speed_mps,
                    'speed_analysis': {
                        'avg_speed': player_stats.avg_speed_mps,
                        'max_speed': player_stats.max_speed_mps,
                        'speed_efficiency': (player_stats.avg_speed_mps / player_stats.max_speed_mps * 100) if player_stats.max_speed_mps > 0 else 0
                    }
                },
                
                # Sprint analysis
                'sprint_analysis': {
                    'sprint_count': player_stats.sprint_count,
                    'sprint_distance_meters': player_stats.sprint_distance_meters,
                    'sprint_time_seconds': player_stats.sprint_time_seconds,
                    'sprint_percentage': player_stats.sprint_percentage,
                    'avg_sprint_distance': player_stats.sprint_distance_meters / player_stats.sprint_count if player_stats.sprint_count > 0 else 0,
                    'avg_sprint_duration': player_stats.sprint_time_seconds / player_stats.sprint_count if player_stats.sprint_count > 0 else 0
                },
                
                # Position and tactical analysis
                'position_analysis': {
                    'avg_position_x': player_stats.avg_position_x,
                    'avg_position_y': player_stats.avg_position_y,
                    'position_variance': player_stats.position_variance,
                    'movement_range': {
                        'x_range': player_stats.position_variance * 2,  # Approximate range
                        'y_range': player_stats.position_variance * 2
                    }
                },
                
                # Performance metrics
                'performance_metrics': {
                    'overall_score': player_stats.performance_score,
                    'stamina_rating': player_stats.stamina_rating,
                    'work_rate': player_stats.work_rate,
                    'fitness_index': (player_stats.stamina_rating + player_stats.work_rate) / 2
                },
                
                # Heatmap visualization data
                'heatmap_data': heatmap_data,
                
                # Metadata
                'calculation_info': {
                    'method': player_stats.calculation_method,
                    'version': player_stats.calculation_version,
                    'last_calculated': player_stats.last_calculated.isoformat() if player_stats.last_calculated else None
                }
            }
            
            return Response({
                "success": True,
                "session_id": session.session_id,
                "player_stats": detailed_stats
            }, status=http_status.HTTP_200_OK)
                
        except TraceSession.DoesNotExist:
            return Response({
                "error": "Session not found",
                "details": "No TraceVision session found with the given ID for this user"
            }, status=http_status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.exception(f"Error getting detailed player stats for session {pk}, player {player_id}: {str(e)}")
            return Response({
                "error": "Internal server error",
                "details": str(e)
            }, status=http_status.HTTP_500_INTERNAL_SERVER_ERROR)
        

     


    



class GetTracePlayerReelsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        player = request.user.trace_players.first()
        clipreels = player.primary_clip_reels.all() if player else []

        # ---------- filters ----------
        video_type = request.query_params.get('video_type')
        if video_type:
            clipreels = clipreels.filter(video_type=video_type)

        session_id = request.query_params.get('session')
        if session_id:
            clipreels = clipreels.filter(session=session_id)

        generation_status = request.query_params.get('generation_status')
        if generation_status:
            clipreels = clipreels.filter(generation_status=generation_status)

        match_date = request.query_params.get('match_date')
        if match_date:
            try:
                match_date = datetime.strptime(match_date, "%Y-%m-%d").date()
                clipreels = clipreels.filter(session__match_date=match_date)
            except ValueError:
                return Response(
                    {"error": "Invalid date format. Use YYYY-MM-DD."},
                    status=400
                )

        age_group = request.query_params.get('age_group')
        if age_group:
            clipreels = clipreels.filter(session__age_group=age_group)

        # ---------- Build JSON ----------
        data = {
            "teams": [],
            "goals": [],
            "highlights": [],
            "events_details": [],
            # "video_urls": {}
        }

        # Teams
        teams_dict = {}
        for reel in clipreels.select_related("session__home_team", "session__away_team"):
            session = reel.session
            if session.home_team and session.home_team.id not in teams_dict:
                teams_dict[session.home_team.id] = {
                    "team_id": str(session.home_team.id),
                    "team_name": session.home_team.name,
                    "logo_url": session.home_team.logo.url if session.home_team.logo else None,
                }
            if session.away_team and session.away_team.id not in teams_dict:
                teams_dict[session.away_team.id] = {
                    "team_id": str(session.away_team.id),
                    "team_name": session.away_team.name,
                    "logo_url": session.away_team.logo.url if session.away_team.logo else None,
                }
        data["teams"] = list(teams_dict.values())

        # ---------- Goals ----------
        for reel in clipreels.filter(event_type="goal").select_related(
            "primary_player", "session__home_team", "session__away_team"
        ):
            session = reel.session
            team = session.home_team if reel.side == "home" else session.away_team
            data["goals"].append({
                "team_id": str(team.id) if team else None,
                "team_name": team.name if team else None,
                "player_id": str(reel.primary_player.id) if reel.primary_player else None,
                "player_name": reel.primary_player.name if reel.primary_player else None,
                "event_time": reel.start_ms,
                "start_time": reel.start_ms,
                "end_time": reel.start_ms + reel.duration_ms,
                "half": getattr(session, "half", None),
            })

        # ---------- Highlights ----------
        for reel in clipreels.exclude(event_type="goal").select_related(
            "primary_player", "session__home_team", "session__away_team"
        ).prefetch_related("involved_players"):
            session = reel.session
            team = session.home_team if reel.side == "home" else session.away_team

            # Convert start_ms to clock format
            start_td = timedelta(milliseconds=reel.start_ms)
            end_td = timedelta(milliseconds=reel.start_ms + reel.duration_ms)
            start_clock = str(start_td)
            end_clock = str(end_td)

            # Involved players
            involved_players = [str(p.id) for p in reel.involved_players.all()]

            data["highlights"].append({
                "id": str(reel.id),
                "age_group": getattr(session, "age_group", None),
                "match_date": session.match_date.strftime("%Y-%m-%d") if session.match_date else None,
                "event_id": reel.event_id,
                "video_type": reel.video_type,
                "video_variant_name": reel.video_variant_name,
                "event_type": reel.event_type,
                "side": reel.side,
                "start_ms": reel.start_ms,
                "duration_ms": reel.duration_ms,
                "start_clock": start_clock,
                "end_clock": end_clock,
                "generation_status": reel.generation_status,
                "video_url": reel.video_url,
                "video_thumbnail_url": reel.video_thumbnail_url,
                "video_size_mb": reel.video_size_mb,
                "video_duration_seconds": reel.video_duration_seconds,
                "generation_started_at": reel.generation_started_at,
                "generation_completed_at": reel.generation_completed_at,
                "generation_errors": reel.generation_errors,
                "generation_metadata": reel.generation_metadata,
                "resolution": reel.resolution,
                "frame_rate": reel.frame_rate,
                "bitrate": reel.bitrate,
                "label": reel.label,
                "description": reel.description or f"{reel.event_type.capitalize()} event for {reel.side} team",
                "tags": reel.tags or [reel.side, reel.event_type],
                "video_stream": reel.video_stream,
                "created_at": reel.created_at.isoformat() if reel.created_at else None,
                "updated_at": reel.updated_at.isoformat() if reel.updated_at else None,
                "session": str(session.id),
                "highlight": str(reel.highlight.id),
                "primary_player": str(reel.primary_player.id) if reel.primary_player else None,
                "involved_players": involved_players,
                "match_start_time": session.match_start_time,
                "first_half_end_time": session.first_half_end_time,
                "second_half_start_time": session.second_half_start_time,
                "match_end_time": session.match_end_time,
                "basic_game_stats": session.basic_game_stats.url if session.basic_game_stats else None,
               
            })

        # ---------- Pagination ----------
        paginator = PageNumberPagination()
        paginator.page_size = 10
        paginated_clipreels = paginator.paginate_queryset(clipreels, request)

        data["count"] = paginator.page.paginator.count if paginator.page else len(clipreels)
        data["next"] = paginator.get_next_link()
        data["previous"] = paginator.get_previous_link()

        return Response(data)


class CoachViewSpecificTeamPlayers(APIView):
    def get(self, request):
        if not request.user.is_authenticated:
            return Response(
                {"error": "Unauthorized", "details": "You are not authorized to access this resource"},
                
            )
        role = request.user.role
        if role == 'Coach':
            team = request.user.team
            players = team.players.all()
            print(players)
            serializer = CoachViewSpecificTeamPlayersSerializer(players, many=True)
            return Response(
                {"success": True, "players": serializer.data},
                
            )
        else:
            return Response(
                {"error": "Unauthorized", "details": "You are not authorized to access this resource"},
                
            )
        

class GeneratingAgainClipReelsView(APIView):
    def post(self, request):
        if not request.user.is_authenticated:
            return Response(
                {"error": "Unauthorized", "details": "You are not authorized to access this resource"},
                
            )
        role = request.user.role
        if role == 'User':
            clip_reel_id = request.data.get('clip_reel_id')
            clip_reel = TraceClipReel.objects.get(id=clip_reel_id)
            clip_reel.generation_status = 'pending'
            generate_overlay_highlights_task.delay(None, [clip_reel.id])
            clip_reel.save()
            return Response(
                {"success": True, "message": "Clip reel generation started"},
                
            )
        if role == 'Coach':
            team = request.user.team
            players = team.players.all()
            for player in players:
                clip_reels = player.primary_clip_reels.all()
                for clip_reel in clip_reels:
                    clip_reel.generation_status = 'pending'
                    generate_overlay_highlights_task.delay(None, [clip_reel.id])
                    clip_reel.save()
            return Response(
                {"success": True, "message": "Clip reel generation started"},
                
            )