import React, {useMemo} from 'react';
import * as THREE from 'three';
import {useFrame, useThree} from '@react-three/fiber';
import {EffectComposer} from 'three/examples/jsm/postprocessing/EffectComposer.js';
import {RenderPass} from 'three/examples/jsm/postprocessing/RenderPass.js';
import {ShaderPass} from 'three/examples/jsm/postprocessing/ShaderPass.js';
import {UnrealBloomPass} from 'three/examples/jsm/postprocessing/UnrealBloomPass.js';
import {CopyShader} from 'three/examples/jsm/shaders/CopyShader.js';
import type {V3} from './Stage';

// Camera effects on the finished frame, for scenes that ask for them:
//  - bloom: bright things (fire, sparks, hot metal) spill light into the lens around them;
//  - heat haze: the air above a fire refracts, a rising ripple over whatever is behind it.
// The scene renders into a half-float target (sparks brighter than white survive until the bloom) with MSAA.

export type Post = {
  bloom?: {strength: number; radius: number; threshold: number};
  haze?: {pos: V3; width: number; height: number; amount: number; time: number};
};

const HazeShader = {
  uniforms: {
    tDiffuse: {value: null},
    uBase: {value: new THREE.Vector2(0.5, 0.5)},
    uSize: {value: new THREE.Vector2(0.1, 0.2)},
    uAmount: {value: 0},
    uTime: {value: 0},
    uAspect: {value: 16 / 9},
  },
  vertexShader: /* glsl */ `varying vec2 vUv; void main(){ vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`,
  fragmentShader: /* glsl */ `
uniform sampler2D tDiffuse;
uniform vec2 uBase;
uniform vec2 uSize;
uniform float uAmount;
uniform float uTime;
uniform float uAspect;
varying vec2 vUv;
float hash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
float noise(vec2 p) {
  vec2 i = floor(p), f = fract(p);
  vec2 u = f * f * (3.0 - 2.0 * f);
  return mix(mix(hash(i), hash(i + vec2(1, 0)), u.x), mix(hash(i + vec2(0, 1)), hash(i + vec2(1, 1)), u.x), u.y);
}
void main() {
  vec2 d = (vUv - uBase) / uSize;               // x: -1..1 across the column, y: 0..1 up it
  float m = (1.0 - smoothstep(0.55, 1.0, abs(d.x))) * smoothstep(0.0, 0.12, d.y) * (1.0 - smoothstep(0.45, 1.0, d.y));
  vec2 q = vec2(vUv.x * uAspect, vUv.y) * 42.0 - vec2(0.0, uTime * 3.2);
  vec2 off = vec2(noise(q) - 0.5, noise(q * 1.7 + 11.0) - 0.5) + 0.5 * vec2(noise(q * 2.3 + 5.0) - 0.5, 0.0);
  gl_FragColor = texture2D(tDiffuse, vUv + off * uAmount * m);
}
`,
};

export const PostFx: React.FC<{post: Post}> = ({post}) => {
  const {gl, scene, camera} = useThree();
  const size = gl.getDrawingBufferSize(new THREE.Vector2());
  const {composer, haze, bloom} = useMemo(() => {
    const rt = new THREE.WebGLRenderTarget(size.x, size.y, {type: THREE.HalfFloatType, samples: 4});
    const c = new EffectComposer(gl, rt);
    c.addPass(new RenderPass(scene, camera));
    const h = new ShaderPass(HazeShader);
    c.addPass(h);
    const b = new UnrealBloomPass(new THREE.Vector2(size.x, size.y), 0.5, 0.4, 0.8);
    c.addPass(b);
    c.addPass(new ShaderPass(CopyShader)); // last pass draws to the canvas, colours unchanged
    return {composer: c, haze: h, bloom: b};
  }, [gl, scene, camera, size.x, size.y]);
  useFrame(() => {
    bloom.enabled = !!post.bloom;
    if (post.bloom) {
      bloom.strength = post.bloom.strength;
      bloom.radius = post.bloom.radius;
      bloom.threshold = post.bloom.threshold;
    }
    haze.enabled = !!post.haze;
    if (post.haze) {
      const {pos, width, height, amount, time} = post.haze;
      const toUv = (p: THREE.Vector3) => {
        p.project(camera);
        return new THREE.Vector2((p.x + 1) / 2, (p.y + 1) / 2);
      };
      const base = toUv(new THREE.Vector3(...pos));
      const top = toUv(new THREE.Vector3(pos[0], pos[1] + height, pos[2]));
      const side = toUv(new THREE.Vector3(pos[0] + width / 2, pos[1], pos[2]));
      const u = haze.uniforms;
      u.uBase.value.copy(base);
      u.uSize.value.set(Math.abs(side.x - base.x), Math.abs(top.y - base.y));
      u.uAmount.value = amount;
      u.uTime.value = time;
      u.uAspect.value = size.x / size.y;
    }
    composer.render();
  }, 1);
  return null;
};
