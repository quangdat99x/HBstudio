# Creater Vid

Tool làm phim tài liệu theo quy trình 6 bước, mỗi bước do Claude Code (chạy headless) làm và bạn duyệt trên giao diện web:

1. **Kịch bản**: nghiên cứu nguồn (tư liệu bạn đưa vào, web, kho highlight JRE nếu bật), luận đề, lời dẫn, trích dẫn, thời lượng.
2. **Tuyển nhân vật**: danh sách vai, ngoại hình bám nguồn, tư thế, ảnh thử vai để bạn chọn.
3. **Phân cảnh & bối cảnh**: cảnh 3D, bối cảnh, danh sách ảnh cần vẽ (prompt, model, credit), footage cần.
4. **Render hình ảnh**: ảnh Higgsfield (GPT Image 2.5, Nano Banana Pro, Soul Cinema), tách nền trên máy, đo điểm neo.
5. **Footage & âm thanh**: footage có giấy phép (chỉ tải khi bạn duyệt), clip trích, lời dẫn ElevenLabs v4, nhạc tự tổng hợp.
6. **Dựng & render**: engine Remotion + three.js (không gian 3D nhiều lớp, hiệu ứng lửa/khói thật), QA, MP4.

Tách ra từ tab "Phim tài liệu" của JRE Studio (`E:\DataBase`, commit e765b14) để làm phim về mọi chủ đề, không chỉ JRE. JRE Studio vẫn giữ nguyên.

## Chạy

- **Tool Manager** (`E:\Tool\run.pyw`) → thẻ **Creater Vid** → Start → Mở. App chạy ở `http://127.0.0.1:5010`.
- Hoặc nhấn đúp `start.bat` (mở trình duyệt), hoặc chạy tay: `"E:\Creater Vid\.venv\Scripts\python.exe" app.py`.
- Lần đầu: vào **Cài đặt**, xem bảng "Kiểm tra hệ thống" phải xanh hết. Bảng có nút cài engine, tải Chrome, chạy thử Claude, kiểm tra số dư Higgsfield.

## Cần có trên máy

| Thứ | Ở đâu | Ghi chú |
|---|---|---|
| Claude Code CLI | `E:\Tool\claude-cli` | dùng chung với JRE Studio; đăng nhập bằng `E:\DataBase\dang-nhap-claude.bat` (`/login`) |
| Connector Higgsfield | claude.ai (tài khoản đã đăng nhập) | lượt headless thấy tool `mcp__claude_ai_HF__*` |
| Node.js | PATH | engine ở `engine/` (đã `npm install`, có Chrome Headless Shell) |
| ffmpeg | PATH hoặc `E:\Tool\video-cutter-portable\ffmpeg` | |
| Tách nền BiRefNet | `E:\Tool\bgremove\.venv` | 0 credit, chạy GPU |
| faster-whisper | Python 3.14 của máy | canh lời dẫn, kiểm tra giọng |

## Cấu trúc

```
app.py                  Flask UI + JSON API (Tool Manager import `app`)
creater/
  config.py             đường dẫn, cổng 5010, giá trị mặc định
  db.py  schema.sql     SQLite (creater.db): settings, projects, project_steps, messages, rules, events
  workflow.py           6 bước: mô tả, file đầu ra bắt buộc, kiểm tra sau lượt, dữ liệu hiển thị
  store.py              dự án, trạng thái bước, tin nhắn, bộ quy tắc có phiên bản, nhật ký, file của dự án
  prompts.py            prompt mỏng: quy trình chi tiết nằm ở bộ quy tắc mục 2
  worker.py             hàng đợi: một lượt Claude mỗi lúc cho mọi dự án, mỗi dự án một phiên Claude (--resume)
  claude_runner.py      chạy Claude Code CLI, bắt stream-json (chép từ JRE Studio)
  scaffold.py           film/ của dự án = bản chép engine + liên kết node_modules dùng chung
  health.py             kiểm tra hệ thống, cài engine, thăm dò Claude/Higgsfield
engine/                 Remotion + three.js (ENGINE.md là cẩm nang), node_modules không commit
RULEBOOK.seed.md        bộ quy tắc bản đầu; bản làm việc ở <thư mục dự án>\RULEBOOK.md, mỗi lần sửa là một phiên bản
templates/ static/      giao diện
```

Thư mục dự án mặc định `D:\VideoLab\creater-projects` (ổ E: gần đầy; đổi ở Cài đặt). Mỗi dự án:

```
project.json  sources/  1_script/  2_cast/  3_scenes/  4_images/  5_footage/  6_render/  film/  out/  notes/
```

## Cách làm một phim

1. **Dự án mới**: chủ đề, yêu cầu riêng, ngôn ngữ, định dạng, thời lượng, ngân sách credit Higgsfield.
2. Bước 1: kéo thả tư liệu (PDF, transcript, ghi chú) và dán link, rồi **▶ Chạy bước**.
3. Mỗi bước xong chuyển sang **chờ duyệt**: xem kết quả ngay trong khung bước, nhắn Claude để sửa, rồi **✓ Duyệt** để mở bước sau.
   - Bước 2: bấm vào ảnh thử vai để chọn.
   - Bước 4: nút **Làm lại** trên từng ảnh (kèm ghi chú).
   - Bước 5: duyệt hoặc bỏ từng footage trước khi Claude tải về.
4. Bước trước bị sửa sau khi bước sau đã chạy: bước sau hiện ⚠ để xem lại.
5. **Hoạt động**: lượt đang chạy, hàng đợi, chi phí Claude và credit Higgsfield theo dự án.
6. **Bộ quy tắc**: Claude đọc toàn văn mỗi lượt. Nhắn "cập nhật quy tắc: …" trong chat, hoặc sửa tay; mỗi lần đổi là một phiên bản, khôi phục được.

Chế độ **Tự chạy** (khi tạo dự án hoặc trong Thông tin): app tự duyệt khi kết quả đủ và chạy luôn bước sau.
