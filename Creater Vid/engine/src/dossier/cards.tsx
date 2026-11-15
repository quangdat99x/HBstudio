import React from 'react';
import {Img, interpolate, spring, staticFile, useCurrentFrame} from 'remotion';
import {loadFont as loadSpecial} from '@remotion/google-fonts/SpecialElite';
import {loadFont as loadInter} from '@remotion/google-fonts/Inter';
import {clamp} from '../lib/anim';
import {FPS, HEIGHT, WIDTH} from '../timeline';

// A real photograph handled like a print from a case file: white border, shadow, a slight tilt, dropped onto the
// desk when the narrator names it. Options: name typed on a tag, a blurred-dark "unknown person" that resolves into
// the face, black redaction bars, a rubber stamp, a pin.

const {fontFamily: special} = loadSpecial('normal', {weights: ['400'], subsets: ['latin', 'latin-ext']});
const {fontFamily: inter} = loadInter('normal', {weights: ['600', '800'], subsets: ['latin', 'latin-ext', 'cyrillic', 'vietnamese']});
export const TYPE_FONT = special;
export const LABEL_FONT = inter;

export type Ink = 'red' | 'green' | 'amber' | 'black' | 'blue';
export const INK: Record<Ink, string> = {red: '#b3121f', green: '#1d6b35', amber: '#b86d0a', black: '#141414', blue: '#1b3f8f'};

export type StampSpec = {text: string; at: number; ink?: Ink; x?: number; y?: number; rot?: number; size?: number};

export type CardSpec = {
  src: string;                    // under public/ (e.g. "evidence/thiel_2016.jpg")
  aspect?: number;                // width / height of the picture (manifest), default 1.4
  x: number; y: number;           // centre on the desk, frame fractions at zoom 1
  w: number;                      // picture width, frame fraction
  rot?: number;                   // degrees in the desk plane
  tilt?: [number, number];        // rotateX, rotateY in degrees (the print is not flat on the glass)
  at?: number;                    // frame it lands (before: invisible)
  enter?: 'drop' | 'slide-left' | 'slide-right' | 'rise' | 'fade' | 'none';
  frame?: 'print' | 'polaroid' | 'clean' | 'none';
  tone?: 'none' | 'bw' | 'sepia' | 'archive' | 'red' | 'cold';
  label?: string;                 // name / caption typed under the picture
  labelAt?: number;
  labelStyle?: 'tag' | 'type' | 'caps';  // black tab · typewriter on the border · thin spaced capitals on the desk
  reveal?: number;                // frame at which the hidden (dark, blurred) picture resolves into the face
  redact?: [number, number, number, number][]; // black bars, fractions of the picture (x, y, w, h)
  stamp?: StampSpec;
  pin?: boolean;
  until?: number;                 // frame it is lifted away (optional)
  z?: number;                     // stacking order
};

// A card whose place has a default (the portrait of a years shot, the photo beside a logo).
export type CardLoose = Omit<CardSpec, 'x' | 'y' | 'w'> & Partial<Pick<CardSpec, 'x' | 'y' | 'w'>>;

const TONE_FILTER: Record<NonNullable<CardSpec['tone']>, string> = {
  none: 'contrast(1.03)',
  bw: 'grayscale(1) contrast(1.12)',
  sepia: 'grayscale(0.4) sepia(0.65) contrast(1.05)',
  archive: 'grayscale(1) contrast(1.18) brightness(0.93)',
  red: 'grayscale(1) sepia(1) hue-rotate(-38deg) saturate(3.2) contrast(1.15) brightness(0.85)',
  cold: 'grayscale(0.55) contrast(1.08) brightness(0.95) hue-rotate(185deg) sepia(0.15)',
};

const enterPose = (e: CardSpec['enter'], q: number) => {
  const r = 1 - q; // 1 before landing, 0 when landed
  switch (e) {
    case 'slide-left': return {dx: -0.45 * r, dy: 0.02 * r, s: 1, dr: -6 * r, o: 1};
    case 'slide-right': return {dx: 0.45 * r, dy: 0.02 * r, s: 1, dr: 6 * r, o: 1};
    case 'rise': return {dx: 0, dy: 0.12 * r, s: 1, dr: 0, o: Math.min(1, q * 2)};
    case 'fade': return {dx: 0, dy: 0, s: 1 + 0.04 * r, dr: 0, o: q};
    case 'none': return {dx: 0, dy: 0, s: 1, dr: 0, o: 1};
    default: return {dx: 0.02 * r, dy: -0.06 * r, s: 1 + 0.3 * r, dr: 9 * r, o: Math.min(1, q * 3)}; // drop
  }
};

export const PhotoCard: React.FC<{c: CardSpec}> = ({c}) => {
  const f = useCurrentFrame();
  const at = c.at ?? 0;
  if (f < at - 1) return null;
  const q = c.enter === 'none' ? 1 : spring({frame: f - at, fps: FPS, config: {damping: 16, stiffness: 120, mass: 0.9}});
  const p = enterPose(c.enter, Math.min(1, q));
  const lift = c.until !== undefined ? interpolate(f, [c.until, c.until + 14], [0, 1], clamp) : 0;
  if (lift >= 1) return null;
  const aspect = c.aspect ?? 1.4;
  const wPx = c.w * WIDTH;
  const hPx = wPx / aspect;
  const fr = c.frame ?? 'print';
  const bw = fr === 'none' || fr === 'clean' ? 0 : Math.max(8, wPx * 0.035);
  const bottom = fr === 'polaroid' ? Math.max(40, wPx * 0.16) : bw;
  // shadow grows as the print settles; a print still in the air throws a softer, offset shadow
  const air = 1 - Math.min(1, q);
  const shadow = `0 ${18 + air * 50}px ${40 + air * 60}px rgba(0,0,0,${0.55 - air * 0.2}), 0 2px 6px rgba(0,0,0,0.5)`;
  const hidden = c.reveal !== undefined ? interpolate(f, [c.reveal, c.reveal + 16], [1, 0], clamp) : 0;
  const filter = `${TONE_FILTER[c.tone ?? 'none']} blur(${(hidden * 14).toFixed(2)}px) brightness(${(1 - hidden * 0.82).toFixed(3)})`;
  const [rx, ry] = c.tilt ?? [0, 0];
  const transform = [
    `translate(${((c.x + p.dx) * WIDTH - (wPx + 2 * bw) / 2).toFixed(1)}px, ${((c.y + p.dy - lift * 0.05) * HEIGHT - (hPx + bw + bottom) / 2).toFixed(1)}px)`,
    `rotate(${((c.rot ?? 0) + p.dr).toFixed(2)}deg)`,
    `rotateX(${rx}deg) rotateY(${ry}deg)`,
    `scale(${(p.s + lift * 0.05).toFixed(4)})`,
  ].join(' ');
  return (
    <div style={{position: 'absolute', left: 0, top: 0, transform, opacity: p.o * (1 - lift), zIndex: c.z ?? 1}}>
      <div style={{padding: `${bw}px ${bw}px ${bottom}px ${bw}px`, background: fr === 'none' || fr === 'clean' ? 'transparent' : '#efeae0',
        boxShadow: fr === 'none' ? undefined : shadow, position: 'relative'}}>
        <div style={{width: wPx, height: hPx, overflow: 'hidden', position: 'relative', background: '#111'}}>
          <Img src={staticFile(c.src)} style={{width: '100%', height: '100%', objectFit: 'cover', filter}} />
          {(c.redact ?? []).map(([x, y, w, h], i) => (
            <div key={i} style={{position: 'absolute', left: `${x * 100}%`, top: `${y * 100}%`, width: `${w * 100}%`, height: `${h * 100}%`, background: '#050505'}} />
          ))}
          {/* paper sheen: a print catches the light a little */}
          <div style={{position: 'absolute', inset: 0, background: 'linear-gradient(125deg, rgba(255,255,255,0.08) 0%, rgba(255,255,255,0) 40%, rgba(0,0,0,0.12) 100%)'}} />
        </div>
        {c.label && (c.labelStyle === 'type' || fr === 'polaroid') && (
          <TypedLabel text={c.label} at={c.labelAt ?? at + 10} style={{position: 'absolute', left: bw, right: bw, bottom: Math.max(4, (bottom - wPx * 0.05) / 2),
            fontFamily: special, fontSize: Math.max(18, wPx * 0.05), color: '#1d1a16', textAlign: 'center'}} />
        )}
        {c.pin && <Pin />}
        {c.stamp && <Stamp s={c.stamp} boxW={wPx + 2 * bw} boxH={hPx + bw + bottom} />}
      </div>
      {c.label && c.labelStyle === 'tag' && fr !== 'polaroid' && (
        <TypedLabel text={c.label} at={c.labelAt ?? at + 10} style={{marginTop: 10, display: 'inline-block', padding: '6px 14px', background: '#0b0b0b',
          fontFamily: inter, fontWeight: 800, letterSpacing: '0.06em', fontSize: Math.max(18, wPx * 0.045), color: '#f4f1ea', textTransform: 'uppercase'}} />
      )}
      {c.label && (c.labelStyle ?? 'caps') === 'caps' && fr !== 'polaroid' && (
        <TypedLabel text={c.label} at={c.labelAt ?? at + 10} style={{marginTop: 18, width: wPx + 2 * bw, textAlign: 'center', fontFamily: inter, fontWeight: 600,
          letterSpacing: '0.32em', fontSize: Math.max(18, wPx * 0.04), color: '#ece5d6', textTransform: 'uppercase', textShadow: '0 2px 12px rgba(0,0,0,0.9)'}} />
      )}
    </div>
  );
};

// Text typed one character every 2 frames, with a caret while it types.
export const TypedLabel: React.FC<{text: string; at: number; style: React.CSSProperties; cps?: number}> = ({text, at, style, cps = 15}) => {
  const f = useCurrentFrame();
  if (f < at) return <div style={{...style, visibility: 'hidden'}}>{text}</div>;
  const n = Math.min(text.length, Math.floor(((f - at) / FPS) * cps));
  const caret = n < text.length && Math.floor(f / 6) % 2 === 0;
  return (
    <div style={style}>
      {text.slice(0, n)}
      <span style={{opacity: 0}}>{text.slice(n)}</span>
      {caret && <span style={{position: 'absolute', opacity: 0.8}}>▌</span>}
    </div>
  );
};

const Pin: React.FC = () => (
  <div style={{position: 'absolute', left: '50%', top: -10, width: 26, height: 26, marginLeft: -13, borderRadius: '50%',
    background: 'radial-gradient(circle at 35% 30%, #ff8a80 0%, #c62828 45%, #6d0f0f 100%)', boxShadow: '3px 8px 10px rgba(0,0,0,0.55)'}} />
);

// A rubber stamp slammed onto the card: overshoot, a jolt, rough ink. The words come from the script's claim status
// (VERIFIED / DISPUTED / UNVERIFIED) or the documents themselves (CLASSIFIED, DECLASSIFIED, DENIED) — never a verdict
// on a person that the sources do not state.
export const Stamp: React.FC<{s: StampSpec; boxW: number; boxH: number}> = ({s, boxW, boxH}) => {
  const f = useCurrentFrame();
  if (f < s.at) return null;
  const k = f - s.at;
  const sc = k < 5 ? interpolate(k, [0, 5], [2.3, 0.94]) : interpolate(k, [5, 9], [0.94, 1], clamp);
  const o = interpolate(k, [0, 3], [0, 0.88], clamp);
  const color = INK[s.ink ?? 'red'];
  const size = (s.size ?? 0.11) * boxW;
  const id = `ink-${s.text.replace(/\W/g, '')}`;
  return (
    <div style={{position: 'absolute', left: (s.x ?? 0.5) * boxW, top: (s.y ?? 0.5) * boxH, transform: `translate(-50%, -50%) rotate(${s.rot ?? -12}deg) scale(${sc})`,
      opacity: o, pointerEvents: 'none'}}>
      <svg width={0} height={0} style={{position: 'absolute'}}>
        <filter id={id}>
          <feTurbulence type="fractalNoise" baseFrequency="0.75" numOctaves={2} seed={7} result="n" />
          <feColorMatrix in="n" type="matrix" values="0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 -2.2 1.6" result="holes" />
          <feComposite in="SourceGraphic" in2="holes" operator="in" />
        </filter>
      </svg>
      <div style={{filter: `url(#${id})`, border: `${Math.max(4, size * 0.09)}px solid ${color}`, borderRadius: size * 0.12, padding: `${size * 0.12}px ${size * 0.35}px`,
        color, fontFamily: inter, fontWeight: 800, fontSize: size * 0.62, letterSpacing: '0.08em', whiteSpace: 'nowrap', textTransform: 'uppercase', mixBlendMode: 'multiply'}}>
        {s.text}
      </div>
    </div>
  );
};
