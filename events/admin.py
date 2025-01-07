from django.contrib import admin
import os
from .models import *
from core.admin import admin_site

class RecurringEventsAdmin(admin.ModelAdmin):
    list_display = ['user', 'event_type', 'event', 'date', 'frequency', 'created_on', 'updated_on']


class OneTimeEventsAdmin(admin.ModelAdmin):
    list_display = ['user', 'event_type', 'event', 'date', 'created_on', 'updated_on']


class MatchEventsDataFileAdmin(admin.ModelAdmin):
    list_display = ['name', 'get_filename', '_type', 'notes', 'created_on', 'updated_on']

    def get_filename(self, obj):
        return os.path.basename(obj.file.name)
    get_filename.short_description = 'File'


admin_site.register(RecurringEvents, RecurringEventsAdmin)
admin_site.register(OneTimeEvents, OneTimeEventsAdmin)
admin_site.register(MatchEventsDataFile, MatchEventsDataFileAdmin)