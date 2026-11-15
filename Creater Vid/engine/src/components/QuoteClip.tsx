import React from 'react';
import {AbsoluteFill, Easing, interpolate, OffthreadVideo, staticFile, useCurrentFrame} from 'remotion';
import {clamp} from '../lib/anim';
import {LETTERBOX} from './Overlays';
import {cinzel, cormorant} from './Text';

export type SubLine = {from: number; to: number; text: string}; // frames relative to the clip start

// A quote from the highlight database: the JRE clip itself (cut frame-accurately with
// scripts/clip.mjs into public/clips/), the speaker and source as a lower third, and the
// verbatim transcript as subtitles. Never re-word the subtitles: they must match the audio.
export const QuoteClip: React.FC<{
  src: string; // path under public/, e.g. "clips/q01.mp4"
  duration: number; // frames
  speaker: string; // e.g. "Timothy Alberino"
  source: string; // e.g. "Joe Rogan Experience #2530"
  lines?: SubLine[];
  volume?: number;
  grade?: boolean; // gentle contrast/desaturation so the clip sits in the film's look
  startFrom?: number; // frames into the file (normally 0: the file is already the quote)
}> = ({src, duration, speaker, source, lines = [], volume = 1, grade = true, startFrom = 0}) => {
  const f = useCurrentFrame();
  const third = Math.min(interpolate(f, [8, 24], [0, 1], clamp), interpolate(f, [110, 130], [1, 0], clamp));
  const push = interpolate(f, [0, duration], [1.0, 1.04], {...clamp, easing: Easing.inOut(Easing.sin)});
  const line = lines.find((l) => f >= l.from && f < l.to);
  return (
    <AbsoluteFill style={{backgroundColor: '#000'}}>
      <AbsoluteFill style={{transform: `scale(${push})`, filter: grade ? 'contrast(1.06) saturate(0.82) brightness(0.96)' : undefined}}>
        <OffthreadVideo src={staticFile(src)} startFrom={startFrom} volume={volume} style={{width: '100%', height: '100%', objectFit: 'cover'}} />
      </AbsoluteFill>
      <AbsoluteFill style={{justifyContent: 'flex-start', paddingTop: LETTERBOX + 28, paddingLeft: 70, opacity: third}}>
        <div style={{fontFamily: cinzel, fontSize: 30, letterSpacing: '0.12em', color: '#f3e6c8', textShadow: '0 2px 14px rgba(0,0,0,0.9)'}}>{speaker}</div>
        <div style={{fontFamily: cinzel, fontSize: 17, letterSpacing: '0.35em', color: '#caa86a', marginTop: 6, textShadow: '0 2px 12px rgba(0,0,0,0.9)'}}>
          {source.toUpperCase()}
        </div>
      </AbsoluteFill>
      {line && (
        <AbsoluteFill style={{justifyContent: 'flex-end', alignItems: 'center', paddingBottom: LETTERBOX + 30}}>
          <div
            style={{
              maxWidth: 1400,
              textAlign: 'center',
              textWrap: 'balance',
              fontFamily: cormorant,
              fontStyle: 'italic',
              fontWeight: 500,
              fontSize: 44,
              lineHeight: 1.22,
              color: '#f7f0e0',
              textShadow: '0 2px 18px rgba(0,0,0,0.95), 0 0 3px rgba(0,0,0,0.9)',
            }}
          >
            {line.text}
          </div>
        </AbsoluteFill>
      )}
    </AbsoluteFill>
  );
};
