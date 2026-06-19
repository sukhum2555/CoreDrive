import os
import re
from pathlib import Path

from django.conf import settings


def sanitize_filename(name: str) -> str:
    """Remove dangerous characters from filename."""
    name = name.strip()
    # Remove path separators and null bytes
    name = re.sub(r'[/\\<>:"|?*\x00]', '_', name)
    # Collapse multiple underscores
    name = re.sub(r'_+', '_', name)
    return name[:255] or 'unnamed'


def get_storage_path_for_node(user_id, filename):
    """Build a relative storage path under NAS_STORAGE_ROOT."""
    return f'{user_id}/{filename}'


def get_total_storage_used(user):
    """Return (used_bytes, total_bytes) from actual disk partition."""
    try:
        import psutil
        from django.conf import settings as django_settings
        try:
            from .models import SystemSettings
            s = SystemSettings.get()
            root = s.storage_root or str(django_settings.NAS_STORAGE_ROOT)
        except Exception:
            root = str(django_settings.NAS_STORAGE_ROOT)
        disk = psutil.disk_usage(root)
        return disk.used, disk.total
    except Exception:
        return 0, 1


def get_user_storage_info(user):
    """
    คืน storage info ที่เหมาะกับ user นั้นๆ
    - admin/staff → disk จริงทั้งหมด (เหมือนเดิม)
    - user ทั่วไป + quota > 0 → ใช้ไปกี่ GB จาก quota ที่กำหนด
    - user ทั่วไป + quota = 0 → disk จริง (ไม่จำกัด)
    คืน dict: { used, total, used_h, total_h, pct, is_quota }
    """
    from django.db.models import Sum
    from .models import FileNode, SystemSettings, UserProfile

    try:
        s = SystemSettings.get()
        default_quota_gb = s.default_quota_gb
    except Exception:
        default_quota_gb = 0

    # admin/staff ไม่มีการจำกัด → แสดง disk จริง
    if user.is_staff or user.is_superuser:
        disk_used, disk_total = get_total_storage_used(user)
        return {
            'used':     disk_used,
            'total':    disk_total,
            'used_h':   _human_size(disk_used),
            'total_h':  _human_size(disk_total),
            'pct':      min(int(disk_used / disk_total * 100), 100) if disk_total else 0,
            'is_quota': False,
        }

    # ดึง quota เฉพาะบุคคล (ถ้ามี) ไม่งั้นใช้ default
    profile = UserProfile.get_for(user)
    quota_gb = profile.effective_quota_gb

    if quota_gb == 0:
        # ไม่จำกัด → แสดง disk จริง
        disk_used, disk_total = get_total_storage_used(user)
        return {
            'used':     disk_used,
            'total':    disk_total,
            'used_h':   _human_size(disk_used),
            'total_h':  _human_size(disk_total),
            'pct':      min(int(disk_used / disk_total * 100), 100) if disk_total else 0,
            'is_quota': False,
        }

    # user ทั่วไป + มี quota → คำนวณจาก DB
    user_used = FileNode.objects.filter(
        owner=user, is_folder=False, is_trashed=False
    ).aggregate(t=Sum('size'))['t'] or 0

    quota_bytes = quota_gb * 1024 ** 3
    pct = min(int(user_used / quota_bytes * 100), 100) if quota_bytes else 0
    return {
        'used':     user_used,
        'total':    quota_bytes,
        'used_h':   _human_size(user_used),
        'total_h':  _human_size(quota_bytes),
        'pct':      pct,
        'is_quota': True,
    }


def get_all_drives():
    """
    Return list of dicts with real disk info for every mounted partition.
    Works on Windows (C:\\, D:\\, ...) and Linux/macOS (/dev/sda1, ...).
    Each dict: { name, mountpoint, total, used, free, percent, total_h, used_h, free_h }
    """
    try:
        import psutil
        drives = []
        for part in psutil.disk_partitions(all=False):
            try:
                usage = psutil.disk_usage(part.mountpoint)
            except (PermissionError, OSError):
                continue
            # Friendly name: Windows → "C:" , Linux → "/dev/sda1" or mountpoint
            name = part.device
            if os.name == 'nt':
                name = part.device.rstrip('\\')   # "C:"
            drives.append({
                'name':       name,
                'mountpoint': part.mountpoint,
                'fstype':     part.fstype,
                'total':      usage.total,
                'used':       usage.used,
                'free':       usage.free,
                'percent':    usage.percent,
                'total_h':    _human_size(usage.total),
                'used_h':     _human_size(usage.used),
                'free_h':     _human_size(usage.free),
            })
        return drives
    except ImportError:
        return []


def _human_size(size):
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size < 1024:
            return f'{size:.1f} {unit}'
        size /= 1024
    return f'{size:.1f} PB'


def iter_file_range(path, start, length, chunk=65536):
    """Generator for HTTP Range responses."""
    with open(path, 'rb') as f:
        f.seek(start)
        remaining = length
        while remaining > 0:
            data = f.read(min(chunk, remaining))
            if not data:
                break
            remaining -= len(data)
            yield data


def mobile_render(request, template, context=None, **kwargs):
    """render — ถ้า mobile ใช้ template/mobile/ แทน"""
    from django.shortcuts import render
    if getattr(request, 'is_mobile', False):
        # แปลง 'app/browse.html' → 'app/mobile/browse.html'
        parts = template.split('/')
        parts.insert(-1, 'mobile')
        mobile_tpl = '/'.join(parts)
        from django.template.loader import get_template
        try:
            get_template(mobile_tpl)
            template = mobile_tpl
        except Exception:
            pass  # fallback to desktop
    return render(request, template, context or {}, **kwargs)