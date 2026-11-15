import React from 'react';
import {AbsoluteFill, random, useCurrentFrame} from 'remotion';
import {fbm} from '../lib/noise';

// fbm is roughly in [-0.6, 0.6]; scale to about [-1, 1]
const fbm1 = (x: number, oct: number, seed = 'kit') => fbm(seed, x, oct) * 1.7;

// Looks and camera feel (Motion kit): colour grades, archival film, handheld, impact shake, light leak, lens flare.
// All are wrappers or overlays for one scene (or the whole film) and depend only on the frame, so stills and
// renders match. Source of the looks: Motion Prompt (MIT) #117 teal and orange, #115 black and white, #116 duotone,
// #118 film grain, #119 light leak, #109 lens flare, #111 chromatic aberration, #034 handheld, #024 impact shake.

export type GradeKind = 'none' | 'teal-orange' | 'bleach' | 'archive' | 'noir' | 'warm' | 'cold' | 'duotone';

// Tone curves per channel (5-point tables, 0..1). Shadows go teal and highlights orange in teal-orange, etc.
const CURVES: Record<Exclude<GradeKind, 'none' | 'duotone'>, {sat: number; r: string; g: string; b: string}> = {
  'teal-orange': {sat: 1.12, r: '0 0.17 0.48 0.82 1', g: '0.02 0.26 0.52 0.77 0.97', b: '0.09 0.34 0.52 0.66 0.8'},
  bleach: {sat: 0.42, r: '0 0.17 0.5 0.85 1', g: '0 0.17 0.5 0.85 1', b: '0.01 0.18 0.5 0.83 0.98'},
  archive: {sat: 0, r: '0.07 0.31 0.56 0.8 0.95', g: '0.06 0.29 0.53 0.77 0.92', b: '0.05 0.25 0.47 0.69 0.84'},
  noir: {sat: 0, r: '0 0.07 0.42 0.9 1', g: '0 0.07 0.42 0.9 1', b: '0 0.08 0.43 0.9 1'},
  warm: {sat: 1.05, r: '0.02 0.29 0.56 0.8 1', g: '0.01 0.26 0.51 0.75 0.96', b: '0 0.2 0.43 0.66 0.86'},
  cold: {sat: 0.9, r: '0 0.2 0.45 0.7 0.92', g: '0.01 0.25 0.5 0.75 0.97', b: '0.06 0.32 0.58 0.82 1'},
};

const hex = (c: string) => [1, 3, 5].map((i) => parseInt(c.slice(i, i + 2), 16) / 255);

// Colour grade as an SVG filter on the children. `amount` 0..1 blends with the original picture.
export const Grade: React.FC<{look: GradeKind; amount?: number; duo?: [string, string]; children: React.ReactNode}> = ({
  look,
  amount = 1,
  duo = ['#0b1a3a', '#f3c98b'],
  children,
}) => {
  if (look === 'none' || amount <= 0) return <AbsoluteFill>{children}</AbsoluteFill>;
  const id = `grade-${look}-${Math.round(amount * 100)}-${duo.join('').replace(/#/g, '')}`;
  let body: React.ReactNode;
  if (look === 'duotone') {
    const [a, b] = [hex(duo[0]), hex(duo[1])];
    body = (
      <>
        <feColorMatrix type="matrix" values="0.3 0.59 0.11 0 0  0.3 0.59 0.11 0 0  0.3 0.59 0.11 0 0  0 0 0 1 0" />
        <feComponentTransfer result="g">
          <feFuncR type="table" tableValues={`${a[0]} ${b[0]}`} />
          <feFuncG type="table" tableValues={`${a[1]} ${b[1]}`} />
          <feFuncB type="table" tableValues={`${a[2]} ${b[2]}`} />
        </feComponentTransfer>
      </>
    );
  } else {
    const c = CURVES[look];
    body = (
      <>
        <feColorMatrix type="saturate" values={String(c.sat)} />
        <feComponentTransfer result="g">
          <feFuncR type="table" tableValues={c.r} />
          <feFuncG type="table" tableValues={c.g} />
          <feFuncB type="table" tableValues={c.b} />
        </feComponentTransfer>
      </>
    );
  }
  return (
    <>
      <svg width={0} height={0} style={{position: 'absolute'}}>
        <filter id={id} colorInterpolationFilters="sRGB">
          {body}
          {amount < 1 && <feComposite in="g" in2="SourceGraphic" operator="arithmetic" k1={0} k2={amount} k3={1 - amount} k4={0} />}
        </filter>
      </svg>
      <AbsoluteFill style={{filter: `url(#${id})`}}>{children}</AbsoluteFill>
    </>
  );
};

// Old film: gate weave (the frame wanders by ~1-2 px), exposure flicker, dust and the odd vertical scratch.
// Pair with <Grade look="archive"> for archival footage or a "memory" flashback.
export const ArchiveFilm: React.FC<{amount?: number; children: React.ReactNode}> = ({amount = 1, children}) => {
  const f = useCurrentFrame();
  const x = (fbm1(f * 0.21, 3, 'wx') * 2.2 + (random(`wx${f}`) - 0.5) * 0.8) * amount;
  const y = (fbm1(f * 0.17, 3, 'wy') * 1.8 + (random(`wy${f}`) - 0.5) * 0.8) * amount;
  const flick = 1 + (random(`fl${f}`) - 0.5) * 0.08 * amount;
  return (
    <AbsoluteFill style={{overflow: 'hidden'}}>
      <AbsoluteFill style={{transform: `translate(${x.toFixed(2)}px, ${y.toFixed(2)}px) scale(1.01)`, filter: `brightness(${flick.toFixed(3)})`}}>
        {children}
      </AbsoluteFill>
      <Dust amount={amount} />
    </AbsoluteFill>
  );
};

const Dust: React.FC<{amount: number}> = ({amount}) => {
  const f = useCurrentFrame();
  const specks = Array.from({length: 9}, (_, i) => {
    const r = (k: string) => random(`d${f}-${i}-${k}`);
    if (r('on') > 0.45) return null;
    const s = 1.5 + r('s') * 4;
    return <div key={i} style={{position: 'absolute', left: `${r('x') * 100}%`, top: `${r('y') * 100}%`, width: s, height: s * (0.6 + r('a')),
      borderRadius: '50%', background: r('c') > 0.3 ? 'rgba(10,8,6,0.75)' : 'rgba(255,250,235,0.6)'}} />;
  });
  // a scratch lives for a few frames at a slowly drifting x
  const k = Math.floor(f / 7);
  const scratch = random(`sc${k}`) < 0.5;
  const sx = random(`sx${k}`) * 100 + Math.sin(f * 0.3) * 0.15;
  return (
    <AbsoluteFill style={{pointerEvents: 'none', opacity: amount}}>
      {specks}
      {scratch && <div style={{position: 'absolute', left: `${sx}%`, top: 0, bottom: 0, width: 1.4, background: 'rgba(255,248,230,0.28)'}} />}
    </AbsoluteFill>
  );
};

// Handheld camera: slow, organic drift + a little rotation (never linear). `amount` 1 = documentary handheld,
// 0.4 = barely alive. Scales up a touch so the edges never show.
export const Handheld: React.FC<{amount?: number; children: React.ReactNode}> = ({amount = 1, children}) => {
  const f = useCurrentFrame();
  const x = fbm1(f * 0.045, 3, 'hx') * 14 * amount;
  const y = fbm1(f * 0.05, 3, 'hy') * 9 * amount;
  const r = fbm1(f * 0.035, 2, 'hr') * 0.45 * amount;
  return (
    <AbsoluteFill style={{overflow: 'hidden'}}>
      <AbsoluteFill style={{transform: `translate(${x.toFixed(2)}px, ${y.toFixed(2)}px) rotate(${r.toFixed(3)}deg) scale(${1 + 0.025 * amount})`}}>
        {children}
      </AbsoluteFill>
    </AbsoluteFill>
  );
};

// Impact shake on given frames (local to the scene): a hard jolt that decays in ~10 frames, with a short punch-in.
export const Impact: React.FC<{hits: number[]; amp?: number; children: React.ReactNode}> = ({hits, amp = 22, children}) => {
  const f = useCurrentFrame();
  let x = 0;
  let y = 0;
  let s = 0;
  for (const h of hits) {
    if (f < h) continue;
    const d = f - h;
    const e = Math.exp(-d / 4.5);
    x += e * amp * Math.sin(d * 2.9 + h);
    y += e * amp * 0.7 * Math.cos(d * 3.7 + h * 1.7);
    s += Math.exp(-d / 6) * 0.04;
  }
  return (
    <AbsoluteFill style={{overflow: 'hidden'}}>
      <AbsoluteFill style={{transform: `translate(${x.toFixed(2)}px, ${y.toFixed(2)}px) scale(${1.03 + s})`}}>{children}</AbsoluteFill>
    </AbsoluteFill>
  );
};

// Slow light leak that breathes over a scene (screen blend): nostalgia, warmth, a sunlit memory.
export const LightLeak: React.FC<{amount?: number; seed?: number; warm?: boolean}> = ({amount = 0.5, seed = 1, warm = true}) => {
  const f = useCurrentFrame();
  const t = f / 30;
  const a = amount * (0.65 + 0.35 * Math.sin(t * 0.7 + seed));
  const x = 12 + 22 * Math.sin(t * 0.13 + seed * 2);
  const y = 25 + 20 * Math.cos(t * 0.11 + seed);
  const c1 = warm ? 'rgba(255,140,50,0.9)' : 'rgba(120,170,255,0.8)';
  const c2 = warm ? 'rgba(255,60,80,0.45)' : 'rgba(170,110,255,0.4)';
  return (
    <AbsoluteFill style={{pointerEvents: 'none', mixBlendMode: 'screen', opacity: a,
      background: `radial-gradient(ellipse 45% 70% at ${x}% ${y}%, ${c1} 0%, rgba(0,0,0,0) 70%), radial-gradient(ellipse 35% 55% at ${96 - x * 0.5}% ${90 - y * 0.6}%, ${c2} 0%, rgba(0,0,0,0) 70%)`}} />
  );
};

// Anamorphic lens flare at a light source (x, y in fractions): bright core, long horizontal streak, ghosts along
// the line through the centre of the frame. Moves with `x`/`y` if you animate them.
export const LensFlare: React.FC<{x: number; y: number; amount?: number; color?: string}> = ({x, y, amount = 1, color = '120,180,255'}) => {
  const f = useCurrentFrame();
  const flick = 0.92 + 0.08 * Math.sin(f * 0.9) * Math.sin(f * 0.37);
  const a = amount * flick;
  const ghosts = [0.35, 0.62, 1.25, 1.6].map((k, i) => {
    const gx = (x + (0.5 - x) * 2 * k) * 100;
    const gy = (y + (0.5 - y) * 2 * k) * 100;
    const size = [70, 34, 120, 50][i];
    return <div key={i} style={{position: 'absolute', left: `${gx}%`, top: `${gy}%`, width: size, height: size, marginLeft: -size / 2, marginTop: -size / 2,
      borderRadius: '50%', background: `radial-gradient(circle, rgba(${color},0.0) 40%, rgba(${color},${0.18 - i * 0.02}) 70%, rgba(${color},0) 100%)`}} />;
  });
  return (
    <AbsoluteFill style={{pointerEvents: 'none', mixBlendMode: 'screen', opacity: a}}>
      <div style={{position: 'absolute', left: `${x * 100}%`, top: `${y * 100}%`, width: 2400, height: 40, marginLeft: -1200, marginTop: -20, filter: 'blur(8px)',
        background: `linear-gradient(90deg, rgba(${color},0) 0%, rgba(${color},0.3) 30%, rgba(${color},0.85) 50%, rgba(${color},0.25) 70%, rgba(${color},0) 100%)`}} />
      <div style={{position: 'absolute', left: `${x * 100}%`, top: `${y * 100}%`, width: 1400, height: 5, marginLeft: -700, marginTop: -2.5, filter: 'blur(1.6px)',
        background: `linear-gradient(90deg, rgba(${color},0) 0%, rgba(${color},0.45) 30%, rgba(235,245,255,0.95) 50%, rgba(${color},0.45) 70%, rgba(${color},0) 100%)`}} />
      <div style={{position: 'absolute', left: `${x * 100}%`, top: `${y * 100}%`, width: 260, height: 260, marginLeft: -130, marginTop: -130,
        background: 'radial-gradient(circle, rgba(255,255,255,0.95) 0%, rgba(255,240,220,0.55) 12%, rgba(255,200,150,0.12) 40%, rgba(0,0,0,0) 70%)'}} />
      {ghosts}
    </AbsoluteFill>
  );
};

// Chromatic aberration: red and blue fringes split sideways by `px` (lens character, unease). One rendering of the
// children, so it is safe on a 3D stage.
export const Chroma: React.FC<{px?: number; children: React.ReactNode}> = ({px = 3, children}) => {
  const id = `chroma-${px}`;
  return (
    <>
      <svg width={0} height={0} style={{position: 'absolute'}}>
        <filter id={id} colorInterpolationFilters="sRGB">
          <feColorMatrix in="SourceGraphic" type="matrix" values="1 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 1 0" result="r" />
          <feOffset in="r" dx={px} result="r2" />
          <feColorMatrix in="SourceGraphic" type="matrix" values="0 0 0 0 0  0 1 0 0 0  0 0 0 0 0  0 0 0 1 0" result="g" />
          <feColorMatrix in="SourceGraphic" type="matrix" values="0 0 0 0 0  0 0 0 0 0  0 0 1 0 0  0 0 0 1 0" result="b" />
          <feOffset in="b" dx={-px} result="b2" />
          <feComposite in="r2" in2="g" operator="arithmetic" k2={1} k3={1} result="rg" />
          <feComposite in="rg" in2="b2" operator="arithmetic" k2={1} k3={1} />
        </filter>
      </svg>
      <AbsoluteFill style={{filter: `url(#${id})`}}>{children}</AbsoluteFill>
    </>
  );
};
