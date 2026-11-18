"""Intake: watch the Full folder (<media_root>\\Full) for new episode videos (any show with a podcast profile),
or download a YouTube URL through the Downloader tool."""
from __future__ import annotations

import logging
import re
import threading
import time
from pathlib import Path

from .. import config, db, paths
from ..util import find_transcript, parse_episode_name
from . import tools

log = logging.getLogger("studio.intake")
_RE_YTDLP_PART = re.compile(r"\.f\d{2,4}$")


class FolderWatcher(threading.Thread):
    """Polls the media root (simple, robust on Windows) and reports files once their size is stable."""

    def __init__(self, on_new_file, interval: int = 15, on_copied=None):
        super().__init__(name="studio-watcher", daemon=True)
        self.on_new_file = on_new_file
        self.on_copied = on_copied          # video that arrives with its transcript: index only (portable.py)
        self.interval = interval
        self._seen: set[str] = set()
        self._sizes: dict[str, tuple[int, float]] = {}
        self._stop = threading.Event()
        self.prime()

    def prime(self) -> None:
        """Mark everything already present as seen so only new files trigger the pipeline."""
        if paths.full_dir().exists():
            paths.ensure()                          # Full\<show>\ folders exist before the user looks for them
            for p in paths.full_videos():
                self._seen.add(str(p))

    def stop(self) -> None:
        self._stop.set()

    def run(self) -> None:
        while not self._stop.is_set():
            try:
                if db.setting_bool("watch_enabled"):
                    self.scan_once()
            except Exception as e:  # noqa: BLE001
                log.warning("watcher error: %s", e)
            self._stop.wait(self.interval)

    def scan_once(self) -> None:
        if not paths.full_dir().exists():
            return
        stable_for = db.setting_int("file_stable_seconds") or 30
        now = time.time()
        for p in paths.full_videos():                   # Full\ and every Full\<show>\ folder
            if _RE_YTDLP_PART.search(p.stem):          # yt-dlp stream file before merge (video-only / audio-only)
                continue
            key = str(p)
            if key in self._seen:
                continue
            if not paths.show_of_path(p) and not parse_episode_name(p.name):
                continue
            if (p.with_suffix(p.suffix + ".part")).exists():
                continue
            try:
                size = p.stat().st_size
            except OSError:
                continue
            prev = self._sizes.get(key)
            if prev is None or prev[0] != size:
                self._sizes[key] = (size, now)
                continue
            if now - prev[1] >= stable_for and size > 10 * 1024 * 1024:
                self._seen.add(key)
                self._sizes.pop(key, None)
                log.info("new video detected: %s", p.name)
                try:
                    if self.on_copied and find_transcript(p):
                        self.on_copied(p)
                    else:
                        self.on_new_file(p)
                except Exception as e:  # noqa: BLE001
                    log.exception("intake failed for %s: %s", p, e)


def download_url(url: str, progress_cb=None, timeout: int = 6 * 3600, podcast_id: str | None = None) -> Path:
    """Download through the Downloader tool (into Full\\<show>\\ when the show is known) and return the file path."""
    base = tools.ensure_tool("downloader")
    root = next((d for d, pid in paths.full_show_dirs() if pid == (podcast_id or "").upper()), paths.full_dir())
    root.mkdir(parents=True, exist_ok=True)
    res = tools.post_json(f"{base}/api/download", {"urls": [{"url": url, "title": ""}], "download_dir": str(root),
                                                  "max_resolution": "1080p"}, timeout=60)
    ids = res.get("task_ids") or []
    if not ids:
        raise RuntimeError(f"Downloader không nhận link: {res.get('error') or res}")
    task_id = ids[0]
    deadline = time.time() + timeout
    while time.time() < deadline:
        tasks = tools.get_json(f"{base}/api/tasks", timeout=30).get("tasks") or {}
        t = tasks.get(task_id) or {}
        if progress_cb:
            progress_cb(float(t.get("progress") or 0), f"tải {t.get('progress') or 0}% {t.get('speed') or ''}")
        if t.get("status") == "completed":
            fname = t.get("filename")
            if not fname:
                break
            return root / fname
        if t.get("status") == "error":
            raise RuntimeError(f"tải lỗi: {t.get('error')}")
        time.sleep(5)
    raise RuntimeError("tải quá thời gian hoặc không rõ tên file")
