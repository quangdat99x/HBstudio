"""Telegram API (your own account, through Telethon): sign in once, then download the photos and videos of channel
posts, the big ones the public web preview will not serve included.

Run by the app with the Python of E:\\Tool\\Creater Vid\\.venv (Telethon is installed there only):
    .venv\\Scripts\\python.exe -m creater.tg status | send-code --phone +84... | sign-in --code 12345 [--password ..]
                                            | logout | download --post channel/123 --out sources/media/m01
Prints one line of JSON. api_id / api_hash come from the Settings page. The session file
(work/telegram/creater.session) gives full access to the account: it never leaves this machine.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from creater import config, db  # noqa: E402

TG_DIR = config.WORK_DIR / "telegram"
SESSION = TG_DIR / "creater"                    # Telethon adds ".session"
LOGIN = TG_DIR / "login.json"                   # phone + phone_code_hash between send-code and sign-in


def out(data: dict) -> None:
    print(json.dumps(data, ensure_ascii=False), flush=True)


def client():
    from telethon.sync import TelegramClient
    api_id = (db.get_setting("telegram_api_id") or "").strip()
    api_hash = (db.get_setting("telegram_api_hash") or "").strip()
    if not api_id.isdigit() or len(api_hash) < 20:
        raise RuntimeError("chưa có api_id / api_hash Telegram (Cài đặt → Telegram API)")
    TG_DIR.mkdir(parents=True, exist_ok=True)
    c = TelegramClient(str(SESSION), int(api_id), api_hash, device_model="Creater Vid", app_version="1.0")
    c.connect()
    return c


def _me(c) -> dict:
    me = c.get_me()
    return {"id": me.id, "username": me.username, "name": " ".join(x for x in (me.first_name, me.last_name) if x),
            "phone": ("+" + me.phone[:4] + "…" + me.phone[-2:]) if me.phone else None}


def cmd_status(args) -> dict:
    c = client()
    try:
        if not c.is_user_authorized():
            return {"ok": True, "authorized": False}
        return {"ok": True, "authorized": True, "me": _me(c)}
    finally:
        c.disconnect()


def cmd_send_code(args) -> dict:
    phone = (args.phone or "").replace(" ", "")
    if not phone.startswith("+") or not phone[1:].isdigit():
        raise RuntimeError("số điện thoại phải theo dạng quốc tế, VD +84912345678")
    c = client()
    try:
        sent = c.send_code_request(phone)
        LOGIN.write_text(json.dumps({"phone": phone, "hash": sent.phone_code_hash}), encoding="utf-8")
        return {"ok": True, "sent": True}
    finally:
        c.disconnect()


def cmd_sign_in(args) -> dict:
    from telethon.errors import SessionPasswordNeededError
    args.code = args.code or os.environ.get("TG_CODE")             # the app passes them by environment, not argv
    args.password = args.password or os.environ.get("TG_PASSWORD")
    c = client()
    try:
        if args.password and not args.code:                    # second step of an account with two-step verification
            c.sign_in(password=args.password)
        else:
            login = json.loads(LOGIN.read_text(encoding="utf-8")) if LOGIN.exists() else {}
            if not login:
                raise RuntimeError("chưa gửi mã: bấm Gửi mã trước")
            try:
                c.sign_in(login["phone"], (args.code or "").strip(), phone_code_hash=login["hash"])
            except SessionPasswordNeededError:
                if not args.password:
                    return {"ok": False, "need_password": True, "error": "tài khoản bật xác minh 2 bước: nhập mật khẩu"}
                c.sign_in(password=args.password)
        LOGIN.unlink(missing_ok=True)
        return {"ok": True, "authorized": True, "me": _me(c)}
    finally:
        c.disconnect()


def cmd_logout(args) -> dict:
    c = client()
    try:
        if c.is_user_authorized():
            c.log_out()
    finally:
        c.disconnect()
    for f in TG_DIR.glob("creater.session*"):
        f.unlink(missing_ok=True)
    LOGIN.unlink(missing_ok=True)
    return {"ok": True, "authorized": False}


def cmd_download(args) -> dict:
    channel, _, msg_id = args.post.strip().removeprefix("https://t.me/").partition("/")
    if not msg_id.split("?")[0].isdigit():
        raise RuntimeError(f"bài không hợp lệ: {args.post}")
    c = client()
    try:
        if not c.is_user_authorized():
            raise RuntimeError("chưa đăng nhập Telegram API (Cài đặt → Telegram API)")
        msg = c.get_messages(channel, ids=int(msg_id.split("?")[0]))
        if not msg or not msg.media:
            raise RuntimeError("bài không có ảnh/video (có thể đã bị xóa)")
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        path = c.download_media(msg, file=args.out)
        if not path:
            raise RuntimeError("Telegram không trả file")
        p = Path(path)
        return {"ok": True, "file": str(p), "size": p.stat().st_size}
    finally:
        c.disconnect()


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser(prog="tg")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    sub.add_parser("send-code").add_argument("--phone", required=True)
    p = sub.add_parser("sign-in")
    p.add_argument("--code")
    p.add_argument("--password")
    sub.add_parser("logout")
    p = sub.add_parser("download")
    p.add_argument("--post", required=True)
    p.add_argument("--out", required=True)
    args = ap.parse_args()
    fn = {"status": cmd_status, "send-code": cmd_send_code, "sign-in": cmd_sign_in, "logout": cmd_logout,
          "download": cmd_download}[args.cmd]
    try:
        out(fn(args))
    except Exception as e:  # noqa: BLE001  (one JSON line for the app, whatever went wrong)
        name = type(e).__name__
        msg = str(e) or name
        if name == "FloodWaitError":
            msg = f"Telegram bắt chờ {getattr(e, 'seconds', '?')} giây trước khi thử lại"
        elif name in ("PhoneCodeInvalidError", "PhoneCodeExpiredError"):
            msg = "mã đăng nhập sai hoặc đã hết hạn: gửi mã lại"
        elif name == "PasswordHashInvalidError":
            msg = "mật khẩu xác minh 2 bước không đúng"
        elif name in ("ApiIdInvalidError", "ApiIdPublishedFloodError"):
            msg = "api_id / api_hash không hợp lệ: lấy lại ở my.telegram.org"
        elif name in ("ChannelPrivateError", "UsernameNotOccupiedError", "UsernameInvalidError"):
            msg = "không đọc được kênh này (kênh riêng tư chưa tham gia, hoặc sai tên)"
        out({"ok": False, "error": msg, "type": name})
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
