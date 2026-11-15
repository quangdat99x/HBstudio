"""Orchestrator: one worker thread runs each episode through the stage state machine.

Stages: download -> transcribe -> select -> [review] -> cut -> index -> ready.
An episode of a `support` show (the supplementary podcast library, studio/podcasts.py) stops after transcribe: its
transcript is what the compilations of the main shows read.
Zoom is not part of the automatic run (unless the `auto_zoom` setting is on): the user picks the segments to
zoom, or "Zoom tất cả", on the episode page and they go through the GPU lane (`enqueue_zoom`).
Every stage is skipped when its output already exists, so backfilled episodes and restarts are cheap.

Lanes: each stage runs in the lane of the resource it needs, one worker thread per lane, so while episode 1 waits
for Claude in `select`, episode 2 already transcribes on the GPU. An episode runs one step at a time (a lane skips
an episode that is busy in another lane). A stage whose output already exists goes to the `light` lane, so a
re-downloaded episode does not wait behind another episode's Whisper run just to skip its own.
"""
from __future__ import annotations

import json
import logging
import threading
import time
import traceback
from collections import deque
from pathlib import Path

from .. import config, db, ingest, notify, paths, podcasts, search
from ..util import ffprobe_duration, find_transcript, now_iso, parse_episode_name
from . import cut as cut_stage
from . import intake, select_ai, transcribe, zoom as zoom_stage

log = logging.getLogger("studio.orchestrator")
STAGES = ["transcribe", "select", "cut", "zoom", "index"]
STAGE_VI = {"transcribe": "Transcript", "select": "Chọn nội dung", "cut": "Cắt clip", "zoom": "Zoom", "index": "Lập chỉ mục"}
STAGE_RUNNING = {"transcribe": "transcribing", "select": "selecting", "cut": "cutting", "zoom": "zooming", "index": "indexing"}
LANES = ("gpu", "claude", "cut", "light")
LANE_VI = {"gpu": "GPU", "claude": "Claude", "cut": "Cắt clip", "light": "việc nhẹ"}
STAGE_LANE = {"transcribe": "gpu", "select": "claude", "cut": "cut", "zoom": "gpu", "index": "light"}


def ep_label(episode_id: str) -> str:
    """"JRE-2558 · Guest" for notifications."""
    ep = db.row("SELECT guest FROM episodes WHERE id=?", (episode_id,)) or {}
    return f"{episode_id} · {ep['guest']}" if ep.get("guest") else episode_id


def ep_link(episode_id: str, seg_id: int | None = None) -> str:
    return f"/episodes/{episode_id}" + (f"#seg-{seg_id}" if seg_id else "")


def _highlights(episode_id: str) -> int:
    return db.scalar("SELECT COUNT(*) FROM segments WHERE episode_id=? AND kind='highlight' AND status!='archived'",
                     (episode_id,)) or 0


def _stage_note(episode_id: str, stage: str, result) -> None:
    """🔔 for a stage that did real work (skipped stages, zoom (zoom.py announces every clip) and index stay quiet)."""
    if stage in ("index", "zoom") or (isinstance(result, dict) and result.get("skipped")):
        return
    n = _highlights(episode_id)
    body = {"transcribe": "đã có transcript, chuyển sang chọn nội dung",
            "select": f"Claude đã chọn {n} đoạn highlight",
            "cut": f"đã cắt xong clip của {n} đoạn"}.get(stage, "xong")
    notify.notify("done", f"{STAGE_VI.get(stage, stage)} xong: {ep_label(episode_id)}", body, ep_link(episode_id))


def _stages(episode_id: str | None = None) -> list[str]:
    if episode_id:
        prof = podcasts.for_episode(episode_id)
        # a support show only gets a transcript, unless it names its own selection skill (then it runs like a main show)
        if podcasts.is_support(prof) and not (prof.get("select_skill") or "").strip():
            return ["transcribe"]
    return STAGES if db.setting_bool("auto_zoom") else [s for s in STAGES if s != "zoom"]


def _zoom_ids(raw: str) -> list[int] | None:
    """episodes.pending_zoom: "all" = every clip of the episode, else a JSON list of segment ids."""
    return None if raw == "all" else json.loads(raw)


def _item_step(item: dict | None) -> str | None:
    if not item:
        return None
    return "zoom" if item["kind"] == "zoom" else item["stages"][item["idx"]]


def _cutlist_reusable(episode_id: str) -> bool:
    """Same test as select_ai.select_episode: a current-format cutlist is reused without calling Claude."""
    p = paths.cutlist_path(episode_id)
    if not p.exists():
        return False
    try:
        return json.loads(p.read_text(encoding="utf-8")).get("cutlist_layout") == "flat_hooks"
    except Exception:  # noqa: BLE001
        return False


class Orchestrator:
    def __init__(self):
        # A work item is one episode's pipeline run ({"kind": "pipe", "stages", "idx", ...}) or a manual zoom
        # ({"kind": "zoom", "segment_ids"}). It waits in the deque of the lane its next step needs.
        self.lanes: dict[str, deque[dict]] = {ln: deque() for ln in LANES}
        self.running: dict[str, dict | None] = {ln: None for ln in LANES}
        self.cv = threading.Condition()
        self.gpu_lock = threading.Lock()              # Whisper and Zoom never run together, whatever lane runs them
        self.stop_requested: set[str] = set()
        self.threads = [threading.Thread(target=self._lane_loop, args=(ln,), name=f"studio-{ln}", daemon=True)
                        for ln in LANES]
        self.watcher = intake.FolderWatcher(self.intake_file, on_copied=self.intake_copied)
        self._downloads: dict[str, threading.Thread] = {}

    # ------------------------------------------------------------ lifecycle
    def start(self) -> None:
        self._resume()
        for t in self.threads:
            t.start()
        self.watcher.start()
        from ..channel_watch import ChannelWatcher
        self.channel_watcher = ChannelWatcher(self)
        self.channel_watcher.start()
        from ..portable import DataIndexer
        self.data_indexer = DataIndexer()
        self.data_indexer.start()
        log.info("orchestrator started (lanes: %s)", ", ".join(LANES))

    def _resume(self) -> None:
        """Episodes left mid-pipeline by a previous run continue where they were."""
        active = ("downloading", "transcribing", "selecting", "cutting", "indexing")
        for r in db.rows("SELECT id FROM episodes WHERE stage IN (%s)" % ",".join("?" * len(active)), active):
            self._submit(r["id"])
        # A manual zoom cut short by the restart continues with the clips not zoomed yet, no Claude call involved.
        for r in db.rows("SELECT id, pending_zoom FROM episodes WHERE pending_zoom IS NOT NULL"):
            self._push("gpu", {"ep": r["id"], "kind": "zoom", "segment_ids": _zoom_ids(r["pending_zoom"])})
        with db.tx() as c:
            c.execute("UPDATE episodes SET stage='ready', stage_error=?, updated_at=? WHERE stage='zooming' AND pending_zoom IS NULL",
                      ("zoom bị ngắt vì Studio khởi động lại: chọn lại đoạn rồi bấm Zoom (đoạn đã zoom xong được giữ)", now_iso()))
        with db.tx() as c:
            c.execute("UPDATE jobs SET status='failed', error='studio restarted', finished_at=? WHERE status='running'", (now_iso(),))

    # ------------------------------------------------------------ lanes
    def _push(self, lane: str, item: dict) -> None:
        with self.cv:
            self.lanes[lane].append(item)
            self.cv.notify_all()

    def _find(self, episode_id: str, kind: str) -> tuple[str, dict, bool] | None:
        """(lane, item, is_running) of the episode's item of that kind. Call with self.cv held."""
        for ln in LANES:
            it = self.running[ln]
            if it and it["ep"] == episode_id and it["kind"] == kind:
                return ln, it, True
            for it in self.lanes[ln]:
                if it["ep"] == episode_id and it["kind"] == kind:
                    return ln, it, False
        return None

    def _waiting(self) -> int:
        with self.cv:
            return sum(len(q) for q in self.lanes.values())

    def _lane_for(self, item: dict) -> str:
        """The lane of the item's next step: `light` when that step will only find its output already there."""
        if item["kind"] == "zoom":
            return "gpu"
        stage = item["stages"][item["idx"]]
        lane = STAGE_LANE[stage]
        try:
            ep = db.row("SELECT * FROM episodes WHERE id=?", (item["ep"],)) or {}
            video = Path(ep["video_path"]) if ep.get("video_path") else None
            if stage == "transcribe" and video and video.exists() and transcribe.transcript_ready(video):
                return "light"
            if stage == "select" and not item["force"] and _cutlist_reusable(item["ep"]):
                return "light"
            if stage == "cut" and video and video.exists() and \
                    not cut_stage.pending_segments(item["ep"], cut_stage.episode_clip_folder(ep)):
                return "light"
        except Exception:  # noqa: BLE001
            log.exception("lane check for %s/%s", item["ep"], stage)
        return lane

    def _submit(self, episode_id: str, force: bool = False, from_stage: str | None = None) -> str:
        stages = _stages(episode_id)
        start = stages.index(from_stage) if from_stage in stages else 0
        item = {"ep": episode_id, "kind": "pipe", "force": force, "stages": stages, "idx": start, "start": start}
        # The running label of the next step marks the episode as in the pipeline, so a restart resumes it.
        self._set_stage(episode_id, STAGE_RUNNING[stages[start]])
        lane = self._lane_for(item)
        self._push(lane, item)
        return lane

    # ------------------------------------------------------------ public API
    def enqueue_episode(self, episode_id: str, from_stage: str | None = None, force: bool = False) -> dict:
        ep = db.row("SELECT id, stage, video_path, pending_zoom FROM episodes WHERE id=?", (episode_id,))
        if not ep:
            return {"error": f"không có tập {episode_id}"}
        if ep["pending_zoom"] and not force and not from_stage:    # "Chạy tiếp" after a zoom that stopped midway
            with self.cv:
                z = self._find(episode_id, "zoom")
            if z and z[2]:
                return {"message": f"{episode_id} đang zoom"}
            res = self.enqueue_zoom(episode_id, _zoom_ids(ep["pending_zoom"]))
            if "queue" in res:
                return res
        if not ep["video_path"] or not Path(ep["video_path"]).exists():
            return {"error": f"{episode_id} không còn video gốc (đã xoá sau khi xử lý xong). Muốn chạy lại thì dán lại "
                             "link hoặc thả file video vào thư mục media, tập sẽ tự nạp lại."}
        with self.cv:
            if self._find(episode_id, "pipe"):
                return {"message": f"{episode_id} đã ở trong hàng đợi"}
        if force:                                                  # selecting again replaces the segments it was for
            self._forget_zoom(episode_id)
        with db.tx() as c:
            c.execute("UPDATE episodes SET stage_error=NULL, updated_at=? WHERE id=?", (now_iso(), episode_id))
        lane = self._submit(episode_id, force, from_stage)
        return {"message": f"đã xếp {episode_id} vào hàng đợi (làn {LANE_VI[lane]})", "episode_id": episode_id,
                "queue": self._waiting()}

    def enqueue_zoom(self, episode_id: str, segment_ids: list[int] | None = None) -> dict:
        """Zoom only the segments the user picked (None = every cut clip of the episode). Picking a highlight
        brings its hooks along. A zoom request already waiting in the queue for this episode absorbs the new one."""
        if not db.row("SELECT id FROM episodes WHERE id=?", (episode_id,)):
            return {"error": f"không có tập {episode_id}"}
        ids = None
        if segment_ids is not None:
            ids = {int(i) for i in segment_ids}
            if not ids:
                return {"error": "chưa chọn đoạn nào"}
            ids |= {r["id"] for r in db.rows("SELECT id FROM segments WHERE episode_id=? AND kind='hook' AND parent_id IN (%s)"
                                             % ",".join("?" * len(ids)), (episode_id, *ids))}
        todo = zoom_stage.pending_segments(episode_id, ids)
        if not todo:
            self._forget_zoom(episode_id)
            return {"message": "các đoạn đã chọn đều đã có bản zoom, hoặc chưa có clip (cắt xong mới zoom được)"}
        self._remember_zoom(episode_id, ids)
        with self.cv:
            gpu = self.lanes["gpu"]
            for o in gpu:
                if o["ep"] == episode_id and o["kind"] == "zoom":
                    o["segment_ids"] = None if ids is None or o["segment_ids"] is None else sorted(set(o["segment_ids"]) | ids)
                    return {"message": f"đã gộp vào lệnh zoom đang chờ của {episode_id}", "queue": len(gpu)}
            gpu.append({"ep": episode_id, "kind": "zoom", "segment_ids": None if ids is None else sorted(ids)})
            ahead = len(gpu) - 1 + (1 if self.running["gpu"] else 0)
            self.cv.notify_all()
        with db.tx() as c:
            c.execute("UPDATE episodes SET stage_error=NULL, updated_at=? WHERE id=?", (now_iso(), episode_id))
        return {"message": f"đã xếp zoom {len(todo)} clip của {episode_id}" + (f", chờ {ahead} việc GPU trước" if ahead else ", bắt đầu ngay"),
                "clips": len(todo), "queue": self._waiting()}

    def approve(self, episode_id: str) -> dict:
        ep = db.row("SELECT stage FROM episodes WHERE id=?", (episode_id,))
        if not ep:
            return {"error": "không có tập"}
        if ep["stage"] != "reviewing":
            return {"error": f"tập đang ở stage {ep['stage']}, không phải reviewing"}
        with db.tx() as c:
            c.execute("UPDATE episodes SET stage='selected', updated_at=? WHERE id=?", (now_iso(), episode_id))
        notify.resolve(f"ep-review:{episode_id}")
        return self.enqueue_episode(episode_id, from_stage="cut")

    def intake_file(self, path: Path, podcast_id: str | None = None) -> dict:
        """Register a video and run it. podcast_id (picked on the Queue page) puts it into that show even when no file
        name pattern matches: needed for the support library, whose videos come from many different podcasts."""
        path = Path(path)
        if podcast_id:
            from ..util import clean_stem
            info = podcasts.assign(clean_stem(path.name), podcast_id)
            if not info:
                return {"error": f"không có show {podcast_id}"}
        else:
            info = parse_episode_name(path.name)
        if not info:
            return {"error": f"không show nào nhận tên file này (chọn show khi nạp, hoặc thêm mẫu tên ở Cài đặt → Show podcast): {path.name}"}
        if not path.exists():
            return {"error": f"không thấy file: {path}"}
        self.watcher._seen.add(str(path))
        transcript = find_transcript(path)
        with db.tx() as c:
            ingest.upsert_episode(c, {"id": info["episode_id"], "podcast_id": info["podcast_id"], "number": info["number"],
                                      "guest": info["guest"], "source_video": path.name, "video_path": str(path),
                                      "transcript_path": str(transcript) if transcript else None,
                                      "duration_sec": ffprobe_duration(path) or None})
            if info.get("title"):
                c.execute("UPDATE episodes SET title=COALESCE(title, ?) WHERE id=?", (info["title"], info["episode_id"]))
        return self.enqueue_episode(info["episode_id"])

    def intake_copied(self, path: Path) -> dict:
        """A video dropped into Full together with its transcript: data copied from another machine (or restored).
        Index it with what came along, never start Whisper/Claude for it: "Chạy" on the episode page still can."""
        from .. import portable
        res = portable.index_copied_video(Path(path))
        if res.get("episode_id"):
            notify.notify("done", f"Đã index video chép vào: {ep_label(res['episode_id'])}",
                          "có sẵn transcript nên không chạy pipeline" + ("" if res.get("cutlist") else
                          "; chưa có cutlist: muốn chọn đoạn thì bấm Chạy ở trang tập"), ep_link(res["episode_id"]))
        return res

    def intake_url(self, url: str, podcast_id: str | None = None) -> dict:
        key = url.strip()
        if key in self._downloads and self._downloads[key].is_alive():
            return {"message": "link này đang tải"}
        job_id = self._job("download:" + key[-40:], "download", "running")

        def _run():
            try:
                path = intake.download_url(key, progress_cb=lambda p, m: self._job_update(job_id, p, m))
                self.watcher._seen.add(str(path))
                res = self.intake_file(path, podcast_id)
                if res.get("error"):
                    self._job_update(job_id, 100, None, status="failed",
                                     error=f"đã tải {path.name} nhưng không đưa vào pipeline: {res['error']}")
                    notify.notify("error", f"Tải xong nhưng không vào pipeline: {path.name}", res["error"], "/queue")
                else:
                    self._job_update(job_id, 100, f"đã tải {path.name} → {res.get('episode_id')}", status="done")
                    notify.notify("done", f"Tải video xong: {path.name}", f"{res.get('episode_id')} đã vào hàng đợi",
                                  ep_link(res["episode_id"]) if res.get("episode_id") else "/queue")
            except Exception as e:  # noqa: BLE001
                log.exception("download failed")
                self._job_update(job_id, None, None, status="failed", error=str(e))
                notify.notify("error", "Tải video lỗi", f"{key[:120]}: {e}", "/queue")

        t = threading.Thread(target=_run, name="studio-download", daemon=True)
        self._downloads[key] = t
        t.start()
        return {"message": "đang tải, tập sẽ tự vào pipeline khi tải xong"}

    def request_stop(self, episode_id: str) -> dict:
        """Drop a queued episode, or ask the running one to stop at the next safe point."""
        removed = running = False
        with self.cv:
            for ln in LANES:
                for item in list(self.lanes[ln]):
                    if item["ep"] == episode_id:
                        self.lanes[ln].remove(item)
                        removed = True
                if self.running[ln] and self.running[ln]["ep"] == episode_id:
                    running = True
            if running:
                self.stop_requested.add(episode_id)
        self._forget_zoom(episode_id)
        if running:
            return {"message": f"đang dừng {episode_id}, bước hiện tại dừng ở điểm an toàn gần nhất"}
        if removed:
            self._set_stage(episode_id, "failed:stopped", "dừng theo yêu cầu")
            return {"message": f"đã bỏ {episode_id} khỏi hàng đợi"}
        return {"message": f"{episode_id} không chạy"}

    def is_busy(self) -> bool:
        with self.cv:
            return any(self.running.values()) or any(self.lanes.values())

    def status(self) -> dict:
        """running: episodes working right now (one per lane at most); queue: episodes waiting for a lane.
        current (the first running episode) is kept for old callers."""
        with self.cv:
            lanes = {ln: {"label": LANE_VI[ln], "running": self.running[ln]["ep"] if self.running[ln] else None,
                          "step": _item_step(self.running[ln]), "waiting": [it["ep"] for it in self.lanes[ln]]}
                     for ln in LANES}
        running = list(dict.fromkeys(v["running"] for v in lanes.values() if v["running"]))
        queue = [e for e in dict.fromkeys(e for v in lanes.values() for e in v["waiting"]) if e not in running]
        return {"current": running[0] if running else None, "running": running, "queue": queue, "lanes": lanes}

    # ------------------------------------------------------------ workers
    def _lane_loop(self, lane: str) -> None:
        while True:
            with self.cv:
                while True:
                    busy = {it["ep"] for it in self.running.values() if it}
                    item = next((it for it in self.lanes[lane] if it["ep"] not in busy), None)
                    if item is not None:
                        break
                    self.cv.wait(timeout=30)
                self.lanes[lane].remove(item)
                self.running[lane] = item
            episode_id, nxt, nxt_lane = item["ep"], None, None
            try:
                if item["kind"] == "zoom":
                    self.run_zoom(episode_id, item.get("segment_ids"))
                else:
                    nxt = self._run_step(item)
                    if nxt is not None:
                        nxt_lane = self._lane_for(nxt)     # still marked running: the episode stays locked meanwhile
            except Exception as e:  # noqa: BLE001
                log.exception("pipeline crashed for %s", episode_id)
                self._set_stage(episode_id, "failed:unknown", str(e))
                notify.notify("error", f"Pipeline lỗi: {ep_label(episode_id)}", str(e), ep_link(episode_id))
                nxt = None
            with self.cv:
                self.running[lane] = None
                if nxt is not None:
                    self.lanes[nxt_lane].append(nxt)
                else:
                    self.stop_requested.discard(episode_id)
                self.cv.notify_all()

    def _run_step(self, item: dict) -> dict | None:
        """Run the item's next stage. Returns the item for its following stage, or None when the run is over."""
        episode_id = item["ep"]
        stage = item["stages"][item["idx"]]
        if episode_id in self.stop_requested:
            self._set_stage(episode_id, f"failed:{stage}", "dừng theo yêu cầu")
            return None
        ep = db.row("SELECT * FROM episodes WHERE id=?", (episode_id,))
        if not ep:
            return None
        if item["idx"] == item["start"]:
            log.info("=== pipeline %s (force=%s, from=%s) ===", episode_id, item["force"], stage)
        job_id = self._job(episode_id, stage, "running")
        self._set_stage(episode_id, STAGE_RUNNING[stage])
        try:
            result = getattr(self, f"_stage_{stage}")(ep, job_id, item["force"] and stage == "select")
        except Exception as e:  # noqa: BLE001
            log.error("stage %s failed for %s: %s\n%s", stage, episode_id, e, traceback.format_exc())
            self._job_update(job_id, None, None, status="failed", error=str(e)[:2000])
            self._set_stage(episode_id, f"failed:{stage}", str(e)[:1000])
            if episode_id not in self.stop_requested:
                notify.notify("error", f"{STAGE_VI.get(stage, stage)} lỗi: {ep_label(episode_id)}", str(e),
                              ep_link(episode_id))
            return None
        if result == "review":
            self._job_update(job_id, 100, "chờ duyệt cutlist", status="done")
            self._set_stage(episode_id, "reviewing")
            notify.notify("review", f"Cutlist cần duyệt: {ep_label(episode_id)}",
                          f"Claude đã chọn {_highlights(episode_id)} đoạn, duyệt để cắt clip", ep_link(episode_id),
                          key=f"ep-review:{episode_id}")
            return None
        skipped = isinstance(result, dict) and result.get("skipped")
        summary = result.get("summary") if isinstance(result, dict) else None
        self._job_update(job_id, 100, "skip" if skipped else (summary or "xong"),
                         status="skipped" if skipped else "done")
        _stage_note(episode_id, stage, result)
        item["idx"] += 1
        if item["idx"] >= len(item["stages"]):
            self._set_stage(episode_id, "ready")
            log.info("=== %s ready ===", episode_id)
            if item["stages"] == ["transcribe"]:
                notify.notify("done", f"Đã vào kho bổ trợ: {ep_label(episode_id)}",
                              "transcript sẵn sàng cho video tổng hợp", ep_link(episode_id))
                return None
            notify.notify("done", f"Tập đã xong toàn bộ: {ep_label(episode_id)}",
                          f"{_highlights(episode_id)} đoạn highlight đã vào kho", ep_link(episode_id))
            self._delete_source(episode_id)
            return None
        nxt = item["stages"][item["idx"]]
        if episode_id in self.stop_requested:
            self._set_stage(episode_id, f"failed:{nxt}", "dừng theo yêu cầu")
            return None
        self._set_stage(episode_id, STAGE_RUNNING[nxt])    # waiting for the next lane; a restart resumes from here
        return item

    def run_zoom(self, episode_id: str, segment_ids: list[int] | None = None) -> None:
        """Manual zoom: the episode shows `zooming` meanwhile, then goes back to the stage it had."""
        ep = db.row("SELECT stage FROM episodes WHERE id=?", (episode_id,))
        if not ep:
            return
        back = ep["stage"] if ep["stage"] and ep["stage"] != "zooming" else "ready"
        log.info("=== zoom %s (%s) ===", episode_id, "all" if segment_ids is None else f"{len(segment_ids)} segments")
        job_id = self._job(episode_id, "zoom", "running")
        self._set_stage(episode_id, "zooming")
        try:
            with self.gpu_lock:
                res = zoom_stage.zoom_episode(episode_id, progress_cb=lambda p, m: self._job_update(job_id, p, m),
                                              stop_flag=lambda: episode_id in self.stop_requested,
                                              segment_ids=None if segment_ids is None else set(segment_ids))
        except Exception as e:  # noqa: BLE001
            log.error("zoom failed for %s: %s", episode_id, e)
            self._job_update(job_id, None, None, status="failed", error=str(e)[:2000])
            if episode_id not in self.stop_requested:
                notify.notify("error", f"Zoom lỗi: {ep_label(episode_id)}", str(e), ep_link(episode_id))
            self._set_stage(episode_id, back, str(e)[:1000])
            return
        self._forget_zoom(episode_id)
        skipped = res.get("skipped")
        self._job_update(job_id, 100, "không còn clip nào cần zoom" if skipped else f"zoom xong {res.get('zoomed', 0)} clip",
                         status="skipped" if skipped else "done")
        self._set_stage(episode_id, back)

    def _delete_source(self, episode_id: str) -> None:
        """Free disk space: once every highlight/hook has its clip on disk, delete the full source video for good."""
        if not db.setting_bool("delete_source_after_ready"):
            return
        ep = db.row("SELECT * FROM episodes WHERE id=?", (episode_id,))
        video = Path(ep["video_path"]) if ep and ep.get("video_path") else None
        if not video or not video.is_file():
            return
        root = Path(db.get_setting("media_root")).resolve()
        if root not in video.resolve().parents:
            log.warning("keep source of %s: %s is outside media_root", episode_id, video)
            return
        job_id = self._job(episode_id, "cleanup", "running")
        has_clips = db.row("SELECT COUNT(*) AS n FROM segments WHERE episode_id=? AND start_sec IS NOT NULL "
                           "AND rank IS NOT NULL AND status NOT IN ('archived')", (episode_id,))["n"]
        missing = cut_stage.pending_segments(episode_id, cut_stage.episode_clip_folder(ep)) if has_clips else []
        if not has_clips or missing:
            why = f"{len(missing)} đoạn chưa có clip" if has_clips else "tập chưa có đoạn nào"
            self._job_update(job_id, 100, f"giữ video gốc: {why}", status="skipped")
            return
        size_gb = video.stat().st_size / 1e9
        try:
            video.unlink()
        except OSError as e:
            log.warning("could not delete source of %s: %s", episode_id, e)
            self._job_update(job_id, None, None, status="failed", error=f"không xoá được video gốc (file đang mở?): {e}")
            return
        log.info("deleted source video of %s: %s (%.1f GB)", episode_id, video.name, size_gb)
        self._job_update(job_id, 100, f"đã xoá video gốc {video.name}, giải phóng {size_gb:.1f} GB", status="done")

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
    def _remember_zoom(self, episode_id: str, ids: set[int] | None) -> None:
        """Keep the picked segments in the DB until they are zoomed, so a restart can continue with them."""
        with db.tx() as c:
            cur = c.execute("SELECT pending_zoom FROM episodes WHERE id=?", (episode_id,)).fetchone()[0]
            if cur and ids is not None:
                old = _zoom_ids(cur)
                ids = None if old is None else ids | set(old)
            c.execute("UPDATE episodes SET pending_zoom=? WHERE id=?",
                      ("all" if ids is None else json.dumps(sorted(ids)), episode_id))

    def _forget_zoom(self, episode_id: str) -> None:
        """Only a zoom request still waiting in the queue stays remembered."""
        with self.cv:
            waiting = [o["segment_ids"] for o in self.lanes["gpu"] if o["ep"] == episode_id and o["kind"] == "zoom"]
        value = None if not waiting else "all" if waiting[0] is None else json.dumps(waiting[0])
        with db.tx() as c:
            c.execute("UPDATE episodes SET pending_zoom=? WHERE id=?", (value, episode_id))

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
