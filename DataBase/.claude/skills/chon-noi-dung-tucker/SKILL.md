---
name: chon-noi-dung-tucker
description: "Workflow quét transcript The Tucker Carlson Show và chọn khối nội dung đắt giá nhất cho kênh Tucker Carlson Highlights — clone từ JRE V2.7: lập Hồ Sơ Khách Mời bắt buộc trước khi quét (Guest-Topic Fit), xếp hạng theo CQ×GTF, NGƯỠNG THỜI LƯỢNG và PRIOR CHỦ ĐỀ mượn từ dữ liệu thật 1.725 video top kênh JRE Clips (prior tạm thời cho Tucker), BẮT BUỘC khai báo KEYWORD HẠT NHÂN và BẮT BUỘC rút HOOK COLD OPEN — lát cắt 5–25 giây đắt nhất nằm ngay trong đoạn. Từ V2.7 cutlist chỉ xuất MỘT file duy nhất: hook là entry bình thường trong chính mảng segments[], đứng ngay trước đoạn highlight cha, import thẳng vào Video Cutter. Không còn gate loại thẳng theo thẩm quyền khách mời: trọng tâm là nội dung thu hút người xem, GTF chỉ là hệ số. Kích hoạt khi người dùng gửi transcript Tucker Carlson kèm \"chọn nội dung tucker\", \"chạy wf chọn nội dung tucker\", \"quét transcript tucker carlson\", \"tìm đoạn tiếp theo\", \"xuất cutlist tucker\", \"tìm hook mở đầu\", hoặc muốn cắt clip The Tucker Carlson Show có tính đến khách mời."
---

# Workflow: Chọn Nội Dung The Tucker Carlson Show — V2.7 clone từ JRE (Guest-Aware + Data-Calibrated + Keyword-Anchored + Hook-First + One-File Cutlist)

> **Có gì mới ở V2.7:**
> 7. **CUTLIST CHỈ CÒN MỘT FILE — hook xuất phẳng y như đoạn highlight** (Mục Vb). Trước đây hook chỉ nằm lồng trong mảng `hooks[]` của từng đoạn, nên phải xuất thêm một file thứ hai mới import hook vào tool cắt được. Từ V2.7: **mỗi hook là MỘT entry bình thường ngay trong mảng `segments[]`** — có `start` / `end` / `title` giống hệt đoạn highlight, đặt **ngay TRƯỚC** đoạn highlight cha của nó, đánh số `rank` liên tục cùng một dãy. Import **một file `cutlist_<episode_id>.json` duy nhất** là tool cắt được cả hook lẫn thân đoạn. Mảng `hooks[]` lồng trong đoạn cha **vẫn giữ nguyên** để `viet-tittle-v2` và `tong-hop-rabbit-hole` đọc `hooks[0].quote_en` như cũ — không skill nào khác phải sửa.
>
> **Có gì mới ở V2.6:**
> 6. **HOOK COLD OPEN — bắt buộc** (Mục III.9). Mỗi đoạn được chọn phải kèm **1–2 lát cắt cực ngắn (5–25 giây) nằm NGAY TRONG chính đoạn đó**, là câu đắt nhất/cô đọng nhất — để người dựng cắt riêng và dán lên đầu video làm mở màn. Hook có timestamp riêng, quote nguyên văn, phân loại, và được xuất trong cutlist *(từ V2.7: xuất thành entry phẳng trong chính `segments[]` **và** giữ bản lồng `hooks[]` — xem Mục Vb)*. Lý do: khán giả quyết định ở lằn ranh 5–15 giây đầu — một khối 15–22 phút mở bằng câu dẫn nhập bình thường sẽ mất người trước khi nội dung hay kịp xuất hiện.
>
> **Có gì mới ở V2.5:**
> 5. **BỎ LUẬT 1 (gate loại thẳng theo GTF).** Trước đây nếu `GTF ≤ 2` thì khối bị loại khỏi bảng xếp hạng bất kể CQ cao đến đâu. Gate cứng đó đã bị bỏ theo yêu cầu chủ kênh: **mục tiêu tối thượng là nội dung thu hút người xem, không phải sự thuần khiết về thẩm quyền khách mời.** GTF giờ chỉ còn là hệ số nhân trong ĐIỂM CUỐI (III.3) — một khối CQ cực cao vẫn được xếp hạng và có thể được chọn dù khách không phải chuyên gia của chủ đề. "LUẬT 2" cũ được đổi tên thành **LUẬT VÀNG PERSONA** vì giờ là quy tắc đặc biệt duy nhất còn lại.
>
> **Có gì mới ở V2.4:**
> 4. **KEYWORD HẠT NHÂN — bắt buộc** (Mục III.8). Mỗi đoạn được chọn phải khai báo: *đoạn này sẽ thành công nhờ cụm từ tìm kiếm nào*. Keyword = **cụm khán giả gõ vào ô tìm kiếm**, KHÔNG bắt buộc là nhân vật/sự vật/sự kiện — `workout smarter` là keyword hợp lệ y như `hitler`. Chấm theo 2 chiều: **Reach** (bao nhiêu người gõ) × **KGC** (người gõ cụm đó có tin người đang nói không).
>
> **Có gì mới ở V2.3** — hiệu chỉnh bằng dữ liệu thật quét từ kênh JRE Clips (1.725 video, toàn bộ video >880K view, tháng 8/2026):
> 1. **Ngưỡng thời lượng viết lại** (Mục IV) — vùng vàng thật là **15–22 phút**, không phải 8–20. Ngưỡng PERSONA 3–8 phút của V2.2 **đã bị dữ liệu bác bỏ**.
> 2. **Thêm PRIOR CHỦ ĐỀ** (Mục III.6) — dùng làm tie-break khi hai khối chênh nhau <1 điểm.
> 3. **Thêm Phụ lục IX** — ghi lại các giả thuyết đã kiểm định và **bị bác**, để không ai đi lại đường cụt.

> **⚠️ Lưu ý dữ liệu (bản Tucker):** mọi con số hiệu chỉnh trong skill này — ngưỡng thời lượng (Mục IV), PRIOR CHỦ ĐỀ (III.6), Idx, tín hiệu Story (III.7), Phụ lục IX — được đo trên **kênh JRE Clips**, KHÔNG phải trên dữ liệu Tucker. Giữ nguyên luật và ngưỡng như **prior làm việc** cho đến khi có dữ liệu thật của kênh Tucker Carlson Highlights; không tự bịa thống kê Tucker.

## I. VAI TRÒ (ROLE)

Bạn là trợ lý AI chuyên nghiệp, đồng thời là fan cứng của The Tucker Carlson Show (thích sự thực tế, chiều sâu, bộc trực). Clip xuất ra cho kênh **Tucker Carlson Highlights**, khán giả là khán giả YouTube Mỹ. Show là phỏng vấn dài về chính trị, chính sách đối ngoại/chiến tranh, cơ quan tình báo & những vụ che giấu, truyền thông, Epstein, UFO/UAP, đức tin/tôn giáo, kinh tế, kiểm duyệt; khách mời là chính trị gia, whistleblower, nhà báo, cựu tình báo/quân đội, tác giả, nhân vật tôn giáo. Nhiệm vụ gồm **hai lớp**:

1. **Lớp khách mời** — hiểu khách mời này là ai, họ có thẩm quyền nói về cái gì, và khán giả kéo vào xem tập này là để nghe họ nói về cái gì.
2. **Lớp nội dung** — quét transcript, tìm khối nội dung đắt giá nhất *đối với chính khách mời đó*, ưu tiên hội thoại liền mạch dài, viết tóm tắt tối ưu Retention kèm lý do chọn, và rút **hook cold open** cho mỗi khối.

> **Nguyên tắc cốt lõi của V2:** Giá trị của một đoạn clip không nằm ở chủ đề, mà nằm ở **tích số giữa chủ đề và người đang nói về nó**. Cùng một chủ đề UFO: Bob Lazar kể chuyện S-4 là vàng ròng; một YouTuber giải trí suy đoán về UFO là rác. Ngược lại, một đoạn *không có thông tin gì* — chỉ là một diễn viên hài cà khịa Tucker Carlson — lại có thể là clip đắt nhất tập.

---

## II. BƯỚC 0 — HỒ SƠ KHÁCH MỜI (GUEST CARD) — BẮT BUỘC, CHẠY TRƯỚC KHI QUÉT

**Tuyệt đối không được quét transcript và chọn đoạn khi chưa lập xong Guest Card.**

### II.1 — Xác định khách mời

Theo thứ tự ưu tiên:
1. Tên file transcript / mã tập người dùng cung cấp.
2. Phần mở đầu transcript (Tucker Carlson thường giới thiệu khách ngay đầu tập).
3. Suy ra từ nội dung (khách tự kể về sự nghiệp, sách, chức vụ, vụ việc từng tham gia...).
4. Nếu vẫn không chắc → **hỏi người dùng đúng 1 lần**, rồi tiếp tục.

Nếu tập có **nhiều khách mời** → lập Guest Card riêng cho từng người, và thêm một mục "Hoá học giữa các khách" (xem II.5).

### II.2 — Research: 3 nguồn, theo thứ tự

| Nguồn | Khi nào dùng | Ghi chú |
|---|---|---|
| **1. Tra cứu web** | Luôn ưu tiên nếu môi trường có công cụ search | Tra: tên khách + lĩnh vực, tên khách + "Tucker Carlson", tên khách + tranh cãi/sự kiện nổi bật |
| **2. Kiến thức nội tại** | Khi không có công cụ search, hoặc để bổ sung | Ghi rõ đây là kiến thức có sẵn, có thể đã cũ |
| **3. Bằng chứng từ chính transcript** | Luôn dùng để kiểm chứng chéo | Khách tự khai lý lịch, Tucker giới thiệu, những đoạn khách nói với thẩm quyền cao nhất |

**QUY TẮC LIÊM CHÍNH (bắt buộc):**
- Chỉ ghi vào Guest Card những thông tin **xác minh được** hoặc **chính khách nói ra trong transcript**. Không bịa chức danh, không bịa bằng cấp, không bịa thành tích.
- Nếu một chi tiết chỉ là suy đoán → đánh dấu rõ `(chưa xác minh)`.
- Với các cáo buộc hình sự/đạo đức nghiêm trọng nhắm vào người thật còn sống mà chưa có kết luận chính thức: ghi đúng bản chất là **cáo buộc/lời kể của khách**, không viết như sự thật đã được xác lập.
- Mức độ tin cậy tổng thể của Guest Card phải ghi rõ: `Cao` / `Trung bình` / `Thấp`.

### II.3 — Bảng ARCHETYPE khách mời (dùng để định vị nhanh)

| # | Archetype | Trục giá trị | Khán giả CỰC THÍCH nghe họ nói về | Khán giả KHÔNG quan tâm khi họ nói về |
|---|---|---|---|---|
| 1 | **Người trong cuộc / Whistleblower** | Authority | Cái họ tận mắt thấy, chi tiết kỹ thuật, cái họ bị cấm nói, hậu quả họ chịu | Bình luận chính trị chung chung, chuyện đời thường |
| 2 | **Nhà nghiên cứu rìa / tác giả điều tra** | Authority | Bằng chứng vật lý, niên đại, tài liệu giải mật, đường dây quyền lực | Chuyện đời tư, tán gẫu thể thao |
| 3 | **Nhà khoa học / chuyên gia chính thống** | Authority | Điều khoa học chưa giải thích được, phản biện sắc, cơ chế ẩn sau hiện tượng quen thuộc | Suy đoán ngoài chuyên môn, showbiz |
| 4 | **Chính trị gia / quan chức (đương nhiệm hoặc cựu)** | Authority + Persona | Hậu trường quyết định, ai thật sự ra lệnh, đấu đá nội bộ, cái họ bị chặn không cho làm, tiền bạc thật | Khoa học, y tế, chuyện giải trí |
| 5 | **Diễn viên hài / bình luận viên chính trị kiểu hài** | Persona (chủ đạo) | Cà khịa Tucker, cà khịa giới truyền thông/chính trị, chuyện đời tệ hại có thật, riff leo thang | Phân tích nghiêm túc tình báo/khoa học/địa chính trị — trừ khi để cười |
| 6 | **Nhà báo / người làm truyền thông** | Authority + Persona | Mặt tối ngành truyền thông, hậu trường tòa soạn, câu chuyện bị giết bài, bị sa thải/kiểm duyệt | Giảng khoa học, y tế, vật lý |
| 7 | **Doanh nhân / creator / YouTuber** | Authority (hẹp) | Cơ chế vận hành đế chế, con số thật, thất bại, mặt tối thành công | UFO, người ngoài hành tinh, lịch sử cổ đại — bẫy kinh điển |
| 8 | **Bác sĩ / chuyên gia sức khoẻ** | Authority | Sự thật ngược dòng, cảnh báo cụ thể, ca bệnh thật | Chính trị, giải trí |
| 9 | **Người sống sót / nhân chứng đời thực** | Authority (trải nghiệm) | Chi tiết cảm giác, khoảnh khắc sinh tử, thế giới ngầm họ từng sống | Ý kiến chuyên môn ngoài lĩnh vực họ sống trong đó |
| 10 | **Nhân vật tôn giáo / người khám phá đức tin** | Authority (trải nghiệm) + Persona | Trải nghiệm đức tin cụ thể, cái họ "gặp", thiện–ác, tranh luận với Tucker | Chính sách kinh tế chi tiết, kỹ thuật quân sự |

**Khách lai:** ghi cả hai archetype, hai vùng vàng riêng biệt, không ép về một archetype.

### II.4 — Hai trục giá trị

| Trục | Bản chất | Đoạn đắt trông như thế nào | Dấu hiệu nhận biết |
|---|---|---|---|
| **AUTHORITY** | Giá trị đến từ việc chỉ người này mới kể được | Tiết lộ, dữ kiện, chuyện first-hand, chuyên môn sâu | Khách nói dài, Tucker nghe nhiều hơn nói, tên riêng/con số/mốc thời gian |
| **PERSONA** | Giá trị đến từ con người họ và tương tác với Tucker | Cà khịa, riff, cãi vui, khoảnh khắc thật | Câu ngắn qua lại nhanh, cười liên tục, Tucker bị đẩy vào thế bị động |

Mỗi khách gán **trục chủ đạo** và **trục phụ** (nếu có).

### II.5 — Format GUEST CARD (in ra 1 lần, ngay đầu phiên làm việc)

```
🎙️ HỒ SƠ KHÁCH MỜI — [Tên đầy đủ] | [Mã tập]

• Định danh: [1 câu]
• Archetype: [#số - tên] (+ [#số - tên] nếu lai)
• Trục giá trị: Chủ đạo = [AUTHORITY/PERSONA] | Phụ = [.../không có]
• Chuyên môn cấp 1 (độc quyền): [1-3 mục]
• Chuyên môn cấp 2: [1-3 mục]
• Vùng cấp 3 (hạ điểm mạnh): [1-3 mục]
• Phong cách nói: [...]
• Hoá học với Tucker Carlson: [...]
• 🎯 KHÁN GIẢ MUỐN NGHE NGƯỜI NÀY NÓI VỀ: [3-5 chủ đề, giảm dần]
• 🚫 KHÁN GIẢ KHÔNG QUAN TÂM KHI HỌ NÓI VỀ: [2-4 chủ đề]
• Độ tin cậy hồ sơ: [Cao/Trung bình/Thấp] — [nguồn]
```

Guest Card lập **một lần duy nhất cho mỗi tập**. Ở các lượt "tìm đoạn tiếp theo", **tái sử dụng** Guest Card đã có — không research lại, không in lại.

---

## III. GUEST-TOPIC FIT (GTF) — CƠ CHẾ XẾP HẠNG

Sau khi có Guest Card, mỗi khối nội dung ứng viên được chấm theo trình tự: **CQ → GTF → ĐIỂM CUỐI**.

### III.1 — Điểm nội dung (CQ: Content Quality, 1–10)

1. **Tối / drama / rùng mình** — hậu quả thực tế, cảm xúc mạnh.
2. **Revelation dồn dập** — sự thật bất ngờ nối tiếp.
3. **Hook tương phản mạnh** — câu mở đầu bẻ lái đột ngột.
4. **Leo thang (escalation)** — mức độ điên/sốc/insight tăng dần.
5. **Density cao** — nhiều dữ kiện/con số cụ thể, ít lan man.

### III.2 — Điểm khớp khách mời (GTF: Guest-Topic Fit, 1–10)

| GTF | Nghĩa | Ví dụ |
|---|---|---|
| **9–10** | Chủ đề nằm ngay lõi cấp 1 của khách | Bob Lazar mô tả S-4; một cựu sĩ quan CIA kể chiến dịch chính mình tham gia |
| **7–8** | Chủ đề cấp 2, hoặc persona bùng nổ đúng chất | Nhà báo điều tra đọc lại tài liệu giải mật; comedian cà khịa Tucker |
| **5–6** | Chủ đề kề cận, không độc quyền | Nhà khoa học kể chuyện sinh viên |
| **3–4** | Chủ đề chung chung, ai cũng nói được | Bàn thời tiết, mạng xã hội chung chung |
| **1–2** | Khách không có thẩm quyền, không buồn cười — không loại thẳng, nhưng ĐIỂM CUỐI gần như luôn thấp hơn hẳn khối khác | YouTuber giải trí đoán mò về UFO |

> **Lưu ý:** GTF cao phải đến từ khách dùng chuyên môn/nghiên cứu để nói SÂU về chủ đề — không chỉ vì "chuyện riêng chỉ họ kể được". Tiểu sử cá nhân không mặc định GTF cao trừ archetype 1/9 (nơi trải nghiệm cá nhân LÀ chủ đề). Test nhanh: đổi khách khác cùng chuyên môn, đoạn còn giá trị không? Còn → GTF cao đúng. Mất → hạ GTF.

### III.3 — Công thức xếp hạng

```
ĐIỂM CUỐI = CQ × (GTF / 10)
```

> **✅ ĐÃ BỎ LUẬT 1 — BẪY "CHỦ ĐỀ HOT SAI NGƯỜI" (từ V2.5):** Bản cũ có một gate loại cứng — nếu `GTF ≤ 2` thì loại khối khỏi bảng xếp hạng bất kể CQ cao đến đâu. Gate đó đã bị bỏ. **Trọng tâm giờ là tối ưu nội dung thu hút người xem** — GTF không còn quyền phủ quyết, chỉ còn là hệ số nhân trong ĐIỂM CUỐI (III.3). Một khối CQ=10 nhưng GTF=2 vẫn được xếp hạng (điểm 2.0) và hoàn toàn có thể là lựa chọn tốt nhất còn lại của tập, đặc biệt nếu đó là một câu chuyện/hook cực mạnh do chính Tucker kể. Vẫn nên chấm GTF đúng mức khi khách không có thẩm quyền thật (III.2) — điều đó giữ cho ĐIỂM CUỐI phản ánh đúng thực tế — nhưng đừng tự loại một khối chỉ vì lý do đó nữa.

**⭐ LUẬT VÀNG PERSONA:** Với khách có trục PERSONA, một khối có thể CQ thấp về thông tin nhưng vẫn điểm rất cao nếu thoả ≥3 dấu hiệu: Tucker bị trêu/bị bẻ/bị bắt bí (chuyện Fox News, quá khứ của chính anh); Tucker cười sặc (tràng cười đặc trưng); riff leo thang; khách bộc lộ con người thật; callback nội bộ tập; câu chốt tự thành title. Khi đó chấm CQ lại theo thang giải trí, không theo mật độ thông tin.

### III.6 — PRIOR CHỦ ĐỀ (chỉ dùng làm TIE-BREAK)

Đo trên 1.549 video ≥4 năm tuổi của kênh JRE Clips. **Không nhân vào công thức** — chỉ dùng khi hai khối chênh nhau **<1 điểm cuối**, thì chọn khối thuộc nhóm prior cao hơn.

| Nhóm chủ đề | % sản lượng kênh | Idx | Độ chắc |
|---|---|---|---|
| Âm mưu & lịch sử bị giấu (Paperclip, MK Ultra, JFK, Epstein, Area 51) | 4,7% | **1.35** | ✅ CI 1.05–1.65 |
| Văn minh cổ đại / khảo cổ | 1,2% | 1.68 | ⚠️ n=18, CI rất rộng — **giả thuyết đáng thử, chưa chứng minh** |
| Thiên nhiên & động vật nguy hiểm | 4,5% | 1.25 | ⚠️ chưa chắc |
| Khoa học & vũ trụ giải thích dễ hiểu | 5,5% | 1.20 | ⚠️ chưa chắc |
| Hollywood & drama người nổi tiếng | 6,1% | 1.10 | ⚪ |
| Quân đội / tình báo / tội phạm | 8,8% | 1.00 | ⚪ |
| MMA / võ thuật / thể thao | **17,2%** | 0.90 | ⚠️ khối sản xuất lớn nhất mà không có lợi thế |
| Chính trị / culture war | **12,2%** | **0.85** | ✅ CI 0.75–0.95 — kém rõ rệt |
| Tâm linh / triết học / self-help | 3,3% | **0.80** | ✅ CI 0.65–0.95 — kém nhất |

**Cách dùng:**
- Hai khối chênh ≤1 điểm → chọn khối có prior cao hơn.
- Khối thuộc **chính trị/culture war** hoặc **tâm linh/self-help**: cần chênh **≥1,5 điểm** so với đối thủ mới được chọn.
- PRIOR vẫn chỉ là tie-break — không tự nó đẩy một khối GTF thấp lên đầu bảng nếu CQ không thực sự áp đảo khối đối thủ. Chủ đề âm mưu ăn khách *mạnh nhất* khi khách có bằng chứng/nghiên cứu thật — Annie Jacobsen, Tom O'Neill; nhưng từ V2.5, một khối âm mưu do chính Tucker kể với CQ cao vẫn có thể được chọn dù khách không góp thẩm quyền gì, miễn ĐIỂM CUỐI cạnh tranh được (Alex Jones Idx 0.85 trên 18 clip cho thấy chủ đề này tự nó cũng không quá vượt trội, nên đừng chọn chỉ vì "nghe hot").

### III.7 — TÍN HIỆU "CÂU CHUYỆN" (Story)

Clip mà title chứa chữ **Story/Stories** đạt Idx **1.50** (CI 1.10–1.90) — một trong ba kết luận vững nhất của toàn bộ dữ liệu, và mới chỉ xuất hiện ở 3,3% sản lượng.

Khi chấm CQ, **cộng ưu tiên cho khối là MỘT CÂU CHUYỆN có thật** — có nhân vật, có mốc thời gian, có diễn biến, có kết cục — thay vì một cuộc trao đổi quan điểm. Nếu khối đủ điều kiện, viết `summary_en` và `title` sao cho người đọc thấy ngay đây là một câu chuyện sắp được kể.

### III.8 — KEYWORD HẠT NHÂN (Core Keyword) — **BẮT BUỘC**

#### Định nghĩa — đọc kỹ, đây là chỗ dễ hiểu sai nhất

> **Keyword hạt nhân = cụm từ mà khán giả GÕ VÀO Ô TÌM KIẾM để tìm ra chính video này.**

**Không giới hạn loại từ.** Không bắt buộc phải là nhân vật, sự vật hay sự kiện. Người ta gõ gì thì đó chính xác là thứ họ quan tâm — thế là đủ:

| Clip | View | Keyword hạt nhân | Loại |
|---|---|---|---|
| How Serious is the Coronavirus? … Michael Osterholm Explains | 22M | **coronavirus** | hiện tượng |
| Joe Rogan SHOCKED By Hitler Conspiracy Theory | 22M | **hitler** | nhân vật |
| The Amazon is a Colossal Mystery w/Graham Hancock | 16M | **rừng Amazon** | địa danh |
| **Joe Rogan - How To Workout Smarter** | **15M** | **workout smarter** | **hành vi / nhu cầu** |
| Joe Rogan - Why Obese People Can't Lose Weight | 11M | **why you can't lose weight** | câu hỏi |
| Edward Snowden: How Your Cell Phone Spies on You | 19M | **phone spying** | nỗi lo |
| Joe Rogan \| The Harsh Truths of Operation Paperclip | 14M | **operation paperclip** | sự kiện |

`workout smarter` là keyword đúng nghĩa — có người gõ nó. Việc nó không phải danh từ chỉ một vật thể **không liên quan gì**.

**Test duy nhất:** *"Có ai gõ cụm này vào ô tìm kiếm không?"* Nếu có → là keyword hợp lệ. Hết.

**Chỉ có một thứ bị loại khỏi vai trò keyword hạt nhân:** tên khách mời — trừ khi chính khách là thứ người ta đang săn tìm (Bob Lazar, Edward Snowden, Vladimir Putin). Người xem gõ *coronavirus*, không gõ *Osterholm*.

#### Hai điều kiện phải thoả CÙNG LÚC

Một keyword chỉ tạo ra view khi **cả hai** cùng đúng:

**① REACH — có bao nhiêu người gõ cụm này?**

| Mức | Nghĩa | Test nhanh | Ví dụ |
|---|---|---|---|
| **R3** | Rất nhiều người tìm, không cần giải thích gì | Không phải giải thích một chữ nào | hitler · coronavirus · epstein · area 51 · cia · ufo · world war 3 · how to lose weight |
| **R2** | Có lượng tìm ổn định, cần 1 câu bối cảnh | Giải thích trong ≤1 câu mà vẫn kích tò mò | operation paperclip · bob lazar · mk ultra · nord stream · usaid · gobekli tepe |
| **R1** | Ít người tìm, hoặc phải giải thích thuật ngữ trước | Cần ≥2 câu, nghe như bài giảng | nguyên lý bất định heisenberg · laplace's demon · một điều khoản dự luật ít người biết |
| **R0** | Không ai gõ được | Không thành cụm tìm kiếm | "some infinities are bigger than others" |

**② KGC — Keyword–Guest Credibility: người gõ cụm đó, khi thấy người đang nói, có tin không?**

Đây là chỗ quyết định, và **uy tín ở đây là uy tín CẢM NHẬN trong mắt người đang search — không phải bằng cấp chính thức.**

Ví dụ mẫu (từ dữ liệu JRE Clips): người gõ `workout smarter` gặp Joe Rogan. Joe không có bằng khoa học thể thao — nhưng anh ta là bình luận viên UFC, tập BJJ và kickboxing hàng chục năm, thân hình cơ bắp thấy ngay trên thumbnail. Với người đang tìm cách tập cho đúng, **đó là uy tín đủ và thấy được ngay lập tức**. Nên clip đạt 15M dù keyword không phải một "sự vật" nào cả.

| KGC | Nghĩa |
|---|---|
| **Cao** | Người search nhìn phát là tin. Uy tín hiển thị được ngay trên title/thumbnail — chức danh, thành tích, hoặc đơn giản là ngoại hình/hành vi chứng minh (Joe + cơ bắp cho keyword tập luyện) |
| **Trung bình** | Tin được nhưng cần title nói rõ vì sao (`Infectious Disease Expert…`, `Former CIA Agent…`) |
| **Thấp** | Người search không có lý do gì để tin người này về cụm từ đó → khối này khó giữ chân người xem dù kéo được click, cân nhắc kỹ trước khi chọn làm keyword hạt nhân |

#### Ma trận quyết định

| | **KGC cao** | **KGC thấp** |
|---|---|---|
| **Reach cao (R3/R2)** | ✅ **VÀNG — chọn** | ❌ Clickbait: kéo được click nhưng người xem bỏ giữa chừng ngay phút đầu — phản tác dụng với chính mục tiêu thu hút người xem *bền vững* (hại watch-time, hại đề xuất về sau), nên vẫn loại dù không còn gắn với gate GTF nào |
| **Reach thấp (R1)** | ⚠️ Chính xác nhưng ít người tìm. Chỉ chọn khi vượt ≥1,5 điểm, VÀ phải tìm được **cầu nối sang một keyword R3** (nguyên lý bất định → *"vì sao vũ trụ không cho phép biết mọi thứ"*) | ❌ Loại |
| **R0** | ❌ Loại, trừ khối PERSONA thuần theo Luật Vàng Persona (khi đó keyword là chính khoảnh khắc: `tucker bị bắt bí về X`) | ❌ Loại |

> **Lưu ý về ca Neil deGrasse Tyson #919** (cùng khách, cùng tập, cùng ngày, chênh 54 lần view): cả 5 clip đều KGC cao — NdGT nói về vật lý thì ai cũng tin. Cái tách chúng thuần tuý là **Reach**: `aliens` và `Monster's Inc` (R3) đạt 5,9M và 5,8M; `nguyên lý bất định Heisenberg` (R1) chỉ 758K; `flat-earthers/chiêm tinh` ở thế bác bỏ (R1–R2) chỉ 110K. KGC cao không cứu được Reach thấp.

#### Quy trình rút keyword — chạy NGAY SAU khi chốt khối, TRƯỚC khi xuất

1. **Rút keyword:** *"Nếu chỉ được gõ MỘT cụm vào ô tìm kiếm YouTube để tìm ra đúng đoạn này, đó là cụm nào?"* Viết đúng như người ta sẽ gõ — chữ thường, không hoa mỹ.
2. **Kiểm keyword có thật trong khối** — được đào sâu, không phải nhắc lướt một câu.
3. **Chấm Reach** (R3/R2/R1/R0).
4. **Chấm KGC** — tự hỏi: *người gõ cụm này, nhìn thấy khách mời/Tucker nói về nó, có lý do gì để tin không? Lý do đó có hiển thị được lên title hoặc thumbnail không?*
5. **Tra ma trận.** Nếu rơi vào ô ❌ → xử lý theo thứ tự: (a) thu hẹp biên cắt vào tiểu đoạn có keyword mạnh hơn, vẫn giữ ngưỡng thời lượng Mục IV; (b) gộp với khối liền kề cùng keyword; (c) chuyển sang khối tiếp theo trong bảng xếp hạng.
6. **Kiểm vị trí:** nếu keyword không xuất hiện ở 1/3 đầu khối → cân nhắc dời Start tới chỗ nó xuất hiện. Hook mở đầu nên chạm keyword.

#### Keyword vệ tinh (rabbit hole)

Khối 15–22 phút thường đi qua nhiều chủ đề. Khai báo:
- **1 keyword hạt nhân** — cái có Reach cao nhất *và* KGC đủ. Đây là cái sẽ lên title và thumbnail.
- **Tối đa 2 keyword vệ tinh** — các chủ đề còn lại, để `viet-tittle-v2` dựng Connective Thread và `tong-hop-rabbit-hole` gom theo trục.

### III.4 — Bảng cân nhắc bắt buộc trước khi chốt

1. Ai cũng nói được đoạn này không? → Nếu có, hạ GTF.
2. Bỏ tên khách mời khỏi title, clip còn ai xem không? → Nếu không, GTF cao là đúng.
3. Đoạn này được chọn vì chủ đề hợp kênh hay vì chính người này nói nó? → Nếu là vế đầu, hạ GTF xuống 1–2 (không loại thẳng) — để CQ tự quyết định khối này có đủ hấp dẫn để đứng một mình không.
4. Đoạn này đang KỂ VỀ khách mời hay DÙNG khách mời để đào sâu chủ đề? → Nếu là vế đầu và khách không có fame độc lập → hạ GTF xuống 5–6.
5. **Rút được keyword hạt nhân chưa — cụm mà khán giả sẽ GÕ để tìm ra đoạn này?** → Nếu chưa, quay lại III.8.
6. **Tra ma trận Reach × KGC (III.8).** Rơi vào ô ❌ → xử lý trước khi chốt. Đặc biệt: Reach cao + KGC thấp = clickbait — vẫn loại vì hại retention/watch-time, không phải vì gate thẩm quyền khách mời.
7. **Rút được HOOK COLD OPEN chưa (III.9)?** → Nếu quét cả khối mà không tìm nổi một lát 5–25 giây tự đứng một mình và giật mình được, đó là dấu hiệu khối này lan man: cân nhắc thu hẹp biên cắt hoặc đổi khối.

### III.5 — Chọn biên cắt khi khối tốt bị xen lẫn tiểu sử cá nhân

- Đoạn tiểu sử là bối cảnh cần thiết → giữ nhưng nén tối đa (≤15–20% thời lượng khối).
- Đoạn tiểu sử có thể bỏ mà không mất gì → cắt hẳn, dời Start tới điểm nội dung thật bắt đầu.
- Ưu tiên cả hook mở đầu lẫn câu chốt đều là nội dung về chủ đề — trừ archetype 1/9.
- Nếu tiểu sử và chuyên môn tách biệt rõ ràng → cân nhắc tách thành hai khối riêng.

### III.9 — HOOK COLD OPEN — **BẮT BUỘC**

#### Định nghĩa

> **Hook cold open = một lát cắt CỰC NGẮN (5–25 giây) lấy TỪ BÊN TRONG chính đoạn highlight đó, để người dựng cắt riêng và dán lên ĐẦU video, phát trước khi vào nội dung chính.**

Đây **không phải** câu Start của đoạn (dù đôi khi trùng). Đây là **câu đắt nhất, cô đọng nhất của cả khối** — thường nằm ở giữa hoặc cuối đoạn, nơi cao trào thật sự xảy ra — được bê ngược lên đầu để giữ người xem.

**Vì sao bắt buộc:** khán giả quyết định ở lằn ranh 5–15 giây đầu. Một khối 15–22 phút mở bằng câu dẫn nhập bình thường ("So I want to talk about…", "That's interesting…") sẽ mất người trước khi phần hay kịp xuất hiện. Nội dung tốt mà mở màn nhạt = mất view, không phải mất chất lượng.

#### 5 LUẬT CỨNG

1. **Hook PHẢI nằm trong khoảng `[start, end]` của chính đoạn đó.** Không lấy từ đoạn khác, không lấy ngoài biên. Lý do thực tế: người dựng chỉ mở đúng một khối video đã cắt — hook nằm ngoài là không cắt được.
2. **Mỗi hook là MỘT lát liền mạch.** Không ghép hai câu rời nhau ở hai chỗ khác nhau thành một hook. Muốn hai ý → khai hai hook riêng.
3. **Thời lượng 5–25 giây**, lý tưởng **8–15 giây**. Dưới 5 giây khán giả chưa kịp hiểu; trên 25 giây không còn là hook mà là đoạn mở đầu.
4. **Timestamp thật, tra trực tiếp từ transcript** — áp đúng "QUY TẮC TIMESTAMP" ở Mục VI. Không ước tính, không nội suy.
5. **Quote nguyên văn.** Không viết lại, không rút gọn, không sửa ngữ pháp cho đẹp.

#### 4 tiêu chí chọn hook

| # | Tiêu chí | Test |
|---|---|---|
| 1 | **Tự đứng một mình được** | Nghe xong mà không cần biết trước bối cảnh nào. Đây là tiêu chí LOẠI mạnh nhất |
| 2 | **Có cú sốc hoặc khoảng trống tò mò** | Phải có thứ khiến ngón tay dừng lại: con số gây choáng, tuyên bố ngược đời, tiết lộ, hoặc câu chuyện dở dang |
| 3 | **Không spoil trọn** | Hook nêu câu hỏi hoặc nửa đầu sự việc, KHÔNG đưa luôn đáp án. Hook kể hết = người xem hết lý do xem tiếp |
| 4 | **Chạm keyword hạt nhân (ưu tiên)** | Hook chứa hoặc gợi thẳng tới keyword hạt nhân sẽ xác nhận ngay với người vừa click từ tìm kiếm rằng "đúng video rồi". Không bắt buộc, nhưng thắng khi hai ứng viên ngang nhau |

> **Phân biệt mơ hồ TỐT và mơ hồ XẤU** (chỗ dễ sai nhất): hook chứa đại từ chưa rõ ("he", "they", "that thing") **không mặc định bị loại**. Test: nghe xong, khán giả có hình thành được **MỘT câu hỏi cụ thể** muốn biết đáp án không?
> - *"And they did an autopsy and the guy had a tumor in his brain."* → "Ai? Vì sao mổ tử thi?" → **mơ hồ tạo tò mò, GIỮ.**
> - *"And then he said it wasn't ready, so I did it again."* → không hình thành được câu hỏi nào, chỉ thấy rối → **LOẠI.**

#### 5 loại hook (khai `hook_type` ở entry phẳng và `type` ở bản lồng)

| Loại | giá trị | Bản chất | Ví dụ mẫu |
|---|---|---|---|
| **Tuyên bố sốc** | `shock_claim` | Một câu ngắn đi ngược hiểu biết thông thường | "Knowledge alone does not protect us." |
| **Bom dữ kiện** | `fact_bomb` | Con số hoặc sự thật gây choáng, tự nó là tin | "Medical error is responsible for 251,000 deaths a year." |
| **Câu chuyện dở dang** | `story_teaser` | Mở đúng cảnh gay cấn rồi cắt trước khi có kết cục | "He wrote in his diary, I don't know why I want to do this." |
| **Câu hỏi tò mò** | `curiosity_question` | Câu hỏi mà chính khán giả cũng đang thắc mắc | "What is obsessive compulsive disorder versus being passionate about something?" |
| **Xung đột trực diện** | `conflict` | Ai đó bị bẻ, bị tấn công, hoặc đang cãi thẳng | "The neurosurgery community dogpiled me." |

#### Số lượng hook

- **Bắt buộc ≥1 hook cho mỗi đoạn được chọn.**
- **Tối đa 2 hook**, và chỉ khi đoạn có ĐÚNG hai khoảnh khắc đỉnh **thật sự tách biệt** — khác chủ đề con, khác loại hook. Hai câu cùng nói một ý = một hook, không phải hai.
- Khai 2 hook thì `hook_rank: 1` là cái mạnh nhất — cái sẽ dựng lên đầu video. Hook 2 dùng cho biến thể thumbnail, bản Shorts, hoặc dựng nối ngay sau hook 1.
- **Không bao giờ khai 3+.** Nhiều hook = không có hook.

#### Khi hook trùng đầu đoạn

Nếu câu mạnh nhất chính là dòng Start của đoạn (trường hợp TH3 ở Mục IV), vẫn khai hook bình thường nhưng đặt `is_segment_opening: true` — báo cho người dựng biết **không cần cắt riêng và dán lại**, tránh phát lặp hai lần liên tiếp ngay đầu video.

#### Hook được xuất ở đâu — **CHỈ MỘT FILE** (từ V2.7)

Toàn bộ tập chỉ có **MỘT file `cutlist_<episode_id>.json`**. Tuyệt đối không tách hook ra file thứ hai. Trong chính file đó, mỗi hook xuất hiện ở **hai chỗ, phục vụ hai mục đích khác nhau**:

1. **Entry phẳng trong `segments[]`** (`kind: "hook"`) — một đoạn cắt **bình thường y như highlight**: có `rank`, `start`, `end`, `title`. Đặt **ngay TRƯỚC** đoạn highlight cha. **Đây là thứ Video Cutter đọc và cắt ra thành file video.**
2. **Mảng `hooks[]` lồng trong đoạn highlight cha** — giữ nguyên như V2.6, để `viet-tittle-v2` và `tong-hop-rabbit-hole` lấy `hooks[0].quote_en` mà không phải sửa gì.

Hai chỗ này phải **khớp tuyệt đối**: cùng `start`, cùng `end`, cùng `duration_sec`, cùng quote nguyên văn, cùng loại hook, cùng `is_segment_opening`. Lệch nhau một ký tự = lỗi, phải sửa trước khi ghi file.

#### Quy trình rút hook — chạy SAU khi đã chốt Start/End, TRƯỚC khi xuất

1. **Quét lại toàn bộ đoạn đã chốt**, gạch ra 3–6 câu ứng viên "nghe phát giật mình".
2. **Loại ngay** các câu: cần bối cảnh mới hiểu; nằm trong đoạn quảng cáo; chứa tên riêng lạ mà khán giả đại chúng không biết; đã spoil trọn nội dung.
3. **Chấm từng ứng viên còn lại** theo 4 tiêu chí bảng trên.
4. **Chọn câu thắng** → tra timestamp thật của dòng bắt đầu và dòng kết thúc trọn ý.
5. **Kiểm thời lượng.** Quá dài (>25s) → thu vào đúng mệnh đề đắt nhất. Quá ngắn (<5s) → mở rộng thêm một câu liền kề.
6. **Kiểm biên:** hook nằm trong `[start, end]` của đoạn. Nếu không → chọn lại, tuyệt đối không nới biên đoạn chỉ để chứa hook.

#### Tránh (anti-pattern)

- Câu dẫn nhập: *"So I want to talk about…"*, *"That's interesting."*, *"Right, exactly."*
- Câu mà từ đệm ("um", "you know", "like") chiếm gần nửa thời lượng.
- Câu chỉ trọn ý khi có cả hai người nói qua lại — trừ khi cả cặp vẫn ≤25 giây và liền mạch.
- Lấy từ đoạn đọc quảng cáo (nhà tài trợ đọc trong tập, lời mời đăng ký Tucker Carlson Network…).
- Hook hay nhưng nằm ngoài biên đoạn — **tuyệt đối không**.
- Hook trùng gần như nguyên văn với hook của một đoạn khác trong cùng tập.
- **Xuất hook ra một file riêng** — từ V2.7 là lỗi quy trình, không phải lựa chọn.

> **Dùng lại ở downstream:** `hooks[0].quote_en` là nguyên liệu sẵn cho `viet-tittle-v2` (chữ trên thumbnail, câu mở description) và cho `tong-hop-rabbit-hole` (đoạn teaser đầu tập tổng hợp). Viết hook chuẩn một lần, ba skill dùng chung. Các skill đọc `segments[]` để lấy nội dung nên lọc `kind == "highlight"` để bỏ qua entry hook.

### III.10 — LIÊM CHÍNH NỘI DUNG CHÍNH TRỊ (riêng Tucker)

Cáo buộc, tuyên bố và giả thuyết về người thật/tổ chức thật luôn được trình bày là **quan điểm của khách hoặc của Tucker** (`Says…`, `Claims…`, "khách cho rằng…") — không viết như sự thật đã xác lập. Không bịa quote, không ghép quote: mọi câu trích phải nguyên văn từ transcript. `summary_vi` và Tóm tắt viết **trung tính** với các tuyên bố chính trị/tôn giáo còn tranh cãi. **Không chọn** khối chỉ là công kích đảng phái/than phiền chung chung mà không có một tiết lộ, câu chuyện hay lập luận cụ thể — khối như vậy hạ CQ, không được cứu bằng chủ đề hot.

---

## IV. CHIẾN LƯỢC CHỌN LỌC

### Mặc định: TỰ ĐỘNG XẾP HẠNG, KHÔNG CẦN TỪ KHÓA
- Người dùng đưa từ khóa chủ đề cụ thể → bám theo; nếu khách không thực sự có thẩm quyền về chủ đề đó, cứ báo rõ điều này kèm GTF thấp để người dùng biết, nhưng vẫn chọn khối tốt nhất tìm được thay vì tự động từ chối.
- Không có từ khóa → tự quét toàn bộ, tự xếp hạng theo Mục III, chọn khối đứng đầu.

### Quy tắc "Rabbit Hole"
- Mỗi lần chạy chỉ trích xuất **DUY NHẤT 1 khối tốt nhất còn lại**.
- Ưu tiên tuyệt đối các "rabbit hole" liền mạch **15–22 phút**, nhiều chủ đề kết nối tự nhiên — luôn đắt hơn 1 mẩu chuyện đơn lẻ 5 phút. *(ngưỡng hiệu chỉnh V2.3, xem bảng ngay dưới)*

### Thời lượng — HIỆU CHỈNH BẰNG DỮ LIỆU (V2.3)

> Đây là thay đổi lớn nhất của V2.3. Ba phép kiểm định độc lập trên 1.725 video đều cho cùng kết luận, nên **ngưỡng này ưu tiên cao hơn cảm tính khi chọn biên cắt.**

| Khoảng | % sản lượng kênh | Hiệu suất (Idx) | Kết luận |
|---|---|---|---|
| ≤ 5 phút | 16,7% | **0.80** (CI 0.80–0.97) | ❌ Kém rõ rệt — tránh |
| 5–10 phút | 44,1% | 0.95 | ⚪ Kênh làm nhiều nhất nhưng chỉ dưới trung bình |
| 10–15 phút | 22,8% | 1.00 | ⚪ Trung bình |
| **15–20 phút** | 9,2% | **1.40** (CI 1.25–1.65) | ✅ **VÙNG VÀNG** |
| **20–30 phút** | 5,9% | **1.38** (CI 1.02–1.70) | ✅ Rất tốt |
| > 30 phút | 1,3% | 0.90 | ⚠️ Rơi lại — chỉ khi thật sự liền mạch |

Kiểm định trong-cùng-khách-mời (kiểm soát khách, thời kỳ, sản xuất): clip lọt top 25% của mỗi khách có **33,3%** dài ≥15 phút, clip nằm đáy 25% chỉ **8,7%** (p<0.001). Chiều ngược lại: clip ≤5 phút chiếm **8,7%** ở nhóm hit nhưng **21,7%** ở nhóm lặn (p<0.05).

**Ngưỡng áp dụng:**

| Trục | Tối thiểu | Mục tiêu | Trần |
|---|---|---|---|
| **AUTHORITY** | 10 phút liên tục | **15–22 phút** | 30 phút |
| **PERSONA** | 8 phút liên tục | **12–18 phút** | 25 phút |

> **⚠️ ĐÃ BỎ:** ngưỡng "PERSONA 3 phút / ưu tiên 3–8 phút" của V2.2. Dữ liệu cho thấy clip 3–5 phút là nhóm kém nhất kênh, kể cả clip hài. Bit hài hay vẫn cần được **gộp với riff liền kề cùng mạch** để đạt ≥8 phút, thay vì cắt gọn đúng câu chốt rồi dừng.

> **Lưu ý:** ngưỡng thời lượng ở bảng này áp cho **thân đoạn highlight** (`kind: "highlight"`), KHÔNG tính hook cold open. Entry hook 5–25 giây là phần dựng thêm lên đầu, không bao giờ bị đo theo ngưỡng này và không được dùng để "kéo" một khối ngắn cho đủ ngưỡng.

**Xử lý khi khối tốt nhất quá ngắn:**
1. **Ưu tiên số 1 — GỘP.** Tìm khối liền kề cùng mạch hội thoại và nối lại. Một rabbit hole 16 phút gồm 3 chủ đề nối tiếp luôn thắng một mẩu 6 phút gọn gàng.
2. Nếu không gộp được vì đứt mạch thật sự → vẫn ưu tiên chọn khối khác dài hơn có điểm gần bằng (chênh ≤1 điểm).
3. Chỉ giữ khối ngắn khi nó vượt trội hẳn (chênh >2 điểm) HOẶC xung quanh có rủi ro (cáo buộc chưa kiểm chứng, ngoài chuyên môn khách, quảng cáo xen giữa). Khi đó **ghi rõ ngoại lệ có chủ đích** trong `fit_reason` và báo lại người dùng.

### 3 Trường Hợp Cắt Cúp (Tối ưu Retention)

| TH | Điều kiện | Cấu trúc |
|---|---|---|
| **TH1** | Khối nhiều chủ đề | [Mở đầu ngắn] + [Cốt lõi] + [Tranh luận mở rộng] |
| **TH2** | Lõi đủ dài | Chặt mở đầu lan man → *in medias res* + [leo thang] |
| **TH3** | Hook mở đầu cực sốc | Giữ nguyên Hook + [Cốt lõi] + [Tranh luận] |
| **TH4** | Bit hài (chỉ PERSONA) | Vào thẳng câu châm ngòi + [riff] + cắt ngay sau câu chốt nặng nhất |

---

## V. LUỒNG "TÌM ĐOẠN TIẾP THEO"

1. **Tái sử dụng Guest Card** — không research lại, không in lại.
2. **Nhớ các khối đã chọn** — không lặp lại, không chồng lấn timestamp.
3. Lấy khối đứng kế tiếp trong bảng xếp hạng ĐIỂM CUỐI, chưa dùng.
4. **Cân bằng trục**: nếu 2–3 đoạn liên tiếp cùng trục, ưu tiên trục còn lại — trừ khi chênh lệch điểm >3.
5. Rút hook cold open cho đoạn mới (III.9) — không tái dùng hook của đoạn trước.
6. Xuất theo format khóa cứng. Không giải thích lại quy trình.

---

## Vb. LUỒNG "XUẤT CUTLIST" — QUY TẮC TUYỆT ĐỐI

**KHÔNG ĐƯỢC làm:** ghi file `.md`, `.txt`, `.csv`; in bảng markdown hay bullet; **tách hook và highlight thành hai file**. Sản phẩm cuối CHỈ là **MỘT file `.json` THẬT duy nhất** trên disk, chứa cả hook lẫn thân đoạn trong cùng một mảng `segments[]`.

### Bước 1 — XẾP HẠNG THEO ĐIỂM CUỐI

Với TẤT CẢ đoạn highlight đã chọn: xếp lại theo ĐIỂM CUỐI giảm dần (`CQ × GTF/10`), **`content_rank` 1 = hay nhất**. KHÔNG giữ thứ tự đã chọn.

Trọng số: Guest-Topic Fit (cao nhất) → **Keyword Reach × KGC** → **Hook cold open mạnh** → Credibility/Specificity → Revelation dồn dập → Viral/Shareability → Density → Thời lượng theo trục.

### Bước 2 — DỰNG MẢNG `segments[]` PHẲNG (hook + highlight chung một dãy)

Đây là thay đổi cốt lõi của V2.7. Duyệt các đoạn highlight theo `content_rank` tăng dần; với mỗi đoạn, **đẩy hook của nó vào mảng TRƯỚC, rồi mới đẩy chính đoạn đó**:

```
[hook 01 của đoạn #1] → [highlight #1] → [hook 01 của đoạn #2] → [highlight #2] → …
```

Đoạn nào có 2 hook thì cả hai đứng trước nó, theo `hook_rank` tăng dần:

```
[hook 01 đoạn #1] → [hook 02 đoạn #1] → [highlight #1] → …
```

**Đánh số `rank`:** liên tục 1, 2, 3, … theo đúng vị trí trong mảng, **tính cả entry hook**. `rank` = thứ tự cắt, KHÔNG phải thứ hạng chất lượng. Thứ hạng chất lượng nằm ở `content_rank` (chỉ có ở entry highlight).

**Mọi entry BẮT BUỘC có `kind`:** `"hook"` hoặc `"highlight"`. Đây là chỗ để tool và các skill downstream phân biệt hai loại.

### Bước 3 — GHI FILE THỰC TẾ RA DISK

- Tên file BẮT BUỘC `.json`: `cutlist_<episode_id>.json`. TUYỆT ĐỐI KHÔNG `.md`/`.txt`, và **không có file thứ hai cho hook**.
- Vị trí: thư mục outputs của phiên làm việc (hoặc nơi người dùng chỉ định).
- Nội dung CHÍNH XÁC JSON **CUTLIST V2 (layout `flat_hooks`)** dưới đây — dữ liệu thật, KHÔNG placeholder, segments xếp theo `rank` tăng dần. Giữ `"version": 2` để tương thích ngược với `tong-hop-rabbit-hole` và các cutlist V2 cũ; `cutlist_layout`, `kind`, `content_rank` là field thêm, công cụ cũ bỏ qua được.

```json
{
  "version": 2,
  "cutlist_layout": "flat_hooks",
  "source": "chon-noi-dung-tucker",
  "episode": {
    "id": "TUCKER-1",
    "guest": "Mike Benz",
    "source_video": "Mike Benz ｜ The Tucker Carlson Show.mp4",
    "guest_profile": {
      "identity": "Cựu quan chức Bộ Ngoại giao Mỹ, nay điều tra về bộ máy kiểm duyệt và các khoản tài trợ của USAID",
      "archetypes": ["whistleblower", "investigative researcher"],
      "value_axis_primary": "authority",
      "value_axis_secondary": "none",
      "expertise_tier1": ["censorship industrial complex", "state department programs"],
      "expertise_tier2": ["usaid funding", "foreign policy influence operations"],
      "low_authority_zones": ["hard science", "UFO", "theology"],
      "speaking_style": "Nói nhanh, dồn dập tên chương trình, tổ chức và con số, dẫn tài liệu liên tục",
      "chemistry_with_host": "Tucker nghe nhiều hơn nói, liên tục hỏi dồn và phản ứng sửng sốt",
      "audience_wants": ["where usaid money goes", "government censorship", "deep state"],
      "audience_ignores": ["his take on aliens", "generic partisan commentary"],
      "confidence": "Cao"
    }
  },
  "segments": [
    {
      "rank": 1,
      "kind": "hook",
      "parent_rank": 2,
      "hook_rank": 1,
      "start": "00:28:12",
      "end": "00:28:24",
      "duration_sec": 12,
      "title": "HOOK 01 — Tiêu đề ngắn cho Cutter",
      "summary_vi": "1 câu tiếng Việt: lát cold open này nói gì, viết THẲNG",
      "hook_type": "shock_claim",
      "is_segment_opening": false,
      "quote_en": "Câu nguyên văn tiếng Anh — lát cắt đắt nhất của cả đoạn",
      "hook_en": "Câu nguyên văn tiếng Anh — lát cắt đắt nhất của cả đoạn",
      "summary_en": "1 câu tiếng Anh: vì sao câu này giữ được người xem trong 10 giây đầu",
      "core_keyword": "usaid",
      "topics": ["chủ đề chính 1", "chủ đề 2", "chủ đề 3"],
      "value_axis": "authority"
    },
    {
      "rank": 2,
      "kind": "highlight",
      "content_rank": 1,
      "summary_vi": "1 câu tiếng Việt, viết THẲNG — không giật tít — để đọc lướt hiểu ngay đoạn nói về ai/chuyện gì",
      "start": "00:21:54",
      "end": "00:35:41",
      "title": "Tiêu đề ngắn cho Cutter",
      "hooks": [
        {
          "rank": 1,
          "flat_rank": 1,
          "start": "00:28:12",
          "end": "00:28:24",
          "duration_sec": 12,
          "quote_en": "Câu nguyên văn tiếng Anh — lát cắt đắt nhất của cả đoạn",
          "type": "shock_claim",
          "is_segment_opening": false,
          "why": "1 câu tiếng Anh: vì sao câu này giữ được người xem trong 10 giây đầu"
        }
      ],
      "core_keyword": "usaid",
      "keyword_reach": "R2",
      "keyword_credibility": "high",
      "keyword_reason": "People typing 'usaid' want to know what the agency actually funds, and the title shows a former State Department official explaining it from the inside — the credential is visible before the click.",
      "satellite_keywords": ["censorship industrial complex", "state department"],
      "topics": ["chủ đề chính 1", "chủ đề 2", "chủ đề 3"],
      "hook_en": "Câu Start tiếng Anh nguyên văn — cú hook mạnh nhất của đoạn",
      "summary_en": "1-2 câu tiếng Anh tóm tắt đoạn nói về gì, có tên riêng, có sự kiện cụ thể.",
      "intensity": 9,
      "value_axis": "authority",
      "gtf": 9,
      "cq": 9,
      "final_score": 8.1,
      "fit_reason": "1 câu tiếng Anh: vì sao CHÍNH khách mời này nói chủ đề này mới đắt"
    }
  ]
}
```

**Cách điền field CHUNG cho mọi entry:**
- `rank`: số thứ tự trong mảng, liên tục từ 1, tính cả hook.
- `kind`: `"hook"` hoặc `"highlight"` — bắt buộc, không được thiếu.
- `start` / `end` / `title`: ba field Video Cutter thật sự dùng. Entry hook và entry highlight điền y hệt nhau về mặt hình thức.
- `summary_vi`: 1 câu tiếng Việt viết THẲNG, không giật tít.

**Field riêng của entry `kind: "hook"`:**
- `parent_rank`: `rank` của entry highlight cha (luôn là entry đứng ngay sau nhóm hook).
- `hook_rank`: `1` hoặc `2` — trùng với `rank` trong mảng `hooks[]` lồng của đoạn cha.
- `title`: **`HOOK 01 — <title đoạn cha>`** (hook thứ hai: `HOOK 02 — <title đoạn cha>`). Tiền tố in hoa, hai chữ số, gạch ngang dài — để nhìn danh sách file tool xuất ra là biết ngay cold open thuộc đoạn nào.
- `duration_sec`: số giây thật (`end` − `start`), phải nằm trong **5–25**, lý tưởng 8–15.
- `quote_en`: nguyên văn tiếng Anh, không viết lại, không rút gọn. `hook_en` điền **cùng chuỗi** với `quote_en` để entry hook có cùng shape với entry highlight.
- `summary_en`: 1 câu tiếng Anh — vì sao câu này giữ chân người xem trong 10 giây đầu (chính là nội dung `why` ở bản lồng).
- `hook_type`: `shock_claim` · `fact_bomb` · `story_teaser` · `curiosity_question` · `conflict`.
- `is_segment_opening`: `true` nếu hook chính là phần mở đầu của đoạn cha → người dựng KHÔNG cần cắt riêng dán lại.
- `core_keyword`, `topics`, `value_axis`: **chép y nguyên từ đoạn cha**, để mọi entry trong file đều tra được về cùng một trục chủ đề.
- **KHÔNG khai** trên entry hook: `gtf`, `cq`, `final_score`, `content_rank`, `intensity`, `keyword_reach`, `keyword_credibility`, `keyword_reason`, `satellite_keywords`, `fit_reason`, `hooks`. Những field này chỉ thuộc về đoạn highlight.

**Field riêng của entry `kind: "highlight"`:**
- `content_rank`: thứ hạng chất lượng theo ĐIỂM CUỐI, 1 = hay nhất. Các entry highlight trong file phải có `content_rank` tăng dần.
- `episode.id`: `TUCKER-<số>`.
- `episode.guest_profile`: bản rút gọn Guest Card, viết tiếng Anh cho field mảng, tiếng Việt cho `identity`/`speaking_style`/`chemistry_with_host`.
- `hooks`: **BẮT BUỘC, 1–2 phần tử** (Mục III.9), xếp theo `rank` — giữ nguyên để `viet-tittle-v2` và `tong-hop-rabbit-hole` đọc như cũ. Mỗi phần tử phải **khớp tuyệt đối** với entry hook phẳng tương ứng.
  - `hooks[].rank`: 1 hoặc 2 — bằng `hook_rank` của entry phẳng.
  - `hooks[].flat_rank`: `rank` của entry hook phẳng tương ứng trong `segments[]` — cầu nối hai chiều.
  - `hooks[].start` / `hooks[].end`: timestamp thật, **PHẢI nằm trong `[segment.start, segment.end]`**.
  - `hooks[].duration_sec`: `end` − `start`, trong khoảng **5–25**.
  - `hooks[].quote_en`: nguyên văn tiếng Anh.
  - `hooks[].type`: `shock_claim` · `fact_bomb` · `story_teaser` · `curiosity_question` · `conflict`.
  - `hooks[].is_segment_opening`: `true`/`false`.
  - `hooks[].why`: 1 câu tiếng Anh — vì sao câu này giữ chân người xem trong 10 giây đầu.
- `core_keyword`: **BẮT BUỘC.** Cụm tiếng Anh **viết đúng như người ta sẽ gõ vào ô tìm kiếm**, chữ thường. Không giới hạn loại từ — `coronavirus`, `hitler`, `workout smarter`, `why you can't lose weight` đều hợp lệ. KHÔNG phải tên khách mời (trừ khách là thứ người ta đang săn tìm: Bob Lazar, Snowden, Putin).
- `keyword_reach`: `R3` (rất nhiều người tìm) · `R2` (lượng tìm ổn định) · `R1` (ít người tìm / phải giải thích thuật ngữ). `R0` không được xuất.
- `keyword_credibility`: `high` · `medium` · `low` — người gõ cụm đó, nhìn thấy người đang nói, có tin không. **Uy tín CẢM NHẬN, không phải bằng cấp** (Tucker + hàng chục năm làm truyền hình chính trị = `high` cho `fox news`). `low` không được xuất — clickbait hại retention, không phục vụ mục tiêu thu hút người xem bền vững.
- `keyword_reason`: 1–2 câu tiếng Anh — người gõ cụm này đang muốn biết gì, đoạn này trả lời gì, và **vì sao người nói đáng tin trong mắt họ**. Nếu `R1`: nêu rõ cầu nối sang một keyword R3.
- `satellite_keywords`: 0–2 cụm — các chủ đề còn lại của rabbit hole, để `viet-tittle-v2` dựng Connective Thread.
- `topics`: 2–5 cụm chủ đề tiếng Anh ngắn.
- `hook_en`: đúng câu quote Start của thân đoạn, không viết lại. (Khác `hooks[]` — đây là câu mở đầu thân đoạn, `hooks[]` là các lát cold open dựng lên trước.)
- `final_score`: `CQ × (GTF/10)`, làm tròn 1 chữ số thập phân.
- `fit_reason`: 1 câu tiếng Anh, lý do khách mời khiến đoạn đắt.

**Kiểm tra trước khi ghi file (bắt buộc, tự chạy):**
1. Chỉ có **một** file `.json` được ghi — không có file hook riêng.
2. `rank` liên tục 1..N, không trùng, không nhảy cóc; mảng xếp theo `rank` tăng dần.
3. Mọi entry đều có `kind`; mỗi entry `kind: "hook"` đứng **trước** entry highlight mà `parent_rank` trỏ tới, và giữa chúng không có entry highlight nào khác.
4. Mọi `hook.start/end` nằm trong `[start, end]` của đoạn cha; mọi `duration_sec` trong khoảng 5–25.
5. Không đoạn highlight nào thiếu hook; không đoạn nào có >2 hook; không hai đoạn dùng trùng một hook.
6. Entry hook phẳng và phần tử `hooks[]` lồng tương ứng **khớp tuyệt đối**: `start`, `end`, `duration_sec`, `quote_en`, loại hook, `is_segment_opening`.
7. Mọi entry highlight có `content_rank`, và các `content_rank` tăng dần theo thứ tự xuất hiện.
8. `title` của mọi entry hook bắt đầu bằng `HOOK 01 — ` hoặc `HOOK 02 — `.

### Bước 4 — Báo đúng 1 dòng kèm đường dẫn thật:
`✅ Đã lưu cutlist V2 (layout flat_hooks, <H> hook + <S> đoạn trong CÙNG 1 file): <đường_dẫn_đầy_đủ>\cutlist_<episode_id>.json → import thẳng vào Video Cutter, HOẶC gom nhiều file cutlist_*.json rồi chạy skill tong-hop-rabbit-hole.`

**Dự phòng (chỉ khi không ghi được file):** in JSON trong code block, nhắc lưu thành `.json` (KHÔNG `.md`).

**Không thêm văn bản nào khác. Không giải thích. Không tóm tắt lại các đoạn.**

---

## VI. FORMAT ĐẦU RA (KHÓA CỨNG)

Mỗi lần chạy chỉ xuất **1 kết quả duy nhất**:

[N]. **[Tiêu đề đoạn nội dung — giật tít được]**

Start: (hh:mm:ss) "[Trích câu tiếng Anh — Hook mạnh nhất]..."

End: (hh:mm:ss) "...[Trích câu tiếng Anh kết thúc]"

Tóm tắt: [Tóm tắt chi tiết tiếng Việt, diễn giải sâu từ hook đến kết. Nêu dữ kiện/con số/câu chuyện đắt nhất. Nhân vật phải có TÊN ĐẦY ĐỦ ở lần nhắc đầu.]

Tại sao đoạn này đắt: [2–4 câu — hook, revelation, leo thang, density, rabbit hole liền mạch.]

**🪝 HOOK COLD OPEN** (lát cắt dựng lên đầu video, nằm trong chính đoạn này — xuất thành entry riêng trong cùng file cutlist):
1. `(hh:mm:ss – hh:mm:ss · ~Ns)` "[quote nguyên văn tiếng Anh]" — *[loại hook]*
   → [1 câu: vì sao câu này giữ chân người xem trong 10 giây đầu]
2. `(hh:mm:ss – hh:mm:ss · ~Ns)` "[quote 2]" — *[loại hook]* *(chỉ khi đoạn có 2 khoảnh khắc đỉnh tách biệt)*
   → [1 câu lý do]

**🔑 Keyword hạt nhân:** `[cụm viết đúng như người ta gõ vào ô tìm kiếm]` · **Reach [R3/R2/R1]** · **KGC [cao/trung bình]**
*Vì sao đoạn này thắng nhờ keyword đó:* [1–2 câu — người gõ cụm này đang muốn biết gì, đoạn này trả lời gì, và **vì sao người đang nói đáng tin trong mắt họ** (uy tín cảm nhận, hiển thị được lên title/thumbnail). Nếu R1: ghi rõ cầu nối sang keyword R3.]
*Keyword vệ tinh:* `[kw2]`, `[kw3]` — hoặc ghi "không có" nếu khối đơn chủ đề.

**🎯 Fit với khách mời:** [1–2 câu — vùng chuyên môn cấp mấy / vàng persona. Kèm `GTF x/10 · CQ y/10` và trục giá trị, cùng `Điểm cuối: [CQ × GTF/10]`.]

---

📋 **CUT BLOCK** — timestamp/title thực tế, KHÔNG placeholder. Hook và thân đoạn nằm CHUNG một mảng, hook đứng trước:
```json
[
  {"rank":1,"kind":"hook","parent_rank":2,"hook_rank":1,"start":"HH:MM:SS","end":"HH:MM:SS","duration_sec":12,"title":"HOOK 01 — Tiêu đề thực tế"},
  {"rank":2,"kind":"highlight","content_rank":1,"start":"HH:MM:SS","end":"HH:MM:SS","title":"Tiêu đề thực tế"}
]
```

---

### QUY TẮC TIMESTAMP — BẮT BUỘC

1. Tìm câu quote trước.
2. Tra timestamp trực tiếp từ transcript (số [hh:mm:ss] ngay trên/trước dòng chứa quote).
3. Ghi timestamp đó — không ước tính.
4. Không bao giờ chọn timestamp trước rồi mới chọn quote.
5. Áp y hệt cho timestamp của hook cold open — kể cả khi hook chỉ dài 8 giây.

Kiểm tra chéo: mở transcript, nhảy tới timestamp, câu đầu tiên nghe được có đúng là quote này không? Không chắc → tra lại.

**Nếu transcript KHÔNG có timestamp:** không được suy ra giờ:phút:giây từ số từ hay tốc độ nói. Báo rõ cho người dùng, dùng số dòng transcript làm mốc tạm, và xin bản transcript có timestamp trước khi xuất cutlist.

### QUY TẮC TÊN ĐẦY ĐỦ NHÂN VẬT — BẮT BUỘC

1. Lần đầu xuất hiện → TÊN ĐẦY ĐỦ, chính tả chuẩn.
2. Sau đó có thể gọi ngắn.
3. Nhân vật không quá nổi tiếng → thêm cụm định danh ngắn.
4. Không áp dụng cho quote tiếng Anh Start/End, quote hook, và `title` cutlist.

---

## VII. QUY TRÌNH THỰC HIỆN (V2.7)

**Giai đoạn A — Khách mời (1 lần/tập):**
1. Xác định khách mời (II.1).
2. Research 3 nguồn (II.2), tuân thủ liêm chính.
3. Định vị archetype + trục giá trị (II.3, II.4).
4. In GUEST CARD (II.5), dừng cho người dùng đọc/chỉnh sửa.

**Giai đoạn B — Nội dung:**
5. Quét toàn bộ transcript, phân khối theo cụm chủ đề liền mạch.
6. Chấm CQ (III.1).
7. Chấm GTF (III.2).
8. Rà lại các khối persona có thể bị đánh giá thấp vì "trông như không có nội dung" (Luật Vàng Persona) — không áp gate loại nào theo GTF nữa.
9. Tính ĐIỂM CUỐI (`CQ×GTF/10`), xếp hạng (III.3), chạy 7 câu hỏi kiểm tra (III.4).
10. **Tie-break:** nếu hai khối đầu bảng chênh <1 điểm → áp PRIOR CHỦ ĐỀ (III.6) và tín hiệu CÂU CHUYỆN (III.7). Khối thuộc chính trị/culture war hoặc tâm linh/self-help phải chênh ≥1,5 điểm mới được chọn.
11. Chọn khối đứng đầu chưa dùng. **Kiểm tra ngưỡng thời lượng (Mục IV):** nếu <10 phút (AUTHORITY) hoặc <8 phút (PERSONA) → thử GỘP với khối liền kề cùng mạch trước khi chấp nhận.
12. **Rút KEYWORD HẠT NHÂN (III.8)** — "gõ một cụm gì vào ô tìm kiếm để ra đúng đoạn này?". Chấm **Reach × KGC**, tra ma trận. Ô ❌ → thu hẹp biên / gộp / đổi khối. R1 + KGC cao → kiểm điều kiện vượt ≥1,5 điểm và tìm cầu nối sang keyword R3.
13. Xác định trường hợp cắt (TH1–TH4). Nếu keyword hạt nhân không nằm ở 1/3 đầu khối → cân nhắc dời Start tới chỗ nó xuất hiện.
14. Chọn Start/End — timestamp gắn trực tiếp; áp III.5 nếu có tiểu sử xen kẽ.
15. **Rút HOOK COLD OPEN (III.9)** — quét lại đoạn đã chốt, gạch 3–6 ứng viên, chấm 4 tiêu chí, chọn 1 (tối đa 2), gắn timestamp thật, kiểm thời lượng 5–25 giây và kiểm hook nằm trong biên đoạn.
16. Kiểm tra chéo timestamp + quote (cả thân đoạn lẫn hook).
17. Kiểm tra tên đầy đủ nhân vật.
18. Xuất kết quả theo format khóa cứng — gồm "Tại sao đắt", **"Hook cold open"**, **"Keyword hạt nhân"**, "Fit với khách mời", và CUT BLOCK.
19. **Khi người dùng yêu cầu xuất cutlist:** dựng mảng `segments[]` phẳng theo Mục Vb (hook đứng ngay trước đoạn cha, `rank` liên tục), chạy đủ 8 mục kiểm tra, rồi ghi **đúng MỘT file** `cutlist_<episode_id>.json`.

---

## VIII. TIÊU CHÍ CHỌN NỘI DUNG TỐT (tổng hợp)

Ưu tiên:
- **Nội dung thực sự thu hút người xem trước tiên** (CQ cao: hook mạnh, revelation dồn dập, density cao) — đây là mục tiêu tối thượng từ V2.5; GTF chỉ còn là hệ số điều chỉnh điểm, không phải điều kiện loại
- **GTF cao** — chuyên môn/thẩm quyền dùng để đào sâu chủ đề, không chỉ vì "chuyện riêng" (vẫn cộng điểm mạnh, chỉ không còn là điều kiện bắt buộc)
- **Rabbit hole liền mạch dài — 15–22 phút**, nhiều chủ đề kết nối tự nhiên *(ngưỡng V2.3, xem Mục IV)*
- **Là một CÂU CHUYỆN có thật** — nhân vật, mốc thời gian, diễn biến, kết cục *(III.7)*
- **Có KEYWORD HẠT NHÂN gõ được vào ô tìm kiếm, Reach R3/R2 VÀ người nói đáng tin với chính cụm đó (KGC cao)** *(III.8)*
- **Rút được HOOK COLD OPEN sắc — một lát 5–25 giây tự đứng một mình, giật mình được, không spoil trọn** *(III.9)*
- **Vàng persona** — Tucker bị trêu/bị bẻ, riff leo thang, khoảnh khắc thật
- **Conflict/Tranh cãi**, **Revelation dồn dập**, **Story stakes cao**, **Expertise sâu**, **Hook mạnh**, **Density cao + kết chốt nặng**

Tránh:
- **Khối dưới 8 phút** — nhóm kém nhất kênh; gộp với khối liền kề trước khi chấp nhận
- **Khối không rút được cụm nào để gõ vào ô tìm kiếm (R0)** — nội dung lan man, không có chỗ neo cho title/thumbnail
- **Khối không rút nổi một hook cold open nào** — cả 15 phút không có một câu tự đứng một mình được là dấu hiệu khối nhạt, dù tóm tắt nghe hay
- **Keyword R1 mà không tìm được cầu nối sang R3** — chính xác nhưng không ai tìm
- **Reach cao nhưng KGC thấp** — clickbait: kéo được click, mất người xem ngay phút đầu
- Chủ đề hot nhưng nội dung thực chất nhạt (không hook, không revelation, không density) — đừng chọn chỉ vì chủ đề nghe hấp dẫn; nếu khách không có thẩm quyền NHƯNG bản thân đoạn (thường do Tucker kể) vẫn đủ CQ cao thì cứ chọn, chỉ cần hạ GTF đúng mức
- Đoạn "ai ngồi ghế đó cũng nói y hệt"
- Kéo dài bit hài quá điểm chốt để đủ ngưỡng thời lượng
- Tiểu sử/đời tư khách mời không có fame độc lập (trừ archetype 1/9)
- **Xuất cutlist thành hai file** (một cho hook, một cho highlight) — từ V2.7 luôn là MỘT file

---

## IX. PHỤ LỤC — GIẢ THUYẾT ĐÃ KIỂM ĐỊNH VÀ **BỊ BÁC**

Ghi lại để không ai đi lại đường cụt. Tất cả đo trên 1.549 video ≥4 năm tuổi của kênh JRE Clips.

### ❌ "Clip focus vào MỘT sự kiện/nhân vật/vật thể cụ thể thì ăn hơn clip nói chung chung"

Đây là giả thuyết trực giác rất hợp lý (kiểu: video về kim tự tháp Ai Cập > video về lý thuyết khảo cổ). **Đã kiểm định bằng 4 cách đo độc lập, tất cả đều KHÔNG có ý nghĩa thống kê:**

| Cách đo | Kết quả |
|---|---|
| NER thật (spaCy) tách "vùng người nói" khỏi "vùng chủ đề", đếm thực thể đích danh | Top 150: 66,7% có thực thể · phần còn lại: 71,6% — **chi2=1,6, ns** |
| Xác suất đạt ≥5M view khi có vs không có thực thể | 12,3% vs 15,2% — **lift 0,81x, ns** |
| Kiểm định trong-cùng-khách-mời (20 khách, kiểm soát khách/thời kỳ/sản xuất) | "Có thực thể" thắng **8/20** khách — sign test **p=0,868** |
| Title liệt kê nhiều thứ vs một tiêu điểm / danh từ phạm trù rộng vs hẹp / kể sự việc vs nêu quan điểm | **Cả ba đều ns** |
| **Thực thể ĐẠI CHÚNG vs NGÁCH vs KHÔNG CÓ** (tiền thân của thang Reach ở III.8) | 13,6% vs 11,5% vs 15,2% đạt ≥5M — **chi2=0,1, ns** |

**Cảnh báo phương pháp:** một phiên bản sớm hơn của phép đo này *có vẻ* xác nhận giả thuyết (73% vs 49%, p<0.001). Đó là **artifact**: từ điển thực thể được soạn bằng cách đọc chính các video top, nên nó tự khớp với nhóm top. Khi thay bằng NER không thiên vị, hiệu ứng biến mất hoàn toàn.

**Nhưng KHÔNG có nghĩa là "cứ chung chung cũng được".** Có hai lý do phải cẩn trọng:
1. Mẫu bị chặn đầu — chỉ gồm video >880K view. Rất có thể **độ cụ thể là điều kiện CẦN để lọt vào nhóm thành công**, và trong nội bộ nhóm đã thành công thì nó hết tác dụng phân biệt. Thực tế 93% clip top đã sẵn cụ thể, chỉ 7% là trừu tượng — gần như không còn phương sai để đo.
2. Phép đo dựa trên **title**, không đo được "nội dung có thực sự tập trung hay không". Một title có tên riêng vẫn có thể là một cuộc tán gẫu lan man.

**Kết luận hành động:** giữ thói quen chọn đoạn có tiêu điểm rõ — nó vô hại và gần như chắc chắn là điều kiện cần. Nhưng **đừng loại một khối chỉ vì nó không có tên riêng**, và đừng ưu tiên một khối yếu chỉ vì nó gắn với một cái tên nổi. Khi phải chọn, **thời lượng 15–22 phút và tính câu chuyện là tín hiệu mạnh hơn nhiều.**

### 🔗 Mục III.8 có mâu thuẫn với kết quả này không? — KHÔNG. Nó GIẢI THÍCH kết quả này.

Phép kiểm định ở trên đo **"title có chứa thực thể đích danh hay không"** (dùng NER: người, tổ chức, địa danh, sự kiện, tác phẩm). Đó **không phải** thứ III.8 nói tới.

III.8 định nghĩa keyword là **cụm khán giả gõ vào ô tìm kiếm** — và rất nhiều cụm như thế **không phải thực thể**, nên NER đếm chúng là "không có thực thể":

| Clip | View | Keyword | NER đếm là |
|---|---|---|---|
| Joe Rogan - How To Workout Smarter | 15M | `workout smarter` | ❌ không có thực thể |
| Edward Snowden: How Your Cell Phone Spies on You | 19M | `phone spying` | ❌ không có thực thể |
| Joe Rogan - Why Obese People Can't Lose Weight | 11M | `why you can't lose weight` | ❌ không có thực thể |
| Joe Rogan on Uncontacted Tribes | 13M | `uncontacted tribes` | ❌ không có thực thể |

Nhóm "không có thực thể" trong phép đo **đầy ắp keyword tốt**. Đó chính là lý do nó đạt tỉ lệ hit **15,2%** — cao hơn cả nhóm "có thực thể" (12,3%).

**Kết luận đúng phải là:** phép đo cũ sai đơn vị. Nó hỏi *"có tên riêng không"* trong khi câu hỏi đúng là *"có phải cụm người ta đang tìm không"*. Một cái tên riêng ít người tìm (`Rendlesham`, `Blagojevich`) không bằng một cụm không-tên-riêng nhiều người tìm (`workout smarter`).

**Vậy phần nào của III.8 đã được kiểm chứng, phần nào chưa?**

| Thành phần | Trạng thái |
|---|---|
| "Keyword phải là thực thể đích danh" | ❌ **SAI** — đã bác bỏ, và đó là lý do III.8 KHÔNG yêu cầu điều này |
| "Keyword = cụm người ta gõ vào ô tìm kiếm" | ⚪ Chưa đo được bằng dữ liệu title (cần dữ liệu search volume thật). Là **định nghĩa vận hành**, không phải giả thuyết cần chứng minh |
| Thang **Reach** (R3 > R2 > R1) | ⚠️ Bằng chứng: ca NdGT #919 (n=5, chênh 54 lần). Phép đo gần đúng trên toàn mẫu ra ns. **Giả thuyết làm việc** |
| **KGC** (người search có tin người nói không) | ⚠️ Chưa đo riêng. Đây từng là **Luật 1 phát biểu lại từ phía ô tìm kiếm** — Luật 1 đã bị bỏ ở V2.5, nhưng suy luận "KGC thấp thì đừng chọn làm keyword hạt nhân" vẫn còn giá trị độc lập vì nó phản ánh trải nghiệm người xem thật (bỏ giữa chừng), không phải vì gắn với gate cũ |
| Bắt buộc khai báo keyword | ✅ Không cần bằng chứng — là **kỷ luật quy trình**: không rút được keyword = dấu hiệu khối lan man; và `viet-tittle-v2`/`tao-thumbnail`/`tong-hop-rabbit-hole` đều cần chỗ neo này |
| **HOOK COLD OPEN (III.9)** | ⚠️ **Chưa đo trên dữ liệu kênh.** Dựa trên nguyên lý retention chung của YouTube (khán giả quyết định ở 5–15 giây đầu), chưa phải kết luận rút từ 1.725 video. Là **kỷ luật quy trình + giả thuyết làm việc**: cách kiểm chứng ở cuối phụ lục này |
| **Layout một file (V2.7)** | ✅ Không cần bằng chứng — là **quyết định vận hành** của chủ kênh: tool cắt chỉ nhận một file, hook phải là entry bình thường để cắt được cùng lượt với thân đoạn |

**Điều KHÔNG được làm:** biến `keyword_reach` thành hệ số nhân vào ĐIỂM CUỐI. Nó là **tie-break và bộ lọc ngưỡng** (R1 phải vượt ≥1,5 điểm; R0 và KGC thấp loại). Biến thành hệ số nhân là quay lại đúng kiểu suy luận mà dữ liệu đã bác. Điều tương tự áp cho hook: **không nhân "độ mạnh hook" vào ĐIỂM CUỐI** — hook là bước bắt buộc phải làm sau khi đã chọn khối, không phải biến số xếp hạng khối. Và **entry hook không bao giờ tham gia xếp hạng `content_rank`** — nó chỉ là một lát cắt của đoạn cha.

### ⚠️ Quan sát định tính đáng chú ý (chưa đủ dữ liệu để thành luật)

Cùng khách **Neil deGrasse Tyson**, cùng tập #919, cùng ngày đăng, chênh nhau **54 lần view**:

| View | Title |
|---|---|
| 5,9M | Responds to **Stephen Hawking's** Take on **Aliens** |
| 5,8M | On How **Monster's Inc** Got the 4th Dimension Right |
| 758K | Explains **Heisenberg's Uncertainty Principle** |
| 199K | "Some infinities are bigger than others" |
| 110K | Debunking **Flat-Earthers, Astrology** |

Cả 5 đều "cụ thể". Cái tách nhóm thắng không phải độ cụ thể, mà là **chủ thể có sẵn quan hệ tò mò với khán giả đại chúng** (người ngoài hành tinh, Monster's Inc) so với **chủ thể chính xác nhưng gây e ngại về mặt kỹ thuật** (nguyên lý bất định, vô hạn, bác bỏ chiêm tinh). Ngoài ra nhóm thua có thói quen xấu: nhét `#919` vào đầu title.

**Gợi ý áp dụng:** khi chọn giữa hai khối cùng chất lượng, ưu tiên khối mà **người ngoài ngành cũng đã tò mò sẵn về chủ thể**, và tránh khối phải giải thích thuật ngữ mới hiểu tại sao nên xem. Đây là quan sát trên **1 tập, n=5** — và phép đo tương đương trên toàn mẫu 1.549 video lại cho kết quả ns. Hãy coi thang Reach ở III.8 là **giả thuyết làm việc có lý lẽ**, không phải luật đã chứng minh.

**Cách kiểm chứng thang Reach trong 3 tháng tới:** ghi `keyword_reach` cho mọi đoạn xuất ra, tích đủ ~60–80 clip đã lên sóng ≥60 ngày, rồi so median view giữa nhóm R3 và nhóm R1–R2. Đây là thí nghiệm rẻ và tự chạy được — nếu R3 không tách khỏi R1/R2, hạ III.8 xuống thành checklist thuần kỷ luật và bỏ luật "R1 phải vượt ≥1,5 điểm".

**Cách kiểm chứng HOOK COLD OPEN:** đây là thí nghiệm A/B rẻ nhất trong cả workflow vì cùng một nội dung, chỉ khác 10 giây đầu. Đăng ~20 clip có dán hook cold open lên đầu và ~20 clip mở thẳng vào thân đoạn, cùng khoảng thời gian, rồi so **tỉ lệ giữ chân ở mốc 30 giây** trong YouTube Analytics (không so tổng view — view còn phụ thuộc title/thumbnail). Nếu nhóm có hook không nhỉnh hơn rõ ở mốc 30 giây, hạ III.9 xuống thành tuỳ chọn thay vì bước bắt buộc.