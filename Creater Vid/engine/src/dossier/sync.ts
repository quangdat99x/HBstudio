// Narration sync for dossier shots: any `at` in a shot config may be a frame number (local to the scene) or a
// string that points into the narration, so a highlight sweeps, a card lands or a stamp hits exactly when the
// narrator says the word:
//   "l12"                -> first word of narration line l12
//   "l12:non-faculty"    -> first word of the phrase "non-faculty" in line l12 (case and punctuation ignored)
//   "l12:non-faculty+6"  -> the same, 6 frames later (negative offsets allowed: "l12:Drexel-4")
// Frames are local to the scene that is being rendered (the line may belong to the scene before: a J-cut).
import voice from '../voice.json';
import {SCENES} from '../timeline';

type Line = {id: string; scene: string; caption: string | null; start: number; end: number; words: number[]};
const LINES = (voice as {lines: Line[]}).lines;
const SCENE_MAP = SCENES as Record<string, {from: number; duration: number}>;

export type At = number | string;

const tokens = (s: string) =>
  s.toLowerCase().replace(/[“”"‘’'.,;:!?()[\]…—–*]/g, ' ').replace(/-/g, ' ').split(/\s+/).filter(Boolean);

// Absolute frame span of a phrase (or a whole line) in the narration.
const spanAbs = (ref: string): {from: number; to: number} => {
  const [id, phrase] = ref.split(/:(.*)/s);
  const line = LINES.find((l) => l.id === id);
  if (!line) throw new Error(`dossier sync: no narration line "${id}" in voice.json`);
  if (!phrase) return {from: line.words[0] ?? line.start, to: line.end};
  // caption words are counted the same way voice-build.py counts them (whitespace split), so word k of the
  // caption is words[k]; a caption word that tokenises to two pieces ("non-faculty") still maps to one index
  const capWords = (line.caption ?? '').split(/\s+/).filter(Boolean);
  const flat: {tok: string; idx: number}[] = [];
  capWords.forEach((w, idx) => tokens(w).forEach((tok) => flat.push({tok, idx})));
  const want = tokens(phrase);
  for (let i = 0; i + want.length <= flat.length; i++) {
    if (want.every((w, k) => flat[i + k].tok === w)) {
      const a = flat[i].idx;
      const b = flat[i + want.length - 1].idx;
      const to = line.words[b + 1] ?? line.end;
      return {from: line.words[a], to};
    }
  }
  throw new Error(`dossier sync: phrase "${phrase}" not found in narration line "${id}": ${line.caption}`);
};

const parse = (at: string): {ref: string; off: number} => {
  const m = at.match(/^(.*?)([+-]\d+)$/s);
  return m && !/:$/.test(m[1]) ? {ref: m[1], off: Number(m[2])} : {ref: at, off: 0};
};

// Frame (local to `scene`) of an `at`.
export const atFrame = (at: At | undefined, scene: string | undefined, fallback = 0): number => {
  if (at === undefined || at === null) return fallback;
  if (typeof at === 'number') return at;
  const {ref, off} = parse(at);
  const s = spanAbs(ref);
  const base = scene && SCENE_MAP[scene] ? SCENE_MAP[scene].from : sceneOf(ref);
  return Math.round(s.from - base + off);
};

// How long the phrase is spoken, in frames (for a highlight that sweeps while the words are said).
export const atLength = (at: At | undefined): number | undefined => {
  if (typeof at !== 'string') return undefined;
  const s = spanAbs(parse(at).ref);
  return Math.max(8, Math.round(s.to - s.from));
};

const sceneOf = (ref: string) => {
  const line = LINES.find((l) => l.id === ref.split(':')[0]);
  return line && SCENE_MAP[line.scene] ? SCENE_MAP[line.scene].from : 0;
};

// Keys of a shot config whose values are `At`s; resolveShot turns them into frames before the shot renders.
const AT_KEYS = new Set(['at', 'labelAt', 'reveal', 'until']);

export function resolveShot<T>(cfg: T, scene?: string): T {
  const walk = (v: unknown, key?: string): unknown => {
    if (Array.isArray(v)) return v.map((x) => walk(x));
    if (v && typeof v === 'object') {
      const out: Record<string, unknown> = {};
      for (const [k, x] of Object.entries(v)) {
        out[k] = walk(x, k);
        // a highlight driven by a spoken phrase sweeps for as long as the phrase is said
        if (k === 'at' && typeof x === 'string' && (v as Record<string, unknown>).dur === undefined) out.spoken = atLength(x);
      }
      return out;
    }
    if (key && AT_KEYS.has(key) && typeof v === 'string') return atFrame(v, scene);
    return v;
  };
  return walk(cfg) as T;
}
