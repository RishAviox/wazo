from django.contrib import admin
from .models import WajoUser

# Register your models here.

class WajoUserAdmin(admin.ModelAdmin):
    list_display = ('phone_no', 'selected_language', 'fcm_token', 'created_on', 'updated_on', )

admin.site.register(WajoUser, WajoUserAdmin)