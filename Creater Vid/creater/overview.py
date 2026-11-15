"""Film overview: one picture of a documentary project, read from the files the steps write.

Top down: what the film says (title, thesis, acts on a timeline), what it is made of (characters, locations,
evidence), how it is cut (scenes). The page /p/<id>/overview draws it; every item links to the beats and scenes it
appears in, so a click narrows from the whole film to one beat. Works from step 1 on: parts not made yet are empty.
"""
from __future__ import annotations

from pathlib import Path

from .util import read_json
from .workflow import _list, _num

IMG_EXT = (".png", ".jpg", ".jpeg", ".webp", ".gif")
VID_EXT = (".mp4", ".webm", ".mov")
CLAIM_RANK = {"verified": 0, "unverified": 1, "disputed": 2}


def _d(x) -> dict:
    return x if isinstance(x, dict) else {}


def _media(d: Path, rel) -> str:
    """Project-relative path of an image/video named in the step files (film/public/…, project root, or as is)."""
    if not isinstance(rel, str) or not rel.lower().endswith(IMG_EXT + VID_EXT):
        return ""
    rel = rel.replace("\\", "/").lstrip("/")
    for cand in (rel, f"film/public/{rel}", f"film/{rel}"):
        if (d / cand).is_file():
            return cand
    return ""


def _strings(x):
    if isinstance(x, str):
        yield x
    elif isinstance(x, dict):
        for v in x.values():
            yield from _strings(v)
    elif isinstance(x, list):
        for v in x:
            yield from _strings(v)


def _first_media(d: Path, x, video=True) -> str:
    for s in _strings(x):
        m = _media(d, s)
        if m and (video or m.lower().endswith(IMG_EXT)):
            return m
    return ""


def _by_name(d: Path, eid) -> str:
    """A still saved next to the evidence under its id (film/public/evidence/E01_rogan.jpg for a clip E01)."""
    if not isinstance(eid, str) or not eid:
        return ""
    for folder in ("film/public/evidence", "film/public/docs"):
        base = d / folder
        if base.is_dir():
            for f in sorted(base.glob(f"{eid}*")):
                if f.suffix.lower() in IMG_EXT and (f.stem == eid or f.stem[len(eid):][:1] in "_-"):
                    return f"{folder}/{f.name}"
    return ""


def build(d: Path, p: dict) -> dict:
    script = _d(read_json(d / "1_script" / "script.json"))
    srcs = _d(read_json(d / "1_script" / "sources.json"))
    cast = _d(read_json(d / "2_cast" / "cast.json"))
    choices = _d(read_json(d / "2_cast" / "choices.json"))
    scn = _d(read_json(d / "3_scenes" / "scenes.json"))
    man = _d(read_json(d / "4_images" / "manifest.json"))
    render = _d(read_json(d / "6_render" / "render.json"))

    # generated / captured files by key (character id, evidence id, "<scene>_<layer>")
    files = {}
    for a in _list(man.get("assets")):
        a = _d(a)
        f = _media(d, a.get("file")) or _media(d, a.get("raw"))
        if a.get("key") and f:
            files[str(a["key"])] = f

    # ---- beats and acts
    beats = [_d(b) for b in _list(script.get("beats")) if isinstance(b, dict)]
    beat_by = {b.get("id"): b for b in beats}
    acts = [_d(a) for a in _list(script.get("acts")) if isinstance(a, dict)]
    act_of_beat = {b.get("id"): b.get("act") for b in beats}

    # ---- scenes (the real cut once step 3 exists)
    scenes_raw = [_d(s) for s in _list(scn.get("scenes")) if isinstance(s, dict)]
    scene_by = {s.get("id"): s for s in scenes_raw}
    scenes = []
    t = 0.0
    for s in scenes_raw:
        shot = _d(s.get("shot"))
        kind = shot.get("kind") or ("layers" if s.get("layers") or s.get("reuse_layers") else s.get("kind") or "scene")
        sid = s.get("id")
        thumb = _first_media(d, shot, video=False)
        if not thumb:  # layers: generated plates are keyed "<scene>_<layer>"; reused layers point at another scene
            for src in (sid, s.get("reuse_layers")):
                for lay in ("far", "mid", "fg", "bg", "full"):
                    if f"{src}_{lay}" in files:
                        thumb = files[f"{src}_{lay}"]
                        break
                if thumb:
                    break
        if not thumb:
            thumb = _first_media(d, s.get("layers"), video=False)
        if not thumb:
            thumb = next((files[e] for e in _list(s.get("evidence")) if e in files), "")
        if not thumb:
            thumb = _first_media(d, shot)  # a clip
        dur = _num(s.get("duration_sec"))
        s_beats = [b for b in _list(s.get("beats")) if isinstance(b, str)]
        chars = []
        for c in _list(s.get("characters")):
            cid = c.get("id") if isinstance(c, dict) else c
            if isinstance(cid, str):
                chars.append(cid)
        texts = [x.get("text") for x in _list(s.get("text_fx")) if isinstance(x, dict) and x.get("text")]
        scenes.append({
            "id": sid, "title": s.get("title") or "", "kind": kind, "start": round(t, 2), "dur": round(dur, 2),
            "beats": s_beats, "act": act_of_beat.get(s_beats[0]) if s_beats else None,
            "narration": s.get("narration") or "", "line": s.get("line"), "transition": s.get("transition") or "",
            "location": s.get("location"), "characters": chars, "evidence": [e for e in _list(s.get("evidence")) if isinstance(e, str)],
            "reconstruction": bool(s.get("reconstruction")), "label": s.get("label") or "",
            "grade": _d(s.get("look")).get("grade") or "", "text_fx": texts, "thumb": thumb,
            "speaker": shot.get("speaker") or "", "camera": _d(s.get("camera")).get("move") or "",
        })
        t += dur
    scenes_total = t

    # beat timing: from its scenes when cut, else its own estimate
    scenes_of_beat: dict[str, list] = {}
    for s in scenes:
        for b in s["beats"]:
            scenes_of_beat.setdefault(b, []).append(s)
    t = 0.0
    beat_rows = []
    for b in beats:
        bid = b.get("id")
        mine = scenes_of_beat.get(bid, [])
        if mine and scenes:
            start = min(x["start"] for x in mine)
            dur = sum(x["dur"] for x in mine)
        else:
            start, dur = t, _num(b.get("duration_sec"))
        t += _num(b.get("duration_sec"))
        q = _d(b.get("quote"))
        beat_rows.append({
            "id": bid, "act": b.get("act"), "type": b.get("type") or "", "role": b.get("role") or "",
            "start": round(start, 2), "dur": round(dur, 2), "est": _num(b.get("duration_sec")),
            "narration": b.get("narration") or "", "on_screen_text": b.get("on_screen_text") or "",
            "quote": {"speaker": q.get("speaker"), "text": q.get("text"), "source": q.get("source")} if q.get("text") else None,
            "visual_idea": b.get("visual_idea") or "", "characters": [c for c in _list(b.get("characters")) if isinstance(c, str)],
            "sources": [x for x in _list(b.get("sources")) if isinstance(x, str)],
            "evidence": [x for x in _list(b.get("evidence")) if isinstance(x, str)],
            "scenes": [x["id"] for x in mine],
        })
    beats_total = t
    total = scenes_total if scenes else beats_total

    act_rows = []
    for a in acts:
        aid = a.get("id")
        mine = [b for b in beat_rows if b["act"] == aid]
        if mine:
            start = min(b["start"] for b in mine)
            end = max(b["start"] + b["dur"] for b in mine)
        else:
            start = end = 0
        act_rows.append({"id": aid, "title": a.get("title") or aid, "summary": a.get("summary") or "",
                         "start": round(start, 2), "dur": round(end - start, 2), "beats": [b["id"] for b in mine],
                         "scenes": [s["id"] for s in scenes if s["act"] == aid]})

    # ---- characters
    cast_ids = set()
    chars = []
    for c in _list(cast.get("characters")):
        c = _d(c)
        cid = c.get("id")
        if not cid:
            continue
        cast_ids.add(cid)
        thumb = files.get(cid) or _media(d, choices.get(cid)) or _media(d, _d(scn.get("choices")).get(cid))
        if not thumb:
            thumb = next((_media(d, _d(x).get("file")) for x in _list(c.get("candidates")) if _media(d, _d(x).get("file"))), "")
        if not thumb:
            for ph in _list(c.get("photos")):
                e = _d(ph).get("evidence")
                thumb = files.get(e, "") or _first_media(d, ph, video=False) or _by_name(d, e)
                if thumb:
                    break
        b_ids = [b["id"] for b in beat_rows if cid in b["characters"]] or [x for x in _list(c.get("beats")) if isinstance(x, str)]
        s_ids = [s["id"] for s in scenes if cid in s["characters"]]
        chars.append({"id": cid, "name": c.get("name") or cid, "role": c.get("role") or "", "kind": c.get("kind") or "",
                      "depiction": c.get("depiction") or "", "description": c.get("description") or "", "look": c.get("look") or "",
                      "thumb": thumb, "beats": b_ids, "scenes": s_ids})
    for b in beat_rows:  # named in the script, not cast yet
        for cid in b["characters"]:
            if cid not in cast_ids:
                cast_ids.add(cid)
                chars.append({"id": cid, "name": cid, "role": "", "kind": "", "depiction": "", "description": "", "look": "",
                              "thumb": "", "beats": [x["id"] for x in beat_rows if cid in x["characters"]], "scenes": []})
    role_order = {"narrator": 0, "main": 1, "supporting": 2, "crowd": 3}
    chars.sort(key=lambda c: (role_order.get(c["role"], 4), -len(c["beats"])))

    # ---- locations
    locs = []
    for lo in _list(scn.get("locations")):
        lo = _d(lo)
        lid = lo.get("id")
        if not lid:
            continue
        thumb = next((files[_d(pl).get("key")] for pl in _list(lo.get("plates")) if _d(pl).get("key") in files), "")
        s_ids = [s["id"] for s in scenes if s["location"] == lid]
        if not thumb:
            thumb = next((s["thumb"] for s in scenes if s["id"] in s_ids and s["thumb"]), "")
        locs.append({"id": lid, "name": lo.get("name") or lid, "era": lo.get("era") or "", "description": lo.get("description") or "",
                     "thumb": thumb, "scenes": s_ids, "beats": sorted({b for s in scenes if s["id"] in s_ids for b in s["beats"]})})

    # ---- evidence (step 3 list, else the step 1 plan)
    plan = {_d(e).get("id"): _d(e) for e in _list(script.get("evidence_plan"))}
    ev_src = [_d(e) for e in _list(scn.get("evidence"))] or list(plan.values())
    evid = []
    for e in ev_src:
        eid = e.get("id")
        if not eid:
            continue
        pe = plan.get(eid, {})
        thumb = files.get(eid) or _first_media(d, e.get("file"), video=False) or _by_name(d, eid)
        s_ids = [s["id"] for s in scenes if eid in s["evidence"]]
        if not thumb:
            thumb = next((s["thumb"] for s in scenes if s["id"] in s_ids and s["thumb"]), "")
        b_ids = sorted({b["id"] for b in beat_rows if eid in b["evidence"]} | {b for s in scenes if s["id"] in s_ids for b in s["beats"]})
        evid.append({"id": eid, "type": e.get("type") or pe.get("type") or "", "what": pe.get("what") or e.get("what") or "",
                     "proves": e.get("proves") or pe.get("proves") or "", "url": e.get("source_url") or pe.get("source") or "",
                     "license": e.get("license") or pe.get("license") or "", "note": e.get("note") or "",
                     "thumb": thumb, "scenes": s_ids, "beats": b_ids})

    # ---- sources and claims
    sources = [_d(x) for x in _list(srcs.get("sources")) if isinstance(x, dict)]
    claims = [_d(x) for x in _list(srcs.get("claims")) if isinstance(x, dict)]
    claim_count = {"verified": 0, "disputed": 0, "unverified": 0}
    for c in claims:
        st = c.get("status") or "unverified"
        claim_count[st] = claim_count.get(st, 0) + 1
    # a beat leans on a disputed / unverified claim when it cites one of that claim's sources
    worst_by_src: dict[str, str] = {}
    for c in claims:
        st = c.get("status") or "unverified"
        for s in _list(c.get("sources")):
            if CLAIM_RANK.get(st, 1) > CLAIM_RANK.get(worst_by_src.get(s, "verified"), 0):
                worst_by_src[s] = st
    for b in beat_rows:
        b["claims"] = [{"id": c.get("id"), "text": c.get("text"), "status": c.get("status") or "unverified", "note": c.get("note") or ""}
                       for c in claims if set(_list(c.get("sources"))) & set(b["sources"])]

    # ---- warnings a person should look at
    warns = []
    target = _num(script.get("target_sec") or p.get("target_sec"))
    if target and total and total < target:
        warns.append(f"Phim {int(total)} s, ngắn hơn mục tiêu {int(target)} s")
    for b in beat_rows:
        words = len(b["narration"].split())
        if words and b["est"] and words / 2.6 > b["est"] * 1.2:
            warns.append(f"{b['id']}: lời dẫn {words} chữ (~{words / 2.6:.0f} s) dài hơn {b['est']:g} s dự tính")
        if b["dur"] > 45:
            warns.append(f"{b['id']}: một beat kéo dài {b['dur']:.0f} s")
    if beat_rows and beat_rows[0]["type"] not in ("cold_open", "quote") and beat_rows[0]["role"] != "hook":
        warns.append("Beat đầu không phải hook / cold open")
    for e in evid:
        if scenes and not e["scenes"]:
            warns.append(f"Bằng chứng {e['id']} chưa dùng ở cảnh nào")
    for c in chars:
        if c["role"] in ("main", "supporting") and not c["beats"]:
            warns.append(f"Nhân vật {c['name']} không có beat nào")

    video = ""
    for v in reversed(_list(render.get("versions"))):
        video = _media(d, _d(v).get("file"))
        if video:
            break

    steps = _d(p.get("steps"))
    voice = _d(script.get("voice"))
    budget = _d(scn.get("budget"))
    return {
        "title": script.get("title") or p.get("title"), "logline": script.get("logline") or "", "thesis": script.get("thesis") or "",
        "frame": script.get("frame") or "", "pipeline": p.get("pipeline") or scn.get("pipeline") or "",
        "style": script.get("style") or p.get("style") or "", "format": script.get("format") or p.get("format"),
        "target_sec": target, "est_sec": _num(script.get("est_sec")) or beats_total, "total_sec": round(total, 2),
        "cut": bool(scenes), "video": video,
        "voice": {"name": voice.get("name"), "usd": voice.get("est_usd")} if voice else None,
        "budget": {"est": budget.get("est_usd"), "limit": budget.get("budget_usd") or p.get("budget_usd")} if budget else None,
        "steps": steps, "acts": act_rows, "beats": beat_rows, "scenes": scenes, "characters": chars,
        "locations": locs, "evidence": evid,
        "sources": [{"id": x.get("id"), "title": x.get("title"), "url": x.get("url"), "type": x.get("type"),
                     "reliability": x.get("reliability"), "author": x.get("author"), "date": x.get("date")} for x in sources],
        "claims": [{"id": c.get("id"), "text": c.get("text"), "status": c.get("status") or "unverified", "note": c.get("note") or "",
                    "sources": _list(c.get("sources"))} for c in claims],
        "claim_count": claim_count, "warnings": warns,
        "risks": [x for x in _list(script.get("risks")) if isinstance(x, str)],
        "open_questions": [x for x in _list(script.get("open_questions")) if isinstance(x, str)],
    }
