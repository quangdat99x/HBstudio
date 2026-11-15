"""Paid generation APIs of the films: ElevenLabs (narration, sound effects) and fal.ai (images, video, and any other
model of its catalog). The keys are typed on the Settings page and kept in the settings table (or come from the
environment). Claude never sees them: headless turns run gen.py, which calls the functions here. Standard library only.
"""
from __future__ import annotations

import base64
import json
import mimetypes
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from . import config, db

UA = "CreaterVid/1.0"


class ApiError(Exception):
    def __init__(self, message: str, status: int | None = None, code: str | None = None):
        super().__init__(message)
        self.status, self.code = status, code


# ---------------------------------------------------------------- keys, settings
def key(name: str) -> str:
    """API key from the Settings page, else from the environment (ELEVENLABS_API_KEY, FAL_KEY)."""
    return (db.get_setting(name) or "").strip() or os.environ.get(config.SECRET_ENV.get(name, ""), "").strip()


def has_key(name: str) -> bool:
    return bool(key(name))


def set_key(name: str, value: str | None) -> None:
    if name not in config.SECRET_KEYS:
        raise ValueError("không có key này")
    db.set_setting(name, (value or "").strip())


def voices_map() -> dict:
    try:
        data = json.loads(db.get_setting("voices") or "{}")
    except ValueError:
        data = {}
    return data if isinstance(data, dict) else {}


def voice_for(language: str | None) -> dict:
    """Narrator of a video language: the language's own voice, else the English one."""
    m = voices_map()
    lang = (language or "en").lower().split("-")[0]
    return m.get(lang) or m.get("en") or {}


def set_voice(language: str, voice: dict | None) -> dict:
    m = voices_map()
    lang = (language or "").strip().lower()
    if not re.fullmatch(r"[a-z]{2,3}", lang):
        raise ValueError("mã ngôn ngữ phải là 2–3 chữ cái (en, ru, vi…)")
    if voice and (voice.get("id") or "").strip():
        m[lang] = {k: str(voice[k]).strip() for k in ("id", "name", "owner") if voice.get(k)}
    else:
        m.pop(lang, None)
    db.set_setting("voices", json.dumps(m, ensure_ascii=False))
    return m


def status() -> dict:
    try:
        data = json.loads(db.get_setting("provider_status") or "{}")
    except ValueError:
        data = {}
    return data if isinstance(data, dict) else {}


def _save_status(provider: str, result: dict) -> None:
    data = status()
    data[provider] = result
    db.set_setting("provider_status", json.dumps(data, ensure_ascii=False))


# ---------------------------------------------------------------- HTTP
def _error_text(body: bytes) -> tuple[str, str | None]:
    """Readable message (and machine code) of an API error body: ElevenLabs {"detail": {"status", "message"}},
    fal {"detail": "..."} or validation lists."""
    try:
        data = json.loads(body.decode("utf-8", "replace"))
    except ValueError:
        return body.decode("utf-8", "replace").strip()[:400], None
    if isinstance(data, dict) and isinstance(data.get("error"), dict):          # fal: {"error": {"type", "message"}}
        return str(data["error"].get("message") or data["error"])[:400], data["error"].get("type")
    detail = data.get("detail", data) if isinstance(data, dict) else data
    if isinstance(detail, dict):
        return str(detail.get("message") or detail.get("msg") or detail)[:400], detail.get("status") or detail.get("code")
    if isinstance(detail, list) and detail:
        parts = []
        for d in detail[:4]:
            if isinstance(d, dict):
                loc = ".".join(str(x) for x in d.get("loc", []) if x != "body")
                parts.append(f"{loc}: {d.get('msg') or d.get('message') or d}" if loc else str(d.get("msg") or d))
            else:
                parts.append(str(d))
        return "; ".join(parts)[:400], None
    return str(detail)[:400], (data.get("error_type") if isinstance(data, dict) else None)


def request(method: str, url: str, headers: dict, body=None, timeout: int = 120) -> tuple[int, bytes, dict]:
    data = None
    hdr = {"User-Agent": UA, **headers}
    if body is not None:
        data = body if isinstance(body, bytes) else json.dumps(body).encode("utf-8")
        hdr.setdefault("Content-Type", "application/json")
    req = urllib.request.Request(url, data=data, headers=hdr, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read(), {k.lower(): v for k, v in r.headers.items()}
    except urllib.error.HTTPError as e:
        msg, code = _error_text(e.read() or b"")
        raise ApiError(f"HTTP {e.code}: {msg}", e.code, code) from e
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise ApiError(f"không kết nối được: {getattr(e, 'reason', e)}") from e


def _json(method: str, url: str, headers: dict, body=None, timeout: int = 120):
    _, raw, _ = request(method, url, headers, body, timeout)
    return json.loads(raw.decode("utf-8")) if raw else {}


def download(url: str, out: Path, timeout: int = 600) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    tmp = out.with_suffix(out.suffix + ".part")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r, open(tmp, "wb") as f:
            while True:
                chunk = r.read(1 << 20)
                if not chunk:
                    break
                f.write(chunk)
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        tmp.unlink(missing_ok=True)
        raise ApiError(f"tải file thất bại: {getattr(e, 'reason', e)}") from e
    tmp.replace(out)
    return out


def data_uri(path: Path) -> str:
    """Local file as a data URI (fal accepts these wherever it wants a file URL)."""
    path = Path(path)
    if not path.is_file():
        raise ApiError(f"không thấy file {path}")
    if path.stat().st_size > 40 * 1024 * 1024:
        raise ApiError(f"file quá lớn để gửi kèm ({path.stat().st_size / 1e6:.0f} MB > 40 MB): {path.name}")
    mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    return f"data:{mime};base64," + base64.b64encode(path.read_bytes()).decode("ascii")


# ---------------------------------------------------------------- ElevenLabs
EL_DEFAULT_BASE = "https://api.elevenlabs.io"


def el_base() -> str:
    """ElevenLabs address from Settings (a reseller's), without a trailing /v1: the paths below carry it."""
    base = (db.get_setting("elevenlabs_base_url") or "").strip().rstrip("/") or EL_DEFAULT_BASE
    return base[:-3] if base.lower().endswith("/v1") else base


# model_id: (label, USD per 1,000 characters at the API list price, characters per request, audio tags understood)
TTS_MODELS = {
    "eleven_v4": ("Eleven v4", 0.08, 10000, True),
    "eleven_v4_turbo": ("Eleven v4 Turbo", 0.04, 5000, True),
    "eleven_v3": ("Eleven v3", 0.08, 5000, True),
    "eleven_multilingual_v2": ("Multilingual v2", 0.08, 10000, False),
    "eleven_flash_v2_5": ("Flash v2.5", 0.04, 40000, False),
}
SFX_USD_PER_MIN = 0.12
_TAG = re.compile(r"\[[^\]\n]{1,40}\]")


def _el_headers() -> dict:
    k = key("elevenlabs_api_key")
    if not k:
        raise ApiError("chưa có ElevenLabs API key: điền ở Cài đặt → API tạo nguyên liệu", code="no_key")
    return {"xi-api-key": k}


def tts_model(model_id: str | None = None) -> tuple[str, tuple]:
    mid = (model_id or db.get_setting("tts_model") or "eleven_v4").strip()
    return mid, TTS_MODELS.get(mid, (mid, 0.08, 5000, False))


def tts_usd(chars: int, model_id: str) -> float:
    return round(chars / 1000 * tts_model(model_id)[1][1], 4)


def el_subscription(k: str | None = None, base: str | None = None) -> dict:
    hdr = {"xi-api-key": k} if k else _el_headers()
    return _json("GET", f"{base or el_base()}/v1/user/subscription", hdr, timeout=30)


def _el_probe(k: str | None = None, base: str | None = None) -> dict:
    """Plan and characters left of a key (the active one by default) at an address."""
    base = base or el_base()
    hdr = {"xi-api-key": k} if k else _el_headers()
    try:
        s = el_subscription(k, base)
    except ApiError as e:
        # a reseller address often has no /user/subscription: the key still works if the model list answers
        try:
            models = _json("GET", f"{base}/v1/models", hdr, timeout=30)
        except ApiError:
            return {"ok": False, "error": str(e), "at": _now()}
        ids = [m.get("model_id") for m in models if isinstance(m, dict) and m.get("model_id")]             if isinstance(models, list) else []
        return {"ok": True, "tier": "không rõ (địa chỉ trung gian không báo gói)", "used": 0, "limit": 0,
                "left": 0, "reset": None, "models": ids, "at": _now()}
    used, limit = s.get("character_count") or 0, s.get("character_limit") or 0
    reset = s.get("next_character_count_reset_unix")
    return {"ok": True, "tier": s.get("tier"), "status": s.get("status"), "used": used, "limit": limit,
            "left": max(0, limit - used), "reset": time.strftime("%Y-%m-%d", time.localtime(reset)) if reset else None,
            "at": _now()}


def el_check() -> dict:
    """Is the active key valid, which plan, how many characters are left this period."""
    res = _el_probe()
    _save_status("elevenlabs", res)
    active = db.get_setting("elevenlabs_key_active") or ""
    keys = _el_keys_raw()
    for e in keys:
        if e["id"] == active:
            e["status"] = res
            _el_keys_save(keys)
    return res


# ---------------------------------------------------------------- several ElevenLabs keys
# Kept as a JSON list in the secret setting elevenlabs_keys: [{"id", "label", "key", "base_url", "status"}].
# The chosen one is copied into elevenlabs_api_key / elevenlabs_base_url, which everything else reads
# (gen.py, Hổ Báo Studio through gen.py, voice-dub), and its id is kept in elevenlabs_key_active.
def _el_keys_raw() -> list[dict]:
    try:
        data = json.loads(db.get_setting("elevenlabs_keys") or "[]")
    except ValueError:
        data = []
    keys = [e for e in data if isinstance(e, dict) and e.get("id") and e.get("key")] if isinstance(data, list) else []
    cur = (db.get_setting("elevenlabs_api_key") or "").strip()
    if cur and not any(e["key"] == cur for e in keys):       # the key saved before the list existed joins it
        keys.insert(0, {"id": _el_new_id(keys), "label": "Key đang dùng", "key": cur,
                        "base_url": (db.get_setting("elevenlabs_base_url") or "").strip(),
                        "status": status().get("elevenlabs")})
        _el_keys_save(keys)
        db.set_setting("elevenlabs_key_active", keys[0]["id"])
    return keys


def _el_keys_save(keys: list[dict]) -> None:
    db.set_setting("elevenlabs_keys", json.dumps(keys, ensure_ascii=False))


def _el_new_id(keys: list[dict]) -> str:
    n = 1
    while f"k{n}" in {e["id"] for e in keys}:
        n += 1
    return f"k{n}"


def _el_entry_base(e: dict) -> str:
    base = (e.get("base_url") or "").strip().rstrip("/") or EL_DEFAULT_BASE
    return base[:-3] if base.lower().endswith("/v1") else base


def el_keys() -> list[dict]:
    """The list for the browser: never the key itself, only its last 4 characters."""
    keys = _el_keys_raw()                      # first: it may take in the key saved before the list existed
    active = db.get_setting("elevenlabs_key_active") or ""
    cur = (db.get_setting("elevenlabs_api_key") or "").strip()
    return [{"id": e["id"], "label": e.get("label") or e["id"], "hint": "••••" + e["key"][-4:],
             "base_url": _el_entry_base(e), "active": e["id"] == active and e["key"] == cur,
             "status": e.get("status")} for e in keys]


def el_key_add(label: str, k: str, base_url: str = "") -> dict:
    k = (k or "").strip().strip("\"'").strip()
    base_url = (base_url or "").strip().rstrip("/")
    if not k or any(ch.isspace() for ch in k) or len(k) < 20:
        raise ValueError("key không hợp lệ (có dấu cách hoặc quá ngắn): dán đúng một dòng key")
    if base_url and not base_url.startswith(("http://", "https://")):
        raise ValueError("Base URL phải bắt đầu bằng https://")
    keys = _el_keys_raw()
    if any(e["key"] == k for e in keys):
        raise ValueError("key này đã có trong danh sách")
    e = {"id": _el_new_id(keys), "label": (label or "").strip()[:40] or f"Key {len(keys) + 1}", "key": k,
         "base_url": base_url}
    e["status"] = _el_probe(k, _el_entry_base(e))
    keys.append(e)
    _el_keys_save(keys)
    if not (db.get_setting("elevenlabs_api_key") or "").strip():    # the first key is used right away
        el_key_use(e["id"])
    return e["status"]


def el_key_check(key_id: str | None = None) -> None:
    """Refresh the credit of one key, or of every key."""
    keys = _el_keys_raw()
    active = db.get_setting("elevenlabs_key_active") or ""
    for e in keys:
        if key_id in (None, e["id"]):
            e["status"] = _el_probe(e["key"], _el_entry_base(e))
            if e["id"] == active:
                _save_status("elevenlabs", e["status"])
    _el_keys_save(keys)


def el_key_use(key_id: str) -> None:
    keys = _el_keys_raw()
    e = next((x for x in keys if x["id"] == key_id), None)
    if not e:
        raise ValueError("không thấy key này")
    db.set_setting("elevenlabs_api_key", e["key"])
    db.set_setting("elevenlabs_base_url", _el_entry_base(e))
    db.set_setting("elevenlabs_key_active", e["id"])
    if e.get("status"):
        _save_status("elevenlabs", e["status"])


def el_key_remove(key_id: str) -> None:
    keys = _el_keys_raw()
    gone = next((x for x in keys if x["id"] == key_id), None)
    if not gone:
        return
    keys = [x for x in keys if x["id"] != key_id]
    in_use = (db.get_setting("elevenlabs_api_key") or "").strip() == gone["key"]
    if in_use:                                 # cleared first, or the list would take it back in as the key in use
        db.set_setting("elevenlabs_api_key", "")
    _el_keys_save(keys)
    if in_use:                                 # the next key takes over
        if keys:
            el_key_use(keys[0]["id"])
        else:
            db.set_setting("elevenlabs_api_key", "")
            db.set_setting("elevenlabs_base_url", EL_DEFAULT_BASE)
            db.set_setting("elevenlabs_key_active", "")


def _split_text(text: str, limit: int) -> list[str]:
    """Paragraph-sized pieces under the per-request limit (a sentence never broken in two)."""
    if len(text) <= limit:
        return [text]
    units: list[tuple[str, str]] = []                  # (text, separator before it)
    for para in re.split(r"\n\s*\n", text.strip()):
        sentences = [para] if len(para) <= limit else re.split(r"(?<=[.!?…])\s+", para)
        units += [(s, "\n\n" if i == 0 else " ") for i, s in enumerate(sentences)]
    pieces, cur = [], ""
    for u, sep in units:
        if cur and len(cur) + len(sep) + len(u) > limit:
            pieces.append(cur)
            cur = u
        else:
            cur = cur + sep + u if cur else u
    if cur:
        pieces.append(cur)
    return pieces


def el_tts(text: str, voice_id: str, out: Path, *, model_id: str | None = None, language: str | None = None,
           voice_settings: dict | None = None, seed: int | None = None, timestamps: bool = False,
           previous_text: str | None = None, next_text: str | None = None) -> dict:
    """One request: the mp3 at `out`, plus `<out>.alignment.json` (character times) when timestamps is set."""
    mid, meta = tts_model(model_id)
    if not meta[3]:
        text = _TAG.sub("", text)                       # this model would read "[grave]" aloud
    body = {"text": text, "model_id": mid}
    if language:
        body["language_code"] = language
    if voice_settings:
        body["voice_settings"] = {k: v for k, v in voice_settings.items() if v is not None}
    if seed is not None:
        body["seed"] = int(seed)
    if previous_text:
        body["previous_text"] = previous_text[-1000:]
    if next_text:
        body["next_text"] = next_text[:1000]
    path = f"/v1/text-to-speech/{urllib.parse.quote(voice_id)}" + ("/with-timestamps" if timestamps else "")
    status_, raw, hdr = request("POST", f"{el_base()}{path}?output_format=mp3_44100_128",
                                {**_el_headers(), "Accept": "application/json" if timestamps else "audio/mpeg"},
                                body, timeout=600)
    out.parent.mkdir(parents=True, exist_ok=True)
    alignment = None
    if timestamps:
        data = json.loads(raw.decode("utf-8"))
        out.write_bytes(base64.b64decode(data.get("audio_base64") or ""))
        alignment = data.get("alignment") or data.get("normalized_alignment")
    else:
        out.write_bytes(raw)
    chars = int(hdr.get("character-cost") or hdr.get("x-character-count") or len(text))
    return {"file": out, "chars": chars, "request_id": hdr.get("request-id"), "alignment": alignment, "model": mid}


def el_library_voices(language: str | None = None, search: str | None = None, gender: str | None = None,
                      page_size: int = 30, use_cases: str | None = None, sort: str | None = None) -> list[dict]:
    params = {"page_size": str(min(100, max(1, page_size)))}
    for k, v in (("language", language), ("search", search), ("gender", gender), ("use_cases", use_cases), ("sort", sort)):
        if v:
            params[k] = v
    data = _json("GET", f"{el_base()}/v1/shared-voices?" + urllib.parse.urlencode(params), _el_headers(), timeout=30)
    out = []
    for v in data.get("voices") or []:
        out.append({"id": v.get("voice_id"), "owner": v.get("public_owner_id"), "name": v.get("name"),
                    "gender": v.get("gender"), "age": v.get("age"), "accent": v.get("accent"), "language": v.get("language"),
                    "use_case": v.get("use_case"), "description": (v.get("description") or "")[:300],
                    "preview": v.get("preview_url"), "free_ok": v.get("free_users_allowed"), "library": True})
    return out


def el_my_voices() -> list[dict]:
    data = _json("GET", f"{el_base()}/v1/voices", _el_headers(), timeout=30)
    out = []
    for v in data.get("voices") or []:
        labels = v.get("labels") or {}
        out.append({"id": v.get("voice_id"), "name": v.get("name"), "category": v.get("category"),
                    "gender": labels.get("gender"), "accent": labels.get("accent"), "language": labels.get("language"),
                    "description": (v.get("description") or "")[:300], "preview": v.get("preview_url"), "library": False})
    return out


def el_add_voice(owner_id: str, voice_id: str, name: str) -> dict:
    """Add a library voice to the account's voices (needed before the API can speak with it on some plans)."""
    return _json("POST", f"{el_base()}/v1/voices/add/{urllib.parse.quote(owner_id)}/{urllib.parse.quote(voice_id)}",
                 _el_headers(), {"new_name": name[:100]}, timeout=60)


def el_sfx(prompt: str, seconds: float | None, out: Path, influence: float | None = None) -> dict:
    body = {"text": prompt}
    if seconds:
        body["duration_seconds"] = max(0.5, min(30.0, float(seconds)))
    if influence is not None:
        body["prompt_influence"] = float(influence)
    _, raw, hdr = request("POST", f"{el_base()}/v1/sound-generation?output_format=mp3_44100_128",
                          {**_el_headers(), "Accept": "audio/mpeg"}, body, timeout=300)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(raw)
    return {"file": out, "request_id": hdr.get("request-id")}


# ---------------------------------------------------------------- fal.ai
FAL_QUEUE = "https://queue.fal.run"
FAL_API = "https://api.fal.ai/v1"
FAL_OPENAPI = "https://fal.ai/api/openapi/queue/openapi.json?endpoint_id="
# short names Claude and the Settings page may use instead of endpoint ids
ALIASES = {
    "seedream": "bytedance/seedream/v5/flash/text-to-image",
    "nano2": "fal-ai/nano-banana-2", "nano2-edit": "fal-ai/nano-banana-2/edit",
    "nano-pro": "fal-ai/nano-banana-pro", "nano-pro-edit": "fal-ai/nano-banana-pro/edit",
    "gpt": "openai/gpt-image-2.5/sunburst/text-to-image", "gpt-edit": "openai/gpt-image-2.5/sunburst/edit",
    "kling": "fal-ai/kling-video/v3/standard/image-to-video", "kling-pro": "fal-ai/kling-video/v3/pro/image-to-video",
    "seedance": "bytedance/seedance-2.5/image-to-video", "birefnet": "fal-ai/birefnet/v2",
    # called directly with the OpenAI / Google key instead of through fal
    "openai": "openai:gpt-image-2.5-sunburst", "openai-flare": "openai:gpt-image-2.5-flare",
    "openai-mini": "openai:gpt-image-1-mini",
    "gemini-pro": "google:gemini-3-pro-image", "gemini-flash": "google:gemini-3.1-flash-image",
    "gemini-lite": "google:gemini-3.1-flash-lite-image",
    # gemini.google.com in the app's own Chrome profile, with the user's Gemini plan (no API cost): creater/gemini_web.py
    "gemini-web": "gemini-web:", "gemini-web-argon": "gemini-web:Argon", "gemini-web-pro": "gemini-web:Pro",
}
DIRECT = ("openai:", "google:")
WEB = "gemini-web:"
SETTING_ALIASES = {"draft": "image_model_draft", "main": "image_model", "edit": "image_model_edit", "video": "video_model"}


def endpoint(name: str) -> str:
    name = (name or "").strip()
    if name in SETTING_ALIASES:
        return db.get_setting(SETTING_ALIASES[name])
    return ALIASES.get(name, name)


def _fal_headers() -> dict:
    k = key("fal_api_key")
    if not k:
        raise ApiError("chưa có fal.ai API key: điền ở Cài đặt → API tạo nguyên liệu", code="no_key")
    return {"Authorization": f"Key {k}"}


def _cache(name: str) -> Path:
    d = config.WORK_DIR / "fal"
    d.mkdir(parents=True, exist_ok=True)
    return d / (re.sub(r"[^\w.-]+", "_", name) + ".json")


def _cached(name: str, max_age: float, fetch):
    path = _cache(name)
    if path.exists() and time.time() - path.stat().st_mtime < max_age:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except ValueError:
            pass
    data = fetch()
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return data


def _resolve(schema: dict, comps: dict) -> dict:
    """Follow $ref / allOf / anyOf one level so a property shows its real type and enum."""
    if "$ref" in schema:
        return comps.get(schema["$ref"].split("/")[-1], {})
    for k in ("allOf", "anyOf", "oneOf"):
        for sub in schema.get(k) or []:
            if "$ref" in sub:
                ref = comps.get(sub["$ref"].split("/")[-1], {})
                return {**ref, **{x: y for x, y in schema.items() if x not in (k,)}}
            if sub.get("enum") or (sub.get("type") and sub.get("type") != "null"):
                return {**sub, **{x: y for x, y in schema.items() if x not in (k,)}}
    return schema


def fal_schema(ep: str) -> dict:
    """Input parameters of a fal endpoint: {"props": {name: {type, enum, default, description}}, "required": [...]}."""
    def fetch():
        spec = _json("GET", FAL_OPENAPI + urllib.parse.quote(ep, safe=""), {}, timeout=60)
        comps = (spec.get("components") or {}).get("schemas") or {}
        inp = None
        for ops in (spec.get("paths") or {}).values():
            post = ops.get("post") or {}
            ref = (((post.get("requestBody") or {}).get("content") or {}).get("application/json") or {}).get("schema", {})
            if ref:
                inp = _resolve(ref, comps)
                break
        if not inp:
            raise ApiError(f"không đọc được tham số của {ep} (sai tên model?)")
        props = {}
        for name, p in (inp.get("properties") or {}).items():
            r = _resolve(p, comps)
            props[name] = {"type": r.get("type") or p.get("type"), "enum": r.get("enum"), "default": p.get("default"),
                           "description": (p.get("description") or r.get("description") or "")[:300],
                           "items": (r.get("items") or {}).get("type")}
        return {"endpoint": ep, "props": props, "required": inp.get("required") or []}
    return _cached("schema_" + ep, 7 * 86400, fetch)


def fal_price(ep: str) -> dict | None:
    """{"unit_price", "unit", "currency"} of an endpoint (needs the key), None when fal has no price for it."""
    def fetch():
        data = _json("GET", f"{FAL_API}/models/pricing?" + urllib.parse.urlencode({"endpoint_id": ep}), _fal_headers(), timeout=30)
        prices = data.get("prices") or []
        return prices[0] if prices else {}
    try:
        p = _cached("price_" + ep, 86400, fetch)
    except ApiError:
        return None
    return p or None


def fal_estimate_call(ep: str) -> float | None:
    """Average cost of one call of the endpoint, from fal's own history."""
    try:
        data = _json("POST", f"{FAL_API}/models/pricing/estimate", _fal_headers(),
                     {"estimate_type": "historical_api_price", "endpoints": {ep: {"call_quantity": 1}}}, timeout=30)
        return float(data.get("total_cost"))
    except (ApiError, TypeError, ValueError):
        return None


def fal_search(q: str = "", category: str = "", limit: int = 20) -> list[dict]:
    params = {"limit": str(limit), "status": "active"}
    if q:
        params["q"] = q
    if category:
        params["category"] = category
    hdr = _fal_headers() if has_key("fal_api_key") else {}
    data = _json("GET", f"{FAL_API}/models?" + urllib.parse.urlencode(params), hdr, timeout=30)
    return [{"endpoint": m.get("endpoint_id"), "name": (m.get("metadata") or {}).get("display_name"),
             "category": (m.get("metadata") or {}).get("category"), "date": ((m.get("metadata") or {}).get("date") or "")[:10],
             "description": ((m.get("metadata") or {}).get("description") or "")[:160]} for m in data.get("models") or []]


def fal_check() -> dict:
    """Is the key valid (a priced endpoint answers), and the credit balance when the key is allowed to read it."""
    ep = db.get_setting("image_model") or ALIASES["nano-pro"]
    try:
        _json("GET", f"{FAL_API}/models/pricing?" + urllib.parse.urlencode({"endpoint_id": ep}), _fal_headers(), timeout=30)
    except ApiError as e:
        res = {"ok": False, "error": str(e), "at": _now()}
        _save_status("fal", res)
        return res
    res = {"ok": True, "at": _now()}
    try:
        b = _json("GET", f"{FAL_API}/account/billing?expand=credits", _fal_headers(), timeout=30)
        credits = b.get("credits") or {}
        res.update(balance=credits.get("current_balance"), currency=credits.get("currency") or "USD", account=b.get("username"))
    except ApiError as e:
        res["balance_note"] = ("key thường không xem được số dư (cần ADMIN key)" if e.status in (401, 403)
                               else f"không đọc được số dư: {e}")
    _save_status("fal", res)
    return res


def fal_submit(ep: str, payload: dict) -> dict:
    return _json("POST", f"{FAL_QUEUE}/{ep}", _fal_headers(), payload, timeout=120)


def fal_wait(sub: dict, timeout: int = 900, on_status=None) -> dict:
    """Poll a queued request until it completes; returns the model's output JSON."""
    started, last = time.time(), None
    status_url, response_url = sub.get("status_url"), sub.get("response_url")
    if not status_url or not response_url:
        raise ApiError(f"fal không trả request_id: {str(sub)[:200]}")
    delay = 1.5
    while True:
        st = _json("GET", status_url + ("&" if "?" in status_url else "?") + "logs=0", _fal_headers(), timeout=60)
        state = st.get("status")
        if on_status and state != last:
            on_status(state, st)
        last = state
        if state == "COMPLETED":
            if st.get("error"):
                raise ApiError(f"model báo lỗi: {st.get('error')}", code=st.get("error_type"))
            return _json("GET", response_url, _fal_headers(), timeout=120)
        if state not in ("IN_QUEUE", "IN_PROGRESS"):
            raise ApiError(f"trạng thái lạ từ fal: {str(st)[:300]}")
        if time.time() - started > timeout:
            raise ApiError(f"quá {timeout // 60} phút chưa xong (request {sub.get('request_id')}): xem lại trên fal.ai, "
                           "không gửi lại ngay kẻo trả tiền hai lần", code="timeout")
        time.sleep(delay)
        delay = min(6.0, delay * 1.3)


def media_outputs(result) -> list[dict]:
    """Every file the model returned: images[], image, video, audio... (url + whatever size/duration fal reports)."""
    out = []

    def walk(x, key_=""):
        if isinstance(x, dict):
            if isinstance(x.get("url"), str) and x["url"].startswith(("http", "data:")):
                out.append({"url": x["url"], "kind": key_, "content_type": x.get("content_type"),
                            "width": x.get("width"), "height": x.get("height"), "duration": x.get("duration"),
                            "file_name": x.get("file_name")})
                return
            for k, v in x.items():
                walk(v, k)
        elif isinstance(x, list):
            for v in x:
                walk(v, key_)

    walk(result)
    return out


# ---------------------------------------------------------------- OpenAI (GPT Image, called directly)
OPENAI_BASE = "https://api.openai.com/v1"
# model: (text input, image input, image output) USD per 1M tokens (openai.com pricing, 2026-10)
OPENAI_IMAGE_MODELS = {
    "gpt-image-2.5-sunburst": (5.0, 8.0, 30.0),
    "gpt-image-2.5-flare": (5.0, 8.0, 30.0),
    "gpt-image-2": (5.0, 8.0, 30.0),
    "gpt-image-1.5": (5.0, 8.0, 32.0),
    "gpt-image-1-mini": (2.0, 2.5, 8.0),
}
# rough USD of one 1024×1024 image by quality, for the budget check before a call (the real cost comes from usage)
OPENAI_QUALITY_USD = {"low": 0.012, "medium": 0.045, "high": 0.17, "xhigh": 0.25, "max": 0.35, "auto": 0.17}


def _oa_headers() -> dict:
    k = key("openai_api_key")
    if not k:
        raise ApiError("chưa có OpenAI API key: điền ở Cài đặt → API tạo nguyên liệu", code="no_key")
    return {"Authorization": f"Bearer {k}"}


def _oa_base() -> str:
    """api.openai.com, or the /v1 address of an OpenAI-compatible service (keys sold as "Codex API" and the like)."""
    base = (db.get_setting("openai_base_url") or OPENAI_BASE).strip().rstrip("/")
    return base if base.startswith(("http://", "https://")) else OPENAI_BASE


def _oa_hint(e: ApiError) -> str:
    """Why an official-looking call fails with a key from a reseller."""
    k = key("openai_api_key")
    official = _oa_base() == OPENAI_BASE
    if e.status == 401 and official and k.startswith("sk-") and not k.startswith(("sk-proj-", "sk-svcacct-", "sk-admin-")):
        return (" · Key dạng sk-… không có 'proj' thường là key của dịch vụ trung gian (bán Codex/GPT qua server riêng), không "
                "phải key OpenAI: điền 'Base URL' của dịch vụ đó (dạng https://…/v1) rồi kiểm tra lại.")
    if e.status == 403 and official:
        return " · Tổ chức OpenAI cần được xác minh (platform.openai.com → Settings → Organization) mới dùng được GPT Image."
    return ""


def openai_check() -> dict:
    try:
        data = _json("GET", f"{_oa_base()}/models", _oa_headers(), timeout=30)
    except ApiError as e:
        res = {"ok": False, "error": str(e) + _oa_hint(e), "at": _now()}
        _save_status("openai", res)
        return res
    ids = [m.get("id") or "" for m in data.get("data") or []]
    models = sorted(i for i in ids if "image" in i)
    res = {"ok": True, "models": models, "base": _oa_base(), "at": _now()}
    if not models:
        res["note"] = (f"key dùng được nhưng nơi cấp key không có model tạo ảnh ({len(ids)} model khác: "
                       f"{', '.join(sorted(ids)[:6])}{'…' if len(ids) > 6 else ''}); key Codex thường chỉ dùng cho model viết code")
    _save_status("openai", res)
    return res


def _multipart(fields: dict, files: list[tuple[str, Path]]) -> tuple[bytes, str]:
    boundary = "----creater" + base64.b16encode(os.urandom(12)).decode().lower()
    out = bytearray()
    for name, value in fields.items():
        out += (f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n{value}\r\n").encode("utf-8")
    for name, path in files:
        mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        out += (f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"; filename=\"{path.name}\"\r\n"
                f"Content-Type: {mime}\r\n\r\n").encode("utf-8")
        out += path.read_bytes() + b"\r\n"
    out += f"--{boundary}--\r\n".encode("utf-8")
    return bytes(out), f"multipart/form-data; boundary={boundary}"


def openai_usd(model: str, usage: dict | None) -> float | None:
    prices = OPENAI_IMAGE_MODELS.get(model)
    if not prices or not usage:
        return None
    det = usage.get("input_tokens_details") or {}
    text_in = det.get("text_tokens", usage.get("input_tokens") or 0) if det else (usage.get("input_tokens") or 0)
    image_in = det.get("image_tokens") or 0
    return round((text_in * prices[0] + image_in * prices[1] + (usage.get("output_tokens") or 0) * prices[2]) / 1e6, 4)


def openai_image(model: str, prompt: str, refs: list[Path], *, size: str | None = None, quality: str | None = None,
                 n: int = 1, output_format: str | None = None, extra: dict | None = None, timeout: int = 600) -> dict:
    """Images API: generations, or edits when reference images are given. {"images": [(bytes, mime)], "usage", "usd"}."""
    body = {"model": model, "prompt": prompt, "n": max(1, n)}
    for k, v in (("size", size), ("quality", quality), ("output_format", output_format)):
        if v:
            body[k] = v
    body.update(extra or {})
    if refs:
        fields = {k: (json.dumps(v) if isinstance(v, (dict, list, bool)) else v) for k, v in body.items()}
        payload, ctype = _multipart(fields, [("image[]", Path(r)) for r in refs])
    try:
        if refs:
            _, raw, _ = request("POST", f"{_oa_base()}/images/edits", {**_oa_headers(), "Content-Type": ctype}, payload, timeout)
            data = json.loads(raw.decode("utf-8"))
        else:
            data = _json("POST", f"{_oa_base()}/images/generations", _oa_headers(), body, timeout)
    except ApiError as e:
        raise ApiError(str(e) + _oa_hint(e), e.status, e.code) from e
    mime = "image/" + {"jpeg": "jpeg", "webp": "webp"}.get(output_format or "png", "png")
    images = []
    for d in data.get("data") or []:
        if d.get("b64_json"):
            images.append((base64.b64decode(d["b64_json"]), mime))
        elif str(d.get("url") or "").startswith("http"):              # some compatible services answer with links
            _, raw, hdr = request("GET", d["url"], {}, timeout=timeout)
            images.append((raw, hdr.get("content-type") or mime))
    if not images:
        raise ApiError(f"OpenAI không trả ảnh: {str(data)[:300]}")
    return {"images": images, "usage": data.get("usage"), "usd": openai_usd(model, data.get("usage"))}


# ---------------------------------------------------------------- Google Gemini (Nano Banana, called directly)
GOOGLE_BASE = "https://generativelanguage.googleapis.com/v1beta"
# model: USD per image by imageSize (ai.google.dev pricing, 2026-10)
GOOGLE_IMAGE_MODELS = {
    "gemini-3-pro-image": {"1K": 0.134, "2K": 0.134, "4K": 0.24},
    "gemini-3.1-flash-image": {"512px": 0.045, "1K": 0.067, "2K": 0.101, "4K": 0.151},
    "gemini-3.1-flash-lite-image": {"1K": 0.0336},
    "gemini-2.5-flash-image": {"1K": 0.039},
}
GOOGLE_ASPECTS = ("1:1", "3:2", "2:3", "3:4", "4:3", "4:5", "5:4", "9:16", "16:9", "21:9")
GOOGLE_SIZES = ("512px", "1K", "2K", "4K")


def _g_headers() -> dict:
    k = key("google_api_key")
    if not k:
        raise ApiError("chưa có Google (Gemini) API key: điền ở Cài đặt → API tạo nguyên liệu", code="no_key")
    return {"x-goog-api-key": k}


def google_check() -> dict:
    try:
        data = _json("GET", f"{GOOGLE_BASE}/models?pageSize=1000", _g_headers(), timeout=30)
    except ApiError as e:
        res = {"ok": False, "error": str(e), "at": _now()}
        _save_status("google", res)
        return res
    models = sorted((m.get("name") or "").removeprefix("models/") for m in data.get("models") or []
                    if "image" in (m.get("name") or ""))
    res = {"ok": True, "models": models, "at": _now()}
    _save_status("google", res)
    return res


def google_usd(model: str, size: str | None) -> float | None:
    table = GOOGLE_IMAGE_MODELS.get(model) or GOOGLE_IMAGE_MODELS.get(model.removesuffix("-preview"))
    if not table:
        return None
    return table.get(size or "1K") or table.get("1K") or max(table.values())


def google_image(model: str, prompt: str, refs: list[Path], *, aspect: str | None = None, size: str | None = None,
                 extra: dict | None = None, timeout: int = 600) -> dict:
    """generateContent with image output: one image per call. {"images": [(bytes, mime)], "text", "usage"}."""
    parts = []
    for r in refs:
        r = Path(r)
        parts.append({"inline_data": {"mime_type": mimetypes.guess_type(r.name)[0] or "image/png",
                                      "data": base64.b64encode(r.read_bytes()).decode("ascii")}})
    parts.append({"text": prompt})
    image_config = {}
    if aspect:
        image_config["aspectRatio"] = aspect
    if size:
        image_config["imageSize"] = size
    image_config.update(extra or {})
    body = {"contents": [{"role": "user", "parts": parts}],
            "generationConfig": {"responseModalities": ["TEXT", "IMAGE"], **({"imageConfig": image_config} if image_config else {})}}
    try:
        data = _json("POST", f"{GOOGLE_BASE}/models/{urllib.parse.quote(model)}:generateContent", _g_headers(), body, timeout)
    except ApiError as e:
        if e.status == 404:
            raise ApiError(f"Google không có model {model} cho key này ({e}); xem danh sách bằng nút Kiểm tra ở Cài đặt "
                           "hoặc gen.py check", e.status) from e
        raise
    images, texts = [], []
    for cand in data.get("candidates") or []:
        for part in (cand.get("content") or {}).get("parts") or []:
            blob = part.get("inlineData") or part.get("inline_data")
            if blob and blob.get("data"):
                images.append((base64.b64decode(blob["data"]), blob.get("mimeType") or blob.get("mime_type") or "image/png"))
            elif part.get("text"):
                texts.append(part["text"])
    if not images:
        cand = (data.get("candidates") or [{}])[0]
        why = cand.get("finishReason") or (data.get("promptFeedback") or {}).get("blockReason") or "không rõ"
        raise ApiError(f"Google không trả ảnh (lý do: {why}){': ' + ' '.join(texts)[:200] if texts else ''}")
    return {"images": images, "text": " ".join(texts).strip(), "usage": data.get("usageMetadata")}


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")
