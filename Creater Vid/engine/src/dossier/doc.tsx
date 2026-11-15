import React from 'react';
import {AbsoluteFill, Img, interpolate, staticFile, useCurrentFrame} from 'remotion';
import {loadFont as loadCaveat} from '@remotion/google-fonts/Caveat';
import {clamp} from '../lib/anim';
import {HEIGHT, WIDTH} from '../timeline';
import {CamKey, Desk, DeskCam, DeskTone, FocusPool} from './desk';
import {CardSpec, INK, Ink, PhotoCard, StampSpec, Stamp} from './cards';

// A real document (Wikipedia page, newspaper article, declassified memo, membership roster, court filing) shown as
// a page lying on the desk. The camera travels to each marked passage when the narrator reads it and a marker
// sweeps across the words line by line, in time with the voice. Red-pen notes and arrows can be written on it.
// Page images and the boxes of the phrases come from scripts/pagecap.mjs (web pages) or are measured by hand
// (scans: fractions of the page image).

const {fontFamily: caveat} = loadCaveat('normal', {weights: ['700'], subsets: ['latin', 'latin-ext']});

export type Box = [number, number, number, number]; // x, y, w, h as fractions of the page image
export type Mark = {
  boxes: Box[];                 // one box per line of the passage, in reading order
  at: number;                   // frame the sweep starts (or "line:phrase", resolved before)
  dur?: number;                 // frames for the whole sweep (default: as long as the phrase is spoken, or 0.6 s per line)
  spoken?: number;              // set by resolveShot when `at` came from the narration
  color?: 'yellow' | 'green' | 'pink' | 'blue';
  style?: 'marker' | 'box' | 'underline';
  focus?: boolean;              // camera travels to it (default true)
  zoom?: number;                // zoom on this passage (default: passage ~55 % of the frame width)
};
export type Note = {text: string; at: number; x: number; y: number; to?: [number, number]; size?: number; ink?: Ink};

export type DocSpec = {
  src: string;                  // under public/ (e.g. "docs/wiki_fridman.png")
  aspect: number;               // width / height of the page image
  w?: number;                   // page width on the desk, frame fraction (default 0.82)
  rot?: number;                 // degrees (default -1.2)
  marks?: Mark[];
  notes?: Note[];
  stamp?: StampSpec;
  cam?: CamKey[];               // explicit camera instead of the automatic one
  blur?: number;                // depth of field at the edges (default 4, 0 = off)
};

const MARKER = {yellow: 'rgba(255, 214, 10, 0.58)', green: 'rgba(120, 230, 120, 0.5)', pink: 'rgba(255, 120, 170, 0.5)', blue: 'rgba(110, 180, 255, 0.5)'};

// Where the page sits on the desk (frame px at zoom 1): centred horizontally, top at 12 % of the frame.
const pageRect = (d: DocSpec) => {
  const w = (d.w ?? 0.82) * WIDTH;
  return {left: (WIDTH - w) / 2, top: HEIGHT * 0.12, w, h: w / d.aspect};
};

// Automatic camera: open a little wider on the first passage, travel to each passage ~14 frames before its sweep,
// hold, and drift on. A page with no marks: slow travel down its top half.
export const docCamera = (d: DocSpec, duration: number): CamKey[] => {
  if (d.cam?.length) return d.cam;
  const r = pageRect(d);
  const marks = (d.marks ?? []).filter((m) => m.focus !== false && m.boxes.length).sort((a, b) => a.at - b.at);
  const fx = (x: number) => (r.left + x * r.w) / WIDTH;
  const fy = (y: number) => (r.top + y * r.h) / HEIGHT;
  if (!marks.length) {
    return [{at: 0, x: 0.5, y: fy(0.08) + 0.32, zoom: 1.15}, {at: duration, x: 0.5, y: fy(0.3) + 0.2, zoom: 1.3}];
  }
  const keyOf = (m: Mark, at: number): CamKey => {
    const x0 = Math.min(...m.boxes.map((b) => b[0]));
    const x1 = Math.max(...m.boxes.map((b) => b[0] + b[2]));
    const y0 = Math.min(...m.boxes.map((b) => b[1]));
    const y1 = Math.max(...m.boxes.map((b) => b[1] + b[3]));
    const span = ((x1 - x0) * r.w) / WIDTH;
    const zoom = m.zoom ?? Math.max(1.15, Math.min(2.6, 0.58 / Math.max(0.05, span)));
    return {at, x: fx((x0 + x1) / 2), y: fy((y0 + y1) / 2), zoom};
  };
  const keys: CamKey[] = [];
  const first = keyOf(marks[0], 0);
  keys.push({...first, zoom: first.zoom * 0.78});
  marks.forEach((m, i) => {
    const k = keyOf(m, Math.max(1, m.at - 14));
    if (i === 0 && k.at < 20) keys.push({...k, at: Math.max(keys[0].at + 1, m.at)});
    else keys.push(k);
    keys.push({...k, at: m.at + sweepLen(m) + 6});
  });
  // a red-pen note: frame the note together with what its arrow points at, while it is written
  (d.notes ?? []).forEach((n) => {
    const tx = n.to ? n.to[0] : n.x;
    const ty = n.to ? n.to[1] : n.y;
    const textW = (n.size ?? 0.035) * n.text.length * 0.45;
    const x0 = Math.min(n.x, tx);
    const x1 = Math.max(n.x + textW, tx);
    const span = ((x1 - x0) * r.w) / WIDTH;
    const k: CamKey = {at: Math.max(1, n.at - 10), x: fx((x0 + x1) / 2), y: fy((n.y + ty) / 2), zoom: Math.max(1.15, Math.min(2.2, 0.6 / Math.max(0.05, span)))};
    keys.push(k, {...k, at: n.at + 30 + n.text.length * 2});
  });
  // a later key wins over an earlier one that would land after it (a note written while a mark still holds)
  const sorted = keys.sort((a, b) => a.at - b.at);
  return sorted.filter((k, i) => !sorted.slice(i + 1).some((q) => q.at === k.at));
};

const sweepLen = (m: Mark) => m.dur ?? m.spoken ?? Math.round(18 * m.boxes.length);

// Marker sweeping box by box: each line takes a share of the time proportional to its width (reading speed).
const Highlight: React.FC<{m: Mark; pw: number; ph: number}> = ({m, pw, ph}) => {
  const f = useCurrentFrame();
  if (f < m.at) return null;
  const total = m.boxes.reduce((s, b) => s + b[2], 0) || 1;
  const len = sweepLen(m);
  let t0 = m.at;
  const style = m.style ?? 'marker';
  const color = MARKER[m.color ?? 'yellow'];
  return (
    <>
      {m.boxes.map((b, i) => {
        const d = Math.max(3, (len * b[2]) / total);
        const p = interpolate(f, [t0, t0 + d], [0, 1], clamp);
        t0 += d;
        const [x, y, w, h] = [b[0] * pw, b[1] * ph, b[2] * pw, b[3] * ph];
        if (style === 'underline')
          return <div key={i} style={{position: 'absolute', left: x, top: y + h * 0.98, width: w * p, height: Math.max(3, h * 0.12), background: INK.red, borderRadius: 2}} />;
        if (style === 'box')
          return (
            <svg key={i} style={{position: 'absolute', left: x - 8, top: y - 6, overflow: 'visible'}} width={w + 16} height={h + 12}>
              <rect x={2} y={2} width={w + 12} height={h + 8} rx={6} fill="none" stroke={INK.red} strokeWidth={Math.max(3, h * 0.09)}
                pathLength={1} strokeDasharray={1} strokeDashoffset={1 - p} />
            </svg>
          );
        return (
          <div key={i} style={{position: 'absolute', left: x - h * 0.1, top: y - h * 0.08, width: (w + h * 0.2) * p, height: h * 1.16, background: color,
            mixBlendMode: 'multiply', borderRadius: h * 0.18, transform: 'skewX(-4deg)'}} />
        );
      })}
    </>
  );
};

// Red pen: the words write themselves (clip from left), an arrow draws to the point it is about.
const PenNote: React.FC<{n: Note; pw: number; ph: number}> = ({n, pw, ph}) => {
  const f = useCurrentFrame();
  if (f < n.at) return null;
  const size = (n.size ?? 0.035) * pw;
  const write = interpolate(f, [n.at, n.at + Math.max(10, n.text.length * 2.2)], [0, 100], clamp);
  const arrowP = interpolate(f, [n.at + 6, n.at + 22], [0, 1], clamp);
  const color = INK[n.ink ?? 'red'];
  const [x, y] = [n.x * pw, n.y * ph];
  let arrow: React.ReactNode = null;
  if (n.to) {
    const [tx, ty] = [n.to[0] * pw, n.to[1] * ph];
    const sx = x + (tx > x ? size * n.text.length * 0.42 : -size * 0.3);
    const sy = y;
    const mx = (sx + tx) / 2;
    const my = Math.min(sy, ty) - Math.abs(tx - sx) * 0.18;
    const ang = Math.atan2(ty - my, tx - mx);
    const hl = size * 0.55;
    arrow = (
      <svg style={{position: 'absolute', left: 0, top: 0, overflow: 'visible'}} width={1} height={1}>
        <path d={`M ${sx} ${sy} Q ${mx} ${my} ${tx} ${ty}`} fill="none" stroke={color} strokeWidth={size * 0.09} strokeLinecap="round"
          pathLength={1} strokeDasharray={1} strokeDashoffset={1 - arrowP} />
        {arrowP > 0.97 && (
          <path d={`M ${tx - hl * Math.cos(ang - 0.45)} ${ty - hl * Math.sin(ang - 0.45)} L ${tx} ${ty} L ${tx - hl * Math.cos(ang + 0.45)} ${ty - hl * Math.sin(ang + 0.45)}`}
            fill="none" stroke={color} strokeWidth={size * 0.09} strokeLinecap="round" strokeLinejoin="round" />
        )}
      </svg>
    );
  }
  return (
    <>
      {arrow}
      <div style={{position: 'absolute', left: x, top: y, transform: 'translateY(-50%) rotate(-3deg)', fontFamily: caveat, fontWeight: 700, fontSize: size, color,
        whiteSpace: 'nowrap', clipPath: `inset(-20% ${100 - write}% -20% -5%)`}}>
        {n.text}
      </div>
    </>
  );
};

export const DocPage: React.FC<{d: DocSpec}> = ({d}) => {
  const r = pageRect(d);
  return (
    <div style={{position: 'absolute', left: r.left, top: r.top, width: r.w, height: r.h, transform: `rotate(${d.rot ?? -1.2}deg) rotateX(4deg)`,
      boxShadow: '0 30px 70px rgba(0,0,0,0.65), 0 2px 8px rgba(0,0,0,0.5)', background: '#fff'}}>
      <Img src={staticFile(d.src)} style={{width: '100%', height: '100%', display: 'block'}} />
      {/* paper: faint warm tone and uneven light, so a screenshot reads as a printed page */}
      <div style={{position: 'absolute', inset: 0, background: 'linear-gradient(160deg, rgba(255,246,225,0.10) 0%, rgba(0,0,0,0) 45%, rgba(40,25,5,0.14) 100%)', mixBlendMode: 'multiply'}} />
      {(d.marks ?? []).map((m, i) => <Highlight key={i} m={m} pw={r.w} ph={r.h} />)}
      {(d.notes ?? []).map((n, i) => <PenNote key={i} n={n} pw={r.w} ph={r.h} />)}
      {d.stamp && <Stamp s={d.stamp} boxW={r.w} boxH={r.h} />}
    </div>
  );
};

// A whole shot: desk, camera, the page, and optional cards laid over it (portraits sliding onto a roster).
export const DocShot: React.FC<{d: DocSpec; duration: number; tone?: DeskTone; cards?: CardSpec[]}> = ({d, duration, tone = 'night', cards = []}) => {
  const keys = docCamera(d, duration);
  return (
    <AbsoluteFill>
      <Desk tone={tone} />
      <FocusPool blur={d.blur ?? 4}>
        <DeskCam keys={keys} duration={duration}>
          <DocPage d={d} />
          {cards.map((c, i) => <PhotoCard key={i} c={{z: 5 + i, ...c}} />)}
        </DeskCam>
      </FocusPool>
    </AbsoluteFill>
  );
};
