# BỘ QUY TẮC LÀM PHIM TÀI LIỆU · Creater Vid

> Mọi lượt làm việc của mọi dự án trong Creater Vid phải tuân theo bộ quy tắc này.
> Thứ tự ưu tiên: yêu cầu của người dùng trong chat > bộ quy tắc này > thói quen mặc định.
> Người dùng yêu cầu điều trái quy tắc thì vẫn làm theo người dùng, kèm một dòng ⚠️ nêu rõ quy tắc nào bị phá và rủi ro.
> Quy tắc được viết ra từ những lần người dùng sửa phim. Mỗi lần người dùng sửa hay góp ý, cập nhật vào đây (mục 12).

---

## 0. Phim của chúng ta là gì

- Phim tài liệu cho YouTube, chủ đề bất kỳ: lịch sử, cổ văn, khoa học, bí ẩn, nhân vật, sự kiện.
- **Ngôn ngữ trên phim và lời dẫn** theo `language` của dự án (mặc định tiếng Anh, khán giả Mỹ). Ghi chú nội bộ và trả lời người dùng bằng tiếng Việt.
- **Xương sống luận điểm = nguồn có thật:** tài liệu gốc, sách, bài học thuật, báo chí, phỏng vấn/podcast, tư liệu người dùng đưa vào `sources/`, và kho highlight JRE khi dự án bật nguồn này. Lời dẫn nối các nguồn và đặt bối cảnh.
- **Hình ảnh:**
  - nhân vật và bối cảnh do AI vẽ (Higgsfield), tách lớp để dựng 3D;
  - footage thật (tư liệu, cảnh quay hiệu ứng lửa/khói) khi có giấy phép;
  - Claude dựng chuyển động, không gian 3D nhiều lớp, hiệu ứng, chữ và âm thanh bằng code (engine trong `film/`, cẩm nang `film/ENGINE.md`).
- **Phim mẫu tham chiếu:**
  - `D:\VideoLab\watchers-v2`: The Watchers v2.2, Book of Enoch 6–10, 32 s, ảnh Soul Cinema + Nano Banana Pro. Cảnh lò rèn `src/scenes/Azazel.tsx` là mẫu hiệu ứng lửa, khói, tia lửa, ánh sáng.
  - `D:\VideoLab\watchers-gpt`: cùng phim, cùng code, ảnh GPT Image 2.5 (so sánh A/B trong `out/ab_v2_vs_gpt.mp4`).

## 1. Tính xác thực (phim tài liệu)

1.1 Chỉ trình bày như **tư liệu** những gì có nguồn kiểm chứng được. Trích dẫn văn bản cổ phải lấy từ một bản dịch có tên, ưu tiên bản thuộc phạm vi công cộng (ví dụ R.H. Charles 1917 cho 1 Enoch), và ghi chương:câu. Không bịa câu trích. Câu diễn ý (paraphrase) không được đặt trong ngoặc kép như nguyên văn.
1.2 Hình ảnh, biểu tượng hay chi tiết **không có trong nguồn** là *tái hiện nghệ thuật*. Không trình bày chúng như tư liệu gốc. Ưu tiên hình ảnh bám văn bản (ví dụ: lời thề "trói buộc lẫn nhau" = sợi sáng nối tay các Watcher với nhau; tên núi Hermon ↔ *ḥērem* theo 1 Enoch 6:6). Nếu vẫn dùng chi tiết tự tạo thì ghi chú nhỏ "artistic reconstruction". *(Nguồn gốc: vụ vòng ấn lời thề, 2026-09-29.)*
1.3 **Kiểm tra niên đại và nguồn gốc** của mọi biểu tượng, trang phục, vật dụng trước khi đưa vào phim. Ví dụ: sao 6 cánh chỉ thành biểu tượng Do Thái từ thế kỷ 17 (Prague), không có trong 1 Enoch (thế kỷ 3–1 TCN). Nếu đưa vào là sai niên đại.
1.4 **Không trộn nguồn.** Ví dụ: Sách Enoch (1 Enoch, cổ đại) ≠ "Enochian" của John Dee (ma thuật thế kỷ 16). Khi một khái niệm "nghe quen trên mạng", truy ra nguồn gốc trước khi dùng.
1.5 Người dùng đưa tiền đề có vẻ sai thì **kiểm chứng bằng WebSearch/WebFetch**, trình bày bằng chứng kèm link nguồn, đề xuất phương án đúng rồi để người dùng quyết. Không im lặng làm theo, cũng không tự ý bác bỏ.
1.6 **Trích phỏng vấn, podcast** (kể cả kho highlight JRE):
  - chữ trên màn hình phải đúng nguyên văn transcript;
  - clip cắt đúng lời, không ghép làm sai ý người nói;
  - luôn ghi tên người nói và nguồn (chương trình, số tập hoặc ngày);
  - lời khẳng định của khách mời là *ý kiến của họ*, không trình bày như sự thật đã kiểm chứng. Nếu là tuyên bố gây tranh cãi, lời dẫn đặt bối cảnh hoặc nêu phản biện có nguồn.
  - **Luận đề, lời dẫn và tựa phim không được khẳng định tuyên bố gây tranh cãi như sự thật.** Đặt thành câu hỏi hoặc ghi rõ ai tuyên bố:
    - viết "A pilot claims he flew a 10-foot body out of Kandahar. Who took it?";
    - không viết "Giants existed and the evidence is being suppressed".

    Sức hút đến từ bí ẩn và lời chứng, không phải từ việc phim tự đứng ra khẳng định.
1.7 **Biểu tượng nhạy cảm:** không gắn biểu tượng của tôn giáo, dân tộc hay cộng đồng có thật (Ngôi sao David, thánh giá, trăng lưỡi liềm, chữ Vạn...) cho phe ác hay ma quỷ. Tránh cả ký hiệu sáo mòn kiểu phim kinh dị (ngôi sao năm cánh ngược). Khi cần một ký hiệu huyền bí, dùng hình học trung tính hoặc chữ viết lấy từ chính nguồn (vòng rune, vòng chữ, sao 7 cánh {7/3}). Ảnh AI hay tự thêm hoa văn hình chữ thập lên áo: luôn ghi "no symbols, no emblems" trong prompt và soát lại.
1.8 Bản quyền: bản dịch cổ văn dùng bản công cộng hoặc trích rất ngắn. Nhạc và hiệu ứng âm thanh tự tổng hợp (không tải nhạc về). Trích phỏng vấn/podcast dạng đoạn ngắn có bình luận và dựng lại.
1.9 **Footage tải từ web** (cảnh quay lửa, khói, tia lửa, bụi trên nền đen; tư liệu lịch sử; ảnh tư liệu):
  - chỉ lấy từ nguồn có giấy phép cho dùng thương mại (Pexels, Pixabay, Mixkit, Wikimedia Commons với giấy phép ghi rõ, kho lưu trữ công; trả phí: ActionVFX);
  - **chưa tải gì khi người dùng chưa duyệt.** Ghi từng file vào `5_footage/footage.json` với `status: "proposed"` (tên, trang nguồn, giấy phép, độ dài, độ phân giải, dung lượng). Người dùng duyệt trên app (`5_footage/approvals.json`) hoặc trong chat;
  - đã duyệt thì tải vào `film/assets/fx/` (hiệu ứng) hoặc `film/assets/archival/` (tư liệu), ghi nguồn vào `notes/sources.md`.
1.10 **Người thật** (nhất là người còn sống hoặc mới mất):
  - không vẽ AI giống hệt người thật rồi trình bày như ảnh chụp;
  - ưu tiên ảnh tư liệu có giấy phép; nếu tái hiện thì cách điệu (bóng đen, tranh vẽ, nhìn từ xa) và ghi "artistic reconstruction";
  - không đặt lời vào miệng họ: chỉ trích nguyên văn có nguồn.

## 2. Quy trình một dự án (6 bước)

Mỗi dự án có thư mục riêng:

```
project.json        app ghi: mô tả dự án, trạng thái các bước (đọc đầu tiên)
sources/            tư liệu người dùng (pdf, txt, srt, ảnh, audio) + links.txt
1_script/           bước 1: research.md, sources.json, script.json, script.md
2_cast/             bước 2: cast.json, cast.md, casting/ (ảnh thử vai), choices.json (app ghi)
3_scenes/           bước 3: scenes.json, scenes.md
4_images/           bước 4: manifest.json, bảng xem nhanh *.jpg (ảnh nằm trong film/)
5_footage/          bước 5: footage.json, approvals.json (app ghi)
6_render/           bước 6: render.json
film/               dự án Remotion app dựng từ engine ở bước 4 (node_modules là liên kết dùng chung)
out/                các bản render, out/review/
notes/              credits.json, sources.md, runs/ (nhật ký các lượt, app ghi)
```

- **Trạng thái bước** (app quản lý): chưa tới → sẵn sàng → đang chạy → chờ duyệt → đã duyệt. Bước sau chỉ mở khi bước trước được duyệt. App kiểm tra file đầu ra sau mỗi lượt; thiếu file bắt buộc thì bước báo lỗi.
- **Mỗi bước chỉ làm việc của bước đó.** Không làm trước bước sau khi người dùng chưa bảo (dự án ở chế độ tự chạy thì app tự chuyển bước).
- Người dùng có thể nhắn chat bất kỳ lúc nào để chỉnh (mục 2.7).
- Các file JSON là JSON hợp lệ, UTF-8, đúng lược đồ mục 11: app đọc chúng để hiển thị. Đường dẫn file trong JSON luôn **tương đối với thư mục dự án**, dùng `/`.

### 2.1 Bước 1 · Kịch bản (`1_script/`)

- **Đầu vào:** `project.json` (chủ đề, yêu cầu riêng, ngôn ngữ, khán giả, định dạng, thời lượng), `sources/` (đọc **trước** khi tra web), kho highlight JRE nếu dự án bật.
- **Làm:**
  1. Nghiên cứu: đọc hết tư liệu người dùng; tra thêm bằng WebSearch/WebFetch, ưu tiên nguồn gốc (primary) và học thuật; ghi từng nguồn vào `sources.json` kèm độ tin cậy.
  2. Tách các khẳng định quan trọng thành `claims` với trạng thái `verified | disputed | unverified` và nguồn. Khẳng định chưa kiểm chứng không được nói như sự thật (mục 1.6).
  3. Luận đề một câu + 2–3 hướng dàn ý (trong `research.md`); chọn hướng hợp yêu cầu nhất, nêu lý do. Người dùng có thể đổi ở cổng duyệt.
  4. Phong cách hình ảnh: nếu dự án chưa có `style`, đề xuất một chuỗi phong cách (mục 3) hợp chủ đề và ghi vào `script.json`.
  5. Viết kịch bản thành các **beat**:
     - cấu trúc mặc định: cold open (câu mạnh nhất hoặc hình ảnh bí ẩn nhất, ≤ 15 s), tựa phim, 3–5 hồi, kết (điều còn bỏ ngỏ hoặc câu khép lại);
     - mỗi beat: loại, thời lượng, lời dẫn, chữ trên màn hình, trích dẫn nguyên văn (nếu có), ý tưởng hình ảnh, nhân vật xuất hiện, nguồn;
     - lời dẫn: câu ngắn, giọng tài liệu điềm tĩnh; đọc ≈ 150 từ/phút; mỗi phụ đề ≤ 2 dòng (≈ 16 từ), đủ thời gian đọc ≥ 0,35 s/từ + 1 s;
     - tổng thời lượng = `target_sec` ± 10%.
  6. Kiểm chứng: mọi trích dẫn nguyên văn so chuỗi bằng python với văn bản nguồn (transcript, bản dịch); mọi khẳng định sự thật trong lời dẫn có nguồn trong `sources.json`.
  7. Ước tính credit giọng đọc (mục 3).
- **Đầu ra:** `research.md` (bản đọc: nguồn chính, luận đề, các hướng dàn ý, khẳng định cần thận trọng), `sources.json` + `script.json` (mục 11.1), `script.md` (kịch bản đọc được, chia hồi, có thời lượng từng beat).
- **Cổng duyệt:** người dùng bấm Duyệt (hoặc nói "duyệt") thì mới sang bước 2.

### 2.2 Bước 2 · Tuyển nhân vật (`2_cast/`)

- **Đầu vào:** `script.json` đã duyệt, `sources.json`.
- **Làm:**
  1. Gom mọi nhân vật trong các beat: vai chính, phụ, đám đông, người dẫn (chỉ có giọng). Gộp vai trùng.
  2. Mỗi vai:
     - mô tả, ngoại hình **bám nguồn và niên đại** (mục 1.3): tuổi, vóc dáng, trang phục, màu, đạo cụ; ghi nguồn;
     - cách thể hiện `depiction`: `ai_reconstruction` (vẽ AI), `archival_photo` (ảnh tư liệu), `silhouette` (bóng), `none` (chỉ nhắc tên); người thật theo mục 1.10;
     - các tư thế cần (từ beat), ví dụ đứng, chỉ tay, giơ tay cầm lửa, bị trói;
     - prompt ảnh gốc hoàn chỉnh theo mục 3 (nhân vật cần tách: toàn thân, nền xám trơn, chuỗi phong cách cuối prompt).
  3. **Ảnh thử vai:** tối đa 2 ứng viên cho mỗi vai chính và phụ có `ai_reconstruction`, model rẻ (mục 3), lưu `2_cast/casting/<id>_<n>.png`. Tổng credit thử vai ≤ 10% ngân sách. Vai đám đông và vai không vẽ thì không thử vai.
- **Đầu ra:** `cast.json` (mục 11.2), `cast.md` (bảng vai: tên, vai trò, cách thể hiện, ngoại hình, beat xuất hiện).
- **Cổng duyệt:** người dùng chọn ứng viên trên app (app ghi `2_cast/choices.json`: `{id_nhân_vật: đường_dẫn_ảnh}`), hoặc nhắn sửa ngoại hình để thử vai lại, rồi Duyệt.

### 2.3 Bước 3 · Phân cảnh & bối cảnh (`3_scenes/`)

- **Đầu vào:** `script.json`, `cast.json`, `choices.json`.
- **Làm:**
  1. Chia các beat thành **cảnh dựng được** (thường 6–20 s/cảnh, một beat có thể thành nhiều cảnh và ngược lại). Mỗi cảnh là một sân khấu 3D (mục 4): bối cảnh, các lớp theo độ sâu, nhân vật + tư thế, chuyển động máy quay, hiệu ứng (mục 5), âm thanh, lời dẫn và chữ.
  2. Danh sách **bối cảnh** (locations): mô tả bám niên đại, các tấm nền cần vẽ cho mỗi bối cảnh (trời, xa, trung, tiền cảnh). Dùng lại một bối cảnh cho nhiều cảnh khi được.
  3. Danh sách **ảnh cần vẽ** (assets): mỗi ảnh một `key`, loại, model, chất lượng, tỉ lệ, prompt hoàn chỉnh (chuỗi phong cách cuối prompt), ảnh gốc `base` cho biến thể, credit ước tính (mục 3). Nhân vật: ảnh gốc từ ứng viên đã chọn, rồi biến thể.
  4. Danh sách **footage cần** (footage_needs): hiệu ứng quay thật (lửa, khói…), tư liệu, clip phỏng vấn, giọng đọc, nhạc.
  5. Tổng credit ước tính của bước 4 + 5 ≤ ngân sách còn lại. Vượt thì đề xuất cắt giảm (dùng lại ảnh, chất lượng medium cho nền).
- **Đầu ra:** `scenes.json` (mục 11.3), `scenes.md` (bảng cảnh, bảng bối cảnh, bảng ảnh với tổng credit, bảng footage).
- **Cổng duyệt:** duyệt bước 3 = duyệt danh sách ảnh và số credit sẽ tiêu ở bước 4.

### 2.4 Bước 4 · Render hình ảnh (`4_images/`, ảnh trong `film/`)

- App đã dựng khung `film/` từ engine. `film/node_modules` là liên kết tới engine dùng chung: không `npm install`, **không bao giờ xóa** nó hay thứ gì bên trong.
- **Làm:**
  1. Kiểm tra số dư Higgsfield (`balance`), ghi `notes/credits.json` trước và sau.
  2. Thứ tự: ảnh gốc nhân vật (từ ứng viên đã chọn trong `choices.json`: dùng làm ảnh tham chiếu để vẽ bản chất lượng cao, hoặc dùng luôn nếu đã đủ tốt) → biến thể (sửa từ ảnh gốc, mục 3) → nền bối cảnh → đạo cụ → lớp additive (sương, ánh sáng, lông vũ trên nền đen).
  3. Gửi tối đa 3 job cùng lúc (mục 3), chờ bằng `show_generations`, tải ảnh gốc về `film/assets/raw/<key>.png`.
  4. Tách nền trên máy: `"$BGREMOVE_PY" scripts/cutout.py assets/raw/<key>.png --out public/img` (chạy trong `film/`). Nền và lớp additive không tách: chép thẳng vào `film/public/img/`. **Xem bảng soát** `film/out/stills/cutouts.jpg`.
  5. Soát từng ảnh: đúng niên đại, không biểu tượng cấm (mục 1.7), nhân vật giữ đúng nhân dạng giữa các biến thể, khung đủ lề (đầu cánh, chân không bị cắt). Lỗi thì làm lại ngay (vẫn trong ngân sách).
  6. Đo điểm neo theo mục 6 (tay, chân, đỉnh núi, miệng lò…) và ghi vào `landmarks` của từng ảnh trong manifest.
  7. Ghép bảng xem nhanh theo nhóm vào `4_images/sheet_<nhóm>.jpg`.
- **Đầu ra:** `manifest.json` (mục 11.4), bảng xem nhanh.
- **Cổng duyệt:** người dùng xem gallery trên app, bấm "Làm lại" kèm ghi chú cho ảnh chưa ưng (app gửi thành tin nhắn chat), rồi Duyệt.

### 2.5 Bước 5 · Footage & âm thanh (`5_footage/`)

- **Làm:**
  1. **Footage** theo `footage_needs` và mục 1.9: tìm, ghi từng file vào `footage.json` với `status: "proposed"`. **Không tải** khi chưa có quyết định trong `5_footage/approvals.json` (`approved`) hoặc lời duyệt trong chat. Lượt sau: tải mục đã duyệt, xử lý bằng `scripts/fx-prep.mjs` (cắt, khử nền đen, đo độ chập chờn), cập nhật `status` và `file`. Mục bị bỏ (`rejected`): tìm phương án khác hoặc dựng bằng code.
  2. **Clip phỏng vấn/podcast** (nếu kịch bản có trích): cắt bằng `node scripts/clip.mjs` vào `film/public/clips/`, đúng nguyên văn (mục 1.6).
  3. **Lời dẫn** theo mục 8.4: một lần đọc cả kịch bản, chọn bản bằng whisper, đặt câu theo cảnh (`audio/voice/plan.json` + `scripts/voice-build.py`).
  4. **Nhạc và hiệu ứng âm thanh:** tự tổng hợp (mục 8.1); ghi kế hoạch vào `footage.json` (`music`).
- **Đầu ra:** `footage.json` (mục 11.5), file trong `film/public/fx`, `film/public/clips`, `film/audio/voice`.
- **Cổng duyệt:** mọi footage đã duyệt đã tải xong, giọng đọc đã chọn thì người dùng Duyệt.

### 2.6 Bước 6 · Dựng & render (`6_render/`, `film/`, `out/`)

1. Đọc `film/ENGINE.md`, xem các cảnh mẫu trong phim tham chiếu (mục 0).
2. Viết `src/timeline.js`, `src/assets.ts`, các cảnh và `Film.tsx` theo `scenes.json`: đúng bối cảnh, lớp, máy quay, hiệu ứng đã duyệt.
3. Soát ảnh tĩnh (mục 9), sửa.
4. Âm thanh: `make-audio` trộn nhạc, hiệu ứng, lời dẫn; master −15 LUFS (mục 8).
5. Render `out/<slug>_v<N>.mp4`. **Không ghi đè bản cũ**, mỗi lần render tăng N.
6. QA (mục 9) trên chính file MP4, ghi `6_render/render.json` (mục 11.6) kèm kết quả QA và bảng ghép `out/review/contact_v<N>.jpg`.
- **Cổng duyệt:** người dùng xem phim; góp ý qua chat (2.7) thành bản v<N+1>. Duyệt = chốt bản cuối.

### 2.7 Sửa theo góp ý (chat)

- Tin nhắn chat kèm bước người dùng đang xem. Sửa đúng file của bước đó, soát lại đúng chỗ đã sửa (ảnh tĩnh hoặc cắt cận), báo cáo đã sửa gì và bằng chứng.
- Thay đổi ảnh hưởng các bước sau (ví dụ đổi kịch bản khi đã có ảnh) thì nói rõ cần làm lại gì và tốn bao nhiêu credit; chưa tự làm lại bước sau khi chưa được bảo.
- Góp ý mang tính nguyên tắc thì **ghi thành quy tắc** (mục 12).

## 3. Ảnh AI với Higgsfield

- **Công cụ (headless):**
  - `mcp__claude_ai_HF__balance`, `generate_image`, `show_generations`, `models_explore`, `create_project`, `media_upload` + `media_confirm`;
  - lời dẫn: `generate_audio`, `list_voices`, `show_generations`;
  - `remove_background` chỉ dự phòng: tách nền làm trên máy.
  - Mỗi phim một project Higgsfield. Mọi lần tạo **ảnh** dùng `folder_id` của project đó. Riêng `elevenlabs_v4` **không** truyền `folder_id` (bị lỗi 422).
- **Mẹo dùng connector (đo 2026-09-30):**
  - Sau khi connector kết nối lại, tham số dạng mảng có thể bị biến thành chuỗi: `generate_image_batch`, `jobs_wait`, `show_generation_by_ids` báo lỗi. Khi đó: gọi `generate_image` từng ảnh với `params` là object, chờ bằng `show_generations(type: "image", size: N)`.
  - Tải ảnh lên làm tham chiếu: `media_upload(filename)` → PUT file lên URL được ký (curl) → `media_confirm(type: "image", media_id)`.
  - Sửa từ một ảnh đã tạo: truyền job id cũ trong `medias` với `role: "image_references"`, không cần tải lên lại.
  - Gửi quá nhiều job GPT cùng lúc bị 429 (không bị trừ credit): gửi tối đa 3 job, chờ xong rồi gửi tiếp.
  - Job bị timeout thì không tự gửi lại: xem `show_generations` trước.
- **Chi phí đo thực tế (2026-09/10):**

  | Việc | Model | Credit |
  |---|---|---|
  | Ảnh 2k | `soul_cinematic` | 0,12 |
  | Ảnh | `nano_banana_pro` | 2 |
  | Ảnh 2k chất lượng high (mọi tỉ lệ) | `gpt_image_2_5` (sunburst/flare) | 2,75 |
  | Ảnh 2k chất lượng medium | `gpt_image_2_5` | 1 |
  | Ảnh 2k chất lượng xhigh | `gpt_image_2_5` | 4,5 |
  | Tách nền trên máy | `scripts/cutout.py` | **0** |
  | Tách nền (dự phòng) | `remove_background` | ≈ 1 |
  | Lời dẫn | `elevenlabs_v4` | 0,23 / 50 ký tự ≈ 4,6 / 1.000 ký tự ≈ 4,3 / phút đọc |
  | Video 5 s | `kling3_0` | 8,75 |
  | Video 5 s | `seedance_2_5` | 35 |

  Trần credit mỗi dự án: "ngân sách credit" trong `project.json`. Sắp vượt thì dừng và hỏi.
- **Chọn model theo việc** (thử nghiệm 2026-09-30: The Watchers làm hai lần, Soul + Nano Banana Pro và GPT Image 2.5):
  - **Ảnh thử vai, nền rẻ:** `soul_cinematic` (0,12) hoặc `gpt_image_2_5` medium (1).
  - **Nhân vật gốc và biến thể cần giữ đúng nhân dạng, cảnh cần đếm đúng số người:** `gpt_image_2_5` high. Giữ nhân vật tốt nhất khi đổi tư thế, đếm đúng (7/7 người so với 6/7 của Nano Banana Pro), chi tiết nền phong phú.
  - **Phong cách tranh sơn dầu, màu thống nhất:** `nano_banana_pro` hoặc `soul_cinematic`. GPT ngả về ảnh chụp: nếu dùng GPT thì chuỗi phong cách phải mạnh ("painterly oil painting with visible brushwork…") và soát lại.
  - Sửa ảnh (đổi tư thế, xoá vật, đổi trang phục): GPT và Nano Banana Pro ngang nhau. Prompt: "Edit this image. Keep the same … Only change …". Soul Cinema kèm ảnh tham chiếu sẽ chép gần như y nguyên, không dùng để sửa.
  - Nền trời, cảnh xa: chất lượng medium là đủ (bị làm mờ theo độ sâu).
- **Lưu ý khi dùng ảnh GPT** (rút từ bản Watchers GPT):
  - nhân vật chiếm nhiều khung hơn: chỉnh chiều cao trong cảnh theo độ dài đầu → chân, không theo cạnh ảnh;
  - núi, công trình hay bị vẽ chạm mép trên: ghi rõ vị trí ("summit at 40% from the top, plain background above") hoặc sửa "zoom out";
  - áo rộng, cánh rủ sát người: rig cần `body` lớn hơn để vạt áo không vẫy theo cánh;
  - kiểm tra hướng tay, hướng nhìn so với bố cục cảnh (lật ngang ảnh nếu cần);
  - viền vàng, hào quang làm sai phép đo vị trí lửa trên tay: đo trong vùng hẹp.
- **Cách tạo từng loại:**
  - Nhân vật/đạo cụ cần tách: toàn thân, ở giữa, chừa lề, **nền xám trơn phẳng**, không mặt đất, không chữ. Sau đó tách trên máy:
    - `"$BGREMOVE_PY" scripts/cutout.py assets/raw/<ảnh>.png --out public/img`;
    - `cutout.py` khử viền xám, và lấy lại chi tiết mảnh tách rời (vòng hào quang);
    - `--mode matting` **chỉ** cho vật trong mờ (lửa, khói, quầng sáng), không bao giờ cho cảnh vật (làm đá thành bán trong suốt);
    - luôn xem bảng soát `out/stills/cutouts.jpg` (nền đỏ tối và nền xám).
    *(Nguồn gốc: so sánh 12 ảnh Watchers, 2026-09-30: trên máy khớp HF 97–99%, sạch viền hơn, 0 credit.)*
  - **Không vẽ lửa hay khói vào ảnh tĩnh.** Lửa đứng im trông giả, tách nền còn kẹt mảng xám giữa các lưỡi lửa. Ảnh lỡ có lửa vẽ sẵn thì xoá đi (sửa ảnh, hoặc mặt nạ màu + inpaint) và thay bằng cảnh quay thật (mục 5.8). Nêu rõ trong prompt: "no fire, no flames, no smoke" cho đạo cụ sẽ có lửa thật.
  - Sương, ánh sáng, lông vũ: vẽ **trên nền đen tuyền** rồi dùng `blend="add"`, không tách nền. Tách nền để lại viền đen trên vật trắng mềm.
  - Cảnh nền (plate): không nhân vật, không chữ. Chừa khoảng cho chủ thể đứng.
- **Một chuỗi phong cách cho cả phim**, gắn vào cuối mọi prompt. Ví dụ: *dark biblical fantasy concept art, painterly oil painting with visible brushwork, cinematic lighting, ... in the spirit of Gustave Dore and modern film concept art*.
- **Tính đồng nhất:** mỗi nhân vật có một ảnh gốc. Mọi biến thể đều sửa từ ảnh gốc đó.
- **Lỗi ngẫu nhiên:** khoảng 1/5 job `soul_cinematic` báo `failed`, cứ tạo lại.
- **Tải về:** tải `rawUrl` vào `film/assets/raw/`, đặt tên theo `key`. Xem lại bằng bảng ghép trước khi dùng.
- **Video AI** (Kling) chỉ dùng cho khoảnh khắc "diễn" đắt nhất mà biến dạng lưới không làm được, và phải hỏi người dùng trước.

## 4. Không gian 3D nhiều lớp

4.1 Mọi cảnh là một sân khấu 3D (multiplane): mỗi lớp là một tấm phẳng ở **độ sâu thật**. Máy quay phải **di chuyển thật** (tiến vào, lia ngang, vòng quanh), không chỉ phóng to. Máy quay nhìn về −z: **tiến vào là z âm** (z dương là lùi ra). *(Người dùng muốn "không gian đa chiều".)*
4.2 Các lớp chuẩn:
  - trời ở z −130…−170 (`dof={false}`, cao `frameH(d)*1.35–1.4`);
  - dãy núi hoặc cảnh xa ở z −60…−110;
  - sương (additive) xen giữa các lớp;
  - nhân vật ở z −15…−45;
  - tiền cảnh (đá, sương, tàn lửa) ở z −7…−15, được làm mờ theo độ sâu.
4.3 Độ nét sâu: đặt `focus` vào chủ thể, `aperture` 1,2–1,5. Có thể chuyển điểm lấy nét (rack focus) khi chuyển chủ thể.
4.4 **Bố cục:**
  - khối chữ ở đáy khung (trên thanh letterbox 100 px) phải tối và thoáng;
  - đầu, hào quang, đầu cánh không bị letterbox cắt;
  - phải kiểm tra khung ở **đầu, giữa, cuối** mỗi đường máy quay, vì máy quay tiến vào làm chủ thể to dần.
4.5 Khi máy quay đi vòng, nhân vật quay mặt theo máy (billboard). Không để lộ nhân vật là tấm bìa phẳng nhìn nghiêng.

## 5. Chuyển động và hiệu ứng

5.1 **Không dùng nội suy tuyến tính** cho vật sống. Dùng lò xo (spring) hoặc easing vào/ra, có quán tính.
5.2 **Cánh:**
  - nhịp đập lan từ vai ra như sóng: đầu cánh trễ hơn và cong hơn (overlapping action, follow-through);
  - nhịp đập xuống nhanh hơn nhịp nâng lên;
  - biên độ 0,03–0,06 khi đứng, tới 0,12 khi bay.

  *(Nguồn gốc: người dùng chê "đôi cánh bay lên không mềm mại".)*
5.3 **Chuyển động phụ:** vạt áo đung đưa, thở, bay lơ lửng nhẹ. Không có nhân vật nào đứng im tuyệt đối.
5.4 **Vật nhẹ rơi** (lông vũ, tro, lá) dùng mô phỏng vật lý `simulateFeather`: lượn, chậm dần, chúc lên ở cuối nhịp rồi đổi hướng. Góc xoay đi theo hướng bay. Thông số dò bằng `feather-search.mjs`, không lộn vòng. *(Nguồn gốc: người dùng chê lông vũ "bay zic zắc, không như vật lý thực tế".)*
5.5 **Vật thể từ trời xuống** (sao, ánh sáng): đường cong, nhanh lúc đầu, chậm dần rồi chạm nhẹ. Vệt đuôi liền mạch. Khi chạm có loé sáng rồi đốm sáng nằm lại **đúng trên bề mặt**.
5.6 **Sợi sáng, xích:** đung đưa nhẹ, có luồng năng lượng chạy dọc. Xích có độ võng tự nhiên.
5.7 **Máy quay:** có quán tính (easing sin), rung nhẹ khi va chạm lớn rồi tắt dần. Không giật cục.
5.8 **Lửa và khói phải là chuyển động thật:** cảnh quay thật trên nền đen (mục 1.9) qua `<VideoFx>`, thu thành dáng ngọn lửa (`taper`), gốc lửa khuất sau miệng vật chứa (`mouth`). Code chỉ làm lửa ma thuật (lửa trên tay, lửa của ấn). *(Nguồn gốc: bản thử lò rèn 2026-09-30 được duyệt.)*
5.9 **Lửa phải thắp sáng cảnh:** mọi tấm ảnh gần đám lửa nhận `light` (ánh sáng điểm, nhân vào màu bề mặt), cường độ chập chờn theo đúng độ sáng của clip lửa (`fx-prep --flicker`). Va chạm (búa, sét) làm loé thêm.
5.10 **Tia lửa, tàn lửa:** `blowSparks` ở mỗi cue va chạm (vệt nhòe theo vận tốc, nguội dần trắng → cam → đỏ, nảy trên mặt đất), `risingEmbers` bốc lên từ đám lửa. Không dùng chấm tròn đứng yên.
5.11 **Hậu kỳ máy quay:** cảnh có lửa hay nguồn sáng mạnh bật `post={{bloom, haze}}` (quầng sáng quanh vùng sáng, không khí méo phía trên lửa). Nhân vật tách nền đặt trong không khí có màu thì thêm `wrap` 0,1–0,2 (ánh nền tràn qua viền).
5.12 **Hiệu ứng phải nằm trong khung nhìn:** kiểm tra mép dưới khung (letterbox, tiền cảnh). Bản thử đầu tiên đặt chậu than dưới mép khung, lửa thật không ai thấy.

## 6. Neo vật thể và tính nhất quán không gian

6.1 **Đo landmark từ pixel, không ước lượng bằng mắt trên lưới 10%:**
  - `measure.mjs ridge`: đường viền (alpha) của núi hoặc mái nhà, nơi vật thể đáp xuống;
  - `measure.mjs glow`: vị trí tay đang cầm lửa hoặc ánh sáng;
  - `measure.mjs bbox`: vị trí chân;
  - `measure.mjs grid` (lưới 5%): những điểm không có màu đặc trưng.

  *(Nguồn gốc: sao đáp lệch đỉnh núi.)*
6.2 Mọi thứ gắn vào nhân vật (sợi sáng, xích, hào quang, lửa trên tay) phải lấy vị trí qua `makeActor(...).point()/.hands()`, để đi qua **cùng phép biến dạng cánh và phép xoay** như pixel. *(Nguồn gốc: sợi sáng lệch khỏi tay khi máy quay chạy.)*
6.3 Hiệu ứng phải bị che bởi vật đứng trước: engine đã có depth pass, không được tắt. Vật gắn vào chính nhân vật dùng `order = actor.order + 0.25`, nếu không cánh của chính nó sẽ nuốt mất.
6.4 Ánh sáng additive biến mất trên nền trắng: vật cần đọc được trên vùng sáng (xích qua cánh trắng) phải có lõi đặc (normal blend) và quầng additive bên ngoài.
6.5 **Kiểm chứng bằng cắt cận ảnh tĩnh ở ít nhất hai vị trí máy quay** mỗi khi có vật thể neo. Chỉ nhìn cả khung ở cỡ nhỏ thì không đủ.

## 7. Chữ trên màn hình

7.1 Font: Cinzel cho tựa và dòng nguồn trích; Cormorant Garamond nghiêng cho lời dẫn và phụ đề.
7.2 Lời dẫn hiện từng chữ (mờ → rõ, nổi nhẹ). Dòng chia cân đối (`text-wrap: balance`), không để một chữ lẻ rớt xuống dòng dưới.
7.3 Trích nguyên văn đặt trong ngoặc kép cong “ ”, cắt bớt thì dùng "…". Dòng nguồn in hoa, giãn chữ, kiểu "1 ENOCH 6:4" hay "JOE ROGAN EXPERIENCE #2530".
7.4 Khi clip phỏng vấn đang phát: góc trên có tên người nói và nguồn, phụ đề là transcript nguyên văn theo từng dòng thời gian.

## 8. Âm thanh

8.1 Nhạc và hiệu ứng tự tổng hợp bằng `scripts/audio-lib.mjs` (drone, gió, boom, sấm, kim loại, xích, whoosh...). Mọi cue lấy từ `src/timeline.js`, nên hình và tiếng luôn khớp.
8.2 Clip phỏng vấn giữ tiếng gốc. Nhạc nền **hạ ~12 dB** dưới mọi trích đoạn (danh sách `QUOTES`).
8.3 **Master:** `m.write(...)` master 2 lượt (đo → chỉnh gain → limiter) về −15 LUFS. File cuối ≈ −15 LUFS, true peak ≤ −1,5 dBTP. *(Bản đầu tiên ở −20,6 LUFS, nghe nhỏ hơn video khác trên YouTube.)*
8.4 **Lời dẫn bằng giọng đọc** (ElevenLabs v4 qua Higgsfield). Làm theo `film/ENGINE.md` mục Narration:
  - Giọng mặc định trong `project.json` (Alistair `d9d5c263-f84e-4752-97b5-3750fcc6fd2f`: trầm, lớn tuổi, giọng Anh). Đổi giọng thì hỏi người dùng.
  - Chi phí nằm trong ước tính của kịch bản. Người dùng duyệt kịch bản là duyệt luôn chi phí giọng. Tối đa 3 bản đọc cho mỗi lượt viết lại lời dẫn; nhiều hơn thì hỏi.
  - **Đọc cả kịch bản trong một lần** (một `dialogue`, mỗi câu một lượt, cùng giọng): như một buổi thu, giọng liền mạch giữa các câu. `batch_size` N tính tiền N bản nhưng chỉ trả một URL, các bản kia tìm trong `show_generations(type: "audio")`.
  - Tag cảm xúc ngắn, mỗi câu một tag (`[reverent]`, `[ominous]`, `[low, intense]`, `[grave]`, `[sorrowful]`, `[solemn, firm]`, `[quietly]`), một hơi thở mở đầu `[inhales softly]`. Ngắt nhịp bằng "…" và "—". Không nhồi tag.
  - Chữ trên màn hình = đúng chữ được đọc (phụ đề hiện theo từng chữ được đọc).
  - Chọn bản đọc bằng whisper: đủ chữ, không đọc lọt tag, nhịp vừa cảnh. Đặt câu bằng `audio/voice/plan.json` + `scripts/voice-build.py`; tăng tốc tối đa 3%; từ khoá rơi đúng cue hình (ví dụ "hand and foot" đúng tiếng xích).
  - Cảnh không đủ chỗ cho câu đọc tự nhiên thì kéo dài cảnh (đuôi cảnh giữ hình), không đọc nhanh hơn.
  *(Nguồn gốc: người dùng yêu cầu lời dẫn giống người thật cho The Watchers, 2026-09-29.)*
8.5 **Trộn giọng:** `make-audio` tự hạ nhạc dưới giọng (dải trên −8 dB, dải trầm −3 dB, hạ thêm tới −10 dB chỗ nhạc lấn giọng). Hiệu ứng mạnh (sấm, nổ) đặt vào khoảng lặng giữa hai câu thì giữ nguyên lực.

## 9. Kiểm tra trước khi giao (bắt buộc)

1. `npx tsc --noEmit -p .` không báo lỗi.
2. `node scripts/stills.mjs ...`:
   - ảnh tĩnh ở đầu, giữa, cuối mỗi cảnh và ở mỗi lần chuyển cảnh;
   - **tự xem** bảng ghép `out/stills/sheet.jpg`;
   - cắt cận (`--crop`) mọi chỗ có vật thể neo.
3. Soát theo danh sách:
   - chữ không che mặt;
   - letterbox không cắt đầu nhân vật;
   - quầng sáng không lộ viền;
   - không có vật lơ lửng sai chỗ;
   - cảnh đầu không thiếu ảnh;
   - không có biểu tượng vi phạm mục 1.7.
4. Render xong chạy `node scripts/qa.mjs out/<file>.mp4`:
   - đủ số khung hình;
   - không có đoạn đen giữa phim;
   - có tiếng;
   - LUFS và peak đạt;
   - bảng ghép lấy từ **chính file MP4**.
5. So từng phụ đề trích với transcript (python).
6. Có lời dẫn:
   - cho whisper nghe lại file cuối: đủ mọi câu, không sai chữ;
   - giọng hơn nhạc ≥ 10 LU khi đang nói, trong dải 300–5000 Hz (đo `out/stem_voice.wav` với `out/stem_score.wav`).
7. Có hiệu ứng lửa/khói: trích 5–6 khung rải đều từ **chính file MP4** để chắc hiệu ứng có mặt ở mọi khung và nằm trong khung nhìn.
8. Báo cáo đúng sự thật. Chưa kiểm được thì nói là chưa kiểm (ví dụ: Claude không nghe được giọng, chỉ đo được).

## 10. Giao tiếp với người dùng

- Trả lời bằng tiếng Việt, ngắn gọn, đi thẳng vào việc. Người dùng xưng "tao/mày".
- Mỗi lượt kết thúc bằng:
  - làm gì, file nào;
  - bằng chứng đã kiểm (con số, ảnh);
  - credit Higgsfield đã tiêu (lượt này và cả dự án);
  - giới hạn còn lại (nói thật);
  - việc người dùng cần làm ở cổng duyệt (chọn ứng viên, duyệt footage, bấm Duyệt), hoặc câu hỏi nếu cần người dùng quyết.
- Lỗi phát hiện ra thì nhận là lỗi, giải thích nguyên nhân gốc, sửa tận gốc (trong engine của phim hoặc quy tắc) chứ không vá riêng một chỗ.
- Quyết định thuộc về người dùng (phong cách, tiêu credit lớn, chủ đề nhạy cảm) thì hỏi. Việc kỹ thuật có mặc định rõ ràng thì tự làm.
- Chạy headless thì không chờ người dùng giữa chừng: làm hết phần làm được, cuối lượt liệt kê câu hỏi.

## 11. Lược đồ file

Đường dẫn trong mọi file: tương đối với thư mục dự án, dấu `/`.

### 11.1 Bước 1: `1_script/sources.json` và `1_script/script.json`
```json
{"sources": [{"id": "S1", "type": "book|article|paper|video|podcast|web|archive|user_file|jre_segment",
   "title": "...", "author": "...", "date": "...", "url": "...", "file": "sources/x.pdf",
   "reliability": "primary|scholarly|journalism|opinion", "notes": "..."}],
 "claims": [{"id": "C1", "text": "...", "sources": ["S1"], "status": "verified|disputed|unverified", "note": "..."}]}
```
```json
{"title": "...", "logline": "...", "thesis": "luận đề một câu", "language": "en", "format": "16:9",
 "target_sec": 180, "est_sec": 176, "style": "chuỗi phong cách hình ảnh",
 "acts": [{"id": "A1", "title": "...", "summary": "..."}],
 "beats": [{"id": "b01", "act": "A1", "type": "cold_open|title|narration|quote|reconstruction|archival|outro",
   "duration_sec": 12, "narration": "lời dẫn đúng chữ sẽ đọc", "on_screen_text": "...",
   "quote": {"speaker": "...", "source": "S3", "text": "nguyên văn", "start_sec": 1234.5, "end_sec": 1250.2},
   "visual_idea": "...", "characters": ["Azazel"], "sources": ["S1"]}],
 "voice": {"name": "Alistair", "voice_id": "...", "chars": 2400, "est_credits": 11},
 "risks": ["..."], "open_questions": ["..."]}
```

### 11.2 Bước 2: `2_cast/cast.json` (+ `choices.json` do app ghi)
```json
{"style": "chuỗi phong cách chung",
 "characters": [{"id": "c_azazel", "name": "Azazel", "role": "main|supporting|crowd|narrator",
   "kind": "historical|mythical|fictional_composite|real_person|group",
   "depiction": "ai_reconstruction|archival_photo|silhouette|none",
   "description": "...", "look": "tuổi, vóc dáng, trang phục, màu, đạo cụ (có nguồn, đúng niên đại)", "sources": ["S1"],
   "beats": ["b03", "b07"], "poses": [{"key": "point", "desc": "...", "beats": ["b07"]}],
   "master_prompt": "...",
   "candidates": [{"file": "2_cast/casting/c_azazel_1.png", "model": "soul_cinematic", "job_id": "...", "credits": 0.12, "note": "..."}]}]}
```
`choices.json`: `{"c_azazel": "2_cast/casting/c_azazel_2.png"}`

### 11.3 Bước 3: `3_scenes/scenes.json`
```json
{"locations": [{"id": "l_hermon", "name": "...", "description": "...", "era": "...", "sources": ["S2"],
   "plates": [{"key": "hermon_sky", "layer": "sky|far|mid|fg", "aspect": "21:9"}]}],
 "scenes": [{"id": "sc01", "beats": ["b01"], "title": "...", "duration_sec": 14, "location": "l_hermon",
   "characters": [{"id": "c_azazel", "pose": "point"}],
   "layers": ["sky: hermon_sky", "far: hermon", "char: azazel_point", "fg: rocks"],
   "camera": "dolly in + pan right", "fx": ["fire_brazier", "embers"], "sound": ["thunder at 3.2s"],
   "narration": "...", "on_screen_text": "...", "footage": ["fx_fire_1"], "reconstruction": true}],
 "assets": [{"key": "azazel_point", "kind": "character|variant|plate|prop|additive", "of": "c_azazel",
   "base": "azazel", "model": "gpt_image_2_5|nano_banana_pro|soul_cinematic", "quality": "high|medium",
   "aspect": "1:1", "prompt": "...", "est_credits": 2.75}],
 "footage_needs": [{"id": "fx_fire_1", "type": "stock_fx|archival|interview_clip|voice|music|sfx",
   "desc": "...", "scenes": ["sc05"]}],
 "budget": {"est_credits": 31.5, "budget": 40}}
```

### 11.4 Bước 4: `4_images/manifest.json`
```json
{"balance_before": 36.9, "balance_after": 6.9,
 "assets": [{"key": "azazel_point", "kind": "character|variant|plate|prop|additive", "status": "done|failed|redo|pending",
   "model": "gpt_image_2_5", "job_id": "...", "credits": 2.75,
   "raw": "film/assets/raw/azazel_point.png", "file": "film/public/img/azazel_point.png", "cutout": true,
   "landmarks": {"hands": [[0.31, 0.545]], "feet": 0.985}, "note": "..."}],
 "sheets": ["4_images/sheet_characters.jpg"]}
```

### 11.5 Bước 5: `5_footage/footage.json` (+ `approvals.json` do app ghi)
```json
{"items": [{"id": "fx_fire_1", "type": "stock_fx|archival|interview_clip|voice|music|sfx", "title": "...",
   "source_page": "https://...", "license": "Pexels License", "duration_sec": 12, "resolution": "1920x1080",
   "size_mb": 18, "status": "proposed|approved|downloaded|processed|generated|rejected",
   "file": "film/public/fx/fire_brazier.mp4", "scenes": ["sc05"], "note": "..."}],
 "voice": {"voice": "Alistair", "takes": [{"file": "film/audio/voice/take1.mp3", "credits": 2.3, "chosen": true}],
   "plan": "film/audio/voice/plan.json"},
 "music": {"approach": "tự tổng hợp (audio-lib)", "notes": "..."}}
```
`approvals.json`: `{"fx_fire_1": {"decision": "approved|rejected", "at": "2026-10-03T15:00:00"}}`

### 11.6 Bước 6: `6_render/render.json`
```json
{"versions": [{"file": "out/the-watchers_v1.mp4", "created": "2026-10-03T16:00:00", "duration_sec": 180,
   "qa": {"ok": true, "lufs": -15.0, "true_peak": -1.6, "frames": 5400, "black": [], "notes": "..."},
   "sheet": "out/review/contact_v1.jpg", "changes": "bản đầu"}]}
```

### 11.7 `notes/credits.json`
```json
{"total": 12.4, "events": [{"at": "2026-10-03T15:10:00", "step": "images", "what": "azazel_point",
   "model": "gpt_image_2_5 high", "credits": 2.75, "balance_after": 24.1}]}
```

## 12. Nhật ký quy tắc (cập nhật mỗi khi người dùng sửa)

Cách cập nhật: sửa đúng mục liên quan ở trên (ngắn gọn, có lý do), rồi thêm một dòng vào đây theo dạng `YYYY-MM-DD · dự án · thay đổi`. Muốn **xóa** quy tắc thì phải hỏi người dùng.

- 2026-09-29 · JRE Studio · Rút từ phim thử The Watchers:
  - v1 bị chê chuyển động cứng, nhân vật thô, không gian phẳng → mục 3, 4, 5;
  - v2 bị chê sao đáp lệch đỉnh núi và sợi sáng trượt khỏi tay → mục 6;
  - tranh luận sao 6 cánh và sao 7 cánh → mục 1.2–1.5, 1.7;
  - độ to âm thanh −20,6 LUFS → mục 8.3;
  - các lỗi tự soát (chữ lẻ rớt dòng, quầng sáng lộ viền, xích vàng biến mất trên cánh trắng, letterbox cắt đầu) → mục 4.4, 6.4, 7.2.
- 2026-09-29 · The Watchers v2.2 · Lời dẫn ElevenLabs v4 (giọng Alistair), một lần đọc cả kịch bản, phụ đề theo từng chữ, ducking 2 dải, master −15 LUFS → mục 3, 8.3–8.5, 9.6.
- 2026-09-30 · thử nghiệm · Tách nền trên máy thay Higgsfield (0 credit, sạch viền hơn); lửa, khói là cảnh quay thật, lửa thắp sáng cảnh, tia lửa, bloom, không khí méo; clip tải về phải được duyệt trước → mục 1.9, 3, 5.8–5.12, 9.7.
- 2026-09-30 · The Watchers GPT · So sánh Nano Banana Pro và GPT Image 2.5, làm lại cả phim bằng ảnh GPT: bảng giá GPT, chọn model theo việc, lưu ý khi dùng ảnh GPT, mẹo dùng connector Higgsfield; máy quay tiến vào là z âm → mục 3, 4.1.
- 2026-10-03 · Creater Vid · Tách thành app riêng, không chỉ JRE: quy trình 6 bước (kịch bản → tuyển nhân vật → phân cảnh & bối cảnh → render hình ảnh → footage & âm thanh → dựng & render) có cổng duyệt từng bước; nguồn tư liệu tổng quát; người thật → mục 0, 1.6, 1.9, 1.10, 2, 10, 11.
