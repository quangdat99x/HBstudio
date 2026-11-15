"""
FFmpeg auto-downloader for Windows.
Downloads a static FFmpeg build if not found on the system.
"""

import os
import subprocess
import sys
import zipfile
import urllib.request
import shutil

# FFmpeg static build for Windows (from gyan.dev - reliable, maintained)
FFMPEG_URL = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
FFMPEG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ffmpeg")
FFMPEG_EXE = os.path.join(FFMPEG_DIR, "ffmpeg.exe")


def find_ffmpeg() -> str | None:
    """Find FFmpeg binary in PATH or local directory."""
    # Check local tool directory first
    if os.path.isfile(FFMPEG_EXE):
        return FFMPEG_EXE

    # Check system PATH
    path = shutil.which('ffmpeg')
    if path:
        return path

    # Check common Windows locations
    common_paths = [
        r'C:\ffmpeg\bin\ffmpeg.exe',
        r'C:\Program Files\ffmpeg\bin\ffmpeg.exe',
        r'C:\Program Files (x86)\ffmpeg\bin\ffmpeg.exe',
        os.path.expanduser(r'~\ffmpeg\bin\ffmpeg.exe'),
        os.path.expanduser(r'~\scoop\shims\ffmpeg.exe'),
    ]
    for p in common_paths:
        if os.path.isfile(p):
            return p

    return None


def ensure_ffmpeg() -> str:
    """
    Ensure FFmpeg is available. Downloads it if not found.
    Returns path to ffmpeg.exe.
    """
    existing = find_ffmpeg()
    if existing:
        return existing

    print("\n" + "=" * 50)
    print("[*] FFmpeg not found -- downloading automatically...")
    print("=" * 50)

    os.makedirs(FFMPEG_DIR, exist_ok=True)
    zip_path = os.path.join(FFMPEG_DIR, "ffmpeg.zip")

    try:
        # Download with progress
        def _progress(block_num, block_size, total_size):
            downloaded = block_num * block_size
            if total_size > 0:
                pct = min(100, int(downloaded / total_size * 100))
                mb_done = downloaded / (1024 * 1024)
                mb_total = total_size / (1024 * 1024)
                sys.stdout.write(f"\r   Downloading: {mb_done:.1f}/{mb_total:.1f} MB ({pct}%)")
                sys.stdout.flush()

        urllib.request.urlretrieve(FFMPEG_URL, zip_path, reporthook=_progress)
        print("\n   Download complete. Extracting...")

        # Extract - find ffmpeg.exe inside the zip
        with zipfile.ZipFile(zip_path, 'r') as zf:
            ffmpeg_found = False
            for member in zf.namelist():
                basename = os.path.basename(member)
                if basename in ('ffmpeg.exe', 'ffprobe.exe'):
                    # Extract to our ffmpeg directory
                    target_path = os.path.join(FFMPEG_DIR, basename)
                    with zf.open(member) as src, open(target_path, 'wb') as dst:
                        shutil.copyfileobj(src, dst)
                    if basename == 'ffmpeg.exe':
                        ffmpeg_found = True
                    print(f"   [OK] Extracted: {basename}")

            if not ffmpeg_found:
                raise FileNotFoundError("ffmpeg.exe not found in downloaded archive")

        # Clean up zip
        os.remove(zip_path)

        print(f"   [OK] FFmpeg installed at: {FFMPEG_DIR}")
        print("=" * 50 + "\n")

        return FFMPEG_EXE

    except Exception as e:
        # Clean up on failure
        if os.path.exists(zip_path):
            os.remove(zip_path)

        print(f"\n   [ERROR] Auto-download failed: {e}")
        print(f"\n   Please install FFmpeg manually:")
        print(f"   1. Download from: https://www.gyan.dev/ffmpeg/builds/")
        print(f"   2. Extract ffmpeg.exe to: {FFMPEG_DIR}")
        print(f"   Or: winget install ffmpeg")
        print("=" * 50 + "\n")

        raise RuntimeError(
            f"FFmpeg is required but not found and auto-download failed: {e}"
        )


# ---------------------------------------------------------------------------
# Hardware encoder (NVENC) detection
# ---------------------------------------------------------------------------
_nvenc_available: bool | None = None  # cached across calls; None = not checked yet


def _check_nvenc_available(ffmpeg_bin: str) -> bool:
    """Real one-frame encode test — a compiled-in h264_nvenc can still fail at
    runtime with no NVIDIA GPU/driver present, so listing encoders isn't enough."""
    global _nvenc_available
    if _nvenc_available is not None:
        return _nvenc_available
    try:
        creationflags = subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0
        result = subprocess.run(
            [ffmpeg_bin, "-hide_banner", "-loglevel", "error",
             "-f", "lavfi", "-i", "nullsrc=s=256x256:d=0.1",
             "-c:v", "h264_nvenc", "-f", "null", "-"],
            capture_output=True, timeout=15, creationflags=creationflags,
        )
        _nvenc_available = (result.returncode == 0)
    except Exception:
        _nvenc_available = False
    print(f"[FFmpeg] NVENC hardware encoder available: {_nvenc_available}")
    return _nvenc_available


def video_encode_args(ffmpeg_bin: str, crf: int = 20) -> list[str]:
    """Video-encode args, preferring GPU NVENC (RTX cards) over CPU libx264.
    `crf` is on the libx264 quality scale; NVENC's -cq runs ~1 point hotter
    at the same visual quality, so it is nudged up by 1 when GPU is used."""
    if _check_nvenc_available(ffmpeg_bin):
        return ["-c:v", "h264_nvenc", "-preset", "p5", "-tune", "hq",
                "-rc", "vbr", "-cq", str(crf + 1), "-b:v", "0"]
    return ["-c:v", "libx264", "-preset", "medium", "-crf", str(crf)]
