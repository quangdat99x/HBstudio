"""Creater Vid: documentary film workflow (Flask UI + JSON API). Started by Tool Manager (`from app import app`) or
`python app.py` (port 5010)."""
from __future__ import annotations

import logging
import os
import subprocess
import sys
import threading
from pathlib import Path

from flask import Flask, abort, jsonify, redirect, render_template, request, send_file, url_for

sys.path.insert(0, str(Path(__file__).resolve().parent))

from creater import config, db, store, workflow  # noqa: E402
from creater.textfmt import md_to_html  # noqa: E402

config.LOG_DIR.mkdir(exist_ok=True)
config.WORK_DIR.mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.FileHandler(config.LOG_DIR / "creater.log", encoding="utf-8"), logging.StreamHandler()],
)
log = logging.getLogger("creater.app")

app = Flask(__name__, template_folder="templates", static_folder="static")
app.config["TEMPLATES_AUTO_RELOAD"] = True
app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 ** 3          # source uploads (PDF, audio, video) up to 2 GB per request
app.jinja_env.auto_reload = True
app.jinja_env.filters["md"] = md_to_html
app.jinja_env.filters["basename"] = lambda p: os.path.basename(str(p)) if p else ""
db.init_db()

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


def _project(pid: int) -> dict:
    p = store.get_project(pid)
    if not p:
        abort(404)
    return p


@app.context_processor
def _ctx():
    return {"nav": [("projects", "/", "Dự án"), ("activity", "/activity", "Hoạt động"), ("rules", "/rules", "Bộ quy tắc"),
                    ("settings", "/settings", "Cài đặt")],
            "STEPS": workflow.STEPS, "STATUS_LABELS": workflow.STATUS_LABELS,
            "STEP_NAMES": {s.key: f"{s.num} · {s.name}" for s in workflow.STEPS}}


# ---------------------------------------------------------------- pages
@app.route("/")
def projects_page():
    worker()
    archived = request.args.get("archived") == "1"
    s = db.all_settings()
    return render_template("projects.html", page="projects", projects=store.list_projects(archived), archived=archived,
                           s=s, root=str(store.root()), archived_count=db.scalar("SELECT COUNT(*) FROM projects WHERE archived=1"))


def _project_context(p: dict, step_key: str | None) -> dict:
    rows = store.steps(p)
    if step_key not in workflow.BY_KEY:
        step_key = (store.current_step(rows) or rows[0])["step"]
    row = next(r for r in rows if r["step"] == step_key)
    d = store.project_dir(p)
    _, summary = workflow.check(step_key, d, p)
    return {"p": p, "rows": rows, "row": row, "step": workflow.BY_KEY[step_key], "v": workflow.view(step_key, d, p),
            "summary": summary, "busy": store.busy_turn(p["id"]), "sources": store.sources(p),
            "credits": workflow.credits_spent(d), "film_ready": (d / "film" / "src" / "index.ts").exists()}


@app.route("/p/<int:pid>")
def project_page(pid):
    worker()
    p = _project(pid)
    ctx = _project_context(p, request.args.get("step"))
    return render_template("project.html", page="projects", msgs=store.messages(pid), events=store.events(pid, 30),
                           rules=store.current_rules(), **ctx)


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
    return render_template("_chat.html", p=p, msgs=store.messages(pid), busy=store.busy_turn(pid))


@app.route("/p/<int:pid>/file")
def project_file(pid):
    p = _project(pid)
    target = store.safe_file(p, request.args.get("path", ""))
    if not target:
        abort(404)
    return send_file(str(target), conditional=True)


@app.route("/activity")
def activity_page():
    w = worker()
    turns = store.recent_turns(80)
    totals = db.rows("""SELECT p.id, p.title, p.cost_usd, p.dir, p.archived,
                               (SELECT COUNT(*) FROM messages m WHERE m.project_id=p.id AND m.role='assistant') AS turns
                        FROM projects p ORDER BY p.updated_at DESC""")
    for t in totals:
        t["credits"] = workflow.credits_spent(Path(t["dir"]))["total"] if Path(t["dir"]).exists() else 0
    return render_template("activity.html", page="activity", turns=turns, status=w.status() if w else None,
                           totals=totals, events=store.events(None, 60),
                           sum_usd=sum(t["cost_usd"] or 0 for t in totals), sum_credits=sum(t["credits"] for t in totals))


@app.route("/rules")
def rules_page():
    return render_template("rules.html", page="rules", rules=store.current_rules(), history=store.rules_history(),
                           rules_path=str(store.rules_path()))


@app.route("/settings", methods=["GET", "POST"])
def settings_page():
    if request.method == "POST":
        checkboxes = ("auto_advance",)
        changed = request.form.get("_changed")
        # only fields the user edited: a page left open with old values must not overwrite newer settings
        keys = [k for k in changed.split(",") if k] if changed is not None else list(config.DEFAULT_SETTINGS)
        for key in keys:
            if key not in config.DEFAULT_SETTINGS:
                continue
            if key in checkboxes:
                db.set_setting(key, "1" if key in request.form else "0")
            elif key in request.form:
                db.set_setting(key, request.form[key].strip())
        return redirect(url_for("settings_page", saved=1))
    from creater import health
    items = health.checks()
    return render_template("settings.html", page="settings", s=db.all_settings(), saved=request.args.get("saved"),
                           checks=items, health=health.summary(items), step_keys=config.STEP_SETTING_KEYS)


# ---------------------------------------------------------------- project API
@app.route("/api/projects", methods=["POST"])
def api_create():
    data = request.json or {}
    try:
        p = store.create_project(data)
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
    if step not in workflow.BY_KEY:
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
    if step not in workflow.BY_KEY:
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
    subprocess.Popen(["explorer", "/select," + str(target)] if target.is_file() else ["explorer", str(target)])
    return jsonify({"ok": True})


# ---------------------------------------------------------------- rules API
@app.route("/api/rules", methods=["POST"])
def api_rules_save():
    data = request.json or {}
    body = (data.get("body") or "").strip()
    if len(body) < 50:
        return jsonify({"error": "bộ quy tắc trống hoặc quá ngắn"}), 400
    version = store.set_rules(body + "\n", source="manual", note=(data.get("note") or "sửa tay trên app")[:200])
    return jsonify({"ok": True, "version": version})


@app.route("/api/rules/restore", methods=["POST"])
def api_rules_restore():
    try:
        version = store.restore_rules(int((request.json or {}).get("version") or 0))
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"ok": True, "version": version})


@app.route("/api/rules/<int:version>")
def api_rules_version(version):
    r = store.rules_version(version)
    if not r:
        abort(404)
    return jsonify({"version": r["version"], "body": r["body"], "html": md_to_html(r["body"]), "source": r["source"],
                    "note": r["note"], "created_at": r["created_at"]})


# ---------------------------------------------------------------- setup, monitoring
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


@app.route("/api/hf/probe", methods=["POST"])
def api_hf_probe():
    from creater import health
    return jsonify(health.hf_probe())


@app.route("/api/open-folder", methods=["POST"])
def api_open_folder():
    path = (request.json or {}).get("path", "")
    if path and os.path.exists(path):
        subprocess.Popen(["explorer", "/select," + path] if os.path.isfile(path) else ["explorer", path])
        return jsonify({"ok": True})
    return jsonify({"error": "không thấy"}), 404


# Start the worker as soon as the module is imported (Tool Manager imports `app` and calls app.run()).
if os.environ.get("CREATER_NO_WORKER") != "1":
    worker()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", config.PORT))
    app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False, threaded=True)
