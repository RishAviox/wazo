from django.urls import path
from .views import ChatwellnessAPIView, RPEChatAPIView, GameOverviewAPIView

urlpatterns = [
    path("chat-wellness" , ChatwellnessAPIView.as_view() , name="chat-wellness"),
    path("chat-rpe" , RPEChatAPIView.as_view() , name="chat-rpe"),
    path("game-overview" , GameOverviewAPIView.as_view() , name="game-overview")
]