from django.contrib.admin import AdminSite
from django.contrib.auth.models import User
from django.contrib.auth.admin import UserAdmin
from django.contrib import admin
from .models import APILog

class WajoAdminSite(AdminSite):
    site_header = "Wajo Admin"
    site_title = "Wajo Admin Portal"
    index_title = "Welcome to Wajo Admin Dashboard"

    # Define the desired app order
    APP_ORDER = [
        "Accounts",
        "Onboarding",
        "Games",
        "Teams",
        "Cards",
        "Questionnaire",
        "Events",
        "Notifications",
        "Core",
    ]

    # Define custom order for models in specific apps
    APP_MODEL_ORDER = {
        "Accounts": [
            "Wajo Users",
            "Wajo User Devices",
            "Player ID Mappings",
            "OTP Store",
        ],
        "Onboarding": [
            'Onboarding Flow',
        ],
        "Games": [
            "Games",
            "Game GPS Data",
            "Game Video Data",
        ],
        "Teams": [
            "Teams",
        ],
        "Cards": [
            "Status Card Metrics",
            "RPE Metrics",
            "Attacking Skills",
            "Video Card Defensive",
            "Video Card Distributions",
            "GPS-Athletic Skills",
            "GPS-Football Abilities",
            "Training Card Data (JSON)",
            "News Card Data (JSON)",
        ],
        "Questionnaire": [
            'Daily Wellness Questionnaire',
            'Daily Wellness User Responses',
            'RPE Questionnaire',
            'RPE User Responses',
            'Card Suggested Actions',
            'Schedule Planning Questionnaire',
            'Schedule Planning User Responses',
        ],
        "Events": [
            'One Time Events',
            'Recurring Events',
            'Match Events Data Files',
        ],
        "Notifications": [
            'Notifications',
        ],
        "Core": [
            'API Logs',
        ]
    }

    def get_app_list(self, request, app_label=None):
        app_list = super().get_app_list(request)

        # Helper function to sort models within an app
        def sort_models(app):
            if app["name"] in self.APP_MODEL_ORDER:
                desired_order = self.APP_MODEL_ORDER[app["name"]]
                app["models"].sort(
                    key=lambda model: desired_order.index(model["name"])
                    if model["name"] in desired_order else len(desired_order)
                )

        # Sort apps and models
        app_list.sort(
            key=lambda app: (
                self.APP_ORDER.index(app["name"])
                if app["name"] in self.APP_ORDER else len(self.APP_ORDER)
            )
        )

        # Ensure "Authentication and Authorization" is placed last
        app_list.sort(key=lambda app: 1 if app["name"] == "Authentication and Authorization" else 0)

        # Sort models within each app
        for app in app_list:
            sort_models(app)

        return app_list
    

admin_site = WajoAdminSite(name='wajo_admin')


class APILogAdmin(admin.ModelAdmin):
    list_display = ['user', 'method', 'path', 'status_code', 'created_on']
    list_filter = ['method', 'status_code', 'created_on']
    search_fields = ['path']

# add user to panel
admin_site.register(User, UserAdmin)
admin_site.register(APILog, APILogAdmin)

