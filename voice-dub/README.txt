LỒNG TIẾNG — thuyết minh video bằng Whisper + ElevenLabs
========================================================

Quy trình: Whisper nhận dạng lời -> Claude dịch (tuỳ chọn) -> xem lại, sửa lời -> ElevenLabs đọc từng câu
-> canh giọng khớp thời điểm lời gốc -> hạ tiếng gốc khi có giọng đọc -> ghép vào video (hình giữ nguyên, không render lại).

CÁCH DÙNG
  Launcher (run.pyw) -> thẻ "Lồng Tiếng" -> Start -> Mở  (cổng 5013)
  1. Chọn video, ngôn ngữ thuyết minh -> "Nhận dạng & dịch" (miễn phí).
  2. Xem lại lời, chọn giọng -> "Lồng tiếng" (báo trước số ký tự sẽ tốn).
  3. Muốn đổi âm lượng hay sửa vài câu: chỉnh rồi bấm lại. Câu không đổi dùng lại audio cũ, không tính phí lần nữa.

CÁCH CANH KHỚP
  - Mỗi câu vào đúng lúc lời gốc bắt đầu.
  - Câu dài: mượn tối đa 0,4 giây phía trước, rồi đọc nhanh hơn, tối đa theo thanh trượt (mặc định ×1,25).
  - Vẫn dài: Claude rút gọn và đọc lại riêng câu đó (chỉ khi có dịch; không dịch thì không sửa lời).
  - Vẫn lố: câu sau lùi lại, không bao giờ đè tiếng nhau. Bảng lời ghi rõ câu nào lố bao nhiêu giây.

CHỌN GIỌNG
  Danh sách chỉ hiện giọng đã có trong tài khoản. Mục "Tìm thêm giọng" tìm trong thư viện ElevenLabs theo ngôn ngữ,
  giới tính, miền; nghe thử rồi bấm Chọn để thêm vào tài khoản. Hoặc dán Voice ID.

KẾT QUẢ  output\<thời gian>_<tên>\
  <tên>_thuyetminh.mp4   video thành phẩm
  giong_doc.m4a          riêng giọng đọc, đặt đúng thời gian
  thuyet_minh.srt        phụ đề theo giọng đọc
  tts\ , pcm\            audio từng câu (bộ đệm chống trả tiền hai lần)
  Xoá thư mục đó là xoá kết quả.

GHI CHÚ
  - Dùng chung: model Whisper + ffmpeg của Video Cutter, API key ElevenLabs của Creater Vid
    (không có thì nhập key ngay trong tool, lưu ở settings.json).
  - Chạy bằng Python 3.14 mặc định (đã có faster-whisper, CUDA, numpy, Flask). Dịch dùng Claude CLI trong claude-cli.
  - Một giọng đọc cho cả video, không tách theo từng người nói.
