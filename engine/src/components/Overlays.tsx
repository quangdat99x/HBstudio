import React from 'react';
import {AbsoluteFill, useCurrentFrame} from 'remotion';

export const LETTERBOX = 100;

export const Grain: React.FC = () => {
  const frame = useCurrentFrame();
  return (
    <AbsoluteFill style={{mixBlendMode: 'overlay', opacity: 0.22, pointerEvents: 'none'}}>
      <svg width={1920} height={1080} viewBox="0 0 960 540" preserveAspectRatio="none">
        <filter id="film-grain">
          <feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves={2} seed={frame % 30} stitchTiles="stitch" />
          <feColorMatrix type="saturate" values="0" />
        </filter>
        <rect width={960} height={540} filter="url(#film-grain)" />
      </svg>
    </AbsoluteFill>
  );
};

export const Vignette: React.FC = () => (
  <AbsoluteFill
    style={{
      background: 'radial-gradient(ellipse at 50% 48%, rgba(0,0,0,0) 52%, rgba(0,0,0,0.55) 82%, rgba(0,0,0,0.85) 100%)',
      pointerEvents: 'none',
    }}
  />
);

export const Letterbox: React.FC = () => (
  <AbsoluteFill style={{pointerEvents: 'none'}}>
    <div style={{position: 'absolute', left: 0, right: 0, top: 0, height: LETTERBOX, background: '#000'}} />
    <div style={{position: 'absolute', left: 0, right: 0, bottom: 0, height: LETTERBOX, background: '#000'}} />
  </AbsoluteFill>
);

// Full-frame light burst, `amount` 0..1.
export const Flash: React.FC<{amount: number; color: string; x?: string; y?: string}> = ({amount, color, x = '50%', y = '40%'}) =>
  amount <= 0.001 ? null : (
    <AbsoluteFill
      style={{
        background: `radial-gradient(ellipse at ${x} ${y}, ${color} 0%, ${color} 25%, rgba(0,0,0,0) 85%)`,
        opacity: amount,
        mixBlendMode: 'screen',
        pointerEvents: 'none',
      }}
    />
  );
