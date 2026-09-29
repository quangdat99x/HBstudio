// Landmarks measured from the image pixels, never eyeballed on a coarse grid.
//   node scripts/measure.mjs bbox  public/img/raphael.png            -> opaque bounding box, feet row
//   node scripts/measure.mjs ridge public/img/mountain.png           -> top silhouette (alpha) + peak
//   node scripts/measure.mjs glow  public/img/semjaza.png [yMax] [fire|white|gold]
//                                                                    -> centroid of the glow in each half (hands in fire, ...)
//   node scripts/measure.mjs grid  public/img/azazel.png out/grid.png [stepPercent]
//                                                                    -> 5% grid overlay for points with no colour signature
// Coordinates are image fractions: x from the left, y from the top (0..1), whatever the aspect ratio.
import {execFileSync} from 'node:child_process';

const FFMPEG = process.env.FFMPEG || 'ffmpeg';
const N = 512;
const [cmd, file, ...rest] = process.argv.slice(2);
if (!cmd || !file) {
  console.error('usage: measure.mjs bbox|ridge|glow|grid <image> [...]');
  process.exit(1);
}

const rgba = () => {
  const buf = execFileSync(FFMPEG, ['-v', 'error', '-i', file, '-vf', `scale=${N}:${N}:flags=area`, '-f', 'rawvideo', '-pix_fmt', 'rgba', '-'], {maxBuffer: 1 << 26});
  return (x, y) => {
    const i = (y * N + x) * 4;
    return [buf[i], buf[i + 1], buf[i + 2], buf[i + 3]];
  };
};
const fr = (v) => +(v / (N - 1)).toFixed(4);

if (cmd === 'bbox') {
  const px = rgba();
  let x0 = N, y0 = N, x1 = -1, y1 = -1;
  for (let y = 0; y < N; y++) for (let x = 0; x < N; x++) if (px(x, y)[3] > 128) {
    x0 = Math.min(x0, x); x1 = Math.max(x1, x); y0 = Math.min(y0, y); y1 = Math.max(y1, y);
  }
  console.log(JSON.stringify({left: fr(x0), right: fr(x1), top: fr(y0), feet: fr(y1), centerX: fr((x0 + x1) / 2)}));
} else if (cmd === 'ridge') {
  const px = rgba();
  const ridge = [];
  for (let x = 0; x < N; x += 2) {
    for (let y = 0; y < N; y++) if (px(x, y)[3] > 160) { ridge.push([fr(x), fr(y)]); break; }
  }
  const peak = ridge.reduce((a, b) => (b[1] < a[1] ? b : a));
  console.log(JSON.stringify({peak, ridge}));
} else if (cmd === 'glow') {
  const yMax = Number(rest[0] || 1);
  const kind = rest[1] || 'fire';
  const tests = {
    fire: (r, g, b) => r > 200 && g > 90 && b < 110 && r - b > 120,
    gold: (r, g, b) => r > 190 && g > 150 && b < 140,
    white: (r, g, b) => r > 235 && g > 235 && b > 220,
  };
  const test = tests[kind] || tests.fire;
  const px = rgba();
  const out = [];
  for (const [xa, xb] of [[0, N / 2], [N / 2, N]]) {
    let sx = 0, sy = 0, w = 0;
    for (let y = 0; y < N * yMax; y++) for (let x = xa; x < xb; x++) {
      const [r, g, b, a] = px(x, y);
      if (a < 128 || !test(r, g, b)) continue;
      const k = r + g;
      sx += x * k; sy += y * k; w += k;
    }
    out.push(w ? [fr(sx / w), fr(sy / w)] : null);
  }
  console.log(JSON.stringify({left: out[0], right: out[1]}));
} else if (cmd === 'grid') {
  const outFile = rest[0] || 'out/grid.png';
  const step = Number(rest[1] || 5);
  const cells = Math.round(100 / step);
  execFileSync(FFMPEG, ['-v', 'error', '-y', '-f', 'lavfi', '-i', 'color=c=0x2a6f73:s=1000x1000', '-i', file, '-filter_complex',
    `[1:v]scale=1000:1000[f];[0:v][f]overlay,drawgrid=w=${1000 / cells}:h=${1000 / cells}:t=1:c=white@0.3,drawgrid=w=250:h=250:t=2:c=yellow@0.7`,
    '-frames:v', '1', outFile]);
  console.log(`${outFile}: thin lines every ${step}%, yellow every 25% (x from left, y from top)`);
} else {
  console.error(`unknown command ${cmd}`);
  process.exit(1);
}
