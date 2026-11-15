// Narration timing (written by scripts/voice-build.py): captions follow the voice instead of fixed frames.
import voice from './voice.json';
import {SCENES} from './timeline';

type Line = {id: string; scene: keyof typeof SCENES; caption: string | null; cite: string | null; start: number; end: number; words: number[]};
const LINES = voice.lines as Line[];

// Caption props for a narrated line, in frames local to its scene: in just before the first word, out after the
// line, and gone before the next caption starts (even across a crossfade).
export function narration(id: string) {
  const i = LINES.findIndex((l) => l.id === id);
  if (i < 0) throw new Error(`no narration line "${id}" in voice.json`);
  const l = LINES[i];
  const s = SCENES[l.scene];
  const next = LINES.slice(i + 1).find((n) => n.caption);
  const last = l.words[l.words.length - 1];
  let to = Math.max(l.end + 18, last + 30);
  if (next) to = Math.min(to, next.words[0] - 10);
  return {
    text: l.caption ?? '',
    cite: l.cite ?? undefined,
    from: Math.max(0, Math.round(l.words[0] - 6 - s.from)),
    to: Math.min(s.duration - 1, Math.round(to - s.from)),
    words: l.words.map((w) => w - s.from),
  };
}
