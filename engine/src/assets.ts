import type {Rig} from './engine/rig';

// Images of this film (public/img/...). Aspect ratios are fixed here so layout never waits on
// decoding. Characters: cut-outs (plain grey background removed). Fog/fire/light: raw on black,
// drawn with blend="add". Plates: 21:9 at 2k.
export const IMG = {
  // sky: {src: 'img/sky.png', aspect: 2528 / 1088},
} satisfies Record<string, {src: string; aspect: number}>;

// Rig landmarks per character, measured with scripts/measure.mjs (bbox for feet, glow for hands
// in fire/light, grid for the rest). Image coordinates, x from left, y from top.
export const RIGS = {
  // hero: {pivotX: 0.065, pivotY: 0.3, body: 0.1, feet: 0.97, hemTop: 0.6, hands: [[0.34, 0.17], [0.66, 0.17]]},
} satisfies Record<string, Rig>;

export const TEX = Object.fromEntries(Object.entries(IMG).map(([k, v]) => [k, (v as {src: string}).src])) as Record<keyof typeof IMG, string>;
