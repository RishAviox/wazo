from django.contrib import admin
from core.admin import admin_site

from .models import Game, GameGPSData, GameVideoData, GameMetaData, GameUserRole
from .forms import GameAdminForm, GameGPSDataForm, GameVideoDataForm


class GameAdmin(admin.ModelAdmin):
    form = GameAdminForm
    list_display = (
        "id",
        "type",
        "name",
        "date",
        "created_on",
        "updated_on",
        "teams_display",
    )
    list_filter = ("type",)
    search_fields = ("id", "name")

    def teams_display(self, obj):
        return ", ".join([team.name for team in obj.teams.all()])

    teams_display.short_description = "Teams"


class GameGPSDataAdmin(admin.ModelAdmin):
    form = GameGPSDataForm
    list_display = (
        "id",
        "data_file",
        "game_type",
        "game_display",
        "is_processed",
        "created_on",
        "updated_on",
    )
    readonly_fields = ("game",)

    def game_display(self, obj):
        return obj.game.name if obj.game else "Unlinked"

    game_display.short_description = "Linked Game"


class GameVideoDataAdmin(admin.ModelAdmin):
    form = GameVideoDataForm
    list_display = (
        "id",
        "data_file",
        "game_type",
        "provider",
        "game_display",
        "is_processed",
        "created_on",
        "updated_on",
    )
    readonly_fields = ("game",)

    def game_display(self, obj):
        return obj.game.name if obj.game else "Unlinked"

    game_display.short_description = "Linked Game"


class GameMetaDataAdmin(admin.ModelAdmin):
    list_display = ("id", "game_display", "created_on", "updated_on")
    readonly_fields = ("game",)

    def game_display(self, obj):
        return obj.game.name if obj.game else "Unlinked"

    game_display.short_description = "Linked Game"


class GameUserRoleAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user_display",
        "user_role_display",
        "game_display",
        "created_on",
        "updated_on",
    )
    list_filter = ("game", "user__role", "created_on")
    search_fields = (
        "user__phone_no",
        "game__id",
        "game__name",
        "user__role",
    )
    raw_id_fields = ("game", "user")

    def user_display(self, obj):
        return obj.user.phone_no if obj.user else "Unknown"

    user_display.short_description = "User"

    def user_role_display(self, obj):
        return obj.user.role if obj.user and obj.user.role else "No Role"

    user_role_display.short_description = "User Role"

    def game_display(self, obj):
        return f"{obj.game.id} - {obj.game.name}" if obj.game else "Unknown"

    game_display.short_description = "Game"


admin_site.register(Game, GameAdmin)
admin_site.register(GameGPSData, GameGPSDataAdmin)
admin_site.register(GameVideoData, GameVideoDataAdmin)
admin_site.register(GameMetaData, GameMetaDataAdmin)
admin_site.register(GameUserRole, GameUserRoleAdmin)
