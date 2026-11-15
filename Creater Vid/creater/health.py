"""Checks of everything a film needs on this machine (Settings page), and the background setup jobs
(engine install, Chrome Headless Shell) started from there."""
from __future__ import annotations

import shutil
import subprocess
import sys
import threading
from pathlib import Path

from . import claude_runner, config, db, providers, scaffold, store
from .util import now_iso

_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def _run(cmd: list[str], timeout: int = 30) -> tuple[bool, str]:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout,
                           creationflags=_NO_WINDOW)
        return r.returncode == 0, (r.stdout or r.stderr or "").strip()
    except Exception as e:  # noqa: BLE001
        return False, str(e)


def _item(key, name, state, detail, action=None, hint=None, group="core"):
    """state: ok | warn | error | info"""
    return {"key": key, "name": name, "state": state, "detail": detail, "action": action, "hint": hint, "group": group}


def _ffmpeg() -> str:
    return db.get_setting("ffmpeg") or shutil.which("ffmpeg") or str(config.FFMPEG_FALLBACK)


def checks() -> list[dict]:
    out = []
    # app
    out.append(_item("python", "Python của app", "ok", f"{sys.version.split()[0]} · {sys.executable}"))
    # Claude
    st = claude_runner.cli_status()
    if not st.get("installed"):
        out.append(_item("claude", "Claude Code CLI", "error", "chưa cài", hint="npm i -g --prefix E:\\Tool\\claude-cli @anthropic-ai/claude-code"))
    else:
        login = "đã đăng nhập" if st.get("logged_in") else ("có token" if st.get("token") else "CHƯA đăng nhập")
        out.append(_item("claude", "Claude Code CLI", "ok" if (st.get("logged_in") or st.get("token")) else "error",
                         f"{st.get('version')} · {login}", action="probe",
                         hint=None if (st.get("logged_in") or st.get("token")) else "Nhấn đúp dang-nhap-claude.bat, gõ /login"))
    # Node + engine
    ok_node, node_v = _run(["node", "--version"])
    out.append(_item("node", "Node.js", "ok" if ok_node else "error", node_v if ok_node else "không tìm thấy node",
                     hint=None if ok_node else "Cài Node.js LTS"))
    if scaffold.engine_ready():
        out.append(_item("engine", "Engine dựng phim (Remotion + three.js)", "ok", str(config.ENGINE_DIR / "node_modules")))
    else:
        out.append(_item("engine", "Engine dựng phim (Remotion + three.js)", "error", "chưa cài node_modules", action="install_engine"))
    out.append(_item("chrome", "Chrome Headless Shell (render)", "ok" if scaffold.chrome_ready() else "error",
                     "đã có" if scaffold.chrome_ready() else "chưa tải", action=None if scaffold.chrome_ready() else "ensure_browser"))
    # ffmpeg
    ff = _ffmpeg()
    ok_ff, ff_v = _run([ff, "-hide_banner", "-version"])
    out.append(_item("ffmpeg", "ffmpeg", "ok" if ok_ff else "error", (ff_v.splitlines() or [""])[0][:90] + f" · {ff}" if ok_ff else f"không chạy được: {ff}"))
    # local background removal
    bg = Path(db.get_setting("bgremove_python"))
    if bg.exists():
        hf = bg.parents[2] / "hf" if len(bg.parents) > 2 else None
        model = hf and any(hf.glob("**/models--ZhengPeng7--BiRefNet"))
        out.append(_item("bgremove", "Tách nền trên máy (BiRefNet, miễn phí)", "ok" if model else "warn",
                         f"{bg}" + ("" if model else " · chưa thấy model BiRefNet trong thư mục hf (lần đầu sẽ tự tải)")))
    else:
        out.append(_item("bgremove", "Tách nền trên máy (BiRefNet, miễn phí)", "error", f"không thấy {bg}",
                         hint="venv có torch + transformers + pymatting (xem E:\\Tool\\bgremove)"))
    # whisper
    wp = Path(db.get_setting("whisper_python"))
    if wp.exists():
        ok_w, msg = _run([str(wp), "-c", "import faster_whisper; print(faster_whisper.__version__)"], timeout=60)
        out.append(_item("whisper", "Whisper (canh lời dẫn, kiểm tra giọng)", "ok" if ok_w else "warn",
                         f"faster-whisper {msg} · {wp}" if ok_w else f"{wp} chưa có faster-whisper"))
    else:
        out.append(_item("whisper", "Whisper (canh lời dẫn, kiểm tra giọng)", "warn", f"không thấy {wp}"))
    # projects folder and disk space
    root = store.root()
    try:
        root.mkdir(parents=True, exist_ok=True)
        free = shutil.disk_usage(root).free / 1e9
        state = "ok" if free > 50 else ("warn" if free > 15 else "error")
        out.append(_item("root", "Thư mục dự án", state, f"{root} · còn trống {free:.0f} GB"))
    except OSError as e:
        out.append(_item("root", "Thư mục dự án", "error", f"{root}: {e}"))
    try:
        free_app = shutil.disk_usage(config.BASE_DIR).free / 1e9
        out.append(_item("disk_app", "Ổ chứa app và engine", "ok" if free_app > 15 else "warn", f"{config.BASE_DIR} · còn trống {free_app:.0f} GB"))
    except OSError:
        pass
    # generation APIs (keys on this page, last result of the Check buttons)
    out += provider_items()
    # optional JRE source
    hl, jpy = Path(db.get_setting("jre_hldb")), Path(db.get_setting("jre_python"))
    out.append(_item("jre", "Kho highlight JRE (nguồn tùy chọn)", "ok" if hl.exists() and jpy.exists() else "info",
                     f"{hl}" if hl.exists() and jpy.exists() else "không có (chỉ cần khi dự án bật nguồn JRE)", group="services"))
    return out


def provider_items() -> list[dict]:
    st = providers.status()
    out = []
    el = st.get("elevenlabs") or {}
    if not providers.has_key("elevenlabs_api_key"):
        out.append(_item("elevenlabs", "ElevenLabs (giọng đọc, hiệu ứng âm thanh)", "warn", "chưa có API key",
                         hint="Điền key ở mục API tạo nguyên liệu bên dưới", group="services"))
    elif el.get("ok"):
        out.append(_item("elevenlabs", "ElevenLabs (giọng đọc, hiệu ứng âm thanh)", "ok",
                         f"gói {el.get('tier')} · còn {el.get('left', 0):,} / {el.get('limit', 0):,} ký tự"
                         + (f" · làm mới {el['reset']}" if el.get("reset") else "") + f" · kiểm tra lúc {el.get('at')}",
                         action="check_elevenlabs", group="services"))
    else:
        out.append(_item("elevenlabs", "ElevenLabs (giọng đọc, hiệu ứng âm thanh)", "error" if el else "info",
                         el.get("error") or "đã có key, chưa kiểm tra", action="check_elevenlabs", group="services"))
    fal = st.get("fal") or {}
    if not providers.has_key("fal_api_key"):
        out.append(_item("fal", "fal.ai (ảnh, video)", "warn", "chưa có API key",
                         hint="Điền key ở mục API tạo nguyên liệu bên dưới", group="services"))
    elif fal.get("ok"):
        bal = f"số dư ${fal['balance']}" if fal.get("balance") is not None else (fal.get("balance_note") or "")
        out.append(_item("fal", "fal.ai (ảnh, video)", "ok", f"key hợp lệ · {bal} · kiểm tra lúc {fal.get('at')}",
                         action="check_fal", group="services"))
    else:
        out.append(_item("fal", "fal.ai (ảnh, video)", "error" if fal else "info",
                         fal.get("error") or "đã có key, chưa kiểm tra", action="check_fal", group="services"))
    for name, label in (("openai", "OpenAI (ảnh GPT trực tiếp, tùy chọn)"), ("google", "Google Gemini (ảnh Nano Banana trực tiếp, tùy chọn)")):
        r = st.get(name) or {}
        if not providers.has_key(f"{name}_api_key"):
            out.append(_item(name, label, "info", "chưa có API key (không bắt buộc: chỉ cần khi chọn model openai:/google:)",
                             group="services"))
        elif r.get("ok"):
            out.append(_item(name, label, "ok" if r.get("models") else "warn",
                             (f"key hợp lệ · model ảnh: {', '.join(r['models'])[:160]}" if r.get("models") else r.get("note") or "")
                             + f" · kiểm tra lúc {r.get('at')}", action=f"check_{name}", group="services"))
        else:
            out.append(_item(name, label, "error" if r else "info", r.get("error") or "đã có key, chưa kiểm tra",
                             action=f"check_{name}", group="services"))
    tg = st.get("telegram") or {}
    label = "Telegram API (tải video lớn từ kênh, tùy chọn)"
    if not db.get_setting("telegram_api_id"):
        out.append(_item("telegram", label, "info", "chưa cấu hình (ảnh và video nhỏ vẫn lấy qua trang web công khai của kênh)",
                         group="services"))
    elif tg.get("authorized"):
        me = tg.get("me") or {}
        out.append(_item("telegram", label, "ok", f"đã đăng nhập: {me.get('name') or ''}"
                         + (f" (@{me['username']})" if me.get("username") else "") + f" · kiểm tra lúc {tg.get('at')}",
                         group="services"))
    else:
        out.append(_item("telegram", label, "warn", tg.get("error") or "chưa đăng nhập: bấm Gửi mã đăng nhập ở mục Telegram API",
                         group="services"))
    return out


def summary(items: list[dict]) -> dict:
    errors = [i for i in items if i["state"] == "error"]
    warns = [i for i in items if i["state"] == "warn"]
    return {"errors": len(errors), "warns": len(warns), "ok": not errors}


# ---------------------------------------------------------------- background setup jobs
_jobs: dict[str, dict] = {}
_lock = threading.Lock()


def start_job(name: str) -> dict:
    fns = {"install_engine": scaffold.install_engine, "ensure_browser": scaffold.ensure_browser}
    if name not in fns:
        return {"error": "không có việc này"}
    with _lock:
        cur = _jobs.get(name)
        if cur and cur.get("running"):
            return {"message": "đang chạy"}
        _jobs[name] = {"running": True, "started": now_iso(), "progress": "bắt đầu", "error": None}

    def run():
        def update(msg):
            _jobs[name]["progress"] = msg
        try:
            fns[name](update)
            _jobs[name].update(running=False, progress="xong", finished=now_iso())
        except Exception as e:  # noqa: BLE001
            _jobs[name].update(running=False, error=str(e)[:800], finished=now_iso())

    threading.Thread(target=run, name=f"setup-{name}", daemon=True).start()
    return {"message": "đã bắt đầu"}


def jobs() -> dict:
    return {k: dict(v) for k, v in _jobs.items()}
