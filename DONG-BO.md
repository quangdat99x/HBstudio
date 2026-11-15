# Đồng bộ bộ tool giữa các máy

Code của `C:\Tool` nằm trong một repo GitHub private (remote `origin`, nhánh `main`). Chỉ có code đi qua Git:
database (`studio.db`, `creater.db`), `.venv`, model Whisper/AI, ffmpeg, log, `work/`, `output/` và file bí mật
(`.env`, `cookies.txt`, `proxies.txt`) ở lại từng máy (xem `.gitignore`). Vì vậy mỗi máy có dữ liệu, kho highlight và
cài đặt (vd `media_root`) riêng.

## Cài đặt riêng từng máy
- Đường dẫn dữ liệu (`media_root` của DataBase, `projects_root` của Creater Vid) lưu trong database của từng máy:
  sửa ở trang Cài đặt của tool. Mặc định trong code chỉ dùng khi máy đó chưa từng lưu.
- File cài đặt chung (`cpu_budget.json`, `voice-dub/settings.json`, `news-digest/config.json`) chỉ là mặc định.
  Máy nào cần khác thì tạo `<tên>.local.json` cạnh nó, chỉ ghi các khoá muốn đổi (vd `cpu_budget.local.json`:
  `{"render_concurrency": 6}`). File `.local.json` không lên GitHub. voice-dub tự ghi giọng đã chọn vào đó.
- Video / âm thanh (`*.mp4`, `*.wav`, `*.mp3`...) không bao giờ đi qua Git; file mới trên 50 MB bị nút Đồng bộ bỏ qua.

## Dùng hằng ngày
- Sửa code ở máy nào (tự sửa, hoặc nhờ Claude sửa) thì mở Tool Manager trên máy đó, bấm **🔄 Đồng bộ code**: commit
  thay đổi của máy này → kéo bản mới của máy kia → đẩy lên GitHub. Tool đang chạy mà có code mới thì tự khởi động lại.
  Có `requirements.txt` mới thì tự `pip install` vào đúng venv của tool.
- Mở Tool Manager ở máy kia là tự kéo bản mới (khi máy đó không có sửa dở dang); 15 phút kiểm tra lại một lần.
- Đổi `run.pyw` / `_sync.py` thì đóng và mở lại Tool Manager để dùng bản mới.
- Hai máy sửa cùng một chỗ trong cùng một file: Đồng bộ dừng lại, báo tên file, code máy này vẫn nguyên (đã commit).
  Nhờ Claude: "gộp xung đột Git trong C:\Tool" rồi bấm Đồng bộ lại. Thói quen tránh xung đột: bấm Đồng bộ trước khi bắt đầu sửa.

## Nối một máy vào repo (một lần)
1. Cài Git nếu chưa có: `_setup\cai-git.bat`.
2. Máy đã có bộ tool chép từ trước: chép `_setup\noi-github.bat` + `noi-github.ps1` vào `C:\Tool\_setup\`, bấm đúp
   `noi-github.bat`, dán link repo. Script sao lưu mọi file code khác bản GitHub vào `_sync_backup\<thời gian>\`,
   chuyển lịch sử Git cũ của DataBase / Creater Vid sang `.git-cu\`, rồi lấy đúng bản GitHub. Dữ liệu không bị đụng.
3. Máy mới tinh: `git clone <link> C:\Tool`, chạy `_setup\cai-dat.bat`, tạo `.venv` cho từng tool từ
   `requirements.txt`, `npm install` trong `Creater Vid\engine`, chép ffmpeg và model (`video-cutter-portable\whisper_models`,
   `podcast-zoom-tool\models\whisper`, `bgremove\hf`) từ máy cũ, tạo lại `.env` / `cookies.txt` / `proxies.txt`.

Lần đầu đẩy hoặc kéo, Git mở trình duyệt để đăng nhập GitHub (Git Credential Manager), sau đó nhớ luôn.
Lịch sử Git cũ của DataBase và Creater Vid được giữ trong repo dưới `refs/archive/*`.
