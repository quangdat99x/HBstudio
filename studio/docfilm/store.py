"""Projects, messages, rulebook versions and the files a project has produced."""
from __future__ import annotations

import json
import os
from pathlib import Path

from .. import config, db
from ..util import now_iso, slugify

STAGES = ("new", "research", "script", "film")
STAGE_NAMES = {"new": "mới tạo", "research": "đã chọn đoạn", "script": "đã có kịch bản", "film": "đã render"}


# ---------------------------------------------------------------- paths
def root() -> Path:
    return Path(db.get_setting("docfilm_root") or config.DEFAULT_SETTINGS["docfilm_root"])


def rules_path() -> Path:
    return root() / "RULEBOOK.md"


def project_dir(p: dict) -> Path:
    return Path(p["dir"])


# ---------------------------------------------------------------- rulebook
def _latest_rules() -> dict | None:
    return db.row("SELECT * FROM docfilm_rules ORDER BY version DESC LIMIT 1")


def _add_rules(body: str, source: str, project_id=None, message_id=None, note=None) -> int:
    with db.tx() as c:
        c.execute("INSERT INTO docfilm_rules(body, source, project_id, message_id, note, created_at) VALUES(?,?,?,?,?,?)",
                  (body, source, project_id, message_id, note, now_iso()))
        return c.execute("SELECT last_insert_rowid()").fetchone()[0]


def sync_rules(source: str = "file", project_id=None, message_id=None, note=None) -> dict:
    """Make the working copy and the history agree. The file wins: whatever changed it (Claude in a turn,
    the user in an editor) becomes a new version. Returns {"version", "changed"}."""
    path = rules_path()
    latest = _latest_rules()
    if latest is None:
        body = config.DOCFILM_RULEBOOK_SEED.read_text(encoding="utf-8")
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
    if body.strip() == latest["body"].strip():
        return {"version": latest["version"], "changed": False}
    version = _add_rules(body, source, project_id, message_id, note)
    return {"version": version, "changed": True}


def set_rules(body: str, source: str = "manual", note: str | None = None) -> int:
    path = rules_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body.replace("\r\n", "\n"), encoding="utf-8")
    return sync_rules(source=source, note=note)["version"]


def restore_rules(version: int) -> int:
    old = db.row("SELECT * FROM docfilm_rules WHERE version=?", (version,))
    if not old:
        raise ValueError(f"không có phiên bản v{version}")
    return set_rules(old["body"], source="restore", note=f"khôi phục v{version}")


def rules_history(limit: int = 100) -> list[dict]:
    return db.rows("""SELECT r.version, r.source, r.project_id, r.message_id, r.note, r.created_at, length(r.body) AS chars,
                             p.title AS project_title
                      FROM docfilm_rules r LEFT JOIN docfilm_projects p ON p.id=r.project_id
                      ORDER BY r.version DESC LIMIT ?""", (limit,))


def rules_version(version: int) -> dict | None:
    return db.row("SELECT * FROM docfilm_rules WHERE version=?", (version,))


def current_rules() -> dict:
    sync_rules()
    return _latest_rules()


# ---------------------------------------------------------------- projects
def create_project(title: str, topic: str, brief: str = "", fmt: str = "16:9", target_sec: int | None = None,
                   credit_budget: float | None = None) -> dict:
    title = (title or "").strip() or topic.strip()
    topic = (topic or "").strip()
    if not topic:
        raise ValueError("cần nhập chủ đề")
    base = slugify(title, 48)
    slug, n = base, 2
    while db.row("SELECT id FROM docfilm_projects WHERE slug=?", (slug,)):
        slug, n = f"{base}-{n}", n + 1
    folder = root() / slug
    for sub in ("research/transcripts", "script", "out/review", "notes"):
        (folder / sub).mkdir(parents=True, exist_ok=True)
    if credit_budget is None:
        credit_budget = db.setting_float("docfilm_credit_budget")
    now = now_iso()
    with db.tx() as c:
        c.execute("""INSERT INTO docfilm_projects(slug, title, topic, brief, format, target_sec, credit_budget, stage, dir,
                     created_at, updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                  (slug, title, topic, brief.strip() or None, fmt if fmt in ("16:9", "9:16") else "16:9",
                   int(target_sec) if target_sec else None, credit_budget, "new", str(folder), now, now))
        pid = c.execute("SELECT last_insert_rowid()").fetchone()[0]
    p = get_project(pid)
    write_brief(p)
    return p


def update_project(pid: int, **fields) -> None:
    allowed = {"title", "topic", "brief", "format", "target_sec", "credit_budget", "stage", "session_id",
               "session_cost_usd", "rules_version", "cost_usd"}
    sets = {k: v for k, v in fields.items() if k in allowed}
    if not sets:
        return
    with db.tx() as c:
        c.execute(f"UPDATE docfilm_projects SET {', '.join(k + '=?' for k in sets)}, updated_at=? WHERE id=?",
                  list(sets.values()) + [now_iso(), pid])


def get_project(pid: int) -> dict | None:
    return db.row("SELECT * FROM docfilm_projects WHERE id=?", (pid,))


def list_projects() -> list[dict]:
    out = db.rows("SELECT * FROM docfilm_projects ORDER BY updated_at DESC")
    for p in out:
        p["busy"] = db.row("SELECT id, status FROM docfilm_messages WHERE project_id=? AND role='assistant' "
                           "AND status IN ('queued','running') ORDER BY id DESC LIMIT 1", (p["id"],))
        p["artifacts"] = artifacts(p, light=True)
    return out


def write_brief(p: dict) -> Path:
    """project.json in the folder: what Claude reads first (kept in sync with the database)."""
    path = project_dir(p) / "project.json"
    data = {k: p.get(k) for k in ("id", "slug", "title", "topic", "brief", "format", "target_sec", "credit_budget")}
    data["folder"] = p["dir"]
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


# ---------------------------------------------------------------- messages
def add_user_message(pid: int, text: str, kind: str = "chat") -> int:
    with db.tx() as c:
        c.execute("INSERT INTO docfilm_messages(project_id, role, kind, content, status, created_at) VALUES(?,?,?,?,?,?)",
                  (pid, "user", kind, text.strip(), "done", now_iso()))
        return c.execute("SELECT last_insert_rowid()").fetchone()[0]


def add_assistant_turn(pid: int, reply_to: int, kind: str) -> int:
    with db.tx() as c:
        c.execute("""INSERT INTO docfilm_messages(project_id, role, kind, status, progress_msg, reply_to, model, effort, created_at)
                     VALUES(?,?,?,?,?,?,?,?,?)""",
                  (pid, "assistant", kind, "queued", "đang chờ tới lượt", reply_to, db.get_setting("claude_model_docfilm"),
                   db.get_setting("claude_effort_docfilm"), now_iso()))
        return c.execute("SELECT last_insert_rowid()").fetchone()[0]


def messages(pid: int) -> list[dict]:
    return db.rows("SELECT * FROM docfilm_messages WHERE project_id=? ORDER BY id", (pid,))


def busy_turn(pid: int) -> dict | None:
    return db.row("SELECT * FROM docfilm_messages WHERE project_id=? AND role='assistant' AND status IN ('queued','running') "
                  "ORDER BY id LIMIT 1", (pid,))


# ---------------------------------------------------------------- files the project produced
def _rel(p: dict, path: Path) -> str:
    return str(path.relative_to(project_dir(p))).replace("\\", "/")


def _read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None


def artifacts(p: dict, light: bool = False) -> dict:
    d = project_dir(p)
    out: dict = {"folder": str(d)}
    pool = d / "research" / "pool.json"
    sel = d / "research" / "selection.json"
    script = d / "script" / "script.json"
    out["pool_count"] = len((_read_json(pool) or {}).get("segments") or []) if pool.exists() else 0
    out["has_selection"] = sel.exists()
    out["has_script"] = script.exists()
    videos = []
    for folder in (d / "out", d / "film" / "out"):
        if folder.exists():
            videos += [v for v in folder.glob("*.mp4")]
    videos.sort(key=lambda v: v.stat().st_mtime, reverse=True)
    out["videos"] = [{"path": _rel(p, v), "name": v.name, "mb": round(v.stat().st_size / 1e6, 1),
                      "mtime": v.stat().st_mtime} for v in videos]
    stage = "film" if videos else "script" if out["has_script"] else "research" if out["has_selection"] else "new"
    out["stage"] = stage
    if light:
        return out
    if sel.exists():
        s = _read_json(sel) or {}
        out["selection"] = s
        md = d / "research" / "selection.md"
        out["selection_md"] = md.read_text(encoding="utf-8") if md.exists() else ""
    if out["pool_count"]:
        out["pool"] = (_read_json(pool) or {}).get("segments") or []
    if script.exists():
        out["script"] = _read_json(script) or {}
        scenes = out["script"].get("scenes") if isinstance(out["script"], dict) else None
        out["script_duration"] = sum(float(s.get("duration_sec") or 0) for s in scenes or [] if isinstance(s, dict))
        md = d / "script" / "script.md"
        out["script_md"] = md.read_text(encoding="utf-8") if md.exists() else ""
    images = []
    for folder in (d / "out" / "review", d / "film" / "out" / "stills", d / "out"):
        if folder.exists():
            images += [i for i in folder.glob("*.jpg")] + [i for i in folder.glob("*.png")]
    images.sort(key=lambda i: i.stat().st_mtime, reverse=True)
    out["images"] = [{"path": _rel(p, i), "name": i.name} for i in images[:24]]
    credits = _read_json(d / "notes" / "credits.json")
    out["credits"] = credits if isinstance(credits, dict) else None
    return out


def safe_file(p: dict, rel: str) -> Path | None:
    """A file inside the project folder (never outside it)."""
    base = project_dir(p).resolve()
    try:
        target = (base / rel).resolve()
    except Exception:  # noqa: BLE001
        return None
    if base not in target.parents or not target.is_file():
        return None
    return target


def open_folder(path: str) -> None:
    os.startfile(path)  # noqa: S606  (Windows explorer, user's own folder)
