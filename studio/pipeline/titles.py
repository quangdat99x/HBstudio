"""Viết Title: run the viet-tittle skill headless for one highlight and keep the result on that segment.

Runs have their own queue and worker thread, so writing titles never blocks the main pipeline
(transcribe/select/cut/zoom). Every run is stored in `segment_titles`; the episode page shows the latest.
The skill gets exactly what it expects when run by hand: the clip transcript in the Video Cutter sidecar
format (absolute timestamps + "Thời gian: start → end" header) and the cutlist entry of that segment (Bước 0).

Chat: under the result the user can message Claude to adjust the metadata. Each message is one more run
(`parent_id` = the run it adjusts, `user_message` = the message) that resumes the Claude session of the parent,
so Claude still has the skill, the transcript and its own answer, and edits the result JSON in place. A parent
without a stored session (runs made before chat existed, or a session Claude Code no longer keeps) gets a new
session seeded with the skill, the inputs and the previous answer. Runs use the isolated CLI setup (skill text in
the prompt, no MCP servers or skill list riding along), so every chat turn stays small.
"""
from __future__ import annotations

import json
import logging
import re
import threading
import time
from collections import deque
from pathlib import Path

from .. import config, db
from ..util import clean_stem, now_iso, read_json, slice_transcript, write_json
from . import claude_runner
from .select_ai import skill_body, sync_skill

log = logging.getLogger("studio.titles")
TITLE_TOOLS = "Read,Write,Edit,WebSearch,WebFetch,Bash(python *),Bash(py *)"     # pre-approved
TITLE_TOOLSET = "Read,Write,Edit,Bash,WebSearch,WebFetch"                          # all the model sees
ENTRY_FIELDS = ("rank", "kind", "content_rank", "start_hms", "end_hms", "title", "summary_vi", "summary_en", "hook_en",
                "intensity", "cq", "gtf", "final_score", "value_axis", "core_keyword", "keyword_reach",
                "keyword_credibility", "keyword_reason", "fit_reason")


# ---------------------------------------------------------------- inputs
def _bundle(seg_id: int) -> tuple[dict, dict, list[dict]]:
    seg = db.row("SELECT * FROM segments WHERE id=?", (seg_id,))
    if not seg:
        raise RuntimeError(f"không có đoạn #{seg_id}")
    if seg["kind"] != "highlight":
        raise RuntimeError("chỉ viết title cho đoạn highlight, không cho hook")
    if seg["start_sec"] is None:
        raise RuntimeError("đoạn này không có timestamp (nạp từ clip cũ), không viết title tự động được")
    ep = db.row("SELECT * FROM episodes WHERE id=?", (seg["episode_id"],))
    hooks = db.rows("SELECT * FROM segments WHERE parent_id=? ORDER BY rank", (seg_id,))
    return seg, ep, hooks


def episode_name(ep: dict) -> str:
    return clean_stem(Path(ep.get("source_video") or "").stem) or ep["id"]


def _entry(seg: dict) -> dict:
    """Cutlist entry of a segment: DB columns, overlaid with the original cutlist entry when we have it."""
    e = {("start" if k == "start_hms" else "end" if k == "end_hms" else k): seg.get(k) for k in ENTRY_FIELDS
         if seg.get(k) not in (None, "")}
    e["topics"] = [r["name"] for r in db.rows(
        "SELECT t.name FROM segment_topics st JOIN topics t ON t.id=st.topic_id WHERE st.segment_id=?", (seg["id"],))]
    if seg.get("satellite_keywords_json"):
        try:
            e["satellite_keywords"] = json.loads(seg["satellite_keywords_json"])
        except ValueError:
            pass
    if seg.get("raw_json"):
        try:
            e.update(json.loads(seg["raw_json"]))
        except ValueError:
            pass
    return e


def prepare_inputs(seg: dict, ep: dict, hooks: list[dict], work: Path, keep_existing: bool = False) -> tuple[Path, Path]:
    """Clip transcript + one-segment cutlist for the skill. keep_existing (chat turns): leave files Claude already read."""
    work.mkdir(parents=True, exist_ok=True)
    tpath = work / f"{int(seg['rank'] or 0):02d}_transcript.txt"
    cpath = work / f"cutlist_{ep['id']}_doan{int(seg['rank'] or 0):02d}.json"
    if keep_existing and tpath.exists() and cpath.exists():
        return tpath, cpath
    text = seg.get("transcript") or ""
    if not text:
        lines = db.rows("SELECT start_sec AS start, end_sec AS end, text FROM transcript_lines WHERE episode_id=? ORDER BY seq",
                        (ep["id"],))
        text = slice_transcript(lines, seg["start_sec"], seg["end_sec"])
    if not text.strip():
        raise RuntimeError("không có transcript cho đoạn này")
    dur = max(0.0, (seg["end_sec"] or 0) - (seg["start_sec"] or 0))
    header = [f"Tên: {seg['title']}",
              f"Thời gian: {seg['start_hms']} → {seg['end_hms']} ({int(dur // 60)} phút {int(dur % 60)} giây)",
              f"Video gốc: {ep.get('source_video') or ''}", "", "--- Transcript ---"]
    tpath.write_text("\n".join(header) + "\n" + text.strip() + "\n", encoding="utf-8")

    profile = None
    if ep.get("guest_profile_json"):
        try:
            profile = json.loads(ep["guest_profile_json"])
        except ValueError:
            profile = None
    cutlist = {
        "version": 2, "cutlist_layout": "flat_hooks", "source": "jre-studio (trích 1 đoạn)",
        "episode": {"id": ep["id"], "guest": ep.get("guest"), "source_video": ep.get("source_video"),
                    **({"guest_profile": profile} if profile else {})},
        "segments": [_entry(h) for h in hooks] + [_entry(seg)],
    }
    cpath.write_text(json.dumps(cutlist, ensure_ascii=False, indent=2), encoding="utf-8")
    return tpath, cpath


def _skill_lines(skill: str, skill_text: str) -> list[str]:
    return [f"Dưới đây là toàn văn skill `{skill}` (bản đồng bộ từ app desktop). Làm đúng theo skill này.", "",
            f'<skill name="{skill}">', skill_text, "</skill>", ""]


def _data_lines(seg: dict, ep: dict, tpath: Path, cpath: Path) -> list[str]:
    dur = max(0.0, (seg["end_sec"] or 0) - (seg["start_sec"] or 0))
    return [
        "DỮ LIỆU (dùng thẳng, không hỏi lại):",
        f"- Transcript của đoạn đã cắt: {tpath}",
        f"  Timestamp trong file là giờ của tập gốc. Clip bắt đầu ở {seg['start_hms']}, kết thúc ở {seg['end_hms']} "
        f"(dòng \"Thời gian\" ở đầu file), nên timestamps cho YouTube phải trừ offset {seg['start_hms']} đúng luật của skill.",
        f"- Cutlist của riêng đoạn này cho Bước 0: {cpath}. Entry kind=highlight là đoạn cần viết; "
        "các entry kind=hook là hook cold open nằm bên trong đoạn.",
        f"- Tên tập: {episode_name(ep)} · episode_id {ep['id']} · khách mời: {ep.get('guest') or ''}",
        f"- Thời lượng clip: {int(dur // 60)} phút {int(dur % 60)} giây",
        "",
    ]


_PYTHON_RULE = ("Chỉ được phép chạy python bằng MỘT lệnh đứng riêng dạng `python -X utf8 <đường dẫn file .py>` hoặc "
                "`python -X utf8 -c \"...\"`: không `cd`, không nối lệnh bằng && hay ;, không dùng PowerShell.")


def build_prompt(skill: str, skill_text: str, seg: dict, ep: dict, tpath: Path, cpath: Path, out_json: Path) -> str:
    return "\n".join(_skill_lines(skill, skill_text) + [
        "YÊU CẦU: chạy wf VIẾT TITTLE cho MỘT đoạn highlight, ở CHẾ ĐỘ TỰ ĐỘNG (headless).",
        "",
        *_data_lines(seg, ep, tpath, cpath),
        "LUẬT CHẾ ĐỘ TỰ ĐỘNG:",
        "1. Không hỏi người dùng. Chỗ nào skill bảo báo hoặc hỏi người dùng thì ghi một dòng ⚠️ cảnh báo ngay trong kết quả, "
        "tự quyết theo mặc định của skill rồi làm tiếp.",
        "2. Xuất đủ 4 bước đúng format của skill ngay trong câu trả lời: phân tích bằng tiếng Việt; title, description, "
        "timestamps, tags và image prompt bằng tiếng Anh.",
        f"3. Sau đó ghi MỘT file JSON UTF-8 vào {out_json} với các khóa: "
        "\"core_keyword\", \"vibe\", \"big_hook\", \"titles_format1\" (mảng 3 title), \"titles_format2\" (mảng 3 title), "
        "\"recommended_title\" (title bạn khuyên dùng nhất), \"description\" (toàn văn, gồm cả dòng cuối), "
        "\"timestamps\" (toàn văn khối timestamps), \"tags\" (chuỗi tags), \"tags_chars\" (số ký tự thực tế), "
        "\"thumbnail\" (tóm tắt chiến lược thumbnail), \"image_prompt\" (toàn văn), \"warnings\" (mảng cảnh báo, có thể rỗng).",
        "4. Đếm ký tự của title và tags bằng python khi cần, không ước lượng. " + _PYTHON_RULE,
        "5. Không đọc mã nguồn trong E:\\DataBase. Kết thúc bằng đúng một dòng: DONE title_json=<đường dẫn>",
    ])


def build_chat_prompt(message: str, out_json: Path) -> str:
    """One chat turn inside the session that wrote the metadata (or a seeded one): adjust the JSON in place."""
    return "\n".join([
        "Người dùng vừa xem metadata của đoạn này trên JRE Studio và nhắn:",
        '"""', message.strip(), '"""',
        "",
        "LUẬT KHI CHỈNH:",
        f"1. File JSON đang hiển thị trên Studio: {out_json}. Nếu tin nhắn yêu cầu đổi metadata thì sửa thẳng file đó "
        "(Edit, hoặc Write lại cả file nếu đổi nhiều), giữ đủ các khóa như cũ và cập nhật cả các trường liên quan theo luật "
        "của skill (recommended_title, titles_format1/2, description, timestamps, tags và tags_chars, thumbnail, image_prompt).",
        "2. Nếu tin nhắn chỉ hỏi thì trả lời, không sửa file.",
        "3. Giữ luật của skill (keyword ở đầu title, giới hạn ký tự…). Người dùng yêu cầu điều trái luật skill thì vẫn làm theo "
        "người dùng, kèm một dòng ⚠️ nói rõ luật nào bị phá.",
        "4. Đếm ký tự title và tags bằng python khi đổi chúng, không ước lượng. " + _PYTHON_RULE,
        "5. Trả lời ngắn bằng tiếng Việt: đổi trường nào, giá trị mới là gì (title, tags… ghi nguyên văn tiếng Anh). "
        "Không in lại toàn bộ kết quả, không đọc lại file sau khi sửa.",
        f"6. Kết thúc bằng đúng một dòng: DONE title_json={out_json}",
    ])


def build_seed_prompt(skill: str, skill_text: str, seg: dict, ep: dict, tpath: Path, cpath: Path, out_json: Path,
                      previous_md: str, message: str) -> str:
    """Chat turn without a session to resume: skill, inputs and the stored answer, then the user's message."""
    return "\n".join(_skill_lines(skill, skill_text) + [
        "BỐI CẢNH: skill này đã chạy cho MỘT đoạn highlight ở chế độ tự động. Câu trả lời lần đó ở dưới; metadata đang "
        f"hiển thị trên JRE Studio nằm trong {out_json} (đọc file đó trước khi sửa, nó có thể mới hơn câu trả lời).",
        "",
        *_data_lines(seg, ep, tpath, cpath),
        "<cau_tra_loi_truoc>", (previous_md or "(không lưu)").strip(), "</cau_tra_loi_truoc>",
        "",
        build_chat_prompt(message, out_json),
    ])


# ---------------------------------------------------------------- progress
class TitleProgress:
    def __init__(self, update):
        self.update = update
        self.started = time.time()
        self.tools = 0
        self.thinking = 0
        self.last = "khởi động"
        self._t = 0.0

    def _emit(self, force: bool = False) -> None:
        now = time.time()
        if not force and now - self._t < 6:
            return
        self._t = now
        think = f" · {self.thinking / 1000:.0f}k token suy nghĩ" if self.thinking >= 1000 else ""
        self.update(f"[{int((now - self.started) // 60)} phút · {self.tools} lượt công cụ{think}] {self.last}")

    def __call__(self, kind: str, data) -> None:
        if kind == "text_delta":                          # raw streamed text; "writing" already counts it
            return
        if kind == "thinking":
            self.thinking += int(data or 0)
            self._emit()
            return
        if kind in ("writing", "writing_tool"):
            what = "ghi file kết quả" if kind == "writing_tool" else "viết title, description, tags"
            chars = f"{int(data or 0):,}".replace(",", ".")
            self.last = f"đang {what} (~{chars} ký tự)"
            self._emit()
            return
        if kind == "text":
            self.last = str(data).strip().replace("\n", " ")[-140:]
            self._emit(force=True)
            return
        name, inp = data
        self.tools += 1
        fp = str(inp.get("file_path") or "")
        if name == "Read" and fp.endswith("_transcript.txt"):
            self.last = "đọc transcript của đoạn"
        elif name == "Read" and "cutlist_" in fp:
            self.last = "nạp cutlist của đoạn (Bước 0)"
        elif name == "Read" and fp.endswith("SKILL.md"):
            self.last = "đọc skill"
        elif name in ("WebSearch", "WebFetch"):
            self.last = "tra web: " + str(inp.get("query") or inp.get("url") or "")[:70]
        elif name in ("Bash", "PowerShell"):
            self.last = "đếm ký tự / kiểm tra bằng python"
        elif name == "Write":
            self.last = "ghi kết quả"
        else:
            self.last = f"dùng công cụ {name}"
        self._emit(force=True)


# ---------------------------------------------------------------- run
_RE_TITLE_LINE = re.compile(r"^\s*\|?\s*\d\s*\|\s*(.+?Joe Rogan.*?)\s*\|", re.M)
_RE_DONE_LINE = re.compile(r"^\s*DONE\s+title_json=.*$", re.M)


def final_answer(texts: list[str]) -> str:
    """The skill's answer without the short status notes Claude writes between tool calls, and without the DONE line."""
    blocks = [t for t in texts if t and t.strip()]
    if not blocks:
        return ""
    longest = max(range(len(blocks)), key=lambda i: len(blocks[i]))
    answer = "\n\n".join(blocks[longest:])
    return _RE_DONE_LINE.sub("", answer).strip()


def _fallback_title(text: str) -> str | None:
    m = _RE_TITLE_LINE.search(text or "")
    return m.group(1).strip().strip("*`") if m else None


def _work_paths(seg: dict, ep: dict) -> tuple[Path, Path]:
    work = config.WORK_DIR / "titles" / f"{ep['id']}_{int(seg['rank'] or 0):02d}"
    return work, work / f"title_{ep['id']}_{int(seg['rank'] or 0):02d}.json"


def _skill_text(skill: str) -> str:
    path = sync_skill(skill)
    if not path:
        raise RuntimeError(f"không tìm thấy SKILL.md của {skill} trong thư mục plugin của app desktop")
    return skill_body(path)


def _start(run_id: int, seg: dict, ep: dict, label: str):
    """Job row for the queue page + a progress callback writing to the run and the job."""
    with db.tx() as c:
        c.execute("INSERT INTO jobs(episode_id, stage, status, progress, message, attempts, started_at) VALUES(?,?,?,?,?,?,?)",
                  (ep["id"], "title", "running", 0, label[:500], 1, now_iso()))
        job_id = c.execute("SELECT last_insert_rowid()").fetchone()[0]
        c.execute("UPDATE segment_titles SET status='running', started_at=?, progress_msg=? WHERE id=?",
                  (now_iso(), "khởi động", run_id))

    def update(msg: str) -> None:
        with db.tx() as c:
            c.execute("UPDATE segment_titles SET progress_msg=? WHERE id=?", (msg[:400], run_id))
            c.execute("UPDATE jobs SET message=? WHERE id=?", (f"#{seg['rank']} {msg}"[:500], job_id))
    return job_id, update


def _read_result(out_json: Path, run_id: int):
    if not out_json.exists():
        return None
    try:
        return read_json(out_json)
    except Exception as e:  # noqa: BLE001
        log.warning("title json unreadable for run %s: %s", run_id, e)
        return None


def _finish(run_id: int, job_id: int, seg: dict, res: dict, data, text: str, turn_cost=None) -> dict:
    recommended = (data or {}).get("recommended_title") or _fallback_title(text)
    shown = dict(res, cost_usd=turn_cost) if turn_cost is not None else res
    summary = claude_runner.describe_run(shown)
    with db.tx() as c:
        c.execute("""UPDATE segment_titles SET status='done', output_md=?, output_json=?, recommended_title=?, models_used=?,
                     usage_json=?, duration_sec=?, finished_at=?, progress_msg=?, error=?, session_id=?, session_cost_usd=?
                     WHERE id=?""",
                  (text, json.dumps(data, ensure_ascii=False) if data else None, recommended,
                   ",".join(res.get("models") or []), json.dumps(res.get("usage") or {}), res.get("duration_sec"),
                   now_iso(), summary, None if res.get("ok") else f"cảnh báo: {res.get('error')}",
                   res.get("session_id"), res.get("cost_usd"), run_id))
        c.execute("UPDATE jobs SET status='done', progress=100, message=?, finished_at=? WHERE id=?",
                  (f"#{seg['rank']} xong · {summary}"[:500], now_iso(), job_id))
    from ..search import rebuild_index
    rebuild_index([seg["id"]])
    return {"run_id": run_id, "recommended_title": recommended, "summary": summary}


def _claude(prompt: str, run: dict, work: Path, log_name: str, update, stop_flag, resume: str | None = None,
            max_turns: int = 40, timeout: int = 45 * 60) -> dict:
    return claude_runner.run(prompt, cwd=config.BASE_DIR, tools=TITLE_TOOLSET, allowed_tools=TITLE_TOOLS, isolated=True,
                             permission_mode="acceptEdits", max_turns=max_turns, model=run["model"] or None,
                             effort=run["effort"] or None, timeout=timeout, log_path=work / log_name,
                             on_event=TitleProgress(update), stop_flag=stop_flag, resume=resume)


def run_title(run_id: int, stop_flag=None) -> dict:
    run = db.row("SELECT * FROM segment_titles WHERE id=?", (run_id,))
    if run.get("parent_id"):
        return run_chat(run, stop_flag)
    seg, ep, hooks = _bundle(run["segment_id"])
    skill = run["skill"] or db.get_setting("title_skill")
    skill_text = _skill_text(skill)
    work, out_json = _work_paths(seg, ep)
    tpath, cpath = prepare_inputs(seg, ep, hooks, work)
    if out_json.exists():
        out_json.rename(out_json.with_name(out_json.name + f".old_{int(out_json.stat().st_mtime)}"))
    job_id, update = _start(run_id, seg, ep, f"viết title đoạn #{seg['rank']}: {seg['title'][:60]}")
    prompt = build_prompt(skill, skill_text, seg, ep, tpath, cpath, out_json)
    (work / "prompt.txt").write_text(prompt, encoding="utf-8")
    res = _claude(prompt, run, work, "claude_run.jsonl", update, stop_flag)
    data = _read_result(out_json, run_id)
    text = final_answer(res.get("texts") or [res.get("text") or ""])
    if not res.get("ok") and not data:
        raise RuntimeError(res.get("error") or "Claude không trả kết quả")
    if not text and not data:
        raise RuntimeError("Claude chạy xong nhưng không có nội dung")
    return _finish(run_id, job_id, seg, res, data, text)


def _chain_root(run: dict) -> dict:
    cur = run
    while cur.get("parent_id"):
        parent = db.row("SELECT * FROM segment_titles WHERE id=?", (cur["parent_id"],))
        if not parent:
            break
        cur = parent
    return cur


def run_chat(run: dict, stop_flag=None) -> dict:
    """One chat message: resume the parent's Claude session and let it edit the result JSON in place."""
    parent = db.row("SELECT * FROM segment_titles WHERE id=?", (run["parent_id"],))
    if not parent or parent["status"] != "done":
        raise RuntimeError("không còn bản title gốc để chỉnh")
    seg, ep, hooks = _bundle(run["segment_id"])
    skill = parent["skill"] or db.get_setting("title_skill")
    work, out_json = _work_paths(seg, ep)
    tpath, cpath = prepare_inputs(seg, ep, hooks, work, keep_existing=True)
    current = None
    if parent.get("output_json"):
        try:
            current = json.loads(parent["output_json"])
        except ValueError:
            current = None
    if current is not None and _read_result(out_json, run["id"]) != current:
        write_json(out_json, current)                    # Claude edits exactly what the page shows
    job_id, update = _start(run["id"], seg, ep, f"chat title đoạn #{seg['rank']}: {run['user_message'][:80]}")
    session = parent.get("session_id")
    log_name = f"chat_{run['id']}.jsonl"
    res = None
    if session:
        res = _claude(build_chat_prompt(run["user_message"], out_json), run, work, log_name, update, stop_flag,
                      resume=session, max_turns=25, timeout=20 * 60)
        if "No conversation found" in (res.get("error") or ""):
            log.info("title session %s is gone, seeding a new one", session)
            res, session = None, None
    if res is None:
        prompt = build_seed_prompt(skill, _skill_text(skill), seg, ep, tpath, cpath, out_json,
                                   _chain_root(parent).get("output_md") or "", run["user_message"])
        res = _claude(prompt, run, work, log_name, update, stop_flag, max_turns=25, timeout=20 * 60)
    if stop_flag and stop_flag():
        raise RuntimeError("đã hủy")
    data = _read_result(out_json, run["id"]) or current
    text = final_answer(res.get("texts") or [res.get("text") or ""])
    if not res.get("ok") and not text:
        raise RuntimeError(res.get("error") or "Claude không trả lời")
    # a resumed session reports its running total, so this turn costs the difference to the parent
    same = session and res.get("session_id") == parent.get("session_id")
    turn_cost = (res["cost_usd"] - (parent.get("session_cost_usd") or 0)) if same and res.get("cost_usd") else None
    if turn_cost is not None and turn_cost < 0:
        turn_cost = None
    return _finish(run["id"], job_id, seg, res, data, text or "Đã xong.", turn_cost=turn_cost)


# ---------------------------------------------------------------- queue + worker
class TitleWorker:
    def __init__(self):
        self.queue: deque[int] = deque()
        self.cv = threading.Condition()
        self.current: int | None = None
        self.cancelled: set[int] = set()
        self.thread = threading.Thread(target=self._loop, name="studio-titles", daemon=True)

    def start(self) -> None:
        with db.tx() as c:
            c.execute("UPDATE segment_titles SET status='failed', error='studio khởi động lại giữa chừng', finished_at=? "
                      "WHERE status='running'", (now_iso(),))
        for r in db.rows("SELECT id FROM segment_titles WHERE status='queued' ORDER BY id"):
            self.queue.append(r["id"])
        self.thread.start()
        log.info("title worker started (%d queued)", len(self.queue))

    def enqueue(self, segment_id: int) -> dict:
        seg = db.row("SELECT id, kind, start_sec FROM segments WHERE id=?", (segment_id,))
        if not seg:
            return {"error": f"không có đoạn #{segment_id}"}
        if seg["kind"] != "highlight":
            return {"error": "chỉ viết title cho đoạn highlight"}
        if seg["start_sec"] is None:
            return {"error": "đoạn này không có timestamp nên không viết title tự động được"}
        busy = db.row("SELECT id, status FROM segment_titles WHERE segment_id=? AND status IN ('queued','running')",
                      (segment_id,))
        if busy:
            return {"run_id": busy["id"], "message": "đoạn này đang " + ("viết" if busy["status"] == "running" else "chờ")}
        with db.tx() as c:
            c.execute("INSERT INTO segment_titles(segment_id, skill, model, effort, status, progress_msg, created_at) "
                      "VALUES(?,?,?,?,?,?,?)",
                      (segment_id, db.get_setting("title_skill"), db.get_setting("claude_model_title"),
                       db.get_setting("claude_effort_title"), "queued", "đang chờ tới lượt", now_iso()))
            run_id = c.execute("SELECT last_insert_rowid()").fetchone()[0]
        with self.cv:
            self.queue.append(run_id)
            self.cv.notify()
        ahead = len(self.queue) - 1 + (1 if self.current else 0)
        return {"run_id": run_id, "message": "đã xếp vào hàng đợi viết title" + (f", còn {ahead} đoạn trước" if ahead else "")}

    def enqueue_chat(self, segment_id: int, message: str) -> dict:
        """Queue a chat turn that adjusts the latest finished title result of the segment."""
        busy = db.row("SELECT id, status FROM segment_titles WHERE segment_id=? AND status IN ('queued','running')",
                      (segment_id,))
        if busy:
            return {"error": "Claude đang " + ("viết" if busy["status"] == "running" else "chờ tới lượt") +
                             " cho đoạn này, đợi xong rồi nhắn tiếp"}
        parent = db.row("SELECT * FROM segment_titles WHERE segment_id=? AND status='done' ORDER BY id DESC LIMIT 1",
                        (segment_id,))
        if not parent:
            return {"error": "đoạn này chưa có title, bấm Viết Title trước"}
        with db.tx() as c:
            c.execute("INSERT INTO segment_titles(segment_id, skill, model, effort, status, progress_msg, created_at, "
                      "parent_id, user_message) VALUES(?,?,?,?,?,?,?,?,?)",
                      (segment_id, parent["skill"], parent["model"], parent["effort"], "queued", "đang chờ tới lượt",
                       now_iso(), parent["id"], message.strip()))
            run_id = c.execute("SELECT last_insert_rowid()").fetchone()[0]
        with self.cv:
            self.queue.append(run_id)
            self.cv.notify()
        ahead = len(self.queue) - 1 + (1 if self.current else 0)
        return {"run_id": run_id, "message": "đã gửi cho Claude" + (f", còn {ahead} lượt trước" if ahead else "")}

    def cancel(self, segment_id: int) -> dict:
        run = db.row("SELECT id, status FROM segment_titles WHERE segment_id=? AND status IN ('queued','running') "
                      "ORDER BY id DESC LIMIT 1", (segment_id,))
        if not run:
            return {"message": "không có lượt nào đang chạy"}
        if run["status"] == "queued":
            with self.cv:
                if run["id"] in self.queue:
                    self.queue.remove(run["id"])
            with db.tx() as c:
                c.execute("UPDATE segment_titles SET status='failed', error='đã hủy', finished_at=? WHERE id=?",
                          (now_iso(), run["id"]))
            return {"message": "đã bỏ khỏi hàng đợi"}
        self.cancelled.add(run["id"])
        return {"message": "đang dừng lượt viết title"}

    def status(self) -> dict:
        return {"current": self.current, "queue": list(self.queue)}

    def _loop(self) -> None:
        while True:
            with self.cv:
                while not self.queue:
                    self.cv.wait(timeout=30)
                run_id = self.queue.popleft()
            self.current = run_id
            try:
                run_title(run_id, stop_flag=lambda rid=run_id: rid in self.cancelled)
            except Exception as e:  # noqa: BLE001
                log.exception("title run %s failed", run_id)
                msg = "đã hủy" if run_id in self.cancelled else str(e)[:1000]
                with db.tx() as c:
                    c.execute("UPDATE segment_titles SET status='failed', error=?, finished_at=? WHERE id=?",
                              (msg, now_iso(), run_id))
                    c.execute("UPDATE jobs SET status='failed', error=?, finished_at=? WHERE stage='title' AND status='running'",
                              (msg, now_iso()))
            finally:
                self.current = None
                self.cancelled.discard(run_id)


def normalize(data) -> dict:
    """Make the run's JSON safe to render: title lists are lists of strings, text fields are strings."""
    if not isinstance(data, dict):
        return {}
    out = dict(data)
    for key in ("titles_format1", "titles_format2", "warnings"):
        v = out.get(key)
        if isinstance(v, str):
            v = [x.strip() for x in v.split("\n") if x.strip()]
        elif isinstance(v, list):
            v = [(x.get("title") if isinstance(x, dict) else str(x)).strip() for x in v
                 if (x.get("title") if isinstance(x, dict) else x)]
        else:
            v = []
        out[key] = v
    for key in ("description", "timestamps", "tags", "thumbnail", "image_prompt", "recommended_title", "core_keyword"):
        v = out.get(key)
        if isinstance(v, list):
            out[key] = ", ".join(str(x) for x in v) if key == "tags" else "\n".join(str(x) for x in v)
        elif isinstance(v, dict):
            out[key] = "\n".join(f"{k}: {x}" for k, x in v.items())
        elif v is not None:
            out[key] = str(v)
    return out


def _root_id(run: dict, by_id: dict[int, dict]) -> int:
    cur = run
    while cur.get("parent_id") in by_id:
        cur = by_id[cur["parent_id"]]
    return cur["id"]


def runs_for_episode(episode_id: str) -> dict[int, dict]:
    """Per segment: latest run (any status), latest finished run with its data, the chat turns that follow the
    current "Viết Title" run (`thread`), and the full skill answer of the run the shown result descends from."""
    out: dict[int, dict] = {}
    rows = db.rows("""SELECT t.* FROM segment_titles t JOIN segments s ON s.id=t.segment_id
                      WHERE s.episode_id=? ORDER BY t.id""", (episode_id,))
    by_id = {r["id"]: r for r in rows}
    for r in rows:
        d = out.setdefault(r["segment_id"], {"latest": None, "done": None, "thread": [], "full_md": None})
        d["latest"] = r
        if r["status"] == "done":
            d["done"] = r
    for seg_id, d in out.items():
        chain = _root_id(d["latest"], by_id)
        d["thread"] = [r for r in rows if r["segment_id"] == seg_id and r.get("parent_id")
                       and _root_id(r, by_id) == chain]
        if d["done"]:
            d["full_md"] = by_id[_root_id(d["done"], by_id)].get("output_md")
            try:
                d["done"]["data"] = normalize(json.loads(d["done"]["output_json"])) if d["done"].get("output_json") else {}
            except ValueError:
                d["done"]["data"] = {}
    return out
