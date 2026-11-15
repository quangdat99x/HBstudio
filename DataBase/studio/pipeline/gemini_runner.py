"""Call the Gemini API (generateContent) with the same result shape as claude_runner.run.

Used when a step's model setting starts with "gemini" (for now only "Viết Title"). Gemini runs in one request
with no tools on the machine: everything it needs goes into the prompt, and it answers with text only.
API key: setting `gemini_api_key`, else env GEMINI_API_KEY, else E:\\Tool\\viet-tittle-gemini\\.env.
Google Search grounding is tried first; a free-tier key rejects it (429), so the call is retried without it.
"""
from __future__ import annotations

import json
import logging
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from .. import config, db

log = logging.getLogger("studio.gemini")
API = "https://generativelanguage.googleapis.com/v1beta"
ENV_FILE = config.TOOLS_ROOT / "viet-tittle-gemini" / ".env"
RETRY_WAIT = (20, 60)                # seconds between attempts while a model is overloaded (503)
# The free tier allows ~20 requests/day PER MODEL and every failed attempt counts, so an overloaded or used-up Flash
# model hands over to the next one instead of retrying many times.
FLASH_FALLBACK = ("gemini-3.5-flash", "gemini-3-flash-preview", "gemini-flash-lite-latest")
_search_blocked = False              # a free key rejects Google Search: stop asking once seen (saves daily requests)
_RE_RETRY = re.compile(r"retry in ([0-9hms.]+)", re.I)


def _retry_hint(msg: str) -> str:
    m = _RE_RETRY.search(msg or "")
    if not m:
        return ""
    t = m.group(1).rstrip(".")
    h, mins = re.search(r"(\d+)h", t), re.search(r"(\d+)m", t)
    if not h and not mins:
        return ", gọi lại được sau ít phút"
    return ", gọi lại được sau " + " ".join(x for x in (f"{h.group(1)} giờ" if h else "", f"{mins.group(1)} phút" if mins else "") if x)


def is_gemini(model: str | None) -> bool:
    return (model or "").strip().lower().startswith("gemini")


def api_key() -> str:
    key = (db.get_setting("gemini_api_key") or os.environ.get("GEMINI_API_KEY") or "").strip()
    if not key and ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("GEMINI_API_KEY="):
                key = line.split("=", 1)[1].strip().strip('"')
    return key


def configured() -> bool:
    return bool(api_key())


_NO_SEARCH = ("Gemini không dùng được Google Search với key này, chạy không có Search "
              "(không tra được chính tả tên riêng và link ảnh)")


class GeminiError(RuntimeError):
    def __init__(self, code: int, message: str):
        super().__init__(f"Gemini HTTP {code}: {message}")
        self.code = code


def _post(path: str, body: dict, key: str, timeout: int) -> dict:
    base = base_url() or API                           # a Gemini-native reseller (…/v1beta) takes Google's format
    headers = {"Content-Type": "application/json", "x-goog-api-key": key}
    if base != API:
        headers["Authorization"] = f"Bearer {key}"
    req = urllib.request.Request(f"{base}/{path}", data=json.dumps(body).encode(), headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "replace")
        try:
            msg = json.loads(raw)["error"]["message"]
        except (ValueError, KeyError, TypeError):
            msg = raw
        raise GeminiError(e.code, msg.strip()[:600]) from None


def base_url() -> str:
    """Empty = Google's own API. A reseller key ("sk-…") needs the seller's address: an OpenAI-compatible …/v1
    (chat/completions), or a Gemini-native …/v1beta."""
    return (db.get_setting("gemini_base_url") or "").strip().rstrip("/")


def _run_compat(base: str, system: str, contents: list[dict], key: str, model: str, timeout: int, log_path,
                say, stop_flag, started: float) -> dict:
    """OpenAI-compatible reseller: POST {base}/chat/completions (a bare host gets /v1, the usual OpenAI path)."""
    if not re.search(r"/v\d+[a-z]*(/|$)", urllib.parse.urlsplit(base).path):
        base += "/v1"
    messages = [{"role": "system", "content": system}] + [
        {"role": "assistant" if c.get("role") == "model" else "user",
         "content": "".join(p.get("text", "") for p in c.get("parts", []))} for c in contents]
    body = json.dumps({"model": model, "messages": messages, "temperature": 0.7}).encode()
    waits = list(RETRY_WAIT)
    while True:
        if stop_flag and stop_flag():
            return {"ok": False, "error": "đã hủy", "text": "", "texts": []}
        say(f"gọi {model} qua {urllib.parse.urlsplit(base).netloc}")
        req = urllib.request.Request(f"{base}/chat/completions", data=body, headers={
            "Content-Type": "application/json", "Authorization": f"Bearer {key}"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                res = json.load(r)
            break
        except urllib.error.HTTPError as e:
            raw = e.read().decode("utf-8", "replace")
            try:
                msg = json.loads(raw)["error"]["message"]
            except (ValueError, KeyError, TypeError):
                msg = raw
            log.warning("gemini (compat) %s: %s %s", model, e.code, msg[:300])
            if e.code in (429, 500, 502, 503, 504) and waits:
                w = waits.pop(0)
                say(f"{model} bận (HTTP {e.code}), thử lại sau {w}s")
                time.sleep(w)
                continue
            return {"ok": False, "error": f"Gemini (máy chủ {urllib.parse.urlsplit(base).netloc}) HTTP {e.code}: "
                                          f"{msg.strip()[:600]}", "text": "", "texts": [], "models": [model],
                    "duration_sec": round(time.time() - started, 1)}
        except (urllib.error.URLError, TimeoutError) as e:
            return {"ok": False, "error": f"không gọi được {base}: {e}", "text": "", "texts": [], "models": [model],
                    "duration_sec": round(time.time() - started, 1)}
    if log_path:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    choice = (res.get("choices") or [{}])[0]
    text = (choice.get("message") or {}).get("content") or ""
    if isinstance(text, list):
        text = "".join(p.get("text", "") for p in text if isinstance(p, dict))
    u = res.get("usage") or {}
    finish = choice.get("finish_reason")
    ok = bool(text.strip()) and finish in (None, "stop", "STOP")
    return {"ok": ok, "error": None if ok else f"Gemini dừng với lý do {finish or 'không rõ'}"
                                                + ("" if text.strip() else ", không có nội dung"),
            "text": text, "texts": [text], "models": [res.get("model") or model], "cost_usd": None,
            "usage": {"input_tokens": u.get("prompt_tokens") or 0, "output_tokens": u.get("completion_tokens") or 0},
            "duration_sec": round(time.time() - started, 1), "session_id": None,
            "warnings": ["chạy qua máy chủ bán key, không có Google Search (không tra được chính tả tên riêng và link ảnh)"]}


def run(system: str, contents: list[dict], *, model: str, search: bool = True, timeout: int = 15 * 60,
        log_path: Path | None = None, update=None, stop_flag=None) -> dict:
    """contents: Gemini turns [{"role": "user"|"model", "parts": [{"text": ...}]}].
    Returns {ok, error, text, texts, usage, models, cost_usd, duration_sec, session_id, warnings}."""
    started = time.time()
    key = api_key()
    if not key:
        return {"ok": False, "error": f"chưa có Gemini API key (trang Cài đặt, hoặc {ENV_FILE})", "text": "", "texts": []}
    base = base_url()
    if base and not base.endswith("/v1beta"):
        return _run_compat(base, system, contents, key, model, timeout, log_path, update or (lambda _m: None),
                           stop_flag, started)
    if key.startswith("sk-") and not base:
        return {"ok": False, "error": "key dạng \"sk-…\" là key mua ngoài: điền Gemini base URL của bên bán ở trang "
                                      "Cài đặt (thường dạng https://…/v1), key này không gọi thẳng Google được",
                "text": "", "texts": [], "models": [model]}
    body = {"systemInstruction": {"parts": [{"text": system}]}, "contents": contents,
            "generationConfig": {"temperature": 0.7}}
    global _search_blocked
    warnings, use_search, waits = [], search and not _search_blocked, list(RETRY_WAIT)
    if search and _search_blocked:
        warnings.append(_NO_SEARCH)
    queue = [model] + ([m for m in FLASH_FALLBACK if m != model] if "flash" in model else [])
    asked, problems = model, []
    say = update or (lambda _m: None)
    while True:
        if stop_flag and stop_flag():
            return {"ok": False, "error": "đã hủy", "text": "", "texts": []}
        req = dict(body, tools=[{"google_search": {}}]) if use_search else body
        say(f"gọi {model}" + (" (có Google Search)" if use_search else ""))
        try:
            res = _post(f"models/{model}:generateContent", req, key, timeout)
            break
        except GeminiError as e:
            log.warning("gemini %s: %s", model, e)
            if use_search and e.code in (400, 403, 429):
                use_search, _search_blocked = False, True
                warnings.append(_NO_SEARCH)
                continue
            if e.code in (500, 503) and waits:
                w = waits.pop(0)
                say(f"{model} đang quá tải, thử lại sau {w}s")
                time.sleep(w)
                continue
            if e.code in (429, 500, 503):
                problems.append(f"{model}: " + ("hết lượt gói free hôm nay" + _retry_hint(str(e)) if e.code == 429
                                                 else "đang quá tải"))
                queue.pop(0)
                if queue:
                    model, waits = queue[0], list(RETRY_WAIT)
                    say(f"{problems[-1]}, chuyển sang {model}")
                    continue
                return {"ok": False, "error": "Gemini không chạy được: " + "; ".join(problems), "text": "", "texts": [],
                        "models": [asked], "duration_sec": round(time.time() - started, 1)}
            return {"ok": False, "error": str(e), "text": "", "texts": [], "models": [model],
                    "duration_sec": round(time.time() - started, 1)}
        except (urllib.error.URLError, TimeoutError) as e:
            return {"ok": False, "error": f"không gọi được Gemini: {e}", "text": "", "texts": [], "models": [model],
                    "duration_sec": round(time.time() - started, 1)}
    if model != asked:
        warnings.append(f"chạy bằng {model} thay cho {asked} ({'; '.join(problems)})")
    if log_path:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    cand = (res.get("candidates") or [{}])[0]
    text = "".join(p.get("text", "") for p in (cand.get("content") or {}).get("parts", []) if not p.get("thought"))
    u = res.get("usageMetadata") or {}
    usage = {"input_tokens": u.get("promptTokenCount") or 0,
             "output_tokens": (u.get("candidatesTokenCount") or 0) + (u.get("thoughtsTokenCount") or 0),
             "output_tokens_details": {"thinking_tokens": u.get("thoughtsTokenCount") or 0}}
    finish = cand.get("finishReason")
    ok = bool(text.strip()) and finish in (None, "STOP")
    err = None if ok else f"Gemini dừng với lý do {finish or 'không rõ'}" + ("" if text.strip() else ", không có nội dung")
    return {"ok": ok, "error": err, "text": text, "texts": [text], "usage": usage,
            "models": [res.get("modelVersion") or model], "cost_usd": None,
            "duration_sec": round(time.time() - started, 1), "session_id": None, "warnings": warnings}
