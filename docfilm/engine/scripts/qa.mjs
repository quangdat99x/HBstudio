// Final checks on a rendered film:
//   node scripts/qa.mjs out/film_v1.mp4 [--frames 12] [--sheet out/review/contact.jpg]
// Prints frame count, duration, audio presence, black stretches, integrated loudness and true
// peak, and writes a contact sheet of evenly spaced frames taken from the MP4 itself.
// Exit code 1 when something is off (the report says what).
import {execFileSync, spawnSync} from 'node:child_process';
import {mkdirSync} from 'node:fs';
import path from 'node:path';

const args = process.argv.slice(2);
const file = args[0];
let n = 12;
let sheet = null;
for (let i = 1; i < args.length; i++) {
  if (args[i] === '--frames') n = Number(args[++i]);
  else if (args[i] === '--sheet') sheet = args[++i];
}
if (!file) {
  console.error('usage: qa.mjs <film.mp4> [--frames 12] [--sheet out/review/contact.jpg]');
  process.exit(1);
}
const FFMPEG = process.env.FFMPEG || 'ffmpeg';
const FFPROBE = process.env.FFPROBE || 'ffprobe';
const problems = [];

const probe = JSON.parse(execFileSync(FFPROBE, ['-v', 'error', '-count_frames', '-show_entries', 'stream=codec_type,nb_read_frames,width,height', '-show_entries', 'format=duration', '-of', 'json', file]).toString());
const video = probe.streams.find((s) => s.codec_type === 'video');
const audio = probe.streams.find((s) => s.codec_type === 'audio');
const duration = Number(probe.format.duration);
console.log(`video ${video?.width}x${video?.height}, ${video?.nb_read_frames} frames, ${duration.toFixed(2)} s, audio ${audio ? 'yes' : 'NO'}`);
if (!audio) problems.push('no audio track');

const black = spawnSync(FFMPEG, ['-hide_banner', '-nostats', '-i', file, '-vf', 'blackdetect=d=0.1:pix_th=0.06', '-an', '-f', 'null', '-'], {encoding: 'utf8'}).stderr;
const stretches = [...black.matchAll(/black_start:([\d.]+) black_end:([\d.]+)/g)].map((m) => [Number(m[1]), Number(m[2])]);
const unexpected = stretches.filter(([a, b]) => a > 0.5 && b < duration - 0.8);
console.log(`black stretches: ${stretches.map(([a, b]) => `${a.toFixed(2)}-${b.toFixed(2)}`).join(', ') || 'none'}`);
if (unexpected.length) problems.push(`black frames mid-film: ${unexpected.map(([a, b]) => `${a.toFixed(2)}-${b.toFixed(2)}s`).join(', ')} (missing texture or scene gap?)`);

if (audio) {
  const loud = spawnSync(FFMPEG, ['-hide_banner', '-nostats', '-i', file, '-af', 'ebur128=peak=true', '-f', 'null', '-'], {encoding: 'utf8'}).stderr;
  const I = Number((loud.match(/I:\s+(-?[\d.]+) LUFS/g) || []).pop()?.match(/-?[\d.]+/)[0]);
  const P = Number((loud.match(/Peak:\s+(-?[\d.]+) dBFS/g) || []).pop()?.match(/-?[\d.]+/)[0]);
  console.log(`loudness ${I} LUFS, true peak ${P} dBFS`);
  if (!(I >= -17 && I <= -13)) problems.push(`loudness ${I} LUFS outside -17..-13`);
  if (P > -1) problems.push(`true peak ${P} dBFS above -1`);
}

const out = sheet || path.join(path.dirname(file), 'review', path.basename(file, '.mp4') + '_contact.jpg');
mkdirSync(path.dirname(out), {recursive: true});
const total = Number(video?.nb_read_frames || 0);
const picks = Array.from({length: n}, (_, i) => Math.round(((i + 0.5) * total) / n));
const sel = picks.map((k) => `eq(n\\,${k})`).join('+');
const cols = n >= 9 ? 3 : 2;
execFileSync(FFMPEG, ['-v', 'error', '-y', '-i', file, '-vf', `select='${sel}',scale=640:-1,tile=${cols}x${Math.ceil(n / cols)}`, '-frames:v', '1', '-fps_mode', 'passthrough', out]);
console.log(`contact sheet ${out} (frames ${picks.join(', ')})`);

if (problems.length) {
  console.log('PROBLEMS:\n- ' + problems.join('\n- '));
  process.exit(1);
}
console.log('QA OK');
