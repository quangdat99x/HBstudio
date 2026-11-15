"""Talk to the existing tools (Downloader, Cutter, Zoom) and start them when they are not running."""
from __future__ import annotations

import logging
import os
import socket
import subprocess
import time
from pathlib import Path

import requests

from .. import config

log = logging.getLogger("studio.tools")

TOOLS = {
    "downloader": {"dir": config.DOWNLOADER_DIR, "port": config.PORT_DOWNLOADER, "type": "socketio", "python": config.PY_CUTTER},
    "cutter": {"dir": config.CUTTER_DIR, "port": config.PORT_CUTTER, "type": "flask", "python": config.PY_CUTTER},
    "zoom": {"dir": config.ZOOM_DIR, "port": config.PORT_ZOOM, "type": "flask", "python": config.PY_ZOOM},
    "creater": {"dir": config.CREATER_DIR, "port": config.PORT_CREATER, "type": "flask", "python": config.PY_ZOOM},
}
_procs: dict[str, subprocess.Popen] = {}


def port_open(port: int, host: str = "127.0.0.1") -> bool:
    try:
        with socket.create_connection((host, port), timeout=1):
            return True
    except OSError:
        return False


def base_url(name: str) -> str:
    return f"http://127.0.0.1:{TOOLS[name]['port']}"


def ensure_tool(name: str, timeout: int = 90) -> str:
    """Return the tool's base URL, starting its server through Tool Manager's helper if needed."""
    tool = TOOLS[name]
    if port_open(tool["port"]):
        return base_url(name)
    python = tool["python"] if Path(tool["python"]).exists() else "python"
    venv = Path(tool["dir"]) / ".venv" / "Scripts" / "python.exe"
    if venv.exists():
        python = str(venv)
    config.LOG_DIR.mkdir(exist_ok=True)
    logf = open(config.LOG_DIR / f"tool-{name}.log", "a", encoding="utf-8", errors="replace")
    logf.write(f"\n===== {time.strftime('%Y-%m-%d %H:%M:%S')} start {name} (by studio) =====\n")
    logf.flush()
    log.info("starting tool %s with %s", name, python)
    proc = subprocess.Popen(
        [str(python), str(config.TOOL_SERVER_HELPER), str(tool["dir"]), str(tool["port"]), tool["type"]],
        cwd=str(tool["dir"]), stdout=logf, stderr=subprocess.STDOUT,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    _procs[name] = proc
    deadline = time.time() + timeout
    while time.time() < deadline:
        if port_open(tool["port"]):
            return base_url(name)
        if proc.poll() is not None and not port_open(tool["port"]):
            raise RuntimeError(f"{name} server exited with code {proc.returncode}; see logs/tool-{name}.log")
        time.sleep(1)
    raise RuntimeError(f"{name} server did not open port {tool['port']} within {timeout}s")


def get_json(url: str, timeout: int = 30):
    r = requests.get(url, timeout=timeout)
    r.raise_for_status()
    return r.json()


def post_json(url: str, payload: dict | None = None, timeout: int = 60):
    r = requests.post(url, json=payload or {}, timeout=timeout)
    try:
        data = r.json()
    except ValueError:
        data = {"error": r.text[:500]}
    if r.status_code >= 400 and "error" not in data:
        data["error"] = f"HTTP {r.status_code}"
    data["_status"] = r.status_code
    return data


def free_disk_gb(path: Path) -> float:
    try:
        st = os.statvfs(str(path)) if hasattr(os, "statvfs") else None
        if st:
            return st.f_bavail * st.f_frsize / 1e9
        import shutil
        return shutil.disk_usage(str(path)).free / 1e9
    except Exception:  # noqa: BLE001
        return 0.0
