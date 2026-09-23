"""Orchestrator: one worker thread runs each episode through the stage state machine.

Stages: download -> transcribe -> select -> [review] -> cut -> zoom -> index -> ready.
Every stage is skipped when its output already exists, so backfilled episodes and restarts are cheap.
"""
from __future__ import annotations

import logging
import threading
import time
import traceback
from collections import deque
from pathlib import Path

from .. import config, db, ingest, search
from ..util import ffprobe_duration, find_transcript, now_iso, parse_episode_name
from . import cut as cut_stage
from . import intake, select_ai, transcribe, zoom as zoom_stage

log = logging.getLogger("studio.orchestrator")
STAGES = ["transcribe", "select", "cut", "zoom", "index"]


class Orchestrator:
    def __init__(self):
        self.queue: deque[tuple[str, dict]] = deque()
        self.cv = threading.Condition()
        self.gpu_lock = threading.Lock()
        self.current: str | None = None
        self.stop_requested: set[str] = set()
        self.thread = threading.Thread(target=self._loop, name="studio-worker", daemon=True)
        self.watcher = intake.FolderWatcher(self.intake_file)
        self._downloads: dict[str, threading.Thread] = {}

    # ------------------------------------------------------------ lifecycle
    def start(self) -> None:
        self._resume()
        self.thread.start()
        self.watcher.start()
        log.info("orchestrator started")

    def _resume(self) -> None:
        """Episodes left mid-pipeline by a previous run continue where they were."""
        active = ("downloading", "transcribing", "selecting", "cutting", "zooming", "indexing")
        for r in db.rows("SELECT id FROM episodes WHERE stage IN (%s)" % ",".join("?" * len(active)), active):
            self.queue.append((r["id"], {}))
        with db.tx() as c:
            c.execute("UPDATE jobs SET status='failed', error='studio restarted', finished_at=? WHERE status='running'", (now_iso(),))

    # ------------------------------------------------------------ public API
    def enqueue_episode(self, episode_id: str, from_stage: str | None = None, force: bool = False) -> dict:
        ep = db.row("SELECT id, stage FROM episodes WHERE id=?", (episode_id,))
        if not ep:
            return {"error": f"không có tập {episode_id}"}
        if any(e == episode_id for e, _ in self.queue) or self.current == episode_id:
            return {"message": f"{episode_id} đã ở trong hàng đợi"}
        opts = {"force": force, "from_stage": from_stage}
        with self.cv:
            self.queue.append((episode_id, opts))
            self.cv.notify()
        with db.tx() as c:
            c.execute("UPDATE episodes SET stage_error=NULL, updated_at=? WHERE id=?", (now_iso(), episode_id))
        return {"message": f"đã xếp {episode_id} vào hàng đợi", "episode_id": episode_id, "queue": len(self.queue)}

    def approve(self, episode_id: str) -> dict:
        ep = db.row("SELECT stage FROM episodes WHERE id=?", (episode_id,))
        if not ep:
            return {"error": "không có tập"}
        if ep["stage"] != "reviewing":
            return {"error": f"tập đang ở stage {ep['stage']}, không phải reviewing"}
        with db.tx() as c:
            c.execute("UPDATE episodes SET stage='selected', updated_at=? WHERE id=?", (now_iso(), episode_id))
        return self.enqueue_episode(episode_id, from_stage="cut")

    def intake_file(self, path: Path) -> dict:
        path = Path(path)
        info = parse_episode_name(path.name)
        if not info:
            return {"error": f"tên file không phải tập JRE: {path.name}"}
        if not path.exists():
            return {"error": f"không thấy file: {path}"}
        transcript = find_transcript(path)
        with db.tx() as c:
            ingest.upsert_episode(c, {"id": info["episode_id"], "podcast_id": info["podcast_id"], "number": info["number"],
                                      "guest": info["guest"], "source_video": path.name, "video_path": str(path),
                                      "transcript_path": str(transcript) if transcript else None,
                                      "duration_sec": ffprobe_duration(path) or None})
        return self.enqueue_episode(info["episode_id"])

    def intake_url(self, url: str) -> dict:
        key = url.strip()
        if key in self._downloads and self._downloads[key].is_alive():
            return {"message": "link này đang tải"}
        job_id = self._job("download:" + key[-40:], "download", "running")

        def _run():
            try:
                path = intake.download_url(key, progress_cb=lambda p, m: self._job_update(job_id, p, m))
                self.watcher._seen.add(str(path))
                res = self.intake_file(path)
                if res.get("error"):
                    self._job_update(job_id, 100, None, status="failed",
                                     error=f"đã tải {path.name} nhưng không đưa vào pipeline: {res['error']}")
                else:
                    self._job_update(job_id, 100, f"đã tải {path.name} → {res.get('episode_id')}", status="done")
            except Exception as e:  # noqa: BLE001
                log.exception("download failed")
                self._job_update(job_id, None, None, status="failed", error=str(e))

        t = threading.Thread(target=_run, name="studio-download", daemon=True)
        self._downloads[key] = t
        t.start()
        return {"message": "đang tải, tập sẽ tự vào pipeline khi tải xong"}

    def request_stop(self, episode_id: str) -> dict:
        """Drop a queued episode, or ask the running one to stop at the next safe point."""
        removed = False
        with self.cv:
            for item in list(self.queue):
                if item[0] == episode_id:
                    self.queue.remove(item)
                    removed = True
        if self.current == episode_id:
            self.stop_requested.add(episode_id)
            return {"message": f"đang dừng {episode_id}, bước hiện tại dừng ở điểm an toàn gần nhất"}
        if removed:
            self._set_stage(episode_id, "failed:stopped", "dừng theo yêu cầu")
            return {"message": f"đã bỏ {episode_id} khỏi hàng đợi"}
        return {"message": f"{episode_id} không chạy"}

    def is_busy(self) -> bool:
        return self.current is not None or bool(self.queue)

    def status(self) -> dict:
        return {"current": self.current, "queue": [e for e, _ in self.queue]}

    # ------------------------------------------------------------ worker
    def _loop(self) -> None:
        while True:
            with self.cv:
                while not self.queue:
                    self.cv.wait(timeout=30)
                episode_id, opts = self.queue.popleft()
            self.current = episode_id
            try:
                self.run_episode(episode_id, **opts)
            except Exception as e:  # noqa: BLE001
                log.exception("pipeline crashed for %s", episode_id)
                self._set_stage(episode_id, "failed:unknown", str(e))
            finally:
                self.current = None
                self.stop_requested.discard(episode_id)

    def run_episode(self, episode_id: str, force: bool = False, from_stage: str | None = None) -> None:
        ep = db.row("SELECT * FROM episodes WHERE id=?", (episode_id,))
        if not ep:
            return
        log.info("=== pipeline %s (force=%s, from=%s) ===", episode_id, force, from_stage)
        start_idx = STAGES.index(from_stage) if from_stage in STAGES else 0
        for stage in STAGES[start_idx:]:
            if episode_id in self.stop_requested:
                self._set_stage(episode_id, f"failed:{stage}", "dừng theo yêu cầu")
                return
            ep = db.row("SELECT * FROM episodes WHERE id=?", (episode_id,))
            job_id = self._job(episode_id, stage, "running")
            self._set_stage(episode_id, {"transcribe": "transcribing", "select": "selecting", "cut": "cutting",
                                         "zoom": "zooming", "index": "indexing"}[stage])
            try:
                result = getattr(self, f"_stage_{stage}")(ep, job_id, force and stage == "select")
            except Exception as e:  # noqa: BLE001
                log.error("stage %s failed for %s: %s\n%s", stage, episode_id, e, traceback.format_exc())
                self._job_update(job_id, None, None, status="failed", error=str(e)[:2000])
                self._set_stage(episode_id, f"failed:{stage}", str(e)[:1000])
                return
            if result == "review":
                self._job_update(job_id, 100, "chờ duyệt cutlist", status="done")
                self._set_stage(episode_id, "reviewing")
                return
            skipped = isinstance(result, dict) and result.get("skipped")
            summary = result.get("summary") if isinstance(result, dict) else None
            self._job_update(job_id, 100, "skip" if skipped else (summary or "xong"),
                             status="skipped" if skipped else "done")
        self._set_stage(episode_id, "ready")
        log.info("=== %s ready ===", episode_id)

    # ------------------------------------------------------------ stages
    def _stage_transcribe(self, ep: dict, job_id: int, force: bool):
        video = Path(ep["video_path"]) if ep.get("video_path") else None
        if not video or not video.exists():
            raise RuntimeError("không có file video (video_path trống hoặc đã bị xoá)")
        ready = transcribe.transcript_ready(video)
        if not ready:
            with self.gpu_lock:
                ready = transcribe.transcribe(video, progress_cb=lambda p, m: self._job_update(job_id, p, m),
                                              stop_flag=lambda: ep["id"] in self.stop_requested)
            skipped = False
        else:
            skipped = True
        with db.tx() as c:
            c.execute("UPDATE episodes SET transcript_path=?, duration_sec=COALESCE(duration_sec, ?), updated_at=? WHERE id=?",
                      (str(ready), ffprobe_duration(video) or None, now_iso(), ep["id"]))
        ingest.load_episode_transcript(ep["id"], force=not skipped)
        return {"skipped": skipped, "transcript": str(ready)}

    def _stage_select(self, ep: dict, job_id: int, force: bool):
        res = select_ai.select_episode(ep["id"], progress_cb=lambda p, m: self._job_update(job_id, p, m), force=force,
                                       stop_flag=lambda: ep["id"] in self.stop_requested)
        search.rebuild_index()
        if db.setting_bool("review_gate") and not res.get("skipped"):
            return "review"
        return res

    def _stage_cut(self, ep: dict, job_id: int, force: bool):
        return cut_stage.cut_episode(ep["id"], progress_cb=lambda p, m: self._job_update(job_id, p, m),
                                     stop_flag=lambda: ep["id"] in self.stop_requested)

    def _stage_zoom(self, ep: dict, job_id: int, force: bool):
        with self.gpu_lock:
            return zoom_stage.zoom_episode(ep["id"], progress_cb=lambda p, m: self._job_update(job_id, p, m),
                                           stop_flag=lambda: ep["id"] in self.stop_requested)

    def _stage_index(self, ep: dict, job_id: int, force: bool):
        ep = db.row("SELECT * FROM episodes WHERE id=?", (ep["id"],))
        if ep.get("clip_folder") and Path(ep["clip_folder"]).exists():
            ingest.scan_clip_folder(Path(ep["clip_folder"]), episode_id=ep["id"])
        ingest.fill_segment_transcripts(ep["id"])
        search.rebuild_index()
        free = 0.0
        try:
            import shutil
            free = shutil.disk_usage(db.get_setting("media_root")).free / 1e9
        except Exception:  # noqa: BLE001
            pass
        if free and free < db.setting_float("disk_warn_gb"):
            self._job_update(job_id, 100, f"CẢNH BÁO: ổ đĩa còn {free:.0f} GB")
        return {"indexed": True, "free_gb": round(free, 1)}

    # ------------------------------------------------------------ bookkeeping
    def _set_stage(self, episode_id: str, stage: str, error: str | None = None) -> None:
        with db.tx() as c:
            c.execute("UPDATE episodes SET stage=?, stage_error=?, updated_at=? WHERE id=?",
                      (stage, error, now_iso(), episode_id))

    def _job(self, episode_id: str, stage: str, status: str) -> int:
        with db.tx() as c:
            c.execute("INSERT INTO jobs(episode_id, stage, status, progress, message, attempts, started_at) VALUES(?,?,?,?,?,?,?)",
                      (episode_id, stage, status, 0, "", 1, now_iso()))
            return c.execute("SELECT last_insert_rowid()").fetchone()[0]

    def _job_update(self, job_id: int, progress, message, status: str | None = None, error: str | None = None) -> None:
        sets, params = [], []
        if progress is not None:
            sets.append("progress=?"); params.append(float(progress))
        if message is not None:
            sets.append("message=?"); params.append(str(message)[:500])
        if status:
            sets.append("status=?"); params.append(status)
            sets.append("finished_at=?"); params.append(now_iso())
        if error:
            sets.append("error=?"); params.append(error[:2000])
        if not sets:
            return
        with db.tx() as c:
            c.execute(f"UPDATE jobs SET {', '.join(sets)} WHERE id=?", params + [job_id])
