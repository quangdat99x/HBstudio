import React from 'react';
import {AbsoluteFill, Html5Audio, interpolate, Sequence, staticFile, useCurrentFrame} from 'remotion';
import {Grain, Letterbox, Vignette} from './components/Overlays';
import {clamp} from './lib/anim';
import {AUDIO, SCENES} from './timeline';
import {TitleCard} from './scenes/TitleCard';

// Each scene fades in on top of the previous one, which stays opaque underneath: a true crossfade.
const Fade: React.FC<{children: React.ReactNode; duration: number; fadeIn?: number; fadeOut?: number}> = ({
  children,
  duration,
  fadeIn = 15,
  fadeOut = 0,
}) => {
  const f = useCurrentFrame();
  const a = Math.min(
    fadeIn ? interpolate(f, [0, fadeIn], [0, 1], clamp) : 1,
    fadeOut ? interpolate(f, [duration - fadeOut, duration], [1, 0], clamp) : 1,
  );
  return <AbsoluteFill style={{opacity: a}}>{children}</AbsoluteFill>;
};

type SceneEntry = {key: keyof typeof SCENES; C: React.FC<{duration: number}>; fadeIn: number; fadeOut: number};
const SCENE_LIST: SceneEntry[] = [{key: 'title', C: TitleCard, fadeIn: 20, fadeOut: 20}];

export const Film: React.FC = () => (
  <AbsoluteFill style={{backgroundColor: 'black'}}>
    {SCENE_LIST.map(({key, C, fadeIn, fadeOut}) => {
      const s = SCENES[key];
      return (
        <Sequence key={key} name={String(key)} from={s.from} durationInFrames={s.duration}>
          <Fade duration={s.duration} fadeIn={fadeIn} fadeOut={fadeOut}>
            <C duration={s.duration} />
          </Fade>
        </Sequence>
      );
    })}
    <Vignette />
    <Grain />
    <Letterbox />
    {AUDIO && <Html5Audio src={staticFile('soundtrack.wav')} />}
  </AbsoluteFill>
);
