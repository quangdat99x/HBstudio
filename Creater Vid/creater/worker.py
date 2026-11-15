"""Queue + worker threads for the Claude turns.

Turns run in parallel (setting `claude_parallel`, default 4), one turn at a time per project (a project is one Claude
session). Turns that use the machine hard (GPU / CPU: image making and cut-outs, parallax, voice + whisper, rendering)
take the single heavy slot, so two of them never run at the same time; light turns (script, scenes, metadata, chat
about them) never wait for a heavy one.

A turn = one assistant message answering one user message: a chat text, or a step button. A step run starts a new
Claude session and a chat resumes the session of its step (setting claude_session_mode = "project": every turn of a
project resumes one session, see _pick_session). Before a turn the rulebook file and its history are synced (an edit made in an
editor becomes a version); after it, a change made by Claude becomes a version attributed to that turn. After a step
turn the step's output files are checked and the step goes to "chờ duyệt" (or "lỗi" when files are missing).
"""
from __future__ import annotations

import json
import logging
import os
import shutil
import sys
import threading
import time
from collections import deque
from pathlib import Path

from . import claude_runner, config, db, notify, prompts, scaffold, store, tgbot, workflow
from .util import now_iso

log = logging.getLogger("creater.worker")

# Voice, images and video come from gen.py (ElevenLabs and fal.ai APIs, keys on the Settings page) through Bash.
# No connector tool is allowed: a headless turn cannot publish, mail or spend through an account connector.
ALLOWED_TOOLS = ",".join(["Read", "Write", "Edit", "Glob", "Grep", "WebSearch", "WebFetch", "Bash", "TodoWrite"])
_GEN_LABELS = {"tts": "đọc lời dẫn (ElevenLabs)", "sfx": "tạo hiệu ứng âm thanh (ElevenLabs)", "image": "tạo ảnh (fal.ai)",
               "video": "tạo video AI (fal.ai)", "run": "chạy model fal.ai", "voices": "tìm giọng đọc",
               "check": "kiểm tra API", "schema": "xem tham số model", "models": "tìm model", "price": "xem giá model",
               "cost": "xem chi phí dự án"}
FILM_STEPS = ("images", "footage", "render")        # steps that work inside film/
LONG_STEPS = ("images", "footage", "render")
HEAVY_STEPS = ("images", "footage", "render")       # GPU / CPU heavy: only one such turn at a time across all projects


def is_heavy(m: dict) -> bool:
    """A step turn of a heavy step, or a chat sent while looking at one (it may redo images, the voice or a render)."""
    return (m.get("step") or "") in HEAVY_STEPS


def clean_remotion_temp(min_age_s: float = 15 * 60) -> None:
    """Delete Remotion's leftover temp folders (%TEMP%\\remotion-v*-assets*, remotion-webpack-bundle-*). Remotion
    removes them only when a render ends cleanly; a render that is stopped, times out or crashes leaves them behind
    (hundreds of folders, GBs). Only folders untouched for min_age_s go, so a render still running keeps its own."""
    import tempfile
    cutoff = time.time() - min_age_s
    n = 0
    for d in Path(tempfile.gettempdir()).glob("remotion-*"):
        try:
            if d.is_dir() and d.stat().st_mtime < cutoff:
                shutil.rmtree(d, ignore_errors=True)
                n += not d.exists()
        except OSError:
            pass
    if n:
        log.info("removed %d Remotion temp folders", n)


def _clean_remotion_temp_bg(min_age_s: float = 15 * 60) -> None:
    threading.Thread(target=clean_remotion_temp, args=(min_age_s,), name="remotion-temp-clean", daemon=True).start()


def _cuda_dll_dirs(python: str | None) -> list[str]:
    """bin folders of the nvidia-* wheels (cuBLAS, cuDNN…) next to a Python. faster-whisper (ctranslate2) looks for
    cublas64_12.dll on PATH only: without these on PATH, `WhisperModel(device="cuda")` fails and scripts fall back to
    the CPU. voice-build.py adds them itself; Claude's own whisper checks in a turn need them on PATH."""
    if not python:
        return []
    exe = Path(python)
    out: list[str] = []
    for sp in (exe.parent / "Lib" / "site-packages", exe.parent.parent / "Lib" / "site-packages"):   # install | venv
        out += [str(b) for b in sorted((sp / "nvidia").glob("*/bin")) if b.is_dir()]
    return out


def _physical_cores() -> int:
    """Real CPU cores (i9-10900: 10). Hyper-threading doubles the logical CPUs Windows shows, but the second thread
    of a core adds only ~15-30% on heavy work, so budgets count cores, not threads."""
    try:
        import subprocess
        out = subprocess.run(["powershell", "-NoProfile", "-Command",
                              "(Get-CimInstance Win32_Processor | Measure-Object NumberOfCores -Sum).Sum"],
                             capture_output=True, text=True, timeout=20,
                             creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout
        return max(1, int(out.strip()))
    except Exception:
        return max(1, (os.cpu_count() or 2) // 2)


_render_conc: int | None = None


def render_concurrency() -> int:
    """Chrome tabs Remotion renders with (E:\\Tool\\cpu_budget.json): a measured value when the budget has one
    ("render_concurrency", from `npx remotion benchmark`), else real cores minus the cores kept for the user. Each tab
    renders frames on the CPU, so more tabs than cores only makes them fight over the same cores."""
    global _render_conc
    if _render_conc is None:
        budget = {}
        for name in ("cpu_budget.json", "cpu_budget.local.json"):   # shared through Git, then this machine only
            try:
                budget.update(json.loads((config.TOOLS_ROOT / name).read_text(encoding="utf-8")))
            except Exception:  # noqa: BLE001
                pass
        measured = budget.get("render_concurrency")
        _render_conc = int(measured) if measured else max(2, int(_physical_cores() - float(budget.get("reserve_cores", 2))))
    return _render_conc


def tool_env(kind: str = "doc") -> dict:
    ff = db.get_setting("ffmpeg") or shutil.which("ffmpeg") or str(config.FFMPEG_FALLBACK)
    fp = str(Path(ff).with_name("ffprobe.exe")) if ff.lower().endswith("ffmpeg.exe") else (shutil.which("ffprobe") or str(config.FFPROBE_FALLBACK))
    bg = Path(db.get_setting("bgremove_python") or config.DEFAULT_SETTINGS["bgremove_python"])
    cuda = _cuda_dll_dirs(db.get_setting("whisper_python"))
    return {"CLAUDE_CODE_DISABLE_AUTO_MEMORY": "1", "FFMPEG": ff, "FFPROBE": fp, "PYTHONUTF8": "1",
            **({"PATH": os.pathsep.join(cuda + [os.environ.get("PATH", "")])} if cuda else {}),
            "ENABLE_CLAUDEAI_MCP_SERVERS": "false",           # claude.ai connectors stay out of film turns
            "CREATER_PYTHON": sys.executable, "GEN_PY": str(config.GEN_PY), "PARALLAX_PY": str(config.PARALLAX_PY), "LAYERKIT_PY": str(config.LAYERKIT_PY),
            # local background removal (BiRefNet on the GPU) and whisper for the narration timing
            "BGREMOVE_PY": str(bg), "BGREMOVE_HF": str(bg.parents[2] / "hf") if len(bg.parents) > 2 else "",
            "WHISPER_PY": db.get_setting("whisper_python"),
            "RENDER_CONCURRENCY": str(render_concurrency()),
            **_subagent_env(kind)}


def _subagent_env(kind: str) -> dict:
    """Subagents (Agent/Task tool) of a desk on another model than the turn (setting subagent_model_<desk>). _FORCE
    makes the CLI ignore a model the main turn names in its Agent call, so the setting always holds."""
    sub = (db.get_setting(f"subagent_model_{kind}") or "").strip()
    if not sub or sub == "inherit":
        return {}
    return {"CLAUDE_CODE_SUBAGENT_MODEL": sub, "CLAUDE_CODE_SUBAGENT_MODEL_FORCE": "1"}


def _pick_session(p: dict, kind: str, step: str | None, mid: int, book: str) -> tuple[str | None, int, float]:
    """The Claude session a turn resumes (None = a new one), the rulebook version that session already knows, and the
    session's running cost so far (the CLI reports a resumed run's cost as the session total).

    Setting claude_session_mode = "project": one session for the whole project (later steps carry every earlier step's
    context). "step" (default): a step run starts a new session (rulebook, brief, step states and the recent reports;
    the earlier steps' work is in their files); a chat resumes the session of the last turn of the step it is about,
    so a fix keeps that step's context."""
    own = (p.get("session_id"), p.get("rules_version") or 0, p.get("session_cost_usd") or 0)
    if (db.get_setting("claude_session_mode") or "step") == "project":
        return own
    if kind == "step":
        return None, 0, 0
    sql = ("SELECT session_id, finished_at FROM messages WHERE project_id=? AND role='assistant' AND status='done' "
           "AND session_id IS NOT NULL AND id<>?")
    args: list = [p["id"], mid]
    if step:
        sql += " AND step=?"
        args.append(step)
    last = db.row(sql + " ORDER BY id DESC LIMIT 1", args)
    if not last:
        return None, 0, 0
    sid = last["session_id"]
    if sid == p.get("session_id"):
        return own
    known = db.row("SELECT MAX(version) AS v FROM rules WHERE COALESCE(book, 'doc')=? AND created_at<=?",
                   (book, last["finished_at"] or ""))
    spent = db.row("SELECT COALESCE(SUM(cost_usd), 0) AS c FROM messages WHERE session_id=? AND role='assistant'", (sid,))
    return sid, (known or {}).get("v") or 0, (spent or {}).get("c") or 0


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
            elif "GEN_PY" in cmd or "gen.py" in cmd:
                words = cmd.replace('"', " ").split()
                sub = next((w for w in words if w in _GEN_LABELS), "")
                self.last = _GEN_LABELS.get(sub, "gọi API tạo nguyên liệu")
            else:
                self.last = "chạy lệnh: " + cmd.strip().splitlines()[0][:90] if cmd.strip() else "chạy lệnh"
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
    st = workflow.flow(p).by_key.get(step)
    has_output = bool(st) and any((store.project_dir(p) / rel).exists() for rel in st.outputs)
    status = "review" if has_output and not workflow.blocking(problems) else ("failed" if error else "ready")
    store.set_step(p["id"], step, status=status, error=(error or "")[:1500] or None, finished_at=now_iso(),
                   problems=json.dumps(problems, ensure_ascii=False))
    return status


def run_turn(mid: int, stop_flag=None, on_auto_next=None) -> None:
    m = db.row("SELECT * FROM messages WHERE id=?", (mid,))
    p = store.get_project(m["project_id"])
    user = db.row("SELECT * FROM messages WHERE id=?", (m["reply_to"],)) if m.get("reply_to") else None
    kind = m["kind"] if m["kind"] in ("chat", "step") else "chat"
    fl = workflow.flow(p)
    book = store.kind_of(p)                      # each kind of video reads and edits only its own rulebook
    step = m.get("step") if m.get("step") in fl.by_key else None
    _set_msg(mid, status="running", started_at=now_iso(), progress_msg="khởi động")
    if kind == "step":
        r = store.step_row(p["id"], step) or {}
        store.set_step(p["id"], step, status="running", started_at=now_iso(), message_id=mid, runs=(r.get("runs") or 0) + 1,
                       error=None)
        store.log_event(p["id"], "run", f"chạy bước {fl.names()[step]}", step)

    def update(msg: str) -> None:
        _set_msg(mid, progress_msg=msg[:500])

    store.sync_rules(book, source="file", project_id=p["id"], note="sửa file ngoài app")
    rules = store.current_rules(book)
    if step in FILM_STEPS or (kind == "chat" and scaffold.film_ready(store.project_dir(p))):
        scaffold.scaffold_film(p, update)
    store.write_brief(p)

    session, known_rules, base_cost = _pick_session(p, kind, step, mid, book)
    per_step = (db.get_setting("claude_session_mode") or "step") != "project"
    note = ""
    if session and known_rules < rules["version"]:
        note = prompts.rules_changed_note(p, rules)
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
            stop_flag=stop_flag, resume=resume, extra_args=["--disable-slash-commands"], env_extra=tool_env(book),
            add_dirs=[str(store.rules_path(book).parent), str(config.ENGINE_DIR)])

    history = [x for x in store.messages(p["id"]) if x["id"] not in (mid, m.get("reply_to"))]
    if session:
        prompt = turn
    else:
        # a new session: the earlier steps' reports carry the user's decisions into it (the work itself is in files)
        prompt = "\n".join([prompts.context_prompt(p, rules, per_step=per_step),
                            prompts.seed_history(history, 8000, gone=False) if per_step else "", turn])
    (work / f"turn_{mid}_prompt.txt").write_text(prompt, encoding="utf-8")
    res = claude(prompt, session)
    if session and "No conversation found" in (res.get("error") or ""):
        log.info("session %s of project %s is gone, starting a new one", session, p["id"])
        prompt = "\n".join([prompts.context_prompt(p, rules, per_step=per_step), prompts.seed_history(history), turn])
        res = claude(prompt, None)
        session = None
    if stop_flag and stop_flag():
        raise RuntimeError("đã dừng theo yêu cầu")
    answer = (res.get("result") or "").strip() or (res.get("texts") or [""])[-1].strip()
    if not res.get("ok") and not answer:
        raise RuntimeError(res.get("error") or "Claude không trả lời")

    same = session and res.get("session_id") == session
    cost = res.get("cost_usd")
    turn_cost = (cost - base_cost) if same and cost is not None else cost
    if turn_cost is not None and turn_cost < 0:
        turn_cost = None
    after = store.sync_rules(book, source="claude", project_id=p["id"], message_id=mid,
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
        st = fl.by_key[step]
        store.log_event(p["id"], "failed" if bad else "done",
                        f"bước {st.num} · {st.name}: " + ("thiếu kết quả" if bad else (check_summary or "xong")), step)
        if not bad and fresh.get("auto_advance") and res.get("ok"):
            store.approve(fresh, step)
            nxt = fl.next(step)
            if nxt and on_auto_next:
                on_auto_next(p["id"], nxt)
        elif not fresh.get("auto_advance"):
            # step by step: the approval (or the failure) goes to the user's Telegram too
            if bad:
                tgbot._safe(tgbot.notify_failed, p["id"], step, "thiếu kết quả: " + "; ".join(
                    x for x in problems if not x.startswith("⚠")))
            else:
                tgbot._safe(tgbot.notify_review, p["id"], step, answer)
        # 🔔 the bell in the header: done (auto), waiting for approval, or failed
        if bad:
            notify.step_failed(p["id"], step, "thiếu kết quả: " + "; ".join(x for x in problems if not x.startswith("⚠")))
        elif fresh.get("auto_advance") and res.get("ok"):
            notify.step_done(p["id"], step, fl.next(step))
        else:
            notify.step_review(p["id"], step, "" if not fresh.get("auto_advance") else
                               f"tự chạy dừng lại ({(res.get('error') or 'lượt Claude báo lỗi')[:120]}), duyệt tay để chạy tiếp")
    else:
        # a chat turn may have edited any step's files: refresh the checks of the steps that have run
        for r in store.steps(fresh):
            if r["status"] in ("review", "approved", "failed"):
                store.recheck(fresh, r["step"])
        notify.chat_done(p["id"], step, answer)
        # a change asked from Telegram: send the step back for approval
        if step and ((user or {}).get("content") or "").startswith(tgbot.ORIGIN):
            tgbot._safe(tgbot.notify_review, p["id"], step, answer, "Claude đã sửa theo yêu cầu")
    store.write_brief(store.get_project(p["id"]))


class Worker:
    """N threads pull turns from one queue. A turn may start when its project has no other turn running and, if it is
    heavy, when the heavy slot is free; otherwise later turns that can start go first (the queue keeps its order)."""

    def __init__(self):
        self.queue: deque[int] = deque()
        self.cv = threading.Condition()
        self.running: dict[int, dict] = {}            # message id -> {"pid", "heavy"}
        self.cancelled: set[int] = set()
        self.threads: list[threading.Thread] = []

    @property
    def current(self) -> int | None:                  # kept for callers that show "the" running turn
        return next(iter(self.running), None)

    def slots(self) -> int:
        return max(1, min(8, db.setting_int("claude_parallel") or 1))

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
            store.sync_all_rules()
        except Exception:  # noqa: BLE001
            log.exception("rulebook sync failed")
        _clean_remotion_temp_bg()
        for n in range(8):                            # idle threads cost nothing; slots() caps how many work at once
            th = threading.Thread(target=self._loop, name=f"creater-worker-{n}", daemon=True)
            th.start()
            self.threads.append(th)
        log.info("worker started (%d queued, %d parallel)", len(self.queue), self.slots())

    def enqueue(self, pid: int, text: str, kind: str = "chat", step: str | None = None) -> dict:
        p = store.get_project(pid)
        if not p:
            return {"error": "không có dự án này"}
        kind = kind if kind in ("chat", "step") else "chat"
        fl = workflow.flow(p)
        step = step if step in fl.by_key else None
        busy = store.busy_turn(pid)
        if busy:
            return {"error": "Claude đang " + ("làm" if busy["status"] == "running" else "chờ tới lượt") +
                             " cho dự án này, đợi xong rồi gửi tiếp (hoặc bấm Dừng)"}
        if kind == "step":
            if not step:
                return {"error": "thiếu bước"}
            r = store.step_row(pid, step) or {}
            if r.get("status") == "locked":
                return {"error": f"bước {fl.names()[fl.prev(step)]} chưa được duyệt"}
            text = (text or "").strip() or prompts.step_label(p, step)
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
            self.cv.notify_all()
            heavy = step in HEAVY_STEPS
            wait = self._why_waiting({"project_id": pid, "step": step})
        msg = "đã gửi cho Claude"
        if wait:
            msg += f", chờ {wait}"
        elif heavy:
            msg += " (việc nặng: chạy một mình phần GPU/CPU)"
        return {"message_id": mid, "message": msg}

    def _why_waiting(self, m: dict) -> str:
        """Why a turn could not start now ('' = it can). Call with self.cv held."""
        if is_heavy(m) and any(r["heavy"] for r in self.running.values()):
            return "việc nặng khác (render / ảnh / giọng) chạy xong"
        if len(self.running) >= self.slots():
            return f"{len(self.running)} lượt đang chạy (tối đa {self.slots()} cùng lúc)"
        return ""

    def _pick(self) -> dict | None:
        """First queued turn that can start now. Call with self.cv held."""
        if len(self.running) >= self.slots():
            return None
        heavy_busy = any(r["heavy"] for r in self.running.values())
        busy_projects = {r["pid"] for r in self.running.values()}
        for mid in list(self.queue):
            m = db.row("SELECT id, project_id, step, status FROM messages WHERE id=?", (mid,))
            if not m or m["status"] != "queued":
                self.queue.remove(mid)
                continue
            if m["project_id"] in busy_projects:
                continue
            heavy = is_heavy(m)
            if heavy and heavy_busy:
                continue
            self.queue.remove(mid)
            self.running[mid] = {"pid": m["project_id"], "heavy": heavy}
            return m
        return None

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

    def _row(self, mid: int) -> dict | None:
        return db.row("""SELECT m.id, m.project_id, m.kind, m.step, m.progress_msg, m.started_at, p.title AS project_title,
                                COALESCE(p.kind, 'doc') AS project_kind
                         FROM messages m JOIN projects p ON p.id=m.project_id WHERE m.id=?""", (mid,))

    def status(self) -> dict:
        with self.cv:
            running = [(mid, dict(r)) for mid, r in self.running.items()]
            queued_ids = list(self.queue)
        cur = []
        for mid, r in running:
            row = self._row(mid)
            if row:
                cur.append(dict(row, heavy=r["heavy"]))
        queued = []
        for mid in queued_ids:
            row = self._row(mid)
            if row:
                with self.cv:
                    row["waiting"] = self._why_waiting(row) or ("dự án này còn lượt khác" if row["project_id"] in
                                                                {r["pid"] for _, r in running} else "")
                queued.append(row)
        return {"current": cur[0] if cur else None, "running": cur, "queue": queued, "parallel": self.slots()}

    def _auto_next(self, pid: int, step: str) -> None:
        res = self.enqueue(pid, "", "step", step)
        if res.get("error"):
            log.warning("auto advance of project %s to %s: %s", pid, step, res["error"])

    def _loop(self) -> None:
        while True:
            with self.cv:
                m = self._pick()
                while m is None:
                    self.cv.wait(timeout=30)
                    m = self._pick()
            mid = m["id"]
            try:
                run_turn(mid, stop_flag=lambda i=mid: i in self.cancelled, on_auto_next=self._auto_next)
            except Exception as e:  # noqa: BLE001
                log.exception("turn %s failed", mid)
                err = ("đã dừng" if mid in self.cancelled else str(e))[:1500]
                _set_msg(mid, status="failed", error=err, finished_at=now_iso())
                row = db.row("SELECT * FROM messages WHERE id=?", (mid,))
                if row and row["kind"] == "step" and row.get("step"):
                    p = store.get_project(row["project_id"])
                    status = _settle_step(p, row["step"], err)
                    store.log_event(p["id"], "failed", f"bước {workflow.flow(p).names().get(row['step'], row['step'])}: {err[:200]} ({status})", row["step"])
                    if status == "review":
                        notify.step_review(p["id"], row["step"], "lượt chạy dừng giữa chừng nhưng kết quả dùng được")
                        tgbot._safe(tgbot.notify_review, p["id"], row["step"], "", "lượt chạy dừng giữa chừng nhưng kết quả dùng được")
                    elif mid not in self.cancelled:
                        notify.step_failed(p["id"], row["step"], err)
                        tgbot._safe(tgbot.notify_failed, p["id"], row["step"], err)
            finally:
                with self.cv:
                    was_heavy = (self.running.pop(mid, None) or {}).get("heavy")
                    self.cancelled.discard(mid)
                    self.cv.notify_all()
                if was_heavy:                         # renders run only in heavy turns, one at a time
                    _clean_remotion_temp_bg()
