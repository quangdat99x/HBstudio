import React from 'react';
import {AbsoluteFill, Img, interpolate, OffthreadVideo, staticFile, useCurrentFrame} from 'remotion';
import {loadFont as loadPlexMono} from '@remotion/google-fonts/IBMPlexMono';
import {clamp} from '../lib/anim';
import {ArchiveFilm} from '../kit/looks';
import {Desk} from './desk';

// Old footage or an old photograph played inside the gate of a film projector / an old TV: rounded corners, the
// edge burnt dark, frame counter and stock name in the margin, gate weave and dust (ArchiveFilm), a warm light leak
// as it ends. One look for every source, so a 1970s interview and a 1950s newsreel sit in the same film.

const {fontFamily: mono} = loadPlexMono('normal', {weights: ['500'], subsets: ['latin']});

export type ArchiveSpec = {
  src: string;                   // under public/: .mp4/.webm/.mov plays, anything else is a still
  gate?: 'film' | 'tv';
  color?: boolean;               // keep the (faded) colour; default black and white
  stock?: string;                // margin text, default "8MM FILM" / "VHS"
  counter?: number;              // first frame number printed in the margin
  startFrom?: number;            // frames into the video
  volume?: number;               // 0 = silent (default: the narration plays over it)
  playbackRate?: number;
  leak?: boolean;                // warm light leak at the end (default true)
};

const isVideo = (s: string) => /\.(mp4|webm|mov|m4v)$/i.test(s);

export const ArchiveShot: React.FC<{a: ArchiveSpec; duration: number}> = ({a, duration}) => {
  const f = useCurrentFrame();
  const tv = a.gate === 'tv';
  const push = interpolate(f, [0, duration], [1.0, 1.05], clamp);
  const leak = a.leak === false ? 0 : interpolate(f, [duration - 24, duration - 4], [0, 0.75], clamp);
  const counter = String((a.counter ?? 255) + Math.floor(f / 2)).padStart(6, '0');
  const filter = a.color ? 'saturate(0.55) sepia(0.28) contrast(1.1) brightness(0.95)' : 'grayscale(1) contrast(1.2) brightness(0.92)';
  const media = isVideo(a.src) ? (
    <OffthreadVideo src={staticFile(a.src)} startFrom={a.startFrom ?? 0} volume={a.volume ?? 0} playbackRate={a.playbackRate ?? 1}
      style={{width: '100%', height: '100%', objectFit: 'cover', filter}} />
  ) : (
    <Img src={staticFile(a.src)} style={{width: '100%', height: '100%', objectFit: 'cover', filter, transform: `scale(${push})`}} />
  );
  const margin = {position: 'absolute' as const, fontFamily: mono, fontSize: 17, letterSpacing: '0.2em', color: 'rgba(225,215,190,0.55)'};
  return (
    <AbsoluteFill>
      <Desk tone="black" />
      <AbsoluteFill style={{transform: `scale(${push})`}}>
        <div style={{position: 'absolute', left: '9%', right: '9%', top: '14%', bottom: '14%', borderRadius: tv ? 70 : 34, overflow: 'hidden',
          boxShadow: '0 0 0 2px rgba(255,255,255,0.05), 0 30px 90px rgba(0,0,0,0.9)'}}>
          <ArchiveFilm amount={1}>{media}</ArchiveFilm>
          {/* burnt gate edge / tube curvature */}
          <AbsoluteFill style={{boxShadow: `inset 0 0 ${tv ? 160 : 110}px ${tv ? 40 : 20}px rgba(0,0,0,0.85)`, borderRadius: tv ? 70 : 34}} />
          {tv && <AbsoluteFill style={{background: 'repeating-linear-gradient(0deg, rgba(0,0,0,0.18) 0px, rgba(0,0,0,0.18) 1px, transparent 2px, transparent 4px)'}} />}
        </div>
        <div style={{...margin, left: '9.5%', top: '10.4%'}}>{tv ? '▶ PLAY' : '▸▸ ' + (a.stock ?? '8MM FILM')}</div>
        <div style={{...margin, right: '9.5%', top: '10.4%'}}>{counter} ▪▪▪</div>
        <div style={{...margin, left: '9.5%', bottom: '10.4%'}}>{a.stock ?? (tv ? 'VHS' : '8MM FOOTAGE')}</div>
        <div style={{...margin, right: '9.5%', bottom: '10.4%'}}>{tv ? 'SP' : '◂◂ ' + counter}</div>
      </AbsoluteFill>
      {leak > 0 && (
        <AbsoluteFill style={{background: 'radial-gradient(ellipse 60% 80% at 92% 40%, rgba(255,140,40,0.95) 0%, rgba(255,80,20,0.4) 40%, rgba(0,0,0,0) 75%)',
          mixBlendMode: 'screen', opacity: leak}} />
      )}
    </AbsoluteFill>
  );
};
