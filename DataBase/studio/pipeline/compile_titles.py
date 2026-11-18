"""Viết title tổng hợp: the `viet-tittle-tong-hop` skill, run headless for one built compile job.

Mirrors how titles.py runs `viet-tittle` for a single highlight: the whole SKILL.md goes into the prompt (the run is
isolated, so the skill list is not loaded), followed by the data of the job (manifest + chapters.txt in out_dir, the
clip list with guests from the DB, the main show) and the automatic-mode rules. The skill writes
`youtube_title_<slug>.json` + `youtube_metadata_<slug>.md` next to the manifest; Studio reads the JSON back, stores it
in compile_jobs.title_json and takes `recommended_title` as the job's YouTube title.
"""
from __future__ import annotations

import json
import logging
import re
import time
from pathlib import Path

from .. import config, db, podcasts
from ..util import clean_stem, now_iso, read_json
from . import claude_runner, compile_video
from .select_ai import show_lines, skill_body, sync_skill
from .titles import TitleProgress, final_answer

log = logging.getLogger("studio.compile_titles")

SKILL_NAME = "viet-tittle-tong-hop"
TOOLSET = "Read,Write,Edit,Bash,WebSearch,WebFetch"                       # all the model sees
TOOLS = "Read,Write,Edit,WebSearch,WebFetch,Bash(python *),Bash(py *)"    # pre-approved
_PYTHON_RULE = ("Chỉ được phép chạy python bằng MỘT lệnh đứng riêng dạng `python -X utf8 <đường dẫn file .py>` hoặc "
                "`python -X utf8 -c \"...\"`: không `cd`, không nối lệnh bằng && hay ;, không dùng PowerShell.")
_RE_DONE = re.compile(r"DONE\s+title_json=(.+)$", re.M)


# ---------------------------------------------------------------- files of a built job
def manifest_path(folder: Path) -> Path | None:
    """compilation_<slug>.json written by the last build (the newest one when a rebuild changed the slug)."""
    found = sorted(folder.glob("compilation_*.json"), key=lambda p: p.stat().st_mtime)
    return found[-1] if found else None


def slug_of(folder: Path) -> str | None:
    m = manifest_path(folder)
    return m.stem[len("compilation_"):] if m else None


def paths(job: dict) -> dict | None:
    """out_dir, manifest, chapters.txt and the two files the skill writes; None when the video is not built."""
    if not job.get("out_dir"):
        return None
    folder = Path(job["out_dir"])
    if not folder.is_dir():
        return None
    slug = slug_of(folder)
    if not slug:
        return None
    return {"folder": folder, "slug": slug, "manifest": folder / f"compilation_{slug}.json",
            "chapters": folder / "chapters.txt", "json": folder / f"youtube_title_{slug}.json",
            "md": folder / f"youtube_metadata_{slug}.md"}


def ready(job: dict) -> str | None:
    """Why the button cannot run yet (None = ready)."""
    if job.get("status") != "done":
        return "chỉ viết title sau khi video đã dựng xong"
    p = paths(job)
    if not p:
        return "thư mục của tập không còn hoặc chưa có compilation_<slug>.json: bấm Dựng lại video"
    if not p["chapters"].is_file():
        return "chưa có chapters.txt: bấm Tạo lại mốc trước"
    return None


def load(job: dict) -> dict | None:
    """What the page shows: the JSON the skill wrote (file first, DB copy as fallback) plus where the files are."""
    p = paths(job)
    data, written = None, None
    if p and p["json"].is_file():
        try:
            data = read_json(p["json"])
            written = time.strftime("%Y-%m-%d %H:%M", time.localtime(p["json"].stat().st_mtime))
        except Exception as e:  # noqa: BLE001
            log.warning("compile %s title json unreadable: %s", job["id"], e)
    if data is None and job.get("title_json"):
        try:
            data = json.loads(job["title_json"])
        except ValueError:
            data = None
    if not isinstance(data, dict):
        return None
    for key in ("titles_format1", "titles_format2", "warnings", "satellite_keywords", "featured_episodes"):
        if not isinstance(data.get(key), list):
            data[key] = [data[key]] if data.get(key) else []
    data["titles_format1"] = [str(t) for t in data["titles_format1"]]
    data["titles_format2"] = [str(t) for t in data["titles_format2"]]
    for key in ("description", "timestamps", "tags", "thumbnail", "recommended_title"):
        if data.get(key) is not None and not isinstance(data[key], str):
            data[key] = json.dumps(data[key], ensure_ascii=False, indent=2) if not isinstance(data[key], list) \
                else "\n".join(str(x) for x in data[key])
    return {"data": data, "json_path": str(p["json"]) if p else None, "md_path": str(p["md"]) if p and p["md"].is_file() else None,
            "written": written, "full_md": _full_md(job["id"])}


def _full_md(job_id: int) -> str:
    p = compile_video.work_dir(job_id) / "title.md"
    return p.read_text(encoding="utf-8") if p.is_file() else ""


# ---------------------------------------------------------------- prompt
def _episode_name(episode_id: str, cache: dict) -> str:
    if episode_id not in cache:
        ep = db.row("SELECT title, source_video FROM episodes WHERE id=?", (episode_id,)) or {}
        cache[episode_id] = (ep.get("title") or clean_stem(Path(ep.get("source_video") or "").stem) or episode_id)
    return cache[episode_id]


def _clip_lines(job: dict) -> list[str]:
    cache: dict = {}
    out = []
    for it in compile_video.items(job["id"]):
        if not it["included"]:
            continue
        out.append(json.dumps({
            "order": it["ord"], "role": it.get("role") or ("cold_open" if it["kind"] == "seed" else "clip"),
            "episode_id": it["episode_id"], "show": it.get("src"), "episode": _episode_name(it["episode_id"], cache),
            "guest": it.get("guest") or None, "start": it["start_hms"], "end": it["end_hms"], "dur_sec": it["dur"],
            "title": it["title"], "summary_vi": it.get("summary_vi"), "why_vi": it.get("why_vi"),
        }, ensure_ascii=False))
    return out


def build_prompt(job: dict, seed: dict, skill_text: str, p: dict) -> str:
    prof = podcasts.for_episode(seed["episode_id"])
    final_sec = int(job.get("final_sec") or 0)
    minutes = f"{final_sec // 60} phút {final_sec % 60:02d} giây ({final_sec} giây, đo từ file mp4 đã dựng)" if final_sec else "chưa đo"
    support = sorted({it.get("src") or it.get("podcast_id") or "" for it in compile_video.items(job["id"])
                      if it["included"] and (it.get("podcast_id") or "") != prof["id"]})
    return "\n".join([
        f"Dưới đây là toàn văn skill `{SKILL_NAME}` (bản đồng bộ từ app desktop). Làm đúng theo skill này.", "",
        f'<skill name="{SKILL_NAME}">', skill_text, "</skill>", "",
        "YÊU CẦU: chạy wf VIẾT TITTLE TỔNG HỢP cho MỘT video tổng hợp của JRE Studio, ở CHẾ ĐỘ TỰ ĐỘNG (headless).",
        "",
        *show_lines(prof),
        f"ĐẦU VÀO (nguồn ⭐ JRE Studio → Video tổng hợp, compile job #{job['id']}):",
        f"- Thư mục của tập: {p['folder']}",
        f"- Manifest: {p['manifest']}",
        f"- chapters.txt (mốc đã đo từ video dựng xong, GIỮ NGUYÊN mốc, chỉ viết lại tên): {p['chapters']}",
        f"- Thời lượng video: {minutes}",
        f"- Show chính: {podcasts.label(prof)} · kênh {prof.get('channel') or '?'} · mã show `{prof['id']}`"
        + (f" · podcast bổ trợ trong tập: {', '.join(s for s in support if s)}" if any(support) else ""),
        f"- Theme Studio (topic_en): {job.get('topic_en') or ''}",
        f"- Big question (angle_vi): {job.get('angle_vi') or ''}",
        f"- Title nháp của bước arrange (chỉ tham khảo, không dùng thẳng): {job.get('title_en') or ''}",
        f"- Clip seed (cold open): {seed['episode_id']} · khách {seed.get('guest') or '?'} · «{seed.get('title') or ''}»"
        + (f" · hook_en trong kho (lời mở đầu clip, chỉ dùng làm Big Hook nếu thật sự đắt; không thì lấy câu đắt nhất "
           f"từ summary/why của clip seed): {seed['hook_en']}" if seed.get("hook_en") else "")
        + (f" · core_keyword của clip lẻ: {seed['core_keyword']}" if seed.get("core_keyword") else ""),
        *([f"- Ghi chú của người dùng cho tập này: {job['note']}"] if job.get("note") else []),
        "",
        "DANH SÁCH CLIP THEO THỨ TỰ TRONG VIDEO (tên khách đã chuẩn từ Studio, dùng nguyên văn; `show` là tên show của "
        "clip; `episode` là tên tập chuẩn cho mục FEATURED EPISODES), mỗi dòng một JSON:",
        "<clips>", *_clip_lines(job), "</clips>",
        "",
        "LUẬT CHẾ ĐỘ TỰ ĐỘNG:",
        "1. Không hỏi người dùng. Chỗ nào skill bảo báo hoặc hỏi người dùng thì ghi một dòng ⚠️ vào `warnings`, tự quyết "
        "theo mặc định của skill rồi làm tiếp. Mọi tên khách và tên tập đã có ở trên: không cần hỏi, không đoán khác.",
        "2. Đọc manifest và chapters.txt bằng Read (không đọc file .mp4, timeline.json chỉ khi cần). Xuất các bước đúng "
        "thứ tự Bước 4.1 của skill ngay trong câu trả lời: phân tích bằng tiếng Việt; title, description, chapters, tags "
        "bằng tiếng Anh.",
        "3. BƯỚC 3 (thumbnail) chỉ mô tả kế hoạch 3 ô bằng chữ: không trích khung, không tải ảnh, không tạo ảnh, không "
        "dựng mock, không dùng Canva.",
        f"4. Ghi hai file UTF-8 vào thư mục của tập đúng tên sau: {p['json']} (đúng cấu trúc JSON ở Bước 4.2 của skill, "
        "trong đó `recommended_title` là title bạn khuyên dùng nhất, `timestamps` là toàn văn khối chapters với mốc "
        f"nguyên văn từ chapters.txt, `tags_chars` là số ký tự thực tế) và {p['md']} (toàn bộ mục 4.1, sẵn copy-dán).",
        "5. Đếm ký tự của title, tên chapter và tags bằng python khi cần, không ước lượng. " + _PYTHON_RULE,
        f"6. Không đọc mã nguồn trong {config.BASE_DIR}. Kết thúc bằng đúng một dòng: DONE title_json={p['json']}",
    ])


# ---------------------------------------------------------------- run
def start(job_id: int) -> dict:
    job = compile_video.get_job(job_id)
    if not job:
        return {"error": "không có video này"}
    why = ready(job)
    if why:
        return {"error": why}
    if compile_video.busy(job_id):
        return {"error": "video này đang chạy"}
    res = compile_video._start(job_id, _run)
    if res.get("ok"):
        res["message"] = "đang viết title tổng hợp"
    return res


def _skill_text() -> str:
    path = sync_skill(SKILL_NAME)
    if not path:
        raise RuntimeError(f"không tìm thấy SKILL.md của {SKILL_NAME}")
    return skill_body(path)


def _run(job_id: int) -> None:
    runs: list = []
    work = compile_video.work_dir(job_id)
    try:
        job = compile_video.get_job(job_id)
        p = paths(job)
        if not p or not p["chapters"].is_file():
            raise RuntimeError(ready(job) or "thiếu file đầu vào")
        seed = db.row("SELECT s.*, e.guest FROM segments s JOIN episodes e ON e.id=s.episode_id WHERE s.id=?",
                      (job["seed_segment_id"],))
        compile_video._set(job_id, error=None, progress_msg="viết title tổng hợp: khởi động")
        prompt = build_prompt(job, seed, _skill_text(), p)
        (work / "title_prompt.md").write_text(prompt, encoding="utf-8")
        if p["json"].exists():                                     # a stale file must not pass for the new result
            p["json"].replace(p["json"].with_suffix(".prev.json"))
        progress = TitleProgress(lambda msg: compile_video._progress(job_id, f"viết title tổng hợp {msg}"))
        res = claude_runner.run(prompt, cwd=config.BASE_DIR, tools=TOOLSET, allowed_tools=TOOLS, isolated=True,
                                permission_mode="acceptEdits", max_turns=60, timeout=45 * 60,
                                model=db.get_setting("claude_model_compile_title") or None,
                                effort=db.get_setting("claude_effort_compile_title") or None,
                                add_dirs=[str(p["folder"])], log_path=work / "title.jsonl", on_event=progress,
                                stop_flag=lambda: job_id in compile_video._stop)
        runs.append(res)
        text = final_answer(res.get("texts") or []) or res.get("text") or ""
        (work / "title.md").write_text(text, encoding="utf-8")
        if not res.get("ok"):
            raise RuntimeError(res.get("error") or "Claude không chạy xong")
        data = _read_result(p["json"], res)
        if not isinstance(data, dict):
            raise RuntimeError(f"skill không ghi được {p['json'].name}")
        recommended = str(data.get("recommended_title") or "").strip()
        summary = claude_runner.describe_run(res)
        cols = {"title_json": json.dumps(data, ensure_ascii=False),
                "progress_msg": f"title tổng hợp xong · {summary}", "error": None}
        if recommended:
            cols["title_en"] = recommended[:200]
        compile_video._set(job_id, **cols)
        compile_video._add_usage(job_id, runs)
        prev = p["json"].with_suffix(".prev.json")
        if prev.exists():
            prev.unlink()
        log.info("compile %s title written: %s", job_id, recommended)
        compile_video._note(job_id, "done", "Viết title tổng hợp xong", recommended or p["json"].name)
    except Exception as e:  # noqa: BLE001
        log.exception("compile %s title failed", job_id)
        if runs:
            compile_video._add_usage(job_id, runs)
        compile_video._set(job_id, error=f"viết title lỗi: {e}"[:1000], progress_msg="viết title tổng hợp không xong")
        try:                                                      # put the previous result back
            p = paths(compile_video.get_job(job_id) or {})
            prev = p["json"].with_suffix(".prev.json") if p else None
            if prev and prev.exists() and not p["json"].exists():
                prev.replace(p["json"])
        except Exception:  # noqa: BLE001
            pass
        compile_video._note(job_id, "error", "Viết title tổng hợp lỗi", str(e))
    finally:
        compile_video._stop.discard(job_id)


def _read_result(out_json: Path, res: dict):
    """The JSON the skill wrote; the DONE line may name another path when the model picked its own file name."""
    candidates = [out_json]
    m = _RE_DONE.search(res.get("result") or res.get("text") or "")
    if m:
        alt = Path(m.group(1).strip().strip("`'\""))
        if alt != out_json:
            candidates.append(alt)
    for c in candidates:
        if c.is_file():
            try:
                data = read_json(c)
            except Exception as e:  # noqa: BLE001
                log.warning("title json %s unreadable: %s", c, e)
                continue
            if c != out_json:
                out_json.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            return data
    return None
