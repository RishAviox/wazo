from django.urls import path
from .views import *

urlpatterns = [
    path('send-otp', SendOTPAPI.as_view(), name='send-otp'),
    path('login', LoginAPI.as_view(), name='login'),
    path('logout', LogoutAPI.as_view(), name='logout'),
    path('refresh', RefreshTokenAPI.as_view(), name='refresh'),
    path('user-profile', WajoUserProfileDetails.as_view(), name='user-profile'),
    path('user-request', UserRequestCreateView.as_view(), name='user-request')
]