# Đồng bộ bộ tool giữa các máy

Code của `C:\Tool` nằm trong một repo GitHub private (remote `origin`, nhánh `main`). Chỉ có code đi qua Git:
database (`studio.db`, `creater.db`), `.venv`, model Whisper/AI, ffmpeg, log, `work/`, `output/` và file bí mật
(`.env`, `cookies.txt`, `proxies.txt`) ở lại từng máy (xem `.gitignore`). Vì vậy mỗi máy có dữ liệu, kho highlight và
cài đặt (vd `media_root`) riêng.

## Thư mục data: chỗ để khác nhau, format giống nhau
Mỗi máy chọn một thư mục data (Tool Manager → **📁 Thư mục data**, lưu trong `data_root.local.json`, không lên Git).
Bên trong luôn cùng một format trên mọi máy:

```
<thư mục data>\YouTube\Full\              video tập đầy đủ + <tên video>.transcript.json
<thư mục data>\YouTube\Cutlists\          cutlist_<TẬP>.json
<thư mục data>\YouTube\Clips\<tập>\       clip, bản zoom, thumbnail, _studio.json
<thư mục data>\YouTube\Tong-hop\          video tổng hợp
<thư mục data>\VideoLab\creater-projects\<dự án>\   dự án Creater Vid (có project.json)
```

Chuyển data sang máy kia: chép đúng thư mục con sang thư mục data của máy kia (ví dụ chép
`D:\DATA TOOL\YouTube\Clips\Joe Rogan Experience #2562 - …` vào `<data máy kia>\YouTube\Clips\`). Không cần bấm gì:
- **Studio** (mỗi phút, chờ chép xong): nạp cutlist, transcript và thư mục clip vào Kho highlight. File `_studio.json`
  trong thư mục clip mang theo những thứ chỉ database biết: Title / metadata đã viết, các bản thumbnail, trạng thái
  từng đoạn, phần phân tích, cả show podcast nếu máy kia chưa có. Gộp kiểu cộng dồn: máy nhận giữ nguyên cái nó đã có,
  thêm cái còn thiếu. Chép ngược lại cũng được.
- Video thả vào `Full\` mà có sẵn transcript bên cạnh thì **chỉ được index**, không chạy Whisper / Claude (không tốn
  tiền). Muốn chọn đoạn thì bấm Chạy ở trang tập.
- **Creater Vid**: thư mục dự án chép vào `creater-projects\` tự thành dự án (tiêu đề, cài đặt, trạng thái các bước
  lấy từ `project.json`). Lịch sử chat với Claude của dự án ở lại máy cũ.
- Đổi ổ / chuyển thư mục data: chép hoặc chuyển cả thư mục, chọn lại ở Tool Manager. Đường dẫn trong database tự trỏ
  sang chỗ mới lúc tool khởi động.
- Muốn nạp ngay không chờ: Studio, gửi `POST /api/portable` (hoặc nhờ Claude "index data chép vào Studio").

## Cài đặt riêng từng máy
- Có thư mục data thì `media_root` (Studio) và `projects_root` (Creater Vid) đi theo nó, trang Cài đặt chỉ hiện để xem.
  Máy chưa chọn thư mục data thì vẫn dùng đường dẫn trong Cài đặt như cũ.
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
4. Mở Tool Manager, bấm **📁 Thư mục data**, chọn thư mục data của máy đó (tool tự tạo `YouTube\…` và
   `VideoLab\creater-projects` bên trong).

Lần đầu đẩy hoặc kéo, Git mở trình duyệt để đăng nhập GitHub (Git Credential Manager), sau đó nhớ luôn.
Lịch sử Git cũ của DataBase và Creater Vid được giữ trong repo dưới `refs/archive/*`.
