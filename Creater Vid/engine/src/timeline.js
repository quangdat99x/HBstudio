// Single source of truth for timing, shared by the video (Remotion scenes) and the soundtrack
// (scripts/make-audio.mjs), so every sound lands on the frame its picture does.
export const FPS = 30;
export const WIDTH = 1920;
export const HEIGHT = 1080;

// Scenes overlap by ~15 frames: the incoming scene fades in on top of the outgoing one.
export const SCENES = {
  title: {from: 0, duration: 120},
};
export const DURATION = 120;

// Frames local to the scene each cue belongs to (booms, hits, reveals...).
export const CUES = {
  titleHit: 6,
};

// Windows (absolute frames) where a JRE clip is speaking: the score ducks under them.
export const QUOTES = [];

// true once public/soundtrack.wav exists (scripts/make-audio.mjs)
export const AUDIO = false;
