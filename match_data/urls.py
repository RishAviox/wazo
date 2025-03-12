from django.urls import path
from .views import *

urlpatterns = [ 
    # greeting and insight
    path('overview/<str:user_id>', MatchOverviewAPIView.as_view(), name='match-overview'),
]