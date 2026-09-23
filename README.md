# JRE Studio

Pipeline tự động cho kênh JRE Highlights: **video vào → transcript → chọn nội dung (Claude) → cắt → zoom → kho highlight**, quản lý qua giao diện web. Kế hoạch chi tiết và các quyết định: [PLAN.md](PLAN.md).

## Chạy

- Cách thường dùng: mở **Tool Manager** (`E:\Tool\run.pyw`) → thẻ **JRE Studio** → Start → Mở. Studio chạy ở `http://127.0.0.1:5004` và tự khởi động Cutter/Zoom/Downloader khi cần.
- Chạy tay: `E:\DataBase\.venv\Scripts\python.exe app.py`
- CLI cho Claude và cho người: `E:\DataBase\.venv\Scripts\python.exe hldb.py --help`

## Cấu trúc

```
app.py                  Flask UI + JSON API (Tool Manager import `app`)
hldb.py                 CLI: scan/ingest/search/show/export/tag/import-analysis
studio/
  config.py             đường dẫn, port, mặc định
  db.py  schema.sql     SQLite + FTS5, settings
  ingest.py             nạp cutlist mọi biến thể, quét thư mục clip, transcript
  search.py             chỉ mục full-text và truy vấn có lọc
  analysis.py           bắt khối phân tích của skill (Mục VI) gắn vào từng đoạn
  tagging.py            theme/entity do Claude gán
  export.py             pool cho tong-hop-rabbit-hole, cut_multi cho Video Cutter
  pipeline/
    orchestrator.py     worker + state machine mỗi tập, hàng đợi trong SQLite
    intake.py           theo dõi thư mục media, tải URL qua Downloader
    transcribe.py       whisper_worker.py của Cutter (CUDA)
    select_ai.py        claude -p "/chon-noi-dung-jre-v2 ..." headless + validator
    cut.py  zoom.py     gọi Cutter (/api/cut-headless) và Zoom (/api/enqueue-path)
    claude_runner.py    chạy Claude Code CLI, bắt stream-json
.claude/skills/         chon-noi-dung-jre-v2 (sync từ app desktop), kho-highlight (mới)
templates/ static/      UI
studio.db               database (không commit)
work/  logs/            file tạm, log
```

## Trạng thái tập (state machine)

`new → transcribing → selecting → [reviewing] → cutting → zooming → indexing → ready`, lỗi thì `failed:<bước>` và bấm "Chạy tiếp" trên UI. Bước nào đã có sản phẩm (transcript, cutlist, clip, bản zoom) thì tự bỏ qua.

## Bước Claude headless (người dùng làm một lần)

1. CLI đã cài tại `E:\Tool\claude-cli` (bản 2.1.280) bằng `npm i -g --prefix E:\Tool\claude-cli @anthropic-ai/claude-code`. Không cài vào `%APPDATA%\npm` từ bên trong app Claude desktop: app là gói MSIX nên thư mục đó bị ảo hoá, bên ngoài không thấy.
2. Đăng nhập: nhấn đúp `E:\DataBase\dang-nhap-claude.bat`, gõ `/login`, làm theo hướng dẫn trên trình duyệt, rồi `/exit`. Muốn token dài hạn cho script thì chạy `E:\Tool\claude-cli\claude.cmd setup-token` trong PowerShell và đặt biến môi trường `CLAUDE_CODE_OAUTH_TOKEN`.
3. Kiểm tra ở trang **Cài đặt** của Studio: dòng "Claude Code headless" phải báo CLI và token hoặc đã đăng nhập.
4. Chọn model ở cùng trang: model và effort riêng cho bước chọn nội dung và cho Hỏi AI (bí danh `fable`, `opus`, `sonnet`, `haiku` hoặc tên đầy đủ), model dự phòng khi quá tải. Để trống = model mặc định của Claude Code cho tài khoản. Nút "Kiểm tra" chạy một lượt nhỏ và in ra model thực tế trả lời; mỗi job chọn nội dung cũng ghi model, số token và thời gian vào cột thông báo.

Skill `chon-noi-dung-jre-v2` được copy tự động từ thư mục plugin của app desktop vào `.claude/skills/` trước mỗi lần chạy, nên luôn cùng phiên bản với bản chạy tay.

## Sao lưu, làm sạch, khôi phục

- Trang **Cài đặt → Làm sạch dữ liệu**, hoặc `hldb reset --yes`: sao lưu `studio.db` vào `backups\` rồi xóa mọi tập, đoạn, transcript, theme đã gán, job. Giữ cài đặt và danh sách theme. Không đụng tới file trên đĩa.
- `hldb backup`: sao lưu thủ công. `hldb restore backups\studio_<thời gian>.db`: khôi phục (tự sao lưu trạng thái hiện tại trước).
- Cutlist cũ (không có `cutlist_layout: flat_hooks`) nằm trong thư mục media sẽ không được dùng lại: pipeline đổi tên thành `.old_…` và cho Claude chọn lại bằng skill hiện hành.

## Dừng và khởi động lại

- Nút **Dừng** ở trang Hàng đợi và trang tập: bỏ tập khỏi hàng đợi, hoặc dừng bước đang chạy ở điểm an toàn gần nhất (Claude bị dừng ngay, Cutter/Zoom làm nốt đoạn đang xử lý).
- Khởi động lại Studio giữa chừng là an toàn: tập đang dở tự vào lại hàng đợi, bước cắt chờ Cutter xong việc cũ và dùng lại clip đã có, bước zoom dùng lại job Zoom đang chạy.
- Template tự nạp lại khi sửa; sửa file `.py` thì cần Stop rồi Start Studio.

## Sửa đổi ở tool cũ

- Video Cutter: endpoint `POST /api/cut-headless` (không mở hộp thoại, không đụng trạng thái UI), tham số `write_sidecars` (mặc định tắt) và ô chọn "Xuất kèm transcript + manifest" trên giao diện tay, `index` cố định số thứ tự file clip.
- Podcast Zoom: `generate_thumbnail` mặc định tắt, endpoint `POST /api/enqueue-path` nhận đường dẫn và ghi thẳng ra `output_path`, không xoá file gốc.
- Tool Manager: thẻ JRE Studio, mọi tool có `.venv` tự dùng interpreter riêng.
