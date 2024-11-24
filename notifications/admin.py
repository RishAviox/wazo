from django.contrib import admin
from .models import Notification
from core.admin import admin_site

class NotificationAdmin(admin.ModelAdmin):
    list_display = ['user', 'device', 'title', 'body', 'postback', 'created_on']

admin_site.register(Notification, NotificationAdmin)
