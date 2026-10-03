import React, {createContext, useContext} from 'react';
import * as THREE from 'three';
import {useThree} from '@react-three/fiber';
import {ThreeCanvas} from '@remotion/three';
import {useVideoConfig} from 'remotion';
import {Post, PostFx} from './PostFx';

export type V3 = [number, number, number];

export type Shot = {
  pos: V3;
  target: V3;
  fov?: number;
  roll?: number;
  focus: number; // distance in focus
  aperture: number; // blur strength for things far from the focus plane
};

type Lens = {z: number; focus: number; aperture: number; pxPerUnitAt1: number};
const LensContext = createContext<Lens>({z: 0, focus: 20, aperture: 0, pxPerUnitAt1: 1712});
export const useLens = () => useContext(LensContext);

const CameraRig: React.FC<{shot: Shot}> = ({shot}) => {
  const camera = useThree((s) => s.camera) as THREE.PerspectiveCamera;
  const roll = shot.roll ?? 0;
  camera.position.set(...shot.pos);
  camera.up.set(Math.sin(roll), Math.cos(roll), 0);
  camera.lookAt(...shot.target);
  camera.fov = shot.fov ?? 35;
  camera.near = 0.1;
  camera.far = 2000;
  camera.updateProjectionMatrix();
  return null;
};

// A 3D multiplane stage: every layer is a plane at a real depth in front of a moving camera.
export const Stage: React.FC<{shot: Shot; post?: Post; children: React.ReactNode}> = ({shot, post, children}) => {
  const {width, height} = useVideoConfig();
  const fov = shot.fov ?? 35;
  const lens: Lens = {
    z: shot.pos[2],
    focus: shot.focus,
    aperture: shot.aperture,
    pxPerUnitAt1: height / (2 * Math.tan(((fov / 2) * Math.PI) / 180)),
  };
  return (
    <ThreeCanvas
      width={width}
      height={height}
      linear
      flat
      gl={{antialias: true, alpha: false}}
      camera={{fov, near: 0.1, far: 2000, position: shot.pos}}
      style={{background: '#000'}}
    >
      <color attach="background" args={['#000000']} />
      <CameraRig shot={shot} />
      <LensContext.Provider value={lens}>{children}</LensContext.Provider>
      {post && <PostFx post={post} />}
    </ThreeCanvas>
  );
};
