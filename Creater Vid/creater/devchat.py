"""Dev chat on the Pipeline page: talk to Claude Code about one node and let it change the app's own code.

Each node keeps its own conversation (one Claude Code session, resumed on every message, so the context stays warm)
in <store_dir>/<node>.json. A message runs `claude -p` headless in the app folder with edit rights; the page polls
the live text and the tools Claude is using. Python and template changes need the app restarted: `restart()`
relaunches the server process with the same command line once nothing is running.

The same file lives in Hổ Báo Studio (studio/devchat.py) and Creater Vid (creater/devchat.py); keep them identical.
Everything app-specific (the Claude runner, markdown renderer, node context, what counts as busy) is passed in.
"""
from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

log = logging.getLogger("devchat")

EDIT_TOOLS = ("Edit", "Write", "MultiEdit", "NotebookEdit")
ALLOWED_TOOLS = "Read,Write,Edit,MultiEdit,Glob,Grep,Bash,WebSearch,WebFetch,TodoWrite"


def _now() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def _safe(node: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "__", node)[:80] or "node"


LOCAL_HOSTS = ("127.0.0.1", "localhost", "::1", "[::1]")


def guard(req) -> str | None:
    """These endpoints run Claude with edit and shell rights: only this machine's own pages may call them.

    Host must be local (stops DNS rebinding), a cross-site Origin is refused, and the custom header forces a CORS
    preflight that no other website can pass (stops a page elsewhere from posting to localhost).
    """
    from urllib.parse import urlparse
    if (req.host or "").rsplit(":", 1)[0].lower() not in LOCAL_HOSTS:
        return "chỉ gọi được từ chính máy này"
    origin = req.headers.get("Origin")
    if origin and (urlparse(origin).hostname or "").lower() not in ("127.0.0.1", "localhost", "::1"):
        return "nguồn gọi không hợp lệ"
    if req.headers.get("X-Devchat") != "1":
        return "thiếu header X-Devchat"
    return None


def _short(name: str, inp: dict) -> str:
    """One line for the activity feed: what the tool is touching."""
    for k in ("file_path", "path", "pattern", "command", "url", "query"):
        v = inp.get(k)
        if v:
            v = str(v).replace("\n", " ")
            return f"{name} · {v[:110]}"
    return name


class DevChat:
    def __init__(self, *, app_name: str, base_dir: Path, store_dir: Path, port: int, run_fn, md_fn,
                 context_fn, busy_fn=None, test_hint: str = ""):
        self.app_name, self.base_dir, self.port = app_name, Path(base_dir), port
        self.store_dir = Path(store_dir)
        self.run_fn, self.md_fn, self.context_fn, self.busy_fn = run_fn, md_fn, context_fn, busy_fn
        self.test_hint = test_hint
        self.lock = threading.Lock()
        self.live: dict[str, dict] = {}          # node -> {"text", "activity", "files", "started"}
        self.stop_req: set[str] = set()

    # ------------------------------------------------------------ storage
    def _path(self, node: str) -> Path:
        return self.store_dir / f"{_safe(node)}.json"

    def _load(self, node: str) -> dict:
        try:
            return json.loads(self._path(node).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {"node": node, "session_id": None, "messages": []}

    def _save(self, node: str, data: dict) -> None:
        self.store_dir.mkdir(parents=True, exist_ok=True)
        tmp = self._path(node).with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(self._path(node))

    # ------------------------------------------------------------ public
    def busy(self, node: str | None = None) -> bool:
        with self.lock:
            return bool(self.live) if node is None else node in self.live

    def state(self, node: str) -> dict:
        data = self._load(node)
        msgs = []
        for m in data.get("messages", []):
            m = dict(m)
            if m.get("role") == "assistant":
                m["html"] = self.md_fn(m.get("text") or "")
            msgs.append(m)
        with self.lock:
            live = dict(self.live[node]) if node in self.live else None
        if live:
            live["html"] = self.md_fn(live.get("text") or "")
            live["elapsed"] = round(time.time() - live["started"])
        return {"node": node, "messages": msgs, "busy": live is not None, "live": live,
                "session": bool(data.get("session_id")), "others_busy": [n for n in self.live if n != node]}

    def send(self, node: str, text: str, model: str = "", effort: str = "") -> dict:
        text = (text or "").strip()
        if not text:
            return {"error": "chưa có nội dung"}
        ctx = self.context_fn(node)
        if not ctx:
            return {"error": "không có node này"}
        with self.lock:
            if node in self.live:
                return {"error": "Claude đang trả lời node này, chờ xong hoặc bấm Dừng"}
            if self.live:
                return {"error": f"Claude đang sửa code ở node khác ({', '.join(self.live)}): "
                                 "mỗi lúc chỉ một cuộc chat được sửa code để hai bên không ghi đè nhau"}
            self.live[node] = {"text": "", "activity": [], "files": [], "started": time.time()}
        data = self._load(node)
        data["messages"].append({"role": "user", "text": text[:20000], "at": _now(), "model": model, "effort": effort})
        self._save(node, data)
        threading.Thread(target=self._run, args=(node, text, ctx, model, effort), daemon=True,
                         name=f"devchat-{node}").start()
        return {"ok": True}

    def stop(self, node: str) -> dict:
        if not self.busy(node):
            return {"message": "không có lượt nào đang chạy"}
        self.stop_req.add(node)
        return {"message": "đang dừng"}

    def reset(self, node: str) -> dict:
        if self.busy(node):
            return {"error": "đang chạy, dừng trước đã"}
        p = self._path(node)
        if p.exists():
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            p.replace(p.with_name(f"{p.stem}.{stamp}.done.json"))   # old conversation kept, not shown
        return {"ok": True}

    # ------------------------------------------------------------ run
    def _prompt(self, node: str, text: str, ctx: dict, first: bool) -> str:
        if not first:
            return f"[Node đang chọn: {ctx['label']}]\n\n{text}"
        files = "\n".join(f"- {f}" for f in ctx.get("files", [])) or "- (tự tìm trong mã nguồn)"
        settings = ", ".join(ctx.get("settings", [])) or "(không có)"
        return f"""Bạn là kỹ sư phụ trách mã nguồn của app **{self.app_name}** tại `{self.base_dir}` (Flask, cổng {self.port}).
Người dùng đang mở trang Pipeline (sơ đồ node của workflow) và chat với bạn từ node **{ctx['label']}**
để chỉnh sửa bước này hoặc làm thêm tính năng. Bạn được sửa code trực tiếp.

## Node này
{ctx.get('desc', '')}

File liên quan (đọc trước khi sửa, đường dẫn tính từ thư mục app):
{files}

Cài đặt của node (bảng settings, sửa trên trang Pipeline/Cài đặt): {settings}
{ctx.get('extra', '')}

## Sơ đồ Pipeline
{ctx.get('graph_files', '')}: muốn thêm/bớt node, đổi nối, thêm cài đặt cho node thì sửa ở đó.

## Quy tắc khi làm
- Đọc code liên quan trước, giữ đúng phong cách sẵn có, chữ trên giao diện bằng tiếng Việt.
- Thay đổi gọn, đúng chỗ. Đổi schema DB thì viết migration, không xoá hay ghi đè dữ liệu có sẵn.
- **Bạn đang chạy bên trong chính app này.** KHÔNG khởi động lại, tắt hay kill tiến trình app ở cổng {self.port},
  không kill python.exe. Cần chạy thử thì: {self.test_hint or 'dùng script python ngắn hoặc một bản app ở cổng khác'}, và tắt nó khi xong.
- File thử nghiệm để trong `_claude_tmp/` của app rồi xoá hết khi xong, kể cả `__pycache__` do bạn sinh ra.
- Yêu cầu mơ hồ hoặc rủi ro (xoá dữ liệu, tốn tiền API, đổi luồng lớn) thì hỏi lại trước, chưa sửa.
- Thay đổi Python hoặc template chỉ có hiệu lực sau khi app khởi động lại (người dùng bấm nút trên trang);
  JS/CSS trong static/ chỉ cần tải lại trang.

## Trả lời
Bằng tiếng Việt, ngắn gọn: đã làm gì, file nào, cách thử. Dòng cuối ghi đúng một trong hai:
`KHỞI ĐỘNG LẠI: CẦN` hoặc `KHỞI ĐỘNG LẠI: KHÔNG`.

## Yêu cầu của người dùng
{text}"""

    def _run(self, node: str, text: str, ctx: dict, model: str, effort: str) -> None:
        data = self._load(node)
        session = data.get("session_id")

        def on_event(kind, payload):
            with self.lock:
                lv = self.live.get(node)
                if not lv:
                    return
                if kind == "text_delta":
                    lv["text"] += payload
                elif kind == "text":
                    lv["text"] += "\n\n"
                elif kind == "tool":
                    name, inp = payload
                    lv["activity"] = (lv["activity"] + [_short(name, inp or {})])[-40:]
                    fp = (inp or {}).get("file_path")
                    if name in EDIT_TOOLS and fp and fp not in lv["files"]:
                        lv["files"].append(fp)

        def go(resume):
            return self.run_fn(self._prompt(node, text, ctx, first=not resume), cwd=self.base_dir,
                               allowed_tools=ALLOWED_TOOLS, permission_mode="acceptEdits", max_turns=200,
                               model=model or None, effort=effort or None, timeout=2 * 3600, resume=resume,
                               on_event=on_event, stop_flag=lambda: node in self.stop_req,
                               log_path=self.store_dir / f"{_safe(node)}.last.log",
                               env_extra={"ENABLE_CLAUDEAI_MCP_SERVERS": "false"})

        self.store_dir.mkdir(parents=True, exist_ok=True)
        try:
            res = go(session)
            if session and not res.get("ok") and node not in self.stop_req and \
                    "session" in str(res.get("error") or res.get("result") or "").lower():
                res = go(None)                       # the old session is gone: start a fresh one with full context
        except Exception as e:  # noqa: BLE001
            log.exception("devchat run failed")
            res = {"ok": False, "error": str(e)}
        with self.lock:
            lv = self.live.get(node) or {}
        answer = (res.get("result") or "").strip() or "\n\n".join(res.get("texts") or []).strip()
        if not res.get("ok"):
            answer = (answer + "\n\n" if answer else "") + f"**Lỗi:** {res.get('error') or 'không rõ'}"
        restart = bool(re.search(r"KHỞI ĐỘNG LẠI:\s*CẦN", answer))
        files = lv.get("files", [])
        if files and not re.search(r"KHỞI ĐỘNG LẠI:", answer):
            restart = any("/static/" not in f.replace("\\", "/") for f in files)   # static JS/CSS: reload is enough
        data = self._load(node)
        if res.get("session_id"):
            data["session_id"] = res["session_id"]
        data["messages"].append({
            "role": "assistant", "text": answer or "(không có trả lời)", "at": _now(), "ok": bool(res.get("ok")),
            "files": [os.path.relpath(f, self.base_dir) if str(f).lower().startswith(str(self.base_dir).lower()) else f
                      for f in files],
            "restart": restart, "cost_usd": res.get("cost_usd"), "duration_sec": res.get("duration_sec"),
            "models": res.get("models"), "activity": lv.get("activity", [])[-15:]})
        self._save(node, data)
        with self.lock:
            self.live.pop(node, None)
        self.stop_req.discard(node)

    # ------------------------------------------------------------ restart
    def restart(self) -> dict:
        """Relaunch this server with the same command line so code changes take effect."""
        if self.busy():
            return {"error": "Claude còn đang sửa code, chờ xong rồi khởi động lại"}
        why = self.busy_fn() if self.busy_fn else None
        if why:
            return {"error": f"App đang chạy việc: {why}. Chờ xong hoặc dừng việc đó trước"}
        cmd = [sys.executable] + list(getattr(sys, "orig_argv", sys.argv)[1:])
        logs = self.base_dir / "logs"
        logs.mkdir(exist_ok=True)
        # A detached helper waits for this process to exit (the port to free up), then starts the server again.
        helper = (
            "import socket,subprocess,sys,time,json\n"
            "cmd,cwd,port,logp=json.loads(sys.argv[1])\n"
            "for _ in range(150):\n"
            "  s=socket.socket();s.settimeout(0.3)\n"
            "  busy=s.connect_ex(('127.0.0.1',port))==0;s.close()\n"
            "  if not busy: break\n"
            "  time.sleep(0.2)\n"
            "f=open(logp,'a',encoding='utf-8')\n"
            "subprocess.Popen(cmd,cwd=cwd,stdout=f,stderr=subprocess.STDOUT,"
            "creationflags=0x08000000|0x00000200)\n")
        args = json.dumps([cmd, os.getcwd(), self.port, str(logs / "restart.log")])
        flags = 0x00000008 | 0x00000200 | 0x08000000          # DETACHED_PROCESS | NEW_PROCESS_GROUP | NO_WINDOW
        subprocess.Popen([sys.executable, "-c", helper, args], cwd=os.getcwd(), creationflags=flags, close_fds=True)
        threading.Timer(0.8, lambda: os._exit(0)).start()
        log.warning("restart requested from the Pipeline page: %s", cmd)
        return {"ok": True, "message": "Đang khởi động lại, trang sẽ tự tải lại"}
