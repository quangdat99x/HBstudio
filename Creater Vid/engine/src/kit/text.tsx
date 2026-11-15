import React from 'react';
import {AbsoluteFill, Easing, interpolate, random, spring, useCurrentFrame} from 'remotion';
import {loadFont as loadInter} from '@remotion/google-fonts/Inter';
import {loadFont as loadOswald} from '@remotion/google-fonts/Oswald';
import {loadFont as loadPlexMono} from '@remotion/google-fonts/IBMPlexMono';
import {cinzel, cormorant} from '../components/Text';
import {LETTERBOX} from '../components/Overlays';
import {clamp} from '../lib/anim';
import {FPS} from '../timeline';

// Animated text (Motion kit): mask-reveal titles, chapter cards, lower thirds, typewriter stamps, decoding text,
// count-ups, punch words, pull quotes and a marker highlight. Every component takes `from`/`to` (frames local to
// the scene) and a theme. Source of the moves: Motion Prompt (MIT) #005 mask reveal, #002 stagger, #006 typewriter,
// #129 text scramble, #007 count-up, #008 kinetic typography, #010 overshoot, #004 line draw, #080 highlighter.

const {fontFamily: inter} = loadInter('normal', {weights: ['400', '600', '800'], subsets: ['latin', 'latin-ext', 'cyrillic', 'vietnamese']});
const {fontFamily: oswald} = loadOswald('normal', {weights: ['500', '700'], subsets: ['latin', 'latin-ext', 'cyrillic', 'vietnamese']});
const {fontFamily: plexMono} = loadPlexMono('normal', {weights: ['500'], subsets: ['latin', 'latin-ext', 'cyrillic', 'vietnamese']});

export type KitTheme = {
  title: string; titleWeight: number; titleCase: 'upper' | 'none'; tracking: number;
  body: string; bodyStyle: 'italic' | 'normal';
  mono: string;
  color: string; accent: string; dim: string; shadow: string;
};

// Documentary: Cinzel + Cormorant, warm ivory and old gold (matches Caption / Label).
export const DOC_THEME: KitTheme = {
  title: cinzel, titleWeight: 700, titleCase: 'upper', tracking: 0.16,
  body: cormorant, bodyStyle: 'italic', mono: plexMono,
  color: '#f3ead7', accent: '#d8b46a', dim: '#a8946a', shadow: '0 2px 24px rgba(0,0,0,0.9), 0 0 3px rgba(0,0,0,0.8)',
};

// News: Oswald + Inter, white with a red accent (Cyrillic and Vietnamese included).
export const NEWS_THEME: KitTheme = {
  title: oswald, titleWeight: 700, titleCase: 'upper', tracking: 0.02,
  body: inter, bodyStyle: 'normal', mono: plexMono,
  color: '#ffffff', accent: '#e3262f', dim: '#c9ced8', shadow: '0 2px 18px rgba(0,0,0,0.75)',
};

const outExpo = Easing.out(Easing.exp);
const outCubic = Easing.out(Easing.cubic);
const inCubic = Easing.in(Easing.cubic);

// opacity of an element shown in [from, to] with fades of `fi`/`fo` frames
const life = (f: number, from: number, to: number, fi = 12, fo = 12) =>
  Math.min(interpolate(f, [from, from + fi], [0, 1], clamp), interpolate(f, [to - fo, to], [1, 0], clamp));

const caseOf = (t: KitTheme, s: string) => (t.titleCase === 'upper' ? s.toUpperCase() : s);

type Place = {x?: number; y?: number; align?: 'left' | 'center' | 'right'};
const placeStyle = ({x = 0.5, y = 0.5, align = 'center'}: Place): React.CSSProperties => ({
  position: 'absolute',
  left: align === 'left' ? `${x * 100}%` : align === 'center' ? `${x * 100}%` : undefined,
  right: align === 'right' ? `${(1 - x) * 100}%` : undefined,
  top: `${y * 100}%`,
  transform: `translate(${align === 'center' ? '-50%' : '0'}, -50%)`,
  textAlign: align,
  width: 'max-content',
  maxWidth: 1560,
  textWrap: 'balance',
});

// Soft dark pool behind a text block so it reads on bright, busy pictures (sky, snow, sunset). `a` 0..1.
const Scrim: React.FC<Place & {a: number; w?: number; h?: number}> = ({x = 0.5, y = 0.5, align = 'center', a, w = 46, h = 34}) =>
  a <= 0 ? null : (
    <AbsoluteFill style={{background: `radial-gradient(ellipse ${w}% ${h}% at ${align === 'left' ? x * 100 + w * 0.6 : align === 'right' ? x * 100 - w * 0.6 : x * 100}% ${y * 100}%, rgba(0,0,0,${a}) 0%, rgba(0,0,0,${a * 0.55}) 50%, rgba(0,0,0,0) 100%)`}} />
  );

// --- #005 Mask reveal + #002 stagger: each line rises out of an invisible slot, then leaves upward. ---
export const MaskTitle: React.FC<Place & {
  lines: string[]; from: number; to: number; size?: number; theme?: KitTheme; rule?: boolean; sub?: string; scrim?: number;
}> = ({lines, from, to, size = 96, theme = DOC_THEME, rule = true, sub, scrim = 0.4, ...place}) => {
  const f = useCurrentFrame();
  if (f < from - 1 || f > to + 1) return null;
  const IN = 20;
  const STAG = 5;
  const OUT = 14;
  const lastIn = from + (lines.length - 1) * STAG + IN;
  const ruleP = interpolate(f, [lastIn - 8, lastIn + 14], [0, 1], {...clamp, easing: outCubic});
  const ruleOut = interpolate(f, [to - OUT - 6, to - 6], [1, 0], {...clamp, easing: inCubic});
  const subO = Math.min(interpolate(f, [lastIn, lastIn + 16], [0, 1], clamp), interpolate(f, [to - OUT, to - 4], [1, 0], clamp));
  return (
    <AbsoluteFill style={{pointerEvents: 'none'}}>
      <AbsoluteFill style={{opacity: life(f, from - 6, to, 16, 14)}}><Scrim {...place} a={scrim} /></AbsoluteFill>
      <div style={{...placeStyle(place), fontFamily: theme.title, fontWeight: theme.titleWeight, fontSize: size, lineHeight: 1.08,
        color: theme.color, letterSpacing: `${theme.tracking}em`, textShadow: theme.shadow}}>
        {lines.map((ln, i) => {
          const a = from + i * STAG;
          const pin = interpolate(f, [a, a + IN], [0, 1], {...clamp, easing: outExpo});
          const b = to - OUT - (lines.length - 1 - i) * 3;
          const pout = interpolate(f, [b, b + OUT], [0, 1], {...clamp, easing: inCubic});
          return (
            <div key={i} style={{overflow: 'hidden', paddingBottom: '0.06em'}}>
              <div style={{transform: `translateY(${((1 - pin) * 105 - pout * 105).toFixed(2)}%)`}}>{caseOf(theme, ln)}</div>
            </div>
          );
        })}
        {rule && <div style={{height: 2, marginTop: size * 0.22, background: theme.accent, transform: `scaleX(${(ruleP * ruleOut).toFixed(3)})`,
          transformOrigin: place.align === 'left' ? 'left' : place.align === 'right' ? 'right' : 'center', boxShadow: `0 0 12px ${theme.accent}`}} />}
        {sub && <div style={{marginTop: size * 0.22, fontFamily: theme.body, fontStyle: theme.bodyStyle, fontWeight: 500, fontSize: size * 0.34,
          letterSpacing: '0.04em', color: theme.dim, opacity: subO}}>{sub}</div>}
      </div>
    </AbsoluteFill>
  );
};

// --- Chapter card: numeral tracks in, two rules draw outward from the centre, the title rises from a mask. ---
export const ChapterCard: React.FC<{num: string; title: string; sub?: string; from: number; to: number; theme?: KitTheme; dim?: number}> = ({
  num, title, sub, from, to, theme = DOC_THEME, dim = 0.55,
}) => {
  const f = useCurrentFrame();
  if (f < from - 1 || f > to + 1) return null;
  const o = life(f, from, to, 14, 18);
  const sp = interpolate(f, [from, from + 50], [0.9, 0.5], {...clamp, easing: outCubic});
  const ruleP = interpolate(f, [from + 6, from + 34], [0, 1], {...clamp, easing: outExpo});
  const tin = interpolate(f, [from + 12, from + 34], [0, 1], {...clamp, easing: outExpo});
  const drift = interpolate(f, [from, to], [1, 1.035], clamp);
  return (
    <AbsoluteFill style={{pointerEvents: 'none', opacity: o}}>
      <AbsoluteFill style={{background: `radial-gradient(ellipse 70% 60% at 50% 50%, rgba(0,0,0,${dim}) 0%, rgba(0,0,0,${dim * 0.6}) 70%, rgba(0,0,0,${dim * 0.3}) 100%)`}} />
      <AbsoluteFill style={{alignItems: 'center', justifyContent: 'center', transform: `scale(${drift})`}}>
        <div style={{fontFamily: theme.title, fontSize: 30, letterSpacing: `${sp}em`, paddingLeft: `${sp}em`, color: theme.accent, textShadow: theme.shadow}}>
          {caseOf(theme, num)}
        </div>
        <div style={{display: 'flex', alignItems: 'center', gap: 26, margin: '26px 0'}}>
          <div style={{width: 220, height: 1.5, background: theme.accent, transform: `scaleX(${ruleP})`, transformOrigin: 'right'}} />
          <div style={{width: 7, height: 7, transform: `rotate(45deg) scale(${ruleP})`, background: theme.accent}} />
          <div style={{width: 220, height: 1.5, background: theme.accent, transform: `scaleX(${ruleP})`, transformOrigin: 'left'}} />
        </div>
        <div style={{overflow: 'hidden'}}>
          <div style={{transform: `translateY(${(1 - tin) * 105}%)`, fontFamily: theme.title, fontWeight: theme.titleWeight, fontSize: 84,
            letterSpacing: `${theme.tracking}em`, color: theme.color, textShadow: theme.shadow}}>{caseOf(theme, title)}</div>
        </div>
        {sub && <div style={{marginTop: 18, fontFamily: theme.body, fontStyle: theme.bodyStyle, fontSize: 34, color: theme.dim,
          opacity: interpolate(f, [from + 30, from + 48], [0, 1], clamp)}}>{sub}</div>}
      </AbsoluteFill>
    </AbsoluteFill>
  );
};

// --- #004 line draw + mask: lower third for a person or a place. ---
export const LowerThird: React.FC<{name: string; role?: string; from: number; to: number; theme?: KitTheme; side?: 'left' | 'right'}> = ({
  name, role, from, to, theme = DOC_THEME, side = 'left',
}) => {
  const f = useCurrentFrame();
  if (f < from - 1 || f > to + 1) return null;
  const bar = interpolate(f, [from, from + 12], [0, 1], {...clamp, easing: outExpo});
  const line = interpolate(f, [from + 4, from + 26], [0, 1], {...clamp, easing: outExpo});
  const nin = interpolate(f, [from + 8, from + 26], [0, 1], {...clamp, easing: outExpo});
  const rin = interpolate(f, [from + 16, from + 32], [0, 1], {...clamp, easing: outCubic});
  const out = interpolate(f, [to - 14, to], [0, 1], {...clamp, easing: inCubic});
  const left = side === 'left';
  return (
    <AbsoluteFill style={{pointerEvents: 'none', opacity: 1 - out}}>
      <AbsoluteFill style={{opacity: bar, background: `radial-gradient(ellipse 38% 22% at ${left ? 18 : 82}% 76%, rgba(0,0,0,0.55) 0%, rgba(0,0,0,0.3) 55%, rgba(0,0,0,0) 100%)`}} />
      <div style={{position: 'absolute', bottom: LETTERBOX + 150, [left ? 'left' : 'right']: 120, display: 'flex', flexDirection: left ? 'row' : 'row-reverse',
        alignItems: 'stretch', gap: 22, transform: `translateX(${(left ? -1 : 1) * out * 30}px)`}}>
        <div style={{width: 5, background: theme.accent, transform: `scaleY(${bar})`, boxShadow: `0 0 14px ${theme.accent}`}} />
        <div style={{textAlign: left ? 'left' : 'right'}}>
          <div style={{overflow: 'hidden'}}>
            <div style={{transform: `translateY(${(1 - nin) * 105}%)`, fontFamily: theme.title, fontWeight: theme.titleWeight, fontSize: 48,
              letterSpacing: `${theme.tracking * 0.6}em`, color: theme.color, textShadow: theme.shadow}}>{caseOf(theme, name)}</div>
          </div>
          <div style={{height: 1.5, margin: '10px 0 10px', background: `linear-gradient(${left ? 90 : 270}deg, ${theme.accent}, rgba(0,0,0,0))`,
            transform: `scaleX(${line})`, transformOrigin: left ? 'left' : 'right', width: 420, marginLeft: left ? 0 : 'auto'}} />
          {role && <div style={{fontFamily: theme.body, fontStyle: theme.bodyStyle, fontSize: 30, color: theme.dim, opacity: rin,
            transform: `translateY(${(1 - rin) * 8}px)`, textShadow: theme.shadow}}>{role}</div>}
        </div>
      </div>
    </AbsoluteFill>
  );
};

// --- #006 typewriter: a place/date stamp ("ANTARCTICA · 1946") typed out with a blinking caret. ---
export const Typewriter: React.FC<Place & {text: string; from: number; to: number; cps?: number; size?: number; theme?: KitTheme; box?: boolean}> = ({
  text, from, to, cps = 16, size = 30, theme = DOC_THEME, box = false, x = 0.065, y = 0.2, align = 'left',
}) => {
  const f = useCurrentFrame();
  if (f < from - 1 || f > to + 1) return null;
  const n = Math.min(text.length, Math.max(0, Math.floor(((f - from) / FPS) * cps)));
  const typing = n < text.length;
  const caretOn = typing || Math.floor((f - from) / 15) % 2 === 0;
  const o = interpolate(f, [to - 12, to], [1, 0], clamp);
  return (
    <AbsoluteFill style={{pointerEvents: 'none', opacity: o}}>
      <div style={{...placeStyle({x, y, align}), fontFamily: theme.mono, fontWeight: 500, fontSize: size, letterSpacing: '0.12em', color: theme.color,
        textShadow: theme.shadow, whiteSpace: 'pre', background: box ? 'rgba(0,0,0,0.55)' : undefined, padding: box ? '8px 16px' : undefined}}>
        {text.slice(0, n)}
        <span style={{display: 'inline-block', width: '0.6em', height: '1.05em', marginLeft: 4, verticalAlign: '-0.15em',
          background: theme.accent, opacity: caretOn ? 0.9 : 0}} />
      </div>
    </AbsoluteFill>
  );
};

// --- #129 text scramble: letters flicker through random glyphs and lock in from left to right. ---
const GLYPHS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789#%&*+=/<>';
export const Scramble: React.FC<Place & {text: string; from: number; to: number; dur?: number; size?: number; theme?: KitTheme; mono?: boolean; scrim?: number}> = ({
  text, from, to, dur = 26, size = 64, theme = DOC_THEME, mono = false, scrim = 0.4, ...place
}) => {
  const f = useCurrentFrame();
  if (f < from - 1 || f > to + 1) return null;
  const o = life(f, from, to, 4, 12);
  const chars = [...caseOf(theme, text)];
  return (
    <AbsoluteFill style={{pointerEvents: 'none', opacity: o}}>
      <Scrim {...place} a={scrim} h={22} />
      <div style={{...placeStyle(place), fontFamily: mono ? theme.mono : theme.title, fontWeight: mono ? 500 : theme.titleWeight, fontSize: size,
        letterSpacing: `${theme.tracking}em`, color: theme.color, textShadow: theme.shadow, whiteSpace: 'pre'}}>
        {chars.map((c, i) => {
          const lock = from + (dur * i) / Math.max(1, chars.length - 1);
          if (c === ' ' || f >= lock) return <span key={i}>{c}</span>;
          const g = GLYPHS[Math.floor(random(`sc${i}-${Math.floor(f / 2)}`) * GLYPHS.length)];
          return <span key={i} style={{color: theme.accent, opacity: 0.85}}>{f < from + (lock - from) * 0.25 ? ' ' : g}</span>;
        })}
      </div>
    </AbsoluteFill>
  );
};

// --- #007 count-up: a number runs to its value (years, distances, death tolls, money) with a label under it. ---
export const CountUp: React.FC<Place & {
  value: number; from: number; to: number; dur?: number; start?: number; decimals?: number; prefix?: string; suffix?: string;
  label?: string; size?: number; theme?: KitTheme; locale?: string; scrim?: number;
}> = ({value, from, to, dur = 45, start = 0, decimals = 0, prefix = '', suffix = '', label, size = 150, theme = DOC_THEME, locale = 'en-US', scrim = 0.4, ...place}) => {
  const f = useCurrentFrame();
  if (f < from - 1 || f > to + 1) return null;
  const p = interpolate(f, [from, from + dur], [0, 1], {...clamp, easing: Easing.out(Easing.poly(4))});
  const v = start + (value - start) * p;
  const txt = v.toLocaleString(locale, {minimumFractionDigits: decimals, maximumFractionDigits: decimals});
  const o = life(f, from, to, 8, 14);
  const pop = f >= from + dur ? 1 + 0.06 * Math.exp(-(f - from - dur) / 4) : 1;
  const lab = interpolate(f, [from + dur - 10, from + dur + 10], [0, 1], clamp);
  return (
    <AbsoluteFill style={{pointerEvents: 'none', opacity: o}}>
      <Scrim {...place} a={scrim} w={34} />
      <div style={{...placeStyle(place)}}>
        <div style={{fontFamily: theme.title, fontWeight: theme.titleWeight, fontSize: size, lineHeight: 1, color: theme.color, textShadow: theme.shadow,
          fontVariantNumeric: 'tabular-nums', transform: `scale(${pop})`}}>
          <span style={{color: theme.accent}}>{prefix}</span>{txt}<span style={{color: theme.accent, fontSize: size * 0.55}}>{suffix}</span>
        </div>
        {label && <div style={{marginTop: 16, fontFamily: theme.body, fontStyle: theme.bodyStyle, fontSize: size * 0.24, color: theme.dim, opacity: lab,
          letterSpacing: '0.05em', textShadow: theme.shadow}}>{label}</div>}
      </div>
    </AbsoluteFill>
  );
};

// --- #008 kinetic typography + #010 overshoot: words punch in one by one; *word* = accent colour. ---
export const PunchWords: React.FC<Place & {text: string; from: number; to: number; per?: number; size?: number; theme?: KitTheme; scrim?: number}> = ({
  text, from, to, per = 7, size = 92, theme = DOC_THEME, scrim = 0.5, ...place
}) => {
  const f = useCurrentFrame();
  if (f < from - 1 || f > to + 1) return null;
  const words = text.split(' ');
  const o = interpolate(f, [to - 12, to], [1, 0], clamp);
  return (
    <AbsoluteFill style={{pointerEvents: 'none', opacity: o}}>
      <AbsoluteFill style={{opacity: interpolate(f, [from - 4, from + 10], [0, 1], clamp)}}><Scrim {...place} a={scrim} w={55} /></AbsoluteFill>
      <div style={{...placeStyle(place), width: 1500, fontFamily: theme.title, fontWeight: theme.titleWeight, fontSize: size, lineHeight: 1.12,
        letterSpacing: `${theme.tracking * 0.5}em`, textShadow: theme.shadow, textWrap: 'balance'}}>
        {words.map((w, i) => {
          const hot = /^\*.+\*$/.test(w);
          const s = spring({frame: f - from - i * per, fps: FPS, config: {damping: 11, stiffness: 170, mass: 0.7}});
          return (
            <span key={i} style={{display: 'inline-block', marginRight: '0.28em', color: hot ? theme.accent : theme.color, opacity: Math.min(1, s * 1.6),
              transform: `scale(${(0.35 + 0.65 * s).toFixed(3)}) translateY(${((1 - s) * 30).toFixed(1)}px)`}}>
              {caseOf(theme, hot ? w.slice(1, -1) : w)}
            </span>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};

// --- Pull quote: big quotation marks, words sharpen in one by one, the citation draws a line and fades in. ---
export const PullQuote: React.FC<{text: string; cite?: string; from: number; to: number; per?: number; size?: number; theme?: KitTheme; dim?: number}> = ({
  text, cite, from, to, per = 3, size = 62, theme = DOC_THEME, dim = 0.5,
}) => {
  const f = useCurrentFrame();
  if (f < from - 1 || f > to + 1) return null;
  const words = text.split(' ');
  const o = life(f, from, to, 14, 16);
  const done = from + words.length * per + 12;
  const markS = interpolate(f, [from, from + 22], [0.6, 1], {...clamp, easing: outExpo});
  const ruleP = interpolate(f, [done, done + 18], [0, 1], {...clamp, easing: outExpo});
  return (
    <AbsoluteFill style={{pointerEvents: 'none', opacity: o}}>
      <AbsoluteFill style={{background: `rgba(0,0,0,${dim})`}} />
      <AbsoluteFill style={{alignItems: 'center', justifyContent: 'center'}}>
        <div style={{fontFamily: theme.title, fontSize: 200, lineHeight: 0.6, color: theme.accent, opacity: 0.85, transform: `scale(${markS})`, height: 90}}>“</div>
        <div style={{maxWidth: 1350, textAlign: 'center', textWrap: 'balance', fontFamily: theme.body, fontStyle: theme.bodyStyle, fontWeight: 500,
          fontSize: size, lineHeight: 1.25, color: theme.color, textShadow: theme.shadow}}>
          {words.map((w, i) => {
            const p = interpolate(f, [from + 8 + i * per, from + 8 + i * per + 14], [0, 1], {...clamp, easing: outCubic});
            return <span key={i} style={{display: 'inline-block', marginRight: '0.25em', opacity: p, filter: `blur(${((1 - p) * 8).toFixed(1)}px)`,
              transform: `translateY(${(1 - p) * 10}px)`}}>{w}</span>;
          })}
        </div>
        {cite && (
          <div style={{display: 'flex', alignItems: 'center', gap: 18, marginTop: 34}}>
            <div style={{width: 90, height: 1.5, background: theme.accent, transform: `scaleX(${ruleP})`, transformOrigin: 'right'}} />
            <div style={{fontFamily: theme.title, fontSize: 22, letterSpacing: '0.38em', color: theme.accent, opacity: ruleP}}>{caseOf(theme, cite)}</div>
          </div>
        )}
      </AbsoluteFill>
    </AbsoluteFill>
  );
};

// --- #080 highlighter: a marker sweeps behind one phrase of a line (news: the key claim, the number). ---
export const Highlight: React.FC<Place & {text: string; mark: string; from: number; to: number; size?: number; theme?: KitTheme; color?: string; scrim?: number}> = ({
  text, mark, from, to, size = 58, theme = NEWS_THEME, color, scrim = 0.5, ...place
}) => {
  const f = useCurrentFrame();
  if (f < from - 1 || f > to + 1) return null;
  const o = life(f, from, to, 10, 12);
  const i = text.indexOf(mark);
  const sweep = interpolate(f, [from + 12, from + 32], [0, 1], {...clamp, easing: Easing.inOut(Easing.cubic)});
  const before = i < 0 ? text : text.slice(0, i);
  const after = i < 0 ? '' : text.slice(i + mark.length);
  return (
    <AbsoluteFill style={{pointerEvents: 'none', opacity: o}}>
      <Scrim {...place} a={scrim} h={24} />
      <div style={{...placeStyle(place), maxWidth: 1500, fontFamily: theme.body, fontWeight: 800, fontSize: size, lineHeight: 1.3, color: theme.color,
        textShadow: theme.shadow}}>
        {before}
        {i >= 0 && (
          <span style={{position: 'relative', whiteSpace: 'nowrap'}}>
            <span style={{position: 'absolute', left: '-0.12em', right: '-0.12em', top: '0.12em', bottom: '0.02em', background: color ?? theme.accent,
              transform: `scaleX(${sweep}) skewX(-8deg)`, transformOrigin: 'left', zIndex: 0, borderRadius: 3}} />
            <span style={{position: 'relative', zIndex: 1}}>{mark}</span>
          </span>
        )}
        {after}
      </div>
    </AbsoluteFill>
  );
};
