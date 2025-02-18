from core.admin import admin_site

from calendar_entry.models import CalendarEventEntry, CalendarGoalEntry


admin_site.register(CalendarEventEntry)
admin_site.register(CalendarGoalEntry)
