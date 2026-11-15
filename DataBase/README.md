# Hổ Báo Studio

Pipeline tự động cho kênh JRE Highlights: **video vào → transcript → chọn nội dung (Claude) → cắt → zoom → kho highlight**, quản lý qua giao diện web. Kế hoạch chi tiết và các quyết định: [PLAN.md](PLAN.md).

## Chạy

- Cách thường dùng: mở **Tool Manager** (`E:\Tool\run.pyw`) → thẻ **Hổ Báo Studio** → Start → Mở. Studio chạy ở `http://127.0.0.1:5004` và tự khởi động Cutter/Zoom/Downloader khi cần.
- Chạy tay: `E:\Tool\DataBase\.venv\Scripts\python.exe app.py`
- CLI cho Claude và cho người: `E:\Tool\DataBase\.venv\Scripts\python.exe hldb.py --help`

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
    orchestrator.py     4 làn chạy song song (GPU: Whisper/Zoom · Claude: chọn nội dung · Cắt clip · việc nhẹ), state machine mỗi tập
    intake.py           theo dõi thư mục media, tải URL qua Downloader
    transcribe.py       whisper_worker.py của Cutter (CUDA)
    select_ai.py        chon-noi-dung-jre-v2 headless (skill + transcript trong prompt) + validator + sửa lỗi bằng --resume
    cut.py  zoom.py     gọi Cutter (/api/cut-headless) và Zoom (/api/enqueue-path)
    claude_runner.py    chạy Claude Code CLI, bắt stream-json
    topic_scan.py       Compilation: quét chủ đề trên transcript tập full
    compile_video.py    Video tổng hợp: một đoạn → mạch nhiều tập + lời dẫn ElevenLabs → mp4
.claude/skills/         chon-noi-dung-jre-v2 (sync từ app desktop), kho-highlight (mới)
templates/ static/      UI
studio.db               database (không commit)
work/  logs/            file tạm, log
```

## Trạng thái tập (state machine)

`new → transcribing → selecting → [reviewing] → cutting → zooming → indexing → ready`, lỗi thì `failed:<bước>` và bấm "Chạy tiếp" trên UI. Bước nào đã có sản phẩm (transcript, cutlist, clip, bản zoom) thì tự bỏ qua.

## Bước Claude headless (người dùng làm một lần)

1. CLI đã cài tại `E:\Tool\claude-cli` (bản 2.1.280) bằng `npm i -g --prefix E:\Tool\claude-cli @anthropic-ai/claude-code`. Không cài vào `%APPDATA%\npm` từ bên trong app Claude desktop: app là gói MSIX nên thư mục đó bị ảo hoá, bên ngoài không thấy.
2. Đăng nhập: nhấn đúp `E:\Tool\DataBase\dang-nhap-claude.bat`, gõ `/login`, làm theo hướng dẫn trên trình duyệt, rồi `/exit`. Muốn token dài hạn cho script thì chạy `E:\Tool\claude-cli\claude.cmd setup-token` trong PowerShell và đặt biến môi trường `CLAUDE_CODE_OAUTH_TOKEN`.
3. Kiểm tra ở trang **Cài đặt** của Studio: dòng "Claude Code headless" phải báo CLI và token hoặc đã đăng nhập.
4. Chọn model ở cùng trang: model và effort riêng cho bước chọn nội dung và cho Hỏi AI (bí danh `fable`, `opus`, `sonnet`, `haiku` hoặc tên đầy đủ), model dự phòng khi quá tải. Để trống = model mặc định của Claude Code cho tài khoản. Nút "Kiểm tra" chạy một lượt nhỏ và in ra model thực tế trả lời; mỗi job chọn nội dung cũng ghi model, số token và thời gian vào cột thông báo.

Skill `chon-noi-dung-jre-v2` được copy tự động từ thư mục plugin của app desktop vào `.claude/skills/` trước mỗi lần chạy, nên luôn cùng phiên bản với bản chạy tay.

### Bước chọn nội dung tốn bao nhiêu và vì sao

Mỗi lần Claude gọi một công cụ là một request mới, đọc lại toàn bộ hội thoại từ đầu (phần đọc lại tính giá cache, rẻ nhưng cộng dồn rất nhanh), còn mọi chữ Claude viết ra là output, đắt và chậm (~100 token/giây). Ba lần chạy đầu (JRE-2368, 2551, 2558, opus xhigh) tốn 22–41 phút, 3,3–4,5 triệu token, 168–245 nghìn token output mỗi tập vì: đọc transcript từng khúc 400–800 dòng (6–8 request), mỗi request mang theo ~30 nghìn token của MCP (Premiere, Canva, ElevenLabs, Trello…), danh sách 49 skill và memory, chạy python tự kiểm tra rồi đi xem file của tập cũ, và viết phân tích ba lần (câu trả lời, `analysis_<id>.json` có cả `raw_md` lẫn từng mục tách riêng, cộng cutlist).

Cách chạy hiện nay:
- Toàn văn skill và toàn văn transcript nằm ngay trong prompt, không đọc file từng khúc.
- CLI chạy cô lập: `--strict-mcp-config`, `--disable-slash-commands`, `--tools Read,Write,Edit,WebSearch,WebFetch`, tắt auto-memory và connector claude.ai. Phần cố định mỗi request (system prompt, định nghĩa tool, danh sách skill/MCP) giảm khoảng 4 lần (lượt đo thử: ~31 nghìn xuống ~7 nghìn token).
- Chạy thử 2026-09-25 (45 phút đầu JRE-2558, tối đa 2 đoạn, opus xhigh): 3 request thay vì 15–20, 9 phút, 58 nghìn token viết ra (42 nghìn là suy nghĩ), $2.10; lượt sửa lỗi bằng `--resume` thêm 20 giây, $0.21.
- Phân tích (Guest Card + khối Mục VI của từng đoạn) chỉ in một lần trong câu trả lời, Studio tự tách và gắn vào từng đoạn. Ngoài cutlist, Claude chỉ ghi thêm `work\<id>\tags_<id>.json` rất nhỏ (content_rank, start, end, themes, entities).
- Studio tự kiểm tra cutlist. Có lỗi thì gửi danh sách lỗi vào đúng phiên cũ (`--resume`, cache còn nóng) để Claude sửa file, không chạy lại từ đầu.
- Cột thông báo của job ghi: tổng token (phần đọc lại cache), token viết ra (phần suy nghĩ), chi phí quy đổi, thời gian.
- Effort `xhigh` làm phần suy nghĩ chiếm 100–140 nghìn token mỗi tập (hơn nửa thời gian chạy). Muốn nhanh hơn nữa thì hạ effort bước chọn nội dung xuống `high` ở trang Cài đặt.

## Viết Title cho từng đoạn

- Trên trang tập, mỗi đoạn highlight có khối **📝 Title & metadata** với nút **Viết Title**. Nút này chạy skill `viet-tittle` bằng Claude headless cho đúng đoạn đó, mặc định model **opus**, effort high (đổi ở Cài đặt → Viết Title).
- Skill nhận đúng thứ nó cần như khi chạy tay: transcript của đoạn theo định dạng file `.txt` của Video Cutter (timestamp gốc + dòng "Thời gian: start → end") và cutlist của riêng đoạn đó cho Bước 0.
- Kết quả hiện ngay trên đoạn: title khuyên dùng, 3 title Format 1, 3 title Format 2, description, timestamps, tags kèm số ký tự, thumbnail, image prompt, mỗi phần có nút Copy, cùng toàn văn câu trả lời của skill. Mọi lượt đều được lưu trong bảng `segment_titles`, bấm "Viết lại title" để chạy lượt mới.
- Hàng đợi viết title chạy riêng, lần lượt từng đoạn, không chặn pipeline cắt và zoom. Nút "Viết Title cho mọi đoạn" ở đầu danh sách xếp tất cả đoạn chưa có title vào hàng đợi.
- **Chat để chỉnh metadata**: dưới kết quả có ô nhắn Claude (Ctrl+Enter để gửi), ví dụ "title ngắn hơn", "đưa keyword lên đầu", "thêm tag …", "description giọng kịch tính hơn", hay hỏi "vì sao chọn keyword này?". Mỗi tin nhắn tiếp tục đúng phiên Claude đã viết title (`--resume`, Claude nhớ skill, transcript và bản vừa viết), Claude sửa thẳng file JSON kết quả, trang hiện ngay bản mới và cả luồng hỏi đáp. Mỗi tin nhắn là một lượt mới trong `segment_titles` (`parent_id`, `user_message`), nên mọi phiên bản đều còn trong database. Lượt title viết trước khi có tính năng này chưa lưu phiên: tin nhắn đầu tiên mở phiên mới kèm skill, transcript và kết quả cũ, các tin sau nối tiếp phiên đó.
- Lượt Viết Title chạy Claude ở chế độ cô lập như bước chọn nội dung (skill nằm trong prompt, không MCP, không danh sách skill), request đầu còn ~42 nghìn token thay vì ~61 nghìn. Chạy thử 2026-09-27: chat tiếp đúng phiên 8–16 giây, $0.04–0.05 mỗi tin; tin đầu tiên trên lượt cũ (mở phiên mới) 21 giây, $0.44.

## Khách mời theo nhóm chuyên môn

- Tab **Khách mời** xếp khách vào 20 nhóm theo kiểu JRE: UFO/UAP, lịch sử cổ đại, tôn giáo, chính trị, quân đội & tình báo, MMA, diễn viên hài, khoa học & vũ trụ, AI, sức khỏe, psychedelics, bí ẩn & mất tích, điều tra & tố giác, săn bắn, tâm lý & triết học, giải trí, kinh doanh, thể thao, tội phạm & nhà tù, khác (`studio/guests.py`, bảng `guest_groups` + `guests`).
- Nhóm đi theo **clip** của khách, không theo nghề, vì nhóm dùng để dựng playlist, tập tổng hợp và chọn tập nên làm tiếp. Claude nhận Guest Card (định danh, archetype, chuyên môn cấp 1, khán giả muốn nghe) cùng mọi highlight đã chọn (điểm cuối, theme chính, keyword, title) và phân bố highlight theo nhóm. Nhóm chính = nơi có nhiều clip mạnh nhất (diễn viên hài luôn là hài, võ sĩ luôn là MMA); nhóm phụ (tối đa 2, hiện mờ) cần ít nhất 2 clip, không bao giờ vì khách là YouTuber, host, nhà đầu tư hay tác giả. Code còn chốt chặn: nhóm phụ nào không clip nào của khách chạm tới thì bị bỏ. Dòng "clip:" dưới mỗi khách đếm highlight theo theme chính. Khách xuất hiện nhiều tập được gộp theo tên; "A & B" là hai khách.
- Claude xếp nhóm: khách của tập mới được xếp ngay trong bước chọn nội dung (khóa `guests` của `tags_<id>.json`); khách cũ bấm **Phân nhóm N khách bằng Claude** (một lượt opus, không công cụ). **Sửa nhóm** để chọn tay; khách sửa tay không bị Claude đổi khi bấm "Phân nhóm lại tất cả".
- "xem highlight →" mở trang Tìm kiếm lọc theo nhóm (bộ lọc "Nhóm khách" mới), trang tập hiện nhãn nhóm cạnh tên khách, `hldb guests [--group slug]` và `hldb search --group slug` cho skill kho-highlight.

## Video tổng hợp (một đoạn → tập tổng hợp dài)

- Bấm **🧩 Tạo video tổng hợp** trên một đoạn highlight (trang Tập, trang Tìm kiếm) hoặc tìm đoạn ở tab **Video tổng hợp**. Chọn thời lượng (30, 60, 90, 120 phút hoặc số khác) và ghi chú cho Claude nếu muốn (`studio/pipeline/compile_video.py`, bảng `compile_jobs`, `compile_candidates`, `compile_items`).
- Các bước tự chạy:
  1. **Chủ đề**: Claude đọc đoạn đã chọn (title, tóm tắt, transcript) và đặt chủ đề, mạch lớn, 15–30 từ khoá tiếng Anh (mặc định sonnet, effort low).
  2. **Quét mọi tập**: lọc từ khoá trên toàn bộ transcript ngay trên máy (bộ lọc của Compilation), mỗi chỗ khớp lấy ±120 giây; Claude chỉ đọc các vùng đó theo lô và chọn đoạn 1–12 phút thật sự đúng chủ đề (sonnet, medium). Vùng của chính đoạn mở đầu bị loại. Vượt ngân sách `compile_max_scan_tokens` (mặc định 600 nghìn token) thì bỏ các vùng ít khớp nhất.
  3. **Dựng mạch + lời dẫn**: Claude (opus, high) xếp đoạn bạn chọn làm clip 1, các đoạn liên quan theo dòng leo thang (setup → đào sâu → nghi vấn → payoff, Rogan làm trục nối, ghép quan điểm đối lập), cộng thời lượng cho khớp yêu cầu; viết lời dẫn tiếng Anh dạng prompt ElevenLabs v3 có audio tag: INTRO ngay sau clip 1, BRIDGE giữa mỗi cặp clip, OUTRO cuối video. Quy tắc lời dẫn lấy từ skill `tong-hop-rabbit-hole` (không tóm tắt lại clip vừa xong, không nói trước câu đắt của clip sau, không bịa dữ kiện).
- Dừng ở trạng thái **review**: sửa title, INTRO/BRIDGE/OUTRO (bấm ra ngoài ô là lưu), bỏ tick hoặc đổi thứ tự clip, thêm ứng viên chưa dùng, nhắn yêu cầu rồi **Dựng lại mạch** (không quét lại), hoặc sửa từ khoá rồi **Quét lại**. Thanh tổng hiện thời lượng clip + lời dẫn so với yêu cầu.
- **🎬 Dựng video**: lời dẫn đọc bằng ElevenLabs qua `gen.py` của Creater Vid (key ElevenLabs và giọng tiếng Anh của Creater, model `eleven_v3`; đổi giọng ở Cài đặt bằng `compile_voice_id`), **mọi clip đều là bản zoom**: đoạn nằm trong một highlight đã zoom thì cắt thẳng từ bản `_zoomed.mp4` đó; chưa có bản zoom thì Studio cắt đoạn ở kích thước gốc rồi gửi Podcast Zoom (cùng thiết lập zoom của pipeline, file `parts\zoom_*.mp4`, lần dựng sau dùng lại) trước khi ghép (`compile_require_zoom` = 0 để tắt). Trang duyệt ghi rõ từng clip "có bản zoom" hay "sẽ zoom khi dựng". Clip được cắt bằng ffmpeg từ bản zoom đó, lời dẫn hiện thành khung chữ trên ảnh mờ của clip kế tiếp, mọi phần chuẩn hoá 1920x1080 30fps, AAC 48 kHz, loudnorm −16 LUFS (NVENC nếu GPU mã hoá được), rồi ghép thành một file. Phần đã làm được dùng lại khi dựng lại (chỉ phần sửa mới làm lại).
- Kết quả trong `<media_root>\_tong-hop\video-<id>-<chủ đề>\`: `<title>.mp4`, `chapters.txt` (mốc chương cho description YouTube, có nút Copy trên trang), `compilation_<slug>.json` (mạch + lời dẫn), `cut_multi_<slug>.json` (cho Video Cutter), thư mục `parts\`.
- Model, effort, vùng đệm, ngân sách token, giọng, model TTS, chữ trên khung lời dẫn, bộ mã hoá: các khoá `claude_model_compile_*`, `claude_effort_compile_*`, `compile_*` trong bảng settings (mặc định ở `studio/config.py`).
## Phim tài liệu bổ sung (highlight + hook → câu nối → phim tài liệu)

- Trên trang tập, đoạn highlight đã **nối hook vào bản zoom** có nút **🎞 Làm phim tài liệu** (`studio/pipeline/doc_extend.py`, bảng `docext_jobs`). Chọn bản có hook (`…_HOOKnn.mp4`), thời lượng phim (phút, gần đúng, mặc định `docext_target_min` = 10), ngân sách nguyên liệu USD (trống = mặc định của Creater), ghi chú, câu nối tự viết (không bắt buộc), Tự chạy hay duyệt từng bước, có cho dùng kho highlight JRE không.
- Studio tạo dự án trong **Creater Vid** (tự bật Creater nếu đang tắt): mảng Phim tài liệu, cách dựng `dossier` (hồ sơ tư liệu thật), tiếng Anh 16:9, tư liệu `sources/highlight.md` = tóm tắt, khối phân tích và transcript nguyên văn của đoạn. Brief yêu cầu phim là chương tiếp theo: không kể lại highlight, không giới thiệu lại Rogan/khách, bám đúng văn bản, hiện vật, giả thuyết được nhắc, bổ sung bằng chứng gốc, phản biện học thuật, kiểm chứng khẳng định, không dùng lại clip của chính đoạn đó. Rồi chạy bước 1.
- Studio theo dõi dự án mỗi 30 giây (đọc thẳng `creater.db`), trang tập hiện bước Creater đang làm và nút **Mở dự án Creater** để xem, nhắn sửa, duyệt. Bước 6 · Dựng & render được **duyệt** (Tự chạy tự duyệt sau QA; chế độ từng bước thì bạn duyệt trong Creater) thì lấy bản render mới nhất.
- Nối: Claude viết **một câu nối** (mặc định sonnet, effort low: `claude_model_docext_bridge`, `claude_effort_docext_bridge`) từ 90 giây cuối của highlight và phần mở đầu kịch bản phim; ElevenLabs đọc (cùng giọng `compile_voice_id` với Video tổng hợp), hiện thành khung chữ trên ảnh mờ của phim. Ghép **[highlight + hook] → [câu nối] → [phim tài liệu]** thành `…_HOOKnn_DOC.mp4` cạnh bản có hook. File highlight + hook không bị sửa; bản ghép được mã hoá lại một lần ở 1080p, đúng fps của bản có hook, AAC 48 kHz.
- **↻ Nối lại**: dùng bản render mới nhất của Creater (VD sau khi nhắn sửa ra v2 và duyệt lại) và câu nối trong ô (xoá trống = Claude viết lại). **Dừng theo dõi** chỉ dừng phía Studio, dự án Creater giữ nguyên.
- Chi phí: Claude của Creater (hai phim dossier gần đây tốn ~$42 và ~$66 quy đổi mỗi phim) + nguyên liệu trong ngân sách của dự án; câu nối của Studio vài cent.

- Tab Phim tài liệu cũ đã gỡ (trùng chức năng với Creater Vid). Code, template và engine cũ nằm ở `backups\docfilm_removed_20261027\`; các bảng `docfilm_*` vẫn còn trong `studio.db`, phim đã làm ở `K:\VideoLab\docfilms` giữ nguyên.

## Quét kênh tự động (hẹn giờ + keyword)

- Cài đặt → Show podcast → mở một show → khối **📡 Quét kênh tự động** (`studio/channel_watch.py`, bảng `channel_watch`, `channel_videos`). Dán link kênh chính (vd `https://www.youtube.com/@joerogan`, Studio tự đọc tab `/videos`: không Shorts, không live), tick **Bật hẹn giờ quét**, **Lưu lịch quét**.
- Hẹn giờ: giờ cố định trong ngày (`06:00, 18:30`) hoặc để trống và đặt chu kỳ N giờ. Luồng nền kiểm tra mỗi phút, đến giờ thì dùng yt-dlp (Python 3.14) liệt kê N video mới nhất, không tải gì.
- Lọc: keyword cần lấy (khớp tiêu đề, không phân biệt hoa thường, trống = mọi video mới), keyword loại trừ, bỏ video ngắn hơn X phút, tối đa M video mỗi lượt (phần dư lượt sau lấy tiếp, cũ trước mới sau). Video đang live/sắp công chiếu để lượt sau.
- Video giữ lại được tải qua Downloader vào `Full\` rồi chạy pipeline như dán link ở trang Hàng đợi (transcript → chọn nội dung → cắt → zoom → index). Tiêu đề khớp mẫu tên show khác thì vào show đó (kênh PowerfulJRE có cả JRE, JRE MMA Show, Protect Our Parks); tập đã có trong Studio thì bỏ qua.
- **Lần quét đầu chỉ ghi nhận video đang có** trên kênh (không kéo cả kho cũ). Nút **Xem video đã quét** liệt kê từng video và lý do bỏ qua, nút **Tải + index** để lấy tay một video bất kỳ. **Quét ngay** chạy một lượt ngoài lịch. Đổi link kênh thì danh sách cũ bị xoá và quét lại từ đầu.

## Dịch khi bôi đen (Google Dịch)

- Bôi đen chữ tiếng Anh ở bất kỳ trang nào, bấm nút **🌐 Dịch** hiện cạnh đoạn chọn. Khung bản dịch có nút Copy, nút mở Google Dịch và ô "Tự dịch ngay khi bôi đen" để bỏ bước bấm nút. Esc hoặc bấm ra ngoài để đóng.
- Dịch ngay trong Studio cần **API key chính thức** của Google Cloud Translation, dán ở Cài đặt → Google Dịch khi bôi đen. Key chỉ gửi tới `translation.googleapis.com`, trang Cài đặt không hiện lại key.
- Chưa có key thì nút Dịch mở translate.google.com trên trình duyệt với đoạn đã chọn.
- Dịch vụ Google Dịch không cần key đã bị Google chặn cho mạng này bằng trang "unusual traffic", nên Studio không dùng nó.

## Sao lưu, làm sạch, khôi phục

- Trang **Cài đặt → Làm sạch dữ liệu**, hoặc `hldb reset --yes`: sao lưu `studio.db` vào `backups\` rồi xóa mọi tập, đoạn, transcript, theme đã gán, job. Giữ cài đặt và danh sách theme. Không đụng tới file trên đĩa.
- `hldb backup`: sao lưu thủ công. `hldb restore backups\studio_<thời gian>.db`: khôi phục (tự sao lưu trạng thái hiện tại trước).
- Cutlist cũ (không có `cutlist_layout: flat_hooks`) nằm trong thư mục media sẽ không được dùng lại: pipeline đổi tên thành `.old_…` và cho Claude chọn lại bằng skill hiện hành.

## Dừng và khởi động lại

- Nút **Dừng** ở trang Hàng đợi và trang tập: bỏ tập khỏi hàng đợi, hoặc dừng bước đang chạy ở điểm an toàn gần nhất (Claude bị dừng ngay, Cutter/Zoom làm nốt đoạn đang xử lý).
- Khởi động lại Studio giữa chừng là an toàn: tập đang dở tự vào lại hàng đợi, bước cắt chờ Cutter xong việc cũ và dùng lại clip đã có, bước zoom dùng lại job Zoom đang chạy.
- Clip chỉ được tính là xong khi ffprobe mở được. Clip bị ghi dở (Cutter bị ngắt giữa chừng, lỗi "moov atom not found") được đưa vào Thùng rác và cắt lại ở lần "Chạy tiếp" sau; bản zoom render dở cũng vậy. Việc này chỉ làm khi Cutter đang rảnh, không đụng file đang ghi.

## Xoá đoạn

- Trang tập: nút **🗑 Xoá đoạn** trong từng đoạn, nút **✕** cạnh từng hook, hoặc tick ô bên trái nhiều đoạn rồi bấm **Xoá đoạn đã chọn**. Xoá một highlight thì các hook của nó đi theo.
- Đoạn đã xoá không hiện trên trang tập, trong tìm kiếm, trong các con số; bước cắt và zoom bỏ qua, "Chạy tiếp" nạp lại cutlist cũng không làm nó hiện lại (trạng thái `archived`). File cutlist trong thư mục media giữ nguyên.
- Hộp xác nhận có ô **chuyển luôn file clip (bản gốc + bản zoom) vào Thùng rác của Windows**. Không tick thì file vẫn nằm trên ổ đĩa.
- Mục **Đoạn đã xoá** cuối trang tập có nút **Khôi phục**. Đoạn khôi phục mà file đã vào Thùng rác sẽ được cắt và zoom lại khi bấm "Chạy tiếp pipeline".
- Template tự nạp lại khi sửa; sửa file `.py` thì cần Stop rồi Start Studio.

## Sửa đổi ở tool cũ

- Video Cutter: endpoint `POST /api/cut-headless` (không mở hộp thoại, không đụng trạng thái UI), tham số `write_sidecars` (mặc định tắt) và ô chọn "Xuất kèm transcript + manifest" trên giao diện tay, `index` cố định số thứ tự file clip.
- Podcast Zoom: `generate_thumbnail` mặc định tắt, endpoint `POST /api/enqueue-path` nhận đường dẫn và ghi thẳng ra `output_path`, không xoá file gốc.
- Tool Manager: thẻ Hổ Báo Studio, mọi tool có `.venv` tự dùng interpreter riêng.
