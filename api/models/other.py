from django.db import models
from django.utils import timezone
from .user import WajoUser


# Store OTP
class OTPStore(models.Model):
    phone_no = models.CharField(max_length=15)
    data = models.CharField(max_length=6)
    is_used = models.BooleanField(default=False)
    created_on = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"OTP {self.data} for {self.phone_no}"
    
    def is_valid(self):
        time_valid = timezone.now() - self.created_on < timezone.timedelta(minutes=5)
        return time_valid and not self.is_used

    
# store api logs
class APILog(models.Model):
    user = models.ForeignKey(WajoUser, on_delete=models.SET_NULL, null=True, blank=True)
    method = models.CharField(max_length=10)
    path = models.CharField(max_length=255)
    status_code = models.IntegerField()
    request_body = models.TextField(blank=True, null=True)
    response_message = models.TextField(blank=True, null=True)
    created_on = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.method} {self.path} {self.status_code} {self.created_on}"

