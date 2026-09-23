"""Stage: cut clips with Video Cutter's headless endpoint (same ffmpeg/NVENC path as the manual UI, no sidecars).

The Cutter runs in its own process, so a job it accepted keeps going even if Studio restarts. Before sending
work we therefore wait until the Cutter is idle and recompute what is still missing: clips produced by the
earlier job are picked up from disk instead of being cut twice.
"""
from __future__ import annotations

import logging
import time
from pathlib import Path

from .. import db
from ..util import clip_filename, cutter_safe_stem, now_iso
from . import tools

log = logging.getLogger("studio.cut")
STOPPED = "dừng theo yêu cầu"


def episode_clip_folder(ep: dict) -> Path:
    if ep.get("clip_folder") and Path(ep["clip_folder"]).exists():
        return Path(ep["clip_folder"])
    root = Path(db.get_setting("media_root"))
    return root / cutter_safe_stem(Path(ep["video_path"]).stem)


def pending_segments(episode_id: str, folder: Path) -> list[dict]:
    """Segments (highlights + hooks) that do not have a clip file yet; clips already on disk get linked."""
    segs = db.rows("SELECT * FROM segments WHERE episode_id=? AND start_sec IS NOT NULL AND rank IS NOT NULL "
                   "AND status NOT IN ('archived') ORDER BY rank", (episode_id,))
    out = []
    for s in segs:
        expected = folder / clip_filename(s["rank"], s["title"])
        if s["clip_path"] and Path(s["clip_path"]).exists():
            continue
        if expected.exists() and expected.stat().st_size > 1024:
            with db.tx() as c:
                c.execute("UPDATE segments SET clip_path=?, status=CASE WHEN status='selected' THEN 'cut' ELSE status END, "
                          "updated_at=? WHERE id=?", (str(expected), now_iso(), s["id"]))
            continue
        out.append(s)
    return out


def wait_cutter_idle(base: str, progress_cb=None, stop_flag=None, timeout: int = 6 * 3600) -> dict:
    started = time.time()
    while True:
        st = tools.get_json(f"{base}/api/cut/status", timeout=30)
        if st.get("status") != "running":
            return st
        if stop_flag and stop_flag():
            raise RuntimeError(STOPPED)
        if progress_cb:
            progress_cb(None, f"chờ Cutter làm xong việc đang dở ({st.get('current_segment') or 0}/"
                              f"{st.get('total_segments') or '?'}: {st.get('segment_title') or ''})")
        if time.time() - started > timeout:
            raise RuntimeError("Cutter bận quá lâu, hãy mở Video Cutter kiểm tra")
        time.sleep(5)


def cut_episode(episode_id: str, progress_cb=None, stop_flag=None) -> dict:
    ep = db.row("SELECT * FROM episodes WHERE id=?", (episode_id,))
    if not ep or not ep.get("video_path") or not Path(ep["video_path"]).exists():
        raise RuntimeError("không tìm thấy file video của tập")
    folder = episode_clip_folder(ep)
    folder.mkdir(parents=True, exist_ok=True)
    with db.tx() as c:
        c.execute("UPDATE episodes SET clip_folder=?, updated_at=? WHERE id=?", (str(folder), now_iso(), episode_id))
    if not pending_segments(episode_id, folder):
        return {"skipped": True, "folder": str(folder)}

    base = tools.ensure_tool("cutter")
    todo: list[dict] = []
    for attempt in range(4):
        wait_cutter_idle(base, progress_cb, stop_flag)
        todo = pending_segments(episode_id, folder)          # an earlier job may have produced some of them
        if not todo:
            return {"skipped": True, "folder": str(folder)}
        payload = {
            "video_path": ep["video_path"], "output_dir": str(folder), "write_sidecars": False,
            "segments": [{"index": s["rank"], "start": s["start_hms"], "end": s["end_hms"], "title": s["title"]}
                         for s in todo],
        }
        res = tools.post_json(f"{base}/api/cut-headless", payload, timeout=60)
        if res.get("_status") == 409:                        # Cutter picked up other work meanwhile
            time.sleep(5)
            continue
        if res.get("error"):
            raise RuntimeError(f"Cutter từ chối: {res['error']}")
        break
    else:
        raise RuntimeError("Cutter vẫn bận sau nhiều lần thử")

    total = len(todo)
    done_files: dict[int, str] = {}
    while True:
        if stop_flag and stop_flag():
            raise RuntimeError(STOPPED + " (Cutter vẫn cắt nốt các đoạn đã gửi, lần chạy sau sẽ dùng lại)")
        st = tools.get_json(f"{base}/api/cut/status", timeout=30)
        cur = st.get("current_segment") or 0
        if progress_cb:
            progress_cb(min(99, float(st.get("progress") or 0)),
                        f"cắt {cur}/{total}: {st.get('segment_title') or ''} {st.get('segment_progress') or ''}% {st.get('eta') or ''}")
        for r in st.get("results") or []:
            if r.get("status") == "done" and r.get("file"):
                done_files[int(r.get("index") or 0)] = r["file"]
        if st.get("status") in ("done", "error", "idle"):
            if st.get("status") == "error":
                raise RuntimeError(f"Cutter lỗi: {st.get('error')}")
            break
        time.sleep(2)
    errors = [r for r in st.get("results") or [] if r.get("status") == "error"]
    with db.tx() as c:
        for s in todo:
            f = done_files.get(s["rank"])
            if f and Path(f).exists():
                c.execute("UPDATE segments SET clip_path=?, status=CASE WHEN status IN ('selected','cut') THEN 'cut' ELSE status END, "
                          "updated_at=? WHERE id=?", (f, now_iso(), s["id"]))
    if errors:
        raise RuntimeError("một số đoạn cắt lỗi: " + "; ".join(f"#{e.get('index')}: {e.get('error')}" for e in errors)[:800])
    return {"folder": str(folder), "cut": len(done_files)}
