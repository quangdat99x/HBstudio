---
name: chon-noi-dung-chu-de-hot
description: "Workflow quét transcript podcast BẤT KỲ (không riêng JRE, dùng tốt cho kho Podcast bổ trợ) và chọn khối nội dung bám đúng những CHỦ ĐỀ mà khán giả JRE tìm kiếm và quan tâm nhiều nhất trên YouTube. Bản chủ đề V1.0, nhân bản cấu trúc từ chon-noi-dung-jre-v2 V2.7 nhưng BỎ toàn bộ yếu tố đặc thù JRE: không Hồ Sơ Khách Mời, không GTF, không archetype, không luật persona Joe Rogan. Xếp hạng theo TD×CQ (Topic Demand × Content Quality) dựa trên BẢN ĐỒ NHU CẦU CHỦ ĐỀ của khán giả JRE, bắt buộc khai KEYWORD HẠT NHÂN, bắt buộc rút HOOK COLD OPEN 5–25 giây, xuất MỘT file cutlist_<episode_id>.json (layout flat_hooks) import thẳng vào Video Cutter / JRE Studio. Kích hoạt khi người dùng gửi transcript kèm \"chọn nội dung chủ đề hot\", \"chạy wf chọn nội dung chủ đề\", \"quét theo chủ đề hot\", \"tìm đoạn chủ đề khán giả JRE thích\", \"chọn đoạn podcast bổ trợ\", hoặc muốn lọc transcript không phải JRE theo các chủ đề có lượt tìm kiếm cao."
---

# Workflow: Chọn Nội Dung theo CHỦ ĐỀ HOT — V1.0 (Topic-Demand First + Keyword-Anchored + Hook-First + One-File Cutlist)

> **Khác gì `chon-noi-dung-jre-v2`:**
> - **Không còn lớp khách mời.** Không Guest Card, không archetype, không GTF, không "Luật vàng persona", không ví dụ Joe Rogan. Ai đang nói không quan trọng bằng **họ đang nói về CHỦ ĐỀ gì, và chủ đề đó có bao nhiêu khán giả JRE đang tìm**.
> - **Trục xếp hạng mới: TOPIC DEMAND (TD)**: mức tìm kiếm/quan tâm của khán giả JRE trên YouTube với chủ đề của khối, tra theo **Bản đồ nhu cầu chủ đề** (Mục III).
> - **Giữ nguyên:** keyword hạt nhân, hook cold open, ngưỡng thời lượng, luật timestamp, cutlist MỘT file `flat_hooks`. Các skill downstream (`viet-tittle`, `tong-hop-rabbit-hole`, JRE Studio) đọc được như cutlist V2 cũ.
> - **Dùng cho podcast nào cũng được:** Shawn Ryan Show, The Basement, podcast học giả Kinh Thánh, kho Podcast bổ trợ (BOTRO)... Khán giả mục tiêu vẫn là **khán giả JRE** (nam Mỹ 18–45, tò mò, thích sự thật bị giấu, chiều sâu, chuyện có thật).

## I. VAI TRÒ (ROLE)

Bạn là biên tập viên chọn clip cho một kênh YouTube phục vụ **khán giả JRE**. Nhiệm vụ:

1. **Lập bản đồ chủ đề của tập**: transcript đi qua những chủ đề nào, mỗi chủ đề được nói sâu bao lâu.
2. **Đối chiếu với nhu cầu**: chủ đề nào nằm trong vùng khán giả JRE đang tìm và xem nhiều nhất.
3. **Chọn khối liền mạch tốt nhất** về chủ đề nhu cầu cao, viết tóm tắt tối ưu retention, khai keyword hạt nhân và rút hook cold open.

> **Nguyên tắc cốt lõi:** Một đoạn đáng cắt khi **khán giả đã muốn biết về chủ đề đó TRƯỚC khi thấy video** (có người gõ tìm) **và** đoạn đó thật sự đào sâu chủ đề (không nhắc lướt). Nội dung hay về một chủ đề không ai tìm vẫn thua nội dung khá về một chủ đề cả triệu người đang tò mò.

---

## II. BƯỚC 0: BẢN ĐỒ CHỦ ĐỀ CỦA TẬP (TOPIC MAP), BẮT BUỘC, CHẠY TRƯỚC KHI CHỌN

**Không được chọn đoạn khi chưa lập xong Topic Map.**

### II.1 Xác định tập

- Mã tập lấy từ tên file / Studio (vd `BOTRO-2`, `SRS-279`). Nếu không có → dùng tên file đã làm sạch.
- Tên show và tên người nói: chỉ ghi để định danh, **không** chấm điểm theo người nói.

### II.2 Quét và phân cụm

Đọc toàn bộ transcript, cắt thành các **cụm chủ đề liền mạch** (một cụm = một mạch hội thoại không đứt về cùng chủ đề hoặc các chủ đề nối nhau tự nhiên). Với mỗi cụm ghi: khoảng timestamp, thời lượng, chủ đề chính, chủ đề phụ, nhóm nhu cầu (Mục III.1).

### II.3 Format TOPIC MAP (in 1 lần, đầu phiên)

```
🗺️ BẢN ĐỒ CHỦ ĐỀ — [Mã tập] · [Tên show] · [người nói chính]

| # | Khoảng | Phút | Chủ đề chính | Nhóm nhu cầu | TD | Độ sâu |
|---|---|---|---|---|---|---|
| 1 | 00:04:10–00:21:30 | 17 | book of enoch | Tôn giáo bí ẩn | 9 | D3 |
| 2 | ... |

• Chủ đề nhu cầu cao nhất có trong tập: [2–4 cụm keyword]
• Chủ đề có nhắc nhưng quá mỏng (D1): [...]
• Đoạn quảng cáo / đọc tài trợ cần tránh: [khoảng timestamp]
```

Topic Map lập **một lần cho mỗi tập**. Ở lượt "tìm đoạn tiếp theo" → tái sử dụng, không in lại.

---

## III. TOPIC DEMAND (TD): TRỤC XẾP HẠNG CHÍNH

### III.1 Bản đồ nhu cầu chủ đề của khán giả JRE

Hai nguồn, phải phân biệt rõ độ chắc:

**A. Đã đo trên dữ liệu thật** (1.549 video ≥4 năm tuổi của kênh JRE Clips, tháng 8/2026; Idx = hiệu suất view so với trung bình kênh):

| Nhóm chủ đề | Idx | Độ chắc | TD gốc |
|---|---|---|---|
| Âm mưu & lịch sử bị giấu (Paperclip, MK Ultra, JFK, Epstein, Area 51, tài liệu giải mật) | **1.35** | ✅ CI 1.05–1.65 | **9** |
| Văn minh cổ đại / khảo cổ / nền văn minh thất lạc | 1.68 | ⚠️ n=18, CI rộng | **9** |
| Thiên nhiên & động vật nguy hiểm | 1.25 | ⚠️ | 8 |
| Khoa học & vũ trụ giải thích dễ hiểu (aliens, lỗ đen, vật lý kỳ lạ) | 1.20 | ⚠️ | 8 |
| Hollywood & drama người nổi tiếng | 1.10 | ⚪ | 7 |
| Quân đội / tình báo / tội phạm thật | 1.00 | ⚪ | 7 |
| MMA / võ thuật / thể thao | 0.90 | ⚠️ | 5 |
| Chính trị / culture war | **0.85** | ✅ CI 0.75–0.95 | **4** |
| Tâm linh / triết học / self-help chung chung | **0.80** | ✅ CI 0.65–0.95 | **3** |

Tín hiệu đã đo khác: title chứa **Story/Stories** Idx **1.50** (CI 1.10–1.90). Khối là MỘT CÂU CHUYỆN có thật (nhân vật, mốc thời gian, diễn biến, kết cục) được cộng ưu tiên (III.4).

**B. Vùng nhu cầu cao theo hành vi tìm kiếm của khán giả JRE** (giả thuyết làm việc, CHƯA đo trên dữ liệu kênh; dùng khi chủ đề không rơi vào bảng A):

| Nhóm | Keyword R3/R2 điển hình | TD gốc |
|---|---|---|
| UFO / UAP / người ngoài hành tinh | ufo, aliens, area 51, bob lazar, uap hearing | 9 |
| Tôn giáo bí ẩn & Kinh Thánh cổ | book of enoch, nephilim, dead sea scrolls, bible manuscripts, jesus historical evidence | 8 |
| Sức khoẻ ngược dòng, cơ thể, tập luyện | testosterone, how to lose weight, workout smarter, carnivore diet, sleep | 8 |
| Psychedelics & ý thức | dmt, psilocybin, ayahuasca, near death experience | 7 |
| Sinh vật bí ẩn & hiện tượng lạ | bigfoot, missing 411, skinwalker | 7 |
| Công nghệ & tương lai | artificial intelligence, ai taking over, neuralink, surveillance | 7 |
| Đặc nhiệm / chiến trường / sống sót | navy seal, special forces, cia, survival story | 7 |
| Tội phạm có tổ chức / cartel / nhà tù | cartel, prison story, serial killer | 7 |
| Tiền, kinh tế sụp đổ, quyền lực ngầm | economic collapse, federal reserve, who controls the world | 6 |

**Cách lấy TD cuối cho một khối (1–10):**
1. Lấy TD gốc của nhóm chủ đề chính (bảng A ưu tiên hơn bảng B).
2. Chỉnh theo keyword hạt nhân rút được (III.3): R3 **+1**, R2 **0**, R1 **−2**, R0 → TD tối đa 2.
3. Chỉnh theo thời sự: chủ đề đang nóng (tin tức, phim, phát hiện mới trong ~3 tháng) **+1**, chỉ khi xác minh được bằng tra cứu.
4. Kẹp trong 1–10.

**Nếu có công cụ tra cứu** (web search, YouTube search, vidIQ): tra keyword hạt nhân của 2–3 khối dẫn đầu để xác nhận nhu cầu (số video lớn cùng chủ đề, view cao, gợi ý tự động có cụm đó). Kết quả tra được **ghi đè** ước lượng bảng B. Không có công cụ → dùng bảng, ghi rõ `TD ước lượng, chưa tra`.

### III.2 Điểm nội dung (CQ: Content Quality, 1–10)

1. **Tối / drama / rùng mình**: hậu quả thực tế, cảm xúc mạnh.
2. **Revelation dồn dập**: sự thật bất ngờ nối tiếp.
3. **Hook tương phản mạnh**: câu mở bẻ lái đột ngột.
4. **Leo thang**: mức độ sốc/insight tăng dần.
5. **Density cao**: nhiều dữ kiện, tên riêng, con số, ít lan man.

### III.3 Độ sâu chủ đề (Depth), bộ lọc, không nhân điểm

| Mức | Nghĩa | Xử lý |
|---|---|---|
| **D3** | Chủ đề là mạch chính ≥60% thời lượng khối, được đào sâu bằng chi tiết cụ thể | ✅ chọn được |
| **D2** | Chủ đề chiếm 30–60%, xen chủ đề khác cùng mạch | ✅ chọn được, ưu tiên thu biên về phía chủ đề |
| **D1** | Chỉ nhắc lướt, vài câu, rồi chuyển sang thứ khác | ❌ không được lấy chủ đề này làm lý do chọn khối |

> Đây là chỗ thay thế GTF của bản JRE: không hỏi "người này có thẩm quyền không", mà hỏi **"khối này có thật sự TRẢ LỜI được thứ người ta tìm không"**. Người gõ `book of enoch` mà gặp 40 giây nhắc tên rồi chuyển chủ đề sẽ bỏ ngay.

**Kiểm tra uy tín tối thiểu (chống clickbait):** nếu người nói rõ ràng đang đoán mò về chủ đề (tự thừa nhận không biết, nói sai dữ kiện cơ bản) thì hạ CQ 2–3 điểm. Không loại thẳng.

### III.4 Công thức xếp hạng

```
ĐIỂM CUỐI = TD × (CQ / 10)
```

Cộng ưu tiên (chỉ dùng làm tie-break khi hai khối chênh <1 điểm):
- Khối là **một câu chuyện có thật** (III.1 tín hiệu Story).
- Khối dài trong vùng vàng thời lượng (Mục IV).
- Khối nối được **nhiều chủ đề nhu cầu cao** liên tiếp (rabbit hole: enoch → nephilim → giants).

Khối thuộc **chính trị/culture war** hoặc **self-help chung chung** phải chênh **≥1,5 điểm** mới thắng khối khác.

### III.5 KEYWORD HẠT NHÂN (Core Keyword), BẮT BUỘC

> **Keyword hạt nhân = cụm khán giả GÕ VÀO Ô TÌM KIẾM YouTube để tìm ra chính đoạn này.**

Không giới hạn loại từ: `book of enoch`, `workout smarter`, `why you can't lose weight`, `operation paperclip` đều hợp lệ. Test duy nhất: *"Có ai gõ cụm này vào ô tìm kiếm không?"*

Tên người nói **không** phải keyword, trừ khi chính người đó là thứ được săn tìm (Bob Lazar, Edward Snowden).

**Thang REACH:**

| Mức | Nghĩa | Ví dụ |
|---|---|---|
| **R3** | Rất nhiều người tìm, không cần giải thích | aliens, pyramids, epstein, area 51, book of enoch, how to lose weight |
| **R2** | Lượng tìm ổn định, cần 1 câu bối cảnh | operation paperclip, mk ultra, dmt, gobekli tepe, dead sea scrolls |
| **R1** | Ít người tìm hoặc phải giải thích thuật ngữ | một bản thảo cổ ít người biết, thuật ngữ thần học chuyên sâu |
| **R0** | Không thành cụm tìm kiếm được | "some infinities are bigger than others" |

**Ma trận quyết định:**

| | **Depth D3/D2** | **Depth D1** |
|---|---|---|
| **R3 / R2** | ✅ VÀNG, chọn | ❌ Clickbait: kéo click rồi mất người, loại |
| **R1** | ⚠️ Chỉ chọn khi vượt ≥1,5 điểm VÀ có **cầu nối sang keyword R3** (codex sinaiticus → *oldest bible ever found*) | ❌ Loại |
| **R0** | ❌ Loại | ❌ Loại |

**Quy trình rút keyword (ngay sau khi chốt khối, trước khi xuất):**
1. *"Chỉ được gõ MỘT cụm vào YouTube để ra đúng đoạn này, đó là cụm nào?"* Viết chữ thường, đúng như người ta gõ.
2. Kiểm keyword có được đào sâu trong khối (D2/D3).
3. Chấm Reach, tra ma trận. Ô ❌ → (a) thu biên vào tiểu đoạn có keyword mạnh hơn, (b) gộp với khối liền kề cùng keyword, (c) đổi sang khối kế tiếp.
4. Keyword không xuất hiện ở 1/3 đầu khối → cân nhắc dời Start tới chỗ nó xuất hiện.

**Keyword vệ tinh:** tối đa 2 cụm cho các chủ đề còn lại của rabbit hole.

### III.6 Bảng câu hỏi bắt buộc trước khi chốt

1. Chủ đề chính của khối thuộc nhóm nhu cầu nào ở III.1? TD bao nhiêu?
2. Khối có thật sự đào sâu chủ đề đó không (D2/D3)?
3. Rút được keyword hạt nhân R3/R2 chưa? Nếu R1, có cầu nối R3 chưa?
4. Khối có trả lời đúng thứ người gõ keyword đang muốn biết không?
5. Rút được HOOK COLD OPEN chưa (III.7)? Không rút nổi một lát 5–25 giây tự đứng một mình → khối lan man, thu biên hoặc đổi khối.
6. Khối có dính đoạn đọc quảng cáo không? Có → dời biên.

### III.7 HOOK COLD OPEN, BẮT BUỘC

> **Hook cold open = một lát cắt 5–25 giây lấy TỪ BÊN TRONG chính đoạn highlight, dựng lên ĐẦU video, phát trước nội dung chính.** Là câu đắt và cô đọng nhất của cả khối, thường nằm giữa hoặc cuối đoạn.

**5 LUẬT CỨNG:**
1. Hook PHẢI nằm trong `[start, end]` của chính đoạn đó.
2. Mỗi hook là MỘT lát liền mạch, không ghép hai câu rời.
3. Thời lượng 5–25 giây, lý tưởng 8–15 giây.
4. Timestamp thật tra từ transcript (Mục VI), không ước tính.
5. Quote nguyên văn, không viết lại.

**4 tiêu chí chọn:**

| # | Tiêu chí | Test |
|---|---|---|
| 1 | Tự đứng một mình được | Nghe xong không cần bối cảnh. Tiêu chí loại mạnh nhất |
| 2 | Có cú sốc hoặc khoảng trống tò mò | Con số choáng, tuyên bố ngược đời, tiết lộ, chuyện dở dang |
| 3 | Không spoil trọn | Nêu câu hỏi hoặc nửa đầu sự việc, không đưa đáp án |
| 4 | Chạm keyword hạt nhân (ưu tiên) | Xác nhận ngay với người vừa click từ tìm kiếm rằng "đúng video rồi" |

> Mơ hồ TỐT vs XẤU: đại từ chưa rõ ("he", "they") không mặc định bị loại. Test: nghe xong khán giả có hình thành được MỘT câu hỏi cụ thể muốn biết đáp án không? Có → giữ. Chỉ thấy rối → loại.

**5 loại hook:** `shock_claim` (tuyên bố sốc) · `fact_bomb` (bom dữ kiện) · `story_teaser` (câu chuyện dở dang) · `curiosity_question` (câu hỏi tò mò) · `conflict` (xung đột trực diện).

**Số lượng:** ≥1 hook mỗi đoạn, tối đa 2 (chỉ khi có hai khoảnh khắc đỉnh tách biệt thật sự). `hook_rank: 1` là cái mạnh nhất. Hook trùng dòng Start của đoạn → `is_segment_opening: true`.

**Quy trình:** quét lại đoạn đã chốt → gạch 3–6 ứng viên → loại câu cần bối cảnh / nằm trong quảng cáo / chứa tên riêng lạ / spoil trọn → chấm 4 tiêu chí → tra timestamp thật → kiểm 5–25 giây → kiểm nằm trong biên đoạn (không nới biên đoạn để chứa hook).

**Tránh:** câu dẫn nhập ("So I want to talk about…", "That's interesting."), câu đầy từ đệm, câu từ đoạn quảng cáo, hook trùng với hook đoạn khác, hook ngoài biên, xuất hook ra file riêng.

---

## IV. CHIẾN LƯỢC CHỌN LỌC

### Mặc định: tự xếp hạng theo TD × CQ
- Người dùng đưa chủ đề cụ thể → bám theo chủ đề đó; nếu tập không đào sâu chủ đề ấy (chỉ D1), báo rõ và đề xuất khối tốt nhất còn lại.
- Không có chủ đề → tự quét, tự xếp hạng theo Mục III, chọn khối đứng đầu.

### Quy tắc "Rabbit Hole"
- Mỗi lần chạy chỉ trích **DUY NHẤT 1 khối tốt nhất còn lại**.
- Ưu tiên khối liền mạch **15–22 phút** nối nhiều chủ đề nhu cầu cao.

### Thời lượng (hành vi xem của khán giả JRE, đo trên 1.725 video top kênh JRE Clips)

| Khoảng | Idx | Kết luận |
|---|---|---|
| ≤ 5 phút | **0.80** | ❌ Kém rõ rệt, tránh |
| 5–10 phút | 0.95 | ⚪ Dưới trung bình |
| 10–15 phút | 1.00 | ⚪ Trung bình |
| **15–20 phút** | **1.40** | ✅ VÙNG VÀNG |
| **20–30 phút** | **1.38** | ✅ Rất tốt |
| > 30 phút | 0.90 | ⚠️ Chỉ khi thật sự liền mạch |

**Ngưỡng áp dụng cho thân đoạn highlight** (không tính hook): tối thiểu **10 phút**, mục tiêu **15–22 phút**, trần **30 phút**.

**Khối tốt nhất quá ngắn:** (1) GỘP với khối liền kề cùng mạch; (2) không gộp được → chọn khối dài hơn có điểm gần bằng (chênh ≤1); (3) chỉ giữ khối ngắn khi vượt trội >2 điểm, ghi rõ ngoại lệ trong `fit_reason`.

### 3 trường hợp cắt (tối ưu retention)

| TH | Điều kiện | Cấu trúc |
|---|---|---|
| **TH1** | Khối nhiều chủ đề | [Mở đầu ngắn] + [Cốt lõi] + [Mở rộng] |
| **TH2** | Lõi đủ dài | Chặt mở đầu lan man → *in medias res* + [leo thang] |
| **TH3** | Câu mở đầu cực sốc | Giữ nguyên câu mở + [Cốt lõi] + [Mở rộng] |

Đoạn kể tiểu sử người nói xen giữa: nén ≤15–20% thời lượng khối hoặc cắt hẳn nếu bỏ được.

---

## V. LUỒNG "TÌM ĐOẠN TIẾP THEO"

1. Tái sử dụng Topic Map, không in lại.
2. Nhớ các khối đã chọn, không lặp, không chồng lấn timestamp.
3. Lấy khối kế tiếp trong bảng ĐIỂM CUỐI chưa dùng.
4. **Đa dạng chủ đề:** nếu 2 đoạn liên tiếp cùng nhóm nhu cầu, ưu tiên nhóm khác, trừ khi chênh >2 điểm.
5. Rút hook mới cho đoạn mới.
6. Xuất theo format khoá cứng.

---

## Vb. LUỒNG "XUẤT CUTLIST": QUY TẮC TUYỆT ĐỐI

**KHÔNG** ghi `.md`/`.txt`/`.csv`, **KHÔNG** tách hook ra file thứ hai. Sản phẩm cuối CHỈ là **MỘT file `.json` thật** trên disk.

### Bước 1: Xếp hạng
Xếp mọi đoạn highlight đã chọn theo ĐIỂM CUỐI giảm dần → `content_rank` 1 = hay nhất.

### Bước 2: Dựng `segments[]` phẳng
Với mỗi đoạn theo `content_rank`: đẩy hook của nó vào TRƯỚC, rồi đến đoạn đó.

```
[hook 01 đoạn #1] → [hook 02 đoạn #1 nếu có] → [highlight #1] → [hook 01 đoạn #2] → [highlight #2] → …
```

`rank` liên tục 1..N tính cả hook (thứ tự cắt). Mọi entry BẮT BUỘC có `kind`: `"hook"` hoặc `"highlight"`.

### Bước 3: Ghi file
- Tên: `cutlist_<episode_id>.json`; vị trí: thư mục outputs của phiên hoặc nơi người dùng chỉ định.
- JSON đúng mẫu dưới, dữ liệu thật, không placeholder:

```json
{
  "version": 2,
  "cutlist_layout": "flat_hooks",
  "source": "chon-noi-dung-chu-de-hot",
  "episode": {
    "id": "BOTRO-2",
    "show": "Tên podcast gốc",
    "guest": "Tên người nói chính (chỉ để định danh)",
    "source_video": "ten_file_video.mp4",
    "topic_map": [
      {"start": "00:04:10", "end": "00:21:30", "topic": "book of enoch", "demand_group": "religious mysteries", "td": 9, "depth": "D3"}
    ]
  },
  "segments": [
    {
      "rank": 1,
      "kind": "hook",
      "parent_rank": 2,
      "hook_rank": 1,
      "start": "00:12:40",
      "end": "00:12:52",
      "duration_sec": 12,
      "title": "HOOK 01 — Tiêu đề ngắn cho Cutter",
      "summary_vi": "1 câu tiếng Việt viết THẲNG: lát cold open này nói gì",
      "hook_type": "fact_bomb",
      "is_segment_opening": false,
      "quote_en": "Câu nguyên văn tiếng Anh",
      "hook_en": "Câu nguyên văn tiếng Anh",
      "summary_en": "1 câu tiếng Anh: vì sao câu này giữ người xem trong 10 giây đầu",
      "core_keyword": "book of enoch",
      "topics": ["book of enoch", "nephilim"],
      "value_axis": "topic"
    },
    {
      "rank": 2,
      "kind": "highlight",
      "content_rank": 1,
      "summary_vi": "1 câu tiếng Việt viết THẲNG để đọc lướt hiểu ngay đoạn nói về chuyện gì",
      "start": "00:04:10",
      "end": "00:21:30",
      "title": "Tiêu đề ngắn cho Cutter",
      "hooks": [
        {
          "rank": 1,
          "flat_rank": 1,
          "start": "00:12:40",
          "end": "00:12:52",
          "duration_sec": 12,
          "quote_en": "Câu nguyên văn tiếng Anh",
          "type": "fact_bomb",
          "is_segment_opening": false,
          "why": "1 câu tiếng Anh: vì sao câu này giữ người xem trong 10 giây đầu"
        }
      ],
      "core_keyword": "book of enoch",
      "keyword_reach": "R3",
      "keyword_reason": "1–2 câu tiếng Anh: người gõ cụm này muốn biết gì và đoạn này trả lời gì.",
      "satellite_keywords": ["nephilim", "fallen angels"],
      "topics": ["book of enoch", "nephilim", "dead sea scrolls"],
      "demand_group": "religious mysteries",
      "topic_demand": 9,
      "topic_depth": "D3",
      "demand_source": "table A | table B | searched",
      "hook_en": "Câu Start nguyên văn tiếng Anh của thân đoạn",
      "summary_en": "1–2 câu tiếng Anh tóm tắt, có tên riêng, có sự kiện cụ thể.",
      "intensity": 8,
      "value_axis": "topic",
      "cq": 8,
      "final_score": 7.2,
      "fit_reason": "1 câu tiếng Anh: vì sao chủ đề này là thứ khán giả JRE đang tìm, và vì sao đoạn này đáp ứng được"
    }
  ]
}
```

**Field chung:** `rank`, `kind`, `start`, `end`, `title`, `summary_vi`.

**Riêng entry `kind: "hook"`:** `parent_rank`, `hook_rank`, `title` = `HOOK 01 — <title đoạn cha>`, `duration_sec` 5–25, `quote_en` = `hook_en` (cùng chuỗi), `summary_en`, `hook_type`, `is_segment_opening`; `core_keyword`, `topics`, `value_axis` chép từ đoạn cha. **Không khai** trên hook: `cq`, `final_score`, `content_rank`, `topic_demand`, `topic_depth`, `keyword_reach`, `keyword_reason`, `satellite_keywords`, `fit_reason`, `hooks`.

**Riêng entry `kind: "highlight"`:**
- `content_rank`: 1 = hay nhất, tăng dần theo thứ tự xuất hiện.
- `hooks`: BẮT BUỘC 1–2 phần tử, khớp tuyệt đối với entry hook phẳng (`start`, `end`, `duration_sec`, `quote_en`, loại hook, `is_segment_opening`); `flat_rank` trỏ về `rank` của entry hook.
- `core_keyword`: chữ thường, đúng như người ta gõ. `keyword_reach`: R3/R2/R1 (R0 không được xuất).
- `topic_demand` (TD 1–10), `topic_depth` (D2/D3, D1 không được xuất), `demand_group`, `demand_source`.
- `cq` 1–10; `final_score` = `TD × CQ / 10`, làm tròn 1 chữ số.
- `value_axis` luôn là `"topic"`. **Không khai `gtf`** (skill này không chấm khách mời).
- `fit_reason`: lý do nhu cầu chủ đề (giữ tên field để JRE Studio hiển thị được).

**Kiểm tra trước khi ghi (bắt buộc, tự chạy):**
1. Chỉ MỘT file `.json`.
2. `rank` liên tục 1..N, không trùng, mảng theo `rank` tăng dần.
3. Mọi entry có `kind`; hook đứng ngay trước highlight cha, không có highlight khác chen giữa.
4. Mọi hook nằm trong biên đoạn cha; `duration_sec` trong 5–25.
5. Không đoạn nào thiếu hook hoặc có >2 hook; không hai đoạn trùng hook.
6. Hook phẳng và `hooks[]` lồng khớp tuyệt đối.
7. `content_rank` tăng dần.
8. `title` của hook bắt đầu bằng `HOOK 01 — ` hoặc `HOOK 02 — `.

### Bước 4: Báo đúng 1 dòng
`✅ Đã lưu cutlist (chủ đề hot, layout flat_hooks, <H> hook + <S> đoạn trong CÙNG 1 file): <đường_dẫn_đầy_đủ>\cutlist_<episode_id>.json → import thẳng vào Video Cutter, HOẶC gom nhiều file cutlist_*.json rồi chạy skill tong-hop-rabbit-hole.`

Không ghi được file → in JSON trong code block, nhắc lưu thành `.json`. Không thêm văn bản nào khác.

---

## VI. FORMAT ĐẦU RA (KHOÁ CỨNG)

Mỗi lần chạy chỉ xuất **1 kết quả**:

[N]. **[Tiêu đề đoạn, giật tít được]**

Start: (hh:mm:ss) "[Trích câu tiếng Anh mở đầu]..."

End: (hh:mm:ss) "...[Trích câu tiếng Anh kết thúc]"

Tóm tắt: [Tóm tắt chi tiết tiếng Việt từ mở đến kết. Nêu dữ kiện/con số/câu chuyện đắt nhất. Nhân vật có TÊN ĐẦY ĐỦ ở lần nhắc đầu.]

Tại sao đoạn này đắt: [2–4 câu: hook, revelation, leo thang, density, rabbit hole liền mạch.]

**🪝 HOOK COLD OPEN** (nằm trong chính đoạn này, xuất thành entry riêng trong cùng file cutlist):
1. `(hh:mm:ss – hh:mm:ss · ~Ns)` "[quote nguyên văn]" — *[loại hook]*
   → [1 câu: vì sao giữ chân người xem trong 10 giây đầu]
2. *(chỉ khi có khoảnh khắc đỉnh thứ hai tách biệt)*

**🔑 Keyword hạt nhân:** `[cụm như người ta gõ]` · **Reach [R3/R2/R1]** · **Depth [D3/D2]**
*Người gõ cụm này muốn biết gì, đoạn này trả lời gì:* [1–2 câu. Nếu R1: ghi cầu nối sang R3.]
*Keyword vệ tinh:* `[kw2]`, `[kw3]` hoặc "không có".

**📈 Nhu cầu chủ đề:** [Nhóm nhu cầu] · `TD x/10 · CQ y/10 · Điểm cuối z` · nguồn TD: [bảng A / bảng B / đã tra: mô tả ngắn kết quả tra]

---

📋 **CUT BLOCK** (timestamp/title thật, hook đứng trước):
```json
[
  {"rank":1,"kind":"hook","parent_rank":2,"hook_rank":1,"start":"HH:MM:SS","end":"HH:MM:SS","duration_sec":12,"title":"HOOK 01 — Tiêu đề thực tế"},
  {"rank":2,"kind":"highlight","content_rank":1,"start":"HH:MM:SS","end":"HH:MM:SS","title":"Tiêu đề thực tế"}
]
```

### QUY TẮC TIMESTAMP, BẮT BUỘC
1. Tìm câu quote trước.
2. Tra timestamp trực tiếp từ transcript (mốc [hh:mm:ss] ngay trên/trước dòng chứa quote).
3. Không ước tính; không bao giờ chọn timestamp trước rồi mới tìm quote.
4. Áp y hệt cho hook, kể cả hook 8 giây.
5. Transcript KHÔNG có timestamp → không suy giờ từ số từ; báo người dùng, dùng số dòng làm mốc tạm, xin bản có timestamp trước khi xuất cutlist.

### QUY TẮC TÊN ĐẦY ĐỦ NHÂN VẬT
Lần đầu xuất hiện → tên đầy đủ, chính tả chuẩn; nhân vật ít nổi tiếng → thêm cụm định danh ngắn. Không áp cho quote tiếng Anh và `title` cutlist.

### QUY TẮC LIÊM CHÍNH
- Tóm tắt chỉ ghi điều người nói thật sự nói trong transcript; không bịa dữ kiện để đoạn nghe "hot" hơn.
- Cáo buộc nghiêm trọng nhắm vào người thật chưa có kết luận chính thức: ghi đúng là **cáo buộc/lời kể** của người nói.
- Kết quả tra cứu nhu cầu chỉ ghi điều tra được; không tra được thì ghi `chưa tra`.

---

## VII. QUY TRÌNH THỰC HIỆN

**Giai đoạn A: Topic Map (1 lần/tập)**
1. Xác định tập (II.1).
2. Quét và phân cụm (II.2).
3. Gán nhóm nhu cầu + TD gốc + Depth cho từng cụm (III.1, III.3).
4. In TOPIC MAP (II.3).

**Giai đoạn B: Chọn khối**
5. Chấm CQ từng cụm (III.2).
6. Rút keyword sơ bộ, chỉnh TD theo Reach (III.1 bước 2).
7. Tra cứu nhu cầu cho 2–3 khối dẫn đầu nếu có công cụ (III.1).
8. Tính ĐIỂM CUỐI `TD × CQ/10`, xếp hạng, chạy 6 câu hỏi (III.6); tie-break theo III.4.
9. Chọn khối đứng đầu chưa dùng; kiểm ngưỡng thời lượng (IV), ngắn quá → thử GỘP.
10. Chốt keyword hạt nhân, tra ma trận Reach × Depth (III.5).
11. Xác định trường hợp cắt (TH1–TH3), chọn Start/End bằng timestamp thật, né quảng cáo.
12. Rút HOOK COLD OPEN (III.7).
13. Kiểm chéo timestamp + quote, kiểm tên đầy đủ.
14. Xuất theo format khoá cứng (VI).
15. Khi được yêu cầu xuất cutlist: dựng `segments[]` phẳng (Vb), chạy 8 mục kiểm tra, ghi **MỘT** file `cutlist_<episode_id>.json`.

---

## VIII. TIÊU CHÍ TỔNG HỢP

Ưu tiên:
- **Chủ đề khán giả JRE đã tò mò sẵn** (TD cao: âm mưu & lịch sử bị giấu, văn minh cổ đại, UFO, tôn giáo bí ẩn, vũ trụ, động vật nguy hiểm, sức khoẻ ngược dòng).
- **Đào sâu thật** (D3), không nhắc lướt.
- **Keyword R3/R2 gõ được vào ô tìm kiếm.**
- **Rabbit hole liền mạch 15–22 phút** nối nhiều chủ đề nhu cầu cao.
- **Câu chuyện có thật**: nhân vật, mốc thời gian, diễn biến, kết cục.
- **Hook cold open sắc**, tự đứng một mình, không spoil trọn.
- Revelation dồn dập, density cao, kết chốt nặng.

Tránh:
- Khối dưới 10 phút; khối không rút được keyword (R0); khối chỉ nhắc lướt chủ đề hot (D1).
- Chính trị/culture war và self-help chung chung, trừ khi vượt ≥1,5 điểm.
- Chọn khối yếu chỉ vì gắn với một cái tên nổi tiếng. Phép đo trên dữ liệu kênh JRE Clips đã **bác** giả thuyết "title có thực thể đích danh thì ăn hơn" (NER, 4 cách đo, đều ns). Thứ tạo view là **cụm người ta đang tìm**, không phải có tên riêng hay không.
- Đoạn quảng cáo / đọc tài trợ.
- Xuất cutlist thành hai file.

> **Không được** biến `keyword_reach` hay độ mạnh hook thành hệ số nhân thêm vào ĐIỂM CUỐI ngoài cách chỉnh TD ở III.1. Entry hook không bao giờ tham gia xếp `content_rank`.

**Cách kiểm chứng bảng B trong 3 tháng tới:** ghi `demand_group` và `topic_demand` cho mọi đoạn xuất ra, tích ~60–80 clip đã lên sóng ≥60 ngày, so median view theo nhóm. Nhóm nào ở bảng B không vượt trung bình thì hạ TD gốc của nhóm đó.
