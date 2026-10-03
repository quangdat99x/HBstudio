"""Checks of everything a film needs on this machine (Settings page), and the background setup jobs
(engine install, Chrome Headless Shell) started from there."""
from __future__ import annotations

import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

from . import claude_runner, config, db, prompts, scaffold, store
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
        out.append(_item("bgremove", "Tách nền trên máy (BiRefNet, 0 credit)", "ok" if model else "warn",
                         f"{bg}" + ("" if model else " · chưa thấy model BiRefNet trong thư mục hf (lần đầu sẽ tự tải)")))
    else:
        out.append(_item("bgremove", "Tách nền trên máy (BiRefNet, 0 credit)", "error", f"không thấy {bg}",
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
    # Higgsfield (last probe)
    bal = db.get_setting("hf_balance")
    when = db.get_setting("hf_checked_at")
    if bal:
        out.append(_item("higgsfield", "Higgsfield (ảnh, giọng đọc)", "ok",
                         f"{bal} credit · gói {db.get_setting('hf_plan') or '?'} · kiểm tra lúc {when}", action="hf_probe", group="services"))
    else:
        out.append(_item("higgsfield", "Higgsfield (ảnh, giọng đọc)", "info",
                         "chưa kiểm tra: bấm Kiểm tra (Claude gọi tool balance qua connector claude.ai)", action="hf_probe", group="services"))
    # optional JRE source
    hl, jpy = Path(db.get_setting("jre_hldb")), Path(db.get_setting("jre_python"))
    out.append(_item("jre", "Kho highlight JRE (nguồn tùy chọn)", "ok" if hl.exists() and jpy.exists() else "info",
                     f"{hl}" if hl.exists() and jpy.exists() else "không có (chỉ cần khi dự án bật nguồn JRE)", group="services"))
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


# ---------------------------------------------------------------- probes (each runs one small Claude turn)
def hf_probe() -> dict:
    """Ask Claude to call the Higgsfield balance tool through the claude.ai connector (the app has no API key of its own)."""
    config.WORK_DIR.mkdir(exist_ok=True)
    started = time.time()
    res = claude_runner.run(prompts.hf_probe_prompt(), cwd=config.WORK_DIR, permission_mode="dontAsk", max_turns=6, timeout=300,
                            allowed_tools="ToolSearch,mcp__claude_ai_HF__balance", model="haiku", effort="",
                            fallback_model="", extra_args=["--disable-slash-commands"],
                            env_extra={"CLAUDE_CODE_DISABLE_AUTO_MEMORY": "1"},
                            log_path=config.WORK_DIR / f"hf_probe_{int(started)}.jsonl")
    data = prompts.parse_json_line(res.get("result") or res.get("text") or "")
    if "credits" in data:
        db.set_setting("hf_balance", data.get("credits"))
        db.set_setting("hf_plan", data.get("plan") or "")
        db.set_setting("hf_checked_at", now_iso())
        return {"ok": True, "credits": data.get("credits"), "plan": data.get("plan"), "summary": claude_runner.describe_run(res)}
    return {"ok": False, "error": data.get("error") or res.get("error") or (res.get("result") or "không đọc được số dư")[:300],
            "summary": claude_runner.describe_run(res)}
