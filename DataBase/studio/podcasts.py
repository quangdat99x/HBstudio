"""Podcast profiles: everything that differs from one show to another, kept in the `podcasts` table.

A profile says how Studio recognises the show's video files, which skills select highlights and write titles for it,
the Canva thumbnail template, and the names the prompts use (host, the YouTube channel the clips go to). Code that
used to say "Joe Rogan" or "JRE" reads them from here, so a new show is a new row, not a code change.

File name patterns (one per line, the first matching line wins, profiles tried in `sort` order):
  - template: literal text plus {num} (episode number), {guest}, {date} (YYYY-MM-DD, YYYYMMDD …) and {*} (anything).
    Spaces and the gaps around placeholders match any amount of whitespace, case is ignored, and the pattern may
    appear anywhere in the name ("Joe Rogan Experience #{num} - {guest}").
  - raw regex: a line starting with "re:" and the named groups num / guest / date.
Episode id = <podcast id>-<number>; a show without episode numbers uses {date}: SHOW-20261105.

Role: `main` shows run the whole pipeline (highlights, clips, titles). `support` shows only get a transcript: they are
the supplementary library a main show's compilation pulls extra clips from (other experts, evidence, counterpoints).
A support show may have no file pattern at all (the default BOTRO library holds episodes of many different podcasts):
its videos come in through the Queue page with the show picked by hand, get the next free number, and are recognised
again later by their file name stored in the database.

The list of shows travels between machines through `shows.json` next to this module (it is in Git, the database is
not). The main machine (see `_sync_main.json`) rewrites the file whenever a show is saved or deleted on the Settings
page; every other machine applies the file to its `podcasts` table when it changes (at start-up and whenever the
profile cache is refreshed, so a `git pull` is enough: no restart). The file wins over local edits on those machines,
shows that only exist locally are kept, and a show removed from the file is not deleted (it may still have episodes).
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import socket
import threading
import time
from pathlib import Path
from typing import Optional

from . import db

log = logging.getLogger(__name__)
SHOWS_FILE = Path(__file__).with_name("shows.json")
_ROLE_FILE = Path(__file__).resolve().parents[2] / "_sync_main.json"     # C:\Tool\_sync_main.json

ID_RE = re.compile(r"^[A-Z][A-Z0-9]{1,15}$")
_RE_EPISODE_ID = re.compile(r"^([A-Za-z][A-Za-z0-9]*)-(\d+)$")
FIELDS = ("name", "host", "host_short", "channel", "audience", "patterns", "select_skill", "title_skill",
          "thumb_template", "sort", "role")
ROLES = ("main", "support")

# Seeded on the existing rows the first time (only empty fields are filled, so edits on the page are kept).
DEFAULTS = {
    "JRE": {
        "name": "Joe Rogan Experience", "host": "Joe Rogan", "host_short": "Joe", "channel": "JRE Highlights",
        "audience": "khán giả YouTube Mỹ",
        "patterns": "Joe Rogan Experience #{num} - {guest}",
        "select_skill": "chon-noi-dung-jre-v2", "title_skill": "viet-tittle", "thumb_template": "DAHVNt9L56k",
        "sort": 10,
    },
    "JREMMA": {
        "name": "JRE MMA Show", "host": "Joe Rogan", "host_short": "Joe", "channel": "JRE Highlights",
        "audience": "khán giả YouTube Mỹ",
        "patterns": r"re:JRE MMA Show\s*#\s*(?P<num>\d+)\s*(?:with|-)?\s*(?P<guest>.+?)\s*$",
        "select_skill": "chon-noi-dung-jre-v2", "title_skill": "viet-tittle", "thumb_template": "DAHVNt9L56k",
        "sort": 20,
    },
    # supplementary library: episodes of any podcast, transcript only, used by the compilations of the main shows
    "BOTRO": {
        "name": "Podcast bổ trợ", "role": "support", "sort": 900, "audience": "",
    },
}

_lock = threading.Lock()
_cache: dict = {"at": 0.0, "rows": None}
_TTL = 15.0


# ---------------------------------------------------------------- schema
def ensure_schema(conn) -> None:
    """Profile columns on `podcasts` and the podcast filter on topic scans (called by db.init_db)."""
    cols = {"host_short": "TEXT", "channel": "TEXT", "audience": "TEXT", "patterns": "TEXT", "select_skill": "TEXT",
            "title_skill": "TEXT", "thumb_template": "TEXT", "sort": "INTEGER DEFAULT 100", "role": "TEXT"}
    existing = {r[1] for r in conn.execute("PRAGMA table_info(podcasts)")}
    for col, decl in cols.items():
        if col not in existing:
            with conn:
                conn.execute(f"ALTER TABLE podcasts ADD COLUMN {col} {decl}")
    existing = {r[1] for r in conn.execute("PRAGMA table_info(topic_scans)")}
    if "podcast_id" not in existing:
        with conn:
            conn.execute("ALTER TABLE topic_scans ADD COLUMN podcast_id TEXT")      # comma list, empty = every show
    existing = {r[1] for r in conn.execute("PRAGMA table_info(compile_jobs)")}
    if "podcast_ids" not in existing:
        with conn:
            conn.execute("ALTER TABLE compile_jobs ADD COLUMN podcast_ids TEXT")    # shows the scan reads, comma list
    _apply_shows_file(conn, force=False)
    invalidate()


# ---------------------------------------------------------------- read
def invalidate() -> None:
    with _lock:
        _cache["rows"] = None


# ---------------------------------------------------------------- shows.json (list of shows shared through Git)
def is_main_machine() -> bool:
    """The machine named in _sync_main.json owns the list; without that file every machine is its own main."""
    try:
        main = str(json.loads(_ROLE_FILE.read_text(encoding="utf-8")).get("main_machine") or "").strip()
    except (OSError, ValueError):
        return True
    me = os.environ.get("COMPUTERNAME") or socket.gethostname()
    return not main or main.upper() == me.upper()


def _read_shows_file() -> tuple[list[dict], str]:
    """(shows, stamp): the profiles in shows.json and a hash of the file; the built-in DEFAULTS when there is none."""
    try:
        raw = SHOWS_FILE.read_bytes()
        shows = json.loads(raw.decode("utf-8"))
        if not isinstance(shows, list):
            raise ValueError("shows.json must be a list")
        return shows, hashlib.sha1(raw).hexdigest()
    except FileNotFoundError:
        return [{"id": pid, **vals} for pid, vals in DEFAULTS.items()], "defaults"
    except (OSError, ValueError) as e:
        log.warning("shows.json unreadable, keeping the shows in the database: %s", e)
        return [], ""


def _apply_shows_file(conn, force: bool) -> bool:
    """Put the shows of shows.json into `podcasts` when the file changed since the last time (or `force`).
    Missing shows are added, known ones take the file's values. On the main machine the file is written from the
    database, so it only fills gaps there (a machine that edited its shows before the file existed keeps them)."""
    shows, stamp = _read_shows_file()
    if not stamp:
        return False
    seen = conn.execute("SELECT value FROM settings WHERE key='shows_file_stamp'").fetchone()
    if not force and seen and seen[0] == stamp:
        return False
    main = is_main_machine()
    have_cols = {r[1] for r in conn.execute("PRAGMA table_info(podcasts)")}
    with conn:
        for prof in shows:
            pid = str(prof.get("id") or "").strip().upper()
            if not ID_RE.match(pid) or not prof.get("name"):
                continue
            exists = conn.execute("SELECT 1 FROM podcasts WHERE id=?", (pid,)).fetchone()
            if not exists and prof.get("role") == "support":
                # the support library is created once; deleting it on the Settings page is final
                if conn.execute("SELECT 1 FROM settings WHERE key='seeded_support_library'").fetchone():
                    continue
                conn.execute("INSERT OR REPLACE INTO settings(key, value) VALUES('seeded_support_library', '1')")
            conn.execute("INSERT OR IGNORE INTO podcasts(id, name, host) VALUES(?, ?, ?)",
                         (pid, prof["name"], prof.get("host") or ""))
            for k in FIELDS:
                if k not in have_cols or k not in prof:
                    continue
                v = prof[k]
                if main and exists:
                    conn.execute(f"UPDATE podcasts SET {k}=? WHERE id=? AND ({k} IS NULL OR {k}='' "
                                 f"OR ?='sort' AND {k}=100)", (v, pid, k))
                else:
                    conn.execute(f"UPDATE podcasts SET {k}=? WHERE id=?", (v, pid))
        conn.execute("INSERT OR REPLACE INTO settings(key, value) VALUES('shows_file_stamp', ?)", (stamp,))
    if not main:
        log.info("shows.json applied: %d show(s) from the main machine", len(shows))
    invalidate()
    return True


def write_shows_file() -> Optional[Path]:
    """Main machine only: the `podcasts` table as shows.json, so a commit carries the list to the other machines."""
    if not is_main_machine():
        return None
    rows = db.rows("SELECT * FROM podcasts ORDER BY COALESCE(sort, 100), id")
    out = [{"id": r["id"], **{k: r.get(k) for k in FIELDS}} for r in rows]
    raw = (json.dumps(out, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    try:
        if SHOWS_FILE.exists() and SHOWS_FILE.read_bytes() == raw:
            return SHOWS_FILE
        tmp = SHOWS_FILE.with_suffix(".json.tmp")
        tmp.write_bytes(raw)
        os.replace(tmp, SHOWS_FILE)
        db.set_setting("shows_file_stamp", hashlib.sha1(raw).hexdigest())
    except OSError as e:
        log.warning("cannot write %s: %s", SHOWS_FILE, e)
        return None
    return SHOWS_FILE


def sync_from_file() -> bool:
    """Apply shows.json when its content changed (cheap: a read + hash of a small file). Runs with the cache refresh,
    so a machine that just pulled the main machine's code picks the new list up within _TTL seconds."""
    try:
        return _apply_shows_file(db.get_conn(), force=False)
    except Exception as e:                                  # never let the show list break a page
        log.warning("shows.json sync: %s", e)
        return False


def all_profiles() -> list[dict]:
    with _lock:
        if _cache["rows"] is not None and time.time() - _cache["at"] < _TTL:
            return _cache["rows"]
    sync_from_file()
    rows = db.rows("SELECT * FROM podcasts ORDER BY COALESCE(sort, 100), id")
    for r in rows:
        r["host_short"] = r.get("host_short") or (r.get("host") or "").split(" ")[0] or "host"
        r["channel"] = r.get("channel") or r.get("name") or r["id"]
        r["compiled"] = [p for p in (compile_pattern(x) for x in split_patterns(r.get("patterns"))) if p]
        r["role"] = r.get("role") if r.get("role") in ROLES else "main"
    with _lock:
        _cache["rows"], _cache["at"] = rows, time.time()
    return rows


def get(podcast_id: Optional[str]) -> Optional[dict]:
    pid = (podcast_id or "").strip().upper()
    return next((p for p in all_profiles() if p["id"] == pid), None)


def for_episode(ep) -> dict:
    """Profile of an episode (dict with podcast_id/id, or an episode id). Falls back to a neutral profile."""
    if isinstance(ep, dict):
        pid = ep.get("podcast_id") or (parse_id(ep.get("id") or "") or {}).get("podcast_id")
    else:
        pid = (parse_id(str(ep or "")) or {}).get("podcast_id")
        if not pid and ep:
            pid = db.scalar("SELECT podcast_id FROM episodes WHERE id=?", (str(ep).upper(),))
    prof = get(pid)
    if prof:
        return prof
    return {"id": pid or "?", "name": pid or "podcast", "host": "host", "host_short": "host", "channel": pid or "",
            "audience": "khán giả YouTube Mỹ", "patterns": "", "select_skill": "", "title_skill": "",
            "thumb_template": "", "compiled": [], "role": "main"}


def is_support(prof: Optional[dict]) -> bool:
    return bool(prof) and prof.get("role") == "support"


def support_ids() -> list[str]:
    return [p["id"] for p in all_profiles() if p["role"] == "support"]


def main_profiles() -> list[dict]:
    return [p for p in all_profiles() if p["role"] == "main"]


def split_ids(text: Optional[str]) -> list[str]:
    """'JRE, BOTRO' -> ['JRE', 'BOTRO'] (known shows only, order kept)."""
    known = {p["id"] for p in all_profiles()}
    out = []
    for x in re.split(r"[,\s]+", text or ""):
        x = x.strip().upper()
        if x in known and x not in out:
            out.append(x)
    return out


def is_jre(prof: dict) -> bool:
    """The JRE-family profiles: the skills and prompts were written for them, nothing to adapt."""
    return (prof.get("host") or "").strip().lower() == "joe rogan"


def source_label(podcast_id: Optional[str], title: Optional[str] = None) -> str:
    """Where a clip comes from, for prompts and pages: the show name, or for a library without a single host (the
    support library holds many podcasts) the show name plus the episode's own title (its YouTube file name)."""
    prof = get(podcast_id)
    if not prof:
        return podcast_id or "?"
    if prof.get("host") or not title:
        return prof["name"]
    return f"{prof['name']}: {title[:100]}"


def label(prof: dict) -> str:
    return f"{prof.get('name')} (host {prof.get('host')})" if prof.get("host") else str(prof.get("name"))


def host_names(podcast_ids: Optional[list[str]] = None) -> str:
    """'Joe Rogan' for one show, 'Joe Rogan, Shawn Ryan' for several: used by prompts that cover many episodes."""
    profs = [get(p) for p in podcast_ids] if podcast_ids else all_profiles()
    names = []
    for p in profs:
        if p and p.get("host") and p["host"] not in names:
            names.append(p["host"])
    return ", ".join(names) or "podcast"


def show_names(podcast_ids: Optional[list[str]] = None) -> str:
    profs = [get(p) for p in podcast_ids] if podcast_ids else all_profiles()
    return ", ".join(p["name"] for p in profs if p) or "podcast"


# ---------------------------------------------------------------- patterns
def split_patterns(text: Optional[str]) -> list[str]:
    return [ln.strip() for ln in (text or "").splitlines() if ln.strip() and not ln.strip().startswith("//")]


_PLACE = {"{num}": r"(?P<num>\d+)", "{guest}": r"(?P<guest>.+?)",
          "{date}": r"(?P<date>\d{4}[-._ ]?\d{2}[-._ ]?\d{2})", "{*}": r".*?"}


def pattern_regex(pattern: str) -> str:
    p = pattern.strip()
    if p.lower().startswith("re:"):
        return p[3:].strip()
    parts = []
    for tok in re.split(r"(\{num\}|\{guest\}|\{date\}|\{\*\})", p):
        if tok in _PLACE:
            parts.append(_PLACE[tok])
        elif tok.strip():
            parts.append(r"\s*".join(re.escape(w) for w in tok.split()))
    return r"\s*".join(parts) + r"\s*$"


def compile_pattern(pattern: str) -> Optional[re.Pattern]:
    try:
        return re.compile(pattern_regex(pattern), re.I)
    except re.error:
        return None


def pattern_errors(text: str) -> list[str]:
    errs = []
    for p in split_patterns(text):
        try:
            rx = re.compile(pattern_regex(p), re.I)
        except re.error as e:
            errs.append(f"{p}: regex lỗi ({e})")
            continue
        if "num" not in rx.groupindex and "date" not in rx.groupindex:
            errs.append(f"{p}: cần {{num}} hoặc {{date}} để đặt mã tập")
    return errs


def _match(prof: dict, stem: str) -> Optional[dict]:
    for rx in prof["compiled"]:
        m = rx.search(stem)
        if not m:
            continue
        g = m.groupdict()
        if g.get("num"):
            number = int(g["num"])
        elif g.get("date"):
            number = int(re.sub(r"\D", "", g["date"]))
        else:
            continue
        guest = (g.get("guest") or "").strip(" -–—|") or None
        return {"episode_id": f"{prof['id']}-{number}", "podcast_id": prof["id"], "number": number, "guest": guest}
    return None


def parse_name(stem: str, podcast_id: Optional[str] = None) -> Optional[dict]:
    """{episode_id, podcast_id, number, guest} of a cleaned video/folder name, or None when no show matches.
    A name no pattern knows is still recognised when an episode registered by hand has that video (or its clip
    folder): that is how episodes of the support library are found again by the media scan."""
    for prof in all_profiles():
        if podcast_id and prof["id"] != podcast_id.upper():
            continue
        info = _match(prof, stem)
        if info:
            return info
    return known_name(stem, podcast_id)


def known_name(stem: str, podcast_id: Optional[str] = None) -> Optional[dict]:
    from .util import clean_stem, cutter_safe_stem
    key = stem.strip().lower()
    if not key:
        return None
    for r in db.rows("SELECT id, podcast_id, number, guest, source_video FROM episodes WHERE source_video IS NOT NULL "
                     "AND source_video!=''"):
        if podcast_id and r["podcast_id"] != podcast_id.upper():
            continue
        vs = clean_stem(r["source_video"])
        if key in (vs.lower(), cutter_safe_stem(vs).lower()):
            return {"episode_id": r["id"], "podcast_id": r["podcast_id"], "number": r["number"], "guest": r["guest"]}
    return None


def next_number(podcast_id: str) -> int:
    return int(db.scalar("SELECT COALESCE(MAX(number), 0) FROM episodes WHERE podcast_id=?", (podcast_id.upper(),)) or 0) + 1


def assign(stem: str, podcast_id: str) -> Optional[dict]:
    """Episode info for a video the user put into a chosen show by hand: its own pattern if one matches, the episode
    it already is, else the show's next free number (guest unknown, the file name stays as the title)."""
    prof = get(podcast_id)
    if not prof:
        return None
    info = _match(prof, stem) or known_name(stem, prof["id"])
    if info:
        return info
    n = next_number(prof["id"])
    return {"episode_id": f"{prof['id']}-{n}", "podcast_id": prof["id"], "number": n, "guest": None, "title": stem}


def parse_id(episode_id: str) -> Optional[dict]:
    m = _RE_EPISODE_ID.match((episode_id or "").strip())
    if not m:
        return None
    pod = m.group(1).upper()
    if not any(p["id"] == pod for p in all_profiles()):
        return None
    return {"episode_id": f"{pod}-{int(m.group(2))}", "podcast_id": pod, "number": int(m.group(2))}


# ---------------------------------------------------------------- write (Settings page)
def save(data: dict) -> dict:
    pid = (data.get("id") or "").strip().upper()
    if not ID_RE.match(pid):
        return {"error": "mã show phải là 2–16 chữ in hoa/số, bắt đầu bằng chữ (vd SRS, GOODHANG)"}
    if not (data.get("name") or "").strip():
        return {"error": "thiếu tên show"}
    errs = pattern_errors(data.get("patterns") or "")
    if errs:
        return {"error": "; ".join(errs)}
    vals = {k: (str(data.get(k)).strip() if data.get(k) is not None else "") for k in FIELDS}
    vals["role"] = vals["role"] if vals["role"] in ROLES else "main"
    try:
        vals["sort"] = int(vals["sort"] or 100)
    except ValueError:
        vals["sort"] = 100
    with db.tx() as c:
        c.execute("INSERT OR IGNORE INTO podcasts(id, name) VALUES(?, ?)", (pid, vals["name"]))
        c.execute(f"UPDATE podcasts SET {', '.join(f'{k}=?' for k in FIELDS)} WHERE id=?", (*vals.values(), pid))
    invalidate()
    write_shows_file()
    return {"ok": True, "id": pid}


def delete(podcast_id: str) -> dict:
    pid = (podcast_id or "").upper()
    n = db.scalar("SELECT COUNT(*) FROM episodes WHERE podcast_id=?", (pid,)) or 0
    if n:
        return {"error": f"show {pid} đang có {n} tập trong database, không xoá được"}
    with db.tx() as c:
        c.execute("DELETE FROM podcasts WHERE id=?", (pid,))
    invalidate()
    write_shows_file()
    return {"ok": True}


def test_name(name: str) -> dict:
    """What Studio would make of a file name (Settings page check box)."""
    from .util import clean_stem
    info = parse_name(clean_stem(name))
    return info or {"error": "không show nào nhận tên này"}


def overview() -> list[dict]:
    counts = {r["podcast_id"]: r for r in db.rows(
        "SELECT podcast_id, COUNT(*) AS episodes, "
        "(SELECT COUNT(*) FROM segments s JOIN episodes e2 ON e2.id=s.episode_id WHERE e2.podcast_id=e.podcast_id "
        " AND s.kind='highlight' AND s.status!='archived') AS highlights FROM episodes e GROUP BY podcast_id")}
    out = []
    for p in all_profiles():
        c = counts.get(p["id"]) or {}
        out.append({**{k: v for k, v in p.items() if k != "compiled"}, "episodes": c.get("episodes", 0),
                    "highlights": c.get("highlights", 0)})
    return out


def as_json() -> str:
    return json.dumps([{"id": p["id"], "name": p["name"]} for p in all_profiles()], ensure_ascii=False)
