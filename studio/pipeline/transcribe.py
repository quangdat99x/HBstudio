"""Transcribe an episode with the Cutter's whisper_worker.py (faster-whisper, CUDA) as a subprocess."""
from __future__ import annotations

import json
import logging
import os
import subprocess
import time
from pathlib import Path

from .. import config, db
from ..util import find_transcript, load_transcript, write_json

log = logging.getLogger("studio.transcribe")


def transcript_ready(video_path: Path) -> Path | None:
    t = find_transcript(video_path)
    if t and t.exists():
        try:
            if len(load_transcript(t)) > 20:
                return t
        except Exception:  # noqa: BLE001
            return None
    return None


def transcribe(video_path: Path, progress_cb=None, stop_flag=None) -> Path:
    """Run Whisper and write <stem>.transcript.json next to the video. Returns the transcript path."""
    model = db.get_setting("whisper_model")
    language = db.get_setting("whisper_language")
    work = config.WORK_DIR / "whisper"
    work.mkdir(parents=True, exist_ok=True)
    status_file = work / f"{video_path.stem[:40]}_{int(time.time())}.json"
    stop_file = Path(str(status_file) + ".stop")
    python = config.PY_CUTTER if config.PY_CUTTER.exists() else Path("python")
    ffmpeg = str(config.FFMPEG) if config.FFMPEG.exists() else "ffmpeg"
    cmd = [str(python), str(config.WHISPER_WORKER), str(video_path), model, language, str(status_file), ffmpeg]
    log.info("whisper: %s", " ".join(cmd[1:4]))
    env = dict(os.environ, PYTHONUTF8="1")
    proc = subprocess.Popen(cmd, cwd=str(config.CUTTER_DIR), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            env=env, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    last = None
    try:
        while True:
            if stop_flag and stop_flag():
                stop_file.write_text("stop", encoding="utf-8")
            status = _read_status(status_file)
            if status and status != last:
                last = status
                if progress_cb:
                    progress_cb(float(status.get("progress") or 0), status.get("message") or "")
            if status and status.get("status") in ("done", "error", "idle"):
                break
            if proc.poll() is not None:
                status = _read_status(status_file) or {}
                if status.get("status") not in ("done",):
                    raise RuntimeError(f"whisper worker exited ({proc.returncode}): {status.get('error') or status.get('message')}")
                break
            time.sleep(2)
    finally:
        if proc.poll() is None:
            try:
                proc.wait(timeout=30)
            except subprocess.TimeoutExpired:
                proc.kill()
    status = _read_status(status_file) or {}
    if status.get("status") != "done":
        raise RuntimeError(f"whisper failed: {status.get('error') or status.get('message') or status.get('status')}")
    segments = [{"start": float(s["start"]), "end": float(s["end"]), "text": str(s.get("text", "")).strip()}
                for s in status.get("segments", [])]
    if len(segments) < 20:
        raise RuntimeError(f"whisper produced only {len(segments)} segments")
    out = video_path.with_name(f"{video_path.stem}.transcript.json")
    write_json(out, {"video": video_path.name, "model": model, "segments": segments})
    try:
        status_file.unlink()
    except OSError:
        pass
    return out


def _read_status(path: Path) -> dict | None:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None
