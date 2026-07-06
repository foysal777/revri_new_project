from django.contrib import admin
from .models import User, UserReport, UserBlock

# admin.site.register(User) # Handled dynamically in project_root/urls.py with full columns
admin.site.register(UserReport)
admin.site.register(UserBlock)