"""Hổ Báo Studio: Flask UI + JSON API. Started by Tool Manager (`from app import app`) or `python app.py`."""
from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import sys
import threading
from pathlib import Path

from flask import Flask, abort, jsonify, redirect, render_template, request, send_file, url_for

sys.path.insert(0, str(Path(__file__).resolve().parent))

from studio import channel_watch, config, db, devchat, export as export_mod, flow, guests, ingest, link_queue, maintenance, notify, paths, podcasts, search, tagging  # noqa: E402
from studio.analysis import import_markdown, sections_for_display  # noqa: E402
from studio.textfmt import md_to_html  # noqa: E402
from studio.util import now_iso, parse_episode_name  # noqa: E402

config.LOG_DIR.mkdir(exist_ok=True)
config.WORK_DIR.mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.FileHandler(config.LOG_DIR / "studio.log", encoding="utf-8"), logging.StreamHandler()],
)
log = logging.getLogger("studio.app")

def _below_normal_priority() -> None:
    """Heavy work (Claude turns and everything they start: Remotion/Chrome, ffmpeg, whisper…) runs below the user's own
    apps: Windows children of a below-normal process inherit it, so Chrome and Claude desktop stay responsive."""
    if os.name != "nt":
        return
    try:
        import ctypes
        from ctypes import wintypes
        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        # declare the types: without them the 64-bit pseudo-handle of GetCurrentProcess() is cut to 32 bits and the
        # call fails silently (the process stayed at Normal)
        k32.GetCurrentProcess.restype = wintypes.HANDLE
        k32.SetPriorityClass.argtypes = (wintypes.HANDLE, wintypes.DWORD)
        k32.SetPriorityClass.restype = wintypes.BOOL
        k32.SetPriorityClass(k32.GetCurrentProcess(), 0x00004000)   # BELOW_NORMAL_PRIORITY_CLASS
    except Exception:  # noqa: BLE001
        pass


_below_normal_priority()

app = Flask(__name__, template_folder="templates", static_folder="static")
app.config["TEMPLATES_AUTO_RELOAD"] = True      # template fixes apply without restarting the tool
app.jinja_env.auto_reload = True
app.jinja_env.filters["md"] = md_to_html
app.jinja_env.filters["basename"] = lambda p: os.path.basename(p) if p else ""
db.init_db()
notify.register(app)     # 🔔 /api/notifications (bell in the header)
with db.tx() as _c:     # a topic scan cut short by a restart cannot resume (its thread is gone)
    _c.execute("UPDATE topic_scans SET status='failed', error='studio khởi động lại giữa chừng' "
               "WHERE status IN ('queued','running')")
    _c.execute("UPDATE topic_scans SET status='done', error='studio khởi động lại khi đang cắt' WHERE status='cutting'")
from studio.pipeline import compile_titles, compile_video, doc_extend, hook_join  # noqa: E402
compile_video.recover_after_restart()
doc_extend.recover_after_restart()

_orchestrator = None
_orch_lock = threading.Lock()
_title_worker = None
_title_lock = threading.Lock()


def title_worker():
    """Worker for the "Viết Title" button (own queue, never blocks the main pipeline)."""
    global _title_worker
    if os.environ.get("STUDIO_NO_WORKER") == "1":
        return None
    with _title_lock:
        if _title_worker is None:
            try:
                from studio.pipeline import titles
                from studio.pipeline.titles import TitleWorker
                titles.AFTER_HOOK_RECUT = lambda ep_id, ids: orchestrator() and orchestrator().enqueue_zoom(ep_id, ids)
                _title_worker = TitleWorker()
                _title_worker.start()
            except Exception as e:  # noqa: BLE001
                log.warning("title worker unavailable: %s", e)
                _title_worker = False
    return _title_worker or None


def _attach_titles(episode_id: str, segments: list[dict]) -> None:
    from studio.pipeline.titles import runs_for_episode, thumbs_for_episode
    runs = runs_for_episode(episode_id)
    thumbs = thumbs_for_episode(episode_id)
    for s in segments:
        r = runs.get(s["id"]) or {}
        s["title_run"] = r.get("latest")
        s["title_done"] = r.get("done")
        s["title_thread"] = r.get("thread") or []
        s["title_full_md"] = r.get("full_md")
        s["title_history"] = r.get("history") or []
        t = thumbs.get(s["id"]) or {}
        s["thumb_run"] = t.get("latest")
        s["thumb_current"] = t.get("current")
        s["thumb_versions"] = t.get("versions") or []
        s["thumb_chat"] = t.get("chat") or []


def orchestrator():
    """Lazily start the pipeline worker (module is optional until phase 2 lands)."""
    global _orchestrator
    if os.environ.get("STUDIO_NO_WORKER") == "1":      # read-only instance (tests, second viewer): never run jobs
        return None
    with _orch_lock:
        if _orchestrator is None:
            try:
                from studio.pipeline.orchestrator import Orchestrator
                _orchestrator = Orchestrator()
                _orchestrator.start()
            except Exception as e:  # noqa: BLE001
                log.warning("orchestrator unavailable: %s", e)
                _orchestrator = False
    return _orchestrator or None


# ---------------------------------------------------------------- pages
@app.context_processor
def _ctx():
    return {"nav": [("queue", "Hàng đợi"), ("pipeline", "Pipeline"), ("episodes", "Tập"), ("guests", "Khách mời"), ("search", "Tìm kiếm"),
                    ("compilations", "Compilation"), ("compile", "Video tổng hợp"), ("ask", "Hỏi AI"), ("settings", "Cài đặt")]}


@app.route("/")
def index():
    return redirect(url_for("queue_page"))


@app.route("/queue")
def queue_page():
    orchestrator()
    episodes = db.rows(
        """SELECT e.*, (SELECT COUNT(*) FROM segments s WHERE s.episode_id=e.id AND s.kind='highlight' AND s.status!='archived') AS highlights,
                  (SELECT COUNT(*) FROM segments s WHERE s.episode_id=e.id AND s.clip_zoomed_path IS NOT NULL AND s.status!='archived') AS zoomed
           FROM episodes e ORDER BY e.updated_at DESC""")
    jobs = db.rows("SELECT * FROM jobs ORDER BY id DESC LIMIT 60")
    orch = orchestrator()
    pipe = orch.status() if orch else {"current": None, "queue": []}
    return render_template("queue.html", page="queue", episodes=episodes, jobs=jobs, pipe=pipe, podcasts=podcasts.overview(),
                           media_root=db.get_setting("media_root"))


@app.route("/episodes")
def episodes_page():
    show = (request.args.get("show") or "").strip().upper()
    episodes = db.rows(
        """SELECT e.*, (SELECT COUNT(*) FROM segments s WHERE s.episode_id=e.id AND s.kind='highlight' AND s.status!='archived') AS highlights,
                  (SELECT COUNT(*) FROM segments s WHERE s.episode_id=e.id AND s.kind='hook' AND s.status!='archived') AS hooks,
                  (SELECT COUNT(*) FROM segments s WHERE s.episode_id=e.id AND s.clip_path IS NOT NULL AND s.status!='archived') AS cut,
                  (SELECT COUNT(*) FROM segments s WHERE s.episode_id=e.id AND s.clip_zoomed_path IS NOT NULL AND s.status!='archived') AS zoomed,
                  (SELECT COUNT(*) FROM segments s WHERE s.episode_id=e.id AND s.analysis_md IS NOT NULL AND s.status!='archived') AS analysed
           FROM episodes e WHERE (?='' OR e.podcast_id=?) ORDER BY e.podcast_id, e.number DESC""", (show, show))
    return render_template("episodes.html", page="episodes", episodes=episodes, show=show,
                           podcasts=podcasts.overview())


@app.route("/episodes/<episode_id>")
def episode_page(episode_id):
    ep = db.row("SELECT * FROM episodes WHERE id=?", (episode_id.upper(),))
    if not ep:
        abort(404)
    segs = db.rows("SELECT * FROM segments WHERE episode_id=? ORDER BY COALESCE(rank, 999), start_sec", (ep["id"],))
    deleted = [s for s in segs if s["status"] == "archived"]
    segs = [s for s in segs if s["status"] != "archived"]
    by_id = {s["id"]: s for s in segs}
    for s in segs:
        s["topics"] = [r["name"] for r in db.rows(
            "SELECT t.name FROM segment_topics st JOIN topics t ON t.id=st.topic_id WHERE st.segment_id=?", (s["id"],))]
        s["themes"] = [r["slug"] for r in db.rows(
            "SELECT th.slug FROM segment_themes st JOIN themes th ON th.id=st.theme_id WHERE st.segment_id=? "
            "ORDER BY st.is_primary DESC", (s["id"],))]
        s["hooks"] = []
        s["analysis"] = sections_for_display(s)
        s["preview"] = s.get("summary_vi") or (s["analysis"].get("tom_tat") or "")[:260] or s.get("summary_en") or ""
    highlights = []
    for s in segs:
        if s["kind"] == "hook" and s["parent_id"] in by_id:
            by_id[s["parent_id"]]["hooks"].append(s)
            s["joined"] = hook_join.status(s["id"])
        elif s["kind"] == "hook":
            highlights.append(s)      # orphan hook, show inline
        else:
            s["hooked_files"] = doc_extend.hooked_files(s)
            s["docext"] = doc_extend.state(s["id"])
            highlights.append(s)
    profile = None
    if ep.get("guest_profile_json"):
        try:
            profile = json.loads(ep["guest_profile_json"])
        except Exception:  # noqa: BLE001
            profile = None
    _attach_titles(ep["id"], highlights)
    jobs = db.rows("SELECT * FROM jobs WHERE episode_id=? ORDER BY id DESC LIMIT 20", (ep["id"],))
    for s in deleted:
        s["has_clip"] = bool(s["clip_path"] and Path(s["clip_path"]).exists())
        s["has_zoom"] = bool(s["clip_zoomed_path"] and Path(s["clip_zoomed_path"]).exists())
    return render_template("episode.html", page="episodes", ep=ep, segments=highlights, profile=profile, jobs=jobs,
                           hook_transitions=hook_join.TRANSITIONS,
                           hook_transition=db.get_setting("hook_join_transition") or "fade",
                           docext_min=db.get_setting("docext_target_min") or "10",
                           docext_budget=db.get_setting("docext_budget_usd") or "",
                           deleted=deleted, guest_groups=guests.groups_for_episode(ep.get("guest")),
                           title_skill=db.get_setting("title_skill"),
                           title_model=db.get_setting("claude_model_title"))


@app.route("/guests")
def guests_page():
    return render_template("guests.html", page="guests", ov=guests.overview())


@app.route("/segments/<int:seg_id>/title-block")
def title_block(seg_id):
    """HTML fragment of the title section of one segment (polled while a run is in progress)."""
    s = db.row("SELECT * FROM segments WHERE id=?", (seg_id,))
    if not s:
        abort(404)
    _attach_titles(s["episode_id"], [s])
    return render_template("_title_block.html", s=s, title_skill=db.get_setting("title_skill"),
                           title_model=db.get_setting("claude_model_title"))


@app.route("/search")
def search_page():
    args = request.args
    q = args.get("q", "").strip()
    filters = {
        "episode_id": args.get("episode") or None, "guest": args.get("guest") or None, "kind": args.get("kind") or None,
        "min_intensity": float(args["min_intensity"]) if args.get("min_intensity") else None,
        "min_gtf": float(args["min_gtf"]) if args.get("min_gtf") else None,
        "keyword_reach": args.get("reach") or None, "status": args.get("status") or None,
        "theme": args.get("theme") or None, "topic": args.get("topic") or None, "group": args.get("group") or None,
        "unused": args.get("unused") == "1", "limit": int(args.get("limit") or 50),
    }
    results = search.search(q, **filters) if (q or any(v for k, v in filters.items() if k != "limit")) else []
    themes = db.rows("SELECT slug, name_vi FROM themes ORDER BY slug")
    episodes = db.rows("SELECT id, guest FROM episodes ORDER BY podcast_id, number DESC")
    return render_template("search.html", page="search", q=q, f=args, results=results, themes=themes, episodes=episodes,
                           guest_groups=guests.groups())


@app.route("/compilations")
def compilations_page():
    comps = db.rows("""SELECT c.*, (SELECT COUNT(*) FROM compilation_items ci WHERE ci.compilation_id=c.id) AS n
                       FROM compilations c ORDER BY c.id DESC""")
    for c in comps:
        c["items"] = db.rows("""SELECT ci.ord, ci.role, s.id, s.episode_id, s.title, s.start_hms, s.end_hms
                                FROM compilation_items ci JOIN segments s ON s.id=ci.segment_id
                                WHERE ci.compilation_id=? ORDER BY ci.ord""", (c["id"],))
    from studio.pipeline import topic_scan
    scans = db.rows("SELECT * FROM topic_scans ORDER BY id DESC LIMIT 30")
    for s in scans:
        s["items"] = topic_scan.items(s["id"])
    return render_template("compilations.html", page="compilations", comps=comps, scans=scans,
                           podcasts=podcasts.overview(),
                           topic_model=db.get_setting("claude_model_topic"),
                           topic_effort=db.get_setting("claude_effort_topic"))


# ---------------------------------------------------------------- Video tổng hợp (one highlight → long compilation)
def _compile_job(job_id: int) -> dict:
    job = compile_video.get_job(job_id)
    if not job:
        abort(404)
    return job


@app.route("/compile")
def compile_page():
    seed = None
    if request.args.get("seed"):
        seed = db.row("SELECT s.*, e.guest FROM segments s JOIN episodes e ON e.id=s.episode_id WHERE s.id=?",
                      (int(request.args["seed"]),))
    sources = []
    if seed:
        own = podcasts.for_episode(seed["episode_id"])["id"]
        default = set(compile_video.default_sources(seed["episode_id"]))
        sources = [dict(p, own=p["id"] == own, checked=p["id"] in default) for p in podcasts.overview()
                   if p["id"] == own or p["episodes"]]
    return render_template("compile.html", page="compile", jobs=compile_video.list_jobs(), seed=seed, sources=sources,
                           q=request.args.get("q", ""),
                           results=search.search(request.args["q"], kind="highlight", limit=30) if request.args.get("q") else [])


@app.route("/compile/<int:job_id>")
def compile_job_page(job_id):
    job = _compile_job(job_id)
    seed = db.row("SELECT s.*, e.guest FROM segments s JOIN episodes e ON e.id=s.episode_id WHERE s.id=?",
                  (job["seed_segment_id"],))
    its = compile_video.items(job_id)
    compile_video.zoom_state(job, its)
    return render_template("compile_job.html", page="compile", job=job, seed=seed, items=its,
                           seed_show=podcasts.for_episode(seed["episode_id"])["name"] if seed else "",
                           cands=compile_video.candidates(job_id, unused_only=True), totals=compile_video.totals(job),
                           busy=compile_video.busy(job_id), chapters=compile_video.chapters_text(job),
                           ctitle=compile_titles.load(job), ctitle_block=compile_titles.ready(job),
                           ctitle_model=db.get_setting("claude_model_compile_title"))


@app.route("/api/compile", methods=["POST"])
def api_compile_create():
    data = request.json or {}
    try:
        res = compile_video.create(int(data.get("seed") or 0), int(data.get("target_min") or 0), data.get("note") or "",
                                   data.get("podcast_ids"))
    except ValueError:
        res = {"error": "dữ liệu không hợp lệ"}
    if res.get("ok"):
        res["url"] = url_for("compile_job_page", job_id=res["id"])
    return jsonify(res), (400 if res.get("error") else 200)


@app.route("/api/compile/<int:job_id>/state")
def api_compile_state(job_id):
    job = _compile_job(job_id)
    return jsonify({"status": job["status"], "progress": job["progress_msg"], "error": job["error"],
                    "busy": compile_video.busy(job_id), "updated_at": job["updated_at"]})


@app.route("/api/compile/<int:job_id>/<action>", methods=["POST"])
def api_compile_action(job_id, action):
    _compile_job(job_id)
    data = request.json or {}
    if action == "stop":
        res = compile_video.stop(job_id)
    elif action == "rearrange":
        res = compile_video.rearrange(job_id, data.get("feedback") or "")
    elif action == "rescan":
        res = compile_video.rescan(job_id, data.get("keywords") or "")
    elif action == "build":
        res = compile_video.build(job_id)
    elif action == "chapters":
        res = compile_video.refresh_chapters(job_id)
    elif action == "title":
        res = compile_titles.start(job_id)
    elif action == "text":
        compile_video.update_job_text(job_id, **{k: data[k] for k in ("intro_text", "outro_text", "title_en") if k in data})
        res = {"ok": True}
    elif action == "item":
        iid = int(data.get("id") or 0)
        if data.get("move"):
            compile_video.move_item(job_id, iid, int(data["move"]))
        fields = {k: data[k] for k in ("bridge_text",) if k in data}
        if "included" in data:
            fields["included"] = 1 if data["included"] else 0
        compile_video.update_item(job_id, iid, **fields)
        res = {"ok": True}
    elif action == "add":
        res = compile_video.add_candidate(job_id, int(data.get("cand_id") or 0))
    else:
        abort(404)
    return jsonify(res), (400 if res.get("error") else 200)


# ---------------------------------------------------------------- topic compilation from full episodes
@app.route("/api/topic/keywords", methods=["POST"])
def api_topic_keywords():
    from studio.pipeline import topic_scan
    topic = ((request.json or {}).get("topic") or "").strip()
    if not topic:
        return jsonify({"error": "chưa nhập chủ đề"}), 400
    return jsonify(topic_scan.suggest_keywords(topic, (request.json or {}).get("podcast_id") or None))


@app.route("/api/topic/estimate", methods=["POST"])
def api_topic_estimate():
    from studio.pipeline import topic_scan
    data = request.json or {}
    kws = topic_scan.parse_keywords(data.get("keywords", ""))
    if not kws:
        return jsonify({"error": "chưa có từ khoá"}), 400
    return jsonify(topic_scan.estimate(kws, float(data.get("pad_sec") or 120), podcast_id=data.get("podcast_id") or None))


@app.route("/api/topic/scan", methods=["POST"])
def api_topic_scan():
    from studio.pipeline import topic_scan
    data = request.json or {}
    res = topic_scan.start_scan(data.get("topic", ""), topic_scan.parse_keywords(data.get("keywords", "")),
                                float(data.get("pad_sec") or 120), data.get("model", ""), data.get("effort", ""),
                                podcast_id=data.get("podcast_id") or None)
    return jsonify(res), (400 if res.get("error") else 200)


@app.route("/api/topic/<int:scan_id>")
def api_topic_get(scan_id):
    from studio.pipeline import topic_scan
    s = db.row("SELECT * FROM topic_scans WHERE id=?", (scan_id,))
    if not s:
        abort(404)
    return jsonify({**s, "items": topic_scan.items(scan_id)})


@app.route("/api/topic/<int:scan_id>/stop", methods=["POST"])
def api_topic_stop(scan_id):
    from studio.pipeline import topic_scan
    return jsonify(topic_scan.stop(scan_id))


@app.route("/api/topic/<int:scan_id>/items/<int:item_id>", methods=["POST"])
def api_topic_item(scan_id, item_id):
    included = 1 if (request.json or {}).get("included") else 0
    with db.tx() as c:
        c.execute("UPDATE topic_scan_items SET included=? WHERE id=? AND scan_id=?", (included, item_id, scan_id))
    return jsonify({"ok": True})


@app.route("/api/topic/<int:scan_id>/export", methods=["POST"])
def api_topic_export(scan_id):
    from studio.pipeline import topic_scan
    return jsonify(topic_scan.export_cutlist(scan_id))


@app.route("/api/topic/<int:scan_id>/cut", methods=["POST"])
def api_topic_cut(scan_id):
    from studio.pipeline import topic_scan
    res = topic_scan.start_cut(scan_id)
    return jsonify(res), (400 if res.get("error") else 200)


@app.route("/ask")
def ask_page():
    return render_template("ask.html", page="ask")


@app.route("/settings", methods=["GET", "POST"])
def settings_page():
    if request.method == "POST":
        checkboxes = ("zoom_hooks", "auto_zoom", "review_gate", "delete_original_clip_after_zoom", "delete_source_after_ready", "watch_enabled")
        changed = request.form.get("_changed")
        # Only fields the user actually edited: a page left open with old values must not overwrite newer settings.
        keys = [k for k in changed.split(",") if k] if changed is not None else list(config.DEFAULT_SETTINGS)
        for key in keys:
            if key not in config.DEFAULT_SETTINGS:
                continue
            if key in checkboxes:
                db.set_setting(key, "1" if key in request.form else "0")
            elif key in request.form:
                db.set_setting(key, request.form[key].strip())
        return redirect(url_for("settings_page", saved=1))
    from studio import translate
    from studio.pipeline import gemini_runner
    return render_template("settings.html", page="settings", podcasts=podcasts.overview(), watch=channel_watch.all_configs(),hook_transitions=hook_join.TRANSITIONS, sfx_files=hook_join.sfx_choices(), s=db.all_settings(), saved=request.args.get("saved"),
                           claude=_claude_status(), gt_configured=translate.configured(),
                           gemini_configured=gemini_runner.configured(), media_locked=bool(config.media_root_locked()))


def _claude_status() -> dict:
    try:
        from studio.pipeline import claude_runner
        return claude_runner.cli_status()
    except Exception as e:  # noqa: BLE001
        return {"installed": False, "version": str(e), "token": False}


# ---------------------------------------------------------------- media
@app.route("/media")
def media():
    path = Path(request.args.get("path", ""))
    root = Path(db.get_setting("media_root")).resolve()
    try:
        resolved = path.resolve()
    except Exception:  # noqa: BLE001
        abort(400)
    if not resolved.exists() or root not in resolved.parents and resolved != root:
        abort(404)
    return send_file(str(resolved), conditional=True)


# ---------------------------------------------------------------- JSON API
@app.route("/api/stats")
def api_stats():
    return jsonify({
        "episodes": db.scalar("SELECT COUNT(*) FROM episodes"),
        "highlights": db.scalar("SELECT COUNT(*) FROM segments WHERE kind='highlight' AND status!='archived'"),
        "hooks": db.scalar("SELECT COUNT(*) FROM segments WHERE kind='hook' AND status!='archived'"),
        "zoomed": db.scalar("SELECT COUNT(*) FROM segments WHERE clip_zoomed_path IS NOT NULL AND status!='archived'"),
        "with_analysis": db.scalar("SELECT COUNT(*) FROM segments WHERE analysis_md IS NOT NULL AND status!='archived'"),
    })


@app.route("/api/search")
def api_search():
    a = request.args
    res = search.search(a.get("q", ""), episode_id=a.get("episode"), guest=a.get("guest"), kind=a.get("kind"),
                        min_intensity=float(a["min_intensity"]) if a.get("min_intensity") else None,
                        min_gtf=float(a["min_gtf"]) if a.get("min_gtf") else None, keyword_reach=a.get("reach"),
                        status=a.get("status"), theme=a.get("theme"), topic=a.get("topic"), unused=a.get("unused") == "1",
                        limit=int(a.get("limit") or 50))
    return jsonify(res)


@app.route("/api/segments/<int:seg_id>")
def api_segment(seg_id):
    d = search.segment_detail(seg_id)
    if not d:
        abort(404)
    return jsonify(d)


@app.route("/api/segments/<int:seg_id>", methods=["PATCH"])
def api_segment_patch(seg_id):
    data = request.json or {}
    allowed = {"status", "title", "summary_vi", "core_keyword", "analysis_md"}
    sets = {k: v for k, v in data.items() if k in allowed}
    if not sets:
        return jsonify({"error": "nothing to update"}), 400
    with db.tx() as c:
        c.execute(f"UPDATE segments SET {', '.join(k + '=?' for k in sets)}, updated_at=? WHERE id=?",
                  list(sets.values()) + [now_iso(), seg_id])
    search.rebuild_index([seg_id])
    return jsonify({"ok": True})


@app.route("/api/segments/delete", methods=["POST"])
def api_segments_delete():
    """Delete segments from the episode page: {"ids": [...], "files": bool}. Hooks of a deleted highlight go too."""
    data = request.json or {}
    ids = [int(i) for i in data.get("ids") or [] if str(i).isdigit()]
    if not ids:
        return jsonify({"error": "chưa chọn đoạn nào"}), 400
    return jsonify(maintenance.delete_segments(ids, trash_files=bool(data.get("files"))))


@app.route("/api/segments/restore", methods=["POST"])
def api_segments_restore():
    ids = [int(i) for i in (request.json or {}).get("ids") or [] if str(i).isdigit()]
    if not ids:
        return jsonify({"error": "chưa chọn đoạn nào"}), 400
    return jsonify(maintenance.restore_segments(ids))


@app.route("/api/guests/classify", methods=["POST"])
def api_guests_classify():
    """Let Claude group the guests without a group ({"all": true}: every guest not grouped by hand)."""
    try:
        return jsonify(guests.classify(only_missing=not (request.json or {}).get("all")))
    except Exception as e:  # noqa: BLE001
        log.exception("guest classification failed")
        return jsonify({"error": f"phân nhóm lỗi: {e}"}), 500


@app.route("/api/guests/<int:guest_id>", methods=["POST"])
def api_guest_update(guest_id):
    """Group picked by hand: {"group", "also": [...], "expertise"}; Claude never overwrites it."""
    data = request.json or {}
    try:
        guests.set_guest(guest_id, data.get("group") or None, data.get("also") or [],
                         (data.get("expertise") or "").strip() or None, source="manual")
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"ok": True})


@app.route("/api/export", methods=["POST"])
def api_export():
    data = request.json or {}
    ids = [int(i) for i in data.get("ids", [])]
    fmt = data.get("format", "pool")
    theme = data.get("theme") or "selection"
    out_dir = Path(data.get("out_dir") or paths.cutlists_dir())
    name = ("cut_multi_" if fmt == "multi" else "pool_") + export_mod.slugify(theme) + ".json"
    out = export_mod.export_segments(ids, fmt=fmt, theme=theme, out_path=out_dir / name)
    return jsonify({"ok": True, "path": str(out)})


@app.route("/api/compilations/record", methods=["POST"])
def api_record_compilation():
    data = request.json or {}
    if data.get("manifest_path"):
        cid = export_mod.record_compilation_manifest(Path(data["manifest_path"]))
    else:
        cid = export_mod.record_compilation(data.get("theme", "compilation"), [int(i) for i in data.get("ids", [])])
    return jsonify({"ok": True, "id": cid})


@app.route("/api/episodes/<episode_id>/analysis", methods=["POST"])
def api_import_analysis(episode_id):
    data = request.json or {}
    stats = import_markdown(episode_id.upper(), data.get("text", ""), source=data.get("source", "manual"))
    return jsonify(stats)


@app.route("/api/scan", methods=["POST"])
def api_scan():
    res = ingest.scan_media_root(force=bool((request.json or {}).get("force")))
    return jsonify(res)


@app.route("/api/portable", methods=["GET", "POST"])
def api_portable():
    """GET: last round of the data indexer. POST: index what was copied in right now (no waiting for the next round),
    and import every _studio.json written by another machine."""
    from studio import portable
    if request.method == "GET":
        orch = orchestrator()
        return jsonify({"media_root": db.get_setting("media_root"), "machine": portable.MACHINE,
                        "last": getattr(getattr(orch, "data_indexer", None), "last", None)})
    portable.relocate_db()
    snap = portable.snapshot()
    res = portable.index_changes({k: sorted(v) for k, v in snap.items()})
    res["exported"] = len(portable.export_all())
    db.set_setting("portable_indexed", json.dumps({"_root": str(portable.paths.root()), **portable.snapshot()},
                                                  ensure_ascii=False))
    return jsonify(res)


@app.route("/api/jobs")
def api_jobs():
    return jsonify(db.rows("SELECT * FROM jobs ORDER BY id DESC LIMIT 100"))


@app.route("/api/episodes/<episode_id>/run", methods=["POST"])
def api_run_episode(episode_id):
    orch = orchestrator()
    if not orch:
        return jsonify({"error": "pipeline chưa sẵn sàng"}), 503
    data = request.json or {}
    return jsonify(orch.enqueue_episode(episode_id.upper(), from_stage=data.get("from_stage"), force=data.get("force", False)))


@app.route("/api/episodes/<episode_id>/zoom", methods=["POST"])
def api_zoom_episode(episode_id):
    """{"segment_ids": [...]} zooms those segments (and their hooks); {"all": true} every clip of the episode."""
    orch = orchestrator()
    if not orch:
        return jsonify({"error": "pipeline chưa sẵn sàng"}), 503
    data = request.json or {}
    ids = None if data.get("all") else (data.get("segment_ids") or [])
    return jsonify(orch.enqueue_zoom(episode_id.upper(), ids))


@app.route("/api/segments/<int:hook_id>/hook-join", methods=["GET", "POST"])
def api_hook_join(hook_id):
    """POST {"transition": xfade name}: join this hook as the opening of its highlight's ZOOMED clip (transition +
    sound effect). GET: status of that join ({"status": running|done|failed, "msg", "pct", "out", "error"})."""
    if request.method == "GET":
        return jsonify(hook_join.status(hook_id))
    res = hook_join.start(hook_id, ((request.json or {}).get("transition") or "").strip() or None)
    return jsonify(res), (400 if res.get("error") else 200)


@app.route("/api/segments/<int:seg_id>/docfilm", methods=["GET", "POST"])
def api_docfilm(seg_id):
    """POST {hooked, target_min, note, budget_usd, auto_advance, use_jre, bridge}: make a documentary (Creater Vid,
    dossier) that plays after this highlight + hook, then join them. GET: the latest job of this highlight."""
    if request.method == "GET":
        return jsonify(doc_extend.state(seg_id) or {})
    d = request.json or {}
    try:
        budget = float(d["budget_usd"]) if str(d.get("budget_usd") or "").strip() else None
        res = doc_extend.create(seg_id, d.get("hooked") or "", int(d.get("target_min") or 10), d.get("note") or "",
                                budget, bool(d.get("auto_advance", True)), bool(d.get("use_jre")), d.get("bridge") or "")
    except (TypeError, ValueError) as e:
        res = {"error": f"dữ liệu không hợp lệ: {e}"}
    return jsonify(res), (400 if res.get("error") else 200)


@app.route("/api/docfilm/<int:job_id>/<action>", methods=["POST"])
def api_docfilm_action(job_id, action):
    """rejoin {bridge?}: join again with the newest approved render (bridge given = that line, '' = Claude rewrites);
    stop: stop watching the Creater project."""
    d = request.json or {}
    if action == "rejoin":
        res = doc_extend.rejoin(job_id, d.get("bridge") if "bridge" in d else None)
    elif action == "stop":
        res = doc_extend.stop(job_id)
    else:
        res = {"error": "không rõ thao tác"}
    return jsonify(res), (400 if res.get("error") else 200)


@app.route("/api/episodes/<episode_id>/approve", methods=["POST"])
def api_approve(episode_id):
    orch = orchestrator()
    if not orch:
        return jsonify({"error": "pipeline chưa sẵn sàng"}), 503
    return jsonify(orch.approve(episode_id.upper()))


@app.route("/api/translate", methods=["POST"])
def api_translate():
    """Selected text -> Vietnamese with the official Google Cloud Translation API (user's key)."""
    from studio import translate
    data = request.json or {}
    text = (data.get("text") or "").strip()
    if not text:
        return jsonify({"error": "chưa chọn đoạn nào"}), 400
    try:
        return jsonify(translate.translate(text, target=data.get("target") or "vi"))
    except translate.NoKey:
        return jsonify({"error": "chưa có Google API key", "code": "no_key", "web_url": translate.web_url(text)}), 400
    except ValueError as e:
        return jsonify({"error": str(e), "web_url": translate.web_url(text)}), 400
    except Exception as e:  # noqa: BLE001
        return jsonify({"error": f"Google Dịch báo lỗi: {e}", "web_url": translate.web_url(text)}), 502


@app.route("/api/translate/open", methods=["POST"])
def api_translate_open():
    """Open translate.google.com in the default browser with the selected text (no key needed)."""
    import webbrowser
    from studio import translate
    text = ((request.json or {}).get("text") or "").strip()
    url = translate.web_url(text)
    try:
        webbrowser.open(url)
        return jsonify({"ok": True, "url": url})
    except Exception as e:  # noqa: BLE001
        return jsonify({"error": str(e), "url": url}), 500


@app.route("/api/translate/status")
def api_translate_status():
    from studio import translate
    return jsonify({"configured": translate.configured()})


@app.route("/api/segments/<int:seg_id>/title", methods=["POST"])
def api_title(seg_id):
    tw = title_worker()
    if not tw:
        return jsonify({"error": "bộ viết title chưa sẵn sàng"}), 503
    data = request.json or {}
    focus = (data.get("focus") or "").strip()[:2000]
    model = (data.get("model") or "").strip()
    if model and not re.fullmatch(r"[A-Za-z0-9._:-]{1,80}", model):
        return jsonify({"error": "tên model không hợp lệ"}), 400
    return jsonify(tw.enqueue(seg_id, focus=focus or None, model=model or None))


@app.route("/api/segments/<int:seg_id>/title/chat", methods=["POST"])
def api_title_chat(seg_id):
    """Message Claude about the title/metadata of one segment; it edits the latest result in the same session."""
    tw = title_worker()
    if not tw:
        return jsonify({"error": "bộ viết title chưa sẵn sàng"}), 503
    message = ((request.json or {}).get("message") or "").strip()
    if not message:
        return jsonify({"error": "chưa nhập nội dung"}), 400
    return jsonify(tw.enqueue_chat(seg_id, message[:4000]))


@app.route("/api/segments/<int:seg_id>/title/approve-thumb", methods=["POST"])
def api_title_approve_thumb(seg_id):
    """The user approved one thumbnail version (`run_id`, default the newest): apply it on Canva, save, export."""
    tw = title_worker()
    if not tw:
        return jsonify({"error": "bộ viết title chưa sẵn sàng"}), 503
    run_id = (request.json or {}).get("run_id")
    return jsonify(tw.enqueue_thumb_chat(seg_id, "", approve=True, run_id=int(run_id) if run_id else None))


@app.route("/api/segments/<int:seg_id>/thumb/canva", methods=["POST"])
def api_thumb_canva(seg_id):
    """Put a thumbnail version that has a mock but no Canva link on its own Canva copy (no export)."""
    tw = title_worker()
    if not tw:
        return jsonify({"error": "bộ viết title chưa sẵn sàng"}), 503
    run_id = (request.json or {}).get("run_id")
    return jsonify(tw.enqueue_thumb_chat(seg_id, "", push=True, run_id=int(run_id) if run_id else None))


@app.route("/api/segments/<int:seg_id>/thumb", methods=["POST"])
def api_thumb(seg_id):
    """"Tạo thumbnail": a new thumbnail version (frames, centre image, mock) from the current title result."""
    tw = title_worker()
    if not tw:
        return jsonify({"error": "bộ viết title chưa sẵn sàng"}), 503
    data = request.json or {}
    model = (data.get("model") or "").strip()
    if model and not re.fullmatch(r"[A-Za-z0-9._:-]{1,80}", model):
        return jsonify({"error": "tên model không hợp lệ"}), 400
    return jsonify(tw.enqueue_thumb(seg_id, (data.get("request") or "")[:4000], model or None))


@app.route("/api/segments/<int:seg_id>/thumb/chat", methods=["POST"])
def api_thumb_chat(seg_id):
    """Ask for a change to a thumbnail version (`run_id`, default the newest): the result is a new version."""
    tw = title_worker()
    if not tw:
        return jsonify({"error": "bộ viết title chưa sẵn sàng"}), 503
    data = request.json or {}
    message = (data.get("message") or "").strip()
    if not message:
        return jsonify({"error": "chưa nhập nội dung"}), 400
    run_id = data.get("run_id")
    return jsonify(tw.enqueue_thumb_chat(seg_id, message[:4000], run_id=int(run_id) if run_id else None))


@app.route("/api/segments/<int:seg_id>/title/cancel", methods=["POST"])
def api_title_cancel(seg_id):
    tw = title_worker()
    if not tw:
        return jsonify({"error": "bộ viết title chưa sẵn sàng"}), 503
    return jsonify(tw.cancel(seg_id))


@app.route("/api/episodes/<episode_id>/titles", methods=["POST"])
def api_titles_for_episode(episode_id):
    """Queue "Viết Title" for every highlight of the episode that has no finished title yet."""
    tw = title_worker()
    if not tw:
        return jsonify({"error": "bộ viết title chưa sẵn sàng"}), 503
    segs = db.rows("""SELECT s.id FROM segments s WHERE s.episode_id=? AND s.kind='highlight' AND s.start_sec IS NOT NULL
                      AND s.status!='archived' AND s.id NOT IN (SELECT segment_id FROM segment_titles WHERE status IN ('done','queued','running'))
                      ORDER BY COALESCE(s.content_rank, 999), s.rank""", (episode_id.upper(),))
    queued = [tw.enqueue(r["id"]) for r in segs]
    return jsonify({"queued": len([q for q in queued if q.get("run_id")]),
                    "message": f"đã xếp {len(queued)} đoạn vào hàng đợi viết title" if queued else "mọi đoạn đều đã có title"})


@app.route("/api/episodes/<episode_id>/stop", methods=["POST"])
def api_stop_episode(episode_id):
    orch = orchestrator()
    if not orch:
        return jsonify({"error": "pipeline chưa sẵn sàng"}), 503
    return jsonify(orch.request_stop(episode_id.upper()))


@app.route("/api/pipeline")
def api_pipeline():
    orch = orchestrator()
    return jsonify(orch.status() if orch else {"current": None, "queue": []})


@app.route("/pipeline")
def pipeline_page():
    orchestrator()
    return render_template("pipeline.html", page="pipeline")


@app.route("/api/pipeline/graph")
def api_pipeline_graph():
    orch = orchestrator()
    g = flow.graph(orch.status() if orch else None)
    g["worker"] = bool(orch)
    return jsonify(g)


@app.route("/api/pipeline/settings", methods=["POST"])
def api_pipeline_settings():
    return jsonify(flow.save_settings(request.json or {}))


# ---------------------------------------------------------------- dev chat (Pipeline page)
def _busy_reason() -> str | None:
    """Work a restart would cut short (long Creater films are left out: doc_extend resumes them after a restart)."""
    orch = orchestrator()
    if orch and orch.is_busy():
        st = orch.status()
        return f"pipeline {', '.join(st.get('running') or []) or ''} (chờ: {', '.join(st['queue']) or 'không'})"
    for sql in ("SELECT stage || ' ' || episode_id FROM jobs WHERE status='running' LIMIT 1",
                "SELECT 'viết title' FROM segment_titles WHERE status IN ('queued','running') LIMIT 1",
                "SELECT 'quét chủ đề' FROM topic_scans WHERE status IN ('queued','running','cutting') LIMIT 1",
                "SELECT 'video tổng hợp' FROM compile_jobs WHERE status IN ('queued','topic','scanning','arranging','building') LIMIT 1",
                "SELECT 'nối phim tài liệu' FROM docext_jobs WHERE status IN ('creating','joining') LIMIT 1"):
        try:
            r = db.scalar(sql)
        except Exception:  # noqa: BLE001
            r = None
        if r:
            return r
    return None


def _dev_run(prompt, **kw):
    from studio.pipeline import claude_runner
    return claude_runner.run(prompt, **kw)


_devchat = devchat.DevChat(
    app_name="Hổ Báo Studio", base_dir=config.BASE_DIR, store_dir=config.BASE_DIR / "work" / "_devchat",
    port=int(os.environ.get("PORT", config.PORT_STUDIO)), run_fn=_dev_run, md_fn=md_to_html,
    context_fn=flow.dev_context, busy_fn=_busy_reason,
    test_hint="chạy một bản chỉ-xem ở cổng khác (biến môi trường STUDIO_NO_WORKER=1 và PORT=5015, rồi "
              "`.venv\\Scripts\\python.exe -X utf8 app.py`; bản này dùng chung database thật nên chỉ đọc)")


@app.route("/api/devchat/<node>", methods=["GET", "POST"])
def api_devchat(node):
    if request.method == "GET":
        return jsonify(_devchat.state(node))
    bad = devchat.guard(request)
    if bad:
        return jsonify({"error": bad}), 403
    data = request.json or {}
    res = _devchat.send(node, data.get("text") or "", data.get("model") or "", data.get("effort") or "")
    return jsonify(res), (400 if res.get("error") else 200)


@app.route("/api/devchat/<node>/<action>", methods=["POST"])
def api_devchat_action(node, action):
    bad = devchat.guard(request)
    if bad:
        return jsonify({"error": bad}), 403
    if action == "stop":
        return jsonify(_devchat.stop(node))
    if action == "reset":
        res = _devchat.reset(node)
        return jsonify(res), (400 if res.get("error") else 200)
    return jsonify({"error": "không rõ thao tác"}), 400


@app.route("/api/app/restart", methods=["POST"])
def api_app_restart():
    bad = devchat.guard(request)
    if bad:
        return jsonify({"error": bad}), 403
    res = _devchat.restart()
    return jsonify(res), (409 if res.get("error") else 200)


@app.route("/api/admin/reset", methods=["POST"])
def api_reset():
    """Wipe episodes/segments/jobs (keeps settings + themes). Requires {"confirm": "XOA"}; backs up first."""
    data = request.json or {}
    if (data.get("confirm") or "").strip().upper() != "XOA":
        return jsonify({"error": "cần gõ XOA để xác nhận"}), 400
    orch = orchestrator()
    if orch and orch.is_busy():
        st = orch.status()
        return jsonify({"error": f"pipeline đang chạy {', '.join(st.get('running') or [])} (hàng đợi: {', '.join(st['queue']) or 'trống'}), "
                                 "bấm Dừng ở trang Hàng đợi trước"}), 409
    return jsonify(maintenance.reset_data())


@app.route("/api/podcasts", methods=["GET", "POST"])
def api_podcasts():
    """GET: every show profile with its counts. POST {id, name, host, ...}: add or update one (Cài đặt → Show podcast)."""
    if request.method == "GET":
        return jsonify(podcasts.overview())
    res = podcasts.save(request.json or {})
    return jsonify(res), (400 if res.get("error") else 200)


@app.route("/api/podcasts/<podcast_id>/delete", methods=["POST"])
def api_podcast_delete(podcast_id):
    res = podcasts.delete(podcast_id)
    return jsonify(res), (400 if res.get("error") else 200)


@app.route("/api/podcasts/test-name", methods=["POST"])
def api_podcast_test_name():
    """What Studio makes of a video file name with the current profiles."""
    name = ((request.json or {}).get("name") or "").strip()
    return jsonify(podcasts.test_name(name) if name else {"error": "chưa nhập tên file"})


@app.route("/api/channel-watch/<podcast_id>", methods=["GET", "POST"])
def api_channel_watch(podcast_id):
    """GET: the show's channel watch config + recent videos. POST: save it (Cài đặt → Show podcast → Quét kênh)."""
    if request.method == "GET":
        return jsonify({**channel_watch.status(podcast_id), "videos": channel_watch.videos(podcast_id)})
    res = channel_watch.save(podcast_id, request.json or {})
    return jsonify(res), (400 if res.get("error") else 200)


@app.route("/api/channel-watch/<podcast_id>/scan", methods=["POST"])
def api_channel_watch_scan(podcast_id):
    """Scan the channel now (blocks until yt-dlp has listed it, ~5-30 s; downloads run in the background)."""
    res = channel_watch.scan(podcast_id, orchestrator(), manual=True)
    return jsonify({**res, "videos": channel_watch.videos(podcast_id)}), (400 if res.get("error") else 200)


@app.route("/api/channel-watch/<podcast_id>/download", methods=["POST"])
def api_channel_watch_download(podcast_id):
    orch = orchestrator()
    if not orch:
        return jsonify({"error": "pipeline chưa sẵn sàng"}), 503
    res = channel_watch.download_one(podcast_id, (request.json or {}).get("video_id") or "", orch)
    return jsonify(res), (400 if res.get("error") else 200)


# ---------------------------------------------------------------- danh sách chờ (trang Hàng đợi)
@app.route("/api/link-queue", methods=["GET"])
def api_link_queue():
    return jsonify({"items": link_queue.items()})


@app.route("/api/link-queue/import", methods=["POST"])
def api_link_queue_import():
    """Dán cả loạt link (mỗi dòng một link) kèm show; không gọi YouTube ở bước này."""
    data = request.json or {}
    res = link_queue.add(data.get("text") or "", data.get("podcast_id"))
    if res.get("error"):
        return jsonify(res), 400
    return jsonify({**res, "items": link_queue.items()})


@app.route("/api/link-queue/<item_id>/download", methods=["POST"])
def api_link_queue_download(item_id):
    """Tải một mục qua Youtube Downloader rồi chạy pipeline; xong tự đánh dấu."""
    orch = orchestrator()
    if not orch:
        return jsonify({"error": "pipeline chưa sẵn sàng"}), 503
    res = link_queue.start(item_id, orch, (request.json or {}).get("podcast_id"))
    return jsonify(res), (400 if res.get("error") else 200)


@app.route("/api/link-queue/<item_id>/mark", methods=["POST"])
def api_link_queue_mark(item_id):
    status = (request.json or {}).get("status", "done")
    item = link_queue.mark(item_id, "done" if status == "done" else "pending")
    return jsonify({"item": item} if item else {"error": "Mục này không còn trong danh sách."}), (200 if item else 400)


@app.route("/api/link-queue/<item_id>/delete", methods=["POST"])
def api_link_queue_delete(item_id):
    return jsonify({"ok": link_queue.remove(item_id)})


@app.route("/api/link-queue/clear-done", methods=["POST"])
def api_link_queue_clear_done():
    return jsonify({"removed": link_queue.remove_done()})


@app.route("/api/intake", methods=["POST"])
def api_intake():
    """Register a video path or a YouTube URL and start the pipeline."""
    orch = orchestrator()
    if not orch:
        return jsonify({"error": "pipeline chưa sẵn sàng"}), 503
    data = request.json or {}
    pid = (data.get("podcast_id") or "").strip().upper() or None
    if data.get("path"):
        return jsonify(orch.intake_file(Path(data["path"]), pid))
    if data.get("url"):
        return jsonify(orch.intake_url(data["url"].strip(), pid))
    return jsonify({"error": "cần path hoặc url"}), 400


@app.route("/api/pick-file", methods=["POST"])
def api_pick_file():
    """Native file dialog (tkinter in a subprocess so it never blocks Flask)."""
    code = ("import tkinter as tk\nfrom tkinter import filedialog\nr=tk.Tk();r.withdraw();r.attributes('-topmost',True)\n"
            "print(filedialog.askopenfilename(title='Chọn video podcast', filetypes=[('Video','*.mp4 *.mkv *.webm *.mov')]))")
    try:
        out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=300)
        return jsonify({"path": out.stdout.strip()})
    except Exception as e:  # noqa: BLE001
        return jsonify({"error": str(e)}), 500


@app.route("/api/open-folder", methods=["POST"])
def api_open_folder():
    path = (request.json or {}).get("path", "")
    if path and os.path.exists(path):
        path = os.path.normpath(os.path.abspath(path))
        # one command string: as a list, Python quotes the whole "/select,<path>" (the path has spaces, e.g.
        # D:\DATA TOOL\...) and explorer then ignores it and opens Documents. It wants /select,"<path>".
        subprocess.Popen(f'explorer /select,"{path}"' if os.path.isfile(path) else f'explorer "{path}"')
        return jsonify({"ok": True})
    return jsonify({"error": "not found"}), 404


@app.route("/api/ask", methods=["POST"])
def api_ask():
    from studio.pipeline import claude_runner
    data = request.json or {}
    q = (data.get("q") or "").strip()
    if not q:
        return jsonify({"error": "câu hỏi trống"}), 400
    return jsonify(claude_runner.ask(q))


@app.route("/api/claude/probe", methods=["POST"])
def api_claude_probe():
    """Run one tiny Claude turn with the chosen model/effort and report login state + model actually used."""
    from studio.pipeline import claude_runner
    data = request.json or {}
    res = claude_runner.probe(model=(data.get("model") or "").strip() or None, effort=(data.get("effort") or "").strip() or None)
    return jsonify({k: res.get(k) for k in ("ok", "error", "result", "logged_in", "models", "model_usage", "usage",
                                             "cost_usd", "duration_sec", "summary")})


@app.route("/api/tag/pending")
def api_tag_pending():
    return jsonify(tagging.pending(limit=int(request.args.get("limit") or 40), episode_id=request.args.get("episode")))


# Start the workers as soon as the module is imported (Tool Manager imports `app` and calls app.run()).
if os.environ.get("STUDIO_NO_WORKER") != "1":
    orchestrator()
    title_worker()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", config.PORT_STUDIO))
    app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False, threaded=True)
