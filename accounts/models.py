from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.conf import settings

from core.soft_delete import WajoModel


# On creating WajoUser, new OnboardingStep instance will be created using signals
# refer signals.py

def profile_picture_path(instnace, filename):
    # MEDIA_ROOT / uploads/user_phone_no/profile_picture/<filename>
    return 'uploads/user_{0}/profile_picture/{1}'.format(instnace.phone_no, filename)

class WajoUser(models.Model):
    phone_no = models.CharField(max_length=15, unique=True, primary_key=True)
    selected_language = models.CharField(max_length=15)
    # fcm_token = models.CharField(max_length=255)
    # we have WajoUserDevice to store FCM tokens

    # Onboarding Profile
    name = models.CharField(max_length=50, blank=True, null=True)
    nickname = models.CharField(max_length=50, blank=True, null=True)
    gender = models.CharField(max_length=15, blank=True, null=True)
    dob = models.DateField(blank=True, null=True)
    primary_sport = models.CharField(max_length=50, blank=True, null=True)
    role = models.CharField(max_length=50, blank=True, null=True)
    wake_up_time = models.TimeField(blank=True, null=True)
    sleep_time = models.TimeField(blank=True, null=True)
    picture = models.ImageField(blank=True, null=True, upload_to=profile_picture_path)

    # Self-referential many-to-many relationship
    coach = models.ManyToManyField('self', related_name='players',
                                blank=True,
                                limit_choices_to={'role': 'Coach'},
                                symmetrical=False, 
                            )
    """
        symmetrical=False meaning
        if Player1 has Coach1 as a coach, 
        it doesn't mean that Coach1 automatically has Player1 as a coach. 
        The relationship is one-way: coaches are assigned to players,
        but not the other way around.
    """

    
    created_on = models.DateTimeField(auto_now_add=True)
    updated_on = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Wajo User"
        verbose_name_plural = "Wajo Users"


    def clean(self):
        # Ensure that only players can have a coach
        if self.role == 'Coach' and self.coach.exists():
            raise ValidationError("A coach cannot have another coach assigned.")
         
        # Track if the role is changing from 'Coach' to 'Player'
        if self.pk:  # If this is not a new object
            previous = WajoUser.objects.get(pk=self.pk)
            if previous.role == 'Coach' and self.role != 'Coach':
                # Remove this user as a coach for any players
                print("Players before clearing: ", self.players.all())
                self.players.clear()  # Clears all players related to this coach
                # If you want to also remove them from any CoachTeamMapping
        #         CoachTeamMapping.objects.filter(coach=self).delete()

    def save(self, *args, **kwargs):
        self.clean()  # Call the clean method to enforce the validation
        super().save(*args, **kwargs)

    def __str__(self):
        return self.phone_no + " - " + self.name if self.name else self.phone_no
    
    @property
    def is_authenticated(self):
        """Always return True for compatibility with Django's authentication system."""
        return True

# Store FCM Tokens
class WajoUserDevice(models.Model):
    user = models.ForeignKey(WajoUser, on_delete=models.CASCADE, related_name="devices")
    fcm_token = models.CharField(max_length=255)
    created_on = models.DateTimeField(auto_now_add=True)
    updated_on = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return str(self.user.phone_no) + "--->" + self.fcm_token
    
    class Meta:
        unique_together = ('user', 'fcm_token')
        verbose_name = "Wajo User Device"
        verbose_name_plural = "Wajo User Devices"


# Map player id with the user
POSITION_CHOICES = [
        ('GK', 'Goalkeeper'),
        ('CB', 'Center Back'),
        ('LB', 'Left Back'),
        ('RB', 'Right Back'),
        ('LWB', 'Left Wing Back'),
        ('RWB', 'Right Wing Back'),
        ('CDM', 'Central Defensive Midfielder'),
        ('CM', 'Central Midfielder'),
        ('CAM', 'Central Attacking Midfielder'),
        ('LM', 'Left Midfielder'),
        ('RM', 'Right Midfielder'),
        ('LW', 'Left Winger'),
        ('RW', 'Right Winger'),
        ('ST', 'Striker'),
        ('CF', 'Center Forward'),
    ]
class PlayerIDMapping(WajoModel):
    user = models.ForeignKey(WajoUser, on_delete=models.CASCADE, related_name="player_ids")
    player_id = models.CharField(max_length=10, unique=True)
    player_position = models.CharField(max_length=10, choices=POSITION_CHOICES, default='ST')
    
    created_on = models.DateTimeField(auto_now_add=True)
    updated_on = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return self.player_id
    
    class Meta:
        verbose_name = "Player ID Mappings"
        verbose_name_plural = "Player ID Mappings"
        constraints = [
            models.UniqueConstraint(fields=['user'],  name='accounts_unique_user_player_id_mapping')
        ]


# Store OTP
class OTPStore(models.Model):
    phone_no = models.CharField(max_length=15)
    data = models.CharField(max_length=6)
    is_used = models.BooleanField(default=False)
    created_on = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"OTP {self.data} for {self.phone_no}"
    
    def is_valid(self):
        time_valid = timezone.now() - self.created_on < timezone.timedelta(minutes=settings.OTP_EXPIRATION_TIME)
        return time_valid and not self.is_used
    
    class Meta:
        verbose_name = "OTP Store"
        verbose_name_plural = "OTP Store"


class UserRequest(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    )
    REQUEST_TYPE_CHOICES = (
        ('account_deletion', 'Account Deletion'),
    )
    # Link the request to the user
    user = models.ForeignKey(WajoUser, on_delete=models.CASCADE, related_name='requests')
    request_type = models.CharField(max_length=50, choices=REQUEST_TYPE_CHOICES)
    description = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    requested_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    admin_notes = models.TextField(blank=True, null=True)
    
    def __str__(self):
        return f"Request by {self.user.phone_no} - Type: {self.request_type} (Status: {self.status})"

    class Meta:
        verbose_name = 'User Request'
        verbose_name_plural = 'User Requests'
