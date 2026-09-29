import {useEffect, useState} from 'react';
import * as THREE from 'three';
import {cancelRender, continueRender, delayRender, staticFile} from 'remotion';

const cache = new Map<string, Promise<THREE.Texture>>();

export const loadTexture = (path: string) => {
  let p = cache.get(path);
  if (!p) {
    p = new Promise<THREE.Texture>((resolve, reject) => {
      new THREE.TextureLoader().load(
        staticFile(path),
        (t) => {
          // Colours pass straight through (sRGB in, sRGB out), like a 2D compositor.
          t.colorSpace = THREE.NoColorSpace;
          t.generateMipmaps = true;
          t.minFilter = THREE.LinearMipmapLinearFilter;
          t.magFilter = THREE.LinearFilter;
          t.anisotropy = 4;
          resolve(t);
        },
        undefined,
        reject,
      );
    });
    cache.set(path, p);
  }
  return p;
};

// Loads every texture a scene needs before its canvas mounts, so the first rendered frame
// already has them (R3F only re-renders when Remotion advances a frame).
export const useTextures = <K extends string>(paths: Record<K, string>) => {
  const [texs, setTexs] = useState<Record<K, THREE.Texture> | null>(null);
  const [handle] = useState(() => delayRender(`Loading textures: ${Object.values(paths).join(', ')}`));
  useEffect(() => {
    let alive = true;
    const keys = Object.keys(paths) as K[];
    Promise.all(keys.map((k) => loadTexture(paths[k])))
      .then((list) => {
        if (!alive) return;
        const out = {} as Record<K, THREE.Texture>;
        keys.forEach((k, i) => (out[k] = list[i]));
        setTexs(out);
      })
      .catch((e) => cancelRender(e));
    return () => {
      alive = false;
    };
    // paths is a static table per scene
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  useEffect(() => {
    if (texs) continueRender(handle);
  }, [texs, handle]);
  return texs;
};
