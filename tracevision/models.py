from django.db import models

from accounts.models import WajoUser


class MatchDataTracevision(models.Model):
    user = models.ForeignKey(WajoUser, on_delete=models.CASCADE)
    data = models.JSONField(default=dict)
    video = models.FileField(upload_to='match_data_videos/')

class TraceSession(models.Model):
    match_data = models.ForeignKey(to=MatchDataTracevision, on_delete=models.CASCADE)
    session_id = models.CharField(max_length=250)
    match_date = models.DateField()
    home_team = models.CharField(max_length=100)
    away_team = models.CharField(max_length=100)
    home_score = models.PositiveSmallIntegerField()
    away_score = models.PositiveSmallIntegerField()


class TracePlayer(models.Model):
    name = models.CharField(max_length=100)
    jersey_number = models.PositiveIntegerField()
    team = models.CharField(max_length=100)
    position = models.CharField(max_length=100)
    session = models.ForeignKey(to=TraceSession, on_delete=models.CASCADE)
