"""
Admin views สำหรับ NAS Drive
URL prefix: /nas-admin/
"""
import sys
import django
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Sum, Count
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST, require_GET
from django.utils import timezone

from .models import FileNode, ActivityLog, SystemSettings
from .utils import get_all_drives, _human_size


def staff_required(view_func):
    return user_passes_test(lambda u: u.is_staff or u.is_superuser)(login_required(view_func))


def _log(request, action, detail=''):
    """Helper — บันทึก ActivityLog ถ้าเปิดใช้"""
    try:
        s = SystemSettings.get()
        if not s.enable_logging:
            return
    except Exception:
        pass
    ip = request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR', ''))
    if ',' in ip:
        ip = ip.split(',')[0].strip()
    ActivityLog.objects.create(user=request.user, action=action, detail=detail[:512], ip_address=ip or None)


# ─── Dashboard ────────────────────────────────────────────────────────────────

@staff_required
def admin_dashboard(request):
    total_users  = User.objects.count()
    active_users = User.objects.filter(is_active=True).count()
    total_files  = FileNode.objects.filter(is_folder=False, is_trashed=False).count()
    total_folders = FileNode.objects.filter(is_folder=True, is_trashed=False).count()
    trashed_files = FileNode.objects.filter(is_folder=False, is_trashed=True).count()

    db_used = FileNode.objects.filter(is_folder=False, is_trashed=False).aggregate(t=Sum('size'))['t'] or 0
    trashed_size = FileNode.objects.filter(is_folder=False, is_trashed=True).aggregate(t=Sum('size'))['t'] or 0

    # Top users by storage
    users_qs = User.objects.annotate(
        storage=Sum('file_nodes__size', filter=__import__('django.db.models', fromlist=['Q']).Q(file_nodes__is_folder=False, file_nodes__is_trashed=False)),
        file_count=Count('file_nodes', filter=__import__('django.db.models', fromlist=['Q']).Q(file_nodes__is_folder=False, file_nodes__is_trashed=False)),
    ).order_by('-storage')[:5]

    total_db = db_used or 1
    top_users = []
    for u in users_qs:
        sz = u.storage or 0
        u.storage_human = _human_size(sz)
        u.storage_pct = min(int(sz / total_db * 100), 100)
        top_users.append(u)

    recent_logs = ActivityLog.objects.select_related('user')[:10]
    drives = get_all_drives()

    ctx = {
        'active': 'dashboard',
        'total_users': total_users,
        'active_users': active_users,
        'total_files': total_files,
        'total_folders': total_folders,
        'trashed_files': trashed_files,
        'db_used_human': _human_size(db_used),
        'trashed_size_human': _human_size(trashed_size),
        'top_users': top_users,
        'recent_logs': recent_logs,
        'drives': drives,
    }

    if getattr(request, 'is_mobile', False):
        return render(request, 'app/mobile/admin_dashboard.html', ctx)
    return render(request, 'app/admin/dashboard.html', ctx)


# ─── Users ────────────────────────────────────────────────────────────────────

@staff_required
def admin_users(request):
    from django.db.models import Q, Sum, Count
    from .models import UserProfile, SystemSettings
    q = request.GET.get('q', '').strip()
    users_qs = User.objects.annotate(
        storage=Sum('file_nodes__size', filter=Q(file_nodes__is_folder=False, file_nodes__is_trashed=False)),
        file_count=Count('file_nodes', filter=Q(file_nodes__is_folder=False, file_nodes__is_trashed=False)),
    ).order_by('username')

    if q:
        users_qs = users_qs.filter(Q(username__icontains=q) | Q(email__icontains=q))

    default_quota = SystemSettings.get().default_quota_gb
    for u in users_qs:
        u.storage_human = _human_size(u.storage or 0)
        profile = UserProfile.get_for(u)
        u.custom_quota_gb    = profile.custom_quota_gb
        u.effective_quota_gb = profile.effective_quota_gb

    tpl = 'app/mobile/admin_users.html' if getattr(request, 'is_mobile', False) else 'app/admin/users.html'
    return render(request, tpl, {
        'active': 'users',
        'users': users_qs,
        'default_quota': default_quota,
        'q': q,
    })


@staff_required
@require_POST
def admin_user_add(request):
    username = request.POST.get('username', '').strip()
    email    = request.POST.get('email', '').strip()
    password = request.POST.get('password', '')
    is_staff = bool(request.POST.get('is_staff'))

    if not username or not password:
        messages.error(request, 'กรุณากรอกชื่อผู้ใช้และรหัสผ่าน')
        return redirect('admin_users')

    if User.objects.filter(username=username).exists():
        messages.error(request, f'ชื่อผู้ใช้ "{username}" มีอยู่แล้ว')
        return redirect('admin_users')

    user = User.objects.create_user(username=username, email=email, password=password, is_staff=is_staff)
    _log(request, 'login', f'Admin สร้าง user: {username}')
    messages.success(request, f'สร้างผู้ใช้ "{username}" เรียบร้อยแล้ว')
    return redirect('admin_users')


@staff_required
@require_POST
def admin_user_toggle(request, user_id):
    user = get_object_or_404(User, id=user_id)
    if user == request.user:
        messages.error(request, 'ไม่สามารถระงับตัวเองได้')
        return redirect('admin_users')
    user.is_active = not user.is_active
    user.save(update_fields=['is_active'])
    status = 'เปิดใช้' if user.is_active else 'ระงับ'
    messages.success(request, f'{status} ผู้ใช้ "{user.username}" เรียบร้อยแล้ว')
    return redirect('admin_users')


@staff_required
@require_POST
def admin_user_quota(request, user_id):
    """ตั้ง quota เฉพาะบุคคล"""
    from .models import UserProfile
    user = get_object_or_404(User, id=user_id)
    profile = UserProfile.get_for(user)

    raw = request.POST.get('custom_quota_gb', '').strip()
    if raw == '' or raw == 'default':
        profile.custom_quota_gb = None  # ใช้ default
        profile.save()
        messages.success(request, f'รีเซ็ต quota ของ "{user.username}" เป็นค่า default แล้ว')
    else:
        try:
            gb = int(raw)
            if gb < 0:
                raise ValueError
            profile.custom_quota_gb = gb
            profile.save()
            label = 'ไม่จำกัด' if gb == 0 else f'{gb} GB'
            messages.success(request, f'ตั้ง quota ของ "{user.username}" เป็น {label} แล้ว')
        except ValueError:
            messages.error(request, 'ค่า quota ต้องเป็นตัวเลขจำนวนเต็ม ≥ 0')
    return redirect('admin_users')


@staff_required
@require_POST
def admin_user_delete(request, user_id):
    user = get_object_or_404(User, id=user_id)
    if user.is_superuser:
        messages.error(request, 'ไม่สามารถลบ superuser ได้')
        return redirect('admin_users')
    if user == request.user:
        messages.error(request, 'ไม่สามารถลบตัวเองได้')
        return redirect('admin_users')

    # ลบไฟล์บน disk
    for node in FileNode.objects.filter(owner=user, is_folder=False):
        try:
            import os
            p = node.get_absolute_storage_path()
            if os.path.exists(p):
                os.remove(p)
        except Exception:
            pass

    username = user.username
    user.delete()
    messages.success(request, f'ลบผู้ใช้ "{username}" และไฟล์ทั้งหมดเรียบร้อยแล้ว')
    return redirect('admin_users')


# ─── Logs ─────────────────────────────────────────────────────────────────────

@staff_required
def admin_logs(request):
    logs_qs = ActivityLog.objects.select_related('user').all()

    filter_action    = request.GET.get('action', '')
    filter_user      = request.GET.get('user_id', '')
    filter_date_from = request.GET.get('date_from', '')
    filter_date_to   = request.GET.get('date_to', '')

    if filter_action:
        logs_qs = logs_qs.filter(action=filter_action)
    if filter_user:
        logs_qs = logs_qs.filter(user_id=filter_user)
    if filter_date_from:
        logs_qs = logs_qs.filter(created_at__date__gte=filter_date_from)
    if filter_date_to:
        logs_qs = logs_qs.filter(created_at__date__lte=filter_date_to)

    paginator = Paginator(logs_qs, 50)
    page = request.GET.get('page', 1)
    logs = paginator.get_page(page)

    tpl = 'app/mobile/admin_logs.html' if getattr(request, 'is_mobile', False) else 'app/admin/logs.html'
    return render(request, tpl, {
        'active': 'logs',
        'logs': logs,
        'all_users': User.objects.order_by('username'),
        'filter_action': filter_action,
        'filter_user': filter_user,
        'filter_date_from': filter_date_from,
        'filter_date_to': filter_date_to,
    })


# ─── Settings ─────────────────────────────────────────────────────────────────

@staff_required
def admin_settings(request):
    from .models import BackupConfig
    settings_obj = SystemSettings.get()
    backup_cfg   = BackupConfig.get()

    if request.method == 'POST':
        settings_obj.storage_root        = request.POST.get('storage_root', '').strip()
        settings_obj.default_quota_gb    = int(request.POST.get('default_quota_gb', 0) or 0)
        settings_obj.max_upload_gb       = int(request.POST.get('max_upload_gb', 10) or 10)
        settings_obj.trash_retention_days = int(request.POST.get('trash_retention_days', 1) or 1)
        settings_obj.auto_purge          = bool(request.POST.get('auto_purge'))
        settings_obj.share_expire_days   = int(request.POST.get('share_expire_days', 0) or 0)
        settings_obj.allow_register      = bool(request.POST.get('allow_register'))
        settings_obj.enable_logging      = bool(request.POST.get('enable_logging'))
        settings_obj.log_retention_days  = int(request.POST.get('log_retention_days', 90) or 90)
        settings_obj.save()

        # บันทึก backup config ด้วย
        backup_cfg.enabled          = bool(request.POST.get('backup_enabled'))
        backup_cfg.destination_path = request.POST.get('backup_destination', '').strip()
        backup_cfg.schedule         = request.POST.get('backup_schedule', 'manual')
        backup_cfg.schedule_hour    = int(request.POST.get('backup_schedule_hour', 2) or 2)
        backup_cfg.schedule_weekday = int(request.POST.get('backup_schedule_weekday', 0) or 0)
        backup_cfg.keep_versions    = int(request.POST.get('backup_keep_versions', 3) or 3)
        backup_cfg.include_trashed  = bool(request.POST.get('backup_include_trashed'))
        backup_cfg.save()

        # ลบ log เก่าเกินกำหนดทันทีเมื่อบันทึก
        if settings_obj.enable_logging and settings_obj.log_retention_days > 0:
            from django.utils import timezone
            from datetime import timedelta
            cutoff = timezone.now() - timedelta(days=settings_obj.log_retention_days)
            deleted, _ = ActivityLog.objects.filter(created_at__lt=cutoff).delete()
            if deleted:
                messages.info(request, f'ลบ log เก่า {deleted} รายการ (เกิน {settings_obj.log_retention_days} วัน)')

        messages.success(request, 'บันทึกการตั้งค่าเรียบร้อยแล้ว')
        return redirect('admin_settings')

    from django.conf import settings as django_settings
    weekdays = [(0,'จันทร์'),(1,'อังคาร'),(2,'พุธ'),(3,'พฤหัสบดี'),(4,'ศุกร์'),(5,'เสาร์'),(6,'อาทิตย์')]
    ctx = {
        'active': 'settings',
        'settings': settings_obj,
        'backup_cfg': backup_cfg,
        'weekdays': weekdays,
        'django_version': django.VERSION,
        'python_version': f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}',
        'debug': django_settings.DEBUG,
    }
    tpl = 'app/mobile/admin_settings.html' if getattr(request, 'is_mobile', False) else 'app/admin/settings.html'
    return render(request, tpl, ctx)


# ─── Storage Browser API ──────────────────────────────────────────────────────

@staff_required
@require_GET
def storage_drives_api(request):
    """คืน list of drives สำหรับ picker"""
    try:
        import psutil
        drives = []
        for part in psutil.disk_partitions(all=False):
            try:
                usage = psutil.disk_usage(part.mountpoint)
            except (PermissionError, OSError):
                continue
            import os as _os
            name = part.device.rstrip('\\') if _os.name == 'nt' else part.mountpoint
            drives.append({
                'name':       name,
                'mountpoint': part.mountpoint,
                'fstype':     part.fstype,
                'total_h':    _human_size(usage.total),
                'used_h':     _human_size(usage.used),
                'free_h':     _human_size(usage.free),
                'percent':    round(usage.percent, 1),
            })
        return JsonResponse({'drives': drives})
    except Exception as e:
        return JsonResponse({'drives': [], 'error': str(e)})


@staff_required
@require_GET
def storage_browse_api(request):
    """Browse directory — คืน subdirs ของ path ที่ระบุ"""
    import os as _os
    path = request.GET.get('path', '').strip()

    if not path:
        return JsonResponse({'error': 'ต้องระบุ path'}, status=400)

    # security: ต้อง absolute path และมีอยู่จริง
    try:
        path = _os.path.abspath(path)
    except Exception:
        return JsonResponse({'error': 'path ไม่ถูกต้อง'}, status=400)

    if not _os.path.isdir(path):
        return JsonResponse({'error': 'ไม่พบโฟลเดอร์นี้'}, status=404)

    try:
        entries = []
        for name in sorted(_os.listdir(path)):
            full = _os.path.join(path, name)
            if _os.path.isdir(full) and not name.startswith('.'):
                try:
                    count = len(_os.listdir(full))
                except PermissionError:
                    count = -1
                entries.append({
                    'name':      name,
                    'full_path': full,
                    'items':     count,
                })
        parent = _os.path.dirname(path) if path != _os.path.dirname(path) else None
        return JsonResponse({
            'current': path,
            'parent':  parent,
            'entries': entries,
        })
    except PermissionError:
        return JsonResponse({'error': 'ไม่มีสิทธิ์เข้าถึงโฟลเดอร์นี้'}, status=403)


# ─── Backup ───────────────────────────────────────────────────────────────────

@staff_required
@require_POST
def admin_backup_save(request):
    """บันทึกการตั้งค่า Backup"""
    from .models import BackupConfig
    cfg = BackupConfig.get()
    cfg.destination_path = request.POST.get('destination_path', '').strip()
    cfg.enabled          = bool(request.POST.get('enabled'))
    cfg.schedule         = request.POST.get('schedule', 'manual')
    cfg.schedule_hour    = int(request.POST.get('schedule_hour', 2) or 2)
    cfg.schedule_weekday = int(request.POST.get('schedule_weekday', 0) or 0)
    cfg.keep_versions    = int(request.POST.get('keep_versions', 3) or 3)
    cfg.include_trashed  = bool(request.POST.get('include_trashed'))
    cfg.save()
    messages.success(request, 'บันทึกการตั้งค่า Backup เรียบร้อยแล้ว')
    return redirect('admin_settings')


@staff_required
@require_POST
def admin_backup_run(request):
    """รัน backup ทันที (manual trigger) — รันใน background thread"""
    from .models import BackupConfig, BackupLog
    import threading

    cfg = BackupConfig.get()

    if not cfg.enabled:
        messages.error(request, 'กรุณาเปิดใช้งาน Backup ก่อน')
        return redirect('admin_settings')
    if not cfg.destination_path:
        messages.error(request, 'กรุณาตั้งค่า Destination Path ก่อน')
        return redirect('admin_settings')

    def _run():
        from django.core.management import call_command
        try:
            call_command('run_backup', trigger='manual')
        except Exception:
            pass

    t = threading.Thread(target=_run, daemon=True)
    t.start()

    messages.success(request, 'เริ่ม Backup แล้ว — ดูผลใน Backup History ด้านล่าง (รีเฟรชเพื่ออัปเดต)')
    return redirect('admin_settings')


@staff_required
@require_GET
def admin_backup_status(request):
    """API — คืน backup logs ล่าสุดเป็น JSON"""
    from .models import BackupLog
    logs = BackupLog.objects.all()[:10]
    data = [{
        'id':           l.id,
        'started_at':   l.started_at.strftime('%d %b %Y, %H:%M'),
        'status':       l.status,
        'status_label': l.get_status_display(),
        'triggered_by': l.triggered_by,
        'files_copied': l.files_copied,
        'bytes_human':  l.bytes_human,
        'duration':     l.duration,
        'version_name': l.version_name,
        'error':        l.error,
    } for l in logs]
    return JsonResponse({'logs': data})