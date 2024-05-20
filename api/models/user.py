from django.db import models
from django.utils import timezone


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
    problems = models.TextField(blank=True, null=True)
    activities = models.TextField(blank=True, null=True)
    picture = models.ImageField(blank=True, null=True, upload_to=profile_picture_path)
    location = models.CharField(max_length=255, blank=True, null=True)
    affiliation = models.CharField(max_length=255, blank=True, null=True)
    
    created_on = models.DateTimeField(auto_now_add=True)
    updated_on = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.phone_no
    
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
        return self.user.phone_no
    
    class Meta:
        unique_together = ('user', 'fcm_token')

