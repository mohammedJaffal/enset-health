from django.contrib import admin
from .models import HealthRecord


@admin.register(HealthRecord)
class HealthRecordAdmin(admin.ModelAdmin):
    list_display = ['user', 'date', 'heart_rate', 'sleep_hours', 'steps', 'created_at']
    list_filter = ['user', 'date', 'created_at']
    search_fields = ['date', 'user__username']
    date_hierarchy = 'date'
    ordering = ['-date']
