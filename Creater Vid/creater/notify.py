"""In-app notifications: the 🔔 bell in the header of every page (Hổ Báo Studio and Creater Vid share the same design).

Background work calls `notify()` when a job ends: a zoom clip finished, a title written, a thumbnail mock waiting for
approval, a step that failed... The bell polls `/api/notifications` and shows a red badge + a toast for new ones.

kind: "done" (a job finished), "review" (waiting for the user's approval), "error" (a job failed), "info".
key:  optional identity of the event. A new notification with the same key replaces the unread one (no pile of
      "đang chờ duyệt" for one thing), and `resolve(key)` marks it read once the user dealt with it (approved…).

Notifications never break the work that sends them: every function here swallows its own errors.
"""
from __future__ import annotations

import logging
import time

from . import db

log = logging.getLogger("creater.notify")
KINDS = ("done", "review", "error", "info")
KEEP = 400                                    # newest notifications kept in the table

_DDL = """CREATE TABLE IF NOT EXISTS notifications (
  id       INTEGER PRIMARY KEY,
  ts       REAL NOT NULL,                     -- unix time
  kind     TEXT NOT NULL,                     -- done | review | error | info
  title    TEXT NOT NULL,
  body     TEXT,
  link     TEXT,                              -- page to open on click (path of this app)
  key      TEXT,                              -- identity of the event (dedupe + resolve)
  read_at  REAL
);
CREATE INDEX IF NOT EXISTS idx_notifications_key ON notifications(key);"""
_ready = False


def _ensure() -> None:
    global _ready
    if not _ready:
        with db._write_lock:
            db.get_conn().executescript(_DDL)
        _ready = True


def notify(kind: str, title: str, body: str = "", link: str = "", key: str | None = None) -> int | None:
    try:
        _ensure()
        kind = kind if kind in KINDS else "info"
        title, body = str(title or "").strip()[:200], str(body or "").strip()[:600]
        now = time.time()
        with db.tx() as c:
            if key:
                c.execute("DELETE FROM notifications WHERE key=? AND read_at IS NULL", (key,))
            c.execute("INSERT INTO notifications(ts, kind, title, body, link, key) VALUES(?,?,?,?,?,?)",
                      (now, kind, title, body or None, link or None, key))
            nid = c.execute("SELECT last_insert_rowid()").fetchone()[0]
            c.execute("DELETE FROM notifications WHERE id <= ?", (nid - KEEP,))
        return nid
    except Exception as e:  # noqa: BLE001
        log.warning("notify failed: %s", e)
        return None


def resolve(key: str) -> None:
    """The user dealt with it (approved, re-ran…): the matching unread notifications are marked read."""
    try:
        _ensure()
        with db.tx() as c:
            c.execute("UPDATE notifications SET read_at=? WHERE key=? AND read_at IS NULL", (time.time(), key))
    except Exception as e:  # noqa: BLE001
        log.warning("notify resolve failed: %s", e)


def listing(after: int = 0, limit: int = 60) -> dict:
    _ensure()
    items = db.rows("SELECT id, ts, kind, title, body, link, read_at FROM notifications WHERE id > ? "
                    "ORDER BY id DESC LIMIT ?", (int(after or 0), max(1, min(200, int(limit or 60)))))
    return {"items": items, "unread": db.scalar("SELECT COUNT(*) FROM notifications WHERE read_at IS NULL") or 0,
            "last_id": db.scalar("SELECT MAX(id) FROM notifications") or 0}


def mark_read(ids: list[int] | None = None) -> int:
    """ids=None marks everything read."""
    _ensure()
    now = time.time()
    with db.tx() as c:
        if ids is None:
            cur = c.execute("UPDATE notifications SET read_at=? WHERE read_at IS NULL", (now,))
        else:
            ids = [int(i) for i in ids][:500]
            if not ids:
                return 0
            cur = c.execute("UPDATE notifications SET read_at=? WHERE read_at IS NULL AND id IN (%s)"
                            % ",".join("?" * len(ids)), (now, *ids))
        return cur.rowcount


def clear_read() -> int:
    _ensure()
    with db.tx() as c:
        return c.execute("DELETE FROM notifications WHERE read_at IS NOT NULL").rowcount


# ---------------------------------------------------------------- Creater helpers
def project_link(pid: int, step: str | None = None) -> str:
    return f"/p/{pid}" + (f"?step={step}" if step else "")


def _project(pid: int) -> tuple[dict, str]:
    from . import store
    p = store.get_project(pid) or {}
    desk = "📰" if p.get("kind") == "news" else "🎬"
    return p, f"{desk} {(p.get('title') or f'dự án #{pid}')[:80]}"


def _step_name(p: dict, step: str) -> str:
    from . import workflow
    try:
        st = workflow.flow(p).by_key.get(step)
        return f"Bước {st.num} · {st.name}" if st else step
    except Exception:  # noqa: BLE001
        return step


def review_key(pid: int, step: str) -> str:
    return f"review:{pid}:{step}"


def step_review(pid: int, step: str, note: str = "") -> None:
    """A step waits for the user's approval (step-by-step projects, or an automatic run that could not go on)."""
    try:
        p, name = _project(pid)
        notify("review", f"{_step_name(p, step)} cần duyệt", name + (f" · {note}" if note else ""),
               project_link(pid, step), key=review_key(pid, step))
    except Exception as e:  # noqa: BLE001
        log.warning("notify step_review: %s", e)


def step_done(pid: int, step: str, nxt: str | None = None) -> None:
    """Automatic projects: a step finished and was approved by the app."""
    try:
        p, name = _project(pid)
        resolve(review_key(pid, step))
        if nxt:
            notify("done", f"Xong {_step_name(p, step)} (tự duyệt)", f"{name} · đang chạy {_step_name(p, nxt)}",
                   project_link(pid, step))
        else:
            notify("done", f"Dự án đã xong mọi bước: {name}", f"{_step_name(p, step)} vừa tự duyệt", project_link(pid))
    except Exception as e:  # noqa: BLE001
        log.warning("notify step_done: %s", e)


def step_failed(pid: int, step: str, error: str) -> None:
    try:
        p, name = _project(pid)
        notify("error", f"{_step_name(p, step)} lỗi", f"{name} · {error}", project_link(pid, step))
    except Exception as e:  # noqa: BLE001
        log.warning("notify step_failed: %s", e)


def step_approved(pid: int, step: str) -> None:
    resolve(review_key(pid, step))


def chat_done(pid: int, step: str | None, answer: str) -> None:
    try:
        _, name = _project(pid)
        notify("info", f"Claude đã trả lời: {name}", (answer or "").strip().replace("\n", " ")[:200],
               project_link(pid, step))
    except Exception as e:  # noqa: BLE001
        log.warning("notify chat_done: %s", e)


# ---------------------------------------------------------------- Flask routes (same in both apps)
def register(app) -> None:
    """GET /api/notifications?after=ID · POST /api/notifications/read {ids|all} · POST /api/notifications/clear.
    The other app (5004 ⇄ 5010) reads this bell too, so the routes answer cross-origin requests from localhost."""
    from flask import jsonify, request

    def _cors(resp):
        origin = request.headers.get("Origin") or ""
        if origin.startswith(("http://127.0.0.1:", "http://localhost:")):
            resp.headers["Access-Control-Allow-Origin"] = origin
            resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
            resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
            resp.headers["Vary"] = "Origin"
        return resp

    @app.route("/api/notifications", methods=["GET", "OPTIONS"])
    def api_notifications():
        if request.method == "OPTIONS":
            return _cors(app.make_default_options_response())
        return _cors(jsonify(listing(request.args.get("after", 0), request.args.get("limit", 60))))

    @app.route("/api/notifications/read", methods=["POST", "OPTIONS"])
    def api_notifications_read():
        if request.method == "OPTIONS":
            return _cors(app.make_default_options_response())
        body = request.get_json(silent=True, force=True) or {}
        n = mark_read(None if body.get("all") else body.get("ids") or [])
        return _cors(jsonify({"ok": True, "marked": n}))

    @app.route("/api/notifications/clear", methods=["POST", "OPTIONS"])
    def api_notifications_clear():
        if request.method == "OPTIONS":
            return _cors(app.make_default_options_response())
        return _cors(jsonify({"ok": True, "deleted": clear_read()}))
