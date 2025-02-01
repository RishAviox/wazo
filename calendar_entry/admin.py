from django.contrib import admin

from calendar_entry.models import CalendarEventEntry, CalendarGoalEntry


admin.site.register(CalendarEventEntry)
admin.site.register(CalendarGoalEntry)
