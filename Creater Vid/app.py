"""Creater Vid: two desks, documentaries and news videos, each with its own projects, workflow and rulebook (Flask UI +
JSON API). Started by Tool Manager (`from app import app`) or `python app.py` (port 5010)."""
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

from creater import config, db, devchat, news, notify, pipeline_graph, publish, store, tgbot, workflow  # noqa: E402
from creater.textfmt import md_to_html  # noqa: E402

config.LOG_DIR.mkdir(exist_ok=True)
config.WORK_DIR.mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.FileHandler(config.LOG_DIR / "creater.log", encoding="utf-8"), logging.StreamHandler()],
)
log = logging.getLogger("creater.app")

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
app.config["TEMPLATES_AUTO_RELOAD"] = True
app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 ** 3          # source uploads (PDF, audio, video) up to 2 GB per request
app.jinja_env.auto_reload = True
app.jinja_env.filters["md"] = md_to_html
app.jinja_env.filters["basename"] = lambda p: os.path.basename(str(p)) if p else ""
app.jinja_env.globals.update(flow_of=workflow.flow, KINDS=config.KINDS, VISIBILITY=publish.VISIBILITY,
                             yt_channels=publish.channels, yt_last=lambda kind: db.get_setting(f"yt_last_{kind}") or "")
db.init_db()
notify.register(app)     # 🔔 /api/notifications (bell in the header)
store.ensure_step_rows()          # a step added to a workflow (7 · metadata) reaches older projects
if os.environ.get("CREATER_NO_WORKER") != "1":
    from creater.portable import ProjectScanner     # project folders copied in from another machine register themselves
    ProjectScanner().start()

_worker = None
_worker_lock = threading.Lock()


def worker():
    """The Claude turn queue (one run at a time across all projects)."""
    global _worker
    if os.environ.get("CREATER_NO_WORKER") == "1":
        return None
    with _worker_lock:
        if _worker is None:
            try:
                from creater.worker import Worker
                _worker = Worker()
                _worker.start()
            except Exception as e:  # noqa: BLE001
                log.exception("worker unavailable: %s", e)
                _worker = False
    return _worker or None


_poller = None


def poller():
    """The news poller (keeps every enabled topic of the Tin tức page up to date)."""
    global _poller
    if os.environ.get("CREATER_NO_NEWS") == "1":
        return None
    with _worker_lock:
        if _poller is None:
            try:
                _poller = news.Poller()
                _poller.start()
            except Exception as e:  # noqa: BLE001
                log.exception("news poller unavailable: %s", e)
                _poller = False
    return _poller or None


def _project(pid: int) -> dict:
    p = store.get_project(pid)
    if not p:
        abort(404)
    return p


# The header: one tab per desk (each with its own pages), then the pages both desks share.
DESK_NAV = {
    "doc": [("projects", "/doc", "Dự án"), ("pipeline", "/doc/pipeline", "Pipeline"), ("rules", "/doc/rules", "Bộ quy tắc")],
    "news": [("feed", "/news", "Tin theo dõi"), ("projects", "/news/projects", "Dự án"), ("pipeline", "/news/pipeline", "Pipeline"),
             ("rules", "/news/rules", "Bộ quy tắc")],
}
SHARED_NAV = [("channels", "/channels", "Kênh YouTube"), ("activity", "/activity", "Hoạt động"), ("settings", "/settings", "Cài đặt")]


@app.context_processor
def _ctx():
    return {"desk_nav": DESK_NAV, "shared_nav": SHARED_NAV, "STATUS_LABELS": workflow.STATUS_LABELS}


def _kind(kind: str) -> str:
    if kind not in config.KINDS:
        abort(404)
    return kind


# ---------------------------------------------------------------- pages
@app.route("/")
def home():
    return redirect("/doc")


@app.route("/doc")
def doc_projects_page():
    return _projects_page("doc")


@app.route("/news/projects")
def news_projects_page():
    return _projects_page("news")


def _projects_page(kind: str):
    worker()
    archived = request.args.get("archived") == "1"
    s = db.all_settings()
    return render_template("projects.html", desk=kind, page="projects", kind=kind, flow=workflow.flow(kind),
                           projects=store.list_projects(kind, archived), archived=archived, s=s, root=str(store.root()),
                           archived_count=db.scalar("SELECT COUNT(*) FROM projects WHERE COALESCE(kind, 'doc')=? AND archived=1",
                                                    (kind,)))


def _project_context(p: dict, step_key: str | None) -> dict:
    rows = store.steps(p)
    fl = workflow.flow(p)
    if step_key not in fl.by_key:
        step_key = (store.current_step(rows) or rows[0])["step"]
    row = next(r for r in rows if r["step"] == step_key)
    d = store.project_dir(p)
    _, summary = workflow.check(step_key, d, p)
    kind = store.kind_of(p)
    up = _upload_context(p, row) if step_key == "metadata" else None
    return {"p": p, "kind": kind, "desk": kind, "flow": fl, "rules_url": f"/{kind}/rules", "up": up,
            "rows": rows, "row": row, "step": fl.by_key[step_key], "v": workflow.view(step_key, d, p),
            "summary": summary, "busy": store.busy_turn(p["id"]), "sources": store.sources(p),
            "costs": workflow.costs_spent(d), "film_ready": (d / "film" / "src" / "index.ts").exists()}


def _upload_context(p: dict, row: dict) -> dict:
    job, problems = publish.build_job(p)
    return {"state": publish.state(p), "job": job, "problems": problems, "approved": row.get("status") == "approved",
            "channel": publish.channel(p.get("yt_profile"), p.get("yt_channel"))}


@app.route("/p/<int:pid>")
def project_page(pid):
    worker()
    p = _project(pid)
    ctx = _project_context(p, request.args.get("step"))
    from creater import media
    return render_template("project.html", page="projects", msgs=store.messages(pid), events=store.events(pid, 30),
                           rules=store.current_rules(store.kind_of(p)), mitems=media.load(p)["items"], msum=media.summary(p),
                           tg=_tg_state(), **ctx)


@app.route("/p/<int:pid>/overview")
def project_overview(pid):
    from creater import overview
    p = _project(pid)
    return render_template("overview.html", page="projects", p=p, desk=store.kind_of(p),
                           data=overview.build(store.project_dir(p), p))


@app.route("/p/<int:pid>/blueprint")
def project_blueprint(pid):
    from creater import blueprint
    p = _project(pid)
    return render_template("blueprint.html", page="projects", p=p, desk=store.kind_of(p),
                           data=blueprint.build(store.project_dir(p), p))


@app.route("/p/<int:pid>/panel/<step>")
def project_panel(pid, step):
    p = _project(pid)
    return render_template("_step_panel.html", **_project_context(p, step))


@app.route("/p/<int:pid>/stepper")
def project_stepper(pid):
    p = _project(pid)
    return render_template("_stepper.html", **_project_context(p, request.args.get("step")))


@app.route("/p/<int:pid>/chat")
def project_chat(pid):
    p = _project(pid)
    return render_template("_chat.html", p=p, flow=workflow.flow(p), rules_url=f"/{store.kind_of(p)}/rules",
                           msgs=store.messages(pid), busy=store.busy_turn(pid))


@app.route("/p/<int:pid>/file")
def project_file(pid):
    p = _project(pid)
    target = store.safe_file(p, request.args.get("path", ""))
    if not target:
        abort(404)
    return send_file(str(target), conditional=True)


@app.route("/<kind>/pipeline")
def pipeline_page(kind):
    kind = _kind(kind)
    worker()
    return render_template("pipeline.html", desk=kind, page="pipeline", kind=kind, title="Pipeline")


@app.route("/api/<kind>/pipeline")
def api_pipeline_graph(kind):
    kind = _kind(kind)
    w = worker()
    g = pipeline_graph.graph(kind)
    g["worker"] = bool(w)
    return jsonify(g)


@app.route("/api/<kind>/pipeline/settings", methods=["POST"])
def api_pipeline_settings(kind):
    return jsonify(pipeline_graph.save_settings(_kind(kind), request.json or {}))


# ---------------------------------------------------------------- dev chat (Pipeline page)
def _busy_reason() -> str | None:
    """Work a restart would cut short: Claude turns of projects and a YouTube upload in progress."""
    r = db.row("""SELECT p.title, m.step FROM messages m JOIN projects p ON p.id=m.project_id
                  WHERE m.role='assistant' AND m.status IN ('queued','running') LIMIT 1""")
    if r:
        return f"lượt Claude của dự án “{r['title']}” ({r['step'] or 'chat'})"
    if publish._lock.locked():
        return "đang đăng video lên YouTube"
    return None


def _dev_run(prompt, **kw):
    from creater import claude_runner
    return claude_runner.run(prompt, **kw)


_devchat = devchat.DevChat(
    app_name="Creater Vid", base_dir=config.BASE_DIR, store_dir=config.BASE_DIR / "work" / "_devchat",
    port=int(os.environ.get("PORT", config.PORT)), run_fn=_dev_run, md_fn=md_to_html,
    context_fn=pipeline_graph.dev_context, busy_fn=_busy_reason,
    test_hint="chạy một bản chỉ-xem ở cổng khác (biến môi trường CREATER_NO_WORKER=1, CREATER_NO_NEWS=1, PORT=5013, rồi "
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


@app.route("/activity")
def activity_page():
    w = worker()
    turns = store.recent_turns(80)
    totals = db.rows("""SELECT p.id, p.title, p.cost_usd, p.dir, p.archived, COALESCE(p.kind, 'doc') AS kind,
                               (SELECT COUNT(*) FROM messages m WHERE m.project_id=p.id AND m.role='assistant') AS turns
                        FROM projects p ORDER BY p.updated_at DESC""")
    for t in totals:
        t["spent_usd"] = workflow.costs_spent(Path(t["dir"]))["total"] if Path(t["dir"]).exists() else 0
    return render_template("activity.html", page="activity", turns=turns, status=w.status() if w else None,
                           step_names={k: f.names() for k, f in workflow.FLOWS.items()},
                           totals=totals, events=store.events(None, 60),
                           sum_usd=sum(t["cost_usd"] or 0 for t in totals), sum_assets=sum(t["spent_usd"] for t in totals))


@app.route("/rules")
def rules_redirect():
    return redirect("/doc/rules")


@app.route("/<kind>/rules")
def rules_page(kind):
    book = _kind(kind)
    return render_template("rules.html", desk=book, page="rules", book=book, book_label=config.KINDS[book]["label"],
                           rules=store.current_rules(book), history=store.rules_history(book),
                           rules_path=str(store.rules_path(book)), flow=workflow.flow(book))


@app.route("/settings", methods=["GET", "POST"])
def settings_page():
    if request.method == "POST":
        checkboxes = ("auto_advance", "news_enabled", "tg_bot_on", "gemini_web_delogo")
        changed = request.form.get("_changed")
        # only fields the user edited: a page left open with old values must not overwrite newer settings
        keys = [k for k in changed.split(",") if k] if changed is not None else list(config.DEFAULT_SETTINGS)
        for key in keys:
            if key not in config.DEFAULT_SETTINGS:
                continue
            if key in config.SECRET_KEYS:          # a key field left empty keeps the saved key (Xóa key clears it)
                if request.form.get(key, "").strip():
                    db.set_setting(key, request.form[key].strip())
                continue
            if key in checkboxes:
                db.set_setting(key, "1" if key in request.form else "0")
            elif key in request.form:
                db.set_setting(key, request.form[key].strip())
        return redirect(url_for("settings_page", saved=1))
    from creater import health, providers
    items = health.checks()
    tgbot.pair_code()                        # the pairing code exists before the page shows it
    return render_template("settings.html", page="settings", s=db.all_settings(), saved=request.args.get("saved"),
                           checks=items, health=health.summary(items),
                           voices=providers.voices_map(), tts_models=providers.TTS_MODELS, aliases=providers.ALIASES,
                           tg_status=providers.status().get("telegram"),
                           projects_locked=bool(config.projects_root_locked()))


# ---------------------------------------------------------------- project API
@app.route("/api/projects", methods=["POST"])
def api_create():
    data = request.json or {}
    try:
        p = store.create_project(data)          # data["kind"]: doc (default) | news
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except OSError as e:
        return jsonify({"error": f"không tạo được thư mục dự án: {e}"}), 500
    out = {"ok": True, "id": p["id"], "url": url_for("project_page", pid=p["id"])}
    if data.get("start"):
        w = worker()
        out["queued"] = w.enqueue(p["id"], "", "step", "script") if w else {"error": "hàng đợi Claude chưa sẵn sàng"}
    return jsonify(out)


@app.route("/api/p/<int:pid>/update", methods=["POST"])
def api_update(pid):
    p = _project(pid)
    fields = store.clean_fields(request.json or {})
    store.update_project(pid, **fields)
    store.write_brief(store.get_project(pid))
    if fields:
        store.log_event(pid, "edit", "sửa thông tin: " + ", ".join(sorted(fields)))
    return jsonify({"ok": True, "archived": fields.get("archived", p.get("archived"))})


@app.route("/api/p/<int:pid>/delete", methods=["POST"])
def api_delete(pid):
    from creater.scaffold import unlink_node_modules
    from creater.util import send_to_trash
    p = _project(pid)
    data = request.json or {}
    if (data.get("confirm") or "").strip().upper() != "XOA":
        return jsonify({"error": "cần gõ XOA để xác nhận"}), 400
    if store.busy_turn(pid):
        return jsonify({"error": "dự án đang chạy, bấm Dừng trước"}), 409
    with db.tx() as c:
        c.execute("DELETE FROM messages WHERE project_id=?", (pid,))
        c.execute("DELETE FROM project_steps WHERE project_id=?", (pid,))
        c.execute("DELETE FROM events WHERE project_id=?", (pid,))
        c.execute("DELETE FROM projects WHERE id=?", (pid,))
    trashed = False
    if data.get("trash_folder") and Path(p["dir"]).exists():
        unlink_node_modules(Path(p["dir"]))     # the shared engine install must never go with the folder
        try:
            send_to_trash(Path(p["dir"]))
            trashed = True
        except OSError as e:
            return jsonify({"ok": True, "trashed": False, "warning": str(e)})
    return jsonify({"ok": True, "trashed": trashed})


def _enqueue(pid: int, text: str, kind: str, step: str | None):
    _project(pid)
    w = worker()
    if not w:
        return jsonify({"error": "hàng đợi Claude chưa sẵn sàng"}), 503
    res = w.enqueue(pid, (text or "")[:8000], kind, step)
    return jsonify(res), (400 if res.get("error") else 200)


@app.route("/api/p/<int:pid>/run", methods=["POST"])
def api_run_step(pid):
    data = request.json or {}
    return _enqueue(pid, data.get("note") or "", "step", data.get("step"))


@app.route("/api/p/<int:pid>/message", methods=["POST"])
def api_message(pid):
    data = request.json or {}
    return _enqueue(pid, data.get("text") or "", "chat", data.get("step"))


@app.route("/api/p/<int:pid>/redo", methods=["POST"])
def api_redo(pid):
    data = request.json or {}
    key, note = (data.get("key") or "").strip(), (data.get("note") or "").strip()
    if not key:
        return jsonify({"error": "thiếu ảnh"}), 400
    text = f"Làm lại ảnh `{key}`" + (f": {note}" if note else "") + ". Cập nhật 4_images/manifest.json và bảng xem nhanh."
    store.log_event(pid, "redo", f"yêu cầu làm lại ảnh {key}" + (f": {note}" if note else ""), "images")
    return _enqueue(pid, text, "chat", "images")


@app.route("/api/p/<int:pid>/cancel", methods=["POST"])
def api_cancel(pid):
    w = worker()
    if not w:
        return jsonify({"error": "hàng đợi Claude chưa sẵn sàng"}), 503
    return jsonify(w.cancel(pid))


@app.route("/api/p/<int:pid>/approve", methods=["POST"])
def api_approve(pid):
    p = _project(pid)
    step = (request.json or {}).get("step")
    if step not in workflow.flow(p).by_key:
        return jsonify({"error": "thiếu bước"}), 400
    try:
        res = store.approve(p, step)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"ok": True, **res})


@app.route("/api/p/<int:pid>/reopen", methods=["POST"])
def api_reopen(pid):
    p = _project(pid)
    step = (request.json or {}).get("step")
    if step not in workflow.flow(p).by_key:
        return jsonify({"error": "thiếu bước"}), 400
    store.reopen(p, step)
    return jsonify({"ok": True})


@app.route("/api/p/<int:pid>/state")
def api_state(pid):
    p = _project(pid)
    busy = store.busy_turn(pid)
    last = db.scalar("SELECT MAX(id) FROM messages WHERE project_id=?", (pid,))
    done = db.scalar("SELECT COUNT(*) FROM messages WHERE project_id=? AND status IN ('done','failed')", (pid,))
    steps_sig = "|".join(f"{r['step']}:{r['status']}" for r in db.rows(
        "SELECT step, status FROM project_steps WHERE project_id=? ORDER BY rowid", (pid,)))
    return jsonify({"busy": bool(busy), "status": busy["status"] if busy else None, "step": busy["step"] if busy else None,
                    "progress": busy["progress_msg"] if busy else None, "last_id": last, "done": done,
                    "steps": steps_sig, "cost_usd": p.get("cost_usd") or 0})


@app.route("/api/p/<int:pid>/sources", methods=["POST"])
def api_sources_upload(pid):
    p = _project(pid)
    files = request.files.getlist("files")
    if not files:
        return jsonify({"error": "chưa chọn file"}), 400
    names = [store.save_upload(p, f) for f in files if f and f.filename]
    store.log_event(pid, "sources", "thêm tư liệu: " + ", ".join(names), "script")
    return jsonify({"ok": True, "names": names})


@app.route("/api/p/<int:pid>/links", methods=["POST"])
def api_links(pid):
    p = _project(pid)
    store.save_links(p, (request.json or {}).get("text") or "")
    store.log_event(pid, "sources", "cập nhật danh sách link", "script")
    return jsonify({"ok": True})


@app.route("/api/p/<int:pid>/sources/delete", methods=["POST"])
def api_sources_delete(pid):
    from creater.util import send_to_trash
    p = _project(pid)
    name = (request.json or {}).get("name") or ""
    target = store.safe_file(p, f"sources/{Path(name).name}")
    if not target:
        return jsonify({"error": "không thấy file"}), 404
    try:
        send_to_trash(target)
    except OSError as e:
        return jsonify({"error": str(e)}), 500
    store.log_event(pid, "sources", f"bỏ tư liệu: {target.name}", "script")
    return jsonify({"ok": True})


@app.route("/api/p/<int:pid>/cast/choose", methods=["POST"])
def api_cast_choose(pid):
    p = _project(pid)
    data = request.json or {}
    try:
        choices = store.choose_candidate(p, (data.get("character") or "").strip(), (data.get("file") or "").strip() or None)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    store.recheck(p, "cast")
    store.log_event(pid, "cast", f"chọn ứng viên cho {data.get('character')}: {Path(data.get('file') or '-').name}", "cast")
    return jsonify({"ok": True, "choices": choices})


@app.route("/api/p/<int:pid>/footage/decide", methods=["POST"])
def api_footage_decide(pid):
    p = _project(pid)
    data = request.json or {}
    item, decision = (data.get("item") or "").strip(), data.get("decision")
    if not item:
        return jsonify({"error": "thiếu mục"}), 400
    store.decide_footage(p, item, decision)
    store.recheck(p, "footage")
    store.log_event(pid, "footage", f"{'duyệt' if decision == 'approved' else 'bỏ' if decision == 'rejected' else 'huỷ quyết định'} footage {item}", "footage")
    return jsonify({"ok": True})


@app.route("/api/p/<int:pid>/open", methods=["POST"])
def api_open(pid):
    p = _project(pid)
    sub = (request.json or {}).get("sub") or ""
    base = store.project_dir(p)
    target = (base / sub).resolve() if sub else base
    if base.resolve() not in (target, *target.parents) or not target.exists():
        return jsonify({"error": "không thấy thư mục"}), 404
    _reveal(str(target))
    return jsonify({"ok": True})


# ---------------------------------------------------------------- YouTube through GPM Login
@app.route("/channels")
def channels_page():
    return render_template("channels.html", page="channels", s=db.all_settings())


@app.route("/api/yt/profiles")
def api_yt_profiles():
    res = publish.gpm_profiles()
    if not res["ok"]:
        return jsonify({"error": res["error"]})
    return jsonify({"profiles": res["profiles"], "channels": publish.channels(), "scans": publish.scans()})


@app.route("/api/yt/scan", methods=["POST"])
def api_yt_scan():
    ids = [str(x) for x in (request.json or {}).get("ids") or []][:60]
    res = publish.gpm_profiles()
    if not res["ok"]:
        return jsonify({"error": res["error"]}), 503
    names = {p["id"]: p["name"] for p in res["profiles"] if p["browser"] == "chrome"}
    items = [(i, names[i]) for i in ids if i in names]
    if not items:
        return jsonify({"error": "không có profile Chrome nào trong danh sách chọn"}), 400
    busy = {k for k, v in publish.scans().items() if v.get("status") in ("queued", "running")}
    items = [x for x in items if x[0] not in busy]
    publish.scan_async(items)
    return jsonify({"ok": True, "message": f"đang quét {len(items)} profile (lần lượt từng cái)"})


@app.route("/api/yt/settings", methods=["POST"])
def api_yt_settings():
    data = request.json or {}
    for key in ("gpm_api", "yt_visibility", "yt_time_doc", "yt_time_news"):
        if key in data and str(data[key]).strip():
            if key == "yt_visibility" and data[key] not in publish.VISIBILITY:
                continue
            db.set_setting(key, str(data[key]).strip())
    return jsonify({"ok": True})


@app.route("/api/p/<int:pid>/upload", methods=["GET", "POST"])
def api_project_upload(pid):
    p = _project(pid)
    if request.method == "GET":
        job, problems = publish.build_job(p)
        return jsonify({"state": publish.state(p), "job": job, "problems": problems})
    data = request.json or {}
    row = store.step_row(pid, "metadata") or {}
    if row.get("status") != "approved":
        return jsonify({"error": "duyệt bước Metadata trước rồi mới đăng"}), 400
    override = {k: data.get(k) for k in ("visibility", "publish_at") if data.get(k)}
    res = publish.start(p, override, force=bool(data.get("force")))
    return jsonify(res), (400 if res.get("error") else 200)


# ---------------------------------------------------------------- rules API
@app.route("/api/rules/restore", methods=["POST"])
def api_rules_restore():
    try:
        res = store.restore_rules(int((request.json or {}).get("version") or 0))
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"ok": True, **res})


@app.route("/api/rules/v/<int:version>")
def api_rules_version(version):
    r = store.rules_version(version)
    if not r:
        abort(404)
    return jsonify({"version": r["version"], "num": r["num"], "book": r["book"], "body": r["body"],
                    "html": md_to_html(r["body"]), "source": r["source"], "note": r["note"], "created_at": r["created_at"]})


@app.route("/api/rules/<kind>", methods=["POST"])
def api_rules_save(kind):
    book = _kind(kind)
    data = request.json or {}
    body = (data.get("body") or "").strip()
    if len(body) < 50:
        return jsonify({"error": "bộ quy tắc trống hoặc quá ngắn"}), 400
    version = store.set_rules(book, body + "\n", source="manual", note=(data.get("note") or "sửa tay trên app")[:200])
    return jsonify({"ok": True, "version": version, "num": store.rules_version(version)["num"]})


# ---------------------------------------------------------------- news desk
@app.route("/news")
def news_page():
    worker()
    poller()
    from creater.news_fetch import KINDS, SIDES
    return render_template("news.html", desk="news", page="feed", s=db.all_settings(), kinds=KINDS, sides=SIDES,
                           audiences=news.AUDIENCES, presets={k: v["label"] for k, v in news.PRESETS.items()},
                           video_kinds=news.VIDEO_KINDS, digest={"stories": news.DIGEST_STORIES,
                                                                 "target_sec": news.DIGEST_TARGET_SEC})


def _topic(tid: int) -> dict:
    t = news.get_topic(tid)
    if not t:
        abort(404)
    return t


@app.route("/api/news/topics")
def api_news_topics():
    p = poller()
    busy = set(p.polling()) if p else set()
    topics = news.list_topics()
    for t in topics:
        t["polling"] = t["id"] in busy
    return jsonify({"topics": topics, "enabled": db.setting_bool("news_enabled"), "poller": bool(p)})


@app.route("/api/news/topics", methods=["POST"])
def api_news_topic_create():
    try:
        tid = news.create_topic(request.json or {})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    p = poller()
    if p:
        p.poll_now(tid)
    return jsonify({"ok": True, "id": tid})


@app.route("/api/news/topics/<int:tid>")
def api_news_topic(tid):
    return jsonify({"topic": _topic(tid), "sources": news.sources(tid)})


@app.route("/api/news/topics/<int:tid>", methods=["POST"])
def api_news_topic_update(tid):
    _topic(tid)
    news.update_topic(tid, request.json or {})
    return jsonify({"ok": True, "topic": news.get_topic(tid)})


@app.route("/api/news/topics/<int:tid>/delete", methods=["POST"])
def api_news_topic_delete(tid):
    _topic(tid)
    news.delete_topic(tid)
    return jsonify({"ok": True})


@app.route("/api/news/topics/<int:tid>/poll", methods=["POST"])
def api_news_poll(tid):
    _topic(tid)
    p = poller()
    if not p:
        return jsonify({"error": "luồng cập nhật tin chưa chạy"}), 503
    return jsonify(p.poll_now(tid))


@app.route("/api/news/topics/<int:tid>/digest")
def api_news_digest(tid):
    """Items for a 24-hour digest of a topic (the most covered events), for the user to review before making the video."""
    _topic(tid)
    try:
        hours = max(1, min(168, int(request.args.get("hours") or 24)))
        stories = max(1, min(20, int(request.args.get("stories") or news.DIGEST_STORIES)))   # ≤ 2 items each, ≤ 40
    except ValueError:
        return jsonify({"error": "giờ / số sự kiện không hợp lệ"}), 400
    return jsonify(news.digest_pick(tid, hours, stories, (request.args.get("focus") or "").strip()[:500]))


@app.route("/api/news/topics/<int:tid>/seen", methods=["POST"])
def api_news_seen_all(tid):
    _topic(tid)
    return jsonify({"ok": True, "count": news.mark_all_seen(tid)})


@app.route("/api/news/topics/<int:tid>/sources", methods=["POST"])
def api_news_source_add(tid):
    _topic(tid)
    try:
        sid = news.add_source(tid, request.json or {})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"ok": True, "id": sid})


@app.route("/api/news/sources/<int:sid>", methods=["POST"])
def api_news_source_update(sid):
    try:
        news.update_source(sid, request.json or {})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"ok": True})


@app.route("/api/news/sources/<int:sid>/delete", methods=["POST"])
def api_news_source_delete(sid):
    news.delete_source(sid)
    return jsonify({"ok": True})


@app.route("/api/news/sources/test", methods=["POST"])
def api_news_source_test():
    data = request.json or {}
    if (data.get("kind") or "") not in ("rss", "telegram", "bing", "gnews") or not (data.get("url") or "").strip():
        return jsonify({"ok": False, "error": "cần loại nguồn và địa chỉ"}), 400
    return jsonify(news.test_source(data["kind"], data["url"], data.get("language") or "ru", data.get("keywords")))


@app.route("/api/news/items")
def api_news_items():
    tid = request.args.get("topic", type=int)
    _topic(tid or 0)
    return jsonify({"items": news.items(tid, request.args.get("state") or "", request.args.get("q") or "",
                                        request.args.get("side") or "", min(request.args.get("limit", 400, type=int), 1000))})


@app.route("/api/news/story/<int:story_id>")
def api_news_story(story_id):
    return jsonify({"items": news.story_items(story_id)})


@app.route("/api/news/items/state", methods=["POST"])
def api_news_items_state():
    data = request.json or {}
    return jsonify({"ok": True, "count": news.set_state(data.get("ids") or [], data.get("state") or "")})


@app.route("/api/news/items/<int:iid>/body")
def api_news_item_body(iid):
    try:
        res = news.ensure_body(iid)
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    news.mark_seen([iid])
    return jsonify(res)


@app.route("/api/news/make-project", methods=["POST"])
def api_news_make_project():
    data = request.json or {}
    try:
        p = news.make_project(data.get("ids") or [], data)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except OSError as e:
        return jsonify({"error": f"không tạo được thư mục dự án: {e}"}), 500
    out = {"ok": True, "id": p["id"], "url": url_for("project_page", pid=p["id"])}
    if data.get("start"):
        w = worker()
        out["queued"] = w.enqueue(p["id"], "", "step", "script") if w else {"error": "hàng đợi Claude chưa sẵn sàng"}
    return jsonify(out)


# ---------------------------------------------------------------- setup, monitoring
@app.route("/api/quota")
def api_quota():
    """The quota bar: Claude plan limits, ElevenLabs characters, fal balance, what the app spent (creater/quota.py)."""
    from creater import quota
    return jsonify(quota.gather(force=request.args.get("refresh") == "1"))


@app.route("/api/status")
def api_status():
    w = worker()
    st = w.status() if w else {"current": None, "queue": []}
    return jsonify({"worker": bool(w), **st,
                    "projects": db.scalar("SELECT COUNT(*) FROM projects WHERE archived=0"),
                    "cost_usd": db.scalar("SELECT COALESCE(SUM(cost_usd),0) FROM projects")})


@app.route("/api/health")
def api_health():
    from creater import health
    items = health.checks()
    return jsonify({"checks": items, **health.summary(items), "jobs": health.jobs()})


@app.route("/api/setup/<job>", methods=["POST"])
def api_setup(job):
    from creater import health
    res = health.start_job(job)
    return jsonify(res), (400 if res.get("error") else 200)


@app.route("/api/setup/jobs")
def api_setup_jobs():
    from creater import health
    return jsonify(health.jobs())


@app.route("/api/claude/probe", methods=["POST"])
def api_claude_probe():
    """One tiny Claude turn with the chosen model/effort: login state and the model that actually answers."""
    from creater import claude_runner
    data = request.json or {}
    res = claude_runner.probe(model=(data.get("model") or "").strip() or None, effort=(data.get("effort") or "").strip() or None)
    return jsonify({k: res.get(k) for k in ("ok", "error", "result", "logged_in", "models", "cost_usd", "duration_sec", "summary")})


# ---------------------------------------------------------------- generation APIs (ElevenLabs, fal.ai)
@app.route("/api/providers/<name>/check", methods=["POST"])
def api_provider_check(name):
    from creater import providers
    if name == "elevenlabs":
        return jsonify(providers.el_check())
    if name == "fal":
        return jsonify(providers.fal_check())
    if name == "openai":
        return jsonify(providers.openai_check())
    if name == "google":
        return jsonify(providers.google_check())
    abort(404)


@app.route("/api/providers/gemini-web/<action>", methods=["POST"])
def api_gemini_web(action):
    """login: a visible Chrome window on the app's Gemini profile (the user signs in, then closes it);
    status: signed in or not, checked without a window. Both run gen.py in its own process (Playwright)."""
    if action not in ("login", "status"):
        abort(404)
    cmd = [sys.executable, "-X", "utf8", str(config.GEN_PY), "gemini-web", action]
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    if action == "login":
        subprocess.Popen(cmd, cwd=str(config.BASE_DIR), creationflags=flags,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return jsonify({"ok": True, "message": "đã mở cửa sổ Chrome: đăng nhập Google rồi đóng cửa sổ"})
    try:
        out = subprocess.run(cmd, cwd=str(config.BASE_DIR), capture_output=True, text=True, encoding="utf-8",
                             errors="replace", timeout=150, creationflags=flags).stdout
    except subprocess.TimeoutExpired:
        return jsonify({"ok": False, "error": "kiểm tra quá 150 s"})
    line = next((x for x in reversed(out.splitlines()) if x.startswith("RESULT ")), "")
    try:
        return jsonify(json.loads(line[7:]))
    except ValueError:
        return jsonify({"ok": False, "error": (out.strip().splitlines() or ["không rõ"])[-1][:300]})


@app.route("/api/providers/<name>/key", methods=["POST"])
def api_provider_key(name):
    """Save a key typed on the Settings page (the Check button saves before it checks). Answers only the hint."""
    from creater import providers
    if f"{name}_api_key" not in config.SECRET_KEYS:
        abort(404)
    data = request.json or {}
    value = (data.get("key") or "").strip().strip("\"'").strip()
    if value:
        if any(ch.isspace() for ch in value) or len(value) < 20:
            return jsonify({"error": "key không hợp lệ (có dấu cách hoặc quá ngắn): dán đúng một dòng key"}), 400
        providers.set_key(f"{name}_api_key", value)
    if name in ("openai", "elevenlabs") and "base_url" in data:
        base = (data.get("base_url") or "").strip().rstrip("/") or config.DEFAULT_SETTINGS[f"{name}_base_url"]
        if not base.startswith(("http://", "https://")):
            return jsonify({"error": "Base URL phải bắt đầu bằng https://"}), 400
        db.set_setting(f"{name}_base_url", base)
    saved = providers.key(f"{name}_api_key")
    return jsonify({"ok": True, "hint": ("••••" + saved[-4:]) if saved else ""})


@app.route("/api/providers/elevenlabs/keys", methods=["GET", "POST"])
def api_el_keys():
    """Several ElevenLabs keys: list them (with the credit last read), add one (POST {label, key, base_url})."""
    from creater import providers
    if request.method == "POST":
        data = request.json or {}
        try:
            providers.el_key_add(data.get("label", ""), data.get("key", ""), data.get("base_url", ""))
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
    return jsonify({"keys": providers.el_keys()})


@app.route("/api/providers/elevenlabs/keys/<key_id>/<action>", methods=["POST"])
def api_el_key_action(key_id, action):
    """check (key_id 'all' = every key), use, delete."""
    from creater import providers, quota
    try:
        if action == "check":
            providers.el_key_check(None if key_id == "all" else key_id)
        elif action == "use":
            providers.el_key_use(key_id)
        elif action == "delete":
            providers.el_key_remove(key_id)
        else:
            abort(404)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    quota._cache.pop("elevenlabs", None)      # the quota bar shows the key now in use
    return jsonify({"keys": providers.el_keys()})


@app.route("/api/providers/<name>/clear-key", methods=["POST"])
def api_provider_clear(name):
    from creater import providers
    if f"{name}_api_key" not in config.SECRET_KEYS:
        abort(404)
    providers.set_key(f"{name}_api_key", "")
    return jsonify({"ok": True})


@app.route("/api/telegram/<action>", methods=["POST"])
def api_telegram(action):
    """Sign in to the Telegram API with the user's own account (the user types phone, code and password)."""
    from creater import media, providers
    data = request.json or {}
    if action == "send-code":
        api_id = str(data.get("api_id") or "").strip()
        api_hash = str(data.get("api_hash") or "").strip()
        phone = str(data.get("phone") or "").replace(" ", "").strip()
        if api_id:
            if not api_id.isdigit():
                return jsonify({"ok": False, "error": "api_id là một dãy số (my.telegram.org → API development tools)"}), 400
            db.set_setting("telegram_api_id", api_id)
        if api_hash:
            if len(api_hash) != 32 or not api_hash.isalnum():
                return jsonify({"ok": False, "error": "api_hash phải là 32 ký tự chữ và số"}), 400
            providers.set_key("telegram_api_hash", api_hash)
        if phone:
            db.set_setting("telegram_phone", phone)
        res = media.tg_run(["send-code", "--phone", phone or db.get_setting("telegram_phone")])
    elif action == "sign-in":
        env = {"TG_CODE": str(data.get("code") or "").strip(), "TG_PASSWORD": str(data.get("password") or "")}
        res = media.tg_run(["sign-in"], env=env)
    elif action in ("status", "logout"):
        res = media.tg_run([action])
    else:
        abort(404)
    if action != "send-code" or not res.get("ok"):
        providers._save_status("telegram", {k: res.get(k) for k in ("ok", "authorized", "me", "error")} | {"at": providers._now()})
    return jsonify(res)


@app.route("/p/<int:pid>/media")
def project_media(pid):
    from creater import media
    p = _project(pid)
    return render_template("_media.html", p=p, mitems=media.load(p)["items"], msum=media.summary(p), tg=_tg_state())


def _tg_state() -> dict:
    from creater import providers
    return providers.status().get("telegram") or {}


@app.route("/api/p/<int:pid>/media/<action>", methods=["POST"])
def api_project_media(pid, action):
    from creater import media
    p = _project(pid)
    data = request.json or {}
    try:
        if action == "decide":
            decision = data.get("decision") if data.get("decision") in ("approved", "rejected") else None
            item = media.decide(p, data.get("id") or "", decision)
            store.log_event(pid, "sources", f"{'duyệt' if decision == 'approved' else 'bỏ' if decision == 'rejected' else 'hoàn tác'} "
                                            f"nguyên liệu {item['id']} ({item.get('kind')}, {item.get('source')})", "footage")
        elif action == "approve-clean":
            n = media.approve_clean(p)
            store.log_event(pid, "sources", f"duyệt {n} nguyên liệu không có cảnh báo", "footage")
        elif action == "retry":
            media.retry(p, data.get("id") or "")
        else:
            abort(404)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"ok": True, "summary": media.summary(p)})


@app.route("/api/providers/voices")
def api_provider_voices():
    from creater import providers
    try:
        if request.args.get("mine") == "1":
            voices = providers.el_my_voices()
        else:
            voices = providers.el_library_voices(request.args.get("lang") or None, request.args.get("q") or None,
                                                 request.args.get("gender") or None, 40)
    except providers.ApiError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"voices": voices})


@app.route("/api/providers/voice", methods=["POST"])
def api_provider_voice():
    from creater import providers
    data = request.json or {}
    try:
        voices = providers.set_voice(data.get("lang") or "", data.get("voice"))
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"ok": True, "voices": voices})


@app.route("/api/providers/fal/models")
def api_provider_fal_models():
    from creater import providers
    try:
        return jsonify({"models": providers.fal_search(request.args.get("q") or "", request.args.get("category") or "", 20)})
    except providers.ApiError as e:
        return jsonify({"error": str(e)}), 400


def _reveal(path: str) -> None:
    """Explorer at a folder, or at the folder of a file with the file selected. One command string: as a list,
    Python quotes the whole "/select,<path>" (paths have spaces, e.g. D:\\DATA TOOL\\...) and explorer then
    ignores it and opens Documents. It wants /select,"<path>"."""
    path = os.path.normpath(os.path.abspath(path))
    subprocess.Popen(f'explorer /select,"{path}"' if os.path.isfile(path) else f'explorer "{path}"')


@app.route("/api/open-folder", methods=["POST"])
def api_open_folder():
    path = (request.json or {}).get("path", "")
    if path and os.path.exists(path):
        _reveal(path)
        return jsonify({"ok": True})
    return jsonify({"error": "không thấy"}), 404


@app.route("/api/tgbot/<action>", methods=["POST"])
def api_tgbot(action):
    """The approval bot: check the token, send a test message, forget the paired chat."""
    data = request.json or {}
    try:
        if action == "check":
            tok = (data.get("token") or "").strip()
            res = tgbot.check(tok or None)
            if tok:
                db.set_setting("tg_bot_token", tok)
            return jsonify(res | {"chat": db.get_setting("tg_bot_chat_name") or "", "pair": tgbot.pair_code()})
        if action == "test":
            if not tgbot.chat_id():
                return jsonify({"ok": False, "error": "chưa ghép chat: gửi /start <mã> cho bot"}), 400
            tgbot.send("✓ Creater Vid: bot hoạt động. Gõ /cho để xem các bước đang chờ duyệt.")
            return jsonify({"ok": True})
        if action == "unpair":
            tgbot.unpair()
            return jsonify({"ok": True, "pair": tgbot.pair_code()})
    except tgbot.TgError as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    abort(404)


# Start the worker and the news poller as soon as the module is imported (Tool Manager imports `app` and calls app.run()).
if os.environ.get("CREATER_NO_WORKER") != "1":
    worker()
poller()
if os.environ.get("CREATER_NO_WORKER") != "1":
    tgbot.start(worker)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", config.PORT))
    app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False, threaded=True)
