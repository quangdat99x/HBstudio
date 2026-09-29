import React, {useEffect, useMemo} from 'react';
import * as THREE from 'three';
import {useLens, V3} from './Stage';

// Effects never write depth but are tested against it, so solid cut-outs in front hide them.
const ADD = {transparent: true, depthWrite: false, depthTest: true, blending: THREE.AdditiveBlending} as const;

// ---------- Particles: soft additive points with per-particle size, alpha and colour ----------

export type Particle = {x: number; y: number; z: number; size: number; alpha: number; color?: THREE.Color};

const P_VERT = /* glsl */ `
attribute float aSize;
attribute float aAlpha;
attribute vec3 aColor;
uniform float uScale;
varying float vAlpha;
varying vec3 vColor;
void main() {
  vec4 mv = modelViewMatrix * vec4(position, 1.0);
  gl_PointSize = min(512.0, aSize * uScale / max(0.1, -mv.z));
  gl_Position = projectionMatrix * mv;
  vAlpha = aAlpha;
  vColor = aColor;
}
`;
const P_FRAG = /* glsl */ `
varying float vAlpha;
varying vec3 vColor;
void main() {
  vec2 d = gl_PointCoord - 0.5;
  float r = length(d) * 2.0;
  float a = exp(-r * r * 5.0) * (1.0 - smoothstep(0.85, 1.0, r));
  float core = exp(-r * r * 40.0);
  gl_FragColor = vec4(mix(vColor, vec3(1.0), core * 0.6), a * vAlpha);
}
`;

export const Particles: React.FC<{count: number; get: (i: number) => Particle | null; color?: string; order?: number}> = ({
  count,
  get,
  color = '#ffb45a',
  order = 100000,
}) => {
  const lens = useLens();
  const {geometry, material} = useMemo(() => {
    const g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.BufferAttribute(new Float32Array(count * 3), 3));
    g.setAttribute('aSize', new THREE.BufferAttribute(new Float32Array(count), 1));
    g.setAttribute('aAlpha', new THREE.BufferAttribute(new Float32Array(count), 1));
    g.setAttribute('aColor', new THREE.BufferAttribute(new Float32Array(count * 3), 3));
    const m = new THREE.ShaderMaterial({vertexShader: P_VERT, fragmentShader: P_FRAG, uniforms: {uScale: {value: 1712}}, ...ADD});
    return {geometry: g, material: m};
  }, [count]);
  const base = useMemo(() => new THREE.Color(color), [color]);
  const pos = geometry.attributes.position as THREE.BufferAttribute;
  const size = geometry.attributes.aSize as THREE.BufferAttribute;
  const alpha = geometry.attributes.aAlpha as THREE.BufferAttribute;
  const col = geometry.attributes.aColor as THREE.BufferAttribute;
  for (let i = 0; i < count; i++) {
    const p = get(i);
    if (!p) {
      alpha.setX(i, 0);
      size.setX(i, 0);
      continue;
    }
    pos.setXYZ(i, p.x, p.y, p.z);
    size.setX(i, p.size);
    alpha.setX(i, Math.max(0, p.alpha));
    const c = p.color ?? base;
    col.setXYZ(i, c.r, c.g, c.b);
  }
  pos.needsUpdate = size.needsUpdate = alpha.needsUpdate = col.needsUpdate = true;
  material.uniforms.uScale.value = lens.pxPerUnitAt1;
  return <points geometry={geometry} material={material} frustumCulled={false} renderOrder={order} />;
};

// ---------- Glow: a soft radial light on a plane ----------

const G_VERT = /* glsl */ `varying vec2 vUv; void main(){ vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`;
const G_FRAG = /* glsl */ `
uniform vec3 uColor;
uniform float uIntensity;
uniform float uFalloff;
varying vec2 vUv;
void main() {
  vec2 d = (vUv - 0.5) * 2.0;
  float r = length(d);
  float a = exp(-r * r * uFalloff) * (1.0 - smoothstep(0.35, 1.0, r));
  gl_FragColor = vec4(uColor, a * uIntensity);
}
`;

export const Glow: React.FC<{pos: V3; w: number; h?: number; color: string; intensity: number; falloff?: number; rot?: number; order?: number}> = ({
  pos,
  w,
  h,
  color,
  intensity,
  falloff = 3,
  rot = 0,
  order,
}) => {
  const material = useMemo(
    () => new THREE.ShaderMaterial({vertexShader: G_VERT, fragmentShader: G_FRAG, uniforms: {uColor: {value: new THREE.Color()}, uIntensity: {value: 0}, uFalloff: {value: 3}}, ...ADD}),
    [],
  );
  material.uniforms.uColor.value.set(color);
  material.uniforms.uIntensity.value = intensity;
  material.uniforms.uFalloff.value = falloff;
  if (intensity <= 0.001) return null;
  return (
    <mesh position={pos} rotation={[0, 0, rot]} scale={[w, h ?? w, 1]} material={material} frustumCulled={false} renderOrder={order ?? Math.round(pos[2] * 100) + 1}>
      <planeGeometry args={[1, 1]} />
    </mesh>
  );
};

// ---------- Dark pool: normal-blended soft black ellipse (shadows, the pit) ----------

const D_FRAG = /* glsl */ `
uniform vec3 uColor;
uniform float uIntensity;
varying vec2 vUv;
void main() {
  vec2 d = (vUv - 0.5) * 2.0;
  float r = length(d);
  float a = 1.0 - smoothstep(0.55, 1.0, r);
  gl_FragColor = vec4(uColor, a * uIntensity);
}
`;
export const Shade: React.FC<{pos: V3; w: number; h: number; color?: string; intensity: number; order?: number}> = ({pos, w, h, color = '#000000', intensity, order}) => {
  const material = useMemo(
    () => new THREE.ShaderMaterial({vertexShader: G_VERT, fragmentShader: D_FRAG, uniforms: {uColor: {value: new THREE.Color()}, uIntensity: {value: 0}}, transparent: true, depthWrite: false, depthTest: false}),
    [],
  );
  material.uniforms.uColor.value.set(color);
  material.uniforms.uIntensity.value = intensity;
  if (intensity <= 0.001) return null;
  return (
    <mesh position={pos} scale={[w, h, 1]} material={material} frustumCulled={false} renderOrder={order ?? Math.round(pos[2] * 100) + 1}>
      <planeGeometry args={[1, 1]} />
    </mesh>
  );
};

// ---------- Streak: a light trail from tail to head in the XY plane ----------

const S_FRAG = /* glsl */ `
uniform vec3 uColor;
uniform float uIntensity;
uniform float uTaper;
varying vec2 vUv;
void main() {
  float across = 1.0 - abs(vUv.y - 0.5) * 2.0;
  float a = pow(vUv.x, uTaper) * pow(across, 1.6);
  vec3 c = mix(uColor, vec3(1.0), pow(vUv.x, 6.0) * across);
  gl_FragColor = vec4(c, a * uIntensity);
}
`;
export const Streak: React.FC<{tail: V3; head: V3; width: number; color: string; intensity: number; taper?: number; order?: number}> = ({
  tail,
  head,
  width,
  color,
  intensity,
  taper = 2.2,
  order,
}) => {
  const material = useMemo(
    () => new THREE.ShaderMaterial({vertexShader: G_VERT, fragmentShader: S_FRAG, uniforms: {uColor: {value: new THREE.Color()}, uIntensity: {value: 0}, uTaper: {value: 2.2}}, ...ADD}),
    [],
  );
  material.uniforms.uColor.value.set(color);
  material.uniforms.uIntensity.value = intensity;
  material.uniforms.uTaper.value = taper;
  const dx = head[0] - tail[0];
  const dy = head[1] - tail[1];
  const len = Math.hypot(dx, dy);
  if (len < 1e-3 || intensity <= 0) return null;
  const mid: V3 = [(head[0] + tail[0]) / 2, (head[1] + tail[1]) / 2, (head[2] + tail[2]) / 2];
  return (
    <mesh position={mid} rotation={[0, 0, Math.atan2(dy, dx)]} scale={[len, width, 1]} material={material} frustumCulled={false} renderOrder={order ?? Math.round(mid[2] * 100) + 2}>
      <planeGeometry args={[1, 1]} />
    </mesh>
  );
};

// ---------- Beam: a glowing tube along a 3D curve, drawn up to `progress` ----------

export const Beam: React.FC<{points: V3[]; progress: number; radius: number; color: string; opacity: number; order?: number}> = ({
  points,
  progress,
  radius,
  color,
  opacity,
  order = 50000,
}) => {
  const key = points.map((p) => p.map((v) => v.toFixed(3)).join(',')).join(';') + progress.toFixed(3);
  const geometries = useMemo(() => {
    if (progress <= 0.01) return null;
    const full = new THREE.CatmullRomCurve3(points.map((p) => new THREE.Vector3(...p)));
    const n = Math.max(2, Math.round(40 * progress));
    const part = Array.from({length: n + 1}, (_, i) => full.getPoint((i / n) * progress));
    const curve = new THREE.CatmullRomCurve3(part);
    return [new THREE.TubeGeometry(curve, n * 2, radius, 8, false), new THREE.TubeGeometry(curve, n * 2, radius * 3.2, 8, false)];
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, radius]);
  useEffect(() => () => geometries?.forEach((g) => g.dispose()), [geometries]);
  const core = useMemo(() => new THREE.MeshBasicMaterial({...ADD, color: new THREE.Color(color)}), [color]);
  const halo = useMemo(() => new THREE.MeshBasicMaterial({...ADD, color: new THREE.Color(color)}), [color]);
  core.opacity = opacity;
  halo.opacity = opacity * 0.22;
  if (!geometries) return null;
  // Both passes stay within [order, order + 0.1] so a beam can be slotted between its owner's
  // colour pass and depth pass (see Plate): then the owner's own wings never hide it.
  return (
    <group>
      <mesh geometry={geometries[1]} material={halo} renderOrder={order} frustumCulled={false} />
      <mesh geometry={geometries[0]} material={core} renderOrder={order + 0.05} frustumCulled={false} />
    </group>
  );
};

// ---------- Chain: real 3D torus links along a quadratic curve ----------

const LINK = new THREE.TorusGeometry(0.085, 0.022, 8, 20);
LINK.scale(1.7, 1, 1);

export const Chain: React.FC<{
  from: V3;
  to: V3;
  bow: V3;
  links: number;
  shown: number;
  color: string;
  glowColor?: string;
  opacity: number;
  order?: number;
}> = ({from, to, bow, links, shown, color, glowColor = '#ffe7a8', opacity, order = 60000}) => {
  // Solid gold links (visible even across white wings) inside an additive halo of light.
  const mat = useMemo(() => new THREE.MeshBasicMaterial({transparent: true, depthWrite: false, depthTest: true, color: new THREE.Color(color)}), [color]);
  const glow = useMemo(() => new THREE.MeshBasicMaterial({...ADD, color: new THREE.Color(glowColor)}), [glowColor]);
  mat.opacity = opacity;
  glow.opacity = opacity * 0.25;
  const a = new THREE.Vector3(...from);
  const b = new THREE.Vector3(...to);
  const c = new THREE.Vector3((from[0] + to[0]) / 2 + bow[0], (from[1] + to[1]) / 2 + bow[1], (from[2] + to[2]) / 2 + bow[2]);
  const curve = new THREE.QuadraticBezierCurve3(a, c, b);
  const len = curve.getLength();
  const count = Math.min(links, Math.floor(len / 0.2));
  const visible = Math.floor(shown * count);
  const items = [];
  const up = new THREE.Vector3(0, 0, 1);
  for (let k = 0; k < visible; k++) {
    const t = k / Math.max(1, count - 1);
    const p = curve.getPointAt(t);
    const tan = curve.getTangentAt(t).normalize();
    const side = new THREE.Vector3().crossVectors(tan, up).normalize();
    const n = new THREE.Vector3().crossVectors(side, tan).normalize();
    const m = new THREE.Matrix4().makeBasis(tan, k % 2 ? n : side, k % 2 ? side.clone().negate() : n);
    const q = new THREE.Quaternion().setFromRotationMatrix(m);
    items.push(
      <group key={k} position={p} quaternion={q}>
        <mesh geometry={LINK} material={mat} renderOrder={order + 1} frustumCulled={false} />
        <mesh geometry={LINK} material={glow} scale={1.9} renderOrder={order} frustumCulled={false} />
      </group>,
    );
  }
  return <group>{items}</group>;
};

// ---------- CanvasPlate: a plane textured by a 2D canvas redrawn every frame ----------

export const CanvasPlate: React.FC<{
  pos: V3;
  size: number;
  px?: number;
  draw: (ctx: CanvasRenderingContext2D, px: number) => void;
  opacity?: number;
  order?: number;
}> = ({pos, size, px = 1024, draw, opacity = 1, order}) => {
  const {canvas, texture, material} = useMemo(() => {
    const cv = document.createElement('canvas');
    cv.width = cv.height = px;
    const t = new THREE.CanvasTexture(cv);
    t.colorSpace = THREE.NoColorSpace;
    const m = new THREE.MeshBasicMaterial({map: t, ...ADD});
    return {canvas: cv, texture: t, material: m};
  }, [px]);
  const ctx = canvas.getContext('2d')!;
  ctx.clearRect(0, 0, px, px);
  draw(ctx, px);
  texture.needsUpdate = true;
  material.opacity = opacity;
  return (
    <mesh position={pos} scale={[size, size, 1]} material={material} frustumCulled={false} renderOrder={order ?? Math.round(pos[2] * 100) + 3}>
      <planeGeometry args={[1, 1]} />
    </mesh>
  );
};
