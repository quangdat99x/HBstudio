# Creater Vid

Tool làm video với **hai mảng riêng biệt**, chọn ở hai tab trên cùng của app:

| Mảng | Dự án | Quy trình | Bộ quy tắc |
|---|---|---|---|
| 🎬 **Phim tài liệu** (`/doc`) | tạo ở trang Dự án của mảng | 7 bước (dưới đây) | `RULEBOOK.doc.md` |
| 📰 **Tin tức** (`/news`) | tạo từ tin theo dõi (hoặc tạo tay ở `/news/projects`) | 6 bước: kịch bản tin → bảng hình → hình thật → giọng đọc & âm thanh → dựng & render → metadata | `RULEBOOK.news.md` |

Mỗi mảng có danh sách dự án, quy trình (`creater/workflow.py` → `FLOWS`) và bộ quy tắc (lịch sử phiên bản riêng) của riêng nó: một lượt Claude chỉ nhận bộ quy tắc của mảng dự án đó, nên sửa quy tắc hay quy trình mảng này không đụng mảng kia. Hoạt động và Cài đặt dùng chung (một hàng đợi Claude cho mọi dự án).

Phim tài liệu theo quy trình 7 bước, mỗi bước do Claude Code (chạy headless) làm và bạn duyệt trên giao diện web:

1. **Kịch bản**: nghiên cứu nguồn (tư liệu bạn đưa vào, web, kho highlight JRE nếu bật), luận đề, lời dẫn, trích dẫn, thời lượng.
2. **Tuyển nhân vật**: danh sách vai, ngoại hình bám nguồn, tư thế, ảnh thử vai để bạn chọn.
3. **Phân cảnh & bối cảnh**: cảnh 3D, bối cảnh, danh sách ảnh cần vẽ (prompt, model, chi phí USD), footage cần.
4. **Render hình ảnh**: ảnh qua API fal.ai (Nano Banana Pro, GPT Image 2.5, Seedream…), tách nền trên máy, đo điểm neo.
5. **Footage & âm thanh**: footage có giấy phép (chỉ tải khi bạn duyệt), clip trích, lời dẫn qua API ElevenLabs, nhạc tự tổng hợp.
6. **Dựng & render**: engine Remotion + three.js (không gian 3D nhiều lớp, hiệu ứng lửa/khói thật), QA, MP4.
7. **Metadata YouTube**: từ khóa, tiêu đề, mô tả có chương, thẻ, hashtag, phụ đề .srt, thumbnail.

## Bốn cách dựng hình (chọn cho từng dự án)

- **Ghép lớp** (mặc định, cách cũ): nhân vật vẽ trên nền xám, tách nền trên máy, ghép lên các tấm nền vẽ trong không gian 3D của engine. Nhân vật cử động được (rig), nhưng ánh sáng giữa nhân vật và nền dễ lệch.
- **Ảnh liền khối → 3D** (ô "Cách mới" khi tạo dự án hoặc trong Thông tin dự án): mỗi cảnh dựng lại là một ảnh hoàn chỉnh có nhân vật (GPT Image + ảnh gốc nhân vật làm tham chiếu), rồi `parallax/` biến ảnh thành clip camera 3D trên GPU của máy: Depth Anything V2 ước lượng độ sâu → tách lớp ở mép đứt gãy độ sâu, vá nền phía sau → camera orbit / push-in / crane… Ánh sáng, bóng, phối cảnh thống nhất; nhân vật không cử động riêng. Chi tiết ở bộ quy tắc mục 4.9.
- **Xếp lớp: GPT vẽ từng lớp → camera 3D** (mới): mỗi cảnh chia 2–4 lớp theo độ sâu (nhân vật cùng lớp với mặt đất họ đứng), GPT vẽ riêng từng lớp (`staged/layerkit.py`: lớp xa vẽ kín khung, lớp trước vẽ trên nền xám rồi `staged/greykey.py` cắt đúng phần xám), engine xếp lớp ở đúng khoảng cách và đi camera thật (`engine/src/staged/LayerScene.tsx`). Hiệu ứng code chỉ là đề xuất trong bảng cảnh, chờ bạn duyệt. Chi tiết ở bộ quy tắc mục 4.10.
- **Hồ sơ tư liệu thật** (mới, `pipeline: dossier`): phim dựng từ ảnh, trang tài liệu, footage **thật** như vật chứng trong hồ sơ. Ảnh in có viền đáp xuống bàn đúng lúc lời dẫn gọi tên; trang báo/Wikipedia có highlight quét theo đúng chữ đang đọc (`engine/scripts/pagecap.mjs` chụp trang và đo toạ độ cụm từ); bảng điều tra nối dây đỏ; footage cũ trong khung phim 8mm; logo tổ chức thành khối 3D; con dấu trạng thái kiểm chứng. Kịch bản có hai khung kể mới: *hồ sơ vụ việc* (các vụ song song, leo thang) và *đường hang thỏ* (chuỗi mắt xích người). AI chỉ tái hiện cảnh không thể có ảnh (bằng cách xếp lớp). Engine `engine/src/dossier`, video mẫu `engine/out/showcase/dossier_showcase.mp4`, chi tiết ở bộ quy tắc mục 4.11.

Chọn ở ô **Cách dựng hình** khi tạo dự án, trong **Thông tin** dự án, hoặc mặc định ở Cài đặt.

Tách ra từ tab "Phim tài liệu" của JRE Studio (`E:\Tool\DataBase`, commit e765b14) để làm phim về mọi chủ đề, không chỉ JRE. JRE Studio vẫn giữ nguyên.

## Chạy

- **Tool Manager** (`E:\Tool\run.pyw`) → thẻ **Creater Vid** → Start → Mở. App chạy ở `http://127.0.0.1:5010`.
- Hoặc nhấn đúp `start.bat` (mở trình duyệt), hoặc chạy tay: `"E:\Tool\Creater Vid\.venv\Scripts\python.exe" app.py`.
- Lần đầu: vào **Cài đặt**, xem bảng "Kiểm tra hệ thống" phải xanh hết. Bảng có nút cài engine, tải Chrome, chạy thử Claude, kiểm tra key ElevenLabs và fal.ai. Điền hai API key ở mục **API tạo nguyên liệu**.

## Cần có trên máy

| Thứ | Ở đâu | Ghi chú |
|---|---|---|
| Claude Code CLI | `E:\Tool\claude-cli` | dùng chung với JRE Studio; đăng nhập bằng `E:\Tool\DataBase\dang-nhap-claude.bat` (`/login`) |
| API key ElevenLabs | Cài đặt → API tạo nguyên liệu (hoặc biến môi trường `ELEVENLABS_API_KEY`) | giọng đọc, hiệu ứng âm thanh |
| API key fal.ai | Cài đặt → API tạo nguyên liệu (hoặc `FAL_KEY`) | ảnh, sửa ảnh, video |
| Node.js | PATH | engine ở `engine/` (đã `npm install`, có Chrome Headless Shell) |
| ffmpeg | PATH hoặc `E:\Tool\video-cutter-portable\ffmpeg` | |
| Tách nền BiRefNet | `E:\Tool\bgremove\.venv` | miễn phí, chạy GPU |
| faster-whisper | Python 3.14 của máy | canh lời dẫn, kiểm tra giọng |

## Cấu trúc

```
app.py                  Flask UI + JSON API (Tool Manager import `app`)
creater/
  config.py             đường dẫn, cổng 5010, giá trị mặc định
  db.py  schema.sql     SQLite (creater.db): settings, projects, project_steps, messages, rules, events
  workflow.py           quy trình của từng mảng (FLOWS: doc 7 bước, news 6 bước): mô tả, file đầu ra, kiểm tra sau lượt, dữ liệu hiển thị
  store.py              dự án (cột kind: doc | news), trạng thái bước, tin nhắn, hai bộ quy tắc có phiên bản, nhật ký, file của dự án
  prompts.py            prompt mỏng theo mảng: quy trình chi tiết nằm ở mục 2 của bộ quy tắc mảng đó
  worker.py             hàng đợi lượt Claude; mỗi lần chạy bước là một phiên mới, chat nối tiếp (--resume) phiên của bước đó
                        (Cài đặt → Phiên Claude; model agent con theo mảng ở bảng của từng mảng: phim tài liệu
                        mặc định như model của lượt, tin tức mặc định sonnet)
  claude_runner.py      chạy Claude Code CLI, bắt stream-json (chép từ JRE Studio)
  scaffold.py           film/ của dự án = bản chép engine + liên kết node_modules dùng chung
parallax/               ảnh tĩnh → clip camera 3D (chạy bằng Python của bgremove: PyTorch + CUDA)
  parallax.py           CLI: một ảnh hoặc --batch jobs.json; cache độ sâu/lớp theo nội dung ảnh
  depth.py              Depth Anything V2 Large (model ở E:\Tool\bgremove\hf)
  layers.py             tách lớp ở mép đứt gãy độ sâu, vá nền (Telea + vân soi gương), lớp trời riêng
  render.py             camera 3D: chiếu ngược từng lớp, DoF, bloom, mây trôi; NVENC; ~0,1 s/khung 1080p trên RTX 4060
  health.py             kiểm tra hệ thống, cài engine, thăm dò Claude, trạng thái API
  providers.py          gọi API ElevenLabs (giọng đọc, hiệu ứng âm thanh) và fal.ai (ảnh, video, mọi model khác)
  gen.py                lệnh tạo nguyên liệu cho lượt headless: tts, sfx, image, video, run, schema, models, price, cost
  media.py              ảnh, video lấy từ tin: danh sách chờ duyệt (sources/media.json), tải sau khi duyệt
  tg.py                 Telegram API bằng tài khoản của bạn (Telethon, chạy bằng .venv): đăng nhập, tải video lớn
  news.py               mục Tin tức: chủ đề, nguồn, tin, luồng tự cập nhật, gộp tin cùng sự kiện, tạo dự án từ tin
  news_fetch.py         tải và đọc RSS/Atom, kênh Telegram công khai, Bing/Google News, toàn văn bài báo (chỉ thư viện chuẩn)
engine/                 Remotion + three.js (ENGINE.md là cẩm nang), node_modules không commit
RULEBOOK.doc.seed.md    bộ quy tắc phim tài liệu bản đầu; bản làm việc ở <thư mục dự án>\RULEBOOK.doc.md
RULEBOOK.news.seed.md   bộ quy tắc video tin tức bản đầu; bản làm việc ở <thư mục dự án>\RULEBOOK.news.md
                        (mỗi lần sửa là một phiên bản của riêng bộ đó; trước 2026-10-14 hai mảng dùng chung RULEBOOK.md)
templates/ static/      giao diện
```

Thư mục dự án mặc định `K:\VideoLab\creater-projects` (ổ E: gần đầy; đổi ở Cài đặt). Mỗi dự án:

```
project.json  sources/  1_script/  2_cast/  3_scenes/  4_images/  5_footage/  6_render/  7_metadata/  film/  out/  notes/
```

## Cách làm một phim

1. **Dự án mới**: chủ đề, yêu cầu riêng, ngôn ngữ, định dạng, thời lượng, ngân sách nguyên liệu (USD).
2. Bước 1: kéo thả tư liệu (PDF, transcript, ghi chú) và dán link, rồi **▶ Chạy bước**.
3. Mỗi bước xong chuyển sang **chờ duyệt**: xem kết quả ngay trong khung bước, nhắn Claude để sửa, rồi **✓ Duyệt** để mở bước sau.
   - Bước 2: bấm vào ảnh thử vai để chọn.
   - Bước 4: nút **Làm lại** trên từng ảnh (kèm ghi chú).
   - Bước 5: duyệt hoặc bỏ từng footage trước khi Claude tải về.
4. Bước trước bị sửa sau khi bước sau đã chạy: bước sau hiện ⚠ để xem lại.
5. **Hoạt động**: lượt đang chạy, hàng đợi, chi phí Claude và chi phí nguyên liệu (USD) theo dự án.
6. **Bộ quy tắc** (tab Bộ quy tắc của mỗi mảng): Claude đọc toàn văn bộ của mảng dự án mỗi lượt. Nhắn "cập nhật quy tắc: …" trong chat của một dự án, hoặc sửa tay; mỗi lần đổi là một phiên bản của riêng bộ đó, khôi phục được.

Chế độ **Tự chạy** (khi tạo dự án hoặc trong Thông tin): app tự duyệt khi kết quả đủ và chạy luôn bước sau.

## Nguyên liệu trả phí: ElevenLabs và fal.ai

Giọng đọc, ảnh và video gọi thẳng API bằng key của bạn (trang **Cài đặt → API tạo nguyên liệu**). Key nằm trong `creater.db`, không bao giờ gửi lại trình duyệt hay cho Claude: lượt headless chạy `gen.py` (đường dẫn trong biến `GEN_PY`), gen.py tự đọc key.

- **ElevenLabs**: model giọng (mặc định `eleven_v4`), giọng đọc theo ngôn ngữ video (chọn từ thư viện giọng, nghe thử ngay trên trang), hiệu ứng âm thanh.
- **fal.ai**: model ảnh chính, ảnh rẻ (thử vai), sửa ảnh, video. Ô model nhận id bất kỳ trong danh mục fal (có ô tìm model).
- **OpenAI, Google (tùy chọn)**: tạo ảnh gọi thẳng bằng key riêng. Đặt model `openai:gpt-image-2.5-sunburst` (GPT Image) hoặc `google:gemini-3-pro-image` (Nano Banana Pro), `google:gemini-3.1-flash-image` (Nano Banana 2) vào ô model ảnh nào cũng được. Key OpenAI mua qua dịch vụ trung gian (dạng `sk-` + 48 ký tự, thường bán kèm Codex) thì điền thêm **Base URL** /v1 của dịch vụ đó; nút "Lưu và kiểm tra key" báo key đó có model tạo ảnh hay không.
- **Chi phí**: mỗi lần gọi, gen.py ghi USD vào `notes/costs.json` của dự án; vượt `budget_usd` thì gen.py từ chối và Claude hỏi bạn. Chi phí hiện ở trang dự án, danh sách dự án và Hoạt động.
- Thử tay: `.venv\Scripts\python.exe gen.py check`, `... gen.py voices --lang ru`, `... gen.py image --prompt "..." --out x.png --dry-run`.

## Mảng Tin tức: tin theo dõi → video

Trang **Tin theo dõi** (`/news`) theo dõi tin theo thời gian thực và biến tin đã chọn thành một dự án của mảng Tin tức (quy trình 6 bước, bộ quy tắc tin tức).

- **Chủ đề theo dõi**: tên, ngôn ngữ video, chu kỳ cập nhật (mặc định 10 phút), từ khóa và từ loại trừ, yêu cầu mặc định, định dạng, thời lượng, kiểu video mặc định. Mẫu có sẵn "Chiến sự Nga–Ukraina (tiếng Nga)": 22 nguồn đã kiểm tra (Минобороны/Рыбарь/Два майора/WarGonzo, ТАСС, РИА, Интерфакс, РБК, Коммерсантъ, Lenta, Военное обозрение; Генштаб ВСУ, DeepState, Украинская правда, УНИАН, Страна.ua; Meduza, Новая газета Европа, BBC/DW tiếng Nga; Bing News, Google News).
- **Nguồn**: RSS/Atom, kênh Telegram công khai (đọc qua `t.me/s/<kênh>`), tìm theo từ khóa trên Bing News hoặc Google News. Mỗi nguồn ghi **phía** (Nga, Ukraina, độc lập, quốc tế) để kịch bản ghi rõ ai nói gì, và bật/tắt **lọc từ khóa** (tắt cho kênh chuyên về chủ đề). Nút **Thử** đọc nguồn một lần mà không lưu.
- **Từ khóa**: viết thường khớp đầu từ (`наступлен` → наступление, наступления…), viết HOA khớp nguyên từ (`СВО` không khớp "своим").
- **Luồng cập nhật** chạy trong app (cùng tiến trình với hàng đợi Claude): mỗi 30 giây xem chủ đề nào tới hạn, đọc mọi nguồn song song, bỏ tin cũ hơn `news_max_age_h`, gộp tin cùng sự kiện từ nhiều nguồn (trùng từ, không lệch số liệu, ngày giờ hay địa danh). Nguồn lỗi 5 lần liền thì chỉ thử lại mỗi giờ. Tin cũ hơn `news_keep_days` bị xóa, trừ tin ★ và tin đã làm video. Bật/tắt và các giới hạn ở **Cài đặt → Tin tức**.
- **Làm video**: tích chọn tin (hoặc "chọn cả nhóm" của một sự kiện) → **🎬 Làm video**. App đọc toàn văn từng tin, tạo dự án mới với `sources/news_NN_*.md` (nguồn, phía, giờ đăng, link, toàn văn), `sources/news.json` và `links.txt`, rồi chạy bước 1 nếu chọn. Một số trang chặn bot (ТАСС, BBC, УНИАН): tin đó chỉ có tóm tắt từ RSS, Claude tự đọc link gốc khi viết kịch bản.
- **Kiểu video**: *Tin nóng* (một sự kiện, mặc định 9:16 · 60 s) hoặc *Điểm tin 24h* (bản tin tổng hợp YouTube 16:9 · 15 phút, bộ quy tắc tin tức mục 2.9: menu tiêu đề mở đầu, mỗi tin 30–75 s có ghi ai công bố, tin của thumbnail ở giữa video, tin căng nhất gần cuối, tin nhẹ trước lời tạm biệt; mỗi tin 2–4 hình, dải tít, phụ đề hộp tối). Nút **📰 Điểm tin 24h** tự chọn 16 sự kiện được nhiều nguồn đưa nhất trong 24 giờ qua (mỗi sự kiện tin đầy đủ nhất, thêm một tin của phía kia nếu có), rồi mở hộp Làm video; dự án có thêm `sources/digest.md` (các sự kiện, xếp theo số nguồn). Ô **Trọng tâm điểm tin** (VD «ưu tiên tin về Putin, Zelensky, đàm phán»): tên người, nước, chủ đề viết tiếng Việt/Anh được đổi sang từ khóa tiếng Nga (bảng `FOCUS_ALIASES` trong `creater/news.py`; gõ thẳng tiếng Nga cũng được), sự kiện nhắc tới trọng tâm trong tiêu đề, hoặc ≥ 2 lần trong bài, được chọn trước và đánh ★; câu trọng tâm vào yêu cầu riêng để Claude ưu tiên các tin đó. Trước khán giả không nêu tên kênh Telegram, chỉ nêu báo, hãng tin lớn (bộ quy tắc tin tức mục 1.6). Mẫu chủ đề "Điểm tin 24h Nga–Ukraina" dùng cùng nguồn với mẫu chiến sự, thêm từ khóa chính trị (Kremlin, Kyiv, Trump, NATO, EU, viện trợ, trừng phạt, động viên).

### Ảnh, video từ tin: duyệt trước khi dùng

- Mỗi bài Telegram có ảnh (cả album) và video. Trang Tin tức hiện 🖼 / 🎞 cạnh mỗi tin để chọn tin có hình.
- **Làm video** từ các tin: app lập danh sách **🧾 Nguyên liệu từ tin** trên trang dự án (`sources/media.json`). Mỗi mục có ảnh xem trước, nguồn, link bài gốc, nguồn gốc nếu là bài chuyển tiếp, và nhắc nhở: ⚠ người chết hoặc bị thương, tù binh, trẻ em, ℹ ảnh của báo (có thể có Content ID), tư liệu của một bên tham chiến, video dài.
- **Ảnh thật trước, ảnh AI sau** (bộ quy tắc tin tức mục 1.7): khi tạo dự án, app **tự duyệt và tải hết** ảnh, video của các tin vào `sources/media/` (4 file cùng lúc); Claude lấy thêm mọi ảnh trong thân các bài gốc, chỉ dùng ảnh AI khi một tin không còn ảnh thật nào. Content ID, logo, watermark không cản việc dùng ảnh: bạn tự xử lý khi edit. Bấm **Bỏ** trên trang dự án để loại một mục (file bị xóa, Claude không dùng). Claude vẫn tự xem từng file trước khi dùng, che mờ thi thể, máu, tù binh, mặt trẻ em (mục 1.5).
- Video nhỏ và ảnh tải qua trang web công khai của kênh. **Video lớn** (Telegram báo "Media is too big") cần **Telegram API**: Cài đặt → Telegram API → điền `api_id`, `api_hash` (lấy ở my.telegram.org → API development tools) và số điện thoại → Gửi mã → nhập mã Telegram gửi trong app (và mật khẩu 2 bước nếu có). Phiên đăng nhập lưu ở `work\telegram\creater.session` (không commit, không gửi cho ai). Nên dùng tài khoản Telegram phụ.
