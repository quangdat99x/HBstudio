"""Backup, reset and restore of the Studio database; deleting and restoring single segments.

Reset removes every episode, segment, transcript line, job and log row but keeps the settings (paths, models,
zoom parameters) and the theme taxonomy. A full copy of the database is written to backups/ first, and the
scratch folder work/ is moved there too, so a reset can always be undone with `hldb restore <file>`.
Media files on disk (videos, transcripts, cutlists, clips) are never touched.

Deleting a segment (episode page) sets its status to 'archived' instead of removing the row: the episode page,
search, cut and zoom skip it, and re-ingesting the cutlist (every "Chạy tiếp" does) keeps it hidden because the
upsert never overwrites status. Its clip files only move when asked, and then to the Windows Recycle Bin.
"""
from __future__ import annotations

import shutil
import sqlite3
import time
from pathlib import Path

from . import config, db
from .util import now_iso, send_to_trash

BACKUP_DIR = config.BASE_DIR / "backups"
DATA_TABLES = ["segment_titles", "segment_search", "segment_topics", "segment_themes", "segment_entities", "compilation_items",
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


FILE_COLUMNS = ("clip_path", "clip_zoomed_path", "thumbnail_path")


def _with_hooks(ids: list[int]) -> list[dict]:
    """The given segments plus the hooks of every highlight among them (a hook is useless without its parent)."""
    ids = sorted({int(i) for i in ids})
    if not ids:
        return []
    marks = ",".join("?" * len(ids))
    return db.rows(f"SELECT * FROM segments WHERE id IN ({marks}) OR (kind='hook' AND parent_id IN ({marks})) "
                   "ORDER BY episode_id, COALESCE(rank, 999)", ids + ids)


def delete_segments(ids: list[int], trash_files: bool = False) -> dict:
    """Hide segments (and the hooks of deleted highlights) from Studio; optionally send their clips to the Recycle Bin."""
    from .search import rebuild_index
    rows = _with_hooks(ids)
    trashed, errors = [], []
    cleared: dict[int, list[str]] = {}
    if trash_files:                                    # outside the DB transaction: moving files can take a moment
        for s in rows:
            for col in FILE_COLUMNS:
                p = s.get(col)
                if not p:
                    continue
                try:
                    if Path(p).exists():
                        send_to_trash(Path(p))
                        trashed.append(Path(p).name)
                    cleared.setdefault(s["id"], []).append(col)
                except OSError as e:
                    errors.append(str(e))
    with db.tx() as c:
        for s in rows:
            cols = "".join(f"{col}=NULL, " for col in cleared.get(s["id"], []))
            c.execute(f"UPDATE segments SET status='archived', {cols}updated_at=? WHERE id=?", (now_iso(), s["id"]))
    if rows:
        rebuild_index([s["id"] for s in rows])
    return {"deleted": len(rows), "highlights": sum(s["kind"] == "highlight" for s in rows),
            "hooks": sum(s["kind"] == "hook" for s in rows), "trashed": trashed, "errors": errors}


def restore_segments(ids: list[int]) -> dict:
    """Undo delete_segments: the status follows the files that are still there, so the pipeline redoes the rest."""
    from .search import rebuild_index
    rows = [s for s in _with_hooks(ids) if s["status"] == "archived"]
    with db.tx() as c:
        for s in rows:
            if s["clip_zoomed_path"] and Path(s["clip_zoomed_path"]).exists():
                status = "zoomed"
            elif s["clip_path"] and Path(s["clip_path"]).exists():
                status = "cut"
            else:
                status = "selected"
            c.execute("UPDATE segments SET status=?, updated_at=? WHERE id=?", (status, now_iso(), s["id"]))
    if rows:
        rebuild_index([s["id"] for s in rows])
    return {"restored": len(rows), "missing_clips": sum(1 for s in rows if not (s["clip_path"] and Path(s["clip_path"]).exists()))}


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
