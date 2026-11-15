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
import shutil
import threading
import time
from collections import deque
from pathlib import Path

from .. import config, db, notify, podcasts
from ..util import clean_stem, now_iso, read_json, slice_transcript, write_json
from . import claude_runner, gemini_runner, hook_recut
from . import cut as cut_stage
from .select_ai import show_lines, skill_body, sync_skill

log = logging.getLogger("studio.titles")
TITLE_TOOLS = "Read,Write,Edit,WebSearch,WebFetch,Bash(python *),Bash(py *),Bash(curl *)"   # pre-approved
TITLE_TOOLSET = "Read,Write,Edit,Bash,WebSearch,WebFetch"                          # all the model sees
THUMB_TOOL = str(config.TOOLS_ROOT / "jre-thumb" / "frames.py")
# Thumbnail (Bước 4 of the skill) is two-phase. Title runs and chat turns only build a local plan + mock (no
# Canva at all). Canva is touched only by an approval turn, which the user starts with the "Duyệt thumbnail"
# button: that turn keeps the claude.ai connectors and pre-approves just the Canva tools needed to apply the plan.
APPROVE_MSG = "✅ Duyệt thumbnail: áp bản mock lên Canva, lưu và export"
CANVA_TOOLS = ("copy-design", "read-design", "edit-design", "create-upload-url", "upload-asset-from-url",
               "generate-image", "get-generate-image-job", "export-design", "get-assets")
APPROVE_TOOLS = ",".join(["Read", "Write", "Edit", "ToolSearch", "Bash(py *)", "Bash(python *)", "Bash(curl *)"]
                         + [f"mcp__claude_ai_Canva__{n}" for n in CANVA_TOOLS])
APPROVE_TOOLSET = "Read,Write,Edit,Bash,ToolSearch"
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


def title_skill_for(ep) -> str:
    """Title skill of the episode's show; a show without its own uses the global "Viết Title" skill (Cài đặt)."""
    return (podcasts.for_episode(ep).get("title_skill") or "").strip() or db.get_setting("title_skill")


def _segment_title_skill(segment_id: int) -> str:
    return title_skill_for(db.scalar("SELECT episode_id FROM segments WHERE id=?", (segment_id,)) or "")


def thumb_template(ep) -> str:
    """Canva template of the show's thumbnails ('' = the show has none: mocks only, no Canva)."""
    return (podcasts.for_episode(ep).get("thumb_template") or "").strip()


def thumb_paths(seg: dict, ep: dict, folder: Path | None = None, version: int | None = None) -> dict:
    """Video for the Joe/guest frames, the thumbnail work folder (plan + mock) and the final JPG path.
    Each thumbnail version has its own folder thumb_NN\\v<run id> (or `folder` for one imported from old title runs),
    so a new version never overwrites the mock of an earlier one."""
    clip = next((Path(p) for p in (seg.get("clip_path"), seg.get("clip_zoomed_path")) if p and Path(p).exists()), None)
    src = Path(ep["video_path"]) if ep.get("video_path") and Path(ep["video_path"]).exists() else None
    # Thumbnail folders live next to the clips (Clips\<episode>), never next to the full video in Full\.
    base = clip.parent if clip else (cut_stage.episode_clip_folder(ep) if src else config.WORK_DIR / "titles")
    rank = int(seg["rank"] or 0)
    slug = re.sub(r"[^a-z0-9]+", "-", (seg.get("core_keyword") or "thumb").lower()).strip("-")[:40] or "thumb"
    work = folder or (base / f"thumb_{rank:02d}" / f"v{version}" if version else base / f"thumb_{rank:02d}")
    tag = f"_v{version}" if version else ""
    return {"clip": clip, "source": src, "work": work, "plan": work / "thumb_plan.json", "mock": work / "mock.jpg",
            "thumb": base / f"thumb_{ep['id']}_{rank:02d}_{slug}{tag}.jpg", "base": base / f"thumb_{rank:02d}"}


def _thumb_lines(seg: dict, ep: dict, folder: Path | None = None, version: int | None = None) -> list[str]:
    tp = thumb_paths(seg, ep, folder, version)
    host = podcasts.for_episode(ep)["host_short"]
    if tp["clip"]:
        video = f"- Video để trích khung {host}/khách: clip đã cắt {tp['clip']} (giây tính từ 0 của clip)."
    elif tp["source"]:
        video = (f"- Video để trích khung {host}/khách: tập gốc {tp['source']}, chỉ quét "
                 f"--start {seg['start_sec']:.0f} --end {seg['end_sec']:.0f}.")
    else:
        video = f"- ⚠️ Không có file video của đoạn này trên máy: không trích được khung {host}/khách, ghi cảnh báo."
    return [video,
            f"- Script thumbnail: {THUMB_TOOL} (gọi `py -3.14 -X utf8 {THUMB_TOOL} <lệnh> ...`, đọc docstring đầu file).",
            f"- Thư mục làm việc thumbnail: {tp['work']} · plan: {tp['plan']} · mock: {tp['mock']}",
            f"- File thumbnail cuối (chỉ tạo ở lượt duyệt): {tp['thumb']}"]


def _data_lines(seg: dict, ep: dict, tpath: Path, cpath: Path, thumb: list[str] | None = None) -> list[str]:
    """Inputs of a run; `thumb` = the thumbnail lines (video, script, version folder) for thumbnail runs only."""
    dur = max(0.0, (seg["end_sec"] or 0) - (seg["start_sec"] or 0))
    return [
        *show_lines(podcasts.for_episode(ep)),
        "DỮ LIỆU (dùng thẳng, không hỏi lại):",
        f"- Transcript của đoạn đã cắt: {tpath}",
        f"  Timestamp trong file là giờ của tập gốc. Clip bắt đầu ở {seg['start_hms']}, kết thúc ở {seg['end_hms']} "
        f"(dòng \"Thời gian\" ở đầu file), nên timestamps cho YouTube phải trừ offset {seg['start_hms']} đúng luật của skill.",
        f"- Cutlist của riêng đoạn này cho Bước 0: {cpath}. Entry kind=highlight là đoạn cần viết; "
        "các entry kind=hook là hook cold open nằm bên trong đoạn.",
        f"- Tên tập: {episode_name(ep)} · episode_id {ep['id']} · khách mời: {ep.get('guest') or ''}",
        f"- Thời lượng clip: {int(dur // 60)} phút {int(dur % 60)} giây",
        *(thumb or []),
        "",
    ]


GPT_IMAGE_TOOL = str(config.TOOLS_ROOT / "jre-thumb" / "gpt_image.py")


def _gpt_image_rule() -> str:
    """When the centre needs an AI image: render it now with GPT Image (Creater Vid's OpenAI key) and fill it like a photo."""
    model = db.get_setting("thumb_image_model") or "openai:gpt-image-2.5-sunburst"
    quality = db.get_setting("thumb_image_quality") or "high"
    return (
        "ẢNH Ô GIỮA BẰNG AI (chỉ khi chủ đề không thể có ảnh thật, đúng luật của skill): KHÔNG dùng Canva generate-image và "
        "KHÔNG ghi \"center_ai_prompt\". Viết prompt tiếng Anh theo mẫu prompt AI của skill vào file <thư mục làm việc>"
        f"\\center_ai_prompt.txt (Write), rồi render bằng GPT: `py -3.14 -X utf8 {GPT_IMAGE_TOOL} --prompt-file "
        f"\"<thư mục làm việc>\\center_ai_prompt.txt\" --out \"<thư mục làm việc>\\center_ai.png\" --model {model} "
        f"--quality {quality} --aspect 2:3` (một lệnh đứng riêng, đặt timeout 600000 cho lệnh Bash này vì ảnh mất 1–3 phút, tốn tiền thật ~$0,04/ảnh: render 1 ảnh, chỉ render lại "
        "khi ảnh sai subject/có chữ/méo mặt, tối đa 3 lần). Read ảnh để soát, rồi `fill --img center_ai.png --plan` như ảnh "
        "thật. Ghi vào JSON \"image_prompt\" (prompt đã dùng) và nói rõ trong \"thumbnail\" là ảnh AI GPT.")


_TITLE_NO_THUMB = (
    "BƯỚC 4 KHÔNG LÀM Ở LƯỢT NÀY: thumbnail có nút riêng trên Studio. Bước 3 chỉ mô tả bằng chữ (ô giữa: subject + gợi "
    "ý nguồn ảnh thật hoặc lý do phải dùng AI; biểu cảm + mốc giây gợi ý cho Joe và khách). Không trích khung, không tải "
    "ảnh, không tạo ảnh, không dựng mock, không dùng Canva.")

_THUMB_PLAN_RULE = (
    "BƯỚC 4 (THUMBNAIL) Ở STUDIO = CHỈ DỰNG BẢN MOCK, KHÔNG DÙNG CANVA: trích khung (sheet → grab), chọn ảnh giữa (ảnh "
    "thật tải bằng `curl` vào thư mục làm việc; chủ đề không thể có ảnh thật thì render AI theo luật ẢNH Ô GIỮA BẰNG AI), "
    "rồi `crop --img --plan` cho left/right, `fill --img --plan` cho center, `mock --plan --out <mock>`. Read mock.jpg và "
    "soát checklist bước 6 của skill (mặt trọn vẹn, hai đầu ~700px bằng nhau, ngang hàng, logo không đè mặt); trượt thì sửa "
    "plan rồi dựng lại. Bản mock để người dùng duyệt trên Studio; lưu Canva và export chỉ diễn ra khi người dùng bấm Duyệt.")


def _canva_build_steps(template: str) -> list[str]:
    """Steps 1–5: copy the channel template and apply the version's plan on the copy (shared by draft and approval)."""
    return [
        "CÁC BƯỚC (công cụ mcp__claude_ai_Canva__*; chưa thấy schema thì nạp bằng ToolSearch):",
        f"1. copy-design từ template {template} (KHÔNG BAO GIỜ sửa template gốc); update_title "
        "`THUMB | <keyword> | <khách>`.",
        "2. Với từng ảnh trong plan: create-upload-url rồi `curl -s -X POST \"<url>\" -H \"Content-Type: "
        "application/octet-stream\" --data-binary \"@<file>\"` (một lệnh đứng riêng) để lấy mediaId. Nếu plan có "
        "center_ai_prompt: generate-image (PORTRAIT_2_3) với prompt đó, chờ job, dùng media_id kết quả.",
        "3. read-design bản copy (open_transaction, design_content + thumbnails). Nhận 3 ô theo hình học: viền xanh #00bf63 "
        "= center, left≈0 rộng >900 = left, left≈900–1000 = right. Đối chiếu element với plan; lệch thì dừng và báo.",
        "4. edit-design keep_open: update_fill 3 ô, rồi crop_media mỗi ô đúng image_box trong plan (ô center AI: dùng "
        "`py -3.14 -X utf8 " + THUMB_TOOL + " fill` trên ảnh đã tải về để tính, hoặc để Canva tự fill). "
        "Logo 4K: upload file plan.logo.img như các ảnh khác, update_fill vào badge 4K của template (ô nhỏ góc phải trên, "
        "left≈1772), rồi resize_element (preserve_aspect_ratio=false) + position_element đúng plan.logo.element.",
        "5. So thumbnail trả về với mock. Khớp thì edit-design finalize=commit (đây là bản copy, không phải template). "
        "Không khớp thì sửa tiếp trong transaction cho tới khi khớp mock, không commit bản khác mock.",
    ]


def _canva_export_step(n: int) -> str:
    return (f"{n}. export-design jpg quality 90, 1920x1080; `curl -s -L -o \"<file thumbnail cuối>\" \"<download_url>\"`; "
            "> 2 MB thì export lại quality 80.")


def build_canva_draft_prompt(seg: dict, ep: dict, out_json: Path, folder: Path, version: int | None) -> str:
    """After a version's mock is built: put it on its own Canva copy so the user can open and edit it by hand."""
    tp = thumb_paths(seg, ep, folder, version)
    return "\n".join([
        "Bản mock thumbnail này vừa dựng xong trên máy. Nhiệm vụ: dựng ĐÚNG bản này thành một design Canva riêng để người "
        "dùng tự mở ra sửa tay khi cần. Không đổi bố cục, không chọn lại ảnh, KHÔNG export.",
        "",
        f"- Plan: {tp['plan']} (slots left/right/center: img = file ảnh trên máy, element = ô trên trang, "
        "image_box = imageBox cho crop_media; có thể có center_ai_prompt).",
        f"- Mock: {tp['mock']}",
        f"- Kết quả thumbnail của bản này: {out_json}",
        "",
        *_canva_build_steps(thumb_template(ep)),
        f"6. Cập nhật {out_json} (Edit): \"canva_design_id\" (id bản copy), \"canva_edit_url\" (link edit của bản copy); "
        "giữ nguyên các khóa khác. Có ảnh giữa tạo bằng Canva generate-image thì thêm một dòng vào \"warnings\".",
        "7. Trả lời ngắn bằng tiếng Việt: link Canva, bản Canva có khớp mock không. " + _PYTHON_RULE,
        f"8. Kết thúc bằng đúng một dòng: DONE title_json={out_json}",
    ])


def build_export_prompt(seg: dict, ep: dict, out_json: Path, folder: Path, version: int | None, design_id: str) -> str:
    """Approval of a version that already has its Canva copy: export that design as it is now (it may have been
    edited by hand on Canva, so it is not re-applied and not required to match the mock)."""
    tp = thumb_paths(seg, ep, folder, version)
    return "\n".join([
        "Người dùng BẤM DUYỆT một bản thumbnail đã có design Canva riêng (có thể họ đã tự sửa tay trên Canva). Nhiệm vụ: "
        "export đúng design đó như hiện tại. KHÔNG sửa design, không copy template, không dựng lại theo plan.",
        "",
        f"- Design Canva: {design_id}",
        f"- Mock gốc trên máy (chỉ để so): {tp['mock']}",
        f"- File thumbnail cuối: {tp['thumb']} (ghi đè nếu đã có)",
        f"- Kết quả thumbnail của bản này: {out_json}",
        "",
        "CÁC BƯỚC (công cụ mcp__claude_ai_Canva__*; chưa thấy schema thì nạp bằng ToolSearch):",
        _canva_export_step(1),
        f"2. Check back: `py -3.14 -X utf8 {THUMB_TOOL} verify --export \"<file cuối>\" --mock \"{tp['mock']}\"` rồi Read "
        "file export. MISMATCH ở đây KHÔNG phải lỗi (người dùng có thể đã sửa tay): chỉ ghi lại, không sửa design. "
        "Chỉ báo lỗi khi file export hỏng/trống.",
        f"3. Cập nhật {out_json} (Edit): \"thumbnail_path\", \"check_back\" (một dòng: kết quả verify + nhận xét ngắn về "
        "khác biệt so với mock nếu có), giữ nguyên các khóa khác.",
        "4. Trả lời ngắn bằng tiếng Việt: file, dòng Check back. " + _PYTHON_RULE,
        f"5. Kết thúc bằng đúng một dòng: DONE title_json={out_json}",
    ])


def build_approve_prompt(seg: dict, ep: dict, out_json: Path, folder: Path, version: int | None) -> str:
    """The user pressed "Duyệt" on a version without a Canva copy (older runs): apply its plan on Canva, save, export,
    check back."""
    tp = thumb_paths(seg, ep, folder, version)
    return "\n".join([
        "Người dùng vừa xem bản mock thumbnail trên Studio và BẤM DUYỆT. Nhiệm vụ: áp đúng bản đã duyệt lên Canva, "
        "lưu, export và kiểm lại. Không đổi bố cục, không chọn lại ảnh.",
        "",
        f"- Plan đã duyệt: {tp['plan']} (slots left/right/center: img = file ảnh trên máy, element = ô trên trang, "
        "image_box = imageBox cho crop_media; có thể có center_ai_prompt).",
        f"- Mock đã duyệt: {tp['mock']}",
        f"- File thumbnail cuối: {tp['thumb']} (ghi đè nếu đã có)",
        f"- Kết quả thumbnail của bản này: {out_json}",
        "",
        *_canva_build_steps(thumb_template(ep)),
        _canva_export_step(6),
        f"7. Check back (bắt buộc): `py -3.14 -X utf8 {THUMB_TOOL} verify --export \"<file cuối>\" --mock \"{tp['mock']}\"` "
        "phải OK cả hai bên, rồi Read file export và soát lại checklist. MISMATCH thì sửa, export lại.",
        f"8. Cập nhật {out_json} (Edit): \"thumbnail_path\", \"canva_design_id\", \"canva_edit_url\", \"check_back\" "
        "(một dòng kết quả kiểm), "
        "giữ nguyên các khóa khác.",
        "9. Trả lời ngắn bằng tiếng Việt: link Canva, file, dòng Check back. " + _PYTHON_RULE,
        f"10. Kết thúc bằng đúng một dòng: DONE title_json={out_json}",
    ])


_FOCUS_HOOK_KEY = ('"focus_hook": {"start": "HH:MM:SS", "end": "HH:MM:SS", "quote_en": "<nguyên văn lời nói trong '
                   'lát cắt>", "why": "<1 câu: vì sao lát này giữ chân người gõ keyword mới>"}')


def focus_lines(focus: str | None, seg: dict) -> list[str]:
    """User-chosen focus: overrides the cutlist keyword/hook and asks for a new HOOK 01 cut around it."""
    if not focus:
        return []
    return [
        "🎯 YÊU CẦU TRỌNG TÂM CỦA NGƯỜI DÙNG (ƯU TIÊN HƠN CUTLIST VÀ HƠN BƯỚC 0):",
        '"""', focus.strip(), '"""',
        "- KHÔNG dùng `core_keyword`, `hook_en`, `keyword_reason` của cutlist. Chọn KEYWORD HẠT NHÂN MỚI đúng khúc trọng "
        "tâm này theo luật Bước 1 (cụm người ta gõ thật, chấm Reach × KGC). Người dùng có gợi ý key thì bám theo gợi ý "
        "đó, chỉ chỉnh về đúng cách người ta gõ.",
        "- Toàn bộ title (cả 2 format), description, tags, thumbnail ô giữa xoay quanh keyword mới; Big Hook lấy trong khúc "
        "trọng tâm. Timestamps vẫn phủ cả clip như luật cũ. Ghi một dòng ⚠️ `keyword cũ → keyword mới`.",
        "- Chọn HOOK COLD OPEN MỚI cho keyword mới: một lát liền mạch 5–25 giây nằm trong đoạn "
        f"({seg['start_hms']} → {seg['end_hms']}), đắt nhất cho người gõ keyword mới, bắt đầu và kết thúc đúng ranh giới "
        "câu (không cắt giữa từ), không cần ngữ cảnh trước mới hiểu. Câu chốt chứa keyword phải nằm TRỌN trong hook: nếu "
        "cần thì được kéo tới 35 giây, không bỏ câu chốt để giữ 25 giây. Mốc theo TIMESTAMP GỐC CỦA TẬP (như trong transcript), "
        "dạng HH:MM:SS. Studio sẽ dùng nó cắt lại HOOK 01 của đoạn.",
        f"- Trong JSON kết quả thêm khóa {_FOCUS_HOOK_KEY}; \"core_keyword\" là keyword MỚI.",
        "",
    ]


_PYTHON_RULE = ("Chỉ được phép chạy python bằng MỘT lệnh đứng riêng dạng `python -X utf8 <đường dẫn file .py>` hoặc "
                "`python -X utf8 -c \"...\"`: không `cd`, không nối lệnh bằng && hay ;, không dùng PowerShell.")


def build_prompt(skill: str, skill_text: str, seg: dict, ep: dict, tpath: Path, cpath: Path, out_json: Path,
                 focus: str | None = None) -> str:
    return "\n".join(_skill_lines(skill, skill_text) + [
        "YÊU CẦU: chạy wf VIẾT TITTLE cho MỘT đoạn highlight, ở CHẾ ĐỘ TỰ ĐỘNG (headless).",
        "",
        *_data_lines(seg, ep, tpath, cpath),
        *focus_lines(focus, seg),
        "LUẬT CHẾ ĐỘ TỰ ĐỘNG:",
        "1. Không hỏi người dùng. Chỗ nào skill bảo báo hoặc hỏi người dùng thì ghi một dòng ⚠️ cảnh báo ngay trong kết quả, "
        "tự quyết theo mặc định của skill rồi làm tiếp.",
        "2. Xuất các bước đúng format của skill ngay trong câu trả lời: phân tích bằng tiếng Việt; title, description, "
        "timestamps, tags bằng tiếng Anh. " + _TITLE_NO_THUMB,
        f"3. Sau đó ghi MỘT file JSON UTF-8 vào {out_json} với các khóa: "
        "\"core_keyword\", \"vibe\", \"big_hook\", \"titles_format1\" (mảng 3 title), \"titles_format2\" (mảng 3 title), "
        "\"recommended_title\" (title bạn khuyên dùng nhất), \"description\" (toàn văn, gồm cả dòng cuối), "
        "\"timestamps\" (toàn văn khối timestamps), \"tags\" (chuỗi tags), \"tags_chars\" (số ký tự thực tế), "
        "\"thumbnail\" (ý tưởng Bước 3 bằng chữ: ảnh giữa là gì + gợi ý nguồn hoặc AI, biểu cảm Joe/khách + mốc giây), "
        "\"warnings\" (mảng cảnh báo, có thể rỗng).",
        "4. Đếm ký tự của title và tags bằng python khi cần, không ước lượng. " + _PYTHON_RULE,
        "5. Không đọc mã nguồn trong E:\\Tool\\DataBase. Kết thúc bằng đúng một dòng: DONE title_json=<đường dẫn>",
    ])


def build_chat_prompt(message: str, out_json: Path) -> str:
    """One chat turn inside the session that wrote the metadata (or a seeded one): adjust the JSON in place."""
    return "\n".join([
        "Người dùng vừa xem metadata của đoạn này trên Hổ Báo Studio và nhắn:",
        '"""', message.strip(), '"""',
        "",
        "LUẬT KHI CHỈNH:",
        f"1. File JSON đang hiển thị trên Studio: {out_json}. Nếu tin nhắn yêu cầu đổi metadata thì sửa thẳng file đó "
        "(Edit, hoặc Write lại cả file nếu đổi nhiều), giữ đủ các khóa như cũ và cập nhật cả các trường liên quan theo luật "
        "của skill (recommended_title, titles_format1/2, description, timestamps, tags và tags_chars, thumbnail).",
        "   Tin nhắn đòi dựng hoặc sửa ẢNH thumbnail: KHÔNG làm ở đây (không trích khung, không tạo ảnh, không dùng Canva). "
        "Trả lời ngắn rằng ảnh thumbnail làm ở mục 🖼 Thumbnail riêng (nút Tạo thumbnail, hoặc khung nhắn của mục đó). "
        "Chỉ được sửa trường chữ \"thumbnail\" (ý tưởng) nếu người dùng muốn đổi ý tưởng.",
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
        f"hiển thị trên Hổ Báo Studio nằm trong {out_json} (đọc file đó trước khi sửa, nó có thể mới hơn câu trả lời).",
        "",
        *_data_lines(seg, ep, tpath, cpath),
        "<cau_tra_loi_truoc>", (previous_md or "(không lưu)").strip(), "</cau_tra_loi_truoc>",
        "",
        build_chat_prompt(message, out_json),
    ])


# ---------------------------------------------------------------- thumbnail runs
# "Tạo thumbnail" is its own run (segment_titles.kind='thumb'), separate from "Viết Title": it builds Bước 3–4A (frames,
# centre image, plan, mock) from the current title result. Every thumbnail run and every chat edit is a version with its
# own folder thumb_NN\v<run id>, so earlier mocks stay viewable and any version can be approved for Canva.
_THUMB_JSON_KEYS = ('"thumb_mock" (đường dẫn mock.jpg trong thư mục của bản này), "thumbnail" (tóm tắt: ảnh giữa là gì + '
                    'nguồn/license hoặc AI GPT, Joe @ giây X, khách @ giây Y, kết quả soát mock), "image_prompt" (chỉ khi '
                    'ô giữa dùng AI), "warnings" (mảng cảnh báo, có thể rỗng)')


def _title_context(title_data: dict | None) -> list[str]:
    if not title_data:
        return ["KẾT QUẢ VIẾT TITLE: chưa có. Dùng core_keyword trong cutlist làm keyword hạt nhân; tự chạy nhanh Bước 1 "
                "(chỉ để chốt keyword + vibe), không viết title.", ""]
    keep = {k: title_data.get(k) for k in ("core_keyword", "vibe", "big_hook", "recommended_title", "titles_format1",
                                           "titles_format2", "thumbnail") if title_data.get(k)}
    return ["KẾT QUẢ VIẾT TITLE ĐANG DÙNG (thumbnail phải khớp keyword và title này; \"thumbnail\" là ý tưởng Bước 3 bằng chữ):",
            "```json", json.dumps(keep, ensure_ascii=False, indent=1), "```", ""]


def build_thumb_prompt(skill: str, skill_text: str, seg: dict, ep: dict, tpath: Path, cpath: Path, out_json: Path,
                       folder: Path, version: int, title_data: dict | None, request: str | None) -> str:
    return "\n".join(_skill_lines(skill, skill_text) + [
        "YÊU CẦU: dựng THUMBNAIL cho MỘT đoạn highlight (Bước 3 + 4A của skill), CHẾ ĐỘ TỰ ĐỘNG. Không viết lại title, "
        "description, tags.",
        "",
        *_data_lines(seg, ep, tpath, cpath, _thumb_lines(seg, ep, folder, version)),
        *_title_context(title_data),
        *(["YÊU CẦU RIÊNG CỦA NGƯỜI DÙNG CHO THUMBNAIL (ưu tiên hơn ý tưởng trong kết quả title):", '"""',
           request.strip(), '"""', ""] if request else []),
        "LUẬT:",
        f"1. Mọi file của bản thumbnail này nằm trong {folder} (tạo nếu chưa có). Được ĐỌC/chép ảnh và khung từ các bản "
        f"cũ trong {thumb_paths(seg, ep)['base']} để khỏi trích lại, nhưng KHÔNG sửa file của bản cũ.",
        "2. Không hỏi người dùng; chỗ nào skill bảo hỏi thì ghi ⚠️ rồi tự quyết. " + _THUMB_PLAN_RULE + " " + _gpt_image_rule(),
        f"3. Ghi MỘT file JSON UTF-8 vào {out_json} với các khóa: {_THUMB_JSON_KEYS}.",
        "4. " + _PYTHON_RULE + " Không đọc mã nguồn trong E:\\Tool\\DataBase.",
        "5. Trả lời ngắn bằng tiếng Việt: ảnh giữa là gì (nguồn), khung Joe/khách, kết quả soát mock.",
        f"6. Kết thúc bằng đúng một dòng: DONE title_json={out_json}",
    ])


def build_thumb_chat_prompt(message: str, out_json: Path, folder: Path, parent_folder: Path) -> str:
    """Edit turn: the parent version's folder was copied to `folder`; change the copy, rebuild its mock."""
    return "\n".join([
        "Người dùng vừa xem bản mock thumbnail trên Hổ Báo Studio và nhắn:",
        '"""', message.strip(), '"""',
        "",
        "LUẬT KHI CHỈNH:",
        f"1. Đây là một BẢN THUMBNAIL MỚI. Studio đã chép toàn bộ bản trước ({parent_folder}) sang {folder}: chỉ làm "
        f"trong {folder} (plan: {folder / 'thumb_plan.json'}, mock: {folder / 'mock.jpg'}); KHÔNG sửa file trong "
        f"{parent_folder}. Plan chép sang có thể còn trỏ ảnh ở thư mục cũ: được đọc, nhưng ảnh mới phải ghi vào {folder}.",
        "2. Sửa plan bằng script thumbnail (crop/fill --plan) rồi dựng lại mock và Read để soát. " + _THUMB_PLAN_RULE + " "
        + _gpt_image_rule() + " Người dùng nhắn đổi ô giữa sang ảnh AI (hoặc sửa ảnh AI) thì render theo đúng luật đó.",
        f"3. File JSON của bản mới: {out_json} (đã chép từ bản trước). Cập nhật \"thumb_mock\" = {folder / 'mock.jpg'}, "
        "\"thumbnail\", \"image_prompt\", \"warnings\"; giữ các khóa khác.",
        "4. Nếu tin nhắn chỉ hỏi thì trả lời, không dựng lại.",
        "5. " + _PYTHON_RULE,
        "6. Trả lời ngắn bằng tiếng Việt: đã đổi gì, kết quả soát mock.",
        f"7. Kết thúc bằng đúng một dòng: DONE title_json={out_json}",
    ])


# ---------------------------------------------------------------- Gemini
# A model setting starting with "gemini" runs the skill through the Gemini API instead of Claude Code. Gemini has no
# tools on this machine: the transcript and cutlist go inline, it skips Bước 4 (mock/Canva), and it returns the result
# JSON as the last ```json block of its answer, which Studio writes to the same file a Claude run would.
_JSON_KEYS = ('"core_keyword", "vibe", "big_hook", "titles_format1" (mảng 3 title), "titles_format2" (mảng 3 title), '
              '"recommended_title", "description" (toàn văn, gồm cả dòng cuối), "timestamps" (toàn văn khối timestamps), '
              '"tags" (chuỗi tags), "thumbnail" (tóm tắt: ảnh giữa là gì + gợi ý nguồn, biểu cảm + mốc giây cho Joe và '
              'khách), "image_prompt" (chỉ khi ô giữa phải dùng AI), "warnings" (mảng cảnh báo, có thể rỗng)')
_RE_JSON_BLOCK = re.compile(r"```json\s*(\{.*?\})\s*```", re.S)


def _gemini_inputs(seg: dict, ep: dict, tpath: Path, cpath: Path, focus: str | None = None) -> str:
    dur = max(0.0, (seg["end_sec"] or 0) - (seg["start_sec"] or 0))
    return "\n".join([
        "chạy wf VIẾT TITTLE cho MỘT đoạn highlight, ở CHẾ ĐỘ TỰ ĐỘNG (headless).",
        "",
        *show_lines(podcasts.for_episode(ep)),
        *focus_lines(focus, seg),
        f"Tên tập: {episode_name(ep)} · episode_id {ep['id']} · khách mời: {ep.get('guest') or ''}",
        f"Clip bắt đầu ở {seg['start_hms']}, kết thúc ở {seg['end_hms']} ({int(dur // 60)} phút {int(dur % 60)} giây). "
        f"Timestamp trong transcript là giờ của tập gốc, timestamps cho YouTube phải trừ offset {seg['start_hms']}.",
        "",
        "### Cutlist của riêng đoạn này (Bước 0). Entry kind=highlight là đoạn cần viết, kind=hook là hook cold open bên trong.",
        "```json", cpath.read_text(encoding="utf-8").strip(), "```",
        "",
        "### Transcript của đoạn", tpath.read_text(encoding="utf-8").strip(),
    ])


def _gemini_system(skill: str, skill_text: str) -> str:
    return "\n".join(_skill_lines(skill, skill_text) + [
        "LUẬT KHI CHẠY QUA GEMINI API (không có công cụ trên máy, không đọc được video, không có Canva):",
        "1. Không hỏi người dùng. Chỗ nào skill bảo báo hoặc hỏi người dùng thì ghi một dòng ⚠️ cảnh báo, tự quyết theo "
        "mặc định của skill rồi làm tiếp.",
        "2. Làm đủ Bước 0–3 đúng format của skill: phân tích bằng tiếng Việt; title, description, timestamps, tags bằng "
        "tiếng Anh. Bước 3 chỉ mô tả bằng chữ: subject ô giữa + gợi ý nguồn ảnh, biểu cảm và mốc giây (giờ tập gốc) "
        "có khả năng có biểu cảm đó cho Joe và cho khách. Bước 4 ghi đúng một dòng: \"Bước 4: bỏ qua (chạy qua Gemini).\"",
        "3. Tự kiểm từng title theo Gate 0 của skill (keyword nguyên văn trong 5 từ đầu, 9–14 từ, dưới 100 ký tự, đúng "
        "đuôi), description 150–250 từ, tags ≤ 480 ký tự, trước khi xuất.",
        f"4. Cuối câu trả lời in MỘT khối ```json chứa các khóa: {_JSON_KEYS}.",
    ])


def _gemini_parse(text: str) -> tuple[str, dict | None]:
    """Answer text without the trailing JSON block, and that block parsed (None if missing or broken)."""
    blocks = list(_RE_JSON_BLOCK.finditer(text or ""))
    if not blocks:
        return (text or "").strip(), None
    m = blocks[-1]
    try:
        data = json.loads(m.group(1))
    except ValueError:
        return (text or "").strip(), None
    if isinstance(data, dict) and isinstance(data.get("tags"), str):
        data["tags_chars"] = len(data["tags"])               # Gemini cannot count, so Studio does
    return (text[:m.start()] + text[m.end():]).strip(), data if isinstance(data, dict) else None


def _gemini_title(run: dict, seg: dict, ep: dict, skill: str, skill_text: str, work: Path, tpath: Path, cpath: Path,
                  out_json: Path, update, stop_flag) -> tuple[dict, dict | None, str]:
    system = _gemini_system(skill, skill_text)
    user = _gemini_inputs(seg, ep, tpath, cpath, run.get("focus"))
    (work / "prompt.txt").write_text(system + "\n\n=====\n\n" + user, encoding="utf-8")
    res = gemini_runner.run(system, [{"role": "user", "parts": [{"text": user}]}], model=run["model"],
                            log_path=work / "gemini_run.json", update=update, stop_flag=stop_flag)
    text, data = _gemini_parse(res.get("text") or "")
    if data is not None:
        data["warnings"] = list(data.get("warnings") or []) + res.get("warnings", [])
        write_json(out_json, data)
    return res, data, text


def _gemini_chat(run: dict, parent: dict, seg: dict, ep: dict, skill: str, work: Path, tpath: Path, cpath: Path,
                 out_json: Path, current: dict | None, update, stop_flag) -> tuple[dict, dict | None, str]:
    """No session to resume: replay the inputs and the first answer, then the current JSON and the message."""
    previous = _chain_root(parent).get("output_md") or "(không lưu)"
    ask = "\n".join([
        "Người dùng vừa xem metadata của đoạn này trên Hổ Báo Studio. Metadata đang hiển thị (có thể mới hơn câu trả lời trước):",
        "```json", json.dumps(current or {}, ensure_ascii=False, indent=1), "```",
        "", "Người dùng nhắn:", '"""', run["user_message"].strip(), '"""', "",
        "LUẬT KHI CHỈNH:",
        "1. Nếu tin nhắn yêu cầu đổi metadata: trả lời ngắn bằng tiếng Việt đổi trường nào, giá trị mới (title, tags… ghi "
        "nguyên văn tiếng Anh), rồi in TOÀN BỘ JSON mới trong một khối ```json, giữ đủ các khóa như cũ và cập nhật cả các "
        "trường liên quan theo luật của skill.",
        "2. Nếu tin nhắn chỉ hỏi thì trả lời, KHÔNG in khối json.",
        "3. Người dùng yêu cầu điều trái luật skill thì vẫn làm theo, kèm một dòng ⚠️ nói rõ luật nào bị phá.",
        "4. Không dựng thumbnail, không dùng Canva.",
    ])
    contents = [{"role": "user", "parts": [{"text": _gemini_inputs(seg, ep, tpath, cpath, _chain_root(parent).get("focus"))}]},
                {"role": "model", "parts": [{"text": previous}]},
                {"role": "user", "parts": [{"text": ask}]}]
    res = gemini_runner.run(_gemini_system(skill, _skill_text(skill)), contents, model=run["model"],
                            log_path=work / f"gemini_chat_{run['id']}.json", update=update, stop_flag=stop_flag)
    text, data = _gemini_parse(res.get("text") or "")
    if data is not None:
        write_json(out_json, data)
    return res, data or current, text


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
_RE_TITLE_ROW = r"^\s*\|?\s*\d\s*\|\s*(.+?{host}.*?)\s*\|"     # a title table row naming the host
_RE_DONE_LINE = re.compile(r"^\s*DONE\s+title_json=.*$", re.M)


def final_answer(texts: list[str]) -> str:
    """The skill's answer without the short status notes Claude writes between tool calls, and without the DONE line."""
    blocks = [t for t in texts if t and t.strip()]
    if not blocks:
        return ""
    longest = max(range(len(blocks)), key=lambda i: len(blocks[i]))
    answer = "\n\n".join(blocks[longest:])
    return _RE_DONE_LINE.sub("", answer).strip()


def _fallback_title(text: str, host: str = "Joe Rogan") -> str | None:
    m = re.search(_RE_TITLE_ROW.format(host=re.escape(host or "Joe Rogan")), text or "", re.M)
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


def _finish(run_id: int, job_id: int, seg: dict, res: dict, data, text: str, turn_cost=None, thumb: bool = False) -> dict:
    thumb_run = thumb                                     # `thumb` is reused below for the JPG path
    recommended = None if thumb else (data or {}).get("recommended_title") or _fallback_title(text, podcasts.for_episode(seg.get("episode_id") or "").get("host"))
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
        thumb = str((data or {}).get("thumbnail_path") or "").strip() if isinstance(data, dict) else ""
        if thumb and Path(thumb).exists():
            c.execute("UPDATE segments SET thumbnail_path=? WHERE id=?", (thumb, seg["id"]))
    from ..search import rebuild_index
    rebuild_index([seg["id"]])
    _announce(run_id, seg, recommended, thumb_run)
    return {"run_id": run_id, "recommended_title": recommended, "summary": summary}


def _seg_where(seg: dict) -> str:
    return f"đoạn #{seg.get('rank') or '?'}: {(seg.get('title') or '')[:70]}"


def _announce(run_id: int, seg: dict, recommended: str | None, thumb: bool) -> None:
    """🔔 title written / metadata edited / thumbnail mock waiting for approval / thumbnail exported."""
    from .orchestrator import ep_label, ep_link
    run = db.row("SELECT parent_id, user_message FROM segment_titles WHERE id=?", (run_id,)) or {}
    where, ep, link = _seg_where(seg), ep_label(seg["episode_id"]), ep_link(seg["episode_id"], seg["id"])
    if thumb and run.get("user_message") == APPROVE_MSG:
        notify.resolve(f"thumb-review:{seg['id']}")
        notify.notify("done", f"Thumbnail đã lên Canva và export JPG: {where}", ep, link)
    elif thumb:
        notify.notify("review", f"Thumbnail xong, cần duyệt: {where}", f"{ep} · xem bản mock rồi bấm Duyệt để lên Canva",
                      link, key=f"thumb-review:{seg['id']}")
    elif run.get("parent_id"):
        notify.notify("done", f"Claude đã chỉnh metadata: {where}", (run.get("user_message") or ep)[:160], link)
    else:
        notify.notify("done", f"Viết title xong: {where}", recommended or ep, link)


def _claude(prompt: str, run: dict, work: Path, log_name: str, update, stop_flag, resume: str | None = None,
            max_turns: int = 90, timeout: int = 60 * 60) -> dict:
    return claude_runner.run(prompt, cwd=config.BASE_DIR, tools=TITLE_TOOLSET, allowed_tools=TITLE_TOOLS, isolated=True,
                             permission_mode="acceptEdits", max_turns=max_turns, model=run["model"] or None,
                             effort=run["effort"] or None, timeout=timeout, log_path=work / log_name,
                             on_event=TitleProgress(update), stop_flag=stop_flag, resume=resume)


def _claude_canva(prompt: str, run: dict, work: Path, log_name: str, update, stop_flag) -> dict:
    """Approval turn only: keeps the claude.ai connectors (Canva) but drops slash commands and auto-memory."""
    model = None if gemini_runner.is_gemini(run["model"]) else run["model"] or None   # Canva needs Claude
    return claude_runner.run(prompt, cwd=config.BASE_DIR, tools=APPROVE_TOOLSET, allowed_tools=APPROVE_TOOLS,
                             permission_mode="acceptEdits", max_turns=60, model=model,
                             effort=run["effort"] or None, timeout=30 * 60, log_path=work / log_name,
                             on_event=TitleProgress(update), stop_flag=stop_flag,
                             extra_args=["--disable-slash-commands"], env_extra={"CLAUDE_CODE_DISABLE_AUTO_MEMORY": "1"})


def run_title(run_id: int, stop_flag=None) -> dict:
    run = db.row("SELECT * FROM segment_titles WHERE id=?", (run_id,))
    if run.get("kind") == "thumb":
        return run_thumb(run, stop_flag)
    if run.get("parent_id"):
        return run_chat(run, stop_flag)
    seg, ep, hooks = _bundle(run["segment_id"])
    skill = run["skill"] or title_skill_for(ep)
    skill_text = _skill_text(skill)
    work, out_json = _work_paths(seg, ep)
    tpath, cpath = prepare_inputs(seg, ep, hooks, work)
    if out_json.exists():
        out_json.rename(out_json.with_name(out_json.name + f".old_{int(out_json.stat().st_mtime)}"))
    job_id, update = _start(run_id, seg, ep, f"viết title đoạn #{seg['rank']}: {seg['title'][:60]}")
    if gemini_runner.is_gemini(run["model"]):
        res, data, text = _gemini_title(run, seg, ep, skill, skill_text, work, tpath, cpath, out_json, update, stop_flag)
        if not res.get("ok") and not data:
            raise RuntimeError(res.get("error") or "Gemini không trả kết quả")
        if data is None:
            res.update(ok=False, error="Gemini không in khối JSON kết quả, chỉ có câu trả lời")
        _focus_hook(run, seg, ep, data, out_json, update)
        return _finish(run_id, job_id, seg, res, data, text)
    prompt = build_prompt(skill, skill_text, seg, ep, tpath, cpath, out_json, focus=run.get("focus"))
    (work / "prompt.txt").write_text(prompt, encoding="utf-8")
    res = _claude(prompt, run, work, "claude_run.jsonl", update, stop_flag)
    data = _read_result(out_json, run_id)
    text = final_answer(res.get("texts") or [res.get("text") or ""])
    if not res.get("ok") and not data:
        raise RuntimeError(res.get("error") or "Claude không trả kết quả")
    if not text and not data:
        raise RuntimeError("Claude chạy xong nhưng không có nội dung")
    _focus_hook(run, seg, ep, data, out_json, update)
    return _finish(run_id, job_id, seg, res, data, text)


# Set by the app: queue a zoom for re-cut hooks (the orchestrator lives in the app process).
AFTER_HOOK_RECUT = None


def _focus_hook(run: dict, seg: dict, ep: dict, data, out_json: Path, update) -> None:
    """Focus run: re-cut HOOK 01 at the hook the model chose and note the outcome in the result JSON."""
    if not run.get("focus") or not isinstance(data, dict):
        return
    try:
        r = hook_recut.recut(seg, ep, data.get("focus_hook"), update)
        data["focus_hook_result"] = r["message"]
        if r.get("zoom_ids") and AFTER_HOOK_RECUT:
            try:
                AFTER_HOOK_RECUT(ep["id"], r["zoom_ids"])
            except Exception as e:  # noqa: BLE001
                log.warning("zoom for re-cut hook not queued: %s", e)
    except Exception as e:  # noqa: BLE001
        log.warning("focus hook re-cut failed for segment %s: %s", seg["id"], e)
        data["focus_hook_result"] = f"⚠️ chưa cắt lại hook: {e}"
        data["warnings"] = list(data.get("warnings") or []) + [data["focus_hook_result"]]
    write_json(out_json, data)


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
    skill = parent["skill"] or title_skill_for(ep)
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
    if gemini_runner.is_gemini(run["model"]):
        res, data, text = _gemini_chat(run, parent, seg, ep, skill, work, tpath, cpath, out_json, current, update,
                                       stop_flag)
        if stop_flag and stop_flag():
            raise RuntimeError("đã hủy")
        if not res.get("ok") and not text:
            raise RuntimeError(res.get("error") or "Gemini không trả lời")
        return _finish(run["id"], job_id, seg, res, data, text or "Đã xong.")
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


TITLE_KIND = "COALESCE(kind,'title')='title'"       # SQL: title runs (rows made before thumbnails split have no kind)


def _json_of(run: dict | None) -> dict:
    try:
        return json.loads(run["output_json"]) if run and run.get("output_json") else {}
    except ValueError:
        return {}


def _latest_title_data(seg_id: int) -> dict | None:
    return _json_of(db.row(f"SELECT output_json FROM segment_titles WHERE segment_id=? AND status='done' AND {TITLE_KIND} "
                           "ORDER BY id DESC LIMIT 1", (seg_id,))) or None


def thumb_model(model: str | None) -> str:
    """Thumbnails need Claude (frames, images, mock, Canva): a Gemini choice falls back to the Claude title model."""
    if model and not gemini_runner.is_gemini(model):
        return model
    m = db.get_setting("claude_model_title") or ""
    return m if m and not gemini_runner.is_gemini(m) else "opus"


# Keys that belong to one version's Canva copy and export: an edit starts a new version without them.
_PER_VERSION_KEYS = ("canva_design_id", "canva_edit_url", "thumbnail_path", "check_back")


def _canva_draft(run: dict, seg: dict, ep: dict, work: Path, out_json: Path, folder: Path, version: int | None,
                 update, stop_flag) -> tuple[dict, float | None]:
    """Second turn of a new version: put its mock on its own Canva copy (link in the JSON) so the user can edit it by
    hand. A failure only adds a warning: the version and its mock stay usable, approval then builds the copy itself."""
    if not thumb_template(ep):
        data = _read_result(out_json, run["id"]) or {}
        data.update(folder=str(folder), version=version)
        data["warnings"] = [*normalize(data)["warnings"],
                            "show này chưa có template Canva (Cài đặt → Show podcast): chỉ có bản mock, chưa lên Canva"]
        write_json(out_json, data)
        return data, None
    update("đẩy bản mock lên Canva để sửa tay…")
    try:
        res = _claude_canva(build_canva_draft_prompt(seg, ep, out_json, folder, version), run, work,
                            f"canva_{run['id']}.jsonl", update, stop_flag)
    except Exception as e:  # noqa: BLE001
        log.warning("canva draft failed for run %s: %s", run["id"], e)
        res = {"ok": False, "error": str(e)}
    data = _read_result(out_json, run["id"]) or {}
    data.update(folder=str(folder), version=version)
    if not data.get("canva_edit_url"):
        why = "đã hủy" if stop_flag and stop_flag() else (res.get("error") or "không có link")
        data["warnings"] = [*normalize(data)["warnings"], f"chưa đẩy được lên Canva ({why}): bấm Duyệt sẽ tự dựng trên Canva"]
    write_json(out_json, data)
    return data, res.get("cost_usd")


def run_thumb(run: dict, stop_flag=None) -> dict:
    """A thumbnail version: fresh (no parent), an edit of a parent version (copied to a new folder), or the approval of
    a version (Canva, in that version's folder)."""
    seg, ep, hooks = _bundle(run["segment_id"])
    skill = run["skill"] or title_skill_for(ep)
    work, _ = _work_paths(seg, ep)
    tpath, cpath = prepare_inputs(seg, ep, hooks, work, keep_existing=True)
    out_json = work / f"thumb_v{run['id']}.json"
    parent = db.row("SELECT * FROM segment_titles WHERE id=?", (run["parent_id"],)) if run.get("parent_id") else None
    pdata = _json_of(parent)
    approve = run.get("user_message") == APPROVE_MSG
    session, turn_cost = None, None
    if parent and not pdata.get("folder"):
        raise RuntimeError("bản thumbnail gốc không còn thư mục để làm tiếp")
    if approve:
        folder, version = Path(pdata["folder"]), pdata.get("version")
        design_id = str(pdata.get("canva_design_id") or "").strip()
        if not design_id and (not (folder / "thumb_plan.json").exists() or not (folder / "mock.jpg").exists()):
            raise RuntimeError("bản này không có plan/mock để duyệt")
        if not design_id and not thumb_template(ep):
            raise RuntimeError("show này chưa có template Canva (Cài đặt → Show podcast), chưa duyệt lên Canva được")
        write_json(out_json, pdata)
        job_id, update = _start(run["id"], seg, ep, f"duyệt thumbnail đoạn #{seg['rank']} (bản #{parent['id']})")
        prompt = (build_export_prompt(seg, ep, out_json, folder, version, design_id) if design_id
                  else build_approve_prompt(seg, ep, out_json, folder, version))
        res = _claude_canva(prompt, run, work, f"approve_{run['id']}.jsonl", update, stop_flag)
    elif parent:
        folder, version = thumb_paths(seg, ep, version=run["id"])["work"], run["id"]
        if folder.exists():
            shutil.rmtree(folder)
        shutil.copytree(Path(pdata["folder"]), folder, ignore=shutil.ignore_patterns("v[0-9]*", "*.jsonl"))
        pdata = {k: v for k, v in pdata.items() if k not in _PER_VERSION_KEYS}   # the new version gets its own Canva copy
        write_json(out_json, dict(pdata, folder=str(folder), version=version, thumb_mock=str(folder / "mock.jpg")))
        job_id, update = _start(run["id"], seg, ep, f"chỉnh thumbnail đoạn #{seg['rank']}: {run['user_message'][:70]}")
        ask = build_thumb_chat_prompt(run["user_message"], out_json, folder, Path(pdata["folder"]))
        session = parent.get("session_id")
        res = None
        if session:
            res = _claude(ask, run, work, f"thumb_{run['id']}.jsonl", update, stop_flag, resume=session, max_turns=60,
                          timeout=40 * 60)
            if "No conversation found" in (res.get("error") or ""):
                res, session = None, None
        if res is None:
            seed = "\n".join(_skill_lines(skill, _skill_text(skill)) + [
                "BỐI CẢNH: thumbnail của đoạn này đã được dựng ở chế độ tự động; người dùng muốn chỉnh.", "",
                *_data_lines(seg, ep, tpath, cpath, _thumb_lines(seg, ep, folder, version)),
                *_title_context(_latest_title_data(seg["id"])), ask])
            res = _claude(seed, run, work, f"thumb_{run['id']}.jsonl", update, stop_flag, max_turns=60, timeout=40 * 60)
        same = session and res.get("session_id") == parent.get("session_id")
        turn_cost = (res["cost_usd"] - (parent.get("session_cost_usd") or 0)) if same and res.get("cost_usd") else None
        if turn_cost is not None and turn_cost < 0:
            turn_cost = None
    else:
        folder, version = thumb_paths(seg, ep, version=run["id"])["work"], run["id"]
        folder.mkdir(parents=True, exist_ok=True)
        job_id, update = _start(run["id"], seg, ep, f"tạo thumbnail đoạn #{seg['rank']}")
        prompt = build_thumb_prompt(skill, _skill_text(skill), seg, ep, tpath, cpath, out_json, folder, version,
                                    _latest_title_data(seg["id"]), run.get("user_message"))
        (folder / "prompt.txt").write_text(prompt, encoding="utf-8")
        res = _claude(prompt, run, work, f"thumb_{run['id']}.jsonl", update, stop_flag)
    if stop_flag and stop_flag():
        raise RuntimeError("đã hủy")
    data = _read_result(out_json, run["id"])
    text = final_answer(res.get("texts") or [res.get("text") or ""])
    if not res.get("ok") and not data and not text:
        raise RuntimeError(res.get("error") or "Claude không trả lời")
    data = dict(data or pdata or {}, folder=str(folder), version=version)
    if not approve and not data.get("thumb_mock") and (folder / "mock.jpg").exists():
        data["thumb_mock"] = str(folder / "mock.jpg")
    write_json(out_json, data)
    if not approve and (folder / "thumb_plan.json").exists() and (folder / "mock.jpg").exists():
        data, cost = _canva_draft(run, seg, ep, work, out_json, folder, version, update, stop_flag)
        base = turn_cost if turn_cost is not None else res.get("cost_usd")
        if cost and base is not None:
            turn_cost = base + cost                    # shown cost only; the session's own cost stays as it was
    return _finish(run["id"], job_id, seg, res, data, text or "Đã xong.", turn_cost=turn_cost, thumb=True)


def import_legacy_thumbs() -> int:
    """Mocks built by title runs before the split become thumbnail version zero of their segment (folder thumb_NN), so
    they show in the Thumbnail section again and can be edited or approved. Idempotent."""
    n = 0
    rows = db.rows(f"SELECT * FROM segment_titles WHERE status='done' AND {TITLE_KIND} AND output_json LIKE '%thumb_mock%' "
                   "AND segment_id NOT IN (SELECT segment_id FROM segment_titles WHERE kind='thumb') ORDER BY id")
    latest: dict[int, dict] = {}
    for r in rows:
        d = _json_of(r)
        if d.get("thumb_mock") and Path(d["thumb_mock"]).exists():
            latest[r["segment_id"]] = (r, d)
    with db.tx() as c:
        for seg_id, (r, d) in latest.items():
            data = {k: d.get(k) for k in ("thumb_mock", "thumbnail", "image_prompt", "thumbnail_path", "canva_edit_url",
                                          "check_back", "warnings") if d.get(k)}
            data.update(folder=str(Path(d["thumb_mock"]).parent), version=None, from_title_run=r["id"])
            c.execute("""INSERT INTO segment_titles(segment_id, kind, skill, model, effort, status, progress_msg, output_json,
                         output_md, session_id, session_cost_usd, created_at, started_at, finished_at)
                         VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                      (seg_id, "thumb", r["skill"], r["model"], r["effort"], "done",
                       f"bản dựng cùng Viết Title #{r['id']}", json.dumps(data, ensure_ascii=False),
                       "Thumbnail dựng trong lượt Viết Title trước khi tách thành nút riêng.", r.get("session_id"),
                       r.get("session_cost_usd"), r["created_at"], r.get("started_at"), r.get("finished_at")))
            n += 1
    return n


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
        try:
            if (n := import_legacy_thumbs()):
                log.info("imported %d thumbnail mocks from title runs", n)
        except Exception as e:  # noqa: BLE001
            log.warning("legacy thumbnail import failed: %s", e)
        self.thread.start()
        log.info("title worker started (%d queued)", len(self.queue))

    def _push(self, run_id: int) -> int:
        with self.cv:
            self.queue.append(run_id)
            self.cv.notify()
        return len(self.queue) - 1 + (1 if self.current else 0)

    def _busy(self, segment_id: int) -> dict | None:
        return db.row("SELECT id, status, kind FROM segment_titles WHERE segment_id=? AND status IN ('queued','running')",
                      (segment_id,))

    def enqueue_thumb(self, segment_id: int, request: str | None = None, model: str | None = None) -> dict:
        """"Tạo thumbnail": a new thumbnail version from the current title result (+ the user's wish, if any)."""
        seg = db.row("SELECT id, kind, start_sec FROM segments WHERE id=?", (segment_id,))
        if not seg or seg["kind"] != "highlight" or seg["start_sec"] is None:
            return {"error": "chỉ tạo thumbnail cho đoạn highlight có timestamp"}
        if (busy := self._busy(segment_id)):
            return {"error": "đoạn này đang có lượt " + ("thumbnail" if busy["kind"] == "thumb" else "viết title") +
                             (" chạy" if busy["status"] == "running" else " chờ") + ", đợi xong rồi bấm lại"}
        with db.tx() as c:
            c.execute("INSERT INTO segment_titles(segment_id, kind, skill, model, effort, status, progress_msg, created_at, "
                      "user_message) VALUES(?,?,?,?,?,?,?,?,?)",
                      (segment_id, "thumb", _segment_title_skill(segment_id), thumb_model(model),
                       db.get_setting("claude_effort_title"), "queued", "đang chờ tới lượt", now_iso(),
                       (request or "").strip() or None))
            run_id = c.execute("SELECT last_insert_rowid()").fetchone()[0]
        ahead = self._push(run_id)
        return {"run_id": run_id, "message": "đã xếp tạo thumbnail" + (f", còn {ahead} lượt trước" if ahead else "")}

    def enqueue_thumb_chat(self, segment_id: int, message: str, approve: bool = False, run_id: int | None = None) -> dict:
        """Edit (a new version) or approve one thumbnail version: `run_id` picks it, else the latest finished one."""
        if approve:
            message = APPROVE_MSG
        elif message.strip() == APPROVE_MSG:
            return {"error": "dùng nút Duyệt để lưu lên Canva"}
        if (busy := self._busy(segment_id)):
            return {"error": "đoạn này đang có lượt " + ("thumbnail" if busy["kind"] == "thumb" else "viết title") +
                             (" chạy" if busy["status"] == "running" else " chờ") + ", đợi xong rồi nhắn tiếp"}
        q = "SELECT * FROM segment_titles WHERE segment_id=? AND kind='thumb' AND status='done'"
        parent = db.row(q + " AND id=?", (segment_id, run_id)) if run_id else db.row(q + " ORDER BY id DESC LIMIT 1",
                                                                                    (segment_id,))
        if not parent:
            return {"error": "chưa có bản thumbnail nào, bấm Tạo thumbnail trước"}
        with db.tx() as c:
            c.execute("INSERT INTO segment_titles(segment_id, kind, skill, model, effort, status, progress_msg, created_at, "
                      "parent_id, user_message) VALUES(?,?,?,?,?,?,?,?,?,?)",
                      (segment_id, "thumb", parent["skill"], thumb_model(parent["model"]), parent["effort"], "queued",
                       "đang chờ tới lượt", now_iso(), parent["id"], message.strip()))
            new_id = c.execute("SELECT last_insert_rowid()").fetchone()[0]
        ahead = self._push(new_id)
        return {"run_id": new_id, "message": ("đã gửi duyệt bản #%d" % parent["id"] if approve else "đã gửi chỉnh thumbnail")
                + (f", còn {ahead} lượt trước" if ahead else "")}

    def enqueue(self, segment_id: int, focus: str | None = None, model: str | None = None) -> dict:
        """model: picked next to the button for this run only; None = the Settings default."""
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
            c.execute("INSERT INTO segment_titles(segment_id, skill, model, effort, status, progress_msg, created_at, focus) "
                      "VALUES(?,?,?,?,?,?,?,?)",
                      (segment_id, _segment_title_skill(segment_id), model or db.get_setting("claude_model_title"),
                       db.get_setting("claude_effort_title"), "queued", "đang chờ tới lượt", now_iso(), focus))
            run_id = c.execute("SELECT last_insert_rowid()").fetchone()[0]
        with self.cv:
            self.queue.append(run_id)
            self.cv.notify()
        ahead = len(self.queue) - 1 + (1 if self.current else 0)
        return {"run_id": run_id, "message": "đã xếp vào hàng đợi viết title" + (f", còn {ahead} đoạn trước" if ahead else "")}

    def enqueue_chat(self, segment_id: int, message: str, approve: bool = False) -> dict:
        """Queue a chat turn that adjusts the latest finished title result of the segment (approve: see
        enqueue_thumb_chat, kept for old callers)."""
        if approve:
            return self.enqueue_thumb_chat(segment_id, "", approve=True)
        if message.strip() == APPROVE_MSG:
            return {"error": "dùng nút Duyệt thumbnail để lưu lên Canva"}
        busy = db.row("SELECT id, status FROM segment_titles WHERE segment_id=? AND status IN ('queued','running')",
                      (segment_id,))
        if busy:
            return {"error": "Claude đang " + ("viết" if busy["status"] == "running" else "chờ tới lượt") +
                             " cho đoạn này, đợi xong rồi nhắn tiếp"}
        parent = db.row(f"SELECT * FROM segment_titles WHERE segment_id=? AND status='done' AND {TITLE_KIND} "
                        "ORDER BY id DESC LIMIT 1", (segment_id,))
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

    @staticmethod
    def _announce_failure(run_id: int, msg: str) -> None:
        try:
            from .orchestrator import ep_label, ep_link
            r = db.row("SELECT t.kind, t.user_message, s.id, s.rank, s.title, s.episode_id FROM segment_titles t "
                       "JOIN segments s ON s.id=t.segment_id WHERE t.id=?", (run_id,))
            if not r:
                return
            what = ("Duyệt thumbnail" if r["user_message"] == APPROVE_MSG else "Thumbnail") if r["kind"] == "thumb" \
                else "Viết title"
            notify.notify("error", f"{what} lỗi: {_seg_where(r)}", f"{ep_label(r['episode_id'])} · {msg}",
                          ep_link(r["episode_id"], r["id"]))
        except Exception as e:  # noqa: BLE001
            log.warning("title failure notification: %s", e)

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
                if run_id not in self.cancelled:
                    self._announce_failure(run_id, msg)
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
    for key in ("description", "timestamps", "tags", "thumbnail", "image_prompt", "recommended_title", "core_keyword",
                "thumb_mock", "thumbnail_path", "canva_edit_url", "check_back", "focus_hook_result"):
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
    current "Viết Title" run (`thread`), the full skill answer of the run the shown result descends from, and
    `history`: every earlier "Viết Title" run (newest first) with the last finished state of its chain, so runs
    made with different models stay side by side for comparison."""
    out: dict[int, dict] = {}
    rows = db.rows("""SELECT t.* FROM segment_titles t JOIN segments s ON s.id=t.segment_id
                      WHERE s.episode_id=? AND COALESCE(t.kind,'title')='title' ORDER BY t.id""", (episode_id,))
    by_id = {r["id"]: r for r in rows}
    for r in rows:
        d = out.setdefault(r["segment_id"], {"latest": None, "done": None, "thread": [], "full_md": None,
                                             "history": []})
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
        shown_root = _root_id(d["done"], by_id) if d["done"] else None
        for root in reversed([r for r in rows if r["segment_id"] == seg_id and not r.get("parent_id")]):
            if root["id"] == shown_root:
                continue
            last = None
            for r in rows:
                if r["segment_id"] == seg_id and r["status"] == "done" and _root_id(r, by_id) == root["id"]:
                    last = r
            if not last:
                continue
            try:
                data = normalize(json.loads(last["output_json"])) if last.get("output_json") else {}
            except ValueError:
                data = {}
            d["history"].append({"root": root, "run": last, "data": data,
                                 "edits": sum(1 for r in rows if r.get("parent_id") and r["status"] == "done"
                                              and _root_id(r, by_id) == root["id"])})
    return out


def thumbs_for_episode(episode_id: str) -> dict[int, dict]:
    """Per segment, for the Thumbnail section: `latest` thumbnail run (any status), `current` = newest finished
    version, `versions` = every finished version newest first (each with its own folder and mock), and `chat` = the
    user's messages with the outcome of each turn (edits and approvals)."""
    out: dict[int, dict] = {}
    rows = db.rows("""SELECT t.* FROM segment_titles t JOIN segments s ON s.id=t.segment_id
                      WHERE s.episode_id=? AND t.kind='thumb' ORDER BY t.id""", (episode_id,))
    for r in rows:
        d = out.setdefault(r["segment_id"], {"latest": None, "current": None, "versions": [], "chat": []})
        d["latest"] = r
        r["data"] = normalize(_json_of(r))
        r["approve"] = r.get("user_message") == APPROVE_MSG
        if r["status"] == "done":
            d["versions"].insert(0, r)
        if r.get("parent_id") or (r.get("user_message") and r["status"] != "done"):
            d["chat"].append(r)
    for d in out.values():
        d["current"] = d["versions"][0] if d["versions"] else None
    return out
