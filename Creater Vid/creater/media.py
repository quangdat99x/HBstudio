"""Materials taken from the news: photos and videos of Telegram posts, pictures of articles. The user reviews the
list (sources/media.json) before anything is downloaded or used; an approved item is downloaded into sources/media/,
a rejected one never is (and is deleted if it was). Videos the Telegram web preview will not serve come through the
Telegram API (creater/tg.py, the user's own account) once the user has signed in on the Settings page.
"""
from __future__ import annotations

import json
import logging
import os
import re
import shutil
import subprocess
import threading
import time
from pathlib import Path

from . import config, db, news_fetch as nf, store
from .util import now_iso, read_json, write_json

log = logging.getLogger("creater.media")

_lock = threading.RLock()
MAX_PER_ITEM = 12
VENV_PY = config.BASE_DIR / ".venv" / "Scripts" / "python.exe"
TG_SCRIPT = config.BASE_DIR / "creater" / "tg.py"

# words of a post (Russian, Ukrainian) that call for a careful look at its pictures
_GRAPHIC = re.compile(r"(?i)(погиб|убит|убил|тела\b|тело\b|трупы?|ранен|кров|казн|расстрел|обезглав|мертв|загинул|вбит|поранен|смерт)")
_POW = re.compile(r"(?i)(пленн|полонен|сдал[аи]?с[ья] в плен|здал[иа]?с[яь] в полон)")
_CHILD = re.compile(r"(?i)(\bдет(и|ей|ям|ьми)\b|ребен|ребён|школьн|дитин|\bдіт)")
_OFFICIAL = re.compile(r"(?i)(минобороны|генштаб|генеральний штаб|mod_russia|generalstaff)")


# ---------------------------------------------------------------- the list (sources/media.json)
def path(p: dict) -> Path:
    return store.project_dir(p) / "sources" / "media.json"


def load(p: dict) -> dict:
    with _lock:                                         # Windows will not replace a file another thread is reading
        data = read_json(path(p))
    return data if isinstance(data, dict) and isinstance(data.get("items"), list) else {"items": []}


def save(p: dict, data: dict) -> None:
    with _lock:
        for attempt in range(20):
            try:
                write_json(path(p), data)
                return
            except PermissionError:                     # the page or an indexer has the file open for a moment
                if attempt == 19:
                    raise
                time.sleep(0.1)


def summary(p: dict) -> dict:
    items = load(p)["items"]
    count = lambda *st: sum(1 for i in items if i.get("status") in st)  # noqa: E731
    return {"total": len(items), "proposed": count("proposed"), "approved": count("approved", "downloading", "downloaded"),
            "downloaded": count("downloaded"), "rejected": count("rejected"), "failed": count("failed", "need_api")}


def flags_for(item: dict, m: dict) -> list[dict]:
    """Reminders for the reviewer (level high | warn | info). They point at risks; the decision stays the user's."""
    text = f"{item.get('title') or ''}\n{item.get('summary') or ''}"
    source = item.get("source") or "?"
    fwd = ((item.get("extra") or {}).get("forwarded_from") or {}).get("name")
    out = []
    if _GRAPHIC.search(text):
        out.append({"level": "warn", "text": "Bài nhắc tới người chết hoặc bị thương: xem kỹ hình, không dùng cảnh thi thể, máu; "
                                             "che mờ nếu cần (YouTube có thể giới hạn tuổi hoặc gỡ video)."})
    if _POW.search(text):
        out.append({"level": "warn", "text": "Có thể có tù binh: Công ước Geneva cấm phơi bày tù binh, che mặt hoặc bỏ."})
    if _CHILD.search(text):
        out.append({"level": "warn", "text": "Có thể có trẻ em trong hình: che mặt."})
    if item.get("kind") in ("bing", "gnews") or (item.get("kind") == "rss" and m.get("kind") == "photo"):
        # the user's choice (2026-10-13): real pictures of the article first, rights handled by hand at the edit
        out.append({"level": "info", "text": f"Ảnh của báo ({source}): có thể là ảnh hãng có Content ID; vẫn dùng (ảnh thật trước "
                                             "ảnh AI, bộ quy tắc tin tức mục 1.7), bản quyền bạn tự xử lý khi edit."})
    if fwd:
        out.append({"level": "info", "text": f"Bài chuyển tiếp từ «{fwd}»."})
    if item.get("kind") == "telegram" and (_OFFICIAL.search(source) or _OFFICIAL.search(item.get("url") or "")):
        out.append({"level": "info", "text": f"Tư liệu chính thức của một bên tham chiến ({source}): lời dẫn nói rõ đây là tư "
                                             "liệu của bên đó (không đọc tên kênh Telegram, mục 1.6)."})
    if m.get("too_big"):
        out.append({"level": "info", "text": "Video lớn: chỉ tải được qua Telegram API (Cài đặt → Telegram API)."})
    dur = _seconds(m.get("duration"))
    if dur and dur > 30:
        out.append({"level": "info", "text": f"Video dài {m['duration']}: chỉ trích đoạn ngắn (≤ 10–15 s mỗi lần) kèm lời dẫn."})
    return out


def _seconds(d: str | None) -> int | None:
    if not d:
        return None
    try:
        parts = [int(x) for x in d.split(":")]
    except ValueError:
        return None
    total = 0
    for x in parts:
        total = total * 60 + x
    return total


def build(rows: list[dict], fresh: dict[int, dict | None], files: dict[int, str]) -> list[dict]:
    """Candidates of the chosen news items. `fresh`: the Telegram post read again just now (current media links);
    `files`: the sources/news_*.md file of each item."""
    out = []
    for r in rows:
        media = ((fresh.get(r["id"]) or {}).get("media") or r.get("media") or [])[:MAX_PER_ITEM]
        if fresh.get(r["id"]) and fresh[r["id"]].get("forwarded_from"):
            r.setdefault("extra", {})["forwarded_from"] = fresh[r["id"]]["forwarded_from"]
        fwd = ((r.get("extra") or {}).get("forwarded_from") or {}).get("name")
        for m in media:
            out.append({
                "id": f"m{len(out) + 1:02d}", "kind": m.get("kind") or "photo", "news_file": files.get(r["id"]),
                "news_title": r.get("title"), "source": r.get("source"), "side": r.get("side") or "",
                "origin": fwd or r.get("source"), "post_url": r.get("url"), "media_post": m.get("post"),
                "url": m.get("url"), "thumb": m.get("thumb") or (m.get("url") if m.get("kind") == "photo" else None),
                "duration": m.get("duration"), "too_big": bool(m.get("too_big")), "posted_at": r.get("published_at"),
                "caption": nf.short(r.get("summary") or r.get("title") or "", 300), "flags": flags_for(r, m),
                "rights": f"© {fwd or r.get('source') or 'nguồn'}. Dùng dạng đưa tin, có lời bình; bản quyền người dùng tự xử lý khi edit.",
                "status": "proposed"})
    return out


# ---------------------------------------------------------------- decisions and downloads
def decide(p: dict, mid: str, decision: str | None) -> dict:
    """approved → downloaded in the background; rejected or undone → never used (a downloaded file is removed)."""
    with _lock:
        data = load(p)
        item = next((i for i in data["items"] if i.get("id") == mid), None)
        if not item:
            raise ValueError("không có mục này")
        if decision == "approved":
            if item.get("status") in ("downloaded", "downloading"):
                return item
            item.update(status="approved", decided_at=now_iso(), error=None)
        else:
            _remove_file(p, item)
            item.update(status="rejected" if decision == "rejected" else "proposed", decided_at=now_iso(), error=None,
                        file=None)
        save(p, data)
    if decision == "approved":
        start_download(p, mid)
    return item


def approve_clean(p: dict) -> int:
    """Approve every proposed item without a warning (only "info" reminders)."""
    with _lock:
        data = load(p)
        ids = [i["id"] for i in data["items"] if i.get("status") == "proposed"
               and not any(f.get("level") in ("warn", "high") for f in i.get("flags") or [])]
        for i in data["items"]:
            if i["id"] in ids:
                i.update(status="approved", decided_at=now_iso())
        save(p, data)
    for mid in ids:
        start_download(p, mid)
    return len(ids)


def approve_all(p: dict) -> int:
    """Approve every proposed item, warnings included, and download them 4 at a time (one Telegram API session at a
    time would clash with dozens of threads). News projects start this way: the real pictures of the chosen items
    are the first material of the film (news rulebook 1.7); Claude still looks at each file before using it (1.5)."""
    with _lock:
        data = load(p)
        ids = [i["id"] for i in data["items"] if i.get("status") == "proposed"]
        for i in data["items"]:
            if i["id"] in ids:
                i.update(status="approved", decided_at=now_iso(), auto=True)
        save(p, data)
    if ids:
        def run():
            from concurrent.futures import ThreadPoolExecutor
            with ThreadPoolExecutor(max_workers=4) as ex:
                list(ex.map(lambda mid: _download(p["id"], mid), ids))
        threading.Thread(target=run, name=f"media-all-{p['id']}", daemon=True).start()
    return len(ids)


def _remove_file(p: dict, item: dict) -> None:
    f = item.get("file")
    if f:
        target = store.project_dir(p) / f
        if target.exists():
            try:
                from .util import send_to_trash
                send_to_trash(target)
            except OSError:
                target.unlink(missing_ok=True)


def _update(p: dict, mid: str, **fields) -> None:
    with _lock:
        data = load(p)
        for i in data["items"]:
            if i.get("id") == mid:
                i.update(fields)
        save(p, data)


def start_download(p: dict, mid: str) -> None:
    threading.Thread(target=_download, args=(p["id"], mid), name=f"media-{p['id']}-{mid}", daemon=True).start()


def _ext(url: str | None, kind: str) -> str:
    suffix = Path((url or "").split("?")[0]).suffix.lower()
    return suffix if suffix in (".jpg", ".jpeg", ".png", ".webp", ".mp4", ".mov", ".webm") else (".mp4" if kind == "video" else ".jpg")


def _download(pid: int, mid: str) -> None:
    p = store.get_project(pid)
    if not p:
        return
    item = next((i for i in load(p)["items"] if i.get("id") == mid), None)
    if not item or item.get("status") != "approved":
        return
    folder = store.project_dir(p) / "sources" / "media"
    try:
        _update(p, mid, status="downloading", error=None)
        folder.mkdir(parents=True, exist_ok=True)
        url = item.get("url")
        if item.get("media_post") and (item.get("post_url") or "").startswith("https://t.me/"):
            try:                                            # links of a channel page expire: read the post again
                fresh = nf.fetch_telegram_post(item["post_url"])
                match = next((m for m in (fresh or {}).get("media") or []
                              if m.get("post") == item["media_post"] and m.get("kind") == item["kind"]), None)
                if match:
                    url = match.get("url")
            except nf.FetchError as e:
                log.info("refresh %s: %s", item["post_url"], e)
        target = None
        if url:
            target = folder / f"{mid}{_ext(url, item['kind'])}"
            try:
                res = nf.http_get(url, timeout=300)
                target.write_bytes(res["body"])
            except nf.FetchError as e:
                log.info("media %s: direct download failed (%s), trying the Telegram API", mid, e)
                target = None
        if target is None:
            if not item.get("media_post"):
                raise RuntimeError("không có link tải")
            res = tg_run(["download", "--post", item["media_post"], "--out", str(folder / mid)], timeout=1800)
            if not res.get("ok"):
                st = "need_api" if "đăng nhập" in (res.get("error") or "") or "api_id" in (res.get("error") or "") else "failed"
                _update(p, mid, status=st, error=res.get("error"))
                return
            target = Path(res["file"])
        info = probe(target)
        _update(p, mid, status="downloaded", file=store.rel(p, target), size_mb=round(target.stat().st_size / 1e6, 2),
                downloaded_at=now_iso(), **info)
        store.log_event(pid, "sources", f"tải nguyên liệu đã duyệt {mid} ({item['kind']}, {item.get('source')})", "footage")
    except Exception as e:  # noqa: BLE001  (shown on the item; the user can retry)
        log.exception("media %s of project %s", mid, pid)
        _update(p, mid, status="failed", error=str(e)[:300])


def retry(p: dict, mid: str) -> None:
    _update(p, mid, status="approved", error=None)
    start_download(p, mid)


def probe(f: Path) -> dict:
    ffprobe = shutil.which("ffprobe") or (str(config.FFPROBE_FALLBACK) if config.FFPROBE_FALLBACK.exists() else None)
    ff = db.get_setting("ffmpeg")
    if ff and ff.lower().endswith("ffmpeg.exe") and Path(ff).with_name("ffprobe.exe").exists():
        ffprobe = str(Path(ff).with_name("ffprobe.exe"))
    if not ffprobe:
        return {}
    try:
        res = subprocess.run([ffprobe, "-v", "error", "-select_streams", "v:0", "-show_entries",
                              "stream=width,height:format=duration", "-of", "json", str(f)],
                             capture_output=True, text=True, timeout=60, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        data = json.loads(res.stdout or "{}")
    except (OSError, ValueError, subprocess.SubprocessError):
        return {}
    s = (data.get("streams") or [{}])[0]
    dur = float((data.get("format") or {}).get("duration") or 0)
    return {"width": s.get("width"), "height": s.get("height"), **({"seconds": round(dur, 1)} if dur > 0.2 else {})}


# ---------------------------------------------------------------- Telegram API (creater/tg.py in the venv)
def tg_ready() -> bool:
    return VENV_PY.exists()


def tg_run(args: list[str], timeout: int = 90, env: dict | None = None) -> dict:
    if not VENV_PY.exists():
        return {"ok": False, "error": f"không thấy {VENV_PY} (Telethon cài trong venv của app)"}
    try:
        res = subprocess.run([str(VENV_PY), str(TG_SCRIPT), *args], capture_output=True, text=True, encoding="utf-8",
                             errors="replace", timeout=timeout, cwd=str(config.BASE_DIR),
                             env={**os.environ, "PYTHONUTF8": "1", **(env or {})},
                             creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"quá {timeout} giây"}
    lines = [ln for ln in (res.stdout or "").splitlines() if ln.strip().startswith("{")]
    if not lines:
        err = (res.stderr or "").strip().splitlines()[-1:] or ["không có phản hồi"]
        if "No module named 'telethon'" in (res.stderr or ""):
            err = ["chưa cài Telethon: .venv\\Scripts\\python.exe -m pip install telethon"]
        return {"ok": False, "error": err[0][:300]}
    try:
        return json.loads(lines[-1])
    except ValueError:
        return {"ok": False, "error": lines[-1][:300]}
