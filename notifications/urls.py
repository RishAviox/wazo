from django.urls import path
from .views import *

urlpatterns = [
    path('<str:fcm_token>', NotificationsAPI.as_view(), name='wajo-notifications'),
]