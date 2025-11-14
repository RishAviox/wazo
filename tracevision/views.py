import logging
import requests
from django.db import models
from django.db.models import Q
from datetime import timedelta
from django.conf import settings
from datetime import datetime
from django.db.models import Prefetch
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status as http_status
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.pagination import PageNumberPagination

from teams.models import Team
from tracevision.models import (
    TraceClipReel, TraceSession, TraceVisionPlayerStats, TracePlayer,
    TracePossessionSegment, TracePossessionStats
)
from tracevision.tasks import download_video_and_save_to_azure_blob, generate_overlay_highlights_task, process_trace_sessions_task
from tracevision.serializers import (
    TraceVisionProcessesSerializer, TraceVisionProcessSerializer, TraceSessionListSerializer, 
    CoachViewSpecificTeamPlayersSerializer, HighlightDateSessionSerializer,
    HighlightClipReelSerializer, MatchInfoSerializer,
    PossessionTeamMetricsSerializer, PossessionPlayerMetricsSerializer
)
from tracevision.services import TraceVisionService


logger = logging.getLogger()

CUSTOMER_ID = int(settings.TRACEVISION_CUSTOMER_ID)
API_KEY = settings.TRACEVISION_API_KEY
GRAPHQL_URL = settings.TRACEVISION_GRAPHQL_URL


class TraceVisionProcessesList(ListAPIView):
    serializer_class = TraceSessionListSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        base_queryset = TraceSession.objects.filter(
            Q(user=self.request.user) |
            Q(trace_players__user=self.request.user)
        ).distinct()

        serializer = self.serializer_class(data=self.request.query_params)
        if not serializer.is_valid():
            # Return empty queryset instead of Response object
            return TraceSession.objects.none()

        return self.serializer_class.get_filtered_queryset(base_queryset, serializer.validated_data)

    def list(self, request, *args, **kwargs):
        """
        Override list method to handle validation errors properly
        """
        # Validate query parameters first
        serializer = self.serializer_class(data=request.query_params)
        if not serializer.is_valid():
            return Response({
                "error": "Invalid query parameters",
                "details": serializer.errors
            }, status=http_status.HTTP_400_BAD_REQUEST)

        # If validation passes, proceed with normal list behavior
        return super().list(request, *args, **kwargs)

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
            # TODO: For video upload instead of video URL.
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
            match_start_time = serializer.validated_data.get(
                'match_start_time')
            first_half_end_time = serializer.validated_data.get(
                'first_half_end_time')
            second_half_start_time = serializer.validated_data.get(
                'second_half_start_time')
            match_end_time = serializer.validated_data.get('match_end_time')
            basic_game_stats = serializer.validated_data.get(
                'basic_game_stats')
            print(type(basic_game_stats))

            # Set pitch size (custom or default based on age group)
            if pitch_length and pitch_width:
                pitch_size = {'length': pitch_length, 'width': pitch_width}
            else:
                # Use default pitch size for the age group
                from tracevision.models import TraceSession
                pitch_size = TraceSession.DEFAULT_PITCH_SIZES.get(
                    age_group, TraceSession.DEFAULT_PITCH_SIZES['SENIOR'])

            # Parse the final score to get individual team scores
            home_score, away_score = map(int, final_score_str.split('-'))

            logger.info("Getting or creating Team objects...")
            # Generate team IDs based on team names (first 10 chars, uppercase, alphanumeric only)
            home_team_id = ''.join(
                c for c in home_team.upper() if c.isalnum())[:10]
            away_team_id = ''.join(
                c for c in away_team.upper() if c.isalnum())[:10]

            # Get or create home team using generated ID
            home_team_obj, _ = Team.objects.get_or_create(
                id=home_team_id,
                defaults={
                    'name': home_team,
                    'jersey_color': home_color
                }
            )

            # Get or create away team using generated ID
            away_team_obj, _ = Team.objects.get_or_create(
                id=away_team_id,
                defaults={
                    'name': away_team,
                    'jersey_color': away_color
                }
            )

            # Create TraceVision session
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
                home_team=home_team_obj,
                away_team=away_team_obj,
                home_score=home_score,
                away_score=away_score,
                age_group=age_group,
                pitch_size=pitch_size,
                final_score=final_score_str,
                start_time=start_time,
                video_url=video_url_for_db,
                status="waiting_for_data",  # Set initial status
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

            # If session is processed, include session URL and highlights
            if session.status == "processed":
                # Get highlights for this session
                highlights = session.highlights.all().order_by('start_offset')
                highlights_data = []

                for highlight in highlights:
                    highlight_data = {
                        "id": highlight.id,
                        "highlight_id": highlight.highlight_id,
                        "start_offset": highlight.start_offset,
                        "duration": highlight.duration,
                        "event_type": highlight.event_type,
                        "match_time": highlight.match_time,
                        "half": highlight.half,
                        "tags": highlight.tags,
                        "video_stream": highlight.video_stream,
                        "performance_impact": highlight.performance_impact,
                        "team_impact": highlight.team_impact,
                        "event_metadata": highlight.event_metadata,
                    }

                    # Include primary player info if available
                    if hasattr(highlight, 'primary_player') and highlight.primary_player:
                        highlight_data["primary_player"] = {
                            "id": highlight.primary_player.id,
                            "name": highlight.primary_player.name,
                            "jersey_number": highlight.primary_player.jersey_number,
                        }

                    highlights_data.append(highlight_data)

                # Add session URL and highlights to response
                response_data.update({
                    "session_url": f"/api/vision/process/{session.id}/",
                    "highlights": highlights_data,
                    "highlights_count": len(highlights_data),
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
                })

            return Response(response_data, status=http_status.HTTP_200_OK)

        except TraceSession.DoesNotExist:
            return Response({"error": "Session not found"}, status=http_status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.exception(
                f"Error while polling TraceVision status: {str(e)}")
            return Response({"error": "Internal server error"}, status=http_status.HTTP_500_INTERNAL_SERVER_ERROR)


class TraceVisionPlayerStatsView(APIView):
    """
    API endpoint to manage and retrieve player performance statistics.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        """
        Trigger player stats calculation for a session or generate overlay highlights

        Query Parameters:
        - task_type: 'process_sessions' (default) or 'generate_overlays'
        """
        try:
            # Get the session for the authenticated user
            session = TraceSession.objects.get(id=pk, user=request.user)

            # Get task type from query parameters
            task_type = request.query_params.get(
                'task_type', 'process_sessions')

            # Validate task type
            if task_type not in ['process_sessions', 'generate_overlays']:
                return Response({
                    "error": "Invalid task type",
                    "details": "task_type must be 'process_sessions' or 'generate_overlays'"
                }, status=http_status.HTTP_400_BAD_REQUEST)

            # Check if session is processed (only for process_sessions task)
            if task_type == 'process_sessions' and session.status != "processed":
                return Response({
                    "error": "Session is not processed yet",
                    "details": f"Current status: {session.status}. Wait for processing to complete."
                }, status=http_status.HTTP_400_BAD_REQUEST)

            # Trigger the appropriate async task
            if task_type == 'process_sessions':
                task = process_trace_sessions_task.delay(session.id)
                message = "Player stats calculation started"
                logger.info(
                    f"Queued player stats calculation for session {session.session_id}")
            else:  # generate_overlays
                task = generate_overlay_highlights_task.delay(
                    session_id=session.session_id)
                message = "Overlay highlights generation started"
                logger.info(
                    f"Queued overlay highlights generation for session {session.session_id}")

            return Response({
                "success": True,
                "message": message,
                "task_id": task.id,
                "session_id": session.session_id,
                "task_type": task_type,
                "status": "processing"
            }, status=http_status.HTTP_202_ACCEPTED)

        except TraceSession.DoesNotExist:
            return Response({
                "error": "Session not found",
                "details": "No TraceVision session found with the given ID for this user"
            }, status=http_status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.exception(
                f"Error starting stats calculation for session {pk}: {str(e)}")
            return Response({
                "error": "Internal server error",
                "details": str(e)
            }, status=http_status.HTTP_500_INTERNAL_SERVER_ERROR)

    def get(self, request, pk):
        """
        Get possession segment data (team and player metrics) for a session.
        
        Query Parameters:
        - team_id: Filter by specific team ID (optional)
        - player_id: Filter by specific player ID (optional)
        """
        try:
            # Get the session for the authenticated user
            session = TraceSession.objects.select_related('home_team', 'away_team').get(
                id=pk, user=request.user
            )

            # Get filter parameters
            team_id_filter = request.query_params.get('team_id', None)
            player_id_filter = request.query_params.get('player_id', None)

            # Validate filters - if both provided, ensure they're from the same side
            if team_id_filter and player_id_filter:
                try:
                    team_id = team_id_filter  # Team ID is a string (CharField)
                    player_id = int(player_id_filter)
                    
                    # Get the team and player
                    team = Team.objects.get(id=team_id)
                    player = TracePlayer.objects.select_related('team').get(id=player_id)
                    
                    # Determine sides
                    team_side = None
                    if session.home_team and team.id == session.home_team.id:
                        team_side = 'home'
                    elif session.away_team and team.id == session.away_team.id:
                        team_side = 'away'
                    
                    player_side = None
                    if player.team:
                        if session.home_team and player.team.id == session.home_team.id:
                            player_side = 'home'
                        elif session.away_team and player.team.id == session.away_team.id:
                            player_side = 'away'
                    
                    # Validate they're from the same side - return simple 404 if not
                    if team_side and player_side and team_side != player_side:
                        return Response({
                            "error": "Not found",
                            "details": "No stats found with the team_id & player_id"
                        }, status=http_status.HTTP_404_NOT_FOUND)
                    
                except (Team.DoesNotExist, TracePlayer.DoesNotExist, ValueError):
                    return Response({
                        "error": "Not found",
                        "details": "No stats found with the team_id & player_id"
                    }, status=http_status.HTTP_404_NOT_FOUND)

            # Get team metrics from last TracePossessionSegment for each side
            team_metrics_data = {}
            
            # Determine which sides to query
            sides_to_query = ['home', 'away']
            if team_id_filter:
                team_id = team_id_filter  # Team ID is a string (CharField)
                if session.home_team and team_id == session.home_team.id:
                    sides_to_query = ['home']
                elif session.away_team and team_id == session.away_team.id:
                    sides_to_query = ['away']
                else:
                    return Response({
                        "error": "Team not found",
                        "details": f"Team {team_id} is not associated with this session"
                    }, status=http_status.HTTP_404_NOT_FOUND)

            for side in sides_to_query:
                # Get the last segment for this side (cumulative metrics)
                last_segment = TracePossessionSegment.objects.filter(
                    session=session, side=side
                ).order_by('-end_ms').only('team_metrics', 'side').first()
                
                if last_segment and last_segment.team_metrics:
                    team = session.home_team if side == 'home' else session.away_team
                    metrics = last_segment.team_metrics
                    
                    # Format team metrics data
                    team_metrics_data[side] = {
                        'team': team,
                        'possession_time_ms': metrics.get('possession_time_ms', 0),
                        'possession_count': metrics.get('possession_count', 0),
                        'avg_duration_ms': metrics.get('avg_duration_ms', 0.0),
                        'avg_passes': metrics.get('avg_passes', 0.0),
                        'longest_possession_ms': metrics.get('longest_possession_ms', 0),
                        'turnovers': metrics.get('turnovers', 0),
                        'total_touches': metrics.get('total_touches', 0),
                        'total_passes': metrics.get('total_passes', 0),
                        'possession_percentage': metrics.get('possession_percentage', 0.0)
                    }
                else:
                    team = session.home_team if side == 'home' else session.away_team
                    team_metrics_data[side] = {
                        'team': team,
                        'possession_time_ms': 0,
                        'possession_count': 0,
                        'avg_duration_ms': 0.0,
                        'avg_passes': 0.0,
                        'longest_possession_ms': 0,
                        'turnovers': 0,
                        'total_touches': 0,
                        'total_passes': 0,
                        'possession_percentage': 0.0
                    }

            # Get player metrics from TracePossessionStats
            player_stats_query = TracePossessionStats.objects.filter(
                session=session,
                possession_type='player'
            ).select_related('player', 'player__team')
            
            # optimize by filtering directly on team through player relationship
            if team_id_filter:
                team_id = team_id_filter
                # This ensures we only get players from the specified team
                player_stats_query = player_stats_query.filter(player__team_id=team_id)
            
            if player_id_filter:
                try:
                    player_id = int(player_id_filter)
                    player_stats_query = player_stats_query.filter(player_id=player_id)
                except ValueError:
                    return Response({
                        "error": "Invalid player_id",
                        "details": "player_id must be a valid integer"
                    }, status=http_status.HTTP_400_BAD_REQUEST)

            player_stats_list = list(player_stats_query.all())
            
            # Format player metrics data
            player_metrics_data = []
            for player_stat in player_stats_list:
                metrics = player_stat.metrics or {}
                
                # Calculate possession_percentage from involvement_percentage if available
                possession_percentage = metrics.get('possession_percentage', 
                                                   metrics.get('involvement_percentage', 0.0))
                
                player_data = {
                    'player': player_stat.player,
                    'involvement_count': metrics.get('involvement_count', 
                                                    metrics.get('possessions_involved', 0)),
                    'total_duration_ms': metrics.get('total_duration_ms', 0),
                    'total_touches': metrics.get('total_touches', 
                                                metrics.get('touches_in_possession', 0)),
                    'total_passes': metrics.get('total_passes', 
                                              metrics.get('passes_in_possession', 0)),
                    'possession_percentage': possession_percentage
                }
                player_metrics_data.append(player_data)

            # Serialize the data
            team_metrics_serialized = {}
            for side, team_data in team_metrics_data.items():
                serializer = PossessionTeamMetricsSerializer(team_data)
                team_metrics_serialized[side] = serializer.data

            # Serialize player metrics with session context
            player_metrics_serialized = []
            for player_data in player_metrics_data:
                serializer = PossessionPlayerMetricsSerializer(
                    player_data,
                    context={'session': session}
                )
                player_metrics_serialized.append(serializer.data)

            return Response({
                "success": True,
                "data": {
                    "team_metrics": team_metrics_serialized,
                    "player_metrics": player_metrics_serialized
                }
            }, status=http_status.HTTP_200_OK)

        except TraceSession.DoesNotExist:
            return Response({
                "error": "Session not found",
                "details": "No TraceVision session found with the given ID for this user"
            }, status=http_status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.exception(
                f"Error getting possession stats for session {pk}: {str(e)}")
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
            logger.exception(
                f"Error getting detailed player stats for session {pk}, player {player_id}: {str(e)}")
            return Response({
                "error": "Internal server error",
                "details": str(e)
            }, status=http_status.HTTP_500_INTERNAL_SERVER_ERROR)


class GetTracePlayerReelsView(ListAPIView):
    """
    API endpoint to get highlights for a specific session.
    URL: highlights/<session_id>/
    Query Parameters:
    - player_id: Filter by specific player ID (optional)
    - video_type: Filter by video type (optional)
    - generation_status: Filter by generation status (optional)
    - event_type: Filter by event type (optional)
    - half: Filter by half (1 or 2) (optional)
    """
    permission_classes = [IsAuthenticated]
    serializer_class = HighlightClipReelSerializer
    pagination_class = PageNumberPagination

    def get_queryset(self):
        """Get optimized queryset for clip reels"""
        session_id = self.kwargs.get('session_id')
        
        # Get session and verify user has access
        try:
            session = TraceSession.objects.select_related(
                'home_team', 'away_team'
            ).get(id=session_id, user=self.request.user)
        except TraceSession.DoesNotExist:
            return TraceClipReel.objects.none()

        # Base queryset with optimized selects
        queryset = TraceClipReel.objects.filter(
            session=session
        ).select_related(
            'primary_player__team',
            'session__home_team',
            'session__away_team',
            'highlight'
        ).prefetch_related(
            'involved_players__team'
        )

        # Apply filters from query parameters
        video_type = self.request.query_params.get('video_type')
        if video_type:
            queryset = queryset.filter(video_type=video_type)

        generation_status = self.request.query_params.get('generation_status')
        if generation_status:
            queryset = queryset.filter(generation_status=generation_status)

        event_type = self.request.query_params.get('event_type')
        if event_type:
            queryset = queryset.filter(event_type=event_type)

        # Filter by player_id if provided
        player_id = self.request.query_params.get('player_id')
        if player_id:
            try:
                player_id = int(player_id)
                queryset = queryset.filter(
                    models.Q(primary_player_id=player_id) |
                    models.Q(involved_players__id=player_id)
                ).distinct()
            except ValueError:
                # Invalid player_id - return empty queryset
                return TraceClipReel.objects.none()

        # Filter by half if specified
        half = self.request.query_params.get('half')
        if half:
            try:
                half_num = int(half)
                if half_num in [1, 2]:
                    queryset = queryset.filter(highlight__half=half_num)
                else:
                    # Invalid half - return empty queryset
                    return TraceClipReel.objects.none()
            except ValueError:
                # Invalid half - return empty queryset
                return TraceClipReel.objects.none()

        return queryset

    def get_serializer_context(self):
        """Add session to serializer context"""
        context = super().get_serializer_context()
        session_id = self.kwargs.get('session_id')
        try:
            context['session'] = TraceSession.objects.select_related(
                'home_team', 'away_team'
            ).get(id=session_id, user=self.request.user)
        except TraceSession.DoesNotExist:
            context['session'] = None
        return context

    def list(self, request, *args, **kwargs):
        """Override list to add match_info and custom response format"""
        session_id = kwargs.get('session_id')
        
        # Get session for match_info
        try:
            session = TraceSession.objects.select_related(
                'home_team', 'away_team'
            ).get(id=session_id, user=request.user)
        except TraceSession.DoesNotExist:
            return Response({
                "error": "Session not found",
                "details": f"No session found with ID {session_id} for this user"
            }, status=http_status.HTTP_404_NOT_FOUND)

        # Validate query parameters
        player_id = request.query_params.get('player_id')
        if player_id:
            try:
                int(player_id)
            except ValueError:
                return Response({
                    "error": "Invalid player_id",
                    "details": "player_id must be a valid integer"
                }, status=http_status.HTTP_400_BAD_REQUEST)

        half = request.query_params.get('half')
        if half:
            try:
                half_num = int(half)
                if half_num not in [1, 2]:
                    return Response({
                        "error": "Invalid half",
                        "details": "half must be 1 or 2"
                    }, status=http_status.HTTP_400_BAD_REQUEST)
            except ValueError:
                return Response({
                    "error": "Invalid half",
                    "details": "half must be 1 or 2"
                }, status=http_status.HTTP_400_BAD_REQUEST)

        # Get queryset and paginate
        queryset = self.filter_queryset(self.get_queryset())
        
        # Serialize highlights
        serializer = self.get_serializer(queryset, many=True)
        highlights = serializer.data

        # Serialize match_info
        match_info_serializer = MatchInfoSerializer(session)
        match_info = match_info_serializer.data

        # Pagination
        paginator = self.pagination_class()
        paginator.page_size = 10
        paginated_highlights = paginator.paginate_queryset(highlights, request)

        # Build response
        response_data = {
            "highlights": paginated_highlights if paginated_highlights else highlights,
            "match_info": match_info,
            "count": paginator.page.paginator.count if paginator.page else len(highlights),
            "next": paginator.get_next_link(),
            "previous": paginator.get_previous_link()
        }

        return Response(response_data, status=http_status.HTTP_200_OK)


class GetAvailableHighlightDatesView(APIView):
    """
    API endpoint to get list of dates on which highlights are available.
    Returns sessions grouped by date with match info and players.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            # Get the current user's player
            player = request.user.trace_players.first()
            if not player:
                return Response({
                    "success": False,
                    "message": "No player found for this user",
                    "data": {}
                }, status=http_status.HTTP_404_NOT_FOUND)

            try:
                # Get sessions with teams where the player has highlights
                sessions_with_highlights = TraceSession.objects.filter(
                    models.Q(clip_reels__primary_player=player) | 
                    models.Q(clip_reels__involved_players=player)
                ).select_related(
                    'home_team', 'away_team'
                ).distinct().order_by('-match_date', '-id')
                
                # Prefetch all players for teams in these sessions
                # Get unique team IDs from sessions
                team_ids = set()
                for session in sessions_with_highlights:
                    if session.home_team:
                        team_ids.add(session.home_team.id)
                    if session.away_team:
                        team_ids.add(session.away_team.id)
                
                # Get all TracePlayers for these teams (NOT filtered by session)
                # This ensures we get players even if they weren't created for this specific session
                all_players = TracePlayer.objects.filter(
                    team_id__in=team_ids
                ).select_related('team', 'session')
                
                # Create a mapping of team_id -> players for quick lookup
                players_by_team = {}
                for player_obj in all_players:
                    team_id = player_obj.team_id
                    if team_id not in players_by_team:
                        players_by_team[team_id] = []
                    players_by_team[team_id].append(player_obj)
                
                # Attach prefetched players to sessions based on teams
                # Get players from home_team and away_team for each session
                for session in sessions_with_highlights:
                    session._prefetched_players = []
                    if session.home_team and session.home_team.id in players_by_team:
                        session._prefetched_players.extend(players_by_team[session.home_team.id])
                    if session.away_team and session.away_team.id in players_by_team:
                        session._prefetched_players.extend(players_by_team[session.away_team.id])

                        
            except Exception as db_error:
                logger.exception(f"Database error while fetching sessions: {str(db_error)}")
                return Response({
                    "success": False,
                    "message": "Something went wrong",
                    "data": {},
                    "error": "Unable to retrieve session data. Please try again later."
                }, status=http_status.HTTP_500_INTERNAL_SERVER_ERROR)

            # Group sessions by date
            sessions_by_date = {}
            try:
                for session in sessions_with_highlights:
                    try:
                        date_key = session.match_date.strftime("%Y-%m-%d") if session.match_date else None
                        if not date_key:
                            continue
                        
                        if date_key not in sessions_by_date:
                            sessions_by_date[date_key] = []
                        
                        # Serialize session data
                        serializer = HighlightDateSessionSerializer(session)
                        sessions_by_date[date_key].append(serializer.data)
                    except (AttributeError, ValueError, KeyError) as session_error:
                        logger.warning(f"Error processing session {session.id if hasattr(session, 'id') else 'unknown'}: {str(session_error)}")
                        continue
                    except Exception as serialization_error:
                        logger.warning(f"Serialization error for session {session.id if hasattr(session, 'id') else 'unknown'}: {str(serialization_error)}")
                        continue
            except Exception as processing_error:
                logger.exception(f"Error processing sessions: {str(processing_error)}")
                return Response({
                    "success": False,
                    "message": "Error processing session data",
                    "data": {},
                    "error": "Unable to process session information. Please try again later."
                }, status=http_status.HTTP_500_INTERNAL_SERVER_ERROR)

            return Response({
                "success": True,
                "message": "Available highlight dates retrieved successfully",
                "data": sessions_by_date
            }, status=http_status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Unexpected error fetching available highlight dates: {str(e)}")
            return Response({
                "success": False,
                "message": "An unexpected error occurred",
                "data": {},
                "error": "Unable to retrieve highlight dates. Please try again later."
            }, status=http_status.HTTP_500_INTERNAL_SERVER_ERROR)


class CoachViewSpecificTeamPlayers(APIView):
    def get(self, request):
        if not request.user.is_authenticated:
            return Response(
                {"error": "Unauthorized",
                    "details": "You are not authorized to access this resource"},

            )
        role = request.user.role
        if role == 'Coach':
            team = request.user.team
            players = team.players.all()
            print(players)
            serializer = CoachViewSpecificTeamPlayersSerializer(
                players, many=True)
            return Response(
                {"success": True, "players": serializer.data},

            )
        else:
            return Response(
                {"error": "Unauthorized",
                    "details": "You are not authorized to access this resource"},

            )


class GeneratingAgainClipReelsView(APIView):
    def post(self, request):
        if not request.user.is_authenticated:
            return Response(
                {"error": "Unauthorized",
                    "details": "You are not authorized to access this resource"},

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
                    generate_overlay_highlights_task.delay(
                        None, [clip_reel.id])
                    clip_reel.save()
            return Response(
                {"success": True, "message": "Clip reel generation started"},
                status=http_status.HTTP_200_OK
            )
