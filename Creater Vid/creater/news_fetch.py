"""News sources on the network: download RSS/Atom feeds, Telegram channels, news searches and article pages, and turn
them into plain items. No database here (news.py stores what this returns).

Standard library only: feeds through ElementTree (regex fallback for broken XML), Telegram through the public web
preview t.me/s/<channel>, search through the RSS output of Bing News and Google News, article text through the page's
JSON-LD articleBody or its paragraphs.
"""
from __future__ import annotations

import gzip
import html
import json
import re
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zlib
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
TIMEOUT = 20
MAX_BYTES = 12 * 1024 * 1024

KINDS = {"rss": "RSS / Atom", "telegram": "Telegram", "bing": "Bing News (từ khóa)", "gnews": "Google News (từ khóa)"}
SIDES = {"ru": "Nga", "ua": "Ukraina", "intl": "Quốc tế", "indep": "Độc lập", "": "Khác"}

# Google News: hl, gl, ceid per language of the topic
_GNEWS = {"ru": ("ru", "RU", "RU:ru"), "uk": ("uk", "UA", "UA:uk"), "vi": ("vi", "VN", "VN:vi"), "en": ("en-US", "US", "US:en"),
          "fr": ("fr", "FR", "FR:fr"), "es": ("es", "ES", "ES:es"), "de": ("de", "DE", "DE:de")}
_TRACKING = re.compile(r"^(utm_\w+|from|ref|rss|at_\w+|yclid|fbclid|gclid|ocid|cmpid|ito|in)$", re.I)


class FetchError(Exception):
    pass


# ---------------------------------------------------------------- HTTP
_BROWSER = {"User-Agent": UA, "Accept-Encoding": "gzip, deflate", "Accept-Language": "ru-RU,ru;q=0.9,uk;q=0.8,en;q=0.7",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/rss+xml;q=0.9,*/*;q=0.8",
            "Upgrade-Insecure-Requests": "1", "Sec-Fetch-Dest": "document", "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none", "Sec-Fetch-User": "?1", "sec-ch-ua-mobile": "?0", "sec-ch-ua-platform": '"Windows"',
            "sec-ch-ua": '"Chromium";v="130", "Google Chrome";v="130", "Not?A_Brand";v="99"'}


def iri_to_uri(url: str) -> str:
    """Links with Cyrillic paths (dw.com/ru/россия-…) or domains (кремль.рф) -> ASCII the HTTP library accepts."""
    u = urllib.parse.urlsplit(url.strip())
    try:
        host = u.hostname.encode("idna").decode("ascii") if u.hostname else ""
    except UnicodeError:
        host = u.hostname or ""
    netloc = host + (f":{u.port}" if u.port else "")
    return urllib.parse.urlunsplit((u.scheme, netloc, urllib.parse.quote(u.path, safe="/%:@!$&'()*+,;=-._~"),
                                    urllib.parse.quote(u.query, safe="=&%+:/?@!$'()*,;-._~"), ""))


def http_get(url: str, etag: str | None = None, modified: str | None = None, timeout: int = TIMEOUT) -> dict:
    """GET like a browser (some news sites answer 403/500 to bare clients), gzip, conditional headers.
    Returns {status, body, headers, url}; status 304 = unchanged since etag/modified."""
    headers = dict(_BROWSER)
    if etag:
        headers["If-None-Match"] = etag
    if modified:
        headers["If-Modified-Since"] = modified
    try:
        with urllib.request.urlopen(urllib.request.Request(iri_to_uri(url), headers=headers), timeout=timeout) as r:
            raw = r.read(MAX_BYTES + 1)
            enc = (r.headers.get("Content-Encoding") or "").lower()
            if enc == "gzip" or raw[:2] == b"\x1f\x8b":
                raw = gzip.decompress(raw)
            elif enc == "deflate":
                raw = zlib.decompress(raw, -zlib.MAX_WBITS)
            return {"status": r.status, "body": raw[:MAX_BYTES], "headers": dict(r.headers.items()), "url": r.geturl()}
    except urllib.error.HTTPError as e:
        if e.code == 304:
            return {"status": 304, "body": b"", "headers": dict(e.headers.items()), "url": url}
        raise FetchError(f"HTTP {e.code}" + (" (trang chặn truy cập)" if e.code in (401, 403, 451) else "")) from e
    except urllib.error.URLError as e:
        reason = str(getattr(e, "reason", e))
        if "getaddrinfo" in reason:
            reason = "không phân giải được tên miền"
        elif "timed out" in reason:
            reason = "quá thời gian chờ"
        elif "CERTIFICATE" in reason:
            reason = "chứng chỉ SSL không hợp lệ"
        raise FetchError(reason[:200]) from e
    except (TimeoutError, OSError, EOFError, zlib.error) as e:
        raise FetchError(str(e)[:200] or type(e).__name__) from e


def _charset(headers: dict, body: bytes) -> str:
    ct = next((v for k, v in headers.items() if k.lower() == "content-type"), "") or ""
    m = re.search(r"charset=([\w-]+)", ct, re.I) or re.search(rb"<meta[^>]+charset=[\"']?([\w-]+)", body[:4096], re.I)
    cs = m.group(1) if m else "utf-8"
    cs = cs.decode("ascii", "ignore") if isinstance(cs, bytes) else cs
    try:
        "".encode(cs)
        return cs
    except LookupError:
        return "utf-8"


def decode(res: dict) -> str:
    return res["body"].decode(_charset(res["headers"], res["body"]), errors="replace")


# ---------------------------------------------------------------- text, dates, urls
_TAG = re.compile(r"<[^>]+>")
_BLOCK_END = re.compile(r"(?i)<br\s*/?>|</p>|</div>|</li>|</h\d>|</blockquote>")


def clean_text(s: str | None) -> str:
    """HTML or plain text -> readable plain text (paragraphs kept as line breaks)."""
    if not s:
        return ""
    s = _BLOCK_END.sub("\n", s)
    s = _TAG.sub("", s)
    s = html.unescape(html.unescape(s)) if "&amp;" in s else html.unescape(s)
    s = s.replace("\xa0", " ").replace("​", "")
    lines = [re.sub(r"[ \t\r\f\v]+", " ", ln).strip() for ln in s.split("\n")]
    out, blank = [], False
    for ln in lines:
        if ln:
            out.append(ln)
            blank = False
        elif out and not blank:
            out.append("")
            blank = True
    return "\n".join(out).strip()


def short(s: str, n: int) -> str:
    s = (s or "").strip()
    if len(s) <= n:
        return s
    cut = s[:n].rsplit(" ", 1)[0]
    return (cut if len(cut) > n * 0.6 else s[:n]).rstrip(" ,.;:—-") + "…"


def parse_date(s: str | None) -> str | None:
    """RFC 822 or ISO 8601 -> local naive ISO (what util.now_iso() writes). Naive input is taken as UTC."""
    s = (s or "").strip()
    if not s:
        return None
    dt = None
    try:
        dt = parsedate_to_datetime(s)
    except (TypeError, ValueError, IndexError):
        try:
            dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        except ValueError:
            return None
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    local = dt.astimezone().replace(tzinfo=None, microsecond=0)
    now = datetime.now()
    if local > now + timedelta(minutes=30):         # wrong time zone in the feed: never "from the future"
        local = now.replace(microsecond=0)
    return local.isoformat()


def canonical_url(url: str) -> str:
    """URL without fragment and tracking parameters: the dedupe key of an item."""
    try:
        u = urllib.parse.urlsplit((url or "").strip())
    except ValueError:
        return (url or "").strip()
    if not u.scheme:
        return (url or "").strip()
    q = [(k, v) for k, v in urllib.parse.parse_qsl(u.query, keep_blank_values=True) if not _TRACKING.match(k)]
    return urllib.parse.urlunsplit(("https" if u.scheme in ("http", "https") else u.scheme, u.netloc.lower(), u.path,
                                    urllib.parse.urlencode(q), ""))


def _unwrap_bing(link: str) -> str:
    if "bing.com/news/apiclick" in link:
        real = urllib.parse.parse_qs(urllib.parse.urlsplit(link).query).get("url")
        if real:
            return real[0]
    return link


def host_name(url: str) -> str:
    try:
        h = urllib.parse.urlsplit(url).netloc.lower()
    except ValueError:
        return ""
    return h[4:] if h.startswith("www.") else h


# ---------------------------------------------------------------- RSS / Atom
def _local(tag) -> str:
    return tag.rsplit("}", 1)[-1].lower() if isinstance(tag, str) else ""


def _txt(el) -> str:
    return "".join(el.itertext()).strip()


def parse_feed(data: bytes) -> list[dict]:
    try:
        root = ET.fromstring(data)
    except ET.ParseError:
        return _parse_feed_regex(data)
    out = []
    for el in root.iter():
        if _local(el.tag) in ("item", "entry"):
            it = _feed_entry(el)
            if it:
                out.append(it)
    return out


def _feed_entry(el) -> dict | None:
    f: dict = {}
    links: list[str] = []
    for ch in el:
        name = _local(ch.tag)
        if name == "link":
            href = ch.get("href")
            if href:
                if (ch.get("rel") or "alternate") == "alternate":
                    links.append(href)
            elif _txt(ch):
                links.append(_txt(ch))
        elif name in ("enclosure", "content", "thumbnail") and ch.get("url"):
            typ = ch.get("type") or ch.get("medium") or "image"
            if "image" in typ or name == "thumbnail":
                f.setdefault("image", ch.get("url"))
        elif name in ("encoded", "full-text") or (name == "content" and _txt(ch)):
            if len(_txt(ch)) > len(f.get("body") or ""):
                f["body"] = _txt(ch)
        elif name in ("description", "summary", "anons"):
            f.setdefault("summary", _txt(ch))
        elif name == "title":
            f["title"] = _txt(ch)
        elif name in ("guid", "id"):
            f["guid"] = _txt(ch)
        elif name in ("pubdate", "published", "date", "issued"):
            f.setdefault("date", _txt(ch))
        elif name == "updated":
            f.setdefault("updated", _txt(ch))
        elif name == "source" and _txt(ch):
            f["source_name"] = _txt(ch)                  # Google News <source>, Bing <News:Source>
        elif name == "image" and _txt(ch).startswith("http"):
            f.setdefault("image", _txt(ch))              # Bing <News:Image>
    guid = f.get("guid") or ""
    link = links[0] if links else (guid if guid.startswith("http") else "")
    return _make_item(f.get("title"), link, guid, f.get("summary"), f.get("body"), f.get("image"),
                      f.get("date") or f.get("updated"), f.get("source_name"))


def _parse_feed_regex(data: bytes) -> list[dict]:
    """Broken XML (stray &, bad bytes): pull the tags of each item with regexes."""
    m = re.search(rb"encoding=[\"']([\w-]+)", data[:200])
    enc = m.group(1).decode() if m else "utf-8"
    try:
        text = data.decode(enc, errors="replace")
    except LookupError:
        text = data.decode("utf-8", errors="replace")

    def tag(block: str, *names: str) -> str:
        for n in names:
            mm = re.search(rf"<{n}(?:\s[^>]*)?>(.*?)</{n}>", block, re.S | re.I)
            if mm:
                v = mm.group(1).strip()
                cd = re.fullmatch(r"<!\[CDATA\[(.*)\]\]>", v, re.S)
                return cd.group(1) if cd else v
        return ""

    out = []
    for mm in re.finditer(r"<(item|entry)[\s>].*?</\1>", text, re.S | re.I):
        b = mm.group(0)
        href = re.search(r"<link[^>]+href=[\"']([^\"']+)", b)
        link = tag(b, "link") or (href.group(1) if href else "")
        img = re.search(r"<(?:enclosure|media:content|media:thumbnail)[^>]+url=[\"']([^\"']+)", b)
        it = _make_item(tag(b, "title"), link, tag(b, "guid", "id"), tag(b, "description", "summary"),
                        tag(b, "content:encoded", "yandex:full-text", "rbc_news:full-text", "content"),
                        img.group(1) if img else None, tag(b, "pubDate", "published", "dc:date", "updated"),
                        tag(b, "source", "News:Source"))
        if it:
            out.append(it)
    return out


def _make_item(title, link, guid, summary, body, image, date, source_name) -> dict | None:
    link = _unwrap_bing(html.unescape((link or "").strip()))
    title = clean_text(title).replace("\n", " ")
    summary, body = clean_text(summary), clean_text(body)
    source_name = clean_text(source_name)
    if source_name and title.endswith(" - " + source_name):          # Google News: "Title - outlet"
        title = title[: -len(source_name) - 3].rstrip()
    if summary and title and summary.replace(" ", "").startswith(title.replace(" ", "")[:40]):
        summary = ""                                                  # Google News description = title + outlet
    if not body and len(summary) > 700:
        body = summary
    if body and summary and body.startswith(summary[:80]) and len(body) <= len(summary) + 20:
        body = ""
    if not title:
        if not (summary or body):
            return None
        title = short((summary or body).split("\n")[0], 140)
    uid = canonical_url(link) if link else (guid or "").strip()
    if not uid:
        return None
    return {"uid": uid, "url": link or (guid if (guid or "").startswith("http") else ""), "title": title[:500],
            "summary": short(summary, 900), "body": body[:60000], "image": (image or "").strip() or None,
            "published_at": parse_date(date), "source_name": source_name or None}


# ---------------------------------------------------------------- Telegram (public web preview)
def channel_name(s: str) -> str:
    s = (s or "").strip()
    m = re.search(r"t\.me/(?:s/)?([A-Za-z0-9_]{3,})", s)
    return m.group(1) if m else s.lstrip("@").strip("/ ")


_TG_POST = re.compile(r'data-post="([^"/]+)/(\d+)"')


def _div_inner(s: str, pos: int) -> str:
    """Inner HTML of the <div> whose opening tag contains position `pos` (nested divs counted)."""
    start = s.rfind("<div", 0, pos)
    open_end = s.find(">", pos)
    if start < 0 or open_end < 0:
        return ""
    depth, i = 1, open_end + 1
    for m in re.finditer(r"<div[\s>]|</div>", s[i:]):
        depth += 1 if m.group(0).startswith("<div") else -1
        if depth == 0:
            return s[i:i + m.start()]
    return s[i:]


_TG_MEDIA = re.compile(r'<a class="tgme_widget_message_(photo_wrap|video_player)([^"]*)"([^>]*)>')
_BG = re.compile(r"background-image:url\('([^']+)'\)")


def _tg_media(block: str, post: str) -> list[dict]:
    """Photos and videos of a post, album items included, in order. A video too big for the web preview has no url
    (only the Telegram API can fetch it) but keeps its thumbnail and duration."""
    found = list(_TG_MEDIA.finditer(block))
    out = []
    for i, m in enumerate(found):
        seg = block[m.end(): found[i + 1].start() if i + 1 < len(found) else len(block)]
        attrs = m.group(3)
        href = re.search(r'href="https://t\.me/([^"?]+)', attrs)
        item_post = href.group(1) if href else post                 # album items are messages of their own
        if m.group(1) == "photo_wrap":
            bg = _BG.search(attrs)
            if bg:
                out.append({"kind": "photo", "url": bg.group(1), "thumb": bg.group(1), "post": item_post})
            continue
        seg = seg.split("js-message_text", 1)[0]
        src = re.search(r'<video[^>]+src="([^"]+)"', seg)
        thumb = _BG.search(seg)
        dur = re.search(r'message_video_duration[^>]*>([^<]+)<', seg)
        out.append({"kind": "video", "url": src.group(1) if src else None, "thumb": thumb.group(1) if thumb else None,
                    "duration": dur.group(1).strip() if dur else None, "post": item_post,
                    "too_big": not src and "too big" in seg.lower()})
    return out


def parse_telegram(page: str) -> list[dict]:
    """Posts of a channel page (t.me/s/<channel>) or of one embedded post (t.me/<channel>/<id>?embed=1)."""
    out = []
    blocks = page.split('<div class="tgme_widget_message_wrap')[1:] or ([page] if _TG_POST.search(page) else [])
    for block in blocks:
        m = _TG_POST.search(block)
        if not m or "service_message" in block[:600]:
            continue
        post = f"{m.group(1)}/{m.group(2)}"
        pos = block.find("js-message_text")
        text = clean_text(_div_inner(block, pos)) if pos >= 0 else ""
        if not text:
            continue                                                  # photo/video without a caption
        when = re.search(r'<time[^>]+datetime="([^"]+)"', block)
        img = re.search(r"(?:message_photo_wrap|video_thumb|link_preview_image)[^>]*background-image:url\('([^']+)'\)", block)
        views = re.search(r'tgme_widget_message_views">([^<]+)<', block)
        fwd = re.search(r'tgme_widget_message_forwarded_from_name"(?: href="([^"]+)")?[^>]*>(?:<span[^>]*>)?([^<]+)', block)
        first = text.split("\n")[0]
        out.append({"uid": f"https://t.me/{post}", "url": f"https://t.me/{post}",
                    "title": short(first, 160), "summary": short(text, 900), "body": text[:60000],
                    "image": img.group(1) if img else None, "published_at": parse_date(when.group(1) if when else None),
                    "source_name": None, "views": views.group(1).strip() if views else None,
                    "video": "tgme_widget_message_video" in block, "media": _tg_media(block, post),
                    "forwarded_from": {"name": clean_text(fwd.group(2)), "url": fwd.group(1)} if fwd else None})
    return out


def fetch_telegram_post(post: str) -> dict | None:
    """One post with fresh media links (the CDN links of a channel page carry a token that expires)."""
    post = post.strip().removeprefix("https://t.me/").split("?")[0]
    items = parse_telegram(decode(http_get(f"https://t.me/{post}?embed=1&mode=tme")))
    return items[0] if items else None


def telegram_title(page: str) -> str:
    m = re.search(r'tgme_channel_info_header_title"><span[^>]*>(.*?)</span>', page, re.S)
    return clean_text(m.group(1)) if m else ""


# ---------------------------------------------------------------- sources
def source_url(kind: str, value: str, language: str = "ru") -> str:
    """The URL actually downloaded for a source (feeds as typed, channels and searches built from the value)."""
    value = (value or "").strip()
    if kind == "telegram":
        return f"https://t.me/s/{channel_name(value)}"
    if kind == "bing":
        lang = language or "ru"
        return ("https://www.bing.com/news/search?" +
                urllib.parse.urlencode({"q": value, "format": "rss", "setlang": lang, "count": "50",
                                        "qft": 'sortbydate="1"'}))
    if kind == "gnews":
        hl, gl, ceid = _GNEWS.get(language or "ru", _GNEWS["en"])
        q = value if "when:" in value else value + " when:2d"
        return "https://news.google.com/rss/search?" + urllib.parse.urlencode({"q": q, "hl": hl, "gl": gl, "ceid": ceid})
    return value


def fetch_source(kind: str, value: str, language: str = "ru", etag: str | None = None,
                 modified: str | None = None) -> dict:
    """Items of one source: {items, not_modified, etag, modified, title}. Raises FetchError."""
    url = source_url(kind, value, language)
    if not url.startswith(("http://", "https://")):
        raise FetchError("địa chỉ phải bắt đầu bằng http:// hoặc https://")
    conditional = kind == "rss"
    res = http_get(url, etag if conditional else None, modified if conditional else None)
    hdr = {k.lower(): v for k, v in res["headers"].items()}
    base = {"etag": hdr.get("etag") if conditional else None, "modified": hdr.get("last-modified") if conditional else None}
    if res["status"] == 304:
        return {"items": [], "not_modified": True, "title": None, **base}
    if kind == "telegram":
        page = decode(res)
        if "tgme_channel_info" not in page and "tgme_widget_message" not in page:
            raise FetchError("không phải kênh Telegram công khai (hoặc kênh tắt bản xem trên web)")
        return {"items": parse_telegram(page), "not_modified": False, "title": telegram_title(page), **base}
    head = res["body"][:600].lstrip().lower()
    if head.startswith(b"<!doctype html") or head.startswith(b"<html"):
        raise FetchError("địa chỉ trả về trang web, không phải RSS/Atom")
    items = parse_feed(res["body"])
    title = None
    try:
        root = ET.fromstring(res["body"])
        ch = next((el for el in root.iter() if _local(el.tag) in ("channel", "feed")), None)
        t = next((x for x in (ch if ch is not None else []) if _local(x.tag) == "title"), None)
        title = clean_text(_txt(t)) if t is not None else None
    except ET.ParseError:
        pass
    if kind in ("bing", "gnews"):
        for it in items:
            it["source_name"] = it.get("source_name") or host_name(it["url"])
    return {"items": items, "not_modified": False, "title": title, **base}


# ---------------------------------------------------------------- keywords, grouping
def norm(s: str | None) -> str:
    return (s or "").lower().replace("ё", "е")


def compile_terms(text: str | None) -> re.Pattern | None:
    """One term per line (or comma-separated). A lower-case term matches at the start of a word, so the stem
    "наступлен" finds наступление, наступления…; an UPPER-CASE term is an acronym and matches the whole word only
    (СВО must not find "своим")."""
    terms = {t.strip() for t in re.split(r"[\n,;]+", text or "") if t.strip()}
    if not terms:
        return None
    alts = []
    for t in sorted(terms, key=len, reverse=True):
        whole = t == t.upper() and any(ch.isalpha() for ch in t)
        alts.append(re.escape(norm(t)) + (r"(?!\w)" if whole else ""))
    return re.compile(r"(?<!\w)(?:" + "|".join(alts) + ")", re.I)


def matches(pattern: re.Pattern | None, text: str) -> list[str]:
    if not pattern:
        return []
    return sorted({m.group(0).lower() for m in pattern.finditer(norm(text))})


_STOP = {w[:6] for w in """это этот эта эти того тому чтобы после более менее также когда может могут будет будут были было
стал стала стало стали году года годом время свой своей своих который которая которые которых через между около против
только уже ещё еще всех весь всего нужно надо заявил заявила заявили сообщил сообщила сообщили рассказал рассказала назвал
назвала назвали отметил отметила считает пишет пишут глава главы новые новый новых сегодня вчера стало россии россия
украины украина украине после того from with that this have will said says about after into over than they their what""".split()}


_YEAR = re.compile(r"(19|20)\d\d")


def fingerprint(title: str) -> tuple[frozenset, frozenset]:
    """Rough fingerprint of a headline: (6-letter stems of its content words, short upper-case acronyms, numbers and
    date/time stamps like "868", "05.10.2026", "08:00"; names: 4-letter stems of capitalised words after the first)."""
    words, names = set(), set()
    title = (title or "").split(" // ")[0]            # Коммерсантъ: "headline // subhead" (the subhead drifts)
    found = re.findall(r"\d+(?:[.:,]\d+)*|[^\W\d_]+", title)
    letters = [w for w in found if not w[0].isdigit()]
    title_case = len(letters) > 3 and sum(w[0].isupper() for w in letters) > 0.6 * len(letters)   # "Russia Hits Kyiv"
    first = True
    for w in found:
        if w[0].isdigit():
            if len(w) >= 2:
                words.add(w)
            continue
        if len(w) >= 4:
            stem = norm(w)[:6]
            if stem not in _STOP:
                words.add(stem)
            if w[0].isupper() and not w.isupper() and not first and not title_case:
                names.add(norm(w)[:4])        # the first word is capitalised anyway
        elif len(w) == 3 and w.isupper():
            words.add(norm(w))
        first = False
    return frozenset(words), frozenset(names)


def tokens(title: str) -> frozenset:
    return fingerprint(title)[0]


def overlap(a: tuple, b: tuple) -> float:
    return len(a[0] & b[0]) / min(len(a[0]), len(b[0])) if a[0] and b[0] else 0.0


def similar(fa: tuple, fb: tuple) -> bool:
    """Two headlines tell the same event: enough shared words, no conflicting figures, no conflicting names.
    Recurring reports share their wording but not their numbers ("сбили 868 БПЛА" / "сбили 199 БПЛА"), stamps (the
    08:00 and 22:00 report) or place ("взяла Голубково" / "взяла Самойловку")."""
    a, b = fa[0], fb[0]
    if not a or not b:
        return False
    inter = len(a & b)
    if inter < 3 or inter / min(len(a), len(b)) < 0.5:
        return False
    if fa[1] - fb[1] and fb[1] - fa[1]:
        return False
    stamps_a = {t for t in a if t[0].isdigit() and not t.isdigit()}
    stamps_b = {t for t in b if t[0].isdigit() and not t.isdigit()}
    if stamps_a and stamps_b and stamps_a != stamps_b:
        return False
    nums_a = {t for t in a if t.isdigit() and not _YEAR.fullmatch(t)}
    nums_b = {t for t in b if t.isdigit() and not _YEAR.fullmatch(t)}
    return not (nums_a and nums_b and not nums_a & nums_b)


# ---------------------------------------------------------------- article pages
class _Node:
    __slots__ = ("tag", "label", "parent", "idx", "end", "parts", "links", "score", "total", "link_total")

    def __init__(self, tag: str, label: str, parent, idx: int):
        self.tag, self.label, self.parent, self.idx, self.end = tag, label, parent, idx, idx
        self.parts: list[str] = []
        self.links = 0
        self.score: float | None = None
        self.total = self.link_total = 0

    def own(self) -> str:
        return re.sub(r"[ \t\r\f\v]+", " ", "".join(self.parts)).strip()


class _Page(HTMLParser):
    """Block tree of a page (inline tags are transparent), plus its meta tags and JSON-LD blobs."""
    SKIP = {"script", "style", "noscript", "nav", "header", "footer", "aside", "form", "button", "svg", "figure",
            "iframe", "select", "template", "figcaption", "picture", "video", "audio", "object"}
    BLOCK = {"body", "main", "article", "section", "div", "p", "li", "ul", "ol", "td", "tr", "table", "tbody", "blockquote",
             "pre", "dd", "dl", "dt", "h1", "h2", "h3", "h4", "h5", "h6", "center"}
    META = {"og:title", "og:description", "og:image", "article:published_time", "description", "twitter:image",
            "og:site_name"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = _Node("root", "", None, 0)
        self.nodes = [self.root]
        self.stack = [self.root]
        self.skip, self.in_a, self.in_ld = 0, 0, False
        self.ld: list[str] = []
        self.meta: dict[str, str] = {}

    def handle_starttag(self, tag, attrs):
        a = {k: (v or "") for k, v in attrs}
        if tag == "meta":
            key = (a.get("property") or a.get("name") or a.get("itemprop") or "").lower()
            if key in self.META and a.get("content"):
                self.meta.setdefault(key, a["content"])
            return
        if tag == "script" and a.get("type", "").lower() == "application/ld+json":
            self.in_ld = True
            self.ld.append("")
            return
        if tag in self.SKIP:
            self.skip += 1
            return
        if self.skip:
            return
        if tag == "br":
            self.stack[-1].parts.append("\n")
        elif tag == "a":
            self.in_a += 1
        elif tag in self.BLOCK:
            top = self.stack[-1]
            if top.tag == "p" or (tag == "li" and top.tag == "li"):      # <p> and <li> cannot hold another block
                self.stack.pop()
            label = " ".join((a.get("class") or "", a.get("id") or "", a.get("itemprop") or ""))
            node = _Node(tag, label, self.stack[-1], len(self.nodes))
            self.nodes.append(node)
            self.stack.append(node)

    def handle_endtag(self, tag):
        if tag == "script" and self.in_ld:
            self.in_ld = False
            return
        if tag in self.SKIP:
            self.skip = max(0, self.skip - 1)
            return
        if self.skip:
            return
        if tag == "a":
            self.in_a = max(0, self.in_a - 1)
        elif tag in self.BLOCK:
            for i in range(len(self.stack) - 1, 0, -1):           # close up to the matching open block
                if self.stack[i].tag == tag:
                    del self.stack[i:]
                    break

    def handle_data(self, data):
        if self.in_ld:
            self.ld[-1] += data
        elif not self.skip:
            node = self.stack[-1]
            node.parts.append(data)
            if self.in_a:
                node.links += len(data.strip())


_BOILER = re.compile(r"(?i)(cookie|подпис(ыв|ат)|все права защищ|©|реклама|javascript|присоединяйтесь|читайте также|"
                     r"мы в telegram|наш telegram|subscribe|newsletter|запрещен\w* в росси|признан\w* (иноагент|нежелательн)|"
                     r"источник фото)")
_POS = re.compile(r"(?i)article|body|content|entry|main|post|text|story|news|material|doc|lead")
_NEG = re.compile(r"(?i)comment|meta|footer|footnote|sidebar|side-|related|share|social|promo|banner|advert|\bads?\b|ad-|"
                  r"widget|menu|nav|subscri|recommend|popular|more|tags|breadcrumb|caption|teaser|card|cookie|rubric|"
                  r"partner|digest|similar|feed|list|slider|carousel|bottom|copyright|disclaimer|inject")
_DOMAINS = re.compile(r"\b[\w-]+\.(?:ru|рф|com|org|net|ua|su)\b", re.I)
_TAG_BONUS = {"div": 5, "article": 10, "main": 5, "section": 3, "td": 3, "blockquote": 3, "pre": 3,
              "ul": -3, "ol": -3, "li": -3, "dl": -3, "dd": -3, "dt": -3, "h1": -5, "h2": -5, "h3": -5, "h4": -5}


def _readable(p: _Page) -> str:
    """Readability-lite: score the blocks that hold paragraphs (parent full, grandparent half), weigh by class names
    and link density, keep the best block plus the siblings that also read like article text."""
    nodes = p.nodes
    for n in nodes:
        n.total = len(n.own())
        n.link_total = n.links
    for n in reversed(nodes[1:]):                     # descendant totals and subtree ends (nodes are in DFS order)
        n.parent.total += n.total
        n.parent.link_total += n.link_total
        n.parent.end = max(n.parent.end, n.end)

    def init(n: _Node) -> None:
        if n.score is None:
            n.score = _TAG_BONUS.get(n.tag, 0) + (25 if _POS.search(n.label) else 0) - (25 if _NEG.search(n.label) else 0)

    for n in nodes[1:]:
        if n.tag not in ("p", "div", "td", "pre", "blockquote", "section", "article", "li"):
            continue
        t = n.own()
        if len(t) < 25 or n.links > 0.5 * len(t):
            continue
        s = 1 + t.count(",") + min(len(t) // 100, 3)
        for parent, share in ((n.parent, 1.0), (n.parent.parent if n.parent else None, 0.5)):
            if parent is not None and parent is not p.root:
                init(parent)
                parent.score += s * share

    def final(n: _Node) -> float:
        density = n.link_total / n.total if n.total else 1
        return (n.score or 0) * (1 - density)

    cands = [n for n in nodes if n.score is not None]
    if not cands:
        return ""
    top = max(cands, key=final)
    keep = [top]
    if top.parent is not None:
        floor = max(10.0, final(top) * 0.2)
        for sib in nodes[top.parent.idx + 1: top.parent.end + 1]:
            if sib is top or sib.parent is not top.parent:
                continue
            own = sib.own()
            density = sib.links / len(own) if own else 1
            if (sib.score is not None and final(sib) >= floor) or (sib.tag == "p" and len(own) > 80 and density < 0.25):
                keep.append(sib)
    keep.sort(key=lambda n: n.idx)
    out: list[str] = []
    for root in keep:
        i = root.idx
        while i <= root.end:
            n = nodes[i]
            if n is not root and _NEG.search(n.label) and (n.total < 300 or n.link_total > 0.3 * n.total):
                i = n.end + 1                                   # a "related" / "share" box inside the article
                continue
            i += 1
            t = n.own()
            if not t or n.links > 0.5 * len(t) or len(_DOMAINS.findall(t)) >= 4:
                continue
            heading = n.tag in ("h2", "h3", "h4") and len(t) >= 12
            if (len(t) >= 40 or heading or (len(t) >= 20 and t[-1] in ".!?…»\"")) and not _BOILER.search(t[:160]):
                out.append(t)
    return "\n\n".join(dict.fromkeys(out))


def _ld_article(blobs: list[str]) -> dict:
    found: dict = {}

    def walk(x):
        if isinstance(x, dict):
            body = x.get("articleBody")
            if isinstance(body, str) and len(body) > len(found.get("body") or ""):
                found["body"] = body
                found["published"] = x.get("datePublished") or found.get("published")
                found["title"] = x.get("headline") or found.get("title")
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)

    for b in blobs:
        try:
            walk(json.loads(b.strip(), strict=False))
        except ValueError:
            continue
    return found


def extract_article(page: str) -> dict:
    p = _Page()
    try:
        p.feed(page)
        p.close()
    except Exception:  # noqa: BLE001  (html.parser can choke on odd markup: keep what was read)
        pass
    text = _readable(p)
    ld = _ld_article(p.ld)
    ld_body = clean_text(ld.get("body"))
    if len(ld_body) > max(200, 0.6 * len(text)):
        text = ld_body
    return {"text": text[:60000], "title": clean_text(ld.get("title") or p.meta.get("og:title")),
            "description": clean_text(p.meta.get("og:description") or p.meta.get("description")),
            "image": p.meta.get("og:image") or p.meta.get("twitter:image"),
            "published_at": parse_date(ld.get("published") or p.meta.get("article:published_time")),
            "site": clean_text(p.meta.get("og:site_name"))}


def fetch_article(url: str) -> dict:
    """Full text of a news page. Raises FetchError when the page cannot be read or has no article text."""
    if not url.startswith(("http://", "https://")):
        raise FetchError("tin không có link")
    if "news.google.com" in url:
        raise FetchError("link Google News chỉ mở được trong trình duyệt (không lấy được toàn văn)")
    art = extract_article(decode(http_get(url)))
    if len(art["text"]) < 150:
        raise FetchError("trang không có đoạn văn đọc được (trang dùng JavaScript hoặc chặn bot)")
    return art
