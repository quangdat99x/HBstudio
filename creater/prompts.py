"""Prompts of the Claude turns. The instructions stay thin on purpose: the workflow itself lives in the rulebook
(section 2), so improving the rulebook improves the workflow without touching code."""
from __future__ import annotations

import json

from . import config, db, workflow
from .store import project_dir, rules_path, steps

STEP_LABELS = {s.key: f"▶ Bước {s.num} · {s.name}" for s in workflow.STEPS}


def _paths(p: dict) -> list[str]:
    d = project_dir(p)
    lines = [
        f'- Thư mục dự án (thư mục làm việc của bạn): "{d}" (đường dẫn có thể có dấu cách: luôn đặt trong ngoặc kép).',
        "  · project.json: mô tả dự án, app ghi · sources/: tư liệu người dùng đưa vào (links.txt là danh sách link)",
        "  · 1_script/ 2_cast/ 3_scenes/ 4_images/ 5_footage/ 6_render/: kết quả từng bước (lược đồ mục 11)",
        "  · 2_cast/choices.json (ứng viên người dùng chọn) và 5_footage/approvals.json (footage người dùng duyệt): app ghi, bạn chỉ đọc",
        "  · film/: dự án Remotion app dựng từ engine ở bước 4 (đọc film/ENGINE.md trước khi code) · out/: bản render · notes/: credits.json, sources.md",
        f'- Bộ quy tắc: "{rules_path()}"',
        f'- Engine gốc (chỉ đọc, không sửa): "{config.ENGINE_DIR}" · phim mẫu: D:\\VideoLab\\watchers-v2 (ảnh Soul/Nano Banana), '
        "D:\\VideoLab\\watchers-gpt (cùng phim, ảnh GPT Image 2.5)",
        "- ffmpeg/ffprobe: biến môi trường FFMPEG và FFPROBE (các script trong film/scripts tự dùng).",
        '- Tách nền trên máy (0 credit): "$BGREMOVE_PY" scripts/cutout.py ... chạy trong film/ (mục 3).',
        '- Whisper (lời dẫn, kiểm tra giọng): "$WHISPER_PY" (python có faster-whisper), xem film/ENGINE.md mục Narration.',
        "- Higgsfield: các tool mcp__claude_ai_HF__* (balance, generate_image, show_generations, media_upload, media_confirm, "
        "generate_audio, list_voices, transactions...). Tìm schema bằng ToolSearch khi cần. Mẹo dùng ở mục 3.",
    ]
    if p.get("use_jre"):
        py, hldb = db.get_setting("jre_python"), db.get_setting("jre_hldb")
        lines.append(f'- Kho highlight JRE (nguồn tư liệu của dự án này, chỉ đọc): "{py}" -X utf8 "{hldb}" search "<từ khóa tiếng Anh>" --json '
                     f'|  ... show <segment_id> --json  |  ... episode <EPISODE_ID> --json')
    return lines


def _brief(p: dict) -> list[str]:
    return [
        f"- Tên phim: {p['title']}",
        f"- Chủ đề: {p['topic']}",
        f"- Yêu cầu riêng của người dùng: {p.get('brief') or '(không có)'}",
        f"- Ngôn ngữ trên phim và lời dẫn: {p.get('language') or 'en'} · khán giả: {p.get('audience') or '(chưa ghi)'}",
        f"- Phong cách hình ảnh: {p.get('style') or '(chưa chốt: đề xuất ở bước 1)'}",
        f"- Định dạng: {p.get('format') or '16:9'} · thời lượng mục tiêu: {p.get('target_sec') or 'tự đề xuất'} giây · "
        f"ngân sách credit Higgsfield: {p.get('credit_budget') or 0:g}",
        f"- Giọng đọc mặc định: {db.get_setting('voice_name')} ({db.get_setting('voice_id')})",
        "- Chế độ: " + ("TỰ CHẠY (không dừng ở cổng duyệt, app tự duyệt khi kết quả đủ)" if p.get("auto_advance")
                        else "DUYỆT TỪNG BƯỚC (người dùng bấm Duyệt trên app trước khi sang bước sau)"),
    ]


_RUN_RULES = [
    "LUẬT CHẠY TỰ ĐỘNG (app gọi bạn headless, người dùng đọc câu trả lời trong khung chat của dự án):",
    "1. Không chờ người dùng giữa chừng. Làm hết phần làm được, kết thúc lượt bằng báo cáo đúng mục 10 của bộ quy tắc "
    "(tiếng Việt, ngắn, có bằng chứng, credit đã tiêu, câu hỏi nếu cần).",
    "2. Chỉ ghi file trong thư mục dự án, và ghi RULEBOOK.md khi cần cập nhật quy tắc. Không sửa mã nguồn của app "
    "(E:\\Creater Vid) hay engine gốc, không xóa gì ngoài thư mục dự án, không cài gói npm/pip toàn cục.",
    "3. Mỗi bước chỉ làm việc của bước đó (mục 2). Không làm trước bước sau khi người dùng chưa bảo.",
    "4. Các file JSON phải là JSON hợp lệ, UTF-8, đúng lược đồ mục 11: app đọc chúng để hiển thị và kiểm tra.",
    "5. Lệnh dài (render, stills) cứ chạy bình thường; mỗi lệnh một lần gọi công cụ.",
    "6. Cập nhật quy tắc theo mục 12 khi người dùng yêu cầu, hoặc khi một góp ý của họ là nguyên tắc chung cho mọi phim "
    "(nói rõ đã thêm quy tắc gì). App tự lưu phiên bản mới.",
    "7. Mỗi lần tạo ảnh, giọng đọc hay video trên Higgsfield: ghi vào notes/credits.json (mục 11.7).",
    "8. Không tải file từ web khi người dùng chưa duyệt (5_footage/approvals.json hoặc lời duyệt trong chat), mục 1.9.",
]


def context_prompt(p: dict, rules: dict) -> str:
    """First turn of a project's session (or a new session when the old one is gone)."""
    return "\n".join([
        "Bạn là đạo diễn kiêm kỹ sư dựng phim tài liệu của Creater Vid, một app làm phim tài liệu theo quy trình 6 bước "
        "(kịch bản → tuyển nhân vật → phân cảnh & bối cảnh → render hình ảnh → footage & âm thanh → dựng & render). "
        "Người dùng (xưng tao/mày) điều khiển từng bước bằng nút trên app và nhắn bạn trong khung chat của dự án. "
        "Toàn bộ dự án này là một cuộc trò chuyện liên tục với bạn.",
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
    lines = ["TRẠNG THÁI CÁC BƯỚC:"]
    d = project_dir(p)
    for r in steps(p):
        st = r["meta"]
        _, summary = workflow.check(st.key, d, p)
        lines.append(f"  {st.num}. {st.name} [{st.key}]: {r['label']}" + (f" · {summary}" if summary else "")
                     + (" · ⚠ bước trước đã đổi sau khi bước này chạy" if r.get("stale") else ""))
    film = d / "film" / "src" / "index.ts"
    lines.append("  film/: " + ("đã dựng khung" if film.exists() else "chưa có"))
    return "\n".join(lines)


def _step_block(step_key: str, p: dict) -> list[str]:
    st = workflow.BY_KEY[step_key]
    lines = [
        STEP_LABELS[step_key].upper(),
        f"Làm đúng mục {st.rule} của bộ quy tắc. Mục tiêu: {st.goal}",
        "Đầu ra bắt buộc: " + ", ".join(st.outputs) + " (lược đồ mục 11). App kiểm tra các file này sau lượt.",
    ]
    if step_key == "script":
        src = project_dir(p) / "sources"
        files = [f.name for f in src.iterdir()] if src.exists() else []
        lines.append("Tư liệu người dùng trong sources/: " + (", ".join(files[:40]) if files else "(chưa có, tự nghiên cứu trên web)"))
        if p.get("use_jre"):
            lines.append("Dự án bật kho highlight JRE: tìm trích đoạn bằng hldb (đường dẫn ở trên), trích nguyên văn transcript.")
    elif step_key == "cast":
        lines.append("Đầu vào: 1_script/script.json, 1_script/sources.json. Ảnh thử vai lưu 2_cast/casting/.")
    elif step_key == "scenes":
        lines.append("Đầu vào: script.json, cast.json và 2_cast/choices.json (ứng viên người dùng đã chọn).")
    elif step_key == "images":
        lines.append("App đã dựng khung film/ từ engine (node_modules là liên kết dùng chung: không npm install, không bao giờ xóa). "
                     "Đầu vào: 3_scenes/scenes.json (danh sách assets đã duyệt), 2_cast/choices.json.")
    elif step_key == "footage":
        lines.append("Đầu vào: footage_needs trong 3_scenes/scenes.json, 5_footage/approvals.json (quyết định của người dùng), "
                     "script.json (lời dẫn).")
    elif step_key == "render":
        lines.append("Đầu vào: mọi kết quả bước 1–5. Render out/<slug>_v<N>.mp4, không ghi đè bản cũ.")
    if p.get("auto_advance"):
        lines.append("Dự án ở chế độ TỰ CHẠY: không dừng ở cổng duyệt, làm trọn bước rồi báo cáo.")
    else:
        lines.append("Kết thúc bằng báo cáo và những gì người dùng cần quyết ở cổng duyệt (app có nút Duyệt).")
    return lines


def turn_prompt(kind: str, step: str | None, p: dict, user_text: str, *, rules_note: str = "") -> str:
    lines = []
    if rules_note:
        lines += [rules_note, ""]
    lines += [state_snapshot(p), ""]
    if kind == "step" and step in workflow.BY_KEY:
        lines += _step_block(step, p)
        if user_text and user_text != STEP_LABELS[step]:
            lines += ["", "Người dùng ghi thêm:", '"""', user_text.strip(), '"""']
    else:
        where = f" (đang xem bước {workflow.BY_KEY[step].num} · {workflow.BY_KEY[step].name})" if step in workflow.BY_KEY else ""
        lines += [
            f"Người dùng nhắn{where}:",
            '"""', user_text.strip(), '"""',
            "",
            "Làm theo tin nhắn theo mục 2.7 của bộ quy tắc: góp ý sửa thì sửa đúng file của bước liên quan và kiểm lại; "
            "thay đổi ảnh hưởng các bước sau thì nói rõ cần làm lại gì và tốn bao nhiêu, chưa tự làm lại khi chưa được bảo. "
            "Yêu cầu cập nhật quy tắc thì sửa RULEBOOK.md theo mục 12. Chỉ hỏi thì trả lời, không sửa file.",
        ]
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


def hf_probe_prompt() -> str:
    return ("Call the Higgsfield tool mcp__claude_ai_HF__balance (load it with ToolSearch first if needed). "
            "Reply with one line of JSON only, no other text: "
            '{"credits": <number>, "plan": "<subscription plan type>"}. '
            'If the tool is not available, reply {"error": "<why>"}.')


def parse_json_line(text: str) -> dict:
    text = (text or "").strip()
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        return {}
    try:
        data = json.loads(text[start:end + 1])
        return data if isinstance(data, dict) else {}
    except ValueError:
        return {}
