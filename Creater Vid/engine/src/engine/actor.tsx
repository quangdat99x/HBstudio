import React from 'react';
import * as THREE from 'three';
import {random} from 'remotion';
import {Plate, PlateProps} from './Plate';
import {Particle} from './Fx';
import {platePointWarped, Rig, WarpParams} from './rig';
import type {V3} from './Stage';

export const TAU = Math.PI * 2;

// Visible frame height at distance d for the default 35 degree lens.
export const frameH = (d: number, fov = 35) => 2 * d * Math.tan(((fov / 2) * Math.PI) / 180);

export type ImgInfo = {src: string; aspect: number};

// One source of truth for a rigged character: the props its plate is drawn with, and a
// function giving the world position of any image point on it after the same wing/robe warp
// and rotation, so attachments (beams, chains, glows) stay exactly on the pixels.
export const makeActor = (o: {
  img: ImgInfo;
  rig: Rig;
  t: number; // seconds
  pos: V3; // feet position
  height: number;
  amp?: number; // wing beat amplitude (radians)
  hz?: number; // wing beats per second
  ph?: number; // phase offset
  cloth?: number;
  rotX?: number;
  rotY?: number;
  rot?: number;
}) => {
  const {img, rig, t, pos, height, amp = 0.05, hz = 0.35, ph = 0, cloth = 0.006, rotX = 0, rotY = 0, rot = 0} = o;
  const aspect = img.aspect;
  const warp: WarpParams = {flap: amp, phase: t * TAU * hz + ph, bend: 3.2, cloth, breath: 0.004 * Math.sin(t * 1.3 + ph), time: t + ph};
  const center: V3 = [pos[0], pos[1] - (0.5 - rig.feet) * height, pos[2]];
  const at = (ix: number, iy: number, lift = 0.15) => platePointWarped({center, rot: [rotX, rotY, rot], height, aspect, rig, warp}, ix, iy, lift);
  return {
    // Draw order of the plate's colour pass; the actor's own attachments use order + 0.25
    // (between its colour pass and its depth pass) so its own wings never hide them.
    order: Math.round(center[2] * 100),
    plate: {
      aspect,
      rig,
      anchor: 'feet' as const,
      pos,
      height,
      flap: warp.flap,
      phase: warp.phase,
      bend: warp.bend,
      cloth: warp.cloth,
      breath: warp.breath,
      time: warp.time,
      rotX,
      rotY,
      rot,
    },
    point: at,
    hands: (lift = 0.15) => (rig.hands ?? []).map(([ix, iy]) => at(ix, iy, lift)),
  };
};

export type ActorHandle = ReturnType<typeof makeActor>;

export const Actor: React.FC<{a: ActorHandle; tex: THREE.Texture} & Omit<PlateProps, 'tex' | 'aspect' | 'pos' | 'height'>> = ({a, tex, ...rest}) => (
  <Plate tex={tex} {...a.plate} {...rest} />
);

// Slow drifting motes in a box, looping forever (dust, embers, snow, sparks of light).
export const motes = (
  seed: string,
  t: number,
  box: {x: [number, number]; y: [number, number]; z: [number, number]},
  opts: {rise?: number; size?: number; alpha?: number; life?: number; color?: THREE.Color} = {},
) => {
  const {rise = 0.3, size = 0.08, alpha = 0.7, life = 6} = opts;
  return (i: number): Particle => {
    const r = (s: string) => random(`${seed}${s}${i}`);
    const period = life * (0.6 + 0.8 * r('p'));
    const age = ((t + r('o') * period * 5) % period) / period;
    const x = box.x[0] + r('x') * (box.x[1] - box.x[0]) + Math.sin(t * 0.4 + i) * 0.3;
    const y = box.y[0] + r('y') * (box.y[1] - box.y[0]) + rise * age * period;
    const z = box.z[0] + r('z') * (box.z[1] - box.z[0]);
    const flick = 0.6 + 0.4 * Math.sin(t * (2 + 3 * r('f')) + i);
    return {x, y, z, size: size * (0.5 + r('s')), alpha: alpha * Math.sin(Math.PI * age) * flick, color: opts.color};
  };
};
