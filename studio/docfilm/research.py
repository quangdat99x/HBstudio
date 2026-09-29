"""Step 1 input: candidate highlights for a topic, straight from the database (no Claude).

The pool is ranked by how well a segment matches the topic (full-text search on the whole topic, on its
word pairs and English keywords, and on the themes whose names match) times its quality score. Every
candidate gets its transcript with exact line timestamps, so Claude can pick verbatim quotes and cut them.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from .. import db, search
from ..util import now_iso, sec_to_hms, strip_diacritics
from .store import project_dir

_STOP = set("""a an and are as at be but by for from has have how i if in into is it its of on or that the their them they this
to was were what when where which who why will with you your about after before over under than then there these those
va cua nhung cac la co cho voi trong ve mot nguoi den tu nay khi thi da se duoc bi cung nhu""".split())


def _tokens(text: str) -> list[str]:
    return [t for t in re.split(r"[^\w]+", strip_diacritics(text or "").lower()) if t]


def queries_for(topic: str) -> list[tuple[str, float]]:
    """(query, weight): the whole topic, adjacent word pairs, and English-looking keywords of 4+ letters."""
    words = [w for w in re.split(r"\s+", (topic or "").strip()) if w]
    toks = [t for t in _tokens(topic) if t not in _STOP]
    out: list[tuple[str, float]] = [(topic.strip(), 3.0)]
    for a, b in zip(words, words[1:]):
        pair = f"{a} {b}"
        if not all(t in _STOP for t in _tokens(pair)):
            out.append((pair, 1.4))
    for t in toks:
        if len(t) >= 4 and t.isascii():
            out.append((t, 1.0))
    seen, uniq = set(), []
    for q, w in out:
        if q and q.lower() not in seen:
            seen.add(q.lower())
            uniq.append((q, w))
    return uniq


def _matching_themes(topic: str) -> list[str]:
    toks = {t for t in _tokens(topic) if t not in _STOP and len(t) >= 3}
    hits = []
    for th in db.rows("SELECT slug, name_vi FROM themes"):
        words = set(_tokens(th["slug"].replace("-", " ") + " " + (th["name_vi"] or "")))
        if toks & words:
            hits.append(th["slug"])
    return hits


def _transcript_text(seg: dict) -> str:
    lines = db.rows("SELECT start_sec, end_sec, text FROM transcript_lines WHERE episode_id=? AND start_sec<? AND end_sec>? "
                    "ORDER BY seq", (seg["episode_id"], seg["end_sec"] or 0, seg["start_sec"] or 0))
    if lines:
        return "\n".join(f"[{l['start_sec']:.2f}–{l['end_sec']:.2f} | {sec_to_hms(l['start_sec'])}] {l['text'].strip()}"
                         for l in lines)
    return seg.get("transcript") or ""


def build_pool(p: dict, limit: int = 40) -> dict:
    """Write research/pool.json, research/pool.md and research/transcripts/<id>.txt. Returns the pool."""
    topic = p["topic"]
    hits: dict[int, dict] = {}

    def add(rows: list[dict], weight: float, via: str) -> None:
        for rank, r in enumerate(rows):
            if r.get("kind") != "highlight":
                continue
            h = hits.setdefault(r["id"], {"rel": 0.0, "via": []})
            h["rel"] += weight / (1 + 0.12 * rank)
            if via not in h["via"]:
                h["via"].append(via)

    for q, w in queries_for(topic):
        add(search.search(q, kind="highlight", limit=60), w, f"tìm: {q}")
    for slug in _matching_themes(topic):
        add(search.search("", theme=slug, kind="highlight", limit=80), 0.8, f"theme: {slug}")

    if not hits:
        pool = {"topic": topic, "built_at": now_iso(), "segments": [], "note": "không tìm thấy đoạn nào khớp chủ đề"}
    else:
        top_rel = max(h["rel"] for h in hits.values())
        rows = {r["id"]: r for r in db.rows(
            f"""SELECT s.*, e.guest, e.title AS episode_title FROM segments s JOIN episodes e ON e.id=s.episode_id
                WHERE s.id IN ({','.join('?' * len(hits))}) AND s.status!='archived'""", list(hits))}
        ranked = []
        for sid, h in hits.items():
            s = rows.get(sid)
            if not s:
                continue
            quality = (s.get("final_score") or s.get("intensity") or 5) / 10
            h["score"] = round((h["rel"] / top_rel) * (0.55 + 0.45 * min(1.0, quality)), 4)
            ranked.append((h["score"], sid))
        ranked.sort(reverse=True)
        out_dir = project_dir(p) / "research" / "transcripts"
        out_dir.mkdir(parents=True, exist_ok=True)
        segments = []
        for score, sid in ranked[:limit]:
            s = rows[sid]
            themes = [r["slug"] for r in db.rows(
                "SELECT th.slug FROM segment_themes st JOIN themes th ON th.id=st.theme_id WHERE st.segment_id=? "
                "ORDER BY st.is_primary DESC", (sid,))]
            clip = s.get("clip_zoomed_path") or s.get("clip_path")
            header = [
                f"# {s['episode_id']} · {s.get('guest') or ''} · segment {sid}: {s['title']}",
                f"# highlight {s.get('start_hms')} → {s.get('end_hms')} (start_sec {s.get('start_sec')}, end_sec {s.get('end_sec')})",
                f"# clip: {clip or '(chưa có clip)'}",
                f"# Clip bắt đầu đúng ở start_sec của đoạn: vị trí trong file clip = thời điểm trong tập - {s.get('start_sec')}",
                "# Mỗi dòng: [giây bắt đầu–giây kết thúc | giờ trong tập] lời nói nguyên văn",
                "",
            ]
            tfile = out_dir / f"{sid}.txt"
            tfile.write_text("\n".join(header) + _transcript_text(s) + "\n", encoding="utf-8")
            segments.append({
                "segment_id": sid, "episode_id": s["episode_id"], "guest": s.get("guest"), "title": s["title"],
                "core_keyword": s.get("core_keyword"), "final_score": s.get("final_score"), "intensity": s.get("intensity"),
                "relevance": score, "found_by": hits[sid]["via"], "themes": themes,
                "start_sec": s.get("start_sec"), "end_sec": s.get("end_sec"), "start_hms": s.get("start_hms"),
                "end_hms": s.get("end_hms"), "duration_sec": s.get("duration_sec"),
                "summary_vi": s.get("summary_vi"), "summary_en": s.get("summary_en"), "hook_en": s.get("hook_en"),
                "quote_en": s.get("quote_en"), "clip": clip,
                "transcript_file": str(tfile.relative_to(project_dir(p))).replace("\\", "/"),
            })
        pool = {"topic": topic, "built_at": now_iso(), "queries": [q for q, _ in queries_for(topic)],
                "themes": _matching_themes(topic), "segments": segments}
    rdir = project_dir(p) / "research"
    rdir.mkdir(parents=True, exist_ok=True)
    (rdir / "pool.json").write_text(json.dumps(pool, ensure_ascii=False, indent=2), encoding="utf-8")
    (rdir / "pool.md").write_text(_pool_md(pool), encoding="utf-8")
    return pool


def _pool_md(pool: dict) -> str:
    lines = [f"# Ứng viên cho chủ đề: {pool['topic']}", "",
             f"{len(pool['segments'])} đoạn highlight, xếp theo độ khớp chủ đề × điểm chất lượng.", "",
             "| # | id | tập | khách | đoạn | điểm | khớp | keyword | dài |", "|---|---|---|---|---|---|---|---|---|"]
    for i, s in enumerate(pool["segments"], 1):
        dur = f"{int((s.get('duration_sec') or 0) // 60)}:{int((s.get('duration_sec') or 0) % 60):02d}"
        lines.append(f"| {i} | {s['segment_id']} | {s['episode_id']} | {s.get('guest') or ''} | {s['title']} | "
                     f"{s.get('final_score') or '-'} | {s['relevance']} | {s.get('core_keyword') or ''} | {dur} |")
    lines.append("")
    for s in pool["segments"]:
        if s.get("summary_vi"):
            lines.append(f"- **{s['segment_id']}** {s['title']}: {s['summary_vi']}")
    return "\n".join(lines) + "\n"


def pool_file(p: dict) -> Path:
    return project_dir(p) / "research" / "pool.json"
