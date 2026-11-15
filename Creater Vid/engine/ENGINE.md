# Documentary film engine (Remotion + three.js)

Technical manual for building a film. The **rulebook** (RULEBOOK.md in the documentary root) says
*what* a film must be; this file says *how* to build it with the engine. Reference film that uses every
piece: `K:\VideoLab\watchers-v2` (The Watchers v2.2, narrated): read its `src/scenes/*.tsx` before writing scenes.
`src/scenes/Azazel.tsx` there shows the effects kit (filmed fire and smoke, sparks, fire light, bloom, heat haze).

## Layout of a film folder (`<project>/film/`)

```
package.json, tsconfig.json, remotion.config.ts   (copied from the engine, do not change versions)
node_modules/        junction to the shared engine install: never run npm install here, NEVER delete it or
                     anything inside it (a recursive delete follows the junction and wipes the engine for every film)
assets/raw/          images as generated (grey backdrop), kept for re-cutting
assets/fx/           filmed elements as downloaded (fire, smoke...), only after the user approved them
audio/voice/         narration takes (ElevenLabs .mp3) + plan.json (which take, where each line goes)
public/img/          images the film uses (cut-outs .png from scripts/cutout.py, plates .png)
public/fx/           filmed elements prepared by scripts/fx-prep.mjs
public/clips/        JRE quote clips cut with scripts/clip.mjs
public/soundtrack.wav  score + effects + narration, mastered (-15 LUFS)
src/timeline.js      FPS, SCENES {from, duration}, DURATION, CUES, QUOTES, AUDIO
src/voice.json       narration timing written by scripts/voice-build.py (empty until there is a voice)
src/voice.ts         narration(id): caption props timed to the spoken words
src/fx/*Flicker.json brightness of a fire clip per frame (drives the light it casts)
src/assets.ts        IMG (src + aspect) and RIGS (measured landmarks)
src/Film.tsx         SCENE_LIST in order, overlays, soundtrack
src/scenes/*.tsx     one file per scene
src/engine/*         the engine (Stage, Plate, Fx, VideoFx, Sparks, PostFx, rig, actor, textures, featherSim)
src/components/*     Text (Caption, Label, fonts), Overlays (Grain, Vignette, Letterbox, Flash), QuoteClip
src/lib/*            anim (ramp, pulse, shake, mix, clamp), noise (fbm, ridge helpers)
src/kit/*            Motion kit: transitions, looks / camera feel, animated text (section "Motion kit")
scripts/*            stills, qa, measure, clip, make-audio + audio-lib, voice-build.py, cutout.py, fx-prep, feather-test/search
out/                 renders, stills, review sheets
```

## Commands (run inside `film/`, one command per call)

| What | Command |
|---|---|
| Typecheck | `npx tsc --noEmit -p .` |
| Proof frames + contact sheet | `node scripts/stills.mjs 20 100 160 420` (`--crop 900x500+510+130` zoomed checks, `--public <dir>` A/B with other images, `--logs` browser console) |
| Cut-outs (free, on this machine) | `"$BGREMOVE_PY" scripts/cutout.py assets/raw/a.png assets/raw/b.png --out public/img` (fire/smoke: `--mode matting`), then look at `out/stills/cutouts.jpg` |
| Filmed element | `node scripts/fx-prep.mjs assets/fx/fire.mp4 fire --start 1 --dur 8.4 --crop 1040:1080:150:0 --flicker` (smoke: `--desat`) |
| Narration | `"$WHISPER_PY" scripts/voice-build.py` (after the takes and `audio/voice/plan.json` exist) |
| Page capture + phrase boxes (dossier) | `node scripts/pagecap.mjs <url> <id> --mark "phrase" --mark "..."` -> `public/docs/<id>.png` + `.json` |
| Full render | `npx remotion render Film ../out/<slug>_v1.mp4 --gl=angle` |
| QA of a render | `node scripts/qa.mjs ../out/<slug>_v1.mp4` (frames, black gaps, loudness, contact sheet) |
| Soundtrack | `node scripts/make-audio.mjs` (mixes in `src/voice.json` if it has lines) then set `AUDIO = true` in `src/timeline.js` |
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
clipBelow (world y under which the plate is cut away: sinking into a pit), order,
light ({pos, color, intensity, radius}: a point light such as a fire; it multiplies the surface colour, so dark
iron stays dark and wood and skin warm up), wrap ({color, amount}: the scene's light bleeds over the cut-out's
edges so it sits in the air it is in; 0.1-0.2)`.
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

### Fire, smoke, sparks, light (the Azazel forge in watchers-v2 is the worked example)

Fire and smoke must MOVE: never use flames painted into a generated still (they stand still, and cut out of a
grey backdrop they trap grey inside the tongues). If an image comes with painted fire, remove it (colour mask +
OpenCV inpaint, then re-cut) and put a filmed element in its place.

| Component | Use |
|---|---|
| `VideoFx src pos width height gain tint tintTop taper fade mouth` | filmed element shot on black (`public/fx/*.mp4`) on a plane, additive, frame-accurate. `pos` is the bottom centre. `taper` narrows the crop into a flame body; `mouth {x, y, a, b, lipTop}` hides everything below the front lip of a bowl so fire rises out of it |
| `SparkStreaks sparks shutter max` | motion-blurred streaks coloured by temperature (white-yellow, orange, dull red), brighter than white when hot so the bloom catches them |
| `blowSparks(seed, origin, age, count, {speed, gravity, floor})` | sparks of a hammer blow / impact: ballistic, drag, bounce on the floor, cooling. One call per cue |
| `risingEmbers(seed, mouth, t, rate, {rise, life})` | embers leaving a fire: buoyant, swaying, fading |
| `<Stage post={{bloom, haze}}>` | camera effects on the finished frame: `bloom {strength 0.5, radius 0.45, threshold 0.8}` (light spills around fire, sparks, hot metal); `haze {pos, width, height, amount 0.006, time: t}` (the air above a fire ripples) |
| Plate `light` | the fire lights what is near it; drive `intensity` with the clip's own brightness: `import FLICKER from '../fx/fireFlicker.json'`, `FLICKER[frame]` (made by `fx-prep --flicker`) |

- The clip plays from the start of the scene's Sequence: trim it with `fx-prep --start/--dur` to the part you
  want and at least the scene's length (8.4 s clip for a 7.8 s scene).
- Place the element where it is seen: check the visible frame bottom (letterbox 100 px, foreground rocks). In the
  first forge test the brazier sat under the frame edge and its fire was invisible.

## Layered scenes (pipeline `stacked`, rulebook 4.10)

`src/staged/LayerScene.tsx`: a scene whose 2-4 layers were painted separately by the image model
(`"$CREATER_PYTHON" "$LAYERKIT_PY" 3_scenes/scenes.json` writes `public/layers/<scene>/<layer>.png` + `layers.json`).

```tsx
import L05 from '../../public/layers/sc05/layers.json';
<LayerScene cfg={L05 as LayerCfg} duration={duration} move="push-truck-right" strength={1} frame={[0.5, 0.38]} />
```
- Cards at their depth `z` (metres), sized from the camera path so no edge ever shows; at the start pose they line up
  into the painted composition. `frame` = picture point at the centre of the shot (heads near the top -> y < 0.5).
- Moves: push-in, pull-out, truck-left/right, orbit-left/right, crane-down/up, push-truck-left/right, drift.
- Approved extras only, through `children={(t) => ...}` (engine Fx in the same 3D space). Never draw objects in code.

## Motion kit (`src/kit`: transitions, looks, animated text)

`import {Enter, Grade, MaskTitle, ...} from '../kit';` Every piece depends only on the frame (stills = render) and draws
the scene ONCE (no copies of a 3D stage). Moves and timings come from Motion Prompt (MIT, showheyohtaki.github.io/motion-prompt;
the `#nnn` numbers below are its catalogue). Showcase of every piece on real layers: `engine/out/showcase/kit_showcase.mp4`
(re-render inside engine/: `npx remotion render showcase/index.ts KitShowcase out/showcase/kit_showcase.mp4 --gl=angle`).

**Variety is the point:** a film where all 80 cuts are the same 15-frame dissolve and every shot is the same slow push
feels flat. Choose the transition, look and text style per scene from what the story does at that moment, and write the
choice in the scene list (`transition`, `look`, `text_fx`) so the user sees it. Restraint still applies: most cuts stay
dissolves; a strong transition is an accent (every 4-8 scenes, on a turn in the story), never every cut.

### Transitions: wrap the INCOMING scene, keep the timeline

```tsx
<Sequence from={s.from} durationInFrames={s.duration + ov}>   // ov = TRANSITION_LEN[kind of the NEXT scene's entry]
  <Enter kind="leak"><Scene .../></Enter>                      // replaces the old <Fade>
</Sequence>
```
The outgoing scene runs `ov` frames under the incoming one (as before), so scene starts and voice sync never move.

| kind | frames | what it is | when |
|---|---|---|---|
| `cut` | 0 | hard cut | rhythm, shock, interview clips |
| `dissolve` | 15 | cross dissolve (#044) | default, time passes softly |
| `dip` | 22 | fade through black (`color` to change) | end of a chapter, a death, a long time jump |
| `flash` | 12 | smash cut on a burst of light (#046) | revelation, impact, explosion, "and then..." |
| `leak` | 26 | warm film-burn light sweeping across (#119) | memory, flashback, the past, warmth, a dream |
| `whip` | 10 | fast pan with horizontal motion blur (#043), `dir` 1/-1 | energy, "meanwhile", jump to another place |
| `zoom` | 14 | zoom through: old shot rushes past, new one settles (#020) | diving deeper, into a detail, into a map |
| `wipe` | 20 | soft diagonal wipe with a line of light (#045) | travel, moving between parallel stories |
| `iris` | 24 | opens in a circle from `at` (#017) | focus on one thing / person, old-film feel |
| `blinds` | 18 | horizontal strips open (#138) | lists, documents, archive material |
| `glitch` | 10 | digital slices + RGB split (#023) | news, leaks, hacking, surveillance, "classified" |

### Looks and camera feel (wrappers / overlays per scene)

| Component | Use |
|---|---|
| `<Grade look="teal-orange \| bleach \| warm \| cold \| archive \| noir \| duotone" amount duo>` | colour grade of the scene (SVG tone curves). `archive` + `<ArchiveFilm>` = old film for archive photos, flashbacks; `bleach` war, harsh; `cold` ice, mystery; `warm` sunsets, nostalgia; `duotone` (`duo={[dark, light]}`) one stylised emphasis scene |
| `<ArchiveFilm amount>` | gate weave, exposure flicker, dust, scratches (#118) |
| `<Handheld amount>` | organic handheld drift (#034): tension, "you are there", reportage. 0.4 = barely alive |
| `<Impact hits={[frames]} amp>` | jolt + punch-in on impact frames (#024): explosion, a blow, a door slams. Put the frames in CUES so the sound lands with it |
| `<LightLeak amount seed warm>` | slow breathing light leak over a scene (overlay, after the scene) |
| `<LensFlare x y amount color>` | anamorphic flare at a light source (sun, lamp, fire, a glowing object) |
| `<Chroma px>` | chromatic fringes (#111): unease, a damaged recording |
| `<Glitch amount seed>` | glitch as a look (not only a transition): a corrupted file, a hacked screen |

Grades and fringes are SVG filters: cheap on stills, a few % slower on renders. Do not stack more than two wrappers.

### Animated text (frames local to the scene; `theme={DOC_THEME | NEWS_THEME}`)

| Component | Use |
|---|---|
| `<MaskTitle lines sub from to y>` | lines rise out of a slot, staggered, rule draws (#005 #002): film title, a big statement |
| `<ChapterCard num title sub from to>` | chapter opener: numeral, rules drawing out, title from a mask, dim backdrop |
| `<LowerThird name role from to side>` | person / place name with a drawn bar and line (#004) |
| `<Typewriter text from to cps x y box>` | place-and-date stamp typed with a caret (#006): "ANTARCTICA · JANUARY 1947" |
| `<Scramble text from to mono>` | text decodes from random glyphs (#129): code names, files, "classified" |
| `<CountUp value from to prefix suffix label>` | number runs to its value (#007): years, distances, tolls, money |
| `<PunchWords text from to>` | words punch in with overshoot; `*word*` = accent colour (#008 #010): key line of the film |
| `<PullQuote text cite from to>` | big quotation, words sharpen in, citation draws in: a verbatim source line |
| `<Highlight text mark from to>` | marker sweeps behind one phrase (#080): the number or the claim in a news line |

Text pieces bring a soft dark pool (`scrim`, 0..1) so they read on bright pictures; keep text off faces and inside the
letterbox band. Cinzel has no Vietnamese/Cyrillic glyphs: films in those languages use `NEWS_THEME` fonts (Oswald, Inter,
IBM Plex Mono) or a theme of your own built from them.

## Dossier kit (pipeline `dossier`, rulebook 4.11: real photos and documents as evidence)

`import {DossierScene} from '../dossier';` A scene is data: `<DossierScene shot={cfg} duration={duration} scene="sc07" />`
(`scene` = the id in SCENES, needed to resolve narration times). Showcase of every kind on demo material:
`engine/out/showcase/dossier_showcase.mp4` (re-render inside engine/:
`npx remotion render showcase/index.ts DossierShowcase out/showcase/dossier_showcase.mp4 --gl=angle`;
stills: `node showcase/stills.mjs --comp DossierShowcase 20 240 ...`).

| `shot.kind` | Data | What it does |
|---|---|---|
| `photos` | `cards: CardSpec[]`, `tone`, `cam?` | real photos as prints on a desk; the camera follows each card as it lands |
| `doc` | `page: DocSpec`, `cards?` | a page image; camera travels to each mark, marker sweeps line by line, red-pen notes, stamp |
| `board` | `cards: (CardSpec & {id})[]`, `links: {a, b, at, label?}[]` | pinned prints, red string drawn per link, labels on the string |
| `archive` | `clip: {src, gate: 'film' or 'tv', color?, stock?, counter?, volume?}` | old footage / photo inside a film gate or old TV, weave, dust, light leak at the end |
| `logo` | `logo: {src, aspect, w?, title?, sub?, ghosts?, photo?}` | real emblem given thickness, slow turn, light sweep, fog, earlier links as ghosts |
| `years` | `years: {label, at}[]`, `card?` | big years sliding along a ruled line over a portrait |

`CardSpec`: `src` (under public/), `aspect`, `x y` (centre, frame fractions), `w` (width fraction), `rot`, `tilt [rx, ry]`,
`at` (lands), `enter` drop|slide-left|slide-right|rise|fade|none, `frame` print|polaroid|clean|none,
`tone` none|bw|sepia|archive|red|cold, `label` + `labelAt` + `labelStyle` caps|tag|type (typed one letter at a time),
`reveal` (dark blurred -> sharp), `redact` [[x,y,w,h]] (fractions of the picture), `stamp {text, at, ink, x, y, rot}`,
`pin`, `until` (lifted away), `z`.
`DocSpec`: `src`, `aspect`, `w` (default 0.82), `rot`, `marks [{boxes [[x,y,w,h]], at, dur?, color yellow|green|pink|blue,
style marker|box|underline, zoom?, focus?}]`, `notes [{text, at, x, y, to?: [x, y], size?, ink?}]`, `stamp`, `cam?`, `blur`.
Desk tones: night (default), paper, steel, cork, black.

- **Every `at` may be a narration reference**: `"l12"` (first word of line l12), `"l12:non-faculty"` (first word of the
  phrase), `"l12:Drexel-4"` (offset in frames). Resolved from `src/voice.json` (`src/dossier/sync.ts`); a mark whose `at`
  is a phrase sweeps for exactly as long as the phrase is spoken. A phrase that is not in the caption throws: fix the words.
- **Page images and phrase boxes**: `node scripts/pagecap.mjs <url|file.html> <id> --mark "phrase" [--mark ...] [--width 1100]
  [--height 1400] [--top] [--css "..."] [--out public/docs]` -> `public/docs/<id>.png` (2x) + `<id>.json`
  (`src`, `aspect`, `marks[].boxes` one box per line, fractions of the image). Exit code 3: a phrase was `missing` or
  `outside_capture`. Navigation, cookie banners and sticky headers are hidden (`--no-clean` keeps them).
- Cameras are automatic (photos: follow the cards; doc: travel to each mark ~14 frames before its sweep, then to each
  pen note; board: toward each new link) and always drift; give `cam: [{at, x, y, zoom}]` only to override.
- The edges of the frame are softly out of focus (`FocusPool`, `blur`), the centre is sharp: place what matters near
  the centre of the camera's path, not at the frame edge.
- Not dossier shots: interview clips (`QuoteClip`), maps (news-map template), numbers (`CountUp`), reconstructions
  (`LayerScene`). Film-level Grain / Vignette / Letterbox stay on top as in every film.

## Text and quotes

- `<Caption text from to cite words>`: word-by-word reveal, bottom band above the letterbox, balanced lines.
  With narration use `<Caption {...narration('lineId')} />`: timing comes from `src/voice.json`, every word
  appears as the narrator says it, and a caption is gone before the next one starts.
- `<Label text sub from to>`: small spaced title at the top (book / chapter).
- `<QuoteClip src duration speaker source lines>`: a JRE clip with lower third and verbatim subtitles.
  Lines are frames relative to the clip; take the words from the transcript, never re-word them.
- Fonts: Cinzel (titles, citations), Cormorant Garamond italic (narration, subtitles).

## Narration (ElevenLabs API through gen.py)

1. **Write the whole script into one text file** `audio/voice/script.txt`: one take = one recording session, same
   timbre and loudness from line to line. One line per paragraph (blank line between lines) so the lines can be
   cut apart. Prompt technique that sounds human (models with audio tags: eleven_v4, eleven_v4_turbo, eleven_v3):
   - one short emotion/delivery tag per line: `[reverent]`, `[ominous]`, `[low, intense]`, `[grave]`,
     `[sorrowful]`, `[solemn, firm]`, `[quietly]`; a breath before the first line `[inhales softly]`;
   - pauses with `…` and `—` (not with tags); do not over-tag;
   - caption text and spoken text must be the same words (captions are timed word by word).
   Other models (multilingual_v2, flash) read tags aloud: gen.py strips them.
2. **Generate** 2–3 takes in one command (the voice of the project's language comes from the Settings page):
   `"$CREATER_PYTHON" "$GEN_PY" tts --text-file audio/voice/script.txt --out audio/voice/take.mp3 --takes 2 --timestamps`
   → `take1.mp3`, `take2.mp3` (+ `.alignment.json`: time of every character and word). Each take costs the full
   script (≈ $0.08 per 1,000 characters with eleven_v4, logged in notes/costs.json).
3. **Pick** the best take by checking each with whisper (all words present, no tag read aloud, pacing that fits
   the scenes).
4. **Place** in `audio/voice/plan.json`:
   ```json
   {"take": "take2.mp3", "voice": {"name": "George", "voice_id": "..."},
    "lines": [{"id": "heaven", "scene": "heaven", "at": 0, "tempo": 1.0, "caption": "The Watchers of heaven looked down upon the daughters of men."},
              {"id": "oath", "scene": "oath", "at": -9, "tempo": 1.03, "caption": "“Let us all swear an oath…”", "cite": "1 ENOCH 6:4"},
              {"id": "title", "scene": "title", "at": 21, "caption": null, "words": 2}]}
   ```
   `at` = frame local to the scene (negative = the voice starts just before the cut, a J-cut); `tempo` <= 1.03
   (rubberband, inaudible); words are counted from `caption` (or `words`). Sync key words to picture cues.
5. `"$WHISPER_PY" scripts/voice-build.py` prints each line's time and gap (warns on overlaps); then
   `node scripts/make-audio.mjs`.
6. Check the balance: `out/stem_voice.wav` vs `out/stem_score.wav` (voice >= 10 LU above the score while it
   speaks, in the 300-5000 Hz band).

Tags count as characters. About 1,000 characters per minute of narration. Voices: the narrator of each video
language is chosen on the Settings page (ElevenLabs voice library); `"$GEN_PY" voices --lang ru --q documentary`
lists others, `--voice <id>` overrides it for one take (ask the user before changing the film's narrator).

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
8. `useOffthreadVideoTexture` delivers each video frame after the canvas has drawn, and while rendering the canvas
   only redraws when Remotion changes frame: the video was invisible. `VideoFx` holds each frame and redraws when
   its texture arrives; reuse `VideoFx`, do not call the hook directly.
9. BiRefNet drops thin detached parts (a halo ring behind a head): `cutout.py` adds them back. The matting model
   keeps flames translucent but turned a rock landscape half transparent: matting only for fire/smoke/glow.
10. Background-removal APIs leave the grey of the backdrop on soft edges (a light outline on dark scenes):
    use `cutout.py` (it re-estimates the edge colours).
