from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import os
import uuid


class FileNode(models.Model):
    """
    Represents both files and folders in the NAS tree.
    is_folder=True  → directory node
    is_folder=False → file node
    """
    NODE_TYPES = [
        ('file', 'File'),
        ('folder', 'Folder'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='file_nodes')
    parent = models.ForeignKey(
        'self', null=True, blank=True,
        on_delete=models.CASCADE, related_name='children'
    )
    name = models.CharField(max_length=255)
    is_folder = models.BooleanField(default=False)
    # relative path inside NAS_STORAGE_ROOT (only for files)
    storage_path = models.CharField(max_length=1024, blank=True)
    size = models.BigIntegerField(default=0)  # bytes
    mime_type = models.CharField(max_length=128, blank=True)
    is_starred = models.BooleanField(default=False)
    is_trashed = models.BooleanField(default=False)
    trashed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-is_folder', 'name']
        unique_together = [('parent', 'name', 'owner')]

    def __str__(self):
        return self.name

    @property
    def extension(self):
        if self.is_folder:
            return ''
        _, ext = os.path.splitext(self.name)
        return ext.lower().lstrip('.')

    @property
    def icon_class(self):
        ext = self.extension
        mapping = {
            'pdf': 'icon-pdf',
            'doc': 'icon-word', 'docx': 'icon-word',
            'xls': 'icon-excel', 'xlsx': 'icon-excel',
            'ppt': 'icon-ppt', 'pptx': 'icon-ppt',
            'jpg': 'icon-image', 'jpeg': 'icon-image',
            'png': 'icon-image', 'gif': 'icon-image', 'webp': 'icon-image',
            'mp4': 'icon-video', 'mov': 'icon-video', 'avi': 'icon-video', 'mkv': 'icon-video',
            'mp3': 'icon-audio', 'wav': 'icon-audio', 'flac': 'icon-audio',
            'zip': 'icon-archive', 'rar': 'icon-archive', '7z': 'icon-archive', 'tar': 'icon-archive',
            'py': 'icon-code', 'js': 'icon-code', 'ts': 'icon-code',
            'html': 'icon-code', 'css': 'icon-code', 'json': 'icon-code',
            'txt': 'icon-text', 'md': 'icon-text',
        }
        return mapping.get(ext, 'icon-file')

    @property
    def human_size(self):
        if self.is_folder:
            return '—'
        size = self.size
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024:
                return f'{size:.1f} {unit}'
            size /= 1024
        return f'{size:.1f} PB'

    def get_breadcrumb(self):
        """Return list of ancestors from root to self."""
        crumbs = []
        node = self
        while node:
            crumbs.insert(0, node)
            node = node.parent
        return crumbs

    def get_absolute_storage_path(self):
        from django.conf import settings
        return os.path.join(str(settings.NAS_STORAGE_ROOT), self.storage_path)


class ShareLink(models.Model):
    """Public share link for a file or folder."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    node = models.ForeignKey(FileNode, on_delete=models.CASCADE, related_name='share_links')
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    token = models.CharField(max_length=64, unique=True)
    password = models.CharField(max_length=128, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    allow_download = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f'Share: {self.node.name}'

    @property
    def is_expired(self):
        if self.expires_at and timezone.now() > self.expires_at:
            return True
        return False


class ActivityLog(models.Model):
    """บันทึกกิจกรรมของผู้ใช้"""
    ACTION_CHOICES = [
        ('upload',   'Upload'),
        ('download', 'Download'),
        ('delete',   'Delete'),
        ('rename',   'Rename'),
        ('move',     'Move'),
        ('share',    'Share'),
        ('login',    'Login'),
        ('logout',   'Logout'),
    ]

    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='activity_logs')
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    detail = models.CharField(max_length=512, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.user} — {self.action} — {self.created_at:%Y-%m-%d %H:%M}'


class SystemSettings(models.Model):
    """ตั้งค่าระบบ (singleton — pk=1 เสมอ)"""
    storage_root        = models.CharField(max_length=512, blank=True)
    default_quota_gb    = models.IntegerField(default=0)
    max_upload_gb       = models.IntegerField(default=10)
    trash_retention_days = models.IntegerField(default=1)
    auto_purge          = models.BooleanField(default=False)
    share_expire_days   = models.IntegerField(default=0)
    allow_register      = models.BooleanField(default=False)
    enable_logging      = models.BooleanField(default=True)
    log_retention_days  = models.IntegerField(default=90)

    class Meta:
        verbose_name = 'System Settings'

    @classmethod
    def get(cls):
        from django.conf import settings as django_settings
        obj, _ = cls.objects.get_or_create(
            pk=1,
            defaults={'storage_root': str(django_settings.NAS_STORAGE_ROOT)},
        )
        return obj

    def __str__(self):
        return 'System Settings'


class UserProfile(models.Model):
    """ข้อมูลเพิ่มเติมของ User"""
    user            = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    custom_quota_gb = models.IntegerField(
        null=True, blank=True,
        help_text='quota เฉพาะบุคคล (GB) — None = ใช้ค่า default จาก SystemSettings'
    )

    def __str__(self):
        return f'Profile({self.user.username})'

    @classmethod
    def get_for(cls, user):
        profile, _ = cls.objects.get_or_create(user=user)
        return profile

    @property
    def effective_quota_gb(self):
        """quota จริงที่ใช้ — custom ถ้ากำหนด ไม่งั้นใช้ default"""
        if self.custom_quota_gb is not None:
            return self.custom_quota_gb
        try:
            return SystemSettings.get().default_quota_gb
        except Exception:
            return 0


class BackupConfig(models.Model):
    """ตั้งค่า Backup"""
    SCHEDULE_CHOICES = [
        ('manual', 'Manual เท่านั้น'),
        ('daily',  'ทุกวัน'),
        ('weekly', 'ทุกสัปดาห์'),
    ]

    destination_path  = models.CharField(max_length=1024, blank=True, help_text='Path ปลายทาง เช่น D:\\Backup หรือ /mnt/backup')
    enabled           = models.BooleanField(default=False)
    schedule          = models.CharField(max_length=20, choices=SCHEDULE_CHOICES, default='manual')
    schedule_hour     = models.IntegerField(default=2, help_text='ชั่วโมงที่ทำ backup (0-23)')
    schedule_weekday  = models.IntegerField(default=0, help_text='วันที่ทำ backup (0=จันทร์ ... 6=อาทิตย์) สำหรับ weekly')
    keep_versions     = models.IntegerField(default=3, help_text='จำนวนรุ่นที่เก็บไว้')
    include_trashed   = models.BooleanField(default=False)
    created_at        = models.DateTimeField(default=timezone.now)
    updated_at        = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Backup Config'

    @classmethod
    def get(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def __str__(self):
        return f'Backup → {self.destination_path or "(ยังไม่ตั้งค่า)"}'


class BackupLog(models.Model):
    """ประวัติการ Backup"""
    STATUS_CHOICES = [
        ('running',  'กำลังทำงาน'),
        ('success',  'สำเร็จ'),
        ('failed',   'ล้มเหลว'),
    ]

    started_at   = models.DateTimeField(default=timezone.now)
    finished_at  = models.DateTimeField(null=True, blank=True)
    status       = models.CharField(max_length=20, choices=STATUS_CHOICES, default='running')
    triggered_by = models.CharField(max_length=50, default='manual')  # 'manual' | 'schedule'
    destination  = models.CharField(max_length=1024, blank=True)
    files_copied = models.IntegerField(default=0)
    bytes_copied = models.BigIntegerField(default=0)
    version_name = models.CharField(max_length=100, blank=True)
    error        = models.TextField(blank=True)

    class Meta:
        ordering = ['-started_at']

    def __str__(self):
        return f'Backup {self.started_at:%Y-%m-%d %H:%M} — {self.status}'

    @property
    def duration(self):
        if self.finished_at and self.started_at:
            secs = int((self.finished_at - self.started_at).total_seconds())
            if secs < 60:
                return f'{secs} วินาที'
            return f'{secs // 60} นาที {secs % 60} วินาที'
        return '—'

    @property
    def bytes_human(self):
        size = self.bytes_copied
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024:
                return f'{size:.1f} {unit}'
            size /= 1024
        return f'{size:.1f} PB'