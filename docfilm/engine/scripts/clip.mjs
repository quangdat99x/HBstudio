// Cut one JRE quote out of a highlight clip, frame-accurately, re-encoded (never stream-copy:
// that snaps to keyframes and shifts the words against the subtitles).
//   node scripts/clip.mjs <source.mp4> <startSec> <endSec> public/clips/q01.mp4
// startSec/endSec are seconds INSIDE the source file. For a zoomed highlight clip that starts at
// the segment's start_sec in the episode: inside = episode_time - segment.start_sec.
import {execFileSync} from 'node:child_process';
import {mkdirSync} from 'node:fs';
import path from 'node:path';

const [src, a, b, out] = process.argv.slice(2);
if (!src || a === undefined || b === undefined || !out) {
  console.error('usage: clip.mjs <source.mp4> <startSec> <endSec> <out.mp4>');
  process.exit(1);
}
const start = Number(a);
const end = Number(b);
if (!(end > start)) throw new Error('end must be after start');
mkdirSync(path.dirname(out), {recursive: true});
const FFMPEG = process.env.FFMPEG || 'ffmpeg';
execFileSync(FFMPEG, [
  '-v', 'error', '-y', '-ss', start.toFixed(3), '-i', src, '-t', (end - start).toFixed(3),
  '-vf', 'scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,fps=30',
  '-c:v', 'libx264', '-crf', '18', '-preset', 'medium', '-pix_fmt', 'yuv420p',
  '-c:a', 'aac', '-b:a', '192k', '-ar', '48000', out,
], {stdio: 'inherit'});
console.log(`${out}  ${(end - start).toFixed(2)} s  (= ${Math.round((end - start) * 30)} frames at 30 fps)`);
