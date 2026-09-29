# Documentary film engine (Remotion + three.js)

Technical manual for building a film. The **rulebook** (RULEBOOK.md in the documentary root) says
*what* a film must be; this file says *how* to build it with the engine. Reference film that uses every
piece: `D:\VideoLab\watchers-v2` (The Watchers v2.1): read its `src/scenes/*.tsx` before writing scenes.

## Layout of a film folder (`<project>/film/`)

```
package.json, tsconfig.json, remotion.config.ts   (copied from the engine, do not change versions)
node_modules/        junction to the shared engine install: never run npm install here, NEVER delete it or
                     anything inside it (a recursive delete follows the junction and wipes the engine for every film)
public/img/          images from Higgsfield (cut-outs .png, plates .png)
public/clips/        JRE quote clips cut with scripts/clip.mjs
public/soundtrack.wav
src/timeline.js      FPS, SCENES {from, duration}, DURATION, CUES, QUOTES, AUDIO
src/assets.ts        IMG (src + aspect) and RIGS (measured landmarks)
src/Film.tsx         SCENE_LIST in order, overlays, soundtrack
src/scenes/*.tsx     one file per scene
src/engine/*         the engine (Stage, Plate, Fx, rig, actor, textures, featherSim)
src/components/*     Text (Caption, Label, fonts), Overlays (Grain, Vignette, Letterbox, Flash), QuoteClip
src/lib/*            anim (ramp, pulse, shake, mix, clamp), noise (fbm, ridge helpers)
scripts/*            stills, qa, measure, clip, make-audio + audio-lib, feather-test/search
out/                 renders, stills, review sheets
```

## Commands (run inside `film/`, one command per call)

| What | Command |
|---|---|
| Typecheck | `npx tsc --noEmit -p .` |
| Proof frames + contact sheet | `node scripts/stills.mjs 20 100 160 420` (add `--crop 900x500+510+130` for zoomed checks) |
| Full render | `npx remotion render Film ../out/<slug>_v1.mp4 --gl=angle` |
| QA of a render | `node scripts/qa.mjs ../out/<slug>_v1.mp4` (frames, black gaps, loudness, contact sheet) |
| Soundtrack | `node scripts/make-audio.mjs` then set `AUDIO = true` in `src/timeline.js` |
| Landmarks | `node scripts/measure.mjs bbox|ridge|glow|grid public/img/x.png ...` |
| JRE quote clip | `node scripts/clip.mjs <zoomed_clip.mp4> <startInFile> <endInFile> public/clips/q01.mp4` |
| Feather physics | `node scripts/feather-test.mjs` (ASCII path), `node scripts/feather-search.mjs` (tune) |

Renders take ~1 min per 30 s on this PC (i9-10900 + RTX 4060, concurrency 6). `--gl=angle` is required.

## Stage and camera

```tsx
const shot: Shot = {pos: [x, y, z], target: [x, y, z], fov: 35, focus: <distance in focus>, aperture: 1.3};
<Stage shot={shot}> ...planes, fx... </Stage>
```
- World units, camera looks down -z. Visible frame height at distance d: `frameH(d)` (35 mm lens: 0.63 d).
- Sky/backdrop plates: z = -130..-170, `height = frameH(d) * 1.35..1.4`, `dof={false} blur={0.3..0.6}`.
- Depth of field is automatic from `focus` and `aperture` (blur = aperture * |1 - focus/distance|).
- Move the camera for real (dolly / truck / orbit); zoom alone gives no parallax.

## Plates (`<Plate>`)

`tex, aspect, pos, height, anchor ('center'|'feet'|'bottom'), rot/rotX/rotY, opacity, tint, exposure,
blend ('normal'|'add'), fog, fogColor, blur, dof, reveal + revealMode (1 angular, 2 left->right, 3 radial),
clipBelow (world y under which the plate is cut away: sinking into a pit), order`.
- Normal plates are painted back to front by depth and write depth for their solid pixels (invisible second
  pass), so effects drawn later are hidden behind whatever stands in front of them.
- `blend="add"` for images on black (fog, fire, light, feather): black adds nothing, no background removal.

## Characters (`makeActor` + `<Actor>`)

```tsx
const hero = makeActor({img: IMG.hero, rig: RIGS.hero, t, pos: [x, feetY, z], height: 9, amp: 0.05, hz: 0.35, ph: 1.2, rotY});
<Actor a={hero} tex={tex.hero} exposure={1.1} />
<Glow pos={hero.hands(0.3)[0]} w={3} color="#ffae50" intensity={0.8} />
<Beam points={[hero.hands(0.25)[0], mid, end]} progress={q} radius={0.045} color="#ffb45a" opacity={0.9} order={hero.order + 0.25} />
```
- The vertex shader bends the wings (a wave from the shoulders: tips lag and bend more, quick downstroke,
  slow recovery), sways the hem and breathes. `amp` 0.03-0.06 idle, up to 0.12 while flying.
- `hero.point(ix, iy, lift)` / `hero.hands(lift)` give world positions after the same warp and rotation:
  attach everything through them, never through raw image coordinates.
- Attachments that start on the character itself (threads from its hands, a sword it holds) render at
  `order = hero.order + 0.25`, otherwise the character's own wings hide them.
- Orbit shots: billboard characters toward the camera, `rotY = Math.atan2(cam.x - x, cam.z - z)`.
- Pose changes are different images (arms raised, bound...), made with Nano Banana Pro from the master image.

## Effects (`engine/Fx.tsx`)

| Component | Use |
|---|---|
| `Particles count get(i)->{x,y,z,size,alpha,color}` | embers, dust, snow, sparks; `motes(seed, t, box, opts)` makes a looping field |
| `Glow pos w h color intensity falloff` | soft light (halo, fire, landing flash); edges fade to zero |
| `Shade pos w h intensity` | dark soft ellipse (pit, shadow), normal blend |
| `Streak tail head width color intensity taper` | light trail; chain 3-4 segments with taper for a smooth comet tail |
| `Beam points progress radius color opacity order` | glowing 3D tube along a curve, drawn up to `progress` |
| `Chain from to bow links shown color glowColor opacity` | real 3D torus links (solid gold core + additive halo) |
| `CanvasPlate pos size draw(ctx, px)` | 2D canvas redrawn every frame (sigils, diagrams, maps) |

Additive light vanishes on white: anything that must read on a bright area needs a solid core.

## Text and quotes

- `<Caption text from to cite>`: word-by-word reveal, bottom band above the letterbox, balanced lines.
- `<Label text sub from to>`: small spaced title at the top (book / chapter).
- `<QuoteClip src duration speaker source lines>`: a JRE clip with lower third and verbatim subtitles.
  Lines are frames relative to the clip; take the words from the transcript, never re-word them.
- Fonts: Cinzel (titles, citations), Cormorant Garamond italic (narration, subtitles).

## Motion helpers

`ramp(f, a, b, from, to, easing)`, `pulse(f, at, len)`, `shake(f, hits, amp, decay)`, `spring()` (remotion),
`simulateFeather({frames})` for anything light that falls (feathers, ash, leaves: glide, stall, reverse).
Never animate organic things with linear interpolation.

## Pitfalls already paid for

1. Landmarks eyeballed on a 10% grid were off by several units: measure (`measure.mjs`).
2. Effects drawn on top regardless of depth broke the space: they must depth-test (the engine does).
3. A character's own wings hid its attachments: use `order + 0.25`.
4. Glows with a hard window showed oval edges: the engine's glow fades to zero; keep falloff >= 2.5.
5. Soul Cinema with a reference image copies it too closely: use Nano Banana Pro to edit the master.
6. Background removal leaves dark fringes on soft white objects on black: use the raw image with blend="add".
7. A scene's first frame can render before its textures: `useTextures` delays the frame until they load; keep it.
