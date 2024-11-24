from django.db import models
from accounts.models import WajoUser
from games.models import Game

# Status Card Metrics
class StatusCardMetrics(models.Model):
    user = models.ForeignKey(WajoUser, on_delete=models.CASCADE, related_name='status_card_metrics')
    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name='game_status_card_metrics')
    metrics = models.JSONField(default=dict)
     
    created_on = models.DateTimeField(auto_now_add=True)
    updated_on = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Status Card Metrics"
        verbose_name_plural = "Status Card Metrics"

    def __str__(self):
        return self.user.phone_no


# Attacking Skills
class AttackingSkills(models.Model):
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
class VideoCardDefensive(models.Model):
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
class VideoCardDistributions(models.Model):
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


class GPSAthleticSkills(models.Model):
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


class GPSFootballAbilities(models.Model):
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