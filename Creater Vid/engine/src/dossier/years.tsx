import React from 'react';
import {AbsoluteFill, Easing, interpolate, useCurrentFrame} from 'remotion';
import {loadFont as loadInter} from '@remotion/google-fonts/Inter';
import {clamp} from '../lib/anim';
import {HEIGHT, WIDTH} from '../timeline';
import {Desk, DeskTone} from './desk';
import {CardLoose, PhotoCard} from './cards';

// Time passing over a real portrait or photo: big years slide along a ruled line as the narration moves through
// them ("1950s … 1970s … 1990s"), the current one sharp and bright, the others small and dim.

const {fontFamily: inter} = loadInter('normal', {weights: ['800'], subsets: ['latin']});

export type YearMark = {label: string; at: number};

export const YearsShot: React.FC<{years: YearMark[]; card?: CardLoose; duration: number; tone?: DeskTone; y?: number}> = ({
  years, card, duration, tone = 'night', y = 0.5,
}) => {
  const f = useCurrentFrame();
  const ys = [...years].sort((a, b) => a.at - b.at);
  // fractional index of the year in focus: eases from one to the next over 16 frames at each `at`
  let idx = 0;
  ys.forEach((m, i) => {
    if (i > 0) idx += interpolate(f, [m.at - 8, m.at + 8], [0, 1], {...clamp, easing: Easing.inOut(Easing.cubic)});
  });
  const gap = WIDTH * 0.36;
  const push = interpolate(f, [0, duration], [1, 1.05], clamp);
  const lineO = interpolate(f, [(ys[0]?.at ?? 0) - 10, ys[0]?.at ?? 0], [0, 1], clamp);
  return (
    <AbsoluteFill>
      <Desk tone={tone} />
      <AbsoluteFill style={{transform: `scale(${push})`}}>
        {card && <PhotoCard c={{x: 0.5, y: 0.45, w: 0.24, at: 0, enter: 'fade', tone: 'bw', ...card}} />}
        <div style={{position: 'absolute', left: 0, right: 0, top: y * HEIGHT, height: 3, background: 'rgba(240,232,215,0.75)', opacity: lineO,
          boxShadow: '0 0 12px rgba(0,0,0,0.8)'}} />
        {Array.from({length: 13}, (_, k) => {
          const x = WIDTH / 2 + (k - 6) * (gap / 4) - ((idx * gap) % (gap / 4));
          return <div key={k} style={{position: 'absolute', left: x, top: y * HEIGHT - 9, width: 2, height: 20, background: 'rgba(240,232,215,0.6)', opacity: lineO}} />;
        })}
        {ys.map((m, i) => {
          const d = i - idx; // 0 = in focus
          if (Math.abs(d) > 1.6 || f < m.at - 24) return null;
          const s = interpolate(Math.abs(d), [0, 1], [1, 0.45], clamp);
          const o = interpolate(Math.abs(d), [0, 1, 1.6], [1, 0.35, 0], clamp) * interpolate(f, [m.at - 24, m.at - 8], [0, 1], clamp);
          return (
            <div key={i} style={{position: 'absolute', left: WIDTH / 2 + d * gap, top: y * HEIGHT, transform: `translate(-50%, -50%) scale(${s})`, opacity: o, zIndex: 10,
              fontFamily: inter, fontWeight: 800, fontSize: 190, color: '#fbf6ea', letterSpacing: '-0.01em',
              textShadow: '0 6px 40px rgba(0,0,0,0.85), 0 0 2px rgba(0,0,0,0.6)', whiteSpace: 'nowrap'}}>
              {m.label}
            </div>
          );
        })}
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
