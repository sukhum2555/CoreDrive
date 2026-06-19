'use strict';

// ─── Admin drive polling ──────────────────────────────────────────────────────

const DRIVE_ICON = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14"><ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/></svg>`;

function renderAdminDrives(drives) {
  const el = document.getElementById('admin-drives');
  if (!el || !drives) return;

  if (!drives.length) {
    el.innerHTML = '<div class="empty-note">ไม่สามารถอ่านข้อมูล disk ได้</div>';
    return;
  }

  el.innerHTML = drives.map(d => {
    const pctClass = d.percent > 90 ? 'pct-red' : d.percent > 70 ? 'pct-amber' : '';
    const barColor = d.percent > 90 ? 'background:#dc2626' : d.percent > 70 ? 'background:#f59e0b' : '';
    return `<div class="drive-row">
      <div class="drive-row-top">
        <span class="drive-row-name">${DRIVE_ICON}${escHtml(d.name)}</span>
        <span class="drive-row-pct ${pctClass}">${Math.round(d.percent)}%</span>
      </div>
      <div class="bar-track" style="height:6px;margin:6px 0 4px">
        <div class="bar-fill" style="height:6px;width:${Math.round(d.percent)}%;${barColor}"></div>
      </div>
      <div class="drive-row-sizes">${escHtml(d.used_h)} ใช้ไป / ${escHtml(d.free_h)} ว่าง / รวม ${escHtml(d.total_h)}</div>
    </div>`;
  }).join('');
}

function escHtml(str) {
  return String(str)
    .replace(/&/g,'&amp;').replace(/</g,'&lt;')
    .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function pollAdminDrives() {
  fetch('/api/drives/')
    .then(r => r.ok ? r.json() : null)
    .then(data => { if (data) renderAdminDrives(data.drives); })
    .catch(() => {})
    .finally(() => setTimeout(pollAdminDrives, 5000));
}

window.addEventListener('load', () => {
  if (document.getElementById('admin-drives')) {
    setTimeout(pollAdminDrives, 1000);
  }
});
