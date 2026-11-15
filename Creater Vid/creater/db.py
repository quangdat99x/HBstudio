"""SQLite access layer: connection per thread, schema init, settings, small helpers."""
from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterable, Optional

from . import config

_SCHEMA = Path(__file__).with_name("schema.sql")
_local = threading.local()
_write_lock = threading.RLock()


def connect(db_path: Optional[Path] = None) -> sqlite3.Connection:
    path = Path(db_path or config.DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    # SQLite's lower() and LIKE only fold ASCII: the news search needs Cyrillic and Vietnamese too
    conn.create_function("ulower", 1, lambda s: s.lower().replace("ё", "е") if isinstance(s, str) else s, deterministic=True)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def get_conn() -> sqlite3.Connection:
    """One connection per thread (Flask request threads + the worker thread)."""
    conn = getattr(_local, "conn", None)
    if conn is None:
        conn = connect()
        _local.conn = conn
    return conn


def init_db(db_path: Optional[Path] = None) -> None:
    conn = connect(db_path)
    try:
        with conn:
            conn.executescript(_SCHEMA.read_text(encoding="utf-8"))
        _migrate(conn)
    finally:
        conn.close()


def _migrate(conn: sqlite3.Connection) -> None:
    """Columns added after the first release go here (SQLite has no ADD COLUMN IF NOT EXISTS)."""
    wanted: dict[str, dict[str, str]] = {
        "projects": {"pipeline": "TEXT DEFAULT 'layered'"},     # 2026-10-08: fullframe pictures (parallax)
        "news_topics": {"video_kind": "TEXT DEFAULT 'single'"},  # 2026-10-12: one story | 24-hour digest
    }
    # 2026-10-14: documentaries and news videos became two desks with their own workflow and rulebook
    split = "kind" not in {r["name"] for r in conn.execute("PRAGMA table_info(projects)")}
    wanted["projects"]["kind"] = "TEXT DEFAULT 'doc'"
    wanted["rules"] = {"book": "TEXT DEFAULT 'doc'", "num": "INTEGER"}
    # 2026-10-14: upload to YouTube through a GPM Login profile
    wanted["projects"].update({"yt_profile": "TEXT", "yt_channel": "TEXT", "yt_auto": "INTEGER DEFAULT 0"})
    # 2026-10-20: the user's own upload choice (Đăng ngay public/unlisted/private | Lên lịch + time), beats metadata.json
    wanted["projects"].update({"yt_vis": "TEXT", "yt_at": "TEXT"})
    # 2026-10-15: Claude model / effort chosen per project (news light, documentaries deep)
    wanted["projects"].update({"claude_model": "TEXT", "claude_effort": "TEXT"})
    for table, cols in wanted.items():
        existing = {r["name"] for r in conn.execute(f"PRAGMA table_info({table})")}
        for col, decl in cols.items():
            if col not in existing:
                with conn:
                    conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {decl}")
    if split:
        # a project made on the news desk has sources/news.json; the rulebook history so far is the documentary one's
        with conn:
            for r in conn.execute("SELECT id, dir FROM projects").fetchall():
                if (Path(r["dir"]) / "sources" / "news.json").exists():
                    conn.execute("UPDATE projects SET kind='news' WHERE id=?", (r["id"],))
            conn.execute("UPDATE rules SET book='doc', num=version WHERE num IS NULL")
    # 2026-10-06: assets are paid in USD through the APIs instead of Higgsfield credits
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(projects)")}
    if "credit_budget" in cols and "budget_usd" not in cols:
        with conn:
            conn.execute("ALTER TABLE projects RENAME COLUMN credit_budget TO budget_usd")
            conn.execute("UPDATE projects SET budget_usd=?", (float(config.DEFAULT_SETTINGS["budget_usd"]),))
    # 2026-11-05: Claude model / effort only from Cài đặt, set per desk and per step (model_<desk>_<step>);
    # the old shared per-step values seed both desks once, then go away
    old = {r["key"]: r["value"] for r in conn.execute("SELECT key, value FROM settings WHERE key LIKE 'model_%' OR key LIKE 'effort_%'")}
    with conn:
        for desk, steps in config.DESK_STEP_KEYS.items():
            for step in steps:
                for name in ("model", "effort"):
                    v = old.get(f"{name}_{step}")
                    if v and f"{name}_{desk}_{step}" not in old:
                        conn.execute("INSERT INTO settings(key, value) VALUES(?, ?)", (f"{name}_{desk}_{step}", v))
        conn.execute("DELETE FROM settings WHERE key IN (%s)" % ",".join("?" * 2 * len(config.STEP_SETTING_KEYS)),
                     [f"{n}_{s}" for s in config.STEP_SETTING_KEYS for n in ("model", "effort")])
    with conn:
        conn.execute("DELETE FROM settings WHERE key IN ('hf_balance','hf_plan','hf_checked_at','credit_budget',"
                     "'voice_name','voice_id')")


@contextmanager
def tx(conn: Optional[sqlite3.Connection] = None):
    """Serialized write transaction (SQLite allows one writer at a time)."""
    c = conn or get_conn()
    with _write_lock:
        try:
            c.execute("BEGIN")
            yield c
            c.execute("COMMIT")
        except Exception:
            c.execute("ROLLBACK")
            raise


# ---------------------------------------------------------------- settings
def get_setting(key: str, default: Any = None) -> str:
    row_ = get_conn().execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    if row_ is not None:
        return row_["value"]
    if default is not None:
        return default
    return config.DEFAULT_SETTINGS.get(key, "")


def set_setting(key: str, value: Any) -> None:
    with tx() as c:
        c.execute("INSERT INTO settings(key, value) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                  (key, str(value)))


def all_settings() -> dict:
    """Every setting for the pages. API keys are never included: only whether one is saved and its last 4 characters."""
    merged = dict(config.DEFAULT_SETTINGS)
    for r in get_conn().execute("SELECT key, value FROM settings"):
        merged[r["key"]] = r["value"]
    for k in config.SECRET_KEYS:
        value = merged.pop(k, "") or ""
        merged[k + "_hint"] = ("••••" + value[-4:]) if value else ""
    return merged


def setting_bool(key: str) -> bool:
    return str(get_setting(key)).strip().lower() in ("1", "true", "yes", "on")


def setting_float(key: str) -> float:
    try:
        return float(get_setting(key))
    except (TypeError, ValueError):
        try:
            return float(config.DEFAULT_SETTINGS.get(key, 0))
        except (TypeError, ValueError):
            return 0.0


def setting_int(key: str) -> int:
    return int(setting_float(key))


# ---------------------------------------------------------------- helpers
def rows(sql: str, params: Iterable = ()) -> list[dict]:
    return [dict(r) for r in get_conn().execute(sql, tuple(params)).fetchall()]


def row(sql: str, params: Iterable = ()) -> Optional[dict]:
    r = get_conn().execute(sql, tuple(params)).fetchone()
    return dict(r) if r else None


def scalar(sql: str, params: Iterable = ()) -> Any:
    r = get_conn().execute(sql, tuple(params)).fetchone()
    return r[0] if r else None
