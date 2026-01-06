from django.contrib import admin
from .models import *
from core.admin import admin_site


class WajoUserAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "name",
        "email",
        "phone_no",
        "selected_language",
        "role",
        "created_on",
        "updated_on",
    )


class WajoUserDeviceAdmin(admin.ModelAdmin):
    list_display = ["user", "fcm_token", "created_on", "updated_on"]


class PlayerIDMappingAdmin(admin.ModelAdmin):
    list_display = ["user", "player_id", "player_position", "created_on", "updated_on"]


class OTPStoreAdmin(admin.ModelAdmin):
    list_display = ["phone_no", "data", "is_used", "created_on"]


class UserRequestAdmin(admin.ModelAdmin):
    list_display = ["user", "request_type", "status", "requested_at", "processed_at"]
    list_filter = ["request_type", "status", "requested_at"]
    search_fields = ["user__phone_no", "description"]


admin_site.register(WajoUser, WajoUserAdmin)
admin_site.register(WajoUserDevice, WajoUserDeviceAdmin)
admin_site.register(PlayerIDMapping, PlayerIDMappingAdmin)
admin_site.register(OTPStore, OTPStoreAdmin)
admin_site.register(UserRequest, UserRequestAdmin)
