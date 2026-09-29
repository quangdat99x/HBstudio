# BỘ QUY TẮC DỰNG PHIM TÀI LIỆU · JRE Studio

> Mọi lượt làm việc trên tab **Make Documentary Film** phải tuân theo bộ quy tắc này.
> Thứ tự ưu tiên: yêu cầu của người dùng trong chat > bộ quy tắc này > thói quen mặc định.
> Người dùng yêu cầu điều trái quy tắc thì vẫn làm theo người dùng, kèm một dòng ⚠️ nêu rõ quy tắc nào bị phá và rủi ro.
> Quy tắc được viết ra từ những lần người dùng sửa phim. Mỗi lần người dùng sửa hay góp ý, cập nhật vào đây (mục 12).

---

## 0. Phim của chúng ta là gì

- Phim tài liệu cho kênh YouTube khán giả Mỹ (chữ trên phim bằng tiếng Anh). Ghi chú nội bộ và trả lời người dùng bằng tiếng Việt.
- **Xương sống luận điểm = các đoạn trích đắt giá từ kho highlight JRE** về chủ đề đó. Lời dẫn chỉ nối và đặt bối cảnh.
- Hình ảnh: nhân vật và bối cảnh do Higgsfield vẽ (ảnh AI tách lớp). Claude dựng chuyển động, không gian 3D nhiều lớp, hiệu ứng, chữ và âm thanh bằng code (engine trong `film/`, cẩm nang `film/ENGINE.md`).
- Phim mẫu tham chiếu: `D:\VideoLab\watchers-v2` (The Watchers v2.1, Book of Enoch 6–10, 30 s).

## 1. Tính xác thực (phim tài liệu)

1.1 Chỉ trình bày như **tư liệu** những gì có nguồn kiểm chứng được. Trích dẫn cổ văn phải lấy từ một bản dịch có tên, ưu tiên bản thuộc phạm vi công cộng (ví dụ R.H. Charles 1917 cho 1 Enoch), và ghi chương:câu. Không bịa câu trích. Câu diễn ý (paraphrase) không được đặt trong ngoặc kép như nguyên văn.
1.2 Hình ảnh, biểu tượng hay chi tiết **không có trong nguồn** là *tái hiện nghệ thuật*. Không trình bày chúng như tư liệu gốc. Ưu tiên hình ảnh bám văn bản (ví dụ: lời thề "trói buộc lẫn nhau" = sợi sáng nối tay các Watcher với nhau; tên núi Hermon ↔ *ḥērem* theo 1 Enoch 6:6). Nếu vẫn dùng chi tiết tự tạo thì ghi chú nhỏ "artistic reconstruction". *(Nguồn gốc: vụ vòng ấn lời thề, 2026-09-29.)*
1.3 **Kiểm tra niên đại và nguồn gốc** của mọi biểu tượng, trang phục, vật dụng trước khi đưa vào phim. Ví dụ: sao 6 cánh chỉ thành biểu tượng Do Thái từ thế kỷ 17 (Prague), không có trong 1 Enoch (thế kỷ 3–1 TCN). Nếu đưa vào là sai niên đại.
1.4 **Không trộn nguồn.** Ví dụ: Sách Enoch (1 Enoch, cổ đại) ≠ "Enochian" của John Dee (ma thuật thế kỷ 16). Khi một khái niệm "nghe quen trên mạng", truy ra nguồn gốc trước khi dùng.
1.5 Người dùng đưa tiền đề có vẻ sai thì **kiểm chứng bằng WebSearch/WebFetch**, trình bày bằng chứng kèm link nguồn, đề xuất phương án đúng rồi để người dùng quyết. Không im lặng làm theo, cũng không tự ý bác bỏ.
1.6 **Trích đoạn JRE:**
  - chữ trên màn hình phải đúng nguyên văn transcript;
  - clip cắt đúng lời, không ghép làm sai ý người nói;
  - luôn ghi tên người nói và số tập;
  - lời khẳng định của khách mời là *ý kiến của họ*, không trình bày như sự thật đã kiểm chứng. Nếu là tuyên bố gây tranh cãi, lời dẫn đặt bối cảnh hoặc nêu phản biện có nguồn.
  - **Luận đề, lời dẫn và tựa phim không được khẳng định tuyên bố gây tranh cãi như sự thật.** Đặt thành câu hỏi hoặc ghi rõ ai tuyên bố:
    - viết "A pilot claims he flew a 10-foot body out of Kandahar. Who took it?";
    - không viết "Giants existed and the evidence is being suppressed".

    Sức hút đến từ bí ẩn và lời chứng, không phải từ việc phim tự đứng ra khẳng định.
1.7 **Biểu tượng nhạy cảm:** không gắn biểu tượng của tôn giáo, dân tộc hay cộng đồng có thật (Ngôi sao David, thánh giá, trăng lưỡi liềm, chữ Vạn...) cho phe ác hay ma quỷ. Tránh cả ký hiệu sáo mòn kiểu phim kinh dị (ngôi sao năm cánh ngược). Khi cần một ký hiệu huyền bí, dùng hình học trung tính hoặc chữ viết lấy từ chính nguồn (vòng rune, vòng chữ, sao 7 cánh {7/3}).
1.8 Bản quyền: bản dịch cổ văn dùng bản công cộng hoặc trích rất ngắn. Nhạc và hiệu ứng âm thanh tự tổng hợp (không tải nhạc về). Chỉ dùng footage JRE từ kho của chính kênh, dạng trích đoạn ngắn có bình luận và dựng lại.

## 2. Quy trình một dự án (workflow)

Mỗi dự án có thư mục riêng:
- `research/`: pool và transcripts do Studio tạo; `selection.*` do Claude viết.
- `script/`: kịch bản.
- `film/`: engine Remotion.
- `out/`: các bản render.
- `notes/`: ghi chú, nhật ký credit.

Bốn bước dưới đây nối tiếp nhau. Người dùng có thể nhắn chat bất kỳ lúc nào để chỉnh.

### 2.1 Bước 1: Tìm đoạn đắt giá (research)

- **Đầu vào:**
  - `research/pool.json` + `pool.md`: ứng viên từ kho, xếp theo độ khớp chủ đề và điểm chất lượng;
  - `research/transcripts/<segment_id>.txt`: transcript từng đoạn, timestamp tính theo tập gốc.
- **Tìm thêm khi cần:**
  - `python -X utf8 E:\DataBase\hldb.py search "<từ khóa>" --json`
  - `python -X utf8 E:\DataBase\hldb.py show <id> --json`
- **Tiêu chí chọn:** khớp đúng chủ đề; `final_score` và `intensity` cao; câu nói **đứng một mình vẫn hiểu** (không cần ngữ cảnh trước đó); đa dạng khách mời và góc nhìn; mỗi trích 8–40 giây; có cảm xúc hoặc chi tiết cụ thể (tên, số, địa điểm).
- **Kiểm tra:** mỗi câu trích phải khớp **nguyên văn** với transcript. Dùng python để so chuỗi.
- **Đầu ra:**
  - `research/selection.json` (lược đồ ở mục 11.1);
  - `research/selection.md`: bản đọc cho người dùng, gồm luận đề, dàn ý, danh sách trích kèm lý do, tuyên bố cần kiểm chứng, câu hỏi mở.
- **Kết thúc:** tóm tắt bằng tiếng Việt và đề xuất 2–3 hướng dàn ý để người dùng chọn.

### 2.2 Bước 2: Kịch bản

- **Cấu trúc mặc định:**
  1. Cold open: câu trích mạnh nhất, ≤ 15 giây.
  2. Tựa phim.
  3. 3–5 hồi. Mỗi hồi có lời dẫn bắc cầu, 1–2 trích JRE và cảnh tái hiện.
  4. Kết (điều còn bỏ ngỏ hoặc câu trích khép lại).
- **Độ dài:** theo `target_sec` của dự án. Tỉ lệ gợi ý: 45–60% thời lượng là trích JRE, phần còn lại là tái hiện và lời dẫn.
- **Lời dẫn:**
  - câu ngắn, giọng tài liệu điềm tĩnh;
  - mỗi phụ đề ≤ 2 dòng (≈ 16 từ), đủ thời gian đọc: ≥ 0,35 s/từ + 1 s;
  - mọi khẳng định sự thật trong lời dẫn phải có nguồn trong `sources`.
- **Hình ảnh mỗi cảnh:** liệt kê các lớp (trời, xa, trung, nhân vật, tiền cảnh, hiệu ứng) và chuyển động máy quay. Chỉ ghi chi tiết có trong nguồn hoặc đánh dấu là tái hiện nghệ thuật.
- **Danh sách tài sản:** prompt cho từng ảnh Higgsfield và ước tính credit (mục 3).
- **Đầu ra:** `script/script.json` (mục 11.2) và `script/script.md` (bản đọc).
- **Cổng duyệt:** chưa có lời "duyệt" của người dùng thì **chưa tiêu credit Higgsfield và chưa dựng**. Người dùng đã nói "làm luôn" thì bỏ qua cổng này.

### 2.3 Bước 3: Dựng phim

1. Đọc `film/ENGINE.md`, xem các cảnh mẫu trong `D:\VideoLab\watchers-v2\src\scenes\`. `film/node_modules` là liên kết tới engine dùng chung: không `npm install`, **không bao giờ xóa** nó hay thứ gì bên trong.
2. Kiểm tra số dư Higgsfield (`balance`), ghi `notes/credits.json` trước và sau.
3. Tạo tài sản theo mục 3, lưu vào `film/public/img/`. Đo landmark theo mục 6.
4. Cắt clip trích bằng `node scripts/clip.mjs`, đặt vào `film/public/clips/`. Viết phụ đề nguyên văn theo từng dòng transcript.
5. Viết `src/timeline.js`, `src/assets.ts`, các cảnh và `Film.tsx`.
6. Soát ảnh tĩnh (mục 9), sửa, rồi làm âm thanh (mục 8).
7. Render `out/<slug>_v<N>.mp4`. **Không ghi đè bản cũ**, mỗi lần render tăng N.
8. Chạy QA (mục 9) và báo cáo.

### 2.4 Bước 4: Sửa theo góp ý

Mỗi góp ý: sửa, soát lại đúng chỗ đã sửa (ảnh tĩnh hoặc cắt cận), render bản mới, báo cáo đã sửa gì và bằng chứng nào cho thấy đã sửa đúng. Góp ý nào mang tính nguyên tắc thì **ghi thành quy tắc** (mục 12).

## 3. Ảnh AI với Higgsfield

- **Công cụ (headless):**
  - `mcp__claude_ai_HF__balance`, `generate_image`, `generate_image_batch`, `jobs_wait`, `remove_background`, `models_explore`, `create_project`.
  - Mỗi phim một project Higgsfield. Mọi lần tạo ảnh dùng `folder_id` của project đó.
- **Chi phí đo thực tế (2026-09):**

  | Việc | Model | Credit |
  |---|---|---|
  | Ảnh 2k | `soul_cinematic` | 0,12 |
  | Ảnh | `nano_banana_pro` | 2 |
  | Tách nền | `remove_background` | ≈ 1 |
  | Video 5 s | `kling3_0` | 8,75 |
  | Video 5 s | `seedance_2_5` | 35 |

  Trần credit mỗi dự án: xem "ngân sách credit" trong phần mô tả dự án. Sắp vượt thì dừng và hỏi.
- **Model theo việc:**
  - Cảnh nền, đạo cụ, nhân vật gốc: `soul_cinematic` (2k; cảnh nền 21:9, nhân vật 1:1).
  - **Biến thể nhân vật** (đổi tư thế, trang phục, nhân vật cùng phong cách): `nano_banana_pro`, sửa từ ảnh gốc: "Edit this image. Keep the same ... Only change ...". Soul Cinema kèm ảnh tham chiếu sẽ chép gần như y nguyên ảnh gốc, nên không dùng cho việc này.
- **Cách tạo từng loại:**
  - Nhân vật/đạo cụ cần tách: toàn thân, ở giữa, chừa lề, **nền xám trơn phẳng**, không mặt đất, không chữ. Sau đó `remove_background`.
  - Sương, lửa, ánh sáng, lông vũ: vẽ **trên nền đen tuyền** rồi dùng `blend="add"`, không tách nền. Tách nền để lại viền đen trên vật trắng mềm.
  - Cảnh nền (plate): không nhân vật, không chữ. Chừa khoảng cho chủ thể đứng.
- **Một chuỗi phong cách cho cả phim**, gắn vào cuối mọi prompt. Ví dụ: *dark biblical fantasy concept art, painterly oil painting with visible brushwork, cinematic lighting, ... in the spirit of Gustave Dore and modern film concept art*.
- **Tính đồng nhất:** mỗi nhân vật có một ảnh gốc. Mọi biến thể đều sửa từ ảnh gốc đó.
- **Lỗi ngẫu nhiên:** khoảng 1/5 job `soul_cinematic` báo `failed`, cứ tạo lại. Khi bị timeout thì không tự gửi lại, xem job cũ trước.
- **Tải về:** tải `result_url` vào `film/public/img/`, đặt tên có nghĩa. Xem lại bằng một bảng ghép (contact sheet) trước khi dùng.
- **Video AI** (Kling) chỉ dùng cho khoảnh khắc "diễn" đắt nhất mà biến dạng lưới không làm được, và phải hỏi người dùng trước.

## 4. Không gian 3D nhiều lớp

4.1 Mọi cảnh là một sân khấu 3D (multiplane): mỗi lớp là một tấm phẳng ở **độ sâu thật**. Máy quay phải **di chuyển thật** (tiến vào, lia ngang, vòng quanh), không chỉ phóng to. *(Người dùng muốn "không gian đa chiều".)*
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

## 5. Chuyển động

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
7.4 Khi clip JRE đang phát: góc trên có tên người nói và nguồn, phụ đề là transcript nguyên văn theo từng dòng thời gian.

## 8. Âm thanh

8.1 Nhạc và hiệu ứng tự tổng hợp bằng `scripts/audio-lib.mjs` (drone, gió, boom, sấm, kim loại, xích, whoosh...). Mọi cue lấy từ `src/timeline.js`, nên hình và tiếng luôn khớp.
8.2 Clip JRE giữ tiếng gốc. Nhạc nền **hạ ~12 dB** dưới mọi trích đoạn (danh sách `QUOTES`).
8.3 **Master:** loudnorm về −16 LUFS ở soundtrack. File cuối phải ở khoảng −14,5 LUFS, true peak ≤ −1,5 dBFS. *(Bản đầu tiên ở −20,6 LUFS, nghe nhỏ hơn video khác trên YouTube.)*
8.4 Giọng đọc (ElevenLabs) tiêu credit của người dùng, nên phải hỏi trước. Mặc định dùng lời dẫn bằng chữ.

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
6. Báo cáo đúng sự thật. Chưa kiểm được thì nói là chưa kiểm.

## 10. Giao tiếp với người dùng

- Trả lời bằng tiếng Việt, ngắn gọn, đi thẳng vào việc. Người dùng xưng "tao/mày".
- Mỗi lượt kết thúc bằng:
  - làm gì, file nào;
  - bằng chứng đã kiểm (con số, ảnh);
  - credit Higgsfield đã tiêu;
  - giới hạn còn lại (nói thật);
  - bước tiếp theo, hoặc câu hỏi nếu cần người dùng quyết.
- Lỗi phát hiện ra thì nhận là lỗi, giải thích nguyên nhân gốc, sửa tận gốc (trong engine hoặc quy tắc) chứ không vá riêng một chỗ.
- Quyết định thuộc về người dùng (phong cách, tiêu credit lớn, chủ đề nhạy cảm) thì hỏi. Việc kỹ thuật có mặc định rõ ràng thì tự làm.
- Chạy ở chế độ tự động (headless) thì không chờ người dùng giữa chừng: làm hết phần làm được, cuối lượt liệt kê câu hỏi.

## 11. Lược đồ file

### 11.1 `research/selection.json`
```json
{"topic": "...", "thesis": "luận đề một câu",
 "segments": [{"segment_id": 122, "episode_id": "JRE-2530", "guest": "...", "title": "...", "why": "...",
   "clip": "đường dẫn clip zoom", "segment_start_sec": 1200.0,
   "quotes": [{"start_sec": 1234.5, "end_sec": 1250.2, "text": "nguyên văn transcript", "role": "hook|evidence|claim|emotion|counterpoint"}]}],
 "outline": [{"act": 1, "idea": "...", "quotes": ["122:1234.5"]}],
 "claims_to_verify": ["..."], "open_questions": ["..."]}
```

### 11.2 `script/script.json`
```json
{"title": "...", "logline": "...", "format": "16:9", "target_sec": 180, "style": "chuỗi phong cách ảnh",
 "scenes": [{"id": "s01", "type": "cold_open|title|narration|quote|reconstruction|outro", "duration_sec": 12,
   "narration_en": "...", "on_screen_text": "...",
   "quote": {"segment_id": 122, "episode_id": "JRE-2530", "speaker": "...", "start_sec": 1234.5, "end_sec": 1250.2, "text": "nguyên văn"},
   "visual": {"layers": ["sky: ...", "mid: ...", "character: ...", "fg: ..."], "camera": "dolly in", "reconstruction": true},
   "sources": ["1 Enoch 6:6 (R.H. Charles 1917)"], "sfx": ["boom ở 3.2s"]}],
 "assets": [{"key": "sky_hermon", "kind": "plate|cutout|additive", "model": "soul_cinematic", "aspect": "21:9", "prompt": "...", "est_credits": 0.12}],
 "sources": [{"ref": "...", "url": "..."}], "risks": ["..."]}
```

## 12. Nhật ký quy tắc (cập nhật mỗi khi người dùng sửa)

Cách cập nhật: sửa đúng mục liên quan ở trên (ngắn gọn, có lý do), rồi thêm một dòng vào đây theo dạng `YYYY-MM-DD · dự án · thay đổi`. Muốn **xóa** quy tắc thì phải hỏi người dùng.

- 2026-09-29 · khởi tạo · Rút từ phim thử The Watchers:
  - v1 bị chê chuyển động cứng, nhân vật thô, không gian phẳng → mục 3, 4, 5;
  - v2 bị chê sao đáp lệch đỉnh núi và sợi sáng trượt khỏi tay → mục 6;
  - tranh luận sao 6 cánh và sao 7 cánh → mục 1.2–1.5, 1.7;
  - độ to âm thanh −20,6 LUFS → mục 8.3;
  - các lỗi tự soát (chữ lẻ rớt dòng, quầng sáng lộ viền, xích vàng biến mất trên cánh trắng, letterbox cắt đầu) → mục 4.4, 6.4, 7.2.
