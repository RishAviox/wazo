from django.db import models
from accounts.models import WajoUser
    

# Status Card Metrics
class StatusCardMetrics(models.Model):
    user = models.ForeignKey(WajoUser, on_delete=models.CASCADE, related_name='status_card_metrics')
    metrics = models.JSONField(default=dict)
     
    created_on = models.DateTimeField(auto_now_add=True)
    updated_on = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Status Card Metrics"
        verbose_name_plural = "Status Card Metrics"

    def __str__(self):
        return self.user.phone_no


# Defensive Performance Metrics
class DefensivePerformanceMetrics(models.Model):
    user = models.ForeignKey(WajoUser, on_delete=models.CASCADE, related_name="difensive_performance_metrics")
    metrics = models.JSONField()

    created_on = models.DateTimeField(auto_now_add=True)
    updated_on = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Defensive Performance Metrics"
        verbose_name_plural = "Defensive Performance Metrics"

    def __str__(self):
        return f"Defensive Performance Metrics for {self.user.phone_no}"


# Offensive Performance Metrics
class OffensivePerformanceMetrics(models.Model):
    user = models.ForeignKey(WajoUser, on_delete=models.CASCADE, related_name="offensive_performance_metrics")
    metrics = models.JSONField()

    created_on = models.DateTimeField(auto_now_add=True)
    updated_on = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Offensive Performance Metrics"
        verbose_name_plural = "Offensive Performance Metrics"

    def __str__(self):
        return f"Offensive Performance Metrics for {self.user.phone_no}"


# Game Stats
class GameStats(models.Model):
    user = models.ForeignKey(WajoUser, on_delete=models.CASCADE, related_name="game_stats")
    metrics = models.JSONField()

    created_on = models.DateTimeField(auto_now_add=True)
    updated_on = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Game Stats"
        verbose_name_plural = "Game Stats"

    def __str__(self):
        return f"Game Stats for {self.user.phone_no}"

    
# Attacking Skills
class AttackingSkills(models.Model):
    user = models.ForeignKey(WajoUser, on_delete=models.CASCADE, related_name="attacking_skills")
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
    metrics = models.JSONField()

    created_on = models.DateTimeField(auto_now_add=True)
    updated_on = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Video Card Distributions"
        verbose_name_plural = "Video Card Distributions"

    def __str__(self):
        return f"Video Card Distributions for {self.user.phone_no}"  