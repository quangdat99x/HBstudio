"""Images from gemini.google.com with the user's own Gemini subscription (no API cost), driven by Playwright.

Model ids "gemini-web:<mode>" (gen.py image): <mode> is the text of the model picker entry to choose ("Pro",
"Thinking"... matched case-insensitively), empty = leave the account's current choice. One Chrome profile of the app's
own (setting gemini_web_profile, empty = work/gemini_web/profile) stays signed in: `gen.py gemini-web login` opens it
visibly once. Chrome 136+ refuses automation of the user's everyday profile, hence a separate folder.

Window (setting gemini_web_mode): hidden = a normal Chrome window placed off screen (Google trusts it most),
headless = no window at all (Google may ask to sign in again), show = visible (to watch or debug).

Self-repair: the selectors live in DEFAULT_SELECTORS, overridden by work/gemini_web/selectors.json. When one no longer
finds its element (Gemini redesigned the page), the page as it is (trimmed HTML + screenshot) goes to a short Claude
run that answers new selectors; they are tried on the live page and saved when they match. One Claude run per
redesign, not per image.
"""
from __future__ import annotations

import base64
import json
import mimetypes
import os
import re
import shutil
import time
from pathlib import Path

from . import config, db

URL = "https://gemini.google.com/app"
DIR = config.WORK_DIR / "gemini_web"
SELECTORS_FILE = DIR / "selectors.json"
MODES = ("hidden", "headless", "show")

# key -> alternatives, first one that matches wins. Playwright selector syntax (CSS plus :has-text()).
DEFAULT_SELECTORS = {
    "input": ['rich-textarea .ql-editor', 'div[contenteditable="true"][role="textbox"]'],
    "send": ['button[aria-label*="Send" i]', 'button.send-button'],
    "busy": ['button[aria-label*="Stop" i]'],
    "upload_menu": ['button[aria-label*="upload file menu" i]', 'button[aria-label*="Add files" i]',
                    'button[aria-label*="upload" i]'],
    "upload_item": ['[data-test-id="local-images-files-uploader-button"]', '[role^="menuitem"]:has-text("Upload")',
                    'button:has-text("Upload files")'],
    "image_tool": ['[role="menuitemcheckbox"]:has-text("Create image")', '[role="menuitemcheckbox"]:has-text("image")'],
    "mode_button": ['[data-test-id="bard-mode-menu-button"]', 'bard-mode-switcher button', 'button.input-area-switch'],
    "mode_option": ['[role^="menuitem"]', 'mat-option', '[role="option"]'],
    "response": ['model-response', '[data-test-id="model-response"]'],
    "image": ['generated-image img', 'single-image img', '.generated-image img'],
    "download": ['button[aria-label*="Download full size" i]', 'button[data-test-id="download-generated-image-button"]',
                 'button[aria-label*="Download" i]'],
    "signed_out": ['a[href*="ServiceLogin"]', 'a:has-text("Sign in")', 'button:has-text("Sign in")'],
    # visible Gemini mark in the bottom-right corner of pictures of the Pro plan, as fractions of the short side:
    # [from right edge, from bottom edge, size]; gen.py blurs it away (delogo) when gemini_web_delogo = 1
    "watermark": [0.085, 0.085, 0.065],
}
# what each key is, for the repair prompt
PURPOSE = {
    "input": "the prompt box where the user types a message (contenteditable)",
    "send": "the button that sends the typed message",
    "upload_menu": "the button next to the prompt box that opens the menu to attach files/images",
    "upload_item": "the entry of the opened attach menu that uploads files from the computer (opens a file chooser)",
    "mode_button": "the model / mode picker button (shows the current model, e.g. Fast, Thinking, Pro)",
    "image": "the generated image (<img>) inside the latest answer of Gemini",
    "download": "the button shown on a generated image that downloads it in full size",
}
QUOTA_HINTS = ("limit", "quota", "try again later", "come back", "more images", "giới hạn", "thử lại sau", "tomorrow")


class GeminiWebError(Exception):
    """code: login (not signed in) | quota (image limit of the plan) | refused (answer without a picture) |
    selector (an element is gone and the repair did not find it) | busy | timeout | setup"""

    def __init__(self, message: str, code: str = "error"):
        super().__init__(message)
        self.code = code


def _say_default(msg: str) -> None:
    print(msg, flush=True)


def profile_dir() -> Path:
    return Path(db.get_setting("gemini_web_profile") or (DIR / "profile"))


def selectors() -> dict:
    sel = {k: (list(v) if isinstance(v, list) else v) for k, v in DEFAULT_SELECTORS.items()}
    try:
        saved = json.loads(SELECTORS_FILE.read_text(encoding="utf-8"))
        for k, v in saved.items():
            if k in sel and v:
                sel[k] = v
    except (OSError, ValueError):
        pass
    return sel


def _save_selectors(key: str, found: list[str]) -> None:
    try:
        saved = json.loads(SELECTORS_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        saved = {}
    old = saved.get(key) or DEFAULT_SELECTORS.get(key) or []
    saved[key] = found + [s for s in old if s not in found]
    saved.setdefault("_history", []).append({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "key": key, "selectors": found})
    saved["_history"] = saved["_history"][-30:]
    DIR.mkdir(parents=True, exist_ok=True)
    SELECTORS_FILE.write_text(json.dumps(saved, ensure_ascii=False, indent=2), encoding="utf-8")


# ---------------------------------------------------------------- one browser at a time (the profile is locked)
class _Lock:
    def __init__(self, say, wait: int):
        self.path, self.say, self.wait = DIR / "busy.lock", say, wait

    def __enter__(self):
        DIR.mkdir(parents=True, exist_ok=True)
        deadline, told = time.time() + self.wait, False
        while True:
            try:
                os.close(os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY))
                return self
            except FileExistsError:
                try:
                    if time.time() - self.path.stat().st_mtime > 20 * 60:     # left by a killed run
                        self.path.unlink(missing_ok=True)
                        continue
                except OSError:
                    continue
                if time.time() > deadline:
                    raise GeminiWebError("trình duyệt Gemini đang bận với ảnh khác quá lâu", "busy")
                if not told:
                    self.say("  Gemini web đang vẽ ảnh khác, chờ tới lượt (ảnh qua trình duyệt chạy lần lượt)…")
                    told = True
                time.sleep(2)

    def touch(self):
        try:
            os.utime(self.path)
        except OSError:
            pass

    def __exit__(self, *exc):
        self.path.unlink(missing_ok=True)


# ---------------------------------------------------------------- browser
def _chrome_channel() -> str | None:
    for ch, exe in (("chrome", r"Google\Chrome\Application\chrome.exe"), ("msedge", r"Microsoft\Edge\Application\msedge.exe")):
        for root in (os.environ.get("PROGRAMFILES"), os.environ.get("PROGRAMFILES(X86)"), os.environ.get("LOCALAPPDATA")):
            if root and (Path(root) / exe).exists():
                return ch
    return None


class Browser:
    def __init__(self, mode: str | None = None, say=_say_default):
        self.mode = mode if mode in MODES else (db.get_setting("gemini_web_mode") or "hidden")
        self.say = say
        self.sel = selectors()
        self.repaired: set[str] = set()

    def __enter__(self):
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as e:
            raise GeminiWebError("thiếu Playwright trong Python của app (pip install playwright)", "setup") from e
        channel = _chrome_channel()
        if not channel:
            raise GeminiWebError("không thấy Chrome hay Edge trên máy", "setup")
        profile_dir().mkdir(parents=True, exist_ok=True)
        args = ["--disable-blink-features=AutomationControlled", "--no-first-run", "--no-default-browser-check"]
        if self.mode == "hidden":
            args += ["--window-position=-32000,-32000"]
        self.pw = sync_playwright().start()
        try:
            self.ctx = self.pw.chromium.launch_persistent_context(
                str(profile_dir()), channel=channel, headless=self.mode == "headless", args=args,
                ignore_default_args=["--enable-automation"], viewport={"width": 1400, "height": 1000},
                accept_downloads=True)
        except Exception as e:  # noqa: BLE001
            self.pw.stop()
            msg = str(e)
            if "user data directory is already in use" in msg.lower() or "ProcessSingleton" in msg:
                raise GeminiWebError(f"hồ sơ {profile_dir()} đang mở ở cửa sổ Chrome khác: đóng cửa sổ đó rồi chạy lại",
                                     "busy") from e
            raise GeminiWebError(f"không mở được Chrome: {msg[:300]}", "setup") from e
        self.page = self.ctx.pages[0] if self.ctx.pages else self.ctx.new_page()
        return self

    def __exit__(self, *exc):
        try:
            self.ctx.close()
        finally:
            self.pw.stop()

    # ------------------------------------------------------------ finding elements
    def find(self, key: str, within=None, timeout: float = 15, visible: bool = True):
        """First alternative of `key` that matches (within an element if given), or None after `timeout` seconds."""
        root = within or self.page
        deadline = time.time() + timeout
        while True:
            for s in self.sel.get(key) or []:
                try:
                    loc = root.locator(s)
                    n = loc.count()
                    for i in range(n - 1, -1, -1) if key in ("response", "image") else range(n):
                        el = loc.nth(i)
                        if not visible or el.is_visible():
                            return el
                except Exception:  # noqa: BLE001  (a selector the page cannot parse: try the next one)
                    continue
            if time.time() >= deadline:
                return None
            time.sleep(0.5)

    def need(self, key: str, within=None, timeout: float = 15):
        """Like find, but an element that is gone gets one repair by Claude before it fails."""
        el = self.find(key, within, timeout)
        if el is not None:
            return el
        if key in PURPOSE and key not in self.repaired:
            self.repaired.add(key)
            if self.repair(key):
                el = self.find(key, within, 10)
                if el is not None:
                    return el
        raise GeminiWebError(f"không tìm thấy “{PURPOSE.get(key, key)}” trên trang Gemini (giao diện đổi?); "
                             f"xem ảnh chụp trong {DIR / 'repair'}", "selector")

    # ------------------------------------------------------------ self-repair
    def repair(self, key: str) -> bool:
        from . import claude_runner
        self.say(f"  Gemini web: không thấy {key}, nhờ Claude đọc lại trang để tìm selector mới…")
        d = DIR / "repair" / f"{time.strftime('%Y%m%d-%H%M%S')}-{key}"
        d.mkdir(parents=True, exist_ok=True)
        try:
            self.page.screenshot(path=str(d / "page.png"))
            html = self.page.evaluate(_TRIM_JS)
        except Exception as e:  # noqa: BLE001
            self.say(f"  không chụp được trang để sửa: {e}")
            return False
        (d / "page.html").write_text(html[:600_000], encoding="utf-8")
        tried = self.sel.get(key) or []
        prompt = (
            "You fix the selectors of a Playwright script that drives gemini.google.com (Google Gemini web app).\n"
            f"The element needed now: `{key}` = {PURPOSE[key]}.\n"
            f"These selectors no longer match anything visible: {json.dumps(tried)}\n"
            "In the current folder: page.png (screenshot of the page right now) and page.html (its DOM, scripts and "
            "styles removed, long attribute values cut). Look at the screenshot, then Grep/Read page.html to find the element.\n"
            "Prefer stable hooks: aria-label, data-test-id, role, custom element tag names; avoid generated class names "
            "and nth-child. Playwright syntax is allowed (CSS, :has-text(\"...\"), attribute [x*=\"y\" i]).\n"
            "Answer with ONE line of JSON only, no prose: {\"selectors\": [\"best\", \"alternative\", ...]} "
            "(1 to 4 entries), or {\"selectors\": [], \"why\": \"...\"} when the element is not on this page.")
        res = claude_runner.run(prompt, cwd=d, tools="Read,Grep,Glob", allowed_tools="Read,Grep,Glob",
                                permission_mode="dontAsk", max_turns=15, timeout=900, isolated=True, fallback_model="",
                                model=db.get_setting("gemini_web_repair_model") or "sonnet", effort="medium",
                                log_path=d / "claude.jsonl")
        text = res.get("result") or res.get("text") or ""
        (d / "answer.txt").write_text(text or (res.get("error") or ""), encoding="utf-8")
        m = re.search(r"\{.*\}", text, re.S)
        try:
            cands = [s for s in json.loads(m.group(0)).get("selectors") or [] if isinstance(s, str) and s.strip()] if m else []
        except ValueError:
            cands = []
        if not cands:
            self.say(f"  Claude không tìm ra selector cho {key}: {(text or res.get('error') or '')[:200]}")
            return False
        good = []
        for s in cands:
            try:
                if self.page.locator(s).count():
                    good.append(s)
            except Exception:  # noqa: BLE001
                continue
        if not good:
            self.say(f"  selector Claude đề xuất cho {key} không khớp gì trên trang: {cands}")
            return False
        _save_selectors(key, good)
        self.sel[key] = good + [s for s in self.sel.get(key) or [] if s not in good]
        self.say(f"  ✓ đã sửa selector {key}: {good[0]} (lưu ở {SELECTORS_FILE.name})")
        _prune(DIR / "repair", keep=8)
        return True

    # ------------------------------------------------------------ pages
    def open_chat(self) -> None:
        self.page.goto(URL, wait_until="domcontentloaded", timeout=60_000)
        # signed out, Gemini still chats (Flash-Lite, no image plan): only the Sign in link tells
        if "accounts.google.com" not in self.page.url:
            self.need("input", timeout=30)
        if "accounts.google.com" in self.page.url or self.find("signed_out", timeout=1.5) is not None:
            raise GeminiWebError("hồ sơ Chrome của Gemini web chưa đăng nhập: Cài đặt → Gemini web → Mở để đăng nhập", "login")

    def signed_in(self) -> bool:
        try:
            self.open_chat()
            return True
        except GeminiWebError as e:
            if e.code == "login":
                return False
            raise

    def pick_mode(self, mode: str) -> None:
        if not mode:
            return
        btn = self.need("mode_button")
        if re.search(re.escape(mode), btn.inner_text() or "", re.I):
            return
        btn.click()
        time.sleep(0.8)
        names = []
        for s in self.sel["mode_option"]:
            try:
                loc = self.page.locator(s)
                for i in range(loc.count()):
                    el = loc.nth(i)
                    if not el.is_visible():
                        continue
                    txt = (el.inner_text() or "").strip()
                    names.append(txt.splitlines()[0] if txt else "")
                    if re.search(re.escape(mode), txt, re.I):
                        el.click()
                        time.sleep(0.8)
                        return
            except Exception:  # noqa: BLE001
                continue
            if names:
                break
        self.page.keyboard.press("Escape")
        raise GeminiWebError(f"không có chế độ “{mode}” trong menu model của Gemini; đang có: "
                             f"{', '.join(n for n in names if n) or '(không đọc được menu)'}", "setup")

    def image_tool(self) -> None:
        """Switch on the "Create image" tool of the attach menu (best effort: the prompt asks for an image anyway)."""
        try:
            self.need("upload_menu").click()
            time.sleep(0.6)
            tool = self.find("image_tool", timeout=2)
            if tool is not None and tool.get_attribute("aria-checked") != "true" \
                    and tool.get_attribute("aria-disabled") != "true":
                tool.click(timeout=5000)
                time.sleep(0.5)
            else:
                self.page.keyboard.press("Escape")
        except Exception:  # noqa: BLE001
            self.page.keyboard.press("Escape")

    def attach(self, refs: list[Path]) -> None:
        if not refs:
            return
        paths = [str(Path(r).resolve()) for r in refs]
        try:
            menu = self.need("upload_menu")
            with self.page.expect_file_chooser(timeout=15_000) as fc:
                menu.click()
                time.sleep(0.6)
                item = self.find("upload_item", timeout=3)
                if item is None and "upload_item" not in self.repaired:  # the menu is open: the moment to look for it
                    item = self.need("upload_item", timeout=1)
                if item.get_attribute("aria-disabled") == "true":
                    raise GeminiWebError("mục Upload files đang bị khoá (chưa đăng nhập?)", "login")
                item.click(timeout=5000)
            fc.value.set_files(paths)
        except Exception as e:  # noqa: BLE001  the file chooser flow failed: the menu's file input, then a drop
            self.say(f"  đính kèm qua menu không được ({str(e)[:120]}), thử cách khác…")
            try:
                self.page.locator('input[type="file"]').first.set_input_files(paths, timeout=5000)
                self.page.keyboard.press("Escape")
            except Exception:  # noqa: BLE001
                self.page.keyboard.press("Escape")
                files = [{"name": Path(p).name, "mime": mimetypes.guess_type(p)[0] or "image/png",
                          "data": base64.b64encode(Path(p).read_bytes()).decode("ascii")} for p in paths]
                self.need("input").evaluate(_DROP_JS, files)
        self._wait_send_ready(120)

    def _wait_send_ready(self, timeout: float) -> None:
        """Uploads keep the send button disabled until they are done."""
        deadline = time.time() + timeout
        time.sleep(1.5)
        while time.time() < deadline:
            btn = self.find("send", timeout=0)
            if btn is not None:
                try:
                    if btn.is_enabled() and btn.get_attribute("aria-disabled") != "true":
                        return
                except Exception:  # noqa: BLE001
                    pass
            time.sleep(1)

    def send(self, text: str) -> None:
        box = self.need("input")
        box.click()
        box.fill(text)
        time.sleep(0.5)
        btn = self.find("send", timeout=5)
        if btn is not None and btn.is_enabled():
            btn.click()
        else:
            box.press("Enter")

    def wait_image(self, timeout: int, lock: _Lock | None = None):
        """Wait for the answer: returns the <img> of the generated picture, or raises quota / refused / timeout."""
        start = time.time()
        deadline = start + timeout
        last_text, stable_since = None, time.time()
        while time.time() < deadline:
            if lock:
                lock.touch()
            resp = self.find("response", timeout=0)
            if resp is not None:
                img = self.find("image", within=resp, timeout=0)
                if img is not None:
                    try:
                        if img.evaluate("i => i.complete && i.naturalWidth > 64"):
                            return img
                    except Exception:  # noqa: BLE001
                        pass
                busy = self.find("busy", timeout=0) is not None
                try:
                    text = (resp.inner_text() or "").strip()
                except Exception:  # noqa: BLE001
                    text = ""
                if text != last_text:
                    last_text, stable_since = text, time.time()
                if not busy and text and time.time() - stable_since > 8 and time.time() - start > 25:
                    any_img = resp.locator("img").count()
                    if any_img and "image" not in self.repaired:
                        self.repaired.add("image")
                        if self.repair("image"):
                            continue
                    low = text.lower()
                    code = "quota" if any(h in low for h in QUOTA_HINTS) else "refused"
                    raise GeminiWebError(("Gemini báo hết lượt vẽ ảnh: " if code == "quota" else "Gemini trả lời không có ảnh: ")
                                         + text[:300], code)
            time.sleep(2)
        raise GeminiWebError(f"Gemini chưa trả ảnh sau {timeout} s", "timeout")

    def download(self, img) -> tuple[bytes, str]:
        """Full-size picture through the Download button; the <img> itself when that button cannot be used."""
        try:
            img.hover()
            time.sleep(0.8)
            container = img.locator("xpath=ancestor::*[self::generated-image or self::single-image][1]")
            btn = self.find("download", within=container if container.count() else None, timeout=4)
            if btn is None and "download" not in self.repaired:
                btn = self.need("download", timeout=1)
            if btn is not None:
                with self.page.expect_download(timeout=90_000) as dl:
                    btn.click()
                path = dl.value.path()
                data = Path(path).read_bytes()
                if len(data) > 1000:
                    return data, mimetypes.guess_type(dl.value.suggested_filename)[0] or "image/png"
        except Exception as e:  # noqa: BLE001
            self.say(f"  không tải được bản đầy đủ ({str(e)[:160]}), lấy ảnh đang hiển thị")
        src = img.get_attribute("src") or ""
        if src.startswith(("blob:", "data:")):
            b64 = img.evaluate("""async i => { const b = await (await fetch(i.src)).blob();
                return await new Promise(r => { const f = new FileReader(); f.onload = () => r(f.result); f.readAsDataURL(b); }); }""")
            head, _, body = b64.partition(",")
            return base64.b64decode(body), head[5:].split(";")[0] or "image/png"
        for url in (re.sub(r"=[swh]\d+[^/=]*$", "=s0", src), src):
            r = self.ctx.request.get(url, timeout=90_000)
            if r.ok and len(r.body()) > 1000:
                return r.body(), (r.headers.get("content-type") or "image/png").split(";")[0]
        raise GeminiWebError("không lấy được file ảnh từ trang Gemini", "selector")


# ---------------------------------------------------------------- entry points
def generate(prompt: str, refs: list[Path], *, mode: str = "", aspect: str | None = None, n: int = 1,
             timeout: int = 420, say=_say_default) -> list[tuple[bytes, str]]:
    """n pictures, each in a new chat. Raises GeminiWebError."""
    text = ("Generate an image" + (f" with aspect ratio {aspect}" if aspect else "")
            + (" using the attached image(s) as reference" if refs else "") + ".\n\n" + prompt)
    out = []
    with _Lock(say, wait=max(900, timeout * 3)) as lock, Browser(say=say) as b:
        for i in range(n):
            b.open_chat()
            b.pick_mode(mode)
            b.image_tool()
            b.attach(refs)
            b.send(text)
            say(f"  Gemini web: đã gửi{f' ({i + 1}/{n})' if n > 1 else ''}, đang chờ ảnh…")
            img = b.wait_image(timeout, lock)
            out.append(b.download(img))
    return out


def status(mode: str | None = None) -> dict:
    with _Lock(_say_default, wait=60), Browser(mode=mode or "headless", say=lambda m: None) as b:
        ok = b.signed_in()
        current = ""
        if ok:
            btn = b.find("mode_button", timeout=3)
            current = (btn.inner_text() or "").strip().splitlines()[0] if btn is not None else ""
        return {"ok": ok, "signed_in": ok, "mode": current, "profile": str(profile_dir()),
                "error": None if ok else "chưa đăng nhập: bấm Mở để đăng nhập"}


def login(say=_say_default, wait: int = 15 * 60) -> dict:
    """Visible window on the app's profile: the user signs in to Google, then closes the window."""
    with _Lock(say, wait=30), Browser(mode="show", say=say) as b:
        b.page.goto(URL, wait_until="domcontentloaded", timeout=60_000)
        say("Đăng nhập tài khoản Google có gói Gemini trong cửa sổ vừa mở, xong thì đóng cửa sổ.")
        deadline = time.time() + wait
        while time.time() < deadline:
            try:
                if not b.ctx.pages:
                    break
                b.ctx.pages[0].wait_for_timeout(1000)
            except Exception:  # noqa: BLE001  window closed
                break
    return {"ok": True, "profile": str(profile_dir())}


def _prune(folder: Path, keep: int) -> None:
    try:
        old = sorted((p for p in folder.iterdir() if p.is_dir()), key=lambda p: p.name)[:-keep]
    except OSError:
        return
    for p in old:
        shutil.rmtree(p, ignore_errors=True)


_TRIM_JS = """() => {
  const c = document.body.cloneNode(true);
  c.querySelectorAll('script,style,noscript,link,meta,path,defs,symbol').forEach(e => e.remove());
  c.querySelectorAll('*').forEach(e => {
    e.removeAttribute('style');
    for (const a of [...e.attributes]) if (a.value.length > 160) e.setAttribute(a.name, a.value.slice(0, 80) + '…');
  });
  return c.outerHTML;
}"""

_DROP_JS = """(el, files) => {
  const dt = new DataTransfer();
  for (const f of files) {
    const bin = atob(f.data), buf = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) buf[i] = bin.charCodeAt(i);
    dt.items.add(new File([buf], f.name, {type: f.mime}));
  }
  for (const t of ['dragenter', 'dragover', 'drop'])
    el.dispatchEvent(new DragEvent(t, {bubbles: true, cancelable: true, dataTransfer: dt}));
}"""
