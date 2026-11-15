"""The quota bar at the top of every page: what is used up and what is left, to refill or change how things are used.

- Claude plan (the Max subscription the headless turns run on): 5-hour and weekly limits, read the way Claude Code's
  /usage reads them (GET api.anthropic.com/api/oauth/usage with the CLI's own OAuth session in ~/.claude). The token is
  only read from that file and sent to Anthropic; it is never stored, logged or shown.
- ElevenLabs: characters used / left in the billing period, and the reset date.
- fal.ai: credit balance (when the key may read it).
- OpenAI, Google: no balance API for these keys, so the bar shows what the app spent with them this month
  (notes/costs.json of every project).
Each source is cached (the page polls; the APIs are not hit on every poll).
"""
from __future__ import annotations

import json
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

from . import db, providers, workflow

_cache: dict[str, tuple[float, dict]] = {}
_lock = threading.Lock()
TTL = {"claude": 120, "elevenlabs": 600, "fal": 600, "spend": 300}
CREDENTIALS = Path.home() / ".claude" / ".credentials.json"


def _cached(key: str, fn, force: bool = False) -> dict:
    with _lock:
        hit = _cache.get(key)
        if hit and not force and time.time() - hit[0] < TTL[key]:
            return hit[1]
    try:
        val = fn()
    except Exception as e:  # noqa: BLE001
        val = {"ok": False, "error": str(e)[:200]}
    with _lock:
        _cache[key] = (time.time(), val)
    return val


def _local(iso: str | None) -> str | None:
    if not iso:
        return None
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone().isoformat(timespec="minutes")
    except ValueError:
        return None


def claude() -> dict:
    try:
        oauth = json.loads(CREDENTIALS.read_text(encoding="utf-8")).get("claudeAiOauth") or {}
    except (OSError, ValueError):
        return {"ok": False, "error": "chưa đăng nhập Claude Code (không thấy ~/.claude/.credentials.json)"}
    token = oauth.get("accessToken")
    if not token:
        return {"ok": False, "error": "phiên Claude Code không có token"}
    if (oauth.get("expiresAt") or 0) / 1000 < time.time():
        return {"ok": False, "error": "phiên Claude Code hết hạn: tự làm mới ở lượt Claude kế tiếp"}
    req = urllib.request.Request("https://api.anthropic.com/api/oauth/usage", headers={
        "Authorization": f"Bearer {token}", "anthropic-beta": "oauth-2025-04-20", "Content-Type": "application/json",
        "User-Agent": "creater-vid"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            u = json.load(r)
    except urllib.error.HTTPError as e:
        return {"ok": False, "error": f"Anthropic trả HTTP {e.code}"}
    windows = []
    for key, label in (("five_hour", "5 giờ"), ("seven_day", "tuần"), ("seven_day_opus", "tuần · Opus"),
                       ("seven_day_sonnet", "tuần · Sonnet")):
        w = u.get(key)
        if isinstance(w, dict) and w.get("utilization") is not None:
            windows.append({"key": key, "label": label, "percent": round(float(w["utilization"])),
                            "resets_at": _local(w.get("resets_at"))})
    extra = u.get("extra_usage") if isinstance(u.get("extra_usage"), dict) else {}
    return {"ok": True, "plan": oauth.get("subscriptionType"), "windows": windows,
            "extra": {"enabled": bool(extra.get("is_enabled")), "used": extra.get("used_credits"),
                      "limit": extra.get("monthly_limit"), "currency": extra.get("currency")} if extra else None}


def elevenlabs() -> dict:
    if not providers.has_key("elevenlabs_api_key"):
        return {"ok": False, "error": "chưa có key"}
    r = providers.el_check()
    if r.get("ok") and r.get("limit"):
        r["percent"] = round(100 * (r.get("used") or 0) / r["limit"])
    return r


def fal() -> dict:
    if not providers.has_key("fal_api_key"):
        return {"ok": False, "error": "chưa có key"}
    return providers.fal_check()


def spend() -> dict:
    """USD the app spent per provider this month and today (every project's notes/costs.json), and Claude's
    equivalent API cost of the turns (it is not billed on the Max plan; it shows how heavy the usage is)."""
    month, today = datetime.now().strftime("%Y-%m"), datetime.now().strftime("%Y-%m-%d")
    out: dict[str, dict] = {}
    for p in db.rows("SELECT dir FROM projects"):
        for e in workflow.costs_spent(Path(p["dir"]))["events"]:
            at = str(e.get("at") or "")
            if not at.startswith(month):
                continue
            prov = str(e.get("provider") or "khác")
            s = out.setdefault(prov, {"month": 0.0, "today": 0.0})
            usd = float(e.get("usd") or 0)
            s["month"] += usd
            if at.startswith(today):
                s["today"] += usd
    claude_today = db.scalar("SELECT COALESCE(SUM(cost_usd), 0) FROM messages WHERE role='assistant' AND substr(created_at,1,10)=?",
                             (today,)) or 0
    return {"ok": True, "providers": {k: {"month": round(v["month"], 2), "today": round(v["today"], 2)} for k, v in out.items()},
            "claude_api_equiv_today": round(float(claude_today), 2)}


def gather(force: bool = False) -> dict:
    return {"claude": _cached("claude", claude, force), "elevenlabs": _cached("elevenlabs", elevenlabs, force),
            "fal": _cached("fal", fal, force), "spend": _cached("spend", spend, force),
            "openai_key": providers.has_key("openai_api_key"), "google_key": providers.has_key("google_api_key"),
            "at": datetime.now().isoformat(timespec="seconds")}
