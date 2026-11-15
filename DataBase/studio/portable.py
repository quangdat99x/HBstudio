"""Data that moves between machines: same folder layout everywhere, paths that follow the media root, and what only the
database knew travelling with the clips.

1. rebase_text / relocate_db: every path the database stores under some media root (`...\\YouTube\\Full|Cutlists|Clips|
   Tong-hop|_old\\...`) is rewritten to the media root of this machine. Runs at startup: moving the data folder or
   changing drives needs nothing else.
2. _studio.json in each episode folder (Clips\\<episode>\\): the episode, its segments (status, edited titles and
   summaries, analyses) and its "Viết Title" / thumbnail runs, written whenever they change. A machine that receives the
   folder imports it (union: what it has stays, what it lacks is added, a status only moves forward).
3. DataIndexer: watches Cutlists\\, Clips\\ and the transcripts in Full\\ and indexes whatever gets copied in once it
   has stopped changing. Videos are handled by the folder watcher (intake.py): a video that arrives together with its
   transcript is only indexed, it does not start the pipeline (no Whisper, no Claude call).
"""
from __future__ import annotations

import json
import logging
import os
import re
import threading
from pathlib import Path

from . import config, db, paths
from .util import find_transcript, now_iso, parse_episode_name, read_json, write_json

log = logging.getLogger("studio.portable")

SIDECAR = "_studio.json"
FORMAT = 1
MACHINE = os.environ.get("COMPUTERNAME") or "may-nay"

# ---------------------------------------------------------------- 1. paths that follow the media root
_LAYOUT = r"(?:Full|Cutlists|Clips|Tong-hop|_old)"
# a drive path whose folder right before the layout folder is "YouTube"; sep = \\ (JSON-escaped), \ or /
_RX_MEDIA = re.compile(
    r"(?<![A-Za-z0-9_])(?P<pre>[A-Za-z]:(?P<sep>\\\\|\\|/)[^\"\r\n\t:*?<>|`]*?YouTube)(?=(?P=sep)" + _LAYOUT
    + r"(?:\\\\|\\|/|\"|$))", re.I)


def rebase_text(text, root=None):
    """Rewrite media-root prefixes of other machines / old drives to this machine's media root. Non-strings pass through."""
    if not isinstance(text, str) or "youtube" not in text.lower():
        return text
    new = str(root or paths.root()).rstrip("\\/")

    def sub(m):
        sep, pre = m.group("sep"), m.group("pre")
        target = new.replace("\\", "/") if sep == "/" else new.replace("\\", sep)
        return pre if pre.lower() == target.lower() else target
    return _RX_MEDIA.sub(sub, text)


def rebase_obj(obj, root=None):
    if isinstance(obj, str):
        return rebase_text(obj, root)
    if isinstance(obj, list):
        return [rebase_obj(v, root) for v in obj]
    if isinstance(obj, dict):
        return {k: rebase_obj(v, root) for k, v in obj.items()}
    return obj


# Columns holding paths (or text that quotes them). History text (jobs.error, notifications, ingest_log) stays as it was.
PATH_COLUMNS = {
    "episodes": ("video_path", "transcript_path", "clip_folder", "cutlist_path", "selection_log_md"),
    "segments": ("clip_path", "clip_zoomed_path", "thumbnail_path", "cutlist_path", "analysis_md", "analysis_json"),
    "segment_titles": ("output_md", "output_json"),
    "topic_scans": ("cutlist_path", "out_dir"),
    "topic_scan_items": ("source_path", "clip_path"),
    "compile_jobs": ("out_dir", "final_path"),
    "compile_candidates": ("source_path",),
    "compile_items": ("source_path",),
    "docext_jobs": ("hooked_path", "final_path"),
}


def relocate_db(root=None) -> int:
    """Rewrite stored paths to this machine's media root. Returns the number of changed values. Idempotent."""
    root = str(root or paths.root())
    conn = db.get_conn()
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    changed = 0
    for table, cols in PATH_COLUMNS.items():
        if table not in tables:
            continue
        have = {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
        cols = [c for c in cols if c in have]
        if not cols:
            continue
        where = " OR ".join(f"{c} LIKE '%youtube%'" for c in cols)
        rows = conn.execute(f"SELECT rowid AS rid, {', '.join(cols)} FROM {table} WHERE {where}").fetchall()
        updates = []
        for r in rows:
            new = {c: rebase_text(r[c], root) for c in cols}
            diff = {c: v for c, v in new.items() if v != r[c]}
            if diff:
                updates.append((diff, r["rid"]))
        if updates:
            with db.tx(conn) as c:
                for diff, rid in updates:
                    c.execute(f"UPDATE {table} SET {', '.join(k + '=?' for k in diff)} WHERE rowid=?", [*diff.values(), rid])
            changed += sum(len(d) for d, _ in updates)
    if changed:
        log.info("relocate: %d stored paths now point into %s", changed, root)
    return changed


def rebase_json_files(folder: Path, root=None) -> int:
    """thumb_plan.json / thumbframes index.json copied from another machine quote its paths: point them here."""
    n = 0
    for p in Path(folder).rglob("*.json"):
        if p.name == SIDECAR:
            continue
        try:
            text = p.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        new = rebase_text(text, root)
        if new != text:
            p.write_text(new, encoding="utf-8")
            n += 1
    return n


# ---------------------------------------------------------------- 2. _studio.json
EP_FIELDS = ("guest", "title", "duration_sec", "guest_profile_json", "guest_card_md", "selection_log_md", "aired_on")
SEG_SKIP = {"id", "episode_id", "parent_id", "clip_path", "clip_zoomed_path", "thumbnail_path"}
SEG_EDITABLE = ("title", "summary_vi", "core_keyword", "analysis_md", "analysis_json")
TITLE_SKIP = {"id", "segment_id", "parent_id"}
STATUS_ORDER = ["selected", "cut", "zoomed", "ready", "published", "archived"]
_STAGE_ORDER = ["new", "downloading", "transcribing", "transcribed", "selecting", "reviewing", "selected",
                "cutting", "cut", "zooming", "zoomed", "indexing", "ready"]


def _seg_key(s: dict) -> tuple:
    if s.get("start_sec") is not None and s.get("end_sec") is not None:
        return (s["kind"], round(float(s["start_sec"]), 2), round(float(s["end_sec"]), 2))
    return (s["kind"], "rank", s.get("rank"), (s.get("title") or "").strip().lower())


def _fingerprint(episode_id: str) -> str:
    r = db.row("""SELECT e.updated_at AS e,
                         (SELECT MAX(updated_at) || '/' || COUNT(*) FROM segments WHERE episode_id=e.id) AS s,
                         (SELECT MAX(COALESCE(t.finished_at, t.started_at, t.created_at)) || '/' || COUNT(*)
                            FROM segment_titles t JOIN segments x ON x.id=t.segment_id
                           WHERE x.episode_id=e.id AND t.status IN ('done','failed')) AS t
                  FROM episodes e WHERE e.id=?""", (episode_id,)) or {}
    return f"{r.get('e')}|{r.get('s')}|{r.get('t')}"


def _in_clips(folder: Path) -> bool:
    try:
        return Path(folder).resolve().parent == paths.clips_dir().resolve()
    except OSError:
        return False


def export_episode(episode_id: str, force: bool = False) -> Path | None:
    """Write Clips\\<episode>\\_studio.json. Skipped when nothing changed since the last write."""
    ep = db.row("SELECT * FROM episodes WHERE id=?", (episode_id,))
    if not ep or not ep.get("clip_folder"):
        return None
    folder = Path(ep["clip_folder"])
    if not folder.is_dir() or not _in_clips(folder):
        return None
    target = folder / SIDECAR
    fp = _fingerprint(episode_id)
    if not force and _EXPORTED.get(episode_id) == fp:
        return None
    if target.exists():
        try:
            old = read_json(target)
        except (OSError, ValueError):
            old = {}
        if old.get("machine") and old["machine"] != MACHINE and \
                not _imported_already(episode_id, old["machine"], old.get("exported_at") or ""):
            return None                     # another machine's sidecar not imported yet: never overwrite it
        if not force and old.get("machine") == MACHINE and old.get("fingerprint") == fp:
            _EXPORTED[episode_id] = fp
            return None
    segs = db.rows("SELECT * FROM segments WHERE episode_id=? ORDER BY rank, start_sec", (episode_id,))
    by_id = {s["id"]: s for s in segs}
    out_segs = []
    for s in segs:
        rec = {k: v for k, v in s.items() if k not in SEG_SKIP}
        parent = by_id.get(s.get("parent_id"))
        rec["parent_key"] = list(_seg_key(parent)) if parent else None
        out_segs.append(rec)
    titles = db.rows("""SELECT t.* FROM segment_titles t JOIN segments s ON s.id=t.segment_id
                        WHERE s.episode_id=? AND t.status IN ('done','failed') ORDER BY t.id""", (episode_id,))
    out_titles = []
    for t in titles:
        rec = {k: v for k, v in t.items() if k not in TITLE_SKIP}
        rec["orig_id"], rec["orig_parent_id"] = t["id"], t.get("parent_id")
        rec["segment_key"] = list(_seg_key(by_id[t["segment_id"]]))
        out_titles.append(rec)
    data = {"format": FORMAT, "machine": MACHINE, "exported_at": now_iso(), "fingerprint": fp,
            "media_root": str(paths.root()), "episode_id": episode_id,
            # the show profile travels too: a machine that never had this show still recognises the file names
            "podcast": db.row("SELECT * FROM podcasts WHERE id=?", (ep["podcast_id"],)),
            "episode": {k: ep.get(k) for k in EP_FIELDS + ("podcast_id", "number", "stage")},
            "segments": out_segs, "titles": out_titles}
    write_json(target, data)
    _EXPORTED[episode_id] = fp
    return target


_EXPORTED: dict[str, str] = {}


def export_all() -> list[Path]:
    """Sidecars written this round (their folders)."""
    out = []
    for r in db.rows("SELECT id FROM episodes WHERE clip_folder IS NOT NULL"):
        try:
            p = export_episode(r["id"])
            if p:
                out.append(p.parent)
        except Exception:  # noqa: BLE001
            log.exception("export %s", r["id"])
    return out


def _imported_already(episode_id: str, machine: str, exported_at: str) -> bool:
    return bool(db.scalar("SELECT 1 FROM portable_imports WHERE episode_id=? AND machine=? AND exported_at>=?",
                          (episode_id, machine, exported_at)))


def import_sidecar(folder: Path, fresh_since: str | None = None) -> dict:
    """Merge Clips\\<episode>\\_studio.json written by another machine into this database."""
    folder = Path(folder)
    p = folder / SIDECAR
    if not p.exists():
        return {"skipped": "no sidecar"}
    try:
        data = read_json(p)
    except (OSError, ValueError) as e:
        return {"error": f"{p}: {e}"}
    machine, exported_at, ep_id = data.get("machine"), data.get("exported_at") or "", data.get("episode_id")
    if not ep_id or data.get("format") != FORMAT:
        return {"skipped": "unknown format"}
    if machine == MACHINE:
        return {"skipped": "written by this machine"}
    if _imported_already(ep_id, machine, exported_at):
        return {"skipped": "already imported"}
    root = str(paths.root())
    data = rebase_obj(data, root)
    stats = {"episode_id": ep_id, "from": machine, "segments_added": 0, "segments_updated": 0, "titles_added": 0,
             "thumb_folders": 0, "json_files": rebase_json_files(folder, root)}
    conn = db.get_conn()
    now = now_iso()
    fresh_since = fresh_since or now
    e = data.get("episode") or {}
    with db.tx(conn) as c:
        prof = data.get("podcast") or {}
        if prof.get("id") and not c.execute("SELECT 1 FROM podcasts WHERE id=?", (prof["id"],)).fetchone():
            have = {r[1] for r in c.execute("PRAGMA table_info(podcasts)")}
            row = {k: v for k, v in prof.items() if k in have}
            c.execute(f"INSERT INTO podcasts({', '.join(row)}) VALUES({', '.join('?' * len(row))})", list(row.values()))
            stats["podcast_added"] = prof["id"]
        ep = c.execute("SELECT * FROM episodes WHERE id=?", (ep_id,)).fetchone()
        if ep is None:
            if not e.get("podcast_id"):
                raise ValueError(f"{p}: episode {ep_id} missing podcast_id")
            c.execute("""INSERT INTO episodes(id, podcast_id, number, clip_folder, stage, created_at, updated_at)
                         VALUES(?,?,?,?,?,?,?)""", (ep_id, e["podcast_id"], e.get("number"), str(folder), "ready", now, now))
            ep = c.execute("SELECT * FROM episodes WHERE id=?", (ep_id,)).fetchone()
        sets = {k: e[k] for k in EP_FIELDS if e.get(k) not in (None, "") and ep[k] in (None, "")}
        if e.get("stage") and _rank(_STAGE_ORDER, e["stage"]) > _rank(_STAGE_ORDER, ep["stage"]):
            sets["stage"] = e["stage"]
        if sets:
            c.execute(f"UPDATE episodes SET {', '.join(k + '=?' for k in sets)}, updated_at=? WHERE id=?",
                      [*sets.values(), now, ep_id])

        seg_cols = {r[1] for r in c.execute("PRAGMA table_info(segments)")}
        local = {_seg_key(dict(r)): dict(r) for r in c.execute("SELECT * FROM segments WHERE episode_id=?", (ep_id,))}
        key_to_id = {k: v["id"] for k, v in local.items()}
        for s in data.get("segments") or []:
            k = _seg_key(s)
            row = {kk: v for kk, v in s.items() if kk in seg_cols and kk not in SEG_SKIP}
            mine = local.get(k)
            if mine is None:
                row.update(episode_id=ep_id, created_at=row.get("created_at") or now, updated_at=now)
                row["title"] = row.get("title") or "clip"
                cols = list(row)
                try:
                    c.execute(f"INSERT INTO segments({', '.join(cols)}) VALUES({', '.join('?' * len(cols))})",
                              [row[x] for x in cols])
                except Exception as ex:  # noqa: BLE001  (UNIQUE clash on a near-identical segment)
                    log.warning("import segment %s %s: %s", ep_id, k, ex)
                    continue
                key_to_id[k] = c.execute("SELECT last_insert_rowid()").fetchone()[0]
                stats["segments_added"] += 1
                continue
            upd = {}
            fresh = (mine.get("created_at") or "") >= fresh_since
            for col, v in row.items():
                if col in ("created_at", "updated_at", "status") or v in (None, ""):
                    continue
                if mine.get(col) in (None, "") or (fresh and col in SEG_EDITABLE and mine.get(col) != v):
                    upd[col] = v
            if s.get("status") and _rank(STATUS_ORDER, s["status"]) > _rank(STATUS_ORDER, mine.get("status")):
                upd["status"] = s["status"]
            if upd:
                c.execute(f"UPDATE segments SET {', '.join(x + '=?' for x in upd)}, updated_at=? WHERE id=?",
                          [*upd.values(), now, mine["id"]])
                stats["segments_updated"] += 1
        for s in data.get("segments") or []:                       # hook -> parent highlight
            pk = s.get("parent_key")
            sid, pid = key_to_id.get(_seg_key(s)), key_to_id.get(tuple(pk)) if pk else None
            if sid and pid:
                c.execute("UPDATE segments SET parent_id=? WHERE id=? AND parent_id IS NULL", (pid, sid))

        title_cols = {r[1] for r in c.execute("PRAGMA table_info(segment_titles)")}
        id_map: dict[int, int] = {}
        added: list[tuple[dict, int]] = []
        for t in data.get("titles") or []:
            seg_id = key_to_id.get(tuple(t.get("segment_key") or ()))
            if not seg_id:
                continue
            same = c.execute("""SELECT id FROM segment_titles WHERE segment_id=? AND created_at=?
                                AND COALESCE(kind,'title')=COALESCE(?,'title') AND COALESCE(skill,'')=COALESCE(?,'')""",
                             (seg_id, t.get("created_at"), t.get("kind"), t.get("skill"))).fetchone()
            if same:
                id_map[t["orig_id"]] = same[0]
                continue
            row = {k: v for k, v in t.items() if k in title_cols and k not in TITLE_SKIP}
            row["segment_id"] = seg_id
            cols = list(row)
            c.execute(f"INSERT INTO segment_titles({', '.join(cols)}) VALUES({', '.join('?' * len(cols))})",
                      [row[x] for x in cols])
            new_id = c.execute("SELECT last_insert_rowid()").fetchone()[0]
            id_map[t["orig_id"]] = new_id
            added.append((t, new_id))
            stats["titles_added"] += 1
        for t, new_id in added:
            if t.get("orig_parent_id") in id_map:
                c.execute("UPDATE segment_titles SET parent_id=? WHERE id=?", (id_map[t["orig_parent_id"]], new_id))
        stats["thumb_folders"] = _renumber_thumb_folders(c, added)
        c.execute("INSERT INTO portable_imports(episode_id, machine, exported_at, imported_at) VALUES(?,?,?,?)",
                  (ep_id, machine, exported_at, now))
    if stats.get("podcast_added"):
        from . import podcasts
        podcasts.invalidate()
    return stats


def import_podcast(folder: Path) -> bool:
    """The show profile a sidecar carries, when this machine does not have that show yet."""
    p = Path(folder) / SIDECAR
    if not p.exists():
        return False
    try:
        prof = read_json(p).get("podcast") or {}
    except (OSError, ValueError):
        return False
    if not prof.get("id") or db.scalar("SELECT 1 FROM podcasts WHERE id=?", (prof["id"],)):
        return False
    with db.tx() as c:
        have = {r[1] for r in c.execute("PRAGMA table_info(podcasts)")}
        row = {k: v for k, v in prof.items() if k in have}
        c.execute(f"INSERT INTO podcasts({', '.join(row)}) VALUES({', '.join('?' * len(row))})", list(row.values()))
    from . import podcasts
    podcasts.invalidate()
    log.info("show %s added from %s", prof["id"], p)
    return True


def _rank(order: list[str], v) -> int:
    v = (v or "").split(":")[0]
    return order.index(v) if v in order else -1


def _renumber_thumb_folders(c, added: list[tuple[dict, int]]) -> int:
    """A thumbnail version lives in thumb_NN\\v<run id>. Imported runs got new ids here: rename their folders to match
    (through a temporary name, so v12 -> v30 never lands on another imported v30 before it moved)."""
    moves = []
    for t, new_id in added:
        if t.get("kind") != "thumb" or not t.get("output_json"):
            continue
        try:
            d = json.loads(t["output_json"])
        except ValueError:
            continue
        old_ver, folder = d.get("version"), d.get("folder")
        if not folder or old_ver in (None, new_id):
            continue
        src = Path(folder)
        if src.name != f"v{old_ver}" or not src.is_dir():
            continue
        moves.append((src, src.with_name(f"v{new_id}"), new_id, d, str(old_ver)))
    staged = []
    for src, dst, new_id, d, old_ver in moves:
        tmp = src.with_name(f"{src.name}.import-{new_id}")
        src.rename(tmp)
        staged.append((tmp, dst, new_id, d, src, old_ver))
    for tmp, dst, new_id, d, src, old_ver in staged:
        if dst.exists():                                     # never overwrite a version of this machine
            dst = dst.with_name(f"{dst.name}-import")
        tmp.rename(dst)
        old_s, new_s = str(src), str(dst)
        nd = {k: (new_s + v[len(old_s):] if isinstance(v, str) and (v == old_s or v.startswith(old_s + "\\")) else v)
              for k, v in d.items()}
        nd["folder"], nd["version"] = new_s, new_id
        c.execute("UPDATE segment_titles SET output_json=? WHERE id=?", (json.dumps(nd, ensure_ascii=False), new_id))
    return len(staged)


# ---------------------------------------------------------------- 3. index what gets copied in
def _sig_file(p: Path) -> list:
    st = p.stat()
    return [st.st_size, int(st.st_mtime)]


def _sig_folder(p: Path) -> list:
    """Count, size and newest mtime of the folder, plus the sidecar's own size/mtime: another machine's newer
    _studio.json (titles written there, nothing else changed) must count as a change too. Our own writes are
    taken into the indexed state right after they happen (DataIndexer.tick), so they never trigger a rescan."""
    n = size = newest = 0
    side = p / SIDECAR
    try:
        st = side.stat()
        side_sig = [st.st_size, int(st.st_mtime)]
    except OSError:
        side_sig = None
    for f in p.rglob("*"):
        if f.name == SIDECAR or f.name.endswith(".tmp"):
            continue
        try:
            st = f.stat()
        except OSError:
            continue
        n += 1
        size += st.st_size if f.is_file() else 0
        newest = max(newest, int(st.st_mtime))
    return [n, size, newest, side_sig]


def snapshot() -> dict:
    snap = {"cutlists": {}, "clips": {}, "transcripts": {}}
    if paths.cutlists_dir().is_dir():
        for p in paths.cutlists_dir().glob("cutlist_*.json"):
            snap["cutlists"][p.name] = _sig_file(p)
    if paths.clips_dir().is_dir():
        for p in paths.clips_dir().iterdir():
            if p.is_dir() and (parse_episode_name(p.name) or (p / SIDECAR).exists()):
                snap["clips"][p.name] = _sig_folder(p)
    if paths.full_dir().is_dir():
        for p in paths.full_dir().glob("*.transcript.*"):
            snap["transcripts"][p.name] = _sig_file(p)
    return snap


def index_changes(changed: dict) -> dict:
    """changed = {"cutlists": [names], "clips": [names], "transcripts": [names]} → index them (order matters:
    cutlists define the segments, folders link clips to them, sidecars add what only a database knew)."""
    from . import ingest
    from .search import rebuild_index
    # "failed": items to try again next round (e.g. a cutlist whose show arrives with a clip folder still copying)
    out = {"cutlists": 0, "transcripts": 0, "folders": 0, "imported": [], "errors": [], "failed": []}
    t0 = now_iso()
    for name in changed.get("clips") or []:             # shows first: cutlists/transcripts of a new show need them
        try:
            if import_podcast(paths.clips_dir() / name):
                out.setdefault("podcasts", []).append(name)
        except Exception as e:  # noqa: BLE001
            out["errors"].append(f"{name}: {e}")
    for name in changed.get("cutlists") or []:
        try:
            ingest.ingest_cutlist(paths.cutlists_dir() / name)
            out["cutlists"] += 1
        except Exception as e:  # noqa: BLE001
            out["errors"].append(f"{name}: {e}")
            out["failed"].append(["cutlists", name])
    for name in changed.get("transcripts") or []:
        try:
            if _index_transcript(paths.full_dir() / name):
                out["transcripts"] += 1
            elif not parse_episode_name(name.split(".transcript.")[0]):
                out["failed"].append(["transcripts", name])          # no show knows it yet
        except Exception as e:  # noqa: BLE001
            out["errors"].append(f"{name}: {e}")
            out["failed"].append(["transcripts", name])
    for name in changed.get("clips") or []:
        folder = paths.clips_dir() / name
        try:
            # the sidecar first: its segments carry the exact timestamps, so the clips then link to them instead of
            # becoming "backfill" segments of unknown time
            res = import_sidecar(folder, fresh_since=t0)
            if res.get("error"):
                out["errors"].append(res["error"])
            ingest.scan_clip_folder(folder, res.get("episode_id"))
            out["folders"] += 1
            if res.get("episode_id"):
                out["imported"].append(res)
                ingest.fill_segment_transcripts(res["episode_id"])
        except Exception as e:  # noqa: BLE001
            out["errors"].append(f"{name}: {e}")
            out["failed"].append(["clips", name])
            log.exception("index folder %s", folder)
    if any(out[k] for k in ("cutlists", "transcripts", "folders")):
        rebuild_index()
    return out


def _index_transcript(tpath: Path) -> bool:
    """A transcript copied next to (or without) its video: attach it to the episode and load its lines."""
    from . import ingest
    stem = tpath.name.split(".transcript.")[0]
    info = parse_episode_name(stem)
    if not info:
        return False
    video = next((p for p in (tpath.with_name(stem + ext) for ext in config.VIDEO_EXTS) if p.exists()), None)
    ep = db.row("SELECT transcript_path FROM episodes WHERE id=?", (info["episode_id"],))
    if ep and ep["transcript_path"] and Path(ep["transcript_path"]).exists():
        # the episode already has a transcript on disk (its own Whisper run, or a duplicate "(1)" copy): keep it
        return False
    with db.tx() as c:
        ingest.upsert_episode(c, {"id": info["episode_id"], "podcast_id": info["podcast_id"], "number": info["number"],
                                  "guest": info["guest"], "source_video": video.name if video else None,
                                  "video_path": str(video) if video else None, "transcript_path": str(tpath),
                                  "stage": "transcribed"})
    ingest.load_episode_transcript(info["episode_id"], force=True)
    ingest.fill_segment_transcripts(info["episode_id"])
    return True


def index_copied_video(video: Path) -> dict:
    """A video that arrived with its transcript beside it (copied from another machine): register and index it with
    whatever came along (transcript, cutlist, clip folder), without running the pipeline."""
    from . import ingest
    from .search import rebuild_index
    info = parse_episode_name(video.name)
    if not info:
        return {"error": "no show recognises the file name"}
    transcript = find_transcript(video)
    with db.tx() as c:
        ingest.upsert_episode(c, {"id": info["episode_id"], "podcast_id": info["podcast_id"], "number": info["number"],
                                  "guest": info["guest"], "source_video": video.name, "video_path": str(video),
                                  "transcript_path": str(transcript) if transcript else None, "stage": "transcribed"})
    ingest.load_episode_transcript(info["episode_id"])
    cl = paths.cutlist_path(info["episode_id"])
    if cl.exists():
        ingest.ingest_cutlist(cl)
    ep = db.row("SELECT clip_folder FROM episodes WHERE id=?", (info["episode_id"],)) or {}
    if ep.get("clip_folder") and Path(ep["clip_folder"]).is_dir():
        ingest.scan_clip_folder(Path(ep["clip_folder"]), info["episode_id"])
    ingest.fill_segment_transcripts(info["episode_id"])
    rebuild_index()
    return {"episode_id": info["episode_id"], "cutlist": cl.exists()}


_ACTIVE = ("downloading", "transcribing", "selecting", "cutting", "zooming", "indexing")


def _episode_of(kind: str, name: str) -> str | None:
    if kind == "cutlists":
        m = re.match(r"cutlist_(.+)\.json$", name, re.I)
        return m.group(1) if m else None
    info = parse_episode_name(name.split(".transcript.")[0] if kind == "transcripts" else name)
    return info["episode_id"] if info else None


def _busy(kind: str, name: str) -> bool:
    ep = _episode_of(kind, name)
    if not ep:
        return False
    r = db.row("SELECT stage, pending_zoom FROM episodes WHERE id=?", (ep,))
    return bool(r) and ((r["stage"] or "").split(":")[0] in _ACTIVE or bool(r.get("pending_zoom")))


def baseline(now: dict) -> dict:
    """State to compare against on a first run: only what this database already knows counts as indexed, so data copied
    in before Studio ever ran here (or while it was closed) is still picked up."""
    eps = db.rows("SELECT clip_folder, transcript_path FROM episodes")
    folders = {Path(r["clip_folder"]).name.lower() for r in eps if r.get("clip_folder")}
    trans = {Path(r["transcript_path"]).name.lower() for r in eps if r.get("transcript_path")}
    cuts = {Path(r["path"]).name.lower() for r in db.rows("SELECT path FROM ingest_log WHERE result IN ('ok','partial')")}
    done = {"_root": str(paths.root()), "cutlists": {}, "clips": {}, "transcripts": {}}
    for name, sig in now.get("cutlists", {}).items():
        if name.lower() in cuts:
            done["cutlists"][name] = sig
    for name, sig in now.get("transcripts", {}).items():
        if name.lower() in trans:
            done["transcripts"][name] = sig
    for name, sig in now.get("clips", {}).items():
        if name.lower() in folders and not _foreign_sidecar_pending(paths.clips_dir() / name):
            done["clips"][name] = sig
    return done


def _foreign_sidecar_pending(folder: Path) -> bool:
    p = folder / SIDECAR
    if not p.exists():
        return False
    try:
        d = read_json(p)
    except (OSError, ValueError):
        return False
    return d.get("machine") != MACHINE and not _imported_already(d.get("episode_id") or "", d.get("machine"),
                                                                 d.get("exported_at") or "")


def ensure_schema(conn) -> None:
    conn.execute("""CREATE TABLE IF NOT EXISTS portable_imports (
        id INTEGER PRIMARY KEY, episode_id TEXT NOT NULL, machine TEXT, exported_at TEXT, imported_at TEXT NOT NULL)""")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_portable_imports_ep ON portable_imports(episode_id)")
    conn.commit()


class DataIndexer(threading.Thread):
    """Every minute: compare Cutlists\\, Clips\\ and the transcripts with the last indexed state (kept in settings, so
    what was copied while Studio was closed is found at the next start), index what changed and stayed unchanged for
    one round (a copy still running is left for later), then write the _studio.json of episodes that changed."""

    def __init__(self, interval: int = 60):
        super().__init__(name="studio-data-indexer", daemon=True)
        self.interval = interval
        self._stop = threading.Event()
        self._pending: dict = {}
        self._reported: set = set()             # errors already shown once (a retried item must not ring every minute)
        self.last: dict = {}

    def stop(self) -> None:
        self._stop.set()

    def run(self) -> None:
        self._stop.wait(20)                      # let the pipeline start first
        try:
            paths.ensure()
            relocate_db()
        except Exception:  # noqa: BLE001
            log.exception("relocate failed")
        while not self._stop.is_set():
            try:
                self.tick()
            except Exception:  # noqa: BLE001
                log.exception("data indexer")
            self._stop.wait(self.interval)

    def tick(self) -> dict:
        try:
            done = json.loads(db.get_setting("portable_indexed", "{}") or "{}")
        except ValueError:
            done = {}
        now = snapshot()
        if done.get("_root") != str(paths.root()):           # first run, or the media root moved
            relocate_db()
            done = baseline(now)
            db.set_setting("portable_indexed", json.dumps(done, ensure_ascii=False))
        ready = {}
        for kind, items in now.items():
            old = done.get(kind) or {}
            for name, sig in items.items():
                if old.get(name) == sig:
                    continue
                key = (kind, name)
                if _busy(kind, name):                        # the pipeline is writing it right now: its own job
                    self._pending.pop(key, None)
                    continue
                if self._pending.get(key) == sig:            # unchanged since the last round: the copy is finished
                    ready.setdefault(kind, []).append(name)
                    self._pending.pop(key, None)
                else:
                    self._pending[key] = sig
        result = {}
        if ready:
            result = index_changes(ready)
            after = snapshot()                  # indexing may touch the folders (thumb JSON, renamed versions)
            retry = {tuple(f) for f in result.get("failed") or []}
            for kind, names in ready.items():
                done.setdefault(kind, {})
                for name in names:
                    if (kind, name) in retry:
                        self._pending[(kind, name)] = after.get(kind, {}).get(name)   # again next round
                    elif name in after.get(kind, {}):
                        done[kind][name] = after[kind][name]
            for kind in ("cutlists", "clips", "transcripts"):          # forget what was deleted
                if kind in done:
                    done[kind] = {k: v for k, v in done[kind].items() if k in after.get(kind, {})}
            db.set_setting("portable_indexed", json.dumps(done, ensure_ascii=False))
            log.info("indexed copied data: %s", {k: v for k, v in result.items() if k != "imported"})
            new_errors = [e for e in result.get("errors") or [] if e not in self._reported]
            self._reported.update(new_errors)
            _notify({**result, "errors": new_errors})
        written = export_all()
        if written:                              # our own sidecar writes are not "copied in" changes
            done.setdefault("clips", {})
            for folder in written:
                if folder.name in done["clips"] and ("clips", folder.name) not in self._pending:
                    done["clips"][folder.name] = _sig_folder(folder)
                    self._pending.pop(("clips", folder.name), None)
            db.set_setting("portable_indexed", json.dumps(done, ensure_ascii=False))
        result["exported"] = len(written)
        self.last = {"at": now_iso(), **result}
        return result


def _notify(res: dict) -> None:
    if not (res.get("cutlists") or res.get("folders") or res.get("transcripts")):
        return
    try:
        from . import notify
        parts = [f"{res['cutlists']} cutlist" if res.get("cutlists") else "",
                 f"{res['folders']} thư mục clip" if res.get("folders") else "",
                 f"{res['transcripts']} transcript" if res.get("transcripts") else ""]
        body = ", ".join(p for p in parts if p)
        if res.get("imported"):
            body += f"; nạp dữ liệu từ máy khác cho {', '.join(i['episode_id'] for i in res['imported'])}"
        if res.get("errors"):
            body += f"; {len(res['errors'])} lỗi: {res['errors'][0]}"
        notify.notify("error" if res.get("errors") else "done", "Đã index data chép vào", body, "/episodes")
    except Exception:  # noqa: BLE001
        log.exception("notify")
