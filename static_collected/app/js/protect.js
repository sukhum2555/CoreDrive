/**
 * NAS Drive — Client-side Protection
 * ป้องกัน: right-click, DevTools shortcuts, view-source
 */
(function () {
  'use strict';

  // ── 1. Disable Right-click ──────────────────────────────────────────────────
  document.addEventListener('contextmenu', function (e) {
    e.preventDefault();
    return false;
  });

  // ── 2. Disable DevTools keyboard shortcuts ──────────────────────────────────
  document.addEventListener('keydown', function (e) {
    // F12
    if (e.key === 'F12') { e.preventDefault(); return false; }

    // Ctrl+Shift+I / Cmd+Option+I (Inspect)
    if ((e.ctrlKey || e.metaKey) && e.shiftKey && (e.key === 'I' || e.key === 'i')) {
      e.preventDefault(); return false;
    }
    // Ctrl+Shift+J / Cmd+Option+J (Console)
    if ((e.ctrlKey || e.metaKey) && e.shiftKey && (e.key === 'J' || e.key === 'j')) {
      e.preventDefault(); return false;
    }
    // Ctrl+Shift+C (Inspector)
    if ((e.ctrlKey || e.metaKey) && e.shiftKey && (e.key === 'C' || e.key === 'c')) {
      e.preventDefault(); return false;
    }
    // Ctrl+U (View Source)
    if ((e.ctrlKey || e.metaKey) && (e.key === 'U' || e.key === 'u')) {
      e.preventDefault(); return false;
    }
    // Ctrl+S (Save Page)
    if ((e.ctrlKey || e.metaKey) && (e.key === 'S' || e.key === 's')) {
      e.preventDefault(); return false;
    }
    // Ctrl+P (Print)
    if ((e.ctrlKey || e.metaKey) && (e.key === 'P' || e.key === 'p')) {
      e.preventDefault(); return false;
    }
  });

  // ── 3. Detect DevTools open (size heuristic) ────────────────────────────────
  let devtoolsOpen = false;
  const threshold = 160;

  function checkDevTools() {
    const widthDiff  = window.outerWidth  - window.innerWidth;
    const heightDiff = window.outerHeight - window.innerHeight;
    const isOpen = widthDiff > threshold || heightDiff > threshold;

    if (isOpen && !devtoolsOpen) {
      devtoolsOpen = true;
      // blur หน้า + แสดง overlay แทนที่จะ redirect ทันที
      document.body.style.filter = 'blur(8px)';
      document.body.style.pointerEvents = 'none';

      const overlay = document.createElement('div');
      overlay.id = 'nas-devtools-block';
      overlay.style.cssText = [
        'position:fixed', 'inset:0', 'z-index:99999',
        'background:rgba(15,23,42,0.95)',
        'display:flex', 'flex-direction:column',
        'align-items:center', 'justify-content:center',
        'color:#f1f5f9', 'font-family:system-ui,sans-serif',
        'gap:12px',
      ].join(';');
      overlay.innerHTML = [
        '<svg viewBox="0 0 24 24" fill="none" stroke="#ef4444" stroke-width="1.5" width="48" height="48">',
        '<rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>',
        '</svg>',
        '<div style="font-size:20px;font-weight:600">การเข้าถึงถูกจำกัด</div>',
        '<div style="font-size:14px;color:#94a3b8">กรุณาปิด Developer Tools แล้วโหลดหน้าใหม่</div>',
        '<button onclick="location.reload()" style="margin-top:8px;padding:10px 24px;background:#2563eb;color:#fff;border:none;border-radius:8px;font-size:14px;cursor:pointer;font-family:inherit">โหลดหน้าใหม่</button>',
      ].join('');
      document.body.appendChild(overlay);
    }

    if (!isOpen && devtoolsOpen) {
      devtoolsOpen = false;
      document.body.style.filter = '';
      document.body.style.pointerEvents = '';
      const el = document.getElementById('nas-devtools-block');
      if (el) el.remove();
    }
  }

  setInterval(checkDevTools, 1000);

  // ── 4. Disable text selection on UI elements (ไม่ block ใน input/textarea) ──
  document.addEventListener('selectstart', function (e) {
    const tag = e.target.tagName.toLowerCase();
    if (['input', 'textarea', 'select'].includes(tag)) return;
    if (e.target.isContentEditable) return;
    e.preventDefault();
  });

  // ── 5. Disable drag ─────────────────────────────────────────────────────────
  document.addEventListener('dragstart', function (e) {
    if (e.target.tagName.toLowerCase() !== 'input') {
      e.preventDefault();
    }
  });

})();
