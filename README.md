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

Skill `chon-noi-dung-jre-v2` được copy tự động từ thư mục plugin của app desktop vào `.claude/skills/` trước mỗi lần chạy, nên luôn cùng phiên bản với bản chạy tay.

## Sửa đổi ở tool cũ

- Video Cutter: endpoint `POST /api/cut-headless` (không mở hộp thoại, không đụng trạng thái UI), tham số `write_sidecars` (mặc định tắt) và ô chọn "Xuất kèm transcript + manifest" trên giao diện tay, `index` cố định số thứ tự file clip.
- Podcast Zoom: `generate_thumbnail` mặc định tắt, endpoint `POST /api/enqueue-path` nhận đường dẫn và ghi thẳng ra `output_path`, không xoá file gốc.
- Tool Manager: thẻ JRE Studio, mọi tool có `.venv` tự dùng interpreter riêng.
