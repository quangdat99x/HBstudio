"""Ingest cutlists (every schema variant), scan clip folders, load transcripts.

Rules:
- Core columns for the fields we filter on, everything else goes to extra_json; raw_json keeps the original entry.
- Segment identity is (episode_id, kind, start_sec, end_sec). Re-ingesting updates, never duplicates, never deletes.
- Backfilled clips (found on disk without a cutlist) may have unknown timestamps; they are matched by clip_path on rescan.
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Optional

from . import config, db, paths
from .util import (clean_stem, clip_filename, cutter_safe_title, ffprobe_duration, find_transcript, hms_to_sec,
                   load_transcript, norm_key, now_iso, parse_episode_id, parse_episode_name, read_json, sec_to_hms,
                   sha1_file, slice_transcript)

log = logging.getLogger("studio.ingest")

CORE_FIELDS = {
    "rank", "kind", "content_rank", "parent_rank", "hook_rank", "start", "end", "duration_sec", "title",
    "summary_vi", "summary_en", "hook_en", "quote_en", "hook_type", "intensity", "cq", "gtf", "final_score",
    "value_axis", "content_type", "core_keyword", "keyword", "keyword_reach", "keyword_credibility",
    "keyword_reason", "satellite_keywords", "topics", "fit_reason", "hooks",
}
TIME_TOLERANCE = 2.0


# ---------------------------------------------------------------- episodes
def upsert_episode(c, ep: dict) -> None:
    """Insert or update an episode. Only non-empty values overwrite existing ones."""
    now = now_iso()
    existing = c.execute("SELECT * FROM episodes WHERE id=?", (ep["id"],)).fetchone()
    if existing is None:
        c.execute(
            """INSERT INTO episodes(id, podcast_id, number, guest, title, source_video, video_path, transcript_path,
                                    clip_folder, duration_sec, guest_profile_json, cutlist_path, stage, created_at, updated_at)
               VALUES(:id, :podcast_id, :number, :guest, :title, :source_video, :video_path, :transcript_path,
                      :clip_folder, :duration_sec, :guest_profile_json, :cutlist_path, :stage, :now, :now)""",
            {**{k: ep.get(k) for k in ("id", "podcast_id", "number", "guest", "title", "source_video", "video_path",
                                       "transcript_path", "clip_folder", "duration_sec", "guest_profile_json",
                                       "cutlist_path")},
             "stage": ep.get("stage") or "new", "now": now})
        return
    sets, params = [], {}
    for k in ("guest", "title", "source_video", "video_path", "transcript_path", "clip_folder", "duration_sec",
              "guest_profile_json", "cutlist_path", "number"):
        v = ep.get(k)
        if v not in (None, "") and v != existing[k]:
            sets.append(f"{k}=:{k}")
            params[k] = v
    if ep.get("stage") and _stage_rank(ep["stage"]) > _stage_rank(existing["stage"]):
        sets.append("stage=:stage")
        params["stage"] = ep["stage"]
    if sets:
        params["id"], params["now"] = ep["id"], now
        c.execute(f"UPDATE episodes SET {', '.join(sets)}, updated_at=:now WHERE id=:id", params)


_STAGE_ORDER = ["new", "downloading", "transcribing", "transcribed", "selecting", "reviewing", "selected",
                "cutting", "cut", "zooming", "zoomed", "indexing", "ready"]


def _stage_rank(stage: Optional[str]) -> int:
    s = (stage or "new").split(":")[0]
    return _STAGE_ORDER.index(s) if s in _STAGE_ORDER else -1


def find_video_for_episode(root: Path, episode_id: str, source_video: Optional[str] = None) -> Optional[Path]:
    """Locate the episode video: exact source_video first, then by parsed episode id.
    Looks in the Full folder first, then in `root` (older layout kept everything in the media root)."""
    dirs = [d for d in dict.fromkeys((paths.full_dir(), Path(root))) if d.is_dir()]
    if source_video and not source_video.startswith("<"):
        for d in dirs:
            p = d / source_video
            if p.exists():
                return p
    best = None
    for d in dirs:
        for p in d.iterdir():
            if p.is_file() and p.suffix.lower() in config.VIDEO_EXTS and not p.name.endswith(".part"):
                info = parse_episode_name(p.name)
                if info and info["episode_id"] == episode_id:
                    if best is None or p.stat().st_size > best.stat().st_size:
                        best = p
    return best


# ---------------------------------------------------------------- cutlists
def _episode_from_cutlist(data: dict, path: Path, root: Path) -> dict:
    ep = data.get("episode") or {}
    eid_raw = str(ep.get("id") or "").strip()
    info = parse_episode_id(eid_raw)
    if info is None:
        m = re.search(r"cutlist_([A-Za-z][A-Za-z0-9]*-\d+)", path.name)
        info = parse_episode_id(m.group(1)) if m else None
    if info is None:
        raise ValueError(f"cannot determine episode id from {path.name} (episode.id={eid_raw!r})")
    source_video = ep.get("source_video") or ""
    if source_video.startswith("<"):
        source_video = ""
    video = find_video_for_episode(root, info["episode_id"], source_video) if root.exists() else None
    transcript = find_transcript(video) if video else None
    profile = ep.get("guest_profile")
    return {
        "id": info["episode_id"], "podcast_id": info["podcast_id"], "number": info["number"],
        "guest": ep.get("guest"), "source_video": video.name if video else (source_video or None),
        "video_path": str(video) if video else None,
        "transcript_path": str(transcript) if transcript else None,
        "guest_profile_json": json.dumps(profile, ensure_ascii=False) if profile else None,
        "cutlist_path": str(path), "stage": "selected",
    }


def _num(v) -> Optional[float]:
    try:
        return float(v) if v not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _segment_record(s: dict, episode_id: str, meta: dict) -> dict:
    start = hms_to_sec(s["start"])
    end = hms_to_sec(s["end"])
    if end <= start:
        raise ValueError(f"end <= start for {s.get('title')!r}")
    kind = (s.get("kind") or "highlight").lower()
    if kind not in ("hook", "highlight"):
        kind = "highlight"
    if kind == "highlight" and str(s.get("title", "")).upper().startswith("HOOK 0") and s.get("parent_rank"):
        kind = "hook"
    extra = {k: v for k, v in s.items() if k not in CORE_FIELDS}
    sat = s.get("satellite_keywords")
    return {
        "episode_id": episode_id, "kind": kind,
        "start_sec": start, "end_sec": end, "start_hms": sec_to_hms(start), "end_hms": sec_to_hms(end),
        "duration_sec": _num(s.get("duration_sec")) or round(end - start, 2),
        "title": str(s.get("title") or "").strip() or f"clip {s.get('rank', '')}",
        "summary_vi": s.get("summary_vi"), "summary_en": s.get("summary_en"),
        "hook_en": s.get("hook_en"), "quote_en": s.get("quote_en"), "hook_type": s.get("hook_type"),
        "intensity": int(_num(s.get("intensity")) or 0) or None,
        "cq": _num(s.get("cq")), "gtf": _num(s.get("gtf")), "final_score": _num(s.get("final_score")),
        "value_axis": s.get("value_axis"), "content_type": s.get("content_type"),
        "core_keyword": s.get("core_keyword") or s.get("keyword"),
        "keyword_reach": s.get("keyword_reach"), "keyword_credibility": s.get("keyword_credibility"),
        "keyword_reason": s.get("keyword_reason"),
        "satellite_keywords_json": json.dumps(sat, ensure_ascii=False) if sat else None,
        "fit_reason": s.get("fit_reason"),
        "rank": int(_num(s.get("rank")) or 0) or None,
        "content_rank": int(_num(s.get("content_rank")) or 0) or None,
        "source_skill": meta.get("source"), "cutlist_version": meta.get("version"),
        "cutlist_path": meta.get("path"),
        "extra_json": json.dumps(extra, ensure_ascii=False) if extra else None,
        "raw_json": json.dumps(s, ensure_ascii=False),
        "_topics": [str(t).strip() for t in (s.get("topics") or []) if str(t).strip()],
        "_parent_rank": s.get("parent_rank"),
        "_hooks": s.get("hooks") or [],
    }


UPDATABLE = ["start_hms", "end_hms", "duration_sec", "title", "summary_vi", "summary_en", "hook_en", "quote_en",
             "hook_type", "intensity", "cq", "gtf", "final_score", "value_axis", "content_type", "core_keyword",
             "keyword_reach", "keyword_credibility", "keyword_reason", "satellite_keywords_json", "fit_reason",
             "rank", "content_rank", "source_skill", "cutlist_version", "cutlist_path", "extra_json", "raw_json"]


def upsert_segment(c, rec: dict) -> int:
    """Insert or update by identity (episode_id, kind, start_sec, end_sec). Returns segment id."""
    now = now_iso()
    existing = c.execute(
        "SELECT id FROM segments WHERE episode_id=? AND kind=? AND start_sec=? AND end_sec=?",
        (rec["episode_id"], rec["kind"], rec["start_sec"], rec["end_sec"])).fetchone()
    if existing:
        sets = ", ".join(f"{k}=:{k}" for k in UPDATABLE if rec.get(k) is not None)
        params = {k: rec.get(k) for k in UPDATABLE}
        params.update({"id": existing["id"], "now": now})
        c.execute(f"UPDATE segments SET {sets}, last_seen=:now, updated_at=:now WHERE id=:id", params)
        seg_id = existing["id"]
    else:
        cols = ["episode_id", "kind", "start_sec", "end_sec", "parent_id", "status", "clip_path", "transcript",
                "analysis_md", "analysis_json"] + UPDATABLE
        params = {k: rec.get(k) for k in cols}
        params.setdefault("status", "selected")
        params["status"] = params["status"] or "selected"
        params.update({"now": now})
        c.execute(
            f"INSERT INTO segments({', '.join(cols)}, last_seen, created_at, updated_at) "
            f"VALUES({', '.join(':' + k for k in cols)}, :now, :now, :now)", params)
        seg_id = c.execute("SELECT last_insert_rowid()").fetchone()[0]
    if rec.get("_topics") is not None:
        set_topics(c, seg_id, rec["_topics"])
    if rec.get("parent_id"):
        c.execute("UPDATE segments SET parent_id=? WHERE id=?", (rec["parent_id"], seg_id))
    return seg_id


def set_topics(c, seg_id: int, topics: list[str]) -> None:
    c.execute("DELETE FROM segment_topics WHERE segment_id=?", (seg_id,))
    for t in topics:
        c.execute("INSERT OR IGNORE INTO topics(name, name_norm) VALUES(?, ?)", (t, norm_key(t)))
        tid = c.execute("SELECT id FROM topics WHERE name=?", (t,)).fetchone()[0]
        c.execute("INSERT OR IGNORE INTO segment_topics(segment_id, topic_id) VALUES(?, ?)", (seg_id, tid))


def ingest_cutlist(path: Path, root: Optional[Path] = None, force: bool = False) -> dict:
    """Parse one cutlist_*.json (V1, V2, V2.7 flat_hooks) into episodes/segments. Idempotent."""
    path = Path(path)
    root = Path(root or db.get_setting("media_root"))
    digest = sha1_file(path)
    conn = db.get_conn()
    if not force:
        seen = conn.execute("SELECT 1 FROM ingest_log WHERE path=? AND sha1=? AND result='ok'",
                            (str(path), digest)).fetchone()
        if seen:
            return {"path": str(path), "skipped": True}
    data = read_json(path)
    meta = {"source": data.get("source"), "version": str(data.get("version", "")), "path": str(path),
            "layout": data.get("cutlist_layout")}
    ep = _episode_from_cutlist(data, path, root)
    segments = data.get("segments") or []
    stats = {"path": str(path), "episode_id": ep["id"], "highlights": 0, "hooks": 0, "errors": []}

    with db.tx(conn) as c:
        upsert_episode(c, ep)
        # pass 1: highlights
        rank_to_id: dict[int, int] = {}
        highlight_records = []
        for s in segments:
            try:
                rec = _segment_record(s, ep["id"], meta)
            except Exception as e:  # noqa: BLE001
                stats["errors"].append(f"{s.get('title')!r}: {e}")
                continue
            if rec["kind"] == "highlight":
                seg_id = upsert_segment(c, rec)
                if rec["rank"]:
                    rank_to_id[rec["rank"]] = seg_id
                highlight_records.append((rec, seg_id))
                stats["highlights"] += 1
        # pass 2: flat hook entries
        flat_hooks = 0
        for s in segments:
            if (s.get("kind") or "").lower() != "hook":
                continue
            try:
                rec = _segment_record(s, ep["id"], meta)
            except Exception as e:  # noqa: BLE001
                stats["errors"].append(f"{s.get('title')!r}: {e}")
                continue
            rec["parent_id"] = rank_to_id.get(int(_num(rec["_parent_rank"]) or 0))
            upsert_segment(c, rec)
            flat_hooks += 1
        # pass 3: nested hooks[] when the cutlist predates the flat layout
        if flat_hooks == 0:
            for rec, parent_id in highlight_records:
                for h in rec["_hooks"]:
                    try:
                        hrec = _segment_record({
                            "kind": "hook", "start": h["start"], "end": h["end"], "duration_sec": h.get("duration_sec"),
                            "title": f"HOOK {int(h.get('rank', 1)):02d} — {rec['title']}",
                            "quote_en": h.get("quote_en"), "hook_en": h.get("quote_en"), "summary_en": h.get("why"),
                            "hook_type": h.get("type"), "topics": rec["_topics"], "core_keyword": rec["core_keyword"],
                            "value_axis": rec["value_axis"], "rank": h.get("flat_rank"),
                        }, ep["id"], meta)
                    except Exception as e:  # noqa: BLE001
                        stats["errors"].append(f"hook of {rec['title']!r}: {e}")
                        continue
                    hrec["parent_id"] = parent_id
                    upsert_segment(c, hrec)
                    flat_hooks += 1
        stats["hooks"] = flat_hooks
        c.execute("INSERT INTO ingest_log(path, sha1, kind, result, ingested_at) VALUES(?,?,?,?,?)",
                  (str(path), digest, "cutlist", "ok" if not stats["errors"] else "partial", now_iso()))
    load_episode_transcript(ep["id"])
    fill_segment_transcripts(ep["id"])
    return stats


# ---------------------------------------------------------------- transcripts
def load_episode_transcript(episode_id: str, force: bool = False) -> int:
    """Load the episode's Whisper transcript into transcript_lines. Returns number of lines."""
    conn = db.get_conn()
    ep = conn.execute("SELECT transcript_path, video_path FROM episodes WHERE id=?", (episode_id,)).fetchone()
    if not ep:
        return 0
    tpath = Path(ep["transcript_path"]) if ep["transcript_path"] else None
    if (not tpath or not tpath.exists()) and ep["video_path"]:
        tpath = find_transcript(Path(ep["video_path"]))
        if tpath:
            with db.tx(conn) as c:
                c.execute("UPDATE episodes SET transcript_path=? WHERE id=?", (str(tpath), episode_id))
    if not tpath or not tpath.exists():
        return 0
    have = conn.execute("SELECT COUNT(*) FROM transcript_lines WHERE episode_id=?", (episode_id,)).fetchone()[0]
    if have and not force:
        return have
    lines = load_transcript(tpath)
    with db.tx(conn) as c:
        c.execute("DELETE FROM transcript_lines WHERE episode_id=?", (episode_id,))
        c.executemany("INSERT INTO transcript_lines(episode_id, seq, start_sec, end_sec, text) VALUES(?,?,?,?,?)",
                      [(episode_id, i, ln["start"], ln["end"], ln["text"]) for i, ln in enumerate(lines)])
        if ep["video_path"]:
            dur = conn.execute("SELECT duration_sec FROM episodes WHERE id=?", (episode_id,)).fetchone()[0]
            if not dur:
                d = ffprobe_duration(Path(ep["video_path"]))
                if d:
                    c.execute("UPDATE episodes SET duration_sec=? WHERE id=?", (d, episode_id))
    return len(lines)


def get_transcript_lines(episode_id: str) -> list[dict]:
    return db.rows("SELECT start_sec AS start, end_sec AS end, text FROM transcript_lines WHERE episode_id=? ORDER BY seq",
                   (episode_id,))


def fill_segment_transcripts(episode_id: str, force: bool = False) -> int:
    lines = get_transcript_lines(episode_id)
    if not lines:
        return 0
    conn = db.get_conn()
    where = "" if force else "AND (transcript IS NULL OR transcript='')"
    segs = conn.execute(f"SELECT id, start_sec, end_sec FROM segments WHERE episode_id=? AND start_sec IS NOT NULL {where}",
                        (episode_id,)).fetchall()
    n = 0
    with db.tx(conn) as c:
        for s in segs:
            text = slice_transcript(lines, s["start_sec"], s["end_sec"])
            if text:
                c.execute("UPDATE segments SET transcript=? WHERE id=?", (text, s["id"]))
                n += 1
    return n


# ---------------------------------------------------------------- clip folders
_RE_CLIP = re.compile(r"^(\d{2})_(.+?)(_zoomed(?:_\d+)?)?\.mp4$", re.I)


def scan_clip_folder(folder: Path, episode_id: Optional[str] = None) -> dict:
    """Link NN_title.mp4 clips (and their _zoomed versions) to segments; create backfill segments when needed."""
    folder = Path(folder)
    info = parse_episode_name(folder.name)
    episode_id = episode_id or (info["episode_id"] if info else None)
    if not episode_id:
        return {"folder": str(folder), "skipped": "no podcast profile matches the folder name"}
    root = paths.full_dir()
    conn = db.get_conn()
    ep_row = conn.execute("SELECT * FROM episodes WHERE id=?", (episode_id,)).fetchone()
    video = find_video_for_episode(root, episode_id, ep_row["source_video"] if ep_row else None)
    transcript = find_transcript(video) if video else None
    with db.tx(conn) as c:
        upsert_episode(c, {
            "id": episode_id, "podcast_id": parse_episode_id(episode_id)["podcast_id"],
            "number": parse_episode_id(episode_id)["number"],
            "guest": (info or {}).get("guest") if not (ep_row and ep_row["guest"]) else None,
            "source_video": video.name if video else None, "video_path": str(video) if video else None,
            "transcript_path": str(transcript) if transcript else None, "clip_folder": str(folder),
        })
    load_episode_transcript(episode_id)
    lines = get_transcript_lines(episode_id)

    stats = {"folder": str(folder), "episode_id": episode_id, "linked": 0, "backfilled": 0, "zoomed": 0}
    clips = {}
    for p in folder.iterdir():
        m = _RE_CLIP.match(p.name) if p.is_file() else None
        if not m:
            continue
        nn, base, zoomed = int(m.group(1)), m.group(2), bool(m.group(3))
        entry = clips.setdefault((nn, base), {"nn": nn, "base": base, "clip": None, "zoomed": None})
        if zoomed:
            if entry["zoomed"] is None or "_zoomed.mp4" in p.name:
                entry["zoomed"] = p
        else:
            entry["clip"] = p
    for (nn, base), e in sorted(clips.items()):
        clip = e["clip"] or e["zoomed"]
        if clip is None:
            continue
        sidecar = folder / f"{nn:02d}_{base}.json"
        meta = read_json(sidecar) if sidecar.exists() else {}
        start = _num(meta.get("clip_start"))
        end = _num(meta.get("clip_end"))
        title = meta.get("title") or base.replace("_", " ")
        thumb = folder / f"{nn:02d}_{base}_zoomed_thumbnail.jpg"
        seg = _match_segment(conn, episode_id, nn, base, start, end, str(e["clip"]) if e["clip"] else None)
        with db.tx(conn) as c:
            if seg is None:
                kind = "hook" if title.upper().startswith("HOOK 0") else "highlight"
                transcript_text = None
                if meta.get("segments"):
                    transcript_text = "\n".join(f"[{sec_to_hms(s['start'])}] {s['text']}" for s in meta["segments"])
                elif start is not None and lines:
                    transcript_text = slice_transcript(lines, start, end)
                rec = {
                    "episode_id": episode_id, "kind": kind, "start_sec": start, "end_sec": end,
                    "start_hms": sec_to_hms(start) if start is not None else None,
                    "end_hms": sec_to_hms(end) if end is not None else None,
                    "duration_sec": (end - start) if start is not None and end is not None else _num(meta.get("duration")),
                    "title": title, "rank": nn, "source_skill": "cutter-backfill", "transcript": transcript_text,
                    "raw_json": json.dumps(meta, ensure_ascii=False) if meta else None, "status": "cut",
                    "extra_json": json.dumps({"timestamps_unknown": start is None}, ensure_ascii=False),
                }
                seg_id = _insert_backfill(c, rec)
                stats["backfilled"] += 1
            else:
                seg_id = seg["id"]
                stats["linked"] += 1
            status = "zoomed" if e["zoomed"] else "cut"
            c.execute(
                """UPDATE segments SET clip_path=COALESCE(?, clip_path), clip_zoomed_path=?, thumbnail_path=?,
                       rank=COALESCE(rank, ?), status=CASE WHEN status IN ('ready','published','archived') THEN status ELSE ? END,
                       updated_at=? WHERE id=?""",
                (str(e["clip"]) if e["clip"] else None, str(e["zoomed"]) if e["zoomed"] else None,
                 str(thumb) if thumb.exists() else None, nn, status, now_iso(), seg_id))
            if e["zoomed"]:
                stats["zoomed"] += 1
    if clips:
        with db.tx(conn) as c:
            c.execute("UPDATE episodes SET stage=CASE WHEN stage IN ('ready') THEN stage ELSE 'ready' END, "
                      "clip_folder=?, updated_at=? WHERE id=?", (str(folder), now_iso(), episode_id))
        link_hook_parents(episode_id)
    fill_segment_transcripts(episode_id)
    return stats


def link_hook_parents(episode_id: str) -> int:
    """Hooks without a parent get the next highlight in cut order (hooks are cut right before their parent)."""
    conn = db.get_conn()
    rows = conn.execute("SELECT id, kind, rank, start_sec, end_sec FROM segments WHERE episode_id=? AND rank IS NOT NULL "
                        "ORDER BY rank", (episode_id,)).fetchall()
    n = 0
    with db.tx(conn) as c:
        for i, r in enumerate(rows):
            if r["kind"] != "hook":
                continue
            parent = next((x for x in rows[i + 1:] if x["kind"] == "highlight"), None)
            if parent is None:
                continue
            if r["start_sec"] is not None and parent["start_sec"] is not None:
                inside = parent["start_sec"] - 2 <= r["start_sec"] and r["end_sec"] <= parent["end_sec"] + 2
                if not inside:
                    continue
            c.execute("UPDATE segments SET parent_id=? WHERE id=? AND parent_id IS NULL", (parent["id"], r["id"]))
            n += 1
    return n


def _insert_backfill(c, rec: dict) -> int:
    cols = list(rec.keys())
    now = now_iso()
    c.execute(f"INSERT INTO segments({', '.join(cols)}, last_seen, created_at, updated_at) "
              f"VALUES({', '.join(':' + k for k in cols)}, :now, :now, :now)", {**rec, "now": now})
    return c.execute("SELECT last_insert_rowid()").fetchone()[0]


def _match_segment(conn, episode_id: str, nn: int, base: str, start, end, clip_path: Optional[str]):
    if clip_path:
        r = conn.execute("SELECT id FROM segments WHERE episode_id=? AND clip_path=?", (episode_id, clip_path)).fetchone()
        if r:
            return r
    if start is not None and end is not None:
        r = conn.execute(
            "SELECT id FROM segments WHERE episode_id=? AND start_sec IS NOT NULL AND abs(start_sec-?)<=? AND abs(end_sec-?)<=? "
            "ORDER BY abs(start_sec-?) LIMIT 1",
            (episode_id, start, TIME_TOLERANCE, end, TIME_TOLERANCE, start)).fetchone()
        if r:
            return r
    # fall back to rank + title prefix (file names are truncated to 50 chars by the Cutter)
    for r in conn.execute("SELECT id, title, rank FROM segments WHERE episode_id=? AND rank=?", (episode_id, nn)):
        if cutter_safe_title(r["title"], nn)[:40].lower() == base[:40].lower():
            return r
    return None


def scan_media_root(root: Optional[Path] = None, force: bool = False) -> dict:
    """Ingest every cutlist in Cutlists\\, register every video in Full\\ a podcast profile recognises,
    and scan every episode folder in Clips\\ (see paths.py for the layout)."""
    root = Path(root or db.get_setting("media_root"))
    out = {"root": str(root), "cutlists": [], "videos": 0, "folders": [], "errors": []}
    if not root.exists():
        out["errors"].append(f"media root not found: {root}")
        return out
    paths.ensure()
    for p in sorted(paths.cutlists_dir().glob("cutlist_*.json")):
        try:
            out["cutlists"].append(ingest_cutlist(p, root, force=force))
        except Exception as e:  # noqa: BLE001
            out["errors"].append(f"{p.name}: {e}")
            log.exception("cutlist %s", p)
    conn = db.get_conn()
    for p in sorted(paths.full_dir().iterdir()):
        if p.is_file() and p.suffix.lower() in config.VIDEO_EXTS and not p.name.endswith(".part"):
            info = parse_episode_name(p.name)
            if not info:
                continue
            transcript = find_transcript(p)
            with db.tx(conn) as c:
                upsert_episode(c, {"id": info["episode_id"], "podcast_id": info["podcast_id"], "number": info["number"],
                                   "guest": info["guest"], "source_video": p.name, "video_path": str(p),
                                   "transcript_path": str(transcript) if transcript else None,
                                   "stage": "transcribed" if transcript else "new"})
            out["videos"] += 1
            if transcript:
                load_episode_transcript(info["episode_id"])
    for p in sorted(paths.clips_dir().iterdir()):
        if p.is_dir() and parse_episode_name(p.name):
            try:
                out["folders"].append(scan_clip_folder(p))
            except Exception as e:  # noqa: BLE001
                out["errors"].append(f"{p.name}: {e}")
                log.exception("folder %s", p)
    from .search import rebuild_index
    rebuild_index()
    return out
