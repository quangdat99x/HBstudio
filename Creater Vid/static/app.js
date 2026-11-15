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
      const run = s.running || (s.current ? [s.current] : []);
      if (run.length) {
        const q = s.queue.length ? ` · ${s.queue.length} lượt chờ` : '';
        const more = run.length > 1 ? ` <a href="/activity">+${run.length - 1} lượt khác</a>` : '';
        el.innerHTML = `<span class="spin"></span><a href="/p/${run[0].project_id}${run[0].step ? '?step=' + run[0].step : ''}">${esc(run[0].project_title)}</a>: ${esc((run[0].progress_msg || '').slice(0, 70))}${more}${q}`;
      } else {
        el.textContent = `${s.projects} dự án · Claude rảnh · đã tốn $${(s.cost_usd || 0).toFixed(2)}`;
      }
    } catch (e) {}
  }
  if (el) { tick(); setInterval(tick, 8000); }
})();

// Quota bar: Claude plan limits, ElevenLabs characters, fal balance, what the app spent this month
(function quotaBar() {
  const el = document.getElementById('quota-bar');
  if (!el) return;
  const when = iso => { if (!iso) return ''; const d = new Date(iso), now = new Date();
    const hm = d.toLocaleTimeString('vi-VN', {hour: '2-digit', minute: '2-digit'});
    return d.toDateString() === now.toDateString() ? hm : `${hm} ${d.toLocaleDateString('vi-VN', {day: '2-digit', month: '2-digit'})}`; };
  const meter = (pct, invert) => { const bad = invert ? pct <= 10 : pct >= 85, warn = invert ? pct <= 30 : pct >= 60;
    return `<span class="q-meter ${bad ? 'bad' : warn ? 'warn' : ''}"><span style="width:${Math.min(100, Math.max(2, pct))}%"></span></span>`; };
  const money = v => '$' + (Number(v) || 0).toFixed(2);
  async function load(force) {
    let q; try { q = await (await fetch('/api/quota' + (force ? '?refresh=1' : ''))).json(); } catch (e) { return; }
    const parts = [];
    const c = q.claude || {};
    if (c.ok) {
      for (const w of c.windows || []) parts.push(`<span class="q-item" title="Giới hạn gói Claude ${esc(c.plan || '')} · reset ${esc(when(w.resets_at))}">Claude ${esc(w.label)} ${meter(w.percent)}<b>${w.percent}%</b><span class="muted">↻ ${esc(when(w.resets_at))}</span></span>`);
      if (c.extra) parts.push(`<span class="q-item" title="Extra usage: dùng thêm trả tiền khi hết giới hạn">extra ${c.extra.enabled ? `<b>${money(c.extra.used)}</b>/${money(c.extra.limit)}` : '<span class="muted">tắt</span>'}</span>`);
    } else parts.push(`<span class="q-item q-err" title="${esc(c.error || '')}">Claude: ${esc((c.error || 'chưa đọc được').slice(0, 60))}</span>`);
    parts.push('<span class="q-sep"></span>');
    const e = q.elevenlabs || {};
    if (e.ok && e.models) parts.push(`<span class="q-item" title="Key qua địa chỉ trung gian: không đọc được số ký tự còn lại">ElevenLabs <b>✓ key dùng được</b> <span class="muted">(không rõ số dư)</span></span>`);
    else if (e.ok) { const left = 100 - (e.percent || 0);
      parts.push(`<span class="q-item" title="ElevenLabs ${esc(e.tier || '')}: đã dùng ${(e.used || 0).toLocaleString('vi-VN')} / ${(e.limit || 0).toLocaleString('vi-VN')} ký tự · reset ${esc(e.reset || '')}">ElevenLabs ${meter(left, true)}<b>còn ${(e.left || 0).toLocaleString('vi-VN')}</b> ký tự <span class="muted">↻ ${esc((e.reset || '').slice(8, 10) + '/' + (e.reset || '').slice(5, 7))}</span></span>`); }
    else parts.push(`<span class="q-item q-err" title="${esc(e.error || '')}">ElevenLabs: ${esc((e.error || '').slice(0, 40))}</span>`);
    const f = q.fal || {};
    if (f.ok && f.balance != null) parts.push(`<span class="q-item" title="Số dư fal.ai">fal <b class="${f.balance < 2 ? 'q-err' : ''}">${money(f.balance)}</b></span>`);
    else if (f.ok) parts.push(`<span class="q-item muted" title="${esc(f.balance_note || '')}">fal: key ok, không xem được số dư</span>`);
    else parts.push(`<span class="q-item muted" title="${esc(f.error || '')}">fal: ${esc(f.error || 'lỗi')}</span>`);
    const sp = (q.spend || {}).providers || {};
    const names = {openai: 'OpenAI', google: 'Google', fal: 'fal', elevenlabs: 'ElevenLabs'};
    const spent = Object.entries(sp).map(([k, v]) => `${names[k] || k} <b>${money(v.month)}</b>`).join(' · ');
    if (spent) parts.push(`<span class="q-sep"></span><span class="q-item" title="Tiền nguyên liệu app đã tiêu tháng này (notes/costs.json mọi dự án); OpenAI/Google không có API báo số dư">tháng này: ${spent}</span>`);
    if ((q.spend || {}).claude_api_equiv_today != null) parts.push(`<span class="q-item muted" title="Giá trị API tương đương của các lượt Claude hôm nay (gói Max không tính tiền theo số này; cho biết mức dùng nặng hay nhẹ)">Claude hôm nay ≈ ${money(q.spend.claude_api_equiv_today)}</span>`);
    parts.push(`<span class="q-item q-btn" onclick="event.stopPropagation(); window._quotaLoad(true)" title="Đọc lại ngay">⟳ ${esc(when(q.at))}</span>`);
    el.innerHTML = parts.join('');
  }
  window._quotaLoad = load;
  load(false); setInterval(() => load(false), 120000);
})();

// copy the text of an element (step 7: title, description, tags)
function copyEl(id) { const el = document.getElementById(id); if (el) copyText(el.innerText); }
