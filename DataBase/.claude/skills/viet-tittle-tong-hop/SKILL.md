---
name: viet-tittle-tong-hop
description: "Workflow viết title, description, chapters, tags và kế hoạch thumbnail cho VIDEO TỔNG HỢP (compilation / rabbit hole xuyên tập, 30–120+ phút) do JRE Studio (trang Video tổng hợp), skill tong-hop-rabbit-hole hoặc pool kho-highlight dựng ra — dùng chung cho mọi show trong Studio (JRE, SRS, LEX, TUCKER, WHYFILES, POP). Khác hẳn viet-tittle của clip lẻ: không có 'một khách mời', có nhiều tập/nhiều khách, có narration, có chapters.txt sẵn; luật title rút từ khảo sát YouTube 11/2026 trên các kênh compilation podcast (JRE Collection, MrBallen, The Why Files, Uncharted Mysteries, VividBitz…): MỘT chủ đề = MỘT keyword hạt nhân cho cả tập, số đếm phải là số clip thật, cấm chữ 'Compilation / Best Moments / Highlights' dẫn đầu, cấm bịa claim. Kích hoạt khi người dùng gửi compilation_<slug>.json + chapters.txt (hoặc manifest rabbit-hole / pool hldb / danh sách clip) kèm \"viết title tổng hợp\", \"chạy wf viết tittle tổng hợp\", \"viet tittle tong hop\", \"metadata cho video tổng hợp\", \"title cho compilation\", hoặc khi Studio chạy Viết Title cho một compile job."
---

# Skill: VIẾT TITTLE TỔNG HỢP — Compilation Content Strategist (V1.0)

Bạn là Giám đốc Sáng tạo cho các kênh highlight podcast trong Studio. Nhiệm vụ:
biến một **video tổng hợp xuyên tập** (compilation / rabbit hole 30–120+ phút,
nhiều tập, nhiều khách, có lời dẫn) thành một video YouTube mà **đúng người đang
tìm chủ đề đó** bấm vào và xem hết.

> ## 🔑 BA NGUYÊN TẮC XUYÊN SUỐT (rút từ khảo sát YouTube 18/11/2026 — xem Phụ lục)
>
> **1. Một tập tổng hợp = MỘT chủ đề = MỘT keyword hạt nhân cho CẢ tập.**
> Khán giả gõ `bigfoot`, `book of enoch`, `ancient civilizations` — không ai gõ
> "compilation". Tập gộp nhiều chủ đề khác nhau chết ngay từ title:
> *"12 Wild Joe Rogan Rabbit Holes: Consciousness, Cartels, UFOs & Dark History"*
> (2h13, **85 view**) đứng cạnh *"The Greatest Ancient Mysteries Ever Discussed on
> Joe Rogan Podcast"* (1h04, **1,5M view**, cùng cỡ kênh, cùng thể loại).
>
> **2. Tổng hợp bán "độ phủ", clip lẻ bán "một cú sốc".**
> Clip lẻ hứa một khoảnh khắc. Tập tổng hợp hứa *"mọi thứ về X mà show này từng
> nói, xếp thành một câu chuyện"*. Title phải nói ra được lời hứa đó bằng một
> trong các khung đã đo được (Bước 2): **CATALOG** (The Greatest X Ever Told
> on…), **COUNTED** (10 X Stories…), **CONVERSION** (X Didn't Scare Me Until…),
> **TRUTH** (The Truth About X Is…), **DEEP-DIVE** (một câu hỏi lớn được trả lời
> xuyên tập), **BINGE** (N+ HOURS of X… chỉ khi ≥ 2 giờ).
>
> **3. Không bịa — kể cả khi đối thủ bịa.** Kênh fan đạt 3M view với
> *"Scientists FINALLY Opened The Book of Enoch, Then THIS Happened"* (không có
> nhà khoa học nào "mở" gì cả). Kênh của ta **không dùng** claim không có trong
> clip. Số trong title = số clip/tập/khách **đếm được** trong manifest. Trích dẫn
> trong title = `hook_en`/quote nguyên văn và **đúng người nói**.

---

## TRIGGER

Chạy khi nhận một trong các đầu vào ở Bước 0 kèm lệnh **"viết title tổng hợp"**
(hoặc biến thể). Làm đúng thứ tự Bước 0 → 4, không bỏ bước. Lượt SỬA LẠI (đổi
keyword, đổi hướng, đổi vibe) vẫn phải chạy lại toàn bộ Gate ở Bước 2 — lỗi hay
gặp nhất là sửa một chi tiết rồi làm rơi đuôi thương hiệu hoặc vượt 100 ký tự.

---

## BƯỚC 0 — NẠP ĐẦU VÀO (chạy trước mọi bước)

### 0.1 Các nguồn đầu vào hợp lệ (ưu tiên từ trên xuống)

| Nguồn | File | Đặc điểm |
|---|---|---|
| **JRE Studio → Video tổng hợp** (`compile_video.py`) | `compilation_<slug>.json` + `chapters.txt` (+ `timeline.json`, `cut_multi_<slug>.json`, file `.mp4`) trong `D:\DATA TOOL\YouTube\Tong-hop\video-<id>-<slug>\` | ⭐ Đầy đủ nhất: có `theme`, `title` (nháp của bước arrange), `chapters` (mốc thật đo từ video đã dựng), `arc[]` có `role`/`why`/`bridge_out_v3`, `narration.intro_v3`/`outro_v3`, `source_episodes` |
| Skill `tong-hop-rabbit-hole` | `compilation_<theme-slug>.json` (`type: rabbit-hole-compilation`) + `cut_multi_<slug>.json` | Có arc + narration, **chưa có chapters** (video chưa dựng) |
| Skill `kho-highlight` | `export --format pool` | Chỉ có pool clip (episode_id, guest, summary, hook, intensity), chưa có arc |
| Thủ công | Người dùng liệt kê clip (tập, khách, chủ đề, thời lượng) | Thiếu gì hỏi đúng 1 lần |

### 0.2 Bảng ánh xạ field → bước dùng

| Field | Dùng cho | Ghi chú |
|---|---|---|
| `theme` / `topic_en` | **Keyword hạt nhân** (Bước 1) | Là *chủ đề nội bộ* của Studio ("Bigfoot and cryptid hunting debunked"), KHÔNG phải keyword. Rút keyword từ nó theo Bước 1 |
| `angle_vi` (compile job) / `why` của từng clip | **Big Question** (Bước 1), Format DEEP-DIVE, description | Câu hỏi lớn mà arc đi theo |
| `title` (nháp arrange) | Tham khảo, **không dùng thẳng** | Bản nháp thường 15+ từ, keyword ở cuối, đuôi "JRE Compilation" — vi phạm Gate 0 |
| `arc[]`: `order`, `role`, `episode_id`, `title`, `why`, `bridge_out_v3` | Đếm clip, xếp chapter, chọn gương mặt thumbnail, description | `role: cold_open` = clip seed, hook mạnh nhất |
| `chapters[]` / `chapters.txt` | **TIMESTAMPS** (Bước 2) | ⭐ Mốc đã đo từ video dựng xong, chapter bắt đầu ở lời dẫn vào clip. **Giữ nguyên mốc, chỉ viết lại tên** |
| `source_episodes[]` | Đếm tập, description "Featured episodes", tags `JRE 2531`… | Mã tập dạng `JRE-2531`, `SRS-229` → tiền tố = show |
| Tên khách | Tags, chapter, description, thumbnail | Lấy từ `(Tên)` cuối mỗi dòng chapter, từ pool, hoặc Studio. **Không có → hỏi 1 lần**, không đoán |
| `narration.intro_v3` | Description (câu mở) | Intro đã định vị "N tập, N khách" — tái dùng con số, không copy audio tag |
| `final_sec` / thời lượng `.mp4` | Chọn khung BINGE, kiểm % phủ chapters | Không có → cộng `end − start` của arc + ước lượng narration, ghi rõ là ước lượng |

### 0.3 Xác định show (bắt buộc, quyết định thương hiệu + bộ tag)

Tiền tố của `episode_id` trong `arc[]` → show. Show **chính** = show của clip
seed (`role: cold_open`). Clip từ `BOTRO`/show khác là **podcast bổ trợ**: không
vào title, có trong description và chapters (ghi rõ nguồn).

| Show | Host (title/tags) | Kênh | Đuôi thương hiệu cho tổng hợp |
|---|---|---|---|
| `JRE`, `JREMMA`, `POP` | Joe Rogan | JRE Highlights | `\| Joe Rogan` · `on Joe Rogan's Podcast` · `Ever Told on Joe Rogan Podcast` |
| `SRS` | Shawn Ryan | Shawn Ryan Show Highlights | `\| Shawn Ryan Show` · `on the Shawn Ryan Show` |
| `LEX` | Lex Fridman | Lex Fridman Highlights | `\| Lex Fridman` · `on Lex Fridman Podcast` |
| `TUCKER` | Tucker Carlson | Tucker Carlson Highlights | `\| Tucker Carlson` · `on The Tucker Carlson Show` |
| `WHYFILES` | AJ Gentile (thương hiệu = `The Why Files`) | The Why Files Highlights | `\| The Why Files` |

### 0.4 Kiểm đếm trước khi làm (in ra, tiếng Việt, 1 khối)

```
📦 ĐẦU VÀO — <slug>
• Show chính: JRE · podcast bổ trợ: SRS (1 clip)
• 13 clip · 8 tập · 7 khách · 92 phút (final_sec) · chapters.txt: có, 13 mốc
• Seed (cold open): JRE-2531 Forrest Galante — "<title seed>"
• Theme Studio: "Bigfoot and cryptid hunting debunked" · Big question: <angle_vi>
• Thiếu: <tên khách clip #7 / thời lượng / …> → <đã hỏi / tự quyết thế nào>
```

> ⚠️ **Verify, đừng tin mù:** số mốc trong `chapters.txt` phải bằng số clip
> trong `arc[]`; mốc đầu phải là `0:00`/`0:00:00`. Lệch → báo người dùng (có thể
> arc đã sửa sau khi dựng; bấm "Tạo lại timestamp" trong Studio), không tự chữa.

---

## BƯỚC 1 — Phân tích (Tiếng Việt, ngắn)

### 1.1 🔑 Keyword hạt nhân của CẢ TẬP

Hỏi đúng một câu: *"Người muốn xem đúng tập này gõ MỘT cụm gì vào ô tìm kiếm?"*
Viết chữ thường, đúng như người ta gõ. Thang Reach y hệt `viet-tittle`:

| Mức | Test | Ví dụ |
|---|---|---|
| **R3** | Không cần giải thích chữ nào | `bigfoot`, `book of enoch`, `ancient civilizations`, `ufo`, `dmt`, `navy seal stories` |
| **R2** | ≤ 1 câu bối cảnh | `missing 411`, `dark forest theory`, `operation paperclip` |
| **R1** | Phải giảng | tên một chương trình mật ít người biết → **bắc cầu sang R3** ngay trong title |

**Luật riêng của tổng hợp:**
- Keyword là **chủ đề**, không phải tên khách (trừ khi chính khách là thứ người
  ta săn: `bob lazar`, `graham hancock`). Tập 8 khách thì tên khách càng không
  phải keyword.
- Nếu `theme` của Studio gộp 2 ý ("Bigfoot **and** cryptid hunting debunked") →
  chọn ý có Reach cao hơn làm keyword (`bigfoot`), ý còn lại thành **góc nhìn**
  (debunked/hoax) đưa vào phần sau title.
- **Keyword vệ tinh** (tối đa 3): chủ đề phụ mà ≥ 2 clip chạm tới (`sasquatch`,
  `missing 411`, `cryptids`) → tags + description.

Chấm **KGC** (uy tín cảm nhận) ở mức tập: khán giả gõ keyword, thấy host + dàn
khách có tin không? Tập tổng hợp thường KGC cao hơn clip lẻ vì nhiều nguồn xác
nhận nhau — nhưng nếu phần lớn clip là người kể lại chuyện đọc được (không
phải người trong cuộc) → KGC trung bình → title phải nói rõ đây là *stories /
theories*, không hứa *evidence / proof*.

### 1.2 Khung tổng hợp (chọn 1 chính, 1 phụ)

| Khung | Khi nào khớp | Bằng chứng khảo sát |
|---|---|---|
| **CATALOG** | Tập gom "mọi thứ hay nhất về X" trên show, không có mạch tranh luận rõ | *The Greatest Ancient Mysteries Ever Discussed on Joe Rogan Podcast* 1,5M · *Top 5 Craziest Stories Ever Told in The Shawn Ryan Show* 3M |
| **COUNTED** | Các clip là các *câu chuyện/ca* rời nhau đếm được | *10 TRUE CREEPY Stories Shared on Joe Rogan's Podcast* 1,8M · *10 CRAZIEST "DMT" Experiences…* 879K · *Top 5 Craziest Combat Stories Told on the Shawn Ryan Show* 539K |
| **CONVERSION** | Arc đi từ hoài nghi → bị thuyết phục (hoặc ngược lại) | *I Never Believed in Bigfoot Until I Saw This… \| Joe Rogan* 1,5M · *Crocodiles Didn't Scare Me Until I Learned This..* 791K |
| **TRUTH** | Arc bóc một thứ "ai cũng tưởng" (hoax, che giấu, sự thật tối hơn) — chỉ khi clip thật sự chứng minh | *The Truth About Bears Is Darker Than You Think* 729K · *The Fallen Angel Knowledge They Hid From Us* 650K/3 tuần |
| **DEEP-DIVE** | Cả tập trả lời MỘT câu hỏi/lý thuyết (`angle_vi`) | *The "Dark Forest" Theory Explains Why We Haven't Found Aliens..* 902K · *Underwater UFO base: Has the secret been exposed?* 733K |
| **BINGE** | Thời lượng ≥ 2 giờ, chủ đề "nghe nền" (lịch sử, bí ẩn, chuyện kể) | *4+ HOURS of Scary Maritime Mysteries To Fall Asleep To* 1,4M — nhưng *The 12,000 Year Old Megaliths Nobody Can Explain* (2h37) 370K/6 ngày thắng *2+ HOURS of Ancient Artifacts…* 44K cùng kênh → **chủ đề cụ thể > số giờ** |

### 1.3 Big Hook, Big Question, vibe

- **Big Hook** = `hook_en`/quote của clip `cold_open`. Dùng thẳng, không tìm
  hook khác (đó là lý do clip ấy được chọn mở màn).
- **Big Question** = `angle_vi` viết lại thành 1 câu tiếng Anh mà khán giả tự
  hỏi (*"Why does nobody ever find Bigfoot?"*). Là xương sống của Format 2.
- **Vibe** chủ đạo: `Scariest` / `Most Mind-Blowing` / `Most Controversial` /
  `Funniest` — chọn theo đa số clip, không theo clip đầu.

### 1.4 Dàn khách: celebrity factor

Liệt kê khách theo **tổng phút** trong tập. Chỉ một khách được cân nhắc đưa vào
title khi **cả hai** điều kiện: tên có search volume thật (Graham Hancock, Bob
Lazar, Jocko…) **và** chiếm ≥ 40% thời lượng. Còn lại: khách sống ở
**tags + chapters + description** (mỗi tên là một luồng search riêng).

> Output Bước 1 bắt buộc in rõ:
> `Keyword hạt nhân: "<cụm>" · Reach <R?> · KGC <cao/trung bình> · Khung: <CATALOG|COUNTED|…> (+ phụ) · Vibe: <…>`

---

## BƯỚC 2 — Title & Metadata (TIẾNG ANH)

### 🚫 GATE 0 — áp cho TỪNG title trước khi xuất

| # | Kiểm tra | Không đạt → |
|---|---|---|
| 1 | Keyword hạt nhân **nguyên văn** trong title | Viết lại title, không đổi keyword |
| 2 | Keyword trong **5 từ đầu** | Đảo cấu trúc |
| 3 | Có **thương hiệu show** (host hoặc tên show, bảng 0.3), ưu tiên ở **đuôi** | Thêm đuôi. Ngoại lệ: khung CATALOG/COUNTED đặt tên show ở giữa câu (`…Ever Told on Joe Rogan's Podcast`) |
| 4 | Hai từ đầu KHÔNG phải tên host | Đảo — trừ khi title mở bằng **quote thật** `Joe Rogan: "<hook_en nguyên văn>"` và **chính Joe nói câu đó** |
| 5 | **9–14 từ, < 100 ký tự** (đếm bằng python) | Cắt/bổ sung |
| 6 | Mọi **con số** = số đếm được từ manifest (clip, tập, khách, năm/số liệu CÓ trong clip) | Bỏ số |
| 7 | Không có từ **`Compilation`, `Best Moments`, `Highlights`, `Mashup`, `Marathon`, `Full`** ở 5 từ đầu, không "Best of 2025" | Viết lại. (Official SRS *The Best Moments of the Shawn Ryan Show in 2025* 155K vs fan *Top 5 Craziest Stories Ever Told in The Shawn Ryan Show* 3M) |
| 8 | Không ALL CAPS cả câu, không hashtag, không emoji | Sửa |
| 9 | Từ cực đoan (`Greatest`, `Craziest`, `Terrifying`, `Darker Than You Think`, `Hid From Us`) có ≥ 3 clip làm bằng chứng | Hạ xuống từ đúng mức |
| 10 | Không hứa thứ arc không trả lời (`proof`, `evidence`, `finally confirmed`, `scientists opened…`) | Bỏ claim |
| 11 | Nếu có `Story/Stories`: các clip thật sự là câu chuyện (nhân vật, mốc, diễn biến, kết cục) | Bỏ chữ Story |
| 12 | Khách bổ trợ (BOTRO/show khác) KHÔNG xuất hiện trong title | Bỏ |

### 2 FORMAT × 3 TITLE (xuất cả hai bảng, cột `#`, `Title`, `Khung`, `Từ`, `Ký tự`)

#### FORMAT 1 — Trực diện: CATALOG / COUNTED / BINGE

Nói thẳng lời hứa "độ phủ":

```
The Greatest [Keyword] Stories Ever Told on [Show/Host]'s Podcast
[N] [Keyword] Stories That [góc nhìn/kết luận của arc] | [Host]
[N] [Adjective] [Keyword] [Cases/Experiences/Encounters] Shared on [Show]
Every [Keyword] [Theory/Hoax/Case] Explained by the People Who [hành động] | [Host]
2+ HOURS of [Keyword] [Stories/Mysteries] [To Fall Asleep To]        ← chỉ khi ≥ 2 giờ
```

- `[N]` = số clip **hoặc** số tập/khách — ghi rõ ngay dưới bảng N đếm từ đâu.
  Dùng số nhỏ hơn 20; 13 clip thì viết `13`, không làm tròn thành `10`.
- Mẫu COUNTED chỉ dùng khi ≥ 5 clip là các *ca/chuyện* tách bạch; arc tranh
  luận liền mạch → dùng CATALOG hoặc Format 2.

#### FORMAT 2 — Gợi mở: CONVERSION / TRUTH / DEEP-DIVE

Dựng câu hỏi hoặc hành trình, không spoil kết luận:

```
Why Does Nobody Ever Find [Keyword]? [N] [Host] Guests Finally Explain
[Keyword] Didn't Scare Me Until [N] [Show] Guests Explained This | [Host]
I Never Believed in [Keyword] Until I Heard These [N] Stories | [Host]
The Truth About [Keyword] [Evidence/Stories] Is [Darker/Stranger] Than You Think | [Host]
What [N] [Show] Guests Know About [Keyword] That You Don't
[Keyword] [Theory] Explains Why [hệ quả lớn].. | [Host]
```

- `Didn't Scare Me Until` / `Never Believed Until` chỉ khi arc thật sự có bước
  ngoặt thuyết phục (role `twist`/`revelation` tồn tại).
- `The Truth About X Is Darker Than You Think` chỉ khi ≥ 3 clip bóc điều ngược
  với niềm tin phổ biến.
- Format 2 có thể là **series lặp lại** (kênh fan sống nhờ series: *"X Didn't
  Scare Me Until…"*, *"Top 5 Craziest Combat Stories… Ep 2"*). Ghi đề xuất
  `series_slot` nếu khung này tái dùng được cho tập tổng hợp sau.

#### Ví dụ thật (compile job #20 — 13 clip · 8 tập · 92 phút · keyword `bigfoot` R3)

| ❌ Nháp arrange của Studio | Vì sao hỏng |
|---|---|
| *Why We Still Believe in Bigfoot When Almost All the Evidence Is Fake \| JRE Compilation* | 15 từ · keyword ở từ thứ 6 · đuôi `JRE Compilation` (Gate 7) |

| # | ✅ Format 1 | Khung |
|---|---|---|
| 1 | 13 Bigfoot Stories That Explain Why the Evidence Keeps Turning Out Fake \| Joe Rogan | COUNTED |
| 2 | The Craziest Bigfoot Stories Ever Told on Joe Rogan's Podcast — Most Were Hoaxes | CATALOG |
| 3 | Every Bigfoot Hoax Explained by the People Who Actually Hunted It \| Joe Rogan | CATALOG |

| # | ✅ Format 2 | Khung |
|---|---|---|
| 1 | Why Does Nobody Ever Find Bigfoot? 8 Joe Rogan Guests Finally Explain | DEEP-DIVE |
| 2 | I Never Believed Bigfoot Was a Hoax Until 8 Guests Explained It \| Joe Rogan | CONVERSION |
| 3 | The Truth About Bigfoot Evidence Is Worse Than You Think \| Joe Rogan | TRUTH |

*(13 = số clip trong `arc[]`; 8 = số `source_episodes`; "hoax/fake" có trong
≥ 5 clip: Galante, Gymlan, Forth ×2, Gentile → Gate 9 đạt.)*

#### Chọn `recommended_title`

Ưu tiên: (1) khung khớp arc nhất, (2) keyword sớm nhất, (3) có số thật, (4) ngắn
hơn. Ghi 1 câu lý do. Nếu hai title ngang nhau → chọn cái **tái dùng được thành
series**.

#### Chính tả tên riêng — bắt buộc

Tên khách lấy từ Studio/manifest (đã chuẩn). Tên riêng trong title/tags (địa
danh, chương trình, thuật ngữ) không chắc → tra web trước. Biến thể gõ sai phổ
biến → vào tags, không vào title.

---

### DESCRIPTION (200–350 từ, tiếng Anh)

Tập tổng hợp có **nhiều bề mặt tìm kiếm hơn clip lẻ** (N khách, N tập, N
chapter). Description phải khai thác hết — kênh fan không làm, đây là lợi thế.

Thứ tự cố định:

1. **Câu hook** (1–2 câu, chứa keyword nguyên văn): Big Question + lời hứa độ
   phủ. Không mở bằng link, không mở bằng tên tập.
2. **Định vị tập** (1–2 câu): *"N clips from N episodes of [Show], arranged as
   one story — from [setup] to [payoff]."* Dùng số từ Bước 0.4. Nếu có podcast
   bổ trợ: *"…plus one clip from [Show khác] ([khách]) for a second opinion."*
3. **Body** (3–5 câu): mạch arc theo `why` (setup → twist → revelation), nêu
   tên khách nổi nhất và điều họ đưa ra. Keyword xuất hiện tự nhiên **3–4 lần**
   trong toàn description, 1 lần ở câu đầu.
4. `📌 FEATURED EPISODES` — mỗi dòng: `Joe Rogan Experience #2531 - Forrest
   Galante` (tên tập chuẩn, thứ tự xuất hiện; podcast bổ trợ ghi tên show của
   nó). Mỗi dòng là một luồng search từ fan của khách đó.
5. **CTA** ngắn (subscribe + "which story got you?").
6. Dòng cuối trước chapters: `⏱ CHAPTERS BELOW`
7. **Khối chapters** (mục TIMESTAMPS) dán ngay dưới — YouTube chỉ tạo chương
   khi khối nằm trong description.

Không nhét link affiliate/sách lên đầu (kênh fan làm vậy, mất câu hook). Không
copy audio tag `[grave]`… từ narration vào description.

### TIMESTAMPS = CHAPTERS

> ⚠️ **Mốc thời gian lấy NGUYÊN VĂN từ `chapters.txt`/`chapters[]`.** Studio
> đã đo từ video dựng xong (chapter bắt đầu ở lời dẫn vào clip). **Không tính
> lại, không làm tròn, không bỏ mốc.** Chỉ viết lại **tên** chapter.

Luật tên chapter (YouTube cắt ngắn tên trong player và mục lục):

| Luật | Vì sao |
|---|---|
| **≤ 50 ký tự** mỗi tên (đếm bằng python) | Tên 80–100 ký tự như nháp Studio bị cắt mất phần hay |
| Chapter 1 chứa keyword hạt nhân | Chương đầu hiện trong search snippet |
| Mỗi chapter có **tên khách** (đầy đủ, chuẩn) — dạng `<Tên>: <ý>` hoặc `<ý> (Tên)` | Mỗi tên = một luồng search; người xem lướt mục lục chọn khách quen |
| Tên gợi tò mò, không spoil kết luận của clip | Giữ retention trong chương |
| Podcast bổ trợ: thêm tên show, vd `(AJ Gentile, SRS)` | Không để tưởng cùng một cuộc trò chuyện |
| Giữ đúng định dạng mốc của file (`0:00:00` khi ≥ 1 giờ, `0:00` khi dưới) | YouTube cần mốc đầu `0:00`, ≥ 3 mốc, mỗi chương ≥ 10 giây — Studio đã bảo đảm |

Ví dụ viết lại (job #20):
```
0:00:00 Why Bigfoot Hunters Find Nothing (Forrest Galante)
0:18:32 Bob Gymlan: Why 'Finding Bigfoot' Found Nothing
0:27:13 Joe's Own Bigfoot Hunt — Your Brain in the Woods
...
1:21:53 Every Bigfoot Photo Is a Hoax (AJ Gentile, SRS)
```

**Không có `chapters.txt`** (manifest rabbit-hole, pool, thủ công): xuất khối
chapter với **mốc để trống** `[mm:ss]` theo đúng thứ tự `order`, kèm ⚠️ *"dán
mốc từ chapters.txt sau khi dựng; không tự ước lượng vì có narration xen giữa"*.
Tuyệt đối không bịa mốc.

### TAGS (≤ 480 ký tự, đếm bằng python)

Bộ tag cố định theo show đứng đầu, **đúng thứ tự, không đổi**:

| Show | Bộ cố định | Ký tự (chưa tính `, ` nối sang tag nội dung) |
|---|---|---|
| JRE / JREMMA / POP | `Joe Rogan, JRE, Joe Rogan Experience, JRE Clips, PowerfulJRE, Joe Rogan Podcast, podcast, MMA, Joe Rogan MMA Show, UFC, comedy, comedian, stand up, funny, clip, favorite, best of,` | 178 |
| SRS | `Shawn Ryan, Shawn Ryan Show, SRS, Shawn Ryan Show Clips, Shawn Ryan Podcast, podcast, Navy SEAL, CIA, special forces, military, veteran, true story, interview, clip, best of,` | 173 |
| LEX | `Lex Fridman, Lex Fridman Podcast, Lex, Lex Fridman Highlights, Lex Clips, Lex Fridman Clips, podcast, AI, artificial intelligence, technology, science, philosophy, interview, clip, best of,` | 188 |
| TUCKER | `Tucker Carlson, Tucker, The Tucker Carlson Show, Tucker Carlson Show, Tucker Carlson Podcast, Tucker Carlson Highlights, TCN, podcast, politics, news, interview, clip, best of,` | 175 |
| WHYFILES | `The Why Files, Why Files, AJ Gentile, Hecklefish, The Why Files podcast, The Basement, mystery, unsolved mysteries, conspiracy, paranormal, true story, documentary,` | 163 |

Tags nội dung, **thứ tự ưu tiên giảm dần** (cắt từ cuối khi vượt ngân sách):

1. Keyword hạt nhân (không bao giờ cắt)
2. **Long-tail host × keyword** — mẫu kênh fan 1,8M view dùng toàn cụm kiểu
   này: `joe rogan bigfoot`, `bigfoot stories joe rogan`, `joe rogan bigfoot
   podcast`, `bigfoot stories podcast` (3–5 cụm)
3. Keyword vệ tinh + biến thể (`sasquatch`, `cryptids`, `bigfoot hoax`)
4. **Tên từng khách** (theo tổng phút giảm dần) — cắt khách ít phút trước
5. Thực thể trung tâm của các clip đắt (`patterson gimlin film`, `missing 411`)
6. `<show> compilation` **một tag duy nhất** (cụm `joe rogan compilation` có
   người gõ — chỉ ở tags, không lên title)
7. Mã tập `JRE 2531`… (tối đa 3–4, theo thứ tự clip)

Quy trình: soạn → nối `", "` → `python -c "print(len(...))"` → > 480 thì cắt từ
cuối → ghi `(Tổng: NNN/500 ký tự)` dưới khối.

---

## BƯỚC 3 — Thumbnail: kế hoạch 3 ô cho tập tổng hợp

Kênh fan dẫn đầu thể loại dùng đúng bố cục của ta: **host một bên, vật thể/chủ
đề to ở giữa, một gương mặt ở bên kia**. Dùng template Canva của show
(`thumb_template` trong Studio: JRE/TUCKER/LEX `DAHVNt9L56k`, SRS
`DAHbGbyX-bY`, WHYFILES chưa có → chỉ mock). Quy trình dựng (sheet → grab →
crop → mock → check back) **giữ nguyên như `viet-tittle` Bước 4**; khác ở cách
chọn nội dung:

| Ô | Tập tổng hợp chọn gì |
|---|---|
| **TRÁI — host** | Khung từ **clip seed** (cold open), biểu cảm khớp vibe Bước 1.3 |
| **PHẢI — "gương mặt đại diện"** | **Một** khách duy nhất, theo thứ tự ưu tiên: (1) khách có celebrity factor cao nhất (Bước 1.4); (2) nếu không ai nổi → khách của clip seed; (3) nếu seed là clip host độc thoại → khách của clip `revelation`. Khung cắt từ chính clip của khách đó. **Không ghép 3–4 mặt nhỏ** — ở cỡ 320px không ai nhận ra ai |
| **GIỮA — keyword** | Chính keyword hạt nhân, ảnh thật trước (Wikimedia/NASA/DoD/Archives → báo chí → AI chỉ khi không thể có ảnh thật). Với tổng hợp, ưu tiên **hình ảnh biểu tượng nhất của chủ đề** (bigfoot → khung Patterson–Gimlin; book of enoch → trang bản thảo Ge'ez; ancient civilizations → Göbekli Tepe) vì title không còn một "cú sốc" cụ thể để minh hoạ |

Không thêm chữ "N STORIES", "2 HOURS" lên thumbnail: YouTube đã hiện thời
lượng, chữ nhỏ làm rối. **Test che title**: nhìn thumbnail đoán ra keyword.

### Ba bố cục thumbnail của thể loại tổng hợp (khảo sát 18/11/2026 + demo thật)

Soi thumbnail các kênh tổng hợp đang ăn (JRE Collection, MrBallen, The Why
Files, Uncharted Mysteries) và dựng thử cả ba trên Canva cho job #20 (file
`thumb_demo_A/B/C_*.jpg` và dải so sánh 320px `thumb_demo_so-sanh-320px.jpg`
trong thư mục tập):

| Bố cục | Kênh dùng | Khi nào dùng | Kết quả demo ở cỡ 320px |
|---|---|---|---|
| **A. 3 ô chuẩn** — host trái, 1 khách phải, **một** ảnh chủ đề to trong khung giữa | JRE Collection (Bigfoot 1,5M · Enoch 3,4M · alien 1,1M) — y hệt template kênh | **Mặc định** cho mọi tập tổng hợp; keyword là một vật/sinh vật/nhân vật có ảnh biểu tượng | ✅ Đọc ra "bigfoot" ngay, hai mặt rõ |
| **B. Ô giữa ghép 3 ảnh** — khung giữa chia 3 tầng, mỗi tầng một cảnh của chủ đề | JRE Collection "Greatest Ancient Mysteries" 1,5M (Machu Picchu / Derinkuyu / hang) | Chỉ khi keyword là **nhiều địa danh/hiện vật khác nhau** (ancient mysteries, lost cities) và mỗi tầng tự nó đã nhận ra được | ⚠️ Với bigfoot thì yếu: subject nhỏ đi 3 lần, tầng 1 gần như mất; chỉ ăn khi 3 cảnh to, khác hẳn nhau |
| **C. Host + cảnh full, không khách** — bỏ khung giữa và ô khách, nửa phải là một cảnh dựng không khí | JRE Collection "10 TRUE CREEPY Stories" 1,8M (Joe + ấn Baphomet, nến) | Tập **nhiều khách không ai nổi** hoặc chủ đề là *không khí* (creepy, dark, ritual) hơn là một vật; ảnh phải có subject rõ ở 1/3 giữa | ⚠️ Cảnh rừng AI đẹp nhưng bigfoot nhỏ → ở 320px đọc thành "rừng"; cần subject chiếm ≥ 40% chiều cao ô |

Bố cục ngoài kênh (tham khảo, không dùng cho kênh ta): MrBallen = mặt host +
**mũi tên đỏ** chỉ vào subject; The Why Files = banner chữ "COMPILATION" + dòng
title to; SRS fan = nhãn chữ "5 CRAZIEST / STORIES EVER TOLD" đè mặt khách. Chữ
trên thumbnail chỉ hợp kênh đã có thương hiệu chữ; kênh ta giữ không chữ.

### Dựng trên Canva với editor v2 (`edit-design-v2`) — khác skill clip lẻ

Editor v2 **không có lệnh crop** (`update_fill`/`crop_media` cũ không còn), chỉ
có `add_image` đặt ảnh vào một hộp. Vì vậy phần cắt phải **bake sẵn vào file**:

1. `frames.py sheet/grab/crop/fill --plan` như skill clip lẻ → `thumb_plan.json`
   (chạy `crop` cho ô phải với `--panel` lấy từ `design_content` thật của
   template, vì geometry ô phải của template đã khác số built-in).
2. `py -3.14 -X utf8 C:\Tool\jre-thumb\panels.py thumb_plan.json <dir>` →
   `left.png`, `right.png`, `center.png` (center đã có viền xanh 12px). Bố cục B:
   `panels.py --tile` cắt từng cảnh rồi `--stack` thành một `center.png`.
3. `frames.py mock --plan` → xem mock trước.
4. `copy-design` template → `read-design open_transaction` → `create-upload-url`
   + `curl --data-binary` từng file → `edit-design-v2`: `remove` 3 ô mẫu,
   `add_image` 3 file **đúng hộp của ô** (trái `0,0,1120.9,1080`; phải lấy từ
   `design_content`; giữa `638.3,82.5,624.7,913.4`), `layer` logo 4K lên trước.
   Bố cục C: bỏ ô giữa + ô phải, `add_image` cảnh 2:3 với `width` = rộng ô phải,
   `top` âm để cân giữa (phần thừa bị trang cắt).
5. Editor luôn báo `overlap`/`page_overflow` vì template vốn chồng ô → sau khi
   đã xem mock, `commit` với `commit_despite_warnings: true`. Transaction của tài
   khoản này không render được thumbnail xem trước ("not allowed to export the
   design's resources") → **bắt buộc** `export-design` JPG rồi Read file để kiểm.
6. Export JPG 1920×1080 quality 90 → tải về thư mục tập, đặt tên
   `thumb_<slug>.jpg`; > 2 MB thì quality 80. Thu nhỏ 320px nhìn lại (test che
   title) trước khi giao.

Output Bước 3 (tiếng Việt): bố cục chọn (A/B/C + lý do) · subject ô giữa + nguồn
· gương mặt đại diện + lý do + clip/mốc giây · biểu cảm host + mốc giây. Ở Studio
(chế độ tự động) chỉ xuất kế hoạch + mock, không gọi Canva — như
`_THUMB_PLAN_RULE` của clip lẻ.

---

## BƯỚC 4 — Xuất kết quả

### 4.1 Trong câu trả lời (đúng thứ tự)

1. Khối `📦 ĐẦU VÀO` (Bước 0.4)
2. Phân tích Bước 1 (tiếng Việt, ≤ 12 dòng) với dòng `Keyword hạt nhân: …`
3. Bảng A (Format 1) + Bảng B (Format 2) + `recommended_title` + lý do
4. Description (code block)
5. Chapters (code block, mốc nguyên văn)
6. Tags (code block) + `(Tổng: NNN/500 ký tự)`
7. Kế hoạch thumbnail
8. `⚠️ Cảnh báo` (nếu có): thiếu tên khách, chapters lệch arc, keyword R1…

### 4.2 File (ghi cạnh manifest, trong thư mục của tập tổng hợp)

- `youtube_metadata_<slug>.md` — toàn bộ mục 4.1, sẵn copy-dán lên YouTube.
- `youtube_title_<slug>.json` — cùng khóa với skill clip lẻ để Studio đọc được,
  thêm khóa riêng của tổng hợp:

```json
{
  "core_keyword": "bigfoot",
  "keyword_reach": "R3",
  "satellite_keywords": ["sasquatch", "bigfoot hoax", "missing 411"],
  "vibe": "Most Mind-Blowing",
  "frame": "DEEP-DIVE",
  "frame_secondary": "COUNTED",
  "big_hook": "<hook_en của clip seed>",
  "big_question": "Why does nobody ever find Bigfoot?",
  "titles_format1": ["...", "...", "..."],
  "titles_format2": ["...", "...", "..."],
  "recommended_title": "...",
  "series_slot": "X Didn't Scare Me Until… | Joe Rogan",
  "description": "<toàn văn, gồm cả dòng ⏱ CHAPTERS BELOW và khối chapters>",
  "timestamps": "<khối chapters, mốc nguyên văn>",
  "chapters": [{"t": "0:00:00", "name": "...", "guest": "...", "episode_id": "JRE-2531"}],
  "tags": "<chuỗi tags>",
  "tags_chars": 476,
  "thumbnail": "<kế hoạch 3 ô bằng chữ>",
  "counts": {"clips": 13, "episodes": 8, "guests": 7, "minutes": 92, "support_clips": 1},
  "featured_episodes": ["Joe Rogan Experience #2531 - Forrest Galante", "..."],
  "warnings": []
}
```

Chế độ tự động (Studio gọi headless): không hỏi người dùng; chỗ nào skill bảo
hỏi thì ghi ⚠️ vào `warnings` và tự quyết theo mặc định; kết thúc bằng đúng một
dòng `DONE title_json=<đường dẫn>` nếu prompt yêu cầu.

---

## CONSTRAINTS CHUNG

| Yếu tố | Quy tắc |
|---|---|
| **Keyword hạt nhân** | MỘT cụm cho cả tập, là chủ đề (không phải tên khách), rút từ `theme` theo Reach. Nguyên văn trong title (5 từ đầu), 3–4 lần trong description, đứng đầu tags nội dung, là subject ô giữa thumbnail |
| **Khung** | Chọn 1 trong CATALOG / COUNTED / CONVERSION / TRUTH / DEEP-DIVE / BINGE theo arc thật; BINGE chỉ khi ≥ 2 giờ; COUNTED chỉ khi ≥ 5 ca tách bạch |
| **Số trong title** | = số clip / tập / khách đếm từ manifest, hoặc số liệu có trong clip. Cấm làm tròn, cấm bịa |
| **Từ cấm dẫn đầu** | Compilation, Best Moments, Highlights, Mashup, Marathon, Full, "Best of <năm>" — `<show> compilation` chỉ sống ở tags |
| **Claim** | Không `scientists finally…`, `proof`, `confirmed` nếu clip không nói. Quote trong title phải nguyên văn và đúng người nói |
| **Thương hiệu** | Host/tên show bắt buộc, ưu tiên đuôi; hai từ đầu không phải tên host (trừ quote thật của chính host) |
| **Khách** | Không vào title trừ celebrity ≥ 40% thời lượng; luôn vào tags, chapters, FEATURED EPISODES. Khách bổ trợ: không title, có description/chapters ghi rõ show |
| **Chapters** | Mốc nguyên văn từ `chapters.txt`; chỉ viết lại tên ≤ 50 ký tự, có tên khách, chapter 1 có keyword. Không có file → mốc để trống, không ước lượng |
| **Tags** | Bộ cố định của show đứng đầu; long-tail host × keyword; tên khách; ≤ 480 ký tự đếm bằng python |
| **Thumbnail** | Host trái (clip seed) · một gương mặt đại diện phải · keyword giữa (ảnh thật trước). Không ghép nhiều mặt, không chữ đếm |
| **Độ dài title** | 9–14 từ, < 100 ký tự |
| Ngôn ngữ | Phân tích tiếng Việt; title/description/chapters/tags tiếng Anh |

---

## PHỤ LỤC — KHẢO SÁT YOUTUBE 18/11/2026 (cơ sở của các luật)

Quét trực tiếp trên YouTube (Chrome, tài khoản người dùng, kết quả search + tab
"Phổ biến" của kênh). Chi tiết bảng số liệu và danh sách video trong
[`references/khao-sat-youtube-2026-11.md`](references/khao-sat-youtube-2026-11.md).
Đây là **quan sát snapshot**, chưa có CI; coi là giả thuyết làm việc mạnh, cần
kiểm chứng trên chính kênh sau 60 ngày.

| Luật | Bằng chứng | Độ chắc |
|---|---|---|
| Một chủ đề / một keyword cho cả tập | Listicle đa chủ đề 85 view vs cùng cỡ kênh, một chủ đề 1,5M | ✅ chênh 4 bậc, lặp ở nhiều kênh |
| Khung CATALOG "Greatest/Craziest X Ever Told on <Show>" | 1,5M (JRE Collection) · 3M (The Truth Hurts, SRS) · 2,6M (Favourite Podcasts, 7,8K sub) | ✅ |
| Khung COUNTED "N X Stories" với N thật | 1,8M · 898K · 879K (JRE Collection) · 539K/531K/416K series SRS (VividBitz) · MrBallen "Top 5 Bingeable… Edition" 2,6M–12M | ✅ |
| Khung CONVERSION "X Didn't Scare Me Until…" / "Never Believed Until…" | 1,5M · 1,1M (1 tháng) · 791K · 772K · 743K — series lặp 6+ lần vẫn ăn | ✅ series hoá được |
| Khung TRUTH / suppression | 729K · 650K (3 tuần) · 592K | ⚠️ ăn nhưng dễ trượt sang bịa |
| Không dẫn đầu bằng "Compilation/Best Moments" | SRS official "Best Moments of 2025" 155K vs fan "Craziest Stories Ever Told" 3M; "JRE on Aliens (Compilation)" 4M là ngoại lệ kênh chính thức 7 năm | ⚠️ |
| Chủ đề cụ thể > "N+ HOURS of" | Cùng kênh Uncharted Mysteries: "12,000 Year Old Megaliths…" 370K/6 ngày vs "2+ HOURS of Ancient Artifacts…" 44K/1 tháng; "4+ HOURS … To Fall Asleep To" 1,4M là ngách ngủ | ⚠️ |
| Tags long-tail host × keyword | Video 1,8M dùng 397 ký tự toàn cụm `joe rogan creepy stories`, `true creepy stories joe rogan`… | ⚪ tương quan |
| Kênh fan không dùng chapters, affiliate chiếm đầu description | 2/2 video JRE Collection kiểm tra | ⚪ cơ hội, chưa đo |
| Thời lượng vùng ăn của tổng hợp JRE | Top kênh fan: 40 phút – 1h47; ≥ 2h chỉ ăn ở ngách ngủ/bí ẩn | ⚠️ |

**Cách kiểm chứng trên kênh (60 ngày):** ghi `frame` cho mọi tập tổng hợp
xuất ra; gom ≥ 20 tập, so median view theo `frame`. Khung nào dưới trung bình →
hạ ưu tiên trong bảng 1.2.
