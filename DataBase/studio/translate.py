"""Translate selected text to Vietnamese with the official Google Cloud Translation API (Basic, v2).

The keyless translate_a endpoint is blocked for this network by Google's automated-traffic protection, so
Studio only uses the official API with the user's own key (setting `google_translate_api_key`, or the
environment variable GOOGLE_TRANSLATE_API_KEY). Without a key the UI opens translate.google.com instead.
"""
from __future__ import annotations

import html
import os
import re
import threading
import urllib.parse
from collections import OrderedDict

import requests

from . import db

API_URL = "https://translation.googleapis.com/language/translate/v2"
WEB_URL = "https://translate.google.com/"
MAX_CHARS = 15000          # longest selection accepted in one request from the UI
CHUNK = 4500               # Google recommends at most ~5K characters per text item
_cache: "OrderedDict[tuple, dict]" = OrderedDict()
_lock = threading.Lock()


class NoKey(RuntimeError):
    pass


def api_key() -> str:
    return (db.get_setting("google_translate_api_key") or os.environ.get("GOOGLE_TRANSLATE_API_KEY") or "").strip()


def configured() -> bool:
    return bool(api_key())


def _chunks(text: str, size: int = CHUNK) -> list[str]:
    """Split on paragraph, then sentence boundaries so each piece stays under `size` characters."""
    if len(text) <= size:
        return [text]
    parts, cur = [], ""
    for piece in re.split(r"(?<=[\n.!?])\s+", text):
        while len(piece) > size:                       # a single huge sentence: hard split
            parts.append(piece[:size])
            piece = piece[size:]
        if len(cur) + len(piece) + 1 > size and cur:
            parts.append(cur)
            cur = piece
        else:
            cur = f"{cur} {piece}" if cur else piece
    if cur:
        parts.append(cur)
    return parts


def translate(text: str, target: str = "vi", source: str | None = None) -> dict:
    text = (text or "").strip()
    if not text:
        return {"translation": "", "source": None}
    if len(text) > MAX_CHARS:
        raise ValueError(f"đoạn chọn dài {len(text)} ký tự, tối đa {MAX_CHARS}")
    key = api_key()
    if not key:
        raise NoKey("chưa có Google API key")
    ck = (text, target, source or "")
    with _lock:
        if ck in _cache:
            _cache.move_to_end(ck)
            return dict(_cache[ck], cached=True)
    body = {"q": _chunks(text), "target": target, "format": "text"}
    if source:
        body["source"] = source
    r = requests.post(API_URL, params={"key": key}, json=body, timeout=30)
    data = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
    if r.status_code != 200:
        raise RuntimeError(explain_error(r.status_code, data))
    items = (data.get("data") or {}).get("translations") or []
    out = {
        "translation": " ".join(html.unescape(t.get("translatedText") or "") for t in items).strip(),
        "source": (items[0].get("detectedSourceLanguage") if items else None) or source,
        "chars": len(text),
    }
    with _lock:
        _cache[ck] = out
        while len(_cache) > 2000:
            _cache.popitem(last=False)
    return out


_HINTS = [
    (("userratelimitexceeded", "ratelimitexceeded", "resource_exhausted", "quota"),
     "Project Google Cloud của key đang có hạn mức dịch bằng 0. Hay gặp nhất là project chưa gắn tài khoản thanh toán: "
     "vào Google Cloud Console → Billing, gắn tài khoản thanh toán cho đúng project chứa key. Nếu đã gắn, vào IAM & Admin → "
     "Quotas, lọc Cloud Translation API và xem các hạn mức ký tự có đang bằng 0 không. Sửa xong đợi vài phút rồi thử lại."),
    (("billing",), "Project của key chưa bật thanh toán: gắn tài khoản thanh toán cho project trong Google Cloud Console → Billing."),
    (("accessnotconfigured", "service_disabled", "has not been used", "is disabled"),
     "Project của key chưa bật Cloud Translation API: vào APIs & Services → Library, tìm Cloud Translation API và bấm Enable."),
    (("api_key_service_blocked", "blocked", "iprefererblocked", "api_key_http_referrer_blocked"),
     "Key đang bị giới hạn không cho gọi Cloud Translation API: vào Credentials, sửa phần API restrictions của key."),
    (("keyinvalid", "api key not valid", "api_key_invalid"), "Key không hợp lệ: kiểm tra lại, dán đủ cả chuỗi bắt đầu bằng AIza."),
]


def explain_error(status: int, data) -> str:
    """Google's error plus a Vietnamese hint on how to fix it in the Cloud Console."""
    err = data.get("error") if isinstance(data, dict) else None
    err = err if isinstance(err, dict) else {}
    message = err.get("message") or f"HTTP {status}"
    blob = " ".join([message, str(err.get("status") or "")] +
                    [f"{e.get('reason', '')} {e.get('domain', '')}" for e in err.get("errors") or [] if isinstance(e, dict)] +
                    [str(d.get("reason", "")) for d in err.get("details") or [] if isinstance(d, dict)]).lower()
    for needles, hint in _HINTS:
        if any(n in blob for n in needles):
            return f"{message} (HTTP {status}). {hint}"
    return f"{message} (HTTP {status})"


def web_url(text: str, target: str = "vi") -> str:
    """translate.google.com with the text pre-filled (the site accepts about 5,000 characters)."""
    q = urllib.parse.urlencode({"sl": "auto", "tl": target, "text": (text or "")[:4500], "op": "translate"})
    return f"{WEB_URL}?{q}"
