"""Publishing to YouTube through GPM Login profiles.

- GPM profiles come from the GPM local API; the YouTube channels inside each profile are found by `yt_gpm.py channels`
  (opens the profile, reads the channel switcher) and cached in the `yt_channels` table.
- A project picks one profile + channel when it is created (projects.yt_profile, yt_channel) and an upload mode:
  yt_auto = 1 uploads by itself as soon as the metadata step is approved, 0 waits for the user's ▶ Đăng button.
- The upload job is built from 7_metadata/metadata.json + the last render, run by `yt_gpm.py upload` in its own process,
  one upload at a time; its progress and result live in 7_metadata/upload.json (the project page reads it).
- An upload that failed after the file was handed to YouTube left a draft in Studio: it is not retried by itself.
"""
from __future__ import annotations

import json
import logging
import subprocess
import sys
import threading
from datetime import datetime, timedelta
from pathlib import Path

from . import config, db, store
from .util import now_iso, read_json, write_json

log = logging.getLogger("creater.publish")
YT_GPM = Path(__file__).with_name("yt_gpm.py")
VISIBILITY = {"schedule": "Lên lịch theo giờ đăng", "private": "Riêng tư", "unlisted": "Không công khai", "public": "Công khai ngay"}
_lock = threading.Lock()            # one browser upload at a time (bandwidth, and one Studio session per profile)
_scans: dict[str, dict] = {}        # profile_id -> {"status", "error", "at"} of scans started from the page


def api() -> str:
    return (db.get_setting("gpm_api") or config.DEFAULT_SETTINGS["gpm_api"]).rstrip("/")


def _get(path: str, timeout: int = 15) -> dict:
    import urllib.request
    with urllib.request.urlopen(api() + path, timeout=timeout) as r:
        data = json.load(r)
    if not data.get("success"):
        raise RuntimeError(data.get("message") or "GPM trả lỗi")
    return data.get("data") or {}


# ---------------------------------------------------------------- profiles and channels
def gpm_profiles() -> dict:
    """Every GPM profile (id, name, group, browser). Profile notes are never read: they can hold passwords."""
    try:
        groups = {g["id"]: g["name"] for g in (_get("/api/v1/groups?page_size=200").get("data") or [])}
    except Exception:  # noqa: BLE001
        groups = {}
    out, page = [], 1
    try:
        while True:
            d = _get(f"/api/v1/profiles?page={page}&page_size=100")
            for x in d.get("data") or []:
                out.append({"id": x["id"], "name": x.get("name") or x["id"], "group": groups.get(x.get("group_id"), ""),
                            "browser": (x.get("browser") or {}).get("name") or ""})
            if page >= (d.get("last_page") or 1):
                break
            page += 1
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"không gọi được GPM Login ở {api()}: {e}", "profiles": []}
    return {"ok": True, "profiles": out}


def channels() -> list[dict]:
    return db.rows("SELECT * FROM yt_channels ORDER BY profile_name, name")


def scans() -> dict:
    saved = {r["profile_id"]: r for r in db.rows("SELECT * FROM yt_scans")}
    return {pid: dict(saved.get(pid) or {}, **_scans.get(pid, {})) for pid in set(saved) | set(_scans)}


def channel(profile_id: str | None, channel_id: str | None) -> dict | None:
    if not profile_id or not channel_id:
        return None
    return db.row("SELECT * FROM yt_channels WHERE profile_id=? AND channel_id=?", (profile_id, channel_id))


def _run_cli(args: list[str], timeout: int) -> list[dict]:
    proc = subprocess.run([sys.executable, str(YT_GPM), *args], capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=timeout, env={**__import__("os").environ, "PYTHONUTF8": "1"})
    lines = []
    for ln in (proc.stdout or "").splitlines():
        try:
            lines.append(json.loads(ln))
        except ValueError:
            continue
    if not lines:
        raise RuntimeError((proc.stderr or proc.stdout or "yt_gpm không trả lời").strip()[-400:])
    return lines


def scan(profile_id: str, profile_name: str) -> dict:
    """Open the profile, read its YouTube channels, store them (replaces what was cached for that profile)."""
    _scans[profile_id] = {"status": "running", "at": now_iso()}
    try:
        res = _run_cli(["channels", profile_id, api()], timeout=300)[-1]
    except Exception as e:  # noqa: BLE001
        res = {"ok": False, "error": str(e), "channels": []}
    with db.tx() as c:
        if res.get("ok"):
            c.execute("DELETE FROM yt_channels WHERE profile_id=?", (profile_id,))
            for ch in res.get("channels") or []:
                if ch.get("channel_id"):
                    c.execute("""INSERT INTO yt_channels(profile_id, channel_id, profile_name, name, handle, subs, photo, scanned_at)
                                 VALUES(?,?,?,?,?,?,?,?)""", (profile_id, ch["channel_id"], profile_name, ch.get("name"),
                                                              ch.get("handle"), ch.get("subs"), ch.get("photo"), now_iso()))
        c.execute("""INSERT INTO yt_scans(profile_id, profile_name, ok, error, count, scanned_at) VALUES(?,?,?,?,?,?)
                     ON CONFLICT(profile_id) DO UPDATE SET profile_name=excluded.profile_name, ok=excluded.ok,
                     error=excluded.error, count=excluded.count, scanned_at=excluded.scanned_at""",
                  (profile_id, profile_name, 1 if res.get("ok") else 0, res.get("error"), len(res.get("channels") or []), now_iso()))
    _scans.pop(profile_id, None)
    return res


def scan_async(items: list[tuple[str, str]]) -> None:
    """Scan profiles one after the other in the background (each opens a browser through its proxy)."""
    for pid, _ in items:
        _scans[pid] = {"status": "queued", "at": now_iso()}

    def job():
        for pid, name in items:
            try:
                scan(pid, name)
            except Exception:  # noqa: BLE001
                log.exception("scan of profile %s failed", pid)
                _scans.pop(pid, None)
    threading.Thread(target=job, name="creater-yt-scan", daemon=True).start()


# ---------------------------------------------------------------- upload of a project
def state_path(p: dict) -> Path:
    return store.project_dir(p) / "7_metadata" / "upload.json"


def state(p: dict) -> dict:
    return read_json(state_path(p)) or {}


def _save(p: dict, st: dict) -> None:
    write_json(state_path(p), st)


def default_time(kind: str) -> datetime:
    """Next occurrence of the desk's default publishing hour (machine local time)."""
    hhmm = db.get_setting(f"yt_time_{kind}") or config.DEFAULT_SETTINGS.get(f"yt_time_{kind}") or "18:00"
    h, m = (int(x) for x in hhmm.split(":")[:2])
    now = datetime.now().astimezone()
    at = now.replace(hour=h, minute=m, second=0, microsecond=0)
    while at < now + timedelta(minutes=30):
        at += timedelta(days=1)
    return at


def _parse(at: str | None) -> datetime | None:
    if not at:
        return None
    try:
        d = datetime.fromisoformat(str(at).replace("Z", "+00:00"))
    except ValueError:
        return None
    return d if d.tzinfo else d.astimezone()


def build_job(p: dict, override: dict | None = None) -> tuple[dict, list[str]]:
    """The upload job of a project from its metadata and last render. Returns (job, problems)."""
    d = store.project_dir(p)
    m = read_json(d / "7_metadata" / "metadata.json")
    problems: list[str] = []
    if not isinstance(m, dict):
        return {}, ["chưa có 7_metadata/metadata.json"]
    versions = [v for v in ((read_json(d / "6_render" / "render.json") or {}).get("versions") or []) if isinstance(v, dict)]
    video = m.get("video") or (versions[-1].get("file") if versions else None)
    if not video or not (d / video).is_file():
        problems.append(f"không thấy file video {video or '(render.json trống)'}")
    thumbs = [t for t in (m.get("thumbnails") or []) if isinstance(t, dict)]
    thumb = next((t.get("file") for t in thumbs if t.get("chosen")), None) or (thumbs[0].get("file") if thumbs else None)
    override = override or {}
    # what the user picked (this click, then the project's saved choice) beats what Claude wrote in metadata.json
    vis = override.get("visibility") or p.get("yt_vis") or m.get("visibility") or db.get_setting("yt_visibility") or "schedule"
    vis = vis if vis in VISIBILITY else "schedule"
    when = _parse(override.get("publish_at")) or _parse(p.get("yt_at")) or _parse(m.get("publish_at"))
    note = None
    if vis == "schedule" and (when is None or when < datetime.now().astimezone() + timedelta(minutes=20)):
        note = "giờ đăng trong metadata " + ("thiếu" if when is None else "đã qua") + ": dùng giờ mặc định của mảng"
        when = default_time(store.kind_of(p))
    if when:
        when = when.astimezone()                 # shown and edited on the page in the machine's local time
    title = str(m.get("title") or "").strip()
    if not title:
        problems.append("metadata.json chưa có title")
    if not p.get("yt_profile") or not p.get("yt_channel"):
        problems.append("dự án chưa chọn kênh YouTube (✏️ Thông tin → Kênh đăng)")
    job = {"api": api(), "profile_id": p.get("yt_profile"), "channel_id": p.get("yt_channel"),
           "video": str(d / video) if video else None, "title": title[:100], "description": str(m.get("description") or ""),
           "tags": [str(t) for t in (m.get("tags") or [])], "thumbnail": str(d / thumb) if thumb and (d / thumb).is_file() else None,
           "made_for_kids": bool(m.get("made_for_kids")), "altered_content": bool(m.get("altered_content")),
           "category": m.get("category") or None, "visibility": vis,
           "publish_at": when.isoformat(timespec="minutes") if when and vis == "schedule" else None,
           "shots": str(d / "7_metadata" / "upload"), "time_note": note,
           "default_at": default_time(store.kind_of(p)).isoformat(timespec="minutes")}   # prefill of «Lên lịch» on the page
    return job, problems


def start(p: dict, override: dict | None = None, force: bool = False, by: str = "người dùng") -> dict:
    st = state(p)
    if st.get("status") in ("queued", "running"):
        return {"error": "đang đăng video này"}
    if st.get("status") == "done" and not force:
        return {"error": f"video đã lên YouTube: {st.get('url') or ''}. Đăng thêm lần nữa sẽ tạo video trùng"}
    if st.get("draft") and not force:
        return {"error": "lần trước đã gửi file lên YouTube rồi mới lỗi: video nháp đang nằm trong Studio. Hoàn tất tay "
                         "trên Studio, hoặc xoá bản nháp rồi bấm Đăng lại (xác nhận)"}
    job, problems = build_job(p, override)
    if problems:
        return {"error": "; ".join(problems)}
    ch = channel(job["profile_id"], job["channel_id"]) or {}
    st = {"status": "queued", "queued_at": now_iso(), "by": by, "channel": ch.get("name"), "handle": ch.get("handle"),
          "profile": ch.get("profile_name"), "visibility": job["visibility"], "publish_at": job["publish_at"],
          "time_note": job.get("time_note"), "log": [], "draft": False}
    _save(p, st)
    store.log_event(p["id"], "upload", f"xếp hàng đăng YouTube ({by}) lên kênh {ch.get('name') or job['channel_id']}", "metadata")
    threading.Thread(target=_run_upload, args=(p["id"], job), name=f"creater-upload-{p['id']}", daemon=True).start()
    return {"ok": True, "message": "đã xếp hàng đăng YouTube"}


def _run_upload(pid: int, job: dict) -> None:
    p = store.get_project(pid)
    jobfile = store.project_dir(p) / "7_metadata" / "upload_job.json"
    write_json(jobfile, job)
    with _lock:
        st = state(p)
        st.update(status="running", started_at=now_iso())
        _save(p, st)
        try:
            proc = subprocess.Popen([sys.executable, str(YT_GPM), "upload", str(jobfile)], stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace",
                                    env={**__import__("os").environ, "PYTHONUTF8": "1"})
            final = None
            for ln in proc.stdout:
                try:
                    ev = json.loads(ln)
                except ValueError:
                    continue
                st = state(p)
                if ev.get("done"):
                    final = ev
                    continue
                if ev.get("stage") == "file":
                    st["draft"] = True                 # from here on a draft exists in Studio
                st["log"] = (st.get("log") or [])[-60:] + [{"at": now_iso()[11:19], "stage": ev.get("stage"), "msg": ev.get("msg"),
                                                           "shot": ev.get("shot")}]
                st["progress"] = ev.get("msg") if ev.get("stage") == "progress" else st.get("progress")
                _save(p, st)
            proc.wait()
        except Exception as e:  # noqa: BLE001
            final = {"ok": False, "error": str(e)}
        st = state(p)
        final = final or {"ok": False, "error": "yt_gpm dừng mà không báo kết quả"}
        if final.get("ok"):
            st.update(status="done", finished_at=now_iso(), url=final.get("url"), video_id=final.get("video_id"),
                      scheduled_for=final.get("scheduled_for"), warnings=final.get("warnings") or [], error=None)
            store.log_event(pid, "upload", f"đã đăng YouTube: {final.get('url') or '(chưa đọc được link)'}"
                            + (f", lên lịch {final.get('scheduled_for')}" if final.get("scheduled_for") else ""), "metadata")
        else:
            st.update(status="failed", finished_at=now_iso(), error=final.get("error"))
            store.log_event(pid, "upload", f"đăng YouTube lỗi: {final.get('error')}", "metadata")
        _save(p, st)
        from . import notify, tgbot
        _, name = notify._project(pid)
        if final.get("ok"):
            notify.notify("done", f"Đã đăng YouTube: {name}", (final.get("url") or "")
                          + (f" · lên lịch {final['scheduled_for']}" if final.get("scheduled_for") else ""),
                          notify.project_link(pid, "metadata"))
        else:
            notify.notify("error", f"Đăng YouTube lỗi: {name}", str(final.get("error") or ""), notify.project_link(pid, "metadata"))
        tgbot._safe(tgbot.notify_upload, pid, final)


def on_metadata_approved(p: dict) -> dict | None:
    """Projects in automatic mode upload as soon as their metadata is approved (by the user or by auto-advance)."""
    if not p.get("yt_auto") or not p.get("yt_channel"):
        return None
    res = start(p, by="tự động khi duyệt metadata")
    if res.get("error"):
        store.log_event(p["id"], "upload", f"không tự đăng được: {res['error']}", "metadata")
    return res
