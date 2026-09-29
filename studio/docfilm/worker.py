"""Queue + worker thread for documentary turns (one Claude run at a time: renders and the GPU are shared).

A turn = one assistant message answering one user message (a chat text, or a step button). Every turn of
a project resumes the project's Claude session. Before a turn the rulebook file and its history are synced
(so an edit made in an editor becomes a version); after it, a change made by Claude becomes a version
attributed to that turn.
"""
from __future__ import annotations

import json
import logging
import shutil
import sys
import threading
import time
from collections import deque
from pathlib import Path

from .. import config, db
from ..pipeline import claude_runner
from ..util import now_iso
from . import prompts, research, scaffold, store

log = logging.getLogger("studio.docfilm")

# Pre-approved tools. MCP tools of other claude.ai connectors (TikTok publishing, websites...) are
# not in the list, so a headless turn cannot call them.
HF_TOOLS = ("balance", "generate_image", "generate_image_batch", "jobs_wait", "remove_background", "models_explore",
            "create_project", "list_workspaces", "list_projects", "list_folders", "create_folder", "generate_video",
            "upscale_image",
            # narration (ElevenLabs v4): a batch of takes returns one URL, the others are found in the history
            "generate_audio", "generate_audio_batch", "list_voices", "show_generations", "transactions")
ALLOWED_TOOLS = ",".join(["Read", "Write", "Edit", "Glob", "Grep", "WebSearch", "WebFetch", "Bash", "ToolSearch", "TodoWrite"]
                         + [f"mcp__claude_ai_HF__{n}" for n in HF_TOOLS])
KINDS = ("chat", "research", "script", "build")


def _env() -> dict:
    ff = shutil.which("ffmpeg") or str(config.FFMPEG)
    fp = shutil.which("ffprobe") or str(config.FFPROBE)
    bg = Path(db.get_setting("docfilm_bgremove_python") or config.DEFAULT_SETTINGS["docfilm_bgremove_python"])
    return {"CLAUDE_CODE_DISABLE_AUTO_MEMORY": "1", "FFMPEG": ff, "FFPROBE": fp, "PYTHONUTF8": "1",
            "STUDIO_PYTHON": sys.executable,
            # local background removal (BiRefNet on the GPU) and whisper for the narration timing
            "BGREMOVE_PY": str(bg), "BGREMOVE_HF": str(bg.parents[2] / "hf") if len(bg.parents) > 2 else "",
            "WHISPER_PY": str(config.PY_CUTTER)}


class TurnProgress:
    """Readable progress line for the chat bubble: minutes, tool calls, thinking, what Claude is doing now."""

    def __init__(self, update):
        self.update = update
        self.started = time.time()
        self.tools = 0
        self.thinking = 0
        self.last = "khởi động"
        self._t = 0.0

    def _emit(self, force: bool = False) -> None:
        now = time.time()
        if not force and now - self._t < 5:
            return
        self._t = now
        think = f" · {self.thinking / 1000:.0f}k token suy nghĩ" if self.thinking >= 1000 else ""
        self.update(f"[{int((now - self.started) // 60)} phút · {self.tools} lượt công cụ{think}] {self.last}")

    def __call__(self, kind: str, data) -> None:
        if kind == "text_delta":
            return
        if kind == "thinking":
            self.thinking += int(data or 0)
            self._emit()
            return
        if kind in ("writing", "writing_tool"):
            chars = f"{int(data or 0):,}".replace(",", ".")
            self.last = ("đang ghi file" if kind == "writing_tool" else "đang viết câu trả lời") + f" (~{chars} ký tự)"
            self._emit()
            return
        if kind == "text":
            self.last = str(data).strip().replace("\n", " ")[-160:]
            self._emit(force=True)
            return
        name, inp = data
        self.tools += 1
        fp = str(inp.get("file_path") or inp.get("path") or "")
        short = fp.replace("\\", "/").split("/")[-1] if fp else ""
        if name == "Read":
            self.last = f"đọc {short}"
        elif name in ("Write", "Edit"):
            self.last = f"{'ghi' if name == 'Write' else 'sửa'} {short}"
        elif name == "Bash":
            cmd = str(inp.get("command") or "")
            if "remotion render" in cmd:
                self.last = "render phim (Remotion)"
            elif "stills.mjs" in cmd:
                self.last = "chụp ảnh tĩnh để soát"
            elif "qa.mjs" in cmd:
                self.last = "QA bản render"
            elif "hldb" in cmd:
                self.last = "tra kho highlight"
            else:
                self.last = "chạy lệnh: " + cmd.strip().splitlines()[0][:90] if cmd.strip() else "chạy lệnh"
        elif name.startswith("mcp__claude_ai_HF__"):
            self.last = "Higgsfield: " + name.split("__")[-1]
        elif name in ("WebSearch", "WebFetch"):
            self.last = "tra web: " + str(inp.get("query") or inp.get("url") or "")[:80]
        else:
            self.last = f"dùng {name}"
        self._emit(force=True)


def _set_msg(mid: int, **fields) -> None:
    with db.tx() as c:
        c.execute(f"UPDATE docfilm_messages SET {', '.join(k + '=?' for k in fields)} WHERE id=?", list(fields.values()) + [mid])


def run_turn(mid: int, stop_flag=None) -> None:
    m = db.row("SELECT * FROM docfilm_messages WHERE id=?", (mid,))
    p = store.get_project(m["project_id"])
    user = db.row("SELECT * FROM docfilm_messages WHERE id=?", (m["reply_to"],)) if m.get("reply_to") else None
    kind = m["kind"] if m["kind"] in KINDS else "chat"
    _set_msg(mid, status="running", started_at=now_iso(), progress_msg="khởi động")

    def update(msg: str) -> None:
        _set_msg(mid, progress_msg=msg[:500])

    store.sync_rules(source="file", project_id=p["id"], note="sửa file ngoài Studio")
    rules = store.current_rules()
    pool = None
    if kind == "research":
        update("tìm ứng viên trong kho highlight")
        pool = research.build_pool(p)
    if kind == "build":
        scaffold.scaffold_film(p, update)
    store.write_brief(p)

    session = p.get("session_id")
    note = ""
    if session and (p.get("rules_version") or 0) < rules["version"]:
        note = (f"📘 Bộ quy tắc đã cập nhật lên v{rules['version']} kể từ lượt trước: đọc lại toàn văn {store.rules_path()} "
                "trước khi làm (thay đổi mới ghi ở mục 12).")
    turn = prompts.turn_prompt(kind, p, (user or {}).get("content") or "", pool=pool, rules_note=note)
    work = store.project_dir(p) / "notes" / "runs"
    work.mkdir(parents=True, exist_ok=True)
    long_turn = kind == "build"
    max_turns = db.setting_int("docfilm_max_turns") if long_turn else min(150, db.setting_int("docfilm_max_turns"))

    def claude(prompt: str, resume: str | None) -> dict:
        return claude_runner.run(
            prompt, cwd=store.project_dir(p), allowed_tools=ALLOWED_TOOLS, permission_mode="acceptEdits",
            max_turns=max_turns, model=m.get("model") or None, effort=m.get("effort") or None,
            timeout=(5 if long_turn else 2) * 3600, log_path=work / f"turn_{mid}.jsonl", on_event=TurnProgress(update),
            stop_flag=stop_flag, resume=resume, extra_args=["--disable-slash-commands"], env_extra=_env(),
            add_dirs=[str(store.rules_path().parent), str(config.DOCFILM_ENGINE_DIR)])

    prompt = turn if session else prompts.context_prompt(p, rules) + "\n" + turn
    (work / f"turn_{mid}_prompt.txt").write_text(prompt, encoding="utf-8")
    res = claude(prompt, session)
    if session and "No conversation found" in (res.get("error") or ""):
        log.info("docfilm session %s of project %s is gone, starting a new one", session, p["id"])
        history = [x for x in store.messages(p["id"]) if x["id"] not in (mid, m.get("reply_to"))]
        prompt = "\n".join([prompts.context_prompt(p, rules), prompts.seed_history(history), turn])
        res = claude(prompt, None)
        session = None
    if stop_flag and stop_flag():
        raise RuntimeError("đã dừng theo yêu cầu")
    answer = (res.get("result") or "").strip() or (res.get("texts") or [""])[-1].strip()
    if not res.get("ok") and not answer:
        raise RuntimeError(res.get("error") or "Claude không trả lời")

    same = session and res.get("session_id") == session
    cost = res.get("cost_usd")
    turn_cost = (cost - (p.get("session_cost_usd") or 0)) if same and cost is not None else cost
    if turn_cost is not None and turn_cost < 0:
        turn_cost = None
    after = store.sync_rules(source="claude", project_id=p["id"], message_id=mid,
                             note=((user or {}).get("content") or kind)[:160])
    summary = claude_runner.describe_run(dict(res, cost_usd=turn_cost))
    _set_msg(mid, status="done", content=answer or "Đã xong.", log_md="\n\n".join(res.get("texts") or []),
             models_used=",".join(res.get("models") or []), usage_json=json.dumps(res.get("usage") or {}),
             cost_usd=turn_cost, duration_sec=res.get("duration_sec"), session_id=res.get("session_id"),
             rules_version=after["version"] if after["changed"] else None, finished_at=now_iso(),
             progress_msg=summary, error=None if res.get("ok") else f"cảnh báo: {res.get('error')}")
    fresh = store.get_project(p["id"])
    store.update_project(p["id"], session_id=res.get("session_id") or session, session_cost_usd=cost,
                         rules_version=after["version"], cost_usd=(fresh.get("cost_usd") or 0) + (turn_cost or 0),
                         stage=store.artifacts(fresh, light=True)["stage"])


class DocFilmWorker:
    def __init__(self):
        self.queue: deque[int] = deque()
        self.cv = threading.Condition()
        self.current: int | None = None
        self.cancelled: set[int] = set()
        self.thread = threading.Thread(target=self._loop, name="studio-docfilm", daemon=True)

    def start(self) -> None:
        with db.tx() as c:
            c.execute("UPDATE docfilm_messages SET status='failed', error='Studio khởi động lại giữa chừng', finished_at=? "
                      "WHERE role='assistant' AND status='running'", (now_iso(),))
        for r in db.rows("SELECT id FROM docfilm_messages WHERE role='assistant' AND status='queued' ORDER BY id"):
            self.queue.append(r["id"])
        try:
            store.sync_rules()
        except Exception:  # noqa: BLE001
            log.exception("rulebook sync failed")
        self.thread.start()
        log.info("docfilm worker started (%d queued)", len(self.queue))

    def enqueue(self, pid: int, text: str, kind: str = "chat") -> dict:
        p = store.get_project(pid)
        if not p:
            return {"error": "không có dự án này"}
        kind = kind if kind in KINDS else "chat"
        busy = store.busy_turn(pid)
        if busy:
            return {"error": "Claude đang " + ("làm" if busy["status"] == "running" else "chờ tới lượt") +
                             " cho dự án này, đợi xong rồi nhắn tiếp (hoặc bấm Dừng)"}
        text = (text or "").strip() or prompts.STEP_LABELS.get(kind, "")
        if not text:
            return {"error": "chưa nhập nội dung"}
        uid = store.add_user_message(pid, text[:8000], kind)
        mid = store.add_assistant_turn(pid, uid, kind)
        store.update_project(pid)
        with self.cv:
            self.queue.append(mid)
            self.cv.notify()
        ahead = len(self.queue) - 1 + (1 if self.current else 0)
        return {"message_id": mid, "message": "đã gửi cho Claude" + (f", còn {ahead} lượt của dự án khác trước" if ahead else "")}

    def cancel(self, pid: int) -> dict:
        m = store.busy_turn(pid)
        if not m:
            return {"message": "không có lượt nào đang chạy"}
        if m["status"] == "queued":
            with self.cv:
                if m["id"] in self.queue:
                    self.queue.remove(m["id"])
            _set_msg(m["id"], status="failed", error="đã hủy", finished_at=now_iso())
            return {"message": "đã bỏ khỏi hàng đợi"}
        self.cancelled.add(m["id"])
        return {"message": "đang dừng lượt đang chạy"}

    def status(self) -> dict:
        return {"current": self.current, "queue": list(self.queue)}

    def _loop(self) -> None:
        while True:
            with self.cv:
                while not self.queue:
                    self.cv.wait(timeout=30)
                mid = self.queue.popleft()
            self.current = mid
            try:
                run_turn(mid, stop_flag=lambda i=mid: i in self.cancelled)
            except Exception as e:  # noqa: BLE001
                log.exception("docfilm turn %s failed", mid)
                _set_msg(mid, status="failed", error=("đã dừng" if mid in self.cancelled else str(e))[:1500],
                         finished_at=now_iso())
            finally:
                self.current = None
                self.cancelled.discard(mid)
