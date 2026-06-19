import os
import mimetypes
import secrets
import shutil
from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import (
    FileResponse, Http404, HttpResponse, JsonResponse, StreamingHttpResponse
)
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.text import slugify
from django.views.decorators.http import require_POST, require_GET

from .models import FileNode, ShareLink, ActivityLog, SystemSettings
from .utils import (
    get_storage_path_for_node, get_total_storage_used,
    get_all_drives, iter_file_range, sanitize_filename,
    mobile_render,
)


# ─── Dashboard / File Browser ────────────────────────────────────────────────

@login_required
def index(request):
    """Root file browser — shows top-level nodes."""
    return browse(request, folder_id=None)


@login_required
def browse(request, folder_id=None):
    """Browse a folder. folder_id=None means root."""
    parent = None
    if folder_id:
        parent = get_object_or_404(FileNode, id=folder_id, owner=request.user, is_folder=True)

    view_mode = request.GET.get('view', request.session.get('view_mode', 'grid'))
    request.session['view_mode'] = view_mode

    nodes = FileNode.objects.filter(
        owner=request.user,
        parent=parent,
        is_trashed=False,
    )

    # Search
    q = request.GET.get('q', '').strip()
    if q:
        nodes = FileNode.objects.filter(
            owner=request.user,
            name__icontains=q,
            is_trashed=False,
        )

    # Sort
    sort = request.GET.get('sort', 'name')
    sort_map = {
        'name': ['name'],
        'name_desc': ['-name'],
        'date': ['-updated_at'],
        'date_asc': ['updated_at'],
        'size': ['-size'],
        'size_asc': ['size'],
    }
    nodes = nodes.order_by('-is_folder', *sort_map.get(sort, ['name']))

    folders = [n for n in nodes if n.is_folder]
    files = [n for n in nodes if not n.is_folder]

    breadcrumb = parent.get_breadcrumb() if parent else []

    ctx = {
        'parent': parent,
        'folders': folders,
        'files': files,
        'breadcrumb': breadcrumb,
        'view_mode': view_mode,
        'sort': sort,
        'q': q,
    }
    return mobile_render(request, 'app/browse.html', ctx)


# ─── Starred ─────────────────────────────────────────────────────────────────

@login_required
def starred(request):
    nodes = FileNode.objects.filter(owner=request.user, is_starred=True, is_trashed=False)
    return mobile_render(request, 'app/special_list.html', {
        'nodes': nodes, 'page_title': 'Starred', 'icon': 'star'
    })


# ─── Trash ───────────────────────────────────────────────────────────────────

@login_required
def trash(request):
    nodes = FileNode.objects.filter(owner=request.user, is_trashed=True)
    return mobile_render(request, 'app/special_list.html', {
        'nodes': nodes, 'page_title': 'ถังขยะ', 'icon': 'trash'
    })


@login_required
@require_POST
def empty_trash(request):
    nodes = FileNode.objects.filter(owner=request.user, is_trashed=True, is_folder=False)
    for node in nodes:
        _delete_file_from_disk(node)
    FileNode.objects.filter(owner=request.user, is_trashed=True).delete()
    messages.success(request, 'ล้างถังขยะเรียบร้อยแล้ว')
    return redirect('trash')


# ─── Create Folder ────────────────────────────────────────────────────────────

@login_required
@require_POST
def create_folder(request):
    name = sanitize_filename(request.POST.get('name', 'โฟลเดอร์ใหม่'))
    parent_id = request.POST.get('parent_id') or None

    parent = None
    if parent_id:
        parent = get_object_or_404(FileNode, id=parent_id, owner=request.user, is_folder=True)

    # Avoid duplicate names
    base_name = name
    counter = 1
    while FileNode.objects.filter(owner=request.user, parent=parent, name=name, is_folder=True).exists():
        name = f'{base_name} ({counter})'
        counter += 1

    FileNode.objects.create(
        owner=request.user,
        parent=parent,
        name=name,
        is_folder=True,
    )
    messages.success(request, f'สร้างโฟลเดอร์ "{name}" เรียบร้อยแล้ว')

    if parent:
        return redirect('browse', folder_id=parent.id)
    return redirect('index')


# ─── Upload ───────────────────────────────────────────────────────────────────

@login_required
@require_POST
def upload_files(request):
    sys_settings = SystemSettings.get()
    parent_id = request.POST.get('parent_id') or None
    parent = None
    if parent_id:
        parent = get_object_or_404(FileNode, id=parent_id, owner=request.user, is_folder=True)

    uploaded      = request.FILES.getlist('files')
    relative_paths = request.POST.getlist('relative_paths')  # path จาก folder upload

    if not uploaded:
        messages.error(request, 'ไม่พบไฟล์ที่อัปโหลด')
        return redirect('index')

    # ตรวจ quota รายคน
    from .models import UserProfile
    profile = UserProfile.get_for(request.user)
    quota_gb = profile.effective_quota_gb
    if quota_gb > 0 and not (request.user.is_staff or request.user.is_superuser):
        from django.db.models import Sum
        used = FileNode.objects.filter(
            owner=request.user, is_folder=False, is_trashed=False
        ).aggregate(t=Sum('size'))['t'] or 0
        quota_bytes = quota_gb * 1024 ** 3
        incoming = sum(f.size for f in uploaded)
        if used + incoming > quota_bytes:
            messages.error(request, f'พื้นที่เต็ม quota {quota_gb} GB')
            if parent:
                return redirect('browse', folder_id=parent.id)
            return redirect('index')

    # ตรวจขนาดไฟล์สูงสุดต่อไฟล์
    max_bytes = sys_settings.max_upload_gb * 1024 ** 3
    for f in uploaded:
        if f.size > max_bytes:
            messages.error(request, f'ไฟล์ "{f.name}" ใหญ่เกิน {sys_settings.max_upload_gb} GB')
            if parent:
                return redirect('browse', folder_id=parent.id)
            return redirect('index')

    storage_root = Path(sys_settings.storage_root or str(settings.NAS_STORAGE_ROOT))
    storage_root.mkdir(parents=True, exist_ok=True)

    def get_or_create_folder(owner, folder_name, parent_node):
        """หา folder node หรือสร้างใหม่ถ้ายังไม่มี"""
        node = FileNode.objects.filter(
            owner=owner, parent=parent_node,
            name=folder_name, is_folder=True, is_trashed=False
        ).first()
        if not node:
            node = FileNode.objects.create(
                owner=owner, parent=parent_node,
                name=folder_name, is_folder=True,
            )
        return node

    def resolve_parent(rel_path, base_parent):
        """แปลง relative path เช่น 'photos/2024/jan' → สร้าง/หา folder nodes"""
        parts = [p for p in rel_path.replace('\\', '/').split('/') if p]
        if len(parts) <= 1:
            return base_parent  # ไฟล์อยู่ใน root upload
        # สร้าง folder tree ยกเว้น part สุดท้าย (ชื่อไฟล์)
        current = base_parent
        for folder_name in parts[:-1]:
            folder_name = sanitize_filename(folder_name)
            current = get_or_create_folder(request.user, folder_name, current)
        return current

    uploaded_count = 0
    for i, f in enumerate(uploaded):
        rel_path = relative_paths[i] if i < len(relative_paths) else ''
        file_parent = resolve_parent(rel_path, parent) if rel_path else parent

        name = sanitize_filename(f.name)
        base_name, ext = os.path.splitext(name)
        counter = 1
        while FileNode.objects.filter(owner=request.user, parent=file_parent, name=name, is_folder=False).exists():
            name = f'{base_name} ({counter}){ext}'
            counter += 1

        rel_dir = str(request.user.id)
        dest_dir = storage_root / rel_dir
        dest_dir.mkdir(parents=True, exist_ok=True)

        unique_name = f'{secrets.token_hex(8)}_{name}'
        dest_path = dest_dir / unique_name
        rel_path_storage = f'{rel_dir}/{unique_name}'

        with open(dest_path, 'wb+') as dest:
            for chunk in f.chunks():
                dest.write(chunk)

        mime_type, _ = mimetypes.guess_type(name)
        FileNode.objects.create(
            owner=request.user,
            parent=file_parent,
            name=name,
            is_folder=False,
            storage_path=rel_path_storage,
            size=f.size,
            mime_type=mime_type or 'application/octet-stream',
        )
        uploaded_count += 1

    if sys_settings.enable_logging:
        _log_activity(request, 'upload', f'อัปโหลด {uploaded_count} ไฟล์')

    messages.success(request, f'อัปโหลดสำเร็จ {uploaded_count} ไฟล์')
    if parent:
        return redirect('browse', folder_id=parent.id)
    return redirect('index')


# ─── Download ─────────────────────────────────────────────────────────────────

@login_required
def download_file(request, file_id):
    node = get_object_or_404(FileNode, id=file_id, owner=request.user, is_folder=False)
    abs_path = node.get_absolute_storage_path()
    if not os.path.exists(abs_path):
        raise Http404('ไม่พบไฟล์บนดิสก์')

    # Support HTTP Range for video streaming
    range_header = request.META.get('HTTP_RANGE', '').strip()
    if range_header:
        file_size = os.path.getsize(abs_path)
        range_match = range_header.replace('bytes=', '').split('-')
        first_byte = int(range_match[0])
        last_byte = int(range_match[1]) if range_match[1] else file_size - 1
        chunk_size = last_byte - first_byte + 1

        response = StreamingHttpResponse(
            iter_file_range(abs_path, first_byte, chunk_size),
            status=206,
            content_type=node.mime_type or 'application/octet-stream',
        )
        response['Content-Range'] = f'bytes {first_byte}-{last_byte}/{file_size}'
        response['Accept-Ranges'] = 'bytes'
        response['Content-Length'] = chunk_size
        return response

    response = FileResponse(open(abs_path, 'rb'), content_type=node.mime_type or 'application/octet-stream')
    response['Content-Disposition'] = f'attachment; filename="{node.name}"'
    response['Content-Length'] = node.size
    if SystemSettings.get().enable_logging:
        _log_activity(request, 'download', f'ดาวน์โหลด: {node.name}')
    return response


@login_required
def serve_file(request, file_id):
    """Serve ไฟล์แบบ inline (ไม่ force download) สำหรับ PDF preview ใน browser"""
    node = get_object_or_404(FileNode, id=file_id, owner=request.user, is_folder=False)
    abs_path = node.get_absolute_storage_path()
    if not os.path.exists(abs_path):
        raise Http404('ไม่พบไฟล์บนดิสก์')
    response = FileResponse(open(abs_path, 'rb'), content_type=node.mime_type or 'application/octet-stream')
    response['Content-Disposition'] = f'inline; filename="{node.name}"'
    response['X-Frame-Options'] = 'SAMEORIGIN'
    return response


# ─── Preview ─────────────────────────────────────────────────────────────────

@login_required
def preview_file(request, file_id):
    node = get_object_or_404(FileNode, id=file_id, owner=request.user, is_folder=False)
    abs_path = node.get_absolute_storage_path()

    IMAGE_EXTS  = {'jpg', 'jpeg', 'png', 'gif', 'webp', 'bmp'}
    VIDEO_EXTS  = {'mp4', 'webm', 'mov'}
    AUDIO_EXTS  = {'mp3', 'wav', 'ogg'}
    TEXT_EXTS   = {'txt', 'md'}
    OFFICE_EXTS = {'xlsx', 'xls', 'csv'}
    WORD_EXTS   = {'docx', 'doc'}
    PPTX_EXTS   = {'pptx', 'ppt'}
    PREVIEWABLE = IMAGE_EXTS | VIDEO_EXTS | AUDIO_EXTS | TEXT_EXTS | OFFICE_EXTS | WORD_EXTS | PPTX_EXTS | {'pdf'}

    ext = node.extension
    can_preview = ext in PREVIEWABLE
    text_content = None
    if ext in TEXT_EXTS and os.path.exists(abs_path):
        with open(abs_path, 'r', errors='replace') as fh:
            text_content = fh.read(50_000)

    return mobile_render(request, 'app/preview.html', {
        'node': node,
        'can_preview': can_preview,
        'is_image':  ext in IMAGE_EXTS,
        'is_video':  ext in VIDEO_EXTS,
        'is_audio':  ext in AUDIO_EXTS,
        'is_pdf':    ext == 'pdf',
        'is_text':   ext in TEXT_EXTS,
        'is_office': ext in OFFICE_EXTS,
        'is_word':   ext in WORD_EXTS,
        'is_pptx':   ext in PPTX_EXTS,
        'text_content': text_content,
    })


# ─── Rename ───────────────────────────────────────────────────────────────────

@login_required
@require_POST
def rename_node(request, node_id):
    node = get_object_or_404(FileNode, id=node_id, owner=request.user)
    new_name = sanitize_filename(request.POST.get('name', '').strip())
    if not new_name:
        messages.error(request, 'ชื่อไม่ถูกต้อง')
    else:
        node.name = new_name
        node.save(update_fields=['name', 'updated_at'])
        if SystemSettings.get().enable_logging:
            _log_activity(request, 'rename', f'เปลี่ยนชื่อเป็น: {new_name}')
        messages.success(request, f'เปลี่ยนชื่อเป็น "{new_name}" เรียบร้อยแล้ว')

    if node.parent:
        return redirect('browse', folder_id=node.parent.id)
    return redirect('index')


# ─── Move ─────────────────────────────────────────────────────────────────────

@login_required
@require_POST
def move_node(request, node_id):
    node = get_object_or_404(FileNode, id=node_id, owner=request.user)
    dest_id = request.POST.get('destination_id') or None

    dest = None
    if dest_id:
        dest = get_object_or_404(FileNode, id=dest_id, owner=request.user, is_folder=True)

    node.parent = dest
    node.save(update_fields=['parent', 'updated_at'])
    messages.success(request, f'ย้าย "{node.name}" เรียบร้อยแล้ว')

    if dest:
        return redirect('browse', folder_id=dest.id)
    return redirect('index')


# ─── Trash / Restore / Delete ─────────────────────────────────────────────────

@login_required
@require_POST
def trash_node(request, node_id):
    node = get_object_or_404(FileNode, id=node_id, owner=request.user)
    prev_parent = node.parent
    node.is_trashed = True
    node.trashed_at = timezone.now()
    node.save(update_fields=['is_trashed', 'trashed_at'])
    if SystemSettings.get().enable_logging:
        _log_activity(request, 'delete', f'ย้ายไปถังขยะ: {node.name}')
    messages.info(request, f'ย้าย "{node.name}" ไปถังขยะแล้ว')

    if prev_parent:
        return redirect('browse', folder_id=prev_parent.id)
    return redirect('index')


@login_required
@require_POST
def restore_node(request, node_id):
    node = get_object_or_404(FileNode, id=node_id, owner=request.user)
    node.is_trashed = False
    node.trashed_at = None
    node.save(update_fields=['is_trashed', 'trashed_at'])
    messages.success(request, f'กู้คืน "{node.name}" เรียบร้อยแล้ว')
    return redirect('trash')


@login_required
@require_POST
def delete_node_permanently(request, node_id):
    node = get_object_or_404(FileNode, id=node_id, owner=request.user)
    name = node.name
    if not node.is_folder:
        _delete_file_from_disk(node)
    node.delete()
    messages.success(request, f'ลบ "{name}" ถาวรเรียบร้อยแล้ว')
    return redirect('trash')


# ─── Star ─────────────────────────────────────────────────────────────────────

@login_required
@require_POST
def toggle_star(request, node_id):
    node = get_object_or_404(FileNode, id=node_id, owner=request.user)
    node.is_starred = not node.is_starred
    node.save(update_fields=['is_starred'])
    return JsonResponse({'starred': node.is_starred})


# ─── Share Links ──────────────────────────────────────────────────────────────

@login_required
@require_POST
def create_share(request, node_id):
    sys_settings = SystemSettings.get()
    node = get_object_or_404(FileNode, id=node_id, owner=request.user)
    token = secrets.token_urlsafe(32)

    # คำนวณวันหมดอายุจาก settings
    expires_at = None
    if sys_settings.share_expire_days > 0:
        from django.utils import timezone as tz
        from datetime import timedelta
        expires_at = tz.now() + timedelta(days=sys_settings.share_expire_days)

    link = ShareLink.objects.create(
        node=node,
        created_by=request.user,
        token=token,
        allow_download=True,
        expires_at=expires_at,
    )

    if sys_settings.enable_logging:
        _log_activity(request, 'share', f'แชร์ไฟล์: {node.name}')

    share_url = request.build_absolute_uri(f'/share/{token}/')
    return JsonResponse({
        'url': share_url,
        'token': token,
        'expires_at': expires_at.strftime('%d %b %Y, %H:%M') if expires_at else None,
        'expire_days': sys_settings.share_expire_days,
    })


def _shared_link_check(token):
    """Helper — คืน link หรือ None ถ้าหมดอายุ"""
    link = get_object_or_404(ShareLink, token=token)
    return None if link.is_expired else link


def _shared_expiry_ctx(link):
    """Helper — คืน dict วันหมดอายุสำหรับ context"""
    days_left = hours_left = None
    if link.expires_at:
        delta = link.expires_at - timezone.now()
        days_left  = max(0, delta.days)
        hours_left = max(0, int(delta.total_seconds() // 3600))
    return {'days_left': days_left, 'hours_left': hours_left}


def _get_folder_contents(folder):
    """คืน (folders, files) ใน folder นั้น ไม่รวมถังขยะ"""
    children = FileNode.objects.filter(parent=folder, is_trashed=False).order_by('-is_folder', 'name')
    return (
        [n for n in children if n.is_folder],
        [n for n in children if not n.is_folder],
    )


def shared_file(request, token):
    """Public share — ไฟล์เดี่ยวหรือโฟลเดอร์ root"""
    link = get_object_or_404(ShareLink, token=token)
    if link.is_expired:
        return render(request, 'app/share_expired.html', status=410)

    node = link.node

    # ── ไฟล์เดี่ยว: POST = download ──────────────────────────
    if not node.is_folder:
        if request.method == 'POST':
            abs_path = node.get_absolute_storage_path()
            if not os.path.exists(abs_path):
                raise Http404
            resp = FileResponse(open(abs_path, 'rb'), content_type=node.mime_type)
            resp['Content-Disposition'] = f'attachment; filename="{node.name}"'
            return resp
        return mobile_render(request, 'app/shared_view.html', {
            'node': node, 'link': link, **_shared_expiry_ctx(link)
        })

    # ── โฟลเดอร์: แสดง contents ──────────────────────────────
    folders, files = _get_folder_contents(node)
    return mobile_render(request, 'app/shared_folder.html', {
        'link': link,
        'root': node,
        'current': node,
        'breadcrumb': [],
        'folders': folders,
        'files': files,
        **_shared_expiry_ctx(link),
    })


def shared_folder_browse(request, token, folder_id):
    """Browse subfolder ภายใน shared folder"""
    link = get_object_or_404(ShareLink, token=token)
    if link.is_expired:
        return render(request, 'app/share_expired.html', status=410)

    root = link.node
    if not root.is_folder:
        raise Http404

    # ตรวจว่า folder_id อยู่ใต้ root จริงๆ
    current = get_object_or_404(FileNode, id=folder_id, is_folder=True, is_trashed=False)
    # Walk up และตรวจว่า root เป็น ancestor
    ancestor = current
    chain = [current]
    while ancestor.parent:
        ancestor = ancestor.parent
        chain.insert(0, ancestor)
    if ancestor.id != root.id:
        raise Http404  # ไม่ให้ browse นอก shared root

    breadcrumb = chain[1:]  # ไม่รวม root (แสดงแยกต่างหาก)
    folders, files = _get_folder_contents(current)

    return mobile_render(request, 'app/shared_folder.html', {
        'link': link,
        'root': root,
        'current': current,
        'breadcrumb': breadcrumb,
        'folders': folders,
        'files': files,
        **_shared_expiry_ctx(link),
    })


def shared_file_download(request, token, file_id):
    """Download ไฟล์ภายใน shared folder"""
    link = get_object_or_404(ShareLink, token=token)
    if link.is_expired:
        return render(request, 'app/share_expired.html', status=410)

    if not link.allow_download:
        raise Http404

    root = link.node

    # ตรวจว่าไฟล์อยู่ใต้ root จริงๆ
    node = get_object_or_404(FileNode, id=file_id, is_folder=False, is_trashed=False)
    ancestor = node.parent
    found = False
    while ancestor:
        if ancestor.id == root.id:
            found = True
            break
        ancestor = ancestor.parent
    # ถ้า root เป็นไฟล์เดี่ยว ตรวจ id ตรงๆ
    if not found and node.id == root.id:
        found = True
    if not found:
        raise Http404

    abs_path = node.get_absolute_storage_path()
    if not os.path.exists(abs_path):
        raise Http404

    response = FileResponse(open(abs_path, 'rb'), content_type=node.mime_type or 'application/octet-stream')
    response['Content-Disposition'] = f'attachment; filename="{node.name}"'
    return response


# ─── AJAX: Node Detail ────────────────────────────────────────────────────────

@login_required
@require_GET
def node_detail_api(request, node_id):
    node = get_object_or_404(FileNode, id=node_id, owner=request.user)
    data = {
        'id': str(node.id),
        'name': node.name,
        'is_folder': node.is_folder,
        'size': node.human_size,
        'mime_type': node.mime_type,
        'extension': node.extension,
        'is_starred': node.is_starred,
        'created_at': node.created_at.strftime('%d %b %Y'),
        'updated_at': node.updated_at.strftime('%d %b %Y, %H:%M'),
    }
    return JsonResponse(data)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _delete_file_from_disk(node):
    try:
        abs_path = node.get_absolute_storage_path()
        if os.path.exists(abs_path):
            os.remove(abs_path)
    except Exception:
        pass


def _human_size(size):
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size < 1024:
            return f'{size:.1f} {unit}'
        size /= 1024
    return f'{size:.1f} PB'


# ─── Drives API ───────────────────────────────────────────────────────────────

@login_required
@require_GET
def drives_api(request):
    """Return real-time disk info for all mounted drives as JSON."""
    drives = get_all_drives()
    return JsonResponse({'drives': drives})


# ─── Activity Logging Helper ──────────────────────────────────────────────────

def _log_activity(request, action, detail=''):
    """บันทึก ActivityLog — เรียกใช้หลัง SystemSettings.get().enable_logging ตรวจแล้ว"""
    try:
        ip = request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR', ''))
        if ',' in ip:
            ip = ip.split(',')[0].strip()
        ActivityLog.objects.create(
            user=request.user,
            action=action,
            detail=detail[:512],
            ip_address=ip or None,
        )
    except Exception:
        pass


# ─── Login signal — บันทึก log เมื่อ login ────────────────────────────────────

from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver

@receiver(user_logged_in)
def on_user_login(sender, request, user, **kwargs):
    try:
        if not SystemSettings.get().enable_logging:
            return
        ip = request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR', ''))
        if ',' in ip:
            ip = ip.split(',')[0].strip()
        ActivityLog.objects.create(
            user=user,
            action='login',
            detail=f'เข้าสู่ระบบ',
            ip_address=ip or None,
        )
    except Exception:
        pass


# ─── Register ─────────────────────────────────────────────────────────────────

def register(request):
    """สมัครสมาชิก — เปิดได้เฉพาะเมื่อ allow_register=True ใน SystemSettings"""
    sys_settings = SystemSettings.get()

    if not sys_settings.allow_register:
        return mobile_render(request, 'app/register.html', {'disabled': True})

    if request.user.is_authenticated:
        return redirect('index')

    error = None
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        email    = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')
        confirm  = request.POST.get('confirm', '')

        if not username or not password:
            error = 'กรุณากรอกชื่อผู้ใช้และรหัสผ่าน'
        elif password != confirm:
            error = 'รหัสผ่านไม่ตรงกัน'
        elif len(password) < 6:
            error = 'รหัสผ่านต้องมีอย่างน้อย 6 ตัวอักษร'
        elif User.objects.filter(username=username).exists():
            error = f'ชื่อผู้ใช้ "{username}" มีอยู่แล้ว'
        else:
            from django.contrib.auth import login as auth_login
            user = User.objects.create_user(username=username, email=email, password=password)
            auth_login(request, user)
            messages.success(request, f'ยินดีต้อนรับ {username}!')
            return redirect('index')

    return mobile_render(request, 'app/register.html', {'error': error, 'disabled': False})


# ─── Mobile Login View ────────────────────────────────────────────────────────

from django.contrib.auth import authenticate, login as auth_login
from django.contrib.auth.views import LoginView as _LoginView

class MobileAwareLoginView(_LoginView):
    def get_template_names(self):
        if getattr(self.request, 'is_mobile', False):
            return ['app/mobile/login.html', 'app/login.html']
        return ['app/login.html']

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        from .models import SystemSettings
        ctx['allow_register'] = SystemSettings.get().allow_register
        return ctx