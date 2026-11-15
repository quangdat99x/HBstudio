import React from 'react';
import {AbsoluteFill, Img, interpolate, spring, staticFile, useCurrentFrame} from 'remotion';
import {clamp} from '../lib/anim';
import {FPS, HEIGHT, WIDTH} from '../timeline';
import {cinzel} from '../components/Text';
import {Desk, DeskTone} from './desk';
import {CardLoose, PhotoCard} from './cards';

// The real emblem of an organisation, turned into an object: given thickness (stacked darker copies in a 3D
// space), a slow turn, a band of light sweeping across its face, fog drifting behind. Optionally the earlier
// organisations of the chain glow faintly behind it ("ghosts"): the viewer sees the trail getting longer.

export type LogoSpec = {
  src: string;                  // logo with transparency (png/webp) under public/
  aspect: number;               // width / height
  w?: number;                   // width, frame fraction (default 0.34)
  title?: string;               // name under the emblem (Cinzel, spaced)
  sub?: string;                 // small line under the title (year, place)
  glow?: string;                // colour of the light behind (default warm)
  ghosts?: string[];            // names of the earlier links, drifting dim in the fog
  photo?: CardLoose;             // optional real photo of the building / meeting beside the emblem
  depth?: number;               // thickness in px (default 18)
};

const Fog: React.FC<{color: string}> = ({color}) => {
  const f = useCurrentFrame();
  return (
    <AbsoluteFill style={{mixBlendMode: 'screen', opacity: 0.55}}>
      <svg width={WIDTH} height={HEIGHT} viewBox={`0 0 ${WIDTH} ${HEIGHT}`}>
        <filter id="logo-fog" x="0" y="0" width="100%" height="100%">
          <feTurbulence type="fractalNoise" baseFrequency="0.0025 0.006" numOctaves={4} seed={11} />
          <feColorMatrix type="matrix" values="0 0 0 0 1  0 0 0 0 1  0 0 0 0 1  0 0 0 0.9 -0.32" />
        </filter>
        <g transform={`translate(${-(f * 1.4) % 600} 0)`}>
          <rect x={0} y={0} width={WIDTH + 600} height={HEIGHT} filter="url(#logo-fog)" />
        </g>
      </svg>
      <AbsoluteFill style={{background: `radial-gradient(ellipse 45% 40% at 50% 48%, ${color} 0%, rgba(0,0,0,0) 70%)`, mixBlendMode: 'multiply'}} />
    </AbsoluteFill>
  );
};

export const LogoShot: React.FC<{l: LogoSpec; duration: number; tone?: DeskTone}> = ({l, duration, tone = 'black'}) => {
  const f = useCurrentFrame();
  const inQ = spring({frame: f, fps: FPS, config: {damping: 18, stiffness: 70}});
  const ry = interpolate(f, [0, duration], [-24, 10], clamp);
  const rx = interpolate(f, [0, duration], [6, -3], clamp);
  const scale = 0.86 + 0.14 * inQ + interpolate(f, [0, duration], [0, 0.05], clamp);
  const sweep = interpolate(f, [10, 52], [-40, 140], clamp);
  const w = (l.w ?? 0.34) * WIDTH;
  const h = w / l.aspect;
  const depth = l.depth ?? 18;
  const glow = l.glow ?? 'rgba(255,170,90,0.55)';
  const titleO = interpolate(f, [18, 34], [0, 1], clamp);
  const cx = l.photo ? WIDTH * 0.36 : WIDTH / 2;
  const mask = {WebkitMaskImage: `url(${staticFile(l.src)})`, maskImage: `url(${staticFile(l.src)})`, WebkitMaskSize: '100% 100%', maskSize: '100% 100%'};
  return (
    <AbsoluteFill>
      <Desk tone={tone} light={[0.5, 0.45]} />
      <AbsoluteFill style={{background: `radial-gradient(ellipse 40% 45% at ${(cx / WIDTH) * 100}% 46%, ${glow} 0%, rgba(0,0,0,0) 70%)`, mixBlendMode: 'screen'}} />
      {(l.ghosts ?? []).map((g, i) => (
        <div key={g} style={{position: 'absolute', left: `${12 + ((i * 37) % 70)}%`, top: `${20 + ((i * 23) % 55)}%`, fontFamily: cinzel, fontSize: 64,
          letterSpacing: '0.2em', color: 'rgba(230,220,200,0.11)', filter: 'blur(2px)', transform: `translateX(${-f * (0.3 + i * 0.07)}px)`, whiteSpace: 'nowrap'}}>
          {g.toUpperCase()}
        </div>
      ))}
      <Fog color={glow} />
      <AbsoluteFill style={{perspective: 1800}}>
        <div style={{position: 'absolute', left: cx - w / 2, top: HEIGHT * 0.44 - h / 2, width: w, height: h, transformStyle: 'preserve-3d',
          transform: `rotateY(${ry}deg) rotateX(${rx}deg) scale(${scale})`, opacity: inQ}}>
          {Array.from({length: 10}, (_, i) => (
            <Img key={i} src={staticFile(l.src)} style={{position: 'absolute', inset: 0, width: '100%', height: '100%',
              transform: `translateZ(${-((i + 1) * depth) / 10}px)`, filter: `brightness(${0.32 - i * 0.015})`}} />
          ))}
          <Img src={staticFile(l.src)} style={{position: 'absolute', inset: 0, width: '100%', height: '100%', filter: 'drop-shadow(0 20px 40px rgba(0,0,0,0.6))'}} />
          <div style={{position: 'absolute', inset: 0, ...mask, background: `linear-gradient(105deg, rgba(255,255,255,0) ${sweep - 18}%, rgba(255,255,255,0.75) ${sweep}%, rgba(255,255,255,0) ${sweep + 18}%)`,
            mixBlendMode: 'screen'}} />
        </div>
      </AbsoluteFill>
      {l.title && (
        <div style={{position: 'absolute', left: cx, top: HEIGHT * 0.44 + h / 2 + 50, transform: 'translateX(-50%)', textAlign: 'center', opacity: titleO, whiteSpace: 'nowrap'}}>
          <div style={{fontFamily: cinzel, fontWeight: 700, fontSize: 54, letterSpacing: '0.22em', color: '#efe4cc', textShadow: '0 4px 24px rgba(0,0,0,0.9)'}}>{l.title.toUpperCase()}</div>
          {l.sub && <div style={{fontFamily: cinzel, fontSize: 22, letterSpacing: '0.45em', color: '#b99a62', marginTop: 10}}>{l.sub.toUpperCase()}</div>}
        </div>
      )}
      {l.photo && <PhotoCard c={{x: 0.72, y: 0.47, w: 0.3, rot: 3, at: 14, ...l.photo}} />}
    </AbsoluteFill>
  );
};
