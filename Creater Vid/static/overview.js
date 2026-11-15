// Film overview: draws creater/overview.py's data. Everything clickable opens the drawer and lights up where the
// item sits in the film (timeline + storyboard); scenes seek the rendered video when there is one.
(function () {
  const D = JSON.parse(document.getElementById('ov-data').textContent);
  const PID = window.OV_PID;
  const $ = (id) => document.getElementById(id);
  const F = (rel) => rel ? `/p/${PID}/file?path=${encodeURIComponent(rel)}` : '';
  const isVid = (rel) => /\.(mp4|webm|mov)$/i.test(rel || '');
  const mmss = (s) => { s = Math.round(s || 0); return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`; };
  const TOTAL = D.total_sec || D.beats.reduce((a, b) => Math.max(a, b.start + b.dur), 0) || 1;
  const pct = (t) => `${(100 * t / TOTAL).toFixed(3)}%`;

  const ACT_COLORS = ['#7c3aed', '#2563eb', '#0891b2', '#059669', '#ca8a04', '#ea580c', '#dc2626', '#db2777', '#9333ea', '#4f46e5'];
  const actColor = {};
  D.acts.forEach((a, i) => { actColor[a.id] = ACT_COLORS[i % ACT_COLORS.length]; });
  const BEAT_COLORS = {cold_open: '#ef4444', quote: '#f59e0b', title: '#a78bfa', narration: '#64748b', archival: '#a16207', reconstruction: '#14b8a6', outro: '#52525b'};
  const KIND_ICON = {doc: '📄', photos: '🖼', quote: '🎙', layers: '🎨', years: '📅', board: '🧵', map: '🗺', archive: '🎞', logo: '⭐', scene: '🎬', fullframe: '🎨', stacked: '🎨'};
  const KIND_VI = {doc: 'tài liệu', photos: 'ảnh thật', quote: 'trích clip', layers: 'tái hiện', years: 'mốc năm', board: 'bảng điều tra', map: 'bản đồ', archive: 'tư liệu cũ', logo: 'biểu tượng', scene: 'cảnh'};
  const ROLE_VI = {narrator: 'người dẫn', main: 'chính', supporting: 'phụ', crowd: 'đám đông'};
  const ST_VI = {verified: '✅ đã kiểm chứng', disputed: '⚠️ tranh cãi', unverified: '❓ chưa kiểm chứng'};
  const STEP_VI = {script: 'Kịch bản', cast: 'Nhân vật', scenes: 'Phân cảnh', images: 'Hình ảnh', footage: 'Tư liệu & giọng', render: 'Dựng', metadata: 'Đăng'};

  const by = (list) => Object.fromEntries(list.map((x) => [x.id, x]));
  const IDX = {act: by(D.acts), beat: by(D.beats), scene: by(D.scenes), char: by(D.characters), loc: by(D.locations),
    ev: by(D.evidence), src: by(D.sources), claim: by(D.claims)};
  // which step a fix to this kind of item belongs to (the chat runs on that step)
  const STEP_OF = {act: 'script', beat: 'script', claim: 'script', src: 'script', char: 'cast', loc: 'scenes', scene: 'scenes', ev: 'scenes'};

  // ------------------------------------------------------------------ hero
  function hero() {
    const h = $('ov-hero');
    const cc = D.claim_count || {};
    const short = D.target_sec && D.total_sec < D.target_sec;
    h.classList.toggle('novideo', !D.video);
    h.innerHTML = `${D.video ? `<video id="ov-video" src="${F(D.video)}" controls preload="metadata"></video>` : ''}
      <div class="ov-hero-text">
        <h1>${esc(D.title)}</h1>
        ${D.logline ? `<div class="ov-logline">${esc(D.logline)}</div>` : ''}
        ${D.thesis ? `<div class="ov-thesis"><b>Luận đề</b>${esc(D.thesis)}</div>` : ''}
        <div class="ov-stats">
          <div class="ov-stat ${short ? 'warn' : ''}"><b>${mmss(D.total_sec)}</b>${D.cut ? 'thời lượng cắt' : 'ước tính'}${D.target_sec ? ` · mục tiêu ${mmss(D.target_sec)}` : ''}</div>
          <div class="ov-stat"><b>${D.acts.length} · ${D.beats.length} · ${D.scenes.length}</b>hồi · beat · cảnh</div>
          <div class="ov-stat"><b>${D.characters.length} · ${D.locations.length} · ${D.evidence.length}</b>nhân vật · bối cảnh · bằng chứng</div>
          <div class="ov-stat"><b>✅${cc.verified || 0} ⚠️${cc.disputed || 0} ❓${cc.unverified || 0}</b>khẳng định</div>
          ${D.frame ? `<div class="ov-stat"><b>${esc(D.frame)}</b>khung kể</div>` : ''}
          ${D.pipeline ? `<div class="ov-stat"><b>${esc(D.pipeline)}</b>cách dựng</div>` : ''}
          ${D.voice ? `<div class="ov-stat"><b>${esc(D.voice.name || '')}</b>giọng${D.voice.usd ? ` · $${D.voice.usd}` : ''}</div>` : ''}
          ${D.budget ? `<div class="ov-stat"><b>$${D.budget.est ?? '?'} / $${D.budget.limit ?? '?'}</b>chi phí dự tính</div>` : ''}
        </div>
        <div class="ov-steps">${Object.entries(D.steps || {}).map(([k, v]) => `<span class="${esc(v)}" title="${esc(v)}">${esc(STEP_VI[k] || k)}</span>`).join('')}</div>
      </div>`;
    const v = $('ov-video');
    if (v) v.addEventListener('timeupdate', () => {
      const ph = $('ov-playhead');
      if (ph) { ph.style.display = 'block'; ph.style.left = pct(v.currentTime); }
    });
  }

  // ------------------------------------------------------------------ timeline
  function timeline() {
    const tl = $('ov-timeline');
    const seg = (type, x, extra, inner, style) =>
      `<div class="ov-seg" data-ref="${type}:${esc(x.id)}" style="left:${pct(x.start)};width:${pct(Math.max(x.dur, TOTAL / 900))};${style || ''}" title="${esc(extra)}">${inner || ''}</div>`;
    let html = `<div class="ov-lane acts"><span class="ov-lane-label">Hồi</span>${D.acts.map((a) =>
      seg('act', a, `${a.id} · ${a.title} · ${mmss(a.dur)}`, `${esc(a.title)}<small>${mmss(a.start)} · ${mmss(a.dur)}</small>`, `background:${actColor[a.id]}`)).join('')}</div>`;
    html += `<div class="ov-lane beats"><span class="ov-lane-label">Beat</span>${D.beats.map((b) =>
      seg('beat', b, `${b.id} · ${b.type}${b.role ? ' / ' + b.role : ''} · ${(b.narration || (b.quote && b.quote.text) || '').slice(0, 120)}`, '',
        `background:${BEAT_COLORS[b.type] || '#64748b'}`)).join('')}</div>`;
    if (D.scenes.length) html += `<div class="ov-lane scenes"><span class="ov-lane-label">Cảnh</span>${D.scenes.map((s) =>
      seg('scene', s, `${s.id} · ${KIND_VI[s.kind] || s.kind} · ${s.title}`, '',
        s.thumb && !isVid(s.thumb) ? `background-image:url('${F(s.thumb)}')` : '')).join('')}</div>`;
    const step = TOTAL > 900 ? 120 : TOTAL > 300 ? 60 : 30;
    let ticks = '';
    for (let t = 0; t <= TOTAL; t += step) ticks += `<span style="left:${pct(t)}">${mmss(t)}</span>`;
    html += `<div class="ov-ruler">${ticks}</div><div class="ov-playhead" id="ov-playhead"></div>`;
    tl.innerHTML = html;
    const used = [...new Set(D.beats.map((b) => b.type))];
    $('ov-tl-legend').innerHTML = used.map((t) => `<span style="color:${BEAT_COLORS[t] || '#64748b'}">■</span> ${esc(t)}`).join(' &nbsp; ');
  }

  function acts() {
    $('ov-acts').innerHTML = D.acts.map((a) => {
      const sc = a.scenes.map((id) => IDX.scene[id]).filter((s) => s && s.thumb && !isVid(s.thumb)).slice(0, 4);
      return `<div class="ov-act" data-ref="act:${esc(a.id)}" style="--c:${actColor[a.id]}">
        <h3><em>${esc(a.id)}</em>${esc(a.title)}</h3>
        <p>${esc(a.summary)}</p>
        ${sc.length ? `<div class="ov-thumbs">${sc.map((s) => `<img loading="lazy" src="${F(s.thumb)}">`).join('')}</div>` : ''}
        <div class="meta">${mmss(a.start)} → ${mmss(a.start + a.dur)} · ${mmss(a.dur)} · ${a.beats.length} beat · ${a.scenes.length} cảnh</div>
      </div>`;
    }).join('') || '<div class="small muted">Kịch bản chưa chia hồi.</div>';
  }

  // ------------------------------------------------------------------ assets
  const presence = (sceneIds, beatIds) => {
    const spans = sceneIds && sceneIds.length ? sceneIds.map((i) => IDX.scene[i]).filter(Boolean)
      : (beatIds || []).map((i) => IDX.beat[i]).filter(Boolean);
    return `<div class="ov-presence" title="Chỗ xuất hiện trong phim">${spans.map((s) => `<i style="left:${pct(s.start)};width:${pct(s.dur)}"></i>`).join('')}</div>`;
  };
  const bg = (rel) => rel && !isVid(rel) ? `style="background-image:url('${F(rel)}')"` : '';
  let assetTab = 'char';
  function assets() {
    const tabs = [['char', `🎭 Nhân vật (${D.characters.length})`], ['loc', `🏛 Bối cảnh (${D.locations.length})`], ['ev', `📎 Bằng chứng (${D.evidence.length})`],
      ['src', `📚 Nguồn (${D.sources.length})`]];
    $('ov-asset-tabs').innerHTML = tabs.map(([k, l]) => `<button class="btn btn-small btn-ghost ov-tab ${k === assetTab ? 'on' : ''}" data-tab="${k}">${l}</button>`).join('');
    const el = $('ov-assets');
    if (assetTab === 'char') {
      const groups = {};
      D.characters.forEach((c) => { (groups[c.role || 'khác'] = groups[c.role || 'khác'] || []).push(c); });
      el.innerHTML = Object.entries(groups).map(([role, list]) => `<div class="ov-group-title">${esc(ROLE_VI[role] || role)} · ${list.length}</div>
        <div class="ov-grid" style="margin-bottom:10px">${list.map((c) => `<div class="ov-item char" data-ref="char:${esc(c.id)}">
          <div class="img" ${bg(c.thumb)}>${c.thumb ? '' : (c.role === 'narrator' ? '🎙' : '👤')}${c.depiction && c.depiction !== 'none' ? `<span class="ov-badge">${esc(c.depiction)}</span>` : ''}</div>
          <div class="txt"><div class="name">${esc(c.name)}</div><div class="sub">${c.beats.length} beat · ${c.scenes.length} cảnh</div>
          ${presence(c.scenes.length ? c.scenes : null, c.beats)}</div></div>`).join('')}</div>`).join('') || '<div class="small muted">Chưa có nhân vật (bước 2).</div>';
    } else if (assetTab === 'loc') {
      el.innerHTML = D.locations.length ? `<div class="ov-grid wide">${D.locations.map((l) => `<div class="ov-item" data-ref="loc:${esc(l.id)}">
        <div class="img" ${bg(l.thumb)}>${l.thumb ? '' : '🏛'}</div>
        <div class="txt"><div class="name">${esc(l.name)}</div><div class="sub">${esc(l.era)}</div><div class="sub">${l.scenes.length} cảnh</div>${presence(l.scenes)}</div></div>`).join('')}</div>`
        : '<div class="small muted">Chưa có bối cảnh dựng (bước 3). Phim dùng chủ yếu ảnh và tài liệu thật, xem tab Bằng chứng.</div>';
    } else if (assetTab === 'ev') {
      const groups = {};
      D.evidence.forEach((e) => { (groups[e.type || 'khác'] = groups[e.type || 'khác'] || []).push(e); });
      el.innerHTML = Object.entries(groups).map(([t, list]) => `<div class="ov-group-title">${esc(t)} · ${list.length}</div>
        <div class="ov-grid" style="margin-bottom:10px">${list.map((e) => `<div class="ov-item" data-ref="ev:${esc(e.id)}">
          <div class="img" ${bg(e.thumb)}>${e.thumb ? '' : '📎'}<span class="ov-badge">${esc(e.id)}</span>${D.cut && !e.scenes.length ? '<span class="ov-badge r" style="background:#b91c1c">chưa dùng</span>' : ''}</div>
          <div class="txt"><div class="sub">${esc(e.what || e.proves)}</div>${presence(e.scenes.length ? e.scenes : null, e.beats)}</div></div>`).join('')}</div>`).join('')
        || '<div class="small muted">Chưa có danh sách bằng chứng.</div>';
    } else {
      el.innerHTML = `<div class="ov-list">${D.sources.map((s) => `<div class="ov-row" data-ref="src:${esc(s.id)}"><span class="t">${esc(s.id)}</span>
        <div class="x"><div style="color:var(--text)">${esc(s.title)}</div>${esc([s.author, s.date, s.type, s.reliability].filter(Boolean).join(' · '))}</div></div>`).join('')}</div>`;
    }
  }

  // ------------------------------------------------------------------ storyboard
  function storyboard() {
    const el = $('ov-scenes');
    $('ov-scene-count').textContent = D.scenes.length ? `${D.scenes.length} cảnh · ${mmss(TOTAL)}` : '';
    if (!D.scenes.length) {
      // before step 3: the beats are the plan of the film
      el.innerHTML = D.acts.map((a) => `<div class="ov-sb-act" style="--c:${actColor[a.id]}"><h3><i></i>${esc(a.id)} · ${esc(a.title)}</h3>
        <div class="ov-sb">${a.beats.map((id) => IDX.beat[id]).map((b) => `<div class="ov-scene" data-ref="beat:${esc(b.id)}">
          <div class="img" style="background:${BEAT_COLORS[b.type] || '#334155'}33">${b.type === 'quote' ? '🎙' : '📝'}<span class="ov-badge">${esc(b.id)}</span><span class="dur">${mmss(b.dur)}</span></div>
          <div class="cap">${esc(b.narration || (b.quote && b.quote.text) || b.visual_idea)}</div></div>`).join('')}</div></div>`).join('')
        + '<div class="small muted">Chưa phân cảnh (bước 3): đang hiện các beat của kịch bản.</div>';
      return;
    }
    const groups = D.acts.map((a) => ({a, list: D.scenes.filter((s) => s.act === a.id)}));
    const orphan = D.scenes.filter((s) => !IDX.act[s.act]);
    if (orphan.length) groups.push({a: {id: '?', title: 'Ngoài hồi'}, list: orphan});
    el.innerHTML = groups.filter((g) => g.list.length).map(({a, list}) => `<div class="ov-sb-act" style="--c:${actColor[a.id] || '#52525b'}">
      <h3><i></i>${esc(a.id)} · ${esc(a.title)} <span class="small muted" style="font-weight:400">${list.length} cảnh</span></h3>
      <div class="ov-sb">${list.map((s) => `<div class="ov-scene" data-ref="scene:${esc(s.id)}">
        <div class="img" ${bg(s.thumb)}>${s.thumb && !isVid(s.thumb) ? '' : (KIND_ICON[s.kind] || '🎬')}
          <span class="ov-badge">${esc(s.id)} · ${KIND_ICON[s.kind] || ''} ${esc(KIND_VI[s.kind] || s.kind)}</span>
          ${s.reconstruction ? '<span class="recon">tái hiện</span>' : ''}<span class="dur">${mmss(s.start)} · ${s.dur.toFixed(1)}s</span></div>
        <div class="cap">${esc(s.narration || s.title)}</div></div>`).join('')}</div></div>`).join('');
  }

  // ------------------------------------------------------------------ checks
  function checks() {
    const li = (cls, text, ref) => `<li class="${cls}" ${ref ? `data-ref="${ref}"` : ''}>${text}</li>`;
    const order = {disputed: 0, unverified: 1, verified: 2};
    const claims = [...D.claims].sort((a, b) => (order[a.status] ?? 1) - (order[b.status] ?? 1));
    const warnRef = (w) => { const m = w.match(/^(b\d+|sc\d+)\b/) || w.match(/Bằng chứng (\S+)/); if (!m) return ''; const id = m[1];
      return IDX.beat[id] ? `beat:${id}` : IDX.scene[id] ? `scene:${id}` : IDX.ev[id] ? `ev:${id}` : ''; };
    $('ov-checks').innerHTML = `
      <div class="ov-check"><h4>Khẳng định (${D.claims.length})</h4><ul>${claims.map((c) => li(c.status, `<b>${esc(c.id)}</b> ${ST_VI[c.status] || c.status}<br>${esc(c.text)}`, `claim:${esc(c.id)}`)).join('') || '<li>Chưa có.</li>'}</ul></div>
      <div class="ov-check"><h4>Cảnh báo tự động (${D.warnings.length})</h4><ul>${D.warnings.map((w) => li('warn', esc(w), warnRef(w))).join('') || '<li class="verified">Không có gì đáng lo.</li>'}</ul></div>
      <div class="ov-check"><h4>Rủi ro &amp; câu hỏi mở</h4><ul>${D.risks.map((r) => li('warn', esc(r))).join('')}${D.open_questions.map((q) => li('', '❔ ' + esc(q))).join('') || ''}</ul></div>`;
  }

  // ------------------------------------------------------------------ highlight + drawer
  function highlight(scenes, beats) {
    const S = new Set(scenes || []);
    const B = new Set(beats || []);
    (scenes || []).forEach((id) => (IDX.scene[id]?.beats || []).forEach((b) => B.add(b)));
    (beats || []).forEach((id) => (IDX.beat[id]?.scenes || []).forEach((s) => S.add(s)));
    const on = S.size || B.size;
    document.querySelectorAll('.ov-seg, .ov-scene').forEach((el) => {
      const [t, id] = (el.dataset.ref || '').split(':');
      el.classList.toggle('hl', !!on && ((t === 'scene' && S.has(id)) || (t === 'beat' && B.has(id))));
    });
    $('ov-timeline').classList.toggle('filtering', !!on);
    $('ov-scenes').classList.toggle('filtering', !!on && D.scenes.length > 0);
    $('ov-clear').hidden = !on;
  }

  const chips = (type, ids, label) => ids && ids.length ? `<div class="ov-chips">${ids.map((id) => {
    const x = IDX[type][id];
    const st = type === 'claim' && x ? ` st-${x.status}` : '';
    return `<span class="ov-chip${st}" data-ref="${type}:${esc(id)}">${esc(label ? label(x, id) : id)}</span>`;
  }).join('')}</div>` : '<span class="small muted">—</span>';
  const field = (name, html) => html ? `<div class="ov-field"><b>${name}</b>${html}</div>` : '';
  const charName = (x, id) => x ? x.name : id;
  const sceneRow = (s) => `<div class="ov-row" data-ref="scene:${esc(s.id)}">${s.thumb && !isVid(s.thumb) ? `<img loading="lazy" src="${F(s.thumb)}">` : ''}
    <span class="t">${esc(s.id)}<br>${mmss(s.start)}</span><div class="x">${KIND_ICON[s.kind] || ''} ${esc(s.narration || s.title)}</div></div>`;
  const beatRow = (b) => `<div class="ov-row" data-ref="beat:${esc(b.id)}"><span class="t">${esc(b.id)}<br>${mmss(b.start)}</span>
    <div class="x"><span style="color:${BEAT_COLORS[b.type] || '#94a3b8'}">${esc(b.type)}${b.role ? ' · ' + esc(b.role) : ''}</span> ${esc(b.narration || (b.quote && ('“' + b.quote.text + '”')) || b.visual_idea)}</div></div>`;
  const seekBtn = (t) => D.video ? `<button class="btn btn-tiny" data-seek="${t}">▶ Xem từ ${mmss(t)}</button>` : '';

  const RENDER = {
    act(a) {
      highlight(a.scenes, a.beats);
      return [`<span style="color:${actColor[a.id]}">■</span> ${esc(a.id)} · ${esc(a.title)}`,
        `${seekBtn(a.start)}${field('Tóm tắt', esc(a.summary))}
        ${field('Thời lượng', `${mmss(a.start)} → ${mmss(a.start + a.dur)} (${mmss(a.dur)})`)}
        ${field(`Beat (${a.beats.length})`, `<div class="ov-list">${a.beats.map((id) => beatRow(IDX.beat[id])).join('')}</div>`)}`];
    },
    beat(b) {
      highlight(b.scenes, [b.id]);
      const sc = b.scenes.map((id) => IDX.scene[id]).filter(Boolean);
      return [`📝 ${esc(b.id)} · ${esc(b.type)}${b.role ? ' · ' + esc(b.role) : ''}`,
        `${seekBtn(b.start)}${field('Hồi', chips('act', [b.act], (x, id) => x ? `${id} · ${x.title}` : id))}
        ${field('Lời dẫn', esc(b.narration))}
        ${b.quote ? field('Trích dẫn', `<div class="quote">“${esc(b.quote.text)}”</div><div class="small muted">— ${esc(b.quote.speaker || '')} ${b.quote.source ? '· ' + esc(b.quote.source) : ''}</div>`) : ''}
        ${field('Chữ trên màn hình', esc(b.on_screen_text))}
        ${field('Ý tưởng hình ảnh', esc(b.visual_idea))}
        ${field('Thời lượng', `${b.dur.toFixed(1)} s${b.est && Math.abs(b.est - b.dur) > 0.5 ? ` (kịch bản dự tính ${b.est} s)` : ''} · ${b.narration.split(/\s+/).filter(Boolean).length} chữ`)}
        ${field('Nhân vật', chips('char', b.characters, charName))}
        ${field('Bằng chứng', chips('ev', b.evidence))}
        ${field('Nguồn', chips('src', b.sources))}
        ${b.claims.length ? field('Khẳng định liên quan', chips('claim', b.claims.map((c) => c.id), (x, id) => `${id} ${x ? ({verified: '✅', disputed: '⚠️', unverified: '❓'}[x.status] || '') : ''}`)) : ''}
        ${sc.length ? field(`Cảnh (${sc.length})`, `<div class="ov-list">${sc.map(sceneRow).join('')}</div>`) : ''}`];
    },
    scene(s) {
      highlight([s.id], s.beats);
      const media = s.thumb ? (isVid(s.thumb) ? `<video class="big" src="${F(s.thumb)}" controls preload="metadata"></video>` : `<img class="big" src="${F(s.thumb)}">`) : '';
      return [`${KIND_ICON[s.kind] || '🎬'} ${esc(s.id)} · ${esc(KIND_VI[s.kind] || s.kind)}`,
        `${media}${seekBtn(s.start)}
        ${field('Tiêu đề', esc(s.title))}
        ${field('Lời dẫn', esc(s.narration))}
        ${s.text_fx.length ? field('Chữ hiệu ứng', s.text_fx.map(esc).join('<br>')) : ''}
        ${field('Thời điểm', `${mmss(s.start)} · ${s.dur.toFixed(1)} s · chuyển cảnh ${esc(s.transition || '—')}${s.camera ? ' · máy ' + esc(s.camera) : ''}${s.grade ? ' · màu ' + esc(s.grade) : ''}`)}
        ${s.reconstruction ? field('Nhãn', `<span style="color:#5eead4">${esc(s.label || 'tái hiện')}</span>`) : ''}
        ${field('Beat', chips('beat', s.beats))}
        ${s.location ? field('Bối cảnh', chips('loc', [s.location], (x, id) => x ? x.name : id)) : ''}
        ${s.characters.length ? field('Nhân vật', chips('char', s.characters, charName)) : ''}
        ${field('Bằng chứng', chips('ev', s.evidence))}`];
    },
    char(c) {
      highlight(c.scenes, c.beats);
      return [`🎭 ${esc(c.name)}`,
        `${c.thumb ? `<img class="big" src="${F(c.thumb)}">` : ''}
        ${field('Vai', esc([ROLE_VI[c.role] || c.role, c.kind, c.depiction].filter(Boolean).join(' · ')))}
        ${field('Mô tả', esc(c.description))}${field('Ngoại hình', esc(c.look))}
        ${field('Xuất hiện', presence(c.scenes.length ? c.scenes : null, c.beats))}
        ${field(`Beat (${c.beats.length})`, `<div class="ov-list">${c.beats.map((id) => IDX.beat[id]).filter(Boolean).map(beatRow).join('')}</div>`)}
        ${c.scenes.length ? field(`Cảnh dựng nhân vật (${c.scenes.length})`, `<div class="ov-list">${c.scenes.map((id) => sceneRow(IDX.scene[id])).join('')}</div>`) : ''}`];
    },
    loc(l) {
      highlight(l.scenes, l.beats);
      return [`🏛 ${esc(l.name)}`,
        `${l.thumb ? `<img class="big" src="${F(l.thumb)}">` : ''}${field('Niên đại', esc(l.era))}${field('Mô tả', esc(l.description))}
        ${field('Xuất hiện', presence(l.scenes))}
        ${field(`Cảnh (${l.scenes.length})`, `<div class="ov-list">${l.scenes.map((id) => sceneRow(IDX.scene[id])).join('')}</div>`)}`];
    },
    ev(e) {
      highlight(e.scenes, e.beats);
      const url = /^https?:/.test(e.url) ? `<a href="${esc(e.url)}" target="_blank" rel="noopener">${esc(e.url)}</a>` : esc(e.url);
      return [`📎 ${esc(e.id)} · ${esc(e.type)}`,
        `${e.thumb ? `<img class="big" src="${F(e.thumb)}">` : ''}
        ${field('Là gì', esc(e.what))}${field('Chứng minh', esc(e.proves))}${field('Nguồn', url)}${field('Giấy phép', esc(e.license))}${field('Ghi chú', esc(e.note))}
        ${field('Xuất hiện', presence(e.scenes.length ? e.scenes : null, e.beats))}
        ${e.scenes.length ? field(`Cảnh (${e.scenes.length})`, `<div class="ov-list">${e.scenes.map((id) => sceneRow(IDX.scene[id])).join('')}</div>`)
          : field('Beat', chips('beat', e.beats))}`];
    },
    src(s) {
      const beats = D.beats.filter((b) => b.sources.includes(s.id));
      highlight(null, beats.map((b) => b.id));
      return [`📚 ${esc(s.id)}`,
        `${field('Tên', esc(s.title))}${field('Tác giả · ngày', esc([s.author, s.date].filter(Boolean).join(' · ')))}
        ${field('Loại · độ tin cậy', esc([s.type, s.reliability].filter(Boolean).join(' · ')))}
        ${s.url ? field('Link', `<a href="${esc(s.url)}" target="_blank" rel="noopener">${esc(s.url)}</a>`) : ''}
        ${field('Khẳng định dựa vào nguồn này', chips('claim', D.claims.filter((c) => c.sources.includes(s.id)).map((c) => c.id)))}
        ${field(`Beat dùng nguồn (${beats.length})`, `<div class="ov-list">${beats.map(beatRow).join('')}</div>`)}`];
    },
    claim(c) {
      const beats = D.beats.filter((b) => b.claims.some((x) => x.id === c.id));
      highlight(null, beats.map((b) => b.id));
      return [`${{verified: '✅', disputed: '⚠️', unverified: '❓'}[c.status] || ''} ${esc(c.id)}`,
        `${field('Khẳng định', esc(c.text))}${field('Trạng thái', ST_VI[c.status] || esc(c.status))}${field('Ghi chú', esc(c.note))}
        ${field('Nguồn', chips('src', c.sources))}
        ${field(`Beat liên quan (${beats.length})`, `<div class="ov-list">${beats.map(beatRow).join('')}</div>`)}`];
    },
  };

  let history = [];
  let current = null;
  function open(ref, push = true) {
    const [type, id] = ref.split(/:(.*)/s);
    const x = IDX[type] && IDX[type][id];
    if (!x || !RENDER[type]) return;
    if (push && current && current !== ref) history.push(current);
    current = ref;
    const [title, body] = RENDER[type](x);
    $('ov-dr-title').innerHTML = title;
    $('ov-dr-body').innerHTML = body;
    $('ov-dr-body').scrollTop = 0;
    $('ov-back').hidden = !history.length;
    const step = STEP_OF[type];
    $('ov-ask-hint').textContent = `Gửi vào chat dự án, chạy ở bước ${STEP_VI[step] || step}. Ghi rõ muốn sửa gì.`;
    $('ov-ask').value = `[${id}] `;
    $('ov-ask').dataset.step = step;
    $('ov-drawer').hidden = false;
    document.body.classList.add('ov-open');
    document.querySelectorAll('.ov-item').forEach((el) => el.classList.toggle('sel', el.dataset.ref === ref));
  }

  window.OV = {
    close() { $('ov-drawer').hidden = true; document.body.classList.remove('ov-open'); current = null; history = []; highlight(); document.querySelectorAll('.ov-item.sel').forEach((el) => el.classList.remove('sel')); },
    back() { const r = history.pop(); if (r) open(r, false); },
    clear() { highlight(); },
    async ask() {
      const ta = $('ov-ask');
      const text = ta.value.trim();
      if (!text || /^\[[^\]]*\]$/.test(text)) { toast('Viết yêu cầu sửa trước đã'); return; }
      const r = await api(`/api/p/${PID}/message`, {text, step: ta.dataset.step});
      if (r && r.error) { toast(r.error); return; }
      toast('Đã gửi Claude. Theo dõi ở trang dự án.');
      ta.value = '';
    },
  };

  document.addEventListener('click', (ev) => {
    const seek = ev.target.closest('[data-seek]');
    if (seek) {
      const v = $('ov-video');
      if (v) { v.currentTime = Number(seek.dataset.seek); v.play(); v.scrollIntoView({behavior: 'smooth', block: 'center'}); }
      return;
    }
    const tab = ev.target.closest('[data-tab]');
    if (tab) { assetTab = tab.dataset.tab; assets(); return; }
    const el = ev.target.closest('[data-ref]');
    if (el && el.dataset.ref) open(el.dataset.ref);
  });
  document.addEventListener('keydown', (ev) => { if (ev.key === 'Escape' && !$('ov-drawer').hidden) OV.close(); });

  hero(); timeline(); acts(); assets(); storyboard(); checks();
})();
