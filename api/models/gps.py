from django.db import models
from .user import WajoUser

class GPSAthleticSkills(models.Model):
    user = models.ForeignKey(WajoUser, on_delete=models.CASCADE, related_name="athletic_skills")
    metrics = models.JSONField()

    created_on = models.DateTimeField(auto_now_add=True)
    updated_on = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "GPS-Athletic Skills"
        verbose_name_plural = "GPS-Athletic Skills"

    def __str__(self):
        return f"Athletic Skills for {self.user.phone_no}"


class GPSFootballAbilities(models.Model):
    user = models.ForeignKey(WajoUser, on_delete=models.CASCADE, related_name="gps_football_abilities")
    metrics = models.JSONField()

    created_on = models.DateTimeField(auto_now_add=True)
    updated_on = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "GPS-Football Abilities"
        verbose_name_plural = "GPS-Football Abilities"

    def __str__(self):
        return f"Football Abilities for {self.user.phone_no}"