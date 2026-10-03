// Shared helpers for Creater Vid pages
async function api(url, body, method) {
  const r = await fetch(url, { method: method || 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body || {}) });
  let data; try { data = await r.json(); } catch (e) { data = { error: 'HTTP ' + r.status }; }
  if (!r.ok && !data.error) data.error = 'HTTP ' + r.status;
  return data;
}
function esc(s) { return String(s == null ? '' : s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c])); }
let _toastTimer;
function toast(msg) { const t = document.getElementById('toast'); t.textContent = msg; t.classList.add('show'); clearTimeout(_toastTimer); _toastTimer = setTimeout(() => t.classList.remove('show'), 3800); }
function copyText(t) {
  const done = () => toast('Đã copy');
  const fallback = () => { const ta = document.createElement('textarea'); ta.value = t; ta.style.position = 'fixed'; ta.style.opacity = '0';
    document.body.appendChild(ta); ta.select(); try { document.execCommand('copy'); done(); } catch (e) { toast('Không copy được'); } ta.remove(); };
  if (navigator.clipboard && window.isSecureContext) navigator.clipboard.writeText(t).then(done).catch(fallback); else fallback();
}
async function openFolder(path) { const r = await api('/api/open-folder', { path }); if (r.error) toast(r.error); }

// Header: what Claude is doing right now, on every page
(async function headerStatus() {
  const el = document.getElementById('header-status');
  async function tick() {
    try {
      const s = await (await fetch('/api/status')).json();
      if (!s.worker) { el.innerHTML = '<span class="error">hàng đợi Claude chưa chạy</span>'; return; }
      if (s.current) {
        const q = s.queue.length ? ` · ${s.queue.length} lượt chờ` : '';
        el.innerHTML = `<span class="spin"></span><a href="/p/${s.current.project_id}${s.current.step ? '?step=' + s.current.step : ''}">${esc(s.current.project_title)}</a>: ${esc((s.current.progress_msg || '').slice(0, 90))}${q}`;
      } else {
        el.textContent = `${s.projects} dự án · Claude rảnh · đã tốn $${(s.cost_usd || 0).toFixed(2)}`;
      }
    } catch (e) {}
  }
  if (el) { tick(); setInterval(tick, 8000); }
})();
