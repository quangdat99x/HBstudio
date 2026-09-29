// Proof frames before any full render:
//   node scripts/stills.mjs 20 100 160 420          -> out/stills/f020.jpg ... + out/stills/sheet.jpg (contact sheet)
//   node scripts/stills.mjs --comp Film 200 --crop 900x500+510+130 -> also writes a 1:1 crop of each frame
// Bundles once, renders each frame with WebGL through ANGLE (GPU).
import path from 'node:path';
import {mkdirSync} from 'node:fs';
import {execFileSync} from 'node:child_process';
import {bundle} from '@remotion/bundler';
import {renderStill, selectComposition} from '@remotion/renderer';
import {browserExecutable} from './browser.mjs';

const args = process.argv.slice(2);
let comp = 'Film';
let crop = null;
const frames = [];
for (let i = 0; i < args.length; i++) {
  if (args[i] === '--comp') comp = args[++i];
  else if (args[i] === '--crop') crop = args[++i];
  else frames.push(Number(args[i]));
}
const FFMPEG = process.env.FFMPEG || 'ffmpeg';
const serveUrl = await bundle({entryPoint: path.resolve('src/index.ts')});
const chromiumOptions = {gl: 'angle'};
const browser = browserExecutable();
const composition = await selectComposition({serveUrl, id: comp, chromiumOptions, browserExecutable: browser});
mkdirSync('out/stills', {recursive: true});
const outs = [];
for (const frame of frames) {
  const output = `out/stills/f${String(frame).padStart(3, '0')}.jpg`;
  await renderStill({serveUrl, composition, frame, output, imageFormat: 'jpeg', jpegQuality: 88, chromiumOptions, timeoutInMilliseconds: 120000, browserExecutable: browser});
  outs.push(output);
  if (crop) {
    const [wh, x, y] = crop.split('+');
    const [w, h] = wh.split('x');
    execFileSync(FFMPEG, ['-v', 'error', '-y', '-i', output, '-vf', `crop=${w}:${h}:${x}:${y}`, output.replace('.jpg', '_crop.jpg')]);
  }
  console.log(output);
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
