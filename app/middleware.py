import re
import time
from collections import defaultdict
from threading import Lock
from django.http import HttpResponse, JsonResponse
from django.core.cache import cache

# ── Mobile Detection ──────────────────────────────────────────────────────────

MOBILE_UA = re.compile(
    r'(android|bb\d+|meego).+mobile|avantgo|bada\/|blackberry|blazer|compal|elaine|fennec'
    r'|hiptop|iemobile|ip(hone|od)|iris|kindle|lge |maemo|midp|mmp|mobile.+firefox|netfront'
    r'|opera m(ob|in)i|palm( os)?|phone|p(ixi|re)\/|plucker|pocket|psp|series(4|6)0|symbian'
    r'|treo|up\.(browser|link)|vodafone|wap|windows ce|xda|xiino',
    re.IGNORECASE
)

class MobileDetectMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        ua = request.META.get('HTTP_USER_AGENT', '')
        request.is_mobile = bool(MOBILE_UA.search(ua))
        if 'mobile' in request.GET:
            request.is_mobile = request.GET['mobile'] == '1'
        return self.get_response(request)


# ── Security Headers ──────────────────────────────────────────────────────────

class SecurityHeadersMiddleware:
    """
    เพิ่ม HTTP security headers ทุก response:
    - X-Frame-Options         → ป้องกัน clickjacking / iframe embedding
    - X-Content-Type-Options  → ป้องกัน MIME sniffing
    - X-XSS-Protection        → เปิด XSS filter ใน browser เก่า
    - Referrer-Policy         → จำกัดการส่ง referrer
    - Permissions-Policy      → ปิด feature ที่ไม่จำเป็น
    - Content-Security-Policy → ป้องกัน inline script injection
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        # ถ้าเป็น serve_file endpoint ไม่ใส่ header ที่บล็อก PDF/Word
        if '/serve/' in request.path:
            response['X-Frame-Options'] = 'SAMEORIGIN'
            return response

        response['X-Frame-Options']        = 'SAMEORIGIN'
        response['X-Content-Type-Options'] = 'nosniff'
        response['X-XSS-Protection']       = '1; mode=block'
        response['Referrer-Policy']        = 'strict-origin-when-cross-origin'
        response['Permissions-Policy']     = 'camera=(), microphone=(), geolocation=()'
        response['Content-Security-Policy'] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://unpkg.com https://cdn.jsdelivr.net https://fonts.googleapis.com; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://fonts.gstatic.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            "img-src 'self' data: blob:; "
            "frame-ancestors 'self'; "
            "object-src 'self'; "
            "base-uri 'self';"
        )
        return response


# ── Rate Limiting (Login Brute Force) ────────────────────────────────────────

# In-memory store: { ip: [timestamp, ...] }
_login_attempts = defaultdict(list)
_lock = Lock()

MAX_ATTEMPTS = 10      # ครั้งสูงสุดต่อ window
WINDOW_SECS  = 300     # 5 นาที
LOCKOUT_SECS = 900     # ล็อก 15 นาที


def _get_ip(request):
    xff = request.META.get('HTTP_X_FORWARDED_FOR', '')
    return xff.split(',')[0].strip() if xff else request.META.get('REMOTE_ADDR', '0.0.0.0')


class LoginRateLimitMiddleware:
    """
    จำกัด POST /login/ ไม่เกิน MAX_ATTEMPTS ครั้งใน WINDOW_SECS วินาที
    เมื่อเกินจะล็อก IP นั้น LOCKOUT_SECS วินาที
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path in ('/login/', '/login') and request.method == 'POST':
            ip = _get_ip(request)
            now = time.time()

            with _lock:
                attempts = _login_attempts[ip]
                # ลบ attempt เก่าออก
                attempts = [t for t in attempts if now - t < WINDOW_SECS]
                _login_attempts[ip] = attempts

                if len(attempts) >= MAX_ATTEMPTS:
                    oldest = attempts[0]
                    remaining = int(LOCKOUT_SECS - (now - oldest))
                    if remaining > 0:
                        mins = remaining // 60
                        secs = remaining % 60
                        msg = f'พยายามเข้าสู่ระบบมากเกินไป กรุณารอ {mins} นาที {secs} วินาที'
                        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                            return JsonResponse({'error': msg}, status=429)
                        # render หน้า login พร้อม error
                        from django.shortcuts import render
                        return render(request, 'app/login.html', {
                            'rate_limit_error': msg,
                            'retry_after': remaining,
                        }, status=429)
                    else:
                        _login_attempts[ip] = []

                attempts.append(now)
                _login_attempts[ip] = attempts

        return self.get_response(request)