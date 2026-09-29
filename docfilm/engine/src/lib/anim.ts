import {Easing, interpolate} from 'remotion';

export type Cam = {zoom: number; x: number; y: number; ox: number; oy: number};

export const clamp = {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'} as const;

export const mix = (a: number, b: number, t: number) => a + (b - a) * t;

export const f1 = (n: number) => n.toFixed(1);

export const ramp = (
  frame: number,
  a: number,
  b: number,
  from = 0,
  to = 1,
  easing: (t: number) => number = Easing.inOut(Easing.cubic),
) => interpolate(frame, [a, b], [from, to], {...clamp, easing});

// Decaying camera shake from a list of impact frames.
export const shake = (frame: number, hits: number[], amp: number, decay: number) => {
  let x = 0;
  let y = 0;
  for (const h of hits) {
    if (frame < h) continue;
    const d = frame - h;
    const e = Math.exp(-d / decay) * amp;
    x += e * Math.sin(d * 2.9 + h);
    y += e * Math.cos(d * 3.7 + h * 1.7);
  }
  return {x, y};
};

// 0 before `at`, jumps to 1 and fades out over `len` frames.
export const pulse = (frame: number, at: number, len: number) =>
  frame < at ? 0 : Math.max(0, 1 - (frame - at) / len) ** 2;
