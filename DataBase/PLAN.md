# KẾ HOẠCH V2: JRE Studio. Pipeline tự động từ video đến clip zoom + database + UI

- Ngày lập: 2026-09-23 (v2, thay thế bản v1 cùng ngày; phần database của v1 giữ nguyên ở Mục 7)
- Trạng thái: ĐÃ DUYỆT 2026-09-23, quyết định A đến F như đề xuất, kèm 3 điều chỉnh của người dùng:
  1. Tool zoom bỏ hẳn chức năng tạo thumbnail (mặc định tắt, bản zoom chỉ ra file mp4).
  2. Cutter không ghi 3 file phụ mỗi clip (`.txt`, `.json`, `.manifest.json`) nữa; chỉ ghi khi bật ô "Xuất kèm transcript + manifest" cho luồng viet-prompt-v2.
  3. Khối phân tích của skill chọn nội dung (Tóm tắt, Tại sao đắt, Hook cold open, Keyword, Fit) được lưu nguyên văn vào database cho từng đoạn (`segments.analysis_md` + `analysis_json`), lấy từ câu trả lời của lần chạy headless (Studio tự tách từng khối, từ 2026-09-25 không bắt Claude ghi thêm bản sao `analysis_<id>.json` nữa, xem README mục "Bước chọn nội dung tốn bao nhiêu") hoặc dán tay trên UI.
- Tiến độ triển khai: xem Mục 12.
- Phạm vi: CHỈ JRE (Joe Rogan Experience và JRE MMA Show). Không làm SRS, GoodHang hay podcast khác.
- Thư mục dự án: `E:\Tool\DataBase` (code + `studio.db`), đăng ký vào Tool Manager `E:\Tool\run.pyw` làm tool thứ 4, port 5004.

## 0. Mục tiêu

Đầu vào: 1 file video JRE (thả vào thư mục hoặc dán URL YouTube).
Đầu ra: thư mục tập chứa clip đã cắt, bản zoom, thumbnail, sidecar; tất cả đã vào database; quản lý qua UI.
Không thao tác tay ở giữa. Hai việc cần AI (chọn nội dung, hỏi đáp kho) chạy Claude Code ở chế độ headless.

## 1. Quy trình hiện tại và quy trình mục tiêu

| # | Bước | Hiện tại (tay) | Mục tiêu (tự động) | Cách nối kỹ thuật |
|---|---|---|---|---|
| 1 | Tải video | Mở YouTube Downloader, dán URL, chọn thư mục | Dán URL trong UI Studio, hoặc thả file vào watch folder | Gọi API `/api/download` của Downloader (port 5001), hoặc watchdog trên `K:/YouTube/` |
| 2 | Transcript | Mở Cutter, chọn video, bấm Whisper, lưu transcript | Tự chạy khi file ổn định | Subprocess `whisper_worker.py` (large-v3, CUDA) của Cutter; orchestrator ghi `.transcript.json` + `.txt` đúng format hiện tại |
| 3 | Chọn nội dung | Dán transcript vào Claude, chạy skill, tải cutlist về | Tự chạy | `claude -p "/chon-noi-dung-jre-v2 ..."` headless, validate JSON, retry |
| 4 | Cắt | Import cutlist vào Cutter, chọn nơi lưu, bấm cắt | Tự chạy | Thêm 1 endpoint headless vào Cutter (nhận `video_path` + `cutlist_path` + `output_folder`, không mở hộp thoại) |
| 5 | Zoom | Mở Podcast Zoom, upload từng clip, chờ, tải về | Tự chạy | POST `/api/upload` của Zoom (port 5003), poll `/api/status`, auto-save vào thư mục tập |
| 6 | Sắp xếp + DB | Không có | Tự chạy | Ingest cutlist + sidecar + bản zoom vào `studio.db`, FTS5 |
| 7 | Quản lý | Mở từng file, đưa JSON cho Claude | UI Studio | Hàng đợi, tập, tìm kiếm, compilation, hỏi AI |

## 2. Số liệu đã đo trên máy này

| Bước | Số liệu thật | Nguồn |
|---|---|---|
| Whisper large-v3 trên RTX 4060 8GB | 20 đến 30 phút cho 1 tập ~3 giờ | `cutter.log`: khoảng cách transcribe → save-transcript các ngày 09/2026 |
| Zoom (mediapipe + render) | 481 giây cho clip 27 phút, tức ~3,4 lần realtime | `podcast-zoom-tool/debug.log` 2026-09-23 |
| Cắt (ffmpeg stream copy) | vài giây mỗi clip | `cutter.log` |
| Chọn nội dung bằng Claude | ước 5 đến 15 phút/tập, chưa đo headless | |

Ước tính một tập 3 giờ, 8 đoạn + hook, tổng ~2 giờ clip: 25 phút transcript + 10 phút AI + 40 phút zoom, khoảng 1 giờ 15 phút hoàn toàn tự động. GPU dùng tuần tự.

## 3. Kiến trúc

```
 [Thả file / dán URL]                [Tool cũ, giữ nguyên, gọi qua HTTP/subprocess]
        |                              Downloader :5001   Cutter :5002   Zoom :5003
        v                                   ^                ^              ^
 +----------------------- JRE Studio (E:\Tool\DataBase, port 5004) --------------------------+
 |  watchdog  -->  Orchestrator (worker nền, state machine mỗi tập, hàng đợi trong SQLite) |
 |                    |  transcribe --> select (claude -p) --> cut --> zoom --> index      |
 |                    v                                                                     |
 |               studio.db (SQLite + FTS5: episodes/segments/themes/jobs/settings)          |
 |                    ^                                                                     |
 |  UI Flask: Hàng đợi | Tập | Tìm kiếm | Compilation | Hỏi AI (claude -p "/kho-highlight") |
 +-----------------------------------------------------------------------------------------+
```

Thành phần:

- **Orchestrator**: Python 3.12 (venv riêng, cùng cách Tool Manager bootstrap venv). Worker nền, mỗi tập là một state machine, hàng đợi lưu trong SQLite nên tắt máy bật lại vẫn chạy tiếp, có retry và log từng bước.
- **Tool cũ giữ nguyên**: Downloader, Cutter, Zoom chạy như hiện nay. Orchestrator tự khởi động tool nếu port chưa mở, dùng đúng `_tool_server.py` mà `run.pyw` đang dùng. Mỗi tool chạy bằng interpreter của nó (Cutter: Python 3.14 qua `py` có faster-whisper; Zoom: venv 3.12.10), orchestrator không import chéo.
- **Claude Code CLI**: cài qua npm (bản 2.1.280, cùng phiên bản với app desktop đang chạy). Dùng cho bước chọn nội dung và Hỏi AI.
- **studio.db**: schema kho highlight của v1 cộng bảng `jobs`, `job_events`, `settings`.
- **UI**: Flask + templates giống các tool hiện có, mở qua pywebview hoặc trình duyệt.

Vì sao giữ tool cũ thay vì viết lại: sidecar và manifest của Cutter đang được `viet-prompt-v2` dùng; pipeline zoom (mediapipe, smoothing, speaker detect) đã tinh chỉnh; giảm rủi ro. Chỉ sửa nhỏ:
1. Cutter: thêm endpoint `POST /api/cut-headless` nhận `video_path`, `cutlist_path`, `output_folder`; phần cắt và ghi sidecar dùng lại `_run_cutting` nguyên bản.
2. Zoom (tuỳ chọn): thêm endpoint nhận đường dẫn file thay vì upload, để không copy 1 GB qua HTTP. Zoom tool xoá file input sau khi xử lý, nên endpoint này phải copy vào `uploads/` rồi xử lý, không đụng file gốc.

## 4. State machine mỗi tập

```
new -> downloading -> transcribing -> selecting -> [reviewing] -> cutting -> zooming -> indexing -> ready
                                                                                   \-> failed:<stage> (retry n lần, rồi chờ người dùng)
```

Quy tắc:

- Chỉ nhận file khớp regex `Joe Rogan Experience #NNNN - <guest>` hoặc `JRE MMA Show #NNN with <guest>`; suy `episode_id` = `JRE-NNNN` / `JREMMA-NNN`, `guest` từ tên file.
- File phải ổn định (kích thước không đổi trong 30 giây, không có `.part`) mới vào hàng đợi.
- Bỏ qua bước nếu sản phẩm đã có: transcript có sẵn thì không chạy Whisper, cutlist có sẵn thì không gọi Claude, clip có sẵn thì không cắt lại. Nhờ vậy 18 tập đang có trên đĩa đi qua cùng state machine để backfill.
- `reviewing` là cổng duyệt tuỳ chọn (setting): bật thì cutlist hiện trên UI chờ bấm duyệt mới cắt; tắt thì chạy thẳng.
- GPU lock: Whisper và Zoom không chạy đồng thời. Nhiều tập thì chạy gối nhau theo làn (GPU / Claude / Cắt clip / việc nhẹ): tập 1 đang chờ Claude thì tập 2 đã Whisper; mỗi tập chỉ chạy một bước tại một thời điểm.

## 5. Bước AI chọn nội dung (headless)

Đã xác minh theo tài liệu chính thức Claude Code (headless.md, skills.md, authentication.md):

- `claude -p` hỗ trợ gọi skill bằng `/skill-name` ngay trong prompt; skill trong `.claude/skills/` của thư mục dự án được nạp tự động (trừ khi dùng `--bare`).
- Flag có thật: `--output-format json`, `--max-turns`, `--allowedTools`, `--permission-mode acceptEdits|dontAsk|bypassPermissions`, `--append-system-prompt-file`, `--mcp-config`.
- Input lớn: đưa đường dẫn file cho Claude tự Read, không pipe qua stdin (giới hạn 10 MB, và transcript 200 đến 600 KB đọc bằng Read ổn hơn).
- Xác thực cho script: `claude setup-token` tạo token 1 năm từ chính tài khoản Claude đang dùng, đặt vào biến môi trường `CLAUDE_CODE_OAUTH_TOKEN`. Dự phòng: `ANTHROPIC_API_KEY`, trả theo token. Người dùng tự đăng nhập và tạo token; tool không lưu hay xử lý credential.

Cách làm:

1. Cài CLI: `npm i -g @anthropic-ai/claude-code`, đăng nhập, chạy `claude setup-token`.
2. Sync skill: script copy `SKILL.md` của `chon-noi-dung-jre-v2` từ thư mục plugin của app desktop vào `E:\Tool\DataBase\.claude\skills\chon-noi-dung-jre-v2\`, để luôn cùng phiên bản với bản đang dùng tay.
3. Lệnh minh hoạ:

```text
claude -p "/chon-noi-dung-jre-v2 <prompt headless>" ^
  --output-format json --permission-mode acceptEdits ^
  --allowedTools "Read,Write,Glob,Grep,WebSearch,WebFetch" --max-turns 60
```

4. Prompt headless cung cấp sẵn mọi thứ skill hay hỏi: đường dẫn transcript, `episode_id`, `guest`, `source_video`, nơi ghi cutlist, số đoạn tối đa; kèm luật: không hỏi lại, tự quyết theo mặc định của skill, Guest Card research bằng WebSearch, ghi đúng một file `cutlist_<id>.json`.
5. Validator sau khi chạy: JSON đúng layout `flat_hooks`; `start < end`; nằm trong thời lượng video (ffprobe); hook nằm trong đoạn cha; không chồng lấn; `kind` và `title` đầy đủ. Sai thì chạy lại 1 lần kèm danh sách lỗi; vẫn sai thì `needs_review`, UI cho sửa tay rồi tiếp tục.
6. Ghi lại `usage` từ output JSON để theo dõi token mỗi tập.

Giới hạn cần biết: bước này dùng quota của gói subscription; một tập tốn vài trăm nghìn token; chạy tuần tự, không song song nhiều tập.

## 6. Cắt và zoom

- Cắt: endpoint headless của Cutter, output `K:/YouTube/<tên video>/NN_title.mp4` + `.txt` + `.json` + `.manifest.json`, giữ nguyên convention hiện nay.
- Zoom: gọi `/api/set-output-dir` = thư mục tập; upload lần lượt từng clip với tham số từ settings (`zoom_factor`, `smoothing_speed`, `analysis_fps`, `max_faces`, `min_switch_duration`, `mar_threshold`); poll `/api/status/<job_id>`; kết quả `<name>_zoomed.mp4` + `<name>_zoomed_thumbnail.jpg`.
- Hook có zoom hay không: setting, mặc định có (hiện tại đang zoom lẫn lộn, có hook zoom có hook không).
- Dung lượng: bản zoom xấp xỉ bản gốc, tức 5 đến 6 GB mỗi tập. UI cảnh báo khi ổ E còn dưới ngưỡng cấu hình.

## 7. Database

Giữ nguyên schema kho highlight của bản v1: `podcasts`, `episodes`, `segments`, `topics`, `segment_topics`, `themes`, `segment_themes`, `entities`, `segment_entities`, `segment_search` + `segments_fts` (FTS5, tokenizer `unicode61 remove_diacritics 2`, cột `ascii_text` cho tiếng Việt không dấu), `compilations`, `compilation_items`, `publications`, `ingest_log`. Nguyên tắc không đổi: cột lõi + `extra_json` + `raw_json`; định danh đoạn `(episode_id, kind, start_sec, end_sec)`; không tự xoá.

Thêm cho pipeline:

```sql
CREATE TABLE jobs (
  id INTEGER PRIMARY KEY, episode_id TEXT NOT NULL, stage TEXT NOT NULL,
  status TEXT NOT NULL, progress REAL DEFAULT 0, message TEXT, attempts INTEGER DEFAULT 0,
  started_at TEXT, finished_at TEXT, error TEXT
);
CREATE TABLE job_events (id INTEGER PRIMARY KEY, job_id INTEGER, ts TEXT, level TEXT, message TEXT);
CREATE TABLE settings   (key TEXT PRIMARY KEY, value TEXT);
```

`segments.status` mở rộng: `selected -> cut -> zoomed -> ready -> published`. `episodes.stage` lưu trạng thái state machine.

## 8. UI (Flask, port 5004)

| Trang | Nội dung |
|---|---|
| Hàng đợi | Ô dán URL, nút chọn file, bảng tập đang chạy: stage, tiến độ, ETA, lỗi, nút retry/skip/duyệt, log từng bước |
| Tập | Danh sách tập; chi tiết: Guest Card, bảng đoạn + hook (timestamp, intensity, keyword, score), preview clip gốc, bản zoom, thumbnail, trạng thái |
| Tìm kiếm | Full-text + lọc theme/guest/intensity/keyword_reach/chưa dùng; chọn nhiều đoạn → xuất pool cho `tong-hop-rabbit-hole` hoặc `cut_multi_*.json` → đẩy vào hàng đợi cắt đa tập |
| Compilation | Danh sách tập tổng hợp đã dựng, đoạn nào đã dùng |
| Hỏi AI | Ô nhập câu hỏi tự nhiên → `claude -p "/kho-highlight <câu hỏi>"` headless, skill gọi CLI `hldb` truy vấn DB, kết quả hiện trên UI; có thể yêu cầu hành động (gom pool theo chủ đề, xuất cutlist) |
| Cài đặt | Đường dẫn, model Whisper, số đoạn tối đa, tham số zoom, zoom hook on/off, cổng duyệt on/off, trạng thái đăng nhập Claude CLI |

## 9. Lộ trình

| GĐ | Nội dung | Kết quả nghiệm thu | Ước tính |
|---|---|---|---|
| 0 | Khung dự án, venv 3.12, schema DB (v1 + jobs), đăng ký Tool Manager, git init | UI rỗng mở được từ Tool Manager | 0.5 ngày |
| 1 | DB + ingest/scan backfill + trang Tập và Tìm kiếm | 18 tập, 134 clip, 10 cutlist hiện có xem và tìm được trên UI | 1 ngày |
| 2 | Pipeline local: intake → transcript → cắt → zoom → index; cutlist do người dùng thả vào thư mục tập | Thả video + cutlist → ra clip zoom + DB, không thao tác tay | 1.5 ngày |
| 3 | Bước AI headless: cài CLI, token, sync skill, prompt, validator, cổng duyệt | Thả video → xong toàn bộ | 1 ngày |
| 4 | Hỏi AI trên UI, gán theme lúc index, compilation → cut_multi, `viet-tittle-v2` headless cho metadata, nút gửi sang youtube-manager | Khai thác kho trên UI | 1 ngày |
| 5 (tuỳ chọn) | Embedding tìm theo nghĩa, tự theo dõi kênh JRE tải tập mới, thông báo khi xong, MCP server | | 1 đến 2 ngày |

Thứ tự này để sau giai đoạn 2 đã bỏ được mọi thao tác tay trừ bước Claude, và giai đoạn 3 đóng nốt bước đó.

## 10. Rủi ro và cách xử lý

| Rủi ro | Xử lý |
|---|---|
| Skill viết cho chế độ hỏi đáp, chạy headless có thể dừng để hỏi | Prompt cung cấp sẵn mọi tham số + luật không hỏi lại; `--max-turns`; validator; `needs_review` trên UI |
| Quota subscription hết giữa chừng | Hàng đợi tuần tự, job `failed:selecting` tự retry sau khoảng nghỉ; dự phòng API key |
| Claude Code cập nhật đổi hành vi | Ghim phiên bản CLI, script sync skill, test 1 tập mẫu sau mỗi lần nâng cấp |
| GPU tranh chấp Whisper và Zoom | Lock GPU trong orchestrator |
| Tool cũ chưa chạy khi orchestrator cần | Tự khởi động qua `_tool_server.py`, chờ port mở |
| Đường dẫn Unicode (tên clip tiếng Việt) | Zoom tool đã có `_safe_path`; orchestrator luôn truyền đường dẫn tuyệt đối |
| Ổ E đầy vì bản zoom | Ngưỡng cảnh báo + tuỳ chọn xoá bản gốc clip sau khi zoom xong |
| File tải chưa xong đã bị nhận | Kiểm tra kích thước ổn định 30 giây, bỏ qua `.part` |
| Mất DB | 1 file, backup định kỳ theo lịch trong orchestrator |

## 11. Quyết định cần chốt

| # | Câu hỏi | Đề xuất |
|---|---|---|
| A | Xác thực Claude headless: token từ subscription hay API key | Token từ subscription đang dùng (không tốn thêm), API key dự phòng |
| B | Zoom cả hook hay chỉ highlight | Cả hai, có setting tắt |
| C | Cổng duyệt cutlist trước khi cắt | Tắt mặc định (full auto), bật được trên UI |
| D | Số đoạn tối đa mỗi tập cho auto | Skill tự quyết, trần 12 |
| E | Sửa nhỏ 2 tool cũ (Cutter endpoint headless, Zoom endpoint đường dẫn) | Có, mỗi cái vài chục dòng, không đổi hành vi UI cũ |
| F | Nơi lưu kết quả cuối | Giữ thư mục tập như hiện nay; `E:/Upload` để dành cho bước đăng |

## 12. Tiến độ triển khai (cập nhật 2026-09-23)

| GĐ | Trạng thái | Ghi chú |
|---|---|---|
| 0 | Xong | `E:\Tool\DataBase` với venv 3.12, schema, git, đăng ký thẻ "JRE Studio" trong Tool Manager (port 5004) |
| 1 | Xong | 29 tập, 152 highlight, 30 hook, 127 clip, 71 bản zoom, 73k dòng transcript đã vào `studio.db`; UI Hàng đợi / Tập / Tìm kiếm / Compilation / Cài đặt chạy |
| 2 | Xong | Orchestrator + state machine; đã test thật: cắt headless (5 phút clip: 34 giây), Whisper GPU (66 dòng: 88 giây), zoom path mode (17 giây clip: 8 giây); pipeline chạy thật trên JRE-2531 |
| 3 | Chờ đăng nhập | Claude Code CLI 2.1.280 đã cài; bộ chạy headless, prompt, validator, bắt khối phân tích đã viết; probe trả "Not logged in · Please run /login". Người dùng cần chạy `claude` rồi `/login` (hoặc `claude setup-token` + biến môi trường `CLAUDE_CODE_OAUTH_TOKEN`) rồi khởi động lại Studio |
| 4 | Một phần | Skill `/kho-highlight` + CLI `hldb` xong; trang Hỏi AI chờ đăng nhập; 152 highlight đã gán theme (20 theme) + 300 thực thể; gợi ý compilation theo theme; export pool/cut_multi; ghi nhận compilation |
| 5 | Chưa | Embedding, tự theo dõi kênh tải tập mới, thông báo, MCP |

Còn lại sau khi đăng nhập Claude: chạy thử bước chọn nội dung headless trên một tập chưa có cutlist (ví dụ JRE-2533 Diana Pasulka đã có transcript), chỉnh prompt nếu validator báo lỗi, rồi bật "Tự theo dõi thư mục media".
