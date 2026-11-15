import React from 'react';
import {AbsoluteFill, Sequence, useCurrentFrame, interpolate} from 'remotion';
import {loadFont} from '@remotion/google-fonts/Inter';
import {Grain, Letterbox, Vignette} from '../src/components/Overlays';
import {clamp} from '../src/lib/anim';
import {Enter} from '../src/kit';
import {DossierScene, ShotCfg} from '../src/dossier';
import WIKI from '../public/dossier-demo/wiki_bilderberg.json';

// Dossier kit showcase (pipeline `dossier`, rulebook 4.11): every shot kind on demo material.
// `npx remotion render showcase/index.ts DossierShowcase out/showcase/dossier_showcase.mp4 --gl=angle` (inside engine/).
// The "photos" are the kit-demo paintings standing in for real photographs; the page is a real Wikipedia capture
// made with scripts/pagecap.mjs; the emblem is a made-up seal.

const {fontFamily: inter} = loadFont('normal', {weights: ['500', '700'], subsets: ['latin', 'vietnamese']});

const P = (k: string) => `kit-demo/${k}/far.png`;
const box = (i: number) => WIKI.marks[i].boxes as [number, number, number, number][];

const SHOTS: {vi: string; len: number; enter: 'cut' | 'dissolve' | 'flash' | 'zoom' | 'blinds' | 'leak'; shot: ShotCfg}[] = [
  {vi: 'photos: ảnh thật thả xuống bàn, lộ mặt, gõ tên, đóng dấu', len: 170, enter: 'cut', shot: {kind: 'photos', cards: [
    {src: P('sc05'), aspect: 1.5, x: 0.27, y: 0.42, w: 0.26, rot: -6, at: 4, tone: 'sepia'},
    {src: P('sc27'), aspect: 1.5, x: 0.73, y: 0.58, w: 0.26, rot: 5, at: 14, enter: 'slide-right', tone: 'bw'},
    {src: P('sc29'), aspect: 1.5, x: 0.5, y: 0.48, w: 0.34, rot: -1.5, at: 30, reveal: 60, label: 'Prince Bernhard', labelAt: 78, labelStyle: 'caps',
      stamp: {text: 'Confirmed', at: 118, ink: 'red', x: 0.72, y: 0.22, rot: -14}},
  ]}},
  {vi: 'doc: trang thật, máy đi tới từng cụm, highlight quét theo lời, bút đỏ', len: 230, enter: 'blinds', shot: {kind: 'doc', page: {
    src: WIKI.src, aspect: WIKI.aspect,
    marks: [{boxes: box(1), at: 26, dur: 46}, {boxes: box(2), at: 92, style: 'box'}, {boxes: box(0), at: 150, dur: 26}],
    notes: [{text: 'the founder', at: 180, x: 0.47, y: 0.31, to: [0.33, 0.288]}],
  }}},
  {vi: 'board: bảng điều tra, dây đỏ nối từng mắt xích', len: 210, enter: 'zoom', shot: {kind: 'board', cards: [
    {id: 'a', src: P('sc19'), aspect: 1.5, x: 0.2, y: 0.36, w: 0.18, rot: -4, at: 2, label: 'Dialog', labelStyle: 'tag'},
    {id: 'b', src: P('sc25'), aspect: 1.5, x: 0.52, y: 0.3, w: 0.18, rot: 3, at: 10, label: 'Bilderberg', labelStyle: 'tag'},
    {id: 'c', src: P('sc29'), aspect: 1.5, x: 0.8, y: 0.42, w: 0.18, rot: -2, at: 18, label: '1001 Club', labelStyle: 'tag'},
    {id: 'd', src: P('sc05'), aspect: 1.5, x: 0.42, y: 0.7, w: 0.17, rot: 5, at: 26, label: 'Safari Club', labelStyle: 'tag'},
  ], links: [{a: 'a', b: 'b', at: 50, label: '4 shared members'}, {a: 'b', b: 'c', at: 100, label: 'same founder'}, {a: 'c', b: 'd', at: 150}]}},
  {vi: 'archive: tư liệu cũ trong khung phim 8mm, vệt sáng cuối', len: 150, enter: 'leak', shot: {kind: 'archive', clip: {src: P('sc29'), counter: 1046}}},
  {vi: 'logo: biểu tượng thật thành vật thể 3D, các hội trước mờ phía sau', len: 170, enter: 'flash', shot: {kind: 'logo', logo: {
    src: 'dossier-demo/emblem.png', aspect: 1, w: 0.24, title: 'The Order', sub: 'est. 1954 · Oosterbeek', ghosts: ['Dialog', 'Bilderberg', '1001 Club', 'Safari Club'],
  }}},
  {vi: 'years: năm trượt trên đường kẻ, qua ảnh chân dung', len: 170, enter: 'dissolve', shot: {kind: 'years', card: {src: P('sc27'), aspect: 1.5, w: 0.3, y: 0.42},
    years: [{label: '1954', at: 10}, {label: '1975', at: 70}, {label: '2026', at: 125}], tone: 'night'}},
];

const Chip: React.FC<{text: string}> = ({text}) => {
  const f = useCurrentFrame();
  return (
    <div style={{position: 'absolute', top: 30, left: 40, fontFamily: inter, fontWeight: 700, fontSize: 30, color: '#ffd27a', opacity: interpolate(f, [0, 8], [0, 1], clamp), zIndex: 20}}>
      {text}
    </div>
  );
};

const STARTS = SHOTS.reduce<number[]>((acc, s, i) => [...acc, i ? acc[i - 1] + SHOTS[i - 1].len : 0], []);
export const DOSSIER_LEN = STARTS[STARTS.length - 1] + SHOTS[SHOTS.length - 1].len;

export const DossierShowcase: React.FC = () => (
  <AbsoluteFill style={{backgroundColor: '#000'}}>
    {SHOTS.map((s, i) => {
      const ov = i < SHOTS.length - 1 ? 16 : 0;
      return (
        <Sequence key={i} from={STARTS[i]} durationInFrames={s.len + ov}>
          <Enter kind={s.enter}>
            <DossierScene shot={s.shot} duration={s.len + ov} />
          </Enter>
          <Chip text={s.vi} />
        </Sequence>
      );
    })}
    <Grain />
    <Vignette />
    <Letterbox />
  </AbsoluteFill>
);
