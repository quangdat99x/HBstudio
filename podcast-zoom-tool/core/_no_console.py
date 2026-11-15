"""
Hide cmd/console windows for ALL subprocess calls on Windows.

Without this, every ffmpeg/ffprobe/whisper invocation flashes a black
console window that steals focus and disrupts the user's other tasks.
Monkey-patching subprocess.Popen covers direct calls AND third-party libs.

Importing this module is the only required action; the patch applies on
import and is idempotent.
"""

import os
import subprocess

_CREATE_NO_WINDOW = 0x08000000
_DETACHED_PROCESS = 0x00000008


def _apply_patch():
    if os.name != 'nt':
        return
    if getattr(subprocess.Popen.__init__, '_no_window_patched', False):
        return

    original_init = subprocess.Popen.__init__

    def patched_init(self, *args, **kwargs):
        flags = kwargs.get('creationflags', 0) or 0
        if not (flags & (_CREATE_NO_WINDOW | _DETACHED_PROCESS)):
            kwargs['creationflags'] = flags | _CREATE_NO_WINDOW
        if kwargs.get('startupinfo') is None:
            si = subprocess.STARTUPINFO()
            si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            si.wShowWindow = subprocess.SW_HIDE
            kwargs['startupinfo'] = si
        return original_init(self, *args, **kwargs)

    patched_init._no_window_patched = True
    subprocess.Popen.__init__ = patched_init


_apply_patch()
