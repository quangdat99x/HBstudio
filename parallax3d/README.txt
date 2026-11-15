PARALLAX 3D TỪ MỘT ẢNH TĨNH
==========================

Ảnh -> bản đồ độ sâu (Depth Anything V2 Large) -> tách lớp ở các mép đứt gãy độ sâu,
vá nền phía sau từng lớp -> dựng lại trong không gian 3D -> camera điện ảnh -> MP4.

Chạy bằng Python của bgremove (có PyTorch CUDA + model đã tải về E:\Tool\bgremove\hf):

  set PY=E:\Tool\bgremove\.venv\Scripts\python.exe
  %PY% depth.py     work\source.png work        (1) bản đồ độ sâu    -> work\depth.png
  %PY% layers.py    work                        (2) tách lớp + vá    -> work\_layers_sheet.png
  %PY% render.py    work cinematic_parallax.mp4 (3) camera 3D, 10 s  (thêm --stills để xem nhanh 3 khung)
  %PY% breakdown.py work cinematic_parallax.mp4 breakdown_and_shot.mp4   (4) đoạn phân tích + cảnh chính

Ảnh khác: đặt vào work\source.png (hoặc thư mục work mới) và chạy lại 4 bước.
Thông số camera ở đầu render.py đang chỉnh cho ảnh hai nhạc công:
  FRAME_CENTER  điểm ảnh làm tâm khung hình
  TARGET_DISP   độ sâu của chủ thể mà camera xoay quanh (0 = trời, 1 = sát ống kính; xem work\depth.png)
  CAM_FROM/TO   vị trí đầu/cuối camera (x trái-phải, y lên-xuống, z tiến-lùi), zoom
  FOCUS_DISP, DOF  lấy nét và độ nhòe hậu cảnh/tiền cảnh
  SKY_DRIFT     mây trôi bao nhiêu pixel
