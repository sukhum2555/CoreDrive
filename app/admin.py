from django.contrib import admin
from .models import FileNode, ShareLink, ActivityLog, SystemSettings


@admin.register(FileNode)
class FileNodeAdmin(admin.ModelAdmin):
    list_display = ['name', 'owner', 'is_folder', 'human_size', 'is_starred', 'is_trashed', 'updated_at']
    list_filter = ['is_folder', 'is_starred', 'is_trashed', 'owner']
    search_fields = ['name', 'owner__username']
    readonly_fields = ['id', 'created_at', 'updated_at']


@admin.register(ShareLink)
class ShareLinkAdmin(admin.ModelAdmin):
    list_display = ['node', 'created_by', 'token', 'expires_at', 'created_at']
    list_filter = ['created_by']
    search_fields = ['node__name', 'created_by__username']


@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = ['created_at', 'user', 'action', 'detail', 'ip_address']
    list_filter = ['action', 'user']
    search_fields = ['user__username', 'detail']
    readonly_fields = ['created_at']


@admin.register(SystemSettings)
class SystemSettingsAdmin(admin.ModelAdmin):
    pass