"""Capture the skill's per-segment analysis block (Mục VI locked format) and store it on the segment.

Sources:
1. `analysis_<episode>.json` written by the headless run (structured, preferred).
2. Text pasted from the desktop app or captured from the headless chat log. The paste may be raw markdown
   ("[1]. **Title**") or the rendered text copied from the chat ("1. Title", no ** markers, emoji kept), so the
   splitter tries several layouts and the matcher uses Start/End, hook timestamps, CUT BLOCK json, title, keyword.
"""
from __future__ import annotations

import json
import re
from typing import Optional

from . import db
from .util import hms_to_sec, norm_key, now_iso

_RE_HEAD_MD = re.compile(r"^\s*\[?(\d{1,2})\]?\.\s*\*\*(.+?)\*\*\s*$", re.M)
# rendered heading: "6. Title" but not a hook item "1. (02:14:01 – 02:14:15 · ~14s) ..."
_RE_HEAD_PLAIN = re.compile(r"^\s*\[?(\d{1,2})\]?\.\s+(?![\(`\"“(\d])(\S.{3,140}?)\s*$", re.M)
_RE_START = re.compile(r"Start:\s*\(?(\d{1,2}:\d{2}:\d{2})\)?\s*[\"“]?(.*?)[\"”]?\s*$", re.M)
_RE_END = re.compile(r"End:\s*\(?(\d{1,2}:\d{2}:\d{2})\)?\s*[\"“]?(.*?)[\"”]?\s*$", re.M)
_RE_TOMTAT = re.compile(r"^\s*(?:\*\*)?Tóm tắt(?:\*\*)?\s*:", re.M)
_RE_HOOK_TS = re.compile(r"\(\s*(\d{1,2}:\d{2}:\d{2})\s*[–—-]\s*(\d{1,2}:\d{2}:\d{2})")
_RE_KEYWORD = re.compile(r"Keyword hạt nhân:\*{0,2}\s*`?([^`\n·]+?)`?\s*·\s*\*{0,2}Reach\s*(R\d)\*{0,2}\s*·\s*\*{0,2}KGC\s*([^\n*]+)",
                         re.I)
_RE_CUT_START = re.compile(r'"kind"\s*:\s*"highlight"[^}]*?"start"\s*:\s*"(\d{1,2}:\d{2}:\d{2})"')
_SECTION_MARKS = [
    ("tom_tat", r"Tóm tắt\s*:"),
    ("ly_do_dat", r"Tại sao đoạn này đắt\s*:"),
    ("hook_cold_open", r"HOOK COLD OPEN"),
    ("keyword", r"Keyword hạt nhân\s*:"),
    ("fit", r"Fit với khách mời\s*:"),
    ("cut_block", r"CUT BLOCK"),
]


def _heads(text: str, pattern: re.Pattern, require_body: bool) -> list[tuple[int, int, str]]:
    """(position, index, title) for headings; with require_body a heading must be followed by Start:/Tóm tắt: soon after."""
    out = []
    for m in pattern.finditer(text):
        if require_body:
            window = text[m.end():m.end() + 1200]
            if not (_RE_START.search(window) or _RE_TOMTAT.search(window)):
                continue
        out.append((m.start(), int(m.group(1)), m.group(2).strip()))
    return out


def split_blocks(text: str) -> list[dict]:
    """Split a skill output into per-segment blocks: [{index, title, raw}]."""
    text = text.replace("\r\n", "\n")
    heads = _heads(text, _RE_HEAD_MD, require_body=False) or _heads(text, _RE_HEAD_PLAIN, require_body=True)
    if not heads:
        # no headings survived (rendered copy without numbers): split at Start: lines, else at Tóm tắt: lines
        anchors = [m.start() for m in _RE_START.finditer(text)] or [m.start() for m in _RE_TOMTAT.finditer(text)]
        heads = [(pos, i + 1, "") for i, pos in enumerate(anchors)]
        if heads and heads[0][0] > 0:
            # keep up to 3 non-empty lines above the first anchor as its header (title usually sits there)
            prefix = text[:heads[0][0]].rstrip("\n").split("\n")
            keep = [ln for ln in prefix if ln.strip()][-3:]
            heads[0] = (max(0, heads[0][0] - sum(len(ln) + 1 for ln in keep)), 1, keep[0].strip("*# ") if keep else "")
    blocks = []
    for i, (pos, idx, title) in enumerate(heads):
        end = heads[i + 1][0] if i + 1 < len(heads) else len(text)
        raw = text[pos:end].strip()
        if len(raw) < 40:
            continue
        blocks.append({"index": idx, "title": title, "raw": raw})
    return blocks


def parse_block(raw: str) -> dict:
    """Extract the named sections of one block. Unknown layout parts stay in raw_md."""
    out: dict = {"raw_md": raw}
    m = _RE_START.search(raw)
    if m:
        out["start_hms"], out["start_quote"] = m.group(1), m.group(2).strip()
    m = _RE_END.search(raw)
    if m:
        out["end_hms"], out["end_quote"] = m.group(1), m.group(2).strip()
    positions = []
    for key, pat in _SECTION_MARKS:
        mm = re.search(pat, raw)
        if mm:
            positions.append((mm.start(), key, mm.end()))
    positions.sort()
    for i, (pos, key, body_start) in enumerate(positions):
        end = positions[i + 1][0] if i + 1 < len(positions) else len(raw)
        body = raw[body_start:end].strip()
        body = re.sub(r"^[\s*:]+|[\s*]+$", "", body).strip()
        out[key] = body
    m = _RE_KEYWORD.search(raw)
    if m:
        out["core_keyword"] = m.group(1).strip().strip("`").strip()
        out["keyword_reach"] = m.group(2).upper()
        out["kgc"] = m.group(3).strip().strip("*").strip()
    hooks = _RE_HOOK_TS.findall(out.get("hook_cold_open") or raw)
    if hooks:
        out["hook_times"] = [{"start": a, "end": b} for a, b in hooks]
    cut = _RE_CUT_START.findall(raw)
    if cut:
        out["cut_block_start"] = cut[0]
    return out


def _nearest_highlight(conn, episode_id: str, st: float, en: Optional[float] = None, tol: float = 3.0):
    if en is not None:
        r = conn.execute(
            "SELECT id FROM segments WHERE episode_id=? AND kind='highlight' AND start_sec IS NOT NULL "
            "AND abs(start_sec-?)<=? AND abs(end_sec-?)<=? ORDER BY abs(start_sec-?) LIMIT 1",
            (episode_id, st, tol, en, tol, st)).fetchone()
        if r:
            return r["id"]
    r = conn.execute(
        "SELECT id FROM segments WHERE episode_id=? AND kind='highlight' AND start_sec IS NOT NULL "
        "AND abs(start_sec-?)<=? ORDER BY abs(start_sec-?) LIMIT 1", (episode_id, st, tol, st)).fetchone()
    return r["id"] if r else None


def match_segment(episode_id: str, parsed: dict, title: str) -> Optional[int]:
    conn = db.get_conn()
    # 1. Start / End of the block
    if parsed.get("start_hms"):
        try:
            st = hms_to_sec(parsed["start_hms"])
            en = hms_to_sec(parsed["end_hms"]) if parsed.get("end_hms") else None
            sid = _nearest_highlight(conn, episode_id, st, en)
            if sid:
                return sid
        except ValueError:
            pass
    # 2. CUT BLOCK json inside the block
    if parsed.get("cut_block_start"):
        try:
            sid = _nearest_highlight(conn, episode_id, hms_to_sec(parsed["cut_block_start"]))
            if sid:
                return sid
        except ValueError:
            pass
    # 3. hook timestamps: a hook segment (-> its parent) or the highlight that contains the hook
    for h in parsed.get("hook_times") or []:
        try:
            hs, he = hms_to_sec(h["start"]), hms_to_sec(h["end"])
        except ValueError:
            continue
        r = conn.execute(
            "SELECT parent_id FROM segments WHERE episode_id=? AND kind='hook' AND parent_id IS NOT NULL "
            "AND abs(start_sec-?)<=3 ORDER BY abs(start_sec-?) LIMIT 1", (episode_id, hs, hs)).fetchone()
        if r and r["parent_id"]:
            return r["parent_id"]
        r = conn.execute(
            "SELECT id FROM segments WHERE episode_id=? AND kind='highlight' AND start_sec IS NOT NULL "
            "AND start_sec-2<=? AND end_sec+2>=? ORDER BY (end_sec-start_sec) LIMIT 1", (episode_id, hs, he)).fetchone()
        if r:
            return r["id"]
    # 4. title, exact then fuzzy
    if title and len(title.strip()) >= 6:
        t = norm_key(title)
        for r in conn.execute("SELECT id, title FROM segments WHERE episode_id=? AND kind='highlight'", (episode_id,)):
            st = norm_key(r["title"] or "")
            if st and (st == t or st.startswith(t[:40]) or t.startswith(st[:40])):
                return r["id"]
    # 5. core keyword
    if parsed.get("core_keyword"):
        r = conn.execute("SELECT id FROM segments WHERE episode_id=? AND kind='highlight' AND lower(core_keyword)=lower(?)",
                         (episode_id, parsed["core_keyword"])).fetchone()
        if r:
            return r["id"]
    return None


def import_markdown(episode_id: str, text: str, source: str = "manual") -> dict:
    """Parse pasted/captured skill output and attach each block to its segment."""
    blocks = split_blocks(text or "")
    stats = {"blocks": len(blocks), "attached": 0, "unmatched": [], "matched": []}
    conn = db.get_conn()
    for b in blocks:
        parsed = parse_block(b["raw"])
        seg_id = match_segment(episode_id, parsed, b["title"])
        label = b["title"] or parsed.get("start_hms") or (parsed.get("tom_tat") or "")[:40]
        if seg_id is None:
            stats["unmatched"].append(label)
            continue
        structured = {k: v for k, v in parsed.items() if k != "raw_md"}
        structured["source"] = source
        with db.tx(conn) as c:
            c.execute("UPDATE segments SET analysis_md=?, analysis_json=?, updated_at=? WHERE id=?",
                      (b["raw"], json.dumps(structured, ensure_ascii=False), now_iso(), seg_id))
        seg_title = conn.execute("SELECT title FROM segments WHERE id=?", (seg_id,)).fetchone()[0]
        stats["matched"].append({"block": label, "segment_id": seg_id, "segment_title": seg_title})
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
        if it.get("raw_md"):
            parsed.update({k: v for k, v in parse_block(it["raw_md"]).items() if k not in parsed or not parsed[k]})
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
