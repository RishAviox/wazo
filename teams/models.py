from django.db import models
from accounts.models import WajoUser

class Team(models.Model):
    id = models.CharField(max_length=10, primary_key=True, unique=True)  # User-defined unique ID
    name = models.CharField(max_length=255, blank=True, null=True)
    logo = models.ImageField(upload_to="team_logos/", blank=True, null=True)
    coach = models.ManyToManyField(
        WajoUser,
        related_name='teams_coached',
        blank=True,
        limit_choices_to={'role': 'Coach'}  # Restrict selection to users with the role "Coach"
    )

    created_on = models.DateTimeField(auto_now_add=True)
    updated_on = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name if self.name else f"Team {self.id}"

