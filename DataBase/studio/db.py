"""SQLite access layer: connection, schema init, settings, small helpers."""
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
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def get_conn() -> sqlite3.Connection:
    """One connection per thread (Flask request threads + worker thread)."""
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
        from . import channel_watch, podcasts
        podcasts.ensure_schema(conn)
        channel_watch.ensure_schema(conn)
    finally:
        conn.close()


def _migrate(conn: sqlite3.Connection) -> None:
    """Add columns introduced after the first release (SQLite has no IF NOT EXISTS for columns)."""
    wanted = {
        "episodes": {
            "duration_sec": "REAL", "guest_card_md": "TEXT", "selection_log_md": "TEXT",
            "cutlist_path": "TEXT", "stage": "TEXT NOT NULL DEFAULT 'new'", "stage_error": "TEXT",
            "pending_zoom": "TEXT",
        },
        "segments": {
            "analysis_md": "TEXT", "analysis_json": "TEXT", "keyword_reason": "TEXT",
            "transcript": "TEXT", "last_seen": "TEXT",
        },
        "segment_titles": {
            "session_id": "TEXT", "parent_id": "INTEGER", "user_message": "TEXT", "session_cost_usd": "REAL",
            "focus": "TEXT", "kind": "TEXT",
        },
    }
    for table, cols in wanted.items():
        existing = {r["name"] for r in conn.execute(f"PRAGMA table_info({table})")}
        for col, decl in cols.items():
            if col not in existing:
                with conn:
                    conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {decl}")


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
    row = get_conn().execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    if row is not None:
        return row["value"]
    if default is not None:
        return default
    return config.DEFAULT_SETTINGS.get(key, "")


def set_setting(key: str, value: Any) -> None:
    with tx() as c:
        c.execute("INSERT INTO settings(key, value) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                  (key, str(value)))


def all_settings() -> dict:
    merged = dict(config.DEFAULT_SETTINGS)
    for r in get_conn().execute("SELECT key, value FROM settings"):
        merged[r["key"]] = r["value"]
    return merged


def setting_bool(key: str) -> bool:
    return str(get_setting(key)).strip().lower() in ("1", "true", "yes", "on")


def setting_float(key: str) -> float:
    try:
        return float(get_setting(key))
    except (TypeError, ValueError):
        return float(config.DEFAULT_SETTINGS.get(key, 0))


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
