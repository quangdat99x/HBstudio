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

from studio import config, db, export as export_mod, ingest, search, tagging  # noqa: E402
from studio.analysis import import_markdown  # noqa: E402
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
app.jinja_env.filters["md"] = md_to_html
app.jinja_env.filters["basename"] = lambda p: os.path.basename(p) if p else ""
db.init_db()

_orchestrator = None
_orch_lock = threading.Lock()


def orchestrator():
    """Lazily start the pipeline worker (module is optional until phase 2 lands)."""
    global _orchestrator
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
        """SELECT e.*, (SELECT COUNT(*) FROM segments s WHERE s.episode_id=e.id AND s.kind='highlight') AS highlights,
                  (SELECT COUNT(*) FROM segments s WHERE s.episode_id=e.id AND s.clip_zoomed_path IS NOT NULL) AS zoomed
           FROM episodes e ORDER BY e.updated_at DESC""")
    jobs = db.rows("SELECT * FROM jobs ORDER BY id DESC LIMIT 60")
    return render_template("queue.html", page="queue", episodes=episodes, jobs=jobs,
                           media_root=db.get_setting("media_root"))


@app.route("/episodes")
def episodes_page():
    episodes = db.rows(
        """SELECT e.*, (SELECT COUNT(*) FROM segments s WHERE s.episode_id=e.id AND s.kind='highlight') AS highlights,
                  (SELECT COUNT(*) FROM segments s WHERE s.episode_id=e.id AND s.kind='hook') AS hooks,
                  (SELECT COUNT(*) FROM segments s WHERE s.episode_id=e.id AND s.clip_path IS NOT NULL) AS cut,
                  (SELECT COUNT(*) FROM segments s WHERE s.episode_id=e.id AND s.clip_zoomed_path IS NOT NULL) AS zoomed,
                  (SELECT COUNT(*) FROM segments s WHERE s.episode_id=e.id AND s.analysis_md IS NOT NULL) AS analysed
           FROM episodes e ORDER BY e.podcast_id, e.number DESC""")
    return render_template("episodes.html", page="episodes", episodes=episodes)


@app.route("/episodes/<episode_id>")
def episode_page(episode_id):
    ep = db.row("SELECT * FROM episodes WHERE id=?", (episode_id.upper(),))
    if not ep:
        abort(404)
    segs = db.rows("SELECT * FROM segments WHERE episode_id=? ORDER BY COALESCE(rank, 999), start_sec", (ep["id"],))
    by_id = {s["id"]: s for s in segs}
    for s in segs:
        s["topics"] = [r["name"] for r in db.rows(
            "SELECT t.name FROM segment_topics st JOIN topics t ON t.id=st.topic_id WHERE st.segment_id=?", (s["id"],))]
        s["themes"] = [r["slug"] for r in db.rows(
            "SELECT th.slug FROM segment_themes st JOIN themes th ON th.id=st.theme_id WHERE st.segment_id=?", (s["id"],))]
        s["hooks"] = []
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
    jobs = db.rows("SELECT * FROM jobs WHERE episode_id=? ORDER BY id DESC LIMIT 20", (ep["id"],))
    return render_template("episode.html", page="episodes", ep=ep, segments=highlights, profile=profile, jobs=jobs)


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
        for key in config.DEFAULT_SETTINGS:
            if key in request.form:
                db.set_setting(key, request.form[key].strip())
            elif key in ("zoom_hooks", "review_gate", "delete_original_clip_after_zoom", "watch_enabled"):
                db.set_setting(key, "0")
        return redirect(url_for("settings_page", saved=1))
    return render_template("settings.html", page="settings", s=db.all_settings(), saved=request.args.get("saved"),
                           claude=_claude_status())


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
        "highlights": db.scalar("SELECT COUNT(*) FROM segments WHERE kind='highlight'"),
        "hooks": db.scalar("SELECT COUNT(*) FROM segments WHERE kind='hook'"),
        "zoomed": db.scalar("SELECT COUNT(*) FROM segments WHERE clip_zoomed_path IS NOT NULL"),
        "with_analysis": db.scalar("SELECT COUNT(*) FROM segments WHERE analysis_md IS NOT NULL"),
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


# Start the pipeline worker as soon as the module is imported (Tool Manager imports `app` and calls app.run()).
if os.environ.get("STUDIO_NO_WORKER") != "1":
    orchestrator()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", config.PORT_STUDIO))
    app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False, threaded=True)
