import React, {useLayoutEffect, useMemo, useRef} from 'react';
import * as THREE from 'three';
import {useThree} from '@react-three/fiber';
import {useOffthreadVideoTexture} from '@remotion/three';
import {staticFile, useCurrentFrame, useDelayRender} from 'remotion';
import type {V3} from './Stage';

// Filmed elements shot on black (fire, smoke), played frame-accurately on a plane in the 3D stage and added
// to the light already there. A taper and soft edges turn a rectangular crop into a flame body; an optional
// ellipse (the mouth of a brazier) hides what is below its front lip, so the fire rises out of the bowl.

const VERT = /* glsl */ `
varying vec2 vUv;
varying vec3 vWorld;
void main() {
  vUv = uv;
  vec4 w = modelMatrix * vec4(position, 1.0);
  vWorld = w.xyz;
  gl_Position = projectionMatrix * viewMatrix * w;
}
`;

const FRAG = /* glsl */ `
uniform sampler2D map;
uniform float uGain;
uniform vec3 uTint;
uniform vec3 uTintTop;
uniform float uTaper;
uniform vec4 uFade;     // side, -, bottom, top (in uv)
uniform float uMaskOn;
uniform vec4 uMouth;    // ellipse centre x, y, half width, half height (world)
uniform float uLipTop;  // world y above which nothing is hidden
varying vec2 vUv;
varying vec3 vWorld;
void main() {
  vec3 c = texture2D(map, vUv).rgb;
  float v = vUv.y;
  float halfw = 0.5 - uTaper * v;
  float m = 1.0 - smoothstep(halfw - uFade.x, halfw, abs(vUv.x - 0.5));
  m *= smoothstep(0.0, uFade.z, v) * (1.0 - smoothstep(1.0 - uFade.w, 1.0, v));
  if (uMaskOn > 0.5) {
    float ex = (vWorld.x - uMouth.x) / uMouth.z;
    float inside = 1.0 - smoothstep(0.85, 1.0, abs(ex));
    float lip = uMouth.y - uMouth.w * sqrt(max(0.0, 1.0 - ex * ex));
    float vis = max(smoothstep(uLipTop - 0.03, uLipTop + 0.08, vWorld.y), inside * smoothstep(lip - 0.01, lip + 0.05, vWorld.y));
    m *= vis;
  }
  gl_FragColor = vec4(c * mix(uTint, uTintTop, v) * uGain * m, 1.0);
}
`;

export type VideoFxProps = {
  src: string; // in public/
  pos: V3; // bottom centre
  width: number;
  height: number;
  gain?: number;
  tint?: string;
  tintTop?: string;
  taper?: number; // 0 = rectangle, 0.3 = narrows to 40 % at the top
  fade?: [number, number, number]; // side, bottom, top
  mouth?: {x: number; y: number; a: number; b: number; lipTop: number};
  order?: number;
};

export const VideoFx: React.FC<VideoFxProps> = ({src, pos, width, height, gain = 1, tint = '#ffffff', tintTop, taper = 0, fade = [0.12, 0.05, 0.3], mouth, order}) => {
  const tex = useOffthreadVideoTexture({src: staticFile(src)});
  // The frame's video texture arrives after the canvas has drawn, and while rendering the canvas only draws
  // when Remotion changes frame: hold each frame until its texture is in, then draw once more.
  const frame = useCurrentFrame();
  const advance = useThree((s) => s.advance);
  const {delayRender, continueRender} = useDelayRender();
  const pending = useRef<number | null>(null);
  useLayoutEffect(() => {
    pending.current = delayRender(`VideoFx ${src} frame ${frame}`);
    return () => {
      if (pending.current !== null) continueRender(pending.current);
      pending.current = null;
    };
  }, [frame, src, delayRender, continueRender]);
  useLayoutEffect(() => {
    if (!tex || pending.current === null) return;
    advance(performance.now());
    continueRender(pending.current);
    pending.current = null;
  }, [tex, advance, continueRender]);
  const material = useMemo(
    () =>
      new THREE.ShaderMaterial({
        vertexShader: VERT,
        fragmentShader: FRAG,
        transparent: true,
        depthWrite: false,
        depthTest: true,
        blending: THREE.AdditiveBlending,
        uniforms: {
          map: {value: null},
          uGain: {value: 1},
          uTint: {value: new THREE.Color()},
          uTintTop: {value: new THREE.Color()},
          uTaper: {value: 0},
          uFade: {value: new THREE.Vector4()},
          uMaskOn: {value: 0},
          uMouth: {value: new THREE.Vector4()},
          uLipTop: {value: 0},
        },
      }),
    [],
  );
  if (!tex) return null;
  tex.colorSpace = THREE.NoColorSpace; // pass colours straight through, like the image plates
  const u = material.uniforms;
  u.map.value = tex;
  u.uGain.value = gain;
  u.uTint.value.set(tint);
  u.uTintTop.value.set(tintTop ?? tint);
  u.uTaper.value = taper;
  u.uFade.value.set(fade[0], 0, fade[1], fade[2]);
  u.uMaskOn.value = mouth ? 1 : 0;
  if (mouth) {
    u.uMouth.value.set(mouth.x, mouth.y, mouth.a, mouth.b);
    u.uLipTop.value = mouth.lipTop;
  }
  return (
    <mesh position={[pos[0], pos[1] + height / 2, pos[2]]} material={material} frustumCulled={false} renderOrder={order ?? Math.round(pos[2] * 100) + 1}>
      <planeGeometry args={[width, height]} />
    </mesh>
  );
};
