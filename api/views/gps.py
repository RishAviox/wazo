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
            # get team stats
            team_assigned = request.user.coach_team_mappings.first()
            if team_assigned:
                team_stats = team_assigned.team_stats.metrics
            else:
                team_stats = {}

            # get players data
            player_data = []
            for player in request.user.players.all():
                player_data.append({
                        'profile': WajoUserSerializer(player).data,
                        'metrics': get_gps_athletic_skills_metrics(player)
                    })

            data = {
                'team': team_stats['gps_athletic_skills'] if 'gps_athletic_skills' in team_stats.keys() else {},
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
            # get team stats
            team_assigned = request.user.coach_team_mappings.first()
            if team_assigned:
                team_stats = team_assigned.team_stats.metrics
            else:
                team_stats = {}

            # get players data
            player_data = []
            for player in request.user.players.all():
                player_data.append({
                        'profile': WajoUserSerializer(player).data,
                        'metrics': get_gps_football_abilities_metrics(player)
                    })

            data = {
                'team': team_stats['gps_football_abilities'] if 'gps_football_abilities' in team_stats.keys() else {},
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