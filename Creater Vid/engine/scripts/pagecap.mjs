// Real documents for the dossier kit: capture a web page (Wikipedia, a news article, an archive page, a local
// .html) as a page image AND measure where the phrases to highlight are, so the marker in <DocPage> lands exactly
// on the words. Uses the Chrome Headless Shell of the engine over the DevTools protocol (no extra packages).
//
//   node scripts/pagecap.mjs <url> <id> --mark "non-faculty" --mark "completed his Ph.D." [options]
//
//   --mark "phrase"      phrase to locate (repeatable; case and spacing ignored; "phrase#2" = its 2nd occurrence)
//   --width 1100         page width in CSS px (a reading column; 1100 suits Wikipedia and most articles)
//   --height 1400        height of the captured page in CSS px (the part around the first mark, or the top: --top)
//   --top                capture from the top of the page instead of around the first mark
//   --scale 2            device pixel ratio of the image (2 = sharp when the camera zooms to 2.6x)
//   --clean              hide navigation chrome, cookie banners, sticky headers (default on; --no-clean)
//   --css "selector{…}"  extra CSS injected before capture
//   --out public/docs    where <id>.png and <id>.json go
//
// Output <id>.json: {src, aspect, url, captured, marks: [{text, boxes: [[x, y, w, h], …]}], missing: [...]}
// with boxes as fractions of the image, one per line of text: paste them into a DocPage mark.
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {spawn} from 'node:child_process';
import {browserExecutable} from './browser.mjs';

const argv = process.argv.slice(2);
const pos = [];
const opt = {mark: [], width: 1100, height: 1400, scale: 2, top: false, clean: true, css: '', out: 'public/docs'};
for (let i = 0; i < argv.length; i++) {
  const a = argv[i];
  if (a === '--mark') opt.mark.push(argv[++i]);
  else if (a === '--width') opt.width = Number(argv[++i]);
  else if (a === '--height') opt.height = Number(argv[++i]);
  else if (a === '--scale') opt.scale = Number(argv[++i]);
  else if (a === '--top') opt.top = true;
  else if (a === '--no-clean') opt.clean = false;
  else if (a === '--clean') opt.clean = true;
  else if (a === '--css') opt.css = argv[++i];
  else if (a === '--out') opt.out = argv[++i];
  else pos.push(a);
}
if (pos.length < 2) {
  console.error('usage: node scripts/pagecap.mjs <url> <id> --mark "phrase" [...]  (see the header of this file)');
  process.exit(1);
}
let [url, id] = pos;
if (!/^[a-z]+:/i.test(url) && fs.existsSync(url)) url = 'file:///' + path.resolve(url).replace(/\\/g, '/');

const exe = browserExecutable();
if (!exe) {
  console.error('Chrome Headless Shell not found in node_modules/.remotion (run `npx remotion browser ensure` in the engine)');
  process.exit(1);
}

const profile = fs.mkdtempSync(path.join(os.tmpdir(), 'pagecap-'));
const chrome = spawn(exe, ['--headless', '--remote-debugging-port=0', `--user-data-dir=${profile}`, '--hide-scrollbars', '--no-first-run',
  '--disable-gpu', '--mute-audio', '--disable-extensions', 'about:blank'], {stdio: ['ignore', 'ignore', 'pipe']});
const cleanup = () => {
  try { chrome.kill(); } catch {}
  setTimeout(() => { try { fs.rmSync(profile, {recursive: true, force: true}); } catch {} }, 400);
};

const wsUrl = await new Promise((resolve, reject) => {
  let buf = '';
  const t = setTimeout(() => reject(new Error('Chrome did not start')), 20000);
  chrome.stderr.on('data', (d) => {
    buf += d.toString();
    const m = buf.match(/DevTools listening on (ws:\/\/\S+)/);
    if (m) { clearTimeout(t); resolve(m[1]); }
  });
});

const ws = new WebSocket(wsUrl);
await new Promise((r) => ws.addEventListener('open', r, {once: true}));
let nextId = 1;
const pending = new Map();
const waiters = [];
ws.addEventListener('message', (ev) => {
  const msg = JSON.parse(ev.data);
  if (msg.id && pending.has(msg.id)) {
    const {resolve, reject} = pending.get(msg.id);
    pending.delete(msg.id);
    msg.error ? reject(new Error(msg.error.message)) : resolve(msg.result);
  } else if (msg.method) {
    for (const w of waiters) if (w.method === msg.method) w.resolve(msg.params);
  }
});
const send = (method, params = {}, sessionId) => new Promise((resolve, reject) => {
  const mid = nextId++;
  pending.set(mid, {resolve, reject});
  ws.send(JSON.stringify({id: mid, method, params, ...(sessionId ? {sessionId} : {})}));
});
const once = (method, ms) => new Promise((resolve) => {
  const w = {method, resolve};
  waiters.push(w);
  setTimeout(() => resolve(null), ms);
});
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

try {
  const {targetId} = await send('Target.createTarget', {url: 'about:blank'});
  const {sessionId} = await send('Target.attachToTarget', {targetId, flatten: true});
  const S = (m, p) => send(m, p, sessionId);
  await S('Page.enable');
  await S('Network.setUserAgentOverride', {userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36',
    acceptLanguage: 'en-US,en;q=0.9'});
  await S('Emulation.setDeviceMetricsOverride', {width: opt.width, height: opt.height, deviceScaleFactor: opt.scale, mobile: false});
  const loaded = once('Page.loadEventFired', 30000);
  await S('Page.navigate', {url});
  await loaded;
  await sleep(1800);

  const CLEAN_CSS = `
    .vector-header-container, .vector-sticky-header, #mw-panel, .vector-column-start, .vector-page-toolbar, .vector-column-end,
    #siteNotice, .mw-jump-link, #p-lang-btn, .vector-toc-landmark, .mw-editsection, #mw-head, #mw-navigation, .noprint,
    .mw-footer-container { display: none !important; }
    .mw-page-container { max-width: none !important; padding: 0 28px !important; }
    .mw-content-container, .vector-body { margin: 0 !important; }
    html, body { background: #fff !important; }
    ${opt.css}`;
  const res = await S('Runtime.evaluate', {returnByValue: true, awaitPromise: true, expression: `(async () => {
    const clean = ${JSON.stringify(opt.clean)};
    const st = document.createElement('style');
    st.textContent = ${JSON.stringify(opt.clean ? CLEAN_CSS : opt.css)};
    document.head.appendChild(st);
    if (clean) for (const el of document.querySelectorAll('body *')) {
      const cs = getComputedStyle(el);
      if ((cs.position === 'fixed' || cs.position === 'sticky') && el.getBoundingClientRect().height < innerHeight * 0.9) el.style.setProperty('display', 'none', 'important');
    }
    await new Promise((r) => setTimeout(r, 300));
    // text of the page with a map back to the text nodes (whitespace collapsed, lower case)
    const nodes = [];
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, {acceptNode: (n) => {
      const p = n.parentElement;
      if (!p || !n.nodeValue.trim()) return NodeFilter.FILTER_REJECT;
      const cs = getComputedStyle(p);
      return cs.display === 'none' || cs.visibility === 'hidden' ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT;
    }});
    let text = '';
    const map = []; // map[i] = [node, offset] of character i of text
    let lastSpace = true;
    for (let n = walker.nextNode(); n; n = walker.nextNode()) {
      const v = n.nodeValue;
      for (let k = 0; k < v.length; k++) {
        const ch = v[k];
        if (/\\s/.test(ch)) { if (!lastSpace) { text += ' '; map.push([n, k]); lastSpace = true; } }
        else { text += ch.toLowerCase(); map.push([n, k]); lastSpace = false; }
      }
      if (!lastSpace) { text += ' '; map.push([n, v.length]); lastSpace = true; }
    }
    const want = ${JSON.stringify(opt.mark)};
    const sx = scrollX, sy = scrollY;
    const marks = [], missing = [];
    for (const raw of want) {
      const m = raw.match(/^(.*?)(?:#(\\d+))?$/s);
      const phrase = m[1].replace(/\\s+/g, ' ').trim().toLowerCase();
      let nth = Number(m[2] || 1), at = -1, from = 0;
      while (nth-- > 0) { at = text.indexOf(phrase, from); if (at < 0) break; from = at + 1; }
      if (at < 0) { missing.push(raw); continue; }
      const [n0, o0] = map[at];
      const [n1, o1] = map[at + phrase.length - 1];
      const r = document.createRange();
      r.setStart(n0, o0);
      r.setEnd(n1, o1 + 1);
      // one box per line: merge the client rects that share a line
      const lines = [];
      for (const b of r.getClientRects()) {
        if (b.width < 1 || b.height < 1) continue;
        const l = lines.find((q) => Math.abs(q.y + q.h / 2 - (b.top + b.height / 2)) < b.height * 0.5);
        if (l) { const x1 = Math.max(l.x + l.w, b.right); l.x = Math.min(l.x, b.left); l.w = x1 - l.x; l.y = Math.min(l.y, b.top); l.h = Math.max(l.h, b.height); }
        else lines.push({x: b.left, y: b.top, w: b.width, h: b.height});
      }
      marks.push({text: raw, lines: lines.map((l) => [l.x + sx, l.y + sy, l.w, l.h])});
    }
    return {marks, missing, docH: document.documentElement.scrollHeight, docW: document.documentElement.scrollWidth, title: document.title};
  })()`});
  if (res.exceptionDetails) throw new Error(res.exceptionDetails.exception?.description || 'page script failed');
  const page = res.result.value;

  const W = opt.width;
  const H = Math.min(opt.height, page.docH);
  const firstY = page.marks.length ? Math.min(...page.marks[0].lines.map((l) => l[1])) : 0;
  const y0 = opt.top ? 0 : Math.max(0, Math.min(page.docH - H, firstY - H * 0.3));
  const shot = await S('Page.captureScreenshot', {format: 'png', captureBeyondViewport: true, clip: {x: 0, y: y0, width: W, height: H, scale: 1}});
  fs.mkdirSync(opt.out, {recursive: true});
  const png = path.join(opt.out, `${id}.png`);
  fs.writeFileSync(png, Buffer.from(shot.data, 'base64'));

  const r4 = (v) => Math.round(v * 10000) / 10000;
  const outside = [];
  const marks = page.marks.map((m) => {
    const boxes = m.lines
      .map(([x, y, w, h]) => [r4(x / W), r4((y - y0) / H), r4(w / W), r4(h / H)])
      .filter((b) => b[1] >= 0 && b[1] + b[3] <= 1);
    if (boxes.length < m.lines.length) outside.push(m.text);
    return {text: m.text, boxes};
  });
  const src = path.relative('public', png).replace(/\\/g, '/');
  const meta = {src, aspect: r4(W / H), url, title: page.title, captured: new Date().toISOString(), marks, missing: page.missing,
    ...(outside.length ? {outside_capture: outside} : {})};
  fs.writeFileSync(path.join(opt.out, `${id}.json`), JSON.stringify(meta, null, 1));
  console.log(JSON.stringify({ok: true, png, aspect: meta.aspect, marks: marks.map((m) => `${m.text}: ${m.boxes.length} line(s)`), missing: page.missing,
    outside_capture: outside}));
  if (page.missing.length || outside.length) process.exitCode = 3;
} catch (e) {
  console.error('pagecap failed:', e.message);
  process.exitCode = 1;
} finally {
  ws.close();
  cleanup();
}
