"""Danh sách chờ trên trang Hàng đợi: dán sẵn cả loạt link YouTube, rồi mỗi lần bấm "Tải và chạy" một link
(tải cả loạt một lúc dễ bị YouTube chặn bot). Tải xong, tập tự vào pipeline như "Nạp tập mới" và mục được đánh
dấu Xong; mục chưa bấm vẫn là Chưa tải. Link đã có trong lịch sử của Youtube Downloader được đánh dấu Xong ngay khi
nhập (không gọi YouTube lúc nhập).

Bảng link_queue: id, url, video_id, podcast_id (show chọn lúc nhập), title (biết sau khi tải), status
('pending' | 'downloading' | 'done' | 'error'), job_id (job tải trong bảng jobs, để hiện tiến độ), episode_id,
filepath, error, added_at, done_at.
"""
from __future__ import annotations

import csv
import logging
import re
import uuid
from typing import Optional

from . import config, db
from .util import now_iso

log = logging.getLogger("studio.link_queue")

_URL_RE = re.compile(r'https?://[^\s<>"\']+')
_ID_RES = (
    re.compile(r"(?:v=|/shorts/|/live/|/embed/)([A-Za-z0-9_-]{11})"),
    re.compile(r"youtu\.be/([A-Za-z0-9_-]{11})"),
)
STATUS_VI = {"pending": "Chưa tải", "downloading": "Đang tải", "done": "Xong", "error": "Lỗi"}


def ensure_schema(conn) -> None:
    with conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS link_queue (
            id TEXT PRIMARY KEY,
            url TEXT NOT NULL,
            video_id TEXT,
            podcast_id TEXT,
            title TEXT DEFAULT '',
            status TEXT DEFAULT 'pending',
            job_id INTEGER,
            episode_id TEXT,
            filepath TEXT,
            error TEXT,
            added_at TEXT,
            done_at TEXT
        );
        """)
        # Studio tắt giữa lúc tải: mục đó quay về Chưa tải
        conn.execute("UPDATE link_queue SET status='pending', job_id=NULL WHERE status='downloading'")


# ---------------------------------------------------------------- helpers
def video_id_of(url: str) -> str:
    for rx in _ID_RES:
        m = rx.search(url)
        if m:
            return m.group(1)
    return url.strip()


def extract_urls(text: str) -> list[str]:
    """Mỗi dòng một link; bỏ chữ thừa quanh link, dòng trống, link trùng (giữ thứ tự)."""
    out, seen = [], set()
    for line in (text or "").splitlines():
        m = _URL_RE.search(line)
        if not m:
            continue
        url = m.group(0).rstrip(".,;)")
        if url not in seen:
            seen.add(url)
            out.append(url)
    return out


def _downloader_history() -> dict[str, dict]:
    """video_id -> dòng lịch sử của Youtube Downloader (history.csv), đọc thẳng file nên không cần tool đang chạy."""
    path = config.DOWNLOADER_DIR / "history.csv"
    try:
        with open(path, "r", encoding="utf-8", newline="") as f:
            return {r.get("video_id"): r for r in csv.DictReader(f) if r.get("video_id")}
    except OSError:
        return {}


def _row(r) -> dict:
    d = dict(r)
    d["status_vi"] = STATUS_VI.get(d.get("status"), d.get("status"))
    return d


# ---------------------------------------------------------------- read / write
def items() -> list[dict]:
    rows = db.rows("""SELECT q.*, j.progress AS job_progress, j.message AS job_message, j.status AS job_status
                      FROM link_queue q LEFT JOIN jobs j ON j.id = q.job_id ORDER BY q.rowid""")
    return [_row(r) for r in rows]


def get(item_id: str) -> Optional[dict]:
    r = db.row("SELECT * FROM link_queue WHERE id=?", (item_id,))
    return _row(r) if r else None


def add(text: str, podcast_id: Optional[str]) -> dict:
    urls = extract_urls(text)
    if not urls:
        return {"error": "Không thấy link nào trong nội dung dán vào."}
    pid = (podcast_id or "").strip().upper() or None
    history = _downloader_history()
    known = {r["video_id"] for r in db.rows("SELECT video_id FROM link_queue")}
    added = already_done = skipped = 0
    with db.tx() as c:
        for url in urls:
            vid = video_id_of(url)
            if vid in known:
                skipped += 1
                continue
            known.add(vid)
            prev = history.get(vid)
            c.execute("""INSERT INTO link_queue(id, url, video_id, podcast_id, title, status, filepath, added_at, done_at)
                         VALUES(?,?,?,?,?,?,?,?,?)""",
                      (uuid.uuid4().hex[:8], url, vid, pid, (prev or {}).get("title") or "",
                       "done" if prev else "pending", (prev or {}).get("filepath"), now_iso(),
                       (prev or {}).get("date") if prev else None))
            added += 1
            if prev:
                already_done += 1
    return {"added": added, "already_done": already_done, "skipped": skipped}


def update(item_id: str, **fields) -> Optional[dict]:
    if fields:
        sets = ", ".join(f"{k}=?" for k in fields)
        with db.tx() as c:
            c.execute(f"UPDATE link_queue SET {sets} WHERE id=?", (*fields.values(), item_id))
    return get(item_id)


def mark(item_id: str, status: str) -> Optional[dict]:
    """Người dùng tự đánh dấu Xong / Chưa tải."""
    if status == "done":
        return update(item_id, status="done", done_at=now_iso(), error=None)
    return update(item_id, status="pending", done_at=None, error=None, job_id=None)


def remove(item_id: str) -> bool:
    with db.tx() as c:
        return c.execute("DELETE FROM link_queue WHERE id=?", (item_id,)).rowcount > 0


def remove_done() -> int:
    with db.tx() as c:
        return c.execute("DELETE FROM link_queue WHERE status='done'").rowcount


# ---------------------------------------------------------------- download one
def start(item_id: str, orch, podcast_id: Optional[str] = None) -> dict:
    """Tải một mục qua Youtube Downloader rồi đưa vào pipeline (như Nạp tập mới). Xong thì tự đánh dấu."""
    item = get(item_id)
    if not item:
        return {"error": "Mục này không còn trong danh sách."}
    if item["status"] == "downloading":
        return {"error": "Mục này đang tải."}
    pid = (podcast_id or item.get("podcast_id") or "").strip().upper() or None

    def _done(path, res, error):
        if error:
            update(item_id, status="error", error=str(error)[:500], done_at=None)
            return
        update(item_id, status="done", error=None, done_at=now_iso(), title=path.name if path else item.get("title"),
               filepath=str(path) if path else None, episode_id=(res or {}).get("episode_id"))

    res = orch.intake_url(item["url"], pid, on_result=_done)
    if res.get("error"):
        update(item_id, status="error", error=res["error"])
        return res
    update(item_id, status="downloading", error=None, podcast_id=pid, job_id=res.get("job_id"))
    return {"message": "Đang tải, xong sẽ tự vào pipeline và đánh dấu Xong.", "item": get(item_id)}
