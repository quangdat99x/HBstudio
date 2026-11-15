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
from ..util import discard_broken, ffmpeg_error_summary, ffprobe_duration, media_ok, now_iso
from . import tools

log = logging.getLogger("studio.zoom")


def _output_ready(out: Path, wait_sec: float = 30.0) -> bool:
    """A finished zoom's output, allowing a short wait: Podcast Zoom used to report 'complete' a moment before
    moving the rendered file into place (fixed in the tool too, the wait covers an instance still running old code)."""
    deadline = time.time() + wait_sec
    while True:
        if media_ok(out):
            return True
        if time.time() >= deadline:
            return False
        time.sleep(2)


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


def pending_segments(episode_id: str, segment_ids: set[int] | None = None) -> list[dict]:
    """Cut clips still without a good zoomed file; `segment_ids` limits it to the segments the user picked."""
    include_hooks = db.setting_bool("zoom_hooks")
    segs = db.rows("SELECT * FROM segments WHERE episode_id=? AND clip_path IS NOT NULL AND status NOT IN ('archived') ORDER BY rank",
                   (episode_id,))
    out = []
    for s in segs:
        if segment_ids is not None and s["id"] not in segment_ids:
            continue
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


def _zoom_window(base: str) -> int:
    """How many clips to keep in the Zoom tool at once: as many as it processes side by side (its CPU budget)."""
    try:
        return max(1, min(12, int(tools.get_json(f"{base}/api/queue-status", timeout=15).get("workers") or 1)))
    except Exception:  # noqa: BLE001
        return 1


def _announce_zoom(s: dict, finished: int, total: int) -> None:
    """🔔 "Zoom xong đoạn #3: <title>" as soon as each clip is rendered."""
    from .. import notify
    from .orchestrator import ep_label, ep_link
    what = "hook" if s.get("kind") == "hook" else "đoạn"
    notify.notify("done", f"Zoom xong {what} #{s.get('rank') or '?'}: {(s.get('title') or '')[:80]}",
                  f"{ep_label(s['episode_id'])} · {finished}/{total} clip của lượt này",
                  ep_link(s["episode_id"], s.get("parent_id") if s.get("kind") == "hook" else s["id"]))


def zoom_episode(episode_id: str, progress_cb=None, stop_flag=None, segment_ids: set[int] | None = None) -> dict:
    """Send the clips to the Zoom tool a few at a time (it renders that many in parallel) and collect them."""
    todo = pending_segments(episode_id, segment_ids)
    if not todo:
        return {"skipped": True}
    base = tools.ensure_tool("zoom")
    cfg = zoom_config()
    delete_original = db.setting_bool("delete_original_clip_after_zoom")
    window = _zoom_window(base)
    done, failed = 0, []
    waiting = list(todo)
    running: dict[str, dict] = {}                          # job id -> {"seg", "clip", "out", "progress"}

    def submit(s: dict) -> None:
        cur = db.row("SELECT status FROM segments WHERE id=?", (s["id"],))
        if not cur or cur["status"] == "archived":         # deleted on the episode page while this stage ran
            return
        clip = Path(s["clip_path"])
        out = clip.with_name(clip.stem + "_zoomed.mp4")
        job_id = _existing_job(base, clip.name)
        if not job_id:
            if not media_ok(clip, (s["end_sec"] or 0) - (s["start_sec"] or 0)):
                failed.append(f"{clip.name}: file clip hỏng (bị ghi dở khi cắt), bấm Chạy tiếp để cắt lại đoạn này")
                with db.tx() as c:                         # the cut stage sees it as missing and cuts it again
                    c.execute("UPDATE segments SET clip_path=NULL, updated_at=? WHERE id=?", (now_iso(), s["id"]))
                return
            if out.exists():                               # left by a render that stopped midway, no job owns it
                log.warning("half-rendered zoom output for %s: %s", s["id"], discard_broken(out))
            res = tools.post_json(f"{base}/api/enqueue-path", {"path": str(clip), "output_path": str(out), "config": cfg},
                                  timeout=60)
            if res.get("error"):
                failed.append(f"{clip.name}: {ffmpeg_error_summary(str(res['error']), 300)}")
                return
            job_id = res["job_id"]
        running[job_id] = {"seg": s, "clip": clip, "out": out, "progress": 0.0}

    def finish(job_id: str, st: dict) -> None:
        nonlocal done
        r = running.pop(job_id)
        clip, out, s = r["clip"], r["out"], r["seg"]
        if st.get("status") == "error" or not _output_ready(out):
            failed.append(f"{clip.name}: " + (ffmpeg_error_summary(str(st["error"]), 300) if st.get("error")
                                              else "Zoom báo xong nhưng file output thiếu hoặc hỏng"))
            return
        with db.tx() as c:
            c.execute("UPDATE segments SET clip_zoomed_path=?, status=CASE WHEN status IN ('selected','cut') THEN 'zoomed' ELSE status END, "
                      "updated_at=? WHERE id=?", (str(out), now_iso(), s["id"]))
        done += 1
        _announce_zoom(s, len(todo) - len(waiting) - len(running), len(todo))
        if delete_original:
            try:
                os.remove(clip)
            except OSError:
                pass

    while waiting or running:
        if stop_flag and stop_flag():
            raise RuntimeError("dừng theo yêu cầu (Zoom làm nốt các clip đang chạy)")
        while waiting and len(running) < window:
            submit(waiting.pop(0))
        for job_id in list(running):
            st = tools.get_json(f"{base}/api/status/{job_id}", timeout=30)
            running[job_id]["progress"] = (st.get("progress") or 0) / 100.0
            if st.get("status") in ("complete", "error"):
                finish(job_id, st)
        if progress_cb:
            finished = len(todo) - len(waiting) - len(running)
            partial = sum(r["progress"] for r in running.values())
            names = ", ".join(r["clip"].name[:30] for r in running.values())
            progress_cb((finished + partial) / len(todo) * 100.0,
                        f"zoom {finished}/{len(todo)} xong, đang chạy {len(running)} clip cùng lúc: {names}")
        if running:
            time.sleep(3)
    if failed:
        raise RuntimeError(f"zoom xong {done}/{len(todo)}, lỗi: " + "; ".join(failed)[:800])
    return {"zoomed": done}


def zoom_files(pairs: list[tuple[Path, Path]], progress_cb=None, stop_flag=None) -> list[str]:
    """Zoom loose files (input → output) a few at a time; used by Video tổng hợp for passages no highlight covers.

    Returns the error lines (empty = every output is a good file). An output that is already a good file is skipped.
    """
    todo = [(Path(a), Path(b)) for a, b in pairs if not media_ok(Path(b), ffprobe_duration(Path(a)))]
    if not todo:
        return []
    base = tools.ensure_tool("zoom")
    cfg = zoom_config()
    window = _zoom_window(base)
    failed: list[str] = []
    waiting = list(todo)
    running: dict[str, dict] = {}
    while waiting or running:
        if stop_flag and stop_flag():
            raise RuntimeError("dừng theo yêu cầu (Zoom làm nốt các clip đang chạy)")
        while waiting and len(running) < window:
            src, out = waiting.pop(0)
            job_id = _existing_job(base, src.name)
            if not job_id:
                if out.exists():
                    discard_broken(out)
                res = tools.post_json(f"{base}/api/enqueue-path", {"path": str(src), "output_path": str(out), "config": cfg},
                                      timeout=60)
                if res.get("error"):
                    failed.append(f"{src.name}: {ffmpeg_error_summary(str(res['error']), 300)}")
                    continue
                job_id = res["job_id"]
            running[job_id] = {"src": src, "out": out, "progress": 0.0}
        for job_id in list(running):
            st = tools.get_json(f"{base}/api/status/{job_id}", timeout=30)
            running[job_id]["progress"] = (st.get("progress") or 0) / 100.0
            if st.get("status") in ("complete", "error"):
                r = running.pop(job_id)
                if st.get("status") == "error" or not _output_ready(r["out"]):
                    failed.append(f"{r['src'].name}: " + (ffmpeg_error_summary(str(st["error"]), 300) if st.get("error")
                                                         else "Zoom báo xong nhưng file output thiếu hoặc hỏng"))
        if progress_cb:
            finished = len(todo) - len(waiting) - len(running)
            partial = sum(r["progress"] for r in running.values())
            progress_cb((finished + partial) / len(todo) * 100.0,
                        f"zoom {finished}/{len(todo)} đoạn xong, đang chạy {len(running)} cùng lúc")
        if running:
            time.sleep(3)
    return failed
