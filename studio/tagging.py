"""Controlled taxonomy (themes) and entities, assigned by Claude through the /kho-highlight skill.

Flow: `hldb tag --pending` prints segments without themes plus the current theme list;
Claude answers with a JSON file; `hldb tag --apply file.json` writes it.
"""
from __future__ import annotations

from . import db
from .search import rebuild_index
from .util import now_iso, slugify

DEFAULT_THEMES = [
    ("ancient-civilizations", "Nền văn minh cổ đại, khảo cổ bị che giấu"),
    ("giants-nephilim", "Người khổng lồ, Nephilim, Sách Enoch"),
    ("ufo-uap", "UFO, UAP, phi thuyền, sinh vật ngoài hành tinh"),
    ("government-coverup", "Chính phủ che giấu, CIA, Pentagon, hồ sơ mật"),
    ("religion-theology", "Tôn giáo, thần học, Kinh Thánh"),
    ("consciousness-psychedelics", "Ý thức, DMT, psychedelics, trải nghiệm cận tử"),
    ("combat-sports", "MMA, boxing, kickboxing, võ thuật"),
    ("health-longevity", "Sức khỏe, tuổi thọ, dinh dưỡng, tập luyện"),
    ("ai-tech-risk", "AI, công nghệ, rủi ro tương lai"),
    ("physics-cosmology", "Vật lý, vũ trụ, thời gian, đa vũ trụ"),
    ("wildlife-nature", "Động vật hoang dã, thiên nhiên, sinh tồn"),
    ("comedy-stories", "Hài, chuyện hậu trường, câu chuyện cá nhân"),
    ("politics-culture-war", "Chính trị, culture war, truyền thông"),
    ("true-crime-mystery", "Tội phạm, mất tích, vụ án bí ẩn"),
    ("history-war", "Lịch sử, chiến tranh, quân sự"),
    ("slavery-human-rights", "Nô lệ, bóc lột, nhân quyền, chuỗi cung ứng"),
    ("business-money", "Kinh doanh, tiền, sự nghiệp"),
    ("celebrity-hollywood", "Người nổi tiếng, Hollywood, showbiz"),
]


def ensure_default_themes() -> None:
    with db.tx() as c:
        for slug, name in DEFAULT_THEMES:
            c.execute("INSERT OR IGNORE INTO themes(slug, name_vi) VALUES(?, ?)", (slug, name))


def pending(limit: int = 40, episode_id: str | None = None) -> dict:
    ensure_default_themes()
    where = "AND s.episode_id=?" if episode_id else ""
    params = (episode_id, limit) if episode_id else (limit,)
    segs = db.rows(
        f"""SELECT s.id, s.episode_id, e.guest, s.title, s.summary_en, s.core_keyword,
                   (SELECT group_concat(t.name, ' ; ') FROM segment_topics st JOIN topics t ON t.id=st.topic_id WHERE st.segment_id=s.id) AS topics
            FROM segments s JOIN episodes e ON e.id=s.episode_id
            WHERE s.kind='highlight' AND s.status!='archived' AND s.id NOT IN (SELECT segment_id FROM segment_themes) {where}
            ORDER BY s.episode_id, s.rank LIMIT ?""", params)
    themes = db.rows("SELECT slug, name_vi FROM themes ORDER BY slug")
    return {"themes": themes, "segments": segs,
            "instructions": "Trả về JSON {\"themes\":[{\"slug\",\"name_vi\"}] (chỉ theme MỚI nếu thật sự cần), "
                            "\"segments\":[{\"id\", \"themes\":[{\"slug\", \"primary\": true|false}], "
                            "\"entities\":[{\"name\", \"type\": person|place|org|work|event}]}]}"}


def apply_tags(data: dict) -> dict:
    ensure_default_themes()
    stats = {"themes_added": 0, "segments": 0, "entities": 0}
    touched = []
    with db.tx() as c:
        for th in data.get("themes", []) or []:
            slug = slugify(th.get("slug") or th.get("name_vi") or "")
            if not slug:
                continue
            before = c.execute("SELECT 1 FROM themes WHERE slug=?", (slug,)).fetchone()
            c.execute("INSERT OR IGNORE INTO themes(slug, name_vi) VALUES(?, ?)", (slug, th.get("name_vi")))
            if not before:
                stats["themes_added"] += 1
        for seg in data.get("segments", []) or []:
            sid = int(seg["id"])
            if not c.execute("SELECT 1 FROM segments WHERE id=?", (sid,)).fetchone():
                continue
            themes = seg.get("themes") or []
            if themes:
                c.execute("DELETE FROM segment_themes WHERE segment_id=?", (sid,))
                for th in themes:
                    slug = slugify(th.get("slug") or "")
                    c.execute("INSERT OR IGNORE INTO themes(slug, name_vi) VALUES(?, ?)", (slug, th.get("name_vi")))
                    tid = c.execute("SELECT id FROM themes WHERE slug=?", (slug,)).fetchone()[0]
                    c.execute("INSERT OR REPLACE INTO segment_themes(segment_id, theme_id, is_primary, confidence) VALUES(?,?,?,?)",
                              (sid, tid, 1 if th.get("primary") else 0, th.get("confidence")))
            ents = seg.get("entities") or []
            if ents:
                c.execute("DELETE FROM segment_entities WHERE segment_id=?", (sid,))
                for en in ents:
                    name, typ = (en.get("name") or "").strip(), (en.get("type") or "other").strip().lower()
                    if not name:
                        continue
                    c.execute("INSERT OR IGNORE INTO entities(name, type) VALUES(?, ?)", (name, typ))
                    eid = c.execute("SELECT id FROM entities WHERE name=? AND type=?", (name, typ)).fetchone()[0]
                    c.execute("INSERT OR IGNORE INTO segment_entities(segment_id, entity_id) VALUES(?, ?)", (sid, eid))
                    stats["entities"] += 1
            c.execute("UPDATE segments SET updated_at=? WHERE id=?", (now_iso(), sid))
            touched.append(sid)
            stats["segments"] += 1
    if touched:
        rebuild_index(touched)
    return stats
