"""The workflow of each kind of video: its steps, what each one does, which files it must leave behind, how those
files are checked after a run, and what the project page shows for each step.

Documentaries (FLOWS["doc"], seven steps) and news videos (FLOWS["news"]) are separate desks: each has its own list of
steps and its own rulebook, so either workflow can change without touching the other. A step key (script, scenes…)
names the same output files in both, so the checks and views below are shared.

The detailed instructions for Claude live in each rulebook (section 2): improving a rulebook improves its workflow
without touching this file. The file schemas below match the rulebooks' schema section.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .util import read_json


@dataclass(frozen=True)
class Step:
    key: str
    num: int
    name: str
    icon: str
    goal: str
    does: tuple[str, ...]
    outputs: tuple[str, ...]
    gate: str
    spends: str
    rule: str = ""                      # rulebook section
    extra: tuple[str, ...] = field(default_factory=tuple)
    # the same step when the project makes one finished picture per scene (pipeline "fullframe")
    goal_ff: str = ""
    does_ff: tuple[str, ...] = field(default_factory=tuple)
    gate_ff: str = ""
    # ... and when the image model paints each depth layer separately (pipeline "stacked")
    goal_st: str = ""
    does_st: tuple[str, ...] = field(default_factory=tuple)
    gate_st: str = ""
    # ... and when the film is built from real photos and documents staged as evidence (pipeline "dossier")
    goal_ds: str = ""
    does_ds: tuple[str, ...] = field(default_factory=tuple)
    gate_ds: str = ""

    def text(self, project: dict | None) -> dict:
        pipe = (project or {}).get("pipeline")
        if pipe == "fullframe" and self.goal_ff:
            return {"goal": self.goal_ff, "does": self.does_ff, "gate": self.gate_ff or self.gate}
        if pipe == "stacked" and self.goal_st:
            return {"goal": self.goal_st, "does": self.does_st, "gate": self.gate_st or self.gate}
        if pipe == "dossier" and self.goal_ds:
            return {"goal": self.goal_ds, "does": self.does_ds, "gate": self.gate_ds or self.gate}
        return {"goal": self.goal, "does": self.does, "gate": self.gate}


DOC_STEPS: tuple[Step, ...] = (
    Step("script", 1, "Kịch bản", "📝",
         "Nghiên cứu nguồn, chốt luận đề, viết kịch bản có lời dẫn, trích dẫn và thời lượng.",
         ("Đọc tư liệu bạn đưa vào (sources/) và tra thêm trên web, ưu tiên nguồn gốc và nguồn học thuật",
          "Tách các khẳng định, đánh dấu cái nào đã kiểm chứng, cái nào còn tranh cãi",
          "Đề xuất 2–3 hướng dàn ý, chọn hướng hợp yêu cầu nhất",
          "Viết kịch bản theo hồi: lời dẫn, chữ trên màn hình, trích dẫn nguyên văn, ý tưởng hình ảnh, nhân vật",
          "Ước tính thời lượng và chi phí giọng đọc",
          "Lập bản thiết kế dự án: khung xương các hồi, nguyên liệu cần, kế hoạch các bước sau, ngân sách (🧭 Sơ đồ dự án)"),
         ("1_script/research.md", "1_script/sources.json", "1_script/script.json", "1_script/blueprint.json", "1_script/script.md"),
         "Duyệt = chốt nội dung phim và bản thiết kế dự án. Sau đó mới tuyển nhân vật.",
         "Không tốn phí API.", "2.1"),
    Step("cast", 2, "Tuyển nhân vật", "🎭",
         "Lập danh sách vai, ngoại hình bám nguồn và niên đại, tư thế cần, ảnh thử vai để chọn.",
         ("Gom các nhân vật xuất hiện trong kịch bản: chính, phụ, đám đông, người dẫn",
          "Mỗi vai: mô tả, ngoại hình đúng niên đại, cách thể hiện (vẽ AI, ảnh tư liệu, bóng đen…), các tư thế cần",
          "Viết prompt ảnh gốc theo phong cách chung của phim",
          "Vẽ 1–2 ảnh thử vai rẻ cho mỗi vai chính và phụ để bạn chọn"),
         ("2_cast/cast.json", "2_cast/cast.md"),
         "Chọn ứng viên cho từng vai rồi Duyệt: ứng viên được chọn thành ảnh gốc của nhân vật.",
         "Ảnh thử vai bằng model rẻ (fal.ai), tối đa khoảng 10% ngân sách.", "2.2",
         goal_ds="Lập hồ sơ nhân vật: người thật dùng ảnh thật (chân dung, ảnh sự kiện); chỉ vai không thể có ảnh mới vẽ AI.",
         does_ds=("Gom các nhân vật, tổ chức, địa điểm được nhắc tên trong kịch bản",
                  "Người thật: tìm ảnh thật có nguồn và giấy phép (Wikimedia Commons, ảnh chính phủ, kho lưu trữ, ảnh báo chí)",
                  "Tổ chức: logo thật; địa điểm: ảnh thật hoặc bản đồ",
                  "Chỉ vai không thể có ảnh (cổ đại, nhân vật vô danh) mới thử vai AI, ghi rõ «tái hiện»"),
         gate_ds="Duyệt hồ sơ nhân vật: ảnh thật nào dùng cho ai, vai nào phải tái hiện AI."),
    Step("scenes", 3, "Phân cảnh & bối cảnh", "🗺️",
         "Chia kịch bản thành các cảnh 3D, lập danh sách bối cảnh, ảnh cần vẽ (prompt, model, chi phí) và footage cần.",
         ("Chia các beat thành cảnh dựng được: bối cảnh, các lớp sâu, nhân vật và tư thế, máy quay, hiệu ứng, âm thanh",
          "Lập danh sách bối cảnh và tấm nền cần vẽ, dùng lại tối đa",
          "Lập danh sách ảnh cần vẽ: model, chất lượng, tỉ lệ, prompt hoàn chỉnh, chi phí ước tính ($)",
          "Lập danh sách footage cần: hiệu ứng quay thật, tư liệu, clip phỏng vấn, giọng đọc, nhạc"),
         ("3_scenes/scenes.json", "3_scenes/scenes.md"),
         "Duyệt = duyệt danh sách ảnh và số tiền sẽ tiêu ở bước 4.",
         "Không tốn phí API.", "2.3",
         goal_ff="Chia kịch bản thành cảnh; mỗi cảnh dựng lại là MỘT ảnh hoàn chỉnh (nhân vật vẽ sẵn trong bối cảnh), "
                 "kèm chuyển động camera 3D và chủ thể.",
         does_ff=("Chia các beat thành cảnh: cảnh dựng lại (một ảnh liền khối), cảnh tư liệu, clip, thẻ chữ",
                  "Mỗi cảnh dựng lại: prompt ảnh hoàn chỉnh có nhân vật, ánh sáng, bố cục nhiều tầng sâu cho 3D",
                  "Chọn camera (orbit, push-in, crane…), chủ thể, thời lượng; ảnh gốc nhân vật làm tham chiếu",
                  "Danh sách footage cần, chi phí ảnh ước tính"),
         gate_ff="Duyệt = duyệt prompt từng cảnh và số tiền sẽ tiêu ở bước 4.",
         goal_st="Chia kịch bản thành cảnh; mỗi cảnh dựng lại ước lượng không gian 3D và chia 2–4 lớp theo độ sâu, "
                 "mỗi lớp một prompt cho GPT, kèm camera điện ảnh và ghi chú hiệu ứng code (nếu có) để bạn duyệt.",
         does_st=("Chia các beat thành cảnh: cảnh dựng lại (xếp lớp), cảnh tư liệu, clip, thẻ chữ",
                  "Mỗi cảnh dựng lại: 2–4 lớp xa → gần với khoảng cách (m); nhân vật luôn cùng lớp với mặt đất họ đứng",
                  "Prompt riêng từng lớp (lớp sau cùng vẽ kín khung, lớp trước vẽ trên nền xám), ảnh gốc nhân vật làm tham chiếu",
                  "Camera: kiểu đi máy, biên độ, khung chính; hiệu ứng code chỉ ghi chú đề xuất, chờ bạn duyệt"),
         gate_st="Duyệt = duyệt bảng lớp, camera, hiệu ứng code đề xuất và số tiền sẽ tiêu ở bước 4.",
         goal_ds="Biến từng danh từ riêng của lời dẫn thành một shot tư liệu thật (ảnh in trên bàn, trang tài liệu có highlight, "
                 "bảng điều tra, khung phim cũ, logo 3D, dải năm); chỉ cảnh không thể có ảnh mới tái hiện AI.",
         does_ds=("Gạch chân mọi người, tổ chức, địa điểm, tài liệu, con số trong lời dẫn: mỗi cái một bằng chứng thật",
                  "Danh sách bằng chứng: link nguồn, giấy phép, loại (ảnh, trang cần chụp + cụm từ highlight, logo, footage cũ)",
                  "Mỗi cảnh một shot hồ sơ (photos, doc, board, archive, logo, years) đồng bộ theo lời dẫn",
                  "Cảnh tái hiện AI (xếp lớp) chỉ khi không có tư liệu, ghi lý do; chuyển cảnh, màu, chữ động"),
         gate_ds="Duyệt = duyệt danh sách bằng chứng sẽ tải/chụp, các cảnh tái hiện AI và số tiền sẽ tiêu ở bước 4."),
    Step("images", 4, "Render hình ảnh", "🖼️",
         "Vẽ ảnh gốc nhân vật, biến thể, nền bối cảnh và đạo cụ; tách nền trên máy; đo điểm neo.",
         ("Kiểm tra API key và số dư (gen.py check); mỗi ảnh tự ghi chi phí vào notes/costs.json",
          "Ảnh gốc từ ứng viên đã chọn, biến thể sửa từ ảnh gốc để giữ đúng nhân vật",
          "Nền bối cảnh, đạo cụ, lớp sương/ánh sáng",
          "Tách nền trên máy (miễn phí), soát viền, ghép bảng xem nhanh",
          "Đo điểm neo (tay, chân, đỉnh núi…) để hiệu ứng bám đúng chỗ"),
         ("4_images/manifest.json",),
         "Xem gallery, bấm Làm lại cho ảnh chưa ưng (kèm ghi chú), rồi Duyệt.",
         "Tiền ảnh fal.ai theo danh sách đã duyệt ở bước 3.", "2.4",
         goal_ff="Vẽ một ảnh hoàn chỉnh cho mỗi cảnh (nhân vật giữ đúng nhân dạng nhờ ảnh gốc tham chiếu) và xem thử 3D.",
         does_ff=("Ảnh gốc nhân vật từ ứng viên đã chọn (dùng làm tham chiếu)",
                  "Mỗi cảnh một ảnh liền khối có nhân vật, --ref ảnh gốc của các nhân vật trong cảnh",
                  "Soát: đúng niên đại, đúng nhân dạng, bố cục đủ tầng sâu, chừa lề cho camera",
                  "Chạy thử 3D (parallax) vài cảnh khó để bắt lỗi tách lớp sớm"),
         gate_ff="Xem gallery ảnh cảnh, bấm Làm lại cho cảnh chưa ưng (kèm ghi chú), rồi Duyệt.",
         goal_st="GPT vẽ từng lớp của mỗi cảnh theo bảng lớp đã duyệt, máy cắt nền xám, ghép thử để soát.",
         does_st=("Ảnh gốc nhân vật từ ứng viên đã chọn (dùng làm tham chiếu)",
                  "layerkit.py: lớp sau cùng vẽ kín khung, mỗi lớp trước vẽ trên nền xám với lớp sau làm tham chiếu",
                  "Cắt bỏ đúng phần nền xám trên máy (giữ người lẫn mặt đất), miễn phí",
                  "Soát bảng ghép từng cảnh: khớp ánh sáng, tỉ lệ, khung hình; vẽ lại lớp lỗi"),
         gate_st="Xem bảng ghép các lớp, bấm Làm lại cho lớp chưa ưng (kèm ghi chú), rồi Duyệt.",
         goal_ds="Gom đủ bằng chứng thật đã duyệt: tải ảnh, chụp trang tài liệu kèm toạ độ cụm từ, tách nền chân dung, logo; "
                 "vẽ AI chỉ cho cảnh tái hiện.",
         does_ds=("Tải ảnh, logo, footage cũ trong danh sách đã duyệt vào film/public/evidence/, ghi nguồn",
                  "Chụp trang web/tài liệu bằng pagecap.mjs: ảnh trang + toạ độ từng cụm cần highlight",
                  "Chuẩn hoá: tách nền chân dung (miễn phí), cắt khung, soát chữ đọc được khi phóng to",
                  "Vẽ lớp AI cho cảnh tái hiện (nếu có); ghép bảng xem nhanh bằng chứng theo hồi"),
         gate_ds="Xem bảng bằng chứng, nhắn thay ảnh chưa ưng hoặc bỏ, rồi Duyệt."),
    Step("footage", 5, "Footage & âm thanh", "🎞️",
         "Footage có giấy phép (tải sau khi bạn duyệt), clip trích, lời dẫn bằng giọng đọc, kế hoạch nhạc và hiệu ứng âm thanh.",
         ("Đề xuất footage: hiệu ứng lửa/khói quay thật, tư liệu, clip phỏng vấn, kèm nguồn, giấy phép, dung lượng",
          "Chỉ tải những file bạn đã duyệt trên app, xử lý (cắt, khử nền đen, đo độ chập chờn)",
          "Thu lời dẫn bằng ElevenLabs một lần cho cả kịch bản, chọn bản tốt nhất bằng whisper",
          "Lên kế hoạch nhạc và hiệu ứng âm thanh (tự tổng hợp)"),
         ("5_footage/footage.json",),
         "Duyệt từng file footage trước khi tải. Footage và giọng đọc đủ rồi thì Duyệt.",
         "Giọng đọc ElevenLabs v4 khoảng $0,08 cho mỗi phút đọc (giá API).", "2.5"),
    Step("render", 6, "Dựng & render", "🎬",
         "Dựng các cảnh bằng engine, soát ảnh tĩnh, trộn âm thanh, render MP4 và QA.",
         ("Viết timeline, các cảnh 3D, hiệu ứng, chữ trên màn hình",
          "Soát ảnh tĩnh đầu/giữa/cuối mỗi cảnh và cắt cận các điểm neo",
          "Trộn nhạc, hiệu ứng, lời dẫn; master −15 LUFS",
          "Render out/<tên>_v<N>.mp4 (không ghi đè bản cũ), chạy QA trên chính file MP4"),
         ("6_render/render.json",),
         "Xem phim, góp ý qua chat để ra bản mới. Duyệt = chốt bản cuối.",
         "Không tốn phí API (render trên máy).", "2.6",
         goal_ff="Biến mỗi ảnh cảnh thành clip camera 3D (parallax trên GPU), ghép với chữ, tư liệu, âm thanh, render MP4 và QA.",
         does_ff=("Render clip camera 3D cho mọi cảnh dựng lại bằng parallax.py (một lệnh batch)",
                  "Soát bảng ghép đầu/giữa/cuối của từng clip, làm lại clip lỗi (đổi camera, giảm biên độ)",
                  "Dựng timeline trong engine: clip 3D + chữ + tư liệu + chuyển cảnh; trộn âm thanh −15 LUFS",
                  "Render out/<tên>_v<N>.mp4 (không ghi đè bản cũ), chạy QA trên chính file MP4"),
         goal_st="Xếp các lớp theo độ sâu trong engine, đi camera điện ảnh cho từng cảnh, ghép chữ, tư liệu, âm thanh, render MP4 và QA.",
         does_st=("Mỗi cảnh dựng lại = LayerScene: các lớp ở đúng khoảng cách, camera thật (push-in, orbit, crane, truck…)",
                  "Hiệu ứng code chỉ ở cảnh bạn đã duyệt, và chỉ làm sáng/động chi tiết đã có trong ảnh",
                  "Soát ảnh tĩnh đầu/giữa/cuối mỗi cảnh: không lộ mép lớp, không cắt đầu, chuyển cảnh mượt",
                  "Trộn âm thanh −15 LUFS, render out/<tên>_v<N>.mp4 (không ghi đè bản cũ), QA trên chính file MP4"),
         goal_ds="Dựng các shot hồ sơ từ dữ liệu (DossierScene): ảnh thật như vật chứng trên bàn, máy quay luôn trôi, "
                 "highlight và dấu chạy đúng chữ lời dẫn; ghép clip, bản đồ, cảnh tái hiện; render MP4 và QA.",
         does_ds=("Viết scenes/config.json: mỗi cảnh một shot (photos, doc, board, archive, logo, years), mốc theo lời dẫn",
                  "Clip phỏng vấn (QuoteClip), bản đồ (mẫu news-map), số đếm, cảnh tái hiện (LayerScene) giữ cách cũ",
                  "Soát ảnh tĩnh lúc highlight đang quét, lúc thẻ vừa đáp, đầu/giữa/cuối mỗi cảnh",
                  "Trộn âm thanh −15 LUFS, render out/<tên>_v<N>.mp4 (không ghi đè bản cũ), QA trên chính file MP4")),
    Step("metadata", 7, "Metadata YouTube", "📈",
         "Tối ưu metadata để đăng YouTube: tiêu đề, mô tả có chương, thẻ, hashtag, thumbnail, phụ đề.",
         ("Tìm từ khóa người xem thật sự gõ cho chủ đề (WebSearch, gợi ý tìm kiếm YouTube), chọn từ khóa chính",
          "3–5 phương án tiêu đề (≤ 70 ký tự, từ khóa ở đầu), chọn một và nói lý do",
          "Mô tả: 2 dòng đầu chứa từ khóa, tóm tắt, chương (mốc thời gian lấy từ bản render đã duyệt), nguồn, hashtag",
          "Thẻ (≤ 500 ký tự), hashtag, danh mục, ngôn ngữ; phụ đề .srt từ lời dẫn",
          "2 thumbnail (ảnh từ phim + chữ lớn, hoặc vẽ mới bằng gen.py nếu còn ngân sách)"),
         ("7_metadata/metadata.json", "7_metadata/metadata.md"),
         "Xem tiêu đề, mô tả, thumbnail; nhắn sửa nếu cần rồi Duyệt = sẵn sàng đăng.",
         "Không tốn phí API, trừ thumbnail vẽ mới (≈ $0,02–0,2/ảnh).", "2.8"),
)

# News videos (Tin nóng, Điểm tin 24h): real photos and videos of the chosen stories, no cast, no painted scenes.
# Rule numbers refer to the news rulebook. Output files keep the documentary layout (1_script/, 3_scenes/…).
NEWS_STEPS: tuple[Step, ...] = (
    Step("script", 1, "Kịch bản tin", "📝",
         "Chọn và xếp tin, kiểm chứng từng tin bằng nguồn gốc, viết lời dẫn kiểu bản tin có ghi rõ ai nói gì.",
         ("Đọc toàn văn các tin đã chọn (sources/news_*.md, digest.md), gộp tin trùng, bỏ tin yếu",
          "Kiểm chứng từng tin: thông cáo gốc, phiên bản của phía bên kia, bài gốc bản mới nhất",
          "Xếp tin theo vai (tin của tựa, tin thumbnail, tin căng nhất, tin nhẹ) và nhịp của kiểu video",
          "Viết lời dẫn: câu tít, chủ thể của tuyên bố, chi tiết, trích nguyên văn, phản hồi phía kia",
          "Ước tính thời lượng và chi phí giọng đọc"),
         ("1_script/research.md", "1_script/sources.json", "1_script/script.json", "1_script/script.md"),
         "Duyệt = chốt danh sách tin và lời dẫn.",
         "Không tốn phí API.", "2.1"),
    Step("scenes", 2, "Bảng hình", "🗺️",
         "Chia lời dẫn thành cảnh, gán cho mỗi cảnh ảnh, video thật của đúng tin đó; chỗ thiếu hình thì bản đồ, thẻ chữ, "
         "ảnh AI là đường cuối.",
         ("Mỗi tin 2–4 hình, đổi hình mỗi 8–15 s; hình nào thuộc tin nào, đoạn video nào, bao nhiêu giây",
          "Đánh dấu file cần xem kỹ (thương vong, tù binh, trẻ em, logo) và chỗ cần che mờ",
          "Chỗ thiếu hình: bản đồ, thẻ chữ số liệu; ảnh AI chỉ khi tin không còn hình thật, ghi lý do",
          "Đồ hoạ cố định: dải tít, nhãn nguồn (chỉ báo lớn), phụ đề"),
         ("3_scenes/scenes.json", "3_scenes/scenes.md"),
         "Duyệt = duyệt hình của từng tin (và số tiền ảnh AI nếu có).",
         "Không tốn phí API.", "2.2"),
    Step("images", 3, "Hình thật", "🖼️",
         "Gom đủ ảnh, video thật của các tin (cả ảnh trong thân bài gốc), kiểm từng file, che mờ, dựng bản đồ và thẻ chữ.",
         ("Lấy thêm ảnh trong thân các bài gốc vào sources/media/",
          "Kiểm từng file: mở được (ffprobe), đúng sự kiện, xem khung hình; che mờ thi thể, máu, tù binh, mặt trẻ em",
          "Bản đồ, thẻ chữ số liệu; ảnh AI chỉ cho tin không còn hình thật",
          "Ghép bảng xem nhanh theo tin"),
         ("4_images/manifest.json",),
         "Xem bảng hình theo tin, bấm Làm lại / nhắn bỏ hình chưa ưng, rồi Duyệt.",
         "Thường không tốn phí (ảnh thật); ảnh AI nếu có theo bảng hình đã duyệt.", "2.3"),
    Step("footage", 4, "Giọng đọc & âm thanh", "🎙️",
         "Thu lời dẫn giọng phát thanh viên, cắt câu theo cảnh, chọn đoạn tiếng gốc, nhạc nền bản tin và sting.",
         ("Ghi mọi hình, đoạn video sẽ dùng vào footage.json (nguồn, file, cảnh)",
          "Thu lời dẫn ElevenLabs một lần cho cả bản tin, kiểm bằng whisper, cắt câu ở quãng lặng",
          "Đoạn tiếng gốc của nhân vật lớn (nếu có video đã tải)",
          "Nhạc nền bản tin, sting, whoosh chuyển tin"),
         ("5_footage/footage.json",),
         "Giọng đọc đã chọn, hình đủ thì Duyệt.",
         "Giọng đọc ElevenLabs v4 khoảng $0,08 cho mỗi phút đọc (giá API).", "2.4"),
    Step("render", 5, "Dựng & render", "🎬",
         "Dựng bản tin trong engine: hình theo từng tin, dải tít, phụ đề, chuyển tin, âm thanh; render MP4 và QA.",
         ("Timeline theo lời dẫn: mỗi hình có zoom/lia chậm, cắt cứng trong tin, whip giữa hai tin",
          "Dải tít, nhãn nguồn, phụ đề hộp tối, logo kênh",
          "Soát ảnh tĩnh đầu/giữa/cuối mỗi cảnh, nhãn khớp lời dẫn của chính cảnh đó",
          "Trộn âm thanh −15 LUFS, render out/<tên>_v<N>.mp4 (không ghi đè bản cũ), QA trên chính file MP4"),
         ("6_render/render.json",),
         "Xem bản tin, góp ý qua chat để ra bản mới. Duyệt = chốt bản cuối.",
         "Không tốn phí API (render trên máy).", "2.5"),
    Step("metadata", 6, "Metadata YouTube", "📈",
         "Tựa 3 vế, thumbnail 2 mảng, mô tả có chương theo từng tin, thẻ, phụ đề; tra lại tin mới sau giờ chốt.",
         ("Tựa từ 3 tin có trong video, vế khẳng định là tuyên bố có chủ thể",
          "Thumbnail từ ảnh thật của tin thumbnail, mốc phát tin đó ở 40–50%",
          "Mô tả: 2 dòng đầu là 2 tin lớn nhất, mỗi tin một chương, nguồn chỉ báo lớn",
          "Metadata xong thì kiểm lại tin của tựa/thumbnail một lượt nhanh (không chờ agent); thẻ, hashtag, phụ đề .srt"),
         ("7_metadata/metadata.json", "7_metadata/metadata.md"),
         "Xem tiêu đề, mô tả, thumbnail; nhắn sửa nếu cần rồi Duyệt = sẵn sàng đăng.",
         "Không tốn phí API.", "2.6"),
)


@dataclass(frozen=True)
class Flow:
    """The ordered steps of one kind of video."""
    kind: str
    steps: tuple[Step, ...]

    @property
    def keys(self) -> tuple[str, ...]:
        return tuple(s.key for s in self.steps)

    @property
    def by_key(self) -> dict[str, Step]:
        return {s.key: s for s in self.steps}

    def prev(self, key: str) -> str | None:
        i = self.keys.index(key)
        return self.keys[i - 1] if i > 0 else None

    def next(self, key: str) -> str | None:
        i = self.keys.index(key)
        return self.keys[i + 1] if i + 1 < len(self.keys) else None

    def names(self) -> dict[str, str]:
        return {s.key: f"{s.num} · {s.name}" for s in self.steps}


FLOWS = {"doc": Flow("doc", DOC_STEPS), "news": Flow("news", NEWS_STEPS)}


def flow(p_or_kind) -> Flow:
    """The workflow of a project (or of a kind: "doc" | "news")."""
    kind = p_or_kind.get("kind") if isinstance(p_or_kind, dict) else p_or_kind
    return FLOWS.get(kind or "doc", FLOWS["doc"])

STATUS_LABELS = {
    "locked": "chưa tới", "ready": "sẵn sàng", "queued": "đang chờ", "running": "đang chạy",
    "review": "chờ duyệt", "approved": "đã duyệt", "failed": "lỗi",
}


# ---------------------------------------------------------------- helpers
def _rel(d: Path, path: Path) -> str:
    return str(path.relative_to(d)).replace("\\", "/")


def _md(d: Path, rel: str) -> str:
    p = d / rel
    try:
        return p.read_text(encoding="utf-8") if p.exists() else ""
    except OSError:
        return ""


def _num(x, default=0.0) -> float:
    try:
        return float(x)
    except (TypeError, ValueError):
        return default


def _list(x) -> list:
    return x if isinstance(x, list) else []


def _exists(d: Path, rel) -> bool:
    return bool(rel) and isinstance(rel, str) and (d / rel).is_file()


def mmss(sec: float) -> str:
    sec = int(round(sec or 0))
    return f"{sec // 60}:{sec % 60:02d}"


def costs_spent(d: Path) -> dict:
    """notes/costs.json written by gen.py (rulebook 11.7): USD spent on generated assets, and every call."""
    data = read_json(d / "notes" / "costs.json")
    if not isinstance(data, dict):
        return {"total": 0.0, "events": []}
    events = [e for e in _list(data.get("events")) if isinstance(e, dict)]
    total = _num(data.get("total_usd"), sum(_num(e.get("usd")) for e in events))
    return {"total": round(total, 2), "events": events}


def latest_mtime(d: Path, step: Step) -> float:
    times = [(d / rel).stat().st_mtime for rel in step.outputs if (d / rel).exists()]
    return max(times) if times else 0.0


# ---------------------------------------------------------------- checks after a run
def check(step_key: str, d: Path, project: dict) -> tuple[list[str], str]:
    """(problems, one-line summary) of a step's outputs. Problems starting with "⚠" are warnings; any other
    problem means the step did not produce what it must."""
    step = flow(project).by_key.get(step_key)
    if step is None:                    # a step this kind of video no longer has (news projects made before the split)
        return [], ""
    problems = [f"thiếu {rel}" for rel in step.outputs if not (d / rel).exists()]
    fn = globals().get(f"_check_{step_key}")
    summary = ""
    if fn:
        extra, summary = fn(d, project)
        problems += extra
    return problems, summary


def blocking(problems: list[str]) -> bool:
    return any(not p.startswith("⚠") for p in problems or [])


def _check_script(d: Path, p: dict) -> tuple[list[str], str]:
    out: list[str] = []
    s = read_json(d / "1_script" / "script.json")
    if not (d / "1_script" / "script.json").exists():
        return out, ""
    if not isinstance(s, dict):
        return ["script.json không đọc được (JSON lỗi)"], ""
    beats = [b for b in _list(s.get("beats")) if isinstance(b, dict)]
    if not beats:
        out.append("script.json chưa có beats")
    total = sum(_num(b.get("duration_sec")) for b in beats)
    target = _num(p.get("target_sec"))
    # target_sec is a floor (the user's choice, 2026-10-14): longer is fine when the script is better for it
    if target and total and total < 0.95 * target:
        out.append(f"⚠ tổng thời lượng {mmss(total)} ngắn hơn mức tối thiểu {mmss(target)}")
    src = read_json(d / "1_script" / "sources.json")
    ids = {x.get("id") for x in _list((src or {}).get("sources")) if isinstance(x, dict)}
    missing = sorted({sid for b in beats for sid in _list(b.get("sources")) if sid not in ids})
    if missing and ids:
        out.append("⚠ beat dẫn nguồn không có trong sources.json: " + ", ".join(map(str, missing[:8])))
    summary = f"{len(beats)} beat · {mmss(total)}" + (f" (tối thiểu {mmss(target)})" if target else "") + (f" · {len(ids)} nguồn" if ids else "")
    return out, summary


def _check_cast(d: Path, p: dict) -> tuple[list[str], str]:
    c = read_json(d / "2_cast" / "cast.json")
    if not (d / "2_cast" / "cast.json").exists():
        return [], ""
    if not isinstance(c, dict):
        return ["cast.json không đọc được (JSON lỗi)"], ""
    chars = [x for x in _list(c.get("characters")) if isinstance(x, dict)]
    out = [] if chars else ["cast.json chưa có nhân vật"]
    cands = [x for ch in chars for x in _list(ch.get("candidates")) if isinstance(x, dict)]
    lost = [x.get("file") for x in cands if not _exists(d, x.get("file"))]
    if lost:
        out.append(f"⚠ {len(lost)} ảnh thử vai không thấy file: " + ", ".join(map(str, lost[:4])))
    choices = read_json(d / "2_cast" / "choices.json") or {}
    need = [ch for ch in chars if _list(ch.get("candidates"))]
    unchosen = [ch.get("name") or ch.get("id") for ch in need if ch.get("id") not in choices]
    if unchosen:
        out.append("⚠ chưa chọn ứng viên cho: " + ", ".join(map(str, unchosen[:8])))
    return out, f"{len(chars)} vai · {len(cands)} ảnh thử vai"


def _check_scenes(d: Path, p: dict) -> tuple[list[str], str]:
    s = read_json(d / "3_scenes" / "scenes.json")
    if not (d / "3_scenes" / "scenes.json").exists():
        return [], ""
    if not isinstance(s, dict):
        return ["scenes.json không đọc được (JSON lỗi)"], ""
    scenes = [x for x in _list(s.get("scenes")) if isinstance(x, dict)]
    locs = {x.get("id") for x in _list(s.get("locations")) if isinstance(x, dict)}
    assets = [x for x in _list(s.get("assets")) if isinstance(x, dict)]
    out = [] if scenes else ["scenes.json chưa có cảnh"]
    bad = sorted({x.get("location") for x in scenes if x.get("location") and x.get("location") not in locs})
    if bad:
        out.append("⚠ cảnh dùng bối cảnh không có trong locations: " + ", ".join(map(str, bad[:6])))
    est = sum(_num(a.get("est_usd")) for a in assets)
    budget = _num(p.get("budget_usd"))
    spent = costs_spent(d)["total"]
    if budget and est + spent > budget:
        out.append(f"⚠ ước tính ${est:.2f} + đã tiêu ${spent:.2f} vượt ngân sách ${budget:.2f}")
    total = sum(_num(x.get("duration_sec")) for x in scenes)
    if p.get("pipeline") == "dossier":
        # every real document / photo the film will download or capture is listed with where it comes from
        ev = [x for x in _list(s.get("evidence")) if isinstance(x, dict)]
        if not ev:
            out.append("⚠ phim hồ sơ chưa có danh sách evidence (bằng chứng thật)")
        unsourced = [x.get("id") for x in ev if not x.get("source_url") or not x.get("license")]
        if unsourced:
            out.append(f"⚠ {len(unsourced)} bằng chứng thiếu link nguồn hoặc giấy phép: " + ", ".join(map(str, unsourced[:6])))
        recon = sum(1 for x in scenes if x.get("reconstruction"))
        return out, f"{len(scenes)} cảnh · {mmss(total)} · {len(ev)} bằng chứng thật · {recon} cảnh tái hiện · ~${est:.2f}"
    return out, f"{len(scenes)} cảnh · {mmss(total)} · {len(assets)} ảnh · ~${est:.2f}"


def _check_images(d: Path, p: dict) -> tuple[list[str], str]:
    m = read_json(d / "4_images" / "manifest.json")
    if not (d / "4_images" / "manifest.json").exists():
        return [], ""
    if not isinstance(m, dict):
        return ["manifest.json không đọc được (JSON lỗi)"], ""
    assets = [x for x in _list(m.get("assets")) if isinstance(x, dict)]
    done = [a for a in assets if a.get("status") == "done"]
    # a card or map drawn by code has no picture file: its "file" points at the data that draws it
    # ("film/src/digest/config.json#sc12"), so only that data file has to exist
    lost = [a.get("key") for a in done if not _exists(d, str(a.get("file") or "").split("#", 1)[0])]
    out = []
    if lost:
        out.append(f"{len(lost)} ảnh báo xong nhưng không thấy file: " + ", ".join(map(str, lost[:6]))
                   + (" …" if len(lost) > 6 else ""))
    failed = [a.get("key") for a in assets if a.get("status") in ("failed", "redo", "pending")]
    if failed:
        out.append(f"⚠ {len(failed)} ảnh chưa xong: " + ", ".join(map(str, failed[:6])))
    return out, f"{len(done)}/{len(assets)} ảnh xong · ${sum(_num(a.get('usd')) for a in assets):.2f}"


def _check_footage(d: Path, p: dict) -> tuple[list[str], str]:
    f = read_json(d / "5_footage" / "footage.json")
    if not (d / "5_footage" / "footage.json").exists():
        return [], ""
    if not isinstance(f, dict):
        return ["footage.json không đọc được (JSON lỗi)"], ""
    items = [x for x in _list(f.get("items")) if isinstance(x, dict)]
    decisions = read_json(d / "5_footage" / "approvals.json") or {}
    waiting = [i for i in items if i.get("status") == "proposed" and i.get("id") not in decisions]
    approved_missing = [i.get("id") for i in items if (decisions.get(i.get("id")) or {}).get("decision") == "approved"
                        and i.get("status") not in ("downloaded", "processed", "generated")]
    out = []
    if waiting:
        out.append(f"⚠ {len(waiting)} footage chờ bạn duyệt")
    if approved_missing:
        out.append("⚠ đã duyệt nhưng chưa tải: " + ", ".join(map(str, approved_missing[:6])))
    ready = [i for i in items if i.get("status") in ("downloaded", "processed", "generated")]
    news_media = [m for m in _list((read_json(d / "sources" / "media.json") or {}).get("items")) if isinstance(m, dict)]
    unreviewed = sum(1 for m in news_media if m.get("status") == "proposed")
    if unreviewed:
        out.append(f"⚠ {unreviewed} ảnh/video từ tin chưa duyệt (mục Nguyên liệu từ tin)")
    return out, f"{len(ready)}/{len(items)} footage sẵn sàng" + (f" · {len(waiting)} chờ duyệt" if waiting else "")


def _check_render(d: Path, p: dict) -> tuple[list[str], str]:
    r = read_json(d / "6_render" / "render.json")
    if not (d / "6_render" / "render.json").exists():
        return [], ""
    if not isinstance(r, dict):
        return ["render.json không đọc được (JSON lỗi)"], ""
    versions = [v for v in _list(r.get("versions")) if isinstance(v, dict)]
    if not versions:
        return ["render.json chưa có bản render"], ""
    last = versions[-1]
    out = []
    if not _exists(d, last.get("file")):
        out.append(f"không thấy file {last.get('file')}")
    qa = last.get("qa") if isinstance(last.get("qa"), dict) else {}
    if qa and qa.get("ok") is False:
        out.append("⚠ QA báo lỗi ở bản mới nhất")
    name = Path(str(last.get("file") or "")).name
    return out, f"{len(versions)} bản · mới nhất {name}" + (" · QA OK" if qa.get("ok") else "")


# ---------------------------------------------------------------- what the project page shows
def view(step_key: str, d: Path, project: dict) -> dict:
    fn = globals().get(f"_view_{step_key}")
    return fn(d, project) if fn else {}


def _view_script(d: Path, p: dict) -> dict:
    s = read_json(d / "1_script" / "script.json")
    src = read_json(d / "1_script" / "sources.json")
    out = {"research_md": _md(d, "1_script/research.md"), "script_md": _md(d, "1_script/script.md"),
           "script": s if isinstance(s, dict) else None, "sources": [], "claims": []}
    if isinstance(src, dict):
        out["sources"] = [x for x in _list(src.get("sources")) if isinstance(x, dict)]
        out["claims"] = [x for x in _list(src.get("claims")) if isinstance(x, dict)]
    if out["script"]:
        beats = [b for b in _list(out["script"].get("beats")) if isinstance(b, dict)]
        t = 0.0
        for b in beats:
            b["_start"] = mmss(t)
            t += _num(b.get("duration_sec"))
        out["beats"] = beats
        out["total"] = mmss(t)
    return out


def _view_cast(d: Path, p: dict) -> dict:
    c = read_json(d / "2_cast" / "cast.json")
    choices = read_json(d / "2_cast" / "choices.json") or {}
    chars = [x for x in _list((c or {}).get("characters")) if isinstance(x, dict)] if isinstance(c, dict) else []
    for ch in chars:
        ch["_candidates"] = [x for x in _list(ch.get("candidates")) if isinstance(x, dict) and _exists(d, x.get("file"))]
        ch["_chosen"] = choices.get(ch.get("id"))
    return {"cast": c if isinstance(c, dict) else None, "characters": chars, "cast_md": _md(d, "2_cast/cast.md"),
            "choices": choices}


def _view_scenes(d: Path, p: dict) -> dict:
    s = read_json(d / "3_scenes" / "scenes.json")
    if not isinstance(s, dict):
        return {"scenes_md": _md(d, "3_scenes/scenes.md"), "data": None}
    scenes = [x for x in _list(s.get("scenes")) if isinstance(x, dict)]
    t = 0.0
    for x in scenes:
        x["_start"] = mmss(t)
        t += _num(x.get("duration_sec"))
    assets = [x for x in _list(s.get("assets")) if isinstance(x, dict)]
    return {"data": s, "scenes": scenes, "locations": [x for x in _list(s.get("locations")) if isinstance(x, dict)],
            "assets": assets, "needs": [x for x in _list(s.get("footage_needs")) if isinstance(x, dict)],
            "est": round(sum(_num(a.get("est_usd")) for a in assets), 2), "total": mmss(t),
            "scenes_md": _md(d, "3_scenes/scenes.md")}


IMG_EXT = (".png", ".jpg", ".jpeg", ".webp")
KIND_ORDER = ("evidence", "document", "logo", "archival", "map", "card", "layers", "frame", "character", "variant", "plate", "prop", "additive")
KIND_NAMES = {"evidence": "Ảnh thật (hồ sơ)", "document": "Trang tài liệu (highlight)", "logo": "Biểu tượng tổ chức",
              "archival": "Ảnh, video thật của tin", "map": "Bản đồ", "card": "Thẻ chữ, số liệu", "layers": "Bảng ghép lớp từng cảnh (xếp lớp)", "frame": "Ảnh cảnh liền khối (→ 3D)", "character": "Nhân vật (ảnh gốc)", "variant": "Biến thể nhân vật",
              "plate": "Nền bối cảnh",
              "prop": "Đạo cụ", "additive": "Sương, ánh sáng", "other": "Khác"}


def _view_images(d: Path, p: dict) -> dict:
    m = read_json(d / "4_images" / "manifest.json")
    assets = [x for x in _list((m or {}).get("assets")) if isinstance(x, dict)] if isinstance(m, dict) else []
    groups: dict[str, list] = {}
    for a in assets:
        a["_file"] = a.get("file") if _exists(d, a.get("file")) else (a.get("raw") if _exists(d, a.get("raw")) else None)
        kind = a.get("kind") if a.get("kind") in KIND_ORDER else "other"
        groups.setdefault(kind, []).append(a)
    ordered = [(k, KIND_NAMES[k], groups[k]) for k in (*KIND_ORDER, "other") if k in groups]
    sheets = sorted((d / "4_images").glob("*.jpg")) if (d / "4_images").exists() else []
    loose = []
    if not assets and (d / "film" / "public" / "img").exists():
        loose = [_rel(d, f) for f in sorted((d / "film" / "public" / "img").iterdir()) if f.suffix.lower() in IMG_EXT]
    return {"manifest": m if isinstance(m, dict) else None, "groups": ordered, "count": len(assets),
            "done": sum(1 for a in assets if a.get("status") == "done"),
            "sheets": [_rel(d, s) for s in sheets], "loose": loose}


def _view_footage(d: Path, p: dict) -> dict:
    f = read_json(d / "5_footage" / "footage.json")
    decisions = read_json(d / "5_footage" / "approvals.json") or {}
    items = [x for x in _list((f or {}).get("items")) if isinstance(x, dict)] if isinstance(f, dict) else []
    for i in items:
        i["_decision"] = (decisions.get(i.get("id")) or {}).get("decision")
        i["_file"] = i.get("file") if _exists(d, i.get("file")) else None
    voice = (f or {}).get("voice") if isinstance(f, dict) and isinstance(f.get("voice"), dict) else None
    takes = []
    if voice:
        takes = [t for t in _list(voice.get("takes")) if isinstance(t, dict)]
        for t in takes:
            t["_file"] = t.get("file") if _exists(d, t.get("file")) else None
    return {"data": f if isinstance(f, dict) else None, "entries": items, "voice": voice, "takes": takes,
            "music": (f or {}).get("music") if isinstance(f, dict) else None,
            "waiting": sum(1 for i in items if i.get("status") == "proposed" and not i["_decision"])}


def _view_render(d: Path, p: dict) -> dict:
    r = read_json(d / "6_render" / "render.json")
    versions = [v for v in _list((r or {}).get("versions")) if isinstance(v, dict)] if isinstance(r, dict) else []
    for v in versions:
        v["_file"] = v.get("file") if _exists(d, v.get("file")) else None
        v["_sheet"] = v.get("sheet") if _exists(d, v.get("sheet")) else None
    known = {v.get("file") for v in versions}
    videos = []
    if (d / "out").exists():
        for f in sorted((d / "out").glob("*.mp4"), key=lambda x: x.stat().st_mtime, reverse=True):
            rel = _rel(d, f)
            if rel not in known:
                videos.append({"file": rel, "mb": round(f.stat().st_size / 1e6, 1)})
    stills = []
    for folder in (d / "film" / "out" / "stills", d / "out" / "review"):
        if folder.exists():
            stills += [_rel(d, f) for f in sorted(folder.glob("*.jpg"), key=lambda x: x.stat().st_mtime, reverse=True)[:12]]
    # fullframe: one contact sheet (first / middle / last frame) per 3D camera clip
    clips = []
    pdir = d / "film" / "public" / "parallax"
    if pdir.exists():
        for f in sorted(pdir.glob("*.mp4")):
            sheet = f.with_name(f.stem + "_contact.jpg")
            clips.append({"file": _rel(d, f), "name": f.stem, "sheet": _rel(d, sheet) if sheet.exists() else None})
    return {"versions": list(reversed(versions)), "videos": videos, "stills": stills[:12], "clips": clips}


# ---------------------------------------------------------------- step 7: YouTube metadata
YT_TITLE_MAX, YT_DESC_MAX, YT_TAGS_MAX = 100, 5000, 500


def _hms_to_sec(x) -> float | None:
    try:
        parts = [float(v) for v in str(x).strip().split(":")]
    except ValueError:
        return None
    sec = 0.0
    for v in parts:
        sec = sec * 60 + v
    return sec


def _check_metadata(d: Path, p: dict) -> tuple[list[str], str]:
    path = d / "7_metadata" / "metadata.json"
    if not path.exists():
        return [], ""
    m = read_json(path)
    if not isinstance(m, dict):
        return ["metadata.json không đọc được (JSON lỗi)"], ""
    out = []
    title = str(m.get("title") or "")
    if not title:
        out.append("metadata.json chưa có title")
    elif len(title) > YT_TITLE_MAX:
        out.append(f"title dài {len(title)} ký tự (YouTube tối đa {YT_TITLE_MAX})")
    elif len(title) > 70:
        out.append(f"⚠ title {len(title)} ký tự: trên ~70 bị cắt ở kết quả tìm kiếm")
    desc = str(m.get("description") or "")
    if not desc:
        out.append("metadata.json chưa có description")
    elif len(desc) > YT_DESC_MAX:
        out.append(f"description dài {len(desc)} ký tự (tối đa {YT_DESC_MAX})")
    if any(c in title + desc for c in "<>"):
        out.append("title/description có ký tự < hoặc > (YouTube không nhận)")
    tags = [str(t) for t in _list(m.get("tags"))]
    tag_chars = sum(len(t) + (2 if " " in t else 0) for t in tags) + max(0, len(tags) - 1)
    if tag_chars > YT_TAGS_MAX:
        out.append(f"tags {tag_chars} ký tự (tối đa {YT_TAGS_MAX})")
    if len(_list(m.get("title_options"))) < 3:
        out.append("⚠ nên có ít nhất 3 phương án tiêu đề (title_options)")
    chapters = [c for c in _list(m.get("chapters")) if isinstance(c, dict)]
    if chapters:
        times = [_hms_to_sec(c.get("time")) for c in chapters]
        if times[0] != 0:
            out.append("⚠ chương đầu phải bắt đầu ở 0:00 (YouTube mới hiện chương)")
        if len(chapters) < 3:
            out.append("⚠ YouTube cần ít nhất 3 chương")
        if any(b is None or a is None or b - a < 10 for a, b in zip(times, times[1:])):
            out.append("⚠ mỗi chương phải dài ít nhất 10 giây và tăng dần")
    thumbs = [t for t in _list(m.get("thumbnails")) if isinstance(t, dict)]
    lost = [t.get("file") for t in thumbs if not _exists(d, t.get("file"))]
    if lost:
        out.append("⚠ thumbnail không thấy file: " + ", ".join(map(str, lost[:4])))
    if m.get("captions") and not _exists(d, m.get("captions")):
        out.append(f"⚠ không thấy file phụ đề {m.get('captions')}")
    summary = f"{len(title)} ký tự tiêu đề · {len(chapters)} chương · {len(tags)} thẻ · {len(thumbs)} thumbnail"
    return out, summary


def _view_metadata(d: Path, p: dict) -> dict:
    m = read_json(d / "7_metadata" / "metadata.json")
    if not isinstance(m, dict):
        return {"data": None, "md": _md(d, "7_metadata/metadata.md")}
    thumbs = [t for t in _list(m.get("thumbnails")) if isinstance(t, dict)]
    for t in thumbs:
        t["_file"] = t.get("file") if _exists(d, t.get("file")) else None
    tags = [str(t) for t in _list(m.get("tags"))]
    return {"data": m, "md": _md(d, "7_metadata/metadata.md"), "thumbs": thumbs, "tags": tags,
            "tags_text": ", ".join(tags), "chapters": [c for c in _list(m.get("chapters")) if isinstance(c, dict)],
            "options": [o for o in _list(m.get("title_options")) if o],
            "captions": m.get("captions") if _exists(d, m.get("captions")) else None,
            "title_len": len(str(m.get("title") or "")), "desc_len": len(str(m.get("description") or ""))}
