"""Project blueprint: how the film is going to be made, drawn at step 1 before anything is built.

Claude writes 1_script/blueprint.json at step 1 (rulebook 2.1 step 8, schema 11.1): the approach, the spine, every
act (its job, the question it opens, the hand-off to the next), the assets each act needs, the plan of steps 2–7 and
the budget. Projects made before that file existed get a blueprint derived from script.json / research.md, so the
page /p/<id>/blueprint works for every documentary. Fields the file leaves out are filled from the derivation.
"""
from __future__ import annotations

import re
from pathlib import Path

from .util import read_json
from .workflow import _list, _num, flow

# what a beat will look like on screen, from the evidence it uses (rulebook 11.1 evidence_plan types)
EVIDENCE_VISUAL = {
    "archival_video": "clip", "interview_clip": "clip", "video": "clip", "clip": "clip",
    "page": "document", "document": "document", "article": "document", "scan": "document", "book": "document", "paper": "document",
    "photo": "real_photo", "portrait": "real_photo", "image": "real_photo",
    "logo": "logo", "map": "map", "reconstruction": "reconstruction", "footage": "footage", "board": "board",
}
VISUALS = ("clip", "document", "real_photo", "reconstruction", "map", "board", "archive", "logo", "years", "footage", "text")
BUILD_STEPS = ("cast", "scenes", "images", "footage", "render", "metadata")


def _d(x) -> dict:
    return x if isinstance(x, dict) else {}


def _strs(x) -> list[str]:
    return [v for v in _list(x) if isinstance(v, str) and v]


def _beat_visuals(b: dict, ev_type: dict) -> list[str]:
    out = []
    if b.get("type") == "quote" or _d(b.get("quote")).get("text") and not b.get("narration"):
        out.append("clip")
    for e in _strs(b.get("evidence")):
        v = EVIDENCE_VISUAL.get(str(ev_type.get(e, "")).lower())
        if v and v not in out:
            out.append(v)
    idea = str(b.get("visual_idea") or "").lower()
    for key, v in (("reconstruction", "reconstruction"), ("ai ", "reconstruction"), ("map", "map"), ("board", "board"),
                   ("years", "years"), ("timeline", "years"), ("archive", "archive"), ("8mm", "archive"), ("logo", "logo")):
        if key in idea and v not in out:
            out.append(v)
    if b.get("type") in ("title", "outro") and not out:
        out.append("text")
    if b.get("type") == "reconstruction" and "reconstruction" not in out:
        out.append("reconstruction")
    return out or ["text"]


def _options_from_research(md: str) -> list[dict]:
    """The 2–3 outline options of research.md ("1. **Name (...)**, ĐÃ CHỌN. idea…" + "- Lý do chọn: …")."""
    m = re.search(r"^#+ .*(hướng dàn ý|outline).*$", md, re.I | re.M)
    if not m:
        return []
    block = md[m.end():]
    nxt = re.search(r"^#+ ", block, re.M)
    block = block[:nxt.start()] if nxt else block
    opts = []
    for item in re.split(r"^\d+\.\s+", block, flags=re.M)[1:]:
        lines = [x.strip() for x in item.strip().splitlines() if x.strip()]
        if not lines:
            continue
        head = lines[0]
        name = re.search(r"\*\*(.+?)\*\*", head)
        title = re.sub(r"\s*\(`?[\w-]+`?\)\s*", " ", name.group(1)).strip(" .,") if name else head[:60]
        title = re.sub(r",?\s*(ĐÃ CHỌN|chosen)\.?", "", title, flags=re.I).strip(" .,")
        chosen = bool(re.search(r"đã chọn|chosen", head, re.I))
        idea = re.sub(r"\*\*.+?\*\*[\s,.:]*(ĐÃ CHỌN[.,:]?)?\s*", "", head, count=1, flags=re.I).strip()
        why = " ".join(re.sub(r"^[-*]\s*", "", x) for x in lines[1:])
        opts.append({"name": title, "idea": idea, "chosen": chosen, "why": why})
    return opts


# Why a beat of each role is there and how it is usually carried out (rulebook 2.1, 4.11.1). Used only when
# blueprint.json has no tree for the beat: Claude's own reasons are always better than this generic reading.
ROLE_WHY = {
    "hook": ("Giữ người xem ở những giây đầu: đưa điều lạ, đắt nhất ra trước, chưa giải thích.",
             "Vào thẳng câu nói hoặc hình mạnh nhất, dừng trước câu trả lời; câu cuối nhắc lại lời hứa của tựa."),
    "title": ("Khép phần mở, chốt lời hứa của phim trước khi bắt đầu đi tìm câu trả lời.", "Tựa phim trên hình nền, không lời dẫn."),
    "mask": ("Dựng hình ảnh công khai của nhân vật trước, để chỗ lật sau đó có sức nặng.", "Ảnh thật kèm một con số uy tín."),
    "question": ("Đặt câu hỏi mà ai cũng nên hỏi, để người xem tự đi tìm câu trả lời cùng phim.",
                 "Một câu hỏi ngắn, ngay trước clip hoặc tài liệu trả lời nó."),
    "slip": ("Để chính nhân vật nói ra chỗ hở: người xem tự thấy, phim không phải cáo buộc.",
             "Clip nguyên văn, dẫn vào bằng một câu kiểu 'But listen to how he responds'."),
    "decode": ("Dịch lại điều vừa nghe thành một câu khô và rõ, để không ai hiểu sai.", "Một câu ngắn sau clip, kèm dòng tài liệu được highlight."),
    "name": ("Gọi tên hiện tượng để người xem có một khái niệm mang về.", "Một thuật ngữ có nguồn kiểm chứng được."),
    "evidence": ("Đặt tài liệu bên ngoài làm chứng, để lời dẫn không chỉ là ý kiến.", "Trang tài liệu hoặc ảnh thật, highlight đúng chữ lúc được đọc."),
    "reaction": ("Cho thấy người trong cuộc phản ứng thế nào, để câu chuyện có người thật.", "Clip phản ứng có thật, không dựng."),
    "link": ("Mắt xích của đường hang thỏ: một người có tên nối đầu này với đầu kia, kéo người xem lùi thêm một nấc.",
             "Giới thiệu người mới bằng ảnh thật và tài liệu nói rõ họ nối với ai."),
    "loop": ("Khép một vòng về nhân vật mở đầu, để người xem không lạc giữa các mắt xích.", "Câu nối quay về clip hoặc nhân vật đầu phim."),
    "close": ("Khép một mạch, chốt điều đã chứng minh trước khi sang mạch sau.", "Câu tổng kết ngắn trên hình đã quen."),
    "confession": ("Để nhân vật tự nói ra điều quan trọng nhất: mạnh hơn mọi lời dẫn.", "Clip dài, ít cắt."),
    "outro": ("Kết phim: để lại điều đọng lại hoặc câu hỏi còn mở.", "Câu khép, hình chậm, nhạc lắng."),
}
TYPE_WHY = {
    "cold_open": ROLE_WHY["hook"], "quote": ("Để nguồn tự nói bằng lời nguyên văn.", "Clip hoặc trích dẫn nguyên văn có ghi nguồn."),
    "narration": ("Lời dẫn đưa câu chuyện tiến lên một bước.", "Lời dẫn trên hình minh hoạ đúng danh từ đang được đọc."),
    "title": ROLE_WHY["title"], "outro": ROLE_WHY["outro"],
    "reconstruction": ("Tái hiện điều không có ảnh thật, để người xem hình dung được.", "Cảnh vẽ AI có nhãn tái hiện."),
    "archival": ("Cho thấy tư liệu thật của thời đó.", "Ảnh hoặc phim tư liệu cũ."),
}


def _sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?…])\s+(?=[A-Z“\"'(0-9])", (text or "").strip())
    return [x.strip() for x in parts if len(x.strip()) > 1]


def _tree(script: dict, bp: dict, acts: list[dict], plan: list[dict], claims: list[dict]) -> dict:
    """Thesis -> acts -> beats -> ideas, each with why / how (from blueprint.json "tree", else read from the roles)."""
    t = _d(bp.get("tree"))
    t_acts, t_beats = _d(t.get("acts")), _d(t.get("beats"))
    raw = {_d(b).get("id"): _d(b) for b in _list(script.get("beats"))}
    ev = {e["id"]: e for e in plan}
    order = [b["id"] for a in acts for b in a["beats"]]
    out_acts = []
    for a in acts:
        ta = _d(t_acts.get(a["id"]))
        beats = []
        for b in a["beats"]:
            tb, rb = _d(t_beats.get(b["id"])), raw.get(b["id"], {})
            gen = ROLE_WHY.get(b["role"]) or TYPE_WHY.get(b["type"]) or ("", "")
            q = _d(rb.get("quote"))
            narr = rb.get("narration") or ""
            lead = ""
            for sent in _sentences(narr):  # the opening sentences, enough to carry the beat's idea (~80+ chars)
                lead = f"{lead} {sent}".strip()
                if len(lead) >= 80:
                    break
            point = (tb.get("point") or lead or (f"“{q.get('text')}”" if q.get("text") else "")
                     or rb.get("on_screen_text") or "")
            ideas = _strs(tb.get("ideas")) or _sentences(narr) or ([q.get("text")] if q.get("text") else [])
            how_gen = gen[1] + (f" Hình: {rb['visual_idea']}" if rb.get("visual_idea") else "")
            srcs = set(_strs(rb.get("sources")))
            k = order.index(b["id"])
            beats.append({
                "id": b["id"], "type": b["type"], "role": b["role"], "sec": b["sec"], "visuals": b["visuals"],
                "point": point, "why": tb.get("why") or gen[0], "how": tb.get("how") or how_gen.strip(),
                "own": bool(tb.get("why") or tb.get("how")), "ideas": ideas,
                "narration": narr, "quote": {"text": q.get("text"), "speaker": q.get("speaker")} if q.get("text") else None,
                "on_screen_text": rb.get("on_screen_text") or "", "visual_idea": rb.get("visual_idea") or "",
                "evidence": [{"id": e, "what": ev.get(e, {}).get("what") or "", "proves": ev.get(e, {}).get("proves") or ""}
                             for e in _strs(rb.get("evidence"))],
                "claims": [{"id": c.get("id"), "text": c.get("text"), "status": c.get("status") or "unverified"}
                           for c in claims if srcs & set(_strs(c.get("sources")))],
                "prev": order[k - 1] if k else None, "next": order[k + 1] if k + 1 < len(order) else None,
            })
        how = ta.get("how") or ""
        if not how and beats:
            how = f"{len(beats)} beat theo nhịp " + " → ".join(dict.fromkeys(b["role"] or b["type"] for b in beats))
        out_acts.append({"id": a["id"], "title": a["title"], "sec": a["sec"], "start": a["start"],
                         "point": a.get("question") or a.get("purpose") or a.get("summary") or "",
                         "why": ta.get("why") or a.get("purpose") or a.get("summary") or "", "how": how,
                         "own": bool(ta.get("why") or ta.get("how")),
                         "question": a.get("question") or "", "turn": a.get("turn") or "", "bridge": a.get("bridge") or "",
                         "beats": beats})
    return {"acts": out_acts, "own_beats": sum(1 for a in out_acts for b in a["beats"] if b["own"]),
            "n_beats": sum(len(a["beats"]) for a in out_acts)}


def build(d: Path, p: dict) -> dict:
    script = _d(read_json(d / "1_script" / "script.json"))
    bp = _d(read_json(d / "1_script" / "blueprint.json"))
    srcs = _d(read_json(d / "1_script" / "sources.json"))
    cast = _d(read_json(d / "2_cast" / "cast.json"))
    research = ""
    try:
        research = (d / "1_script" / "research.md").read_text(encoding="utf-8")
    except OSError:
        pass

    beats = [_d(b) for b in _list(script.get("beats")) if isinstance(b, dict)]
    plan = [_d(e) for e in _list(script.get("evidence_plan")) if isinstance(e, dict) and _d(e).get("id")]
    ev_type = {e["id"]: e.get("type") for e in plan}
    cast_by = {_d(c).get("id"): _d(c) for c in _list(cast.get("characters"))}
    bp_acts = {_d(a).get("id"): _d(a) for a in _list(bp.get("acts"))}

    # ---- acts, from the script, with the blueprint's intent laid over
    acts = []
    t = 0.0
    script_acts = [_d(a) for a in _list(script.get("acts")) if isinstance(a, dict)]
    if not script_acts and bp_acts:
        script_acts = [{"id": k, "title": v.get("title") or k} for k, v in bp_acts.items()]
    for a in script_acts:
        aid = a.get("id")
        ba = bp_acts.get(aid, {})
        mine = [b for b in beats if b.get("act") == aid]
        sec = sum(_num(b.get("duration_sec")) for b in mine) or _num(ba.get("est_sec"))
        vis_sec: dict[str, float] = {}
        brows = []
        for b in mine:
            vs = _beat_visuals(b, ev_type)
            for v in vs:
                vis_sec[v] = vis_sec.get(v, 0) + _num(b.get("duration_sec")) / len(vs)
            q = _d(b.get("quote"))
            brows.append({"id": b.get("id"), "type": b.get("type") or "", "role": b.get("role") or "", "sec": _num(b.get("duration_sec")),
                          "text": b.get("narration") or (f"“{q.get('text')}” — {q.get('speaker') or ''}" if q.get("text") else "") or b.get("visual_idea") or "",
                          "visuals": vs})
        for v in _strs(ba.get("visuals")):
            vis_sec.setdefault(v, 0)
        chars = list(dict.fromkeys(_strs(ba.get("characters")) + [c for b in mine for c in _strs(b.get("characters"))]))
        evid = list(dict.fromkeys(_strs(ba.get("evidence")) + [e for b in mine for e in _strs(b.get("evidence"))]))
        roles = list(dict.fromkeys(b["role"] for b in brows if b["role"]))
        acts.append({
            "id": aid, "title": a.get("title") or ba.get("title") or aid, "summary": a.get("summary") or "",
            "purpose": ba.get("purpose") or a.get("summary") or "", "question": ba.get("question") or "", "turn": ba.get("turn") or "",
            "bridge": ba.get("bridge") or "", "notes": ba.get("notes") or "",
            "start": round(t, 1), "sec": round(sec, 1),
            "visuals": sorted(({"kind": k, "sec": round(v, 1)} for k, v in vis_sec.items()), key=lambda x: -x["sec"]),
            "roles": roles, "beats": brows, "characters": chars, "locations": _strs(ba.get("locations")), "evidence": evid,
        })
        t += sec
    total = t or _num(script.get("est_sec"))

    # ---- whole-film picture mix
    mix: dict[str, float] = {}
    for a in acts:
        for v in a["visuals"]:
            mix[v["kind"]] = mix.get(v["kind"], 0) + v["sec"]

    # ---- assets the plan needs
    bp_assets = _d(bp.get("assets"))
    bp_chars = {_d(c).get("id"): _d(c) for c in _list(bp_assets.get("characters"))}
    char_ids = list(dict.fromkeys(list(bp_chars) + [c for a in acts for c in a["characters"]]))
    how_of = {"archival_photo": "real_photo", "real_photo": "real_photo", "photo": "real_photo", "clip": "clip",
              "none": "voice_only", "voice": "voice_only", "ai": "ai", "ai_generated": "ai", "silhouette": "ai"}
    characters = []
    for cid in char_ids:
        if not cid:
            continue
        bc, cc = bp_chars.get(cid, {}), cast_by.get(cid, {})
        how = bc.get("how") or how_of.get(str(cc.get("depiction") or "").lower(), "") or ("voice_only" if cid == "c_narrator" else "")
        characters.append({"id": cid, "name": bc.get("name") or cc.get("name") or cid.removeprefix("c_").replace("_", " ").title(),
                           "role": bc.get("role") or cc.get("role") or "", "how": how,
                           "acts": [a["id"] for a in acts if cid in a["characters"]],
                           "beats": sum(1 for b in beats if cid in _strs(b.get("characters")))})
    locations = []
    for lo in _list(bp_assets.get("locations")):
        lo = _d(lo)
        if lo.get("id"):
            locations.append({"id": lo["id"], "name": lo.get("name") or lo["id"], "how": lo.get("how") or "",
                              "acts": [a["id"] for a in acts if lo["id"] in a["locations"]]})
    evidence = [{"id": e["id"], "type": e.get("type") or "", "what": e.get("what") or "", "proves": e.get("proves") or "",
                 "source": e.get("source") or "", "license": e.get("license") or "",
                 "visual": EVIDENCE_VISUAL.get(str(e.get("type") or "").lower(), ""),
                 "acts": [a["id"] for a in acts if e["id"] in a["evidence"]]} for e in plan]

    # ---- plan of the next steps (the blueprint's words, else counts from the script)
    fl = flow(p)
    steps_state = _d(p.get("steps"))
    bp_build = {_d(x).get("step"): _d(x) for x in _list(bp.get("build"))}
    n_real = sum(1 for c in characters if c["how"] in ("real_photo", "clip"))
    n_ai = sum(1 for c in characters if c["how"] == "ai")
    n_clip = sum(1 for b in beats if b.get("type") == "quote")
    n_recon = sum(1 for e in evidence if e["type"] == "reconstruction") or sum(1 for a in acts for b in a["beats"] if "reconstruction" in b["visuals"])
    voice = _d(script.get("voice"))
    derived_will = {
        "cast": (f"{len(characters)} nhân vật: {n_real} dùng ảnh/clip thật, {n_ai} vẽ AI, còn lại chỉ giọng hoặc chưa rõ", len(characters)),
        "scenes": (f"chia {len(beats)} beat thành các cảnh, mỗi cảnh một kiểu hình; lập danh sách bằng chứng cần tải", len(beats)),
        "images": (f"lấy {len(evidence)} bằng chứng thật (ảnh, trang tài liệu, logo, bản đồ)" + (f", vẽ {n_recon} cảnh tái hiện AI" if n_recon else ""), len(evidence)),
        "footage": (f"cắt {n_clip} clip trích dẫn, đọc lời dẫn" + (f" ({voice.get('chars')} ký tự, {voice.get('name')})" if voice.get("chars") else ""), n_clip),
        "render": (f"dựng phim ~{int(total // 60)}:{int(total % 60):02d}, soát âm lượng, phụ đề, khung hình", None),
        "metadata": ("tiêu đề, mô tả, chương, thumbnail để đăng YouTube", None),
    }
    build_rows = []
    for k in BUILD_STEPS:
        if k not in fl.by_key:
            continue
        st = fl.by_key[k]
        bb = bp_build.get(k, {})
        dw, dc = derived_will[k]
        usd = bb.get("usd")
        if usd is None and k == "footage" and voice.get("est_usd") is not None:
            usd = voice.get("est_usd")
        build_rows.append({"step": k, "num": st.num, "name": st.name, "icon": st.icon, "goal": st.text(p)["goal"],
                           "will": bb.get("will") or dw, "count": bb.get("count", dc), "usd": usd,
                           "status": steps_state.get(k) or ""})

    budget = _d(bp.get("budget")) or ({"voice_usd": voice.get("est_usd")} if voice.get("est_usd") is not None else {})
    budget = dict(budget)
    budget.setdefault("limit_usd", p.get("budget_usd"))

    claims = [_d(c) for c in _list(srcs.get("claims")) if isinstance(c, dict)]
    cc = {"verified": 0, "disputed": 0, "unverified": 0}
    for c in claims:
        cc[c.get("status") or "unverified"] = cc.get(c.get("status") or "unverified", 0) + 1

    return {
        "source": "file" if bp else "derived",
        "title": script.get("title") or p.get("title"), "logline": script.get("logline") or "", "thesis": script.get("thesis") or "",
        "approach": bp.get("approach") or "", "spine": bp.get("spine") or script.get("logline") or "",
        "hook": bp.get("hook") or (acts[0]["beats"][0]["text"] if acts and acts[0]["beats"] else ""),
        "ending": bp.get("ending") or (acts[-1]["beats"][-1]["text"] if acts and acts[-1]["beats"] else ""),
        "frame": script.get("frame") or "", "pipeline": p.get("pipeline") or "", "style": script.get("style") or p.get("style") or "",
        "target_sec": _num(p.get("target_sec") or script.get("target_sec")), "est_sec": round(total, 1),
        "options": [_d(o) for o in _list(bp.get("options"))] or _options_from_research(research),
        "acts": acts, "mix": sorted(({"kind": k, "sec": round(v, 1)} for k, v in mix.items()), key=lambda x: -x["sec"]),
        "characters": characters, "locations": locations, "evidence": evidence,
        "build": build_rows, "budget": budget, "claims": cc, "sources": len(_list(srcs.get("sources"))),
        "open_decisions": _strs(bp.get("open_decisions")) or _strs(script.get("open_questions")),
        "risks": _strs(script.get("risks")), "script_status": steps_state.get("script") or "",
        "tree": _tree(script, bp, acts, plan, claims),
    }
