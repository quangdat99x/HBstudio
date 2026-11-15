"""Approvals through a Telegram bot: when a project runs step by step (not "tự chạy tất cả"), every step that waits for
the user's approval is pushed to the user's Telegram chat with buttons; the user approves (and starts the next step),
asks for changes or re-runs the step from the phone.

Only the Telegram Bot API over HTTPS (standard library). The bot answers ONE chat: the one paired on the Settings page
(the user sends `/start <code>` to the bot). Every other chat is ignored.

Card text carries a tag `#p<project id> · <step>` so a reply to a card needs no stored state:
  - reply to a card with text       -> the note goes to Claude as a chat on that step (Claude edits, then a new card)
  - reply to a "làm lại" prompt     -> the step runs again with the note
"""
from __future__ import annotations

import json
import logging
import re
import secrets
import threading
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime
from pathlib import Path

from . import config, db, store, workflow

log = logging.getLogger("creater.tgbot")

ORIGIN = "[Telegram] "                   # prefix of the chat messages the bot sends to Claude
_TAG = re.compile(r"#p(\d+) · ([a-z_]+)(?: · (redo))?")
IMG_EXT = (".jpg", ".jpeg", ".png", ".webp")


# ---------------------------------------------------------------- settings
def token() -> str:
    return (db.get_setting("tg_bot_token") or "").strip()


def chat_id() -> str:
    return (db.get_setting("tg_bot_chat") or "").strip()


def enabled() -> bool:
    return bool(token() and chat_id() and db.setting_bool("tg_bot_on"))


def pair_code() -> str:
    code = (db.get_setting("tg_bot_pair") or "").strip()
    if not code:
        code = secrets.token_hex(3).upper()
        db.set_setting("tg_bot_pair", code)
    return code


def unpair() -> None:
    db.set_setting("tg_bot_chat", "")
    db.set_setting("tg_bot_chat_name", "")
    db.set_setting("tg_bot_pair", secrets.token_hex(3).upper())


# ---------------------------------------------------------------- Bot API
class TgError(RuntimeError):
    pass


def call(method: str, http_timeout: int = 30, tok: str | None = None, **params) -> dict | list | bool:
    tok = tok or token()
    if not tok:
        raise TgError("chưa có token bot")
    req = urllib.request.Request(f"https://api.telegram.org/bot{tok}/{method}",
                                 data=json.dumps(params, ensure_ascii=False).encode("utf-8"),
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=http_timeout) as r:
            data = json.load(r)
    except urllib.error.HTTPError as e:
        try:
            data = json.load(e)
        except Exception:  # noqa: BLE001
            raise TgError(f"Telegram HTTP {e.code}") from None
    if not data.get("ok"):
        raise TgError(data.get("description") or "Telegram báo lỗi")
    return data.get("result")


def send_photo(path: Path, caption: str = "") -> None:
    boundary = uuid.uuid4().hex
    parts = []
    for name, value in (("chat_id", chat_id()), ("caption", caption[:1000])):
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode("utf-8"))
    parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="photo"; filename="{path.name}"\r\n'
                 f'Content-Type: image/jpeg\r\n\r\n'.encode("utf-8") + path.read_bytes() + b"\r\n")
    parts.append(f"--{boundary}--\r\n".encode())
    req = urllib.request.Request(f"https://api.telegram.org/bot{token()}/sendPhoto", data=b"".join(parts),
                                 headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    with urllib.request.urlopen(req, timeout=120) as r:
        json.load(r)


def send(text: str, buttons: list[list[tuple[str, str]]] | None = None, **extra) -> dict | None:
    if not (token() and chat_id()):
        return None
    params = {"chat_id": chat_id(), "text": text[:4000], "parse_mode": "HTML", "disable_web_page_preview": True, **extra}
    if buttons:
        params["reply_markup"] = {"inline_keyboard": [[{"text": t, "callback_data": d} for t, d in row] for row in buttons]}
    return call("sendMessage", **params)


def _esc(s: str) -> str:
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _safe(fn, *a, **kw) -> None:
    """Notifications never break the work that sends them."""
    try:
        fn(*a, **kw)
    except Exception as e:  # noqa: BLE001
        log.warning("telegram: %s", e)


# ---------------------------------------------------------------- cards
def _link(p: dict) -> str:
    return f"http://127.0.0.1:{config.PORT}/p/{p['id']}"


def _head(p: dict) -> str:
    desk = "Tin tức" if store.kind_of(p) == "news" else "Tài liệu"
    return f"🎬 <b>{_esc(p.get('title') or '')}</b>\n<i>{desk}</i> · {_link(p)}"


def _preview(p: dict, step: str, since: str | None) -> Path | None:
    """The newest picture the step produced (contact sheet, chosen thumbnail), to show next to the card."""
    d = store.project_dir(p)
    t0 = 0.0
    try:
        t0 = datetime.fromisoformat(since).timestamp() - 5 if since else 0.0
    except ValueError:
        pass
    folders = [d / "out" / "review"]
    if step == "metadata":
        folders = [d / "7_metadata" / "thumbs", d / "7_metadata"] + folders
    for folder in folders:
        if not folder.is_dir():
            continue
        pics = [f for f in folder.iterdir() if f.suffix.lower() in IMG_EXT and f.stat().st_mtime >= t0
                and f.stat().st_size < 9 * 1024 * 1024]
        if pics:
            return max(pics, key=lambda f: f.stat().st_mtime)
    return None


def _buttons(p: dict, step: str) -> list[list[tuple[str, str]]]:
    fl = workflow.flow(p)
    nxt = fl.next(step)
    pid = p["id"]
    rows = []
    if nxt:
        rows.append([(f"✅ Duyệt & chạy {fl.by_key[nxt].num} · {fl.by_key[nxt].name}", f"ap|{pid}|{step}")])
        rows.append([("✅ Chỉ duyệt", f"ao|{pid}|{step}"), ("🔁 Làm lại bước", f"rr|{pid}|{step}")])
    else:
        first = [("✅ Duyệt", f"ao|{pid}|{step}")]
        if step == "metadata" and p.get("yt_channel") and not p.get("yt_auto"):
            first.insert(0, ("✅ Duyệt & đăng YouTube", f"up|{pid}|{step}"))
        rows.append(first)
        rows.append([("🔁 Làm lại bước", f"rr|{pid}|{step}")])
    return rows


def notify_review(pid: int, step: str, answer: str = "", note: str = "") -> None:
    """A step of a step-by-step project is waiting for approval."""
    if not enabled():
        return
    p = store.get_project(pid)
    if not p or p.get("auto_advance"):
        return
    r = store.step_row(pid, step) or {}
    if r.get("status") != "review":
        return
    fl = workflow.flow(p)
    st = fl.by_key.get(step)
    if not st:                           # a leftover row of a step this desk does not have
        return
    try:
        problems = json.loads(r.get("problems") or "[]")
    except ValueError:
        problems = []
    lines = [_head(p), "", f"⏸ <b>Chờ duyệt: bước {st.num} · {_esc(st.name)}</b>" + (f" ({_esc(note)})" if note else "")]
    if answer:
        a = answer.strip()
        lines += ["", _esc(a[:1500] + ("…" if len(a) > 1500 else ""))]
    if problems:
        lines += ["", "\n".join("• " + _esc(x) for x in problems[:8])]
    lines += ["", f"<i>{_esc(st.gate)}</i>", "↩️ Trả lời tin này để yêu cầu Claude sửa.", f"#p{pid} · {step}"]
    pic = _preview(p, step, r.get("started_at"))
    if pic:
        _safe(send_photo, pic, f"{p.get('title') or ''} · bước {st.num} · {st.name}")
    send("\n".join(lines), _buttons(p, step))


def notify_failed(pid: int, step: str, error: str) -> None:
    if not enabled():
        return
    p = store.get_project(pid)
    if not p or p.get("auto_advance"):
        return
    st = workflow.flow(p).by_key.get(step)
    if not st:
        return
    send("\n".join([_head(p), "", f"✕ <b>Bước {st.num} · {_esc(st.name)} lỗi</b>", _esc((error or "")[:1500]), "",
                    f"#p{pid} · {step}"]), [[("🔁 Chạy lại bước", f"rn|{pid}|{step}"), ("🔁 Chạy lại kèm ghi chú", f"rr|{pid}|{step}")]])


def notify_upload(pid: int, final: dict) -> None:
    if not enabled():
        return
    p = store.get_project(pid)
    if not p:
        return
    if final.get("ok"):
        msg = f"📤 <b>Đã đăng YouTube</b>: {_esc(final.get('url') or '(chưa đọc được link)')}"
        if final.get("scheduled_for"):
            msg += f"\n🕒 lên lịch {_esc(final['scheduled_for'])}"
        for w in final.get("warnings") or []:
            msg += f"\n⚠ {_esc(w)}"
    else:
        msg = f"✕ <b>Đăng YouTube không thành công</b>\n{_esc((final.get('error') or '')[:1500])}"
    _safe(send, _head(p) + "\n\n" + msg)


# ---------------------------------------------------------------- actions from the phone
class Bot:
    def __init__(self, get_worker):
        self.get_worker = get_worker
        self.offset = 0
        self.thread: threading.Thread | None = None

    def start(self) -> None:
        if self.thread and self.thread.is_alive():
            return
        self.thread = threading.Thread(target=self._loop, name="creater-tgbot", daemon=True)
        self.thread.start()

    def _loop(self) -> None:
        last_tok = None
        while True:
            tok = token()
            if not tok or not db.setting_bool("tg_bot_on"):
                time.sleep(15)
                continue
            if tok != last_tok:
                self.offset, last_tok = 0, tok
                _safe(call, "deleteWebhook", tok=tok)
            try:
                ups = call("getUpdates", http_timeout=70, tok=tok, offset=self.offset, timeout=50,
                           allowed_updates=["message", "callback_query"])
            except Exception as e:  # noqa: BLE001
                log.warning("telegram getUpdates: %s", e)
                time.sleep(20)
                continue
            for u in ups or []:
                self.offset = max(self.offset, u["update_id"] + 1)
                try:
                    self._handle(u)
                except Exception as e:  # noqa: BLE001
                    log.exception("telegram update")
                    _safe(send, f"✕ lỗi khi xử lý: {_esc(str(e))[:500]}")

    # ---- dispatch
    def _handle(self, u: dict) -> None:
        if "callback_query" in u:
            q = u["callback_query"]
            if str(((q.get("message") or {}).get("chat") or {}).get("id")) != chat_id():
                return
            text = self._button(q.get("data") or "")
            _safe(call, "answerCallbackQuery", callback_query_id=q["id"], text=text[:190])
            if text:
                msg = q.get("message") or {}
                _safe(call, "editMessageReplyMarkup", chat_id=chat_id(), message_id=msg.get("message_id"),
                      reply_markup={"inline_keyboard": []})
                _safe(send, text, reply_to_message_id=msg.get("message_id"))
            return
        m = u.get("message") or {}
        chat = m.get("chat") or {}
        txt = (m.get("text") or "").strip()
        if txt.startswith("/start"):
            self._pair(chat, txt)
            return
        if str(chat.get("id")) != chat_id() or not txt:
            return
        if txt in ("/cho", "/pending", "/list"):
            self._pending()
            return
        tag = _TAG.search(((m.get("reply_to_message") or {}).get("text")) or "")
        if not tag:
            send("Trả lời (reply) đúng tin của bước cần sửa, hoặc gõ /cho để xem các bước đang chờ duyệt.")
            return
        pid, step, redo = int(tag.group(1)), tag.group(2), tag.group(3)
        send(self._note(pid, step, txt, redo=bool(redo)), reply_to_message_id=m.get("message_id"))

    def _pair(self, chat: dict, txt: str) -> None:
        code = txt.split(maxsplit=1)[1].strip().upper() if " " in txt else ""
        cid = str(chat.get("id"))
        if chat_id() and cid == chat_id():
            send("Bot đã ghép với chat này. Gõ /cho để xem các bước đang chờ duyệt.")
            return
        if chat_id() or code != pair_code():
            call("sendMessage", chat_id=cid, text="Gửi /start <mã ghép đôi> (mã ở trang Cài đặt của Creater Vid).")
            return
        db.set_setting("tg_bot_chat", cid)
        db.set_setting("tg_bot_chat_name", chat.get("username") or chat.get("first_name") or cid)
        send("✓ Đã ghép bot với Creater Vid. Các bước chờ duyệt (dự án chạy từng bước) sẽ gửi về đây. Gõ /cho để xem ngay.")

    def _pending(self) -> None:
        rows = db.rows("SELECT project_id, step FROM project_steps WHERE status='review' ORDER BY project_id")
        sent = 0
        for r in rows:
            p = store.get_project(r["project_id"])
            if p and not p.get("auto_advance") and not p.get("archived"):
                notify_review(p["id"], r["step"])
                sent += 1
        if not sent:
            send("Không có bước nào đang chờ duyệt.")

    # ---- the buttons
    def _button(self, data: str) -> str:
        try:
            act, pid, step = data.split("|", 2)
            pid = int(pid)
        except ValueError:
            return ""
        p = store.get_project(pid)
        if not p:
            return "dự án không còn"
        fl = workflow.flow(p)
        if step not in fl.by_key:
            return "bước không còn"
        st = fl.by_key[step]
        name = f"{st.num} · {st.name}"
        r = store.step_row(pid, step) or {}
        if act in ("ap", "ao", "up"):
            if r.get("status") == "approved":
                return f"bước {name} đã được duyệt rồi"
            if r.get("status") != "review":
                return f"bước {name} đang «{workflow.STATUS_LABELS.get(r.get('status'), r.get('status'))}», chưa duyệt được"
            try:
                res = store.approve(p, step)
            except ValueError as e:
                return f"✕ {e}"
            store.log_event(pid, "approved", f"duyệt qua Telegram bước {name}", step)
            out = f"✅ Đã duyệt bước {name}"
            if act == "ap" and res.get("next"):
                out += "\n" + self._run(pid, res["next"], "")
            if act == "up":
                from . import publish
                up = publish.start(store.get_project(pid), by="Telegram")
                out += "\n" + ("📤 đã xếp hàng đăng YouTube (chờ tải lên + kiểm tra bản quyền)" if up.get("ok")
                               else f"✕ không đăng được: {up.get('error')}")
            elif (res.get("upload") or {}).get("ok"):
                out += "\n📤 đã xếp hàng đăng YouTube"
            return out
        if act == "rn":
            return self._run(pid, step, "")
        if act == "rr":
            send(f"✏️ Trả lời tin này bằng ghi chú: Claude sẽ chạy lại bước {_esc(name)} theo ghi chú đó.\n"
                 f"#p{pid} · {step} · redo", reply_markup={"force_reply": True, "input_field_placeholder": "ghi chú cho Claude"})
            return f"chờ ghi chú để làm lại bước {name}"
        return ""

    def _run(self, pid: int, step: str, note: str) -> str:
        w = self.get_worker()
        if not w:
            return "✕ hàng đợi Claude chưa sẵn sàng"
        p = store.get_project(pid)
        name = workflow.flow(p).names()[step]
        res = w.enqueue(pid, (ORIGIN + note) if note else "", "step", step)
        return f"✕ không chạy được bước {name}: {res['error']}" if res.get("error") else f"▶ đã xếp hàng chạy bước {name}"

    def _note(self, pid: int, step: str, text: str, redo: bool) -> str:
        p = store.get_project(pid)
        if not p:
            return "dự án không còn"
        if step not in workflow.flow(p).by_key:
            return "bước không còn"
        if redo:
            return self._run(pid, step, text)
        w = self.get_worker()
        if not w:
            return "✕ hàng đợi Claude chưa sẵn sàng"
        res = w.enqueue(pid, ORIGIN + text, "chat", step)
        if res.get("error"):
            return f"✕ {res['error']}"
        return "✏️ đã gửi cho Claude sửa; xong sẽ gửi lại để bạn duyệt"


_bot: Bot | None = None


def start(get_worker) -> Bot:
    global _bot
    if _bot is None:
        _bot = Bot(get_worker)
    _bot.start()
    return _bot


def check(tok: str | None = None) -> dict:
    me = call("getMe", tok=tok)
    return {"ok": True, "bot": me.get("username"), "name": me.get("first_name")}
