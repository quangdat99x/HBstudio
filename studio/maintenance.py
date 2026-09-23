"""Backup, reset and restore of the Studio database.

Reset removes every episode, segment, transcript line, job and log row but keeps the settings (paths, models,
zoom parameters) and the theme taxonomy. A full copy of the database is written to backups/ first, and the
scratch folder work/ is moved there too, so a reset can always be undone with `hldb restore <file>`.
Media files on disk (videos, transcripts, cutlists, clips) are never touched.
"""
from __future__ import annotations

import shutil
import sqlite3
import time
from pathlib import Path

from . import config, db

BACKUP_DIR = config.BASE_DIR / "backups"
DATA_TABLES = ["segment_search", "segment_topics", "segment_themes", "segment_entities", "compilation_items",
               "publications", "compilations", "transcript_lines", "segments", "episodes", "topics", "entities",
               "job_events", "jobs", "ingest_log"]


def backup_db(tag: str = "") -> Path:
    """Consistent online copy (SQLite backup API), safe while the Studio server is running."""
    BACKUP_DIR.mkdir(exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    dst = BACKUP_DIR / f"studio_{stamp}{'_' + tag if tag else ''}.db"
    src = db.connect()
    try:
        out = sqlite3.connect(str(dst))
        try:
            src.backup(out)
        finally:
            out.close()
    finally:
        src.close()
    return dst


def counts() -> dict:
    return {t: db.scalar(f"SELECT COUNT(*) FROM {t}") for t in
            ("episodes", "segments", "transcript_lines", "jobs", "topics", "entities", "themes", "settings")}


def reset_data(keep_themes: bool = True, move_work: bool = True) -> dict:
    before = counts()
    backup = backup_db("truoc_khi_lam_sach")
    conn = db.get_conn()
    with db.tx(conn) as c:
        for table in DATA_TABLES:
            c.execute(f"DELETE FROM {table}")
        if not keep_themes:
            c.execute("DELETE FROM themes")
        c.execute("INSERT INTO segments_fts(segments_fts) VALUES('rebuild')")
    try:
        conn.execute("VACUUM")
    except sqlite3.Error:
        pass
    moved = None
    if move_work and config.WORK_DIR.exists() and any(config.WORK_DIR.iterdir()):
        dst = BACKUP_DIR / f"work_{time.strftime('%Y%m%d_%H%M%S')}"
        dst.mkdir(parents=True, exist_ok=True)
        for p in list(config.WORK_DIR.iterdir()):
            try:
                shutil.move(str(p), str(dst / p.name))
            except OSError:
                pass
        moved = str(dst)
    return {"backup": str(backup), "work_moved_to": moved, "before": before, "after": counts()}


def restore(backup_path: Path) -> dict:
    """Copy a backup back over the live database (a safety backup of the current state is taken first)."""
    backup_path = Path(backup_path)
    if not backup_path.exists():
        raise FileNotFoundError(backup_path)
    safety = backup_db("truoc_khi_khoi_phuc")
    src = sqlite3.connect(str(backup_path))
    try:
        dst = db.connect()
        try:
            src.backup(dst)
        finally:
            dst.close()
    finally:
        src.close()
    return {"restored_from": str(backup_path), "safety_backup": str(safety), "now": counts()}
