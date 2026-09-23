"""Capture the skill's per-segment analysis block (Mục VI locked format) and store it on the segment.

Two sources:
1. `analysis_<episode>.json` written by the headless run (structured, preferred).
2. Free text pasted from a manual desktop run or captured from the headless chat log (parsed here).
"""
from __future__ import annotations

import json
import re
from typing import Optional

from . import db
from .util import hms_to_sec, now_iso

_RE_HEAD = re.compile(r"^\s*\[?(\d{1,2})\]?\.\s*\*\*(.+?)\*\*\s*$", re.M)
_RE_START = re.compile(r"Start:\s*\(?(\d{1,2}:\d{2}:\d{2})\)?\s*[\"“]?(.*?)[\"”]?\s*$", re.M)
_RE_END = re.compile(r"End:\s*\(?(\d{1,2}:\d{2}:\d{2})\)?\s*[\"“]?(.*?)[\"”]?\s*$", re.M)
_RE_KEYWORD = re.compile(r"Keyword hạt nhân:\*{0,2}\s*`?([^`\n·]+)`?\s*·\s*\*{0,2}Reach\s*(R\d)\*{0,2}\s*·\s*\*{0,2}KGC\s*([^\n*]+)",
                         re.I)
_SECTION_MARKS = [
    ("tom_tat", r"Tóm tắt:"),
    ("ly_do_dat", r"Tại sao đoạn này đắt:"),
    ("hook_cold_open", r"HOOK COLD OPEN"),
    ("keyword", r"Keyword hạt nhân:"),
    ("fit", r"Fit với khách mời:"),
    ("cut_block", r"CUT BLOCK"),
]


def split_blocks(text: str) -> list[dict]:
    """Split a skill output into per-segment blocks: [{index, title, raw}]."""
    heads = list(_RE_HEAD.finditer(text))
    blocks = []
    for i, h in enumerate(heads):
        end = heads[i + 1].start() if i + 1 < len(heads) else len(text)
        raw = text[h.start():end].rstrip()
        blocks.append({"index": int(h.group(1)), "title": h.group(2).strip(), "raw": raw})
    return blocks


def parse_block(raw: str) -> dict:
    """Extract the named sections of one block. Unknown layout parts are kept in raw."""
    out: dict = {"raw_md": raw}
    m = _RE_START.search(raw)
    if m:
        out["start_hms"], out["start_quote"] = m.group(1), m.group(2).strip()
    m = _RE_END.search(raw)
    if m:
        out["end_hms"], out["end_quote"] = m.group(1), m.group(2).strip()
    # locate section starts
    positions = []
    for key, pat in _SECTION_MARKS:
        mm = re.search(pat, raw)
        if mm:
            positions.append((mm.start(), key, mm.end()))
    positions.sort()
    for i, (pos, key, body_start) in enumerate(positions):
        end = positions[i + 1][0] if i + 1 < len(positions) else len(raw)
        body = raw[body_start:end].strip()
        body = re.sub(r"^\*+\s*|\s*\*+$", "", body).strip()
        out[key] = body
    m = _RE_KEYWORD.search(raw)
    if m:
        out["core_keyword"] = m.group(1).strip().strip("`").strip()
        out["keyword_reach"] = m.group(2).upper()
        out["kgc"] = m.group(3).strip().strip("*").strip()
    return out


def match_segment(episode_id: str, parsed: dict, title: str) -> Optional[int]:
    conn = db.get_conn()
    if parsed.get("start_hms") and parsed.get("end_hms"):
        try:
            st, en = hms_to_sec(parsed["start_hms"]), hms_to_sec(parsed["end_hms"])
        except ValueError:
            st = en = None
        if st is not None:
            r = conn.execute(
                "SELECT id FROM segments WHERE episode_id=? AND kind='highlight' AND start_sec IS NOT NULL "
                "AND abs(start_sec-?)<=3 AND abs(end_sec-?)<=3 ORDER BY abs(start_sec-?) LIMIT 1",
                (episode_id, st, en, st)).fetchone()
            if r:
                return r["id"]
            r = conn.execute(
                "SELECT id FROM segments WHERE episode_id=? AND kind='highlight' AND start_sec IS NOT NULL "
                "AND abs(start_sec-?)<=3 ORDER BY abs(start_sec-?) LIMIT 1", (episode_id, st, st)).fetchone()
            if r:
                return r["id"]
    if title:
        r = conn.execute("SELECT id FROM segments WHERE episode_id=? AND kind='highlight' AND lower(title)=lower(?)",
                         (episode_id, title.strip())).fetchone()
        if r:
            return r["id"]
    return None


def import_markdown(episode_id: str, text: str, source: str = "manual") -> dict:
    """Parse pasted/captured skill output and attach each block to its segment."""
    blocks = split_blocks(text)
    stats = {"blocks": len(blocks), "attached": 0, "unmatched": []}
    conn = db.get_conn()
    for b in blocks:
        parsed = parse_block(b["raw"])
        seg_id = match_segment(episode_id, parsed, b["title"])
        if seg_id is None:
            stats["unmatched"].append(b["title"])
            continue
        structured = {k: v for k, v in parsed.items() if k != "raw_md"}
        structured["source"] = source
        with db.tx(conn) as c:
            c.execute("UPDATE segments SET analysis_md=?, analysis_json=?, updated_at=? WHERE id=?",
                      (b["raw"], json.dumps(structured, ensure_ascii=False), now_iso(), seg_id))
        stats["attached"] += 1
    if stats["attached"]:
        from .search import rebuild_index
        rebuild_index()
    return stats


def import_analysis_json(episode_id: str, data, source: str = "headless") -> dict:
    """Attach entries of analysis_<episode>.json: [{content_rank|title|start|end, tom_tat, ly_do_dat, ..., raw_md}]."""
    items = data.get("segments") if isinstance(data, dict) else data
    stats = {"blocks": len(items or []), "attached": 0, "unmatched": []}
    conn = db.get_conn()
    for it in items or []:
        parsed = {"start_hms": it.get("start"), "end_hms": it.get("end")}
        seg_id = match_segment(episode_id, parsed, it.get("title", ""))
        if seg_id is None and it.get("content_rank"):
            r = conn.execute("SELECT id FROM segments WHERE episode_id=? AND kind='highlight' AND content_rank=?",
                             (episode_id, int(it["content_rank"]))).fetchone()
            seg_id = r["id"] if r else None
        if seg_id is None:
            stats["unmatched"].append(it.get("title"))
            continue
        raw_md = it.get("raw_md") or render_markdown(it)
        structured = {k: v for k, v in it.items() if k != "raw_md"}
        structured["source"] = source
        with db.tx(conn) as c:
            c.execute("UPDATE segments SET analysis_md=?, analysis_json=?, updated_at=? WHERE id=?",
                      (raw_md, json.dumps(structured, ensure_ascii=False), now_iso(), seg_id))
        stats["attached"] += 1
    if stats["attached"]:
        from .search import rebuild_index
        rebuild_index()
    return stats


def render_markdown(it: dict) -> str:
    """Rebuild a readable block from structured fields (used when the run wrote JSON only)."""
    parts = [f"**{it.get('title', '')}**", ""]
    if it.get("start"):
        parts.append(f"Start: ({it['start']}) \"{it.get('start_quote', '')}\"")
    if it.get("end"):
        parts.append(f"End: ({it['end']}) \"{it.get('end_quote', '')}\"")
    for key, label in (("tom_tat", "Tóm tắt"), ("ly_do_dat", "Tại sao đoạn này đắt"),
                       ("hook_cold_open", "🪝 HOOK COLD OPEN"), ("keyword", "🔑 Keyword hạt nhân"),
                       ("fit", "🎯 Fit với khách mời")):
        if it.get(key):
            parts += ["", f"{label}: {it[key]}"]
    return "\n".join(parts).strip()
