import {registerRoot} from 'remotion';
import {ShowcaseRoot} from './Showcase';

// Motion kit showcase: `npx remotion render showcase/index.ts KitShowcase out/kit_showcase.mp4 --gl=angle` (inside engine/).
// Uses the demo layers in engine/public/kit-demo (copied from the Pyramids film). Never copied into film projects.
registerRoot(ShowcaseRoot);
