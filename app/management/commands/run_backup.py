"""
Management command: run_backup
คัดลอกไฟล์ทั้งหมดใน NAS storage ไปยัง destination path

Usage:
    python manage.py run_backup               # backup ตาม config
    python manage.py run_backup --dry-run     # แสดงรายการโดยไม่คัดลอกจริง

ตั้งให้รันอัตโนมัติ (Windows Task Scheduler):
    python manage.py run_backup

ตั้งให้รันอัตโนมัติ (Linux cron):
    0 2 * * * /path/venv/bin/python /path/manage.py run_backup
"""

import os
import shutil
from datetime import datetime
from pathlib import Path

from django.core.management.base import BaseCommand
from django.conf import settings
from django.utils import timezone


class Command(BaseCommand):
    help = 'สำรองข้อมูลไปยัง destination path'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', dest='dry_run', help='แสดงรายการโดยไม่คัดลอกจริง')
        parser.add_argument('--trigger', default='manual', dest='trigger', help='manual หรือ schedule')

    def handle(self, *args, **options):
        from app.models import BackupConfig, BackupLog

        dry_run = options['dry_run']
        trigger = options['trigger']
        cfg = BackupConfig.get()

        if not cfg.enabled:
            self.stdout.write(self.style.WARNING('Backup ปิดใช้งานอยู่ ตั้งค่าใน Admin → Settings'))
            return

        if not cfg.destination_path:
            self.stdout.write(self.style.ERROR('ยังไม่ได้ตั้งค่า destination path'))
            return

        # สร้าง version folder เช่น 2025-03-21_02-00
        version_name = datetime.now().strftime('%Y-%m-%d_%H-%M')
        dest_root = Path(cfg.destination_path) / version_name

        self.stdout.write(f'\n{"[DRY RUN] " if dry_run else ""}Backup เริ่มต้น → {dest_root}')

        # สร้าง log
        log = BackupLog.objects.create(
            status='running',
            triggered_by=trigger,
            destination=str(dest_root),
            version_name=version_name,
        ) if not dry_run else None

        try:
            storage_root = Path(str(settings.NAS_STORAGE_ROOT))
            if not storage_root.exists():
                raise FileNotFoundError(f'Storage root ไม่พบ: {storage_root}')

            if not dry_run:
                dest_root.mkdir(parents=True, exist_ok=True)

            files_copied = 0
            bytes_copied = 0

            for src_file in storage_root.rglob('*'):
                if not src_file.is_file():
                    continue

                rel = src_file.relative_to(storage_root)
                dest_file = dest_root / rel

                size = src_file.stat().st_size
                self.stdout.write(f'  {"[DRY]" if dry_run else "COPY"} {rel}  ({_human(size)})')

                if not dry_run:
                    dest_file.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src_file, dest_file)

                files_copied += 1
                bytes_copied += size

            # ลบ version เก่าถ้าเกิน keep_versions
            if not dry_run and cfg.keep_versions > 0:
                dest_parent = Path(cfg.destination_path)
                versions = sorted(
                    [d for d in dest_parent.iterdir() if d.is_dir()],
                    key=lambda d: d.name
                )
                while len(versions) > cfg.keep_versions:
                    old = versions.pop(0)
                    self.stdout.write(self.style.WARNING(f'  ลบ version เก่า: {old.name}'))
                    shutil.rmtree(old, ignore_errors=True)

            # อัปเดต log
            if log:
                log.status = 'success'
                log.finished_at = timezone.now()
                log.files_copied = files_copied
                log.bytes_copied = bytes_copied
                log.save()

            summary = f'{"[DRY RUN] " if dry_run else ""}สำเร็จ: {files_copied} ไฟล์ ({_human(bytes_copied)})'
            self.stdout.write(self.style.SUCCESS(f'\n{summary}'))

        except Exception as e:
            if log:
                log.status = 'failed'
                log.finished_at = timezone.now()
                log.error = str(e)
                log.save()
            self.stdout.write(self.style.ERROR(f'\nBackup ล้มเหลว: {e}'))
            raise


def _human(size):
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size < 1024:
            return f'{size:.1f} {unit}'
        size /= 1024
    return f'{size:.1f} PB'