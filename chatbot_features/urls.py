from django.urls import path
from .views import ChatwellnessAPIView, GameOverviewAPIView

urlpatterns = [
    path("chat-wellness" , ChatwellnessAPIView.as_view() , name="chat-wellness"),
    path("game-overview" , GameOverviewAPIView.as_view() , name="game-overview")
]