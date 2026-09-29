---
name: kho-highlight
description: Tra cứu, lọc, tổng hợp và xuất dữ liệu từ kho highlight JRE (database SQLite của JRE Studio) qua CLI hldb. Kích hoạt khi người dùng hỏi về các đoạn highlight đã có (theo chủ đề, keyword, khách mời, intensity, trạng thái cắt/zoom/đã dùng), muốn gom pool cho tổng hợp rabbit hole, xuất cutlist đa tập cho Video Cutter, gán theme/entity cho đoạn, hoặc hỏi "trong kho có gì về X".
---

# Kho Highlight JRE — cách dùng

Database nằm tại `E:\DataBase\studio.db`. KHÔNG đọc trực tiếp file .db, KHÔNG đọc thư mục media. Mọi thao tác đi qua CLI:

```
E:\DataBase\.venv\Scripts\python.exe E:\DataBase\hldb.py <lệnh> [tham số]
```

(luôn thêm `--json` khi cần xử lý tiếp; đặt `PYTHONUTF8=1` nếu thấy lỗi encoding).

## Lệnh

| Lệnh | Dùng khi |
|---|---|
| `search "<từ khoá>" [--episode JRE-2530] [--guest tên] [--kind highlight\|hook] [--min-intensity 8] [--min-gtf 8] [--reach R3] [--status zoomed] [--theme slug] [--topic text] [--unused] [--limit 50] --json` | Tìm đoạn. Từ khoá tìm full-text trên title, summary, hook, topics, keyword, phân tích và transcript; có dấu hay không dấu đều được. Không có từ khoá thì chỉ lọc. `--unused` = chưa nằm trong compilation nào. |
| `show <id \| JRE-2530#3> --json` | Toàn bộ thông tin một đoạn: summary, hook, keyword, fit, topics, themes, entities, hook con, đường dẫn clip/zoom, transcript, khối phân tích của skill (`analysis_md`). |
| `episode <JRE-2530> --json` | Một tập và mọi đoạn của nó. |
| `episodes --json` | Danh sách tập, stage, số đoạn, số zoom. |
| `topics --top 80 --json` | Topics thô hay gặp nhất. |
| `themes --json` | Danh sách theme có kiểm soát và số đoạn mỗi theme. |
| `guests [--group ufo-uap] --json` | Khách mời theo nhóm chuyên môn (ufo-uap, ancient-history, religion, politics, military-intel, mma-combat, comedy, science-space, tech-ai, health-fitness, psychedelics-consciousness, paranormal-mystery, conspiracy-investigation, …): tên, nhóm chính/phụ, các tập. Lọc highlight của cả nhóm: `search --group <slug>`. |
| `suggest-compilations --json` | Topic có >= 4 đoạn từ >= 2 tập chưa dùng. |
| `export --ids 12 15 18 --format pool --theme "<tên>" --out <file.json>` | Pool cho skill `tong-hop-rabbit-hole` (mỗi đoạn tự mang episode_id, guest, source_video, timestamp, summary, hook, intensity). |
| `export --ids ... --format multi --theme "<tên>" --out <file.json>` | `cut_multi_<slug>.json` để Video Cutter cắt đa tập. |
| `tag --pending --limit 40` / `tag --apply <file.json>` | Gán theme/entity (xem mục Gán theme). |
| `import-analysis <JRE-xxxx> <file.md\|json>` | Gắn khối phân tích của skill chọn nội dung vào đoạn. |
| `stats` | Số liệu tổng. |

Mỗi đoạn có `id` số (dùng cho `--ids`) và tham chiếu `JRE-2530#3` (= tập + rank cắt). Hook là đoạn `kind=hook` nằm trong đoạn cha (`parent_id`).

## Cách trả lời câu hỏi

1. Dịch câu hỏi thành 1 đến 3 lệnh `search` (thử cả từ khoá tiếng Anh, vì summary/topics viết tiếng Anh; ví dụ "người khổng lồ" → thử thêm `giants`, `Nephilim`).
2. Đọc JSON, lọc lại theo ý người hỏi, cần chi tiết thì `show` vài đoạn.
3. Trả lời ngắn bằng tiếng Việt: bảng gồm `id`, tập, khách mời, timestamp, tiêu đề, intensity/score, trạng thái, một dòng lý do khớp. Không bịa đoạn không có trong kết quả. Không tự chế timestamp.
4. Người hỏi muốn cắt hoặc dựng tổng hợp → chốt danh sách `id` rồi chạy `export` (ghi file vào `E:\Dowload New\YouTube\` trừ khi được chỉ nơi khác) và báo đường dẫn file. Muốn dựng tập tổng hợp có narration thì đưa file pool cho skill `tong-hop-rabbit-hole`.
5. Sau khi một compilation được dựng, ghi nhận bằng API hoặc bảo người dùng bấm "Ghi nhận manifest" trên UI để đoạn được đánh dấu đã dùng.

## Gán theme và entity (khi được yêu cầu "gán theme", "phân loại", hoặc thấy đoạn chưa có theme)

1. `tag --pending --limit 40` in ra danh sách theme hiện có và các đoạn chưa có theme (title, summary_en, topics, keyword).
2. Với mỗi đoạn chọn 1 theme chính (`primary: true`) và tối đa 2 theme phụ từ danh sách; chỉ đề xuất theme MỚI khi thật sự không có theme nào khớp, slug tiếng Anh kebab-case, kèm `name_vi`.
3. Trích entity: người, địa danh, tổ chức, tác phẩm, sự kiện có tên riêng trong summary (type: person | place | org | work | event).
4. Ghi JSON đúng format trong trường `instructions` của output vào `E:\DataBase\work\tags_<thời gian>.json`, rồi chạy `tag --apply <file>`. Lặp lại tới khi `tag --pending` trống.

## Tuyệt đối

- Không sửa database bằng cách khác ngoài các lệnh trên.
- Không xoá file media, không chạy lại cắt/zoom; việc đó do pipeline của Studio làm.
- Mọi timestamp, tiêu đề, tên khách trong câu trả lời phải lấy nguyên từ output của `hldb`.
