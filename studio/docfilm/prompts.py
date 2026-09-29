"""Prompts of the documentary turns. The instructions stay thin on purpose: the workflow itself lives in
the rulebook (section 2), so improving the rulebook improves the workflow without touching code."""
from __future__ import annotations

import json
import sys

from .. import config
from .store import artifacts, project_dir, rules_path

STEP_LABELS = {
    "research": "▶ Bước 1 · Tìm đoạn đắt giá trong kho",
    "script": "▶ Bước 2 · Viết kịch bản",
    "build": "▶ Bước 3 · Dựng phim",
}


def _paths(p: dict) -> list[str]:
    d = project_dir(p)
    py = sys.executable
    hldb = config.BASE_DIR / "hldb.py"
    return [
        f"- Thư mục dự án (thư mục làm việc của bạn): {d}",
        f"  · project.json: mô tả dự án · research/pool.json, research/pool.md, research/transcripts/<segment_id>.txt: Studio tạo",
        "  · research/selection.json + selection.md: bạn viết ở bước 1 · script/script.json + script.md: bước 2",
        f"  · film/: dự án Remotion dựng từ engine (đọc film/ENGINE.md trước khi code) · out/: bản render + out/review/ · notes/: ghi chú, notes/credits.json",
        f"- Bộ quy tắc: {rules_path()}",
        f'- Kho highlight: "{py}" -X utf8 "{hldb}" search "<từ khóa>" --json  |  ... show <segment_id> --json  |  ... episode <EPISODE_ID> --json',
        "- ffmpeg/ffprobe: biến môi trường FFMPEG và FFPROBE (các script trong film/scripts đã tự dùng).",
        '- Tách nền trên máy (0 credit): "$BGREMOVE_PY" scripts/cutout.py ... (mục 3 của bộ quy tắc, film/ENGINE.md).',
        '- Lời dẫn: "$WHISPER_PY" scripts/voice-build.py (python có faster-whisper), xem film/ENGINE.md mục Narration.',
        "- Higgsfield: các tool mcp__claude_ai_HF__* (balance, generate_image, generate_image_batch, jobs_wait, models_explore, "
        "create_project, generate_audio + list_voices + show_generations cho lời dẫn ElevenLabs v4, transactions...). "
        "Tìm schema bằng ToolSearch khi cần.",
    ]


def _brief(p: dict) -> list[str]:
    return [
        f"- Tên phim: {p['title']}",
        f"- Chủ đề: {p['topic']}",
        f"- Yêu cầu riêng của người dùng: {p.get('brief') or '(không có)'}",
        f"- Định dạng: {p.get('format') or '16:9'} · thời lượng mục tiêu: {p.get('target_sec') or 'tự đề xuất'} giây · "
        f"ngân sách credit Higgsfield: {p.get('credit_budget') or 0:g}",
    ]


_RUN_RULES = [
    "LUẬT CHẠY TỰ ĐỘNG (Studio gọi bạn headless, người dùng đọc câu trả lời trong khung chat của dự án):",
    "1. Không chờ người dùng giữa chừng. Làm hết phần làm được, kết thúc lượt bằng báo cáo đúng mục 10 của bộ quy tắc "
    "(tiếng Việt, ngắn, có bằng chứng, credit đã tiêu, câu hỏi nếu cần).",
    "2. Chỉ ghi file trong thư mục dự án, và ghi RULEBOOK.md khi cần cập nhật quy tắc. Không sửa mã nguồn JRE Studio trong "
    "E:\\DataBase, không xóa gì ngoài thư mục dự án, không cài gói npm/pip toàn cục.",
    "3. Lệnh dài trong film/ (render, stills) cứ chạy bình thường; mỗi lệnh một lần gọi công cụ.",
    "4. Cập nhật quy tắc theo mục 12 khi người dùng yêu cầu, hoặc khi một góp ý của họ là nguyên tắc chung cho mọi phim "
    "(nói rõ trong câu trả lời là đã thêm quy tắc gì). Studio tự lưu phiên bản mới.",
    "5. Mỗi lần tạo ảnh hay giọng đọc trên Higgsfield: ghi vào notes/credits.json (số dư trước/sau, từng lần tạo).",
    "6. Không tải file từ web (clip lửa, khói...) khi người dùng chưa duyệt trong chat: liệt kê tên, nguồn, dung lượng, "
    "giấy phép rồi kết thúc lượt để hỏi (mục 1.9).",
]


def context_prompt(p: dict, rules: dict) -> str:
    """First turn of a project's session (or a new session when the old one is gone)."""
    return "\n".join([
        "Bạn là đạo diễn kiêm kỹ sư dựng phim tài liệu của JRE Studio. Người dùng (chủ kênh JRE highlights, xưng tao/mày) "
        "làm việc với bạn qua tab \"Make Documentary Film\". Toàn bộ dự án này là một cuộc trò chuyện liên tục với bạn.",
        "",
        f'<rulebook version="{rules["version"]}" path="{rules_path()}">',
        rules["body"].strip(),
        "</rulebook>",
        "",
        "DỰ ÁN",
        *_brief(p),
        "",
        "ĐƯỜNG DẪN VÀ CÔNG CỤ",
        *_paths(p),
        "",
        *_RUN_RULES,
        "",
    ])


def state_snapshot(p: dict) -> str:
    a = artifacts(p, light=True)
    parts = [f"pool: {a['pool_count']} ứng viên" if a["pool_count"] else "pool: chưa có",
             "selection.json: có" if a["has_selection"] else "selection.json: chưa có",
             "script.json: có" if a["has_script"] else "script.json: chưa có"]
    film = project_dir(p) / "film" / "src" / "index.ts"
    parts.append("film/: đã dựng khung" if film.exists() else "film/: chưa có")
    if a["videos"]:
        parts.append("bản render: " + ", ".join(v["path"] for v in a["videos"][:4]))
    return "TRẠNG THÁI DỰ ÁN: " + " · ".join(parts)


def turn_prompt(kind: str, p: dict, user_text: str, *, pool: dict | None = None, rules_note: str = "") -> str:
    lines = []
    if rules_note:
        lines += [rules_note, ""]
    lines += [state_snapshot(p), ""]
    if kind == "research":
        n = len((pool or {}).get("segments") or [])
        lines += [
            STEP_LABELS["research"].upper(),
            f"Studio vừa tạo research/pool.json và research/pool.md ({n} ứng viên cho chủ đề \"{p['topic']}\") cùng transcript "
            "từng đoạn trong research/transcripts/. Làm đúng mục 2.1 của bộ quy tắc: đọc pool, đọc transcript các đoạn hứa hẹn, "
            "tìm thêm trong kho nếu thiếu, chọn đoạn và câu trích nguyên văn, kiểm chứng bằng python, ghi research/selection.json "
            "và research/selection.md, rồi báo cáo kèm 2-3 hướng dàn ý để người dùng chọn.",
        ]
        if n == 0:
            lines.append("Pool rỗng: tự tìm trong kho bằng hldb với các từ khóa gần nghĩa (tiếng Anh) trước khi kết luận.")
    elif kind == "script":
        lines += [
            STEP_LABELS["script"].upper(),
            "Làm đúng mục 2.2 của bộ quy tắc dựa trên research/selection.json và những gì người dùng đã chọn trong chat. "
            "Ghi script/script.json và script/script.md, kiểm chứng nguyên văn từng câu trích bằng python, ước tính credit "
            "cho danh sách tài sản, rồi báo cáo và hỏi duyệt (cổng duyệt của mục 2.2).",
        ]
    elif kind == "build":
        lines += [
            STEP_LABELS["build"].upper(),
            f"Studio đã dựng khung film/ từ engine (node_modules dùng chung). Làm đúng mục 2.3 của bộ quy tắc theo "
            f"script/script.json: tài sản Higgsfield trong ngân sách {p.get('credit_budget') or 0:g} credit (tách nền trên máy), "
            "lời dẫn ElevenLabs v4 (mục 8.4), clip trích, cảnh, hiệu ứng lửa/khói/ánh sáng (mục 5.8-5.12), âm thanh, "
            "soát ảnh tĩnh, render out/<slug>_v<N>.mp4, QA bằng scripts/qa.mjs. Nếu kịch bản chưa được người dùng duyệt trong chat "
            "thì dừng ở cổng duyệt và hỏi.",
        ]
    if user_text and kind == "chat":
        lines += [
            "Người dùng nhắn:",
            '"""', user_text.strip(), '"""',
            "",
            "Làm theo tin nhắn. Nếu là góp ý sửa phim: mục 2.4 (sửa, soát đúng chỗ, render bản mới, báo cáo bằng chứng). "
            "Nếu yêu cầu cập nhật quy tắc hoặc quy trình: sửa RULEBOOK.md theo mục 12. Nếu chỉ hỏi thì trả lời, không sửa file.",
        ]
    elif user_text and user_text not in STEP_LABELS.values():
        lines += ["", "Người dùng ghi thêm:", '"""', user_text.strip(), '"""']
    return "\n".join(lines)


def seed_history(msgs: list[dict], limit_chars: int = 12000) -> str:
    """When the old session is gone: the recent conversation, newest last, as plain text."""
    out, total = [], 0
    for m in reversed(msgs):
        if m["role"] == "assistant" and m["status"] != "done":
            continue
        text = (m.get("content") or "").strip()
        if not text:
            continue
        chunk = f"[{'Người dùng' if m['role'] == 'user' else 'Bạn'}] {text}"
        if total + len(chunk) > limit_chars:
            break
        out.append(chunk)
        total += len(chunk)
    if not out:
        return ""
    return "\n".join(["LỊCH SỬ TRÒ CHUYỆN GẦN ĐÂY (phiên cũ không còn, đây là bản tóm tắt để bạn nối tiếp):",
                      *reversed(out), ""])


def credits_note(p: dict) -> str:
    try:
        data = json.loads((project_dir(p) / "notes" / "credits.json").read_text(encoding="utf-8"))
        return json.dumps(data, ensure_ascii=False)[:600]
    except Exception:  # noqa: BLE001
        return ""
