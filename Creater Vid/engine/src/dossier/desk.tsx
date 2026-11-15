import React from 'react';
import {AbsoluteFill, Easing, interpolate, useCurrentFrame} from 'remotion';
import {fbm} from '../lib/noise';
import {HEIGHT, WIDTH} from '../timeline';

// The surface every dossier shot lives on, and the camera that never stops moving over it.
// Real photos and documents are laid on a desk / board like physical evidence: the camera drifts, pushes and
// travels between them (2.5D: a CSS perspective space, cards tilt and cast shadows).

export type DeskTone = 'night' | 'paper' | 'black' | 'cork' | 'steel';

const TONES: Record<DeskTone, {base: string; hi: string; tex: number}> = {
  night: {base: '#120f0c', hi: '#2c251c', tex: 0.5},   // dark wood / leather desk: the default
  paper: {base: '#8f8268', hi: '#d9ccb0', tex: 0.35},  // old paper (aged archive look)
  black: {base: '#040404', hi: '#191919', tex: 0.35},  // void: logos, archive frames
  cork: {base: '#3b2b1b', hi: '#6a4f33', tex: 0.7},    // investigation board
  steel: {base: '#0d1114', hi: '#26313a', tex: 0.4},   // cold, intelligence / tech files
};

export const Desk: React.FC<{tone?: DeskTone; light?: [number, number]; seed?: number}> = ({tone = 'night', light = [0.5, 0.42], seed = 3}) => {
  const t = TONES[tone];
  return (
    <AbsoluteFill style={{background: `radial-gradient(ellipse 75% 70% at ${light[0] * 100}% ${light[1] * 100}%, ${t.hi} 0%, ${t.base} 78%)`}}>
      <AbsoluteFill style={{mixBlendMode: 'overlay', opacity: t.tex}}>
        <svg width={WIDTH} height={HEIGHT} viewBox={`0 0 ${WIDTH} ${HEIGHT}`}>
          <filter id={`desk-${tone}-${seed}`}>
            <feTurbulence type="fractalNoise" baseFrequency={tone === 'cork' ? '0.9' : '0.012 0.06'} numOctaves={4} seed={seed} />
            <feColorMatrix type="saturate" values="0" />
          </filter>
          <rect width={WIDTH} height={HEIGHT} filter={`url(#desk-${tone}-${seed})`} />
        </svg>
      </AbsoluteFill>
      <AbsoluteFill style={{background: 'radial-gradient(ellipse at 50% 48%, rgba(0,0,0,0) 45%, rgba(0,0,0,0.65) 100%)'}} />
    </AbsoluteFill>
  );
};

// A camera key: the point of the desk (frame fractions at zoom 1) that sits in the centre of the frame, and the zoom.
export type CamKey = {at: number; x: number; y: number; zoom: number; rot?: number};

const ease = Easing.inOut(Easing.sin);

// Camera position at frame f along the keys. Between keys it eases; it also never stands still: a slow breathing
// drift rides on top (the rule of the dossier look: no static picture, ever).
export const camAt = (keys: CamKey[], f: number, duration: number): CamKey => {
  const ks = keys.length ? [...keys].sort((a, b) => a.at - b.at) : [{at: 0, x: 0.5, y: 0.5, zoom: 1}];
  let k: CamKey = ks[0];
  if (f <= ks[0].at) k = ks[0];
  else if (f >= ks[ks.length - 1].at) k = ks[ks.length - 1];
  else {
    for (let i = 0; i < ks.length - 1; i++) {
      const a = ks[i];
      const b = ks[i + 1];
      if (f >= a.at && f <= b.at) {
        const q = ease((f - a.at) / Math.max(1, b.at - a.at));
        k = {at: f, x: a.x + (b.x - a.x) * q, y: a.y + (b.y - a.y) * q, zoom: a.zoom * Math.pow(b.zoom / a.zoom, q),
          rot: (a.rot ?? 0) + ((b.rot ?? 0) - (a.rot ?? 0)) * q};
        break;
      }
    }
  }
  // breathing drift: ~4 % push over the scene + a slow wander of a few pixels
  const push = interpolate(f, [0, Math.max(1, duration)], [1, 1.045], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const wx = fbm('camx', f * 0.008, 2) * 0.006;
  const wy = fbm('camy', f * 0.007 + 9, 2) * 0.005;
  return {at: f, x: k.x + wx, y: k.y + wy, zoom: k.zoom * push, rot: k.rot ?? 0};
};

// Everything inside moves with the camera. `perspective` makes tilted cards read as objects in space.
export const DeskCam: React.FC<{keys: CamKey[]; duration: number; children: React.ReactNode}> = ({keys, duration, children}) => {
  const f = useCurrentFrame();
  const c = camAt(keys, f, duration);
  const tx = WIDTH / 2 - c.x * WIDTH * c.zoom;
  const ty = HEIGHT / 2 - c.y * HEIGHT * c.zoom;
  return (
    <AbsoluteFill style={{overflow: 'hidden'}}>
      <AbsoluteFill
        style={{
          transformOrigin: '0 0',
          transform: `translate(${tx.toFixed(2)}px, ${ty.toFixed(2)}px) scale(${c.zoom.toFixed(4)}) rotate(${(c.rot ?? 0).toFixed(3)}deg)`,
          perspective: 2400,
          transformStyle: 'preserve-3d',
        }}
      >
        {children}
      </AbsoluteFill>
    </AbsoluteFill>
  );
};

// Depth of field around the centre of the frame: the content is drawn twice, a blurred copy underneath and a sharp
// copy masked to an ellipse in the middle, so whatever the camera centres on is crisp and the edges melt away.
export const FocusPool: React.FC<{blur?: number; size?: [number, number]; children: React.ReactNode}> = ({blur = 5, size = [62, 58], children}) =>
  blur <= 0 ? (
    <>{children}</>
  ) : (
    <AbsoluteFill>
      <AbsoluteFill style={{filter: `blur(${blur}px) brightness(0.8)`}}>{children}</AbsoluteFill>
      <AbsoluteFill
        style={{
          WebkitMaskImage: `radial-gradient(ellipse ${size[0]}% ${size[1]}% at 50% 50%, #000 55%, transparent 100%)`,
          maskImage: `radial-gradient(ellipse ${size[0]}% ${size[1]}% at 50% 50%, #000 55%, transparent 100%)`,
        }}
      >
        {children}
      </AbsoluteFill>
    </AbsoluteFill>
  );
