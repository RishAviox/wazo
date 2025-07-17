from core.admin import admin_site
from django.contrib import admin


from calendar_entry.models import CalendarEventEntry, CalendarGoalEntry

class CalendarEventEntryAdmin(admin.ModelAdmin):
    list_display = ['user', 'category', 'sub_category', 'date', 'repeat', 'start_time', 'end_time']

class CalendarGoalEntryAdmin(admin.ModelAdmin):
    list_display = ['user', 'category', 'title',  'start_date', 'end_date']

admin_site.register(CalendarEventEntry, CalendarEventEntryAdmin)
admin_site.register(CalendarGoalEntry, CalendarGoalEntryAdmin)
