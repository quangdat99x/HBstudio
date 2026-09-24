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
// ---------------------------------------------------------------- bôi đen để dịch (Google Dịch)
(function selectToTranslate() {
  const AUTO_KEY = 'studio.autoTranslate';
  let pill = null, pop = null, selText = '', selRect = null;
  const getAuto = () => { try { return localStorage.getItem(AUTO_KEY) === '1'; } catch (e) { return false; } };
  const setAuto = v => { try { localStorage.setItem(AUTO_KEY, v ? '1' : '0'); } catch (e) {} };
  const mk = (tag, cls, html) => { const e = document.createElement(tag); if (cls) e.className = cls; if (html != null) e.innerHTML = html; return e; };
  const button = (label, fn, cls) => { const b = mk('button', cls || 'btn btn-tiny', label); b.type = 'button';
    b.addEventListener('mousedown', e => e.preventDefault()); b.addEventListener('click', fn); return b; };

  function ensure() {
    if (pill) return;
    pill = button('🌐 Dịch', () => translateSelection(), 'tr-pill');
    pop = mk('div', 'tr-pop');
    document.body.append(pill, pop);
  }
  function place(node) {
    if (!selRect) return;
    const vw = document.documentElement.clientWidth;
    node.style.left = Math.max(window.scrollX + 8, Math.min(window.scrollX + selRect.left, window.scrollX + vw - node.offsetWidth - 12)) + 'px';
    node.style.top = (window.scrollY + selRect.bottom + 8) + 'px';
  }
  function hide(all) { if (pill) pill.style.display = 'none'; if (all && pop) pop.style.display = 'none'; }
  function currentSelection() {
    const s = window.getSelection();
    if (!s || s.isCollapsed || !s.rangeCount) return null;
    const text = s.toString().trim();
    if (!text || !/[A-Za-z]/.test(text)) return null;
    const node = s.anchorNode && (s.anchorNode.nodeType === 1 ? s.anchorNode : s.anchorNode.parentElement);
    if (node && node.closest('.tr-pop, .tr-pill, input, textarea, select')) return null;
    const range = s.getRangeAt(0), rects = range.getClientRects();
    return { text, rect: rects.length ? rects[rects.length - 1] : range.getBoundingClientRect() };
  }
  async function openWeb(text) {
    const r = await api('/api/translate/open', { text });
    if (r.error) window.open(r.url || ('https://translate.google.com/?sl=auto&tl=vi&op=translate&text=' + encodeURIComponent(text)), '_blank');
    else toast('Đã mở Google Dịch trên trình duyệt');
  }
  function render(text, r) {
    pop.innerHTML = '';
    const head = mk('div', 'tr-head');
    head.append(mk('span', 'tr-lang', r && r.source ? esc(String(r.source).toUpperCase()) + ' → VI' : 'Google Dịch'));
    const actions = mk('span', 'tr-actions');
    if (r && r.translation) actions.append(button('Copy', () => copyText(r.translation)));
    actions.append(button('Google Dịch ↗', () => openWeb(text)), button('×', () => hide(true)));
    head.append(actions);
    pop.append(head);
    if (r && r.translation) {
      pop.append(mk('div', 'tr-body', esc(r.translation)));
    } else if (r && r.code === 'no_key') {
      const body = mk('div', 'tr-body', 'Chưa có Google API key nên chưa dịch ngay trong Studio được. ');
      const row = mk('div', 'row gap tr-row');
      row.append(button('Mở trên Google Dịch', () => openWeb(text), 'btn btn-small btn-primary'),
                 button('Cài API key', () => { location.href = '/settings#google-translate'; }, 'btn btn-small'));
      pop.append(body, row);
    } else {
      pop.append(mk('div', 'tr-body error', esc((r && r.error) || 'Không dịch được')));
    }
    const foot = mk('label', 'tr-foot');
    const cb = mk('input'); cb.type = 'checkbox'; cb.checked = getAuto();
    cb.addEventListener('change', () => { setAuto(cb.checked); toast(cb.checked ? 'Bôi đen là tự dịch' : 'Bôi đen rồi bấm Dịch'); });
    foot.append(cb, document.createTextNode(' Tự dịch ngay khi bôi đen'));
    pop.append(foot);
  }
  async function translateSelection() {
    ensure(); hide(false);
    const text = selText; if (!text) return;
    pop.innerHTML = '<div class="tr-body muted">Đang dịch…</div>';
    pop.style.display = 'block'; place(pop);
    let r;
    try { r = await api('/api/translate', { text }); } catch (e) { r = { error: String(e) }; }
    if (r.error && String(r.error).includes('HTTP 404')) r = { error: 'Studio chưa nạp tính năng dịch: bấm Stop rồi Start JRE Studio trong Tool Manager' };
    render(text, r); place(pop);
  }
  document.addEventListener('mouseup', e => {
    if ((pop && pop.contains(e.target)) || (pill && pill.contains(e.target))) return;
    setTimeout(() => {
      const cur = currentSelection();
      if (!cur) { hide(false); return; }
      ensure(); selText = cur.text; selRect = cur.rect;
      if (getAuto() && selText.length <= 1500) { translateSelection(); return; }
      pill.style.display = 'block'; place(pill);
    }, 0);
  });
  document.addEventListener('mousedown', e => {
    if (pop && pop.style.display === 'block' && !pop.contains(e.target) && !(pill && pill.contains(e.target))) pop.style.display = 'none';
  });
  document.addEventListener('keydown', e => { if (e.key === 'Escape') hide(true); });
  window.addEventListener('scroll', () => hide(false), { passive: true });
})();

(async function headerStats() {
  try { const s = await (await fetch('/api/stats')).json();
    document.getElementById('header-stats').textContent = `${s.episodes} tập · ${s.highlights} highlight · ${s.hooks} hook · ${s.zoomed} đã zoom · ${s.with_analysis} có phân tích`; } catch (e) {}
})();
