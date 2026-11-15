import React from 'react';
import {AbsoluteFill} from 'remotion';
import {CamKey, Desk, DeskCam, DeskTone, FocusPool} from './desk';
import {CardLoose, CardSpec, PhotoCard} from './cards';
import {DocShot, DocSpec} from './doc';
import {BoardCard, BoardShot, Link} from './board';
import {ArchiveShot, ArchiveSpec} from './archive';
import {LogoShot, LogoSpec} from './logo';
import {YearMark, YearsShot} from './years';
import {resolveShot} from './sync';

// One dossier scene from data (scenes.json -> "shot"), so a film of 80 evidence shots needs no hand-written scene
// files. Every `at` may be a frame or a narration reference ("l12:non-faculty"), resolved here against voice.json.
//   photos   one or more real photos on the desk (drop / slide / reveal / label / redact / stamp)
//   doc      a document page: camera travels to each marked passage, marker sweeps with the voice, red-pen notes
//   board    investigation board: pinned photos, red string drawn for each link
//   archive  old footage or photo in a film gate / old TV
//   logo     an organisation's real emblem as a 3D object in fog, with the earlier links as ghosts
//   years    years sliding along a line over a portrait
// Maps, interview clips, count-ups and AI reconstructions are not dossier shots: they keep their own components
// (news-map template, QuoteClip, kit CountUp, LayerScene).

export type ShotCfg =
  | {kind: 'photos'; cards: CardSpec[]; tone?: DeskTone; cam?: CamKey[]; blur?: number}
  | {kind: 'doc'; page: DocSpec; cards?: CardSpec[]; tone?: DeskTone}
  | {kind: 'board'; cards: BoardCard[]; links?: Link[]; tone?: DeskTone; cam?: CamKey[]}
  | {kind: 'archive'; clip: ArchiveSpec}
  | {kind: 'logo'; logo: LogoSpec; tone?: DeskTone}
  | {kind: 'years'; years: YearMark[]; card?: CardLoose; tone?: DeskTone};

// Camera for loose photos: start on the first card a little wide, follow each new card as it lands.
const photosCamera = (cards: CardSpec[], duration: number): CamKey[] => {
  const cs = [...cards].sort((a, b) => (a.at ?? 0) - (b.at ?? 0));
  if (cs.length <= 1) {
    const c = cs[0] ?? {x: 0.5, y: 0.5};
    return [{at: 0, x: c.x, y: c.y, zoom: 1.0}, {at: duration, x: c.x, y: c.y, zoom: 1.08}];
  }
  const keys: CamKey[] = [{at: 0, x: cs[0].x, y: cs[0].y, zoom: 1.15}];
  cs.slice(1).forEach((c) => keys.push({at: Math.max(1, (c.at ?? 0) - 6), x: 0.5 + (c.x - 0.5) * 0.45, y: 0.5 + (c.y - 0.5) * 0.45, zoom: 1.04}));
  return keys;
};

export const DossierScene: React.FC<{shot: ShotCfg; duration: number; scene?: string}> = ({shot, duration, scene}) => {
  const s = resolveShot(shot, scene);
  switch (s.kind) {
    case 'doc':
      return <DocShot d={s.page} cards={s.cards} tone={s.tone} duration={duration} />;
    case 'board':
      return <BoardShot cards={s.cards} links={s.links} tone={s.tone} cam={s.cam} duration={duration} />;
    case 'archive':
      return <ArchiveShot a={s.clip} duration={duration} />;
    case 'logo':
      return <LogoShot l={s.logo} tone={s.tone} duration={duration} />;
    case 'years':
      return <YearsShot years={s.years} card={s.card} tone={s.tone} duration={duration} />;
    default: {
      const keys = s.cam?.length ? s.cam : photosCamera(s.cards, duration);
      return (
        <AbsoluteFill>
          <Desk tone={s.tone ?? 'night'} />
          <FocusPool blur={s.blur ?? 3}>
            <DeskCam keys={keys} duration={duration}>
              {s.cards.map((c, i) => <PhotoCard key={i} c={{z: 1 + i, ...c}} />)}
            </DeskCam>
          </FocusPool>
        </AbsoluteFill>
      );
    }
  }
};
