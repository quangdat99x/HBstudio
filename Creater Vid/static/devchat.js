// Dev chat panel of the Pipeline page: chat with Claude Code about one node, it edits the app's code.
// Same file in Hổ Báo Studio and Creater Vid (static/devchat.js): keep them identical.
(function () {
  const CSS = `
  .dc { display: flex; flex-direction: column; height: 100%; min-height: 0; }
  .dc-head { display: flex; align-items: center; gap: 8px; padding: 12px 16px; border-bottom: 1px solid var(--border); }
  .dc-head .t { font-weight: 600; font-size: 14px; flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .dc-msgs { flex: 1; overflow-y: auto; padding: 12px 16px; display: flex; flex-direction: column; gap: 12px; min-height: 120px; }
  .dc-m { font-size: 13.5px; line-height: 1.55; border-radius: 10px; padding: 9px 12px; max-width: 100%; overflow-wrap: anywhere; }
  .dc-m.user { background: var(--accent-glow); border: 1px solid rgba(139,92,246,.35); align-self: flex-end; white-space: pre-wrap; }
  .dc-m.bot { background: var(--bg-input); border: 1px solid var(--border); }
  .dc-m.bot.fail { border-color: rgba(239,68,68,.5); }
  .dc-m pre { background: #0b0b0d; padding: 8px; border-radius: 6px; overflow-x: auto; font-size: 12px; margin: 6px 0; }
  .dc-m code { font-size: 12px; } .dc-m p { margin: 4px 0; } .dc-m ul, .dc-m ol { margin: 4px 0 4px 18px; }
  .dc-meta { font-size: 11.5px; color: var(--text-muted); margin-top: 6px; display: flex; flex-wrap: wrap; gap: 4px 10px; }
  .dc-files { font-size: 12px; margin-top: 6px; color: var(--text-secondary); }
  .dc-files code { background: rgba(255,255,255,.06); padding: 0 4px; border-radius: 4px; }
  .dc-act { font-size: 11.5px; color: var(--text-muted); font-family: ui-monospace, Consolas, monospace; margin-top: 6px; max-height: 110px; overflow-y: auto; }
  .dc-act div { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .dc-live { border-color: rgba(96,165,250,.5) !important; }
  .dc-dots::after { content: '…'; animation: dc-blink 1s steps(3) infinite; }
  @keyframes dc-blink { 50% { opacity: .3; } }
  .dc-empty { color: var(--text-muted); font-size: 13px; line-height: 1.6; }
  .dc-empty b { color: var(--text-secondary); }
  .dc-restart { margin: 0 16px 8px; padding: 8px 10px; border: 1px solid rgba(251,191,36,.5); border-radius: 8px; font-size: 12.5px;
    color: var(--warning); display: flex; align-items: center; gap: 8px; }
  .dc-in { border-top: 1px solid var(--border); padding: 10px 16px 12px; display: flex; flex-direction: column; gap: 8px; }
  .dc-in textarea { width: 100%; min-height: 72px; max-height: 240px; resize: vertical; background: var(--bg-input); border: 1px solid var(--border);
    border-radius: 8px; color: var(--text); padding: 8px 10px; font: inherit; font-size: 13.5px; }
  .dc-in textarea:focus { outline: none; border-color: var(--border-focus); }
  .dc-row { display: flex; gap: 6px; align-items: center; flex-wrap: wrap; }
  .dc-row select { background: var(--bg-input); border: 1px solid var(--border); color: var(--text); border-radius: 6px; padding: 4px 6px; font-size: 12.5px; }
  .dc-row .sp { flex: 1; }`;
  if (!document.getElementById('dc-css')) { const s = document.createElement('style'); s.id = 'dc-css'; s.textContent = CSS; document.head.appendChild(s); }

  const e = s => String(s == null ? '' : s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const LS = 'dc-model-v1';
  async function post(url, body) {
    const r = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Devchat': '1' }, body: JSON.stringify(body || {}) });
    let d; try { d = await r.json(); } catch (x) { d = { error: 'HTTP ' + r.status }; }
    if (!r.ok && !d.error) d.error = 'HTTP ' + r.status; return d;
  }
  function note(msg) { if (typeof toast === 'function') toast(msg); else alert(msg); }
  function fmtDur(s) { if (s == null) return ''; s = Math.round(s); return s < 60 ? s + ' giây' : Math.floor(s / 60) + ' phút ' + (s % 60) + ' giây'; }
  // The answer ends with a "KHỞI ĐỘNG LẠI: CẦN|KHÔNG" line for the app (shown as a badge instead): drop that paragraph.
  function stripFlag(html) {
    return html.replace(/<p[^>]*>(?:(?!<\/p>)[^])*?KHỞI ĐỘNG LẠI:\s*(?:CẦN|KHÔNG)(?:(?!<\/p>)[^])*<\/p>/gi, '')
      .replace(/[`*]*KHỞI ĐỘNG LẠI:\s*(?:CẦN|KHÔNG)[`*]*/gi, '');
  }

  function mount(el, opts) {
    const node = opts.node, base = '/api/devchat/' + encodeURIComponent(node);
    let pref = { model: 'opus', effort: 'high' }; try { pref = Object.assign(pref, JSON.parse(localStorage.getItem(LS) || '{}')); } catch (x) {}
    el.innerHTML = `<div class="dc">
      <div class="dc-head"><span class="t">💬 ${e(opts.label)}</span>
        <button class="btn btn-tiny btn-ghost" data-a="reset" title="Bắt đầu cuộc chat mới cho node này (cuộc cũ vẫn lưu trong work/_devchat)">Chat mới</button></div>
      <div class="dc-msgs"></div>
      <div class="dc-restart" hidden><span style="flex:1">Code Python/template đã đổi: khởi động lại app để áp dụng.</span>
        <button class="btn btn-tiny" data-a="restart">⟳ Khởi động lại</button></div>
      <div class="dc-in">
        <textarea placeholder="Nhắn Claude để sửa bước này hoặc thêm tính năng… (Ctrl+Enter để gửi)"></textarea>
        <div class="dc-row">
          <select data-k="model" title="Model Claude">${['opus', 'fable', 'sonnet', 'haiku', ''].map(m => `<option value="${m}" ${m === pref.model ? 'selected' : ''}>${m || 'mặc định'}</option>`).join('')}</select>
          <select data-k="effort" title="Effort">${['low', 'medium', 'high', 'xhigh', 'max', ''].map(m => `<option value="${m}" ${m === pref.effort ? 'selected' : ''}>${m || 'effort mặc định'}</option>`).join('')}</select>
          <span class="sp"></span>
          <button class="btn btn-tiny btn-ghost" data-a="restart" title="Khởi động lại app để áp dụng thay đổi code">⟳ App</button>
          <button class="btn btn-tiny btn-ghost" data-a="stop" hidden>■ Dừng</button>
          <button class="btn btn-small btn-primary" data-a="send">Gửi</button>
        </div>
      </div></div>`;
    const msgs = el.querySelector('.dc-msgs'), ta = el.querySelector('textarea'), bar = el.querySelector('.dc-restart');
    const btn = a => el.querySelectorAll(`[data-a="${a}"]`);
    let S = null, timer = null, dead = false, lastSig = '';

    function render() {
      if (!S) return;
      const atBottom = msgs.scrollHeight - msgs.scrollTop - msgs.clientHeight < 60;
      let h = '';
      if (!S.messages.length && !S.busy) h = `<div class="dc-empty">Nhắn cho Claude những gì bạn muốn đổi ở <b>${e(opts.label)}</b>, ví dụ:<br>
        • “thêm tuỳ chọn … vào bước này”<br>• “khi bước này lỗi thì tự thử lại 2 lần”<br>• “thêm một node mới sau bước này để …”<br>
        Claude đọc code của bước, sửa trực tiếp và báo lại file đã đổi.</div>`;
      for (const m of S.messages) {
        if (m.role === 'user') { h += `<div class="dc-m user">${e(m.text)}</div>`; continue; }
        const meta = [m.models && m.models.length ? m.models.join(', ') : '', m.duration_sec ? fmtDur(m.duration_sec) : '',
          m.cost_usd != null ? '$' + Number(m.cost_usd).toFixed(2) : '', m.restart ? '⟳ cần khởi động lại' : ''].filter(Boolean);
        h += `<div class="dc-m bot ${m.ok === false ? 'fail' : ''}">${stripFlag(m.html || e(m.text))}
          ${m.files && m.files.length ? `<div class="dc-files">Đã sửa: ${m.files.map(f => `<code>${e(f)}</code>`).join(' ')}</div>` : ''}
          ${meta.length ? `<div class="dc-meta">${meta.map(x => `<span>${e(x)}</span>`).join('')}</div>` : ''}</div>`;
      }
      if (S.busy && S.live) {
        const act = (S.live.activity || []).slice(-8).map(a => `<div>› ${e(a)}</div>`).join('');
        h += `<div class="dc-m bot dc-live">${S.live.text ? stripFlag(S.live.html) : '<span class="muted">Claude đang đọc code</span>'}<span class="dc-dots"></span>
          ${act ? `<div class="dc-act">${act}</div>` : ''}
          ${S.live.files && S.live.files.length ? `<div class="dc-files">Đang sửa: ${S.live.files.map(f => `<code>${e(f.split(/[\\/]/).slice(-2).join('/'))}</code>`).join(' ')}</div>` : ''}
          <div class="dc-meta"><span>${fmtDur(S.live.elapsed)}</span></div></div>`;
      }
      const sig = h.length + ':' + S.messages.length + ':' + (S.live ? S.live.text.length + S.live.activity.length : 0);
      if (sig !== lastSig) { msgs.innerHTML = h; lastSig = sig; if (atBottom || S.busy) msgs.scrollTop = msgs.scrollHeight; }
      btn('stop').forEach(b => b.hidden = !S.busy);
      btn('send').forEach(b => { b.disabled = S.busy; b.textContent = S.busy ? 'Đang chạy…' : 'Gửi'; });
      const lastBot = [...S.messages].reverse().find(m => m.role === 'assistant');
      let restartedAt = 0; try { restartedAt = Number(localStorage.getItem('dc-restarted') || 0); } catch (x) {}
      bar.hidden = !(lastBot && lastBot.restart && !S.busy && Date.parse(lastBot.at) > restartedAt);
    }

    async function load() {
      if (dead) return;
      try { S = await (await fetch(base)).json(); render(); } catch (x) {}
      clearTimeout(timer); timer = setTimeout(load, S && S.busy ? 1200 : 6000);
    }

    async function send() {
      const text = ta.value.trim(); if (!text) return;
      const model = el.querySelector('[data-k="model"]').value, effort = el.querySelector('[data-k="effort"]').value;
      try { localStorage.setItem(LS, JSON.stringify({ model, effort })); } catch (x) {}
      const r = await post(base, { text, model, effort });
      if (r.error) return note(r.error);
      ta.value = ''; load();
    }

    async function restart() {
      if (!confirm('Khởi động lại app để áp dụng thay đổi code? Trang sẽ tự tải lại sau vài giây.')) return;
      const r = await post('/api/app/restart', {});
      if (r.error) return note(r.error);
      note(r.message || 'Đang khởi động lại');
      try { localStorage.setItem('dc-restarted', String(Date.now())); } catch (x) {}
      const t0 = Date.now(); let wentDown = false;
      const tick = async () => {
        try { await fetch(location.pathname, { cache: 'no-store' }); if (wentDown || Date.now() - t0 > 6000) return location.reload(); }
        catch (x) { wentDown = true; }
        if (Date.now() - t0 < 90000) setTimeout(tick, 1000); else note('App chưa lên lại sau 90 giây: mở lại từ Tool Manager');
      };
      setTimeout(tick, 1500);
    }

    el.addEventListener('click', async ev => {
      const a = ev.target.closest('[data-a]'); if (!a) return;
      const k = a.dataset.a;
      if (k === 'send') send();
      else if (k === 'stop') { const r = await post(base + '/stop'); note(r.error || r.message); load(); }
      else if (k === 'reset') { if (!confirm('Bắt đầu cuộc chat mới cho node này? Claude sẽ quên cuộc trò chuyện hiện tại.')) return;
        const r = await post(base + '/reset'); if (r.error) note(r.error); lastSig = ''; load(); }
      else if (k === 'restart') restart();
    });
    ta.addEventListener('keydown', ev => { if (ev.key === 'Enter' && (ev.ctrlKey || ev.metaKey)) { ev.preventDefault(); send(); } });
    load();
    return { destroy() { dead = true; clearTimeout(timer); }, focus() { ta.focus(); } };
  }
  window.DevChatUI = { mount };
})();
