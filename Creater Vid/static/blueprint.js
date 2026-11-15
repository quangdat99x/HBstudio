// Project blueprint: draws creater/blueprint.py's data (intent, spine of acts, assets per act, build plan, decisions).
(function () {
  const D = JSON.parse(document.getElementById('bp-data').textContent);
  const PID = window.OV_PID;
  const $ = (id) => document.getElementById(id);
  const mmss = (s) => { s = Math.round(s || 0); return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`; };
  const ACT_COLORS = ['#7c3aed', '#2563eb', '#0891b2', '#059669', '#ca8a04', '#ea580c', '#dc2626', '#db2777', '#9333ea', '#4f46e5'];
  const actColor = {};
  D.acts.forEach((a, i) => { actColor[a.id] = ACT_COLORS[i % ACT_COLORS.length]; });
  const VIS = {
    clip: ['🎙', 'clip trích', '#f59e0b'], document: ['📄', 'tài liệu thật', '#3b82f6'], real_photo: ['🖼', 'ảnh thật', '#10b981'],
    reconstruction: ['🎨', 'tái hiện AI', '#14b8a6'], map: ['🗺', 'bản đồ', '#84cc16'], board: ['🧵', 'bảng điều tra', '#ef4444'],
    archive: ['🎞', 'tư liệu cũ', '#a16207'], logo: ['⭐', 'biểu tượng', '#e879f9'], years: ['📅', 'mốc năm', '#f97316'],
    footage: ['📹', 'footage', '#06b6d4'], text: ['🔤', 'chữ / tựa', '#71717a'],
  };
  const vis = (k) => VIS[k] || ['▫️', k, '#52525b'];
  const HOW = {real_photo: '📷 ảnh thật', clip: '🎞 clip', ai: '🎨 vẽ AI', voice_only: '🎙 chỉ giọng', map: '🗺 bản đồ'};
  const ROLE_VI = {narrator: 'người dẫn', main: 'chính', supporting: 'phụ', crowd: 'đám đông'};
  const ST_VI = {approved: 'đã duyệt', failed: 'lỗi', locked: 'chưa tới', ready: 'chờ duyệt', running: 'đang chạy', pending: 'chưa chạy'};
  const actBy = Object.fromEntries(D.acts.map((a) => [a.id, a]));
  const charBy = Object.fromEntries(D.characters.map((c) => [c.id, c]));
  const evBy = Object.fromEntries(D.evidence.map((e) => [e.id, e]));
  const TOTAL = D.acts.reduce((s, a) => s + a.sec, 0) || D.est_sec || 1;

  // ------------------------------------------------------------------ banner
  if (D.source === 'derived') {
    $('bp-banner').innerHTML = `<div class="bp-banner"><span>⚙️ Dự án này lập trước khi có <code>blueprint.json</code>: sơ đồ đang được app <b>tự suy từ kịch bản</b>,
      nên thiếu phần ý đồ (câu hỏi từng hồi, ý chuyển hồi, kế hoạch chi phí).</span>
      <button class="btn btn-small btn-primary" onclick="BP.askBlueprint()">Nhờ Claude lập bản thiết kế đầy đủ</button></div>`;
  }

  // ------------------------------------------------------------------ ① intent
  function intent() {
    $('bp-meta').textContent = [D.frame && `khung ${D.frame}`, D.pipeline && `dựng ${D.pipeline}`,
      `~${mmss(D.est_sec)}${D.target_sec ? ` (tối thiểu ${mmss(D.target_sec)})` : ''}`].filter(Boolean).join(' · ');
    $('bp-intent').innerHTML = `
      <h2 style="font-size:19px">${esc(D.title)}</h2>
      ${D.approach ? `<div class="bp-approach">${esc(D.approach)}</div>` : ''}
      <div class="bp-arc">
        <div class="bp-node"><b>🎣 Mở bằng</b>${esc(D.hook)}</div><div class="bp-arrow">→</div>
        <div class="bp-node main"><b>🦴 Xương sống</b>${esc(D.spine)}${D.thesis && D.thesis !== D.spine ? `<div class="small" style="margin-top:6px;color:var(--text-secondary)"><b style="display:inline">Luận đề:</b> ${esc(D.thesis)}</div>` : ''}</div>
        <div class="bp-arrow">→</div>
        <div class="bp-node"><b>🏁 Khép bằng</b>${esc(D.ending)}</div>
      </div>
      ${D.options.length ? `<div class="ov-group-title">Các hướng đã cân nhắc</div><div class="bp-options">${D.options.map((o) => `<div class="bp-opt ${o.chosen ? 'chosen' : ''}">
        <h4>${o.chosen ? '✓ ' : ''}${esc(o.name)}</h4>${esc(o.idea)}${o.why ? `<div class="why">${esc(o.why)}</div>` : ''}</div>`).join('')}</div>` : ''}
      ${D.style ? `<div class="small muted">🎨 Phong cách: ${esc(D.style)}</div>` : ''}`;
  }

  // ------------------------------------------------------------------ ② spine
  const vbar = (list, total) => `<div class="bp-vbar">${list.map((v) => `<i title="${esc(vis(v.kind)[1])} ${Math.round(v.sec)} s" style="width:${100 * v.sec / (total || 1)}%;background:${vis(v.kind)[2]}"></i>`).join('')}</div>`;
  function spine() {
    $('bp-len').textContent = `${D.acts.length} hồi · ${D.acts.reduce((s, a) => s + a.beats.length, 0)} beat · ${mmss(TOTAL)}`;
    $('bp-bar').innerHTML = D.acts.map((a) => `<div data-act="${esc(a.id)}" style="--c:${actColor[a.id]};flex:${a.sec || 1}" title="${esc(a.title)} · ${mmss(a.sec)}">${esc(a.title)}</div>`).join('');
    $('bp-flow').innerHTML = D.acts.map((a, i) => {
      const ppl = a.characters.filter((c) => c !== 'c_narrator').map((c) => charBy[c] ? charBy[c].name : c);
      const node = `<div class="bp-act" data-act="${esc(a.id)}" style="--c:${actColor[a.id]}">
        <h3><em>${esc(a.id)}</em>${esc(a.title)}</h3>
        <div class="sec">${mmss(a.start)} → ${mmss(a.start + a.sec)} · ${mmss(a.sec)} · ${a.beats.length} beat</div>
        ${a.purpose ? `<div class="purpose">${esc(a.purpose)}</div>` : ''}
        ${a.question ? `<div class="q">❓ ${esc(a.question)}</div>` : ''}
        ${a.turn ? `<div class="turn">💡 ${esc(a.turn)}</div>` : ''}
        ${a.roles.length ? `<div class="bp-roles">${a.roles.map((r) => `<span>${esc(r)}</span>`).join('')}</div>` : ''}
        ${vbar(a.visuals, a.sec)}
        <div class="bp-vicons">${a.visuals.map((v) => vis(v.kind)[0]).join(' ')} · ${a.evidence.length} bằng chứng</div>
        ${ppl.length ? `<div class="bp-people">${ppl.slice(0, 6).map((n) => `<span>${esc(n)}</span>`).join('')}${ppl.length > 6 ? `<span>+${ppl.length - 6}</span>` : ''}</div>` : ''}
      </div>`;
      const link = i < D.acts.length - 1 ? `<div class="bp-link"><div class="arr">➜</div>${a.bridge ? `<div class="br">${esc(a.bridge)}</div>` : ''}</div>` : '';
      return node + link;
    }).join('');
  }

  // ------------------------------------------------------------------ ③ assets × acts
  function matrix() {
    const mixTotal = D.mix.reduce((s, v) => s + v.sec, 0) || 1;
    $('bp-mix').innerHTML = `<div class="ov-group-title">Phim sẽ gồm những loại hình nào (theo thời lượng)</div>
      <div class="bp-mixbar">${D.mix.map((v) => `<i style="width:${100 * v.sec / mixTotal}%;background:${vis(v.kind)[2]}">${v.sec / mixTotal > 0.07 ? `${vis(v.kind)[0]} ${Math.round(100 * v.sec / mixTotal)}%` : ''}</i>`).join('')}</div>
      <div class="bp-legend">${D.mix.map((v) => `<span style="--c:${vis(v.kind)[2]}">${vis(v.kind)[0]} ${esc(vis(v.kind)[1])} ${Math.round(100 * v.sec / mixTotal)}% · ${mmss(v.sec)}</span>`).join('')}</div>`;
    const head = `<tr><th></th>${D.acts.map((a) => `<th class="act" style="--c:${actColor[a.id]}" title="${esc(a.title)}">${esc(a.id)}</th>`).join('')}</tr>`;
    const row = (label, ref, has, color) => `<tr><td class="lbl" data-ref="${ref}">${label}</td>${D.acts.map((a) => {
      const n = has(a);
      return `<td class="cell ${n ? 'on' : ''}" style="--c:${color || actColor[a.id]}">${typeof n === 'number' && n > 1 ? n : ''}</td>`;
    }).join('')}</tr>`;
    const grp = (t) => `<tr><td class="grp" colspan="${D.acts.length + 1}">${t}</td></tr>`;
    let rows = '';
    const chars = D.characters.filter((c) => c.acts.length);
    if (chars.length) {
      rows += grp(`🎭 Nhân vật (${chars.length})`);
      rows += chars.map((c) => row(`${esc(c.name)}<span class="bp-how">${esc(HOW[c.how] || c.how || '')}${c.role ? ' · ' + esc(ROLE_VI[c.role] || c.role) : ''}</span>`,
        `char:${c.id}`, (a) => a.characters.includes(c.id))).join('');
    }
    if (D.locations.length) {
      rows += grp(`🏛 Bối cảnh (${D.locations.length})`);
      rows += D.locations.map((l) => row(`${esc(l.name)}<span class="bp-how">${esc(HOW[l.how] || l.how || '')}</span>`, `loc:${l.id}`, (a) => a.locations.includes(l.id))).join('');
    }
    const kinds = [...new Set(D.evidence.map((e) => e.visual || e.type))];
    if (kinds.length) {
      rows += grp(`📎 Bằng chứng thật cần lấy (${D.evidence.length}), số món mỗi hồi`);
      rows += kinds.map((k) => {
        const list = D.evidence.filter((e) => (e.visual || e.type) === k);
        return row(`${vis(k)[0]} ${esc(vis(k)[1])} <span class="bp-how">${list.length}</span>`, `evk:${k}`,
          (a) => list.filter((e) => a.evidence.includes(e.id)).length, vis(k)[2]);
      }).join('');
    }
    $('bp-matrix').innerHTML = rows ? `<table class="bp-matrix">${head}${rows}</table>` : '<div class="small muted">Kịch bản chưa ghi nhân vật hay bằng chứng cho các beat.</div>';
  }

  // ------------------------------------------------------------------ ④ build plan
  function pipe() {
    const b = D.budget || {};
    const parts = [['giọng', b.voice_usd], ['ảnh', b.images_usd], ['âm thanh', b.sfx_usd], ['footage', b.footage_usd]].filter((x) => x[1] != null);
    $('bp-budget').textContent = `Ngân sách: ${parts.map(([k, v]) => `${k} $${v}`).join(' · ') || 'chưa ước tính'}${b.total_usd != null ? ` · tổng $${b.total_usd}` : ''}${b.limit_usd ? ` / trần $${b.limit_usd}` : ''}`;
    $('bp-pipe').innerHTML = D.build.map((s, i) => `${i ? '<div class="bp-link"><div class="arr">➜</div></div>' : ''}<div class="bp-step ${esc(s.status)}">
      <h4>${s.icon} ${s.num} · ${esc(s.name)}</h4>
      ${s.status ? `<span class="st">${esc(ST_VI[s.status] || s.status)}</span>` : ''}
      <div class="will">${esc(s.will)}</div><div class="goal">${esc(s.goal)}</div>
      <div class="nums">${s.count != null ? `<span><b>${s.count}</b> món</span>` : ''}${s.usd != null ? `<span><b>$${s.usd}</b></span>` : ''}</div></div>`).join('');
  }

  // ------------------------------------------------------------------ ⑤ decisions
  function decide() {
    const c = D.claims;
    $('bp-decide').innerHTML = `
      <div class="ov-check"><h4>Câu hỏi mở (${D.open_decisions.length})</h4><ul>${D.open_decisions.map((q) => `<li>❔ ${esc(q)}</li>`).join('') || '<li>Không có.</li>'}</ul></div>
      <div class="ov-check"><h4>Rủi ro (${D.risks.length})</h4><ul>${D.risks.map((r) => `<li class="warn">${esc(r)}</li>`).join('') || '<li>Không có.</li>'}</ul></div>
      <div class="ov-check"><h4>Nền kiểm chứng</h4><ul><li class="verified">✅ ${c.verified} khẳng định đã kiểm chứng</li>
        <li class="disputed">⚠️ ${c.disputed} còn tranh cãi: phim chỉ nói là ý kiến</li><li class="unverified">❓ ${c.unverified} chưa kiểm chứng</li>
        <li>📚 ${D.sources} nguồn</li></ul></div>`;
  }

  // ------------------------------------------------------------------ drawer
  const field = (n, h) => h ? `<div class="ov-field"><b>${n}</b>${h}</div>` : '';
  const chipList = (ids, ref, name) => ids.length ? `<div class="ov-chips">${ids.map((id) => `<span class="ov-chip" data-ref="${ref}:${esc(id)}">${esc(name ? name(id) : id)}</span>`).join('')}</div>` : '';
  const charName = (id) => charBy[id] ? charBy[id].name : id;
  const actRows = (ids) => `<div class="ov-list">${ids.map((id) => actBy[id]).filter(Boolean).map((a) => `<div class="ov-row" data-ref="act:${esc(a.id)}"><span class="t">${esc(a.id)}</span><div class="x">${esc(a.title)}</div></div>`).join('')}</div>`;
  const VIEW = {
    act(a) {
      return [`<span style="color:${actColor[a.id]}">■</span> ${esc(a.id)} · ${esc(a.title)}`, `
        ${field('Vai trò trong mạch', esc(a.purpose))}${field('Câu hỏi hồi mở ra', esc(a.question))}${field('Khi hết hồi, người xem biết thêm', esc(a.turn))}
        ${field('Chuyển sang hồi sau', esc(a.bridge))}${field('Ghi chú', esc(a.notes))}
        ${field('Hình ảnh', vbar(a.visuals, a.sec) + `<div class="small muted" style="margin-top:4px">${a.visuals.map((v) => `${vis(v.kind)[0]} ${esc(vis(v.kind)[1])} ${Math.round(v.sec)} s`).join(' · ')}</div>`)}
        ${field('Nhân vật', chipList(a.characters, 'char', charName))}
        ${field(`Bằng chứng (${a.evidence.length})`, chipList(a.evidence, 'ev'))}
        ${field(`Beat (${a.beats.length})`, `<div class="ov-list">${a.beats.map((b) => `<div class="ov-row"><span class="t">${esc(b.id)}<br>${b.sec}s</span>
          <div class="x">${b.visuals.map((v) => vis(v)[0]).join('')} <span style="color:#c4b5fd">${esc(b.type)}${b.role ? ' · ' + esc(b.role) : ''}</span> ${esc(b.text)}</div></div>`).join('')}</div>`)}`, a.id];
    },
    char(c) {
      return [`🎭 ${esc(c.name)}`, `${field('Thể hiện bằng', esc(HOW[c.how] || c.how || 'chưa rõ'))}${field('Vai', esc(ROLE_VI[c.role] || c.role))}
        ${field('Số beat', String(c.beats))}${field('Có mặt ở hồi', actRows(c.acts))}`, c.id];
    },
    loc(l) { return [`🏛 ${esc(l.name)}`, `${field('Thể hiện bằng', esc(HOW[l.how] || l.how))}${field('Có mặt ở hồi', actRows(l.acts))}`, l.id]; },
    ev(e) {
      const url = /^https?:/.test(e.source) ? `<a href="${esc(e.source)}" target="_blank" rel="noopener">${esc(e.source)}</a>` : esc(e.source);
      return [`📎 ${esc(e.id)} · ${esc(vis(e.visual)[1] || e.type)}`, `${field('Là gì', esc(e.what))}${field('Chứng minh', esc(e.proves))}${field('Nguồn', url)}
        ${field('Giấy phép', esc(e.license))}${field('Dùng ở hồi', actRows(e.acts))}`, e.id];
    },
    evk(k) {
      const list = D.evidence.filter((e) => (e.visual || e.type) === k);
      return [`${vis(k)[0]} ${esc(vis(k)[1])} · ${list.length}`, `<div class="ov-list">${list.map((e) => `<div class="ov-row" data-ref="ev:${esc(e.id)}"><span class="t">${esc(e.id)}</span>
        <div class="x">${esc(e.what || e.proves)}<div class="small muted">${e.acts.join(' · ')}</div></div></div>`).join('')}</div>`, vis(k)[1]];
    },
  };
  // the content tree: why each act / beat is written that way and how it is carried out
  const T = D.tree || {acts: []};
  const tActBy = Object.fromEntries(T.acts.map((a) => [a.id, a]));
  const tBeatBy = Object.fromEntries(T.acts.flatMap((a) => a.beats.map((b) => [b.id, {...b, act: a.id}])));
  const ROLE_COLOR = {hook: '#f87171', title: '#a78bfa', link: '#60a5fa', loop: '#38bdf8', close: '#34d399', decode: '#fbbf24', slip: '#fb923c',
    evidence: '#4ade80', confession: '#f472b6', outro: '#a1a1aa', mask: '#c084fc', question: '#93c5fd', name: '#fde047', reaction: '#fda4af'};
  const ST_ICON = {verified: '✅', disputed: '⚠️', unverified: '❓'};
  const gen = (own) => own ? '' : ' <i class="tr-gen" title="Claude chưa ghi lý do riêng cho mục này: đây là cách đọc chung theo vai trò">(app suy)</i>';
  Object.assign(VIEW, {
    tact(a) {
      return [`<span style="color:${actColor[a.id]}">■</span> ${esc(a.id)} · ${esc(a.title)}`, `
        ${field('Ý chính / câu hỏi của hồi', esc(a.point))}
        ${field('🤔 Vì sao hồi này đứng ở đây' + gen(a.own), `<div class="whybox">${esc(a.why)}</div>`)}
        ${field('🛠 Triển khai thế nào', `<div class="howbox">${esc(a.how)}</div>`)}
        ${field('💡 Khi hết hồi, người xem biết thêm', esc(a.turn))}${field('➜ Chuyển sang hồi sau', esc(a.bridge))}
        ${field('Thời lượng', `${mmss(a.start)} → ${mmss(a.start + a.sec)} · ${mmss(a.sec)}`)}
        ${field(`Các beat (${a.beats.length})`, `<div class="ov-list">${a.beats.map((b) => `<div class="ov-row" data-ref="beat:${esc(b.id)}"><span class="t">${esc(b.id)}<br>${b.sec}s</span>
          <div class="x"><span style="color:${ROLE_COLOR[b.role] || '#c4b5fd'}">${esc(b.role || b.type)}</span> ${esc(b.point)}</div></div>`).join('')}</div>`)}`, a.id];
    },
    beat(b) {
      const nav = (id, lbl) => id && tBeatBy[id] ? `<span class="ov-chip" data-ref="beat:${esc(id)}">${lbl} ${esc(id)} · ${esc((tBeatBy[id].point || '').slice(0, 50))}</span>` : '';
      return [`📝 ${esc(b.id)} · <span style="color:${ROLE_COLOR[b.role] || '#c4b5fd'}">${esc(b.role || b.type)}</span> <span class="small muted">${esc(b.act)} · ${b.sec}s</span>`, `
        ${field('Ý chính', `<div style="font-size:14.5px;color:var(--text)">${esc(b.point)}</div>`)}
        ${field('🤔 Vì sao viết như thế' + gen(b.own), `<div class="whybox">${esc(b.why)}</div>`)}
        ${field('🛠 Triển khai thế nào' + gen(b.own), `<div class="howbox">${esc(b.how)}</div>`)}
        ${b.ideas.length ? field(`Các ý theo thứ tự (${b.ideas.length})`, `<ol>${b.ideas.map((x) => `<li>${esc(x)}</li>`).join('')}</ol>`) : ''}
        ${b.quote ? field('Trích nguyên văn', `<div class="quote">“${esc(b.quote.text)}”</div><div class="small muted">— ${esc(b.quote.speaker || '')}</div>`) : ''}
        ${field('Lời dẫn đầy đủ', esc(b.narration))}${field('Chữ trên màn hình', esc(b.on_screen_text))}
        ${field('Hình', `${b.visuals.map((v) => `${vis(v)[0]} ${esc(vis(v)[1])}`).join(' · ')}${b.visual_idea ? `<div class="small muted" style="margin-top:3px">${esc(b.visual_idea)}</div>` : ''}`)}
        ${b.evidence.length ? field(`Bằng chứng (${b.evidence.length})`, `<div class="ov-list">${b.evidence.map((e) => `<div class="ov-row" data-ref="ev:${esc(e.id)}"><span class="t">${esc(e.id)}</span>
          <div class="x">${esc(e.what)}${e.proves ? `<div class="small muted">chứng minh: ${esc(e.proves)}</div>` : ''}</div></div>`).join('')}</div>`) : ''}
        ${b.claims.length ? field('Khẳng định dựa vào', `<div class="ov-list">${b.claims.map((c) => `<div class="ov-row"><span class="t">${ST_ICON[c.status] || ''} ${esc(c.id)}</span><div class="x">${esc(c.text)}</div></div>`).join('')}</div>`) : ''}
        ${field('Nối mạch', `<div class="ov-chips">${nav(b.prev, '←')}${nav(b.next, '→')}</div>`)}`, b.id];
    },
  });

  function tree() {
    $('tr-note').innerHTML = T.own_beats ? `Claude ghi lý do cho ${T.own_beats}/${T.n_beats} beat`
      : `<span style="color:var(--warning)">Lý do đang do app suy theo vai trò beat</span>`;
    const ideas = (b) => b.ideas.length > 1 ? `<ul>${b.ideas.map((x) => `<li><div class="tr-n tr-idea">${esc(x)}</div></li>`).join('')}</ul>` : '';
    const beat = (b) => `<li class="fold" style="--lc:${ROLE_COLOR[b.role] || 'var(--line)'}55"><div class="tr-n tr-beat" data-ref="beat:${esc(b.id)}" style="--rc:${ROLE_COLOR[b.role] || '#e4e4e7'}">
        <div class="hd"><span class="role">${esc(b.role || b.type)}</span>${esc(b.id)} · ${b.sec}s ${b.visuals.map((v) => vis(v)[0]).join('')}
          ${b.claims.some((c) => c.status !== 'verified') ? '<span class="flag" title="Dựa vào khẳng định còn tranh cãi / chưa kiểm chứng">⚠️</span>' : ''}
          ${b.ideas.length > 1 ? `<span class="tg" data-fold title="Mở / gập các ý con">${b.ideas.length} ý ▸</span>` : ''}</div>
        <div class="pt">${esc(b.point)}</div><div class="why">🤔 ${esc(b.why)}</div></div>${ideas(b)}</li>`;
    const act = (a) => `<li style="--lc:${actColor[a.id]}"><div class="tr-n tr-act" data-ref="tact:${esc(a.id)}" style="--c:${actColor[a.id]}">
        <h4><em>${esc(a.id)}</em>${esc(a.title)}<span class="tg" data-fold title="Mở / gập các beat">${a.beats.length} beat ▾</span></h4>
        <div class="small muted">${mmss(a.start)} · ${mmss(a.sec)}</div><div class="pt">${esc(a.point)}</div><div class="why">🤔 ${esc(a.why)}</div></div>
        <ul>${a.beats.map(beat).join('')}</ul></li>`;
    $('tr').innerHTML = `<div class="tr-n tr-root" data-act-none><b>Luận đề</b>${esc(D.thesis || D.spine)}
        ${D.spine && D.spine !== D.thesis ? `<b>Xương sống</b>${esc(D.spine)}` : ''}${D.frame ? `<b>Khung kể</b>${esc(D.frame)}` : ''}</div>
      <ul>${T.acts.map(act).join('')}</ul>`;
  }
  function level(n) {
    document.querySelectorAll('#tr > ul > li').forEach((li) => li.classList.toggle('fold', n < 2));
    document.querySelectorAll('#tr > ul > li > ul > li').forEach((li) => li.classList.toggle('fold', n < 3));
  }

  function open(ref) {
    const [type, id] = ref.split(/:(.*)/s);
    const x = type === 'act' ? actBy[id] : type === 'char' ? charBy[id] : type === 'ev' ? evBy[id]
      : type === 'tact' ? tActBy[id] : type === 'beat' ? tBeatBy[id]
      : type === 'loc' ? D.locations.find((l) => l.id === id) : type === 'evk' ? id : null;
    document.querySelectorAll('.tr-n.sel').forEach((n) => n.classList.remove('sel'));
    document.querySelectorAll(`.tr-n[data-ref="${CSS.escape(ref)}"]`).forEach((n) => n.classList.add('sel'));
    if (!x || !VIEW[type]) return;
    const [title, body, tag] = VIEW[type](x);
    $('ov-dr-title').innerHTML = title;
    $('ov-dr-body').innerHTML = body;
    $('ov-dr-body').scrollTop = 0;
    $('ov-ask').value = `[sơ đồ · ${tag}] `;
    $('ov-drawer').hidden = false;
    document.body.classList.add('ov-open');
  }

  const send = async (text) => {
    const r = await api(`/api/p/${PID}/message`, {text, step: 'script'});
    if (r && r.error) { toast(r.error); return false; }
    toast('Đã gửi Claude. Theo dõi ở trang dự án.');
    return true;
  };
  window.BP = {
    close() { $('ov-drawer').hidden = true; document.body.classList.remove('ov-open'); },
    async ask() {
      const ta = $('ov-ask');
      const text = ta.value.trim();
      if (!text || /^\[[^\]]*\]$/.test(text)) { toast('Viết yêu cầu sửa trước đã'); return; }
      if (await send(text)) ta.value = '';
    },
    async askBlueprint() {
      if (!confirm('Gửi Claude lập 1_script/blueprint.json từ kịch bản hiện có (không đổi kịch bản)? Lượt này tốn usage Claude.')) return;
      send('Lập 1_script/blueprint.json cho dự án này theo mục 2.1 bước 8 và mẫu ở 11.1, dựa trên kịch bản, research.md và các bước đã làm. '
        + 'Không sửa kịch bản hay file của bước khác.');
    },
  };

  document.addEventListener('click', (ev) => {
    const fold = ev.target.closest('[data-fold]');
    if (fold) { fold.closest('li').classList.toggle('fold'); return; }
    const lv = ev.target.closest('[data-lv]');
    if (lv) { level(Number(lv.dataset.lv)); return; }
    const a = ev.target.closest('[data-act]');
    if (a) { open(`act:${a.dataset.act}`); return; }
    const el = ev.target.closest('[data-ref]');
    if (el) open(el.dataset.ref);
  });
  document.addEventListener('keydown', (ev) => { if (ev.key === 'Escape') BP.close(); });

  $('tr-why').addEventListener('change', (ev) => $('tr').classList.toggle('show-why', ev.target.checked));

  intent(); tree(); level(2); spine(); matrix(); pipe(); decide();
})();
