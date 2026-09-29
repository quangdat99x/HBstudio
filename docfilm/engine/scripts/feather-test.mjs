// Prints the simulated feather path as an ASCII plot plus a few numbers, for tuning.
import {simulateFeather} from '../src/engine/featherSim.js';

const args = Object.fromEntries(process.argv.slice(2).map((a) => a.split('=')).map(([k, v]) => [k, Number(v)]));
const path = simulateFeather({frames: 150, ...args});
const W = 100;
const H = 40;
const xs = path.map((p) => p.x);
const ys = path.map((p) => p.y);
const xmin = Math.min(...xs, -300);
const xmax = Math.max(...xs, 300);
const ymin = Math.min(...ys);
const grid = Array.from({length: H}, () => Array(W).fill(' '));
path.forEach((p, i) => {
  const c = Math.round(((p.x - xmin) / (xmax - xmin)) * (W - 1));
  const r = Math.round((p.y / (ymin || -1)) * (H - 1));
  if (r >= 0 && r < H) grid[r][c] = i % 10 === 0 ? String((i / 10) % 10) : '.';
});
console.log(grid.map((r) => r.join('')).join('\n'));
let reversals = 0;
for (let i = 2; i < path.length; i++) if (Math.sign(path[i].vx) !== Math.sign(path[i - 1].vx)) reversals++;
const rots = path.map((p) => (p.rot * 180) / Math.PI);
console.log(`x range ${Math.min(...xs).toFixed(0)}..${Math.max(...xs).toFixed(0)}  fall ${(-ymin).toFixed(0)} px in 5s  reversals ${reversals}  rot ${Math.min(...rots).toFixed(0)}..${Math.max(...rots).toFixed(0)} deg`);
