import * as THREE from 'three';
import type {V3} from './Stage';

// Rig landmarks of a character image, in image coordinates (x from left, y from top, 0..1).
// Measure them from the pixels (scripts/measure.mjs), never by eye on a coarse grid.
// pivotX: shoulder offset from the centre line; body: half-width that never bends with the wings;
// feet: lowest opaque row; hemTop: where the robe starts to sway; hands: attachment points.
export type Rig = {
  pivotX: number;
  pivotY: number;
  body: number;
  feet: number;
  hemTop: number;
  hands?: Array<[number, number]>;
};

// CPU copy of the vertex-shader warp in Plate.tsx. Anything attached to a character (beams,
// chains, glows on the hands) goes through exactly the same deformation and transform as the
// pixels it sits on, so it stays glued to them whatever the wings and the camera do.
export type WarpParams = {flap: number; phase: number; bend: number; cloth: number; breath: number; time: number};

const smoothstep = (a: number, b: number, x: number) => {
  const t = Math.min(1, Math.max(0, (x - a) / (b - a)));
  return t * t * (3 - 2 * t);
};

// uv: x from left, y from bottom (three.js convention). Returns warped uv.
export const warpUv = (u: number, v: number, aspect: number, rig: Rig, w: WarpParams): [number, number] => {
  const px = u * aspect;
  const py = v;
  const cx = 0.5 * aspect;
  const side = px >= cx ? 1 : -1;
  const pivX = (0.5 + side * rig.pivotX) * aspect;
  const pivY = 1 - rig.pivotY;
  const wing = smoothstep(rig.body * aspect, (rig.body + 0.09) * aspect, Math.abs(px - cx));
  const dist = Math.hypot(px - pivX, py - pivY);
  let s = w.phase - dist * w.bend;
  s += 0.35 * Math.sin(s);
  const ang = side * wing * w.flap * Math.sin(s) * (0.6 + 0.8 * dist);
  const dx = px - pivX;
  const dy = py - pivY;
  let rx = pivX + Math.cos(ang) * dx - Math.sin(ang) * dy;
  let ry = pivY + Math.sin(ang) * dx + Math.cos(ang) * dy;
  const hemTop = 1 - rig.hemTop;
  const hem = 1 - smoothstep(0, hemTop, py);
  rx += w.cloth * hem * hem * Math.sin(w.time * 1.9 + py * 11) * (1 - wing);
  const feetV = 1 - rig.feet;
  ry = feetV + (ry - feetV) * (1 + w.breath);
  return [rx / aspect, ry];
};

// World position of an image point (ix from left, iy from top) on a plate that is centred at
// `center`, rotated by `rot` (x, y, z Euler) and `height` tall. `lift` pushes the point toward
// the viewer so a beam starting on the hand is not hidden inside the plate's own depth.
export const platePointWarped = (
  opts: {center: V3; rot: V3; height: number; aspect: number; rig?: Rig; warp?: WarpParams},
  ix: number,
  iy: number,
  lift = 0.15,
): V3 => {
  let u = ix;
  let v = 1 - iy;
  if (opts.rig && opts.warp) [u, v] = warpUv(u, v, opts.aspect, opts.rig, opts.warp);
  const local = new THREE.Vector3((u - 0.5) * opts.height * opts.aspect, (v - 0.5) * opts.height, lift);
  local.applyEuler(new THREE.Euler(...opts.rot));
  return [local.x + opts.center[0], local.y + opts.center[1], local.z + opts.center[2]];
};
