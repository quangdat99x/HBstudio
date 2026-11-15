// Random search for feather parameters that give a clean flutter: pendulum-like swings,
// no tumbling, a slight rise at the end of each swing, and a sensible descent rate.
import {simulateFeather, } from '../src/engine/featherSim.js';
import {mulberry32} from './rng.mjs';

const rnd = mulberry32(42);
const pick = (a, b) => a + (b - a) * rnd();
let best = [];
for (let i = 0; i < 4000; i++) {
  const p = {
    frames: 110,
    g: pick(500, 1400),
    cn: pick(0.06, 0.2),
    ct: pick(0.001, 0.01),
    cl: pick(0.01, 0.06),
    ktorque: pick(0.0002, 0.003),
    kspin: pick(3, 14),
    theta0: pick(0.3, 0.8),
  };
  const path = simulateFeather(p);
  const xs = path.map((q) => q.x);
  const ys = path.map((q) => q.y);
  const rots = path.map((q) => (q.rot * 180) / Math.PI);
  const fall = -Math.min(...ys);
  const span = Math.max(...xs) - Math.min(...xs);
  let rev = 0;
  let maxRise = 0;
  for (let k = 2; k < path.length; k++) {
    if (Math.sign(path[k].vx) !== Math.sign(path[k - 1].vx)) rev++;
    maxRise = Math.max(maxRise, path[k].y - Math.min(...ys.slice(0, k)));
  }
  const rotSpan = Math.max(...rots.map(Math.abs));
  if (rotSpan > 65 || rev < 3 || rev > 6 || fall < 480 || fall > 900 || span < 260 || span > 600 || maxRise > 40) continue;
  const score = rev * 10 + span / 20 - Math.abs(fall - 650) / 50 - maxRise / 10;
  best.push({score, p, fall: fall.toFixed(0), span: span.toFixed(0), rev, rotSpan: rotSpan.toFixed(0), maxRise: maxRise.toFixed(0)});
}
best.sort((a, b) => b.score - a.score);
console.log(best.length, 'candidates');
for (const b of best.slice(0, 5)) console.log(JSON.stringify(b));
