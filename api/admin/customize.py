from django.contrib.admin import AdminSite

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
                    'Wajo users',
                    'Onboarding Flow',
                    'Wajo user devices',
                    'Daily wellness questionnaires',
                    'Daily wellness user responses',
                    'Rpe questionnaires',
                    'Rpe user responses',
                    'Card suggested actions',
                    'Otp stores',
                    'Api logs',
                ]
                
                # Sort the models according to the desired order
                app['models'].sort(
                    key=lambda x: desired_order.index(x['name'])
                    if x['name'] in desired_order else len(desired_order)
                )
        return app_list
    

# Initialize the custom admin site
admin_site = CustomAdminSite(name='custom_admin')