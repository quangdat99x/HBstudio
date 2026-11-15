import React, {useMemo} from 'react';
import * as THREE from 'three';
import {random} from 'remotion';
import type {V3} from './Stage';

// Hot sparks and embers as motion-blurred streaks: each one is a camera-facing ribbon from where it was a
// shutter-time ago to where it is now, coloured by its temperature (white-yellow, orange, dull red) and
// brighter than white when hot, so the bloom pass makes it glow.

export type Spark = {p: V3; v: V3; heat: number; width: number; alpha: number};

const VERT = /* glsl */ `
attribute vec3 aTail;
attribute vec3 aHead;
attribute vec2 aCorner;   // x: 0 tail / 1 head, y: -1 / +1 side
attribute float aWidth;
attribute float aHeat;
attribute float aAlpha;
varying float vSide;
varying float vAlong;
varying float vHeat;
varying float vAlpha;
void main() {
  vec4 t = modelViewMatrix * vec4(aTail, 1.0);
  vec4 h = modelViewMatrix * vec4(aHead, 1.0);
  vec2 d = h.xy - t.xy;
  float len = length(d);
  vec2 dir = len > 1e-5 ? d / len : vec2(1.0, 0.0);
  vec2 side = vec2(-dir.y, dir.x);
  vec4 p = mix(t, h, aCorner.x);
  // round the ends a little: extend by half a width past both ends
  p.xy += dir * (aCorner.x - 0.5) * aWidth + side * aCorner.y * aWidth * 0.5;
  gl_Position = projectionMatrix * p;
  vSide = aCorner.y;
  vAlong = aCorner.x;
  vHeat = aHeat;
  vAlpha = aAlpha;
}
`;

const FRAG = /* glsl */ `
varying float vSide;
varying float vAlong;
varying float vHeat;
varying float vAlpha;
vec3 heatColor(float h) {
  // dull red -> orange -> yellow -> white-hot, HDR when hot
  vec3 c = mix(vec3(0.55, 0.06, 0.01), vec3(1.0, 0.35, 0.05), smoothstep(0.0, 0.35, h));
  c = mix(c, vec3(1.0, 0.72, 0.28), smoothstep(0.35, 0.7, h));
  c = mix(c, vec3(1.0, 0.95, 0.8), smoothstep(0.7, 1.0, h));
  return c * (0.6 + 2.4 * h * h);
}
void main() {
  float across = 1.0 - vSide * vSide;
  float along = 0.35 + 0.65 * vAlong;          // the head is the brightest part
  float a = across * across * along * vAlpha;
  gl_FragColor = vec4(heatColor(vHeat) * a, 1.0);
}
`;

export const SparkStreaks: React.FC<{sparks: Spark[]; shutter: number; max: number; order?: number}> = ({sparks, shutter, max, order = 200000}) => {
  const {geometry, material} = useMemo(() => {
    const g = new THREE.BufferGeometry();
    const n = max * 6;
    const corner = new Float32Array(n * 2);
    const quad = [[0, -1], [1, -1], [1, 1], [0, -1], [1, 1], [0, 1]];
    for (let i = 0; i < max; i++) quad.forEach(([a, b], k) => corner.set([a, b], (i * 6 + k) * 2));
    g.setAttribute('position', new THREE.BufferAttribute(new Float32Array(n * 3), 3));
    g.setAttribute('aTail', new THREE.BufferAttribute(new Float32Array(n * 3), 3));
    g.setAttribute('aHead', new THREE.BufferAttribute(new Float32Array(n * 3), 3));
    g.setAttribute('aCorner', new THREE.BufferAttribute(corner, 2));
    g.setAttribute('aWidth', new THREE.BufferAttribute(new Float32Array(n), 1));
    g.setAttribute('aHeat', new THREE.BufferAttribute(new Float32Array(n), 1));
    g.setAttribute('aAlpha', new THREE.BufferAttribute(new Float32Array(n), 1));
    const m = new THREE.ShaderMaterial({
      vertexShader: VERT,
      fragmentShader: FRAG,
      transparent: true,
      depthWrite: false,
      depthTest: true,
      blending: THREE.AdditiveBlending,
    });
    return {geometry: g, material: m};
  }, [max]);
  const A = geometry.attributes as Record<string, THREE.BufferAttribute>;
  for (let i = 0; i < max; i++) {
    const s = sparks[i];
    for (let k = 0; k < 6; k++) {
      const j = i * 6 + k;
      if (!s) {
        A.aAlpha.setX(j, 0);
        A.aWidth.setX(j, 0);
        continue;
      }
      A.aHead.setXYZ(j, s.p[0], s.p[1], s.p[2]);
      A.aTail.setXYZ(j, s.p[0] - s.v[0] * shutter, s.p[1] - s.v[1] * shutter, s.p[2] - s.v[2] * shutter);
      A.position.setXYZ(j, s.p[0], s.p[1], s.p[2]);
      A.aWidth.setX(j, s.width);
      A.aHeat.setX(j, s.heat);
      A.aAlpha.setX(j, s.alpha);
    }
  }
  for (const k of ['position', 'aTail', 'aHead', 'aWidth', 'aHeat', 'aAlpha']) A[k].needsUpdate = true;
  return <mesh geometry={geometry} material={material} frustumCulled={false} renderOrder={order} />;
};

// Sparks thrown off a hammer blow: ballistic, with air drag, bouncing once or twice on the floor, cooling as
// they fly. Deterministic per (seed, index), integrated from the moment of the blow to now.
export const blowSparks = (seed: string, origin: V3, age: number, count: number, o: {speed?: number; gravity?: number; floor?: number; spread?: number} = {}): Spark[] => {
  const {speed = 9, gravity = 30, floor = -1e9, spread = 1} = o;
  const out: Spark[] = [];
  if (age < 0) return out;
  const dt = 1 / 240;
  for (let i = 0; i < count; i++) {
    const r = (k: string) => random(`${seed}-${k}-${i}`);
    const life = 0.35 + 0.9 * r('life') ** 1.5;
    if (age > life) continue;
    const ang = Math.PI * (0.08 + 0.84 * r('a'));             // mostly up and sideways
    const sp = speed * (0.35 + 0.9 * r('v')) * spread;
    let vx = Math.cos(ang) * sp;
    let vy = Math.sin(ang) * sp * 0.8;
    let vz = (r('z') - 0.3) * sp * 0.6;                        // some fly toward the camera
    let x = origin[0];
    let y = origin[1];
    let z = origin[2];
    const drag = 1.2 + 2.5 * r('drag');
    for (let t = 0; t < age; t += dt) {
      vy -= gravity * dt;
      const k = Math.exp(-drag * dt);
      vx *= k;
      vy *= k;
      vz *= k;
      x += vx * dt;
      y += vy * dt;
      z += vz * dt;
      if (y < floor && vy < 0) {
        y = floor;
        vy = -vy * 0.3;
        vx *= 0.6;
        vz *= 0.6;
      }
    }
    const heat = Math.max(0, 1 - (age / life) * (0.8 + 0.4 * r('cool')));
    out.push({p: [x, y, z], v: [vx, vy, vz], heat, width: 0.018 + 0.03 * r('w'), alpha: Math.min(1, (life - age) / 0.12)});
  }
  return out;
};

// Embers rising from a fire: buoyant, wobbling in the draught, cooling and fading.
export const risingEmbers = (seed: string, mouth: {x: number; y: number; z: number; a: number}, t: number, rate: number, o: {rise?: number; life?: number} = {}): Spark[] => {
  const {rise = 1.6, life = 2.2} = o;
  const out: Spark[] = [];
  const first = Math.floor((t - life * 1.6) * rate);
  for (let n = Math.max(0, first); n <= t * rate; n++) {
    const r = (k: string) => random(`${seed}-${k}-${n}`);
    const born = (n + r('jit')) / rate;
    const L = life * (0.5 + r('life'));
    const age = t - born;
    if (age < 0 || age > L) continue;
    const u = age / L;
    const sway = Math.sin(age * (2 + 3 * r('f')) + r('ph') * 6.28) * 0.18 * u + Math.sin(age * 0.9 + n) * 0.1 * u;
    const up = rise * (0.6 + 0.8 * r('v'));
    const x = mouth.x + (r('x') - 0.5) * 2 * mouth.a * 0.7 + sway + (r('drift') - 0.4) * 0.5 * age;
    const y = mouth.y + up * age - 0.08 * age * age;
    const z = mouth.z + (r('z') - 0.5) * 0.3;
    const vy = up - 0.16 * age;
    const vx = Math.cos(age * (2 + 3 * r('f')) + r('ph') * 6.28) * 0.3 * u;
    const heat = 0.75 * (1 - u) * (0.7 + 0.3 * Math.sin(age * 20 + n));
    out.push({p: [x, y, z], v: [vx, vy, 0], heat, width: 0.02 + 0.02 * r('w'), alpha: Math.min(1, age / 0.15) * (1 - u * u)});
  }
  return out;
};
