import React from 'react';
import {AbsoluteFill, Easing, interpolate, useCurrentFrame} from 'remotion';
import {loadFont as loadCinzel} from '@remotion/google-fonts/Cinzel';
import {loadFont as loadCormorant} from '@remotion/google-fonts/CormorantGaramond';
import {clamp} from '../lib/anim';
import {LETTERBOX} from './Overlays';

export const {fontFamily: cinzel} = loadCinzel('normal', {weights: ['400', '700'], subsets: ['latin']});
export const {fontFamily: cormorant} = loadCormorant('italic', {weights: ['500'], subsets: ['latin']});

const PER_WORD = 2.4;

// Subtitle that reveals word by word (fade + rise + unblur), with an optional citation. With `words` (the frame
// each word is spoken, from src/voice.json) every word appears as the narrator says it.
export const Caption: React.FC<{text: string; from: number; to: number; cite?: string; words?: number[]}> = ({
  text,
  from,
  to,
  cite,
  words: spoken,
}) => {
  const frame = useCurrentFrame();
  if (frame < from - 1 || frame > to + 1) return null;
  const words = text.split(' ');
  const at = (i: number) => (spoken ? spoken[Math.min(i, spoken.length - 1)] - 3 : from + i * PER_WORD);
  const out = interpolate(frame, [to - 14, to], [1, 0], clamp);
  const done = at(words.length - 1) + 10;
  const citeIn = interpolate(frame, [done, done + 16], [0, 1], clamp);
  return (
    <AbsoluteFill
      style={{justifyContent: 'flex-end', alignItems: 'center', paddingBottom: LETTERBOX + 34, opacity: out}}
    >
      <div
        style={{
          maxWidth: 1380,
          textAlign: 'center',
          textWrap: 'balance',
          fontFamily: cormorant,
          fontStyle: 'italic',
          fontWeight: 500,
          fontSize: 46,
          lineHeight: 1.22,
          color: '#f1e8d4',
          textShadow: '0 2px 22px rgba(0,0,0,0.95), 0 0 3px rgba(0,0,0,0.9)',
        }}
      >
        {words.map((w, i) => {
          const p = interpolate(frame, [at(i), at(i) + 16], [0, 1], {
            ...clamp,
            easing: Easing.out(Easing.cubic),
          });
          return (
            <span
              key={i}
              style={{
                display: 'inline-block',
                opacity: p,
                transform: `translateY(${(1 - p) * 14}px)`,
                filter: `blur(${((1 - p) * 7).toFixed(2)}px)`,
                marginRight: '0.26em',
              }}
            >
              {w}
            </span>
          );
        })}
      </div>
      {cite && (
        <div
          style={{
            marginTop: 12,
            fontFamily: cinzel,
            fontSize: 19,
            letterSpacing: '0.42em',
            color: '#caa86a',
            opacity: citeIn,
            textShadow: '0 2px 14px rgba(0,0,0,0.95)',
          }}
        >
          {cite}
        </div>
      )}
    </AbsoluteFill>
  );
};

export const Label: React.FC<{text: string; sub?: string; from: number; to: number; top?: number}> = ({
  text,
  sub,
  from,
  to,
  top = 175,
}) => {
  const frame = useCurrentFrame();
  const o = Math.min(
    interpolate(frame, [from, from + 22], [0, 1], clamp),
    interpolate(frame, [to - 18, to], [1, 0], clamp),
  );
  if (o <= 0) return null;
  const spacing = interpolate(frame, [from, to], [0.62, 0.48], clamp);
  return (
    <AbsoluteFill style={{alignItems: 'center', paddingTop: top, opacity: o}}>
      <div style={{fontFamily: cinzel, fontSize: 30, letterSpacing: `${spacing}em`, color: '#e2cf9f', paddingLeft: `${spacing}em`}}>
        {text}
      </div>
      {sub && (
        <div style={{marginTop: 14, fontFamily: cinzel, fontSize: 17, letterSpacing: '0.5em', color: '#9e8a60', paddingLeft: '0.5em'}}>
          {sub}
        </div>
      )}
    </AbsoluteFill>
  );
};
