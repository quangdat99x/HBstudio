import React from 'react';
import {AbsoluteFill, interpolate, useCurrentFrame} from 'remotion';
import {clamp} from '../lib/anim';
import {HEIGHT, WIDTH} from '../timeline';
import {CamKey, Desk, DeskCam, DeskTone, FocusPool} from './desk';
import {CardSpec, PhotoCard, TYPE_FONT} from './cards';

// The investigation board: real portraits and logos pinned up, red string drawn from one to the next as the
// narration makes each link ("four of Dialog's members were already inside Bilderberg"). This is the picture of
// a rabbit-hole film: every link is a named person who belongs to both ends.

export type BoardCard = CardSpec & {id: string};
export type Link = {a: string; b: string; at: number; label?: string; color?: string};

const pinPoint = (c: BoardCard): [number, number] => {
  const hPx = (c.w * WIDTH) / (c.aspect ?? 1.4);
  return [c.x * WIDTH, c.y * HEIGHT - hPx / 2 - 2];
};

const String3: React.FC<{a: [number, number]; b: [number, number]; at: number; color: string; label?: string}> = ({a, b, at, color, label}) => {
  const f = useCurrentFrame();
  if (f < at) return null;
  const p = interpolate(f, [at, at + 20], [0, 1], clamp);
  const dist = Math.hypot(b[0] - a[0], b[1] - a[1]);
  const mx = (a[0] + b[0]) / 2;
  const my = (a[1] + b[1]) / 2 + dist * 0.09; // the string sags
  return (
    <>
      <svg style={{position: 'absolute', left: 0, top: 0, overflow: 'visible', zIndex: 50}} width={1} height={1}>
        <path d={`M ${a[0]} ${a[1]} Q ${mx} ${my} ${b[0]} ${b[1]}`} fill="none" stroke="rgba(0,0,0,0.45)" strokeWidth={5}
          transform="translate(4 9)" pathLength={1} strokeDasharray={1} strokeDashoffset={1 - p} />
        <path d={`M ${a[0]} ${a[1]} Q ${mx} ${my} ${b[0]} ${b[1]}`} fill="none" stroke={color} strokeWidth={4} strokeLinecap="round"
          pathLength={1} strokeDasharray={1} strokeDashoffset={1 - p} />
      </svg>
      {label && p > 0.9 && (
        <div style={{position: 'absolute', left: mx, top: (a[1] + b[1]) / 2 + dist * 0.045, transform: 'translate(-50%, -50%) rotate(-2deg)', zIndex: 51,
          background: '#f3ecd9', padding: '4px 12px', fontFamily: TYPE_FONT, fontSize: 24, color: '#1b1814', boxShadow: '0 6px 14px rgba(0,0,0,0.5)',
          opacity: interpolate(f, [at + 18, at + 26], [0, 1], clamp), whiteSpace: 'nowrap'}}>
          {label}
        </div>
      )}
    </>
  );
};

// Automatic camera: wide on the first cards, then drift toward each new link as it is drawn.
const boardCamera = (cards: BoardCard[], links: Link[], duration: number): CamKey[] => {
  const byId = Object.fromEntries(cards.map((c) => [c.id, c]));
  const keys: CamKey[] = [{at: 0, x: 0.5, y: 0.5, zoom: 1.02}];
  [...links].sort((p, q) => p.at - q.at).forEach((l) => {
    const a = byId[l.a];
    const b = byId[l.b];
    if (!a || !b) return;
    keys.push({at: Math.max(1, l.at - 10), x: (a.x + b.x) / 2, y: (a.y + b.y) / 2, zoom: 1.12});
  });
  if (keys.length > 1) keys.push({at: duration, x: 0.5, y: 0.5, zoom: 1.08});
  return keys;
};

export const BoardShot: React.FC<{cards: BoardCard[]; links?: Link[]; duration: number; tone?: DeskTone; cam?: CamKey[]; blur?: number}> = ({
  cards, links = [], duration, tone = 'cork', cam, blur = 3,
}) => {
  const byId = Object.fromEntries(cards.map((c) => [c.id, c]));
  const keys = cam?.length ? cam : boardCamera(cards, links, duration);
  return (
    <AbsoluteFill>
      <Desk tone={tone} />
      <FocusPool blur={blur}>
        <DeskCam keys={keys} duration={duration}>
          {cards.map((c, i) => <PhotoCard key={c.id} c={{pin: true, frame: 'print', tilt: [0, 0], z: 2 + i, ...c}} />)}
          {links.map((l, i) => {
            const a = byId[l.a];
            const b = byId[l.b];
            if (!a || !b) throw new Error(`board link ${l.a} -> ${l.b}: no card with that id`);
            return <String3 key={i} a={pinPoint(a)} b={pinPoint(b)} at={l.at} color={l.color ?? '#c3141f'} label={l.label} />;
          })}
        </DeskCam>
      </FocusPool>
    </AbsoluteFill>
  );
};
