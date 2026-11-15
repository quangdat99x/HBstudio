"""News desk: topics the app watches, their sources, the items fetched from them, and the poller thread that keeps
them fresh. Each topic is polled on its own interval, all of its sources at once; items that pass the topic's keyword
filter are stored, grouped into stories (the same event told by several outlets), and turned into a video project on
demand (the chosen items become the project's sources/ files).
"""
from __future__ import annotations

import json
import logging
import re
import threading
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta

from . import db, media, news_fetch as nf, store
from .util import now_iso, slugify

log = logging.getLogger("creater.news")

STATES = ("new", "seen", "starred", "hidden", "used")
# audience of a video made from news, by language of the video (other languages: the default of the Settings page)
AUDIENCES = {"ru": "Khán giả nói tiếng Nga (YouTube, Telegram, TikTok)", "uk": "Khán giả Ukraina", "vi": "Khán giả Việt Nam"}
FAIL_PAUSE = 5                  # a source failing this many times in a row is retried once an hour only

VIDEO_KINDS = {"single": "Tin nóng (một sự kiện)", "digest": "Điểm tin 24h (bản tin tổng hợp)"}
DIGEST_STORIES = 16             # events a digest starts from (the user adds or drops items before making the video)
DIGEST_TARGET_SEC = 900
# appended to the brief of a digest project; the formula itself lives in the news rulebook 2.9, where the user edits it
DIGEST_NOTE = ("KIỂU VIDEO: ĐIỂM TIN 24H — bản tin tổng hợp nhiều sự kiện trong một ngày, làm theo bộ quy tắc tin tức mục 2.9 "
               "(menu tiêu đề mở đầu, tin của tựa phát đầu tiên, tin của thumbnail trả ở 40–50% thời lượng, tin căng nhất "
               "gần cuối, một tin nhẹ trước lời tạm biệt; tuyên bố của một bên nói rõ bên nào; không nêu tên bất kỳ báo, "
               "hãng tin, kênh nào — mục 1.6; che logo báo/kênh trên ảnh — mục 1.10; không gây hiểu lầm, không spam — mục 1.9). Các sự kiện, xếp theo trọng tâm rồi số nguồn đưa tin, ở sources/digest.md: "
               "không bắt buộc dùng hết, được bỏ tin yếu hoặc trùng.")
DIGEST_FOCUS_NOTE = ("TRỌNG TÂM ĐIỂM TIN (người dùng yêu cầu): {focus}\nBẮT BUỘC: sự kiện đánh dấu ▶ TIN MỞ ĐẦU trong "
                     "sources/digest.md (sát trọng tâm nhất) là tin phát đầu tiên và là câu đầu của menu tiêu đề, hình đầu "
                     "tiên của cold open cũng lấy từ tin này; chỉ đổi tin khác nếu tin đó không kiểm chứng được, ghi lý do "
                     "vào research.md. Các sự kiện ★ khác xếp ngay sau trong menu, ưu tiên làm tựa và thumbnail, cho nhiều "
                     "thời lượng hơn; tin khác kể ngắn. Không có sự kiện ★ thì tự chọn tin sát câu trọng tâm nhất để mở đầu. "
                     "Phần trọng tâm không khớp sự kiện nào thì tìm trong sources/ trước, không bịa.")

# Russia–Ukraine outlets of both sides, independent and international (checked 2026-10-06):
# (kind, url / channel / query, name, side, filter by keywords)
_RU_UA_SOURCES = [
    ("telegram", "mod_russia", "Минобороны России", "ru", 0),
    ("telegram", "rybar", "Рыбарь", "ru", 1),
    ("telegram", "dva_majors", "Два майора", "ru", 1),
    ("telegram", "wargonzo", "WarGonzo", "ru", 1),
    ("rss", "https://tass.ru/rss/v2.xml", "ТАСС", "ru", 1),
    ("rss", "https://ria.ru/export/rss2/archive/index.xml", "РИА Новости", "ru", 1),
    ("rss", "https://www.interfax.ru/rss.asp", "Интерфакс", "ru", 1),
    ("rss", "https://rssexport.rbc.ru/rbcnews/news/30/full.rss", "РБК", "ru", 1),
    ("rss", "https://www.kommersant.ru/RSS/news.xml", "Коммерсантъ", "ru", 1),
    ("rss", "https://lenta.ru/rss/news", "Lenta.ru", "ru", 1),
    ("rss", "https://topwar.ru/rss.xml", "Военное обозрение", "ru", 1),
    ("telegram", "GeneralStaffZSU", "Генштаб ВСУ (укр.)", "ua", 0),
    ("telegram", "DeepStateUA", "DeepState (укр.)", "ua", 0),
    ("rss", "https://www.pravda.com.ua/rus/rss/view_news/", "Украинская правда", "ua", 1),
    ("rss", "https://rss.unian.net/site/news_rus.rss", "УНИАН", "ua", 1),
    ("telegram", "stranaua", "Страна.ua", "ua", 1),
    ("rss", "https://meduza.io/rss/all", "Meduza", "indep", 1),
    ("rss", "https://novayagazeta.eu/feed/rss", "Новая газета Европа", "indep", 1),
    ("rss", "https://feeds.bbci.co.uk/russian/rss.xml", "BBC Русская служба", "intl", 1),
    ("rss", "https://rss.dw.com/xml/rss-ru-all", "DW на русском", "intl", 1),
]
_RU_UA_WAR_TERMS = [
    "СВО", "ВСУ", "ЗСУ", "ВС РФ", "ВС России", "Минобороны", "Генштаб", "силы обороны", "фронт", "передов",
    "наступлен", "контрнаступлен", "освобожд", "освободил", "штурм", "окружен", "котел", "продвин",
    "группировка войск", "бригад", "беспилотн", "БПЛА", "дрон", "ПВО", "ракетн", "обстрел", "артиллер",
    "танк", "бронетехник", "Искандер", "HIMARS", "ATACMS", "Storm Shadow", "мобилизац", "военнопленн",
    "обмен пленн", "Донбасс", "ДНР", "ЛНР", "Донецк", "Луганск", "Запорож", "Херсон", "Харьков", "Сумск",
    "Сумы", "Сумах", "Сумщин", "Курск", "Белгород", "Брянск", "Днепропетровск", "Покровск", "Красноармейск",
    "Мирноград", "Димитров", "Константиновк", "Купянск", "Лиман", "Северск", "Часов Яр", "Торецк",
    "Гуляйпол", "Орехов", "Степногорск", "Волчанск", "Великая Новоселк", "Славянск", "Краматорск",
    "Дружковк", "Угледар", "Курахов", "Авдеевк", "Бахмут", "Артемовск"]
# a digest also tells the politics around the war: Kremlin, Kyiv, Washington, NATO and Europe, money, mobilization
_RU_UA_POLITICS_TERMS = [
    "Украин", "Киев", "Зеленск", "Сырск", "Буданов", "Путин", "Кремл", "Песков", "Лавров", "Захаров", "Ушаков",
    "Трамп", "Уиткофф", "Белый дом", "Пентагон", "НАТО", "Евросоюз", "ЕС", "Еврокомисс", "Брюссел", "Макрон",
    "Мерц", "Стармер", "Орбан", "Эрдоган", "переговор", "перемири", "мирный план", "мирного плана", "санкц",
    "теневой флот", "замороженн", "репарацион", "финансирован", "военная помощь", "военной помощи", "поставк",
    "Patriot", "Tomahawk", "Томагавк", "F-16", "ТЦК", "военком", "СБУ", "ГУР", "ФСБ", "теракт", "диверс", "Крым",
    "Севастопол", "НПЗ", "нефтебаз", "энергосистем", "ТЭЦ", "подстанц"]
_RU_UA_EXCLUDE = ["народный фронт", "ОНФ", "фронтмен", "фронтенд", "фронтальн", "хоккей", "футбол", "матч",
                  "турнир", "сериал"]
_RU_UA_BRIEF = ("Lời dẫn và chữ trên màn hình bằng tiếng Nga. Tuyên bố của một bên luôn nói rõ bên nào (Bộ Quốc phòng "
                "Nga, phía Ukraina, chính quyền địa phương…); không trình bày tuyên bố của một bên như sự thật đã kiểm "
                "chứng, có tin của cả hai bên thì đặt cạnh nhau. Không nêu tên bất kỳ báo, hãng tin, kênh nào (tên "
                "người, tổ chức như Путин, НАТО vẫn dùng — Bộ quy tắc mục 1.6); ảnh thật của báo phải che logo (mục 1.10). Địa danh viết theo tiếng Nga. Hình: bản đồ khu vực, footage đã "
                "duyệt; không dùng hình thương vong.")

PRESETS = {
    "ru-ua-digest": {
        "label": "Điểm tin 24h Nga–Ukraina (tiếng Nga, YouTube 16:9)",
        "topic": {
            "name": "Điểm tin 24h Nga–Ukraina", "language": "ru", "interval_min": 15, "format": "16:9",
            "target_sec": DIGEST_TARGET_SEC, "video_kind": "digest",
            "keywords": "\n".join(_RU_UA_WAR_TERMS + _RU_UA_POLITICS_TERMS),
            "exclude": "\n".join(_RU_UA_EXCLUDE),
            "brief": ("Bản tin tổng hợp 24 giờ về chiến sự Nga–Ukraina và chính trị quanh cuộc chiến (Kremlin, Kyiv, "
                      "Washington, NATO, châu Âu, viện trợ, trừng phạt, động viên). " + _RU_UA_BRIEF +
                      " Tên kênh đọc trong lời chào và lời tạm biệt: (chưa đặt — đề xuất một tên ngắn tiếng Nga, dùng "
                      "nhất quán mọi tập)."),
        },
        "sources": _RU_UA_SOURCES + [
            ("bing", "Украина новости", "Bing News: Украина новости", "", 1),
            ("gnews", "Украина Россия переговоры", "Google News: Украина Россия переговоры", "", 1),
        ],
    },
    "ru-ua-war": {
        "label": "Chiến sự Nga–Ukraina (tiếng Nga)",
        "topic": {
            "name": "Chiến sự Nga–Ukraina", "language": "ru", "interval_min": 10, "format": "9:16", "target_sec": 60,
            "keywords": "\n".join(_RU_UA_WAR_TERMS),
            "exclude": "\n".join(_RU_UA_EXCLUDE[:5] + ["танкер"] + _RU_UA_EXCLUDE[5:]),
            "brief": "Bản tin tình hình chiến trường Nga–Ukraina. " + _RU_UA_BRIEF,
        },
        "sources": _RU_UA_SOURCES + [
            ("bing", "ВСУ фронт", "Bing News: ВСУ фронт", "", 1),
            ("gnews", "линия фронта", "Google News: линия фронта", "", 1),
        ],
    },
}


# ---------------------------------------------------------------- helpers
def _int(v, default: int, lo: int | None = None, hi: int | None = None) -> int:
    try:
        n = int(float(v))
    except (TypeError, ValueError):
        return default
    if lo is not None:
        n = max(lo, n)
    if hi is not None:
        n = min(hi, n)
    return n


def _flag(v) -> int:
    return 1 if v in (True, 1, "1", "on", "true") else 0


def _update(table: str, row_id: int, fields: dict) -> None:
    if fields:
        with db.tx() as c:
            c.execute(f"UPDATE {table} SET {', '.join(k + '=?' for k in fields)} WHERE id=?", [*fields.values(), row_id])


# ---------------------------------------------------------------- topics
def clean_topic(data: dict) -> dict:
    out = {}
    if "name" in data and (data.get("name") or "").strip():
        out["name"] = data["name"].strip()[:120]
    for k in ("keywords", "exclude", "brief"):
        if k in data:
            out[k] = (data.get(k) or "").replace("\r\n", "\n").strip() or None
    if "language" in data:
        out["language"] = (data.get("language") or "ru").strip().lower()[:8] or "ru"
    if "interval_min" in data:
        out["interval_min"] = _int(data["interval_min"], 10, 2, 1440)
    if "target_sec" in data:
        out["target_sec"] = _int(data["target_sec"], 60, 10, 3600)
    if "format" in data:
        out["format"] = data["format"] if data["format"] in ("16:9", "9:16") else "9:16"
    if "video_kind" in data:
        out["video_kind"] = data["video_kind"] if data["video_kind"] in VIDEO_KINDS else "single"
    if "enabled" in data:
        out["enabled"] = _flag(data["enabled"])
    return out


def create_topic(data: dict) -> int:
    preset = PRESETS.get(data.get("preset") or "")
    fields = dict(preset["topic"]) if preset else {}
    fields.update({k: v for k, v in clean_topic(data).items() if v is not None})
    if not fields.get("name"):
        raise ValueError("cần đặt tên chủ đề")
    cols = ["name", "language", "keywords", "exclude", "interval_min", "enabled", "brief", "format", "target_sec",
            "video_kind"]
    defaults = {"language": "ru", "interval_min": 10, "enabled": 1, "format": "9:16", "target_sec": 60,
                "video_kind": "single"}
    vals = [fields.get(k, defaults.get(k)) for k in cols]
    with db.tx() as c:
        c.execute(f"INSERT INTO news_topics({', '.join(cols)}, created_at) VALUES({', '.join('?' * len(cols))}, ?)",
                  [*vals, now_iso()])
        tid = c.execute("SELECT last_insert_rowid()").fetchone()[0]
    for kind, url, name, side, flt in (preset or {}).get("sources", []):
        add_source(tid, {"kind": kind, "url": url, "name": name, "side": side, "filter": flt})
    return tid


def update_topic(tid: int, data: dict) -> None:
    fields = clean_topic(data)
    old = get_topic(tid) or {}
    _update("news_topics", tid, fields)
    if any(k in fields and fields[k] != old.get(k) for k in ("keywords", "exclude", "language")):
        with db.tx() as c:                  # feeds answer "not modified": forget it so the next poll re-reads them
            c.execute("UPDATE news_sources SET etag=NULL, modified=NULL WHERE topic_id=?", (tid,))


def delete_topic(tid: int) -> None:
    with db.tx() as c:
        c.execute("DELETE FROM news_topics WHERE id=?", (tid,))


def get_topic(tid: int) -> dict | None:
    return db.row("SELECT * FROM news_topics WHERE id=?", (tid,))


def list_topics() -> list[dict]:
    return db.rows("""SELECT t.*,
        (SELECT COUNT(*) FROM news_items i WHERE i.topic_id=t.id AND i.state='new') AS new_count,
        (SELECT COUNT(*) FROM news_items i WHERE i.topic_id=t.id AND i.state!='hidden') AS total,
        (SELECT MAX(id) FROM news_items i WHERE i.topic_id=t.id) AS last_item_id,
        (SELECT COUNT(*) FROM news_sources s WHERE s.topic_id=t.id AND s.enabled=1) AS source_count,
        (SELECT COUNT(*) FROM news_sources s WHERE s.topic_id=t.id AND s.enabled=1 AND s.last_error IS NOT NULL) AS source_errors
        FROM news_topics t ORDER BY t.id""")


def due_topics() -> list[dict]:
    now = datetime.now()
    out = []
    for t in db.rows("SELECT * FROM news_topics WHERE enabled=1"):
        last = t.get("last_polled_at")
        if not last or datetime.fromisoformat(last) <= now - timedelta(minutes=t.get("interval_min") or 10):
            out.append(t)
    return out


# ---------------------------------------------------------------- sources
def clean_source(data: dict) -> dict:
    out = {}
    if "kind" in data:
        if data["kind"] not in nf.KINDS:
            raise ValueError("loại nguồn không hợp lệ")
        out["kind"] = data["kind"]
    if "url" in data:
        url = (data.get("url") or "").strip()
        if not url:
            raise ValueError("thiếu địa chỉ / kênh / từ khóa")
        if out.get("kind") == "telegram":
            url = nf.channel_name(url)
        out["url"] = url[:1000]
    if "name" in data:
        out["name"] = (data.get("name") or "").strip()[:120] or None
    if "side" in data:
        out["side"] = data["side"] if data["side"] in nf.SIDES else ""
    for k in ("filter", "enabled"):
        if k in data:
            out[k] = _flag(data[k])
    return out


def add_source(tid: int, data: dict) -> int:
    f = clean_source({"filter": 1, "enabled": 1, "side": "", **data})
    if "kind" not in f or "url" not in f:
        raise ValueError("cần loại nguồn và địa chỉ")
    if db.row("SELECT id FROM news_sources WHERE topic_id=? AND kind=? AND url=?", (tid, f["kind"], f["url"])):
        raise ValueError("chủ đề đã có nguồn này")
    with db.tx() as c:
        c.execute("""INSERT INTO news_sources(topic_id, kind, url, name, side, filter, enabled, created_at)
                     VALUES(?,?,?,?,?,?,?,?)""",
                  (tid, f["kind"], f["url"], f.get("name"), f.get("side", ""), f["filter"], f["enabled"], now_iso()))
        return c.execute("SELECT last_insert_rowid()").fetchone()[0]


def update_source(sid: int, data: dict) -> None:
    src = get_source(sid)
    if not src:
        raise ValueError("không có nguồn này")
    f = clean_source({"kind": src["kind"], **data})
    f.pop("kind", None)
    if "url" in f and f["url"] != src["url"]:
        f.update(etag=None, modified=None, fail_count=0, last_error=None)
    if "enabled" in f and f["enabled"] and not src["enabled"]:
        f.update(fail_count=0)
    _update("news_sources", sid, f)


def delete_source(sid: int) -> None:
    with db.tx() as c:
        c.execute("DELETE FROM news_sources WHERE id=?", (sid,))


def get_source(sid: int) -> dict | None:
    return db.row("SELECT * FROM news_sources WHERE id=?", (sid,))


def sources(tid: int) -> list[dict]:
    lang = (get_topic(tid) or {}).get("language") or "ru"
    out = db.rows("SELECT * FROM news_sources WHERE topic_id=? ORDER BY id", (tid,))
    for s in out:
        s["fetch_url"] = nf.source_url(s["kind"], s["url"], lang)
    return out


def test_source(kind: str, value: str, language: str = "ru", keywords: str | None = None) -> dict:
    """Fetch a source once without storing anything: does it work, how many items, how many match the keywords."""
    if kind == "telegram":
        value = nf.channel_name(value)
    try:
        res = nf.fetch_source(kind, value, language)
    except nf.FetchError as e:
        return {"ok": False, "error": str(e), "url": nf.source_url(kind, value, language)}
    pat = nf.compile_terms(keywords)
    items = res["items"]
    hits = [it for it in items if nf.matches(pat, f"{it['title']}\n{it['summary']}\n{it['body'][:4000]}")] if pat else items
    dates = sorted((it["published_at"] for it in items if it["published_at"]), reverse=True)
    return {"ok": True, "title": res.get("title"), "count": len(items), "matched": len(hits), "latest": dates[0] if dates else None,
            "sample": [it["title"] for it in (hits or items)[:6]], "url": nf.source_url(kind, value, language)}


# ---------------------------------------------------------------- polling
class _Stories:
    """Headline fingerprints of a topic's recent items, to put a new item into the story of an earlier one."""

    def __init__(self, tid: int, hours: int = 36):
        since = (datetime.now() - timedelta(hours=hours)).replace(microsecond=0).isoformat()
        rows_ = db.rows("""SELECT id, story_id, title FROM news_items WHERE topic_id=? AND COALESCE(published_at, fetched_at) >= ?
                           ORDER BY id DESC LIMIT 3000""", (tid, since))
        self.recent = [(r["id"], r["story_id"] or r["id"], nf.fingerprint(r["title"])) for r in rows_]
        self.heads = {i: fp for i, sid, fp in self.recent if i == sid}

    def place(self, iid: int, title: str) -> int:
        """Story id of a new item: the story of the most similar recent item. The item must also resemble the story's
        first item, so a story cannot drift from one event to the next through a chain of half-similar headlines."""
        fp = nf.fingerprint(title)
        story, best = iid, 0.0
        for i, sid, other in self.recent:
            if not nf.similar(fp, other) or (i != sid and sid in self.heads and not nf.similar(fp, self.heads[sid])):
                continue
            score = nf.overlap(fp, other)
            if score > best:
                story, best = sid, score
        self.recent.insert(0, (iid, story, fp))
        if story == iid:
            self.heads[iid] = fp
        return story


def poll_topic(tid: int, force: bool = False) -> dict:
    """Fetch every enabled source of a topic, store the new items that pass the filter. Returns {new, errors, sources}."""
    t = get_topic(tid)
    if not t:
        return {"error": "không có chủ đề này"}
    now_dt = datetime.now().replace(microsecond=0)
    now = now_dt.isoformat()
    srcs = []
    for s in db.rows("SELECT * FROM news_sources WHERE topic_id=? AND enabled=1", (tid,)):
        resting = (s["fail_count"] or 0) >= FAIL_PAUSE and s["last_try_at"] and \
            datetime.fromisoformat(s["last_try_at"]) > now_dt - timedelta(hours=1)
        if force or not resting:
            srcs.append(s)
    include, exclude = nf.compile_terms(t["keywords"]), nf.compile_terms(t["exclude"])
    cutoff = (now_dt - timedelta(hours=db.setting_int("news_max_age_h") or 48)).isoformat()

    def job(s: dict):
        try:
            return s, nf.fetch_source(s["kind"], s["url"], t["language"] or "ru", s["etag"], s["modified"]), None
        except nf.FetchError as e:
            return s, None, str(e)
        except Exception as e:  # noqa: BLE001  (a broken source must not stop the others)
            log.exception("news source %s", s["id"])
            return s, None, f"lỗi đọc nguồn: {e}"[:300]

    with ThreadPoolExecutor(max_workers=max(1, min(8, len(srcs)))) as ex:
        results = list(ex.map(job, srcs))

    stories = _Stories(tid)
    new_total, errors = 0, []
    for s, res, err in results:
        if err:
            _update("news_sources", s["id"], {"last_error": err, "fail_count": (s["fail_count"] or 0) + 1, "last_try_at": now})
            errors.append(f"{s['name'] or s['url']}: {err}")
            continue
        kept = new = 0
        with db.tx() as c:
            for it in res["items"]:
                text = f"{it['title']}\n{it['summary']}\n{it['body'][:4000]}"
                if exclude and nf.matches(exclude, text):
                    continue
                hits = nf.matches(include, text)
                if s["filter"] and include and not hits:
                    continue
                if it["published_at"] and it["published_at"] < cutoff:
                    continue
                kept += 1
                extra = {k: it[k] for k in ("views", "video", "media", "forwarded_from") if it.get(k)}
                if not extra.get("media") and it.get("image"):
                    extra["media"] = [{"kind": "photo", "url": it["image"], "thumb": it["image"]}]
                cur = c.execute("""INSERT OR IGNORE INTO news_items(topic_id, source_id, uid, url, title, summary, body, image,
                                   source_name, extra, published_at, fetched_at, matched, score, state)
                                   VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?, 'new')""",
                                (tid, s["id"], it["uid"], it["url"], it["title"], it["summary"] or None, it["body"] or None,
                                 it["image"], it["source_name"], json.dumps(extra) if extra else None,
                                 it["published_at"] or now, now, ", ".join(hits) or None, len(hits)))
                if not cur.rowcount:
                    if extra.get("media"):                  # items stored before media were collected
                        c.execute("""UPDATE news_items SET extra=? WHERE topic_id=? AND uid=?
                                     AND (extra IS NULL OR extra NOT LIKE '%"media"%')""",
                                  (json.dumps(extra), tid, it["uid"]))
                    continue
                iid = cur.lastrowid
                c.execute("UPDATE news_items SET story_id=? WHERE id=?", (stories.place(iid, it["title"]), iid))
                new += 1
        fields = {"last_ok_at": now, "last_try_at": now, "last_error": None, "fail_count": 0,
                  "etag": res["etag"] or (s["etag"] if res["not_modified"] else None),
                  "modified": res["modified"] or (s["modified"] if res["not_modified"] else None)}
        if not res["not_modified"]:
            fields.update(last_count=kept, last_new=new)
        if not s["name"] and res.get("title"):
            fields["name"] = res["title"][:120]
        _update("news_sources", s["id"], fields)
        new_total += new
    _update("news_topics", tid, {"last_polled_at": now, "last_new": new_total})
    return {"new": new_total, "errors": errors, "sources": len(srcs)}


def purge() -> int:
    """Forget items older than news_keep_days, except the starred ones and those already made into a video."""
    days = db.setting_int("news_keep_days") or 14
    cutoff = (datetime.now() - timedelta(days=days)).replace(microsecond=0).isoformat()
    with db.tx() as c:
        return c.execute("DELETE FROM news_items WHERE state NOT IN ('starred','used') AND fetched_at < ?", (cutoff,)).rowcount


# ---------------------------------------------------------------- items
def _decorate(rows_: list[dict]) -> list[dict]:
    """Add the story size and the outlets of each item's story (the same event told by other sources)."""
    ids = sorted({r["story_id"] for r in rows_ if r.get("story_id")})
    stories: dict[int, dict] = {}
    for chunk in (ids[i:i + 500] for i in range(0, len(ids), 500)):
        for r in db.rows(f"""SELECT i.story_id, COUNT(*) AS n, GROUP_CONCAT(DISTINCT COALESCE(s.name, i.source_name)) AS outlets
                             FROM news_items i LEFT JOIN news_sources s ON s.id=i.source_id
                             WHERE i.story_id IN ({','.join('?' * len(chunk))}) AND i.state!='hidden'
                             GROUP BY i.story_id""", chunk):
            stories[r["story_id"]] = r
    for r in rows_:
        st = stories.get(r.get("story_id")) or {}
        r["story_size"] = st.get("n") or 1
        r["story_outlets"] = st.get("outlets") or ""
        r["source"] = r.get("source_name") if r.get("kind") in ("bing", "gnews") and r.get("source_name") else \
            (r.get("src_name") or r.get("source_name") or nf.host_name(r.get("url") or ""))
        r["has_body"] = _complete(r)
        try:
            r["extra"] = json.loads(r["extra"]) if r.get("extra") else {}
        except ValueError:
            r["extra"] = {}
        r["media"] = r["extra"].get("media") or ([{"kind": "photo", "url": r["image"], "thumb": r["image"]}]
                                                  if r.get("image") else [])
        r.pop("body", None)
    return rows_


_ITEM_SELECT = """SELECT i.*, s.name AS src_name, COALESCE(s.side, '') AS side, s.kind AS kind
                  FROM news_items i LEFT JOIN news_sources s ON s.id=i.source_id"""


def items(tid: int, state: str = "", q: str = "", side: str = "", limit: int = 400) -> list[dict]:
    where, params = ["i.topic_id=?"], [tid]
    if state in STATES:
        where.append("i.state=?")
        params.append(state)
    else:
        where.append("i.state!='hidden'")
    if side == "other":
        where.append("COALESCE(s.side,'')=''")
    elif side and side in nf.SIDES:
        where.append("s.side=?")
        params.append(side)
    if q.strip():
        where.append("(ulower(i.title) LIKE ? OR ulower(i.summary) LIKE ? OR ulower(COALESCE(s.name, i.source_name)) LIKE ?)")
        params += [f"%{nf.norm(q.strip())}%"] * 3
    rows_ = db.rows(f"{_ITEM_SELECT} WHERE {' AND '.join(where)} "
                    "ORDER BY COALESCE(i.published_at, i.fetched_at) DESC, i.id DESC LIMIT ?", [*params, limit])
    return _decorate(rows_)


def get_item(iid: int) -> dict | None:
    return db.row(f"{_ITEM_SELECT} WHERE i.id=?", (iid,))


def story_items(story_id: int) -> list[dict]:
    return _decorate(db.rows(f"{_ITEM_SELECT} WHERE i.story_id=? AND i.state!='hidden' "
                             "ORDER BY COALESCE(i.published_at, i.fetched_at)", (story_id,)))


# What the user may ask a digest to focus on, written in Vietnamese or English without diacritics (prefix match; keys
# of ≤ 3 letters match a whole word) → Russian terms in the keyword syntax of compile_terms (lower case = stem,
# UPPER CASE = whole word). Russia and Ukraine themselves are left out: every item of the topic is about them.
FOCUS_ALIASES = [
    (("putin",), ("путин",)),
    (("zelen", "zelin"), ("зеленск",)),
    (("trump",), ("трамп",)),
    (("peskov",), ("песков",)),
    (("lavrov",), ("лавров",)),
    (("zakharova",), ("захаров",)),
    (("medvedev",), ("медведев",)),
    (("shoigu", "soigu"), ("шойгу",)),
    (("belousov",), ("белоусов",)),
    (("gerasimov",), ("герасимов",)),
    (("syrsk",), ("сырск",)),
    (("budanov",), ("буданов",)),
    (("yermak",), ("ермак",)),
    (("umerov",), ("умеров",)),
    (("witkoff", "vitkoff"), ("уиткофф", "уиткоф")),
    (("vance",), ("вэнс", "венс")),
    (("rubio",), ("рубио",)),
    (("kellogg",), ("келлог",)),
    (("macron",), ("макрон",)),
    (("merz",), ("мерц",)),
    (("starmer",), ("стармер",)),
    (("orban",), ("орбан",)),
    (("erdogan",), ("эрдоган",)),
    (("lukashenk", "belarus"), ("лукашенк", "белорус", "беларус")),
    (("von der leyen", "leyen"), ("ляйен",)),
    (("kallas",), ("каллас",)),
    (("rutte",), ("рютте",)),
    (("kim jong", "trieu tien", "north korea"), ("КНДР", "ким чен", "северокоре")),
    (("trung quoc", "china", "tap can binh", "xi jinping"), ("китай", "китаи", "пекин", "си цзиньпин")),
    (("iran",), ("иран",)),
    (("nato",), ("НАТО", "натовск")),
    (("eu", "lien minh chau au", "chau au", "europe", "european union"), ("ЕС", "евросоюз", "европ", "еврокомисс")),
    (("my", "hoa ky", "usa", "united states", "washington", "nha trang", "white house"),
     ("США", "вашингтон", "белый дом", "белого дома", "американ")),
    (("phap", "france", "paris"), ("франц", "париж")),
    (("duc", "germany", "berlin"), ("герман", "берлин")),
    (("nuoc anh", "vuong quoc anh", "britain", "london", "uk"), ("британ", "лондон")),
    (("ba lan", "poland"), ("польш", "польск", "варшав")),
    (("crimea", "krym"), ("крым", "севастопол")),
    (("kursk",), ("курск",)),
    (("belgorod",), ("белгород",)),
    (("kharkiv", "kharkov"), ("харьков",)),
    (("zaporizh", "zaporozh"), ("запорож",)),
    (("donetsk", "donbas"), ("донецк", "донбасс", "ДНР")),
    (("pokrovsk",), ("покровск", "красноармейск")),
    (("kupiansk", "kupyansk"), ("купянск",)),
    (("odesa", "odessa"), ("одесс",)),
    (("kyiv", "kiev", "kiep"), ("киев",)),
    (("moscow", "moskva", "matxcova"), ("москв", "подмосков")),
    (("bien den", "black sea"), ("черное мор", "черном мор", "черноморск")),
    (("dam phan", "hoa binh", "negotiat", "peace", "ngung ban", "ceasefire", "dinh chien"),
     ("переговор", "перемири", "прекращения огня", "мирный план", "мирного плана", "мирному плану", "мирное соглашение",
      "мирного соглашения", "мирное урегулирование", "мирного урегулирования", "мирный процесс", "мирного процесса",
      "мирные переговор", "мирных переговор")),     # not the stem "мирн": "мирные жители" are civilians
    (("trung phat", "sanction"), ("санкц",)),
    (("vien tro", "tai tro", "funding", "military aid"), ("помощ", "финансирован", "поставк")),
    (("dong vien", "mobiliz", "quan dich", "tck"), ("мобилизац", "ТЦК", "военком")),
    (("tu binh", "prisoner", "trao doi tu"), ("пленн", "обмен")),
    (("hat nhan", "nuclear"), ("ядерн", "АЭС")),
    (("loc dau", "refiner"), ("НПЗ", "нефтеперераб")),
    (("nang luong", "energy", "luoi dien", "nha may dien", "power grid"),
     ("энергет", "энергосистем", "ТЭЦ", "подстанц", "электроснаб")),
    (("dau mo", "dau tho", "crude", "oil", "brent"), ("нефт", "brent")),
    (("diesel", "dieesel", "dizel"), ("дизел", "солярк")),
    (("xang", "gasoline"), ("бензин",)),
    (("nhien lieu", "fuel"), ("топлив",)),
    (("khi dot",), ("газопровод", "СПГ")),
    (("drone", "uav", "khong nguoi lai"), ("беспилотн", "БПЛА", "дрон")),
    (("ten lua", "missile"), ("ракет",)),
    (("tomahawk",), ("томагавк", "tomahawk")),
    (("patriot",), ("patriot", "пэтриот", "петриот")),
    (("taurus",), ("taurus", "таурус")),
    (("f-16", "f16"), ("f-16",)),
    (("atacms",), ("atacms",)),
    (("himars",), ("himars", "хаймарс")),
]
_CYR_WORD = re.compile(r"[А-Яа-яЁё][А-Яа-яЁё-]{2,}")


def _fold(s: str) -> str:
    """Lower case, Vietnamese/Latin diacritics removed (đ → d), for matching the aliases."""
    s = unicodedata.normalize("NFD", (s or "").lower().replace("đ", "d"))
    return "".join(ch for ch in s if unicodedata.category(ch) != "Mn")


def focus_terms(text: str | None) -> list[str]:
    """Russian keyword terms of a free-text focus ("ưu tiên tin về Putin, Zelensky, đàm phán"): names, countries and
    themes found in FOCUS_ALIASES, plus every Russian word typed as is (a long word loses up to two vowel endings, so
    "Зеленский" also finds "Зеленского")."""
    folded, out = _fold(text or ""), []
    for keys, terms in FOCUS_ALIASES:
        if any(re.search(r"(?<![a-z0-9])" + re.escape(k) + (r"(?![a-z0-9])" if len(k) <= 3 else ""), folded) for k in keys):
            out += [t for t in terms if t not in out]
    for w in _CYR_WORD.findall(text or ""):
        if w.isupper():
            term = w
        else:
            term = nf.norm(w)
            for _ in range(2):
                if len(term) > 5 and term[-1] in "аеиоуыэюяйь":
                    term = term[:-1]
        if term not in out:
            out.append(term)
    return out


def _focus_clauses(text: str | None) -> list[set[str]]:
    """The focus split where the user put commas, in the order typed: one set of matched forms per keyword."""
    parts = (focus_terms(p) for p in re.split(r"[,;\n]+", text or ""))
    return [{nf.norm(t) for t in p} for p in parts if p]


def _focus_match(r: dict, body: str, pat: re.Pattern, clauses: list[set[str]]) -> tuple[tuple, list[str]]:
    """How closely an item follows the focus: (rank, terms found). Rank compares best-first: where the focus is named
    (headline 3, start of the summary 2, at least twice in the text 1; a single passing mention deep in an article does
    not count, and only the start of the summary: a Telegram post's summary is the whole post, a roundup of ten topics
    names everything), then how many of the typed keywords are named there, then the earliest typed one."""
    in_title = nf.matches(pat, r["title"])
    in_head = nf.matches(pat, f"{r['title']}\n{(r.get('summary') or '')[:300]}")
    in_body = [m.group(0).lower() for m in pat.finditer(nf.norm((body or "")[:4000]))]
    tier = 3 if in_title else 2 if in_head else 1 if len(in_body) >= 2 else 0
    if not tier:
        return (0, 0, 0), []
    where = set(in_title or in_head or in_body)
    named = [n for n, c in enumerate(clauses) if where & c]
    return (tier, len(named), -named[0] if named else -len(clauses)), sorted(set(in_head) | set(in_body))


def digest_pick(tid: int, hours: int = 24, stories: int = DIGEST_STORIES, focus: str | None = None) -> dict:
    """Items for a 24-hour digest: the events of the last `hours` told by the most outlets (a Bing/Google result counts
    as its own outlet), at most two items per event: the most complete one, plus one from another side when there is.
    With a focus ("ưu tiên tin về Putin, Zelensky"), the events that follow it most closely come first (_focus_match;
    most covered first among equals), the others fill the remaining places.
    Returns {"items", "stories": [{story_id, outlets, sides, focus}], "considered", "focus_terms", "focus_matched"}."""
    since = (datetime.now() - timedelta(hours=hours)).replace(microsecond=0).isoformat()
    terms = focus_terms(focus)
    pat = nf.compile_terms("\n".join(terms)) if terms else None
    clauses = _focus_clauses(focus)
    rows_ = db.rows(f"""{_ITEM_SELECT} WHERE i.topic_id=? AND i.state!='hidden'
                       AND COALESCE(i.published_at, i.fetched_at) >= ?
                       ORDER BY COALESCE(i.published_at, i.fetched_at)""", (tid, since))
    groups: dict[int, dict] = {}
    for r in rows_:
        g = groups.setdefault(r.get("story_id") or r["id"], {"items": [], "outlets": set(), "sides": set(), "last": "",
                                                             "hits": set()})
        g["items"].append(r)
        g["outlets"].add(("n:" + (r.get("source_name") or "")) if r.get("kind") in ("bing", "gnews") else f"s:{r['source_id']}")
        if r.get("side"):
            g["sides"].add(r["side"])
        g["last"] = max(g["last"], r.get("published_at") or r.get("fetched_at") or "")
        if pat:
            r["focus_rank"], r["focus_hits"] = _focus_match(r, r.get("body") or "", pat, clauses)
            g["rank"] = max(g.get("rank", (0, 0, 0)), r["focus_rank"])
            g["hits"].update(r["focus_hits"])
    order = sorted(groups.items(), key=lambda kv: kv[1]["last"], reverse=True)
    order.sort(key=lambda kv: (kv[1].get("rank", (0, 0, 0)), len(kv[1]["outlets"]), len(kv[1]["sides"])), reverse=True)
    top = order[:max(1, stories)]
    by_id = {r["id"]: r for r in _decorate([dict(r) for st in top for r in st[1]["items"]])}
    picked, summary = [], []
    for sid, g in top:
        group = [by_id[r["id"]] for r in g["items"]]
        for r, raw in zip(group, g["items"]):
            r["focus_hits"], r["focus_rank"] = raw.get("focus_hits") or [], raw.get("focus_rank") or (0, 0, 0)
        # the item most about the focus first, then the most complete (full text, length held), the event's first last
        group.sort(key=lambda r: (not r["has_body"], -len(r.get("summary") or ""), r["id"] != sid))
        group.sort(key=lambda r: r["focus_rank"], reverse=True)
        best = group[0]
        other = next((r for r in group[1:] if r.get("side") and r.get("side") != best.get("side")), None)
        best["digest_order"] = len(summary) + 1
        if other:
            other["digest_order"] = len(summary) + 1
        picked += [best] + ([other] if other else [])
        summary.append({"story_id": sid, "outlets": len(g["outlets"]), "sides": len(g["sides"]), "focus": sorted(g["hits"])})
    return {"items": picked, "stories": summary, "considered": len(groups), "focus_terms": terms,
            "focus_matched": sum(1 for s in summary if s["focus"])}


def _digest_md(rows_: list[dict], files: dict, focus: str | None = None, bodies: dict | None = None) -> str:
    """sources/digest.md of a digest project: the events, the focus ones then the most covered first, with item files.
    `bodies` = {item id: {"body": full text}} (decorated rows no longer hold the text)."""
    terms = focus_terms(focus)
    pat = nf.compile_terms("\n".join(terms)) if terms else None
    clauses = _focus_clauses(focus)
    stories: dict[int, list[dict]] = {}
    for r in rows_:
        stories.setdefault(r.get("story_id") or r["id"], []).append(r)
    ranks, hits = {}, {}
    if pat:                                      # same test as digest_pick
        for sid, g in stories.items():
            found = [_focus_match(r, ((bodies or {}).get(r["id"]) or {}).get("body") or "", pat, clauses) for r in g]
            ranks[sid] = max(rank for rank, _ in found)
            hits[sid] = sorted({h for _, hs in found for h in hs})
    order = sorted(stories.items(), key=lambda kv: max(r.get("published_at") or "" for r in kv[1]), reverse=True)
    order.sort(key=lambda kv: (ranks.get(kv[0], (0, 0, 0)), max(r.get("story_size") or 1 for r in kv[1])), reverse=True)
    lines = ["# Điểm tin 24h: các sự kiện", ""]
    if focus:
        lines += [f"**Trọng tâm người dùng yêu cầu:** {focus}", "",
                  f"Sự kiện có ★ nhắc tới trọng tâm ({', '.join(terms) or 'không nhận ra từ khóa'}), sát nhất xếp trước. "
                  "Sự kiện ▶ TIN MỞ ĐẦU phát đầu tiên và là câu đầu của menu tiêu đề; các ★ khác xếp ngay sau trong menu, "
                  "ưu tiên làm tựa, thumbnail và được nhiều thời lượng hơn.", ""]
    lines += [("Sau các sự kiện ★ xếp" if hits else "Xếp") + " theo số tin cùng sự kiện (nhiều nguồn đưa = sự kiện lớn). Phía: " +
              ", ".join(f"{k} = {v}" for k, v in nf.SIDES.items() if k) + ".", ""]
    for n, (sid, g) in enumerate(order, 1):
        head = next((r for r in g if r["id"] == r.get("story_id")), g[0])
        outlets = (head.get("story_outlets") or "").replace(",", ", ")
        star = f" ★ ({', '.join(hits[sid])})" if hits.get(sid) else ""
        opening = " ▶ TIN MỞ ĐẦU" if n == 1 and hits.get(sid) else ""
        lines.append(f"## {n}. {head['title']}{star}{opening}")
        lines.append(f"- {head.get('story_size') or 1} tin cùng sự kiện" + (f": {outlets}" if outlets else ""))
        for r in g:
            lines.append(f"- [{r.get('side') or '-'}] {r.get('source') or '?'} · "
                         f"{(r.get('published_at') or '').replace('T', ' ')[:16]} · `{files.get(r['id'], '')}`")
        lines.append("")
    return "\n".join(lines)


def set_state(ids: list[int], state: str) -> int:
    """The user stars, hides or restores items ("used" is only set by make_project)."""
    if state not in ("new", "seen", "starred", "hidden") or not ids:
        return 0
    ids = [int(i) for i in ids][:2000]
    with db.tx() as c:
        return c.execute(f"UPDATE news_items SET state=? WHERE id IN ({','.join('?' * len(ids))})", [state, *ids]).rowcount


def mark_seen(ids: list[int]) -> None:
    """Opened items stop counting as new (a star, a hide or "used" stays)."""
    ids = [int(i) for i in ids][:2000]
    if ids:
        with db.tx() as c:
            c.execute(f"UPDATE news_items SET state='seen' WHERE state='new' AND id IN ({','.join('?' * len(ids))})", ids)


def mark_all_seen(tid: int) -> int:
    with db.tx() as c:
        return c.execute("UPDATE news_items SET state='seen' WHERE topic_id=? AND state='new'", (tid,)).rowcount


def _complete(it: dict) -> bool:
    """The item already holds its whole text (a Telegram post is complete even when short)."""
    return it.get("kind") == "telegram" or len(it.get("body") or "") >= 300


def _fetch(url: str) -> tuple[dict | None, str | None]:
    try:
        return nf.fetch_article(url), None
    except nf.FetchError as e:
        return None, str(e)


def _save_article(it: dict, art: dict | None, err: str | None) -> dict:
    if err:
        _update("news_items", it["id"], {"fetch_error": err[:300]})
        return {"body": it.get("body") or it.get("summary") or "", "error": err, "complete": False}
    fields = {"body": art["text"], "fetch_error": None}
    if not it.get("image") and art.get("image"):
        fields["image"] = art["image"]
    _update("news_items", it["id"], fields)
    return {"body": art["text"], "error": None, "complete": True}


def ensure_body(iid: int) -> dict:
    """Full text of an item: from the feed, or read from the article page once (and kept). {body, error, complete}"""
    it = get_item(iid)
    if not it:
        raise ValueError("không có tin này")
    if _complete(it) or not it.get("url"):
        return {"body": it.get("body") or it.get("summary") or "", "error": None, "complete": _complete(it)}
    return _save_article(it, *_fetch(it["url"]))


# ---------------------------------------------------------------- video project from items
def _item_md(it: dict, body: str, error: str | None, complete: bool) -> str:
    side = nf.SIDES.get(it.get("side") or "", "")
    lines = [f"# {it['title']}", "",
             f"- Nguồn: {it.get('source') or '?'}" + (f" (phía: {side})" if it.get("side") else "") +
             f" · {nf.KINDS.get(it.get('kind') or '', it.get('kind') or '')}",
             f"- Đăng lúc: {(it.get('published_at') or '').replace('T', ' ')} (giờ máy)",
             f"- Link: {it.get('url') or '-'}"]
    if it.get("matched"):
        lines.append(f"- Từ khóa khớp: {it['matched']}")
    if it.get("story_size", 1) > 1:
        lines.append(f"- Cùng sự kiện, {it['story_size']} tin đưa: {(it.get('story_outlets') or '').replace(',', ', ')}")
    if it.get("summary"):
        lines += ["", "## Tóm tắt", "", it["summary"]]
    lines += ["", "## Toàn văn", "", body if complete else
              f"(không lấy được toàn văn{': ' + error if error else ''}; đọc link gốc)"]
    return "\n".join(lines).strip() + "\n"


def make_project(ids: list[int], opts: dict) -> dict:
    """Create a video project whose sources are the chosen items: one markdown file per item (full text read now),
    sources/news.json (the list, machine readable) and the links."""
    rows_ = [r for r in (get_item(int(i)) for i in ids[:40]) if r]
    if not rows_:
        raise ValueError("chưa chọn tin nào")
    topic = get_topic(rows_[0]["topic_id"]) or {}
    need = [r for r in rows_ if not _complete(r) and r.get("url")]
    tg_rows = [r for r in rows_ if (r.get("url") or "").startswith("https://t.me/")]

    def tg_post(r):
        try:
            return nf.fetch_telegram_post(r["url"])
        except nf.FetchError:
            return None

    with ThreadPoolExecutor(max_workers=6) as ex:           # network only: the database is written from this thread
        fetched = list(ex.map(lambda r: _fetch(r["url"]), need))
        fresh_posts = dict(zip([r["id"] for r in tg_rows], ex.map(tg_post, tg_rows)))
    bodies = {r["id"]: _save_article(r, art, err) for r, (art, err) in zip(need, fetched)}
    for r in rows_:
        bodies.setdefault(r["id"], {"body": r.get("body") or r.get("summary") or "", "error": r.get("fetch_error"),
                                    "complete": _complete(r)})
    rows_ = _decorate([get_item(r["id"]) for r in rows_])
    rows_.sort(key=lambda r: r.get("published_at") or "")
    kind = opts.get("video_kind") or topic.get("video_kind") or "single"
    digest = kind == "digest"
    kind = kind if kind in VIDEO_KINDS else "single"
    head = next((r for r in rows_ if r["id"] == r.get("story_id")), rows_[-1])     # the item a story was built around
    newest = (rows_[-1].get("published_at") or "").replace("T", " ")[:16]
    day = f"{newest[8:10]}.{newest[5:7]}.{newest[:4]}" if len(newest) >= 10 else ""
    title = (opts.get("title") or "").strip() or (f"Điểm tin 24h {day}".strip() if digest else head["title"])
    language = (opts.get("language") or topic.get("language") or "ru").strip()
    brief = (opts.get("brief") if opts.get("brief") is not None else topic.get("brief") or "").strip()
    note = (f"Nguồn: {len(rows_)} tin chọn ở mục Tin tức (chủ đề \"{topic.get('name')}\"), tin mới nhất lúc {newest}. "
            "Toàn văn từng tin ở sources/news_*.md, danh sách ở sources/news.json. "
            + ("Bám" if digest else "Tin nóng: bám") + " đúng các tin này, chỉ tra thêm web để kiểm chứng hoặc bổ sung bối cảnh.")
    focus = (opts.get("focus") or "").strip()[:500] if digest else ""
    if digest:
        note = f"{DIGEST_NOTE}\n\n" + (DIGEST_FOCUS_NOTE.format(focus=focus) + "\n\n" if focus else "") + note
    p = store.create_project({"kind": "news", "topic": title, "title": title, "brief": f"{brief}\n\n{note}".strip(), "language": language,
                              "format": opts.get("format") or ("16:9" if digest else topic.get("format") or "9:16"),
                              "target_sec": opts.get("target_sec") or (DIGEST_TARGET_SEC if digest else
                                                                       topic.get("target_sec") or 60),
                              "budget_usd": opts.get("budget_usd"),
                              "audience": (opts.get("audience") or "").strip() or AUDIENCES.get(language),
                              "style": opts.get("style"), "auto_advance": bool(opts.get("auto_advance")),
                              **({"yt": opts.get("yt") or "", "yt_auto": opts.get("yt_auto"), "yt_vis": opts.get("yt_vis")} if "yt" in opts else {})})
    src_dir = store.project_dir(p) / "sources"
    listing, files = [], {}
    for n, r in enumerate(rows_, 1):
        b = bodies[r["id"]]
        name = f"news_{n:02d}_{slugify(r['title'], 40)}.md"
        files[r["id"]] = f"sources/{name}"
        (src_dir / name).write_text(_item_md(r, b["body"], b["error"], b["complete"]), encoding="utf-8")
        listing.append({"file": f"sources/{name}", "title": r["title"], "outlet": r.get("source"), "side": r.get("side"),
                        "kind": r.get("kind"), "url": r.get("url"), "published_at": r.get("published_at"),
                        "full_text": b["complete"], "story_id": r.get("story_id"), "story_size": r.get("story_size")})
    (src_dir / "news.json").write_text(json.dumps({"topic": topic.get("name"), "video_kind": kind, "focus": focus or None,
                                                   "made_at": now_iso(), "items": listing},
                                                  ensure_ascii=False, indent=2), encoding="utf-8")
    if digest:
        (src_dir / "digest.md").write_text(_digest_md(rows_, files, focus, bodies), encoding="utf-8")
    # photos and videos of these items: approved and downloaded at once (the user's choice, 2026-10-13: real pictures
    # of the articles first, news rulebook 1.7); the project page still lets the user drop one (media.py)
    candidates = media.build(rows_, fresh_posts, files)
    if candidates:
        media.save(p, {"made_at": now_iso(), "items": candidates})
        media.approve_all(p)
    store.save_links(p, "\n".join(f"{x['url']}  — {x['outlet']}" for x in listing if x.get("url")))
    with db.tx() as c:
        c.execute(f"UPDATE news_items SET state='used', project_id=? WHERE id IN ({','.join('?' * len(rows_))})",
                  [p["id"], *[r["id"] for r in rows_]])
    store.log_event(p["id"], "sources", ("Điểm tin 24h: " if digest else "") +
                    f"tạo từ {len(rows_)} tin ở mục Tin tức ({topic.get('name')})"
                    + (f", tự tải {len(candidates)} ảnh/video thật của các tin" if candidates else ""), "script")
    return p


# ---------------------------------------------------------------- background poller
class Poller:
    """Polls every enabled topic when its interval has passed (checked every 30 s); "Cập nhật ngay" polls at once."""

    def __init__(self):
        self.lock = threading.Lock()
        self.busy: set[int] = set()
        self.wake = threading.Event()
        self.last_purge = 0.0
        self.thread = threading.Thread(target=self._loop, name="creater-news", daemon=True)

    def start(self) -> None:
        self.thread.start()
        log.info("news poller started")

    def _claim(self, tid: int) -> bool:
        with self.lock:
            if tid in self.busy:
                return False
            self.busy.add(tid)
            return True

    def _run(self, tid: int, force: bool = False) -> None:
        try:
            t0 = time.time()
            res = poll_topic(tid, force=force)
            log.info("news topic %s: %s new, %d errors, %.1fs", tid, res.get("new"), len(res.get("errors") or []), time.time() - t0)
        except Exception:  # noqa: BLE001
            log.exception("news topic %s poll failed", tid)
        finally:
            with self.lock:
                self.busy.discard(tid)

    def poll_now(self, tid: int) -> dict:
        if not get_topic(tid):
            return {"error": "không có chủ đề này"}
        if not self._claim(tid):
            return {"message": "đang cập nhật"}
        threading.Thread(target=self._run, args=(tid, True), name=f"creater-news-{tid}", daemon=True).start()
        return {"message": "đang cập nhật"}

    def polling(self) -> list[int]:
        with self.lock:
            return sorted(self.busy)

    def _loop(self) -> None:
        self.wake.wait(5)
        while True:
            try:
                if db.setting_bool("news_enabled"):
                    for t in due_topics():
                        if self._claim(t["id"]):
                            self._run(t["id"])
                if time.time() - self.last_purge > 3600:
                    self.last_purge = time.time()
                    gone = purge()
                    if gone:
                        log.info("news: purged %d old items", gone)
            except Exception:  # noqa: BLE001
                log.exception("news poller")
            self.wake.wait(30)
            self.wake.clear()
