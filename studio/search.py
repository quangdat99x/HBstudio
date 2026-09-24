"""Search: rebuild the flat search buffer + FTS5 index, and query with filters."""
from __future__ import annotations

import json
import re
from typing import Optional

from . import db
from .util import strip_diacritics


def _topics_text(conn, seg_id: int) -> str:
    return " ; ".join(r[0] for r in conn.execute(
        "SELECT t.name FROM segment_topics st JOIN topics t ON t.id=st.topic_id WHERE st.segment_id=?", (seg_id,)))


def _entities_text(conn, seg_id: int) -> str:
    return " ; ".join(r[0] for r in conn.execute(
        "SELECT e.name FROM segment_entities se JOIN entities e ON e.id=se.entity_id WHERE se.segment_id=?", (seg_id,)))


def _themes_text(conn, seg_id: int) -> str:
    return " ; ".join(f"{r[0]} {r[1] or ''}" for r in conn.execute(
        "SELECT th.slug, th.name_vi FROM segment_themes st JOIN themes th ON th.id=st.theme_id WHERE st.segment_id=?",
        (seg_id,)))


def rebuild_index(segment_ids: Optional[list[int]] = None) -> int:
    """Rebuild segment_search rows (all, or the given ids) and refresh the FTS index."""
    conn = db.get_conn()
    if segment_ids:
        q = f"SELECT s.*, e.guest FROM segments s JOIN episodes e ON e.id=s.episode_id WHERE s.id IN ({','.join('?'*len(segment_ids))})"
        segs = conn.execute(q, segment_ids).fetchall()
    else:
        segs = conn.execute("SELECT s.*, e.guest FROM segments s JOIN episodes e ON e.id=s.episode_id").fetchall()
    with db.tx(conn) as c:
        if not segment_ids:
            c.execute("DELETE FROM segment_search")
        for s in segs:
            analysis = s["analysis_md"] or ""
            try:
                t = c.execute("SELECT recommended_title, output_json FROM segment_titles WHERE segment_id=? AND status='done' "
                              "ORDER BY id DESC LIMIT 1", (s["id"],)).fetchone()
            except Exception:  # noqa: BLE001  (table missing on an old database)
                t = None
            if t:
                analysis += "\n" + (t["recommended_title"] or "")
                try:
                    tj = json.loads(t["output_json"] or "{}")
                    analysis += "\n" + " ".join(str(tj.get(k) or "") for k in ("tags", "titles_format1", "titles_format2"))
                except ValueError:
                    pass
            if s["analysis_json"]:
                try:
                    aj = json.loads(s["analysis_json"])
                    analysis += "\n" + " ".join(str(v) for v in aj.values() if isinstance(v, str))
                except Exception:  # noqa: BLE001
                    pass
            row = {
                "segment_id": s["id"], "title": s["title"], "summary_en": s["summary_en"], "summary_vi": s["summary_vi"],
                "hook_en": s["hook_en"], "quote_en": s["quote_en"], "topics_text": _topics_text(c, s["id"]),
                "core_keyword": s["core_keyword"], "guest": s["guest"], "entities_text": _entities_text(c, s["id"]),
                "themes_text": _themes_text(c, s["id"]), "analysis": analysis, "transcript": s["transcript"],
            }
            row["ascii_text"] = strip_diacritics(" ".join(str(v) for k, v in row.items()
                                                          if k not in ("segment_id", "transcript") and v))
            cols = list(row.keys())
            c.execute(f"INSERT OR REPLACE INTO segment_search({', '.join(cols)}) VALUES({', '.join(':' + k for k in cols)})",
                      row)
        c.execute("INSERT INTO segments_fts(segments_fts) VALUES('rebuild')")
    return len(segs)


def _fts_query(q: str) -> str:
    """Turn free text into a safe FTS5 query: every token quoted, ANDed; accent-folded variant ORed in."""
    tokens = [t for t in re.split(r"\s+", q.strip()) if t]
    if not tokens:
        return ""
    def quote(t: str) -> str:
        return '"' + t.replace('"', '""') + '"'
    plain = " ".join(quote(t) for t in tokens)
    folded = " ".join(quote(strip_diacritics(t)) for t in tokens)
    return plain if folded == plain else f"({plain}) OR ({folded})"


def search(q: str = "", *, episode_id: str = None, podcast_id: str = None, guest: str = None, kind: str = None,
           min_intensity: float = None, min_gtf: float = None, min_score: float = None, keyword_reach: str = None,
           status: str = None, theme: str = None, topic: str = None, unused: bool = False, limit: int = 30,
           offset: int = 0) -> list[dict]:
    conn = db.get_conn()
    where, params = [], []
    if episode_id:
        where.append("s.episode_id=?"); params.append(episode_id)
    if podcast_id:
        where.append("e.podcast_id=?"); params.append(podcast_id)
    if guest:
        where.append("e.guest LIKE ?"); params.append(f"%{guest}%")
    if kind:
        where.append("s.kind=?"); params.append(kind)
    if min_intensity is not None:
        where.append("s.intensity>=?"); params.append(min_intensity)
    if min_gtf is not None:
        where.append("s.gtf>=?"); params.append(min_gtf)
    if min_score is not None:
        where.append("s.final_score>=?"); params.append(min_score)
    if keyword_reach:
        where.append("s.keyword_reach=?"); params.append(keyword_reach.upper())
    if status:
        where.append("s.status=?"); params.append(status)
    if theme:
        where.append("s.id IN (SELECT st.segment_id FROM segment_themes st JOIN themes th ON th.id=st.theme_id WHERE th.slug=?)")
        params.append(theme)
    if topic:
        where.append("s.id IN (SELECT st.segment_id FROM segment_topics st JOIN topics t ON t.id=st.topic_id WHERE t.name_norm LIKE ?)")
        params.append(f"%{strip_diacritics(topic).lower()}%")
    if unused:
        where.append("s.id NOT IN (SELECT segment_id FROM compilation_items)")
    fts = _fts_query(q or "")
    base_select = ("SELECT s.id, s.episode_id, e.guest, s.kind, s.rank, s.content_rank, s.start_hms, s.end_hms, s.duration_sec, "
                   "s.title, s.summary_vi, s.summary_en, s.hook_en, s.intensity, s.cq, s.gtf, s.final_score, s.value_axis, "
                   "s.core_keyword, s.keyword_reach, s.status, s.clip_path, s.clip_zoomed_path, s.parent_id, "
                   "CASE WHEN json_valid(s.analysis_json) THEN substr(json_extract(s.analysis_json, '$.tom_tat'), 1, 400) END "
                   "AS tom_tat_preview")
    if fts:
        sql = (f"{base_select}, bm25(segments_fts, 10.0, 5.0, 5.0, 3.0, 3.0, 4.0, 6.0, 2.0, 3.0, 4.0, 2.0, 1.0, 1.0) AS score "
               f"FROM segments_fts f JOIN segments s ON s.id=f.rowid JOIN episodes e ON e.id=s.episode_id "
               f"WHERE segments_fts MATCH ? {'AND ' + ' AND '.join(where) if where else ''} "
               f"ORDER BY score LIMIT ? OFFSET ?")
        params = [fts] + params + [limit, offset]
    else:
        sql = (f"{base_select}, NULL AS score FROM segments s JOIN episodes e ON e.id=s.episode_id "
               f"{'WHERE ' + ' AND '.join(where) if where else ''} "
               f"ORDER BY s.final_score DESC NULLS LAST, s.intensity DESC NULLS LAST, s.episode_id, s.rank LIMIT ? OFFSET ?")
        params = params + [limit, offset]
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def segment_detail(seg_id: int) -> Optional[dict]:
    conn = db.get_conn()
    s = conn.execute("SELECT s.*, e.guest, e.source_video, e.video_path FROM segments s JOIN episodes e ON e.id=s.episode_id "
                     "WHERE s.id=?", (seg_id,)).fetchone()
    if not s:
        return None
    d = dict(s)
    d["topics"] = [r[0] for r in conn.execute(
        "SELECT t.name FROM segment_topics st JOIN topics t ON t.id=st.topic_id WHERE st.segment_id=?", (seg_id,))]
    d["themes"] = [dict(r) for r in conn.execute(
        "SELECT th.slug, th.name_vi, st.is_primary FROM segment_themes st JOIN themes th ON th.id=st.theme_id WHERE st.segment_id=?",
        (seg_id,))]
    d["entities"] = [dict(r) for r in conn.execute(
        "SELECT e.name, e.type FROM segment_entities se JOIN entities e ON e.id=se.entity_id WHERE se.segment_id=?", (seg_id,))]
    d["hooks"] = [dict(r) for r in conn.execute(
        "SELECT id, rank, start_hms, end_hms, duration_sec, title, quote_en, hook_type, clip_path, clip_zoomed_path, status "
        "FROM segments WHERE parent_id=? ORDER BY rank", (seg_id,))]
    d["compilations"] = [dict(r) for r in conn.execute(
        "SELECT c.id, c.theme, c.slug, ci.ord, ci.role FROM compilation_items ci JOIN compilations c ON c.id=ci.compilation_id "
        "WHERE ci.segment_id=?", (seg_id,))]
    for k in ("extra_json", "raw_json", "analysis_json", "satellite_keywords_json"):
        if d.get(k):
            try:
                d[k[:-5] if k.endswith("_json") else k] = json.loads(d[k])
            except Exception:  # noqa: BLE001
                pass
    return d


def resolve_segment_ref(ref: str) -> Optional[int]:
    """Accept a numeric id or 'JRE-2530#3' (episode + rank)."""
    ref = str(ref).strip()
    if ref.isdigit():
        return int(ref)
    m = re.match(r"^([A-Za-z]+-\d+)#(\d+)$", ref)
    if m:
        r = db.row("SELECT id FROM segments WHERE episode_id=? AND rank=?", (m.group(1).upper(), int(m.group(2))))
        return r["id"] if r else None
    return None
