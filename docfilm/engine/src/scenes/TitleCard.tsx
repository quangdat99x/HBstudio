import React from 'react';
import {AbsoluteFill, Easing, interpolate, useCurrentFrame} from 'remotion';
import * as THREE from 'three';
import {Particles} from '../engine/Fx';
import {Shot, Stage} from '../engine/Stage';
import {motes} from '../engine/actor';
import {cinzel} from '../components/Text';
import {clamp} from '../lib/anim';
import {FPS} from '../timeline';

// Starter scene: gold dust in a 3D stage + the film title. Replace or extend it.
const GOLD = new THREE.Color('#e8c27a');

export const TitleCard: React.FC<{duration: number; title?: string; subtitle?: string}> = ({title = 'UNTITLED', subtitle = ''}) => {
  const f = useCurrentFrame();
  const t = f / FPS;
  const inO = interpolate(f, [0, 26], [0, 1], {...clamp, easing: Easing.out(Easing.cubic)});
  const spacing = interpolate(f, [0, 70], [0.55, 0.24], {...clamp, easing: Easing.out(Easing.cubic)});
  const shot: Shot = {pos: [0, 0, 0], target: [0, 0, -20], focus: 12, aperture: 1.2};
  return (
    <AbsoluteFill style={{backgroundColor: '#000'}}>
      <Stage shot={shot}>
        <Particles count={90} color="#e8c27a" get={motes('tc', t, {x: [-14, 14], y: [-7, 7], z: [-30, -8]}, {rise: 0.3, size: 0.07, alpha: 0.55, color: GOLD})} />
      </Stage>
      <AbsoluteFill style={{alignItems: 'center', justifyContent: 'center', opacity: inO}}>
        <div
          style={{
            fontFamily: cinzel,
            fontWeight: 700,
            fontSize: 110,
            letterSpacing: `${spacing}em`,
            paddingLeft: `${spacing}em`,
            background: 'linear-gradient(180deg, #fff3d6 0%, #e6c585 55%, #9c7a3e 100%)',
            WebkitBackgroundClip: 'text',
            backgroundClip: 'text',
            color: 'transparent',
            filter: 'drop-shadow(0 0 24px rgba(255, 200, 120, 0.35))',
          }}
        >
          {title}
        </div>
        {subtitle && <div style={{marginTop: 22, fontFamily: cinzel, fontSize: 24, letterSpacing: '0.5em', paddingLeft: '0.5em', color: '#b99a62'}}>{subtitle}</div>}
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
