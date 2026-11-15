import React from 'react';
import {AbsoluteFill, Easing, interpolate, random, useCurrentFrame} from 'remotion';
import {clamp} from '../lib/anim';

// Scene transitions (Motion kit). The film keeps its absolute timeline: each scene's Sequence runs `ov` frames past
// its slot, under the next one, and the NEXT scene is wrapped in <Enter kind=...>. Everything happens on the
// incoming scene (mask, blur, slide) plus an overlay drawn above both, and `backdrop-filter` reaches the outgoing
// scene underneath (blur on whip / zoom). So a kind never changes scene timing and voice sync stays exact.
// Source of the moves: Motion Prompt (MIT, showheyohtaki.github.io/motion-prompt) #043 whip pan, #020 zoom through,
// #045 wipe, #017 mask transition, #138 blinds, #023 glitch, #046 smash cut, #119 light leak, #044 cross dissolve.

export type TransitionKind = 'cut' | 'dissolve' | 'dip' | 'flash' | 'leak' | 'whip' | 'zoom' | 'wipe' | 'iris' | 'blinds' | 'glitch';

// Default length in frames (30 fps) = the overlap `ov` the outgoing scene must run under the incoming one.
export const TRANSITION_LEN: Record<TransitionKind, number> = {
  cut: 0, dissolve: 15, dip: 22, flash: 12, leak: 26, whip: 10, zoom: 14, wipe: 20, iris: 24, blinds: 18, glitch: 10,
};

const outExpo = Easing.out(Easing.exp);
const inOut = Easing.inOut(Easing.cubic);

export const Enter: React.FC<{
  kind?: TransitionKind;
  len?: number;
  dir?: 1 | -1;             // whip / wipe direction: 1 = the new picture comes from the right
  at?: [number, number];    // iris centre (fractions of the frame)
  color?: string;           // dip / flash colour
  children: React.ReactNode;
}> = ({kind = 'dissolve', len, dir = 1, at = [0.5, 0.5], color, children}) => {
  const f = useCurrentFrame();
  const L = len ?? TRANSITION_LEN[kind];
  if (kind === 'cut' || L <= 0 || f >= L + 1) return <AbsoluteFill>{children}</AbsoluteFill>;
  const p = interpolate(f, [0, L], [0, 1], clamp);

  switch (kind) {
    case 'dip': {
      const half = L / 2;
      const black = interpolate(f, [0, half], [0, 1], {...clamp, easing: inOut});
      const o = interpolate(f, [half, L], [0, 1], {...clamp, easing: inOut});
      return (
        <>
          <AbsoluteFill style={{background: color ?? '#000', opacity: black}} />
          <AbsoluteFill style={{opacity: o}}>{children}</AbsoluteFill>
        </>
      );
    }
    case 'flash': {
      // smash cut on a burst of light: the new picture is there from frame 2, the light dies in ~8 frames
      const a = f < 2 ? f / 2 : Math.exp(-(f - 2) / 3.2);
      return (
        <>
          <AbsoluteFill style={{opacity: f < 2 ? 0 : 1, filter: `brightness(${1 + 1.6 * a})`}}>{children}</AbsoluteFill>
          <AbsoluteFill style={{background: color ?? '#fff6e6', opacity: 0.92 * a}} />
        </>
      );
    }
    case 'leak': {
      const o = interpolate(f, [0, L], [0, 1], {...clamp, easing: Easing.inOut(Easing.sin)});
      const bell = Math.sin(Math.PI * p) ** 0.8;
      return (
        <>
          <AbsoluteFill style={{opacity: o, filter: `brightness(${1 + 0.35 * bell})`}}>{children}</AbsoluteFill>
          <LeakBurst p={p} amount={bell} />
        </>
      );
    }
    case 'whip': {
      // outgoing blurs away (backdrop), incoming slides in fast with a horizontal motion blur
      const e = outExpo(p);
      const blur = 70 * (1 - e);
      const id = `whip-${Math.round(blur * 10)}`;
      return (
        <>
          <AbsoluteFill style={{backdropFilter: `blur(${(18 * Math.sin(Math.PI * Math.min(1, p * 1.6))).toFixed(1)}px)`}} />
          <HBlur id={id} amount={blur} />
          <AbsoluteFill style={{transform: `translateX(${(dir * 70 * (1 - e)).toFixed(2)}%)`, filter: blur > 0.5 ? `url(#${id})` : undefined}}>
            {children}
          </AbsoluteFill>
          <AbsoluteFill style={{background: 'linear-gradient(90deg, rgba(255,255,255,0) 0%, rgba(255,250,240,0.35) 50%, rgba(255,255,255,0) 100%)',
            opacity: 0.6 * Math.sin(Math.PI * p), mixBlendMode: 'screen'}} />
        </>
      );
    }
    case 'zoom': {
      // zoom through: the old shot rushes past (blur + brighten), the new one settles from 130 % to 100 %
      const e = outExpo(p);
      const back = Math.sin(Math.PI * Math.min(1, p * 1.4));
      return (
        <>
          <AbsoluteFill style={{backdropFilter: `blur(${(14 * back).toFixed(1)}px) brightness(${(1 + 0.3 * back).toFixed(2)})`}} />
          <AbsoluteFill style={{opacity: interpolate(p, [0, 0.45], [0, 1], clamp), transform: `scale(${1.3 - 0.3 * e})`,
            filter: `blur(${(16 * (1 - e)).toFixed(1)}px)`}}>
            {children}
          </AbsoluteFill>
        </>
      );
    }
    case 'wipe': {
      // soft-edged diagonal wipe with a thin line of light on its edge
      const e = inOut(p);
      const soft = 14;
      const pos = -soft + e * (100 + 2 * soft);
      const ang = dir === 1 ? 255 : 105;
      const mask = `linear-gradient(${ang}deg, #000 ${pos - soft}%, transparent ${pos}%)`;
      return (
        <>
          <AbsoluteFill style={{WebkitMaskImage: mask, maskImage: mask}}>{children}</AbsoluteFill>
          <AbsoluteFill style={{mixBlendMode: 'screen', opacity: Math.sin(Math.PI * p) * 0.55,
            background: `linear-gradient(${ang}deg, transparent ${pos - soft * 0.9}%, rgba(255,236,200,0.9) ${pos - soft * 0.5}%, transparent ${pos - soft * 0.1}%)`}} />
        </>
      );
    }
    case 'iris': {
      const e = Easing.inOut(Easing.quad)(p);
      const r = e * 125;
      const soft = 9;
      const mask = `radial-gradient(circle at ${at[0] * 100}% ${at[1] * 100}%, #000 ${Math.max(0, r - soft)}%, transparent ${r}%)`;
      return <AbsoluteFill style={{WebkitMaskImage: mask, maskImage: mask}}>{children}</AbsoluteFill>;
    }
    case 'blinds': {
      const e = inOut(p);
      const S = 72; // strip height px
      const open = e * S;
      const mask = `repeating-linear-gradient(180deg, #000 0px, #000 ${open.toFixed(1)}px, transparent ${open.toFixed(1)}px, transparent ${S}px)`;
      return <AbsoluteFill style={{WebkitMaskImage: mask, maskImage: mask}}>{children}</AbsoluteFill>;
    }
    case 'glitch': {
      const amt = Math.max(0, 1 - p) ** 1.5;
      return (
        <>
          <Glitch amount={amt} seed={f}>{children}</Glitch>
          <GlitchBars amount={amt} seed={f} />
        </>
      );
    }
    default: {
      const o = interpolate(f, [0, L], [0, 1], {...clamp, easing: Easing.inOut(Easing.sin)});
      return <AbsoluteFill style={{opacity: o}}>{children}</AbsoluteFill>;
    }
  }
};

// Horizontal-only gaussian blur (motion blur of a whip pan), used as `filter: url(#id)`.
export const HBlur: React.FC<{id: string; amount: number}> = ({id, amount}) => (
  <svg width={0} height={0} style={{position: 'absolute'}}>
    <filter id={id} x="-20%" y="0%" width="140%" height="100%" colorInterpolationFilters="sRGB">
      <feGaussianBlur stdDeviation={`${amount.toFixed(1)} 0`} />
    </filter>
  </svg>
);

// Warm burst of a light leak / film burn sweeping across the frame (#119), `p` 0..1 progress, `amount` 0..1.
export const LeakBurst: React.FC<{p: number; amount: number}> = ({p, amount}) =>
  amount <= 0.01 ? null : (
    <AbsoluteFill style={{mixBlendMode: 'screen', opacity: amount, pointerEvents: 'none',
      background: [
        `radial-gradient(ellipse 55% 75% at ${-10 + p * 90}% ${60 - p * 20}%, rgba(255,120,40,0.95) 0%, rgba(255,70,30,0.5) 40%, rgba(0,0,0,0) 75%)`,
        `radial-gradient(ellipse 40% 60% at ${20 + p * 85}% ${30 + p * 25}%, rgba(255,214,120,0.9) 0%, rgba(255,160,60,0.35) 45%, rgba(0,0,0,0) 75%)`,
        `radial-gradient(ellipse 30% 50% at ${100 - p * 40}% 80%, rgba(255,40,90,0.55) 0%, rgba(0,0,0,0) 70%)`,
      ].join(', ')}} />
  );

// Digital glitch on one rendering of its children (no copies, so a 3D stage is drawn once): horizontal slices
// displaced by a banded noise + red/cyan channel split. `amount` 0..1, `seed` changes the slices.
export const Glitch: React.FC<{amount: number; seed: number; children: React.ReactNode}> = ({amount, seed, children}) => {
  if (amount <= 0.01) return <AbsoluteFill>{children}</AbsoluteFill>;
  const id = `glitch-${seed}-${Math.round(amount * 100)}`;
  const shift = 120 * amount;
  const split = 14 * amount;
  const freqY = 0.02 + 0.05 * random(`gy${seed}`);
  return (
    <>
      <svg width={0} height={0} style={{position: 'absolute'}}>
        <filter id={id} x="-5%" y="0%" width="110%" height="100%" colorInterpolationFilters="sRGB">
          <feTurbulence type="fractalNoise" baseFrequency={`0.0001 ${freqY.toFixed(4)}`} numOctaves={1} seed={seed % 97} result="n" />
          <feComponentTransfer in="n" result="bands">
            <feFuncR type="discrete" tableValues="0.5 0.5 0.15 0.5 0.5 0.85 0.5 0.5 0.3 0.5" />
            <feFuncG type="discrete" tableValues="0.5" />
          </feComponentTransfer>
          <feDisplacementMap in="SourceGraphic" in2="bands" scale={shift} xChannelSelector="R" yChannelSelector="G" result="d" />
          <feColorMatrix in="d" type="matrix" values="1 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 1 0" result="r" />
          <feOffset in="r" dx={split} result="r2" />
          <feColorMatrix in="d" type="matrix" values="0 0 0 0 0  0 1 0 0 0  0 0 1 0 0  0 0 0 1 0" result="gb" />
          <feOffset in="gb" dx={-split} result="gb2" />
          <feComposite in="r2" in2="gb2" operator="arithmetic" k1={0} k2={1} k3={1} k4={0} />
        </filter>
      </svg>
      <AbsoluteFill style={{filter: `url(#${id})`}}>{children}</AbsoluteFill>
    </>
  );
};

// A few hard cyan/magenta bars that flicker with a glitch.
export const GlitchBars: React.FC<{amount: number; seed: number}> = ({amount, seed}) => {
  if (amount <= 0.05) return null;
  const bars = Array.from({length: 5}, (_, i) => {
    const r = (k: string) => random(`gb${seed}-${i}-${k}`);
    if (r('on') > 0.35 + 0.5 * amount) return null;
    return (
      <div key={i} style={{position: 'absolute', left: `${r('x') * 60}%`, top: `${r('y') * 100}%`, width: `${20 + r('w') * 60}%`,
        height: 2 + r('h') * 14, background: r('c') > 0.5 ? 'rgba(0,255,240,0.55)' : 'rgba(255,0,120,0.55)', mixBlendMode: 'screen'}} />
    );
  });
  return <AbsoluteFill style={{pointerEvents: 'none', opacity: amount}}>{bars}</AbsoluteFill>;
};
