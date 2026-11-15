// 🔔 Notification bell (same file in Hổ Báo Studio and Creater Vid).
// Reads this app's /api/notifications and the other app's (5004 ⇄ 5010) so one bell shows both tools.
// <div id="notif-bell" data-app="Hổ Báo Studio" data-peers='[{"name":"Creater Vid","port":5010}]'></div>
(function notifBell() {
  const root = document.getElementById('notif-bell');
  if (!root) return;
  const POLL_MS = 5000;
  const SOUND_KEY = 'notif.sound', DESK_KEY = 'notif.desktop';
  const ICON = { done: '✅', review: '🟡', error: '⛔', info: '🔔' };
  const LABEL = { done: 'Xong', review: 'Cần duyệt', error: 'Lỗi', info: 'Thông báo' };
  const lsGet = (k, d) => { try { const v = localStorage.getItem(k); return v == null ? d : v; } catch (e) { return d; } };
  const lsSet = (k, v) => { try { localStorage.setItem(k, v); } catch (e) {} };
  const e = s => String(s == null ? '' : s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

  let peers = [];
  try { peers = JSON.parse(root.dataset.peers || '[]'); } catch (err) {}
  const sources = [{ name: root.dataset.app || '', base: '', self: true }].concat(
    peers.map(p => ({ name: p.name, base: `${location.protocol}//${location.hostname}:${p.port}`, self: false })));
  sources.forEach(s => { s.items = []; s.unread = 0; s.lastId = null; s.alive = false; });

  root.innerHTML = `
    <button type="button" class="nb-btn" title="Thông báo" aria-label="Thông báo">
      <svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor" aria-hidden="true"><path d="M12 22a2.5 2.5 0 0 0 2.45-2h-4.9A2.5 2.5 0 0 0 12 22Zm7-6V11a7 7 0 0 0-5.5-6.84V3.5a1.5 1.5 0 0 0-3 0v.66A7 7 0 0 0 5 11v5l-1.7 1.7A1 1 0 0 0 4 19.4h16a1 1 0 0 0 .7-1.7L19 16Z"/></svg>
      <span class="nb-badge" hidden></span>
    </button>
    <div class="nb-panel" hidden>
      <div class="nb-head">
        <b>Thông báo</b>
        <span class="nb-tools">
          <button type="button" class="nb-link" data-act="readall">Đánh dấu đã đọc hết</button>
        </span>
      </div>
      <div class="nb-tabs">
        <button type="button" class="nb-tab on" data-f="all">Tất cả</button>
        <button type="button" class="nb-tab" data-f="unread">Chưa đọc</button>
        <button type="button" class="nb-tab" data-f="review">Cần duyệt</button>
        <button type="button" class="nb-tab" data-f="error">Lỗi</button>
      </div>
      <div class="nb-list"></div>
      <div class="nb-foot">
        <label><input type="checkbox" data-opt="sound"> Âm báo</label>
        <label><input type="checkbox" data-opt="desktop"> Thông báo Windows</label>
        <button type="button" class="nb-link" data-act="clear">Xoá tin đã đọc</button>
      </div>
    </div>
    <div class="nb-toasts"></div>`;
  const btn = root.querySelector('.nb-btn'), badge = root.querySelector('.nb-badge');
  const panel = root.querySelector('.nb-panel'), list = root.querySelector('.nb-list');
  const toasts = root.querySelector('.nb-toasts');
  document.body.appendChild(toasts);             // toasts sit in the page corner, outside the header
  let filter = 'all';
  const baseTitle = document.title;

  // ------------------------------------------------------------ data
  async function call(src, path, body) {
    const opt = body === undefined ? {} : { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) };
    const r = await fetch(src.base + path, opt);
    if (!r.ok) throw new Error('HTTP ' + r.status);
    return r.json();
  }
  async function poll(src) {
    try {
      const first = src.lastId === null;
      const d = await call(src, `/api/notifications?after=${first ? 0 : src.lastId}&limit=60`);
      src.alive = true;
      src.unread = d.unread || 0;
      const fresh = (d.items || []).map(it => Object.assign(it, { src }));
      if (first) src.items = fresh;
      else if (fresh.length) {
        const ids = new Set(fresh.map(x => x.id));
        src.items = fresh.concat(src.items.filter(x => !ids.has(x.id))).slice(0, 120);
        fresh.slice().reverse().forEach(announce);
      }
      if (d.last_id < (src.lastId || 0)) src.items = fresh;   // the table was cleared
      src.lastId = d.last_id || 0;
    } catch (err) { src.alive = false; }
  }
  async function refreshRead(src) {                 // read state may change in the other window / app
    if (!src.alive) return;
    try {
      const d = await call(src, '/api/notifications?after=0&limit=120');
      src.unread = d.unread || 0;
      src.items = (d.items || []).map(it => Object.assign(it, { src }));
      src.lastId = Math.max(src.lastId || 0, d.last_id || 0);
    } catch (err) {}
  }
  let tick = 0;
  async function loop() {
    tick++;
    await Promise.all(sources.map(s => (tick % 6 === 0 ? refreshRead(s) : poll(s))));
    render();
    setTimeout(loop, document.hidden ? POLL_MS * 2 : POLL_MS);
  }

  // ------------------------------------------------------------ view
  function ago(ts) {
    const s = Math.max(0, Date.now() / 1000 - ts);
    if (s < 60) return 'vừa xong';
    if (s < 3600) return Math.floor(s / 60) + ' phút trước';
    if (s < 86400) return Math.floor(s / 3600) + ' giờ trước';
    if (s < 7 * 86400) return Math.floor(s / 86400) + ' ngày trước';
    return new Date(ts * 1000).toLocaleDateString('vi-VN');
  }
  function href(it) {
    if (!it.link) return '';
    return /^https?:/.test(it.link) ? it.link : it.src.base + it.link;
  }
  function all() {
    return sources.flatMap(s => s.items).sort((a, b) => b.ts - a.ts);
  }
  function render() {
    const unread = sources.reduce((n, s) => n + (s.unread || 0), 0);
    badge.hidden = !unread;
    badge.textContent = unread > 99 ? '99+' : unread;
    btn.classList.toggle('has', unread > 0);
    document.title = (unread ? `(${unread}) ` : '') + baseTitle;
    if (panel.hidden) return;
    let items = all();
    if (filter === 'unread') items = items.filter(x => !x.read_at);
    else if (filter === 'review' || filter === 'error') items = items.filter(x => x.kind === filter);
    const offline = sources.filter(s => !s.self && !s.alive).map(s => s.name);
    list.innerHTML = (items.length ? items.map(it => `
      <a class="nb-item ${it.read_at ? '' : 'unread'} k-${e(it.kind)}" data-src="${sources.indexOf(it.src)}" data-id="${it.id}" ${href(it) ? `href="${e(href(it))}"` : ''}>
        <span class="nb-ic">${ICON[it.kind] || '🔔'}</span>
        <span class="nb-tx">
          <span class="nb-title">${e(it.title)}</span>
          ${it.body ? `<span class="nb-body">${e(it.body)}</span>` : ''}
          <span class="nb-meta"><span class="nb-kind">${LABEL[it.kind] || ''}</span> · ${ago(it.ts)}${sources.length > 1 ? ` · <span class="nb-app">${e(it.src.name)}</span>` : ''}</span>
        </span>
        ${it.read_at ? '' : '<span class="nb-dot"></span>'}
      </a>`).join('') : `<div class="nb-empty">${filter === 'all' ? 'Chưa có thông báo nào' : 'Không có thông báo ở mục này'}</div>`)
      + (offline.length ? `<div class="nb-off">${e(offline.join(', '))} chưa đọc được thông báo (tool đang tắt hoặc chưa khởi động lại bản mới)</div>` : '');
  }

  // ------------------------------------------------------------ new notification: toast + sound + desktop
  function announce(it) {
    if (it.read_at) return;
    const t = document.createElement('a');
    t.className = `nb-toast k-${it.kind}`;
    if (href(it)) t.href = href(it);
    t.innerHTML = `<span class="nb-ic">${ICON[it.kind] || '🔔'}</span><span class="nb-tx"><span class="nb-title">${e(it.title)}</span>`
      + `${it.body ? `<span class="nb-body">${e(it.body)}</span>` : ''}<span class="nb-meta">${e(it.src.name)} · vừa xong</span></span>`
      + `<button type="button" class="nb-x" aria-label="Đóng">×</button>`;
    t.addEventListener('click', ev => {
      if (ev.target.closest('.nb-x')) { ev.preventDefault(); t.remove(); return; }
      markRead(it);
    });
    toasts.prepend(t);
    while (toasts.children.length > 4) toasts.lastChild.remove();
    requestAnimationFrame(() => t.classList.add('show'));
    setTimeout(() => { t.classList.remove('show'); setTimeout(() => t.remove(), 300); }, it.kind === 'review' || it.kind === 'error' ? 15000 : 8000);
    if (lsGet(SOUND_KEY, '1') === '1') chime(it.kind);
    if (lsGet(DESK_KEY, '0') === '1' && document.hidden && 'Notification' in window && Notification.permission === 'granted') {
      try {
        const n = new Notification(`${ICON[it.kind] || ''} ${it.title}`, { body: [it.body, it.src.name].filter(Boolean).join('\n'), tag: `${it.src.name}-${it.id}` });
        n.onclick = () => { window.focus(); if (href(it)) location.href = href(it); markRead(it); n.close(); };
      } catch (err) {}
    }
  }
  let audio;
  function chime(kind) {
    try {
      audio = audio || new (window.AudioContext || window.webkitAudioContext)();
      const notes = kind === 'error' ? [440, 330] : kind === 'review' ? [660, 880] : [880, 1175];
      notes.forEach((f, i) => {
        const o = audio.createOscillator(), g = audio.createGain(), t0 = audio.currentTime + i * 0.12;
        o.type = 'sine'; o.frequency.value = f;
        g.gain.setValueAtTime(0.0001, t0); g.gain.exponentialRampToValueAtTime(0.12, t0 + 0.02);
        g.gain.exponentialRampToValueAtTime(0.0001, t0 + 0.25);
        o.connect(g).connect(audio.destination); o.start(t0); o.stop(t0 + 0.3);
      });
    } catch (err) {}
  }

  // ------------------------------------------------------------ actions
  async function markRead(it) {
    if (it.read_at) return;
    it.read_at = Date.now() / 1000;
    it.src.unread = Math.max(0, it.src.unread - 1);
    render();
    try { await call(it.src, '/api/notifications/read', { ids: [it.id] }); } catch (err) {}
  }
  btn.addEventListener('click', ev => {
    ev.stopPropagation();
    panel.hidden = !panel.hidden;
    if (!panel.hidden) { sources.forEach(refreshRead); render(); }
  });
  document.addEventListener('click', ev => { if (!panel.hidden && !root.contains(ev.target)) panel.hidden = true; });
  document.addEventListener('keydown', ev => { if (ev.key === 'Escape') panel.hidden = true; });
  panel.addEventListener('click', async ev => {
    const tab = ev.target.closest('.nb-tab');
    if (tab) { filter = tab.dataset.f; panel.querySelectorAll('.nb-tab').forEach(b => b.classList.toggle('on', b === tab)); render(); return; }
    const act = ev.target.closest('[data-act]');
    if (act && act.dataset.act === 'readall') {
      await Promise.all(sources.filter(s => s.alive).map(s => call(s, '/api/notifications/read', { all: true }).catch(() => {})));
      sources.forEach(s => { s.unread = 0; s.items.forEach(x => { x.read_at = x.read_at || Date.now() / 1000; }); });
      render(); return;
    }
    if (act && act.dataset.act === 'clear') {
      await Promise.all(sources.filter(s => s.alive).map(s => call(s, '/api/notifications/clear', {}).catch(() => {})));
      sources.forEach(s => { s.items = s.items.filter(x => !x.read_at); });
      render(); return;
    }
    const item = ev.target.closest('.nb-item');
    if (item) {
      const src = sources[+item.dataset.src], it = src && src.items.find(x => x.id === +item.dataset.id);
      if (it) markRead(it);
      if (!item.getAttribute('href')) ev.preventDefault();
    }
  });
  const sound = panel.querySelector('[data-opt=sound]'), desk = panel.querySelector('[data-opt=desktop]');
  sound.checked = lsGet(SOUND_KEY, '1') === '1';
  desk.checked = lsGet(DESK_KEY, '0') === '1' && 'Notification' in window && Notification.permission === 'granted';
  sound.addEventListener('change', () => { lsSet(SOUND_KEY, sound.checked ? '1' : '0'); if (sound.checked) chime('done'); });
  desk.addEventListener('change', async () => {
    if (!desk.checked) { lsSet(DESK_KEY, '0'); return; }
    if (!('Notification' in window)) { desk.checked = false; return; }
    const p = Notification.permission === 'default' ? await Notification.requestPermission() : Notification.permission;
    desk.checked = p === 'granted';
    lsSet(DESK_KEY, desk.checked ? '1' : '0');
  });
  setInterval(() => { if (!panel.hidden) render(); }, 30000);   // keep "x phút trước" current
  loop();
})();
