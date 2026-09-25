"""Stage: render zoomed versions with the Podcast Zoom tool (path mode, no thumbnail).

Zoomed files count as done only when ffprobe can open them: a render that was interrupted leaves a
half-written `_zoomed.mp4` behind. Input clips are checked before they are sent, so a clip that was cut only
halfway gets a clear message and is cut again by the next "Chạy tiếp" instead of failing inside the Zoom tool.
"""
from __future__ import annotations

import logging
import os
import time
from pathlib import Path

from .. import db
from ..util import discard_broken, ffmpeg_error_summary, media_ok, now_iso
from . import tools

log = logging.getLogger("studio.zoom")


def zoom_config() -> dict:
    return {
        "zoom_factor": db.setting_float("zoom_factor"),
        "smoothing_speed": db.setting_float("zoom_smoothing_speed"),
        "analysis_fps": db.setting_int("zoom_analysis_fps"),
        "max_faces": db.setting_int("zoom_max_faces"),
        "min_switch_duration": db.setting_float("zoom_min_switch_duration"),
        "mar_threshold": db.setting_float("zoom_mar_threshold"),
        "generate_thumbnail": False,
    }


def pending_segments(episode_id: str) -> list[dict]:
    include_hooks = db.setting_bool("zoom_hooks")
    segs = db.rows("SELECT * FROM segments WHERE episode_id=? AND clip_path IS NOT NULL AND status NOT IN ('archived') ORDER BY rank",
                   (episode_id,))
    out = []
    for s in segs:
        if s["kind"] == "hook" and not include_hooks:
            continue
        clip = Path(s["clip_path"])
        if not clip.exists():
            continue
        expected = (s["end_sec"] or 0) - (s["start_sec"] or 0)
        zoomed = clip.with_name(clip.stem + "_zoomed.mp4")
        known = Path(s["clip_zoomed_path"]) if s["clip_zoomed_path"] else None
        done = known if known and media_ok(known, expected) else zoomed if media_ok(zoomed, expected) else None
        if done:
            if s["clip_zoomed_path"] != str(done):
                with db.tx() as c:
                    c.execute("UPDATE segments SET clip_zoomed_path=?, status=CASE WHEN status IN ('selected','cut') THEN 'zoomed' ELSE status END, "
                              "updated_at=? WHERE id=?", (str(done), now_iso(), s["id"]))
            continue
        out.append(s)                                      # no zoomed file, or a half-rendered one
    return out


def _existing_job(base: str, clip_name: str) -> str | None:
    """A job for this clip that the Zoom tool is still running from before a Studio restart."""
    try:
        jobs = tools.get_json(f"{base}/api/queue-status", timeout=15).get("jobs") or []
    except Exception:  # noqa: BLE001
        return None
    for j in reversed(jobs):
        if j.get("original_filename") == clip_name and j.get("status") in ("queued", "processing"):
            return j.get("job_id")
    return None


def zoom_episode(episode_id: str, progress_cb=None, stop_flag=None) -> dict:
    todo = pending_segments(episode_id)
    if not todo:
        return {"skipped": True}
    base = tools.ensure_tool("zoom")
    cfg = zoom_config()
    delete_original = db.setting_bool("delete_original_clip_after_zoom")
    done, failed = 0, []
    for n, s in enumerate(todo, 1):
        if stop_flag and stop_flag():
            raise RuntimeError("dừng theo yêu cầu")
        cur = db.row("SELECT status FROM segments WHERE id=?", (s["id"],))
        if not cur or cur["status"] == "archived":         # deleted on the episode page while this stage ran
            continue
        clip = Path(s["clip_path"])
        out = clip.with_name(clip.stem + "_zoomed.mp4")
        job_id = _existing_job(base, clip.name)
        if not job_id:
            if not media_ok(clip, (s["end_sec"] or 0) - (s["start_sec"] or 0)):
                failed.append(f"{clip.name}: file clip hỏng (bị ghi dở khi cắt), bấm Chạy tiếp để cắt lại đoạn này")
                with db.tx() as c:                         # the cut stage sees it as missing and cuts it again
                    c.execute("UPDATE segments SET clip_path=NULL, updated_at=? WHERE id=?", (now_iso(), s["id"]))
                continue
            if out.exists():                               # left by a render that stopped midway, no job owns it
                log.warning("half-rendered zoom output for %s: %s", s["id"], discard_broken(out))
            res = tools.post_json(f"{base}/api/enqueue-path", {"path": str(clip), "output_path": str(out), "config": cfg},
                                  timeout=60)
            if res.get("error"):
                failed.append(f"{clip.name}: {ffmpeg_error_summary(str(res['error']), 300)}")
                continue
            job_id = res["job_id"]
        while True:
            if stop_flag and stop_flag():
                raise RuntimeError("dừng theo yêu cầu (Zoom làm nốt clip đang chạy)")
            st = tools.get_json(f"{base}/api/status/{job_id}", timeout=30)
            if progress_cb:
                progress_cb((n - 1 + (st.get("progress") or 0) / 100.0) / len(todo) * 100.0,
                            f"zoom {n}/{len(todo)} {clip.name[:50]}: {st.get('phase') or ''} {int(st.get('progress') or 0)}%")
            if st.get("status") in ("complete", "error"):
                break
            time.sleep(3)
        if st.get("status") == "error" or not media_ok(out):
            failed.append(f"{clip.name}: " + (ffmpeg_error_summary(str(st["error"]), 300) if st.get("error")
                                              else "Zoom báo xong nhưng file output thiếu hoặc hỏng"))
            continue
        with db.tx() as c:
            c.execute("UPDATE segments SET clip_zoomed_path=?, status=CASE WHEN status IN ('selected','cut') THEN 'zoomed' ELSE status END, "
                      "updated_at=? WHERE id=?", (str(out), now_iso(), s["id"]))
        done += 1
        if delete_original:
            try:
                os.remove(clip)
            except OSError:
                pass
    if failed:
        raise RuntimeError(f"zoom xong {done}/{len(todo)}, lỗi: " + "; ".join(failed)[:800])
    return {"zoomed": done}
