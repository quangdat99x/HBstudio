"""Prompts of the Claude turns. The instructions stay thin on purpose: the workflow itself lives in the rulebook of the
project's kind (section 2), so improving a rulebook improves its workflow without touching code.

Documentaries and news videos are two desks: each turn gets only its own kind's role, tools, run rules and rulebook.
"""
from __future__ import annotations

from . import config, db, providers, workflow
from .store import kind_of, project_dir, rules_path, steps

# where the things the prompts point at live in each rulebook (the two books are numbered independently)
SECTIONS = {
    "doc": {"steps": "2", "chat": "2.7", "paid": "3", "report": "10", "schema": "11", "log": "12"},
    "news": {"steps": "2", "chat": "2.7", "paid": "3", "report": "8", "schema": "9", "log": "10"},
}


def step_label(p: dict, key: str) -> str:
    st = workflow.flow(p).by_key[key]
    return f"▶ Bước {st.num} · {st.name}"


def _paths(p: dict) -> list[str]:
    kind, d = kind_of(p), project_dir(p)
    sec = SECTIONS[kind]
    lines = [
        f'- Thư mục dự án (thư mục làm việc của bạn): "{d}" (đường dẫn có thể có dấu cách: luôn đặt trong ngoặc kép).',
    ]
    if kind == "news":
        lines += [
            "  · project.json: mô tả dự án, app ghi · sources/: các tin đã chọn (news_NN_*.md toàn văn, news.json, links.txt; "
            "digest.md với Điểm tin 24h), media.json + media/ (ảnh, video thật của các tin, app đã tải)",
            "  · 1_script/ 3_scenes/ 4_images/ 5_footage/ 6_render/ 7_metadata/: kết quả các bước "
            f"(lược đồ mục {sec['schema']}; quy trình tin tức không có bước tuyển nhân vật, không có 2_cast/)",
        ]
    else:
        lines += [
            "  · project.json: mô tả dự án, app ghi · sources/: tư liệu người dùng đưa vào (links.txt là danh sách link)",
            f"  · 1_script/ 2_cast/ 3_scenes/ 4_images/ 5_footage/ 6_render/ 7_metadata/: kết quả từng bước (lược đồ mục {sec['schema']})",
            "  · 2_cast/choices.json (ứng viên người dùng chọn) và 5_footage/approvals.json (footage người dùng duyệt): app ghi, bạn chỉ đọc",
        ]
    lines += [
        "  · film/: dự án Remotion app dựng từ engine (đọc film/ENGINE.md trước khi code) · out/: bản render "
        "· notes/: costs.json (gen.py ghi), sources.md",
        f'- Bộ quy tắc {config.KINDS[kind]["label"].lower()} (của riêng loại video này): "{rules_path(kind)}"',
        f'- Engine gốc (chỉ đọc, không sửa): "{config.ENGINE_DIR}"'
        + (" · phim mẫu: K:\\VideoLab\\watchers-v2, K:\\VideoLab\\watchers-gpt (cùng phim, hai bộ ảnh)" if kind == "doc" else ""),
        "- ffmpeg/ffprobe: biến môi trường FFMPEG và FFPROBE (các script trong film/scripts tự dùng).",
        "- Render Remotion: luôn thêm `--concurrency=$RENDER_CONCURRENCY` (số tab Chrome theo ngân sách CPU của máy, đã "
        "chừa phần cho người dùng); mọi lệnh nặng tự chạy ở độ ưu tiên thấp, không cần chỉnh.",
        '- Whisper (lời dẫn, kiểm tra giọng): "$WHISPER_PY" (python có faster-whisper), xem film/ENGINE.md mục Narration. '
        'Chạy trên GPU: `WhisperModel(..., device="cuda", compute_type="float16")` (PATH đã có DLL CUDA). Báo lỗi '
        'cublas/cudnn cho người dùng thay vì lặng lẽ chuyển sang CPU.',
        '- Tạo nguyên liệu trả phí (giọng đọc ElevenLabs; ảnh, video fal.ai): "$CREATER_PYTHON" "$GEN_PY" <lệnh> '
        f'(mục {sec["paid"]}; "$CREATER_PYTHON" "$GEN_PY" <lệnh> --help). Lệnh: check, voices, tts, sfx, image, video, run, '
        "schema, models, price, cost. gen.py tự ghi chi phí vào notes/costs.json và từ chối khi vượt ngân sách.",
    ]
    if kind == "news":
        lines.append('- Che mờ, tách người trên máy (miễn phí, GPU): "$BGREMOVE_PY" scripts/cutout.py ... chạy trong film/.')
        return lines
    lines += [
        '- Tách nền trên máy (miễn phí): "$BGREMOVE_PY" scripts/cutout.py ... chạy trong film/ (mục 3).',
        '- Ảnh tĩnh → clip camera 3D (miễn phí, GPU của máy): "$BGREMOVE_PY" "$PARALLAX_PY" <ảnh> --out <clip.mp4> '
        "--seconds <s> --move <orbit-right|orbit-left|push-in|pull-out|truck-right|truck-left|crane-up|crane-down|drift> "
        '--subject x,y --size 16:9|9:16, hoặc --batch jobs.json cho nhiều cảnh (mục 4.9; "$BGREMOVE_PY" "$PARALLAX_PY" --help).',
        '- GPT vẽ từng lớp của cảnh xếp lớp: "$CREATER_PYTHON" "$LAYERKIT_PY" 3_scenes/scenes.json [--only sc05] [--redo sc05:mid] '
        "(chạy trong thư mục dự án; mục 4.10).",
    ]
    if p.get("use_jre"):
        py, hldb = db.get_setting("jre_python"), db.get_setting("jre_hldb")
        lines.append(f'- Kho highlight JRE (nguồn tư liệu của dự án này, chỉ đọc): "{py}" -X utf8 "{hldb}" search "<từ khóa tiếng Anh>" --json '
                     f'|  ... show <segment_id> --json  |  ... episode <EPISODE_ID> --json')
    return lines


def _brief(p: dict) -> list[str]:
    kind = kind_of(p)
    voice = providers.voice_for(p.get("language"))
    lines = [
        f"- Tên {'video' if kind == 'news' else 'phim'}: {p['title']}",
        f"- Chủ đề: {p['topic']}",
        f"- Yêu cầu riêng của người dùng: {p.get('brief') or '(không có)'}",
        f"- Ngôn ngữ trên hình và lời dẫn: {p.get('language') or 'en'} · khán giả: {p.get('audience') or '(chưa ghi)'}",
    ]
    if kind == "doc":
        lines.append(f"- Phong cách hình ảnh: {p.get('style') or '(chưa chốt: đề xuất ở bước 1)'}")
    lines += [
        f"- Định dạng: {p.get('format') or '16:9'} · thời lượng TỐI THIỂU: {p.get('target_sec') or 'tự đề xuất'} giây "
        "(dài hơn tuỳ nội dung để kịch bản hay nhất, không độn; mục 2.1) · "
        f"ngân sách nguyên liệu (giọng, ảnh, video): ${p.get('budget_usd') or 0:g}",
        f"- Giọng đọc mặc định cho ngôn ngữ này: {voice.get('name') or '(chưa chọn)'} ({voice.get('id') or '-'}) · "
        f"model giọng {db.get_setting('tts_model')}",
        f"- Model ảnh: chính {db.get_setting('image_model')} · rẻ {db.get_setting('image_model_draft')} · "
        f"sửa ảnh {db.get_setting('image_model_edit')} · video {db.get_setting('video_model')} "
        "(openai:… / google:… = gọi thẳng OpenAI / Google, gemini-web:… = gemini.google.com bằng gói Gemini của "
        "người dùng, $0 nhưng chạy lần lượt từng ảnh, mỗi ảnh khoảng 1–3 phút: KHÔNG chạy song song, gọi Bash với "
        "timeout 600000; còn lại qua fal)",
        "- API key đã có: " + ", ".join(f"{label} {'có' if providers.has_key(k) else 'CHƯA'}" for k, label in
                                        (("elevenlabs_api_key", "ElevenLabs"), ("fal_api_key", "fal"),
                                         ("openai_api_key", "OpenAI"), ("google_api_key", "Google"))),
        "- Chế độ: " + ("TỰ CHẠY (không dừng ở cổng duyệt, app tự duyệt khi kết quả đủ)" if p.get("auto_advance")
                        else "DUYỆT TỪNG BƯỚC (người dùng bấm Duyệt trên app trước khi sang bước sau)"),
    ]
    if kind == "doc":
        lines.append("- Cách dựng hình: " + {
            "fullframe": "ẢNH LIỀN KHỐI → 3D (pipeline fullframe): mỗi cảnh dựng lại là một ảnh hoàn chỉnh có nhân vật, "
                         "biến thành clip camera 3D bằng parallax.py; làm bước 3, 4, 6 theo mục 4.9 của bộ quy tắc",
            "stacked": "XẾP LỚP (pipeline stacked): mỗi cảnh dựng lại chia 2–4 lớp theo độ sâu, GPT vẽ từng lớp riêng "
                       "(layerkit.py), engine xếp lớp và đi camera điện ảnh (LayerScene); làm bước 3, 4, 6 theo mục 4.10",
            "dossier": "HỒ SƠ TƯ LIỆU (pipeline dossier): phim dựng từ ảnh, tài liệu, footage THẬT như vật chứng trên bàn "
                       "(engine src/dossier: DossierScene), highlight và dấu chạy theo lời dẫn; AI chỉ tái hiện cảnh không thể có "
                       "ảnh (xếp lớp, mục 4.10); làm bước 1–6 theo mục 4.11 của bộ quy tắc",
        }.get(p.get("pipeline"), "GHÉP LỚP (pipeline layered): nhân vật tách nền, ghép trên nền vẽ trong engine 3D (mục 4)"))
    return lines


def _run_rules(kind: str) -> list[str]:
    sec = SECTIONS[kind]
    rulebook = config.KINDS[kind]["rules_file"]
    lines = [
        "LUẬT CHẠY TỰ ĐỘNG (app gọi bạn headless, người dùng đọc câu trả lời trong khung chat của dự án):",
        f"1. Không chờ người dùng giữa chừng. Làm hết phần làm được, kết thúc lượt bằng báo cáo đúng mục {sec['report']} của "
        "bộ quy tắc (tiếng Việt, ngắn, có bằng chứng, chi phí $ đã tiêu, câu hỏi nếu cần).",
        f"2. Chỉ ghi file trong thư mục dự án, và ghi {rulebook} khi cần cập nhật quy tắc. Không sửa mã nguồn của app "
        "(E:\\Tool\\Creater Vid) hay engine gốc, không xóa gì ngoài thư mục dự án, không cài gói npm/pip toàn cục. "
        "App có hai bộ quy tắc riêng cho phim tài liệu và video tin tức: chỉ đọc và sửa bộ của dự án này.",
        f"3. Mỗi bước chỉ làm việc của bước đó (mục {sec['steps']}). Không làm trước bước sau khi người dùng chưa bảo.",
        f"4. Các file JSON phải là JSON hợp lệ, UTF-8, đúng lược đồ mục {sec['schema']}: app đọc chúng để hiển thị và kiểm tra.",
        "5. Mỗi lệnh công cụ tối đa 10 phút. Việc dài hơn (render cả phim, parallax batch) chia thành nhiều đoạn và chạy "
        "tuần tự ngay trong lượt (render theo --frames rồi nối, mục 2 của bộ quy tắc). KHÔNG BAO GIỜ kết thúc lượt khi còn "
        "lệnh chạy nền (run_in_background): khi bạn trả lời xong, app coi bước đã xong, không có thông báo nào quay lại, "
        "và tiến trình bỏ lại sẽ chết. Chỉ trả lời khi mọi lệnh đã xong và đầu ra của bước đã ghi.",
        f"6. Cập nhật quy tắc theo mục {sec['log']} khi người dùng yêu cầu, hoặc khi một góp ý của họ là nguyên tắc chung cho "
        "mọi video cùng loại (nói rõ đã thêm quy tắc gì). App tự lưu phiên bản mới.",
        f"7. Giọng đọc, ảnh, video, hiệu ứng âm thanh trả phí chỉ tạo bằng gen.py (mục {sec['paid']}). gen.py báo VƯỢT NGÂN SÁCH "
        "thì dừng phần đó và hỏi người dùng; chỉ dùng --over-budget khi họ đã đồng ý. Thiếu API key (mã thoát 2) thì báo người "
        "dùng điền ở Cài đặt, không tìm cách khác.",
    ]
    if kind == "news":
        lines += [
            "8. Ảnh, video thật của các tin đã chọn là nguyên liệu chính (mục 1.5, 1.7): mục \"downloaded\" trong "
            "sources/media.json (app đã tự duyệt và tải) và ảnh trong thân chính các bài gốc (tự tải, không cần chờ duyệt). "
            "Mục người dùng đã bỏ (rejected) thì không dùng. Ảnh, video ở nơi khác: đề xuất vào 5_footage/footage.json để "
            "người dùng duyệt trước khi tải. Xem kỹ từng file trước khi dùng.",
        ]
    else:
        lines += [
            "8. Không tải file từ web khi người dùng chưa duyệt (5_footage/approvals.json hoặc lời duyệt trong chat), mục 1.9.",
        ]
    return lines


_ROLE = {
    "doc": "Bạn là đạo diễn kiêm kỹ sư dựng phim tài liệu của Creater Vid, mảng PHIM TÀI LIỆU, quy trình 7 bước "
           "(kịch bản → tuyển nhân vật → phân cảnh & bối cảnh → render hình ảnh → footage & âm thanh → dựng & render "
           "→ metadata YouTube).",
    "news": "Bạn là biên tập viên kiêm kỹ sư dựng của Creater Vid, mảng VIDEO TIN TỨC (tin nóng, điểm tin), quy trình "
            "6 bước (kịch bản tin → bảng hình → hình thật → giọng đọc & âm thanh → dựng & render → metadata YouTube). "
            "Video tin tức là một mảng riêng, khác hẳn phim tài liệu: chỉ theo bộ quy tắc tin tức.",
}


def context_prompt(p: dict, rules: dict, *, per_step: bool = False) -> str:
    """First turn of a session: of the project (per_step False), or of one step (per_step True: each step run starts
    a new session, so the earlier steps are known only from their files and the reports seeded after this)."""
    kind = kind_of(p)
    session = ("Mỗi bước chạy trong một phiên mới của bạn: việc các bước trước đã làm nằm trong file kết quả của chúng "
               "(đọc file đầu vào của bước trước khi làm, đừng đoán), báo cáo và góp ý gần đây của người dùng ở phần "
               "LỊCH SỬ bên dưới." if per_step else "Toàn bộ dự án này là một cuộc trò chuyện liên tục với bạn.")
    return "\n".join([
        _ROLE[kind] + " Người dùng (xưng tao/mày) điều khiển từng bước bằng nút trên app và nhắn bạn trong khung chat "
        "của dự án. " + session,
        "",
        f'<rulebook kind="{kind}" version="{rules["num"]}" path="{rules_path(kind)}">',
        rules["body"].strip(),
        "</rulebook>",
        "",
        "DỰ ÁN",
        *_brief(p),
        "",
        "ĐƯỜNG DẪN VÀ CÔNG CỤ",
        *_paths(p),
        "",
        *_run_rules(kind),
        "",
    ])


def rules_changed_note(p: dict, rules: dict) -> str:
    """Told to an ongoing session whose rulebook changed since its last turn."""
    kind = kind_of(p)
    return (f"📘 Bộ quy tắc {config.KINDS[kind]['label'].lower()} đã cập nhật lên v{rules['num']} kể từ lượt trước: đọc lại "
            f"toàn văn \"{rules_path(kind)}\" trước khi làm (thay đổi mới ghi ở mục {SECTIONS[kind]['log']}). Đây là bộ quy "
            "tắc của riêng loại video này; nếu trước đây bạn đọc một file bộ quy tắc khác thì bỏ nó, chỉ dùng file này.")


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


def _doc_step_hints(step_key: str, p: dict) -> list[str]:
    lines = []
    if step_key == "script":
        src = project_dir(p) / "sources"
        files = [f.name for f in src.iterdir()] if src.exists() else []
        lines.append("Tư liệu người dùng trong sources/: " + (", ".join(files[:40]) if files else "(chưa có, tự nghiên cứu trên web)"))
        if p.get("use_jre"):
            lines.append("Dự án bật kho highlight JRE: tìm trích đoạn bằng hldb (đường dẫn ở trên), trích nguyên văn transcript.")
        lines.append("Cuối bước ghi 1_script/blueprint.json (mục 2.1 bước 8, mẫu ở 11.1): bản thiết kế cả phim mà app vẽ thành sơ đồ "
                     "để người dùng duyệt; các id hồi, nhân vật, bằng chứng phải khớp script.json. Phần `tree` (vì sao viết từng hồi, "
                     "từng beat như thế và triển khai ra sao) là phần người dùng soi kỹ nhất: viết thật, cụ thể cho phim này.")
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
    elif step_key == "metadata":
        lines.append("Đầu vào: script.json, sources.json, 6_render/render.json (bản đã duyệt: thời lượng thật, mốc cảnh), "
                     "film/audio/voice (lời dẫn có mốc thời gian cho phụ đề). Làm việc trong thư mục dự án, ghi vào 7_metadata/.")
    if p.get("pipeline") == "fullframe" and step_key in ("scenes", "images", "render"):
        lines.append({
            "scenes": "CÁCH DỰNG HÌNH: ẢNH LIỀN KHỐI → 3D (mục 4.9). Mỗi cảnh dựng lại có MỘT asset kind \"frame\" "
                      "(prompt ảnh hoàn chỉnh có nhân vật, refs = ảnh gốc nhân vật, bố cục nhiều tầng sâu) và khối \"parallax\" "
                      "(move, subject, strength). Không lập nền/biến thể/đạo cụ tách lớp cho các cảnh này.",
            "images": "CÁCH DỰNG HÌNH: ẢNH LIỀN KHỐI → 3D (mục 4.9). Vẽ ảnh gốc nhân vật trước (tham chiếu), rồi mỗi cảnh một "
                      "ảnh frame bằng gen.py image --ref <ảnh gốc của từng nhân vật trong cảnh>, lưu film/assets/frames/<scene>.png. "
                      "Không tách nền. Chạy thử parallax.py cho 2–3 cảnh khó, xem bảng ghép *_contact.jpg.",
            "render": "CÁCH DỰNG HÌNH: ẢNH LIỀN KHỐI → 3D (mục 4.9). Render mọi clip bằng một lệnh "
                      "\"$BGREMOVE_PY\" \"$PARALLAX_PY\" --batch film/public/parallax/jobs.json (clip vào film/public/parallax/), "
                      "soát từng *_contact.jpg, rồi dựng timeline trong engine với clip làm hình nền của cảnh.",
        }[step_key])
    if p.get("pipeline") == "stacked" and step_key in ("scenes", "images", "render"):
        lines.append({
            "scenes": "CÁCH DỰNG HÌNH: XẾP LỚP (mục 4.10). Mỗi cảnh dựng lại có \"layers\" (2–4 lớp xa → gần: name, z mét, prompt, "
                      "refs ảnh gốc nhân vật), \"light\", \"camera\" {move, strength, frame} và \"fx_notes\" (hiệu ứng code đề xuất, "
                      "để trống nếu không cần; không tự làm). Nhân vật luôn cùng lớp với mặt đất họ đứng. Ghi asset kind \"layer\" "
                      "cho mỗi lớp (est_usd) để tính ngân sách.",
            "images": "CÁCH DỰNG HÌNH: XẾP LỚP (mục 4.10). Vẽ ảnh gốc nhân vật nếu chưa có (film/assets/raw/<id>.png), rồi chạy "
                      "\"$CREATER_PYTHON\" \"$LAYERKIT_PY\" 3_scenes/scenes.json. Ghép thử từng cảnh thành bảng 4_images/sheet_layers_*.jpg, "
                      "soát, vẽ lại lớp lỗi bằng --redo <cảnh>:<lớp>. Manifest: kind \"layer\", file = film/public/layers/<cảnh>/<lớp>.png.",
            "render": "CÁCH DỰNG HÌNH: XẾP LỚP (mục 4.10). Mỗi cảnh dựng lại = <LayerScene cfg={layers.json của cảnh} move strength frame /> "
                      "(src/staged/LayerScene.tsx, đã có trong film/). Chỉ thêm hiệu ứng code ở cảnh người dùng đã duyệt fx_notes.",
        }[step_key])
    if p.get("pipeline") == "dossier" and step_key in ("script", "cast", "scenes", "images", "render"):
        lines.append({
            "script": "CÁCH DỰNG HÌNH: HỒ SƠ TƯ LIỆU (mục 4.11). Chọn khung kể (mục 4.11.1: hồ sơ vụ việc hay đường hang thỏ, "
                      "hoặc cổ điển) và ghi \"frame\" trong script.json; mỗi beat ghi \"evidence\": danh từ riêng nào cần bằng chứng thật.",
            "cast": "CÁCH DỰNG HÌNH: HỒ SƠ TƯ LIỆU (mục 4.11). Người thật: depiction archival_photo với ảnh thật có nguồn, giấy phép "
                    "(chưa tải, chỉ ghi link); chỉ vai không thể có ảnh mới thử vai AI.",
            "scenes": "CÁCH DỰNG HÌNH: HỒ SƠ TƯ LIỆU (mục 4.11). Lập \"evidence\" (mọi ảnh, trang, logo, footage thật: link nguồn, "
                      "giấy phép, cụm từ cần highlight) và mỗi cảnh một \"shot\" (photos | doc | board | archive | logo | years) "
                      "hoặc cảnh tái hiện xếp lớp. Duyệt bước 3 = duyệt tải/chụp các bằng chứng trong danh sách.",
            "images": "CÁCH DỰNG HÌNH: HỒ SƠ TƯ LIỆU (mục 4.11). Tải bằng chứng đã duyệt vào film/public/evidence/, chụp trang bằng "
                      "node scripts/pagecap.mjs (trong film/, ra public/docs/<id>.png + .json có toạ độ cụm từ), tách nền chân dung "
                      "bằng cutout.py khi cần; lớp AI cho cảnh tái hiện bằng layerkit. Manifest kind evidence | document | logo.",
            "render": "CÁCH DỰNG HÌNH: HỒ SƠ TƯ LIỆU (mục 4.11). Mỗi cảnh hồ sơ = <DossierScene shot={...} duration scene /> "
                      "(src/dossier, ENGINE.md mục Dossier kit); mốc \"at\" viết theo lời dẫn (\"l12:cụm từ\") để highlight, thẻ, dấu "
                      "khớp chữ. Soát ảnh tĩnh lúc highlight đang quét và lúc thẻ vừa đáp.",
        }[step_key])
    return lines


def _news_step_hints(step_key: str, p: dict) -> list[str]:
    d = project_dir(p)
    digest = (d / "sources" / "digest.md").exists()
    kind_line = ("Kiểu video: ĐIỂM TIN 24H (mục 2.9)." if digest else "Kiểu video: TIN NÓNG (mục 2.8).")
    hints = {
        "script": "Đầu vào: sources/news_*.md (toàn văn từng tin), sources/news.json" + (", sources/digest.md (sự kiện xếp theo "
                  "số nguồn, ★ = trọng tâm)" if digest else "") + ". Kiểm chứng từng tin bằng nguồn gốc (mục 1.2) trước khi viết.",
        "scenes": "Đầu vào: 1_script/script.json, sources/media.json + sources/media/ (ảnh, video thật đã tải), ảnh trong bài gốc. "
                  "Không lập nhân vật, không vẽ bối cảnh: gán hình thật của đúng tin cho từng cảnh (mục 1.7).",
        "images": "App đã dựng khung film/ từ engine (node_modules là liên kết dùng chung: không npm install, không bao giờ xóa). "
                  "Đầu vào: 3_scenes/scenes.json đã duyệt, sources/media/. Manifest ghi kind archival | map | card (ảnh AI: plate). "
                  "Bản đồ: chép bộ mẫu engine/templates/news-map (Map3D.tsx, MapView.tsx, build_maps.py; đọc README.md của nó) "
                  "theo mục 4.4, không tự viết bản đồ mới.",
        "footage": "Đầu vào: script.json (lời dẫn), 3_scenes/scenes.json, 4_images/manifest.json, sources/media.json.",
        "render": "Đầu vào: mọi kết quả bước 1–4. Render out/<slug>_v<N>.mp4, không ghi đè bản cũ.",
        "metadata": "Đầu vào: script.json, sources.json, research.md (phương án tựa, chữ thumbnail), 6_render/render.json (bản đã "
                    "duyệt: mốc từng tin), film/audio/voice (phụ đề). Ghi vào 7_metadata/.",
    }
    return [kind_line, hints[step_key]] if step_key in hints else [kind_line]


def _step_block(step_key: str, p: dict) -> list[str]:
    kind = kind_of(p)
    st = workflow.flow(p).by_key[step_key]
    lines = [
        step_label(p, step_key).upper(),
        f"Làm đúng mục {st.rule} của bộ quy tắc {config.KINDS[kind]['label'].lower()}. Mục tiêu: {st.text(p)['goal']}",
        "Đầu ra bắt buộc: " + ", ".join(st.outputs) + f" (lược đồ mục {SECTIONS[kind]['schema']}). App kiểm tra các file này sau lượt.",
    ]
    lines += _news_step_hints(step_key, p) if kind == "news" else _doc_step_hints(step_key, p)
    if p.get("auto_advance"):
        lines.append("Dự án ở chế độ TỰ CHẠY: không dừng ở cổng duyệt, làm trọn bước rồi báo cáo.")
    else:
        lines.append("Kết thúc bằng báo cáo và những gì người dùng cần quyết ở cổng duyệt (app có nút Duyệt).")
    return lines


def turn_prompt(kind: str, step: str | None, p: dict, user_text: str, *, rules_note: str = "") -> str:
    sec = SECTIONS[kind_of(p)]
    fl = workflow.flow(p)
    lines = []
    if rules_note:
        lines += [rules_note, ""]
    lines += [state_snapshot(p), ""]
    if kind == "step" and step in fl.by_key:
        lines += _step_block(step, p)
        if user_text and user_text != step_label(p, step):
            lines += ["", "Người dùng ghi thêm:", '"""', user_text.strip(), '"""']
    else:
        where = f" (đang xem bước {fl.names()[step]})" if step in fl.by_key else ""
        lines += [
            f"Người dùng nhắn{where}:",
            '"""', user_text.strip(), '"""',
            "",
            f"Làm theo tin nhắn theo mục {sec['chat']} của bộ quy tắc: góp ý sửa thì sửa đúng file của bước liên quan và kiểm lại; "
            "thay đổi ảnh hưởng các bước sau thì nói rõ cần làm lại gì và tốn bao nhiêu, chưa tự làm lại khi chưa được bảo. "
            f"Yêu cầu cập nhật quy tắc thì sửa {config.KINDS[kind_of(p)]['rules_file']} theo mục {sec['log']}. "
            "Chỉ hỏi thì trả lời, không sửa file.",
        ]
    return "\n".join(lines)


def seed_history(msgs: list[dict], limit_chars: int = 12000, *, gone: bool = True) -> str:
    """The recent conversation, newest last, as plain text: when the old session is gone (gone True), or at the start
    of a step's new session (gone False)."""
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
    head = ("LỊCH SỬ TRÒ CHUYỆN GẦN ĐÂY (phiên cũ không còn, đây là bản tóm tắt để bạn nối tiếp):" if gone else
            "LỊCH SỬ TRÒ CHUYỆN GẦN ĐÂY (báo cáo các bước trước và góp ý của người dùng, cũ trước mới sau; quyết định "
            "của người dùng ở đây vẫn có hiệu lực):")
    return "\n".join([head, *reversed(out), ""])
