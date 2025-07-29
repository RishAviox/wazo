from django.db import models

from accounts.models import WajoUser


class MatchDataTracevision(models.Model):
    user = models.ForeignKey(WajoUser, on_delete=models.CASCADE)
    data = models.JSONField(default=dict)
    video = models.FileField(upload_to='match_data_videos/')
