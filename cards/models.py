from django.db import models
from accounts.models import WajoUser
from games.models import Game

from core.soft_delete import WajoModel

# Status Card Metrics
class StatusCardMetrics(WajoModel):
    user = models.ForeignKey(WajoUser, on_delete=models.CASCADE, related_name='status_card_metrics')
    metrics = models.JSONField(default=dict)
     
    created_on = models.DateTimeField(auto_now_add=True)
    updated_on = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Status Card Metrics"
        verbose_name_plural = "Status Card Metrics"

    def __str__(self):
        return self.user.phone_no
    
# RPE Metrics
class RPEMetrics(WajoModel):
    user = models.ForeignKey(WajoUser, on_delete=models.CASCADE, related_name='rpe_metrics')
    metrics = models.JSONField(default=dict)
     
    created_on = models.DateTimeField(auto_now_add=True)
    updated_on = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "RPE Metrics"
        verbose_name_plural = "RPE Metrics"

    def __str__(self):
        return self.user.phone_no


# Attacking Skills
class AttackingSkills(WajoModel):
    user = models.ForeignKey(WajoUser, on_delete=models.CASCADE, related_name="attacking_skills")
    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name='game_attacking_skills')
    metrics = models.JSONField()

    created_on = models.DateTimeField(auto_now_add=True)
    updated_on = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Attacking Skills"
        verbose_name_plural = "Attacking Skills"

    def __str__(self):
        return f"Attacking Skills for {self.user.phone_no}"
    

# Video Card Defensive
class VideoCardDefensive(WajoModel):
    user = models.ForeignKey(WajoUser, on_delete=models.CASCADE, related_name="videocard_defensive")
    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name='game_videocard_defensive')
    metrics = models.JSONField()

    created_on = models.DateTimeField(auto_now_add=True)
    updated_on = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Video Card Defensive"
        verbose_name_plural = "Video Card Defensive"

    def __str__(self):
        return f"Video Card Defensive for {self.user.phone_no}"
    
    
# Video Card Distributions
class VideoCardDistributions(WajoModel):
    user = models.ForeignKey(WajoUser, on_delete=models.CASCADE, related_name="videocard_distributions")
    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name='game_videocard_distributions')
    metrics = models.JSONField()

    created_on = models.DateTimeField(auto_now_add=True)
    updated_on = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Video Card Distributions"
        verbose_name_plural = "Video Card Distributions"

    def __str__(self):
        return f"Video Card Distributions for {self.user.phone_no}"


class GPSAthleticSkills(WajoModel):
    user = models.ForeignKey(WajoUser, on_delete=models.CASCADE, related_name="athletic_skills")
    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name='game_athletic_skills')
    metrics = models.JSONField()

    created_on = models.DateTimeField(auto_now_add=True)
    updated_on = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "GPS-Athletic Skills"
        verbose_name_plural = "GPS-Athletic Skills"

    def __str__(self):
        return f"Athletic Skills for {self.user.phone_no}"


class GPSFootballAbilities(WajoModel):
    user = models.ForeignKey(WajoUser, on_delete=models.CASCADE, related_name="gps_football_abilities")
    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name='game_gps_football_abilities')
    metrics = models.JSONField()

    created_on = models.DateTimeField(auto_now_add=True)
    updated_on = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "GPS-Football Abilities"
        verbose_name_plural = "GPS-Football Abilities"

    def __str__(self):
        return f"Football Abilities for {self.user.phone_no}" 
    
# training card json data, send as json of all entries via api
class TrainingCardData(WajoModel):
    first_dropdown = models.CharField(max_length=128)
    second_dropdown = models.CharField(max_length=128)
    topic = models.CharField(max_length=128, null=True, blank=True)
    video_link = models.TextField(null=True, blank=True)
    _type = models.CharField(max_length=128, null=True, blank=True)

    created_on = models.DateTimeField(auto_now_add=True)
    updated_on = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Training Card Data (JSON)"
        verbose_name_plural = "Training Card Data (JSON)"

# news card json data
class NewsCardData(WajoModel):
    title = models.CharField(max_length=128)
    data = models.JSONField()

    created_on = models.DateTimeField(auto_now_add=True)
    updated_on = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "News Card Data (JSON)"
        verbose_name_plural = "News Card Data (JSON)"
        