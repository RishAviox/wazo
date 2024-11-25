from django.contrib import admin
from core.admin import admin_site

from .models import Game, GameGPSData, GameVideoData
from .forms import GameAdminForm, GameGPSDataForm, GameVideoDataForm

    

class GameAdmin(admin.ModelAdmin):
    form = GameAdminForm
    list_display = ('id', 'type', 'name', 'date', 'created_on', 'updated_on', 'teams_display')
    list_filter = ('type',)
    search_fields = ('id', 'name')

    def teams_display(self, obj):
        return ", ".join([team.name for team in obj.teams.all()])
    teams_display.short_description = "Teams"


class GameGPSDataAdmin(admin.ModelAdmin):
    form = GameGPSDataForm
    list_display = ('id', 'data_file', 'game_type', 'game_display', 'is_processed', 'created_on', 'updated_on')
    readonly_fields = ('game',) 

    def game_display(self, obj):
        return obj.game.name if obj.game else "Unlinked"
    game_display.short_description = "Linked Game"


class GameVideoDataAdmin(admin.ModelAdmin):
    form = GameVideoDataForm
    list_display = ('id', 'data_file', 'game_type', 'provider', 'game_display', 'is_processed', 'created_on', 'updated_on')
    readonly_fields = ('game',)  

    def game_display(self, obj):
        return obj.game.name if obj.game else "Unlinked"
    game_display.short_description = "Linked Game"


admin_site.register(Game, GameAdmin)
admin_site.register(GameGPSData, GameGPSDataAdmin)
admin_site.register(GameVideoData, GameVideoDataAdmin)
