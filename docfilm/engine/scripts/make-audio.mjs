// Soundtrack of this film: score + effects from scripts/audio-lib.mjs, timed from src/timeline.js.
// Run: node scripts/make-audio.mjs  -> public/soundtrack.wav (mastered to -16 LUFS), then set AUDIO = true
// in src/timeline.js. JRE quote clips keep their own audio (Remotion mixes them); the score ducks
// under every window listed in QUOTES.
import {DURATION, FPS, QUOTES, SCENES} from '../src/timeline.js';
import {env, Mixer} from './audio-lib.mjs';

const seconds = DURATION / FPS;
const at = (scene, frame) => (SCENES[scene].from + frame) / FPS;
const m = new Mixer({seconds});

// Score: a low drone that breathes with the story (edit the automation to follow the acts).
const drone = (t) => env(t, [[0, 0], [2.5, 0.7], [seconds - 1.5, 0.7], [seconds, 0]]);
m.tone(55, 0.16, drone, {pan: -0.1});
m.tone(82.41, 0.09, drone, {pan: 0.15});
m.tone(110, 0.07, drone, {pan: -0.2});
m.tone(130.81, 0.045, drone, {pan: 0.2});
m.wind((t) => env(t, [[0, 0], [2, 0.4], [seconds - 1, 0.4], [seconds, 0]]));

// Effects: one line per cue, e.g. m.boom(at('oath', CUES.oathBoom), 0.95, 1.4);
m.thump(at('title', 6), 0.45, 0, 62, 30, 1.8, 0.8);

m.duck(QUOTES.map((q) => [q.from / FPS, (q.from + q.duration) / FPS]), -12);
m.write('out/soundtrack_raw.wav', 'public/soundtrack.wav');
