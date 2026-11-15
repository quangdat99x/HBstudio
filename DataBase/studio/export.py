"""Export selected segments for downstream tools.

- pool : one JSON with every segment carrying its episode metadata, input for the tong-hop-rabbit-hole skill.
- multi: cut_multi_<slug>.json, the multi-source cutlist Video Cutter imports in "Cắt Theo Folder (Đa Tập)" mode.
"""
from __future__ import annotations

import json
from pathlib import Path

from . import db
from .util import now_iso, slugify, write_json


def _load(ids: list[int]) -> list[dict]:
    if not ids:
        return []
    q = f"SELECT s.*, e.guest, e.source_video FROM segments s JOIN episodes e ON e.id=s.episode_id WHERE s.id IN ({','.join('?'*len(ids))})"
    rows = {r["id"]: dict(r) for r in db.get_conn().execute(q, ids).fetchall()}
    out = []
    for i in ids:
        if i in rows:
            r = rows[i]
            r["topics"] = [t[0] for t in db.get_conn().execute(
                "SELECT t.name FROM segment_topics st JOIN topics t ON t.id=st.topic_id WHERE st.segment_id=?", (i,))]
            out.append(r)
    return out


def export_segments(ids: list[int], fmt: str = "pool", theme: str = "", out_path: Path | None = None) -> Path:
    segs = _load(ids)
    if not segs:
        raise ValueError("no segments to export")
    theme = theme or "selection"
    slug = slugify(theme)
    episodes = sorted({s["episode_id"] for s in segs})
    if fmt == "multi":
        data = {
            "version": 2, "type": "multi-source-cutlist", "theme": theme, "source_episodes": episodes,
            "segments": [
                {"order": n, "episode_id": s["episode_id"], "source_video": s["source_video"],
                 "start": s["start_hms"], "end": s["end_hms"], "title": s["title"]}
                for n, s in enumerate(segs, 1)
            ],
        }
        out_path = Path(out_path or f"cut_multi_{slug}.json")
    else:
        ep_meta = {}
        for s in segs:
            ep_meta.setdefault(s["episode_id"], {"id": s["episode_id"], "guest": s["guest"], "source_video": s["source_video"]})
        data = {
            "version": 2, "type": "pool", "source": "hldb export", "theme": theme, "exported_at": now_iso(),
            "episodes": list(ep_meta.values()),
            "segments": [
                {"segment_id": s["id"], "episode_id": s["episode_id"], "guest": s["guest"], "source_video": s["source_video"],
                 "kind": s["kind"], "rank": s["rank"], "start": s["start_hms"], "end": s["end_hms"],
                 "duration_sec": s["duration_sec"], "title": s["title"], "topics": s["topics"],
                 "hook_en": s["hook_en"], "summary_en": s["summary_en"], "summary_vi": s["summary_vi"],
                 "intensity": s["intensity"], "cq": s["cq"], "gtf": s["gtf"], "final_score": s["final_score"],
                 "core_keyword": s["core_keyword"], "value_axis": s["value_axis"],
                 "clip_path": s["clip_path"], "clip_zoomed_path": s["clip_zoomed_path"]}
                for s in segs
            ],
        }
        out_path = Path(out_path or f"pool_{slug}.json")
    write_json(out_path, data)
    return out_path


def record_compilation(theme: str, segment_ids: list[int], manifest_path: str = "", cutlist_path: str = "",
                       roles: dict | None = None) -> int:
    """Register a built compilation so its segments count as used."""
    slug = slugify(theme)
    with db.tx() as c:
        c.execute("INSERT INTO compilations(theme, slug, manifest_path, cutlist_path, status, created_at) VALUES(?,?,?,?,?,?) "
                  "ON CONFLICT(slug) DO UPDATE SET manifest_path=excluded.manifest_path, cutlist_path=excluded.cutlist_path",
                  (theme, slug, manifest_path, cutlist_path, "built", now_iso()))
        cid = c.execute("SELECT id FROM compilations WHERE slug=?", (slug,)).fetchone()[0]
        c.execute("DELETE FROM compilation_items WHERE compilation_id=?", (cid,))
        for n, sid in enumerate(segment_ids, 1):
            c.execute("INSERT OR IGNORE INTO compilation_items(compilation_id, segment_id, ord, role) VALUES(?,?,?,?)",
                      (cid, sid, n, (roles or {}).get(sid)))
    return cid


def record_compilation_manifest(path: Path) -> int:
    """Read a compilation_<slug>.json written by tong-hop-rabbit-hole and register it."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    theme = data.get("theme") or Path(path).stem
    ids, roles = [], {}
    conn = db.get_conn()
    for item in data.get("arc", []):
        r = conn.execute("SELECT id FROM segments WHERE episode_id=? AND start_hms=? AND end_hms=?",
                         (item.get("episode_id"), item.get("start"), item.get("end"))).fetchone()
        if r:
            ids.append(r["id"])
            roles[r["id"]] = item.get("role")
    return record_compilation(theme, ids, manifest_path=str(path), roles=roles)
