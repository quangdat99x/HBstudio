// Shared helpers for JRE Studio pages
async function api(url, body, method) {
  const r = await fetch(url, { method: method || 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body || {}) });
  let data; try { data = await r.json(); } catch (e) { data = { error: 'HTTP ' + r.status }; }
  if (!r.ok && !data.error) data.error = 'HTTP ' + r.status;
  return data;
}
function esc(s) { return String(s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c])); }
let _toastTimer;
function toast(msg) { const t = document.getElementById('toast'); t.textContent = msg; t.classList.add('show'); clearTimeout(_toastTimer); _toastTimer = setTimeout(() => t.classList.remove('show'), 3500); }
function copyText(t) {
  const done = () => toast('Đã copy');
  const fallback = () => { const ta = document.createElement('textarea'); ta.value = t; ta.style.position = 'fixed'; ta.style.opacity = '0';
    document.body.appendChild(ta); ta.select(); try { document.execCommand('copy'); done(); } catch (e) { toast('Không copy được'); } ta.remove(); };
  if (navigator.clipboard && window.isSecureContext) navigator.clipboard.writeText(t).then(done).catch(fallback); else fallback();
}
function copyEl(id) { const el = document.getElementById(id); if (el) copyText(el.innerText); }
async function openFolder(path) { const r = await api('/api/open-folder', { path }); if (r.error) toast(r.error); }
(async function headerStats() {
  try { const s = await (await fetch('/api/stats')).json();
    document.getElementById('header-stats').textContent = `${s.episodes} tập · ${s.highlights} highlight · ${s.hooks} hook · ${s.zoomed} đã zoom · ${s.with_analysis} có phân tích`; } catch (e) {}
})();
