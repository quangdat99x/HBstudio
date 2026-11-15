=============================================
  Video Cutter - Cắt video theo timestamp
=============================================

YÊU CẦU:
  - Windows 10/11
  - Python 3.10+ (tải từ python.org)
    → NHỚ tích "Add Python to PATH" khi cài!
  - Internet (lần đầu để cài thư viện)

CÁCH DÙNG:
  1. Chạy run.bat (lần đầu sẽ tự cài thư viện)
  2. Chọn video → tạo transcript bằng Whisper (tuỳ chọn)
  3. Thêm đoạn cắt → xuất video

TÍNH NĂNG:
  ✂️  Cắt video theo timestamp (ffmpeg stream copy, không encode lại)
  🎙  Tạo transcript bằng Whisper AI (tùy chọn, hỗ trợ GPU)
  🖥  Giao diện desktop native (pywebview) hoặc browser fallback
  📝  Xuất transcript dạng JSON/TXT
  🔧  Kéo chỉnh kích thước layout tùy ý

THƯ VIỆN TỰ ĐỘNG CÀI:
  - flask (web server)
  - pywebview (cửa sổ desktop)
  - faster-whisper (AI transcript, tùy chọn)

GHI CHÚ:
  - ffmpeg đã được đóng gói sẵn trong thư mục ffmpeg/
  - Output mặc định: thư mục output/ hoặc chọn thư mục tùy ý
  - Kích thước panel được lưu lại khi thay đổi
