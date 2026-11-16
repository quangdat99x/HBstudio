---
name: chon-noi-dung-srs
description: "Workflow quét transcript Shawn Ryan Show (SRS) và chọn khối nội dung đắt giá nhất cho kênh Shawn Ryan Show Highlights — bản SRS V1.0 (clone cấu trúc JRE V2.7 + dữ liệu SRS V5.0): lập Hồ Sơ Khách Mời bắt buộc trước khi quét (archetype + LANE + NHÃN THẨM QUYỀN HIỂN THỊ, tôn trọng OPSEC), xếp hạng theo CQ×GTF với LUẬT 0 expertise-first, NGƯỠNG THỜI LƯỢNG và PRIOR CHỦ ĐỀ hiệu chỉnh từ dữ liệu thật 2.000 clip kênh SRS Clips (2022–2026), BẮT BUỘC khai báo KEYWORD HẠT NHÂN (Reach × KGC) và BẮT BUỘC rút HOOK COLD OPEN — lát cắt 5–25 giây đắt nhất nằm ngay trong đoạn. Cutlist chỉ xuất MỘT file duy nhất: hook là entry bình thường trong chính mảng segments[], đứng ngay trước đoạn highlight cha, import thẳng vào Video Cutter. Giữ luật tách quảng cáo và quy tắc an toàn nội dung. Không có gate loại thẳng theo thẩm quyền khách mời: trọng tâm là nội dung thu hút người xem, GTF chỉ là hệ số. Kích hoạt khi người dùng gửi transcript SRS kèm \"chọn nội dung srs\", \"chạy wf chọn nội dung srs\", \"quét transcript shawn ryan\", \"tìm đoạn tiếp theo\", \"xuất cutlist srs\", \"tìm hook mở đầu\", hoặc muốn cắt clip hay nhất từ Shawn Ryan Show."
---

# Workflow: Chọn Nội Dung Shawn Ryan Show — SRS V1.0 (Expertise-First + Data-Calibrated + Keyword-Anchored + Hook-First + One-File Cutlist)

> **Nguồn gốc bản này:** clone toàn bộ **cấu trúc, quy trình và hợp đồng đầu ra** của `chon-noi-dung-jre-v2` bản V2.7 (Guest Card → CQ×GTF → keyword hạt nhân → hook cold open → MỘT file cutlist layout `flat_hooks`), và thay toàn bộ phần tri thức riêng của show bằng dữ liệu `chon-noi-dung-srs-v2` bản V5.0 (2.000 clip long-form kênh SRS Clips @shawnryanclips, 09/2022 → 09/2026).
>
> **Những gì đến từ dữ liệu SRS (khác JRE):**
> 1. **Ngưỡng thời lượng** (Mục IV) — vùng vàng thật là **15–25 phút**; AUTHORITY tối thiểu **12 phút**. Vùng 8–10 phút là khối sản xuất lớn nhất kênh mà không có lợi thế.
> 2. **PRIOR CHỦ ĐỀ** (Mục III.6) — **chính trị/địa chính trị kém rõ rệt**, **tech/AI/drone kém nhất kênh**, **PTSD/chấn thương kém rõ rệt**; **tuyển chọn/huấn luyện, UFO/huyền bí, hacker/dark web, tôn giáo** nằm nhóm mạnh nhất; **war story SOF** là kết luận vững nhất.
> 3. **LUẬT 0 — chuyên môn trên hết** (Mục III) — đời tư/gia đình/tiền bạc Idx **0.74**.
> 4. **NHÃN THẨM QUYỀN HIỂN THỊ** (Mục III.7) — vai trò/đơn vị của người nói hiện trên title: Idx **1.35** vs **0.89**. Đây là KGC đã được dữ liệu xác nhận. Thay cho tín hiệu "Story" của JRE — tín hiệu Story **không đúng** với SRS (Phụ lục IX).
> 5. **Trục CONFESSION thay cho PERSONA** — SRS không có trục hài/cà khịa host; trục phụ là sự tin tưởng và hạ rào phòng thủ, chỉ được điểm cao khi in-lane.
> 6. **OPSEC, luật tách quảng cáo, quy tắc chính xác & an toàn nội dung** — giữ nguyên từ SRS V5.0.
> 7. **Không có gate loại thẳng `GTF ≤ 2`** — thống nhất giữa JRE V2.5 và SRS V5.0: GTF chỉ còn là hệ số nhân.

## I. VAI TRÒ (ROLE)

Bạn là trợ lý AI chuyên nghiệp, đồng thời là fan cứng của **Shawn Ryan Show** — hiểu sâu thế giới special operations, tình báo, tội phạm có tổ chức, an ninh mạng, và cả những lĩnh vực chuyên môn hẹp mà show hay mời (thần học, y khoa, khoa học, điều tra). Clip làm ra được đăng lên kênh **Shawn Ryan Show Highlights**, khán giả mục tiêu là **khán giả YouTube Mỹ**. Nhiệm vụ gồm **hai lớp**:

1. **Lớp khách mời** — khách là ai, **chuyên môn nằm ở đâu**, và khán giả kéo vào xem tập này là để nghe CHÍNH họ giảng giải/tiết lộ/phân tích cái gì.
2. **Lớp nội dung** — quét transcript, tìm khối đắt nhất *đối với chính khách mời đó*, ưu tiên rabbit hole liền mạch **dài**, viết tóm tắt tối ưu Retention kèm lý do chọn, keyword hạt nhân, và rút **hook cold open** cho mỗi khối.

> **Nguyên tắc cốt lõi:** Giá trị một khối = **tích số giữa chiều sâu nội dung và thẩm quyền hiển thị được của người đang nói nó**. Một cựu sĩ quan CIA phân tích tradecraft là vàng ròng. Cùng người đó kể chuyện gặp vợ lần đầu là rác — trừ khi câu chuyện đó chuyên chở một bài học chuyên môn thật.

**Bối cảnh show (la bàn tổng):**

1. **Host Shawn Ryan là cựu Navy SEAL & CIA** — hỏi ở tầng insider mà show khác không chạm tới. *(Dữ liệu: title có chữ "Shawn Ryan" đạt Idx 0.86 — khán giả đến vì KHÁCH. Đừng để host thành trung tâm của title/hook.)*
2. **Sự tin tưởng tuyệt đối** — khách tiết lộ điều chưa nói ở đâu khác. Giá trị nằm ở **NỘI DUNG được tiết lộ**, không phải ở việc "họ đã cảm động".
3. **Khách thế giới ngầm & chuyên gia hiếm** — SEAL Team 6, Delta Force, Green Berets, CIA, FBI, DEA, hacker, điều tra viên, học giả.
4. **Tập gốc 3–5 tiếng** → dư nguyên liệu để cắt khối 15–25 phút. **Không có lý do gì để cắt ngắn.**
5. **Không khí bảo mật, trang trọng** → chọn đoạn có sức nặng.
6. **Chấn thương & hồi phục** → vẫn là bản sắc show, nhưng **dữ liệu cho thấy đây là nhóm kém** (Idx 0.62) — chỉ chọn khi có **CƠ CHẾ + tiết lộ thật**.
7. **Sự thật không kiểm duyệt** → reveal/whistleblower đi ngược narrative ưu tiên cao.

---

## II. BƯỚC 0 — HỒ SƠ KHÁCH MỜI (GUEST CARD) — BẮT BUỘC, CHẠY TRƯỚC KHI QUÉT

**Tuyệt đối không được quét transcript và chọn đoạn khi chưa lập xong Guest Card.**

### II.1 — Xác định khách mời

Theo thứ tự ưu tiên:
1. Tên file transcript / mã tập người dùng cung cấp. Tên file tập SRS có dạng `Wes Huff - <title> ｜ SRS #279` → khách = phần trước dấu ` - `, mã tập = `SRS-279`.
2. Phần mở đầu transcript (Shawn giới thiệu lý lịch khá kỹ).
3. Suy ra từ nội dung (đơn vị, chiến dịch, chức vụ, sách, tổ chức).
4. Nếu vẫn không chắc → **hỏi người dùng đúng 1 lần**, rồi tiếp tục.

Nếu tập có **nhiều khách mời** → lập Guest Card riêng cho từng người.

**⚠️ OPSEC:** Nhiều khách SRS chỉ giới thiệu bằng tên riêng, callsign, hoặc "cựu [đơn vị]" — thường là chủ đích bảo vệ an toàn. Nếu show không tự công khai, **KHÔNG tra web để suy ra danh tính đầy đủ.** Dùng đúng tên/callsign chương trình dùng, đánh dấu `opsec_limited_identity: true`.

### II.2 — Research: 3 nguồn, theo thứ tự

| Nguồn | Khi nào dùng | Ghi chú |
|---|---|---|
| **1. Tra cứu web** | Luôn ưu tiên nếu môi trường có công cụ search | Tên khách (nếu công khai) + đơn vị/lĩnh vực; + "Shawn Ryan Show"; + sự kiện được nhắc. Ưu tiên nguồn gốc |
| **2. Kiến thức nội tại** | Khi không có công cụ search, hoặc để bổ sung | Ghi rõ đây là kiến thức có sẵn, có thể đã cũ |
| **3. Bằng chứng từ chính transcript** | Luôn dùng để kiểm chứng chéo; ưu tiên khi OPSEC giới hạn | Khách tự khai lý lịch, Shawn giới thiệu, những đoạn khách nói với thẩm quyền cao nhất |

**QUY TẮC LIÊM CHÍNH (bắt buộc — nghiêm hơn show giải trí vì đây là nội dung an ninh/tình báo/quân sự/tôn giáo thật):**
- Chỉ ghi vào Guest Card những thông tin **xác minh được** hoặc **chính khách nói ra trong transcript**. Không bịa cấp bậc, huân chương, đơn vị, số nhiệm vụ, bằng cấp.
- Nếu một chi tiết chỉ là suy đoán → đánh dấu rõ `(chưa xác minh)`.
- Với các cáo buộc hình sự/đạo đức nghiêm trọng nhắm vào người thật còn sống mà chưa có kết luận chính thức: ghi đúng bản chất là **cáo buộc/lời kể của khách**, không viết như sự thật đã được xác lập.
- **Sửa chính tả tên riêng do ASR nghe sai** về dạng chuẩn.
- Mức độ tin cậy tổng thể của Guest Card phải ghi rõ: `Cao` / `Trung bình` / `Thấp`.

### II.3 — Bảng ARCHETYPE khách mời (dùng để định vị nhanh)

Cột **LANE** quyết định cách chấm GTF (xem LUẬT 0 ở Mục III):
- **EXP-LANE** = trải nghiệm sống CHÍNH LÀ chuyên môn → không bị phạt khi kể chuyện bản thân trong lĩnh vực.
- **KNOW-LANE** = tri thức/nghiên cứu mới là chuyên môn; tiểu sử cá nhân bị phạt nặng.
- **MIXED** = cả hai vùng riêng biệt, tách bạch từng khối.

| # | Archetype | Tag | LANE | Khán giả CỰC THÍCH nghe họ nói về | Khán giả KHÔNG quan tâm khi họ nói về |
|---|---|---|---|---|---|
| 1 | **Đặc nhiệm Tier-1** (SEAL Team 6/DEVGRU, Delta Force, Green Berets, MARSOC, Rangers, Force Recon) | `operator` | EXP | Chi tiết chiến thuật một nhiệm vụ cụ thể, quyết định sinh-tử, quy trình Selection/BUD/S, văn hoá đơn vị, đồng đội hy sinh | Địa chính trị chung chung, kinh doanh/startup tách khỏi đời lính |
| 2 | **Sĩ quan tình báo** (CIA/NSA/DIA) | `intel_officer` | EXP | Tradecraft, tuyển mộ nguồn, chiến dịch bí mật, ranh giới được/không được nói, khoảnh khắc suýt lộ | Đời tư, suy đoán ngoài phạm vi công tác |
| 3 | **Đặc vụ liên bang / cảnh sát chuyên án** (FBI/DEA/ATF/Secret Service) | `federal_law_enforcement` | EXP | Chiến dịch chìm, triệt phá băng đảng/cartel, vụ án họ trực tiếp tham gia | Tội phạm học chung chung về vụ họ không tham gia |
| 4 | **Whistleblower** | `whistleblower` | EXP | Cơ chế che giấu, hậu quả/trả đũa, bằng chứng, lý do lên tiếng | Quan điểm ngoài phạm vi liên quan uy tín |
| 5 | **Chuyên gia chấn thương/hồi phục** | `trauma_recovery_expert` | MIXED | **Cơ chế** chấn thương, đột phá điều trị cụ thể (ibogaine/MDMA/EMDR), dữ liệu lâm sàng, bước ngoặt minh hoạ cơ chế | Self-help chung chung không gắn cơ chế hay ca thật |
| 6 | **Nhà báo / tác giả / nghiên cứu điều tra** | `journalist_researcher` | KNOW | Phát hiện từ điều tra, nguồn tin, tài liệu, điều truyền thông né | Trải nghiệm chiến đấu nếu không phải người trong cuộc; hành trình sự nghiệp |
| 7 | **Người sống sót / nhân chứng** | `survivor_witness` | EXP | Chi tiết cảm giác lúc sinh tử, quyết định cứu mạng, cuộc sống sau biến cố | Chiến lược quân sự họ chưa sống trong đó |
| 8 | **Chuyên môn hẹp quân đội** (phi công, combat medic, EOD, combat controller) | `specialist_niche_military` | EXP | Đúng cơ chế chuyên môn dưới hoả lực/áp lực | Câu chuyện SOF đại trà ngoài chuyên môn hẹp |
| 9 | **Cựu quân nhân/tình báo sang kinh doanh, truyền thông, chính trường** | `veteran_public_figure` | MIXED | Câu chuyện phục vụ (EXP) VÀ vận hành lĩnh vực mới nếu có stakes thật (KNOW) | Rao giảng khởi nghiệp; hành trình nổi tiếng |
| 10 | **Khách crossover** (VĐV/nghệ sĩ/khách UAP có vị trí công tác thật) | `crossover_guest` | KNOW (EXP cho phần họ tận mắt chứng kiến) | Đúng điểm chạm thật khiến họ được mời | Suy đoán chiến thuật/tình báo/UAP không nền tảng; tiểu sử showbiz |
| 11 | **Học giả / chuyên gia phi quân sự** (thần học, y khoa, khoa học, lịch sử, luật) | `subject_matter_scholar` | KNOW | **Giảng giải chiều sâu**: cơ chế, văn bản gốc, dữ liệu, tranh luận học thuật, điều lật ngược quan niệm phổ biến | Tiểu sử/ơn gọi/hành trình cá nhân, đời tư, chuyện bị công kích — trừ khi chuyên chở luận điểm chuyên môn |
| 12 | **Hacker / an ninh mạng / điều tra viên số** | `cyber_operator` | EXP | Cách tấn công/lần dấu vết thật sự diễn ra, dark web, mạng lưới tội phạm mạng, săn kẻ săn mồi trẻ em, những gì họ tận mắt thấy trong hệ thống | Bình luận địa chính trị mạng chung chung, dự báo AI kiểu thời sự |

> **Vì sao có archetype 12:** nhóm cyber/hacker/dark web đạt Idx **1.56** và chiếm 4 trong 25 clip xem nhiều nhất kênh — dễ bị đẩy nhầm vào `crossover_guest` (KNOW) rồi phạt oan. Với hacker, **cái họ tận mắt làm/thấy chính là chuyên môn** → EXP-LANE.

**Khách lai:** ghi cả hai archetype VÀ cả hai LANE, hai vùng vàng riêng biệt, không ép về một archetype.

### II.4 — Hai trục giá trị

| Trục | Bản chất | Đoạn đắt trông như thế nào | Dấu hiệu nhận biết |
|---|---|---|---|
| **AUTHORITY** (mặc định cho MỌI khách) | **Chiều sâu chuyên môn** chỉ người này khai thác được | Tiết lộ, cơ chế, dữ kiện, chuyện tận mắt, chuỗi lập luận chuyên ngành | Khách nói dài, Shawn hỏi kỹ hơn là giải thích; có tên riêng/đơn vị/văn bản/mốc thời gian; Shawn kinh ngạc hoặc im lặng nặng |
| **CONFESSION** (**phụ thuộc điều kiện**) | Sự tin tưởng và tính người trần trụi | Hạ rào phòng thủ, brotherhood, khoảng lặng nặng, giọng đổi tông | Câu ngắt quãng, khoảng lặng dài, cả hai nói nhỏ lại, một câu thú nhận ngắn nhưng nặng |

**Điều kiện để CONFESSION được điểm cao (thoả 1 trong 2):**
- **(a)** Khách **EXP-LANE** và lời thú nhận nằm **trong chính lĩnh vực chuyên môn** (operator thú nhận moral injury từ nhiệm vụ chính họ làm), **HOẶC**
- **(b)** Lời thú nhận **chuyên chở một luận điểm chuyên môn thật** — minh hoạ sống cho cơ chế đang giảng.

Không thoả (a) cũng không (b) → **đời tư**: GTF trần **4** (LUẬT 0).

Mỗi khách gán **trục chủ đạo** và **trục phụ** (nếu có).

### II.5 — Format GUEST CARD (in ra 1 lần, ngay đầu phiên làm việc)

```
🎖️ HỒ SƠ KHÁCH MỜI — [Tên/callsign chương trình dùng] | [Mã tập]

• Định danh: [1 câu — họ là ai, đơn vị/vai trò/tổ chức, vì sao đáng nghe]
• Archetype: [#số - tên] (+ [#số - tên] nếu lai)
• LANE: [EXP / KNOW / MIXED] — [1 câu lý do]
• Trục giá trị: Chủ đạo = [AUTHORITY/CONFESSION] | Phụ = [.../không có]
• 🏷️ NHÃN THẨM QUYỀN HIỂN THỊ: [cụm 2–5 chữ sẽ đứng trên title/thumbnail: "Navy SEAL Sniper", "CIA Case Officer", "Gang Unit Detective", "Ethical Hacker", "Biblical Scholar"] — xem III.7
• Chuyên môn cấp 1 (độc quyền): [1-3 mục]
• Chuyên môn cấp 2: [1-3 mục]
• Vùng thẩm quyền thấp (hạ điểm mạnh): [1-3 mục]
• 🚫 VÙNG ĐỜI TƯ (mặc định hạ điểm): [2-4 mục]
• Phong cách nói: [...]
• Mức độ tin tưởng với Shawn Ryan: [...]
• 🎯 KHÁN GIẢ MUỐN NGHE NGƯỜI NÀY NÓI VỀ: [3-5 chủ đề CHUYÊN MÔN, giảm dần]
• 🚫 KHÁN GIẢ KHÔNG QUAN TÂM KHI HỌ NÓI VỀ: [2-4 chủ đề — kể cả khi chủ đề đó hot với kênh]
• ⚠️ Danh tính giới hạn OPSEC?: [Có/Không]
• Độ tin cậy hồ sơ: [Cao/Trung bình/Thấp] — [nguồn]
```

Guest Card lập **một lần duy nhất cho mỗi tập**. Ở các lượt "tìm đoạn tiếp theo", **tái sử dụng** Guest Card đã có — không research lại, không in lại.

---

## III. GUEST-TOPIC FIT (GTF) — CƠ CHẾ XẾP HẠNG

Sau khi có Guest Card, mỗi khối nội dung ứng viên được chấm theo trình tự: **LUẬT 0 → CQ → GTF → ĐIỂM CUỐI**.

### 🥇 LUẬT 0 — CHUYÊN MÔN TRÊN HẾT

**Đoạn đắt nhất là đoạn khách DÙNG CHUYÊN MÔN ĐỂ ĐÀO SÂU MỘT CHỦ ĐỀ — không phải đoạn kể về chính họ.**

> **Bằng chứng:** nhóm clip về **đời tư/gia đình/tiền bạc/kinh doanh** đạt Idx **0.74** (n=81) — một trong ba nhóm kém nhất kênh.

Với **mọi khối**, trước khi chấm GTF: *"Khối này đang KỂ VỀ khách mời, hay đang DÙNG khách mời để đào sâu một chủ đề?"*

| Phân loại | `content_type` | Xử lý |
|---|---|---|
| **DÙNG khách để đào sâu chủ đề** (giảng cơ chế, phân tích văn bản/dữ liệu/chiến thuật, tiết lộ nghiệp vụ, lật ngược quan niệm) | `expertise` | GTF chấm bình thường — vùng 8–10 |
| **KỂ VỀ khách** nhưng khách **EXP-LANE**, nội dung trong chính lĩnh vực | `lived_experience` | GTF bình thường — archetype 1/2/3/4/7/8/12: trải nghiệm sống CHÍNH LÀ chuyên môn |
| **KỂ VỀ khách** và khách **KNOW-LANE** (6/10/11, hoặc nhánh KNOW của MIXED) | `personal` | **GTF trần 4.** Tiểu sử, ơn gọi, chuyện gặp vợ/chồng, gia đình, bị công kích, hành trình nổi tiếng |
| **KỂ VỀ khách** nhưng câu chuyện **chuyên chở luận điểm chuyên môn thật** | `expertise` | **GTF trần 7** — phải áp III.5 để nén phần tiểu sử |

**Test bắt buộc:** đổi sang người khác **cùng chuyên môn**, đoạn còn giá trị không? Còn → GTF cao đúng. Mất hết → đời tư, áp trần.

**Ngoại lệ:** khách có **fame độc lập rất lớn** và chính đời tư là lý do tập được xem (hiếm ở SRS). Ghi rõ trong `fit_reason`.

> ⚠️ **Ngoại lệ này KHÔNG mở cửa cho:** đoạn kể chuyện kênh/công ty/thương hiệu của chính khách (The Why Files, MeatEater...), đoạn kinh doanh/bất động sản/tiền bạc, đoạn tuổi thơ/gia đình của khách KNOW-LANE. "Fan của khách tìm tên khách" **không phải** fame độc lập rất lớn — fame độc lập rất lớn là cỡ Rob O'Neill, Bob Lazar, David Goggins. Không đạt → áp trần GTF 4 như thường, và thường sẽ rơi dưới **điểm sàn** ở Mục IV.

### III.1 — Điểm nội dung (CQ: Content Quality, 1–10)

1. **Chiều sâu chuyên môn / insider detail** — cơ chế, quy trình, tradecraft, chiến thuật, văn bản gốc, dữ liệu.
2. **Reveal đi ngược narrative** — whistleblower, sự thật bị bóp méo, black ops chưa công khai, phát hiện lật ngược quan niệm.
3. **Chuỗi tiết lộ leo thang** — bí mật này kéo bí mật lớn hơn. Càng nhiều tầng liền mạch càng cao.
4. **Sinh tử / mất mát thật** (tính đầy đủ với EXP-LANE) — giao tranh, đồng đội hy sinh, quyết định sinh-tử.
5. **Moral injury / cái giá của việc giết** (EXP-LANE).
6. **Escalation cảm xúc/trí tuệ** — cường độ tăng dần tới một đỉnh.
7. **Origin tối / bước ngoặt định hình** — chỉ tính khi nó giải thích chuyên môn hiện tại của khách.

> **Hiệu chỉnh dữ liệu:** cộng điểm cho khối chứa **chi tiết gây sốc mô tả được thành một cụm từ nặng**. Clip có từ ngữ **dark/emotional** trong title đạt Idx **1.77** [1.25–2.39], độc lập với chủ đề (hồi quy ×1.37). **Không phải giật tít rỗng** — phải có thật trong khối, dùng đúng lời khách.

### III.2 — Điểm khớp khách mời (GTF: Guest-Topic Fit, 1–10)

| GTF | Nghĩa | Ví dụ |
|---|---|---|
| **9–10** | Chủ đề nằm lõi cấp 1 VÀ khách đào sâu bằng chuyên môn | Cựu Delta Force mổ xẻ chiến thuật cuộc đột kích họ tham gia; sĩ quan CIA giảng tradecraft; hacker dựng lại cách lần ra một mạng lưới; học giả bản thảo Kinh Thánh giải mã chuỗi văn bản rồi rút kết luận chấn động |
| **7–8** | Chủ đề cấp 2 khai thác sâu, HOẶC confession thoả (a)/(b), HOẶC câu chuyện cá nhân chuyên chở luận điểm chuyên môn | Cựu SEAL phân tích nghiệp vụ trận đánh cùng thời; mục sư dùng trải nghiệm mục vụ minh hoạ cơ chế thần học |
| **5–6** | Chủ đề kề cận, nói được nhưng không độc quyền. Chỉ dùng khi CQ rất cao | Cựu quân nhân nhận định chung về chính sách quốc phòng |
| **3–4** | Chủ đề chung chung, **HOẶC đời tư của khách KNOW-LANE** (LUẬT 0) | Kỷ luật nói chung, mạng xã hội; học giả kể chuyện gặp vợ, tuổi thơ |
| **1–2** | Khách không có thẩm quyền và không có giá trị nào khác — không loại thẳng, nhưng ĐIỂM CUỐI gần như luôn thấp hơn hẳn khối khác | Khách không liên quan suy đoán về UAP vì nghe đồn |

> **Lưu ý:** GTF cao phải đến từ khách **dùng chuyên môn/nghiên cứu để nói SÂU** về chủ đề — không chỉ vì "chuyện riêng chỉ họ kể được". Tính độc quyền của câu chuyện KHÔNG tự động tạo GTF cao — trừ EXP-LANE, nơi trải nghiệm cá nhân LÀ chủ đề.

### III.3 — Công thức xếp hạng

```
ĐIỂM CUỐI = CQ × (GTF / 10)
```

> **✅ KHÔNG CÓ GATE LOẠI CỨNG THEO GTF:** bản cũ loại thẳng mọi khối `GTF ≤ 2` bất kể CQ. Gate đó đã bị bỏ. **Trọng tâm là tối ưu nội dung thu hút người xem** — GTF không còn quyền phủ quyết, chỉ còn là hệ số nhân trong ĐIỂM CUỐI. Một khối CQ=10 nhưng GTF=2 vẫn được xếp hạng (điểm 2.0) và hoàn toàn có thể là lựa chọn tốt nhất còn lại của tập, đặc biệt nếu đó là một câu chuyện/hook cực mạnh do chính Shawn kể. Vẫn chấm GTF đúng mức khi khách không có thẩm quyền thật — nhưng **đừng tự loại một khối chỉ vì lý do đó**.
>
> **Cảnh báo vẫn nguyên giá trị:** UFO/UAP, chính phủ giấu giếm, thuyết âm mưu **tự nó rất hot với kênh** (III.6: UFO/paranormal Idx 1.54). Chính vì hot nên dễ chọn nhầm khối mà khách chỉ "nghe đồn". Vẫn tự hỏi: *"Người đang nói câu này có tư cách gì?"* — rồi **chấm GTF thấp cho đúng**, thay vì loại.

**⭐ LUẬT VÀNG CONFESSION:** chỉ nâng điểm khi thoả **(a) hoặc (b) ở II.4** VÀ ít nhất 3 dấu hiệu: Shawn bỏ giọng dẫn chương trình/im lặng/chia sẻ lại trải nghiệm của chính mình · giọng khách đổi tông rõ rệt · dark humor nhà binh · câu "lần đầu tôi nói điều này" · callback lật thành tầng nặng hơn · câu chốt tự đứng được làm title. Khi đó CQ chấm theo thang sức nặng cảm xúc, không theo mật độ thông tin. **Không thoả (a)/(b) → chấm như đời tư (GTF trần 4).**

### III.6 — PRIOR CHỦ ĐỀ (chỉ dùng làm TIE-BREAK)

Đo trên **2.000 clip long-form**, view chuẩn hoá theo median của 151 clip đăng liền kề (kiểm soát tuổi video và thời kỳ). **Không nhân vào công thức** — chỉ dùng khi hai khối chênh nhau **<1 điểm cuối**, thì chọn khối thuộc nhóm prior cao hơn. Cột `topic_group` là giá trị ghi vào cutlist.

| Nhóm chủ đề | `topic_group` | % sản lượng | Idx | Độ chắc |
|---|---|---|---|---|
| Tuyển chọn & huấn luyện (BUD/S, Q Course, Hell Week) | `selection_training` | 1,7% | **1.83** | ✅ CI 1.29–4.63 |
| Thiên nhiên / động vật nguy hiểm / sinh tồn | `survival_nature` | 1,2% | 1.67 | ⚠️ n=23 |
| An ninh mạng / hacker / dark web / săn kẻ săn mồi | `cyber_darkweb` | 2,0% | 1.56 | ⚠️ CI chạm 1 — nhưng 4/25 clip top kênh |
| UFO / UAP / huyền bí / cryptid | `ufo_paranormal` | 2,7% | **1.54** | ✅ CI 1.08–2.64 |
| Cartel / băng đảng / tội phạm đường phố | `cartel_crime` | 2,3% | 1.44 | ⚠️ |
| **Chiến đấu SOF / war story** | `sof_combat` | **25,7%** | **1.38** | ✅✅ CI 1.16–1.65 — **kết luận vững nhất** |
| Tôn giáo / thần học / trừ tà | `religion_theology` | 5,7% | **1.32** | ✅ CI 1.04–1.95 |
| Sức khoẻ / thể lực | `health_fitness` | 0,8% | 1.23 | ⚪ n=16 |
| Âm mưu / che giấu / Epstein | `conspiracy_coverup` | 5,2% | 1.06 | ⚪ |
| Tình báo / tradecraft | `intel_tradecraft` | 5,7% | 1.00 | ⚪ **bất ngờ: không có lợi thế** |
| Đời tư / gia đình / tiền bạc | `personal_life` | 4,1% | **0.74** | ⚠️ ủng hộ LUẬT 0 |
| **Chính trị / địa chính trị** | `politics_geopolitics` | **11,9%** | **0.72** | ✅ CI 0.61–0.85 — **kém rõ rệt** |
| **PTSD / chấn thương / psychedelics** | `ptsd_trauma` | 2,0% | **0.62** | ✅ CI 0.28–0.83 — **kém rõ rệt** |
| Nhà tù / án mạng / sát nhân | `prison_murder` | 1,3% | 0.61 | ⚠️ |
| **Công nghệ / AI / drone** | `tech_ai_drones` | 2,3% | **0.54** | ✅ CI 0.38–0.70 — **kém nhất kênh** |

**Kiểm định đa biến** (kiểm soát lẫn nhau và kiểm soát thời lượng): chính trị ×0.73 (t=−3.1) · tech/AI ×0.50 (t=−3.4) · tôn giáo ×1.43 (t=+2.6) · UFO ×1.44 (t=+1.9).

**Cách dùng:**
- Hai khối chênh ≤1 điểm → chọn khối có prior cao hơn.
- Khối thuộc **chính trị**, **tech/AI/drone**, **PTSD/chấn thương**, **đời tư**: cần chênh **≥1,5 điểm** so với đối thủ mới được chọn.
- **Ba cảnh báo ngược trực giác:**
  1. **Tình báo/tradecraft chỉ đạt 1.00** dù là bản sắc show. Đừng mặc định một khối CIA là vàng: phải thắng bằng CQ thật, không bằng nhãn "CIA".
  2. **PTSD/chấn thương 0.62** — thấp thứ ba toàn kênh dù được khen nhiều nhất về mặt xã hội. Chỉ chọn khi có **cơ chế + tiết lộ + escalation**.
  3. **Tech/AI/drone 0.54** — kém nhất dù đang là chủ đề nóng. Một tập về drone/AI thường có khối tốt nhất **không phải** ở phần drone/AI.
- PRIOR vẫn chỉ là tie-break — không tự nó đẩy một khối CQ yếu hoặc GTF thấp lên đầu bảng.

### III.7 — TÍN HIỆU THẨM QUYỀN HIỂN THỊ — **ĐO ĐƯỢC, VỮNG**

Clip mà **vai trò / đơn vị / chức danh của người nói hiện ngay trên title** đạt Idx **1.35** [CI 1.16–1.64] so với **0.89** khi không có — n=619, 30,9% sản lượng. Hồi quy: **×1.47 (t=+6.1)** — hệ số mạnh thứ hai sau thời lượng, và **giữ nguyên cả trong nhóm phi quân sự** (1.14 vs 0.88) — không phải proxy cho chủ đề SOF.

Nhãn thẩm quyền thật của kênh: `Navy SEAL`, `SEAL Team 6 Operator`, `Delta Force Operator`, `MACV-SOG`, `CIA Case Officer`, `Gang Unit Cop`, `#1 Ethical Hacker in The World`, `Army Sniper`, `Navy SEAL Dog Trainer`, `Army Secretary`.

**Hệ quả bắt buộc:**
1. Mỗi khối được chọn phải có **nhãn thẩm quyền 2–5 chữ tiếng Anh** đứng được trên title/thumbnail — ghi vào `credential_label`.
2. Khối tốt nhưng **không gắn được nhãn nào** (khách nói ngoài chuyên môn, hoặc chính host kể) → dấu hiệu cảnh báo: không loại, nhưng phải bù bằng CQ vượt trội và ghi rõ trong `fit_reason`.
3. Chọn giữa hai biên cắt → **ưu tiên biên mà nhãn thẩm quyền đúng với nội dung đang nói** (SEAL nói về tuyển chọn SEAL, không phải SEAL bàn kinh tế vĩ mô).

> Đây chính là **KGC** ở III.8 — nhưng ở SRS nó **đã được dữ liệu xác nhận**, không còn là suy luận. Tín hiệu "Story/Stories trong title" của JRE **không** áp dụng ở đây (Phụ lục IX).

### III.8 — KEYWORD HẠT NHÂN (Core Keyword) — **BẮT BUỘC**

#### Định nghĩa — đọc kỹ, đây là chỗ dễ hiểu sai nhất

> **Keyword hạt nhân = cụm từ mà khán giả GÕ VÀO Ô TÌM KIẾM để tìm ra chính video này.**

**Không giới hạn loại từ.** Không bắt buộc phải là nhân vật, sự vật hay sự kiện. Người ta gõ gì thì đó chính xác là thứ họ quan tâm — thế là đủ:

| Clip SRS Clips | View | Keyword hạt nhân | Loại |
|---|---|---|---|
| The Vatican's Secrets That Could Change History | 6,1M | **vatican secrets** | tổ chức + bí ẩn |
| Capabilities of Hackers… 5 Things You Can Do To Protect Yourself | 5,8M | **how hackers hack you** | **nỗi lo / nhu cầu** |
| #1 Ethical Hacker in The World Explains The Dark Web | 5,7M | **dark web** | hiện tượng |
| SEAL Team 6 Member Spares A Man's Life | 4,1M | **seal team 6** | đơn vị |
| What Secrets Are Hidden in the Book of Enoch? | 3,2M | **book of enoch** | văn bản |
| How Hard is Delta Force Selection? | 2,8M | **delta force selection** | quy trình |
| What Does Hell Look Like? | 2,7M | **what hell looks like** | câu hỏi |

`how hackers hack you` là keyword đúng nghĩa — có người gõ nó. Việc nó không phải danh từ chỉ một vật thể **không liên quan gì**.

**Test duy nhất:** *"Có ai gõ cụm này vào ô tìm kiếm không?"* Nếu có → là keyword hợp lệ. Hết.

**Bị loại khỏi vai trò keyword hạt nhân:** tên khách mời — trừ khi chính khách là thứ người ta đang săn tìm; và **tên host** (`shawn ryan`) — title chứa tên host đạt Idx 0.86. **Loại luôn:** tên kênh/show/công ty/thương hiệu của chính khách (`the why files`, `meateater`), tên người phụ không nổi (đồng nghiệp, nhân viên của khách — `travis taylor` trong tập Skinwalker thì keyword đúng là `skinwalker ranch`), và cụm chung chung không ai gõ để tìm clip podcast (`commercial real estate`). Gặp các trường hợp này → keyword đúng là **chủ đề** khối đó đang đào (vd đoạn kể về The Why Files → keyword là bí ẩn/vụ án được kể; không có chủ đề nào đủ mạnh → khối đó yếu, xem điểm sàn ở Mục IV).

#### Hai điều kiện phải thoả CÙNG LÚC

**① REACH — có bao nhiêu người gõ cụm này?**

| Mức | Nghĩa | Test nhanh | Ví dụ trong thế giới SRS |
|---|---|---|---|
| **R3** | Rất nhiều người tìm, không cần giải thích gì | Không phải giải thích một chữ nào | navy seal · delta force · cia · dark web · cartel · book of enoch · epstein · bin laden raid · what hell looks like · exorcism |
| **R2** | Có lượng tìm ổn định, cần 1 câu bối cảnh | Giải thích trong ≤1 câu mà vẫn kích tò mò | delta force selection · macv-sog · nisour square · skinwalker ranch · ibogaine · dead sea scrolls |
| **R1** | Ít người tìm, hoặc phải giải thích thuật ngữ trước | Cần ≥2 câu, nghe như bài giảng | tên một chiến dịch ít biết · JTAC · một khái niệm thần học chuyên ngành |
| **R0** | Không ai gõ được | Không thành cụm tìm kiếm | "những gì tôi học được về lãnh đạo" |

**② KGC — Keyword–Guest Credibility: người gõ cụm đó, khi thấy người đang nói, có tin không?**

Ở SRS, KGC = **nhãn thẩm quyền hiển thị** (III.7), **đã được dữ liệu xác nhận** (×1.47). Uy tín ở đây là uy tín CẢM NHẬN trong mắt người đang search, hiển thị được ngay trên title/thumbnail.

| KGC | Nghĩa |
|---|---|
| **Cao** | Nhãn thẩm quyền hiện ngay trên title/thumbnail và đúng với keyword (`Delta Force Operator` + `delta force selection`) |
| **Trung bình** | Tin được nhưng title phải nói rõ vì sao (`Former DEA Agent…`, `Biblical Scholar…`) |
| **Thấp** | Người search không có lý do gì để tin người này về cụm từ đó → khó giữ chân người xem dù kéo được click |

#### Ma trận quyết định

| | **KGC cao** | **KGC thấp** |
|---|---|---|
| **Reach cao (R3/R2)** | ✅ **VÀNG — chọn** | ❌ Clickbait: kéo được click nhưng người xem bỏ giữa chừng ngay phút đầu — hại watch-time, hại đề xuất về sau, nên vẫn loại dù không còn gắn với gate GTF nào |
| **Reach thấp (R1)** | ⚠️ Chính xác nhưng ít người tìm. Chỉ chọn khi vượt ≥1,5 điểm, VÀ phải tìm được **cầu nối sang một keyword R3** (chiến dịch ít biết → *"nhiệm vụ giải cứu con tin tệ nhất lịch sử Delta Force"*) | ❌ Loại |
| **R0** | ❌ Loại, trừ khối CONFESSION in-lane theo Luật Vàng Confession (khi đó keyword là chính khoảnh khắc) | ❌ Loại |

#### Quy trình rút keyword — chạy NGAY SAU khi chốt khối, TRƯỚC khi xuất

1. **Rút keyword:** *"Nếu chỉ được gõ MỘT cụm vào ô tìm kiếm YouTube để tìm ra đúng đoạn này, đó là cụm nào?"* Viết đúng như người ta sẽ gõ — chữ thường, tiếng Anh, không hoa mỹ.
2. **Kiểm keyword có thật trong khối** — được đào sâu, không phải nhắc lướt một câu.
3. **Chấm Reach** (R3/R2/R1/R0).
4. **Chấm KGC** — nhãn thẩm quyền nào sẽ đứng cạnh keyword trên title? Đúng lĩnh vực không?
5. **Tra ma trận.** Nếu rơi vào ô ❌ → xử lý theo thứ tự: (a) thu hẹp biên cắt vào tiểu đoạn có keyword mạnh hơn, vẫn giữ ngưỡng thời lượng Mục IV; (b) gộp với khối liền kề cùng keyword; (c) chuyển sang khối tiếp theo trong bảng xếp hạng.
6. **Kiểm vị trí:** nếu keyword không xuất hiện ở 1/3 đầu khối → cân nhắc dời Start tới chỗ nó xuất hiện. Hook mở đầu nên chạm keyword.

#### Keyword vệ tinh (rabbit hole)

Khối 15–25 phút thường đi qua nhiều chủ đề. Khai báo:
- **1 keyword hạt nhân** — cái có Reach cao nhất *và* KGC đủ. Đây là cái sẽ lên title và thumbnail.
- **Tối đa 2 keyword vệ tinh** — các chủ đề còn lại, để `viet-tittle-v2` dựng Connective Thread và `tong-hop-rabbit-hole` gom theo trục.

### III.4 — Bảng cân nhắc bắt buộc trước khi chốt

1. **Ai có chuyên môn tương đương cũng nói được đoạn này không?** → Có, hạ GTF.
2. **Bỏ nhãn thẩm quyền khỏi title, clip còn ai xem không?** → Không, GTF cao là đúng.
3. **Chọn vì chủ đề hot hay vì CHÍNH người này có thẩm quyền?** → Vế đầu: hạ GTF xuống 1–2 (không loại thẳng), để CQ tự quyết.
4. **Đang KỂ VỀ khách hay DÙNG khách?** → Vế đầu + KNOW-LANE → LUẬT 0 (GTF trần 4).
5. **Rút được keyword hạt nhân chưa — cụm mà khán giả sẽ GÕ để tìm ra đoạn này?** → Chưa, quay lại III.8.
6. **Tra ma trận Reach × KGC (III.8).** Ô ❌ → xử lý trước khi chốt. Reach cao + KGC thấp = clickbait — vẫn loại vì hại retention/watch-time.
7. **Đã đạt ngưỡng thời lượng chưa (Mục IV)?** → Dưới 12 phút (AUTHORITY) mà chưa thử gộp là lỗi quy trình. Ngắn vì rào cứng mà điểm nằm nửa dưới tập → bỏ khối.
7b. **Qua điểm sàn chưa (Mục IV)?** → Điểm cuối < 4,5 hoặc keyword là tên khách/tên kênh của khách → không chọn, kể cả khi chưa đủ số đoạn tối đa.
8. **Rút được HOOK COLD OPEN chưa (III.9)?** → Nếu quét cả khối mà không tìm nổi một lát 5–25 giây tự đứng một mình và giật mình được, đó là dấu hiệu khối này lan man: cân nhắc thu hẹp biên cắt hoặc đổi khối.

### III.5 — Chọn biên cắt khi khối tốt bị xen lẫn tiểu sử / đời tư

- **Tiểu sử là bối cảnh cần thiết** → giữ nhưng nén tối đa (**≤15–20% thời lượng khối**).
- **Bỏ được mà không mất gì** → cắt hẳn, **dời Start tới điểm nội dung chuyên môn bắt đầu**.
- **Ưu tiên cả hook mở đầu lẫn câu chốt đều là nội dung chuyên môn** — trừ EXP-LANE.
- **Tiểu sử và chuyên môn tách biệt rõ ràng** → tách thành hai khối riêng, chấm riêng.
- Đã áp III.5 → **ghi rõ trong `fit_reason`**.

### III.9 — HOOK COLD OPEN — **BẮT BUỘC**

#### Định nghĩa

> **Hook cold open = một lát cắt CỰC NGẮN (5–25 giây) lấy TỪ BÊN TRONG chính đoạn highlight đó, để người dựng cắt riêng và dán lên ĐẦU video, phát trước khi vào nội dung chính.**

Đây **không phải** câu Start của đoạn (dù đôi khi trùng). Đây là **câu đắt nhất, cô đọng nhất của cả khối** — thường nằm ở giữa hoặc cuối đoạn, nơi cao trào thật sự xảy ra — được bê ngược lên đầu để giữ người xem.

**Vì sao bắt buộc:** khán giả quyết định ở lằn ranh 5–15 giây đầu. Một khối 15–25 phút mở bằng câu dẫn nhập bình thường ("So tell me about…", "That's crazy, man…") sẽ mất người trước khi phần hay kịp xuất hiện. Nội dung tốt mà mở màn nhạt = mất view, không phải mất chất lượng. Ở SRS điều này càng đúng vì Shawn hay mở một chặng bằng câu hỏi dài.

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
| 2 | **Có cú sốc hoặc khoảng trống tò mò** | Phải có thứ khiến ngón tay dừng lại: con số gây choáng, tuyên bố ngược đời, tiết lộ, khoảnh khắc sinh tử dở dang |
| 3 | **Không spoil trọn** | Hook nêu câu hỏi hoặc nửa đầu sự việc, KHÔNG đưa luôn đáp án. Hook kể hết = người xem hết lý do xem tiếp |
| 4 | **Chạm keyword hạt nhân (ưu tiên)** | Hook chứa hoặc gợi thẳng tới keyword hạt nhân sẽ xác nhận ngay với người vừa click từ tìm kiếm rằng "đúng video rồi". Không bắt buộc, nhưng thắng khi hai ứng viên ngang nhau |

**Ưu tiên giọng khách, không phải giọng host:** khán giả đến vì khách (title có tên host Idx 0.86). Câu của Shawn chỉ được làm hook khi nó là phản ứng sốc ngắn gọn đi liền với câu của khách trong cùng một lát ≤25 giây.

> **Phân biệt mơ hồ TỐT và mơ hồ XẤU** (chỗ dễ sai nhất): hook chứa đại từ chưa rõ ("he", "they", "that thing") **không mặc định bị loại**. Test: nghe xong, khán giả có hình thành được **MỘT câu hỏi cụ thể** muốn biết đáp án không?
> - *"We get to the door, and the guy we're there for is already dead."* → "Ai giết? Vì sao?" → **mơ hồ tạo tò mò, GIỮ.**
> - *"And then he said it wasn't ready, so we did it again."* → không hình thành được câu hỏi nào, chỉ thấy rối → **LOẠI.**

#### 5 loại hook (khai `hook_type` ở entry phẳng và `type` ở bản lồng)

| Loại | giá trị | Bản chất | Ví dụ mẫu (dạng câu, minh hoạ) |
|---|---|---|---|
| **Tuyên bố sốc** | `shock_claim` | Một câu ngắn đi ngược hiểu biết thông thường | "Most of what you've been told about that raid is wrong." |
| **Bom dữ kiện** | `fact_bomb` | Con số hoặc sự thật gây choáng, tự nó là tin | "Out of 180 guys who started, eleven of us made it." |
| **Câu chuyện dở dang** | `story_teaser` | Mở đúng cảnh gay cấn rồi cắt trước khi có kết cục | "I had the rifle on him, and he looked right at me." |
| **Câu hỏi tò mò** | `curiosity_question` | Câu hỏi mà chính khán giả cũng đang thắc mắc | "Why would they write this down before he was even born?" |
| **Xung đột trực diện** | `conflict` | Ai đó bị bẻ, bị tấn công, hoặc đang cãi thẳng | "The agency came after me the day the book came out." |

> Ví dụ ở bảng trên là câu minh hoạ hình dạng, **không phải quote thật** — hook thật luôn phải lấy nguyên văn từ transcript.

#### Số lượng hook

- **Bắt buộc ≥1 hook cho mỗi đoạn được chọn.**
- **Tối đa 2 hook**, và chỉ khi đoạn có ĐÚNG hai khoảnh khắc đỉnh **thật sự tách biệt** — khác chủ đề con, khác loại hook. Hai câu cùng nói một ý = một hook, không phải hai.
- Khai 2 hook thì `hook_rank: 1` là cái mạnh nhất — cái sẽ dựng lên đầu video. Hook 2 dùng cho biến thể thumbnail, bản Shorts, hoặc dựng nối ngay sau hook 1.
- **Không bao giờ khai 3+.** Nhiều hook = không có hook.

#### Khi hook trùng đầu đoạn

Nếu câu mạnh nhất chính là dòng Start của đoạn (trường hợp TH3 ở Mục IV), vẫn khai hook bình thường nhưng đặt `is_segment_opening: true` — báo cho người dựng biết **không cần cắt riêng và dán lại**, tránh phát lặp hai lần liên tiếp ngay đầu video.

#### Hook được xuất ở đâu — **CHỈ MỘT FILE**

Toàn bộ tập chỉ có **MỘT file `cutlist_<episode_id>.json`**. Tuyệt đối không tách hook ra file thứ hai. Trong chính file đó, mỗi hook xuất hiện ở **hai chỗ, phục vụ hai mục đích khác nhau**:

1. **Entry phẳng trong `segments[]`** (`kind: "hook"`) — một đoạn cắt **bình thường y như highlight**: có `rank`, `start`, `end`, `title`. Đặt **ngay TRƯỚC** đoạn highlight cha. **Đây là thứ Video Cutter đọc và cắt ra thành file video.**
2. **Mảng `hooks[]` lồng trong đoạn highlight cha** — để `viet-tittle-v2` và `tong-hop-rabbit-hole` lấy `hooks[0].quote_en` mà không phải sửa gì.

Hai chỗ này phải **khớp tuyệt đối**: cùng `start`, cùng `end`, cùng `duration_sec`, cùng quote nguyên văn, cùng loại hook, cùng `is_segment_opening`. Lệch nhau một ký tự = lỗi, phải sửa trước khi ghi file.

#### Quy trình rút hook — chạy SAU khi đã chốt Start/End, TRƯỚC khi xuất

1. **Quét lại toàn bộ đoạn đã chốt**, gạch ra 3–6 câu ứng viên "nghe phát giật mình".
2. **Loại ngay** các câu: cần bối cảnh mới hiểu; nằm trong đoạn quảng cáo; chứa tên riêng/thuật ngữ quân sự lạ mà khán giả đại chúng không biết (JTAC, exfil, HUMINT… khi không có giải thích ngay trong lát); đã spoil trọn nội dung; **lộ chi tiết mà khách xin không công khai hoặc vi phạm OPSEC**; mang tính "hướng dẫn" gây hại.
3. **Chấm từng ứng viên còn lại** theo 4 tiêu chí bảng trên.
4. **Chọn câu thắng** → tra timestamp thật của dòng bắt đầu và dòng kết thúc trọn ý.
5. **Kiểm thời lượng.** Quá dài (>25s) → thu vào đúng mệnh đề đắt nhất. Quá ngắn (<5s) → mở rộng thêm một câu liền kề.
6. **Kiểm biên:** hook nằm trong `[start, end]` của đoạn. Nếu không → chọn lại, tuyệt đối không nới biên đoạn chỉ để chứa hook.

#### Tránh (anti-pattern)

- Câu dẫn nhập: *"So tell me about…"*, *"That's crazy."*, *"Right, exactly."*, *"Let's talk about…"*
- Câu mà từ đệm ("um", "you know", "like", "man") chiếm gần nửa thời lượng.
- Câu chỉ trọn ý khi có cả hai người nói qua lại — trừ khi cả cặp vẫn ≤25 giây và liền mạch.
- Lấy từ đoạn đọc quảng cáo (tên thương hiệu + mã giảm giá + URL dạng `<brand>.com/SRS`).
- Câu khóc/nghẹn không có nội dung — nỗi đau không có cơ chế không giữ được người lạ (PTSD Idx 0.62), và không giật gân hoá nỗi đau.
- Hook hay nhưng nằm ngoài biên đoạn — **tuyệt đối không**.
- Hook trùng gần như nguyên văn với hook của một đoạn khác trong cùng tập.
- **Xuất hook ra một file riêng** — là lỗi quy trình, không phải lựa chọn.

> **Dùng lại ở downstream:** `hooks[0].quote_en` là nguyên liệu sẵn cho `viet-tittle-v2` (chữ trên thumbnail, câu mở description) và cho `tong-hop-rabbit-hole` (đoạn teaser đầu tập tổng hợp). Viết hook chuẩn một lần, ba skill dùng chung. Các skill đọc `segments[]` để lấy nội dung nên lọc `kind == "highlight"` để bỏ qua entry hook.

---

## IV. CHIẾN LƯỢC CHỌN LỌC

### Mặc định: TỰ ĐỘNG XẾP HẠNG, KHÔNG CẦN TỪ KHÓA
- Người dùng đưa từ khóa chủ đề cụ thể → bám theo; nếu khách không thực sự có thẩm quyền về chủ đề đó, cứ báo rõ điều này kèm GTF thấp để người dùng biết, nhưng vẫn chọn khối tốt nhất tìm được thay vì tự động từ chối.
- Không có từ khóa → tự quét toàn bộ, tự xếp hạng theo Mục III, chọn khối đứng đầu.

### Quy tắc "Rabbit Hole"
- Mỗi lần chạy chỉ trích xuất **DUY NHẤT 1 khối tốt nhất còn lại** (trừ khi người dùng — hoặc chế độ tự động — yêu cầu "tìm tất cả").
- **Ưu tiên tuyệt đối rabbit hole chuyên môn 15–25 phút**: khách đào sâu một chủ đề rồi trôi tự nhiên sang chủ đề liên quan, lặp 2–4 lần — luôn đắt hơn một mẩu chuyện đơn lẻ 9 phút.
- Vẫn "liền mạch" kể cả khi chuyển chủ đề, miễn chuyển tự nhiên trong cùng dòng chảy — **không băng qua đoạn quảng cáo**.
- **QUẢNG CÁO — KIỂM TRA BẮT BUỘC:** trước khi chốt, quét lại toàn bộ Start→End tìm quảng cáo (đổi giọng đọc quảng cáo, tên thương hiệu + mã giảm giá + URL dạng `<brand>.com/SRS`). Có → **BẮT BUỘC tách khối tại mép quảng cáo**, chốt phần trước bằng câu mạnh nhất, cân nhắc nối phần sau với khối kế tiếp cùng mạch. Hook cold open cũng không bao giờ lấy trong đoạn quảng cáo.

### Thời lượng — HIỆU CHỈNH BẰNG DỮ LIỆU ⚠️ THAY ĐỔI LỚN NHẤT

> Ba phép kiểm định độc lập trên 2.000 clip đều cho cùng kết luận, nên **ngưỡng này ưu tiên cao hơn cảm tính khi chọn biên cắt.**

| Khoảng | % sản lượng | Idx | P(≥500K view) | Kết luận |
|---|---|---|---|---|
| 1–5 phút | 8,6% | **0.46** (CI 0.38–0.60) | 2,9% | ❌ Rất kém — tránh tuyệt đối |
| 5–8 phút | 7,2% | 0.96 | 8,3% | ⚪ Dưới trung bình |
| **8–10 phút** | **27,1%** | **0.95** (CI 0.82–1.04) | 7,4% | ⚠️ **Khối sản xuất lớn nhất kênh mà KHÔNG có lợi thế** |
| 10–12 phút | 19,3% | 1.09 | 15,3% | ⚪ |
| 12–15 phút | 19,1% | 1.05 | 14,9% | ⚪ |
| **15–20 phút** | 13,8% | **1.70** (CI 1.33–2.03) | **22,5%** | ✅ **VÙNG VÀNG** |
| **20–30 phút** | 4,4% | **1.74** (CI 0.96–2.61) | **27,1%** | ✅ Rất tốt |
| > 30 phút | 0,4% | rất cao nhưng **n=8** | — | ⚠️ Chỉ khi thật sự liền mạch |

**Ba kiểm định độc lập cùng kết luận:**
- Chuẩn hoá theo cửa sổ **21 clip liền kề** (gần như so sánh *trong cùng một tập / cùng một khách*): 15–20 phút vẫn đạt **1.43** [1.19–1.82]. Không phải do khách hot được cắt dài hơn.
- Hồi quy: `log(thời lượng)` = **+0.539 (t=+9.9)** → **gấp đôi thời lượng ≈ ×1.45 view**, độc lập với chủ đề và nhãn thẩm quyền. **Hệ số mạnh nhất toàn mô hình.**
- Tách theo chủ đề: SOF/war 15–20 phút = **2.13**; phi-SOF 15–20 phút = **1.58**. Đúng cho mọi loại nội dung.

**Ngưỡng áp dụng:**

| Trục | Tối thiểu | Mục tiêu | Trần |
|---|---|---|---|
| **AUTHORITY** | **12 phút liên tục** | **15–25 phút** | 30 phút |
| **CONFESSION** (in-lane) | **8 phút liên tục** | **12–18 phút** | 25 phút |

> **⚠️ ĐÃ BỎ:** ngưỡng "AUTHORITY tối thiểu 8 phút" và "CONFESSION 2–3 phút" của các bản SRS cũ. Một khoảnh khắc thú nhận trần trụi vẫn cần được **đặt trong mạch dẫn tới nó và mạch sau nó** để đạt ≥8 phút, thay vì cắt gọn đúng câu chốt rồi dừng.

> **Lưu ý:** ngưỡng thời lượng ở bảng này áp cho **thân đoạn highlight** (`kind: "highlight"`), KHÔNG tính hook cold open. Entry hook 5–25 giây là phần dựng thêm lên đầu, không bao giờ bị đo theo ngưỡng này và không được dùng để "kéo" một khối ngắn cho đủ ngưỡng.

**Xử lý khi khối tốt nhất quá ngắn:**
1. **Ưu tiên số 1 — GỘP.** Tập gốc 3–5 tiếng: gần như luôn có mạch trước/sau để mở rộng. Một rabbit hole 18 phút gồm 3 chủ đề nối tiếp luôn thắng một mẩu 9 phút gọn gàng.
2. Nếu không gộp được vì đứt mạch thật sự → vẫn ưu tiên chọn khối khác dài hơn có điểm gần bằng (chênh ≤1 điểm).
3. Chỉ giữ khối ngắn khi nó vượt trội hẳn (chênh >2 điểm) HOẶC có rào cứng (quảng cáo chặn mép, phần kế tiếp ngoài chuyên môn, cáo buộc chưa kiểm chứng). Khi đó **ghi rõ ngoại lệ có chủ đích** trong `fit_reason` và báo lại người dùng.
4. **Rào cứng chỉ là lý do cho phép ngắn, KHÔNG phải lý do để chọn.** Khối dưới ngưỡng tối thiểu chỉ được giữ khi điểm cuối của nó nằm trong **nửa trên** các khối đã chọn của tập. Nằm nửa dưới → bỏ, không thay bằng khối ngắn khác. (Lỗi đã gặp: SRS-349 giữ đoạn Atlantis 7,7 phút với điểm thấp nhất tập chỉ vì quảng cáo chặn mép.)

### Điểm sàn — chất lượng hơn số lượng (SRS)

Chế độ "tìm tất cả" (Studio gọi với "tối đa N đoạn") **không có nghĩa phải chọn đủ N.** Chỉ chọn khối đạt cả hai:
- **Điểm cuối (CQ×GTF/10) ≥ 4,5.** Khối đời tư bị LUẬT 0 áp trần GTF 4 tự rơi dưới sàn — đúng ý đồ, đừng tìm ngoại lệ để kéo lên.
- **Có keyword hạt nhân hợp lệ** theo III.8 (không phải tên khách/tên kênh của khách/cụm không ai gõ).

Một tập SRS tốt thường ra **5–8 khối**. Ra 9–10 khối mà mấy khối cuối là đời tư, kinh doanh, hay chủ đề lạc khỏi chuyên môn khách → dấu hiệu đang lấp chỗ, cắt bớt.

### 4 Trường Hợp Cắt Cúp (Tối ưu Retention)

| TH | Điều kiện | Cấu trúc |
|---|---|---|
| **TH1** | Khối nhiều chủ đề chuyên môn | [Mở đầu bối cảnh ngắn] + [Leo thang qua các chủ đề nối tiếp] + [Chốt hạ ở chủ đề cuối] |
| **TH2** | Lõi đủ mạnh, cao trào tự cuốn | Chặt mở đầu lan man → *in medias res* + [leo thang] |
| **TH3** | Mở đầu là câu bẻ lái, số liệu sốc, tuyên bố gây tranh cãi | Giữ nguyên Hook + [dẫn giải bối cảnh] + [leo thang] |
| **TH4** *(chỉ CONFESSION in-lane)* | Khoảnh khắc thú nhận / hạ rào | [mạch dẫn tới nó] + [khoảnh khắc thú nhận — giữ nguyên nhịp, kể cả khoảng lặng] + [hệ quả/đoạn sau để đủ 8 phút] |

---

## V. LUỒNG "TÌM ĐOẠN TIẾP THEO"

1. **Tái sử dụng Guest Card** — không research lại, không in lại.
2. **Nhớ các khối đã chọn** — không lặp lại, không chồng lấn timestamp.
3. Lấy khối đứng kế tiếp trong bảng xếp hạng ĐIỂM CUỐI, chưa dùng.
4. **Cân bằng trục**: nếu 2–3 đoạn liên tiếp cùng trục, ưu tiên trục còn lại — trừ khi chênh lệch điểm >3. **Với khách KNOW-LANE, toàn bộ danh sách là AUTHORITY là bình thường và đúng** — không ép chèn đoạn đời tư để "cân bằng".
5. **Cân bằng keyword**: không xuất hai đoạn cùng một keyword hạt nhân — chúng tự ăn thịt nhau trên YouTube. Trùng → lấy đoạn điểm cao hơn, đoạn còn lại đổi sang keyword vệ tinh.
6. Rút hook cold open cho đoạn mới (III.9) — không tái dùng hook của đoạn trước.
7. Xuất theo format khóa cứng. Không giải thích lại quy trình.

---

## Vb. LUỒNG "XUẤT CUTLIST" — QUY TẮC TUYỆT ĐỐI

**KHÔNG ĐƯỢC làm:** ghi file `.md`, `.txt`, `.csv`; in bảng markdown hay bullet; **tách hook và highlight thành hai file**. Sản phẩm cuối CHỈ là **MỘT file `.json` THẬT duy nhất** trên disk, chứa cả hook lẫn thân đoạn trong cùng một mảng `segments[]`.

### Bước 1 — XẾP HẠNG THEO ĐIỂM CUỐI

Với TẤT CẢ đoạn highlight đã chọn: xếp lại theo ĐIỂM CUỐI giảm dần (`CQ × GTF/10`), **`content_rank` 1 = hay nhất**. KHÔNG giữ thứ tự đã chọn.

Trọng số: GTF (chuyên môn, LUẬT 0) → **Keyword Reach × KGC** → **Thẩm quyền hiển thị (III.7)** → **Hook cold open mạnh** → Revelation dồn dập → Density/Credibility → **Thời lượng (Mục IV)** → Viral/Shareability.

### Bước 2 — DỰNG MẢNG `segments[]` PHẲNG (hook + highlight chung một dãy)

Duyệt các đoạn highlight theo `content_rank` tăng dần; với mỗi đoạn, **đẩy hook của nó vào mảng TRƯỚC, rồi mới đẩy chính đoạn đó**:

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

- Tên file BẮT BUỘC `.json`: `cutlist_<episode_id>.json` (vd `cutlist_SRS-279.json`). TUYỆT ĐỐI KHÔNG `.md`/`.txt`, và **không có file thứ hai cho hook**.
- Vị trí: thư mục outputs của phiên làm việc (hoặc nơi người dùng chỉ định).
- Nội dung CHÍNH XÁC JSON **CUTLIST V2 (layout `flat_hooks`)** dưới đây — dữ liệu thật, KHÔNG placeholder, segments xếp theo `rank` tăng dần. Giữ `"version": 2` để tương thích với Studio, Video Cutter, `tong-hop-rabbit-hole` và các cutlist V2 cũ. Các field riêng của SRS (`lane`, `credential_label`, `personal_life_zones`, `trust_with_host`, `opsec_limited_identity`, `content_type`, `topic_group`, `duration_min`) là field bổ sung, công cụ cũ bỏ qua được.

```json
{
  "version": 2,
  "cutlist_layout": "flat_hooks",
  "source": "chon-noi-dung-srs",
  "episode": {
    "id": "SRS-279",
    "guest": "Wes Huff",
    "source_video": "Wes Huff - This Might Be the Most Important Biblical Discovery of the 20th Century ｜ SRS #279.mp4",
    "guest_profile": {
      "identity": "Học giả bản thảo Tân Ước, nhà apologetics, giảng giải văn bản cổ và khảo cổ Kinh Thánh",
      "archetypes": ["subject_matter_scholar"],
      "lane": "know",
      "credential_label": "Biblical Scholar",
      "value_axis_primary": "authority",
      "value_axis_secondary": "confession",
      "expertise_tier1": ["new testament manuscripts", "dead sea scrolls", "textual criticism"],
      "expertise_tier2": ["early church history", "christian apologetics"],
      "low_authority_zones": ["geopolitics", "military tactics", "UFO/UAP"],
      "personal_life_zones": ["how he became a christian", "family life", "online attacks against him"],
      "speaking_style": "Giảng chậm, rõ, dẫn văn bản gốc và niên đại cụ thể, chốt bằng một kết luận gọn",
      "trust_with_host": "Shawn hỏi như người đang tìm lại đức tin, khách trả lời cởi mở, ít phòng thủ",
      "audience_wants": ["what the dead sea scrolls prove", "oldest bible manuscripts", "evidence jesus existed"],
      "audience_ignores": ["his conversion story", "his take on politics"],
      "opsec_limited_identity": false,
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
      "core_keyword": "dead sea scrolls",
      "topics": ["chủ đề chính 1", "chủ đề 2", "chủ đề 3"],
      "value_axis": "authority"
    },
    {
      "rank": 2,
      "kind": "highlight",
      "content_rank": 1,
      "summary_vi": "1 câu tiếng Việt, viết THẲNG — không giật tít — để đọc lướt hiểu ngay đoạn nói về ai/chuyện gì",
      "start": "00:21:54",
      "end": "00:39:26",
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
      "core_keyword": "dead sea scrolls",
      "keyword_reach": "R2",
      "keyword_credibility": "high",
      "credential_label": "Biblical Scholar",
      "keyword_reason": "People searching 'dead sea scrolls' want to know what was actually found and whether it changes the Bible, and the title puts a manuscript scholar right next to the phrase — the authority is visible before the click.",
      "satellite_keywords": ["oldest bible manuscript", "book of isaiah"],
      "topics": ["chủ đề chính 1", "chủ đề 2", "chủ đề 3"],
      "hook_en": "Câu Start tiếng Anh nguyên văn — cú hook mạnh nhất của đoạn",
      "summary_en": "1-2 câu tiếng Anh tóm tắt đoạn nói về gì, có tên riêng, đơn vị/chiến dịch/văn bản/sự kiện cụ thể.",
      "intensity": 9,
      "value_axis": "authority",
      "content_type": "expertise",
      "topic_group": "religion_theology",
      "gtf": 9,
      "cq": 9,
      "final_score": 8.1,
      "duration_min": 17.5,
      "fit_reason": "1 câu tiếng Anh: vì sao CHÍNH khách mời này đào sâu chủ đề này mới đắt"
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
- **KHÔNG khai** trên entry hook: `gtf`, `cq`, `final_score`, `content_rank`, `intensity`, `keyword_reach`, `keyword_credibility`, `keyword_reason`, `satellite_keywords`, `fit_reason`, `hooks`, `credential_label`, `content_type`, `topic_group`, `duration_min`. Những field này chỉ thuộc về đoạn highlight.

**Field riêng của entry `kind: "highlight"`:**
- `content_rank`: thứ hạng chất lượng theo ĐIỂM CUỐI, 1 = hay nhất. Các entry highlight trong file phải có `content_rank` tăng dần.
- `episode.id`: `SRS-<số>` (lấy từ `SRS #<số>` trong tên file). Chưa rõ → hỏi đúng 1 lần hoặc suy từ tên file.
- `episode.guest`: đúng như chương trình dùng — xem OPSEC ở II.1.
- `episode.guest_profile`: bản rút gọn Guest Card, viết tiếng Anh cho field mảng, tiếng Việt cho `identity`/`speaking_style`/`trust_with_host`. `lane`: `"exp"` | `"know"` | `"mixed"`. `archetypes`: tag ở cột Tag bảng II.3.
- `hooks`: **BẮT BUỘC, 1–2 phần tử** (Mục III.9), xếp theo `rank`. Mỗi phần tử phải **khớp tuyệt đối** với entry hook phẳng tương ứng.
  - `hooks[].rank`: 1 hoặc 2 — bằng `hook_rank` của entry phẳng.
  - `hooks[].flat_rank`: `rank` của entry hook phẳng tương ứng trong `segments[]` — cầu nối hai chiều.
  - `hooks[].start` / `hooks[].end`: timestamp thật, **PHẢI nằm trong `[segment.start, segment.end]`**.
  - `hooks[].duration_sec`: `end` − `start`, trong khoảng **5–25**.
  - `hooks[].quote_en`: nguyên văn tiếng Anh.
  - `hooks[].type`: `shock_claim` · `fact_bomb` · `story_teaser` · `curiosity_question` · `conflict`.
  - `hooks[].is_segment_opening`: `true`/`false`.
  - `hooks[].why`: 1 câu tiếng Anh — vì sao câu này giữ chân người xem trong 10 giây đầu.
- `core_keyword`: **BẮT BUỘC.** Cụm tiếng Anh **viết đúng như người ta sẽ gõ vào ô tìm kiếm**, chữ thường. Không giới hạn loại từ — `dark web`, `delta force selection`, `how hackers hack you`, `what hell looks like` đều hợp lệ. KHÔNG phải tên khách mời (trừ khách là thứ người ta đang săn tìm), **không bao giờ là `shawn ryan`**.
- `keyword_reach`: `R3` (rất nhiều người tìm) · `R2` (lượng tìm ổn định) · `R1` (ít người tìm / phải giải thích thuật ngữ). `R0` không được xuất.
- `keyword_credibility`: `high` · `medium` · `low` — người gõ cụm đó, nhìn thấy người đang nói và nhãn thẩm quyền của họ, có tin không. `low` không được xuất — clickbait hại retention.
- `credential_label`: nhãn thẩm quyền 2–5 chữ tiếng Anh hiển thị trên title/thumbnail (III.7), đúng với nội dung của chính đoạn này.
- `keyword_reason`: 1–2 câu tiếng Anh — người gõ cụm này đang muốn biết gì, đoạn này trả lời gì, và **nhãn thẩm quyền nào khiến họ tin**. Nếu `R1`: nêu rõ cầu nối sang một keyword R3.
- `satellite_keywords`: 0–2 cụm — các chủ đề còn lại của rabbit hole, để `viet-tittle-v2` dựng Connective Thread.
- `topics`: 2–5 cụm chủ đề tiếng Anh ngắn.
- `hook_en`: đúng câu quote Start của thân đoạn, không viết lại. (Khác `hooks[]` — đây là câu mở đầu thân đoạn, `hooks[]` là các lát cold open dựng lên trước.)
- `value_axis`: `"authority"` / `"confession"` / `"both"`.
- `content_type`: `"expertise"` / `"lived_experience"` / `"personal"` (phân loại LUẬT 0).
- `topic_group`: nhóm prior ở III.6, đúng một giá trị trong cột `topic_group`.
- `final_score`: `CQ × (GTF/10)`, làm tròn 1 chữ số thập phân.
- `duration_min`: thời lượng thân đoạn (phút, 1 chữ số thập phân) — để tự kiểm ngưỡng Mục IV.
- `fit_reason`: 1 câu tiếng Anh, lý do khách mời khiến đoạn đắt; ghi rõ nếu đã áp III.5, dùng ngoại lệ thời lượng, hoặc đoạn không gắn được nhãn thẩm quyền.

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

[N]. **[Tiêu đề đoạn nội dung — giật tít được, có sức nặng]**

Start: (hh:mm:ss) "[Trích câu tiếng Anh nguyên bản — Hook mạnh nhất]..."

End: (hh:mm:ss) "...[Trích câu tiếng Anh nguyên bản kết thúc]"

Tóm tắt: [Tóm tắt chi tiết tiếng Việt — diễn giải sâu từ hook đến kết, kể cả khi đi qua nhiều chủ đề. Văn phong nghiêm, có sức nặng, bám nhịp căng của SRS. Nêu rõ cơ chế/văn bản/chiến dịch/địa danh/đơn vị/dữ liệu đắt nhất ở từng chặng. Mọi nhân vật, chiến dịch, đơn vị, tổ chức phải có TÊN ĐẦY ĐỦ + chính tả chuẩn ở lần nhắc đầu.]

Tại sao đoạn này đắt: [2–4 câu — chiều sâu chuyên môn, rabbit hole liền mạch, reveal ngược narrative, chuỗi tiết lộ leo thang, hook, density.]

**🪝 HOOK COLD OPEN** (lát cắt dựng lên đầu video, nằm trong chính đoạn này — xuất thành entry riêng trong cùng file cutlist):
1. `(hh:mm:ss – hh:mm:ss · ~Ns)` "[quote nguyên văn tiếng Anh]" — *[loại hook]*
   → [1 câu: vì sao câu này giữ chân người xem trong 10 giây đầu]
2. `(hh:mm:ss – hh:mm:ss · ~Ns)` "[quote 2]" — *[loại hook]* *(chỉ khi đoạn có 2 khoảnh khắc đỉnh tách biệt)*
   → [1 câu lý do]

**🔑 Keyword hạt nhân:** `[cụm viết đúng như người ta gõ vào ô tìm kiếm]` · **Reach [R3/R2/R1]** · **KGC [cao/trung bình]**
*Vì sao đoạn này thắng nhờ keyword đó:* [1–2 câu — người gõ cụm này đang muốn biết gì, đoạn này trả lời gì, và **nhãn thẩm quyền nào khiến họ tin**. Nếu R1: ghi rõ cầu nối sang keyword R3.]
*Keyword vệ tinh:* `[kw2]`, `[kw3]` — hoặc ghi "không có" nếu khối đơn chủ đề.
**🏷️ Thẩm quyền hiển thị:** `[nhãn 2–5 chữ sẽ đứng trên title/thumbnail]`

**🎯 Fit với khách mời:** [1–2 câu — vì sao CHÍNH khách này đào sâu chủ đề này mới đắt: chuyên môn cấp mấy / lived experience in-lane / confession in-lane. Kèm `GTF x/10 · CQ y/10 · Điểm cuối z`, trục giá trị, `Thời lượng: X phút` và nhóm prior (III.6). Đã áp III.5 hoặc ngoại lệ thời lượng → ghi rõ.]

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
3. Ghi timestamp đó — không ước tính, không lấy số từ vùng lân cận.
4. Không bao giờ chọn timestamp trước rồi mới chọn quote.
5. Áp y hệt cho timestamp của hook cold open — kể cả khi hook chỉ dài 8 giây.

Kiểm tra chéo: mở transcript, nhảy tới timestamp, câu đầu tiên nghe được có đúng là quote này không? Không chắc → tra lại.

**Kiểm thời lượng:** `end − start` của thân đoạn phải ≥12 phút (AUTHORITY) hoặc ≥8 phút (CONFESSION). Không đạt → quay lại Mục IV, thử gộp.

**Nếu transcript KHÔNG có timestamp:** không được suy ra giờ:phút:giây từ số từ hay tốc độ nói. Báo rõ cho người dùng, dùng số dòng transcript làm mốc tạm, và xin bản transcript có timestamp trước khi xuất cutlist.

### QUY TẮC TÊN ĐẦY ĐỦ NHÂN VẬT — BẮT BUỘC

1. **Lần đầu xuất hiện → TÊN ĐẦY ĐỦ + định danh ngắn**, chính tả chuẩn. ĐÚNG: "Marcus Luttrell — cựu Navy SEAL, sống sót duy nhất trong Operation Red Wings", "Delta Force (1st SFOD-D)". SAI: "Marcus" đứng một mình, "the op" không rõ chiến dịch nào.
2. Sau đó có thể gọi ngắn.
3. **Chính tả chuẩn** — ASR rất hay sai tên (địa danh Ả Rập/Afghanistan, tên chiến dịch, quân hàm, tổ chức, thuật ngữ thần học/y khoa). Dùng dạng chuẩn và **sửa lỗi ASR**: "Fallujah", "Kandahar", "Abbottabad", "Operation Red Wings", "SEAL Team 6 (DEVGRU)".
4. **Callsign/biệt danh**: nêu kèm tên thật ở lần đầu nếu transcript có — **trừ khi bị chặn bởi OPSEC ở điểm 6**.
5. Không áp dụng cho quote tiếng Anh Start/End, quote hook, và `title` cutlist.
6. **Ngoại lệ OPSEC:** `opsec_limited_identity: true` → quy tắc "tên đầy đủ" CHỈ trong phạm vi chương trình đã công khai — KHÔNG tự thêm họ/tên thật hay đơn vị hiện tại.

### QUY TẮC CHÍNH XÁC & AN TOÀN NỘI DUNG — BẮT BUỘC

1. **Chỉ dùng số liệu/dữ kiện có trong transcript.** Không bịa số thương vong, ngày tháng, tên chiến dịch, chi tiết nghiệp vụ, trích dẫn văn bản. Không rõ → để mờ ("một chiến dịch ở Iraq").
2. **Không thêm cáo buộc.** Khách nêu cáo buộc → "theo lời [tên khách]".
3. **PTSD / tự sát / chấn thương** — xử lý nghiêm túc, tôn trọng, không giật gân hoá nỗi đau. Giữ trọng tâm ở cơ chế, hành trình và ý nghĩa. *(III.6 khuyên hạn chế chọn nhóm này vì lý do hiệu suất — lý do thương mại, không phải coi nhẹ chủ đề. Khi đã chọn, chuẩn mực xử lý không đổi, kể cả khi rút hook.)*
4. **Không đưa chi tiết nghiệp vụ mang tính "hướng dẫn"** (cách chế tạo, quy trình gây sát thương, kỹ thuật tấn công mạng cụ thể) vào tóm tắt hay hook — kể *rằng* điều đó xảy ra, không thành cẩm nang.
5. **Bảo vệ danh tính khi khách có giới hạn OPSEC.**
6. **Tôn giáo / tín ngưỡng / chính trị:** trình bày quan điểm của khách **là quan điểm của khách**, không viết như chân lý đã xác lập. Giữ ngôn ngữ trung tính khi tóm tắt luận điểm gây tranh cãi về nhóm tôn giáo/sắc tộc. *(Nhóm tôn giáo/huyền bí có Idx cao — càng khai thác nhiều càng phải giữ kỷ luật này.)*

---

## VII. QUY TRÌNH THỰC HIỆN (SRS V1.0)

**Giai đoạn A — Khách mời (1 lần/tập):**
1. Xác định khách mời (II.1), tôn trọng OPSEC.
2. Research 3 nguồn (II.2), tuân thủ liêm chính.
3. Định vị archetype + LANE + trục giá trị + **NHÃN THẨM QUYỀN** (II.3, II.4, III.7).
4. In GUEST CARD (II.5), dừng cho người dùng đọc/chỉnh sửa.

**Giai đoạn B — Nội dung:**
5. Quét toàn bộ transcript, phân khối theo rabbit hole liền mạch. **Đánh dấu vị trí mọi đoạn quảng cáo** ngay ở bước này.
6. Phân loại từng khối theo LUẬT 0: `expertise` / `lived_experience` / `personal`.
7. Chấm CQ (III.1) — cộng cho khối có chi tiết gây sốc mô tả được thành cụm từ nặng.
8. Chấm GTF (III.2). **Không áp gate loại nào theo GTF.**
9. Áp LUẬT VÀNG CONFESSION — chỉ nâng khi in-lane.
10. Áp III.5 — khối có lõi chuyên môn bị đời tư làm loãng: tái định biên hoặc tách khối trước khi chấm lại.
11. Tính ĐIỂM CUỐI (`CQ×GTF/10`), xếp hạng (III.3), chạy 8 câu hỏi kiểm tra (III.4).
12. **Tie-break:** nếu hai khối đầu bảng chênh <1 điểm → áp PRIOR CHỦ ĐỀ (III.6). Khối chính trị / tech-AI-drone / PTSD / đời tư phải chênh ≥1,5 điểm mới được chọn.
13. Chọn khối đứng đầu chưa dùng. **Kiểm tra ngưỡng thời lượng (Mục IV):** nếu <12 phút (AUTHORITY) hoặc <8 phút (CONFESSION) → thử GỘP với khối liền kề cùng mạch trước khi chấp nhận.
14. Kiểm quảng cáo trong Start→End — có thì tách tại mép quảng cáo.
15. **Rút KEYWORD HẠT NHÂN (III.8)** — "gõ một cụm gì vào ô tìm kiếm để ra đúng đoạn này?". Chấm **Reach × KGC**, tra ma trận. Ô ❌ → thu hẹp biên / gộp / đổi khối. R1 + KGC cao → kiểm điều kiện vượt ≥1,5 điểm và tìm cầu nối sang keyword R3.
16. Xác định **nhãn thẩm quyền hiển thị** (III.7) đi kèm keyword đó.
17. Xác định trường hợp cắt (TH1–TH4). Nếu keyword hạt nhân không nằm ở 1/3 đầu khối → cân nhắc dời Start tới chỗ nó xuất hiện.
18. Chọn Start/End — timestamp gắn trực tiếp; áp III.5 nếu có tiểu sử xen kẽ.
19. **Rút HOOK COLD OPEN (III.9)** — quét lại đoạn đã chốt, gạch 3–6 ứng viên, chấm 4 tiêu chí, chọn 1 (tối đa 2), gắn timestamp thật, kiểm thời lượng 5–25 giây và kiểm hook nằm trong biên đoạn, ngoài quảng cáo, không vi phạm OPSEC.
20. Kiểm tra chéo timestamp + quote (cả thân đoạn lẫn hook), **và kiểm `end − start` đạt ngưỡng**.
21. Kiểm tra tên đầy đủ nhân vật (tôn trọng OPSEC), sửa lỗi ASR.
22. Kiểm tra chính xác & an toàn nội dung.
23. Xuất kết quả theo format khóa cứng — gồm "Tại sao đắt", **"Hook cold open"**, **"Keyword hạt nhân"**, **"Thẩm quyền hiển thị"**, "Fit với khách mời", và CUT BLOCK.
24. **Khi người dùng yêu cầu xuất cutlist:** dựng mảng `segments[]` phẳng theo Mục Vb (hook đứng ngay trước đoạn cha, `rank` liên tục), chạy đủ 8 mục kiểm tra, rồi ghi **đúng MỘT file** `cutlist_<episode_id>.json`.

---

## VIII. TIÊU CHÍ CHỌN NỘI DUNG TỐT (tổng hợp)

Ưu tiên:
- **Nội dung thực sự thu hút người xem trước tiên** (CQ cao: chiều sâu, reveal, leo thang, density) — GTF chỉ là hệ số điều chỉnh điểm, không phải điều kiện loại
- **Rabbit hole chuyên môn liền mạch 15–25 phút** — tín hiệu mạnh nhất toàn bộ dữ liệu *(Mục IV)*
- **Chiều sâu chuyên môn** — khách dùng tri thức/nghiệp vụ/nghiên cứu để đào sâu (LUẬT 0)
- **Nhãn thẩm quyền hiển thị được trên title/thumbnail** *(III.7 — 1.35 vs 0.89)*
- **Có KEYWORD HẠT NHÂN gõ được vào ô tìm kiếm, Reach R3/R2 VÀ KGC cao** *(III.8)*
- **Rút được HOOK COLD OPEN sắc — một lát 5–25 giây tự đứng một mình, giật mình được, không spoil trọn** *(III.9)*
- **Reveal đi ngược narrative** · **Chuỗi tiết lộ leo thang**
- **War story sinh tử trọn vẹn** *(EXP-LANE)* — nhóm vững nhất kênh (1.38)
- **Chi tiết gây sốc mô tả được thành một cụm từ nặng** (1.77)
- **Quy trình tuyển chọn & huấn luyện khắc nghiệt** (1.83) · **Tôn giáo/huyền bí/UAP có người thật đứng sau** (1.32–1.54) · **An ninh mạng/dark web** (1.56)
- **Confession in-lane** — hạ rào **trong chính lĩnh vực chuyên môn**, đặt trong mạch đủ dài

Tránh:
- **Khối dưới 12 phút** (AUTHORITY) — vùng 8–10 phút là khối sản xuất lớn nhất mà Idx chỉ 0.95; gộp trước khi chấp nhận
- **Khối dưới 5 phút** — đáy tuyệt đối (0.46, chỉ 2,9% đạt 500K)
- **Đời tư/tiểu sử của khách KNOW-LANE** (LUẬT 0, 0.74)
- **Khối thuần chính trị/địa chính trị** (0.72) — trừ khi CQ áp đảo ≥1,5 điểm
- **Khối thuần tech/AI/drone** (0.54 — kém nhất kênh)
- **Khối chấn thương chỉ có nước mắt, không có cơ chế** (0.62)
- **Khối không rút được cụm nào để gõ (R0)** · **Keyword R1 mà không có cầu nối sang R3** · **Reach cao nhưng KGC thấp** (clickbait)
- **Khối không rút nổi một hook cold open nào** — cả 15 phút không có một câu tự đứng một mình được là dấu hiệu khối nhạt
- **Đặt tên host vào title/hook/keyword** (0.86) — khán giả đến vì khách
- Chủ đề hot (UFO, CIA, Epstein) nhưng khách chỉ "nghe đồn" và nội dung thực chất nhạt — chấm GTF thấp cho đúng; nếu bản thân đoạn vẫn đủ CQ cao thì cứ chọn
- Đoạn "ai có chuyên môn tương đương cũng nói được y hệt" · Khối để lọt quảng cáo · Ép chèn đời tư để "cân bằng trục"
- **Xuất cutlist thành hai file** (một cho hook, một cho highlight) — luôn là MỘT file

---

## IX. PHỤ LỤC — DỮ LIỆU & GIẢ THUYẾT ĐÃ KIỂM ĐỊNH VÀ **BỊ BÁC**

**Nguồn:** toàn bộ **2.000 clip long-form** kênh SRS Clips (@shawnryanclips), 09/2022 → 09/2026 (đã loại 2.239 Shorts). View chuẩn hoá theo median của 151 clip đăng liền kề; kiểm lại với cửa sổ 21/51/301; xác nhận bằng hồi quy đa biến. Ghi lại để không ai đi lại đường cụt.

### ❌ "Tín hiệu CÂU CHUYỆN (Story) của JRE cũng đúng với SRS"

Ở JRE Clips, title chứa `Story/Stories` đạt Idx **1.50**. **Trên SRS: 1.07** [CI 0.88–1.83], n=88 — **không khác biệt**. Lý do hợp lý: gần như *mọi* clip SRS đều đã là một câu chuyện. **Đừng bê tín hiệu Story từ skill JRE sang** — vị trí III.7 của skill JRE ở đây đã được thay bằng NHÃN THẨM QUYỀN HIỂN THỊ.

### ❌ "Title mở đầu bằng một câu quote nặng thì ăn hơn"

Format chủ đạo của kênh (15,2% sản lượng). **Idx 1.08** [0.92–1.24] — không tách khỏi nhóm còn lại. Không có hại, nhưng **không phải thứ tạo ra view**; đừng đánh đổi biên cắt tốt chỉ để lấy một câu quote đẹp. *(Điều này nói về TITLE. Hook cold open là lát video dựng lên đầu clip — một chuyện khác, xem bảng trạng thái bên dưới.)*

### ❌ "Thang REACH (cụm đại chúng > cụm ngách) đo được trên title"

Tách title chứa **cụm đại chúng** (`navy seal`, `cia`, `dark web`, `cartel`, `epstein`, `hell`) khỏi title chứa **thuật ngữ ngách** (`macv-sog`, `jsoc`, `eod`, `jtac`, `humint`, `exfil`): 1.12 vs 1.23 — **ngược chiều giả thuyết, không có ý nghĩa**. Trong riêng nhóm SOF: 1.38 vs 1.19, vẫn ns.

**Kết luận đúng:** thang Reach ở III.8 là **định nghĩa vận hành và kỷ luật quy trình**, KHÔNG phải luật đã chứng minh. **KHÔNG được** biến `keyword_reach` thành hệ số nhân vào ĐIỂM CUỐI — nó là **tie-break và bộ lọc ngưỡng** (R1 phải vượt ≥1,5 điểm; R0 và KGC thấp loại).

> **Nhưng KGC thì khác — ở SRS nó ĐÃ được đo và xác nhận:** ×1.47 (t=+6.1), giữ nguyên trong cả nhóm phi quân sự. Nếu phải bỏ bớt một nửa của III.8, **bỏ Reach, giữ KGC.**

### ❌ "Title dạng câu hỏi kéo tò mò tốt hơn"

Title chứa `?`: **0.89** [0.68–1.11] so với 1.03 — không có lợi, nếu không muốn nói là hơi bất lợi. Title mở đầu What/Why/How: 0.98. Một câu khẳng định nặng thắng một câu hỏi mở. *(Áp cho title. Với hook cold open, loại `curiosity_question` vẫn hợp lệ, nhưng khi hai ứng viên ngang nhau thì ưu tiên `shock_claim`/`fact_bomb`/`story_teaser`.)*

### ⚠️ "Tình báo/tradecraft là bản sắc nên phải mạnh nhất"

**Idx 1.00** [0.76–1.29] — đúng bằng trung bình kênh, thấp hơn cả tôn giáo và UFO. Không phải lý do bỏ chủ đề tình báo, mà là cảnh báo: **đừng chọn một khối chỉ vì nó có chữ CIA.**

### ⚠️ Các con số cần đọc thận trọng

| Kết luận | Trạng thái |
|---|---|
| Thời lượng 15–25 phút là vùng vàng | ✅ **Vững nhất.** Bền qua 4 cách chuẩn hoá, qua hồi quy, trong cả SOF lẫn phi-SOF |
| Nhãn thẩm quyền hiển thị (KGC) | ✅ **Vững.** t=+6.1, giữ trong nhóm phi quân sự |
| SOF/war story 1.38 | ✅ **Vững.** n=514, CI 1.16–1.65 |
| Chính trị 0.72 · tech/AI 0.54 · PTSD 0.62 | ✅ CI trên đều <1; hồi quy xác nhận chính trị và tech |
| Tôn giáo 1.32 · UFO 1.54 | ✅ CI dưới >1, hồi quy xác nhận |
| Từ ngữ dark/emotional 1.77 | ✅ n=128, hồi quy xác nhận |
| Selection 1.83 · sinh tồn 1.67 · hacker 1.56 · cartel 1.44 | ⚠️ n nhỏ (16–46), CI rất rộng — **giả thuyết đáng thử, chưa chứng minh** |
| Clip >30 phút Idx rất cao | ⚠️ **n=8.** Các "mini-documentary" đặc biệt, không phải luật áp thường xuyên |
| Đời tư 0.74 · nhà tù/án mạng 0.61 | ⚠️ CI chạm 1 — hướng rõ nhưng chưa chốt |
| Thang Reach (R3 > R2 > R1) | ⚠️ Đo trên title ra ns — **giả thuyết làm việc**, chỉ dùng làm bộ lọc ngưỡng |
| Bắt buộc khai báo keyword | ✅ Không cần bằng chứng — là **kỷ luật quy trình**: không rút được keyword = dấu hiệu khối lan man; `viet-tittle-v2`/`tong-hop-rabbit-hole` đều cần chỗ neo này |
| **HOOK COLD OPEN (III.9)** | ⚠️ **Chưa đo trên dữ liệu kênh SRS.** Dựa trên nguyên lý retention chung của YouTube (khán giả quyết định ở 5–15 giây đầu). Là **kỷ luật quy trình + giả thuyết làm việc** |
| **Layout một file `flat_hooks`** | ✅ Không cần bằng chứng — là **quyết định vận hành**: tool cắt chỉ nhận một file, hook phải là entry bình thường để cắt được cùng lượt với thân đoạn |

**Điều KHÔNG được làm:** biến `keyword_reach` hay "độ mạnh hook" thành hệ số nhân vào ĐIỂM CUỐI. Hook là bước bắt buộc phải làm sau khi đã chọn khối, không phải biến số xếp hạng khối, và **entry hook không bao giờ tham gia xếp hạng `content_rank`** — nó chỉ là một lát cắt của đoạn cha.

**Giới hạn phương pháp:** (1) mọi phép đo dựa trên **title**, không đo được nội dung thật bên trong clip; (2) ngày đăng lấy gần đúng nên chuẩn hoá dùng **thứ tự đăng**; (3) đây là dữ liệu kênh clip tiếng Anh của chính show — kênh Shawn Ryan Show Highlights cùng nhắm khán giả YouTube Mỹ nhưng vẫn có thể lệch; coi mọi Idx là **prior để tie-break**, không phải phán quyết.

**Tự kiểm chứng trong 3 tháng tới:** ghi `core_keyword`, `keyword_reach`, `credential_label`, `topic_group`, `duration_min` cho mọi đoạn xuất ra. Tích ~60–80 clip đã lên sóng ≥60 ngày rồi so median view: (a) ≥15 phút vs <12 phút; (b) có `credential_label` mạnh vs không; (c) R3 vs R1–R2 — **nếu (c) không tách, hạ III.8 xuống thành checklist kỷ luật và bỏ luật "R1 phải vượt ≥1,5 điểm"**.

**Cách kiểm chứng HOOK COLD OPEN:** thí nghiệm A/B rẻ nhất trong cả workflow vì cùng một nội dung, chỉ khác 10 giây đầu. Đăng ~20 clip có dán hook cold open lên đầu và ~20 clip mở thẳng vào thân đoạn, cùng khoảng thời gian, rồi so **tỉ lệ giữ chân ở mốc 30 giây** trong YouTube Analytics (không so tổng view — view còn phụ thuộc title/thumbnail). Nếu nhóm có hook không nhỉnh hơn rõ ở mốc 30 giây, hạ III.9 xuống thành tuỳ chọn thay vì bước bắt buộc.
