"""JRE Studio: Flask UI + JSON API. Started by Tool Manager (`from app import app`) or `python app.py`."""
from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import threading
from pathlib import Path

from flask import Flask, abort, jsonify, redirect, render_template, request, send_file, url_for

sys.path.insert(0, str(Path(__file__).resolve().parent))

from studio import config, db, export as export_mod, ingest, maintenance, search, tagging  # noqa: E402
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

app = Flask(__name__, template_folder="templates", static_folder="static")
app.config["TEMPLATES_AUTO_RELOAD"] = True      # template fixes apply without restarting the tool
app.jinja_env.auto_reload = True
app.jinja_env.filters["md"] = md_to_html
app.jinja_env.filters["basename"] = lambda p: os.path.basename(p) if p else ""
db.init_db()

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
                from studio.pipeline.titles import TitleWorker
                _title_worker = TitleWorker()
                _title_worker.start()
            except Exception as e:  # noqa: BLE001
                log.warning("title worker unavailable: %s", e)
                _title_worker = False
    return _title_worker or None


def _attach_titles(episode_id: str, segments: list[dict]) -> None:
    from studio.pipeline.titles import runs_for_episode
    runs = runs_for_episode(episode_id)
    for s in segments:
        r = runs.get(s["id"]) or {}
        s["title_run"] = r.get("latest")
        s["title_done"] = r.get("done")


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
    return {"nav": [("queue", "Hàng đợi"), ("episodes", "Tập"), ("search", "Tìm kiếm"),
                    ("compilations", "Compilation"), ("ask", "Hỏi AI"), ("settings", "Cài đặt")]}


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
    return render_template("queue.html", page="queue", episodes=episodes, jobs=jobs, pipe=pipe,
                           media_root=db.get_setting("media_root"))


@app.route("/episodes")
def episodes_page():
    episodes = db.rows(
        """SELECT e.*, (SELECT COUNT(*) FROM segments s WHERE s.episode_id=e.id AND s.kind='highlight' AND s.status!='archived') AS highlights,
                  (SELECT COUNT(*) FROM segments s WHERE s.episode_id=e.id AND s.kind='hook' AND s.status!='archived') AS hooks,
                  (SELECT COUNT(*) FROM segments s WHERE s.episode_id=e.id AND s.clip_path IS NOT NULL AND s.status!='archived') AS cut,
                  (SELECT COUNT(*) FROM segments s WHERE s.episode_id=e.id AND s.clip_zoomed_path IS NOT NULL AND s.status!='archived') AS zoomed,
                  (SELECT COUNT(*) FROM segments s WHERE s.episode_id=e.id AND s.analysis_md IS NOT NULL AND s.status!='archived') AS analysed
           FROM episodes e ORDER BY e.podcast_id, e.number DESC""")
    return render_template("episodes.html", page="episodes", episodes=episodes)


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
        elif s["kind"] == "hook":
            highlights.append(s)      # orphan hook, show inline
        else:
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
                           deleted=deleted, title_skill=db.get_setting("title_skill"),
                           title_model=db.get_setting("claude_model_title"))


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
        "theme": args.get("theme") or None, "topic": args.get("topic") or None,
        "unused": args.get("unused") == "1", "limit": int(args.get("limit") or 50),
    }
    results = search.search(q, **filters) if (q or any(v for k, v in filters.items() if k != "limit")) else []
    themes = db.rows("SELECT slug, name_vi FROM themes ORDER BY slug")
    episodes = db.rows("SELECT id, guest FROM episodes ORDER BY podcast_id, number DESC")
    return render_template("search.html", page="search", q=q, f=args, results=results, themes=themes, episodes=episodes)


@app.route("/compilations")
def compilations_page():
    comps = db.rows("""SELECT c.*, (SELECT COUNT(*) FROM compilation_items ci WHERE ci.compilation_id=c.id) AS n
                       FROM compilations c ORDER BY c.id DESC""")
    for c in comps:
        c["items"] = db.rows("""SELECT ci.ord, ci.role, s.id, s.episode_id, s.title, s.start_hms, s.end_hms
                                FROM compilation_items ci JOIN segments s ON s.id=ci.segment_id
                                WHERE ci.compilation_id=? ORDER BY ci.ord""", (c["id"],))
    return render_template("compilations.html", page="compilations", comps=comps)


@app.route("/ask")
def ask_page():
    return render_template("ask.html", page="ask")


@app.route("/settings", methods=["GET", "POST"])
def settings_page():
    if request.method == "POST":
        checkboxes = ("zoom_hooks", "review_gate", "delete_original_clip_after_zoom", "watch_enabled")
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
    return render_template("settings.html", page="settings", s=db.all_settings(), saved=request.args.get("saved"),
                           claude=_claude_status(), gt_configured=translate.configured())


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


@app.route("/api/export", methods=["POST"])
def api_export():
    data = request.json or {}
    ids = [int(i) for i in data.get("ids", [])]
    fmt = data.get("format", "pool")
    theme = data.get("theme") or "selection"
    out_dir = Path(data.get("out_dir") or db.get_setting("media_root"))
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
    return jsonify(tw.enqueue(seg_id))


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


@app.route("/api/admin/reset", methods=["POST"])
def api_reset():
    """Wipe episodes/segments/jobs (keeps settings + themes). Requires {"confirm": "XOA"}; backs up first."""
    data = request.json or {}
    if (data.get("confirm") or "").strip().upper() != "XOA":
        return jsonify({"error": "cần gõ XOA để xác nhận"}), 400
    orch = orchestrator()
    if orch and orch.is_busy():
        st = orch.status()
        return jsonify({"error": f"pipeline đang chạy {st['current'] or ''} (hàng đợi: {', '.join(st['queue']) or 'trống'}), "
                                 "bấm Dừng ở trang Hàng đợi trước"}), 409
    return jsonify(maintenance.reset_data())


@app.route("/api/intake", methods=["POST"])
def api_intake():
    """Register a video path or a YouTube URL and start the pipeline."""
    orch = orchestrator()
    if not orch:
        return jsonify({"error": "pipeline chưa sẵn sàng"}), 503
    data = request.json or {}
    if data.get("path"):
        return jsonify(orch.intake_file(Path(data["path"])))
    if data.get("url"):
        return jsonify(orch.intake_url(data["url"].strip()))
    return jsonify({"error": "cần path hoặc url"}), 400


@app.route("/api/pick-file", methods=["POST"])
def api_pick_file():
    """Native file dialog (tkinter in a subprocess so it never blocks Flask)."""
    code = ("import tkinter as tk\nfrom tkinter import filedialog\nr=tk.Tk();r.withdraw();r.attributes('-topmost',True)\n"
            "print(filedialog.askopenfilename(title='Chọn video JRE', filetypes=[('Video','*.mp4 *.mkv *.webm *.mov')]))")
    try:
        out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=300)
        return jsonify({"path": out.stdout.strip()})
    except Exception as e:  # noqa: BLE001
        return jsonify({"error": str(e)}), 500


@app.route("/api/open-folder", methods=["POST"])
def api_open_folder():
    path = (request.json or {}).get("path", "")
    if path and os.path.exists(path):
        subprocess.Popen(["explorer", "/select," + path] if os.path.isfile(path) else ["explorer", path])
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
