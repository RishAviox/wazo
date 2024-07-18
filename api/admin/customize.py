from django.contrib.admin import AdminSite
from django.contrib.auth.models import User
from django.contrib.auth.admin import UserAdmin

class CustomAdminSite(AdminSite):
    site_header = 'Wajo Administration'
    site_title = 'Admin'
    index_title = 'Wajo Administration'

    def get_app_list(self, request, app_label=None):
        app_list = super().get_app_list(request)
        for app in app_list:
            if app['name'] == 'Api':
                # Define the desired order of models
                desired_order = [
                    'Wajo Users',
                    'Wajo User Devices',
                    'Onboarding Flow',
                    'Status Card Metrics',
                    'Daily Wellness Questionnaire',
                    'Daily Wellness User Responses',
                    'RPE Questionnaire',
                    'RPE User Responses',
                    'Card Suggested Actions',
                    'Schedule Planning Questionnaire',
                    'Schedule Planning User Responses',
                    'One Time Events',
                    'Recurring Events',
                    'Match Events Data Files',
                    'OTP Store',
                    'API Logs',
                    'Activities Questionnaire',
                ]
                
                # Sort the models according to the desired order
                app['models'].sort(
                    key=lambda x: desired_order.index(x['name'])
                    if x['name'] in desired_order else len(desired_order)
                )
        return app_list
    

# Initialize the custom admin site
admin_site = CustomAdminSite(name='custom_admin')

# add user to panel
admin_site.register(User, UserAdmin)