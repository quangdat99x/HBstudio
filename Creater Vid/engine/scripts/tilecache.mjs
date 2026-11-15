// Bộ đệm tile bản đồ trên đĩa cho Map3D (RULEBOOK.news 4.4).
// Mỗi tab Chrome của một lượt render tự tải lại toàn bộ tile (vệ tinh, địa hình, đèn đêm, OSM) → render bản tin rất chậm
// và hay gặp tile lỗi. Máy chủ nhỏ này chạy ngay trong tiến trình render (remotion.config.ts, scripts/stills.mjs):
// tải mỗi tile một lần, giữ lại ở <Creater Vid>/work/tilecache, các tab và các lượt sau đọc từ đĩa.
// Map3D hỏi /ping trước; không có máy chủ thì tải thẳng như cũ.
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';

export const TILE_PORT = 5098;
const HOSTS = new Set(['tiles.openfreemap.org', 's3.amazonaws.com', 'gibs.earthdata.nasa.gov', 'tiles.maps.eox.at']);
const TILE_RE = /\/\d+\/\d+\/\d+(\.[a-z0-9]+)?(\?|$)/i; // …/z/x/y(.ext): không đổi → giữ mãi; còn lại (TileJSON…) giữ 24 h
const DAY = 24 * 3600 * 1000;

const cacheDir = () => {
  try {
    // film/node_modules là liên kết tới engine/node_modules → <Creater Vid>/work/tilecache, dùng chung mọi dự án
    return path.join(fs.realpathSync.native(path.resolve('node_modules')), '..', '..', 'work', 'tilecache');
  } catch {
    return path.resolve('.tilecache');
  }
};

const inflight = new Map();

async function upstream(u) {
  let last;
  for (let i = 0; i < 4; i++) {
    try {
      const r = await fetch(u, {signal: AbortSignal.timeout(30000)});
      if (r.status === 404 || r.status === 204) return {status: 404, type: 'text/plain', body: Buffer.alloc(0)};
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const type = r.headers.get('content-type') || 'application/octet-stream';
      const body = Buffer.from(await r.arrayBuffer());
      if (/text\/html/.test(type) && TILE_RE.test(u)) throw new Error('html instead of tile');
      return {status: 200, type, body};
    } catch (e) {
      last = e;
      await new Promise((ok) => setTimeout(ok, 400 * (i + 1)));
    }
  }
  throw last;
}

async function get(dir, u) {
  const key = crypto.createHash('sha1').update(u).digest('hex');
  const file = path.join(dir, key.slice(0, 2), key);
  const meta = file + '.json';
  try {
    const m = JSON.parse(fs.readFileSync(meta, 'utf8'));
    if (TILE_RE.test(u) || Date.now() - m.t < DAY) return {status: m.status, type: m.type, body: m.status === 200 ? fs.readFileSync(file) : Buffer.alloc(0)};
  } catch {
    // chưa có trong bộ đệm
  }
  if (!inflight.has(key)) {
    inflight.set(key, (async () => {
      const res = await upstream(u);
      fs.mkdirSync(path.dirname(file), {recursive: true});
      if (res.status === 200) {
        fs.writeFileSync(file + '.part', res.body);
        fs.renameSync(file + '.part', file);
      }
      fs.writeFileSync(meta, JSON.stringify({status: res.status, type: res.type, t: Date.now(), u}));
      return res;
    })().finally(() => inflight.delete(key)));
  }
  return inflight.get(key);
}

let started = null;
export function startTileCache() {
  if (started) return started;
  const dir = cacheDir();
  started = new Promise((resolve) => {
    const server = http.createServer(async (req, res) => {
      const cors = {'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Private-Network': 'true'};
      const q = new URL(req.url, 'http://x');
      if (q.pathname === '/ping') {
        res.writeHead(200, {...cors, 'Content-Type': 'text/plain'});
        return res.end('ok');
      }
      const u = q.searchParams.get('u') || '';
      let host = '';
      try {
        host = new URL(u).hostname;
      } catch {
        // URL hỏng
      }
      if (q.pathname !== '/fetch' || !HOSTS.has(host)) {
        res.writeHead(403, cors);
        return res.end();
      }
      try {
        const r = await get(dir, u);
        res.writeHead(r.status, {...cors, 'Content-Type': r.type, 'Cache-Control': 'max-age=86400'});
        res.end(r.body);
      } catch (e) {
        res.writeHead(502, {...cors, 'Content-Type': 'text/plain'});
        res.end(String(e));
      }
    });
    server.on('error', () => resolve(false)); // cổng đã có lượt render khác giữ: dùng chung máy chủ đó
    server.listen(TILE_PORT, '127.0.0.1', () => {
      server.unref(); // không giữ tiến trình render sống sau khi xong
      resolve(true);
    });
  });
  return started;
}
