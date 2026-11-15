VIDEO WATCHER — cho Claude "xem" video để bắt chước
====================================================

Claude không đọc được file video. Công cụ này biến video thành thứ Claude xem được:
  - cắt cảnh (cắt cứng bằng ffmpeg scene + chuyển mềm dissolve/wipe bằng histogram)
  - khung đại diện mỗi shot  -> frames/
  - contact sheet có nhãn "#số mm:ss"  -> sheets/sheet_XX.jpg
  - hook sheet 1 khung/giây cho 15s đầu  -> sheets/hook.jpg
  - transcript Whisper (GPU, model dùng chung với Video Cutter)  -> transcript.txt
  - nhịp dựng, âm lượng, bảng màu, thông tin nguồn (title/tags/mô tả nếu là URL)
  - REPORT.md: bản tổng hợp Claude đọc đầu tiên; analysis.json: dữ liệu đầy đủ

CÁCH DÙNG
  1. Launcher (run.pyw) -> thẻ "Video Watcher" -> Start -> Mở  (cổng 5011)
     Dán đường dẫn/URL, bấm 📁, hoặc kéo-thả file -> "Phân tích video".
  2. Bấm Copy dòng "Gửi cho Claude" và dán vào Claude Code.
     Skill "xem-video" (C:\Users\nguye\.claude\skills\xem-video) hướng dẫn Claude đọc báo cáo,
     xem từng sheet và viết BREAKDOWN.md (hook, beat sheet, hình ảnh, nhịp, công thức bắt chước).
     Giao diện tự hiện BREAKDOWN.md khi có.
  Hoặc nói thẳng với Claude: "xem video D:\abc.mp4 rồi mổ xẻ để bắt chước" — Claude tự chạy:
     py -3.14 -X utf8 E:\Tool\video-watcher\watcher.py "<file hoặc URL>" [--max-frames 100]
        [--model large-v3] [--lang vi] [--scene 0.2] [--hook 30] [--no-transcript]

GHI CHÚ
  - URL tải qua engine của "Youtube Dowloader" (cookie, đổi IP dongle, tự cập nhật yt-dlp), ≤720p.
  - Chạy bằng Python 3.14 mặc định (đã có faster-whisper, CUDA, Pillow, numpy, Flask).
  - Kết quả nằm trong output\<thời gian>_<tên video>\ ; xoá thư mục đó là xoá kết quả.
