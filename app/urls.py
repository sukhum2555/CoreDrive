from django.urls import path
from . import views
from . import admin_views

urlpatterns = [
    # Browser
    path('', views.index, name='index'),
    path('folder/<uuid:folder_id>/', views.browse, name='browse'),

    # Special views
    path('starred/', views.starred, name='starred'),
    path('trash/', views.trash, name='trash'),
    path('trash/empty/', views.empty_trash, name='empty_trash'),

    # File actions
    path('upload/', views.upload_files, name='upload_files'),
    path('folder/new/', views.create_folder, name='create_folder'),
    path('file/<uuid:file_id>/download/', views.download_file, name='download_file'),
    path('file/<uuid:file_id>/serve/', views.serve_file, name='serve_file'),
    path('file/<uuid:file_id>/preview/', views.preview_file, name='preview_file'),

    # Node actions
    path('node/<uuid:node_id>/rename/', views.rename_node, name='rename_node'),
    path('node/<uuid:node_id>/move/', views.move_node, name='move_node'),
    path('node/<uuid:node_id>/trash/', views.trash_node, name='trash_node'),
    path('node/<uuid:node_id>/restore/', views.restore_node, name='restore_node'),
    path('node/<uuid:node_id>/delete/', views.delete_node_permanently, name='delete_node'),
    path('node/<uuid:node_id>/star/', views.toggle_star, name='toggle_star'),
    path('node/<uuid:node_id>/share/', views.create_share, name='create_share'),
    path('node/<uuid:node_id>/detail/', views.node_detail_api, name='node_detail_api'),

    # Public share
    path('share/<str:token>/', views.shared_file, name='shared_file'),
    path('share/<str:token>/folder/<uuid:folder_id>/', views.shared_folder_browse, name='shared_folder_browse'),
    path('share/<str:token>/download/<uuid:file_id>/', views.shared_file_download, name='shared_file_download'),

    # System API
    path('api/drives/', views.drives_api, name='drives_api'),

    # ─── Admin ───────────────────────────────────────────────
    path('nas-admin/', admin_views.admin_dashboard, name='admin_dashboard'),
    path('nas-admin/users/', admin_views.admin_users, name='admin_users'),
    path('nas-admin/users/add/', admin_views.admin_user_add, name='admin_user_add'),
    path('nas-admin/users/<int:user_id>/toggle/', admin_views.admin_user_toggle, name='admin_user_toggle'),
    path('nas-admin/users/<int:user_id>/quota/', admin_views.admin_user_quota, name='admin_user_quota'),
    path('nas-admin/users/<int:user_id>/delete/', admin_views.admin_user_delete, name='admin_user_delete'),
    path('nas-admin/logs/', admin_views.admin_logs, name='admin_logs'),
    path('nas-admin/settings/', admin_views.admin_settings, name='admin_settings'),
    path('nas-admin/backup/save/', admin_views.admin_backup_save, name='admin_backup_save'),
    path('nas-admin/backup/run/', admin_views.admin_backup_run, name='admin_backup_run'),
    path('nas-admin/backup/status/', admin_views.admin_backup_status, name='admin_backup_status'),
    path('nas-admin/api/storage/drives/', admin_views.storage_drives_api, name='storage_drives_api'),
    path('nas-admin/api/storage/browse/', admin_views.storage_browse_api, name='storage_browse_api'),
]