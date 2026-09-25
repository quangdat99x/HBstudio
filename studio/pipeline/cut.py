"""Stage: cut clips with Video Cutter's headless endpoint (same ffmpeg/NVENC path as the manual UI, no sidecars).

The Cutter runs in its own process, so a job it accepted keeps going even if Studio restarts. Before sending
work we therefore wait until the Cutter is idle and recompute what is still missing: clips produced by the
earlier job are picked up from disk instead of being cut twice.

A clip on disk only counts when ffprobe can open it. A clip whose writing was interrupted (Cutter stopped or
killed mid-clip) keeps a plausible size but has no moov atom; before this check such a file was taken as done
and the zoom step failed on it at every "Chạy tiếp" (JRE-2545 #35, 2026-09-25).
"""
from __future__ import annotations

import logging
import time
from pathlib import Path

from .. import db
from ..util import clip_filename, cutter_safe_stem, discard_broken, ffmpeg_error_summary, media_ok, now_iso
from . import tools

log = logging.getLogger("studio.cut")
STOPPED = "dừng theo yêu cầu"


def episode_clip_folder(ep: dict) -> Path:
    if ep.get("clip_folder") and Path(ep["clip_folder"]).exists():
        return Path(ep["clip_folder"])
    root = Path(db.get_setting("media_root"))
    return root / cutter_safe_stem(Path(ep["video_path"]).stem)


def pending_segments(episode_id: str, folder: Path, repair: bool = False, repaired: list | None = None) -> list[dict]:
    """Segments (highlights + hooks) that still need a clip; complete clips already on disk get linked.

    A broken clip makes its segment pending. Only with repair=True, i.e. once the Cutter is idle and nothing is
    being written, the broken file goes to the Recycle Bin (its name is added to `repaired`) so it gets cut again.
    """
    segs = db.rows("SELECT * FROM segments WHERE episode_id=? AND start_sec IS NOT NULL AND rank IS NOT NULL "
                   "AND status NOT IN ('archived') ORDER BY rank", (episode_id,))
    out = []
    for s in segs:
        if s["clip_zoomed_path"] and media_ok(Path(s["clip_zoomed_path"])):
            continue                                       # zoomed already (original may be gone by setting)
        expected = folder / clip_filename(s["rank"], s["title"])
        clip = Path(s["clip_path"]) if s["clip_path"] and Path(s["clip_path"]).exists() else expected
        if clip.exists():
            if media_ok(clip, (s["end_sec"] or 0) - (s["start_sec"] or 0)):
                if s["clip_path"] != str(clip):
                    with db.tx() as c:
                        c.execute("UPDATE segments SET clip_path=?, status=CASE WHEN status='selected' THEN 'cut' ELSE status END, "
                                  "updated_at=? WHERE id=?", (str(clip), now_iso(), s["id"]))
                continue
            if repair:
                note = discard_broken(clip)
                log.warning("broken clip for %s #%s: %s", episode_id, s["rank"], note)
                if repaired is not None:
                    repaired.append(note)
                with db.tx() as c:
                    c.execute("UPDATE segments SET clip_path=NULL, updated_at=? WHERE id=?", (now_iso(), s["id"]))
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
    if not pending_segments(episode_id, folder):              # read-only: the Cutter may still be writing a clip
        return {"skipped": True, "folder": str(folder)}

    base = tools.ensure_tool("cutter")
    todo: list[dict] = []
    repaired: list[str] = []
    for attempt in range(4):
        wait_cutter_idle(base, progress_cb, stop_flag)
        todo = pending_segments(episode_id, folder, repair=True, repaired=repaired)   # earlier job may have made some
        if repaired and progress_cb:
            progress_cb(None, f"{len(repaired)} clip hỏng (ghi dở) đã bỏ vào Thùng rác, cắt lại: " + "; ".join(repaired)[:300])
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
        raise RuntimeError("một số đoạn cắt lỗi: " + "; ".join(
            f"#{e.get('index')}: {ffmpeg_error_summary(str(e.get('error') or ''), 250)}" for e in errors)[:800])
    return {"folder": str(folder), "cut": len(done_files),
            **({"repaired": repaired, "summary": f"cắt {len(done_files)} clip, trong đó {len(repaired)} clip hỏng cắt lại"}
               if repaired else {})}
