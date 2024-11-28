from django.contrib import admin
from core.admin import admin_site
from .models import Team, TeamStats

class TeamAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'created_on', 'updated_on', 'coaches_display')
    search_fields = ('id', 'name')

    def coaches_display(self, obj):
        return ", ".join([coach.name for coach in obj.coach.all()])
    coaches_display.short_description = "Coaches"
    
class TeamStatsAdmin(admin.ModelAdmin):
    list_display = ('id', 'team', 'game', 'created_on', 'updated_on')
    search_fields = ('team',)


admin_site.register(Team, TeamAdmin)
admin_site.register(TeamStats, TeamStatsAdmin)