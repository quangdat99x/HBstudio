"""Projects, their steps, messages, the rulebook history, the activity log and the files a project holds."""
from __future__ import annotations

import json
import os
from pathlib import Path

from . import config, db, workflow
from .util import now_iso, read_json, safe_filename, slugify, write_json

PROJECT_DIRS = ("sources", "1_script", "2_cast/casting", "3_scenes", "4_images", "5_footage", "6_render", "out/review",
                "notes/runs")
EDITABLE = ("title", "topic", "brief", "language", "audience", "style", "format", "target_sec", "credit_budget",
            "use_jre", "auto_advance", "archived")


# ---------------------------------------------------------------- paths
def root() -> Path:
    return Path(db.get_setting("projects_root") or config.DEFAULT_SETTINGS["projects_root"])


def rules_path() -> Path:
    """Working copy of the rulebook: Claude reads and edits this file, the app versions every change."""
    return root() / "RULEBOOK.md"


def project_dir(p: dict) -> Path:
    return Path(p["dir"])


# ---------------------------------------------------------------- rulebook
def _latest_rules() -> dict | None:
    return db.row("SELECT * FROM rules ORDER BY version DESC LIMIT 1")


def _add_rules(body: str, source: str, project_id=None, message_id=None, note=None) -> int:
    with db.tx() as c:
        c.execute("INSERT INTO rules(body, source, project_id, message_id, note, created_at) VALUES(?,?,?,?,?,?)",
                  (body, source, project_id, message_id, note, now_iso()))
        return c.execute("SELECT last_insert_rowid()").fetchone()[0]


def sync_rules(source: str = "file", project_id=None, message_id=None, note=None) -> dict:
    """Make the working copy and the history agree. The file wins: whatever changed it (Claude in a turn, the user
    in an editor) becomes a new version. Returns {"version", "changed"}."""
    path = rules_path()
    latest = _latest_rules()
    if latest is None:
        body = config.RULEBOOK_SEED.read_text(encoding="utf-8")
        if path.exists() and path.read_text(encoding="utf-8").strip():
            body = path.read_text(encoding="utf-8")
        version = _add_rules(body, "seed", note="bộ quy tắc đầu tiên")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
        return {"version": version, "changed": True}
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(latest["body"], encoding="utf-8")
        return {"version": latest["version"], "changed": False}
    body = path.read_text(encoding="utf-8")
    if body.replace("\r\n", "\n").strip() == latest["body"].replace("\r\n", "\n").strip():
        return {"version": latest["version"], "changed": False}
    version = _add_rules(body, source, project_id, message_id, note)
    return {"version": version, "changed": True}


def set_rules(body: str, source: str = "manual", note: str | None = None) -> int:
    path = rules_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body.replace("\r\n", "\n"), encoding="utf-8")
    return sync_rules(source=source, note=note)["version"]


def restore_rules(version: int) -> int:
    old = db.row("SELECT * FROM rules WHERE version=?", (version,))
    if not old:
        raise ValueError(f"không có phiên bản v{version}")
    return set_rules(old["body"], source="restore", note=f"khôi phục v{version}")


def rules_history(limit: int = 100) -> list[dict]:
    return db.rows("""SELECT r.version, r.source, r.project_id, r.message_id, r.note, r.created_at, length(r.body) AS chars,
                             p.title AS project_title
                      FROM rules r LEFT JOIN projects p ON p.id=r.project_id
                      ORDER BY r.version DESC LIMIT ?""", (limit,))


def rules_version(version: int) -> dict | None:
    return db.row("SELECT * FROM rules WHERE version=?", (version,))


def current_rules() -> dict:
    sync_rules()
    return _latest_rules()


# ---------------------------------------------------------------- activity log
def log_event(pid: int | None, kind: str, text: str, step: str | None = None) -> None:
    with db.tx() as c:
        c.execute("INSERT INTO events(project_id, step, kind, text, created_at) VALUES(?,?,?,?,?)",
                  (pid, step, kind, (text or "")[:500], now_iso()))


def events(pid: int | None = None, limit: int = 50) -> list[dict]:
    if pid:
        return db.rows("SELECT * FROM events WHERE project_id=? ORDER BY id DESC LIMIT ?", (pid, limit))
    return db.rows("""SELECT e.*, p.title AS project_title FROM events e LEFT JOIN projects p ON p.id=e.project_id
                      ORDER BY e.id DESC LIMIT ?""", (limit,))


# ---------------------------------------------------------------- projects
def _num_or_none(v, cast=float):
    try:
        return cast(v) if v not in (None, "") else None
    except (TypeError, ValueError):
        return None


def create_project(data: dict) -> dict:
    topic = (data.get("topic") or "").strip()
    if not topic:
        raise ValueError("cần nhập chủ đề")
    title = (data.get("title") or "").strip() or topic
    base = slugify(title, 48)
    slug, n = base, 2
    while db.row("SELECT id FROM projects WHERE slug=?", (slug,)) or (root() / slug).exists():
        slug, n = f"{base}-{n}", n + 1
    folder = root() / slug
    for sub in PROJECT_DIRS:
        (folder / sub).mkdir(parents=True, exist_ok=True)
    s = db.all_settings()
    budget = _num_or_none(data.get("credit_budget"))
    target = _num_or_none(data.get("target_sec"), int)
    fmt = data.get("format") if data.get("format") in ("16:9", "9:16") else s["format"]
    now = now_iso()
    with db.tx() as c:
        c.execute("""INSERT INTO projects(slug, title, topic, brief, language, audience, style, format, target_sec,
                     credit_budget, use_jre, auto_advance, dir, created_at, updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                  (slug, title, topic, (data.get("brief") or "").strip() or None,
                   (data.get("language") or s["language"]).strip(), (data.get("audience") or s["audience"]).strip(),
                   (data.get("style") if data.get("style") is not None else s["style"]).strip() or None, fmt,
                   target if target is not None else _num_or_none(s["target_sec"], int),
                   budget if budget is not None else db.setting_float("credit_budget"),
                   1 if data.get("use_jre") else 0,
                   1 if (data.get("auto_advance") if "auto_advance" in data else db.setting_bool("auto_advance")) else 0,
                   str(folder), now, now))
        pid = c.execute("SELECT last_insert_rowid()").fetchone()[0]
        for i, key in enumerate(workflow.STEP_KEYS):
            c.execute("INSERT INTO project_steps(project_id, step, status) VALUES(?,?,?)",
                      (pid, key, "ready" if i == 0 else "locked"))
    p = get_project(pid)
    write_brief(p)
    log_event(pid, "created", f"tạo dự án: {title}")
    return p


def update_project(pid: int, **fields) -> None:
    allowed = set(EDITABLE) | {"session_id", "session_cost_usd", "rules_version", "cost_usd"}
    sets = {k: v for k, v in fields.items() if k in allowed}
    if not sets:
        with db.tx() as c:
            c.execute("UPDATE projects SET updated_at=? WHERE id=?", (now_iso(), pid))
        return
    with db.tx() as c:
        c.execute(f"UPDATE projects SET {', '.join(k + '=?' for k in sets)}, updated_at=? WHERE id=?",
                  list(sets.values()) + [now_iso(), pid])


def clean_fields(data: dict) -> dict:
    out = {}
    for k in EDITABLE:
        if k not in data:
            continue
        v = data[k]
        if k == "target_sec":
            v = _num_or_none(v, int)
        elif k == "credit_budget":
            v = _num_or_none(v)
        elif k in ("use_jre", "auto_advance", "archived"):
            v = 1 if v in (True, 1, "1", "on", "true") else 0
        elif k == "format":
            v = v if v in ("16:9", "9:16") else "16:9"
        else:
            v = (v or "").strip() or (None if k in ("brief", "style", "audience") else v)
        out[k] = v
    if "topic" in out and not out["topic"]:
        out.pop("topic")
    if "title" in out and not out["title"]:
        out.pop("title")
    return out


def get_project(pid: int) -> dict | None:
    return db.row("SELECT * FROM projects WHERE id=?", (pid,))


def list_projects(archived: bool = False) -> list[dict]:
    out = db.rows("SELECT * FROM projects WHERE archived=? ORDER BY updated_at DESC", (1 if archived else 0,))
    for p in out:
        p["steps"] = steps(p)
        p["busy"] = busy_turn(p["id"])
        p["current"] = current_step(p["steps"])
        p["credits"] = workflow.credits_spent(project_dir(p))["total"] if project_dir(p).exists() else 0
    return out


def write_brief(p: dict) -> Path:
    """project.json in the folder: what Claude reads first (kept in sync with the database)."""
    path = project_dir(p) / "project.json"
    data = {k: p.get(k) for k in ("id", "slug", "title", "topic", "brief", "language", "audience", "style", "format",
                                   "target_sec", "credit_budget")}
    data["use_jre_highlights"] = bool(p.get("use_jre"))
    data["auto_advance"] = bool(p.get("auto_advance"))
    data["folder"] = p["dir"]
    data["steps"] = {s["step"]: s["status"] for s in db.rows("SELECT step, status FROM project_steps WHERE project_id=?", (p["id"],))}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


# ---------------------------------------------------------------- steps
def steps(p: dict) -> list[dict]:
    """Every step of a project with its status, check summary and whether an earlier step changed after it ran."""
    rows_ = {r["step"]: r for r in db.rows("SELECT * FROM project_steps WHERE project_id=?", (p["id"],))}
    d = project_dir(p)
    out, upstream_change = [], 0.0
    for st in workflow.STEPS:
        r = dict(rows_.get(st.key) or {"step": st.key, "status": "locked"})
        r["meta"] = st
        r["label"] = workflow.STATUS_LABELS.get(r["status"], r["status"])
        try:
            r["problems_list"] = json.loads(r.get("problems") or "[]")
        except ValueError:
            r["problems_list"] = []
        mtime = workflow.latest_mtime(d, st) if d.exists() else 0.0
        r["mtime"] = mtime
        # an earlier step's files changed after this step last ran: its outputs may be out of date
        r["stale"] = bool(r["status"] in ("review", "approved") and upstream_change and mtime and upstream_change > mtime + 1)
        if r["status"] in ("review", "approved", "running", "queued") and mtime:
            upstream_change = max(upstream_change, mtime)
        out.append(r)
    return out


def step_row(pid: int, key: str) -> dict | None:
    return db.row("SELECT * FROM project_steps WHERE project_id=? AND step=?", (pid, key))


def set_step(pid: int, key: str, **fields) -> None:
    if not fields:
        return
    with db.tx() as c:
        c.execute(f"UPDATE project_steps SET {', '.join(k + '=?' for k in fields)} WHERE project_id=? AND step=?",
                  list(fields.values()) + [pid, key])


def current_step(step_rows: list[dict]) -> dict | None:
    """The step the project is at: the first one that is not approved yet."""
    for r in step_rows:
        if r["status"] != "approved":
            return r
    return step_rows[-1] if step_rows else None


def approve(p: dict, key: str) -> dict:
    r = step_row(p["id"], key)
    if not r or r["status"] in ("locked", "queued", "running"):
        raise ValueError("bước này chưa chạy xong, chưa duyệt được")
    problems, _ = workflow.check(key, project_dir(p), p)
    if workflow.blocking(problems):
        raise ValueError("chưa đủ kết quả: " + "; ".join(x for x in problems if not x.startswith("⚠"))[:300])
    set_step(p["id"], key, status="approved", approved_at=now_iso())
    nxt = workflow.next_step(key)
    if nxt:
        nr = step_row(p["id"], nxt)
        if nr and nr["status"] == "locked":
            set_step(p["id"], nxt, status="ready")
    update_project(p["id"])
    write_brief(get_project(p["id"]))
    log_event(p["id"], "approved", f"duyệt bước {workflow.BY_KEY[key].num} · {workflow.BY_KEY[key].name}", key)
    return {"next": nxt}


def reopen(p: dict, key: str) -> None:
    """Take an approval back (the user wants to change the step again)."""
    r = step_row(p["id"], key)
    if r and r["status"] == "approved":
        set_step(p["id"], key, status="review", approved_at=None)
        write_brief(get_project(p["id"]))
        log_event(p["id"], "reopened", f"mở lại bước {workflow.BY_KEY[key].num} · {workflow.BY_KEY[key].name}", key)


def recheck(p: dict, key: str) -> tuple[list[str], str]:
    problems, summary = workflow.check(key, project_dir(p), p)
    set_step(p["id"], key, problems=json.dumps(problems, ensure_ascii=False))
    return problems, summary


# ---------------------------------------------------------------- messages
def add_user_message(pid: int, text: str, kind: str = "chat", step: str | None = None) -> int:
    with db.tx() as c:
        c.execute("INSERT INTO messages(project_id, role, kind, step, content, status, created_at) VALUES(?,?,?,?,?,?,?)",
                  (pid, "user", kind, step, text.strip(), "done", now_iso()))
        return c.execute("SELECT last_insert_rowid()").fetchone()[0]


def model_for(step: str | None) -> tuple[str, str]:
    key = step if step in config.STEP_SETTING_KEYS else "chat"
    model = (db.get_setting(f"model_{key}") or db.get_setting("claude_model") or "").strip()
    effort = (db.get_setting(f"effort_{key}") or db.get_setting("claude_effort") or "").strip()
    return model, effort


def add_assistant_turn(pid: int, reply_to: int, kind: str, step: str | None) -> int:
    model, effort = model_for(step if kind == "step" else "chat")
    with db.tx() as c:
        c.execute("""INSERT INTO messages(project_id, role, kind, step, status, progress_msg, reply_to, model, effort, created_at)
                     VALUES(?,?,?,?,?,?,?,?,?,?)""",
                  (pid, "assistant", kind, step, "queued", "đang chờ tới lượt", reply_to, model, effort, now_iso()))
        return c.execute("SELECT last_insert_rowid()").fetchone()[0]


def messages(pid: int) -> list[dict]:
    return db.rows("SELECT * FROM messages WHERE project_id=? ORDER BY id", (pid,))


def busy_turn(pid: int) -> dict | None:
    return db.row("SELECT * FROM messages WHERE project_id=? AND role='assistant' AND status IN ('queued','running') "
                  "ORDER BY id LIMIT 1", (pid,))


def recent_turns(limit: int = 60) -> list[dict]:
    return db.rows("""SELECT m.id, m.project_id, m.kind, m.step, m.status, m.progress_msg, m.model, m.effort, m.models_used,
                             m.cost_usd, m.duration_sec, m.error, m.created_at, m.started_at, m.finished_at, p.title AS project_title
                      FROM messages m JOIN projects p ON p.id=m.project_id
                      WHERE m.role='assistant' ORDER BY m.id DESC LIMIT ?""", (limit,))


# ---------------------------------------------------------------- files of a project
def rel(p: dict, path: Path) -> str:
    return str(path.relative_to(project_dir(p))).replace("\\", "/")


def safe_file(p: dict, rel_path: str) -> Path | None:
    """A file inside the project folder (never outside it)."""
    base = project_dir(p).resolve()
    try:
        target = (base / rel_path).resolve()
    except Exception:  # noqa: BLE001
        return None
    if base not in target.parents or not target.is_file():
        return None
    return target


def sources(p: dict) -> dict:
    d = project_dir(p) / "sources"
    files = []
    if d.exists():
        for f in sorted(d.iterdir()):
            if f.is_file() and f.name != "links.txt":
                files.append({"name": f.name, "path": rel(p, f), "kb": max(1, round(f.stat().st_size / 1024))})
    links = (d / "links.txt").read_text(encoding="utf-8") if (d / "links.txt").exists() else ""
    return {"files": files, "links": links}


def save_upload(p: dict, storage) -> str:
    d = project_dir(p) / "sources"
    d.mkdir(parents=True, exist_ok=True)
    name = safe_filename(storage.filename or "file")
    target, n = d / name, 2
    while target.exists():
        target, n = d / f"{Path(name).stem}-{n}{Path(name).suffix}", n + 1
    storage.save(str(target))
    return target.name


def save_links(p: dict, text: str) -> None:
    d = project_dir(p) / "sources"
    d.mkdir(parents=True, exist_ok=True)
    (d / "links.txt").write_text((text or "").replace("\r\n", "\n").strip() + "\n", encoding="utf-8")


def choose_candidate(p: dict, character: str, file: str | None) -> dict:
    path = project_dir(p) / "2_cast" / "choices.json"
    choices = read_json(path) or {}
    if file:
        if not safe_file(p, file):
            raise ValueError("không thấy ảnh này trong dự án")
        choices[character] = file
    else:
        choices.pop(character, None)
    write_json(path, choices)
    return choices


def decide_footage(p: dict, item: str, decision: str | None) -> dict:
    path = project_dir(p) / "5_footage" / "approvals.json"
    data = read_json(path) or {}
    if decision in ("approved", "rejected"):
        data[item] = {"decision": decision, "at": now_iso()}
    else:
        data.pop(item, None)
    write_json(path, data)
    return data


def open_folder(path: str) -> None:
    os.startfile(path)  # noqa: S606  (Windows explorer, the user's own folder)
