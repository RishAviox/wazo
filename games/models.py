from django.db import models
import os
from django.core.exceptions import ValidationError
import pandas as pd

from teams.models import Team
from core.soft_delete import WajoModel
from accounts.models import WajoUser


class Game(WajoModel):
    GAME_TYPE_CHOICES = [
        ("match", "Match"),
        ("training", "Training"),
    ]

    id = models.CharField(
        max_length=10, primary_key=True, unique=True
    )  # User-defined unique ID
    type = models.CharField(max_length=10, choices=GAME_TYPE_CHOICES)
    name = models.CharField(max_length=255, blank=True, null=True)
    date = models.DateField(blank=True, null=True)
    teams = models.ManyToManyField(
        Team, related_name="games", blank=True
    )  # Teams that played in the game
    referees = models.ManyToManyField(
        WajoUser,
        related_name="games_refereed",
        blank=True,
        limit_choices_to={"role": "Referee"},
    )

    # Multilingual match data (English and Hebrew)
    language_metadata = models.JSONField(
        default=dict,
        blank=True,
        null=True,
        help_text="Multilingual match data with 'en' and 'he' sections containing match summary, lineups, replacements, bench, coaches, and referees",
    )

    created_on = models.DateTimeField(auto_now_add=True)
    updated_on = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Game"
        verbose_name_plural = "Games"

    def __str__(self):
        return f"Game-{self.id} ({self.type})"


class GameUserRole(WajoModel):
    """
    Links users to games. User's role is determined by WajoUser.role field.
    This allows multiple users to access the same game.
    """

    game = models.ForeignKey(
        Game,
        on_delete=models.CASCADE,
        related_name="game_roles",
        help_text="Game this user is linked to",
    )
    user = models.ForeignKey(
        WajoUser,
        on_delete=models.CASCADE,
        related_name="game_roles",
        help_text="User linked to this game",
    )

    created_on = models.DateTimeField(auto_now_add=True)
    updated_on = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Game User Role"
        verbose_name_plural = "Game User Roles"
        # Unique constraint: one role per user per game
        unique_together = [["game", "user"]]
        indexes = [
            models.Index(fields=["game", "user"]),
            models.Index(fields=["user"]),
            models.Index(fields=["game"]),
        ]

    def __str__(self):
        user_role = self.user.role if self.user and self.user.role else "No Role"
        return f"{self.user.phone_no if self.user else 'Unknown'} - {user_role} - Game {self.game.id if self.game else 'Unknown'}"


# Game GPS Data File
def validate_file_extension(value):
    ext = os.path.splitext(value.name)[1]  # [0] returns path + filename
    valid_extensions = [".xlsx"]
    if not ext.lower() in valid_extensions:
        raise ValidationError("Unsupported file extension. Allowed extensions: .xlsx")


def game_gps_data_file_path(instnace, filename):
    # MEDIA_ROOT / uploads/game_gps_data_files/<filename>
    return "uploads/game_gps_data_files/{0}".format(filename)


class GameGPSData(WajoModel):
    GAME_TYPE_CHOICES = [
        ("match", "Match"),
        ("training", "Training"),
    ]
    game_type = models.CharField(max_length=10, choices=GAME_TYPE_CHOICES)
    data_file = models.FileField(
        upload_to=game_gps_data_file_path, validators=[validate_file_extension]
    )
    notes = models.TextField(null=True, blank=True)
    is_processed = models.BooleanField(default=False)
    game = models.ForeignKey(
        Game, on_delete=models.SET_NULL, null=True, blank=True, related_name="gps_data"
    )

    created_on = models.DateTimeField(auto_now_add=True)
    updated_on = models.DateTimeField(auto_now=True)

    # process file with signal

    class Meta:
        verbose_name = "Game GPS Data"
        verbose_name_plural = "Game GPS Data"

    def __str__(self):
        return self.data_file.name


# Game Video Data
def game_video_data_file_path(instnace, filename):
    # MEDIA_ROOT / uploads/game_video_data_files/<filename>
    return "uploads/game_video_data_files/{0}".format(filename)


class GameVideoData(WajoModel):
    GAME_TYPE_CHOICES = [
        ("match", "Match"),
        ("training", "Training"),
    ]
    PROVIDER_CHOICES = [
        ("BEPRO", "BEPRO"),
    ]
    provider = models.CharField(max_length=16, choices=PROVIDER_CHOICES)
    game_type = models.CharField(max_length=10, choices=GAME_TYPE_CHOICES)
    data_file = models.FileField(
        upload_to=game_video_data_file_path, validators=[validate_file_extension]
    )
    notes = models.TextField(null=True, blank=True)
    is_processed = models.BooleanField(default=False)
    game = models.ForeignKey(
        Game,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="video_data",
    )
    first_half_url = models.TextField()
    first_half_padding = models.FloatField(
        default=0.0, verbose_name="First Half Padding (Seconds)"
    )

    second_half_url = models.TextField()
    second_half_padding = models.FloatField(
        default=0.0, verbose_name="Second Half Padding (Seconds)"
    )

    # start time padding is subttracted from start time
    start_time_padding = models.FloatField(
        default=0.0, verbose_name="Start Time Padding (Seconds)"
    )
    # end time padding is added to end time
    end_time_padding = models.FloatField(
        default=0.0, verbose_name="End Time Padding (Seconds)"
    )

    highlights_url = models.TextField()

    created_on = models.DateTimeField(auto_now_add=True)
    updated_on = models.DateTimeField(auto_now=True)

    # process file with signal

    class Meta:
        verbose_name = "Game Video Data"
        verbose_name_plural = "Game Video Data"

    def __str__(self):
        return self.data_file.name


# game video data json, process with signal on GameVideoData save
class GameMetaData(WajoModel):
    game = models.ForeignKey(
        Game,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="game_meta_data",
    )
    data = models.JSONField()

    created_on = models.DateTimeField(auto_now_add=True)
    updated_on = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Game Meta Data JSON"
        verbose_name_plural = "Game Meta Data JSON"

    def __str__(self):
        return self.game.name
