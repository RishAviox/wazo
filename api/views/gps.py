from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from api.utils import *


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
