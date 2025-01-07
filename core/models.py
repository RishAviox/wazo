from django.db import models
from accounts.models import WajoUser

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
    
    class Meta:
        verbose_name = "API Log"
        verbose_name_plural = "API Logs"

