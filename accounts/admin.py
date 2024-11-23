from django.contrib import admin
from .models import *

@admin.register(WajoUser)
class WajoUserAdmin(admin.ModelAdmin):
    list_display = ('phone_no', 'name', 'selected_language', 'role', 'created_on', 'updated_on', )
