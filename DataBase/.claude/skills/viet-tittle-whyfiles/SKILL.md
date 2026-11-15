---
name: viet-tittle-whyfiles
description: "Workflow viết title/metadata/thumbnail cho kênh The Why Files Highlights (clip cắt từ The Why Files của AJ Gentile & Hecklefish, gồm cả podcast The Basement và các tập compilation như Sinister & Unsolved / Campfire). Clone từ skill viet-tittle của JRE, giữ nguyên khung 4 bước + Bước 0 nạp cutlist, nhưng đổi toàn bộ luật thương hiệu sang The Why Files: thương hiệu bắt buộc trong title là `The Why Files` (không phải tên host), đuôi title theo loại tập (solo / The Basement có khách / compilation), bộ tag cố định của The Why Files, vibe ưu tiên mystery – unsolved – paranormal – conspiracy – kinh dị có thật, thumbnail AJ trái / khách hoặc nhân vật vụ án phải / ô giữa là chính keyword. Kích hoạt khi người dùng gửi transcript hoặc cutlist của The Why Files kèm \"chạy wf viết tittle why files\", \"viet tittle whyfiles\", \"viết title the why files\", hoặc khi Studio chạy nút Viết Title cho show WHYFILES."
---

# Skill: VIẾT TITTLE — The Why Files Content Strategist (V1.0, clone từ viet-tittle V1.2 của JRE)

Bạn là Giám đốc Sáng tạo kiêm chiến lược nội dung cho kênh **The Why Files
Highlights**. Nhiệm vụ: biến một đoạn cắt từ The Why Files thành video YouTube
có sức hút lớn với khán giả Mỹ mê **bí ẩn, vụ án chưa giải, paranormal, UFO,
thuyết âm mưu, lịch sử bị giấu, sinh vật bí ẩn**. Tìm ra khía cạnh hấp dẫn
nhất: rùng rợn, khó giải thích, có bằng chứng lạ, hoặc hài (Hecklefish).

### Bối cảnh show (đọc trước khi làm)

| Loại tập | Nhận biết | Người nói |
|---|---|---|
| **Tập chính (solo)** | AJ kể một hồ sơ: dựng bối cảnh → bằng chứng → giả thuyết → kết luận mở. Hecklefish (con cá hoạt hình, giọng New York) chen vào đùa | AJ Gentile + Hecklefish |
| **The Basement** | Tên file `The Basement: <Khách> \| <Chủ đề>`. Podcast phỏng vấn | AJ + khách mời (+ Hecklefish) |
| **Compilation** | `Sinister & Unsolved`, `Campfire Compilation`… ghép nhiều câu chuyện ngắn | AJ kể nhiều vụ liên tiếp |

- Tên host viết đúng: **AJ Gentile**. Nhân vật cá: **Hecklefish** (viết liền).
  Transcript auto-caption hay viết sai thành "Heckle fish", "AJ Gentle"…
- **Thương hiệu người ta gõ là `The Why Files`, không phải `AJ Gentile`.**
  Cái tên AJ gần như không có search volume riêng. Vì vậy chỗ nào skill JRE gốc
  bắt buộc `Joe Rogan`, ở skill này bắt buộc **`The Why Files`**.
- Uy tín của show đến từ **hồ sơ, tài liệu, nhân chứng, bằng chứng được dẫn
  lại**, không từ bằng cấp của AJ. Khách The Basement mới là người có thẩm quyền
  (nhà nghiên cứu, tác giả, nhân chứng).

> ## 🔑 NGUYÊN TẮC XUYÊN SUỐT — KEYWORD HẠT NHÂN
>
> **Keyword hạt nhân = cụm khán giả GÕ VÀO Ô TÌM KIẾM để tìm ra chính video này.**
>
> Không giới hạn loại từ: tên vụ án (`dyatlov pass`), hiện tượng (`skinwalker`),
> địa danh (`antarctica`), chiến dịch (`operation highjump`), sinh vật (`bigfoot`),
> câu hỏi (`what happened to flight 19`). Test duy nhất: *"có ai gõ cụm này không?"*
>
> **Cùng một keyword phải xuyên suốt cả 4 bước, không được đổi giữa chừng:**
>
> | Bước | Keyword xuất hiện ở đâu |
> |---|---|
> | 1 | Chốt keyword hạt nhân, chấm **Reach × KGC** |
> | 2 | **Nguyên văn** trong title, trong 5 từ đầu · 3–4 lần trong description · đứng đầu tags nội dung |
> | 3 | Chính keyword **LÀ subject của ô giữa thumbnail**, không phải ẩn dụ của nó |
> | 4 | Ô giữa thumbnail vượt **test che title** (nhìn ảnh đoán ra keyword) |
>
> Nếu một trong bốn bước không chứa keyword → workflow chạy sai, quay lại làm lại.

---

## TRIGGER

Khi nhận transcript + lệnh **"chạy wf viết tittle why files"** (hoặc Studio gọi
cho show WHYFILES), thực hiện đúng các bước dưới đây theo thứ tự, không bỏ bước.

**Áp dụng cả ở lượt SỬA LẠI:** người dùng chỉ đổi một phần (keyword, hướng SEO,
vibe) mà không nhắc format thì mọi ràng buộc cấu trúc ở Bước 2 (đuôi title,
thương hiệu, độ phủ timestamp, giới hạn tags) vẫn bắt buộc áp lại từ đầu.

---

## BƯỚC 0 — NẠP CUTLIST (nếu có), CHẠY TRƯỚC MỌI BƯỚC

Cutlist của show này thường do `chon-noi-dung-chu-de-hot` xuất (layout
`flat_hooks`, có TOPIC MAP thay cho Guest Card). Có cutlist → nạp và TÁI SỬ
DỤNG, chỉ verify chứ không phân tích lại.

| Field trong cutlist | Dùng cho | Ghi chú |
|---|---|---|
| `core_keyword` | **KEYWORD HẠT NHÂN, cả 4 bước** | ⭐ Dùng thẳng, KHÔNG tự chọn keyword khác. Thấy sai → ghi cảnh báo, không tự đổi |
| `keyword_reach` | Bước 1, 2 | `R3`/`R2`/`R1`. R1 → title bắt buộc có cầu nối sang một cụm R3 |
| `keyword_credibility` | Bước 2, 3, 4 | `medium` → title phải hiện nguồn uy tín (Format 1C), thumbnail phải có bằng chứng nhìn thấy được |
| `keyword_reason` | Bước 1, 2, 3 | Người gõ cụm này muốn biết gì: brief cho title lẫn thumbnail |
| `satellite_keywords` | Tags + phần sau title | 0–2 chủ đề phụ của rabbit hole |
| `hook_en` | Big Hook | Câu mở nguyên văn đã chọn, dùng thẳng |
| `topics` | Tags | Không dùng thay `core_keyword` |
| `summary_en` | Description | Viết lại cho có hook, không copy |
| `fit_reason` | Chọn cấu trúc title | Lý do nhu cầu chủ đề (skill chủ đề) hoặc lý do khách đáng nghe |
| `guest_profile.*` (nếu có) | Format 1C, gate thẩm quyền | Credential xác thực được của khách The Basement |
| `start` | Timestamps | Mốc offset, bắt buộc (xem TIMESTAMPS) |
| `episode.id` / `episode.guest` | Description + Tags | Tên tập chuẩn + chính tả chuẩn tên khách |

Không có cutlist → tự phân tích toàn bộ từ transcript.

> ⚠️ **Verify, đừng tin mù:** field trong cutlist mâu thuẫn với transcript (không
> thấy `hook_en`, `start` không khớp) → báo/ghi cảnh báo ngay, không tự chữa.

---

## BƯỚC 1 — Phân tích & Định hướng

**1. Vibe chủ đạo** (chọn một hoặc kết hợp, ưu tiên cái MẠNH NHẤT):
- `Scariest` — vụ án rùng rợn, mất tích, sinh vật, chuyện có thật khiến lạnh gáy
- `Most Mysterious` — chưa ai giải được, bằng chứng mâu thuẫn, câu hỏi bỏ ngỏ
- `Most Mind-Blowing` — lịch sử/khoa học bị bỏ sót, công nghệ cổ, vũ trụ
- `Most Controversial` — chính phủ che giấu, chiến dịch mật, thuyết âm mưu
- `Funniest` — Hecklefish, khoảnh khắc AJ/khách cười phá

**2. The Big Hook** — khoảnh khắc / câu nói / chi tiết khiến người xem DỪNG
SCROLL. Trích nguyên văn từ transcript. Ở show này hook mạnh nhất thường là
**một chi tiết bằng chứng lạ** (dấu chân, đoạn ghi âm, tài liệu giải mật, lời
khai nhân chứng), không phải một câu bình luận.

**3. 🔑 KEYWORD HẠT NHÂN**

Có `core_keyword` → dùng thẳng, chỉ verify nó có trong transcript.
Không có → tự hỏi đúng một câu:

> *"Nếu chỉ được gõ MỘT cụm vào ô tìm kiếm YouTube để tìm ra đúng đoạn này,
> đó là cụm nào?"*

Viết đúng như người ta gõ — tiếng Anh, chữ thường.

| Loại | Ví dụ |
|---|---|
| Vụ án / sự kiện | `dyatlov pass` · `flight 19` · `the zodiac killer` |
| Chiến dịch / chính phủ | `operation highjump` · `mk ultra` · `area 51` |
| Địa danh | `antarctica` · `skinwalker ranch` · `the bermuda triangle` |
| Sinh vật / hiện tượng | `bigfoot` · `skinwalker` · `missing 411` · `shadow people` |
| Cổ đại / tôn giáo | `ancient technology` · `the nephilim` · `göbekli tepe` |
| Câu hỏi / nỗi sợ | `what's under antarctica` · `people who vanished without a trace` |

**Cấm:** lấy `the why files`, `aj gentile` hay tên khách làm keyword hạt nhân —
trừ khi chính khách là thứ người ta săn tìm (vd `david paulides` gắn với
`missing 411`, `bob lazar`). `The Why Files` là thương hiệu, đã có ở cuối title
và đầu tags.

#### Chấm 2 chiều — BẮT BUỘC

**① REACH — bao nhiêu người gõ cụm này?**

| Mức | Test nhanh |
|---|---|
| **R3** | Không phải giải thích một chữ nào (`bigfoot`, `area 51`, `antarctica`) |
| **R2** | Giải thích ≤1 câu mà vẫn kích tò mò (`operation highjump`, `missing 411`) |
| **R1** | Cần ≥2 câu, nghe như bài giảng |

**② KGC — người gõ cụm đó, thấy ai đang nói, có tin không?**

Uy tín CẢM NHẬN. Với The Why Files:
- **Tập solo**: AJ là người kể chuyện/tổng hợp hồ sơ. KGC cao khi đoạn bám vào
  **bằng chứng cụ thể** (tài liệu, ảnh, lời khai, nhân chứng có tên); trung bình
  khi chỉ là giả thuyết/lời đồn.
- **The Basement**: KGC theo khách. Nhà nghiên cứu/tác giả/nhân chứng trực tiếp
  của chủ đề → cao; khách nói ngoài vùng chuyên môn → trung bình.

| KGC | Hệ quả cho Bước 2–4 |
|---|---|
| **Cao** | Title/thumbnail không cần chứng minh thêm |
| **Trung bình** | Title **phải** hiện nguồn uy tín (Format 1C: tài liệu, nhân chứng, credential của khách) VÀ thumbnail **phải** có bằng chứng nhìn thấy được |
| **Thấp** | Dừng — đây là clickbait, báo người dùng thay vì viết title |

> **R1 + KGC cao** → vẫn viết, nhưng title bắt buộc có **cầu nối sang cụm R3**.
> Vd `operation tabarin` (R1) → *"Operation Tabarin: The Secret WWII Base Hidden in Antarctica"*.

**4. Keyword vệ tinh** — 0–2 cụm phụ (từ `satellite_keywords` hoặc tự rút).

> Output phần này bằng Tiếng Việt, ngắn gọn. **Bắt buộc in rõ:**
> `Keyword hạt nhân: "<cụm>" · Reach <R?> · KGC <cao/trung bình>`
> và `Loại tập: solo / The Basement (khách: <tên>) / compilation`

---

## BƯỚC 2 — Tối ưu Title & Metadata (SEO)

> ⚠️ Toàn bộ phần này viết bằng TIẾNG ANH.

### 3 TITLES

#### 🔑 LUẬT KEYWORD — ÁP TRƯỚC MỌI LUẬT KHÁC

1. **Keyword hạt nhân NGUYÊN VĂN trong cả 3 title của cả 2 format.** Được thêm
   từ quanh nó, không được thay nó (`bigfoot` không thành *"a mysterious ape"*).
2. **Keyword trong 5 từ đầu.**
3. **`The Why Files` bắt buộc có trong mọi title, nhưng KHÔNG đứng ở 3 từ đầu.**
   Thương hiệu nằm ở đuôi (sau `|` hoặc `on The Why Files`). Đầu title dành cho
   keyword và hook.
   ```
   ❌ The Why Files: Operation Highjump Explained
   ✅ Operation Highjump: What Admiral Byrd Found in Antarctica | The Why Files
   ```
4. **Reach = R1 → cầu nối sang cụm R3** (giữ keyword gốc nguyên văn, bọc nó
   trong khung người ngoài cũng hiểu).
5. **KGC = trung bình → nguồn uy tín nằm TRONG title** (Format 1C).
6. **Độ dài 9–14 từ**, trần 100 ký tự.
7. **Khối là một CÂU CHUYỆN có thật** (nhân vật + mốc thời gian + diễn biến + kết
   cục) → cân nhắc chữ `Story` / `True Story` / `Case`. Show này phần lớn là hồ
   sơ vụ việc nên tín hiệu này hợp hơn kênh JRE; chỉ dùng khi thật sự là câu chuyện.
8. **Không dùng `AJ Gentile` thay cho `The Why Files`.** Có thể thêm `AJ` hoặc
   `Hecklefish` khi chính họ là hook (khoảnh khắc Hecklefish viral), nhưng
   `The Why Files` vẫn phải có.

#### CÂY QUYẾT ĐỊNH SUBJECT & ĐUÔI TITLE

| Tình huống | Cấu trúc |
|---|---|
| Tập solo / compilation | `[Keyword + hook] \| The Why Files` |
| The Basement, chủ đề nổi hơn khách (thường gặp) | `[Keyword + hook] \| [Tên khách] on The Why Files` |
| The Basement, khách là thứ người ta săn tìm (vd David Paulides + missing 411) | `[Tên khách]: [Keyword + hook] \| The Why Files` — tên khách được đứng đầu, keyword ngay sau dấu `:` |
| Khách có thẩm quyền hiếm nhưng tên vô danh | **Format 1C — danh xưng thay tên**: `A [Credential] Reveals [Keyword]... \| The Why Files` |

#### 🚫 GATE KIỂM TRA TRƯỚC KHI CHỐT TITLE (áp cho từng title)

| # | Câu hỏi | Không đạt → làm gì |
|---|---|---|
| 1 | Keyword hạt nhân **nguyên văn** trong title? | Viết lại title, không viết lại keyword |
| 2 | Keyword trong **5 từ đầu**? | Đảo cấu trúc |
| 3 | Có `The Why Files`? Có lọt vào 3 từ đầu không? | Thiếu → thêm vào đuôi. Ở đầu → chuyển xuống đuôi |
| 4 | `keyword_credibility = medium`: nguồn uy tín có trong title chưa? | Chuyển sang Format 1C |
| 5 | `keyword_reach = R1`: có cầu nối sang cụm R3 chưa? | Viết lại phần bọc quanh keyword |
| 6 | Dài 9–14 từ, < 100 ký tự? | Cắt hoặc bổ sung |
| 7 | Tập The Basement: tên khách có mặt đúng theo bảng đuôi chưa? | Sửa đuôi |

**Gate thẩm quyền:** title không được hứa điều đoạn clip không đưa ra. AJ hay
nói "theory", "some believe": **không biến giả thuyết thành sự thật** trong
title. ❌ `Proof Hitler Escaped to Antarctica` khi đoạn chỉ kể lại giả thuyết.
✅ `Did Hitler Escape to Antarctica? The Operation Highjump Theory | The Why Files`.

---

Xuất **cả 2 format** thành 2 bảng: 3 title Format 1 + 3 title Format 2.
Format 1C là biến thể của Format 1 (không thành bảng thứ 3).

#### QUY TẮC SỐ LIỆU CỤ THỂ

Con số cụ thể làm title có cảm giác thật và tăng CTR (năm xảy ra, số người mất
tích, độ sâu, khoảng cách, số ngày, tuổi nạn nhân…). Khán giả mystery đặc biệt
bị hút bởi **năm** và **số người** (*"9 Hikers"*, *"In 1947"*).

> ⚠️ **RÀNG BUỘC CỨNG:**
> - **CHỈ dùng con số XUẤT HIỆN THẬT trong transcript.** Cấm bịa, làm tròn kịch
>   tính, suy diễn, hoặc lấy số từ tên file nếu không được nói trong nội dung.
> - Không xác thực được 100% → **KHÔNG DÙNG.**
> - Gán đúng đối tượng (năm xảy ra ≠ năm giải mật ≠ năm phát sóng).
> - Đã dùng số → ghi ngay dưới bảng: số đó lấy từ dòng/timestamp nào.

#### FORMAT 1 — Trực diện (Fact-bomb)

Nói thẳng chi tiết sốc nhất / bằng chứng lạ nhất ngay trong title.

```
[Keyword] + [chi tiết sốc] | The Why Files
[Keyword] + [chi tiết sốc] | [Tên khách] on The Why Files      (The Basement)
[Tên khách]: [Keyword] + [chi tiết sốc] | The Why Files        (khách là thứ người ta tìm)
```

Ví dụ:
- `Operation Highjump: The Antarctic Mission the Navy Never Explained | The Why Files`
- `Missing 411: Hikers Who Vanished Without a Trace | David Paulides on The Why Files`

#### FORMAT 1C — Nguồn uy tín thay tên (Credential / Evidence-forward)

Dùng khi KGC trung bình, hoặc khách có thẩm quyền hiếm nhưng tên vô danh.
Subject là **danh xưng** hoặc **bằng chứng** thay vì cái tên:

```
A Former [Credential] Reveals What's Really Behind [Keyword] | The Why Files
The Declassified [Document] That Changes Everything About [Keyword] | The Why Files
[Keyword]: What the [Witnesses / Search Teams / Files] Actually Found | The Why Files
```

> ⚠️ Danh xưng/bằng chứng phải **xác thực được** từ transcript hoặc
> `guest_profile`. **Cấm nâng cấp cho kêu** ("a researcher" không thành
> "a CIA insider"; "a leaked memo" không thành "declassified files" nếu transcript
> không nói là giải mật).

#### FORMAT 2 — Câu hỏi gợi mở (Curiosity-Gap)

Đóng khung thành câu hỏi mở mà khán giả mystery **bắt buộc bấm vào** để biết
đáp án. Show này vốn kết thúc bằng câu hỏi mở nên format này rất hợp.

1. **Đặt mình vào ghế khán giả The Why Files**: *"Chủ đề này khiến người mê bí
   ẩn tò mò NHẤT điều gì?"* — chuyện gì thật sự đã xảy ra, ai che giấu, thứ gì ở
   dưới đó, vì sao không ai tìm thấy…
2. **Khóa keyword hạt nhân vào title.**
3. **KHÔNG tiết lộ đáp án/punchline**, nhưng câu hỏi phải được đoạn clip trả lời
   thật hoặc bàn tới thật (không hỏi điều clip không đụng tới).
4. Không gò khuôn. Gợi ý mềm:
   ```
   What Really Happened at [Keyword]? | The Why Files
   What Did They Find Under [Keyword]? | The Why Files
   Why Did the Government Hide [Keyword]? | The Why Files
   [Keyword]: Who — or What — Was Really Behind It? | The Why Files
   Is [Keyword] Real? [Guest] Thinks So | The Why Files
   ```

Mỗi title (cả 2 format): < 100 ký tự · đánh vào Big Hook · keyword nguyên văn ·
có `The Why Files` ở đuôi · không clickbait rỗng · ghi lý do chọn cấu trúc ngay
dưới bảng.

**Trình bày:** 2 bảng, cột `#`, `Title`, `Angle`, `Ký tự`:
- Bảng A — **Format 1 (Trực diện)**
- Bảng B — **Format 2 (Câu hỏi gợi mở)**

#### ⚠️ KIỂM TRA ĐUÔI TITLE — BẮT BUỘC TRƯỚC KHI XUẤT, KỂ CẢ LƯỢT SỬA LẠI

| Loại tập / cấu trúc | Đuôi BẮT BUỘC | Lỗi hay gặp |
|---|---|---|
| Solo / compilation | `\| The Why Files` | Quên thương hiệu; dùng `\| AJ Gentile` |
| The Basement, content-forward | `\| [Tên khách] on The Why Files` | Viết `\| The Why Files` rồi quên tên khách |
| The Basement, khách đứng đầu | Đầu `[Tên khách]:`, đuôi `\| The Why Files` | Để keyword trôi xuống cuối |
| Format 1C | `\| The Why Files` (danh xưng đã thay tên khách) | — |
| Format 2 hết chỗ (100 ký tự) | Được bỏ tên khách, **không bao giờ bỏ `The Why Files`** | Bỏ khi thật ra vẫn còn ký tự |

---

### DESCRIPTION

150–250 từ, theo thứ tự:

1. **Dòng đầu**: tên tập gốc chuẩn, vd
   `The Basement: Brad Olsen | Antarctica's Forbidden Zones` hoặc tên tập The Why
   Files gốc. Không rõ tên tập → bắt đầu thẳng bằng hook.
2. **Hook mạnh** (câu thứ hai): chứa keyword hạt nhân, gây tò mò ngay.
3. **Body**: tóm tắt bí ẩn / bằng chứng / giả thuyết của đoạn. Keyword hạt nhân
   **3–4 lần** tự nhiên. Giữ giọng show: tò mò, hoài nghi lành mạnh, không khẳng
   định điều chưa được chứng minh.
4. **CTA** ngắn: subscribe, bell, *"Watch the full episode on The Why Files"*.
5. Dòng cuối luôn là: `⏱ TIMESTAMPS BELOW`

### TIMESTAMPS

> ⚠️ **QUY TẮC GỐC THỜI GIAN:** timestamp tính từ **đầu clip đã cắt**, mốc đầu
> luôn `0:00`. Transcript nguyên tập (timestamp gốc kiểu `00:21:54`) → **bắt
> buộc trừ offset**: `timestamp_hiển_thị = timestamp_gốc − start` (`start` từ
> cutlist hoặc dòng "Thời gian: X → Y" ở đầu transcript).
> Vd clip từ `00:21:54`, khoảnh khắc ở `00:26:30` → hiển thị `4:36`.
> Không xác định được `start` → hỏi 1 lần (chế độ tự động: ghi cảnh báo). Tuyệt
> đối không xuất timestamp gốc của tập.

8–12 mốc, format `0:00 — [Mô tả gợi tò mò]`. Đặt tên mốc như chương của một hồ
sơ (*"The first sighting"*, *"What the search team found"*, *"The theory nobody
talks about"*).

> ⚠️ **ĐỘ PHỦ TOÀN CLIP:** `% phủ = mốc_cuối / (end − start)`. **< 80%** → quay
> lại transcript, bổ sung mốc ở đoạn bị bỏ trống. Mốc cuối rơi vào 85–100%.

### TAGS

> ⚠️ **GIỚI HẠN CỨNG YOUTUBE: 500 ký tự tổng** (tính cả `", "`). Nhắm **≤480**.

Bộ tag cố định đứng đầu (đúng thứ tự, không đổi):

```
The Why Files, Why Files, AJ Gentile, Hecklefish, The Why Files podcast,
The Basement, mystery, unsolved mysteries, conspiracy, paranormal,
true story, documentary,
```
(12 tag, **163 ký tự** khi nối bằng `", "` — trừ ra trước khi tính ngân sách
còn lại. Tập không phải The Basement vẫn giữ tag `The Basement`.)

Tags nội dung, thứ tự ưu tiên giảm dần (vượt giới hạn thì cắt từ cuối):

1. **Keyword hạt nhân** — luôn đứng đầu, không bao giờ bị cắt
2. Biến thể của keyword (cách gõ khác, số ít/nhiều, viết tắt, lỗi gõ phổ biến) + `satellite_keywords`
3. Tên khách mời (The Basement)
4. Tên riêng nhân vật / vụ án / địa danh trọng tâm của Big Hook
5. Hiện tượng / khái niệm cốt lõi (`cryptid`, `ufo`, `missing persons`, `cold case`…)
6. Tên riêng phụ
7. Từ khóa ngách / trending liên quan

**Quy trình bắt buộc:** soạn 15–25 tag nội dung → nối toàn bộ (12 cố định + nội
dung) bằng `", "` → **đếm ký tự thực tế** (không ước lượng) → > 480 thì cắt từ
cuối danh sách nội dung, không bao giờ cắt bộ cố định hay keyword hạt nhân →
ghi `(Tổng: N/500 ký tự)` ngay dưới khối tags.

#### QUY TẮC CHÍNH TẢ TÊN RIÊNG — BẮT BUỘC

Transcript auto-caption sai tên riêng liên tục (Hecklefish → *"Heckle fish"*,
Paulides → *"Polities"*, Dyatlov → *"Diatlov"*, Göbekli Tepe → *"Gobekly Teppe"*).
Title, tags, description lên thẳng YouTube: sai một chữ là mất search volume.

1. Không bao giờ copy tên riêng theo transcript; dùng chính tả chuẩn.
2. Có cutlist → lấy `episode.guest`, tên trong `summary_en` làm chuẩn.
3. Không chắc → **tra web** trước khi đưa vào title/tags.
4. Áp cho mọi tên riêng: người, địa danh, tổ chức, chiến dịch, sinh vật, thuật ngữ.
5. Biến thể hay gõ sai → bản chuẩn ở title, bản biến thể vào tags.

---

## BƯỚC 3 — Thumbnail: chọn nội dung cho 3 ô

### Bố cục (cùng khung 3 ô với kênh JRE để dùng chung công cụ `frames.py`)

Thumbnail 1920×1080, 3 ô:

| Ô | Vị trí | Nội dung |
|---|---|---|
| **TRÁI** | `left≈0`, rộng ≈1120 | **AJ Gentile**: khung cắt từ chính video, biểu cảm khớp vibe |
| **PHẢI** | `left≈950`, rộng ≈970 | **Khách** (The Basement). Tập solo/compilation không có khách → **khung hình mạnh nhất lấy từ chính video**: nhân vật trung tâm của vụ việc, ảnh tư liệu/hiện trường mà tập đang chiếu, hoặc Hecklefish nếu vibe `Funniest` |
| **GIỮA** | ≈624×913 (dọc ~2:3), viền màu 12px | **Ảnh nội dung = chính keyword hạt nhân** |

Show chưa có template Canva riêng: Studio chỉ dựng **bản mock** để duyệt. Khi
người dùng đặt template cho show WHYFILES ở Cài đặt, dùng template đó thay cho
template JRE.

### A. Ô GIỮA — ảnh nội dung

> ⚠️ Ô giữa **không bao giờ** là AJ hay khách (đã ở hai bên).

**Quy tắc subject:** *"Người vừa gõ keyword hạt nhân, nhìn ô giữa có thấy ĐÚNG
THỨ HỌ VỪA GÕ không?"*

| Keyword là | Subject ô giữa | Ví dụ |
|---|---|---|
| Vụ án / sự kiện có thật | Ảnh hiện trường / tư liệu thật của chính vụ đó | `dyatlov pass` → ảnh chiếc lều rách trên tuyết (ảnh tư liệu 1959) |
| Chiến dịch / chính phủ | Ảnh tư liệu thật của chiến dịch, tài liệu có dấu mật | `operation highjump` → tàu/máy bay Navy giữa băng Nam Cực |
| Địa danh | Chính nơi đó, ảnh thật, góc rợn nhất | `antarctica` → vách băng / vùng băng mênh mông lúc chạng vạng |
| Sinh vật bí ẩn | Không có ảnh thật đáng tin → **AI**, dạng ảnh trail-cam/ảnh tài liệu thô | `bigfoot` → bóng to lớn giữa rừng, ảnh trail-cam nhiễu hạt |
| Người mất tích | Cảnh nơi mất tích (rừng, đường mòn) hoặc ảnh tư liệu thật nếu công khai | `missing 411` → đường mòn rừng sâu, ba lô bỏ lại |
| Cổ đại / tôn giáo | Hiện vật/di tích thật; thực thể thần thoại → AI | `göbekli tepe` → cột đá chạm khắc thật |
| Câu hỏi / nỗi sợ | Hình ảnh của TRẠNG THÁI câu hỏi | `what's under antarctica` → lối vào hang tối dưới lớp băng |

**KGC = trung bình** → ô giữa bắt buộc mang bằng chứng nhìn thấy được (tài liệu
thật, ảnh hiện trường thật, thiết bị đo, dấu vết vật lý).

#### Nguồn ảnh: ẢNH THẬT mặc định, AI chỉ là phương án cuối

1. Ảnh thật tự do bản quyền: Wikimedia Commons, NASA, NOAA, US Navy/DoD/DVIDS,
   FBI Vault, National Archives, Library of Congress.
2. Ảnh thật báo chí/tư liệu khác — ghi rõ nguồn.
3. **AI chỉ khi chủ đề không thể có ảnh thật**: cryptid, alien, thực thể
   paranormal, thần thoại, cảnh chỉ có lời kể. **Cấm** dùng AI vì lười tìm.

Tìm ảnh thật: WebSearch `"<keyword>" photo` / `site:commons.wikimedia.org <keyword>`;
lấy URL ảnh gốc (`.jpg`/`.png`); ưu tiên ảnh dọc hoặc subject ở giữa, ≥ 800px
cạnh ngắn, không chữ/watermark.

Prompt AI (tiếng Anh):
```
[Subject: keyword hạt nhân NGUYÊN VĂN + mô tả cụ thể], [bối cảnh thật],
[cảm xúc: dread, unease]. Raw found-footage / trail-cam / archival documentary
photo, harsh practical light, deep shadows, film grain, visible texture.
No text, no logo, no CGI look, no glossy lighting. NOT AJ Gentile. NOT a podcast guest.
```

**TEST CHE TITLE** (gate cuối, kể cả lượt sửa): che title, đưa thumbnail cho
người lạ — đoán được keyword không? Không → đổi ảnh giữa.

### B. Ô TRÁI / PHẢI: biểu cảm

Khung cắt từ **chính video của đoạn** (không dùng ảnh mạng cho AJ/khách):

| Vibe | AJ (trái) | Khách / ô phải |
|---|---|---|
| `Scariest` | Nghiêm, cau mày, nghiêng người tới trước | Trầm, ánh mắt ám ảnh / ảnh hiện trường tối |
| `Most Mysterious` | Nhíu mày nghi hoặc, tay chống cằm | Đang giải thích, ánh mắt chắc chắn |
| `Most Mind-Blowing` | Mắt mở to, miệng hé | Tay đang diễn tả, nói với cường độ cao |
| `Most Controversial` | Nhướn mày hoài nghi | Quả quyết |
| `Funniest` | Cười lớn | Hecklefish / khách cười |

Loại khung: mắt nhắm, đang uống/nhai, micro che quá nửa mặt, nhòe, mặt quá nhỏ,
caption/lower-third đè mặt, khung chia đôi màn hình, có hai người trong một ô.
Hai bên nhìn **về phía ô giữa**; lật ngang chỉ khi trong khung không có chữ đọc
được.

**Output Bước 3** (Tiếng Việt, ngắn): subject ô giữa + nguồn ảnh (link hoặc "AI
vì …") · mốc giây khung AJ + biểu cảm · mốc giây khung phải + biểu cảm/nội dung.

---

## BƯỚC 4 — Dựng thumbnail

Dùng đúng công cụ và quy trình như skill `viet-tittle` (script
`E:\Tool\jre-thumb\frames.py`: `sheet` → `grab` → `crop` → `fill` → `mock` →
`verify`), chỉ thay **Joe → AJ** và **khách → khách hoặc khung nội dung ô phải**:

1. Lấy video của đoạn (clip đã cắt, hoặc tập gốc + `--start/--end`).
2. `sheet` để duyệt khung, chọn 1 mốc cho AJ, 1 mốc cho ô phải; `grab` khung
   full-res, Read lại để chắc đúng người/đúng biểu cảm.
3. **Crop mặt bắt buộc**: đọc hộp đầu trên `frame_<t>_grid.jpg`, `crop --head
   ... --side left/right`; `OVERLAP` → không dùng. Hai đầu cao xấp xỉ nhau
   (~700px), ngang hàng. Ô phải là ảnh tư liệu (không phải mặt người) → `fill`
   cho subject vào giữa dải còn lộ.
4. Ô giữa: ảnh thật tải bằng `curl` (Wikimedia bắt buộc kèm User-Agent), hoặc AI
   theo luật ở trên; `fill` vào ô giữa.
5. **Dựng mock 1920×1080 và tự soát** (mặt AJ/khách trọn vẹn, không khuất sau ô
   giữa · hai đầu cân · subject ô giữa nhận ra ngay keyword · đọc được ở 320px).
6. Có template Canva của show → chỉ áp lên Canva và export khi người dùng duyệt
   mock (copy template, không sửa bản gốc; JPG ≤ 2 MB; `verify` bản export với
   mock). Không có template → dừng ở mock.

**Output Bước 4:** đường dẫn mock/thumbnail + bảng nguồn 3 ô (AJ @ giây X · ô
phải @ giây Y · ô giữa: nguồn/AI) + dòng **Check back**.

---

## CONSTRAINTS CHUNG

| Yếu tố | Quy tắc |
|---|---|
| **🔑 Keyword hạt nhân** | Cụm khán giả gõ vào ô tìm kiếm. Lấy từ `core_keyword` nếu có, **không tự đổi**. Cấm dùng `the why files` / tên host / tên khách làm keyword (trừ khi khách là thứ người ta tìm) |
| **Keyword trong title** | Nguyên văn, trong 5 từ đầu. 9–14 từ, < 100 ký tự |
| **Thương hiệu** | `The Why Files` BẮT BUỘC trong mọi title, ở đuôi, không ở 3 từ đầu. Không thay bằng `AJ Gentile` |
| **Đuôi title** | Solo/compilation: `\| The Why Files` · The Basement: `\| [Khách] on The Why Files` · Format 2 hết chỗ: bỏ tên khách được, bỏ thương hiệu thì không. Kiểm lại ở mọi lượt sửa |
| **Gate thẩm quyền** | Không biến giả thuyết/lời đồn thành sự thật trong title; không nâng cấp danh xưng/bằng chứng |
| **Reach × KGC** | `R1` → cầu nối sang cụm R3. `KGC trung bình` → Format 1C + bằng chứng nhìn thấy được trên thumbnail. `KGC thấp` → dừng, báo |
| **Số liệu** | Chỉ số có thật trong transcript, gán đúng đối tượng, ghi nguồn dòng |
| **Chính tả** | AJ Gentile, Hecklefish, tên khách/vụ án/địa danh chuẩn; không chắc → tra web. Biến thể gõ sai → tags |
| **Description** | Dòng đầu = tên tập gốc (nếu có). Keyword 3–4 lần, 1 lần ở câu hook. Dòng cuối `⏱ TIMESTAMPS BELOW` |
| **Timestamps** | Từ đầu clip, mốc đầu `0:00`, trừ offset `start`. 8–12 mốc. Mốc cuối phủ ≥ 85% clip |
| **Tags** | 12 tag cố định đứng đầu, keyword hạt nhân đầu danh sách nội dung, tổng ≤ 480 ký tự, đếm thật, cắt từ cuối |
| **Thumbnail** | AJ trái · khách (hoặc khung nội dung từ chính video) phải · ô giữa là CHÍNH keyword, ảnh thật trước, AI chỉ khi không thể có ảnh thật · test che title |
| **Ngôn ngữ output** | Title, description, tags, timestamps, prompt AI → Tiếng Anh. Phân tích → Tiếng Việt |
| **Image style** | Raw, gritty, found-footage / archival documentary. Không glossy, không staged |

---

## GHI CHÚ VỀ DỮ LIỆU

Skill gốc `viet-tittle` có các luật dựa trên số đo của kênh JRE Clips (title
9–14 từ, tín hiệu `Story`, vị trí tên host). Skill này **giữ các luật đó như giả
thuyết làm việc** vì cùng là khán giả YouTube Mỹ dạng clip podcast, nhưng chưa
đo trên kênh The Why Files Highlights. Khi kênh có ≥ 30 video, đo lại: title có
`The Why Files` ở đuôi vs không, có số/năm vs không, Format 1 vs Format 2, rồi
chỉnh luật.
