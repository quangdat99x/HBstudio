import {random} from 'remotion';

export type Pt = [number, number];

const lattice = (seed: string, i: number) => random(`${seed}:${i}`) * 2 - 1;

// Smooth 1D value noise in [-1, 1].
export const noise1 = (seed: string, x: number) => {
  const i = Math.floor(x);
  const t = x - i;
  const u = t * t * (3 - 2 * t);
  return lattice(seed, i) * (1 - u) + lattice(seed, i + 1) * u;
};

export const fbm = (seed: string, x: number, octaves = 4) => {
  let amp = 0.5;
  let freq = 1;
  let sum = 0;
  for (let o = 0; o < octaves; o++) {
    sum += amp * noise1(`${seed}${o}`, x * freq);
    amp *= 0.5;
    freq *= 2.13;
  }
  return sum;
};

// A mountain skyline through the control points, roughened by fractal noise.
// Higher ground (smaller y) gets rougher.
export const ridge = (ctrl: Pt[], seed: string, rough: number, step = 8): Pt[] => {
  const pts: Pt[] = [];
  for (let s = 0; s < ctrl.length - 1; s++) {
    const [x0, y0] = ctrl[s];
    const [x1, y1] = ctrl[s + 1];
    const n = Math.max(1, Math.round((x1 - x0) / step));
    for (let k = 0; k < n; k++) {
      const t = k / n;
      const x = x0 + (x1 - x0) * t;
      const base = y0 + (y1 - y0) * t;
      pts.push([x, base + fbm(seed, x / 90) * (1080 - base) * rough]);
    }
  }
  pts.push(ctrl[ctrl.length - 1]);
  return pts;
};

export const ridgeY = (pts: Pt[], x: number) => {
  for (let i = 0; i < pts.length - 1; i++) {
    const [x0, y0] = pts[i];
    const [x1, y1] = pts[i + 1];
    if (x >= x0 && x <= x1) return y0 + (y1 - y0) * ((x - x0) / (x1 - x0 || 1));
  }
  return pts[pts.length - 1][1];
};

export const fillPath = (pts: Pt[], bottom = 1500) =>
  `M${pts[0][0]} ${bottom}` +
  pts.map(([x, y]) => `L${x.toFixed(1)} ${y.toFixed(1)}`).join('') +
  `L${pts[pts.length - 1][0]} ${bottom}Z`;

export const linePath = (pts: Pt[]) =>
  pts.map(([x, y], i) => `${i ? 'L' : 'M'}${x.toFixed(1)} ${y.toFixed(1)}`).join('');
