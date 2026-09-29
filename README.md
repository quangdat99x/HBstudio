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
    select_ai.py        chon-noi-dung-jre-v2 headless (skill + transcript trong prompt) + validator + sửa lỗi bằng --resume
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

## Phim tài liệu (Make Documentary Film)

- Tab **Phim tài liệu** quản lý các dự án phim tài liệu dựng từ kho highlight (`studio/docfilm/`, bảng `docfilm_projects`, `docfilm_messages`, `docfilm_rules`). **＋ Dự án mới**: tên, chủ đề (dùng để tìm trong kho), yêu cầu riêng, định dạng 16:9/9:16, thời lượng, ngân sách credit Higgsfield.
- Mỗi dự án là **một cuộc trò chuyện liên tục với Claude** (một phiên Claude Code, mọi lượt `--resume`), giống chat trong app. Ba nút bước:
  1. **Tìm đoạn đắt giá**: Studio tìm trong kho (FTS theo cả chủ đề, từng cặp từ, từ khóa tiếng Anh, theme khớp tên) rồi xếp theo độ khớp × điểm chất lượng, ghi `research/pool.json` cùng transcript từng đoạn có timestamp chính xác. Claude đọc, tìm thêm bằng `hldb` nếu cần, chọn câu trích **nguyên văn** (kiểm chứng bằng python), ghi `research/selection.json` + `.md` và đề xuất dàn ý.
  2. **Viết kịch bản**: `script/script.json` + `.md`, xương sống là các câu trích JRE, lời dẫn chỉ nối và đặt bối cảnh, kèm danh sách ảnh Higgsfield và ước tính credit. Claude dừng ở cổng duyệt: nhắn "duyệt" thì mới dựng.
  3. **Dựng phim**: Studio dựng khung `film/` từ engine (`docfilm/engine`: Remotion + three.js multiplane, xem `docfilm/engine/ENGINE.md`). Claude:
     - tạo ảnh bằng Higgsfield trong ngân sách và **tách nền trên máy** (`scripts/cutout.py`, BiRefNet trên GPU, 0 credit);
     - làm **lời dẫn ElevenLabs v4** qua Higgsfield (giọng mặc định Alistair, một lần đọc cả kịch bản, phụ đề hiện theo từng chữ được đọc, nhạc tự hạ dưới giọng);
     - dựng **lửa và khói bằng cảnh quay thật** trên nền đen (chỉ tải sau khi người dùng duyệt trong chat), kèm tia lửa, ánh lửa hắt sáng, bloom, không khí méo;
     - cắt clip trích, viết cảnh, soát ảnh tĩnh, render `out/<slug>_v<N>.mp4` và chạy QA.
  Nhắn bất cứ lúc nào để sửa ("cảnh 3 cánh đập mạnh hơn", "bỏ đoạn 87"…). Cột phải hiện kết quả: video, kịch bản, đoạn chọn, ứng viên, ảnh soát.
- **Bộ quy tắc** (`RULEBOOK.md` trong thư mục dự án gốc, mặc định `D:\VideoLab\docfilms`; bản đầu ở `docfilm/RULEBOOK.seed.md`): viết ra từ mọi lần người dùng sửa phim (tính xác thực và nguồn, biểu tượng nhạy cảm, ảnh Higgsfield và chi phí, không gian 3D, chuyển động, neo vật thể, chữ, âm thanh, kiểm tra trước khi giao). Mọi lượt Claude nhận toàn văn; quy trình từng bước nằm ở mục 2 nên sửa quy tắc là sửa quy trình, không cần sửa code. Nhắn "cập nhật quy tắc: …" trong chat để Claude ghi thêm, hoặc sửa tay ở trang Bộ quy tắc. Mỗi lần đổi là một phiên bản (ai sửa, dự án nào), xem và khôi phục được.
- Lượt Claude của tab này giữ các connector claude.ai để dùng **Higgsfield** (chỉ các tool tạo ảnh, tạo giọng đọc, tách nền, số dư, lịch sử tạo, project được cho phép sẵn; TikTok, website… bị chặn), bỏ danh sách slash command và auto-memory. Model/effort, số lượt công cụ, ngân sách credit mặc định, thư mục dự án: Cài đặt → Phim tài liệu. Engine cài một lần (`npm install` trong `docfilm/engine`, Studio tự chạy nếu thiếu); mỗi phim có bản copy `src/` + `scripts/` và junction tới `node_modules` dùng chung.
- Công cụ ngoài repo mà lượt dựng dùng qua biến môi trường:
  - `BGREMOVE_PY`: Python của `E:\Tool\bgremove\.venv` (torch CUDA, transformers, pymatting, scipy, opencv; model BiRefNet trong `E:\Tool\bgremove\hf`). Đổi đường dẫn ở Cài đặt → Phim tài liệu.
  - `WHISPER_PY`: Python của Cutter (faster-whisper), cho `scripts/voice-build.py`.
- Phim mẫu tham chiếu: `D:\VideoLab\watchers-v2` (The Watchers v2.1).

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
- Tool Manager: thẻ JRE Studio, mọi tool có `.venv` tự dùng interpreter riêng.
