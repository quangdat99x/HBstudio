"""YouTube through a GPM Login browser profile (the channel stays signed in there, with its own proxy and fingerprint).

Run by the app as a separate process (Playwright drives the profile's Chromium over CDP):

  python yt_gpm.py channels <profile_id>        -> one JSON line: {"ok", "channels": [{channel_id, name, handle, photo}]}
  python yt_gpm.py upload <job.json>            -> JSON lines {"stage", "msg", ...} while it works, last line {"done": true, ...}

Only the standard library and Playwright: the GPM local API (default http://127.0.0.1:9495) opens and closes profiles.
The upload goes through the YouTube Studio web page, so a Studio redesign can break a selector: every stage writes a
screenshot into the job's folder, and a failure says which stage stopped.

job.json: {"api": "...", "profile_id", "channel_id", "video", "title", "description", "tags": [...], "thumbnail",
           "made_for_kids": false, "altered_content": false, "category": "News & Politics",
           "visibility": "schedule|private|unlisted|public", "publish_at": "2026-10-15T18:00:00+03:00", "shots": "<folder>"}
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path

API = "http://127.0.0.1:9495"


def _norm(s: str) -> str:
    """'1:00 AM' / '1:00 AM' / '1:00AM' -> '1:00am'."""
    return "".join((s or "").replace(" ", " ").replace(" ", " ").split()).lower()


def emit(**kw) -> None:
    print(json.dumps(kw, ensure_ascii=False), flush=True)


# ---------------------------------------------------------------- GPM local API
def gpm(api: str, path: str, timeout: int = 180) -> dict:
    with urllib.request.urlopen(api.rstrip("/") + path, timeout=timeout) as r:
        data = json.load(r)
    if not data.get("success"):
        raise RuntimeError(f"GPM {path}: {data.get('message') or data}")
    return data.get("data") or {}


def profile_running(profile_id: str) -> bool:
    """The profile's browser is already open (by the user or another job): we attach but never close it."""
    ps = ("Get-CimInstance Win32_Process -Filter \"name='chrome.exe'\" | "
          f"Where-Object {{ $_.CommandLine -like '*{profile_id}*' }} | Measure-Object | ForEach-Object Count")
    try:
        out = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True, timeout=30)
        return int((out.stdout or "0").strip() or 0) > 0
    except Exception:  # noqa: BLE001
        return True                      # unknown: safer not to close it afterwards


class Profile:
    """Open a GPM profile and attach Playwright; closes it at the end only when this job opened it."""

    def __init__(self, api: str, profile_id: str):
        self.api, self.id = api, profile_id
        self.was_running = profile_running(profile_id)
        self.pw = self.browser = None

    def __enter__(self):
        from playwright.sync_api import sync_playwright
        info = gpm(self.api, f"/api/v1/profiles/start/{self.id}")
        ws = info.get("websocket_debugging_url")
        if not ws:
            raise RuntimeError("GPM không trả về websocket_debugging_url (profile Firefox không điều khiển được qua CDP)")
        self.pw = sync_playwright().start()
        self.browser = self.pw.chromium.connect_over_cdp(ws)
        self.context = self.browser.contexts[0] if self.browser.contexts else self.browser.new_context()
        return self

    def __exit__(self, *exc):
        try:
            if self.browser:
                self.browser.close()          # detaches; the GPM browser itself keeps running
        finally:
            if self.pw:
                self.pw.stop()
            if not self.was_running:
                try:
                    gpm(self.api, f"/api/v1/profiles/stop/{self.id}", timeout=60)
                except Exception:  # noqa: BLE001
                    pass


# ---------------------------------------------------------------- files into <input type=file>
_DEEP_QUERY = """(sel) => {
  const walk = (root) => {
    const hit = root.querySelector(sel);
    if (hit) return hit;
    for (const el of root.querySelectorAll('*')) { if (el.shadowRoot) { const h = walk(el.shadowRoot); if (h) return h; } }
    return null;
  };
  return walk(document);
}"""


def set_files(page, selector: str, paths: list[str]) -> None:
    """Give a file input the PATHS of local files (CDP DOM.setFileInputFiles); the browser reads them from disk.

    Playwright's set_input_files over connect_over_cdp treats the browser as remote and streams the file contents
    through the connection, refusing anything over 50 MB ("Cannot transfer files larger than 50Mb to a browser not
    co-located with the server"). The GPM browser runs on this same machine, so the path is enough, at any size."""
    cdp = page.context.new_cdp_session(page)
    try:
        cdp.send("DOM.getDocument", {"depth": 0})
        res = cdp.send("Runtime.evaluate", {"expression": f"({_DEEP_QUERY})({json.dumps(selector)})"})
        oid = (res.get("result") or {}).get("objectId")
        if not oid:
            raise RuntimeError(f"không thấy ô chọn file {selector} trên trang")
        cdp.send("DOM.setFileInputFiles", {"files": [str(Path(x).resolve()) for x in paths], "objectId": oid})
    finally:
        try:
            cdp.detach()
        except Exception:  # noqa: BLE001
            pass


# ---------------------------------------------------------------- channels of a profile
def channels(api: str, profile_id: str) -> dict:
    with Profile(api, profile_id) as prof:
        page = prof.context.new_page()
        try:
            # YouTube keeps requests open, so "networkidle" may never come: wait for the channel list itself
            page.goto("https://www.youtube.com/channel_switcher", wait_until="domcontentloaded", timeout=90000)
            if "accounts.google.com" in page.url or "ServiceLogin" in page.url:
                return {"ok": False, "error": "profile chưa đăng nhập Google/YouTube", "channels": []}
            try:
                page.wait_for_selector("ytd-account-item-renderer", timeout=45000)
            except Exception:  # noqa: BLE001
                if "accounts.google.com" in page.url or "ServiceLogin" in page.url:
                    return {"ok": False, "error": "profile chưa đăng nhập Google/YouTube", "channels": []}
                return {"ok": True, "channels": []}     # signed in, but no channel on this account
            page.wait_for_timeout(1500)
            raw = page.evaluate("""() => [...document.querySelectorAll('ytd-account-item-renderer')].map(e => e.data || e.__data || null)""")
        finally:
            page.close()
    out = []
    for d in raw or []:
        if not d or not d.get("hasChannel", True):
            continue
        tokens = (((d.get("serviceEndpoint") or {}).get("selectActiveIdentityEndpoint") or {}).get("supportedTokens") or [])
        key = next((t["offlineCacheKeyToken"].get("clientCacheKey") for t in tokens if "offlineCacheKeyToken" in t), None)
        photos = ((d.get("accountPhoto") or {}).get("thumbnails") or [{}])
        out.append({"channel_id": f"UC{key}" if key else None,
                    "name": ((d.get("accountName") or {}).get("simpleText") or "").strip(),
                    "handle": ((d.get("channelHandle") or {}).get("simpleText") or "").strip(),
                    "subs": ((d.get("accountByline") or {}).get("simpleText") or "").strip(),
                    "photo": photos[-1].get("url"), "active": bool(d.get("isSelected"))})
    return {"ok": True, "channels": out}


# ---------------------------------------------------------------- upload through Studio
class Uploader:
    def __init__(self, page, job: dict):
        self.page, self.job = page, job
        self.shots = Path(job["shots"])
        self.shots.mkdir(parents=True, exist_ok=True)
        self.warnings: list[str] = []
        self.n = 0
        self.file_sent = False

    def shot(self, stage: str) -> str:
        self.n += 1
        path = self.shots / f"{self.n:02d}_{stage}.png"
        try:
            self.page.screenshot(path=str(path))
        except Exception:  # noqa: BLE001
            return ""
        return str(path)

    def stage(self, stage: str, msg: str) -> None:
        emit(stage=stage, msg=msg, shot=self.shot(stage))

    def warn(self, msg: str) -> None:
        self.warnings.append(msg)
        emit(stage="warn", msg=msg)

    def fill_box(self, selector: str, text: str) -> None:
        box = self.page.locator(selector).first
        box.wait_for(state="visible", timeout=60000)
        box.click()
        self.page.keyboard.press("Control+A")
        self.page.keyboard.press("Delete")
        if text:
            self.page.keyboard.insert_text(text)

    def radio(self, name: str) -> bool:
        el = self.page.locator(f'tp-yt-paper-radio-button[name="{name}"]').first
        try:
            el.wait_for(state="visible", timeout=15000)
            el.click()
            return True
        except Exception:  # noqa: BLE001
            return False

    def run(self) -> dict:
        job, page = self.job, self.page
        page.goto(f"https://studio.youtube.com/channel/{job['channel_id']}/videos/upload?d=ud",
                  wait_until="domcontentloaded", timeout=120000)
        if "accounts.google.com" in page.url:
            raise RuntimeError("profile chưa đăng nhập Google: đăng nhập trong GPM rồi chạy lại")
        if job["channel_id"] not in page.url:
            raise RuntimeError(f"Studio không mở được kênh {job['channel_id']} trong profile này (mở ra {page.url})")
        page.locator('input[name="Filedata"]').wait_for(state="attached", timeout=90000)
        set_files(page, 'input[name="Filedata"]', [job["video"]])
        self.file_sent = True
        self.stage("file", "đã chọn file, YouTube đang nhận video")

        # ---- details
        page.locator("#title-textarea #textbox").wait_for(state="visible", timeout=120000)
        self.fill_box("#title-textarea #textbox", job["title"][:100])
        self.fill_box("#description-textarea #textbox", job.get("description") or "")
        if job.get("thumbnail"):
            loader = page.locator("input#file-loader")
            if loader.count():
                set_files(page, "input#file-loader", [job["thumbnail"]])
                page.wait_for_timeout(2500)
            else:
                self.warn("kênh chưa được tải thumbnail riêng (cần xác minh số điện thoại): bỏ qua thumbnail")
        if not self.radio("VIDEO_MADE_FOR_KIDS_MFK" if job.get("made_for_kids") else "VIDEO_MADE_FOR_KIDS_NOT_MFK"):
            raise RuntimeError("không thấy câu hỏi «Made for kids» trong hộp Upload")
        self.stage("details", "đã điền tiêu đề, mô tả, thumbnail, dành cho trẻ em")
        toggle = page.locator("#toggle-button").first
        try:
            toggle.click(timeout=10000)
            page.wait_for_timeout(800)
        except Exception:  # noqa: BLE001
            self.warn("không mở được «Show more»: bỏ qua nội dung tổng hợp, thẻ, danh mục")
        else:
            if not self.radio("VIDEO_HAS_ALTERED_CONTENT_YES" if job.get("altered_content") else "VIDEO_HAS_ALTERED_CONTENT_NO"):
                self.warn("không thấy câu hỏi «Altered content»")
            tags = [t for t in (job.get("tags") or []) if t]
            if tags:
                try:
                    inp = page.locator("#tags-container input#text-input, input[aria-label='Tags']").first
                    inp.click(timeout=10000)
                    inp.fill(",".join(tags) + ",")
                    page.keyboard.press("Enter")
                except Exception:  # noqa: BLE001
                    self.warn("không điền được thẻ (tags)")
            if job.get("category"):
                try:
                    page.locator("#category ytcp-dropdown-trigger, #category").first.click(timeout=10000)
                    page.locator("tp-yt-paper-item").filter(has_text=job["category"]).first.click(timeout=10000)
                except Exception:  # noqa: BLE001
                    self.warn(f"không chọn được danh mục «{job['category']}»")
                    page.keyboard.press("Escape")
            self.stage("more", "đã điền nội dung tổng hợp, thẻ, danh mục")

        # ---- the next pages (monetization, ad suitability, elements, checks) until visibility
        for _ in range(8):
            if page.locator("#privacy-radios").first.is_visible():
                break
            if page.locator("ytcp-uploads-content-ratings").first.is_visible():
                self._ad_suitability()
            page.locator("#next-button").first.click(timeout=30000)
            page.wait_for_timeout(1500)
        else:
            raise RuntimeError("không tới được trang «Visibility» của hộp Upload")
        self.stage("visibility", "tới trang chế độ hiển thị")

        url = self._video_url()
        when = self._visibility()
        self._wait_uploaded()
        self._wait_checks()
        done = page.locator("#done-button").first
        done.click(timeout=30000)
        page.wait_for_timeout(4000)
        # YouTube still warning about checks/copyright: never confirm "publish anyway", the video stays a private draft
        warn = page.locator("ytcp-prechecks-warning-dialog").first
        if warn.count() and warn.is_visible():
            self.stage("checks", "YouTube còn cảnh báo kiểm tra/bản quyền khi bấm đăng")
            raise RuntimeError("YouTube hiện cảnh báo kiểm tra/bản quyền khi bấm đăng. KHÔNG đăng: video để riêng tư "
                               "trong Studio, xem mục Checks")
        self.stage("done", "đã bấm " + ("Schedule" if job.get("visibility") == "schedule" else "Save/Publish"))
        try:
            page.locator("ytcp-video-share-dialog #close-button, #close-button").first.click(timeout=8000)
        except Exception:  # noqa: BLE001
            pass
        return {"url": url, "video_id": url.rsplit("/", 1)[-1] if url else None, "scheduled_for": when,
                "warnings": self.warnings}

    def _ad_suitability(self) -> None:
        """Monetized channels: the ad-suitability questionnaire. The truthful answer for our videos is the user's to
        give, so we only go on when the job carries it (job.ad_rating = "none") and stop otherwise."""
        if self.job.get("ad_rating") != "none":
            raise RuntimeError("kênh bật kiếm tiền: YouTube hỏi «Ad suitability» (tự khai nội dung, phải do người dùng "
                               "trả lời). Video nháp đã nằm trong Studio: trả lời và lên lịch tay ở đó")
        page = self.page
        page.locator("ytcp-uploads-content-ratings ytcp-checkbox-lit").last.click(timeout=10000)
        page.locator("ytcp-uploads-content-ratings ytcp-button").filter(has_text="Submit").first.click(timeout=10000)
        page.wait_for_timeout(1500)

    def _video_url(self) -> str | None:
        for sel in ("ytcp-video-info a", ".video-url-fadeable a", "a[href*='youtu.be/']"):
            a = self.page.locator(sel).first
            try:
                a.wait_for(state="attached", timeout=60000)
                href = a.get_attribute("href")
                if href:
                    return href
            except Exception:  # noqa: BLE001
                continue
        self.warn("chưa đọc được link video trong hộp Upload")
        return None

    def _visibility(self) -> str | None:
        job, page = self.job, self.page
        vis = job.get("visibility") or "private"
        if vis != "schedule":
            name = {"public": "PUBLIC", "unlisted": "UNLISTED"}.get(vis, "PRIVATE")
            radio = page.locator(f'tp-yt-paper-radio-button[name="{name}"]').first
            if not radio.is_visible():          # «Save or publish» folded (e.g. after touching Schedule): open it
                try:
                    page.locator("#first-container-expand-button").first.click(timeout=5000)
                    page.wait_for_timeout(800)
                except Exception:  # noqa: BLE001
                    pass
            if not self.radio(name):
                raise RuntimeError(f"không chọn được chế độ hiển thị {name}")
            page.wait_for_timeout(500)
            if radio.get_attribute("aria-checked") != "true" and radio.get_attribute("checked") is None:
                raise RuntimeError(f"Studio chưa nhận chế độ hiển thị {name} (nút chưa được chọn)")
            self.stage("visibility", f"đã chọn {name}")
            return None
        # the date and time are typed in the browser's own time zone (the profile's fingerprint), then read back
        at = job["publish_at"]
        local = page.evaluate("""(iso) => { const d = new Date(iso);
            const tz = Intl.DateTimeFormat().resolvedOptions().timeZone;
            const date = d.toLocaleDateString('en-US', {month: 'short', day: 'numeric', year: 'numeric'});
            const time = d.toLocaleTimeString('en-US', {hour: 'numeric', minute: '2-digit'}).replace(/[\\u202f\\u00a0]/g, ' ');
            return {date, time, tz}; }""", at)
        page.locator("#second-container-expand-button").first.click(timeout=20000)
        page.wait_for_timeout(1000)
        page.locator("#datepicker-trigger").first.click(timeout=20000)
        date_in = page.locator("ytcp-date-picker tp-yt-paper-input input, ytcp-date-picker input").first
        date_in.wait_for(state="visible", timeout=15000)
        date_in.fill(local["date"])
        date_in.press("Enter")
        page.wait_for_timeout(800)
        time_in = page.locator("ytcp-datetime-picker #time-of-day-container input, ytcp-datetime-picker input").last
        time_in.click(timeout=15000)
        time_in.fill(local["time"])
        time_in.press("Enter")
        page.wait_for_timeout(800)
        shown = self._picker_text()
        self.stage("schedule", f"lên lịch {local['date']} {local['time']} ({local['tz']}); Studio hiện: {shown}")
        if _norm(local["time"]) not in _norm(shown):
            # one more try: the time dropdown sometimes swallows the first Enter
            time_in.click(timeout=15000)
            time_in.fill(local["time"])
            time_in.press("Enter")
            page.wait_for_timeout(800)
            shown = self._picker_text()
            if _norm(local["time"]) not in _norm(shown):
                raise RuntimeError(f"Studio không nhận giờ lên lịch {local['time']} (đang hiện «{shown}»)")
        return f"{local['date']} {local['time']} {local['tz']}"

    def _picker_text(self) -> str:
        """What the schedule picker shows: its text plus the VALUES of its inputs (innerText leaves input values out,
        so the typed time never appears there)."""
        return self.page.evaluate("""() => {
            const p = document.querySelector('ytcp-datetime-picker');
            if (!p) return '';
            const vals = [];
            const walk = (root) => { root.querySelectorAll('input').forEach(i => vals.push(i.value));
                root.querySelectorAll('*').forEach(e => { if (e.shadowRoot) walk(e.shadowRoot); }); };
            walk(p);
            return (p.innerText + ' ' + vals.join(' ')).replace(/\\s+/g, ' ').trim(); }""")

    # the status line at the bottom of the upload dialog, once YouTube's checks are over:
    #   "Checks complete. No issues found."  -> publish
    #   "Checks complete. Copyright-protected content found." / "... claim ..." / "... blocked ..."  -> stop
    _CHECKS_BAD = ("copyright", "claim", "blocked", "takedown", "strike", "violat", "issues found", "issue found")

    def _status_label(self) -> str:
        """Only the status line, never the Checks page or the whole dialog: the Checks page always carries an
        explanation mentioning «copyright» and «restrict», and the title/description may contain anything."""
        try:
            t = self.page.locator("ytcp-video-upload-progress .progress-label, .progress-label").first.inner_text(timeout=5000)
        except Exception:  # noqa: BLE001
            return ""
        return " ".join(t.split())

    def _wait_checks(self, limit_s: int = 2 * 3600) -> None:
        """Publish only after YouTube's checks say «No issues found». Any copyright finding stops the job: the video
        stays a private draft in Studio and nothing is published."""
        t0, last = time.time(), ""
        self.stage("checks", "chờ YouTube kiểm tra bản quyền")
        while time.time() - t0 < limit_s:
            label = self._status_label()
            low = label.lower()
            if label and label != last:
                emit(stage="progress", msg=label)
                last = label
            if "daily upload limit" in low or "processing abandoned" in low:
                raise RuntimeError(f"YouTube báo: {label}")
            rest = low.replace("no issues found", "")
            if any(w in rest for w in self._CHECKS_BAD):
                self.stage("checks", f"YouTube phát hiện vấn đề bản quyền: {label}")
                raise RuntimeError(f"YouTube phát hiện vấn đề bản quyền («{label}»). KHÔNG đăng: video để riêng tư "
                                   f"trong Studio, xem chi tiết ở mục Checks")
            if "no issues found" in low:
                self.stage("checks", "YouTube kiểm tra xong: không vi phạm bản quyền")
                return
            time.sleep(10)
        raise RuntimeError("quá 2 giờ mà YouTube chưa kiểm tra bản quyền xong. KHÔNG đăng: video để riêng tư trong "
                           "Studio, lên lịch tay khi Checks báo «No issues found»")

    def _wait_uploaded(self, limit_s: int = 4 * 3600) -> None:
        """Closing the browser before the file is fully sent cancels the upload."""
        page, t0, last = self.page, time.time(), ""
        while time.time() - t0 < limit_s:
            label = ""
            try:
                label = page.locator("ytcp-video-upload-progress .progress-label, .progress-label").first.inner_text(timeout=5000)
            except Exception:  # noqa: BLE001
                pass
            label = " ".join(label.split())
            if label and label != last:
                emit(stage="progress", msg=label)
                last = label
            low = label.lower()
            if "daily upload limit" in low or "error" in low or "failed" in low:
                raise RuntimeError(f"YouTube báo: {label}")
            sent = ("upload complete" in low or "processing" in low or "checks complete" in low or "checking" in low
                    or "processed" in low)
            if label and "uploading" not in low and sent:
                return
            time.sleep(5)
        raise RuntimeError("quá 4 giờ mà file chưa gửi xong")


def upload(job: dict) -> dict:
    with Profile(job.get("api") or API, job["profile_id"]) as prof:
        page = prof.context.new_page()
        try:
            up = Uploader(page, job)
            try:
                res = up.run()
            except Exception as e:
                up.shot("error")
                if up.file_sent:
                    # closing the browser now would cancel the upload: let the file finish so the draft in Studio is
                    # complete (it stays private) and can be scheduled by hand there
                    emit(stage="warn", msg=f"lỗi ({e}); chờ file tải lên xong rồi mới đóng trình duyệt")
                    try:
                        up._wait_uploaded()
                    except Exception:  # noqa: BLE001
                        pass
                raise
        finally:
            try:
                page.close()
            except Exception:  # noqa: BLE001
                pass
    return res


def main(argv: list[str]) -> int:
    try:
        if len(argv) >= 2 and argv[0] == "channels":
            emit(**channels(argv[2] if len(argv) > 2 else API, argv[1]))
            return 0
        if len(argv) == 2 and argv[0] == "upload":
            job = json.loads(Path(argv[1]).read_text(encoding="utf-8"))
            emit(stage="start", msg=f"mở profile GPM {job['profile_id']} lúc {datetime.now():%H:%M:%S}")
            emit(done=True, ok=True, **upload(job))
            return 0
    except Exception as e:  # noqa: BLE001
        emit(done=True, ok=False, error=f"{type(e).__name__}: {e}")
        return 1
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
