# BỘ QUY TẮC LÀM PHIM TÀI LIỆU · Creater Vid

> Mọi lượt làm việc của mọi dự án **phim tài liệu** (mảng 🎬 Phim tài liệu của Creater Vid) phải tuân theo bộ quy tắc này.
> Video tin tức là một mảng khác, có bộ quy tắc riêng (`RULEBOOK.news.md`): không áp quy tắc của bộ đó cho phim tài liệu, và ngược lại.
> Thứ tự ưu tiên: yêu cầu của người dùng trong chat > bộ quy tắc này > thói quen mặc định.
> Người dùng yêu cầu điều trái quy tắc thì vẫn làm theo người dùng, kèm một dòng ⚠️ nêu rõ quy tắc nào bị phá và rủi ro.
> Quy tắc được viết ra từ những lần người dùng sửa phim. Mỗi lần người dùng sửa hay góp ý, cập nhật vào đây (mục 12).

---

## 0. Phim của chúng ta là gì

- Phim tài liệu cho YouTube, chủ đề bất kỳ: lịch sử, cổ văn, khoa học, bí ẩn, nhân vật, sự kiện.
- **Ngôn ngữ trên phim và lời dẫn** theo `language` của dự án (mặc định tiếng Anh, khán giả Mỹ). Ghi chú nội bộ và trả lời người dùng bằng tiếng Việt.
- **Xương sống luận điểm = nguồn có thật:** tài liệu gốc, sách, bài học thuật, báo chí, phỏng vấn/podcast, tư liệu người dùng đưa vào `sources/`, và kho highlight JRE khi dự án bật nguồn này. Lời dẫn nối các nguồn và đặt bối cảnh.
- **Hình ảnh:**
  - nhân vật và bối cảnh do AI vẽ (fal.ai, mục 3), tách lớp để dựng 3D;
  - footage thật (tư liệu, cảnh quay hiệu ứng lửa/khói) khi có giấy phép;
  - Claude dựng chuyển động, không gian 3D nhiều lớp, hiệu ứng, chữ và âm thanh bằng code (engine trong `film/`, cẩm nang `film/ENGINE.md`).
- **Phim mẫu tham chiếu:**
  - `K:\VideoLab\watchers-v2`: The Watchers v2.2, Book of Enoch 6–10, 32 s. Cảnh lò rèn `src/scenes/Azazel.tsx` là mẫu hiệu ứng lửa, khói, tia lửa, ánh sáng.
  - `K:\VideoLab\watchers-gpt`: cùng phim, cùng code, ảnh GPT Image 2.5 (so sánh A/B trong `out/ab_v2_vs_gpt.mp4`).

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
  - **Kiểm từng ý của khách mời** (agent fact-check riêng, `notes/factcheck.md`). Ý sai kiểm chứng được (niên đại, tên, con số): cắt clip trước/sau câu sai nếu không làm đổi ý, hoặc lời dẫn đính chính ngay sau clip kèm nguồn. Ý không có bằng chứng: bỏ khỏi clip. *(Book of Enoch: "Tertullian ~175 CE" → lời dẫn sửa "c. 200 CE"; câu "Septuagint có cả 1 Enoch" bị bỏ.)*
  - **Cắt clip:** lấy mốc từ transcript của cả tập (không gõ tay); đệm ≤ 0,3 s mỗi đầu nhưng không lẹm câu kế; whisper nghe lại từng clip. Transcript ASR viết sai tên riêng (vd. "Garama" thay "Garima") thì tránh câu đó hoặc sửa theo âm thanh.
  - **Gom đủ một chủ đề trong kho JRE:** `hldb search` chỉ tìm trong các đoạn highlight. Phải quét thêm transcript cả tập của mọi tập (bảng `transcript_lines` trong `studio.db`, mở chỉ đọc) bằng từ khoá và các từ liên quan (tên nhóm, tên người, tên phim tài liệu). Tập không còn video gốc thì cắt từ file highlight có chứa đoạn đó, đổi mốc theo đầu file. *(Giáo phái tổng hợp: chuyện Holy Hell ở #2254 và #2252 chỉ tìm ra khi quét transcript.)*
1.7 **Biểu tượng nhạy cảm:** không gắn biểu tượng của tôn giáo, dân tộc hay cộng đồng có thật (Ngôi sao David, thánh giá, trăng lưỡi liềm, chữ Vạn...) cho phe ác hay ma quỷ. Tránh cả ký hiệu sáo mòn kiểu phim kinh dị (ngôi sao năm cánh ngược). Khi cần một ký hiệu huyền bí, dùng hình học trung tính hoặc chữ viết lấy từ chính nguồn (vòng rune, vòng chữ, sao 7 cánh {7/3}). Ảnh AI hay tự thêm hoa văn hình chữ thập lên áo: luôn ghi "no symbols, no emblems" trong prompt và soát lại.
1.8 Bản quyền: bản dịch cổ văn dùng bản công cộng hoặc trích rất ngắn. Nhạc và hiệu ứng âm thanh: tạo bằng ElevenLabs qua `gen.py sfx` (gói trả phí, dùng thương mại) hoặc tự tổng hợp; không tải nhạc về. Trích phỏng vấn/podcast dạng đoạn ngắn có bình luận và dựng lại.
1.9 **Footage tải từ web** (cảnh quay lửa, khói, tia lửa, bụi trên nền đen; tư liệu lịch sử; ảnh tư liệu):
  - chỉ lấy từ nguồn có giấy phép cho dùng thương mại (Pexels, Pixabay, Mixkit, Wikimedia Commons với giấy phép ghi rõ, kho lưu trữ công; trả phí: ActionVFX);
  - **chưa tải gì khi người dùng chưa duyệt.** Ghi từng file vào `5_footage/footage.json` với `status: "proposed"` (tên, trang nguồn, giấy phép, độ dài, độ phân giải, dung lượng). Người dùng duyệt trên app (`5_footage/approvals.json`) hoặc trong chat;
  - đã duyệt thì tải vào `film/assets/fx/` (hiệu ứng) hoặc `film/assets/archival/` (tư liệu), ghi nguồn vào `notes/sources.md`.
1.10 **Người thật** (nhất là người còn sống hoặc mới mất):
  - không vẽ AI giống hệt người thật rồi trình bày như ảnh chụp;
  - ưu tiên ảnh tư liệu có giấy phép; nếu tái hiện thì cách điệu (bóng đen, tranh vẽ, nhìn từ xa) và ghi "artistic reconstruction";
  - không đặt lời vào miệng họ: chỉ trích nguyên văn có nguồn.
## 2. Quy trình một dự án (7 bước)

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
7_metadata/         bước 7: metadata.json, metadata.md, captions.srt, thumbs/
film/               dự án Remotion app dựng từ engine ở bước 4 (node_modules là liên kết dùng chung)
out/                các bản render, out/review/
notes/              costs.json (chi phí API, gen.py ghi), sources.md, runs/ (nhật ký các lượt, app ghi)
```

- **Cách dựng hình** (`pipeline` trong `project.json`): `layered` (mặc định: nhân vật tách nền ghép trên nền vẽ, mục 2.3–2.6, 4–6), `fullframe` (ảnh liền khối → 3D: bước 3, 4, 6 theo mục 4.9) `stacked` (xếp lớp: GPT vẽ từng lớp → camera 3D, bước 3, 4, 6 theo mục 4.10) hoặc `dossier` (hồ sơ tư liệu thật: ảnh, trang tài liệu, footage thật dựng như vật chứng, bước 1–6 theo mục 4.11); các bước khác giữ nguyên.
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
     - pipeline `dossier`: chọn khung kể hồ sơ vụ việc / đường hang thỏ / cổ điển theo mục 4.11.1;
     - mỗi beat: loại, thời lượng, lời dẫn, chữ trên màn hình, trích dẫn nguyên văn (nếu có), ý tưởng hình ảnh, nhân vật xuất hiện, nguồn;
     - lời dẫn: câu ngắn, giọng tài liệu điềm tĩnh; đọc ≈ 150 từ/phút; mỗi phụ đề ≤ 2 dòng (≈ 16 từ), đủ thời gian đọc ≥ 0,35 s/từ + 1 s;
     - **thời lượng: `target_sec` là mức tối thiểu, không phải con số phải khớp.** Tổng ≥ `target_sec`; dài hơn bao nhiêu tuỳ nội dung: viết bản hay nhất, đủ ý, đủ nhịp, không cắt bớt ý đắt chỉ để gói vào con số. Nhưng không độn (không lặp ý, không kéo dài lời dẫn, không thêm đoạn yếu để đủ giờ): mọi phút thêm phải giữ được người xem. Ghi `est_sec` thật và một câu lý do trong `research.md` khi vượt `target_sec` quá ~30%.
  6. Kiểm chứng: mọi trích dẫn nguyên văn so chuỗi bằng python với văn bản nguồn (transcript, bản dịch); mọi khẳng định sự thật trong lời dẫn có nguồn trong `sources.json`.
     - Lưu văn bản nguồn (bản dịch công cộng, ghi rõ ấn bản và URL) vào `notes/texts/` để so chuỗi; bản số hoá có thể lệch bản in (sacred-texts lệch SPCK 1917 ~27 chỗ): trích đúng câu không nằm trong chỗ lệch.
     - Việc tra cứu dài chạy song song bằng agent: một agent lấy văn bản gốc, một agent fact-check từng khẳng định; agent chỉ ghi vào `notes/`.
  7. Ước tính chi phí giọng đọc: số ký tự × giá model (mục 3).
  8. **Bản thiết kế dự án** `blueprint.json` (mục 11.1): sơ đồ cách làm cả phim, lập ngay ở bước này để người dùng nhìn tổng thể và chỉnh **trước khi** làm:
     - cách làm (2–4 câu), xương sống một câu, mở bằng gì, khép bằng gì; các hướng dàn ý đã cân nhắc, hướng nào chọn, vì sao;
     - từng hồi: vai trò trong mạch, câu hỏi hồi mở ra, điều người xem biết thêm khi hết hồi, ý chuyển sang hồi sau, thời lượng, các loại hình ảnh sẽ dùng, nhân vật, bối cảnh, bằng chứng;
     - kho nguyên liệu dự kiến: nhân vật và cách thể hiện (ảnh thật, clip, vẽ AI, chỉ giọng), bối cảnh và cách thể hiện; bằng chứng lấy theo `evidence_plan`;
     - kế hoạch các bước 2–7 cho riêng phim này: mỗi bước sẽ làm gì, bao nhiêu món, tốn bao nhiêu; ngân sách tách theo giọng, ảnh, âm thanh;
     - những điều người dùng nên quyết ở cổng duyệt;
     - **cây nội dung** (phần quan trọng nhất, người dùng duyệt nội dung phim trên cây này): mỗi hồi ghi `why` (vì sao hồi này đứng ở đây, nó làm gì cho mạch) và `how` (triển khai bằng cách nào); mỗi beat ghi `point` (ý chính một câu), `why` (vì sao viết đúng như thế: người xem đang nghĩ gì, beat này đẩy họ đi đâu, vì sao chọn câu/clip/bằng chứng này thay vì cách khác), `how` (kỹ thuật kể, hình, bằng chứng, nhịp) và `ideas` (các ý con theo thứ tự lời dẫn). Viết cụ thể cho phim này, không chép định nghĩa vai trò.
     Sửa kịch bản ở bước nào thì cập nhật `blueprint.json` cho khớp. App vẽ file này thành sơ đồ (trang 🧭 Sơ đồ dự án); thiếu file thì app tự suy từ `script.json`, nhưng bản suy thiếu ý đồ.
- **Đầu ra:** `research.md` (bản đọc: nguồn chính, luận đề, các hướng dàn ý, khẳng định cần thận trọng), `sources.json` + `script.json` + `blueprint.json` (mục 11.1), `script.md` (kịch bản đọc được, chia hồi, có thời lượng từng beat).
- **Cổng duyệt:** người dùng bấm Duyệt (hoặc nói "duyệt") thì mới sang bước 2.

### 2.2 Bước 2 · Tuyển nhân vật (`2_cast/`)

- **Đầu vào:** `script.json` đã duyệt, `sources.json`.
- **Làm:**
  1. Gom mọi nhân vật trong các beat: vai chính, phụ, đám đông, người dẫn (chỉ có giọng). Gộp vai trùng.
  2. Mỗi vai:
     - mô tả, ngoại hình **bám nguồn và niên đại** (mục 1.3): tuổi, vóc dáng, trang phục, màu, đạo cụ; ghi nguồn;
       ưu tiên mô tả trong chính văn bản và tránh nét của thời sau (vd. Book of the Watchers không tả cánh → Watchers không cánh; dáng sáng lấy từ 1 Enoch 106:2, 5);
     - cách thể hiện `depiction`: `ai_reconstruction` (vẽ AI), `archival_photo` (ảnh tư liệu), `silhouette` (bóng), `none` (chỉ nhắc tên); người thật theo mục 1.10;
     - các tư thế cần (từ beat), ví dụ đứng, chỉ tay, giơ tay cầm lửa, bị trói;
     - prompt ảnh gốc hoàn chỉnh theo mục 3 (nhân vật cần tách: toàn thân, nền xám trơn, chuỗi phong cách cuối prompt).
  3. **Ảnh thử vai:** tối đa 2 ứng viên cho mỗi vai chính và phụ có `ai_reconstruction`, model ảnh rẻ (`--draft`, mục 3), lưu `2_cast/casting/<id>_<n>.png`. Tổng tiền thử vai ≤ 10% ngân sách. Vai đám đông và vai không vẽ thì không thử vai.
- **Đầu ra:** `cast.json` (mục 11.2), `cast.md` (bảng vai: tên, vai trò, cách thể hiện, ngoại hình, beat xuất hiện).
- **Cổng duyệt:** người dùng chọn ứng viên trên app (app ghi `2_cast/choices.json`: `{id_nhân_vật: đường_dẫn_ảnh}`), hoặc nhắn sửa ngoại hình để thử vai lại, rồi Duyệt.

### 2.3 Bước 3 · Phân cảnh & bối cảnh (`3_scenes/`)

- **Đầu vào:** `script.json`, `cast.json`, `choices.json`.
- **Làm:**
  1. Chia các beat thành **cảnh dựng được** (thường 6–20 s/cảnh, một beat có thể thành nhiều cảnh và ngược lại). Mỗi cảnh là một sân khấu 3D (mục 4): bối cảnh, các lớp theo độ sâu, nhân vật + tư thế, chuyển động máy quay, hiệu ứng (mục 5), âm thanh, lời dẫn và chữ.
  2. Danh sách **bối cảnh** (locations): mô tả bám niên đại, các tấm nền cần vẽ cho mỗi bối cảnh (trời, xa, trung, tiền cảnh). Dùng lại một bối cảnh cho nhiều cảnh khi được.
  3. Danh sách **ảnh cần vẽ** (assets): mỗi ảnh một `key`, loại, model, chất lượng, tỉ lệ, prompt hoàn chỉnh (chuỗi phong cách cuối prompt), ảnh gốc `base` cho biến thể, chi phí ước tính `est_usd` (mục 3). Nhân vật: ảnh gốc từ ứng viên đã chọn, rồi biến thể.
  4. Danh sách **footage cần** (footage_needs): hiệu ứng quay thật (lửa, khói…), tư liệu, clip phỏng vấn, giọng đọc, nhạc.
  5. Tổng chi phí ước tính của bước 4 + 5 ≤ ngân sách còn lại (`gen.py cost`). Vượt thì đề xuất cắt giảm (dùng lại ảnh, chất lượng medium cho nền).
  6. **Nhịp hình** (mục 5.13): mỗi cảnh tự chọn `transition`, `look`, `text_fx` theo nội dung, ghi vào `scenes.json` và cột «Chuyển cảnh · màu · chữ động» của `scenes.md`.
- **Đầu ra:** `scenes.json` (mục 11.3), `scenes.md` (bảng cảnh, bảng bối cảnh, bảng ảnh với tổng chi phí, bảng footage).
- **Cổng duyệt:** duyệt bước 3 = duyệt danh sách ảnh và số tiền sẽ tiêu ở bước 4.

### 2.4 Bước 4 · Render hình ảnh (`4_images/`, ảnh trong `film/`)

- App đã dựng khung `film/` từ engine. `film/node_modules` là liên kết tới engine dùng chung: không `npm install`, **không bao giờ xóa** nó hay thứ gì bên trong.
- **Làm:**
  1. `gen.py check` (key, số dư) và `gen.py cost` (đã tiêu so với ngân sách). Mỗi ảnh gen.py tự ghi chi phí.
  2. Thứ tự: ảnh gốc nhân vật (từ ứng viên đã chọn trong `choices.json`: dùng làm ảnh tham chiếu để vẽ bản chất lượng cao, hoặc dùng luôn nếu đã đủ tốt) → biến thể (sửa từ ảnh gốc, mục 3) → nền bối cảnh → đạo cụ → lớp additive (sương, ánh sáng, lông vũ trên nền đen).
  3. Tạo bằng `gen.py image … --out film/assets/raw/<key>.png --what <key>` (mục 3), tối đa 3 lệnh cùng lúc.
  4. Tách nền trên máy: `"$BGREMOVE_PY" scripts/cutout.py assets/raw/<key>.png --out public/img` (chạy trong `film/`). Nền và lớp additive không tách: chép thẳng vào `film/public/img/`. **Xem bảng soát** `film/out/stills/cutouts.jpg`.
  5. Soát từng ảnh: đúng niên đại, không biểu tượng cấm (mục 1.7), nhân vật giữ đúng nhân dạng giữa các biến thể, khung đủ lề (đầu cánh, chân không bị cắt). Lỗi thì làm lại ngay (vẫn trong ngân sách).
  6. Đo điểm neo theo mục 6 (tay, chân, đỉnh núi, miệng lò…) và ghi vào `landmarks` của từng ảnh trong manifest.
  7. Ghép bảng xem nhanh theo nhóm vào `4_images/sheet_<nhóm>.jpg`.
- **Đầu ra:** `manifest.json` (mục 11.4), bảng xem nhanh.
- **Cổng duyệt:** người dùng xem gallery trên app, bấm "Làm lại" kèm ghi chú cho ảnh chưa ưng (app gửi thành tin nhắn chat), rồi Duyệt.

### 2.5 Bước 5 · Footage & âm thanh (`5_footage/`)

- **Làm:**
  1. **Footage** theo `footage_needs` và mục 1.9: tìm, ghi từng file vào `footage.json` với `status: "proposed"`. **Không tải** khi chưa có quyết định trong `5_footage/approvals.json` (`approved`) hoặc lời duyệt trong chat. Lượt sau: tải mục đã duyệt, xử lý bằng `scripts/fx-prep.mjs` (cắt, khử nền đen, đo độ chập chờn), cập nhật `status` và `file`. Mục bị bỏ (`rejected`): tìm phương án khác hoặc dựng bằng code.
     - Trước khi đề xuất, xem nội dung thật mà không cần tải (ảnh xem trước, chú thích, bản chép của trang video) và mô tả trong `footage.json` đúng nội dung có trong đó. Khi không xem trước được thì ghi «chưa xác nhận nội dung». Sau khi tải, nội dung không khớp mô tả thì báo người dùng, không gán sang chỗ khác.
  2. **Clip phỏng vấn/podcast** (nếu kịch bản có trích): cắt bằng `node scripts/clip.mjs` vào `film/public/clips/`, đúng nguyên văn (mục 1.6).
  3. **Lời dẫn** theo mục 8.4: một lần đọc cả kịch bản, chọn bản bằng whisper, đặt câu theo cảnh (`audio/voice/plan.json` + `scripts/voice-build.py`).
  4. **Nhạc và hiệu ứng âm thanh:** tự tổng hợp (mục 8.1); ghi kế hoạch vào `footage.json` (`music`).
- **Đầu ra:** `footage.json` (mục 11.5), file trong `film/public/fx`, `film/public/clips`, `film/audio/voice`.
- **Cổng duyệt:** mọi footage đã duyệt đã tải xong, giọng đọc đã chọn thì người dùng Duyệt.

### 2.6 Bước 6 · Dựng & render (`6_render/`, `film/`, `out/`)

1. Đọc `film/ENGINE.md`, xem các cảnh mẫu trong phim tham chiếu (mục 0).
2. Viết `src/timeline.js`, `src/assets.ts`, các cảnh và `Film.tsx` theo `scenes.json`: đúng bối cảnh, lớp, máy quay, hiệu ứng đã duyệt; chuyển cảnh, màu, chữ động theo `transition`/`look`/`text_fx` bằng Motion kit (`src/kit`, mục 5.13): `<Enter kind>` thay cho `Fade`, độ chồng `ov` của mỗi cảnh = `TRANSITION_LEN` của kiểu vào của cảnh sau (mốc cảnh và giọng đọc không đổi).
3. Soát ảnh tĩnh (mục 9), sửa.
4. Âm thanh: `make-audio` trộn nhạc, hiệu ứng, lời dẫn; master −15 LUFS (mục 8).
5. Render `out/<slug>_v<N>.mp4`. **Không ghi đè bản cũ**, mỗi lần render tăng N.
6. QA (mục 9) trên chính file MP4, ghi `6_render/render.json` (mục 11.6) kèm kết quả QA và bảng ghép `out/review/contact_v<N>.jpg`.
- **Cổng duyệt:** người dùng xem phim; góp ý qua chat (2.7) thành bản v<N+1>. Duyệt = chốt bản cuối.
- **Kinh nghiệm dựng** (Book of Enoch, 66 cảnh):
  - Phim nhiều cảnh: dùng một cảnh chung chạy theo dữ liệu (`scenes/config.json` sinh bằng script từ `scenes.json` + `manifest.json` + giọng đọc) thay vì viết tay từng file; mỗi cảnh chỉ khai báo lớp, máy quay, hiệu ứng, thẻ chữ.
  - Footage web chưa duyệt lúc dựng (chế độ tự chạy): dựng bản thay thế (ánh lò/tàn lửa bằng code, thẻ chữ thay ảnh tư liệu), ghi rõ trong `render.json` và báo cáo; không tự tải.
  - Clip tư liệu ngắn hơn cảnh của nó thì khung cuối cảnh thành màn đen. Giãn tốc độ phát (`playbackRate` ≥ ~0,8) hoặc nối thêm đoạn, và soát ảnh tĩnh ở **cuối** mọi cảnh video. *(Điểm tin 13.10.2026: video truyền đơn 12 s trong cảnh 14 s.)* Clip có tiếng (không được giãn) thì giữ khung đầu trong phần vào và khung cuối trong phần đuôi (`<Freeze>`). *(Tập 3: clip Trump, Синегубов.)*
  - **Chỉ sửa âm thanh:** trộn lại tiếng rồi ghép vào hình bản trước bằng `-c:v copy`, không render lại hình; vẫn tăng số bản (v<N+1>).
  - **Render dài: theo đoạn, chạy tuần tự ngay trong lượt** (≈ 1 phút mỗi 30 s phim). Một lệnh công cụ tối đa 10 phút, nên chia `npx remotion render … --frames=<từ>-<tới>` thành đoạn ~8.000 khung (~6–7 phút ở 1080p) vào `film/out/chunks/pNN.mp4`, chạy lần lượt từng đoạn (không `run_in_background`), rồi nối bằng ffmpeg concat `-c copy`. Đoạn đã có (mở được bằng ffprobe, đủ số khung) thì không render lại khi chạy tiếp. **Không bao giờ kết thúc lượt khi còn lệnh chạy nền**: lượt kết thúc là app coi bước đã xong, không có thông báo nào quay lại, tiến trình bỏ lại sẽ chết khi app khởi động lại. *(Giáo phái tổng hợp, 2026-10-14: render cả phim chạy nền, lượt kết thúc «chờ tác vụ nền báo», bước báo thiếu kết quả, FFmpeg của tiến trình bị bỏ lại chết ở khung 31.010/38.762)*
  - Thẻ chữ trong 3D (`CanvasPlate`): dòng chữ ngắn, cỡ ≤ ~0,05; soát ảnh tĩnh để chắc chữ không tràn mép thẻ và không bị letterbox cắt.
  - Đối chiếu từng nhãn nguồn và thẻ chữ với lời dẫn **của chính cảnh đó** trước khi dựng: `on_screen_text` của bước 3 có thể lệch một cảnh (nguồn trích hiện trước/sau câu đọc nó).

### 2.7 Sửa theo góp ý (chat)

- Tin nhắn chat kèm bước người dùng đang xem. Sửa đúng file của bước đó, soát lại đúng chỗ đã sửa (ảnh tĩnh hoặc cắt cận), báo cáo đã sửa gì và bằng chứng.
- Thay đổi ảnh hưởng các bước sau (ví dụ đổi kịch bản khi đã có ảnh) thì nói rõ cần làm lại gì và tốn bao nhiêu tiền; chưa tự làm lại bước sau khi chưa được bảo.
- Góp ý mang tính nguyên tắc thì **ghi thành quy tắc** (mục 12).

### 2.8 Bước 7 · Metadata YouTube (`7_metadata/`)

- **Đầu vào:** `script.json`, `sources.json`, `research.md`; `6_render/render.json` (bản cuối: file, thời lượng); mốc cảnh trong timeline của bản đó; lời dẫn có mốc chữ (`film/audio/voice/`); `project.json` (ngôn ngữ, khán giả).
- **Làm:**
  1. **Từ khóa:** tra bằng WebSearch (gợi ý tìm kiếm YouTube/Google, video cùng chủ đề đang lên, cách người xem gọi chủ đề). Chọn 1 từ khóa chính (cụm khán giả thật sự gõ) và 5–10 từ khóa phụ; ghi nơi tra trong `metadata.md`.
  2. **Tiêu đề:** 3–5 phương án, ≤ 70 ký tự (YouTube tối đa 100), từ khóa chính ở đầu, gây tò mò nhưng không sai sự thật (mục 1: điều còn tranh cãi thì dùng câu hỏi, không khẳng định). Chọn một, nói lý do.
  3. **Mô tả** (ngôn ngữ của phim, ≤ 5000 ký tự, không có `<` `>`): 2 dòng đầu (~150 ký tự, hiện trước "xem thêm") chứa từ khóa chính và lời hứa của video; tóm tắt 2–3 câu; **chương** mm:ss lấy từ timeline bản render cuối (chương đầu 0:00, ≥ 3 chương, mỗi chương ≥ 10 s, tên chương có từ khóa); nguồn chính (bản dịch, học giả, clip podcast kèm tên kênh và link); ghi chú hình tái hiện bằng AI; 3 hashtag ở cuối.
  4. **Thẻ:** từ khóa chính, biến thể, tên riêng (nhân vật, văn bản, học giả), tổng ≤ 500 ký tự (YouTube đếm cả dấu phẩy và 2 dấu ngoặc kép quanh thẻ có dấu cách). Hashtag 3–5.
  5. Danh mục (Education, Film & Animation…), ngôn ngữ, `made_for_kids: false`, `altered_content: true` khi phim có hình tái hiện bằng AI trông như thật (YouTube buộc khai báo nội dung tổng hợp).
  6. **Phụ đề** `7_metadata/captions.srt` từ lời dẫn (mốc chữ ElevenLabs alignment hoặc whisper), ≤ 2 dòng mỗi khung (~42 ký tự/dòng: khung dài hơn thì tách đôi đúng mốc chữ đầu của nửa sau), khớp bản render cuối (cộng độ lệch của các cảnh trước lời dẫn); clip phỏng vấn theo transcript nguyên văn, ghi người nói.
  7. **Thumbnail:** 2 phương án 1280×720, JPG < 2 MB: khung đẹp nhất của phim (hoặc ảnh frame) + chữ lớn 2–4 từ (khác tiêu đề, cùng ý), tương phản cao, mặt nhân vật rõ; dựng bằng python (PIL) vào `7_metadata/thumbs/`. Vẽ mới bằng gen.py chỉ khi người dùng muốn, hoặc khung phim không đủ mạnh mà ngân sách còn.
  8. **Giờ đăng:** `publish_at` = giờ công chiếu đề xuất, ISO 8601 có múi giờ (`2026-10-15T18:00:00+03:00`), trong tương lai, theo giờ khán giả xem nhiều (mặc định phim tài liệu: tối thứ 5–Chủ nhật giờ Mỹ, ~12:00–15:00 ET); `visibility: "schedule"` (mặc định), hoặc `private` / `unlisted` / `public` khi người dùng bảo. `category` ghi đúng tên danh mục tiếng Anh của YouTube Studio (`News & Politics`, `Education`, `Film & Animation`…). Đánh `"chosen": true` cho thumbnail sẽ đăng.
- **Đầu ra:** `metadata.json` (mục 11.8), `metadata.md` (bản đọc: từ khóa + nơi tra, các phương án tiêu đề, mô tả hoàn chỉnh để dán, thẻ, chương, thumbnail, checklist đăng: phụ đề, màn hình kết thúc, thẻ video, playlist, giờ đăng gợi ý theo khán giả).
- **Cổng duyệt:** người dùng đọc, nhắn sửa, Duyệt = sẵn sàng đăng. Claude không tự đăng: **app** đăng qua profile GPM Login của kênh đã chọn cho dự án (khung 📺 Đăng YouTube ở bước này; tự đăng khi duyệt nếu dự án chọn chế độ tự đăng), lấy tiêu đề, mô tả, thẻ, thumbnail, danh mục, giờ đăng từ `metadata.json` và bản render cuối.

## 3. Nguyên liệu trả phí: giọng đọc, ảnh, video (gen.py)

- **Công cụ:** một lệnh duy nhất `"$CREATER_PYTHON" "$GEN_PY" <lệnh>` (`<lệnh> --help` để xem tham số). Key ElevenLabs và fal.ai do người dùng điền ở trang Cài đặt; gen.py tự đọc key, Claude không bao giờ thấy, hỏi hay ghi key.
  - `check`: key còn dùng được, gói và số ký tự ElevenLabs còn lại, số dư fal (nếu key được xem số dư).
  - `cost`: dự án đã tiêu bao nhiêu so với ngân sách.
  - `image --prompt "…" --out film/assets/raw/<key>.png --what <key>` với `--model main|draft|edit|gpt|gpt-edit|nano-pro|nano-pro-edit|nano2|seedream` hoặc id model fal, hoặc gọi thẳng `openai:<model>` / `google:<model>` (alias `openai`, `openai-flare`, `openai-mini`, `gemini-pro`, `gemini-flash`, `gemini-lite`; dùng key OpenAI, Google riêng), `--ref ảnh_gốc.png` (sửa từ ảnh gốc), `--aspect 16:9`, `--quality high`, `--resolution 2K`, `--n 2`, `--set tham_số=giá_trị`.
  - `video --image ảnh_đầu.png --prompt "…" --seconds 5 --out film/public/clips/<id>.mp4` (thêm `--end ảnh_cuối.png`; `--audio` chỉ khi cần tiếng của model).
  - `tts`, `sfx`, `voices`: lời dẫn và hiệu ứng âm thanh (mục 8.4).
  - `run <model> --set k=v --file k=đường_dẫn --out …`: model khác của fal (phóng to ảnh, tách nền dự phòng `birefnet`…). Xem tham số bằng `schema <model>`, giá bằng `price <model>`, tìm model bằng `models --q "…"`.
  - `--dry-run` in yêu cầu và giá ước tính mà không gửi.
- **Chi phí và ngân sách:** mỗi lần gọi thành công gen.py ghi vào `notes/costs.json` (USD, model, file, request id; mục 11.7). Trần mỗi dự án: `budget_usd` trong `project.json`. Lệnh làm vượt trần bị từ chối (mã thoát 3, "VƯỢT NGÂN SÁCH"): dừng phần đó, báo số tiền và hỏi người dùng; chỉ chạy lại với `--over-budget` khi người dùng đã đồng ý. Thiếu key (mã thoát 2): báo người dùng điền ở Cài đặt, không tìm đường khác.
- **Giá (fal.ai, ElevenLabs, 2026-10):**

  | Việc | Model (alias) | Giá |
  |---|---|---|
  | Ảnh rẻ: thử vai, nháp | `bytedance/seedream/v5/flash/text-to-image` (`seedream`, mặc định của `--draft`) | $0,027/ảnh |
  | Ảnh | `fal-ai/nano-banana-2` (`nano2`) | $0,08/ảnh 1K, ×1,5 ở 2K |
  | Ảnh chính, sửa ảnh | `fal-ai/nano-banana-pro` và `/edit` (`nano-pro`, `nano-pro-edit`; mặc định `main`, `edit`) | $0,15/ảnh (4K ×2) |
  | Ảnh giữ nhân dạng, đếm đúng người | `openai/gpt-image-2.5/sunburst/text-to-image` và `/sunburst/edit` (`gpt`, `gpt-edit`) | tính theo token: xem bằng `--dry-run` hoặc `price` |
  | Ảnh gọi thẳng Google | `google:gemini-3-pro-image` (`gemini-pro`) · `google:gemini-3.1-flash-image` (`gemini-flash`) · `google:gemini-3.1-flash-lite-image` (`gemini-lite`) | $0,134/ảnh 1K–2K, $0,24 4K · $0,067 1K, $0,101 2K · $0,034 |
  | Ảnh gọi thẳng OpenAI | `openai:gpt-image-2.5-sunburst` (`openai`) · `openai:gpt-image-2.5-flare` (`openai-flare`) · `openai:gpt-image-1-mini` (`openai-mini`) | $30/1 triệu token ảnh ra (≈ $0,17/ảnh 1024² high); mini $8 |
  | ↳ chi phí thật đo được (2026-10-08) | `openai` medium: ≈ $0,011/ảnh 1536×1024, ≈ $0,024 khi sửa ảnh có `--ref` · `openai-mini` medium ≈ $0,013 | dry-run ước cao gấp 3–6 lần: lập ngân sách theo dry-run, báo theo `gen.py cost` |
  | Tách nền | `scripts/cutout.py` trên máy | **miễn phí** |
  | Video 5 s | `fal-ai/kling-video/v3/standard/image-to-video` (`kling`, mặc định) | $0,084/giây không tiếng ≈ $0,42 |
  | Video 5 s chất lượng cao | `bytedance/seedance-2.5/image-to-video` (`seedance`) | ≈ $0,47/giây ở 720p ≈ $2,4 |
  | Lời dẫn | ElevenLabs `eleven_v4` | $0,08/1.000 ký tự ≈ 1 phút đọc |
  | Hiệu ứng âm thanh | ElevenLabs sound generation | $0,12/phút |

  Model mặc định của từng việc (`main`, `draft`, `edit`, `video`, model giọng) chỉnh ở trang Cài đặt.
  Cùng một model, gọi thẳng thường rẻ hơn qua fal (Nano Banana Pro $0,134 so với $0,15). Gọi thẳng chỉ chạy khi người dùng đã điền key OpenAI / Google (`gen.py check`); thiếu key thì gen.py báo mã 2, báo người dùng hoặc dùng model fal tương đương. Gemini: `--aspect` theo danh sách cố định (1:1, 3:2, 2:3, 3:4, 4:3, 4:5, 5:4, 9:16, 16:9, 21:9), `--resolution` 512px/1K/2K/4K, không có `--quality`. OpenAI: `--quality low…max`, kích thước 1024x1024 / 1536x1024 / 1024x1536 (hoặc WxH, hoặc `--resolution 2K`).
- **Chọn model theo việc** (thử nghiệm 2026-09-30 trên The Watchers; Nano Banana Pro và GPT Image 2.5 đều có trên fal):
  - **Ảnh thử vai, nền rẻ:** `--draft` (Seedream Flash) hoặc `nano2`.
  - **Nhân vật gốc và biến thể cần giữ đúng nhân dạng, cảnh cần đếm đúng số người:** `gpt` / `gpt-edit` với `--quality high`. Giữ nhân vật tốt nhất khi đổi tư thế, đếm đúng (7/7 người so với 6/7 của Nano Banana Pro), chi tiết nền phong phú.
  - **Phong cách tranh sơn dầu, màu thống nhất:** `nano-pro`. GPT ngả về ảnh chụp: nếu dùng GPT thì chuỗi phong cách phải mạnh ("painterly oil painting with visible brushwork…") và soát lại.
  - Sửa ảnh (đổi tư thế, xoá vật, đổi trang phục): `--ref ảnh_gốc.png` với `gpt-edit` hoặc `nano-pro-edit`, ngang nhau. Prompt: "Edit this image. Keep the same … Only change …".
  - Nền trời, cảnh xa: chất lượng medium hoặc 1K là đủ (bị làm mờ theo độ sâu).
  - **Không dùng `openai-mini` cho nhân vật/đạo cụ cần tách nền:** nó hay bỏ qua "nền xám phẳng" và vẽ thành phong cảnh. Mini chỉ cho trời, cảnh xa, lớp sương/tia sáng.
  - Thiếu key fal: nhân vật gốc và biến thể làm bằng `openai` + `--ref` ảnh thử vai đã chọn (giữ nhân dạng tốt, sửa luôn lỗi của ảnh thử vai), ảnh thử vai bằng `openai-mini` medium (≈ $0,013/ảnh).
- **Gọi API:** chạy tối đa 3 lệnh gen.py cùng lúc. Lỗi tạm (model bận, lỗi 5xx) thì chạy lại. Quá thời gian chờ thì **không gửi lại ngay** (có thể trả tiền hai lần): gen.py in request id, báo người dùng.
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
    *(Nguồn gốc: so sánh 12 ảnh Watchers, 2026-09-30: trên máy khớp API trả phí 97–99%, sạch viền hơn, miễn phí.)*
  - **Không vẽ lửa hay khói vào ảnh tĩnh.** Lửa đứng im trông giả, tách nền còn kẹt mảng xám giữa các lưỡi lửa. Ảnh lỡ có lửa vẽ sẵn thì xoá đi (sửa ảnh, hoặc mặt nạ màu + inpaint) và thay bằng cảnh quay thật (mục 5.8). Nêu rõ trong prompt: "no fire, no flames, no smoke" cho đạo cụ sẽ có lửa thật.
  - Sương, ánh sáng, lông vũ: vẽ **trên nền đen tuyền** rồi dùng `blend="add"`, không tách nền. Tách nền để lại viền đen trên vật trắng mềm.
  - Cảnh nền (plate): không nhân vật, không chữ. Chừa khoảng cho chủ thể đứng.
  - Nền sẽ có lửa/khói thật: ghi "clear air, no smoke, no haze, no fire" (GPT hay tự vẽ khói). Nền mang bản sắc văn hoá/kiến trúc: ghi rõ kiểu (vd. "Ethiopian rock-hewn church, Lalibela") vì model mặc định kiểu châu Âu; soát lại.
- **Một chuỗi phong cách cho cả phim**, gắn vào cuối mọi prompt. Ví dụ: *dark biblical fantasy concept art, painterly oil painting with visible brushwork, cinematic lighting, ... in the spirit of Gustave Dore and modern film concept art*.
- **Tính đồng nhất:** mỗi nhân vật có một ảnh gốc. Mọi biến thể đều sửa từ ảnh gốc đó.
- **Tải về:** gen.py tải thẳng file về `--out`, đặt tên theo `key`. Xem lại bằng bảng ghép trước khi dùng.
- **Video AI** chỉ dùng cho khoảnh khắc "diễn" đắt nhất mà biến dạng lưới không làm được, và phải hỏi người dùng trước (kèm giá).

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

### 4.9 Ảnh liền khối → 3D (pipeline `fullframe`)

Áp dụng khi `project.json` có `"pipeline": "fullframe"` (người dùng tích "Cách mới" trên app). Mỗi cảnh dựng lại (`reconstruction: true`) là **một ảnh hoàn chỉnh**: nhân vật vẽ sẵn trong bối cảnh nên ánh sáng, bóng đổ, khí quyển, phối cảnh thống nhất (hết cảm giác nhân vật "dán" lên nền của cách ghép lớp). Ảnh thành clip camera 3D bằng `parallax.py` trên GPU của máy, miễn phí: Depth Anything V2 ước lượng độ sâu → tách lớp ở mép đứt gãy độ sâu, vá nền phía sau mỗi lớp → camera bay trong không gian (DoF, bloom, mây trôi). Cảnh tư liệu, clip phỏng vấn, thẻ chữ, tựa phim giữ cách làm cũ. Mục 4.1–4.5 và 6 không áp dụng cho cảnh liền khối; mục 5 chỉ còn lớp phủ lên clip (sương, tàn lửa additive, lửa quay thật, chữ).
*(Nguồn gốc: 2026-10-08, người dùng thấy cảnh ghép Noah trên ruộng nho "khá xấu, không chân thực"; thử ảnh hai nhạc công → 3D đẹp hơn rõ.)*

**Bước 3 (phân cảnh):**
- Mỗi cảnh dựng lại có **một** asset `kind: "frame"`, `key` = id cảnh (vd `sc05`), `refs` = ảnh gốc các nhân vật nhìn rõ trong cảnh (`film/assets/raw/<id nhân vật>.png`, vẽ ở bước 4), `model` `openai` (giữ nhân dạng tốt nhất khi có ref) hoặc `gpt-edit`, `quality` high cho cảnh cận nhân vật, medium cho cảnh rộng không người; `aspect` 3:2 cho phim 16:9, 2:3 cho 9:16.
- Trong cảnh: `"frame": "film/assets/frames/sc05.png"` và `"parallax": {"move": "orbit-right", "subject": [0.62, 0.55], "strength": 1.0}`; `subject` là vị trí chủ thể trong ảnh (phân số x, y), camera xoay quanh và lấy nét ở đó.
- `subject`: để x = 0,5 (khung đã rộng ~87% ảnh; lệch tâm 0,08 làm `overscan` lên 1,36–1,45, hình phóng to và mềm), y = đỉnh đầu nhân vật chính + ~0,28 (đầu còn trong khung; y ≥ ~0,31 để không tăng overscan). Nhân vật đứng sát mép thì giảm `strength` (0,6) thay vì kéo `subject` ra xa tâm. *(Nguồn gốc: The Book of Enoch 3D: sc12 overscan 1,45 khi x = 0,42; sc29, sc63b cụt đầu khi thử 3D.)*
- **Phim có letterbox** (engine mặc định 100 px trên dưới): khung nhìn thật là dải 1920×880 (2,18:1). Render clip ở đúng dải đó (`"size": "1920x880"`) và đặt clip vào giữa hai thanh; render 16:9 rồi để thanh đen che thì mất đầu nhân vật sát mép trên. Ảnh 3:2 chỉ còn ~69% chiều cao trong dải: cảnh toàn thân thành cảnh trung (cắt chân), phải đặt y theo đầu. *(Nguồn gốc: The Book of Enoch 3D, bước 6.)*
- Nhân vật chỉ hiện nhỏ, ở xa thì **không gắn ref**, chỉ tả bằng chữ: có ref, model vẽ nhân vật to ở tiền cảnh. *(Nguồn gốc: The Book of Enoch 3D, sc18.)*
- Chọn move theo ý cảnh: `orbit-left/right` giới thiệu nhân vật, không gian · `push-in` căng thẳng, khoảnh khắc then chốt · `pull-out` lộ quy mô, kết hồi · `crane-up/down` hùng vĩ, trời đất · `truck-left/right` theo hành trình · `drift` cảnh tĩnh, lời dẫn dài. Không dùng cùng một move ba cảnh liền nhau; orbit đổi chiều xen kẽ.
- Không lập nền/biến thể/đạo cụ tách lớp cho cảnh liền khối. Một ảnh không giữ quá ~12 s: cảnh dài hơn thì 2 ảnh (2 góc máy) hoặc 2 move nối nhau.
- Chi phí: 1 ảnh mỗi cảnh + ~30% làm lại. Giá thật OpenAI medium có ref ≈ $0,024/ảnh; high lấy theo `--dry-run`.

**Prompt ảnh liền khối (để 3D đẹp):**
- Đủ ba tầng sâu: tiền cảnh (đá, cây, vật cách ống kính vài mét), trung cảnh (chủ thể), hậu cảnh (núi, trời); sương hoặc khói mỏng giữa các tầng (độ sâu ước lượng chuẩn hơn, không gian sâu hơn).
- Chủ thể có viền rõ trên nền đơn giản hơn nó (trời, sương, vùng tối), không chạm mép khung; chừa lề ~8% quanh khung vì camera cần lề.
- Tránh chi tiết mảnh đan ngay trước/sau chủ thể (dây đàn, lưới, cành rủ qua mặt, giáo dài chéo khung): đó là chỗ tách lớp vỡ. Bắt buộc có thì để chúng nằm gọn trong một tầng.
- Giữ nhân dạng: "Use the attached reference image(s) for the exact face, hair, beard and clothing of <tên>; keep them identical." Mỗi nhân vật một ref; tối đa ~3 nhân vật nhìn rõ mặt mỗi cảnh.
- Không chữ, không khung viền, không watermark; ánh sáng có hướng rõ. Không vẽ lửa, khói cuộn (đứng im trong 3D trông giả): lửa thật phủ ở bước 6.
- Chuỗi phong cách cuối prompt như mọi ảnh (mục 3). Muốn sắc nét: `--quality high` (hoặc `--resolution 2K`); không xin "sharpen/HDR" (viền sáng giả làm tách lớp sai).

**Bước 4 (render hình ảnh):** ảnh gốc nhân vật trước (ứng viên đã chọn, vẽ lại high nếu cần) → `film/assets/raw/<id>.png`; rồi mỗi cảnh `gen.py image --model openai --quality high --ref <ảnh gốc 1> --ref <ảnh gốc 2> --aspect 3:2 --out film/assets/frames/<sc>.png --what <sc>`. Không tách nền. Soát: niên đại, nhân dạng, số người, lề, không chữ. Chạy thử 3D cho 2–3 cảnh khó (`--seconds 4`, ra `film/out/parallax_test/`) và xem `*_contact.jpg`. Manifest: `kind: "frame"`, `file` = ảnh frame.

**Bước 6 (dựng):**
1. `film/public/parallax/jobs.json`: mỗi cảnh liền khối một job `{"image": "film/assets/frames/sc05.png", "out": "film/public/parallax/sc05.mp4", "seconds": <thời lượng cảnh + 0,5 s đệm chuyển cảnh>, "move": "orbit-right", "subject": "0.62,0.55", "strength": 1.0, "size": "16:9"}` (9:16 cho phim dọc; `"1920x880"` khi phim có letterbox 100 px, xem bước 3).
2. Chạy một lệnh trong thư mục dự án: `"$BGREMOVE_PY" "$PARALLAX_PY" --batch film/public/parallax/jobs.json`. RTX 4060: ~0,1 s mỗi khung (8 s clip ≈ 25 s) + ~15 s độ sâu cho ảnh mới (cache theo nội dung ảnh, đổi move không tính lại). Phim 20 phút ≈ 1 giờ: chia `jobs.json` thành nhiều batch ≤ 10 phút, chạy tuần tự trong lượt (mục 2.6, render dài). Mỗi job in một dòng JSON (overscan, edge_share, contact).
3. Soát mọi `*_contact.jpg` (đầu/giữa/cuối): mép nhân vật rách, vật mảnh bị kéo, vùng vá loang, chủ thể ra khỏi khung, `overscan` > 1,3 (crop nhiều). Sửa: giảm `strength` (0,6), đổi move (drift, push-in lộ ít hơn orbit), đổi `subject`; vẫn lỗi thì vẽ lại ảnh theo phần prompt.
4. Engine: cảnh liền khối = `OffthreadVideo` của clip làm nền, chồng chữ, phụ đề, lớp additive (sương, tàn lửa, lửa quay thật đặt đúng chỗ), chuyển cảnh mờ chéo ~0,5 s. Không thêm chuyển động máy quay của engine lên clip; grain/vignette toàn phim như cũ (clip mặc định `--look clean`).
5. Âm thanh, QA, render, `render.json` như mục 2.6.

**Giới hạn:** nhân vật không cử động riêng, chỉ có máy quay. Cảnh cần hành động (vung tay, đi lại): hỏi người dùng giữa video AI (`gen.py video`, có giá, mục 3) và tách nhân vật khỏi chính ảnh frame (`cutout.py`) để thở/rung nhẹ trong engine.

### 4.10 Xếp lớp: GPT vẽ từng lớp → camera 3D (pipeline `stacked`)

Áp dụng khi `project.json` có `"pipeline": "stacked"`. Mỗi cảnh dựng lại được **ước lượng không gian 3D rồi chia 2–4 lớp theo độ sâu**; GPT vẽ **riêng từng lớp** theo prompt của bạn, máy cắt nền, engine xếp các lớp ở đúng khoảng cách và **đi camera thật** để tạo chiều sâu. Việc của bạn chỉ là: chia lớp, viết prompt từng lớp, chọn camera phục vụ nội dung. Cảnh tư liệu, clip, thẻ chữ, tựa giữ cách cũ.
*(Nguồn gốc: 2026-10-09, người dùng so 3 cách trên The Book of Enoch: ghép lớp trông phi vật lý, ảnh liền khối gần như không chuyển động, xích vẽ bằng code xấu. Chốt: GPT vẽ từng lớp, Claude xếp lớp + camera; hiệu ứng code chỉ khi người dùng duyệt.)*

**Chia lớp (bước 3):**
- 2 lớp: cảnh đơn giản (chân dung trên nền trời). 3 lớp (phổ biến): xa / trung (nhân vật) / tiền cảnh. 4 lớp: thêm một tầng giữa (rặng núi gần, đám đông phía sau).
- **Nhân vật luôn cùng lớp với mặt đất họ đứng** (mỏm đá, sàn nhà, sườn đồi + người + đạo cụ trên đó). Không bao giờ tách người đứng một mình.
- Lớp xa nhất (`far`) vẽ **kín khung**, không người, không vật gần. Lớp tiền cảnh (`fg`) chỉ vài vật ở mép/góc khung (đá, cột, cành), không che chủ thể.
- Khoảng cách `z` (mét) hợp lý: trời/núi 60–200, trung cảnh có người 6–15, tiền cảnh 2–5. Lớp càng cách xa nhau, thị sai càng mạnh.
- Mỗi cảnh trong `scenes.json`:
  ```json
  {"id": "sc29", "reconstruction": true, "light": "night, cold blue moonlight from the upper left, horizon at one third from the top",
   "layers": [{"name": "far", "z": 60, "prompt": "..."},
              {"name": "mid", "z": 9, "prompt": "...", "refs": ["film/assets/raw/c_raphael.png", "film/assets/raw/c_azazel.png"]},
              {"name": "fg", "z": 3, "prompt": "..."}],
   "camera": {"move": "push-truck-right", "strength": 1, "frame": [0.5, 0.37]},
   "fx_notes": "đề xuất (cần duyệt): ánh sáng chạy dọc sợi xích lúc nghe 'bind'"}
  ```
  và mỗi lớp một asset `{"key": "sc29_mid", "kind": "layer", "model": "openai", "quality": "high", "est_usd": 0.08}`.

**Viết prompt từng lớp:**
- Mọi lớp chung một câu `light` (hướng sáng, giờ, độ cao đường chân trời) để khớp nhau; layerkit tự thêm chuỗi phong cách và luật khung hình. Câu `light` đi vào **mọi** lớp nên chỉ tả ánh sáng, không nhắc người hay vật (viết "light from the newborn baby" thì GPT vẽ thêm một em bé ở lớp xa). *(Nguồn gốc: Book of Enoch "oldest story", sc83.)*
- GPT hay đặt đầu nhân vật quá cao dù ghi phần trăm: ghi thẳng "the top 35% of the image above their heads is empty plain grey", và tránh cho lớp giữa vẽ lại tường/cây của lớp xa ("only these things, nothing else"). Đầu vẫn sát mép thì hạ `frame` y (0,28–0,38) trước khi vẽ lại.
- Mô tả vị trí trong khung bằng phần ba / phần trăm ("Raphael ở phần ba bên trái, cao khoảng một phần ba khung"), giữ đầu, tay giơ, chân trong khoảng 18–82% chiều cao ảnh (phim chiếu dải ~2,2:1, trên dưới bị cắt).
- Lớp có nhân vật: `refs` = ảnh gốc từng nhân vật, nói rõ "second image: exact face…". Nhân vật mặc đồ **trắng/xám nhạt** dễ bị cắt lẫn với nền xám: tô đậm ánh sáng viền, tránh áo cùng tông xám.
- Không vẽ lửa, khói cuộn đứng im; xích, dây, đạo cụ thì **vẽ thật trong ảnh** (đẹp hơn mọi thứ vẽ bằng code).

**Camera (bước 3 chọn, bước 6 dựng):** `move` ∈ `push-in` (căng thẳng, khoảnh khắc then chốt) · `pull-out` (lộ quy mô, kết hồi) · `truck-left/right` (hành trình, giới thiệu không gian) · `orbit-left/right` (giới thiệu nhân vật) · `crane-down` (từ trời xuống người) · `crane-up` (hùng vĩ) · `push-truck-left/right` (tiến vào chéo, điện ảnh nhất) · `drift` (lời dẫn dài, tĩnh). `strength` 0,6–1,4. `frame` = điểm ảnh ở tâm khung lúc bắt đầu (y < 0,5 khi đầu người gần mép trên). Không lặp một move ba cảnh liền; đổi chiều xen kẽ.

**Hiệu ứng code:** mặc định **không có**. Chỉ ghi `fx_notes` khi thật sự nâng cảnh (ánh sáng lướt trên chi tiết đã vẽ, lửa/khói quay thật đặt đúng chỗ, sương trôi giữa các lớp, chớp sáng đúng nhịp lời dẫn) và nói rõ là đề xuất. Người dùng duyệt ở cổng bước 3; cảnh không được duyệt thì chỉ xếp lớp + camera. Không bao giờ dùng code để **vẽ vật thể** (xích, vũ khí, nhân vật). Bộ Motion kit (chuyển cảnh, tông màu, cảm giác máy, chữ động; mục 5.13) **không** thuộc hiệu ứng code cần duyệt: Claude tự chọn.

**Bước 4:** ảnh gốc nhân vật trước (`film/assets/raw/<id>.png`), rồi `"$CREATER_PYTHON" "$LAYERKIT_PY" 3_scenes/scenes.json` (vẽ mọi lớp còn thiếu; `--only sc05`, `--redo sc05:mid` để vẽ lại). Lớp sau cùng vẽ kín khung; các lớp trước GPT vẽ trên nền xám phẳng với lớp sau làm tham chiếu, máy cắt đúng phần xám (giữ người lẫn mặt đất). Ghép thử mỗi cảnh (các lớp chồng lên nhau) vào `4_images/sheet_layers_<nhóm>.jpg` và soát: khớp ánh sáng, tỉ lệ người với mặt đất, lớp trước không có người lạ, đầu không bị cắt. Soát thêm từng lớp cắt trên nền màu (không chỉ ảnh ghép): greykey chỉ bỏ nền xám **nối với mép ảnh**, nên khoảng nền kín (giữa tay và thân) còn đục, quầng sáng đèn vẽ trên nền xám thành mảng xám mờ; khoét bằng mặt nạ (mẫu `notes/tools/fix_layers.py` của dự án mummies) hoặc vẽ lại lớp. Chi phí ≈ $0,04–0,08/lớp (openai, có ref). Đo tỉ lệ pixel đặc của mỗi lớp cắt: lớp trước > ~90% đặc là GPT đã vẽ kín khung (mất thị sai): vẽ lại với câu "Paint ONLY <các vật> and a small patch of ground under them; everything else (sky, walls, floor) is flat plain grey". Không đặt cùng một vật ở cả lớp xa và lớp có người (vd. ghế trống ở far, người ngồi ghế ở mid): GPT không đặt người đúng chỗ vật của lớp xa, ghép lại thành vật đôi. Cần cả bản trống lẫn bản có người thì sửa lớp far xoá vật (`--ref` far, "Only remove…") rồi cắt người khỏi mid bằng `cutout.py`, ghi hai bộ `layers_*.json`. *(Giáo phái tổng hợp: 3/52 lớp mid vẽ kín khung, cảnh TR0 nhìn từ trần ra 4 cái ghế.)*
- Bắt nền xám sót bằng máy, không chỉ bằng mắt: quét mọi lớp cắt tìm vùng **phẳng** (độ lệch chuẩn cửa sổ 7×7 < 2, độ sáng > 60, ≥ 300 px; tranh vẽ thật luôn có hạt) và xem các vùng đó viền màu trên ảnh ghép; quầng đèn ám màu ấm nên đừng lọc theo màu xám trung tính. Viền lá/cành lẫn nền xám thành "cây ma" sáng nhạt trên nền tối: khoét các điểm xám trung tính trong khung chứa chúng. Mảng sàn GPT vẽ kèm dưới vật (vệt nắng, bóng) không khớp sàn của lớp sau và lộ mép răng cưa: bỏ, chỉ giữ chân vật. Mẫu: `notes/tools/fix_grey.py` của dự án Giáo phái tổng hợp (giữ bản cũ ở `notes/layers_backup/`). *(Giáo phái tổng hợp: 12 lớp còn mảng xám lọt qua bước 4 — nan bánh xe, tam giác dây lều, quầng đèn bàn, lưng ghế, hàng cọ — thấy ở ảnh tĩnh bước 6.)*

**Bước 6:** cảnh dựng lại = `<LayerScene cfg={layers.json} duration move strength frame />` (`src/staged/LayerScene.tsx`; `layers.json` ở `public/layers/<cảnh>/`). Kích thước từng lớp được tính tự động theo đường đi camera, nhưng chỉ là ước lượng: lớp tiền cảnh sát máy khi trượt/orbit/cần cẩu mạnh, và lớp xa khi z xa / z chủ thể lớn, vẫn lộ mép thẻ (dải đen, hoặc vật tiền cảnh bị cắt thẳng ở mép khung), thường ở cuối cảnh nên ba ảnh tĩnh dễ bỏ sót. Trước khi render chạy kiểm hình học từng khung (mẫu `notes/tools/check_edges.py` của dự án mummies); lộ mép thì đổi chiều máy về phía mép trống của tiền cảnh, hoặc giảm `strength`. Soát ảnh tĩnh đầu/giữa/cuối mỗi cảnh; nếu khung chật thì giảm `strength` hoặc dời `frame`, nếu lớp lỗi thì vẽ lại lớp đó. Kiểm thêm **độ che của lớp gần nhất** ở đầu/giữa/cuối cảnh (chiếu khung lên thẻ, lấy độ đục; mẫu `notes/tools/check_cover.py` của dự án Giáo phái tổng hợp): `crane-down`/`push-in` đẩy tiền cảnh sát máy dâng lên che kín khung mà không lộ mép nào, kiểm mép không bắt được → đổi đường máy. *(Giáo phái tổng hợp sc39: cỏ mờ z 6 che 26 % → 100 % khung ở cuối cảnh.)*

### 4.11 Hồ sơ tư liệu thật (pipeline `dossier`)

Áp dụng khi `project.json` có `"pipeline": "dossier"`. Phim dựng từ **ảnh, trang tài liệu, footage THẬT** như vật chứng trong một hồ sơ: ảnh in có viền thả xuống bàn đúng lúc lời dẫn gọi tên, trang báo/Wikipedia có highlight quét theo đúng chữ đang đọc, bảng điều tra nối dây đỏ, footage cũ trong khung phim 8mm, logo tổ chức thành vật thể 3D. AI chỉ **tái hiện** những gì không thể có ảnh (cổ đại, cảnh không ai chụp), bằng cách xếp lớp (mục 4.10) và gắn nhãn tái hiện (mục 1.2). Engine: `src/dossier` (`<DossierScene>`, cẩm nang `film/ENGINE.md` mục "Dossier kit"; video mẫu `E:\Tool\Creater Vid\engine\out\showcase\dossier_showcase.mp4`).
*(Nguồn gốc: 2026-11-03, người dùng mổ xẻ hai video kênh Moon: "The Moment Joe Rogan Realises His Guest Is a Fraud" và "The 'Crazy' Conspiracy Theories That Turned Out To Be True" (`C:\Tool\video-watcher\output\…\FORMULA.md`). Ấn tượng nhất: cách triển khai vấn đề và cách dựng tài liệu thật, ảnh thật có chuyển động. Yêu cầu: không chép máy móc, kết hợp với các cách dựng cũ thành một cách dựng mới.)*

**4.11.1 Khung kể (bước 1).** Chọn một khung và ghi `"frame"` trong `script.json`; nêu lý do trong `research.md`.
- `case-files` · **hồ sơ vụ việc**: 3–5 vụ song song cùng một luận đề, mỗi vụ là một *kiểu* khác nhau của luận đề (bởi cái tôi / bởi tổ chức / bởi trí tưởng tượng / bởi tiền…). Xếp theo mức nghiêm trọng **tăng dần**; mở bằng vụ nổi tiếng nhất nhưng nhẹ nhất; vụ dài và sâu nhất đặt thứ hai. Mỗi vụ đi theo chu trình 7 nhịp, ghi vào `role` của beat: `mask` (hình ảnh công khai + 1 con số uy tín) → `question` (câu hỏi ai cũng nên hỏi) → `slip` (clip nguyên văn, dẫn bằng "But listen to how he responds") → `decode` (một câu dịch lại, ngắn, khô) → `name` (gọi tên kỹ thuật bằng một thuật ngữ có nguồn gốc kiểm chứng được) → `evidence` (tài liệu ngoài, có highlight) → `reaction` (phản ứng của người trong cuộc, nếu có thật trong clip). Lặp `question → evidence` 2–4 vòng ở vụ dài. Câu nối giữa hai vụ phải **leo thang** ("But X is nothing compared to…"), không phải "tiếp theo là".
- `rabbit-hole` · **đường hang thỏ**: một chuỗi mắt xích. Mở bằng **một người cụ thể, hiện đại**, không mở bằng khái niệm. **Mắt xích luôn là một người có tên có mặt ở cả hai đầu** ("bốn thành viên của A đã ở sẵn trong B"), lùi dần về quá khứ rồi quay lại hiện tại. Lời dẫn ngôi thứ nhất điều tra ("we found", "when I combed through this leak"). Mỗi 7–10 phút **khép một vòng** (một mắt xích nối về nhân vật mở đầu). Để nhân vật tự thú bằng clip dài nhất phim. Cuối phim có thể dựng phiên bản cực đoan của chủ đề rồi tự gỡ nó, để kết luận nghe tỉnh táo.
- `classic`: cấu trúc mặc định của mục 2.1.
- Chung cho cả hai khung: hook ≤ 35 s, câu cuối hook nói lại lời hứa của tựa; điểm tạm dừng (chương, cliffhanger) đặt ngay sau một câu lộ, không giữa đoạn kể nền. Mỗi beat ghi `"evidence": ["E05", …]`: danh từ riêng nào cần bằng chứng thật.
- **Xác thực vẫn đứng trên hết (mục 1, nhất là 1.6):** hai khung này dễ thành buộc tội. Không gọi ai là "fraud", "asset", "agent" khi nguồn không nói thế; dùng câu hỏi, ghi rõ ai tuyên bố, nêu phản biện có nguồn một nhịp trong mỗi vụ. **Trùng thành viên không phải bằng chứng âm mưu:** lời dẫn nói đúng mức tài liệu cho phép ("both sat on the board"), không suy ra động cơ.

**4.11.2 Triết lý hình.**
- **Mỗi danh từ riêng của lời dẫn = một bằng chứng thật, lên hình đúng lúc được đọc**: tên người → ảnh thật của người đó; tổ chức → logo thật; "a leaked document" → chính tài liệu đó; một con số → `CountUp` hoặc chính dòng chứa nó, highlight.
- Ảnh thật là bằng chứng; ảnh AI chỉ là tái hiện (mục 1.2, 1.10: không vẽ AI giống người thật). Stock điện ảnh chỉ cho đoạn ý niệm không còn danh từ riêng nào (thường ở đoạn kết).
- Ảnh thật tự nó chưa hấp dẫn: hấp dẫn đến từ việc **dàn ảnh như vật thể** (ảnh in có viền, đổ bóng, nghiêng, đáp xuống bàn), **máy quay không bao giờ đứng yên**, và **thông tin lộ dần từng lớp** (ảnh mờ tối → rõ mặt → tên gõ từng chữ → dấu). Engine đã làm sẵn phần chuyển động; việc của Claude là chọn đúng bằng chứng, đúng shot, đúng chữ để đồng bộ.

**4.11.3 Bằng chứng (bước 2–4).**
- **Thứ tự nguồn:** tài liệu gốc (CIA Reading Room, congress.gov, National Archives, văn bản toà án, PDF bị lộ mà báo lớn đã đăng) → trang báo lớn (chụp cả trang có tên báo) → Wikipedia / Wikimedia Commons → ảnh sự kiện → footage tin tức, phỏng vấn. Không tìm được ảnh thật nào thì mới tái hiện, ghi lý do.
- Bước 2: người thật có `depiction: "archival_photo"`, ghi sẵn ảnh dự định (link, giấy phép); chỉ vai không thể có ảnh mới thử vai AI.
- Bước 3 lập `evidence` (mục 11.3): mỗi mục một `id`, loại (`photo | page | logo | archival_video | map`), `source_url`, `license`, người/tổ chức/tài liệu nó chứng minh, và với trang: các cụm từ sẽ highlight. **Ngoại lệ của 1.9 cho pipeline này:** người dùng duyệt bước 3 là duyệt tải/chụp mọi mục trong `evidence` (không cần duyệt từng file ở bước 5); mục thêm sau bước 3 vẫn phải hỏi.
- Giấy phép: ưu tiên phạm vi công cộng (ảnh chính phủ Mỹ, tài liệu giải mật), Wikimedia Commons có giấy phép ghi rõ. Ảnh của hãng ảnh (Getty, AP, Reuters) không tải riêng tấm ảnh: dùng **ảnh chụp cả trang báo** có tên báo, như tư liệu bình luận. Footage tin tức, podcast: đoạn ngắn có lời bình trước và sau, giữ logo, lower-third của nguồn (đó là con dấu "nguồn thật"), ghi vào `notes/sources.md`.
- Bước 4:
  - tải ảnh, logo, footage cũ vào `film/public/evidence/`;
  - chụp trang web bằng `node scripts/pagecap.mjs <url> <id> --mark "cụm 1" --mark "cụm 2"` (chạy trong `film/`): ra `public/docs/<id>.png` (2×, rộng 1100 px CSS) và `<id>.json` có `aspect` và toạ độ từng dòng của từng cụm. Mã thoát 3 = có cụm không tìm thấy (`missing`) hoặc nằm ngoài vùng chụp (`outside_capture`): sửa cụm cho đúng chữ trên trang, hoặc `--height` lớn hơn / `--top`;
  - scan, PDF đã thành ảnh: đo hộp cụm từ bằng tay (phân số của ảnh) và ghi vào manifest;
  - chân dung cần tách nền: `cutout.py` (miễn phí);
  - cảnh tái hiện: layerkit như mục 4.10;
  - manifest `kind`: `evidence` (ảnh), `document` (trang, kèm `marks`), `logo`; mỗi mục ghi `source_url`, `license`, `aspect`;
  - ghép bảng xem nhanh `4_images/sheet_evidence_<hồi>.jpg` và soát: đúng người/đúng tài liệu, chữ trên trang đọc được khi phóng 2,5×, logo nền trong suốt.

**4.11.4 Các kiểu shot (bước 3 chọn, bước 6 dựng bằng `<DossierScene shot>`).**

| `shot.kind` | Dùng khi | Chuyển động |
|---|---|---|
| `photos` | giới thiệu người, sự kiện, nơi chốn (1–5 ảnh) | ảnh in đáp xuống bàn khi tên được đọc; `reveal` mờ tối → rõ mặt cho nhân vật "bí ẩn"; tên gõ từng chữ; `redact` dải đen khi tài liệu gốc đã bôi đen; `stamp` |
| `doc` | mọi câu "tài liệu nói rằng…", tiêu đề báo, danh sách thành viên | máy đi tới từng cụm trước khi đọc ~0,5 s; highlight vàng quét từng dòng trong lúc cụm được đọc; `box` đỏ khoanh tên; bút đỏ ghi chú + mũi tên; ảnh chân dung trượt đè lên danh sách (`cards`) |
| `board` | mắt xích, tóm tắt chuỗi, "tất cả nối với nhau" | ảnh ghim, dây đỏ vẽ ra đúng lúc lời dẫn nói về liên kết, nhãn trên dây ("same founder") |
| `archive` | footage, ảnh trước ~1990 | khung phim 8mm hoặc TV cũ, đếm khung, bụi, vệt sáng cuối |
| `logo` | lần đầu gọi tên một tổ chức | logo thật thành khối 3D, vệt sáng quét, sương; tên các mắt xích trước trôi mờ phía sau (`ghosts`) |
| `years` | nhảy thời gian qua một người | năm lớn trượt trên đường kẻ, ảnh chân dung phía sau |

Không phải shot hồ sơ, giữ component cũ: clip phỏng vấn (`QuoteClip`, mục 1.6, 7.4), bản đồ (mẫu `templates/news-map`, như bộ quy tắc tin tức), con số (`CountUp`), cảnh tái hiện (`LayerScene`), tựa và chương (Motion kit).

- **Dấu (`stamp`):** chữ chỉ lấy từ trạng thái khẳng định trong `sources.json` (`VERIFIED`, `DISPUTED`, `UNVERIFIED`) hoặc từ chính tài liệu (`CLASSIFIED`, `DECLASSIFIED`, `DENIED`, `REDACTED`); không bao giờ là phán xét về một người. Mực: xanh = đã kiểm, đỏ = tranh cãi/mật, vàng sẫm = chưa kiểm.
- **Tông bàn** (`tone`), một tông chủ đạo cho cả phim: `night` (mặc định), `paper` (lịch sử, lưu trữ), `steel` (tình báo, công nghệ), `cork` (bảng điều tra), `black` (logo, khung phim). Một màu nhấn duy nhất: vàng cho highlight bằng chứng, đỏ cho dây, dấu, bút.
- **Nhịp:** một ảnh đứng một mình ≤ 4–6 s; lời dẫn nói lâu về một thứ thì thêm lớp lộ dần (cụm highlight kế tiếp, thẻ thứ hai, dấu), không giữ một khung. Chuyển cảnh (mục 5.13): `blinds` vào tài liệu, `zoom` khi đi sâu một mắt xích, `flash` lúc lộ, `leak` vào footage cũ, `cut` vào/ra clip. Ảnh thật không chỉnh tông điện ảnh: chỉ `tone` của thẻ (`bw`, `sepia`, `archive`) hoặc để nguyên.

**4.11.5 Đồng bộ với lời dẫn (bước 6).** Mọi `at` trong shot viết theo lời dẫn: `"l12"` (đầu dòng), `"l12:non-faculty"` (chữ đầu của cụm), `"l12:Drexel-4"` (lệch khung). Engine đọc `src/voice.json`, highlight tự quét đúng bằng thời gian cụm được đọc; cụm sai chữ thì báo lỗi ngay khi chụp ảnh tĩnh (sửa cho đúng chữ trong `caption`). Chỉ dùng số khung khi không có lời đọc tương ứng.

**4.11.6 Soát (bước 6, thêm vào mục 9).** Ảnh tĩnh của mỗi shot ở: lúc thẻ vừa đáp, **giữa** lúc highlight đang quét, lúc dấu vừa đóng, cuối cảnh. Kiểm: chữ highlight đọc được, không bị letterbox hay phụ đề che; bút đỏ nằm trong khung; tên gõ xong trước khi cảnh hết; không có ảnh AI nào thiếu nhãn tái hiện.

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
5.11 **Hậu kỳ máy quay:** cảnh có lửa hay nguồn sáng mạnh bật `post={{bloom, haze}}` (quầng sáng quanh vùng sáng, không khí méo phía trên lửa). Nhân vật tách nền đặt trong không khí có màu thì thêm `wrap` 0,1–0,2 (ánh nền tràn qua viền). **Không bật bloom ở cảnh có `Streak`** (vệt sao rơi): shader vệt sinh điểm NaN, bloom lan nó ra thành cả khung đen. *(Nguồn gốc: Book of Enoch v1, 3 đoạn đen 0,4–5,8 s.)*
5.12 **Hiệu ứng phải nằm trong khung nhìn:** kiểm tra mép dưới khung (letterbox, tiền cảnh). Bản thử đầu tiên đặt chậu than dưới mép khung, lửa thật không ai thấy.
5.13 **Nhịp hình: bộ Motion kit (Claude tự chọn).** Engine có sẵn `src/kit` (cách dùng: `film/ENGINE.md` mục "Motion kit"; video mẫu mọi hiệu ứng: `E:\Tool\Creater Vid\engine\out\showcase\kit_showcase.mp4`): 11 kiểu chuyển cảnh, 7 tông màu, cảm giác máy (cầm tay, rung va chạm, light leak, lens flare, viền màu, phim cũ) và 9 kiểu chữ động. Người dùng giao cho Claude **tự chọn** theo nội dung từng cảnh, không cần duyệt riêng; lựa chọn ghi vào `scenes.json` (mục 11.3) để người dùng thấy ở cổng bước 3 và sửa nếu muốn.
  - **Chuyển cảnh** (`transition` = cách cảnh **vào**): mặc định `dissolve`; `cut` nhịp nhanh, cú sốc, vào/ra clip phỏng vấn; `dip` hết chương, cái chết, nhảy thời gian dài; `flash` khoảnh khắc lộ sự thật, va chạm, nổ; `leak` ký ức, quá khứ, giấc mơ; `whip` "trong khi đó", đổi nơi chốn gấp; `zoom` đi sâu vào chi tiết, vào bản đồ; `wipe` đi đường, chuyển giữa hai mạch song song; `iris` dồn chú ý vào một người/vật; `blinds` tài liệu, hồ sơ, danh sách; `glitch` hồ sơ mật, giám sát, bản ghi hỏng.
  - **Liều lượng:** kiểu mạnh (mọi kiểu trừ `dissolve`, `cut`, `dip`) là điểm nhấn ở chỗ câu chuyện rẽ hướng, khoảng 1 trên 4–8 cảnh; không hai kiểu mạnh giống nhau liền nhau; mỗi phim dùng ≥ 4 kiểu khác nhau. Không còn phim "tất cả mờ chéo 15 khung".
  - **Màu** (`look.grade`): mỗi phim một tông chủ đạo hợp đề tài (vd. `teal-orange` phiêu lưu, bí ẩn; `cold` băng giá; `warm` cổ đại, hoài niệm; `bleach` chiến tranh), giữ cho mọi cảnh dựng lại; chỉ đổi tông khi câu chuyện đổi thế giới: `archive` + `ArchiveFilm` cho ảnh/tư liệu cũ, hồi tưởng; `noir` đoạn u tối, tội ác; `duotone` một cảnh nhấn cách điệu. Ảnh tư liệu thật không chỉnh tông điện ảnh (chỉ `archive` hoặc để nguyên).
  - **Cảm giác máy** (`look.feel`): `handheld` khi căng thẳng, "bạn đang ở đó"; `impact@<khung>` đúng khung có tiếng va chạm (thêm vào CUES để tiếng khớp); `leak` cảnh ấm, ký ức; `flare@x,y` đặt đúng nguồn sáng có trong tranh (mặt trời, đèn, lửa), không bịa nguồn sáng; `chroma` bất an, bản ghi hỏng. Tối đa hai lớp bọc mỗi cảnh.
  - **Chữ động** (`text_fx`): tựa phim `MaskTitle`; mở chương/hồi `ChapterCard`; nhân vật thật hoặc địa danh lần đầu lên hình `LowerThird`; nhảy sang nơi/thời điểm mới `Typewriter` ("ANTARCTICA · JANUARY 1947"); con số đáng nhớ `CountUp` (đúng số đã kiểm, mục 1); câu then chốt `PunchWords` (1–2 lần mỗi phim); trích dẫn đắt nhất `PullQuote` (nguyên văn, mục 7.3); mật danh, hồ sơ `Scramble`. Chữ động không trùng giờ với phụ đề lời dẫn ở cùng vùng khung, không che mặt; soát ảnh tĩnh lúc chữ đang chạy và lúc đã đứng.
  - Phim tiếng Việt/Nga: Cinzel không có dấu và chữ Kirin, dùng `NEWS_THEME` hoặc theme riêng từ Oswald/Inter/IBM Plex Mono.
  - Soát (mục 9): ảnh tĩnh ở giữa mỗi chuyển cảnh mạnh, không chỉ đầu/giữa/cuối cảnh.
  *(Nguồn gốc: 2026-10-20, người dùng thấy phim "khá đơn điệu" — Pyramids Under the Ice có 86 cảnh, cả 86 lần chuyển cảnh là mờ chéo 15 khung, chữ chỉ có phụ đề — muốn thêm hiệu ứng chuyên nghiệp, nghệ thuật cho cả hai loại video, và giao cho Claude tự chọn hiệu ứng hợp từng cảnh.)*

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
7.2 Lời dẫn hiện từng chữ (mờ → rõ, nổi nhẹ). Dòng chia cân đối (`text-wrap: balance`), không để một chữ lẻ rớt xuống dòng dưới. Chữ viết tắt ("L. Ron Hubbard", "U.S.") không phải hết câu: không ngắt dòng sau nó. Đọc liền thì dòng chỉ tắt sau khi chữ cuối của nó đã bắt đầu (đổi dòng ~6 khung trước chữ đầu dòng sau). Một câu đọc trải qua nhiều shot thì phụ đề lời dẫn đặt ở tầng phim (khung tuyệt đối), không trong từng cảnh.
  - Cảnh tranh có phụ đề: dải tối mờ dưới phụ đề (gradient ~300 px trên letterbox, bật theo phụ đề của cảnh; `CaptionScrim` trong `Gen.tsx`). Chỉ có bóng chữ thì chữ sáng nghiêng chìm vào tranh sáng, rối (bụi, trời hoàng hôn, biển bão, thành phố nhìn từ trên). Soát ảnh tĩnh **giữa** một dòng phụ đề, không chỉ khung đầu/cuối cảnh (lúc chữ đang mờ dần).
7.3 Trích nguyên văn đặt trong ngoặc kép cong “ ”, cắt bớt thì dùng "…". Dòng nguồn in hoa, giãn chữ, kiểu "1 ENOCH 6:4" hay "JOE ROGAN EXPERIENCE #2530".
7.4 Khi clip phỏng vấn đang phát: góc trên có tên người nói và nguồn, phụ đề là transcript nguyên văn theo từng dòng thời gian.
  - Tên người nói chỉ hiện khi chính người đó đang lên hình: clip podcast mở bằng cảnh người kia thì dời thẻ tên tới sau cú cắt máy quay (`thirdAt` của `QuoteClip`, tìm cú cắt bằng ffmpeg scene detect).
  - Mỗi dòng phụ đề clip hiện ≥ 0,8 s: tiếng đệm ngắn ("Yeah.") và câu cuối nói sát điểm cắt gộp vào dòng kề, giữ nguyên văn, tối đa hai hàng chữ.
  - Phụ đề clip lấy từ mốc từng chữ của **chính file clip đã cắt** (whisper `word_timestamps`), chia theo câu, ≤ 16 chữ (tới 18 nếu dừng đúng dấu câu), không kết dòng bằng mạo từ/giới từ/đại từ. Chỗ các lượt nghe khác nhau thì nghe lại riêng đoạn ngắn đó; sửa tên riêng theo ý người nói và ghi lại.
  - Clip có người thứ hai lên hình: mỗi người một thẻ tên đúng lúc máy quay sang họ (`cards` của `QuoteClip`), dòng người thứ hai bắt đầu nói mở bằng "– ". Không chắc ai nói câu ngắn nào thì không gán.
  - Ghép hai lượt nghe từng chữ (A có gợi ý chính tả tên riêng, B không): gốc là A, mỗi chỗ khác nhau giữ bản làm cả clip khớp transcript tập hơn; không dùng lượt nghe cắt ngắn thứ ba để phân xử (chỗ hai người nói chồng nhau nó bỏ chữ). Lượt nghe `condition_on_previous_text=False` có khi trả đoạn dài không dấu câu hoặc viết hoa giữa câu: đặt dấu câu, chữ hoa bằng tay được, nhưng công cụ phải so từng chữ với chữ đã nghe và dừng nếu khác chữ (chỉ cho ghép/tách chữ). Câu dài cắt giữa cụm ("in front / of each other") thì ghi chỗ ngắt tay. Dòng "– " cắt đúng một chữ có mốc gần cú cắt nhất. *(Giáo phái tổng hợp: 28 clip.)*

7.5 **Chữ động** (tựa, thẻ chương, tên người/địa danh, dấu địa điểm–thời gian, số đếm, câu then chốt, trích dẫn lớn): bộ Motion kit, mục 5.13.

## 8. Âm thanh

8.1 **Ưu tiên ElevenLabs cho nhạc nền và hiệu ứng** (`gen.py sfx`, ≈ $0,12/phút): lớp nhạc nền ≤ 22 s (prompt nhạc: drone dây trầm, hợp xướng không lời, trống trầm…) nối vòng có crossfade, nền không khí theo từng bối cảnh, hiệu ứng điểm đặt đúng cue (`Mixer.layer` / `Mixer.shot` trong audio-lib của phim). Mỗi file đo độ to rồi cân theo LUFS; whisper nghe các lớp 'không lời' để chắc không lọt chữ. `scripts/audio-lib.mjs` tự tổng hợp là phương án dự phòng và lớp drone nối mạch. Mọi cue lấy từ `src/timeline.js`, nên hình và tiếng luôn khớp. (gen.py chưa có lệnh Eleven Music: nếu app thêm thì dùng cho nhạc nền dài.) *(Nguồn gốc: người dùng yêu cầu tận dụng ElevenLabs cho âm thanh, Book of Enoch v4.)*
8.2 Clip phỏng vấn giữ tiếng gốc. **Trong trích đoạn podcast/phỏng vấn: tắt hẳn nhạc và hiệu ứng** (fade ~0,7 s hai đầu, danh sách `QUOTES`), chỉ còn tiếng người nói. Ngoài trích đoạn: luôn có một lớp nhạc nền nhỏ đúng vibe nội dung dưới lời dẫn. *(Nguồn gốc: người dùng chọn, Book of Enoch v5.)* **Tiếng clip phải chuẩn hoá về mức lời dẫn** (~−15,5 LUFS mỗi clip) trước khi trộn: tiếng podcast gốc nhỏ hơn lời dẫn 6–9 dB, người xem thấy âm lượng nhảy. QA đo độ to riêng một đoạn clip và một đoạn lời dẫn trên chính file MP4. *(Nguồn gốc: Book of Enoch v1.)*
8.3 **Master:** `m.write(...)` master 2 lượt (đo → chỉnh gain → limiter) về −15 LUFS. File cuối ≈ −15 LUFS, true peak ≤ −1,5 dBTP. *(Bản đầu tiên ở −20,6 LUFS, nghe nhỏ hơn video khác trên YouTube.)*
  - Limiter chạy ở 4× tần số lấy mẫu (bắt đỉnh liên mẫu); bản ghép cuối để trần ~−2,7 dBTP trước khi nén AAC (AAC vọt thêm ~0,7 dB).
  - Tiếng clip phỏng vấn do Remotion trộn không đi qua master: sau render, trộn lại cả phim (soundtrack + từng clip đã chuẩn hoá đặt đúng `QUOTES`), master, rồi ghép vào hình (`-c:v copy`). Mẫu: `notes/tools/final_audio.py` của dự án Book of Enoch.
8.4 **Lời dẫn bằng giọng đọc** (ElevenLabs qua `gen.py tts`). Làm theo `film/ENGINE.md` mục Narration:
  - Giọng theo ngôn ngữ của video, chọn ở trang Cài đặt (tên và id ghi ở đầu phiên). Đổi giọng thì hỏi người dùng.
  - Chi phí nằm trong ước tính của kịch bản. Người dùng duyệt kịch bản là duyệt luôn chi phí giọng. Tối đa 3 bản đọc cho mỗi lượt viết lại lời dẫn; nhiều hơn thì hỏi.
  - **Đọc cả kịch bản trong một lần** (một file văn bản, mỗi câu một đoạn, cùng giọng): như một buổi thu, giọng liền mạch giữa các câu. `--takes N` tính tiền N bản.
  - Tag cảm xúc ngắn, mỗi câu một tag (`[reverent]`, `[ominous]`, `[low, intense]`, `[grave]`, `[sorrowful]`, `[solemn, firm]`, `[quietly]`), một hơi thở mở đầu `[inhales softly]`. Ngắt nhịp bằng "…" và "—". Không nhồi tag.
  - Chữ trên màn hình = đúng chữ được đọc (phụ đề hiện theo từng chữ được đọc).
  - Chọn bản đọc bằng whisper: đủ chữ, không đọc lọt tag, nhịp vừa cảnh. Đặt câu bằng `audio/voice/plan.json` + `scripts/voice-build.py`; tăng tốc tối đa 3%; từ khoá rơi đúng cue hình (ví dụ "hand and foot" đúng tiếng xích).
  - Cảnh không đủ chỗ cho câu đọc tự nhiên thì kéo dài cảnh (đuôi cảnh giữ hình), không đọc nhanh hơn. Sau khi có giọng, đặt lại thời lượng mọi cảnh có lời = thời gian đọc + 0,4 s vào + 0,8 s đuôi + ~1,2 s thở (cảnh dư chỗ thì rút lại), trước khi dựng.
  - File văn bản đọc: **mỗi beat một đoạn liền**, không cắt giữa câu theo cảnh (cắt giữa câu làm giọng ngắt sai).
  - `plan.json`: mỗi dòng audio phải dừng ở chỗ ngắt có khoảng lặng (thường một dòng mỗi cảnh) vì `voice-build` cắt theo khoảng lặng; phụ đề ≤ 16 chữ chia riêng từ mốc từng chữ (`src/captions.json`), không chia dòng audio nhỏ hơn.
  - Bản đọc liền có thể nối hai đoạn chỉ cách < 0,2 s lặng: cắt theo "đảo năng lượng" sẽ gộp đuôi dòng này vào dòng sau (câu cuối cảnh phát sang cảnh khác). `voice-build` phải cắt mỗi ranh giới ở quãng lặng dài nhất giữa chữ cuối dòng này và chữ đầu dòng sau, và đặt chữ đầu mỗi dòng ở tiếng hữu thanh đầu tiên sau chỗ cắt (mốc ElevenLabs có thể trễ tới 0,6 s ở đầu đoạn). Sau `voice-build`: không dòng nào chồng dòng trước, chữ đầu cách điểm bắt đầu dòng ≤ ~0,3 s.
  - Mốc ElevenLabs ở ranh giới đoạn lệch theo **cả hai chiều**: chữ cuối đoạn trước có thể «kéo» sang khoảng nghỉ tới ~0,4 s. Vì vậy tìm quãng lặng trong cửa sổ ±0,6 s quanh **cả hai** mốc (không chỉ giữa hai mốc). Quãng lặng < 0,3 s (hai đoạn đọc liền) thì cắt đúng giữa. Phụ âm xát đầu từ («С», «Ш») nhỏ dưới ngưỡng lặng: đo dB tại mọi điểm cắt, và whisper **từng file dòng** để chắc còn chữ đầu, chữ cuối. *(Điểm tin 13.10.2026 tập 3: «США» đầu tin diesel bị cắt lẹm trong v1.)*
  - Cách sửa đã chạy được: giữ danh sách chữ theo alignment ElevenLabs (đúng số chữ phụ đề) nhưng chữ nào khớp với whisper cả bản (difflib) thì lấy **mốc bắt đầu theo whisper**, và chữ cuối mỗi dòng kết thúc trước chữ đầu dòng sau; ghi vào `out/voice/words_<take>.json` (cache của `voice-build`) rồi mới chạy `voice-build`. *(Giáo phái tổng hợp: mốc đầu đoạn trễ 0,4–0,9 s, «Hollywood» và «Belonging» rơi sang dòng trước.)*
  - Whisper chạy cả file dài có thể **bỏ sót phần đuôi**: nghe theo đoạn ≤ 4 phút. Mốc từng chữ cho `voice-build` lấy từ `take.mp3.alignment.json` của ElevenLabs (đúng số chữ phụ đề), chỗ whisper báo lệch thì cắt nghe lại riêng.
  - Chi phí giọng: báo đúng số `gen.py` ghi (có thể thấp hơn ước tính nhiều), kèm số ký tự quota ElevenLabs đã giảm.
  *(Nguồn gốc: người dùng yêu cầu lời dẫn giống người thật cho The Watchers, 2026-09-29.)*
8.5 **Trộn giọng:** `make-audio` tự hạ nhạc dưới giọng; mặc định nên để nhạc nghe rõ: `voiceOver` ~6, `duckHi` ~−5 dB, `clear` 10 (giọng hơn nhạc trung vị ~20 dB, 90% khung lời ≥ 10 dB trong dải 300–5000 Hz). Nâng mức nhạc tuyệt đối không đổi được tỉ lệ này: phải chỉnh các tham số trên. `voiceOver` tính so với nhạc **đã hạ** (`duckHi`), nên tăng `voiceOver` và hạ `duckHi` cùng một lượng thì triệt tiêu nhau; muốn giọng nổi hơn thì tăng `voiceOver`/`clear` (Điểm tin 13.10 tập 3: `voiceOver` 12, `duckHi` −7, `clear` 13 → trung vị 19,9 dB, 92 % ≥ 10 dB). Hiệu ứng mạnh (sấm, nổ) đặt vào khoảng lặng giữa hai câu thì giữ nguyên lực.

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
   - LUFS và peak đạt (`qa.mjs` có thể báo true peak NaN: đo lại bằng `ffmpeg -af ebur128=peak=true`);
   - bảng ghép lấy từ **chính file MP4**;
   - đo thêm độ to riêng một đoạn clip, một đoạn lời dẫn, cảnh tựa: chênh nhau ≤ ~2 LU;
   - có đoạn đen thì trích khung tại đó xem là đen thật hay cảnh tối, tìm nguyên nhân gốc (vd. mục 5.11).
5. So từng phụ đề trích với transcript (python).
6. Có lời dẫn:
   - cho whisper nghe lại file cuối **theo đoạn ≤ 4 phút**: đủ mọi câu (lời dẫn + clip), không sót đoạn ≥ 4 chữ;
   - bật `vad_filter=True`: whisper large-v3 không có VAD từng bỏ qua cả đoạn lời có nhạc nền (báo thiếu giả). Chỗ báo thiếu thì nghe riêng đoạn ngắn đó bằng một model khác, và đo năng lượng stem giọng trước khi kết luận là mất giọng *(Điểm tin 13.10.2026: menu 8–37 s)*;
   - giọng hơn nhạc ≥ 10 LU khi đang nói, trong dải 300–5000 Hz (đo `out/stem_voice.wav` với `out/stem_score.wav`).
7. Có hiệu ứng lửa/khói: trích 5–6 khung rải đều từ **chính file MP4** để chắc hiệu ứng có mặt ở mọi khung và nằm trong khung nhìn.
8. Báo cáo đúng sự thật. Chưa kiểm được thì nói là chưa kiểm (ví dụ: Claude không nghe được giọng, chỉ đo được).

## 10. Giao tiếp với người dùng

- Trả lời bằng tiếng Việt, ngắn gọn, đi thẳng vào việc. Người dùng xưng "tao/mày".
- Mỗi lượt kết thúc bằng:
  - làm gì, file nào;
  - bằng chứng đã kiểm (con số, ảnh);
  - tiền nguyên liệu đã tiêu, USD (lượt này và cả dự án: `gen.py cost`);
  - giới hạn còn lại (nói thật);
  - việc người dùng cần làm ở cổng duyệt (chọn ứng viên, duyệt footage, bấm Duyệt), hoặc câu hỏi nếu cần người dùng quyết.
- Lỗi phát hiện ra thì nhận là lỗi, giải thích nguyên nhân gốc, sửa tận gốc (trong engine của phim hoặc quy tắc) chứ không vá riêng một chỗ.
- Quyết định thuộc về người dùng (phong cách, tiêu tiền lớn, chủ đề nhạy cảm) thì hỏi. Việc kỹ thuật có mặc định rõ ràng thì tự làm.
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
 "voice": {"name": "George", "voice_id": "...", "model": "eleven_v4", "chars": 2400, "est_usd": 0.19},
 "risks": ["..."], "open_questions": ["..."]}
```

`1_script/blueprint.json`: bản thiết kế dự án (mục 2.1 bước 8). `visuals` dùng các loại: `clip | document | real_photo | reconstruction | map | board | archive | logo | years | footage | text`.
```json
{"approach": "2–4 câu: định làm phim thế nào", "spine": "xương sống một câu", "hook": "mở bằng gì", "ending": "khép bằng gì",
 "options": [{"name": "Đường hang thỏ", "idea": "...", "chosen": true, "why": "..."}],
 "acts": [{"id": "A1", "purpose": "vai trò trong mạch", "question": "câu hỏi hồi mở ra", "turn": "điều biết thêm khi hết hồi",
   "bridge": "ý chuyển sang hồi sau", "est_sec": 45, "visuals": ["clip", "document"],
   "characters": ["c_rogan"], "locations": ["l_hawara"], "evidence": ["E01"], "notes": "..."}],
 "assets": {"characters": [{"id": "c_rogan", "name": "Joe Rogan", "role": "main", "how": "real_photo|clip|ai|voice_only"}],
            "locations": [{"id": "l_hawara", "name": "...", "how": "real_photo|ai|map"}]},
 "tree": {"acts": {"A1": {"why": "vì sao hồi này đứng ở đây", "how": "triển khai bằng cách nào"}},
          "beats": {"b01": {"point": "ý chính một câu", "why": "vì sao viết đúng như thế", "how": "kỹ thuật kể, hình, bằng chứng, nhịp",
                            "ideas": ["ý con 1", "ý con 2"]}}},
 "build": [{"step": "cast|scenes|images|footage|render|metadata", "will": "làm gì cho phim này", "count": 12, "usd": 0.4}],
 "budget": {"voice_usd": 1.1, "images_usd": 2.0, "sfx_usd": 1.0, "footage_usd": 0, "total_usd": 4.1},
 "open_decisions": ["điều người dùng nên quyết ở cổng duyệt"]}
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
   "candidates": [{"file": "2_cast/casting/c_azazel_1.png", "model": "bytedance/seedream/v5/flash/text-to-image", "request_id": "...", "usd": 0.027, "note": "..."}]}]}
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
   "base": "azazel", "model": "id model fal hoặc alias (gpt-edit, nano-pro…)", "quality": "high|medium",
   "aspect": "1:1", "prompt": "...", "est_usd": 0.15}],
 "footage_needs": [{"id": "fx_fire_1", "type": "stock_fx|archival|interview_clip|voice|music|sfx",
   "desc": "...", "scenes": ["sc05"]}],
 "budget": {"est_usd": 4.2, "budget_usd": 5}}
```

Cảnh liền khối (pipeline `fullframe`, mục 4.9): asset `{"key": "sc05", "kind": "frame", "refs": ["film/assets/raw/c_noah.png"], "model": "openai", "quality": "high", "aspect": "3:2", "prompt": "...", "est_usd": 0.05}`; cảnh thêm `"frame": "film/assets/frames/sc05.png"` và `"parallax": {"move": "orbit-right", "subject": [0.62, 0.55], "strength": 1.0}`. Manifest bước 4 ghi `kind: "frame"`, `file` = ảnh frame, `cutout: false`.

Mỗi cảnh thêm (mục 5.13): `"transition": "dissolve|cut|dip|flash|leak|whip|zoom|wipe|iris|blinds|glitch"` (cách cảnh đó **vào**), `"look": {"grade": "none|teal-orange|bleach|warm|cold|archive|noir|duotone", "feel": ["handheld", "impact@92", "leak", "flare@0.54,0.60", "chroma", "archive"]}` (`@` = khung trong cảnh / toạ độ nguồn sáng), `"text_fx": [{"kind": "MaskTitle|ChapterCard|LowerThird|Typewriter|Scramble|CountUp|PunchWords|PullQuote|Highlight", "text": "...", "at": 1.5, "dur": 4}]`. `scenes.md` có cột «Chuyển cảnh · màu · chữ động».

Phim hồ sơ (pipeline `dossier`, mục 4.11): thêm danh sách bằng chứng và mỗi cảnh hồ sơ một `shot` (dữ liệu của `<DossierScene>`; mốc `at` viết theo lời dẫn):
```json
{"evidence": [{"id": "E05", "type": "photo|page|logo|archival_video|map", "proves": "Bernhard founded Bilderberg",
   "source_url": "https://en.wikipedia.org/wiki/Bilderberg_meeting", "license": "CC BY-SA 4.0 (screenshot)",
   "marks": ["Prince Bernhard of the Netherlands"], "file": "film/public/docs/E05.png"}],
 "scenes": [{"id": "sc07", "beats": ["b07"], "duration_sec": 9, "evidence": ["E05"], "transition": "blinds",
   "shot": {"kind": "doc", "tone": "paper", "page": {"src": "docs/E05.png", "aspect": 0.7857,
     "marks": [{"boxes": [[0.1952, 0.2731, 0.228, 0.0121]], "at": "l12:Prince Bernhard"}],
     "notes": [{"text": "the founder", "at": "l12:founder", "x": 0.47, "y": 0.31, "to": [0.33, 0.288]}]}}},
  {"id": "sc08", "duration_sec": 6, "evidence": ["E06"],
   "shot": {"kind": "photos", "cards": [{"src": "evidence/E06.jpg", "aspect": 0.8, "x": 0.5, "y": 0.47, "w": 0.3,
     "at": "l13", "reveal": "l13:Prince", "label": "Prince Bernhard", "stamp": {"text": "Verified", "at": "l13:confirmed", "ink": "green"}}]}}]}
```
Các kiểu khác: `{"kind": "board", "cards": [{"id": "a", …}], "links": [{"a": "a", "b": "b", "at": "l20:four", "label": "4 shared members"}]}`, `{"kind": "archive", "clip": {"src": "evidence/E09.mp4", "gate": "film|tv", "color": false}}`, `{"kind": "logo", "logo": {"src": "evidence/cfr.png", "aspect": 1.6, "title": "Council on Foreign Relations", "sub": "1921 · New York", "ghosts": ["Bilderberg", "1001 Club"]}}`, `{"kind": "years", "years": [{"label": "1954", "at": "l30:1954"}], "card": {"src": "…", "aspect": 0.8}}`. Cảnh tái hiện trong phim hồ sơ giữ khối `layers`/`camera` của mục 4.10 và `"reconstruction": true`.

### 11.4 Bước 4: `4_images/manifest.json`
```json
{"assets": [{"key": "azazel_point", "kind": "character|variant|plate|prop|additive", "status": "done|failed|redo|pending",
   "model": "openai/gpt-image-2.5/sunburst/edit", "request_id": "...", "usd": 0.21,
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
 "voice": {"voice": "George", "takes": [{"file": "film/audio/voice/take1.mp3", "usd": 0.19, "chosen": true}],
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

### 11.7 `notes/costs.json` (gen.py ghi, chỉ đọc)
```json
{"total_usd": 1.84, "budget_usd": 5,
 "events": [{"at": "2026-10-03T15:10:00", "step": "images", "kind": "image|video|tts|sfx|fal", "provider": "fal|elevenlabs",
   "model": "fal-ai/nano-banana-pro/edit", "what": "azazel_point", "usd": 0.15, "estimated": true,
   "files": ["film/assets/raw/azazel_point.png"], "request_id": "..."}]}
```

### 11.8 Bước 7: `7_metadata/metadata.json`
```json
{"title": "...", "title_options": [{"title": "...", "why": "..."}],
 "keywords": [{"term": "book of enoch", "role": "main|secondary", "evidence": "gợi ý tìm kiếm YouTube"}],
 "description": "dòng 1\ndòng 2\n...\n0:00 ...\n1:12 ...", "chapters": [{"time": "0:00", "title": "..."}],
 "tags": ["book of enoch", "nephilim"], "hashtags": ["#BookOfEnoch"], "category": "Education", "language": "en",
 "made_for_kids": false, "altered_content": true, "captions": "7_metadata/captions.srt",
 "thumbnails": [{"file": "7_metadata/thumbs/thumb_a.jpg", "text": "THE BANNED BOOK", "chosen": true, "why": "..."}],
 "visibility": "schedule|private|unlisted|public", "publish_at": "2026-10-16T13:00:00-04:00",
 "video": "out/<slug>_v<N>.mp4", "notes": "..."}
```
`7_metadata/upload.json` (app ghi khi đăng, chỉ đọc): trạng thái, link video, giờ lên lịch, nhật ký.

## 12. Nhật ký quy tắc (cập nhật mỗi khi người dùng sửa)

Cách cập nhật: sửa đúng mục liên quan ở trên (ngắn gọn, có lý do), rồi thêm một dòng vào đây theo dạng `YYYY-MM-DD · dự án · thay đổi`. Muốn **xóa** quy tắc thì phải hỏi người dùng. Chỉ ghi quy tắc cho phim tài liệu; điều chỉ đúng với video tin tức thuộc bộ quy tắc tin tức.

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
- 2026-10-06 · Creater Vid · Bỏ Higgsfield: giọng đọc gọi thẳng API ElevenLabs, ảnh và video gọi thẳng API fal.ai, đều qua `gen.py` (key ở trang Cài đặt); chi phí tính bằng USD trong `notes/costs.json`, ngân sách `budget_usd`, gen.py chặn khi vượt; giọng đọc theo ngôn ngữ video → mục 0, 2, 3, 8.4, 10, 11.
- 2026-10-06 · Creater Vid · Thêm lựa chọn tạo ảnh gọi thẳng OpenAI (GPT Image) và Google Gemini (Nano Banana) bằng key riêng, bên cạnh fal → mục 3.
- 2026-10-08 · The Book of Enoch · Rút từ lỗi tự soát ở bước 6: không bật bloom ở cảnh có vệt sao `Streak` (NaN → khung đen); chuẩn hoá tiếng clip phỏng vấn về mức lời dẫn trước khi trộn và đo riêng trên MP4 → mục 5.11, 8.2.
- 2026-10-08 · The Book of Enoch · Người dùng yêu cầu dùng ElevenLabs để trau chuốt âm thanh: nhạc nền, nền không khí, hiệu ứng tạo bằng `gen.py sfx`, tự tổng hợp thành dự phòng → mục 1.8, 8.1.
- 2026-10-08 · The Book of Enoch · Người dùng chọn: tắt nhạc trong trích đoạn podcast, nhạc nền nhỏ đúng vibe dưới lời dẫn (rõ hơn bản mặc định) → mục 8.2, 8.5.
- 2026-10-08 · The Book of Enoch · Người dùng yêu cầu ghi mọi sửa đổi của dự án thành quy tắc: kiểm từng ý khách mời và cách cắt clip (1.6); lưu văn bản nguồn, agent song song (2.1); ngoại hình bám văn bản (2.2); dựng theo dữ liệu, footage chưa duyệt, chỉ sửa tiếng thì ghép lại không render (2.6); giá thật OpenAI, không dùng mini cho đạo cụ tách nền, nền không khói, kiến trúc văn hoá (3); limiter 4×, trộn lại tiếng clip sau render (8.3); văn bản đọc theo beat, plan theo chỗ ngắt, phụ đề từ mốc chữ, whisper theo đoạn, đặt lại thời lượng cảnh theo giọng (8.4); QA đo theo đoạn, true peak NaN (9).
- 2026-10-08 · Creater Vid · Thêm cách dựng hình **ảnh liền khối → 3D** (tuỳ chọn mỗi dự án, `pipeline: fullframe`): mỗi cảnh một ảnh hoàn chỉnh có nhân vật (ref ảnh gốc), thành clip camera 3D bằng parallax.py trên GPU; thêm **bước 7 · Metadata YouTube** (từ khóa, tiêu đề, mô tả có chương, thẻ, phụ đề, thumbnail) → mục 2, 2.8, 4.9, 11.3, 11.8.
- 2026-10-08 · The Book of Enoch (ảnh liền khối 3D) · Rút từ lỗi tự soát ở bước 4: giữ `subject` gần tâm (x 0,42–0,58), giảm `strength` cho nhân vật sát mép; không gắn ref cho nhân vật nhỏ ở xa → mục 4.9.
- 2026-10-08 · The Book of Enoch (ảnh liền khối 3D) · Bước 6: phim có letterbox thì render clip parallax ở dải nhìn thấy 1920×880; `subject` x = 0,5, y theo đỉnh đầu → mục 4.9.
- 2026-10-09 · Creater Vid · Thêm cách dựng hình thứ ba **xếp lớp** (`pipeline: stacked`): mỗi cảnh chia 2–4 lớp theo độ sâu, GPT vẽ riêng từng lớp (layerkit.py), engine xếp lớp + camera điện ảnh (LayerScene); hiệu ứng code chỉ là đề xuất chờ duyệt → mục 2, 4.10.
- 2026-10-10 · The Rich Used to Eat Egyptian Mummies (xếp lớp) · Rút từ lỗi tự soát ở bước 6: kích thước lớp của LayerScene là ước lượng, 11 cảnh lộ mép thẻ → kiểm hình học từng khung trước render; greykey sót nền kín và quầng đèn; thẻ tên đúng người đang lên hình; dòng phụ đề clip ≥ 0,8 s → mục 4.10, 7.4.
- 2026-10-12 · Is the Book of Enoch the Oldest Story Ever Told? (xếp lớp) · Rút từ lỗi tự soát ở bước 4: câu `light` không nhắc người/vật (lọt vào mọi lớp); cách giữ đầu nhân vật trong dải chiếu → mục 4.10.
- 2026-10-12 · Is the Book of Enoch the Oldest Story Ever Told? (xếp lớp) · Rút từ lỗi tự soát ở bước 6: `voice-build` gộp hai đoạn đọc liền (câu cuối phát sang cảnh sau) → cắt ở quãng lặng dài nhất giữa hai dòng; phụ đề lời dẫn chìm trên tranh sáng → dải tối mờ dưới phụ đề; phụ đề clip từ mốc chữ của file clip, thẻ tên từng người khi máy quay đổi người; nhãn nguồn lệch cảnh ở bước 3 → mục 2.6, 7.2, 7.4, 8.4.
- 2026-10-13 · Điểm tin 24h 13.10.2026 (dự án tin, khi hai mảng còn chung bộ quy tắc) · Phần dùng chung engine: clip ngắn hơn cảnh → giãn tốc độ, soát khung cuối; whisper kiểm phim cuối bật VAD và kiểm chéo chỗ báo thiếu → mục 2.6, 9.6.
- 2026-10-13 · Điểm tin 24h 13.10.2026 tập 3 (dự án tin, khi hai mảng còn chung bộ quy tắc) · Phần dùng chung công cụ: xem trước nội dung footage trước khi đề xuất; cắt giọng ở quãng lặng quanh cả hai mốc chữ, cắt giữa khi đọc liền, whisper từng file dòng; clip có tiếng giữ khung đầu/cuối; `voiceOver` và `duckHi` triệt tiêu nhau → mục 2.5, 2.6, 8.4, 8.5.
- 2026-10-13 · Điểm tin 24h 13.10.2026 tập 3 (dự án tin, khi hai mảng còn chung bộ quy tắc) · Phần dùng chung của metadata: YouTube đếm ngoặc kép trong thẻ; khung phụ đề dài tách theo mốc chữ → mục 2.8.
- 2026-10-14 · Giáo phái tổng hợp · Rút từ bước 1: `hldb search` chỉ tìm trong highlight, phải quét thêm transcript cả tập để gom đủ một chủ đề; tập thiếu video gốc thì cắt từ file highlight → mục 1.6.
- 2026-10-14 · Giáo phái tổng hợp · Rút từ lỗi tự soát ở bước 4: đo độ đặc lớp cắt để bắt lớp GPT vẽ kín khung; không vẽ cùng vật ở hai lớp; bản trống/bản có người bằng sửa far + cutout → mục 4.10.
- 2026-10-14 · Giáo phái tổng hợp · Rút từ lỗi tự soát ở bước 5: mốc chữ ElevenLabs trễ tới 0,9 s ở đầu đoạn làm mất chữ đầu dòng → lấy start theo whisper cho chữ khớp, giữ số chữ theo alignment → mục 8.4.
- 2026-10-14 · Creater Vid · Người dùng yêu cầu tách hẳn hai mảng: phim tài liệu và video tin tức là hai dạng khác nhau, mỗi dạng một bộ quy tắc riêng, không áp chung. Bộ này giữ phần phim tài liệu của bộ chung (v25 + quy tắc 8.4 vừa thêm của Giáo phái tổng hợp); chuyển sang bộ quy tắc tin tức: mục 1.11–1.13 (ảnh, video từ tin; trích nguồn tin; ảnh thật trước), 2.9 (Điểm tin 24h), bước 5 «nguyên liệu từ tin» và các dòng nhật ký chỉ về tin → mục 1, 2.5, 2.9 cũ, 12.
- 2026-10-14 · Creater Vid · Người dùng yêu cầu tự đăng YouTube qua profile GPM Login: metadata thêm `publish_at`, `visibility`, `category` đúng tên trong Studio, thumbnail `chosen`; app (không phải Claude) đăng → mục 2.8, 11.8.
- 2026-10-14 · Creater Vid · Người dùng yêu cầu: thời lượng chọn khi tạo dự án là **mức tối thiểu** (VD 1200 s = từ 1200 s trở lên), kịch bản tối ưu cho hay nhất, không bắt buộc gói gọn → mục 2.1.
- 2026-10-14 · Giáo phái tổng hợp · Rút từ lỗi tự soát ở bước 6: 12 lớp còn nền xám kín/"cây ma"/mảng sàn vẽ kèm → quét vùng phẳng bằng máy; tiền cảnh dâng che kín khung khi `crane-down` → đo độ che của lớp gần; ghép hai lượt nghe phụ đề clip bằng transcript, dấu câu tay có kiểm từng chữ; không ngắt phụ đề lời dẫn sau chữ viết tắt, dòng không tắt trước chữ cuối → mục 4.10, 7.2, 7.4.
- 2026-10-14 · Giáo phái tổng hợp · Render nền bị bỏ lại khi lượt kết thúc → render theo đoạn, tuần tự trong lượt, không kết thúc lượt khi còn lệnh nền → mục 2.6, 4.9.
- 2026-10-20 · Pyramids Under the Ice · Người dùng thấy phim đơn điệu (86 cảnh cùng một kiểu mờ chéo, chữ chỉ có phụ đề), muốn hiệu ứng chuyên nghiệp, nghệ thuật và để Claude tự chọn → bộ Motion kit trong engine (`src/kit`, ENGINE.md "Motion kit"), mục 5.13, 7.5, 2.3 bước 6, 2.6, 4.10, 11.3.
- 2026-11-03 · Creater Vid · Thêm cách dựng hình thứ tư **hồ sơ tư liệu thật** (`pipeline: dossier`), rút từ hai video kênh Moon: khung kể hồ sơ vụ việc / đường hang thỏ, mỗi danh từ riêng một bằng chứng thật, ảnh in và trang tài liệu dựng 2.5D trên bàn, highlight và dấu đồng bộ theo chữ lời dẫn (engine `src/dossier`, `scripts/pagecap.mjs`); duyệt bước 3 = duyệt tải bằng chứng; AI chỉ tái hiện cảnh không có ảnh → mục 2, 2.1, 4.11, 11.3.
- 2026-11-04 · Creater Vid · Bước 1 lập thêm **bản thiết kế dự án** `blueprint.json` (cách làm, xương sống, từng hồi, kho nguyên liệu dự kiến, kế hoạch các bước, ngân sách); app vẽ thành trang 🧭 Sơ đồ dự án để duyệt trước khi làm → mục 2.1, 11.1.
- 2026-11-04 · Creater Vid · `blueprint.json` thêm **cây nội dung** (`tree`: mỗi hồi why/how, mỗi beat point/why/how/ideas); app vẽ thành sơ đồ cây luận đề → hồi → beat → ý con để duyệt nội dung kịch bản → mục 2.1 bước 8, 11.1.
