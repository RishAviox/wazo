from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from api.utils import *

# v1
class GPSAthleticSkillsAPI_v1(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role == 'Coach':
            # Get team stats
            if hasattr(request.user, 'coach_team_mappings'):
                # Access team stats if the mapping exists
                team_stats = request.user.coach_team_mappings.team_stats.metrics.get('gps_athletic_skills', {})
            else:
                # Default to empty if no team mapping
                team_stats = {}
                
            # Get players' data
            player_data = [
                {
                    'profile': WajoUserSerializer(player).data,
                    'metrics': get_gps_athletic_skills_metrics(player)
                }
                for player in request.user.players.all()
            ]

            # Prepare response data
            data = {
                'team': team_stats,
                'players': player_data
            }

            return Response(data, status=status.HTTP_200_OK)
        
        else:
            metrics = get_gps_athletic_skills_metrics(request.user)
            return Response(metrics, status=status.HTTP_200_OK)
        

class GPSAthleticSkillsAPI(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role == 'Coach':
            player_data = []
            for player in request.user.players.all():
                player_data.append({
                        'profile': WajoUserSerializer(player).data,
                        'metrics': get_gps_athletic_skills_metrics(player)
                    })

            return Response(player_data, status=status.HTTP_200_OK)
        
        else:
            metrics = get_gps_athletic_skills_metrics(request.user)
            return Response(metrics, status=status.HTTP_200_OK)
        


class GPSFootballAbilitiesAPI_v1(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role == 'Coach':
            # Get team stats
            if hasattr(request.user, 'coach_team_mappings'):
                # Access team stats if the mapping exists
                team_stats = request.user.coach_team_mappings.team_stats.metrics.get('gps_football_abilities', {})
            else:
                # Default to empty if no team mapping
                team_stats = {}
                
            # Get players' data
            player_data = [
                {
                    'profile': WajoUserSerializer(player).data,
                    'metrics': get_gps_football_abilities_metrics(player)
                }
                for player in request.user.players.all()
            ]

            # Prepare response data
            data = {
                'team': team_stats,
                'players': player_data
            }

            return Response(data, status=status.HTTP_200_OK)
        
        else:
            metrics = get_gps_football_abilities_metrics(request.user)
            return Response(metrics, status=status.HTTP_200_OK)


class GPSFootballAbilitiesAPI(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role == 'Coach':
            player_data = []
            for player in request.user.players.all():
                player_data.append({
                        'profile': WajoUserSerializer(player).data,
                        'metrics': get_gps_football_abilities_metrics(player)
                    })

            return Response(player_data, status=status.HTTP_200_OK)
        
        else:
            metrics = get_gps_football_abilities_metrics(request.user)
            return Response(metrics, status=status.HTTP_200_OK)