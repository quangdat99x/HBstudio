"""Stage: pick highlights with the chon-noi-dung-jre-v2 skill running headless, validate, ingest, keep the analysis."""
from __future__ import annotations

import json
import logging
import re
import shutil
from glob import glob
from pathlib import Path

from .. import config, db, ingest
from ..analysis import import_analysis_json, import_markdown
from ..util import read_json, transcript_to_txt, now_iso
from . import claude_runner
from .validator import validate_cutlist

log = logging.getLogger("studio.select")
SKILL_NAME = "chon-noi-dung-jre-v2"


def sync_skill(name: str = SKILL_NAME) -> Path | None:
    """Copy the desktop app's SKILL.md into .claude/skills so the headless run uses the same version."""
    candidates = sorted(glob(config.DESKTOP_SKILLS_GLOB + f"\\{name}\\SKILL.md"), key=lambda p: Path(p).stat().st_mtime)
    if not candidates:
        return None
    src = Path(candidates[-1])
    dst = config.SKILLS_DIR / name / "SKILL.md"
    dst.parent.mkdir(parents=True, exist_ok=True)
    if not dst.exists() or dst.read_bytes() != src.read_bytes():
        shutil.copy2(src, dst)
        log.info("synced skill %s from %s", name, src)
    return dst


def build_prompt(ep: dict, transcript_txt: Path, cutlist_path: Path, analysis_path: Path, max_segments: int,
                 retry_errors: list[str] | None = None) -> str:
    guest = ep.get("guest") or "(chưa rõ, tự xác định từ transcript)"
    lines = [
        f"/{SKILL_NAME} Chạy wf chọn nội dung v2 ở CHẾ ĐỘ TỰ ĐỘNG (headless) cho tập {ep['id']}.",
        "",
        "THÔNG TIN TẬP (dùng thẳng, không hỏi lại):",
        f"- episode_id: {ep['id']}",
        f"- Khách mời: {guest}",
        f"- source_video: {ep.get('source_video') or ''}",
        f"- Transcript có timestamp [hh:mm:ss] ở file: {transcript_txt}",
        f"  (đọc bằng công cụ Read; file dài, đọc từng phần cho tới hết, KHÔNG bỏ sót phần cuối)",
        f"- Thời lượng video: {int((ep.get('duration_sec') or 0) // 60)} phút",
        "",
        "LUẬT CHẾ ĐỘ TỰ ĐỘNG:",
        "1. Không hỏi người dùng bất cứ điều gì. Mọi chỗ skill bảo 'dừng cho người dùng đọc/chỉnh sửa' hoặc 'hỏi người dùng' thì tự quyết theo mặc định của skill và đi tiếp.",
        "2. Guest Card: research bằng WebSearch/WebFetch nếu có, in Guest Card ra như bình thường.",
        f"3. Chọn TẤT CẢ các khối đạt chuẩn của skill, tối đa {max_segments} đoạn highlight, mỗi đoạn kèm 1–2 hook cold open. Xuất kết quả từng đoạn theo FORMAT ĐẦU RA KHÓA CỨNG (Mục VI) ngay trong câu trả lời.",
        f"4. Sau đó XUẤT CUTLIST theo Mục Vb (layout flat_hooks, hook đứng ngay trước đoạn cha, rank liên tục) và ghi đúng MỘT file: {cutlist_path}",
        f"5. Ghi thêm MỘT file phân tích {analysis_path} dạng JSON: "
        "{\"episode_id\": ..., \"guest_card_md\": \"<toàn văn Guest Card>\", \"segments\": [ {\"content_rank\", \"title\", \"start\", \"end\", "
        "\"tom_tat\": \"<toàn văn phần Tóm tắt tiếng Việt>\", \"ly_do_dat\": \"<Tại sao đoạn này đắt>\", \"hook_cold_open\": \"<phần hook, nguyên văn>\", "
        "\"keyword\": \"<phần Keyword hạt nhân + vì sao + vệ tinh>\", \"fit\": \"<Fit với khách mời>\", \"raw_md\": \"<nguyên văn toàn bộ khối Mục VI của đoạn>\"} ] }. "
        "Mỗi đoạn highlight trong cutlist phải có đúng một phần tử tương ứng (khớp start/end).",
        "6. Timestamp phải tra trực tiếp từ transcript, tuyệt đối không ước lượng. Hook phải nằm trong biên đoạn cha, dài 5–25 giây.",
        "7. Kết thúc bằng đúng một dòng: DONE cutlist=<đường dẫn> analysis=<đường dẫn>",
    ]
    if retry_errors:
        lines += ["", "LẦN CHẠY TRƯỚC BỊ LOẠI VÌ CÁC LỖI SAU, PHẢI SỬA HẾT:", *[f"- {e}" for e in retry_errors]]
    return "\n".join(lines)


def select_episode(episode_id: str, progress_cb=None, force: bool = False) -> dict:
    conn = db.get_conn()
    ep = dict(conn.execute("SELECT * FROM episodes WHERE id=?", (episode_id,)).fetchone())
    media_root = Path(db.get_setting("media_root"))
    cutlist_path = media_root / f"cutlist_{episode_id}.json"
    if cutlist_path.exists() and not force:
        stats = ingest.ingest_cutlist(cutlist_path, media_root, force=True)
        return {"skipped": True, "cutlist": str(cutlist_path), "ingest": stats}

    status = claude_runner.cli_status()
    if not status.get("installed"):
        raise RuntimeError("Claude Code CLI chưa cài hoặc không chạy được. Cài: npm i -g @anthropic-ai/claude-code, rồi đăng nhập.")
    if not sync_skill():
        raise RuntimeError(f"không tìm thấy SKILL.md của {SKILL_NAME} trong thư mục plugin của app desktop")

    work = config.WORK_DIR / episode_id
    work.mkdir(parents=True, exist_ok=True)
    lines = ingest.get_transcript_lines(episode_id)
    if not lines:
        ingest.load_episode_transcript(episode_id, force=True)
        lines = ingest.get_transcript_lines(episode_id)
    if not lines:
        raise RuntimeError("chưa có transcript trong database")
    transcript_txt = work / "transcript.txt"
    transcript_txt.write_text(transcript_to_txt(ep.get("source_video") or episode_id, "large-v3", lines), encoding="utf-8")
    analysis_path = work / f"analysis_{episode_id}.json"
    for stale in (analysis_path, cutlist_path if force else None):
        if stale and stale.exists():
            stale.rename(stale.with_name(stale.name + f".old_{int(Path(stale).stat().st_mtime)}"))

    max_segments = db.setting_int("max_segments") or 12
    retries = db.setting_int("select_retry")
    errors: list[str] = []
    last_run = None
    for attempt in range(retries + 1):
        prompt = build_prompt(ep, transcript_txt, cutlist_path, analysis_path, max_segments, errors if attempt else None)
        (work / f"prompt_{attempt}.txt").write_text(prompt, encoding="utf-8")
        if progress_cb:
            progress_cb(5 + attempt * 40, f"Claude đang chọn nội dung (lần {attempt + 1})…")
        res = claude_runner.run(prompt, cwd=config.BASE_DIR, log_path=work / f"claude_run_{attempt}.jsonl",
                                on_text=lambda t: progress_cb and progress_cb(None, t[-160:].replace("\n", " ")))
        last_run = res
        (work / f"selection_log_{attempt}.md").write_text(res.get("text") or "", encoding="utf-8")
        with db.tx(conn) as c:
            c.execute("UPDATE episodes SET selection_log_md=?, updated_at=? WHERE id=?",
                      (res.get("text") or "", now_iso(), episode_id))
        if not res.get("ok"):
            errors = [f"Claude run lỗi: {res.get('error')}"]
            log.warning("claude run failed for %s: %s", episode_id, res.get("error"))
            continue
        if not cutlist_path.exists():
            errors = [f"không thấy file cutlist tại {cutlist_path}"]
            continue
        try:
            data = read_json(cutlist_path)
        except Exception as e:  # noqa: BLE001
            errors = [f"cutlist không phải JSON hợp lệ: {e}"]
            continue
        v = validate_cutlist(data, ep.get("duration_sec"), expect_episode_id=episode_id)
        if v["errors"]:
            errors = v["errors"]
            log.warning("cutlist invalid for %s: %s", episode_id, errors)
            bad = cutlist_path.with_name(cutlist_path.name + f".invalid_{attempt}")
            cutlist_path.replace(bad)
            continue
        errors = []
        break

    if errors:
        raise RuntimeError("chọn nội dung thất bại: " + "; ".join(errors)[:1500])

    stats = ingest.ingest_cutlist(cutlist_path, media_root, force=True)
    analysis_stats = None
    if analysis_path.exists():
        try:
            adata = read_json(analysis_path)
            analysis_stats = import_analysis_json(episode_id, adata, source="headless")
            if isinstance(adata, dict) and adata.get("guest_card_md"):
                with db.tx(conn) as c:
                    c.execute("UPDATE episodes SET guest_card_md=? WHERE id=?", (adata["guest_card_md"], episode_id))
        except Exception as e:  # noqa: BLE001
            log.warning("analysis json unusable for %s: %s", episode_id, e)
    if not analysis_stats or analysis_stats.get("attached", 0) == 0:
        analysis_stats = import_markdown(episode_id, last_run.get("text") or "", source="headless-log")
    _capture_guest_card(episode_id, last_run.get("text") or "")
    return {"cutlist": str(cutlist_path), "ingest": stats, "analysis": analysis_stats,
            "usage": last_run.get("usage"), "cost_usd": last_run.get("cost_usd"), "duration_sec": last_run.get("duration_sec")}


_RE_GUEST_CARD = re.compile(r"(GUEST CARD.*?)(?=\n\s*\[?1\]?\.\s*\*\*|\n#{1,3}\s|\Z)", re.S | re.I)


def _capture_guest_card(episode_id: str, text: str) -> None:
    conn = db.get_conn()
    row = conn.execute("SELECT guest_card_md FROM episodes WHERE id=?", (episode_id,)).fetchone()
    if row and row["guest_card_md"]:
        return
    m = _RE_GUEST_CARD.search(text or "")
    if m and len(m.group(1)) > 80:
        with db.tx(conn) as c:
            c.execute("UPDATE episodes SET guest_card_md=? WHERE id=?", (m.group(1).strip()[:6000], episode_id))
