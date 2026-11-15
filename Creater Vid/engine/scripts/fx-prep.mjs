// Prepare a filmed element shot on black (fire, smoke, sparks, dust) for <VideoFx>: trim, crop to the part you
// need, conform to 30 fps, crush the black point (compression noise would glow when added), optionally strip
// the colour (smoke), and measure the brightness of every frame so the light the element casts can flicker
// with it (fire). Originals stay in assets/fx/ (downloaded only after the user approved them).
//
//   node scripts/fx-prep.mjs assets/fx/fire_5659678.mp4 fire --start 1 --dur 8.4 --crop 1040:1080:150:0 --flicker
//     -> public/fx/fire.mp4 + src/fx/fireFlicker.json (1 = average brightness, one value per frame)
//   node scripts/fx-prep.mjs assets/fx/smoke_4320605.mp4 smoke --start 2 --dur 8.4 --crop 1100:1080:60:0 --desat
import {spawnSync} from 'node:child_process';
import {mkdirSync, writeFileSync} from 'node:fs';

const [input, name, ...rest] = process.argv.slice(2);
if (!input || !name) {
  console.log('usage: node scripts/fx-prep.mjs <in.mp4> <name> [--start s] [--dur s] [--crop w:h:x:y] [--width px] [--black 0.05] [--desat] [--flicker]');
  process.exit(1);
}
const opt = {start: 0, dur: null, crop: null, width: 720, black: 0.05, desat: false, flicker: false};
for (let i = 0; i < rest.length; i++) {
  const k = rest[i].replace(/^--/, '');
  if (k === 'desat' || k === 'flicker') opt[k] = true;
  else opt[k] = rest[++i];
}
const FFMPEG = process.env.FFMPEG || 'ffmpeg';
const vf = [opt.crop && `crop=${opt.crop}`, 'fps=30', `scale=${opt.width}:-2:flags=lanczos`, opt.desat && 'hue=s=0.15', `colorlevels=rimin=${opt.black}:gimin=${opt.black}:bimin=${opt.black}`].filter(Boolean).join(',');
mkdirSync('public/fx', {recursive: true});
const out = `public/fx/${name}.mp4`;
const args = ['-hide_banner', '-loglevel', 'error', '-y', '-ss', String(opt.start), ...(opt.dur ? ['-t', String(opt.dur)] : []), '-i', input, '-vf', vf, '-an', '-c:v', 'libx264', '-crf', '14', '-preset', 'slow', '-pix_fmt', 'yuv420p', out];
let r = spawnSync(FFMPEG, args, {stdio: 'inherit'});
if (r.status !== 0) throw new Error('ffmpeg failed');
console.log(out);
if (opt.flicker) {
  r = spawnSync(FFMPEG, ['-hide_banner', '-nostats', '-i', out, '-vf', 'signalstats,metadata=print:key=lavfi.signalstats.YAVG', '-f', 'null', '-'], {encoding: 'utf8'});
  const v = [...r.stderr.matchAll(/YAVG=([\d.]+)/g)].map((m) => Number(m[1]));
  const mean = v.reduce((a, b) => a + b, 0) / v.length;
  mkdirSync('src/fx', {recursive: true});
  const file = `src/fx/${name}Flicker.json`;
  writeFileSync(file, JSON.stringify(v.map((x) => Math.round((x / mean) * 1000) / 1000)));
  console.log(`${file}  ${v.length} frames, ${(Math.min(...v) / mean).toFixed(2)}-${(Math.max(...v) / mean).toFixed(2)} x average`);
}
