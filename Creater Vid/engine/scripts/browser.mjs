// Chrome Headless Shell lives in the shared engine install. A film reaches it through its node_modules
// junction, but a deep project folder can push that path past Windows' 260-character limit for launching
// programs, so resolve the junction and hand Remotion the real (short) path.
import fs from 'node:fs';
import path from 'node:path';

export function browserExecutable() {
  try {
    const real = fs.realpathSync.native(path.resolve('node_modules'));
    const exe = path.join(real, '.remotion', 'chrome-headless-shell', 'win64', 'chrome-headless-shell-win64', 'chrome-headless-shell.exe');
    return fs.existsSync(exe) ? exe : null;
  } catch {
    return null;
  }
}
