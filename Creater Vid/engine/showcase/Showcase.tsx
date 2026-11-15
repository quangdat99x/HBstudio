import React from 'react';
import {AbsoluteFill, Composition, Sequence, useCurrentFrame, interpolate} from 'remotion';
import {loadFont} from '@remotion/google-fonts/Inter';
import {LayerCfg, LayerScene, Move} from '../src/staged/LayerScene';
import {Grain, Letterbox, Vignette} from '../src/components/Overlays';
import {clamp} from '../src/lib/anim';
import {
  ArchiveFilm, ChapterCard, Chroma, CountUp, Enter, Grade, GradeKind, Handheld, Highlight, Impact, LensFlare, LightLeak,
  LowerThird, MaskTitle, NEWS_THEME, PullQuote, PunchWords, Scramble, TRANSITION_LEN, TransitionKind, Typewriter,
} from '../src/kit';
import {DOSSIER_LEN, DossierShowcase} from './Dossier';
import L05 from '../public/kit-demo/sc05/layers.json';
import L19 from '../public/kit-demo/sc19/layers.json';
import L25 from '../public/kit-demo/sc25/layers.json';
import L27 from '../public/kit-demo/sc27/layers.json';
import L29 from '../public/kit-demo/sc29/layers.json';

const {fontFamily: inter} = loadFont('normal', {weights: ['500', '700'], subsets: ['latin', 'vietnamese']});

const SC = {sc05: L05, sc19: L19, sc25: L25, sc27: L27, sc29: L29} as unknown as Record<string, LayerCfg>;
const Demo: React.FC<{k: string; d: number; move?: Move; frame?: [number, number]}> = ({k, d, move = 'push-in', frame = [0.5, 0.45]}) => (
  <LayerScene cfg={SC[k]} duration={d} move={move} frame={frame} />
);

// Vietnamese caption chip in the top letterbox band: what is being shown.
const Chip: React.FC<{text: string; sub?: string}> = ({text, sub}) => {
  const f = useCurrentFrame();
  const o = interpolate(f, [0, 8], [0, 1], clamp);
  return (
    <AbsoluteFill style={{pointerEvents: 'none', zIndex: 10}}>
      <div style={{position: 'absolute', top: 26, left: 40, display: 'flex', alignItems: 'baseline', gap: 18, opacity: o, fontFamily: inter}}>
        <span style={{fontWeight: 700, fontSize: 34, color: '#ffd27a'}}>{text}</span>
        {sub && <span style={{fontWeight: 500, fontSize: 24, color: '#c9c9c9'}}>{sub}</span>}
      </div>
    </AbsoluteFill>
  );
};

// ---------- Part A: transitions ----------
const TR: {kind: TransitionKind; vi: string; src: string}[] = [
  {kind: 'dissolve', vi: 'mờ chéo (đang dùng hiện nay)', src: '#044'},
  {kind: 'dip', vi: 'tối dần rồi sáng lại', src: 'dip to black'},
  {kind: 'flash', vi: 'chớp sáng, cắt mạnh', src: '#046 smash cut'},
  {kind: 'leak', vi: 'vệt sáng phim cháy', src: '#119 light leak'},
  {kind: 'whip', vi: 'lia máy giật', src: '#043 whip pan'},
  {kind: 'zoom', vi: 'lao xuyên qua cảnh', src: '#020 zoom through'},
  {kind: 'wipe', vi: 'quét chéo có viền sáng', src: '#045 wipe'},
  {kind: 'iris', vi: 'mở tròn từ một điểm', src: '#017 mask transition'},
  {kind: 'blinds', vi: 'rèm sọc', src: '#138 blinds'},
  {kind: 'glitch', vi: 'nhiễu số (hợp tin tức)', src: '#023 glitch'},
];
const ROT = ['sc05', 'sc19', 'sc25', 'sc27', 'sc29'];
const MOVES: Move[] = ['push-in', 'truck-right', 'crane-down', 'orbit-left', 'push-truck-right'];
const A_SLOT = 80;
const A_N = TR.length + 1;

const PartA: React.FC = () => (
  <>
    {Array.from({length: A_N}, (_, i) => {
      const enter = i > 0 ? TR[i - 1] : null;
      const next = i < TR.length ? TR[i] : null;
      const ov = next ? TRANSITION_LEN[next.kind] : 0;
      const k = ROT[i % ROT.length];
      return (
        <Sequence key={i} from={i * A_SLOT} durationInFrames={A_SLOT + ov}>
          <Enter kind={enter ? enter.kind : 'cut'} dir={i % 2 ? 1 : -1} at={[0.55, 0.45]}>
            <Demo k={k} d={A_SLOT + ov} move={MOVES[i % MOVES.length]} />
          </Enter>
        </Sequence>
      );
    })}
  </>
);
const A_LEN = A_N * A_SLOT;

// ---------- Part B: looks and camera feel ----------
const B_SLOT = 80;
type LookDemo = {vi: string; src: string; k: string; render: (inner: React.ReactNode) => React.ReactNode};
const g = (look: GradeKind) => (inner: React.ReactNode) => <Grade look={look}>{inner}</Grade>;
const LOOKS: LookDemo[] = [
  {vi: 'gốc (không chỉnh)', src: '', k: 'sc27', render: (x) => x},
  {vi: 'teal & orange (màu điện ảnh)', src: '#117', k: 'sc27', render: g('teal-orange')},
  {vi: 'bleach bypass (lạnh, gắt, chiến tranh)', src: '', k: 'sc27', render: g('bleach')},
  {vi: 'ấm (hoàng hôn, hoài niệm)', src: '', k: 'sc19', render: g('warm')},
  {vi: 'lạnh (băng giá, bí ẩn)', src: '', k: 'sc19', render: g('cold')},
  {vi: 'duotone (2 màu, cảnh nhấn)', src: '#116', k: 'sc19', render: g('duotone')},
  {vi: 'phim tư liệu cũ: đen trắng + rung khung + bụi', src: '#115 #118', k: 'sc29', render: (x) => <ArchiveFilm><Grade look="archive">{x}</Grade></ArchiveFilm>},
  {vi: 'noir (đen trắng tương phản mạnh)', src: '', k: 'sc29', render: g('noir')},
  {vi: 'máy cầm tay (handheld)', src: '#034', k: 'sc25', render: (x) => <Handheld>{x}</Handheld>},
  {vi: 'rung khi va chạm (impact shake)', src: '#024', k: 'sc25', render: (x) => <Impact hits={[20, 52]}>{x}</Impact>},
  {vi: 'vệt sáng trôi (light leak)', src: '#119', k: 'sc05', render: (x) => <>{x}<LightLeak amount={0.6} /></>},
  {vi: 'loé ống kính (lens flare)', src: '#109', k: 'sc29', render: (x) => <>{x}<LensFlare x={0.535} y={0.6} /></>},
  {vi: 'viền màu ống kính (chromatic aberration)', src: '#111', k: 'sc05', render: (x) => <Chroma px={4}>{x}</Chroma>},
];
const PartB: React.FC = () => (
  <>
    {LOOKS.map((l, i) => (
      <Sequence key={i} from={i * B_SLOT} durationInFrames={B_SLOT}>
        <AbsoluteFill>{l.render(<Demo k={l.k} d={B_SLOT} move={l.k === 'sc25' ? 'drift' : 'push-in'} />)}</AbsoluteFill>
      </Sequence>
    ))}
  </>
);
const B_LEN = LOOKS.length * B_SLOT;

// ---------- Part C: animated text ----------
const C_SLOT = 110;
type TextDemo = {vi: string; k: string; el: React.ReactNode};
const E = C_SLOT - 4;
const TEXTS: TextDemo[] = [
  {vi: 'tựa lớn trồi lên từ khe (mask reveal + stagger) — #005 #002', k: 'sc05',
    el: <MaskTitle lines={['The Lost', 'Continent']} sub="What lies beneath two miles of ice?" from={6} to={E} y={0.45} />},
  {vi: 'thẻ chương', k: 'sc29', el: <ChapterCard num="Chapter II" title="The Expedition" sub="Operation Highjump, 1946–47" from={4} to={E} />},
  {vi: 'tên nhân vật / địa danh (lower third) — #004', k: 'sc29', el: <LowerThird name="Richard E. Byrd" role="Rear Admiral, U.S. Navy" from={8} to={E} />},
  {vi: 'dấu địa điểm – thời gian gõ máy chữ — #006', k: 'sc05', el: <Typewriter text="ANTARCTICA  ·  JANUARY 1947" from={8} to={E} />},
  {vi: 'chữ giải mã (text scramble) — #129', k: 'sc25', el: <Scramble text="Classified file 47-B" mono from={6} to={E} size={70} />},
  {vi: 'số đếm (count-up) — #007', k: 'sc25', el: <CountUp value={12000} suffix=" YRS" label="since the ice last melted" from={6} to={E} />},
  {vi: 'chữ đập theo nhịp (kinetic + overshoot) — #008 #010', k: 'sc19',
    el: <PunchWords text="They found *something* under the *ice*" from={8} to={E} />},
  {vi: 'trích dẫn lớn (pull quote)', k: 'sc19',
    el: <PullQuote text="In a single day and night of misfortune the island of Atlantis disappeared in the depths of the sea." cite="Plato · Timaeus" from={4} to={E} />},
  {vi: 'tin tức: tô sáng con số — #080', k: 'sc27',
    el: <Highlight text="Giá dầu tăng 12% chỉ trong một đêm" mark="12%" from={6} to={E} />},
  {vi: 'tin tức: tên người (theme tin)', k: 'sc27', el: <LowerThird name="Марина Иванова" role="Корреспондент, Москва" theme={NEWS_THEME} from={8} to={E} />},
];
const PartC: React.FC = () => (
  <>
    {TEXTS.map((t, i) => (
      <Sequence key={i} from={i * C_SLOT} durationInFrames={C_SLOT}>
        <Demo k={t.k} d={C_SLOT} move="drift" />
        {t.el}
      </Sequence>
    ))}
  </>
);
const C_LEN = TEXTS.length * C_SLOT;

export const SHOWCASE_LEN = A_LEN + B_LEN + C_LEN;

// Every chip on the film's own timeline, drawn above the letterbox.
const CHIPS: {from: number; dur: number; text: string; sub?: string}[] = [
  {from: 0, dur: A_SLOT - 6, text: 'PHẦN 1 · CHUYỂN CẢNH', sub: 'mỗi cảnh sau vào bằng một kiểu, tên ghi ở đây'},
  ...TR.map((t, i) => ({from: (i + 1) * A_SLOT, dur: A_SLOT - 6, text: `Chuyển cảnh ${i + 1}/${TR.length} · ${t.kind}`, sub: `${t.vi} — ${t.src}`})),
  ...LOOKS.map((l, i) => ({from: A_LEN + i * B_SLOT, dur: B_SLOT, text: `Màu & cảm giác máy ${i + 1}/${LOOKS.length}`, sub: `${l.vi}${l.src ? ' — ' + l.src : ''}`})),
  ...TEXTS.map((t, i) => ({from: A_LEN + B_LEN + i * C_SLOT, dur: C_SLOT, text: `Chữ động ${i + 1}/${TEXTS.length}`, sub: t.vi})),
];

export const Showcase: React.FC = () => (
  <AbsoluteFill style={{backgroundColor: 'black'}}>
    <Sequence durationInFrames={A_LEN}><PartA /></Sequence>
    <Sequence from={A_LEN} durationInFrames={B_LEN}><PartB /></Sequence>
    <Sequence from={A_LEN + B_LEN} durationInFrames={C_LEN}><PartC /></Sequence>
    <Vignette />
    <Grain />
    <Letterbox />
    {CHIPS.map((c, i) => (
      <Sequence key={i} from={c.from} durationInFrames={c.dur}><Chip text={c.text} sub={c.sub} /></Sequence>
    ))}
  </AbsoluteFill>
);

export const ShowcaseRoot: React.FC = () => (
  <>
    <Composition id="KitShowcase" component={Showcase} durationInFrames={SHOWCASE_LEN} fps={30} width={1920} height={1080} />
    <Composition id="DossierShowcase" component={DossierShowcase} durationInFrames={DOSSIER_LEN} fps={30} width={1920} height={1080} />
  </>
);
