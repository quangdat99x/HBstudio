import fs from 'node:fs';
import path from 'node:path';
import {Config} from '@remotion/cli/config';
import {startTileCache} from './scripts/tilecache.mjs';

Config.setVideoImageFormat('jpeg');
Config.setJpegQuality(92);
Config.setConcurrency(6);
Config.setCrf(17);
Config.setOverwriteOutput(true);
// WebGL through ANGLE on the GPU (RTX 4060) for the three.js stages.
Config.setChromiumOpenGlRenderer('angle');
Config.setDelayRenderTimeoutInMilliseconds(120000);

// Chrome Headless Shell sits in the shared engine install behind the node_modules junction; use its real
// (short) path so deep project folders never hit Windows' 260-character launch limit.
try {
  const real = fs.realpathSync.native(path.resolve('node_modules'));
  const exe = path.join(real, '.remotion', 'chrome-headless-shell', 'win64', 'chrome-headless-shell-win64', 'chrome-headless-shell.exe');
  if (fs.existsSync(exe)) Config.setBrowserExecutable(exe);
} catch {
  // fresh install: Remotion downloads the browser itself
}

// bộ đệm tile bản đồ trên đĩa cho Map3D (scripts/tilecache.mjs): chạy kèm mỗi lượt render, không có thì Map3D tải thẳng
startTileCache();
