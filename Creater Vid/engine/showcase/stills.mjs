// Proof frames of the kit showcase: node showcase/stills.mjs 85 90 95 ... -> out/showcase/fNNNN.jpg + sheet.jpg
import path from 'node:path';
import {mkdirSync} from 'node:fs';
import {execFileSync} from 'node:child_process';
import {bundle} from '@remotion/bundler';
import {renderStill, selectComposition} from '@remotion/renderer';
import {browserExecutable} from '../scripts/browser.mjs';

// --comp DossierShowcase renders that composition instead of the kit showcase (stills in out/showcase/<comp>/)
const args = process.argv.slice(2);
const ci = args.indexOf('--comp');
const compId = ci >= 0 ? args.splice(ci, 2)[1] : 'KitShowcase';
const frames = args.map(Number);
const serveUrl = await bundle({entryPoint: path.resolve('showcase/index.ts')});
const chromiumOptions = {gl: 'angle'};
const browser = browserExecutable();
const composition = await selectComposition({serveUrl, id: compId, chromiumOptions, browserExecutable: browser});
const dir = compId === 'KitShowcase' ? 'out/showcase' : `out/showcase/${compId}`;
mkdirSync(dir, {recursive: true});
const outs = [];
for (const frame of frames) {
  const output = `${dir}/f${String(frame).padStart(4, '0')}.jpg`;
  await renderStill({serveUrl, composition, frame, output, imageFormat: 'jpeg', jpegQuality: 85, chromiumOptions, timeoutInMilliseconds: 120000,
    browserExecutable: browser, onBrowserLog: (l) => l.type === 'error' && console.log('[browser]', l.text.slice(0, 300))});
  outs.push(output);
  console.log(output);
}
const cols = Math.min(4, outs.length);
execFileSync(process.env.FFMPEG || 'ffmpeg', ['-y', '-loglevel', 'error', ...outs.flatMap((o) => ['-i', o]), '-filter_complex',
  `${outs.map((_, i) => `[${i}]scale=640:-1[s${i}]`).join(';')};${outs.map((_, i) => `[s${i}]`).join('')}xstack=inputs=${outs.length}:layout=${outs.map((_, i) => `${(i % cols) * 640}_${Math.floor(i / cols) * 360}`).join('|')}`,
  `${dir}/sheet.jpg`]);
console.log(`sheet: ${dir}/sheet.jpg`);
