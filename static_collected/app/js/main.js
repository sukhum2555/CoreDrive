/* NAS Drive — main.js */
'use strict';

// ─── Helpers ─────────────────────────────────────────────────────────────────

function getCsrf() {
  return document.querySelector('[name=csrfmiddlewaretoken]')?.value || '';
}

function post(url, data) {
  const fd = new FormData();
  fd.append('csrfmiddlewaretoken', getCsrf());
  if (data) Object.entries(data).forEach(([k, v]) => fd.append(k, v));
  return fetch(url, { method: 'POST', body: fd });
}

function humanSize(bytes) {
  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  let size = bytes;
  for (const u of units) {
    if (size < 1024) return `${size.toFixed(1)} ${u}`;
    size /= 1024;
  }
  return `${size.toFixed(1)} PB`;
}

// ─── Auto-dismiss toasts ──────────────────────────────────────────────────────

document.querySelectorAll('.toast').forEach(t => {
  setTimeout(() => t.remove(), 4000);
});

// ─── User Dropdown ────────────────────────────────────────────────────────────

const avatar = document.querySelector('.avatar');
const dropdown = document.getElementById('user-dropdown');
if (avatar && dropdown) {
  avatar.addEventListener('click', e => {
    e.stopPropagation();
    dropdown.classList.toggle('open');
  });
  document.addEventListener('click', () => dropdown.classList.remove('open'));
}

// ─── View Mode ────────────────────────────────────────────────────────────────

function setView(mode) {
  const url = new URL(window.location.href);
  url.searchParams.set('view', mode);
  window.location.href = url.toString();
}

// ─── Upload Modal ─────────────────────────────────────────────────────────────

const uploadModal   = document.getElementById('upload-modal');
const dropZone      = document.getElementById('drop-zone');
const fileInput     = document.getElementById('file-input');
const filePreview   = document.getElementById('file-list-preview');
const uploadSubmit  = document.getElementById('upload-submit');

function openUpload() { uploadModal.style.display = 'flex'; }
function closeUpload() { uploadModal.style.display = 'none'; clearFilePreview(); }

['upload-trigger', 'upload-trigger-tb', 'upload-trigger-empty'].forEach(id => {
  document.getElementById(id)?.addEventListener('click', openUpload);
});
document.getElementById('upload-close')?.addEventListener('click', closeUpload);
document.getElementById('upload-cancel')?.addEventListener('click', closeUpload);

// Click on drop zone triggers file picker
dropZone?.addEventListener('click', () => fileInput?.click());

// Drag & drop
dropZone?.addEventListener('dragover', e => { e.preventDefault(); dropZone.classList.add('drag-over'); });
dropZone?.addEventListener('dragleave', () => dropZone.classList.remove('drag-over'));
dropZone?.addEventListener('drop', e => {
  e.preventDefault();
  dropZone.classList.remove('drag-over');
  const dt = e.dataTransfer;
  if (dt?.files.length) handleFiles(dt.files);
});

fileInput?.addEventListener('change', () => {
  if (fileInput.files.length) handleFiles(fileInput.files);
});

function handleFiles(files) {
  if (!filePreview) return;
  filePreview.innerHTML = '';
  Array.from(files).forEach(f => {
    const div = document.createElement('div');
    div.className = 'upload-file-item';
    div.innerHTML = `<span class="upload-file-name">${escHtml(f.name)}</span><span class="upload-file-size">${humanSize(f.size)}</span>`;
    filePreview.appendChild(div);
  });
  if (uploadSubmit) uploadSubmit.disabled = files.length === 0;

  // Sync files to actual input
  const dt = new DataTransfer();
  Array.from(files).forEach(f => dt.items.add(f));
  if (fileInput) fileInput.files = dt.files;
}

function clearFilePreview() {
  if (filePreview) filePreview.innerHTML = '';
  if (fileInput) fileInput.value = '';
  if (uploadSubmit) uploadSubmit.disabled = true;
}

// Drag & drop on entire page
document.addEventListener('dragover', e => e.preventDefault());
document.addEventListener('drop', e => {
  e.preventDefault();
  if (uploadModal?.style.display !== 'flex') {
    openUpload();
    if (e.dataTransfer?.files.length) handleFiles(e.dataTransfer.files);
  }
});

// ─── New Folder Modal ─────────────────────────────────────────────────────────

const folderModal = document.getElementById('folder-modal');
document.getElementById('new-folder-btn')?.addEventListener('click', () => {
  folderModal.style.display = 'flex';
  document.getElementById('folder-name-input')?.select();
});
['folder-close', 'folder-cancel'].forEach(id => {
  document.getElementById(id)?.addEventListener('click', () => folderModal.style.display = 'none');
});

// ─── Rename Modal ─────────────────────────────────────────────────────────────

const renameModal  = document.getElementById('rename-modal');
const renameForm   = document.getElementById('rename-form');
const renameInput  = document.getElementById('rename-input');

function openRename(nodeId, currentName) {
  if (!renameModal || !renameForm || !renameInput) return;
  renameForm.action = `/node/${nodeId}/rename/`;
  renameInput.value = currentName;
  renameModal.style.display = 'flex';
  renameInput.select();
}
['rename-close', 'rename-cancel'].forEach(id => {
  document.getElementById(id)?.addEventListener('click', () => renameModal.style.display = 'none');
});

// ─── Share Modal ──────────────────────────────────────────────────────────────

const shareModal = document.getElementById('share-modal');
const shareUrlInput = document.getElementById('share-url');

function openShare(nodeId) {
  if (!shareModal) return;
  shareModal.style.display = 'flex';
  if (shareUrlInput) shareUrlInput.value = 'กำลังสร้างลิงก์...';
  // ล้าง expiry notice เก่า
  const oldNotice = document.getElementById('share-expiry-notice');
  if (oldNotice) oldNotice.remove();

  post(`/node/${nodeId}/share/`)
    .then(r => r.json())
    .then(d => {
      if (shareUrlInput && d.url) shareUrlInput.value = d.url;
      // แสดงวันหมดอายุถ้ามี
      const modalBody = shareModal.querySelector('.modal-body');
      if (d.expires_at) {
        const notice = document.createElement('p');
        notice.id = 'share-expiry-notice';
        notice.style.cssText = 'font-size:12px;color:#92400e;background:#fffbeb;border:0.5px solid #fde68a;border-radius:6px;padding:6px 10px;margin-top:10px;display:flex;align-items:center;gap:6px';
        notice.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="13" height="13"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>ลิงก์นี้จะหมดอายุ: ${escHtml(d.expires_at)}`;
        if (modalBody) modalBody.appendChild(notice);
      } else if (d.expire_days === 0) {
        const notice = document.createElement('p');
        notice.id = 'share-expiry-notice';
        notice.style.cssText = 'font-size:12px;color:var(--text-muted);margin-top:8px';
        notice.textContent = 'ลิงก์นี้ไม่มีวันหมดอายุ';
        if (modalBody) modalBody.appendChild(notice);
      }
    })
    .catch(() => { if (shareUrlInput) shareUrlInput.value = 'เกิดข้อผิดพลาด'; });
}
['share-close', 'share-cancel'].forEach(id => {
  document.getElementById(id)?.addEventListener('click', () => shareModal.style.display = 'none');
});
document.getElementById('copy-share-btn')?.addEventListener('click', () => {
  if (!shareUrlInput) return;
  navigator.clipboard.writeText(shareUrlInput.value).then(() => {
    const btn = document.getElementById('copy-share-btn');
    if (btn) { const old = btn.textContent; btn.textContent = 'คัดลอกแล้ว!'; setTimeout(() => btn.textContent = old, 2000); }
  });
});

// Close modals on overlay click
[uploadModal, folderModal, renameModal, shareModal].forEach(m => {
  m?.addEventListener('click', e => { if (e.target === m) m.style.display = 'none'; });
});

// ─── Context Menu ─────────────────────────────────────────────────────────────

const ctxMenu  = document.getElementById('context-menu');
let ctxNodeId  = null;
let ctxNodeType = null;
let ctxNodeName = null;

function showCtx(e, nodeId, nodeName, nodeType) {
  e.preventDefault(); e.stopPropagation();
  ctxNodeId = nodeId; ctxNodeType = nodeType; ctxNodeName = nodeName;

  const isFile = nodeType === 'file';
  document.getElementById('ctx-download').style.display = isFile ? 'flex' : 'none';
  document.getElementById('ctx-open').textContent = isFile ? 'ดูตัวอย่าง' : 'เปิดโฟลเดอร์';

  ctxMenu.style.display = 'block';
  let x = e.clientX, y = e.clientY;
  const rect = ctxMenu.getBoundingClientRect();
  if (x + 190 > window.innerWidth) x = window.innerWidth - 200;
  if (y + rect.height + 10 > window.innerHeight) y = window.innerHeight - rect.height - 10;
  ctxMenu.style.left = x + 'px';
  ctxMenu.style.top  = y + 'px';
}

document.addEventListener('click', () => ctxMenu && (ctxMenu.style.display = 'none'));
document.addEventListener('contextmenu', e => {
  const card = e.target.closest('[data-id]');
  if (card) showCtx(e, card.dataset.id, card.dataset.name, card.closest('.file-row') ? 'file' : (card.closest('.folder-card') ? 'folder' : 'file'));
});

// Context menu actions
document.getElementById('ctx-open')?.addEventListener('click', () => {
  if (!ctxNodeId) return;
  if (ctxNodeType === 'file') window.location.href = `/file/${ctxNodeId}/preview/`;
  else window.location.href = `/folder/${ctxNodeId}/`;
});

document.getElementById('ctx-download')?.addEventListener('click', () => {
  if (ctxNodeId) window.location.href = `/file/${ctxNodeId}/download/`;
});

document.getElementById('ctx-share')?.addEventListener('click', () => {
  if (ctxNodeId) openShare(ctxNodeId);
});

document.getElementById('ctx-rename')?.addEventListener('click', () => {
  if (ctxNodeId) openRename(ctxNodeId, ctxNodeName);
});

document.getElementById('ctx-star')?.addEventListener('click', () => {
  if (!ctxNodeId) return;
  post(`/node/${ctxNodeId}/star/`)
    .then(r => r.json())
    .then(d => showFlash(d.starred ? 'เพิ่มใน Starred แล้ว' : 'นำออกจาก Starred แล้ว'));
});

document.getElementById('ctx-trash')?.addEventListener('click', () => {
  if (!ctxNodeId) return;
  const form = document.getElementById('trash-form');
  if (form) { form.action = `/node/${ctxNodeId}/trash/`; form.submit(); }
});

// ─── Node menu button (⋮) ─────────────────────────────────────────────────────

document.addEventListener('click', e => {
  const btn = e.target.closest('.node-menu-btn');
  if (!btn) return;
  e.stopPropagation();
  const { id, name, type } = btn.dataset;
  showCtx(e, id, name, type);
});

// ─── Detail Panel ─────────────────────────────────────────────────────────────

const detailPanel = document.getElementById('detail-panel');
const detailBody  = document.getElementById('detail-body');
const detailTitle = document.getElementById('detail-title');

function openDetail(nodeId) {
  if (!detailPanel) return;
  detailPanel.classList.add('open');
  if (detailBody) detailBody.innerHTML = '<div class="detail-loading">กำลังโหลด...</div>';

  fetch(`/node/${nodeId}/detail/`)
    .then(r => r.json())
    .then(d => renderDetailPanel(d))
    .catch(() => { if (detailBody) detailBody.innerHTML = '<div class="detail-loading">เกิดข้อผิดพลาด</div>'; });
}

function renderDetailPanel(d) {
  if (!detailBody) return;
  if (detailTitle) detailTitle.textContent = 'รายละเอียด';

  const isImg = ['jpg','jpeg','png','gif','webp'].includes(d.extension);
  const previewHtml = isImg
    ? `<div class="detail-preview"><img src="/file/${d.id}/download/" alt="${escHtml(d.name)}"></div>`
    : `<div class="detail-preview"><svg viewBox="0 0 24 24" fill="none" stroke="var(--accent)" stroke-width="1.5" width="48" height="48"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8l-6-6z"/><polyline points="14 2 14 8 20 8"/></svg></div>`;

  detailBody.innerHTML = `
    ${previewHtml}
    <div class="detail-info">
      <div class="detail-row"><span class="detail-key">ชื่อ</span><span class="detail-val">${escHtml(d.name)}</span></div>
      ${!d.is_folder ? `<div class="detail-row"><span class="detail-key">ขนาด</span><span class="detail-val">${d.size}</span></div>` : ''}
      ${!d.is_folder ? `<div class="detail-row"><span class="detail-key">ประเภท</span><span class="detail-val">${escHtml(d.extension?.toUpperCase() || '—')}</span></div>` : ''}
      <div class="detail-row"><span class="detail-key">แก้ไขล่าสุด</span><span class="detail-val">${d.updated_at}</span></div>
      <div class="detail-row"><span class="detail-key">สร้างเมื่อ</span><span class="detail-val">${d.created_at}</span></div>
    </div>
    <div class="detail-actions">
      ${!d.is_folder ? `<button class="detail-action-btn primary" onclick="window.location='/file/${d.id}/download/'">
        <svg viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2" width="14" height="14"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
        ดาวน์โหลด
      </button>` : ''}
      ${!d.is_folder ? `<button class="detail-action-btn" onclick="window.location='/file/${d.id}/preview/'">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
        ดูตัวอย่าง
      </button>` : ''}
      <button class="detail-action-btn" onclick="openShare('${d.id}')">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14"><circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/><line x1="8.59" y1="13.51" x2="15.42" y2="17.49"/><line x1="15.41" y1="6.51" x2="8.59" y2="10.49"/></svg>
        แชร์
      </button>
      <button class="detail-action-btn" onclick="openRename('${d.id}', '${escHtml(d.name)}')">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
        เปลี่ยนชื่อ
      </button>
      <button class="detail-action-btn danger" onclick="trashNode('${d.id}')">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
        ลบไฟล์
      </button>
    </div>`;
}

function trashNode(nodeId) {
  const form = document.getElementById('trash-form');
  if (form) { form.action = `/node/${nodeId}/trash/`; form.submit(); }
}

document.getElementById('detail-close')?.addEventListener('click', () => {
  detailPanel?.classList.remove('open');
});

// ─── Flash message ────────────────────────────────────────────────────────────

function showFlash(msg) {
  let container = document.querySelector('.toast-container');
  if (!container) {
    container = document.createElement('div');
    container.className = 'toast-container';
    document.body.appendChild(container);
  }
  const toast = document.createElement('div');
  toast.className = 'toast toast-info';
  toast.innerHTML = `${escHtml(msg)}<button class="toast-close" onclick="this.parentElement.remove()">×</button>`;
  container.appendChild(toast);
  setTimeout(() => toast.remove(), 3500);
}

// ─── Escape HTML ─────────────────────────────────────────────────────────────

function escHtml(str) {
  return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

// ─── Keyboard shortcuts ───────────────────────────────────────────────────────

document.addEventListener('keydown', e => {
  if (e.key === 'Escape') {
    [uploadModal, folderModal, renameModal, shareModal].forEach(m => { if (m) m.style.display = 'none'; });
    detailPanel?.classList.remove('open');
    if (ctxMenu) ctxMenu.style.display = 'none';
  }
  // Ctrl+U = upload
  if ((e.ctrlKey || e.metaKey) && e.key === 'u') { e.preventDefault(); openUpload(); }
  // Ctrl+Shift+N = new folder
  if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key === 'N') { e.preventDefault(); folderModal && (folderModal.style.display = 'flex'); }
});


// ─── Drive polling ────────────────────────────────────────────────────────────

const DRIVE_ICON_SVG = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="13" height="13" style="flex-shrink:0"><ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/></svg>`;

let _lastDriveNames = null;

function renderDrives(drives) {
  const container = document.getElementById('drives-container');
  if (!container) return;

  if (!drives || drives.length === 0) {
    container.innerHTML = '<div class="storage-used">ไม่สามารถอ่านข้อมูลดิสก์ได้</div>';
    return;
  }

  const currentNames = drives.map(d => d.name).join(',');
  const isFirstRender = _lastDriveNames === null;
  const hasChanged = _lastDriveNames !== currentNames;

  // Flash toast when drive is added/removed (skip first load)
  if (!isFirstRender && hasChanged) {
    const prev = new Set(_lastDriveNames.split(','));
    const curr = new Set(currentNames.split(','));
    curr.forEach(n => { if (!prev.has(n)) showFlash(`เชื่อมต่อ Drive: ${n}`); });
    prev.forEach(n => { if (!curr.has(n)) showFlash(`ถอด Drive: ${n}`); });
  }

  _lastDriveNames = currentNames;

  // Re-render only if drives changed, otherwise just update bars in-place
  if (hasChanged) {
    container.innerHTML = drives.map((d, i) => {
      const barColor = d.percent > 90 ? '#dc2626' : d.percent > 70 ? '#f59e0b' : '';
      return `
        <div class="drive-item${isFirstRender ? '' : ' drive-new'}" data-drive="${escHtml(d.name)}">
          <div class="drive-header">
            <span class="drive-name">${DRIVE_ICON_SVG}${escHtml(d.name)}</span>
            <span class="drive-pct">${Math.round(d.percent)}%</span>
          </div>
          <div class="bar-track">
            <div class="bar-fill" style="width:${Math.round(d.percent)}%${barColor ? ';background:' + barColor : ''}"></div>
          </div>
          <div class="drive-sizes">${escHtml(d.used_h)} / ${escHtml(d.total_h)}</div>
        </div>`;
    }).join('');
  } else {
    // Just update numbers/bars without re-rendering DOM
    drives.forEach(d => {
      const item = container.querySelector(`[data-drive="${CSS.escape(d.name)}"]`);
      if (!item) return;
      const barColor = d.percent > 90 ? '#dc2626' : d.percent > 70 ? '#f59e0b' : '';
      item.querySelector('.drive-pct').textContent = Math.round(d.percent) + '%';
      item.querySelector('.drive-sizes').textContent = `${d.used_h} / ${d.total_h}`;
      const fill = item.querySelector('.bar-fill');
      fill.style.width = Math.round(d.percent) + '%';
      fill.style.background = barColor || '';
    });
  }
}

function pollDrives() {
  // เฉพาะ admin ที่มี drives-container เท่านั้น
  if (!document.getElementById('drives-container')) return;
  fetch('/api/drives/')
    .then(r => r.ok ? r.json() : null)
    .then(data => { if (data) renderDrives(data.drives); })
    .catch(() => {})
    .finally(() => setTimeout(pollDrives, 5000));
}

// Start polling after page load
window.addEventListener('load', () => setTimeout(pollDrives, 1000));