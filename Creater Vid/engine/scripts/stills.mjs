// Proof frames before any full render:
//   node scripts/stills.mjs 20 100 160 420          -> out/stills/f020.jpg ... + out/stills/sheet.jpg (contact sheet)
//   node scripts/stills.mjs --comp Film 200 --crop 900x500+510+130 -> also writes a 1:1 crop of each frame
//   --public <folder>  render with another public folder (A/B test of swapped images)
//   --logs             print the browser console (debug shaders, textures that never arrive)
// Bundles once, renders each frame with WebGL through ANGLE (GPU).
import path from 'node:path';
import {mkdirSync} from 'node:fs';
import {execFileSync} from 'node:child_process';
import {bundle} from '@remotion/bundler';
import {openBrowser, renderStill, selectComposition} from '@remotion/renderer';
import {browserExecutable} from './browser.mjs';
import {startTileCache} from './tilecache.mjs';

const args = process.argv.slice(2);
let comp = 'Film';
let crop = null;
let publicDir = null;
let logs = false;
const frames = [];
for (let i = 0; i < args.length; i++) {
  if (args[i] === '--comp') comp = args[++i];
  else if (args[i] === '--crop') crop = args[++i];
  else if (args[i] === '--public') publicDir = path.resolve(args[++i]);
  else if (args[i] === '--logs') logs = true;
  else frames.push(Number(args[i]));
}
const FFMPEG = process.env.FFMPEG || 'ffmpeg';
await startTileCache(); // tile bản đồ Map3D đọc từ đĩa (scripts/tilecache.mjs)
const serveUrl = await bundle({entryPoint: path.resolve('src/index.ts'), ...(publicDir && {publicDir})});
const chromiumOptions = {gl: 'angle'};
const browser = browserExecutable();
// One shared Chrome for every frame (renderStill alone launches a new browser per call), several tabs at once.
const puppeteerInstance = await openBrowser('chrome', {chromiumOptions, browserExecutable: browser});
const composition = await selectComposition({serveUrl, id: comp, chromiumOptions, browserExecutable: browser, puppeteerInstance});
mkdirSync('out/stills', {recursive: true});
const tabs = Math.max(1, Math.min(frames.length, Number(process.env.STILLS_CONCURRENCY || process.env.RENDER_CONCURRENCY) || 4));
const outs = frames.map((frame) => `out/stills/f${String(frame).padStart(3, '0')}.jpg`);
let next = 0;
async function lane() {
  while (next < frames.length) {
    const i = next++;
    const output = outs[i];
    await renderStill({serveUrl, composition, frame: frames[i], output, imageFormat: 'jpeg', jpegQuality: 88, chromiumOptions, timeoutInMilliseconds: 120000, browserExecutable: browser, puppeteerInstance, ...(logs && {onBrowserLog: (l) => console.log('[browser]', l.type, l.text.slice(0, 400))})});
    if (crop) {
      const [wh, x, y] = crop.split('+');
      const [w, h] = wh.split('x');
      execFileSync(FFMPEG, ['-v', 'error', '-y', '-i', output, '-vf', `crop=${w}:${h}:${x}:${y}`, output.replace('.jpg', '_crop.jpg')]);
    }
    console.log(output);
  }
}
try {
  await Promise.all(Array.from({length: tabs}, lane));
} finally {
  await puppeteerInstance.close({silent: true});
}
if (outs.length > 1) {
  const cols = Math.min(3, outs.length);
  const rows = Math.ceil(outs.length / cols);
  const inputs = outs.flatMap((o) => ['-i', o]);
  const scaled = outs.map((_, i) => `[${i}:v]scale=640:-1[s${i}]`).join(';');
  const pads = Array.from({length: cols * rows - outs.length}, (_, i) => `color=c=black:s=640x360:d=1[p${i}]`).join(';');
  const all = [...outs.map((_, i) => `[s${i}]`), ...Array.from({length: cols * rows - outs.length}, (_, i) => `[p${i}]`)].join('');
  const layout = Array.from({length: cols * rows}, (_, i) => `${(i % cols) * 640}_${Math.floor(i / cols) * 360}`).join('|');
  const graph = [scaled, pads, `${all}xstack=inputs=${cols * rows}:layout=${layout}`].filter(Boolean).join(';');
  execFileSync(FFMPEG, ['-v', 'error', '-y', ...inputs, '-filter_complex', graph, '-frames:v', '1', 'out/stills/sheet.jpg']);
  console.log('out/stills/sheet.jpg');
}
