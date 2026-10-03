// Falling-feather physics: a thin plate in 2D (y up) under gravity with quasi-steady
// aerodynamics. Normal drag is much larger than tangential drag, lift ~ sin(2α), and the
// centre of pressure pitches the plate nose-up while it glides. Together these produce the
// real "falling leaf" motion: glide, pitch up, stall, slide back, with the fastest descent
// at the bottom of each swing. Deterministic; returns one sample per video frame.
export function simulateFeather({
  frames,
  fps = 30,
  x0 = 0,
  y0 = 0,
  // Tuned by scripts/feather-search.mjs: 3 clean swings, |rot| < 55 deg, no tumbling.
  theta0 = 0.922,
  g = 1690.8,
  cn = 0.2286,
  ct = 0.005527,
  cl = 0.02326,
  ktorque = 0.000546,
  kspin = 5.66,
  gust = 18,
  seed = 1,
  substeps = 12,
}) {
  let x = x0;
  let y = y0;
  let vx = 0;
  let vy = 0;
  let th = theta0;
  let w = 0;
  const dt = 1 / (fps * substeps);
  const out = [];
  // smooth deterministic gust
  const gustAt = (t) =>
    gust * (Math.sin(t * 0.9 + seed) * 0.6 + Math.sin(t * 2.3 + seed * 3.1) * 0.3 + Math.sin(t * 5.1 + seed * 7.7) * 0.1);
  for (let f = 0; f < frames; f++) {
    out.push({x, y, rot: th, vx, vy});
    for (let s = 0; s < substeps; s++) {
      const t = (f * substeps + s) * dt;
      const rvx = vx - gustAt(t);
      const rvy = vy;
      const sp = Math.hypot(rvx, rvy) + 1e-6;
      const tx = Math.cos(th);
      const ty = Math.sin(th);
      const u = rvx * tx + rvy * ty; // along chord
      const v = -rvx * ty + rvy * tx; // normal to chord
      // drag in body frame
      let ax = -sp * (ct * u * tx - cn * v * ty);
      let ay = -sp * (ct * u * ty + cn * v * tx);
      // lift, perpendicular to the relative velocity
      const lift = -cl * u * v;
      ax += lift * (-rvy / sp);
      ay += lift * (rvx / sp);
      ay -= g;
      const aw = -ktorque * u * v * sp * 0.01 - kspin * w;
      vx += ax * dt;
      vy += ay * dt;
      w += aw * dt;
      x += vx * dt;
      y += vy * dt;
      th += w * dt;
    }
  }
  return out;
}
