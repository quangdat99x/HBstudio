"""Queue + worker thread for the Claude turns (one run at a time across all projects: renders and the GPU are shared).

A turn = one assistant message answering one user message: a chat text, or a step button. Every turn of a project
resumes the project's Claude session. Before a turn the rulebook file and its history are synced (an edit made in an
editor becomes a version); after it, a change made by Claude becomes a version attributed to that turn. After a step
turn the step's output files are checked and the step goes to "chờ duyệt" (or "lỗi" when files are missing).
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

from . import claude_runner, config, db, prompts, scaffold, store, workflow
from .util import now_iso

log = logging.getLogger("creater.worker")

# Pre-approved Higgsfield tools (claude.ai connector "HF"). Tools of other connectors (TikTok publishing, websites...)
# are not in the list, so a headless turn cannot call them.
HF_TOOLS = ("balance", "generate_image", "generate_image_batch", "jobs_wait", "remove_background", "models_explore",
            "create_project", "list_workspaces", "list_projects", "list_folders", "create_folder", "generate_video",
            "upscale_image", "outpaint_image", "show_generations", "show_generation_by_ids", "media_upload", "media_confirm",
            "media_import_url", "generate_audio", "generate_audio_batch", "list_voices", "transactions")
ALLOWED_TOOLS = ",".join(["Read", "Write", "Edit", "Glob", "Grep", "WebSearch", "WebFetch", "Bash", "ToolSearch", "TodoWrite"]
                         + [f"mcp__claude_ai_HF__{n}" for n in HF_TOOLS])
FILM_STEPS = ("images", "footage", "render")        # steps that work inside film/
LONG_STEPS = ("images", "footage", "render")


def tool_env() -> dict:
    ff = db.get_setting("ffmpeg") or shutil.which("ffmpeg") or str(config.FFMPEG_FALLBACK)
    fp = str(Path(ff).with_name("ffprobe.exe")) if ff.lower().endswith("ffmpeg.exe") else (shutil.which("ffprobe") or str(config.FFPROBE_FALLBACK))
    bg = Path(db.get_setting("bgremove_python") or config.DEFAULT_SETTINGS["bgremove_python"])
    return {"CLAUDE_CODE_DISABLE_AUTO_MEMORY": "1", "FFMPEG": ff, "FFPROBE": fp, "PYTHONUTF8": "1",
            "CREATER_PYTHON": sys.executable,
            # local background removal (BiRefNet on the GPU) and whisper for the narration timing
            "BGREMOVE_PY": str(bg), "BGREMOVE_HF": str(bg.parents[2] / "hf") if len(bg.parents) > 2 else "",
            "WHISPER_PY": db.get_setting("whisper_python")}


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
            elif "cutout.py" in cmd:
                self.last = "tách nền trên máy"
            elif "hldb" in cmd:
                self.last = "tra kho highlight JRE"
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
        c.execute(f"UPDATE messages SET {', '.join(k + '=?' for k in fields)} WHERE id=?", list(fields.values()) + [mid])


def _settle_step(p: dict, step: str, error: str | None = None) -> str:
    """Status of a step after a turn ended without a clean result: keep "chờ duyệt" when the files are usable."""
    problems, _ = workflow.check(step, store.project_dir(p), p)
    has_output = any((store.project_dir(p) / rel).exists() for rel in workflow.BY_KEY[step].outputs)
    status = "review" if has_output and not workflow.blocking(problems) else ("failed" if error else "ready")
    store.set_step(p["id"], step, status=status, error=(error or "")[:1500] or None, finished_at=now_iso(),
                   problems=json.dumps(problems, ensure_ascii=False))
    return status


def run_turn(mid: int, stop_flag=None, on_auto_next=None) -> None:
    m = db.row("SELECT * FROM messages WHERE id=?", (mid,))
    p = store.get_project(m["project_id"])
    user = db.row("SELECT * FROM messages WHERE id=?", (m["reply_to"],)) if m.get("reply_to") else None
    kind = m["kind"] if m["kind"] in ("chat", "step") else "chat"
    step = m.get("step") if m.get("step") in workflow.BY_KEY else None
    _set_msg(mid, status="running", started_at=now_iso(), progress_msg="khởi động")
    if kind == "step":
        r = store.step_row(p["id"], step) or {}
        store.set_step(p["id"], step, status="running", started_at=now_iso(), message_id=mid, runs=(r.get("runs") or 0) + 1,
                       error=None)
        store.log_event(p["id"], "run", f"chạy bước {workflow.BY_KEY[step].num} · {workflow.BY_KEY[step].name}", step)

    def update(msg: str) -> None:
        _set_msg(mid, progress_msg=msg[:500])

    store.sync_rules(source="file", project_id=p["id"], note="sửa file ngoài app")
    rules = store.current_rules()
    if step in FILM_STEPS or (kind == "chat" and scaffold.film_ready(store.project_dir(p))):
        scaffold.scaffold_film(p, update)
    store.write_brief(p)

    session = p.get("session_id")
    note = ""
    if session and (p.get("rules_version") or 0) < rules["version"]:
        note = (f"📘 Bộ quy tắc đã cập nhật lên v{rules['version']} kể từ lượt trước: đọc lại toàn văn \"{store.rules_path()}\" "
                "trước khi làm (thay đổi mới ghi ở mục 12).")
    turn = prompts.turn_prompt(kind, step, p, (user or {}).get("content") or "", rules_note=note)
    work = store.project_dir(p) / "notes" / "runs"
    work.mkdir(parents=True, exist_ok=True)
    long_turn = step in LONG_STEPS
    max_turns = db.setting_int("claude_max_turns") if long_turn else min(150, db.setting_int("claude_max_turns"))

    def claude(prompt: str, resume: str | None) -> dict:
        return claude_runner.run(
            prompt, cwd=store.project_dir(p), allowed_tools=ALLOWED_TOOLS, permission_mode="acceptEdits",
            max_turns=max_turns, model=m.get("model") or None, effort=m.get("effort") or None,
            timeout=(5 if long_turn else 2) * 3600, log_path=work / f"turn_{mid}.jsonl", on_event=TurnProgress(update),
            stop_flag=stop_flag, resume=resume, extra_args=["--disable-slash-commands"], env_extra=tool_env(),
            add_dirs=[str(store.rules_path().parent), str(config.ENGINE_DIR)])

    prompt = turn if session else prompts.context_prompt(p, rules) + "\n" + turn
    (work / f"turn_{mid}_prompt.txt").write_text(prompt, encoding="utf-8")
    res = claude(prompt, session)
    if session and "No conversation found" in (res.get("error") or ""):
        log.info("session %s of project %s is gone, starting a new one", session, p["id"])
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
                         rules_version=after["version"], cost_usd=(fresh.get("cost_usd") or 0) + (turn_cost or 0))
    fresh = store.get_project(p["id"])

    if kind == "step":
        problems, check_summary = workflow.check(step, store.project_dir(fresh), fresh)
        bad = workflow.blocking(problems)
        store.set_step(p["id"], step, status="failed" if bad else "review", finished_at=now_iso(),
                       problems=json.dumps(problems, ensure_ascii=False),
                       error=("thiếu kết quả: " + "; ".join(x for x in problems if not x.startswith("⚠"))) if bad else None)
        st = workflow.BY_KEY[step]
        store.log_event(p["id"], "failed" if bad else "done",
                        f"bước {st.num} · {st.name}: " + ("thiếu kết quả" if bad else (check_summary or "xong")), step)
        if not bad and fresh.get("auto_advance") and res.get("ok"):
            store.approve(fresh, step)
            nxt = workflow.next_step(step)
            if nxt and on_auto_next:
                on_auto_next(p["id"], nxt)
    else:
        # a chat turn may have edited any step's files: refresh the checks of the steps that have run
        for r in store.steps(fresh):
            if r["status"] in ("review", "approved", "failed"):
                store.recheck(fresh, r["step"])
    store.write_brief(store.get_project(p["id"]))


class Worker:
    def __init__(self):
        self.queue: deque[int] = deque()
        self.cv = threading.Condition()
        self.current: int | None = None
        self.cancelled: set[int] = set()
        self.thread = threading.Thread(target=self._loop, name="creater-worker", daemon=True)

    def start(self) -> None:
        with db.tx() as c:
            c.execute("UPDATE messages SET status='failed', error='app khởi động lại giữa chừng', finished_at=? "
                      "WHERE role='assistant' AND status='running'", (now_iso(),))
        for r in db.rows("SELECT * FROM project_steps WHERE status='running'"):
            p = store.get_project(r["project_id"])
            if p:
                _settle_step(p, r["step"], "app khởi động lại giữa chừng")
        for r in db.rows("SELECT id FROM messages WHERE role='assistant' AND status='queued' ORDER BY id"):
            self.queue.append(r["id"])
        try:
            store.sync_rules()
        except Exception:  # noqa: BLE001
            log.exception("rulebook sync failed")
        self.thread.start()
        log.info("worker started (%d queued)", len(self.queue))

    def enqueue(self, pid: int, text: str, kind: str = "chat", step: str | None = None) -> dict:
        p = store.get_project(pid)
        if not p:
            return {"error": "không có dự án này"}
        kind = kind if kind in ("chat", "step") else "chat"
        step = step if step in workflow.BY_KEY else None
        busy = store.busy_turn(pid)
        if busy:
            return {"error": "Claude đang " + ("làm" if busy["status"] == "running" else "chờ tới lượt") +
                             " cho dự án này, đợi xong rồi gửi tiếp (hoặc bấm Dừng)"}
        if kind == "step":
            if not step:
                return {"error": "thiếu bước"}
            r = store.step_row(pid, step) or {}
            if r.get("status") == "locked":
                prev = workflow.prev_step(step)
                return {"error": f"bước {workflow.BY_KEY[prev].num} · {workflow.BY_KEY[prev].name} chưa được duyệt"}
            text = (text or "").strip() or prompts.STEP_LABELS[step]
        text = (text or "").strip()
        if not text:
            return {"error": "chưa nhập nội dung"}
        uid = store.add_user_message(pid, text[:8000], kind, step)
        mid = store.add_assistant_turn(pid, uid, kind, step)
        if kind == "step":
            store.set_step(pid, step, status="queued", message_id=mid)
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
            if m["kind"] == "step" and m.get("step"):
                _settle_step(store.get_project(pid), m["step"])
            return {"message": "đã bỏ khỏi hàng đợi"}
        self.cancelled.add(m["id"])
        return {"message": "đang dừng lượt đang chạy"}

    def status(self) -> dict:
        cur = db.row("""SELECT m.id, m.project_id, m.kind, m.step, m.progress_msg, m.started_at, p.title AS project_title
                        FROM messages m JOIN projects p ON p.id=m.project_id WHERE m.id=?""", (self.current,)) if self.current else None
        queued = []
        for mid in list(self.queue):
            r = db.row("""SELECT m.id, m.project_id, m.kind, m.step, p.title AS project_title FROM messages m
                          JOIN projects p ON p.id=m.project_id WHERE m.id=?""", (mid,))
            if r:
                queued.append(r)
        return {"current": cur, "queue": queued}

    def _auto_next(self, pid: int, step: str) -> None:
        res = self.enqueue(pid, "", "step", step)
        if res.get("error"):
            log.warning("auto advance of project %s to %s: %s", pid, step, res["error"])

    def _loop(self) -> None:
        while True:
            with self.cv:
                while not self.queue:
                    self.cv.wait(timeout=30)
                mid = self.queue.popleft()
            self.current = mid
            try:
                run_turn(mid, stop_flag=lambda i=mid: i in self.cancelled, on_auto_next=self._auto_next)
            except Exception as e:  # noqa: BLE001
                log.exception("turn %s failed", mid)
                err = ("đã dừng" if mid in self.cancelled else str(e))[:1500]
                _set_msg(mid, status="failed", error=err, finished_at=now_iso())
                m = db.row("SELECT * FROM messages WHERE id=?", (mid,))
                if m and m["kind"] == "step" and m.get("step"):
                    p = store.get_project(m["project_id"])
                    status = _settle_step(p, m["step"], err)
                    store.log_event(p["id"], "failed", f"bước {workflow.BY_KEY[m['step']].num}: {err[:200]} ({status})", m["step"])
            finally:
                self.current = None
                self.cancelled.discard(mid)
