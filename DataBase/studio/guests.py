"""Guests grouped by what listeners come to hear them on (shared by every show): UFO, ancient history, religion, politics, MMA, ...

A guest is a person and can appear in several episodes; episodes link to guests by the name in `episodes.guest`
("A & B" counts as two guests). Every guest has one main group and up to two secondary groups. Claude picks them:
the selection run writes them into tags_<id>.json for its own guest, and the "Phân nhóm bằng Claude" button on the
Khách mời page classifies the guests that still have no group in one short call (no tools). A group the user sets
by hand (source 'manual') is never overwritten.

The groups serve a highlight channel (playlists, topic compilations, which episode to do next), so they follow the
guest's CLIPS, not the guest's job: Claude gets the Guest Card data plus every selected highlight (score, keyword,
theme, title) and the per-group spread of those highlights. A secondary group needs clips behind it; one that no
highlight of the guest touches (e.g. "creator" only because the guest is a YouTuber or a host) is dropped.
"""
from __future__ import annotations

import json
import logging
import re
import time
from collections import defaultdict
from typing import Optional

from . import config, db, podcasts
from .util import norm_key, now_iso

log = logging.getLogger("studio.guests")

# (slug, Vietnamese name, who belongs there), in page order: the guest types JRE keeps coming back to
DEFAULT_GROUPS = [
    ("ufo-uap", "UFO, UAP & người ngoài hành tinh",
     "người tố giác và nhà nghiên cứu UFO/UAP, nhân chứng, nhà báo chuyên UFO (Bob Lazar, David Grusch)"),
    ("ancient-history", "Lịch sử cổ đại & nền văn minh thất lạc",
     "kim tự tháp, cự thạch, đại hồng thủy, người khổng lồ/Nephilim, khảo cổ bị che giấu (Graham Hancock, Randall Carlson)"),
    ("religion", "Tôn giáo, Kinh Thánh & thần học",
     "học giả Kinh Thánh, nhà hộ giáo, người tranh luận về tôn giáo, thần học (Wes Huff)"),
    ("politics", "Chính trị, bình luận & truyền thông",
     "chính trị gia, nhà bình luận, nhà báo chính trị, culture war, tự do ngôn luận"),
    ("military-intel", "Quân đội, đặc nhiệm & tình báo",
     "lính đặc nhiệm/SEAL, cựu CIA/FBI, chiến tranh, an ninh quốc gia (Jocko Willink)"),
    ("mma-combat", "MMA, UFC & võ thuật", "võ sĩ, huấn luyện viên, bình luận viên UFC, boxing, BJJ"),
    ("comedy", "Diễn viên hài", "stand-up comedian, dù trong tập nói về chủ đề gì"),
    ("science-space", "Khoa học, vật lý & vũ trụ",
     "nhà vật lý, thiên văn học, NASA, nhà khoa học chính thống hoặc phản biện giới khoa học"),
    ("tech-ai", "Công nghệ, AI & tương lai", "kỹ sư, CEO công nghệ, người nghiên cứu hoặc cảnh báo về AI (Elon Musk)"),
    ("health-fitness", "Sức khỏe, dinh dưỡng & thể hình",
     "bác sĩ, nhà nghiên cứu y học, tuổi thọ, dinh dưỡng, huấn luyện viên thể hình (Peter Attia, Andrew Huberman)"),
    ("psychedelics-consciousness", "Psychedelics, ý thức & tâm linh",
     "nấm, DMT, ketamine, thiền, trải nghiệm cận tử, tâm linh (Hamilton Morris, Paul Stamets)"),
    ("paranormal-mystery", "Bí ẩn, siêu nhiên & mất tích",
     "Bigfoot và sinh vật huyền bí, hiện tượng siêu nhiên, mất tích bí ẩn (David Paulides - Missing 411)"),
    ("conspiracy-investigation", "Điều tra, âm mưu & tố giác",
     "nhà báo điều tra, người tố giác (ngoài UFO), hồ sơ mật, thuyết âm mưu"),
    ("hunting-outdoors", "Săn bắn, thiên nhiên & sinh tồn",
     "thợ săn, cung thủ, nhà sinh học hoang dã, kỹ năng sinh tồn (Cameron Hanes, Steven Rinella)"),
    ("psychology-philosophy", "Tâm lý, triết học & phát triển bản thân",
     "nhà tâm lý học, triết gia, tác giả self-improvement (Jordan Peterson)"),
    ("entertainment", "Điện ảnh, âm nhạc & người nổi tiếng", "diễn viên, nhạc sĩ, ngôi sao giải trí"),
    ("business-creators", "Kinh doanh, doanh nhân & creator", "doanh nhân, nhà đầu tư, YouTuber, podcaster"),
    ("sports", "Thể thao (ngoài MMA)", "vận động viên bóng rổ, bóng bầu dục, đua xe, thể thao mạo hiểm"),
    ("crime-prison", "Tội phạm, nhà tù & đời thực khắc nghiệt", "cựu tù, băng đảng, true crime, người sống sót"),
    ("other", "Khác", "không hợp nhóm nào ở trên"),
]

# segment theme (tagged per highlight by the selection run) -> guest group(s) it is evidence for
THEME_TO_GROUPS = {
    "ufo-uap": ("ufo-uap",), "ancient-civilizations": ("ancient-history",), "giants-nephilim": ("ancient-history",),
    "religion-theology": ("religion",), "politics-culture-war": ("politics",), "slavery-human-rights": ("politics",),
    "history-war": ("military-intel",), "government-coverup": ("conspiracy-investigation",),
    "combat-sports": ("mma-combat",), "comedy-stories": ("comedy",), "physics-cosmology": ("science-space",),
    "ai-tech-risk": ("tech-ai",), "health-longevity": ("health-fitness",),
    "consciousness-psychedelics": ("psychedelics-consciousness",), "cryptids-paranormal": ("paranormal-mystery",),
    "true-crime-mystery": ("paranormal-mystery", "crime-prison"), "wildlife-nature": ("hunting-outdoors",),
    "psychology-self-improvement": ("psychology-philosophy",), "celebrity-hollywood": ("entertainment",),
    "business-money": ("business-creators",),
}
_RE_SPLIT = re.compile(r"\s+(?:&|and|\+|và)\s+", re.I)
_seeded: set[str] = set()                             # databases already given the default groups in this process


def ensure_default_groups() -> None:
    if str(config.DB_PATH) in _seeded:
        return
    with db.tx() as c:
        for i, (slug, name, hint) in enumerate(DEFAULT_GROUPS):
            c.execute("INSERT OR IGNORE INTO guest_groups(slug, name_vi, hint, sort) VALUES(?,?,?,?)", (slug, name, hint, i))
    _seeded.add(str(config.DB_PATH))


def guest_names(text: Optional[str]) -> list[str]:
    """'Tom Segura & Bert Kreischer' -> two guests."""
    return [n.strip() for n in _RE_SPLIT.split(text or "") if n.strip()]


def _list(raw) -> list[str]:
    try:
        v = json.loads(raw) if raw else []
    except ValueError:
        return []
    return [str(x) for x in v] if isinstance(v, list) else []


def sync_guests() -> int:
    """One row per person named in episodes.guest; returns how many were new."""
    ensure_default_groups()
    added = 0
    with db.tx() as c:
        for e in c.execute("SELECT guest FROM episodes WHERE guest IS NOT NULL AND guest!=''").fetchall():
            for name in guest_names(e["guest"]):
                key = norm_key(name)
                if not c.execute("SELECT 1 FROM guests WHERE name_norm=?", (key,)).fetchone():
                    c.execute("INSERT INTO guests(name, name_norm, updated_at) VALUES(?,?,?)", (name, key, now_iso()))
                    added += 1
    return added


def episodes_by_guest() -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = defaultdict(list)
    for e in db.rows("""SELECT e.id, e.guest, e.stage, e.guest_profile_json, e.guest_card_md,
                          (SELECT COUNT(*) FROM segments s WHERE s.episode_id=e.id AND s.kind='highlight'
                           AND s.status!='archived') AS highlights,
                          (SELECT COUNT(*) FROM segments s WHERE s.episode_id=e.id AND s.kind='highlight'
                           AND s.clip_zoomed_path IS NOT NULL AND s.status!='archived') AS zoomed
                        FROM episodes e ORDER BY e.podcast_id, e.number DESC"""):
        for name in guest_names(e["guest"]):
            out[norm_key(name)].append(e)
    return out


def groups() -> list[dict]:
    ensure_default_groups()
    return db.rows("SELECT * FROM guest_groups ORDER BY sort, slug")


def short_name(name_vi: str) -> str:
    """'Khoa học, vật lý & vũ trụ' -> 'Khoa học' for compact lists."""
    return re.split(r"[,&(]", name_vi or "")[0].strip() or name_vi


def highlights_by_episode() -> dict[str, list[dict]]:
    """Selected highlights with their themes (primary first), strongest first."""
    out: dict[str, list[dict]] = defaultdict(list)
    for r in db.rows("""SELECT s.id, s.episode_id, s.title, s.core_keyword, s.final_score,
                          (SELECT group_concat(slug) FROM (SELECT th.slug AS slug FROM segment_themes st
                             JOIN themes th ON th.id=st.theme_id WHERE st.segment_id=s.id
                             ORDER BY st.is_primary DESC, th.slug)) AS themes
                        FROM segments s WHERE s.kind='highlight' AND s.status!='archived'
                        ORDER BY s.episode_id, COALESCE(s.final_score, 0) DESC"""):
        r["themes"] = [t for t in (r["themes"] or "").split(",") if t]
        out[r["episode_id"]].append(r)
    return out


def clip_spread(clips: list[dict]) -> list[dict]:
    """Guest groups the highlights fall into by their primary theme: [{slug, n, score}], strongest first."""
    agg: dict[str, list[float]] = {}
    for c in clips:
        grp = THEME_TO_GROUPS.get(c["themes"][0], (None,))[0] if c["themes"] else None
        if grp:
            n, score = agg.get(grp, [0, 0.0])
            agg[grp] = [n + 1, score + (c["final_score"] or 0)]
    return sorted(({"slug": g, "n": v[0], "score": round(v[1], 1)} for g, v in agg.items()),
                  key=lambda x: (-x["score"], -x["n"]))


def clip_evidence(clips: list[dict]) -> Optional[set[str]]:
    """Every group any theme of the guest's highlights points to; None when no highlight is tagged yet."""
    tagged = [c for c in clips if c["themes"]]
    if not tagged:
        return None
    return {g for c in tagged for t in c["themes"] for g in THEME_TO_GROUPS.get(t, ())}


def overview() -> dict:
    """Groups with their guests (main members first, then guests that have it as a secondary group)."""
    sync_guests()
    eps = episodes_by_guest()
    clips = highlights_by_episode()
    grps = groups()
    short = {g["slug"]: short_name(g["name_vi"]) for g in grps}
    by_group = {g["slug"]: {"group": g, "main": [], "also": []} for g in grps}
    guests, unassigned = [], []
    for g in db.rows("SELECT * FROM guests"):
        g["episodes"] = eps.get(g["name_norm"], [])
        if not g["episodes"]:
            continue                                      # every episode of this guest was removed
        g["also"] = [s for s in _list(g["also_json"]) if s in by_group and s != g["group_slug"]]
        g["highlights"] = sum(e["highlights"] for e in g["episodes"])
        g["zoomed"] = sum(e["zoomed"] for e in g["episodes"])
        g["spread"] = [dict(x, name=short.get(x["slug"], x["slug"]))
                       for x in clip_spread([c for e in g["episodes"] for c in clips.get(e["id"], [])])]
        guests.append(g)
    guests.sort(key=lambda g: (-g["highlights"], g["name"].lower()))
    for g in guests:
        if g["group_slug"] in by_group:
            by_group[g["group_slug"]]["main"].append(g)
        else:
            unassigned.append(g)
        for s in g["also"]:
            by_group[s]["also"].append(g)
    return {"groups": list(by_group.values()), "unassigned": unassigned, "guests": guests,
            "names": {g["slug"]: g["name_vi"] for g in grps}}


def set_guest(guest_id: int, group: Optional[str], also: Optional[list] = None, expertise: Optional[str] = None,
              source: str = "manual") -> None:
    known = {g["slug"] for g in groups()}
    if group and group not in known:
        raise ValueError(f"không có nhóm {group}")
    also = [s for s in dict.fromkeys(also or []) if s in known and s != group][:2]
    with db.tx() as c:
        c.execute("UPDATE guests SET group_slug=?, also_json=?, expertise=COALESCE(?, expertise), source=?, updated_at=? "
                  "WHERE id=?", (group or None, json.dumps(also) if also else None, expertise or None, source,
                                 now_iso(), guest_id))


def apply(items: list[dict], episode_id: Optional[str] = None) -> dict:
    """Store Claude's grouping ([{id?|name, group, also, expertise}]); hand-picked groups stay as they are.

    A secondary group that none of the guest's tagged highlights points to is dropped: a group needs clips behind it
    (being a YouTuber, a host or an investor makes no clip).
    """
    known = {g["slug"] for g in groups()}
    stats = {"updated": 0, "kept_manual": 0, "unmatched": [], "dropped_also": []}
    eps, clips = episodes_by_guest(), highlights_by_episode()
    ep_guests = []
    if episode_id:
        ep = db.row("SELECT guest FROM episodes WHERE id=?", (episode_id,))
        ep_guests = guest_names(ep["guest"]) if ep else []
    for it in items or []:
        if not isinstance(it, dict):
            continue
        row = db.row("SELECT * FROM guests WHERE id=?", (int(it["id"]),)) if str(it.get("id", "")).isdigit() else None
        if row is None and it.get("name"):
            row = db.row("SELECT * FROM guests WHERE name_norm=?", (norm_key(str(it["name"])),))
        if row is None and len(ep_guests) == 1:           # the selection run may spell the name differently
            row = db.row("SELECT * FROM guests WHERE name_norm=?", (norm_key(ep_guests[0]),))
        if row is None:
            stats["unmatched"].append(it.get("name") or it.get("id"))
            continue
        if row["source"] == "manual":
            stats["kept_manual"] += 1
            continue
        group = it.get("group") if it.get("group") in known else "other"
        also = it.get("also") if isinstance(it.get("also"), list) else []
        evidence = clip_evidence([c for e in eps.get(row["name_norm"], []) for c in clips.get(e["id"], [])])
        if evidence is not None:
            dropped = [s for s in also if s not in evidence]
            also = [s for s in also if s in evidence]
            stats["dropped_also"] += [f"{row['name']}: {s}" for s in dropped]
        set_guest(row["id"], group, also, str(it.get("expertise") or "").strip()[:200] or None, source="claude")
        stats["updated"] += 1
    return stats


def import_from_tags(episode_id: str, data) -> Optional[dict]:
    """`guests` written by the selection run next to the themes/entities of its highlights."""
    items = data.get("guests") if isinstance(data, dict) else None
    if not items:
        return None
    sync_guests()
    return apply(items, episode_id=episode_id)


def prompt_group_lines() -> list[str]:
    return [f"  - {g['slug']}: {g['name_vi']} ({g['hint']})" for g in groups()]


def _guest_info(g: dict, eps: list[dict], clips: dict[str, list[dict]]) -> str:
    parts = []
    for e in eps[:2]:
        try:
            p = json.loads(e.get("guest_profile_json") or "{}") or {}
        except ValueError:
            p = {}
        bits = [p.get("identity"),
                "archetype: " + ", ".join(p.get("archetypes") or []) if p.get("archetypes") else None,
                "chuyên môn: " + "; ".join((p.get("expertise_tier1") or [])[:3]) if p.get("expertise_tier1") else None,
                "khán giả muốn nghe: " + "; ".join((p.get("audience_wants") or [])[:3]) if p.get("audience_wants") else None]
        bits = [str(b) for b in bits if b]
        if bits:
            parts.append("Guest Card: " + " | ".join(bits))
        elif e.get("guest_card_md"):
            parts.append("Guest Card: " + re.sub(r"\s+", " ", e["guest_card_md"])[:600])
    mine = sorted((c for e in eps for c in clips.get(e["id"], [])), key=lambda c: -(c["final_score"] or 0))
    if mine:
        spread = clip_spread(mine)
        parts.append(f"Clip đã chọn: {len(mine)} highlight" + (
            "; theo theme chính: " + ", ".join(f"{x['slug']} {x['n']} clip (tổng điểm {x['score']})" for x in spread)
            if spread else "; chưa gắn theme, đọc title/keyword"))
        parts += [f"- {c['final_score'] if c['final_score'] is not None else '?'} · {c['themes'][0] if c['themes'] else '-'} · "
                  f"\"{c['core_keyword'] or ''}\" · {c['title']}" for c in mine[:12]]
    else:
        parts.append("Chưa có clip nào được chọn: dựa vào Guest Card.")
    head = f"[id={g['id']}] {g['name']} (tập {', '.join(e['id'] for e in eps)})"
    return head + "\n   " + ("\n   ".join(parts) if parts else "(chưa có hồ sơ; dựa vào hiểu biết của bạn về người này)")


# The same principles go into the selection prompt (select_ai.build_prompt), where Claude has just picked the clips.
GROUPING_RULES = [
    "Nhóm chính `group` = nhóm chứa nhiều clip mạnh nhất của khách (tổng điểm cuối cao nhất), tức là thứ người xem bấm "
    "vào clip của khách để nghe; đối chiếu với \"khán giả muốn nghe\" của Guest Card, và đọc title/keyword để sửa chỗ theme "
    "gắn chưa chuẩn. Không xếp theo nghề, bằng cấp hay danh tiếng chung chung.",
    "Ngoại lệ persona: diễn viên hài luôn có nhóm chính comedy, võ sĩ và HLV luôn là mma-combat (người xem bấm vì chính con "
    "người họ); chủ đề clip của họ thành nhóm phụ.",
    "Nhóm phụ `also` (0–2) chỉ khi khách có ít nhất 2 clip thật sự thuộc nhóm đó. KHÔNG BAO GIỜ thêm nhóm chỉ vì nghề, "
    "nền tảng hay chức danh (YouTuber, podcaster, host, nhà đầu tư, tác giả sách, giáo sư…): những thứ đó không sinh ra clip.",
    "`expertise` = 1 câu tiếng Việt, tối đa 18 từ, viết như mô tả playlist: clip của khách cho người xem nghe gì (sự kiện, "
    "bằng chứng, câu chuyện cụ thể), kèm một danh xưng ngắn giúp title đáng tin (vd \"cựu nghiên cứu viên OpenAI\").",
]


def build_prompt(rows: list[dict], eps: dict[str, list[dict]]) -> str:
    clips = highlights_by_episode()
    return "\n".join([
        f"Bạn làm kênh highlight podcast ({podcasts.show_names()}). Xếp khách mời vào nhóm để dựng playlist và tập tổng hợp theo chủ đề, "
        "chọn tập nên làm tiếp, và biết clip của mỗi khách \"bán\" được chủ đề gì. Nhóm đi theo CLIP của khách, không theo "
        "nghề của khách.",
        "",
        "NHÓM (slug: tên (ai thuộc nhóm này)):",
        *prompt_group_lines(),
        "",
        "LUẬT:",
        *[f"{i}. {r}" for i, r in enumerate(GROUPING_RULES, 1)],
        f"{len(GROUPING_RULES) + 1}. Chỉ dùng slug trong danh sách. Trả về DUY NHẤT một khối ```json``` dạng "
        "[{\"id\": <id>, \"name\": \"...\", \"group\": \"...\", \"also\": [...], \"expertise\": \"...\"}] "
        "đủ mọi khách dưới đây, giữ nguyên id và tên. Không dùng công cụ.",
        "",
        "KHÁCH MỜI (Guest Card do skill chọn nội dung lập; mỗi clip: điểm cuối · theme chính · keyword hạt nhân · title):",
        *[_guest_info(g, eps.get(g["name_norm"], []), clips) for g in rows],
    ])


def _parse(text: str) -> list[dict]:
    m = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", text or "", re.S) or re.search(r"(\[\s*\{.*\}\s*\])", text or "", re.S)
    if not m:
        raise RuntimeError("Claude không trả về JSON phân nhóm")
    data = json.loads(m.group(1))
    return [d for d in data if isinstance(d, dict)]


def classify(only_missing: bool = True) -> dict:
    """One Claude call for the guests without a group (or every guest not grouped by hand)."""
    from .pipeline import claude_runner
    sync_guests()
    eps = episodes_by_guest()
    where = "group_slug IS NULL" if only_missing else "COALESCE(source, '')!='manual'"
    rows = [g for g in db.rows(f"SELECT * FROM guests WHERE {where} ORDER BY name") if eps.get(g["name_norm"])]
    if not rows:
        return {"updated": 0, "asked": 0, "message": "không còn khách nào cần phân nhóm"}
    (config.WORK_DIR / "guests").mkdir(parents=True, exist_ok=True)
    res = claude_runner.run(build_prompt(rows, eps), cwd=config.BASE_DIR, tools="", isolated=True, max_turns=2,
                            model=db.get_setting("claude_model_groups") or None,
                            effort=db.get_setting("claude_effort_groups") or None, timeout=900,
                            log_path=config.WORK_DIR / "guests" / f"classify_{int(time.time())}.jsonl")
    if not res.get("ok") and not res.get("text"):
        raise RuntimeError(res.get("error") or "Claude không trả lời")
    stats = apply(_parse(res.get("result") or res.get("text") or ""))
    stats.update(asked=len(rows), summary=claude_runner.describe_run(res))
    return stats


def episode_ids_for_group(slug: str) -> list[str]:
    """Episodes of every guest that has this group, main or secondary (search filter)."""
    eps = episodes_by_guest()
    ids: set[str] = set()
    for g in db.rows("SELECT name_norm, group_slug, also_json FROM guests"):
        if g["group_slug"] == slug or slug in _list(g["also_json"]):
            ids.update(e["id"] for e in eps.get(g["name_norm"], []))
    return sorted(ids)


def groups_for_episode(guest_text: Optional[str]) -> list[dict]:
    """Group pills for the episode page: main groups of its guests, then their secondary groups."""
    names = {g["slug"]: g["name_vi"] for g in groups()}
    out: list[dict] = []
    for name in guest_names(guest_text):
        g = db.row("SELECT * FROM guests WHERE name_norm=?", (norm_key(name),))
        if not g or g["group_slug"] not in names:
            continue
        out.append({"slug": g["group_slug"], "name": names[g["group_slug"]], "main": True, "guest": g["name"]})
        out += [{"slug": s, "name": names[s], "main": False, "guest": g["name"]} for s in _list(g["also_json"]) if s in names]
    return out
