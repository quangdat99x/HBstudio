"""Channel watch: each show can follow its main YouTube channel. On a schedule Studio lists the channel's newest
uploads (yt-dlp --flat-playlist, no download, one light request), keeps the videos that are new, long enough and match
the show's keywords, downloads them through the Downloader and runs them through the pipeline (orchestrator.intake_url),
so they end up indexed like any other episode.

Tables:
  channel_watch   one row per show: channel URL, on/off, keywords, schedule, last/next scan, last result
  channel_videos  every video a scan has seen, with what Studio did with it (so nothing is downloaded twice)

The first scan of a channel only records what is already there (status `baseline`): following a channel never pulls
its whole back catalogue. Older videos can still be downloaded one by one from the list on the Settings page.

Schedule: fixed times of day ("06:00, 18:30") or, when none are set, every N hours.
Keywords: one per line or comma separated, case-insensitive, matched on the title. Empty = every new video.
A title that matches another show's file pattern goes to that show (one channel can carry several shows, e.g.
PowerfulJRE posts JRE and JRE MMA Show).
"""
from __future__ import annotations

import json
import logging
import re
import subprocess
import threading
from datetime import datetime, timedelta
from typing import Optional

from . import config, db, notify, podcasts
from .util import now_iso

log = logging.getLogger("studio.channel_watch")

FIELDS = ("channel_url", "enabled", "keywords", "exclude_keywords", "min_minutes", "schedule_times", "every_hours",
          "max_per_scan", "scan_depth")
DEFAULTS = {"enabled": 0, "keywords": "", "exclude_keywords": "", "min_minutes": 20, "schedule_times": "",
            "every_hours": 6, "max_per_scan": 3, "scan_depth": 15}
STATUS_VI = {
    "baseline": "có sẵn lúc bắt đầu theo dõi",
    "queued": "đã đưa đi tải + index",
    "skip_keyword": "không khớp keyword",
    "skip_exclude": "dính keyword loại trừ",
    "skip_short": "ngắn hơn ngưỡng",
    "skip_limit": "vượt giới hạn mỗi lượt quét",
    "skip_exists": "tập đã có trong Studio",
    "error": "lỗi",
}
_RE_TIME = re.compile(r"^([01]?\d|2[0-3])[:hH.]([0-5]\d)$")

_scan_locks: dict[str, threading.Lock] = {}
_locks_guard = threading.Lock()


# ---------------------------------------------------------------- schema
def ensure_schema(conn) -> None:
    with conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS channel_watch (
            podcast_id TEXT PRIMARY KEY,
            channel_url TEXT,
            enabled INTEGER DEFAULT 0,
            keywords TEXT DEFAULT '',
            exclude_keywords TEXT DEFAULT '',
            min_minutes REAL DEFAULT 20,
            schedule_times TEXT DEFAULT '',
            every_hours REAL DEFAULT 6,
            max_per_scan INTEGER DEFAULT 3,
            scan_depth INTEGER DEFAULT 15,
            last_scan_at TEXT,
            next_scan_at TEXT,
            last_result TEXT,
            last_error TEXT,
            channel_name TEXT
        );
        CREATE TABLE IF NOT EXISTS channel_videos (
            video_id TEXT NOT NULL,
            podcast_id TEXT NOT NULL,
            title TEXT,
            url TEXT,
            duration_sec REAL,
            status TEXT,
            target_podcast TEXT,
            note TEXT,
            first_seen TEXT,
            updated_at TEXT,
            PRIMARY KEY (podcast_id, video_id)
        );
        CREATE INDEX IF NOT EXISTS idx_channel_videos_seen ON channel_videos(podcast_id, first_seen);
        """)


# ---------------------------------------------------------------- config
def split_words(text: Optional[str]) -> list[str]:
    return [w.strip().lower() for w in re.split(r"[,\n;]+", text or "") if w.strip()]


def parse_times(text: Optional[str]) -> list[tuple[int, int]]:
    out = []
    for tok in re.split(r"[,\s;]+", text or ""):
        m = _RE_TIME.match(tok.strip())
        if m:
            out.append((int(m.group(1)), int(m.group(2))))
    return sorted(set(out))


def get(podcast_id: str) -> dict:
    pid = (podcast_id or "").upper()
    r = db.row("SELECT * FROM channel_watch WHERE podcast_id=?", (pid,)) or {}
    return {**DEFAULTS, "podcast_id": pid, "channel_url": "", **{k: v for k, v in r.items() if v is not None}}


def all_configs() -> dict[str, dict]:
    return {p["id"]: get(p["id"]) for p in podcasts.all_profiles()}


def save(podcast_id: str, data: dict) -> dict:
    pid = (podcast_id or "").upper()
    if not podcasts.get(pid):
        return {"error": f"không có show {pid}"}
    url = (data.get("channel_url") or "").strip()
    if url and not re.match(r"^https?://(www\.|m\.)?(youtube\.com|youtu\.be)/", url, re.I):
        return {"error": "link kênh phải là link YouTube, vd https://www.youtube.com/@joerogan"}
    enabled = 1 if str(data.get("enabled")).lower() in ("1", "true", "on", "yes") else 0
    if enabled and not url:
        return {"error": "bật quét thì cần link kênh"}
    bad = [t for t in re.split(r"[,\s;]+", data.get("schedule_times") or "") if t.strip() and not _RE_TIME.match(t.strip())]
    if bad:
        return {"error": f"giờ quét không hợp lệ: {', '.join(bad)} (dạng 06:00, 18:30)"}

    def num(key, lo, hi, cast=float):
        try:
            return max(lo, min(hi, cast(data.get(key) if data.get(key) not in (None, "") else DEFAULTS[key])))
        except (TypeError, ValueError):
            return DEFAULTS[key]

    vals = {
        "channel_url": url, "enabled": enabled,
        "keywords": (data.get("keywords") or "").strip(),
        "exclude_keywords": (data.get("exclude_keywords") or "").strip(),
        "min_minutes": num("min_minutes", 0, 600),
        "schedule_times": ", ".join(f"{h:02d}:{m:02d}" for h, m in parse_times(data.get("schedule_times"))),
        "every_hours": num("every_hours", 0.25, 24 * 7),
        "max_per_scan": num("max_per_scan", 1, 50, int),
        "scan_depth": num("scan_depth", 5, 100, int),
    }
    old = get(pid)
    with db.tx() as c:
        c.execute("INSERT OR IGNORE INTO channel_watch(podcast_id) VALUES(?)", (pid,))
        c.execute(f"UPDATE channel_watch SET {', '.join(f'{k}=?' for k in FIELDS)} WHERE podcast_id=?",
                  (*[vals[k] for k in FIELDS], pid))
        if old.get("channel_url") and old["channel_url"] != url:
            # another channel: start over (its first scan records a fresh baseline)
            c.execute("DELETE FROM channel_videos WHERE podcast_id=?", (pid,))
            c.execute("UPDATE channel_watch SET last_scan_at=NULL, last_result=NULL, last_error=NULL, channel_name=NULL "
                      "WHERE podcast_id=?", (pid,))
    _reschedule(pid)
    return {"ok": True, **status(pid)}


# ---------------------------------------------------------------- schedule
def next_run(cfg: dict, after: Optional[datetime] = None) -> Optional[datetime]:
    if not cfg.get("enabled") or not cfg.get("channel_url"):
        return None
    now = datetime.now()
    times = parse_times(cfg.get("schedule_times"))
    last = _parse_dt(cfg.get("last_scan_at"))
    if times:
        base = after or now
        for day in range(0, 3):
            d = (base + timedelta(days=day)).date()
            for h, m in times:
                t = datetime(d.year, d.month, d.day, h, m)
                if t > base:
                    return t
        return None
    hours = float(cfg.get("every_hours") or 6)
    if not last:
        return now                                   # never scanned: first scan (baseline) right away
    return max(now, last + timedelta(hours=hours)) if after is None else after + timedelta(hours=hours)


def _parse_dt(s: Optional[str]) -> Optional[datetime]:
    try:
        return datetime.fromisoformat(s) if s else None
    except ValueError:
        return None


def _reschedule(pid: str, after: Optional[datetime] = None) -> None:
    cfg = get(pid)
    nxt = next_run(cfg, after)
    if cfg.get("enabled") and cfg.get("channel_url") and not cfg.get("last_scan_at") and parse_times(cfg.get("schedule_times")):
        nxt = datetime.now()                         # fixed times too: the baseline scan does not wait for the first slot
    with db.tx() as c:
        c.execute("UPDATE channel_watch SET next_scan_at=? WHERE podcast_id=?",
                  (nxt.replace(microsecond=0).isoformat() if nxt else None, pid))


# ---------------------------------------------------------------- listing (yt-dlp)
def normalize_url(url: str) -> str:
    """A channel link lists its uploads tab (/videos: no Shorts, no live). Playlist and other tab links stay as they are."""
    u = url.strip().split("#")[0].rstrip("/")
    if "list=" in u or "/playlist" in u:
        return u
    m = re.match(r"^(https?://(?:www\.|m\.)?youtube\.com/(?:@[^/?]+|channel/[^/?]+|c/[^/?]+|user/[^/?]+))(/.*)?$", u, re.I)
    if m and not m.group(2):
        return m.group(1) + "/videos"
    return u


def list_channel(url: str, depth: int = 15) -> dict:
    """{channel, entries: [{id, title, url, duration, live_status}]} of the newest uploads, newest first."""
    py = str(config.PY_CUTTER) if config.PY_CUTTER.exists() else "python"
    cmd = [py, "-m", "yt_dlp", "--flat-playlist", "--dump-single-json", "--playlist-end", str(int(depth)),
           "--no-warnings", "--ignore-no-formats-error", normalize_url(url)]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180,
                             creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except subprocess.TimeoutExpired:
        raise RuntimeError("yt-dlp quá 3 phút không trả danh sách kênh")
    if out.returncode != 0 or not out.stdout.strip():
        err = (out.stderr or "").strip().splitlines()
        raise RuntimeError("yt-dlp không đọc được kênh: " + (err[-1] if err else f"mã {out.returncode}"))
    data = json.loads(out.stdout)
    entries = []
    for e in data.get("entries") or []:
        if not e or not e.get("id"):
            continue
        if e.get("entries"):                         # channel root returned tabs: take the uploads inside
            entries.extend(x for x in e["entries"] if x and x.get("id"))
            continue
        entries.append(e)
    return {"channel": data.get("channel") or data.get("uploader") or data.get("title") or "",
            "entries": [{"id": e["id"], "title": e.get("title") or "", "duration": e.get("duration"),
                         "live_status": e.get("live_status"),
                         "url": e.get("url") if str(e.get("url") or "").startswith("http")
                         else f"https://www.youtube.com/watch?v={e['id']}"} for e in entries[:depth]]}


# ---------------------------------------------------------------- filter
def classify(cfg: dict, video: dict) -> tuple[str, str, Optional[str]]:
    """(status, note, target show) for a new video: what the scan does with it."""
    title = video.get("title") or ""
    low = title.lower()
    excl = [w for w in split_words(cfg.get("exclude_keywords")) if w in low]
    if excl:
        return "skip_exclude", f"dính: {', '.join(excl)}", None
    kws = split_words(cfg.get("keywords"))
    if kws:
        hit = [w for w in kws if w in low]
        if not hit:
            return "skip_keyword", "", None
        note = f"khớp: {', '.join(hit)}"
    else:
        note = ""
    mins = float(cfg.get("min_minutes") or 0)
    dur = video.get("duration")
    if mins and dur is not None and float(dur) < mins * 60:
        return "skip_short", f"{float(dur) / 60:.0f} phút < {mins:g}", None
    from .util import clean_stem
    info = podcasts.parse_name(clean_stem(title))
    target = info["podcast_id"] if info else cfg["podcast_id"]
    if info and db.scalar("SELECT 1 FROM episodes WHERE id=?", (info["episode_id"],)):
        return "skip_exists", info["episode_id"], target
    return "queued", note, target


# ---------------------------------------------------------------- scan
def _lock(pid: str) -> threading.Lock:
    with _locks_guard:
        return _scan_locks.setdefault(pid, threading.Lock())


def scan(podcast_id: str, orch=None, manual: bool = False) -> dict:
    """List the channel, record new videos, send the kept ones to the pipeline. Safe to call from any thread."""
    pid = podcast_id.upper()
    lk = _lock(pid)
    if not lk.acquire(blocking=False):
        return {"message": f"{pid} đang quét"}
    try:
        return _scan(pid, orch, manual)
    finally:
        lk.release()


def _scan(pid: str, orch, manual: bool) -> dict:
    cfg = get(pid)
    if not cfg.get("channel_url"):
        return {"error": "show chưa có link kênh"}
    started = datetime.now()
    try:
        listing = list_channel(cfg["channel_url"], int(cfg.get("scan_depth") or 15))
    except Exception as e:  # noqa: BLE001
        log.warning("channel scan %s failed: %s", pid, e)
        with db.tx() as c:
            c.execute("UPDATE channel_watch SET last_scan_at=?, last_error=?, last_result=? WHERE podcast_id=?",
                      (now_iso(), str(e)[:500], "lỗi khi đọc kênh", pid))
        _reschedule(pid, None if manual else started)
        notify.notify("error", f"Quét kênh {pid} lỗi", str(e)[:300], "/settings#podcasts", key=f"chwatch-err:{pid}")
        return {"error": str(e)}

    baseline = not cfg.get("last_scan_at") and not db.scalar("SELECT 1 FROM channel_videos WHERE podcast_id=?", (pid,))
    known = {r["video_id"] for r in db.rows("SELECT video_id FROM channel_videos WHERE podcast_id=?", (pid,))}
    limit = int(cfg.get("max_per_scan") or 3)
    new_rows, to_queue = [], []
    # oldest first, so with a limit the earliest new upload goes first and the rest wait for the next scan
    for v in reversed(listing["entries"]):
        if v["id"] in known:
            continue
        if v.get("live_status") in ("is_live", "is_upcoming", "post_live"):
            continue                                  # not downloadable yet: picked up by a later scan
        if baseline:
            st, note, target = "baseline", "", None
        else:
            st, note, target = classify(cfg, v)
            if st == "queued":
                if len(to_queue) >= limit:
                    continue                          # over the per-scan limit: left unrecorded, the next scan takes it
                to_queue.append((v, target))
        new_rows.append((v, st, note, target))

    now = now_iso()
    with db.tx() as c:
        for v, st, note, target in new_rows:
            c.execute("INSERT OR IGNORE INTO channel_videos(video_id, podcast_id, title, url, duration_sec, status, "
                      "target_podcast, note, first_seen, updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
                      (v["id"], pid, v["title"], v["url"], v.get("duration"), st, target, note, now, now))

    queued = []
    for v, target in to_queue:
        res = _send(pid, v, target, orch)
        if not res.get("error"):
            queued.append(v["title"])

    if baseline:
        result = f"lần đầu: ghi nhận {len(new_rows)} video đang có, từ giờ chỉ lấy video mới"
    else:
        skipped = len(new_rows) - len(to_queue)
        result = (f"{len(new_rows)} video mới · tải {len(queued)}" + (f" · bỏ qua {skipped}" if skipped else "")
                  if new_rows else "không có video mới")
    with db.tx() as c:
        c.execute("UPDATE channel_watch SET last_scan_at=?, last_result=?, last_error=NULL, channel_name=? WHERE podcast_id=?",
                  (now, result, listing.get("channel") or None, pid))
    _reschedule(pid, None if manual else started)
    if queued:
        notify.notify("info", f"Kênh {pid}: {len(queued)} video mới đang tải", " · ".join(t[:80] for t in queued), "/queue")
    log.info("channel scan %s: %s", pid, result)
    return {"message": result, "queued": queued, **status(pid)}


def _send(pid: str, v: dict, target: Optional[str], orch) -> dict:
    if orch is None:
        res = {"error": "pipeline chưa chạy"}
    else:
        try:
            res = orch.intake_url(v["url"], target or pid)
        except Exception as e:  # noqa: BLE001
            res = {"error": str(e)}
    with db.tx() as c:
        if res.get("error"):
            c.execute("UPDATE channel_videos SET status='error', note=?, updated_at=? WHERE podcast_id=? AND video_id=?",
                      (str(res["error"])[:300], now_iso(), pid, v["id"]))
        else:
            c.execute("UPDATE channel_videos SET status='queued', target_podcast=?, updated_at=? WHERE podcast_id=? AND video_id=?",
                      (target or pid, now_iso(), pid, v["id"]))
    return res


def download_one(podcast_id: str, video_id: str, orch) -> dict:
    """Download a video the scan skipped (or recorded as baseline) by hand."""
    pid = podcast_id.upper()
    r = db.row("SELECT * FROM channel_videos WHERE podcast_id=? AND video_id=?", (pid, video_id))
    if not r:
        return {"error": "không có video này trong danh sách quét"}
    from .util import clean_stem
    info = podcasts.parse_name(clean_stem(r["title"] or ""))
    target = info["podcast_id"] if info else pid
    res = _send(pid, {"id": video_id, "url": r["url"], "title": r["title"]}, target, orch)
    return res if res.get("error") else {"message": f"đang tải {r['title'][:80]} → show {target}"}


# ---------------------------------------------------------------- read
def status(podcast_id: str) -> dict:
    cfg = get(podcast_id)
    counts = {r["status"]: r["n"] for r in db.rows(
        "SELECT status, COUNT(*) AS n FROM channel_videos WHERE podcast_id=? GROUP BY status", (cfg["podcast_id"],))}
    return {"config": cfg, "counts": counts}


def videos(podcast_id: str, limit: int = 40) -> list[dict]:
    rows = db.rows("SELECT * FROM channel_videos WHERE podcast_id=? ORDER BY first_seen DESC, rowid DESC LIMIT ?",
                   (podcast_id.upper(), int(limit)))
    for r in rows:
        r["status_vi"] = STATUS_VI.get(r["status"], r["status"])
    return rows


# ---------------------------------------------------------------- scheduler
class ChannelWatcher(threading.Thread):
    """Wakes every minute and scans the channels whose next_scan_at has come."""

    def __init__(self, orch, interval: int = 60):
        super().__init__(name="studio-channel-watch", daemon=True)
        self.orch = orch
        self.interval = interval
        self._stop = threading.Event()

    def stop(self) -> None:
        self._stop.set()

    def run(self) -> None:
        self._stop.wait(20)                           # let Studio finish starting
        try:
            for r in db.rows("SELECT podcast_id FROM channel_watch WHERE enabled=1 AND (next_scan_at IS NULL OR next_scan_at='')"):
                _reschedule(r["podcast_id"])
        except Exception:  # noqa: BLE001
            log.exception("channel watch init")
        while not self._stop.is_set():
            try:
                now = datetime.now().replace(microsecond=0).isoformat()
                due = db.rows("SELECT podcast_id FROM channel_watch WHERE enabled=1 AND channel_url!='' "
                              "AND next_scan_at IS NOT NULL AND next_scan_at<=? ORDER BY next_scan_at", (now,))
                for r in due:
                    if self._stop.is_set():
                        break
                    scan(r["podcast_id"], self.orch)
            except Exception:  # noqa: BLE001
                log.exception("channel watch loop")
            self._stop.wait(self.interval)
