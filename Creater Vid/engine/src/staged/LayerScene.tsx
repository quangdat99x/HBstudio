import React from 'react';
import {Easing, interpolate, useCurrentFrame} from 'remotion';
import {Plate} from '../engine/Plate';
import {Shot, Stage, V3} from '../engine/Stage';
import {useTextures} from '../engine/textures';
import {LETTERBOX} from '../components/Overlays';
import {clamp, mix} from '../lib/anim';
import {FPS, HEIGHT, WIDTH} from '../timeline';

// A layered scene: 2-4 layers painted separately by the image model (staged/layerkit.py), each a full-frame card
// at its depth. At the start pose they line up into one picture; the camera moves for real and the layers part
// by their depth. Nothing else: no code-drawn objects. Optional effects are added per scene only when approved.

export type LayerCfg = {scene: string; aspect: number; layers: {name: string; file: string; z: number; cutout: boolean}[]};
export type Move = 'push-in' | 'pull-out' | 'truck-left' | 'truck-right' | 'crane-down' | 'crane-up' | 'orbit-left' | 'orbit-right'
  | 'push-truck-right' | 'push-truck-left' | 'drift';

const FOV = 35;
const TAN = Math.tan(((FOV / 2) * Math.PI) / 180);
const ASPECT = WIDTH / HEIGHT;
const BAND = (HEIGHT - 2 * LETTERBOX) / HEIGHT; // share of the frame height between the letterbox bars

// Camera path in units of the subject distance zs (the same move reads the same at any scale). a = strength.
// x right, y up, z toward the scene is negative.
const path = (move: Move, zs: number, a: number): {from: V3; to: V3} => {
  const s = zs * a;
  const P = (x: number, y: number, z: number): V3 => [x * s, y * s, z * s];
  switch (move) {
    case 'push-in': return {from: P(0, 0.01, 0), to: P(0, -0.005, -0.1)};
    case 'pull-out': return {from: P(0, -0.005, -0.1), to: P(0, 0.01, 0)};
    case 'truck-left': return {from: P(0.06, 0, -0.04), to: P(-0.06, 0, -0.04)};
    case 'truck-right': return {from: P(-0.06, 0, -0.04), to: P(0.06, 0, -0.04)};
    case 'crane-down': return {from: P(0, 0.06, 0), to: P(0, -0.01, -0.06)};
    case 'crane-up': return {from: P(0, -0.01, -0.06), to: P(0, 0.06, 0)};
    case 'orbit-left': return {from: P(0.06, 0.008, -0.03), to: P(-0.06, 0, -0.1)};
    case 'orbit-right': return {from: P(-0.06, 0.008, -0.03), to: P(0.06, 0, -0.1)};
    case 'push-truck-left': return {from: P(0.04, 0.006, 0), to: P(-0.03, -0.003, -0.08)};
    case 'push-truck-right': return {from: P(-0.04, 0.006, 0), to: P(0.03, -0.003, -0.08)};
    default: return {from: P(-0.02, 0, -0.02), to: P(0.02, 0, -0.06)}; // drift
  }
};

// Height a card at depth z must have so that no frame of the path (camera aimed at the subject) sees past its
// edges: the start frame at that depth, enlarged by how far the camera wanders from its start.
const cardHeight = (z: number, cfgAspect: number, from: V3, to: V3, fx: number, fy: number) => {
  let need = 0;
  for (let k = 0; k <= 8; k++) {
    const q = k / 8;
    const c: V3 = [mix(from[0], to[0], q), mix(from[1], to[1], q), mix(from[2], to[2], q)];
    const dist = z + c[2]; // distance from camera to the card plane
    // the camera keeps turning toward the subject, so only part of its sideways travel shows the card edges
    const halfH = dist * TAN * BAND + Math.abs(c[1] - from[1]) * 0.6;
    const halfW = dist * TAN * ASPECT + Math.abs(c[0] - from[0]) * 0.6;
    // the framing centre (fx, fy) need not be the picture's centre: the nearer edge limits the card
    need = Math.max(need, halfH / Math.min(fy, 1 - fy), halfW / (cfgAspect * Math.min(fx, 1 - fx)));
  }
  return need * 1.02;
};

export const LayerScene: React.FC<{
  cfg: LayerCfg;
  duration: number;
  move: Move;
  strength?: number;
  frame?: [number, number];   // picture point at the centre of the shot (x, y fractions): heads near the top -> y < 0.5
  focusLayer?: string;        // the layer in focus (default: the second one, usually the people)
  children?: (t: number) => React.ReactNode; // approved extras only
}> = ({cfg, duration, move, strength = 1, frame = [0.5, 0.5], focusLayer, children}) => {
  const f = useCurrentFrame();
  const t = f / FPS;
  const paths = Object.fromEntries(cfg.layers.map((l) => [l.name, l.file])) as Record<string, string>;
  const tex = useTextures(paths);
  if (!tex) return null;
  const focus = cfg.layers.find((l) => l.name === focusLayer) ?? cfg.layers[Math.min(1, cfg.layers.length - 1)];
  const zs = focus.z;
  const {from, to} = path(move, zs, strength);
  const p = interpolate(f, [0, duration], [0, 1], {...clamp, easing: Easing.inOut(Easing.sin)});
  const pos: V3 = [mix(from[0], to[0], p), mix(from[1], to[1], p), mix(from[2], to[2], p)];
  // the framing centre of the picture lies on the start line of sight, at every depth, so the stack lines up
  // into the painted composition when the shot begins
  const [fx, fy] = frame;
  const look: V3 = [0, 0, -zs];
  const shot: Shot = {pos, target: [look[0] + (pos[0] - from[0]) * 0.35, look[1] + (pos[1] - from[1]) * 0.35, look[2]], fov: FOV,
    focus: zs + pos[2], aperture: 0.8};
  return (
    <Stage shot={shot}>
      {cfg.layers.map((l, i) => {
        const h = cardHeight(l.z, cfg.aspect, from, to, fx, fy) * (i === 0 ? 1.06 : 1);
        const k = (l.z + from[2]) / (zs + from[2]);
        // card centre: on the start ray, shifted so that its point (fx, fy) sits on that ray
        const cx = from[0] + (look[0] - from[0]) * k + (0.5 - fx) * h * cfg.aspect;
        const cy = from[1] + (look[1] - from[1]) * k + (fy - 0.5) * h;
        return (
          <Plate key={l.name} tex={tex[l.name]} aspect={cfg.aspect} pos={[cx, cy, -l.z]} height={h}
            dof={i !== 0} blur={i === 0 ? 0.25 : 0} order={-Math.round(l.z * 100)} />
        );
      })}
      {children?.(t)}
    </Stage>
  );
};
