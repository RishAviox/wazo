from django.contrib import admin
from .models import WajoUser, APILog

# Register your models here.

class WajoUserAdmin(admin.ModelAdmin):
    list_display = ('phone_no', 'selected_language', 'fcm_token', 'created_on', 'updated_on', )

class APILogAdmin(admin.ModelAdmin):
    list_display = ['user', 'method', 'path', 'status_code', 'created_at']
    list_filter = ['method', 'status_code', 'created_at']
    search_fields = ['path']


admin.site.register(WajoUser, WajoUserAdmin)
admin.site.register(APILog, APILogAdmin)