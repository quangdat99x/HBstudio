import React, {useMemo} from 'react';
import * as THREE from 'three';
import type {Rig} from './rig';
import {useLens, V3} from './Stage';

const VERT = /* glsl */ `
uniform vec2 uSize;
uniform float uAspect;
uniform float uWarp;
uniform vec2 uPivotL;
uniform vec2 uPivotR;
uniform float uBody;
uniform float uFlap;
uniform float uPhase;
uniform float uBend;
uniform float uCloth;
uniform float uHemTop;
uniform float uFeetV;
uniform float uTime;
uniform float uBreath;
varying vec2 vUv;
varying float vWorldY;

vec2 rot2(vec2 p, vec2 c, float a) {
  vec2 d = p - c;
  float s = sin(a);
  float co = cos(a);
  return c + vec2(co * d.x - s * d.y, s * d.x + co * d.y);
}

void main() {
  vUv = uv;
  vec2 q = uv;
  if (uWarp > 0.5) {
    // Work in image space (x scaled by aspect) so rotations are not skewed.
    vec2 p = vec2(uv.x * uAspect, uv.y);
    float cx = 0.5 * uAspect;
    float side = p.x >= cx ? 1.0 : -1.0;
    vec2 piv = side > 0.0 ? vec2(uPivotR.x * uAspect, uPivotR.y) : vec2(uPivotL.x * uAspect, uPivotL.y);
    // 0 on the body, 1 on the wings, smooth in between: no seams.
    float w = smoothstep(uBody * uAspect, (uBody + 0.09) * uAspect, abs(p.x - cx));
    float dist = length(p - piv);
    // The flap travels outward as a wave: tips lag behind the shoulder (overlapping action)
    // and bend further than the inner feathers (follow-through).
    // Skewed wave: the downstroke is quicker than the recovery.
    float s = uPhase - dist * uBend;
    s += 0.35 * sin(s);
    float ang = side * w * uFlap * sin(s) * (0.6 + 0.8 * dist);
    vec2 r = rot2(p, piv, ang);
    // Robe hem sways, more toward the bottom, not on the wings.
    float hem = 1.0 - smoothstep(0.0, uHemTop, p.y);
    r.x += uCloth * hem * hem * sin(uTime * 1.9 + p.y * 11.0) * (1.0 - w);
    // Breathing: tiny vertical stretch anchored at the feet.
    r.y = uFeetV + (r.y - uFeetV) * (1.0 + uBreath);
    q = vec2(r.x / uAspect, r.y);
  }
  vec3 pos = vec3((q - 0.5) * uSize, 0.0);
  vWorldY = (modelMatrix * vec4(pos, 1.0)).y;
  gl_Position = projectionMatrix * modelViewMatrix * vec4(pos, 1.0);
}
`;

const FRAG = /* glsl */ `
uniform sampler2D map;
uniform float uOpacity;
uniform vec3 uTint;
uniform float uExposure;
uniform float uBlur;
uniform float uAspect;
uniform float uTexH;
uniform vec3 uFogColor;
uniform float uFog;
uniform float uReveal;
uniform float uRevealMode;
uniform float uRevealSoft;
uniform float uClipY;
varying vec2 vUv;
varying float vWorldY;

const vec2 P[12] = vec2[12](
  vec2(-0.326, -0.406), vec2(-0.840, -0.074), vec2(-0.696, 0.457), vec2(-0.203, 0.621),
  vec2(0.962, -0.195), vec2(0.473, -0.480), vec2(0.519, 0.767), vec2(0.185, -0.893),
  vec2(0.507, 0.064), vec2(0.896, 0.412), vec2(-0.322, -0.933), vec2(-0.792, -0.598)
);

// Premultiplied sampling so blurred cut-out edges don't pick up dark fringes.
vec4 pm(vec2 uv, float b) {
  vec4 c = texture2D(map, uv, b);
  c.rgb *= c.a;
  return c;
}

void main() {
  if (vWorldY < uClipY) discard;
  vec4 acc;
  if (uBlur < 0.02) {
    acc = pm(vUv, 0.0);
  } else {
    float r = uBlur * 0.005;
    float b = max(0.0, log2(r * uTexH / 2.5));
    acc = pm(vUv, b) * 0.25;
    for (int i = 0; i < 12; i++) acc += pm(vUv + P[i] * vec2(r / uAspect, r), b) * (0.75 / 12.0);
  }
  float a = acc.a;
  vec3 col = a > 0.0001 ? acc.rgb / a : vec3(0.0);
  col = mix(col * uTint * uExposure, uFogColor, uFog);
  if (uRevealMode > 0.5) {
    vec2 d = vUv - 0.5;
    float m;
    if (uRevealMode < 1.5) {
      float ang = fract(atan(d.x, d.y) / 6.2831853 + 1.0);
      m = 1.0 - smoothstep(uReveal - uRevealSoft, uReveal, ang);
    } else if (uRevealMode < 2.5) {
      m = 1.0 - smoothstep(uReveal - uRevealSoft, uReveal, vUv.x);
    } else {
      m = 1.0 - smoothstep(uReveal - uRevealSoft, uReveal, length(d) * 1.42);
    }
    a *= m;
  }
#ifdef DEPTH_PASS
  // Invisible second pass: only the solid part of the cut-out records its depth.
  if (a * uOpacity < 0.5) discard;
#endif
  gl_FragColor = vec4(col, a * uOpacity);
}
`;

export type PlateProps = {
  tex: THREE.Texture;
  aspect: number;
  pos: V3;
  height: number;
  anchor?: 'center' | 'feet' | 'bottom';
  rot?: number;
  rotX?: number;
  rotY?: number;
  opacity?: number;
  tint?: string;
  exposure?: number;
  blend?: 'normal' | 'add';
  fog?: number;
  fogColor?: string;
  blur?: number;
  dof?: boolean;
  rig?: Rig;
  flap?: number;
  phase?: number;
  bend?: number;
  cloth?: number;
  breath?: number;
  time?: number;
  reveal?: number;
  revealMode?: 0 | 1 | 2 | 3;
  revealSoft?: number;
  order?: number;
  segments?: number;
  clipBelow?: number; // world y under which the plate is cut away (sinking into the pit)
};

// World position of an image-space point (x from left, y from top) on a plate.
export const platePoint = (p: {pos: V3; height: number; aspect: number; anchor?: PlateProps['anchor']; rig?: Rig}, ix: number, iy: number): V3 => {
  const c = plateCenter(p);
  return [c[0] + (ix - 0.5) * p.height * p.aspect, c[1] + (0.5 - iy) * p.height, c[2]];
};

const plateCenter = ({pos, height, anchor = 'center', rig}: {pos: V3; height: number; anchor?: PlateProps['anchor']; rig?: Rig}): V3 => {
  if (anchor === 'bottom') return [pos[0], pos[1] + height / 2, pos[2]];
  if (anchor === 'feet') return [pos[0], pos[1] - (0.5 - (rig?.feet ?? 1)) * height, pos[2]];
  return pos;
};

export const Plate: React.FC<PlateProps> = (props) => {
  const {
    tex,
    aspect,
    height,
    rot = 0,
    rotX = 0,
    rotY = 0,
    opacity = 1,
    tint = '#ffffff',
    exposure = 1,
    blend = 'normal',
    fog = 0,
    fogColor = '#000000',
    blur = 0,
    dof = true,
    rig,
    flap = 0,
    phase = 0,
    bend = 3,
    cloth = 0,
    breath = 0,
    time = 0,
    reveal = 1,
    revealMode = 0,
    revealSoft = 0.02,
    order,
    segments,
  } = props;
  const lens = useLens();
  const center = plateCenter(props);
  const geometry = useMemo(() => new THREE.PlaneGeometry(1, 1, segments ?? (rig ? 72 : 1), segments ?? (rig ? 72 : 1)), [rig, segments]);
  const material = useMemo(
    () =>
      new THREE.ShaderMaterial({
        vertexShader: VERT,
        fragmentShader: FRAG,
        transparent: true,
        // Plates are painted back to front (renderOrder by depth) and always pass the depth test.
        depthTest: true,
        depthFunc: THREE.AlwaysDepth,
        depthWrite: false,
        blending: blend === 'add' ? THREE.AdditiveBlending : THREE.NormalBlending,
        uniforms: {
          map: {value: null},
          uSize: {value: new THREE.Vector2()},
          uAspect: {value: 1},
          uWarp: {value: 0},
          uPivotL: {value: new THREE.Vector2()},
          uPivotR: {value: new THREE.Vector2()},
          uBody: {value: 0.1},
          uFlap: {value: 0},
          uPhase: {value: 0},
          uBend: {value: 3},
          uCloth: {value: 0},
          uHemTop: {value: 0.4},
          uFeetV: {value: 0},
          uTime: {value: 0},
          uBreath: {value: 0},
          uOpacity: {value: 1},
          uTint: {value: new THREE.Color()},
          uExposure: {value: 1},
          uBlur: {value: 0},
          uTexH: {value: 1024},
          uFogColor: {value: new THREE.Color()},
          uFog: {value: 0},
          uReveal: {value: 1},
          uRevealMode: {value: 0},
          uRevealSoft: {value: 0.02},
          uClipY: {value: -1e6},
        },
      }),
    [blend],
  );
  // Solid cut-outs also record their depth, so particles, beams and chains drawn afterwards
  // are hidden behind whatever really stands in front of them.
  const depthMaterial = useMemo(
    () =>
      blend === 'add'
        ? null
        : new THREE.ShaderMaterial({
            vertexShader: VERT,
            fragmentShader: FRAG,
            defines: {DEPTH_PASS: 1},
            uniforms: material.uniforms,
            colorWrite: false,
            depthWrite: true,
            depthTest: true,
            depthFunc: THREE.AlwaysDepth,
            transparent: true,
          }),
    [blend, material],
  );
  const dist = Math.max(0.5, Math.abs(lens.z - center[2]));
  const dofBlur = dof ? lens.aperture * Math.abs(1 - lens.focus / dist) : 0;
  const u = material.uniforms;
  u.map.value = tex;
  u.uSize.value.set(height * aspect, height);
  u.uAspect.value = aspect;
  u.uTexH.value = (tex.image as {height?: number} | undefined)?.height ?? 1024;
  u.uWarp.value = rig ? 1 : 0;
  if (rig) {
    u.uPivotL.value.set(0.5 - rig.pivotX, 1 - rig.pivotY);
    u.uPivotR.value.set(0.5 + rig.pivotX, 1 - rig.pivotY);
    u.uBody.value = rig.body;
    u.uHemTop.value = 1 - rig.hemTop;
    u.uFeetV.value = 1 - rig.feet;
  }
  u.uFlap.value = flap;
  u.uPhase.value = phase;
  u.uBend.value = bend;
  u.uCloth.value = cloth;
  u.uBreath.value = breath;
  u.uTime.value = time;
  u.uOpacity.value = opacity;
  u.uTint.value.set(tint);
  u.uExposure.value = exposure;
  u.uBlur.value = Math.min(6, dofBlur + blur);
  u.uFogColor.value.set(fogColor);
  u.uFog.value = fog;
  u.uReveal.value = reveal;
  u.uRevealMode.value = revealMode;
  u.uRevealSoft.value = revealSoft;
  u.uClipY.value = props.clipBelow ?? -1e6;
  if (opacity <= 0.001) return null;
  const ro = order ?? Math.round(center[2] * 100);
  return (
    <group position={center} rotation={[rotX, rotY, rot]}>
      <mesh geometry={geometry} material={material} frustumCulled={false} renderOrder={ro} />
      {depthMaterial && <mesh geometry={geometry} material={depthMaterial} frustumCulled={false} renderOrder={ro + 0.5} />}
    </group>
  );
};
