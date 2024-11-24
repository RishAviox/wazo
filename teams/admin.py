from django.contrib import admin
from core.admin import admin_site
from .models import Team

class TeamAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'created_on', 'updated_on', 'coaches_display')
    search_fields = ('id', 'name')

    def coaches_display(self, obj):
        return ", ".join([coach.name for coach in obj.coach.all()])
    coaches_display.short_description = "Coaches"

admin_site.register(Team, TeamAdmin)