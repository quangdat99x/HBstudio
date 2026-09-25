"""Stage: pick highlights with the chon-noi-dung-jre-v2 skill running headless, validate, ingest, keep the analysis.

Cost model of one run (measured on JRE-2368/2551/2558 with opus xhigh): every tool call is a new request that
re-reads the whole conversation, and every character the model writes is slow output. So the run is kept to a few
requests: the skill text and the full transcript go into the prompt (no chunked Read calls), the CLI runs isolated
(no MCP servers, connectors, skill list or auto-memory riding along in every request), the analysis is printed once
in the answer (Studio parses it, the run writes no second copy), and Studio does the validation, sending any errors
back into the same session with --resume instead of starting a new run.
"""
from __future__ import annotations

import json
import logging
import math
import re
import shutil
import time
from glob import glob
from pathlib import Path

from .. import config, db, ingest
from ..analysis import extract_guest_card, import_markdown, import_tags
from ..util import now_iso, read_json, transcript_to_txt
from . import claude_runner
from .validator import validate_cutlist

log = logging.getLogger("studio.select")
SKILL_NAME = "chon-noi-dung-jre-v2"
STOPPED = "dừng theo yêu cầu"
# Write/Edit for the two output files, Read so Edit also works in a resumed session, web tools for the Guest Card.
# No Bash/Grep/Glob: the transcript is in the prompt and Studio validates the files itself.
SELECT_TOOLS = "Read,Write,Edit,WebSearch,WebFetch"


def sync_skill(name: str = SKILL_NAME) -> Path | None:
    """Copy the desktop app's SKILL.md into .claude/skills so the headless run uses the same version."""
    candidates = []
    for pattern in config.DESKTOP_SKILLS_GLOBS:
        candidates += glob(pattern + f"\\{name}\\SKILL.md")
    dst = config.SKILLS_DIR / name / "SKILL.md"
    if not candidates:
        return dst if dst.exists() else None      # keep using the copy we already have
    src = Path(sorted(candidates, key=lambda p: Path(p).stat().st_mtime)[-1])
    dst.parent.mkdir(parents=True, exist_ok=True)
    if not dst.exists() or dst.read_bytes() != src.read_bytes():
        shutil.copy2(src, dst)
        log.info("synced skill %s from %s", name, src)
    return dst


def skill_body(path: Path) -> str:
    """SKILL.md without its YAML front matter (name/description are only for skill discovery)."""
    text = path.read_text(encoding="utf-8")
    m = re.match(r"^---\s*\n.*?\n---\s*\n", text, re.S)
    return (text[m.end():] if m else text).strip()


class SelectProgress:
    """Turns the stream events of a selection run into job progress and a message that keeps moving.

    The transcript is already in the prompt, so a run goes: guest lookup on the web (5-12%), reading and scoring
    while it thinks (12-45%), then the output (45-95%): the analysis printed block by block (counted from the
    `N. **Title**` headings as they stream), the cutlist and the small tags file, in whichever order Claude writes
    them. A resumed fix-up starts at 90%. The message always shows elapsed minutes, tool calls and thinking tokens.
    """

    _RE_HEAD = re.compile(r"\n\s*\[?(\d{1,2})\]?\.\s*\*\*")
    _SHARE = {"analysis": 0.55, "cutlist": 0.35, "tags": 0.10}      # rough share of the output each part takes

    def __init__(self, cb, max_segments: int, attempt: int = 0, fixing: bool = False):
        self.cb = cb
        self.expected = max(1, max_segments)              # highlights to print; exact once the cutlist is written
        self.exact = False
        self.attempt = attempt
        self.fixing = fixing
        self.started = time.time()
        self.tools = 0
        self.thinking = 0
        self.block = 0
        self.written = {"cutlist": False, "tags": False}
        self.tail = "\n"                                  # streamed answer text, enough to spot the next heading
        self.pct = 90.0 if fixing else 5.0
        self.phase = "sửa file theo lỗi Studio báo" if fixing else "khởi động, tra cứu khách mời"
        self.last_tool = ""
        self._last = 0.0

    def _output_progress(self) -> None:
        if self.fixing:
            return
        blocks = min(1.0, (self.block - 1) / self.expected) if self.block else 0.0
        share = (self._SHARE["analysis"] * blocks + self._SHARE["cutlist"] * self.written["cutlist"]
                 + self._SHARE["tags"] * self.written["tags"])
        self.pct = max(self.pct, 45 + 50 * share)

    def _count_highlights(self, content) -> None:
        try:
            segs = json.loads(content or "").get("segments") or []
            n = sum(1 for s in segs if isinstance(s, dict) and s.get("kind") == "highlight")
        except (ValueError, AttributeError):
            return
        if n:
            self.expected, self.exact = n, True

    def _emit(self, msg: str, force: bool = False) -> None:
        now = time.time()
        if not self.cb or (not force and now - self._last < 8):
            return
        self._last = now
        mins = int((now - self.started) // 60)
        think = f" · {self.thinking / 1000:.0f}k token suy nghĩ" if self.thinking >= 1000 else ""
        retry = f"lần {self.attempt + 1} · " if self.attempt else ""
        self.cb(round(self.pct, 1), f"[{retry}{mins} phút · {self.tools} lượt công cụ{think}] {msg}")

    def message(self) -> str:
        return self.phase + (f" · vừa: {self.last_tool}" if self.last_tool else "")

    def __call__(self, kind: str, data) -> None:
        if kind == "thinking":
            self.thinking += int(data or 0)
            if not self.block and not self.fixing and not any(self.written.values()):
                self.pct = max(self.pct, 12 + 33 * (1 - math.exp(-self.thinking / 50000)))
                if self.thinking >= 2000 and not self.phase.startswith("đọc"):
                    self.phase, self.last_tool = "đọc transcript, chấm điểm và chọn đoạn", ""
            self._emit(self.message())
            return
        if kind == "text_delta":
            self.tail = (self.tail + str(data or ""))[-400:]
            nums = [int(n) for n in self._RE_HEAD.findall(self.tail)]
            if not self.fixing and nums and max(nums) > self.block:
                self.block = max(nums)
                self._output_progress()
                of = f"/{self.expected}" if self.exact else ""
                self.phase, self.last_tool = f"viết phân tích đoạn {self.block}{of}", ""
                self._emit(self.message(), force=True)
            return
        if kind in ("writing", "writing_tool"):
            if not data:
                return
            what = "soạn nội dung file" if kind == "writing_tool" else "viết"
            chars = f"{int(data):,}".replace(",", ".")
            self._emit(f"{self.phase} · đang {what} (~{chars} ký tự)")
            return
        if kind == "text":
            note = str(data).strip()
            if len(note) < 400:                           # a status note; long texts are the analysis itself
                self._emit(note.replace("\n", " ")[-150:], force=True)
            return
        name, inp = data
        self.tools += 1
        fp = str(inp.get("file_path") or inp.get("path") or "")
        if name in ("WebSearch", "WebFetch"):
            if not self.block and not self.fixing:
                self.pct = max(self.pct, min(12.0, self.pct + 2))
            self.last_tool = "tra web " + str(inp.get("query") or inp.get("url") or "")[:70]
        elif name in ("Write", "Edit") and "cutlist_" in fp:
            if name == "Write":
                self._count_highlights(inp.get("content"))
            self.written["cutlist"] = True
            self._output_progress()
            if self.fixing:
                self.pct = max(self.pct, 94)
            self.phase, self.last_tool = ("sửa cutlist" if self.fixing or name == "Edit" else "ghi cutlist"), ""
        elif name in ("Write", "Edit") and "tags_" in fp:
            self.written["tags"] = True
            self._output_progress()
            if self.fixing:
                self.pct = max(self.pct, 96)
            self.phase, self.last_tool = "ghi nhãn chủ đề và nhân vật", ""
        elif name == "Read":
            self.last_tool = f"đọc {Path(fp).name}" if fp else "đọc tài liệu"
        else:
            self.last_tool = name
        self._emit(self.message(), force=True)


def _theme_lines() -> list[str]:
    from .. import tagging
    tagging.ensure_default_themes()
    return [f"  - {r['slug']}: {r['name_vi'] or ''}" for r in db.rows("SELECT slug, name_vi FROM themes ORDER BY slug")]


def build_prompt(ep: dict, skill_text: str, transcript: str, cutlist_path: Path, tags_path: Path,
                 max_segments: int) -> str:
    """Skill text, then the whole transcript, then the request (long documents first, instructions last)."""
    guest = ep.get("guest") or "(chưa rõ, tự xác định từ transcript)"
    lines = [
        f"Dưới đây là toàn văn skill `{SKILL_NAME}` (bản đồng bộ từ app desktop). Làm đúng theo skill này.",
        "",
        f'<skill name="{SKILL_NAME}">',
        skill_text,
        "</skill>",
        "",
        f'<transcript episode="{ep["id"]}" file="{ep.get("source_video") or ""}">',
        transcript.rstrip("\n"),
        "</transcript>",
        "",
        f"YÊU CẦU: chạy wf chọn nội dung v2 ở CHẾ ĐỘ TỰ ĐỘNG (headless) cho tập {ep['id']}.",
        "",
        "THÔNG TIN TẬP (dùng thẳng, không hỏi lại):",
        f"- episode_id: {ep['id']}",
        f"- Khách mời: {guest}",
        f"- source_video: {ep.get('source_video') or ''}",
        f"- Thời lượng video: {int((ep.get('duration_sec') or 0) // 60)} phút",
        "- Transcript có timestamp [hh:mm:ss]: TOÀN VĂN nằm trong thẻ <transcript> ở trên, đủ từ đầu tới cuối. "
        "Đọc hết và tra timestamp trực tiếp trong đó; không dùng công cụ để đọc lại transcript hay mở file nào khác.",
        "",
        "LUẬT CHẾ ĐỘ TỰ ĐỘNG:",
        "1. Không hỏi người dùng bất cứ điều gì. Mọi chỗ skill bảo 'dừng cho người dùng đọc/chỉnh sửa' hoặc 'hỏi người dùng' thì tự quyết theo mặc định của skill và đi tiếp.",
        "2. Guest Card: tra web bằng WebSearch, gọi các lượt tra SONG SONG trong cùng một lượt (tối đa 3), WebFetch chỉ khi thật cần; in Guest Card đúng format Mục II.5.",
        f"3. Chọn TẤT CẢ các khối đạt chuẩn của skill, tối đa {max_segments} đoạn highlight, mỗi đoạn kèm 1–2 hook cold open. "
        "In từng đoạn MỘT LẦN theo FORMAT ĐẦU RA KHÓA CỨNG (Mục VI) ngay trong câu trả lời, dòng tiêu đề đúng dạng "
        "`N. **Tiêu đề**` với N = content_rank. Studio lưu nguyên văn phần này làm bản phân tích của từng đoạn, "
        "nên KHÔNG chép lại nó vào file nào.",
        f"4. Sau đó XUẤT CUTLIST theo Mục Vb (layout flat_hooks, hook đứng ngay trước đoạn cha, rank liên tục) vào đúng MỘT file: {cutlist_path}",
        f"5. Trong CÙNG lượt đó (hai lệnh Write song song) ghi thêm file nhãn nhỏ {tags_path} dạng JSON: "
        f"{{\"episode_id\": \"{ep['id']}\", \"segments\": [{{\"content_rank\": 1, \"start\": \"hh:mm:ss\", \"end\": \"hh:mm:ss\", "
        "\"themes\": [\"<slug>\", ...], \"entities\": [{\"name\": \"<tên riêng>\", \"type\": \"person|place|org|work|event|other\"}]}]}. "
        "Mỗi đoạn highlight của cutlist có đúng một phần tử (khớp content_rank, start, end); chỉ các khóa trên, "
        "không chép tóm tắt hay phân tích vào file này.",
        "6. `themes`: 1–3 slug chọn trong danh sách dưới đây, slug đầu tiên là chủ đề chính của đoạn; không bịa slug mới. "
        "`entities`: người, địa danh, tổ chức, tác phẩm, sự kiện có tên riêng được nhắc trong đoạn (tối đa 15).",
        *_theme_lines(),
        "7. Timestamp phải tra trực tiếp từ transcript, tuyệt đối không ước lượng. Hook phải nằm trong biên đoạn cha, dài 5–25 giây.",
        f"8. Cutlist được Studio chấp nhận khi: episode.id đúng {ep['id']}; mọi entry có `kind` (hook|highlight) và `title`; "
        "`rank` là số nguyên liên tục 1..N; start < end và không vượt thời lượng video; mỗi hook có `parent_rank` trỏ tới "
        "highlight đứng ngay sau và nằm trong biên của nó. Tự rà 8 mục kiểm tra của Mục Vb trước khi ghi; không cần chạy "
        "lệnh kiểm tra: Studio kiểm tra hai file ngay khi bạn kết thúc, có lỗi sẽ gửi lại trong chính phiên này để bạn sửa.",
        f"9. Kết thúc bằng đúng một dòng: DONE cutlist={cutlist_path} tags={tags_path}",
    ]
    return "\n".join(lines)


def build_fix_prompt(problems: list[str], crashed: str | None, cutlist_path: Path, tags_path: Path) -> str:
    """Follow-up turn in the same session: the model still has the transcript and its own answer in context."""
    if crashed:
        lines = [f"Lượt chạy vừa rồi bị ngắt giữa chừng ({crashed[:300]}). Làm tiếp phần còn thiếu theo đúng YÊU CẦU "
                 "ban đầu: in nốt phân tích các đoạn nếu chưa in xong, ghi cutlist và file nhãn nếu chưa ghi. "
                 "Không lặp lại phần đã xong."]
    else:
        lines = ["Studio đã kiểm tra kết quả và thấy các lỗi sau, phải sửa hết:", *[f"- {p}" for p in problems], "",
                 f"Sửa thẳng vào {cutlist_path} (và {tags_path} nếu cần) bằng Edit hoặc Write. Không in lại phân tích, "
                 "không đổi những phần đã đúng, không đọc lại file sau khi ghi (Studio tự kiểm tra lại). Nếu phải dời "
                 "Start/End của một đoạn thì in lại riêng khối Mục VI của đoạn đó với timestamp mới."]
    return "\n".join(lines + ["", f"Kết thúc bằng đúng một dòng: DONE cutlist={cutlist_path} tags={tags_path}"])


def _check_outputs(ep: dict, cutlist_path: Path, tags_path: Path) -> tuple[list[str], list[str]]:
    """(errors that block the stage, problems worth one fix-up turn but not worth failing for)."""
    errors: list[str] = []
    if not cutlist_path.exists():
        errors.append(f"không thấy file cutlist tại {cutlist_path}")
    else:
        try:
            data = read_json(cutlist_path)
        except Exception as e:  # noqa: BLE001
            errors.append(f"cutlist không phải JSON hợp lệ: {e}")
        else:
            errors += validate_cutlist(data, ep.get("duration_sec"), expect_episode_id=ep["id"])["errors"]
    minor: list[str] = []
    if not tags_path.exists():
        minor.append(f"chưa ghi file nhãn {tags_path}")
    else:
        try:
            read_json(tags_path)
        except Exception as e:  # noqa: BLE001
            minor.append(f"file nhãn {tags_path.name} không phải JSON hợp lệ: {e}")
    return errors, minor


def select_episode(episode_id: str, progress_cb=None, force: bool = False, stop_flag=None) -> dict:
    conn = db.get_conn()
    ep = dict(conn.execute("SELECT * FROM episodes WHERE id=?", (episode_id,)).fetchone())
    media_root = Path(db.get_setting("media_root"))
    cutlist_path = media_root / f"cutlist_{episode_id}.json"
    if cutlist_path.exists() and not force:
        try:
            layout = read_json(cutlist_path).get("cutlist_layout")
        except Exception:  # noqa: BLE001
            layout = None
        if layout == "flat_hooks":                         # made by the current skill (V2.7+): reuse it
            stats = ingest.ingest_cutlist(cutlist_path, media_root, force=True)
            return {"skipped": True, "cutlist": str(cutlist_path), "ingest": stats}
        old = cutlist_path.with_name(cutlist_path.name + f".old_{int(cutlist_path.stat().st_mtime)}")
        cutlist_path.rename(old)                           # old skill format: select again with the current skill
        log.info("old-format cutlist for %s moved to %s, selecting again", episode_id, old.name)

    status = claude_runner.cli_status()
    if not status.get("installed"):
        raise RuntimeError("Claude Code CLI chưa cài hoặc không chạy được (xem README, mục Claude headless).")
    skill_path = sync_skill()
    if not skill_path:
        raise RuntimeError(f"không tìm thấy SKILL.md của {SKILL_NAME} trong thư mục plugin của app desktop")
    skill_text = skill_body(skill_path)

    work = config.WORK_DIR / episode_id
    work.mkdir(parents=True, exist_ok=True)
    lines = ingest.get_transcript_lines(episode_id)
    if not lines:
        ingest.load_episode_transcript(episode_id, force=True)
        lines = ingest.get_transcript_lines(episode_id)
    if not lines:
        raise RuntimeError("chưa có transcript trong database")
    transcript = transcript_to_txt(ep.get("source_video") or episode_id, "large-v3", lines)
    (work / "transcript.txt").write_text(transcript, encoding="utf-8")      # same text as in the prompt, for reference
    tags_path = work / f"tags_{episode_id}.json"
    for stale in (tags_path, work / f"analysis_{episode_id}.json", cutlist_path if force else None):
        if stale and stale.exists():
            stale.rename(stale.with_name(stale.name + f".old_{int(Path(stale).stat().st_mtime)}"))

    max_segments = db.setting_int("max_segments") or 12
    retries = db.setting_int("select_retry")
    model = db.get_setting("claude_model_select") or None
    effort = db.get_setting("claude_effort_select") or None
    all_runs: list[dict] = []      # every run of this stage, for the usage summary
    runs: list[dict] = []          # runs of the current session: the full run plus its resumed fix-ups
    session_id: str | None = None
    errors: list[str] = []
    minor: list[str] = []
    crashed: str | None = None
    for attempt in range(retries + 1):
        if session_id:
            prompt = build_fix_prompt(errors + minor, crashed, cutlist_path, tags_path)
        else:
            runs = []
            prompt = build_prompt(ep, skill_text, transcript, cutlist_path, tags_path, max_segments)
        (work / f"prompt_{attempt}.txt").write_text(prompt, encoding="utf-8")
        if progress_cb:
            what = "sửa lỗi trong cùng phiên" if session_id else "bắt đầu chọn nội dung"
            progress_cb(90 if session_id else 5, f"Claude ({model or 'mặc định'}, effort {effort or 'mặc định'}) {what}"
                                                 f"{f' (lần {attempt + 1})' if attempt else ''}…")
        tracker = SelectProgress(progress_cb, max_segments, attempt, fixing=bool(session_id))
        res = claude_runner.run(prompt, cwd=config.BASE_DIR, log_path=work / f"claude_run_{attempt}.jsonl",
                                model=model, effort=effort, on_event=tracker, stop_flag=stop_flag,
                                add_dirs=[str(media_root)], tools=SELECT_TOOLS, allowed_tools=SELECT_TOOLS,
                                isolated=True, resume=session_id)
        all_runs.append(res)
        (work / f"selection_log_{attempt}.md").write_text(res.get("text") or "", encoding="utf-8")
        if stop_flag and stop_flag():
            raise RuntimeError(STOPPED)
        if session_id and "No conversation found" in (res.get("error") or ""):
            log.warning("session %s of %s cannot be resumed, starting over", session_id, episode_id)
            session_id, crashed = None, None
            errors = [f"không nối lại được phiên Claude: {res.get('error')}"]
            continue
        runs.append(res)
        session_id = res.get("session_id") or session_id
        with db.tx(conn) as c:
            c.execute("UPDATE episodes SET selection_log_md=?, updated_at=? WHERE id=?",
                      ("\n\n".join(r.get("text") or "" for r in runs), now_iso(), episode_id))
        crashed = None if res.get("ok") else (res.get("error") or "không rõ lỗi")
        if crashed:
            log.warning("claude run failed for %s: %s", episode_id, crashed)
            if attempt < retries:                          # resume: the model sees what it already did
                errors, minor = [f"Claude run lỗi: {crashed}"], []
                continue
        errors, minor = _check_outputs(ep, cutlist_path, tags_path)   # last attempt: keep valid output it left
        if crashed and errors:
            errors.insert(0, f"Claude run lỗi: {crashed}")
        if errors:
            log.warning("cutlist invalid for %s: %s", episode_id, errors)
        if errors or (minor and attempt < retries):
            continue
        break

    if errors:
        if cutlist_path.exists():                          # never leave an invalid cutlist where the next run reuses it
            cutlist_path.replace(cutlist_path.with_name(cutlist_path.name + f".invalid_{int(time.time())}"))
        raise RuntimeError("chọn nội dung thất bại: " + "; ".join(errors)[:1500])

    stats = ingest.ingest_cutlist(cutlist_path, media_root, force=True)
    text = "\n\n".join(r.get("text") or "" for r in runs)
    analysis_stats = import_markdown(episode_id, text, source="headless")
    card = extract_guest_card(text)
    if card:
        with db.tx(conn) as c:
            c.execute("UPDATE episodes SET guest_card_md=? WHERE id=?", (card[:8000], episode_id))
    tag_stats = None
    if tags_path.exists():
        try:
            tag_stats = import_tags(episode_id, read_json(tags_path))
        except Exception as e:  # noqa: BLE001
            log.warning("tags json unusable for %s: %s", episode_id, e)
    total = claude_runner.merge_runs(all_runs)
    tagged = f", {tag_stats['tagged']} đoạn có nhãn" if tag_stats else ", chưa có nhãn chủ đề"
    return {"cutlist": str(cutlist_path), "ingest": stats, "analysis": analysis_stats, "tags": tag_stats,
            "usage": total.get("usage"), "models": total.get("models"), "cost_usd": total.get("cost_usd"),
            "duration_sec": total.get("duration_sec"),
            "summary": f"xong · {stats.get('highlights', 0)} đoạn, {stats.get('hooks', 0)} hook, "
                       f"{(analysis_stats or {}).get('attached', 0)} khối phân tích{tagged} · "
                       + claude_runner.describe_run(total)}
