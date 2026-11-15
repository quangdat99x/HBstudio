# BỘ QUY TẮC LÀM VIDEO TIN TỨC · Creater Vid

> Mọi lượt làm việc của mọi dự án **video tin tức** (mảng 📰 Tin tức của Creater Vid) phải tuân theo bộ quy tắc này.
> Phim tài liệu là một mảng khác, có bộ quy tắc riêng (`RULEBOOK.doc.md`): không áp quy tắc của bộ đó cho video tin tức, và ngược lại.
> Thứ tự ưu tiên: yêu cầu của người dùng trong chat > bộ quy tắc này > thói quen mặc định.
> Người dùng yêu cầu điều trái quy tắc thì vẫn làm theo người dùng, kèm một dòng ⚠️ nêu rõ quy tắc nào bị phá và rủi ro.
> Quy tắc được viết ra từ những lần người dùng sửa video. Mỗi lần người dùng sửa hay góp ý, cập nhật vào đây (mục 10).

---

## 0. Video tin tức của chúng ta là gì

- Video tin thời sự cho YouTube (và Shorts/TikTok), làm từ các tin người dùng chọn ở trang **Tin theo dõi** của app (hoặc dự án tạo tay ở trang Dự án tin tức). Chủ đề hiện nay: chiến sự và chính trị Nga–Ukraina, khán giả nói tiếng Nga.
- Hai kiểu video (`video_kind` trong `sources/news.json`, app ghi khi tạo dự án):
  - **Tin nóng** (`single`): một sự kiện, mặc định 9:16 · 60 s (mục 2.8);
  - **Điểm tin 24h** (`digest`): bản tin tổng hợp 14–20 sự kiện trong một ngày, 16:9 · ~15 phút (mục 2.9).
- **Ngôn ngữ trên hình và lời dẫn** theo `language` của dự án (thường tiếng Nga). Ghi chú nội bộ và trả lời người dùng bằng tiếng Việt.
- **Xương sống = các tin đã chọn** (`sources/news_*.md`: nguồn, phía, giờ đăng, link, toàn văn) và nguồn gốc của chúng (thông cáo chính thức, bài gốc). Tra web để kiểm chứng và thêm bối cảnh; không thêm tin ngoài danh sách khi người dùng chưa bảo.
- **Hình = ảnh, video thật của chính các tin** (mục 1.7), bản đồ và thẻ chữ dựng bằng code; ảnh AI là đường cuối. Không có nhân vật vẽ, không dựng cảnh tái hiện.
- **Làm được mỗi ngày:** quy trình đơn giản, lặp lại được; tên kênh, lời chào, lời tạm biệt, đồ hoạ giống nhau mọi tập.

## 1. Tính xác thực và trích nguồn

1.1 **Ai nói gì.** Tuyên bố của một bên luôn có chủ thể (cơ quan, người phát ngôn): viết «Минобороны РФ заявило об уничтожении…», «украинская сторона сообщила…», không viết «уничтожен…» như sự thật đã kiểm chứng. Ảnh, video của một bên tham chiến là tư liệu của bên đó: lời dẫn nói rõ ai công bố. Tựa và thumbnail cũng vậy: vế khẳng định phải là tuyên bố có chủ thể, điều chưa rõ thì đặt thành câu hỏi.
1.2 **Kiểm chứng từng tin** trước khi viết (agent song song, ví dụ mặt trận / hậu phương; agent chỉ ghi vào `notes/`):
  - tìm thông cáo gốc (Telegram của Bộ QP, оперштаб, ОВА, Генштаб) và phiên bản của phía bên kia;
  - không dẫn bản kể lại của kênh milblogger khi đã có bản gốc;
  - đoạn tóm tắt của công cụ tìm kiếm không phải nguồn: mở bài gốc trước khi dẫn;
  - báo/kênh dẫn lời một cơ quan («по информации Минобороны…»): so với chính thông cáo của cơ quan đó. Bản kể lại đăng **trước** thông cáo, hoặc **trước** khi báo gốc đính chính, có thể sai: mở bản mới nhất của bài gốc, đọc ghi chú biên tập;
  - giờ «Đăng lúc» trong `sources/*.md` là giờ máy: đổi về giờ Moskva/Kyiv trước khi viết «sáng/tối»;
  - người dùng đưa tiền đề có vẻ sai: kiểm chứng bằng WebSearch/WebFetch, trình bày bằng chứng kèm link, đề xuất phương án đúng rồi để người dùng quyết. Không im lặng làm theo, cũng không tự ý bác bỏ.

  *(Nguồn gốc: Điểm tin 13.10.2026. WarGonzo gộp ca tử vong ngày 9/10 vào tin ngày 12/10. Tóm tắt tìm kiếm gán cho 24tv câu «Генштаб отрицал присутствие…» không có trong bài. Tin Харьков buổi sáng suýt bị kể thành buổi tối. Tập 3: Военное обозрение gán «Искандер/Циркон/Герань» và Львов cho Bộ QP Nga, đăng 3,5 giờ trước thông cáo thật (không có các chi tiết đó); Страна còn câu «Палиса подтвердил FT» mà Kyiv Independent đã gỡ.)*
1.3 **Trích nguyên văn:** chỉ đặt trong ngoặc kép câu có thật trong nguồn; lưu văn bản gốc vào `notes/texts/` và so chuỗi bằng python. Câu trích từ tiếng Anh/Ukraina: lưu nguyên văn gốc, so chuỗi bản gốc (trường `original` của quote), lời dẫn đọc bản dịch tiếng Nga. Câu diễn ý không đặt trong ngoặc kép như nguyên văn.
1.4 **Người thật** chỉ xuất hiện qua ảnh, video thật của tin (`depiction: archival_photo`) hoặc chỉ được nhắc tên. Không vẽ AI người thật nhận ra được, không đặt lời vào miệng họ: chỉ trích nguyên văn có nguồn.
1.5 **Ảnh, video lấy từ tin** (`sources/media.json`: app lập danh sách và tự tải hết vào `sources/media/` khi tạo dự án; người dùng bỏ mục nào trên trang dự án thì mục đó thành `rejected`):
  - chỉ dùng mục `status: "downloaded"`. Mục `rejected`, `failed`, `need_api`: không dùng;
  - trước khi dùng, tự xem từng file (ảnh: mở xem; video: trích 4–6 khung bằng ffmpeg rồi xem) và báo trong lượt nếu thấy: người chết hoặc bị thương, máu, tù binh nhận diện được, trẻ em, logo hay watermark (ghi `logo_mask` và che theo mục 1.10), chữ trên hình. Thương vong, máu, tù binh nhận diện được, mặt trẻ em: bỏ đoạn đó hoặc che mờ (chính sách nội dung của YouTube, không phải chuyện bản quyền), và báo người dùng;
  - video phải mở được bằng `ffprobe`: file app tải có thể bị cụt (dừng đúng 12 MB, «moov atom not found»). Khi đó tải lại bản đủ từ trang nhúng của chính bài (`t.me/<kênh>/<id>?embed=1`). Trang nhúng báo «Media is too big» thì chỉ tải được qua Telegram API: báo người dùng, dùng hình khác;
  - xem nội dung thật trước khi gán cho cảnh, mô tả đúng **sự kiện nào, câu nào có trong đó**; không xem được thì ghi «chưa xác nhận nội dung». Nội dung không khớp tin thì không gắn sang tin khác (mục 1.7), báo người dùng. *(Điểm tin 13.10.2026 tập 3: «ảnh Kyiv 22:10» trong bài Zelensky hoá ra toàn ảnh Харьков; clip NBC không có câu «time for Ukraine to get a new president».)*
  - mỗi lần dùng đoạn video ≤ 10–15 s, có lời dẫn bình luận, không phát trọn video của người khác; nhãn nguồn theo mục 1.6.
1.6 **Không nêu tên báo, hãng tin, kênh trước khán giả** (lời dẫn, chữ trên hình, nhãn, phụ đề, tựa, thumbnail, mô tả, thẻ, hashtag) — để không dùng thương hiệu của người khác:
  - **loại bỏ hoàn toàn tên mọi báo, hãng tin, đài, trang tin, kênh Telegram/YouTube**, kể cả hãng lớn và hãng nhà nước: không Reuters, AP, AFP, Bloomberg, BBC, CNN, NBC, Fox, The New York Times, The Guardian, Politico, Der Spiegel, Bild…; không ТАСС, РИА Новости, Интерфакс, РБК, Коммерсантъ, Meduza, DW, Радио Свобода, Страна, УНИАН, Украинская правда…; không Рыбарь, Два майора, WarGonzo, DeepState… Không đọc tên, không viết tên (cả viết tắt, cả chữ Latin), không dán link bài báo hay t.me vào mô tả;
  - **thay bằng cách nói chung**: «по данным СМИ», «как сообщают российские / украинские / западные / американские СМИ», «в интервью американскому изданию», «британская пресса пишет…». Tốt hơn nữa: dẫn thẳng **chủ thể gốc** của thông tin (thông cáo, người phát ngôn) khi đã kiểm được (mục 1.2);
  - **tên riêng của người, nhà nước, tổ chức, cơ quan vẫn dùng bình thường** (Путин, Зеленский, Трамп, НАТО, ЕС, ООН, Кремль, Белый дом, Минобороны РФ, Генштаб ВСУ, МАГАТЭ, Запорожская АЭС, Ozon…): họ là chủ thể hoặc đối tượng của tin, không phải nguồn báo chí. **Tuyên bố của một bên vẫn nói rõ ai tuyên bố** (mục 1.1): «Минобороны РФ заявило…», «украинская сторона сообщила…», «губернатор Белгородской области…». Tin chỉ có ở kênh Telegram thì nói «по данным российской/украинской стороны»;
  - chính tờ báo là **chủ thể của sự kiện** (phóng viên bị trục xuất, hãng bị cấm…): vẫn không nêu tên, kể bằng mô tả chung («корреспондент британской телерадиокомпании»); không kể được mà không nêu tên thì bỏ tin hoặc hỏi người dùng, ghi ⚠️ trong báo cáo;
  - **nhãn trên hình** chỉ ghi chủ thể chính thức, không ghi tên báo: «Заявление: Минобороны РФ», «Кадры: Минобороны РФ», «Фото: ГСЧС Украины» (cơ quan tự công bố ảnh/video). Ảnh, video lấy từ bài báo hay kênh Telegram: không ghi nhãn nguồn, hoặc ghi chung «Кадры из открытых источников»;
  - nội bộ vẫn ghi đủ mọi nguồn (tên báo, link) vào `1_script/sources.json`, `notes/`, `metadata.md` (phần nội bộ) để kiểm chứng: quy tắc này chỉ áp cho những gì khán giả thấy và nghe, kể cả metadata đăng YouTube.

  *(Nguồn gốc: người dùng yêu cầu, 2026-10-13; sửa 2026-11-10: bỏ hẳn tên mọi báo, hãng tin — kể cả báo lớn — để tránh vi phạm thương hiệu; tên riêng như Путин, НАТО vẫn dùng.)*
1.7 **Ảnh thật trước, ảnh AI sau:**
  - **Dùng tất cả ảnh, video thật của các tin đã chọn**, để video chính xác và chân thực:
    1. mọi mục trong `sources/media.json` (app đã tự duyệt và tải khi tạo dự án);
    2. ảnh trong chính các bài báo đã chọn: mở link gốc của từng tin (`sources/news_*.md`, `sources/links.txt`), lấy mọi ảnh nội dung trong thân bài (bỏ logo, icon, banner quảng cáo, ảnh của bài liên quan, ảnh nhỏ hơn ~400 px), tải vào `sources/media/art_<số tin>_<n>.<đuôi>` và ghi vào `5_footage/footage.json` (`type: "archival"`, `source_page` = link bài, `status: "downloaded"`). Ảnh của chính các bài đã chọn không cần chờ duyệt. Trang dựng bằng JavaScript (Meduza) không lộ ảnh trong HTML: lấy qua API của chính trang (`meduza.io/api/w5/<đường dẫn bài>` → ảnh `elarge`, kèm chú thích và năm chụp) rồi xem chú thích để biết ảnh có đúng tin không *(Điểm tin 23.10.2026: lấy được ảnh Горелов và Starlink; ảnh An-124 ở Лейпциг trong bài gián điệp là sự kiện khác → bỏ)*. JSON của API có cả ảnh của khối «Читайте также»: ảnh không chú thích, không credit thì coi là ảnh bài liên quan, không dùng; URL `impro/…` là bản thu nhỏ của chính ảnh `elarge` ngay trước nó → lọc trùng (so ảnh thu nhỏ) trước khi gán cảnh *(Điểm tin 01.11.2026: «chân dung Зеленский» không chú thích và 2 ảnh Алешки trùng lặp lọt vào bảng hình, phát hiện khi tải ở bước 3)*.
  - Ảnh, video ở nơi khác (ngoài các tin đã chọn): đề xuất vào `5_footage/footage.json` với `status: "proposed"`, chờ người dùng duyệt rồi mới đưa vào phim. **Mỗi đề xuất phải kèm bản xem** để người dùng duyệt được: tải riêng đoạn định dùng (≤ 30 s, có tiếng) vào `5_footage/preview/<id>_xem.mp4` + bảng khung `<id>_xem.jpg` + chép lời (whisper) và mốc giờ trong video gốc, ghi vào trường `preview` của mục đó; tải bản xem không phải là dùng. Không tải được (trang chặn, quá thời gian) thì nói rõ trong `preview.note` kèm link để người dùng tự mở. *(Điểm tin 16.10.2026 (2): 3 footage chờ duyệt chỉ có link — người dùng không duyệt được.)*
  - **Vẫn dùng ảnh, video thật của báo, nhưng BẮT BUỘC che logo:** không đổi ảnh thật sang ảnh AI vì lý do bản quyền; thay vào đó **mọi logo, watermark, tên/biểu tượng của báo, hãng tin, đài, kênh Telegram/TikTok, dải chữ có thương hiệu (lower third, ticker, khung «breaking» của đài), giao diện ứng dụng có tên kênh** đều phải được che trước khi lên phim (mục 1.10). Không còn để người dùng tự edit tay.
  - **Ảnh đi đúng tin của nó:** không gán ảnh của sự kiện này cho sự kiện khác như thể là ảnh thật của sự kiện đó. Ảnh đầu bài của báo (kể cả ảnh app tải vào `media.json`) thường là **ảnh minh hoạ lưu trữ**: đọc chú thích, credit và ngày trước khi gán cho cảnh «hôm nay»; ảnh minh hoạ chỉ đặt cạnh câu bối cảnh, kèm chip «архив» *(Điểm tin 04.11.2026 (2): ảnh khói của DW trong tin Ozon Адыгейск là vụ Ozon ở Саратов 09.2026)*. Ảnh của một tin khác chỉ dùng làm hình nền chung (bản đồ khu vực, toàn cảnh thành phố) và không đặt cạnh lời dẫn kể chuyện vừa xảy ra.
  - **Ảnh AI chỉ khi thật sự cần:** một tin không còn ảnh, video thật nào dùng được (kể cả sau khi tìm trong bài gốc), và bản đồ hay thẻ chữ số liệu không đủ. Mỗi ảnh AI ghi lý do trong `3_scenes/scenes.md`, ghi nhỏ «иллюстрация» trên hình; không vẽ người thật nhận ra được, không vẽ thương vong (mục 1.4).
  - Vẫn giữ kiểm tra của mục 1.5: xem từng file trước khi dùng; che mờ hoặc bỏ thi thể, máu, tù binh nhận diện được, mặt trẻ em.

  *(Nguồn gốc: người dùng yêu cầu, 2026-10-13: "dùng 100% ảnh real từ bài báo". Sửa 2026-11-10: vẫn dùng ảnh thật của báo nhưng che logo báo để không vi phạm thương hiệu.)*
1.8 **Âm thanh:** nhạc nền, sting, whoosh tạo bằng ElevenLabs qua `gen.py sfx` (gói trả phí, dùng thương mại) hoặc tự tổng hợp; không tải nhạc về. Tiếng gốc của nhân vật chỉ lấy từ video của chính các tin. Đoạn tiếng gốc có jingle, tiếng đọc tên đài hay câu chào của phát thanh viên báo/đài («Вы смотрите…», «This is BBC News»): cắt bỏ phần đó.
1.9 **Tuân thủ chính sách YouTube về spam, hành vi lừa đảo, gây hiểu lầm** (Spam, deceptive practices & scams; Impersonation; Misleading metadata; Reused content):
  - **Metadata không gây hiểu lầm:** tựa, thumbnail, mô tả chỉ hứa điều video thật sự có; câu hỏi của tựa được trả lời rõ trong video và ở câu đầu mô tả (mục 2.6a); không ghi «ОФИЦИАЛЬНО», «СРОЧНО», «ПОДТВЕРЖДЕНО», «ЭКСКЛЮЗИВ», «утечка» khi không đúng; không dùng ảnh, mặt người, sự kiện không có trong video làm thumbnail; không dựng thumbnail giả ảnh chụp màn hình bài báo, giả tweet, giả thông cáo;
  - **Không mạo danh:** tên kênh, logo kênh, đồ hoạ, lời chào không giống hay gợi tới một báo, đài, hãng tin, cơ quan nhà nước có thật; không tự gọi là «официальный канал», «агентство», không bắt chước bộ nhận diện (màu, khung tít, nhạc hiệu) của đài thật; không dùng logo, tên báo trên thumbnail hay ảnh đại diện;
  - **Không nhồi từ khoá:** thẻ, hashtag, mô tả chỉ chứa từ liên quan đúng nội dung video; không nhồi tên người, tên tổ chức, sự kiện không có trong video; không tên báo, tên kênh khác; mô tả viết thành câu tự nhiên, không danh sách từ khoá dài; hashtag ≤ 5 (YouTube bỏ qua mọi hashtag khi > 60);
  - **Không spam đăng:** không đăng lại cùng một video, không ra nhiều bản gần giống nhau cùng nội dung trên một kênh hay nhiều kênh; tập khác nhau phải khác lời dẫn, khác hình (mục 1.2 «tập trước»); không ép tương tác («лайк, чтобы узнать…», hứa quà, giveaway), không link ngoài dẫn tới trang lừa đảo, kiếm tiền, cờ bạc; CTA chỉ là đăng ký, chuông;
  - **Nội dung của người khác phải được biến đổi:** mỗi đoạn video ≤ 10–15 s, luôn có lời dẫn, bình luận, đồ hoạ riêng của kênh (mục 1.5); không ghép chuỗi clip của người khác không có lời dẫn; không tải lại trọn video, trọn bản tin của đài;
  - **Hình cũ, hình AI không giả làm hình thật hôm nay:** ảnh lưu trữ ghi chip «архив» (mục 1.7), ảnh AI ghi «иллюстрация» và bật `altered_content: true` khi trông như thật; không dựng AI người thật, không giả giọng người thật;
  - không chắc một tựa/thumbnail có gây hiểu lầm không → chọn phương án an toàn hơn và ghi lý do trong `metadata.md`.

  *(Nguồn gốc: người dùng yêu cầu, 2026-11-10: "không vi phạm luật lừa đảo, lách luật, spam của YouTube".)*
1.10 **Che logo, watermark của báo, đài, kênh** (bắt buộc, áp cho mọi ảnh, video thật và cả thumbnail):
  - **Khi xem từng file** (mục 1.5): ghi vị trí mọi logo, watermark, dải chữ có thương hiệu vào `5_footage/footage.json` trường `logo_mask`: `[{"x":…, "y":…, "w":…, "h":…, "t_in":…, "t_out":…, "what": "watermark kênh X"}]` (toạ độ pixel của file gốc; video: xem 4–6 khung và cả khung đầu/cuối đoạn dùng, logo có thể đổi chỗ hoặc chỉ hiện một lúc);
  - **Cách che, theo thứ tự ưu tiên:** (1) **cắt khung / zoom** bỏ hẳn vùng logo nếu không mất nội dung chính (logo ở góc, mép); (2) **làm mờ mạnh** vùng logo (ffmpeg `boxblur`/`gblur` theo vùng, hoặc `delogo`; ảnh: PIL GaussianBlur ≥ 25 px, có viền rộng hơn logo ~10 %); (3) **phủ đồ hoạ của kênh** (dải tít, chip, logo kênh mình) lên đúng vùng đó khi hợp bố cục. Không dùng ô màu thô khiến hình trông bị lỗi;
  - lưu bản đã che riêng: `sources/media/clean/<tên gốc>` (không ghi đè file gốc), cảnh dùng bản `clean/`; ghi cách che vào trường `method` của từng mục `logo_mask` trong `footage.json`;
  - logo chiếm phần lớn khung hoặc nằm giữa nội dung (ảnh share có khung báo, thẻ trích dẫn của báo, ảnh chụp màn hình trang báo) → **không dùng** hình đó;
  - **soát lại** bằng ảnh tĩnh của bản render (mục 7.2): không còn logo, watermark, tên báo, tên kênh nào nhìn thấy được, kể cả khi camera push-in/pan làm lộ vùng đã cắt; thumbnail cũng soát như vậy;
  - logo của **cơ quan nhà nước, quân đội, tổ chức là chủ thể của tin** (biểu tượng Минобороны trên video do chính Bộ công bố, cờ, quân hiệu, logo NATO trên bục phát biểu) là một phần của sự kiện, không phải thương hiệu báo chí: không bắt buộc che; watermark của báo/kênh đè lên video đó thì vẫn che.

  *(Nguồn gốc: người dùng yêu cầu, 2026-11-10.)*

## 2. Quy trình một video tin (6 bước)

Mỗi dự án có thư mục riêng:

```
project.json        app ghi: mô tả dự án, trạng thái các bước (đọc đầu tiên)
sources/            app ghi khi tạo dự án: news_NN_*.md (toàn văn từng tin), news.json, links.txt,
                    digest.md (Điểm tin 24h), media.json + media/ (ảnh, video thật của các tin; ảnh trong bài gốc: art_*)
1_script/           bước 1: research.md, sources.json, script.json, script.md
3_scenes/           bước 2: scenes.json, scenes.md
4_images/           bước 3: manifest.json, bảng xem nhanh sheet_*.jpg
5_footage/          bước 4: footage.json
6_render/           bước 5: render.json
7_metadata/         bước 6: metadata.json, metadata.md, captions.srt, thumbs/
film/               dự án Remotion app dựng từ engine (node_modules là liên kết dùng chung)
out/                các bản render, out/review/
notes/              costs.json (gen.py ghi), texts/ (văn bản gốc để so chuỗi), runs/ (nhật ký các lượt, app ghi)
```

Tên thư mục theo bố cục chung của app; video tin không có bước tuyển nhân vật nên không có `2_cast/`.

- **Kiểu video:** mục 2.8 (Tin nóng) hoặc 2.9 (Điểm tin 24h) quy định cấu trúc, nhịp, đồ hoạ riêng; các bước dưới là phần chung.
- **Trạng thái bước** (app quản lý): chưa tới → sẵn sàng → đang chạy → chờ duyệt → đã duyệt. Bước sau chỉ mở khi bước trước được duyệt. App kiểm tra file đầu ra sau mỗi lượt; thiếu file bắt buộc thì bước báo lỗi.
- **Mỗi bước chỉ làm việc của bước đó.** Không làm trước bước sau khi người dùng chưa bảo (dự án ở chế độ tự chạy thì app tự chuyển bước).
- Người dùng có thể nhắn chat bất kỳ lúc nào để chỉnh (mục 2.7).
- Các file JSON là JSON hợp lệ, UTF-8, đúng lược đồ mục 9: app đọc chúng để hiển thị. Đường dẫn file trong JSON luôn **tương đối với thư mục dự án**, dùng `/`.

### 2.1 Bước 1 · Kịch bản tin (`1_script/`)

- **Đầu vào:** `project.json`, `sources/news_*.md`, `sources/news.json`, `sources/digest.md` (Điểm tin), `sources/links.txt`. Một số trang chặn bot (ТАСС, BBC, УНИАН): tin đó chỉ có tóm tắt RSS, tự mở link gốc.
- **Làm:**
  1. Đọc toàn văn mọi tin; gộp tin trùng sự kiện; bỏ tin yếu chỉ có một nguồn không kiểm chứng được.
  2. Kiểm chứng từng tin theo mục 1.2. Ghi từng nguồn vào `sources.json` (kèm phía `side`, độ tin cậy), các khẳng định vào `claims` (`verified | disputed | unverified`). Khẳng định chưa kiểm chứng chỉ nói kèm chủ thể (mục 1.1).
  3. Xếp tin và viết lời dẫn theo kiểu video (mục 2.8 / 2.9):
     - giọng phát thanh viên trung tính, 125–135 từ/phút, câu ngắn kiểu báo chí;
     - mỗi tin mở bằng câu tít đọc riêng;
     - tối đa một tag trung tính đầu mỗi tin (`[serious]`), không dùng tag kịch tính;
     - **thời lượng: `target_sec` là mức tối thiểu, không phải con số phải khớp.** Tổng ≥ `target_sec`; dài hơn bao nhiêu tuỳ nội dung: viết bản hay nhất, đủ ý, đủ nhịp, không cắt bớt ý đắt chỉ để gói vào con số. Nhưng không độn (không lặp ý, không kéo dài lời dẫn, không thêm đoạn yếu để đủ giờ): mọi phút thêm phải giữ được người xem. Ghi `est_sec` thật và một câu lý do trong `research.md` khi vượt `target_sec` quá ~30%. Video dọc 9:16 muốn được YouTube xếp là Shorts thì không quá 180 s (mục 2.8).
  4. Mỗi beat: loại, tin (`story`), vai (`role`), thời lượng, lời dẫn, chữ trên hình, trích dẫn nguyên văn, ý tưởng hình (ảnh thật nào của tin), nguồn.
  5. So chuỗi mọi trích dẫn (mục 1.3). Ước tính chi phí giọng đọc: số ký tự × giá (mục 3).
- **Đầu ra:** `research.md` (tin chọn/bỏ và lý do, kết quả kiểm chứng, phương án tựa và chữ thumbnail), `sources.json` + `script.json` (mục 9.1), `script.md` (đọc được, chia theo tin, có thời lượng).
- **Cổng duyệt:** Duyệt = chốt danh sách tin và lời dẫn.

### 2.2 Bước 2 · Bảng hình (`3_scenes/`)

- **Đầu vào:** `script.json`, `sources/media.json` + `sources/media/`, ảnh trong bài gốc (mục 1.7).
- **Làm:**
  1. Chia lời dẫn thành cảnh. Mỗi tin 2–4 hình, đổi hình mỗi 8–15 s với bản tin dài (mục tiêu 4–8 lần/phút); Tin nóng theo mục 2.8.
  2. Mỗi cảnh ghi: tin (`story`), hình (`image` = file ảnh/video thật, hoặc bản đồ, thẻ chữ), đoạn video dùng (giây vào–ra), camera (mục 4), chữ trên hình, nhãn nguồn (mục 1.6), âm thanh, và chuyển cảnh, màu, chữ động tự chọn theo mục 4.6 (`transition`, `look`, `text_fx`).
  3. Hình theo thứ tự ưu tiên:
     1. **dùng hết** ảnh, video thật của chính tin đó (mục 1.7);
     2. bản đồ hoặc thẻ chữ, số liệu dựng bằng code (mục 4.4, 4.5);
     3. ảnh AI chỉ khi tin không còn hình thật nào dùng được (mục 1.7): ghi lý do.
  4. Ảnh cần tải thêm từ bài gốc: ghi vào `footage_needs` (`type: "archival"`, link bài).
  5. Ảnh AI (nếu có) vào `assets` với `est_usd` (mục 3); tổng ≤ ngân sách còn lại (`gen.py cost`).
- **Đầu ra:** `scenes.json` (mục 9.2), `scenes.md` (bảng cảnh theo tin: lúc, giây, hình, chữ, nhãn; danh sách ảnh AI và lý do).
- **Cổng duyệt:** Duyệt = duyệt hình của từng tin (và số tiền ảnh AI nếu có).

### 2.3 Bước 3 · Hình thật (`4_images/`, file trong `film/`)

- App đã dựng khung `film/` từ engine. `film/node_modules` là liên kết tới engine dùng chung: không `npm install`, **không bao giờ xóa** nó hay thứ gì bên trong.
- **Làm:**
  1. Tải ảnh trong thân các bài gốc (mục 1.7) vào `sources/media/art_<số tin>_<n>.<đuôi>`.
  2. Kiểm từng file theo mục 1.5 (ffprobe, xem khung, đúng sự kiện); che mờ thương vong, tù binh nhận diện được, mặt trẻ em.
  3. Chép hình dùng vào `film/public/img/media/` (video vào `film/public/clips/`); dựng bản đồ, thẻ chữ; ảnh AI đã duyệt bằng `gen.py image` (mục 3).
  4. Ghép bảng xem nhanh theo tin vào `4_images/sheet_<nhóm>.jpg` và tự xem.
- **Đầu ra:** `manifest.json` (mục 9.3), bảng xem nhanh.
- **Cổng duyệt:** người dùng xem bảng hình, bấm "Làm lại" hoặc nhắn bỏ hình chưa ưng, rồi Duyệt.

### 2.4 Bước 4 · Giọng đọc & âm thanh (`5_footage/`)

- **Làm:**
  1. Ghi mọi hình, đoạn video sẽ dùng vào `footage.json`: `type: "archival"`, `source_page` = link bài, `file`, `status: "downloaded"`, các cảnh. Hình ở nơi khác: `status: "proposed"`, chờ duyệt (mục 1.7). Hình có logo, watermark báo/kênh: ghi `logo_mask`, tạo bản che vào `sources/media/clean/` và trỏ `clean_file` tới đó (mục 1.10).
  2. **Lời dẫn** theo mục 6.2: một lần đọc cả bản tin, chọn bản bằng whisper, đặt câu theo cảnh (`audio/voice/plan.json` + `scripts/voice-build.py`).
  3. **Tiếng gốc** (nếu kiểu video có): cắt từ video của tin, chuẩn hoá về mức lời dẫn (mục 6.4).
  4. **Nhạc và hiệu ứng âm thanh** (mục 6.1); ghi kế hoạch vào `footage.json` (`music`).
- **Đầu ra:** `footage.json` (mục 9.4), file trong `film/audio/voice`, `film/public/clips`.
- **Cổng duyệt:** giọng đọc đã chọn, hình đủ thì Duyệt.

### 2.5 Bước 5 · Dựng & render (`6_render/`, `film/`, `out/`)

1. Đọc `film/ENGINE.md`. Dựng theo dữ liệu: một cảnh chung đọc `scenes/config.json` (sinh bằng script từ `scenes.json` + `manifest.json` + giọng đọc), không viết tay từng cảnh.
2. Hình, camera, chuyển cảnh theo mục 4; chữ và đồ hoạ theo mục 5 và kiểu video (2.8 / 2.9).
3. Đối chiếu từng nhãn nguồn và thẻ chữ với lời dẫn **của chính cảnh đó** trước khi dựng: `on_screen_text` của bước 2 có thể lệch một cảnh.
4. Soát ảnh tĩnh (mục 7), sửa. Âm thanh: trộn, master −15 LUFS (mục 6).
5. Render `out/<slug>_v<N>.mp4`. **Không ghi đè bản cũ**, mỗi lần render tăng N. **Render dài: theo đoạn, chạy tuần tự ngay trong lượt** (≈ 1 phút mỗi 30 s video). Một lệnh công cụ tối đa 10 phút, nên chia `npx remotion render … --frames=<từ>-<tới>` thành đoạn ~8.000 khung (~6–7 phút ở 1080p) vào `film/out/chunks/pNN.mp4`, chạy lần lượt từng đoạn (không `run_in_background`), rồi nối bằng ffmpeg concat `-c copy`. Đoạn đã có (mở được bằng ffprobe, đủ số khung) thì không render lại khi chạy tiếp. **Không bao giờ kết thúc lượt khi còn lệnh chạy nền**: lượt kết thúc là app coi bước đã xong, không có thông báo nào quay lại, tiến trình bỏ lại sẽ chết khi app khởi động lại. *(bài học từ phim tài liệu Giáo phái tổng hợp, 2026-10-14)*
6. QA (mục 7) trên chính file MP4, ghi `6_render/render.json` (mục 9.5) kèm kết quả QA và bảng ghép `out/review/contact_v<N>.jpg`.
- **Chỉ sửa âm thanh:** trộn lại tiếng rồi ghép vào hình bản trước bằng `-c:v copy`, không render lại hình; vẫn tăng số bản (v<N+1>).
- **Cổng duyệt:** người dùng xem; góp ý qua chat (2.7) thành bản v<N+1>. Duyệt = chốt bản cuối.

### 2.6 Bước 6 · Metadata YouTube (`7_metadata/`)

- **Đầu vào:** `script.json`, `sources.json`, `research.md` (phương án tựa, chữ thumbnail); `6_render/render.json` (bản cuối: file, thời lượng); mốc từng tin trong timeline của bản đó; lời dẫn có mốc chữ (`film/audio/voice/`).
- **Làm:**
  1. **Tin mới sau giờ chốt — kiểm lại MỘT lần, ngay khi metadata xong:** không tra trước, không giao agent chạy nền, không ngồi chờ. Viết tựa, thumbnail, mô tả theo kịch bản đã duyệt; dựng xong `metadata.json` (gate đạt) thì tra lại một lượt nhanh (≤ ~5 phút, tự làm trong lượt) chỉ câu hỏi/khẳng định của tựa, thumbnail và tin mở đầu, từ giờ chốt kịch bản tới lúc đó: Telegram chính thức của các bên có trong tựa, RSS hãng lớn (ТАСС, РИА, Интерфакс, Reuters, AP), mở bài gốc; không tra các chủ đề phụ của video. Tin chỉ cần còn đúng tới lúc đăng: có diễn biến trả lời hoặc làm cũ câu hỏi → chuyển sang phương án tựa/thumbnail phụ và thêm đoạn «Дополнение» (có chủ thể, không tên báo — mục 1.6) vào mô tả, báo người dùng; không có → ghi «đã kiểm tới HH:MM MSK, không có diễn biến mới» trong `metadata.md` rồi chốt. Hẹn giờ đăng xa hơn ~3 tiếng sau lúc chốt thì ghi rõ trong báo cáo để người dùng tự xem lại trước giờ đăng. *(Điểm tin 13.10.2026 tập 3: Сибига 13.10 nói Kyiv vẫn nhận tình báo Mỹ → thumbnail «БЕЗ РАЗВЕДКИ США?» thành phương án phụ.)*
  2. **Từ khóa:** cách khán giả gọi sự kiện (WebSearch, gợi ý tìm kiếm YouTube): 1 từ khóa chính, 5–10 từ khóa phụ; ghi nơi tra trong `metadata.md`.
  3. **Tiêu đề:** theo kiểu video (mục 2.8, 2.9), 3–5 phương án, vế khẳng định là tuyên bố có chủ thể (mục 1.1). Chọn một, nói lý do.
  4. **Mô tả** (ngôn ngữ của video, ≤ 5000 ký tự, không có `<` `>`): 2 dòng đầu là tin lớn nhất; chương mm:ss theo từng tin lấy từ timeline bản cuối (chương đầu 0:00, ≥ 3 chương, mỗi chương ≥ 10 s, tên chương = tít của tin); dòng nguồn chỉ ghi chung «Источники: официальные заявления сторон и открытые источники» — **không tên báo, hãng tin, không link bài, không link Telegram** (mục 1.6); 3 hashtag ở cuối; soát mục 1.9.
  5. **Thẻ:** tổng ≤ 500 ký tự (YouTube đếm cả dấu phẩy và 2 dấu ngoặc kép quanh thẻ có dấu cách); hashtag 3–5. Danh mục News & Politics, ngôn ngữ, `made_for_kids: false`, `altered_content: true` chỉ khi có ảnh AI trông như thật.
  6. **Phụ đề** `7_metadata/captions.srt` từ lời dẫn (mốc chữ ElevenLabs alignment hoặc whisper), ≤ 2 dòng mỗi khung (~42 ký tự/dòng: khung dài hơn thì tách đôi đúng mốc chữ đầu của nửa sau), khớp bản render cuối; đoạn tiếng gốc theo nguyên văn, ghi người nói.
  7. **Thumbnail** 1280×720, JPG < 2 MB, từ ảnh thật của tin (mục 1.7; Điểm tin theo mục 2.9), dựng bằng python (PIL) vào `7_metadata/thumbs/`; không vẽ AI giả người thật.
  8. **Giờ đăng:** `publish_at` = giờ công chiếu đề xuất, ISO 8601 có múi giờ (`2026-10-15T18:00:00+03:00`), trong tương lai, theo giờ khán giả xem nhiều (Điểm tin 24h: cùng một giờ mỗi ngày, mục 2.9); `visibility: "schedule"` (mặc định), hoặc `private` / `unlisted` / `public` khi người dùng bảo. `category` ghi đúng tên danh mục tiếng Anh của YouTube Studio (`News & Politics`, `Education`, `Film & Animation`…). Đánh `"chosen": true` cho thumbnail sẽ đăng.
- **Đầu ra:** `metadata.json` (mục 9.7), `metadata.md` (bản đọc: từ khóa + nơi tra, các phương án tiêu đề, mô tả hoàn chỉnh để dán, thẻ, chương, thumbnail và mốc phát của tin thumbnail, checklist đăng).
- **Cổng duyệt:** người dùng đọc, nhắn sửa, Duyệt = sẵn sàng đăng. Claude không tự đăng: **app** đăng qua profile GPM Login của kênh đã chọn cho dự án (khung 📺 Đăng YouTube ở bước này; tự đăng khi duyệt nếu dự án chọn chế độ tự đăng), lấy tiêu đề, mô tả, thẻ, thumbnail, danh mục, giờ đăng từ `metadata.json` và bản render cuối.

### 2.7 Sửa theo góp ý (chat)

- Tin nhắn chat kèm bước người dùng đang xem. Sửa đúng file của bước đó, soát lại đúng chỗ đã sửa (ảnh tĩnh hoặc cắt cận), báo cáo đã sửa gì và bằng chứng.
- Thay đổi ảnh hưởng các bước sau (ví dụ bỏ một tin khi đã có giọng đọc) thì nói rõ cần làm lại gì và tốn bao nhiêu tiền; chưa tự làm lại bước sau khi chưa được bảo.
- Góp ý mang tính nguyên tắc cho mọi video tin thì **ghi thành quy tắc** (mục 10).

### 2.8 Kiểu video «Tin nóng» (một sự kiện)

Áp dụng khi `sources/news.json` có `video_kind: "single"` (mặc định 9:16 · tối thiểu 60 s; muốn lên Shorts thì không quá 180 s). Bản đầu lấy từ khung «mỗi tin» của Điểm tin (mục 2.9), chưa thử trên video thật: sửa dần theo góp ý của người dùng.
- **Khung:** câu tít đọc ngay từ giây đầu, không chào → chủ thể của tuyên bố (mục 1.1) → 2–3 chi tiết, số liệu → một trích dẫn nguyên văn → phản hồi của phía kia nếu có → câu kết (điều còn chờ xác nhận, bước tiếp theo).
- **Hình:** toàn bộ là hình thật của tin (mục 1.7); video dọc ngắn đổi hình nhanh hơn bản tin dài (mỗi 3–6 s).
- **Chữ:** tít in hoa ở phần trên khung, phụ đề lời dẫn hộp tối (mục 5); tránh vùng nút của Shorts/TikTok (đáy ~20%, mép phải ~12% khung).
- **Metadata:** tựa ngắn (≤ 70 ký tự) nêu sự kiện và chủ thể; mô tả 2–3 câu, không tên báo (mục 1.6); 3 hashtag; soát mục 1.9.

### 2.9 Kiểu video «Điểm tin 24h» (bản tin tổng hợp)

Áp dụng khi yêu cầu riêng của dự án ghi **KIỂU VIDEO: ĐIỂM TIN 24H** (`video_kind: "digest"`). App ghi dòng này khi tạo dự án bằng nút 📰 Điểm tin 24h hoặc khi chọn kiểu này trong hộp Làm video. Công thức rút từ một bản tin tổng hợp tiếng Nga 16 phút, 180 nghìn view (Video Watcher, 2026-10-12). Giữ phần kịch bản và nhịp tin; bỏ phần hình tĩnh 2 phút không khớp lời, vì YouTube coi kiểu đó là nội dung lặp lại.

**Bước 1 · Kịch bản.** Đầu vào: `sources/digest.md` (các sự kiện xếp theo trọng tâm rồi số nguồn đưa tin), `sources/news_*.md`.
1. Chọn 14–20 sự kiện. Gộp tin trùng; bỏ tin yếu chỉ có một nguồn. Yêu cầu riêng có **TRỌNG TÂM ĐIỂM TIN** (ô Trọng tâm trên trang Tin theo dõi, ví dụ «ưu tiên tin về Putin, Zelensky») thì sự kiện **▶ TIN MỞ ĐẦU** trong `digest.md` (sát trọng tâm nhất) **bắt buộc phát đầu tiên** và là câu đầu của menu tiêu đề, hình đầu tiên của cold open cũng lấy từ tin này; chỉ đổi khi tin đó không kiểm chứng được, ghi lý do vào `research.md`. Các sự kiện ★ khác xếp ngay sau trong menu, ưu tiên làm tựa và thumbnail, kể dài hơn; tin khác kể ngắn.
2. Gán vai cho từng sự kiện:
   - **tin của tựa**: lớn nhất (có trọng tâm thì sát trọng tâm nhất), phát đầu tiên;
   - **tin của thumbnail**: xung đột trông thấy được, phát ở 40–50% thời lượng;
   - 2–3 tin trả các vế còn lại của tựa, đặt ở 55–70%;
   - **tin căng nhất** còn lại, đặt ở 75–85%;
   - một **tin nhẹ** (khoa học, chuyện lạ, có nguồn) trước lời tạm biệt;
   - các tin còn lại xen kẽ chiến trường và chính trị: không để 3 tin cùng loại liền nhau.
3. Khung beat (tổng ≥ `target_sec`, mục 2.1 bước 3; thời lượng từng phần dưới đây là nhịp gợi ý):

   | Beat | Thời lượng | Nội dung |
   |---|---|---|
   | `cold_open` | 6–10 s | Không đọc lời. Hình mạnh nhất của tin thumbnail + 2–3 hình của tin khác, mỗi hình 2–3 s, chuyển whip/zoom-blur, tiếng sting. |
   | Menu tiêu đề | 25–35 s | «Сегодня в выпуске.» + 6–8 tít × ~4 s. Mỗi tít là một câu sự kiện ≤ 10 từ, có thể thêm một câu cảm xúc ngắn có chủ thể. Tít của tin thumbnail nằm trong 3 câu đầu. Mỗi tít là một câu hỏi bỏ ngỏ, trả lời sau. |
   | Chào | ~10 s | Lời chào cố định: tên kênh + ngày + «собрали главные события за сутки… Начнём.» |
   | Mỗi tin | 30–75 s | Tít đọc như dòng tít → chủ thể của tuyên bố (cơ quan, người phát ngôn; không nêu tên báo, mục 1.6) → 2–3 chi tiết, số liệu → một trích dẫn nguyên văn → phản hồi của phía kia nếu có, hoặc câu kết. |
   | Tiếng thật | 10–15 s, một lần ở phút 2–4 | Trích đoạn tiếng gốc của nhân vật lớn từ video của tin (mục 1.5), để đổi giọng. Không có thì thay bằng trích dẫn trên thẻ chữ. |
   | «Немного юмора» | 10–20 s | Một câu nói lạ có thật, có nguồn. Không chế giễu nạn nhân. |
   | Tin nhẹ | 45–90 s | |
   | Lời tạm biệt | ~10 s | Câu cố định, hẹn «ровно через сутки». |
4. **Lời dẫn** theo mục 2.1 bước 3 (≈ 1.900–2.000 từ cho 15 phút; nhiều tin đáng kể thì dài hơn).
5. **`script.json`:**
   - mỗi tin là một hồi (`acts`: `T01`, `T02`…);
   - beat có thêm `"story"` (số thứ tự trong `digest.md`) và `"role"` (`title | thumbnail | title_2 | peak | light | regular`);
   - ghi vào `research.md` 3 phương án tựa và 2 phương án chữ thumbnail, kèm mốc phát của tin thumbnail.
6. **Kiểm chứng từng tin** theo mục 1.2 và 1.3 (agent song song).

**Bước 2–5 · Hình và dựng.** Phải đơn giản để làm được mỗi ngày.
- **Số hình:** mỗi tin 2–4 hình, đổi hình mỗi 8–15 s (mục tiêu 4–8 lần/phút); hình theo thứ tự ưu tiên ở mục 2.2.
- **Đồ hoạ cố định** (mục 5): logo kênh, dải tít mỗi khi vào tin mới, nhãn chỉ ghi chủ thể chính thức («Заявление: Минобороны РФ»), không tên báo (mục 1.6), phụ đề hộp tối.
- **Chuyển cảnh:** cắt cứng trong một tin; giữa hai tin whip/zoom-blur 0,3 s kèm tiếng whoosh ngắn (mục 4.3).
- **Âm thanh:** nhạc nền bản tin nhẹ, hạ dưới giọng; sting ở cold open và lời tạm biệt; master −15 LUFS (mục 6).

**Bước 6 · Metadata.**
- **Tựa:** ≤ 100 ký tự, 3 vế = 3 tin có trong video: `<sự kiện cụ thể dạng câu hỏi>? <ai> требуют/заявили <gì> — <hệ quả lớn>`. Mẫu từ bản gốc: «Топливный поезд уничтожен? Во Франции требуют прекратить финансирование Украины — Европа меняет курс». Vế khẳng định phải là tuyên bố có chủ thể (mục 1.1).
- **Thumbnail 1280×720:**
  - 2 mảng: trái là cảnh hành động của tin thumbnail (ảnh thật của tin, mục 1.7); phải là gương mặt, biểu cảm từ ảnh thật (không vẽ AI giả người thật);
  - nền gradient navy `#0e183c`, 2 từ in hoa trắng rất to (≈ 1/4 chiều cao) + vạch đỏ dọc, logo kênh; ảnh đã che logo báo/kênh (mục 1.10);
  - chữ thumbnail nói một tin khác với tựa, nhưng phải là tin có thật trong video và được trả ở 40–50%: ghi mốc phát trong `metadata.md`.
- **Mô tả:** 2 dòng đầu là 2 tin lớn nhất; mỗi tin một chương mm:ss (tên chương = tít của tin); không tên báo, hãng tin, không link bài, không link Telegram (mục 1.6).
- **Tin mới sau giờ chốt:** mục 2.6 bước 1.
- **Đăng:** mỗi ngày cùng giờ; tên kênh, lời chào và lời tạm biệt giống nhau mọi tập.

## 3. Nguyên liệu trả phí: giọng đọc, hiệu ứng âm thanh, ảnh AI (gen.py)

- **Công cụ:** một lệnh duy nhất `"$CREATER_PYTHON" "$GEN_PY" <lệnh>` (`<lệnh> --help` để xem tham số). Key do người dùng điền ở trang Cài đặt; gen.py tự đọc key, Claude không bao giờ thấy, hỏi hay ghi key.
  - `check`: key còn dùng được, gói và số ký tự ElevenLabs còn lại, số dư fal.
  - `cost`: dự án đã tiêu bao nhiêu so với ngân sách.
  - `tts`, `sfx`, `voices`: lời dẫn và hiệu ứng âm thanh (mục 6).
  - `image --prompt "…" --out film/assets/raw/<key>.png --what <key>` với `--model draft|nano2|openai|openai-mini|…`, `--aspect 16:9`, `--quality medium`: ảnh AI (chỉ khi mục 1.7 cho phép).
  - `run <model> --set k=v --file k=đường_dẫn --out …`: model khác của fal (phóng to ảnh nhỏ…). Xem tham số bằng `schema <model>`, giá bằng `price <model>`.
  - `--dry-run` in yêu cầu và giá ước tính mà không gửi.
- **Chi phí và ngân sách:** mỗi lần gọi thành công gen.py ghi vào `notes/costs.json` (mục 9.6). Trần mỗi dự án: `budget_usd` trong `project.json`. Lệnh làm vượt trần bị từ chối (mã thoát 3, "VƯỢT NGÂN SÁCH"): dừng phần đó, báo số tiền và hỏi người dùng; chỉ chạy lại với `--over-budget` khi người dùng đã đồng ý. Thiếu key (mã thoát 2): báo người dùng điền ở Cài đặt, không tìm đường khác.
- **Giá (2026-10):**

  | Việc | Model (alias) | Giá |
  |---|---|---|
  | Lời dẫn | ElevenLabs `eleven_v4` | $0,08/1.000 ký tự ≈ 1 phút đọc |
  | Nhạc nền, sting, whoosh | ElevenLabs sound generation | $0,12/phút |
  | Ảnh AI rẻ | `bytedance/seedream/v5/flash/text-to-image` (`draft`) · `fal-ai/nano-banana-2` (`nano2`) | $0,027 · $0,08/ảnh |
  | Ảnh AI gọi thẳng OpenAI | `openai` medium | đo được ≈ $0,011/ảnh 1536×1024 (dry-run ước cao gấp 3–6 lần: lập ngân sách theo dry-run, báo theo `gen.py cost`) |

- **Ảnh AI cho tin:** chất lượng medium là đủ; prompt kiểu ảnh báo chí, không người nhận ra được: *photorealistic editorial news illustration, documentary photo look, muted palette, no identifiable faces, no casualties, no blood, no text, no flags, no emblems*. Ghi «иллюстрация» trên hình (mục 1.7).
- **Gọi API:** tối đa 3 lệnh gen.py cùng lúc. Lỗi tạm (model bận, lỗi 5xx) thì chạy lại. Quá thời gian chờ thì **không gửi lại ngay** (có thể trả tiền hai lần): gen.py in request id, báo người dùng.
- **Video AI:** không dùng cho tin (hình phải là thật), trừ khi người dùng yêu cầu.

## 4. Hình và chuyển động

4.1 **Camera trên ảnh:** mọi ảnh có zoom hoặc lia chậm (8–12% mỗi hình), có easing vào/ra; không ảnh nào đứng im. Ảnh nhỏ hoặc khác tỉ lệ khung: đặt vừa khung, nền là chính ảnh đó làm mờ, không phóng to vỡ hình.
4.2 **Video của tin:** mỗi đoạn ≤ 10–15 s (mục 1.5). Clip ngắn hơn cảnh của nó thì khung cuối cảnh thành màn đen: giãn tốc độ phát (`playbackRate` ≥ ~0,8) hoặc nối thêm đoạn, và soát ảnh tĩnh ở **cuối** mọi cảnh video. *(Điểm tin 13.10.2026: video truyền đơn 12 s trong cảnh 14 s.)* Clip có tiếng (không được giãn) thì giữ khung đầu trong phần vào và khung cuối trong phần đuôi (`<Freeze>`). *(Tập 3: clip Trump, Синегубов.)*
4.3 **Chuyển cảnh** (Motion kit, mục 4.6): trong một tin cắt cứng (`cut`) hoặc `dissolve` ngắn; giữa hai tin `whip` hoặc `zoom` (~0,3–0,5 s) kèm whoosh ngắn; tin nóng, chấn động `flash`; tin lộ tài liệu, tin tặc, giám sát `glitch`; vào tin nhẹ hoặc lời tạm biệt `dissolve`/`dip`.
4.4 **Bản đồ: mặc định 3D kiểu Google Maps** (từ 17.10.2026). Mọi cảnh `"type": "map"` dựng bằng `film/src/digest/Map3D.tsx` (MapLibre GL, đã cài trong engine): nhìn vùng rộng thì nền đêm (đèn thành phố NASA VIIRS, địa hình nổi, sông, đường lớn, biên giới quốc tế OSM); máy quay bay vào từ trên cao rồi nghiêng ~55° quanh điểm nóng; cảnh dài có đúng một điểm nóng thì lao xuống mục tiêu (zoom ~13.6, nghiêng 62°): nền chuyển dần sang ảnh vệ tinh Sentinel-2 và nhà 3D dựng khối. Cảnh ngắn và nền menu đã nghiêng sẵn, chỉ trôi nhẹ; chiều xoay đổi theo cảnh. Địa danh tiếng Nga trong thẻ chữ, điểm nhấn đỏ (`claim`) / vàng (`event`) có sóng lan và ống ngắm; vùng hành chính (oblast) chứa điểm nóng tự tô sáng nếu không phủ quá 40 % khung và bản đồ không ở cấp thành phố.
  1. **Bộ mẫu:** chép `Map3D.tsx`, `MapView.tsx` vào `film/src/digest/` và `build_maps.py` vào `notes/tools/` từ `E:\Tool\Creater Vid\engine\templates\news-map\` (đọc `README.md` ở đó: component cần gì từ `theme`, `Overlays`, `Scene`); không tự viết bản đồ mới, không `npm install` trong `film/`. Chỉ sửa `MAPS`/`PLACES` trong `build_maps.py`, rồi chạy nó bằng `E:\Tool\bgremove\.venv\Scripts\python.exe` để sinh `film/src/digest/maps.json` và nền phẳng `film/public/img/maps/<bản đồ>.jpg` (Natural Earth dùng chung trong mẫu, tự tải nếu thiếu). Cấu hình cảnh ghi toạ độ px của `maps.json` (`points`, `cam`, `rings`, `zones`, `route`, `glabels`, `sea`, `border`); Map3D tự đổi ra kinh vĩ.
  2. **Khoá điều khiển từng cảnh:** `"dive": true|false` (lao xuống vệ tinh + nhà 3D; mặc định khi cảnh ≥ 180 khung, đúng một điểm `claim`/`event`, không có `quote`), `"fly": true|false` (bay vào từ trên cao; mặc định khi cảnh ≥ 150 khung), `"flat": true` (bản phẳng `MapView`).
  3. **Trung lập:** chỉ vẽ biên giới quốc tế; không vẽ đường «disputed / line of control» của Natural Earth hay OSM, không tô màu theo chủ quyền. Vùng kiểm soát chỉ khi có dữ liệu mở đã kiểm (`ds`, ghi giờ dữ liệu). Điểm lao xuống phải đúng toạ độ mục tiêu (sân bay, nhà máy…), không chỉ toạ độ trung tâm thành phố; ghi nguồn toạ độ trong docstring `build_maps.py`.
  4. **Bố cục:** cảnh có hộp trích dẫn giữa khung (`quote`) thì Map3D dời tâm nhìn xuống dưới hộp, nghiêng ít hơn, không lao xuống; vẫn soát ảnh tĩnh từng cảnh bản đồ (`node scripts/stills.mjs <khung>`, lấy cả khung cuối cảnh lao xuống) để chắc điểm, nhãn không lọt dưới hộp, phụ đề, panel.
  5. **Tile và dự phòng:** Map3D tải tile qua bộ đệm đĩa `scripts/tilecache.mjs` (cổng 5098, lưu ở `E:\Tool\Creater Vid\work\tilecache`, dùng chung mọi dự án), tự chạy kèm `npx remotion render` (qua `remotion.config.ts`) và `scripts/stills.mjs`; không xoá thư mục đệm. Lần đầu tải tile chậm hơn và có thể thiếu khối nhà ở vùng mới: soát ảnh tĩnh mọi cảnh bản đồ trước khi render (vừa kiểm vừa làm ấm bộ đệm), render lại đoạn có bản đồ thì nhanh ~2,5× và đủ tile. Mất mạng hoặc tile lỗi thì `"flat": true` cho cảnh đó → bản phẳng (nền địa hình + đèn đêm nướng sẵn, bờ biển phát sáng, vùng tô đỏ).
  6. **Ghi nguồn** góc dưới trái (tự có trong component): OpenStreetMap · OpenFreeMap · NASA (VIIRS) · Sentinel-2 cloudless 2016 by EOX (Copernicus) · AWS Terrain Tiles (bản phẳng: Natural Earth · NASA (ASTER, VIIRS)).
4.5 **Thẻ chữ, số liệu:** dòng ngắn, đọc kịp trong 3–5 s; soát ảnh tĩnh để chắc chữ không tràn mép thẻ.
4.6 **Bộ Motion kit (Claude tự chọn).** Engine có sẵn `src/kit` (cách dùng: `film/ENGINE.md` mục "Motion kit"; video mẫu: `E:\Tool\Creater Vid\engine\out\showcase\kit_showcase.mp4`). Claude tự chọn theo nội dung từng tin, không cần duyệt riêng; lựa chọn ghi vào `scenes.json` (mục 9.2). Phong cách tin: nhanh, sạch, đáng tin, không màu mè.
  - **Chuyển cảnh** theo mục 4.3; kiểu mạnh (`flash`, `glitch`, `zoom`) là điểm nhấn, không dùng liên tục, không hai lần liền nhau.
  - **Màu:** ảnh, video thật của tin **không** chỉnh tông điện ảnh (giữ đúng thực tế). Chỉ `archive` cho ảnh tư liệu cũ (lịch sử, nhắc lại sự kiện năm trước); `handheld` nhẹ (0,3–0,5) cho ảnh tĩnh hiện trường; `impact@<khung>` đúng khung tiếng nổ trong cảnh dựng. Không light leak, lens flare, duotone trên ảnh thật của tin.
  - **Chữ động** (`NEWS_THEME`, có chữ Kirin): `CountUp` con số chính của tin (thương vong, tiền, khoảng cách, phần trăm), đúng con số đã kiểm (mục 1.2); `Highlight` tô cụm số/từ then chốt trong thẻ chữ; `LowerThird` tên + chức vụ người phát ngôn lần đầu lên hình; `Typewriter` địa điểm + giờ sự kiện («БЕЛГОРОД · 14:20 МСК»); `Scramble` tin tài liệu rò rỉ, mật; `PunchWords` câu tít của cold open. Không trùng vùng với logo, dải tít, phụ đề, nhãn nguồn; soát ảnh tĩnh lúc chữ đang chạy.
  *(Nguồn gốc: 2026-10-20, người dùng thấy phim "khá đơn điệu" — Pyramids Under the Ice có 86 cảnh, cả 86 lần chuyển cảnh là mờ chéo 15 khung, chữ chỉ có phụ đề — muốn thêm hiệu ứng chuyên nghiệp, nghệ thuật cho cả hai loại video, và giao cho Claude tự chọn hiệu ứng hợp từng cảnh.)*

## 5. Chữ và đồ hoạ trên màn hình

5.1 **Logo kênh** ở góc trên trái, giống nhau mọi tập.
5.2 **Dải tít** mỗi khi vào tin mới, hiện 4–6 s: chữ in hoa sans-serif đậm cô đặc, trắng trên nền navy `#0e183c`, vạch đỏ dọc bên trái.
5.3 **Nhãn nguồn** ở góc trên phải chỉ ghi chủ thể chính thức: «Заявление: Минобороны РФ», «Кадры: Минобороны РФ», «Фото: ГСЧС Украины»; hoặc chung «Кадры из открытых источников». **Không bao giờ ghi tên báo, hãng tin, kênh** (mục 1.6). Nhãn, logo kênh mình có thể đặt đè lên vùng logo báo đã che (mục 1.10).
5.4 **Phụ đề lời dẫn:** chữ trắng sans-serif, ≤ 2 dòng, hộp đen mờ ~60%, giữa–dưới, viết hoa đầu câu, có dấu câu. Chữ trên hình = đúng chữ được đọc; chữ không che mặt.
5.5 **Font** có chữ Kirin: Oswald hoặc Roboto Condensed cho tít, Inter hoặc Roboto cho phụ đề.
5.6 Trích nguyên văn trên thẻ chữ đặt trong ngoặc «…» (tiếng Nga), kèm người nói và ngày.
5.7 **Chữ động** (số đếm, tô sáng cụm then chốt, tên người phát ngôn, địa điểm–giờ, chữ giải mã): bộ Motion kit, mục 4.6.

## 6. Âm thanh

6.1 **Nhạc và hiệu ứng** (ElevenLabs `gen.py sfx`, mục 1.8): nhạc nền bản tin nhẹ (lớp ≤ 22 s nối vòng có crossfade), sting ở mở đầu và lời tạm biệt, whoosh khi chuyển tin. Mỗi file đo độ to rồi cân theo LUFS; whisper nghe các lớp "không lời" để chắc không lọt chữ.
6.2 **Lời dẫn bằng giọng đọc** (ElevenLabs qua `gen.py tts`; làm theo `film/ENGINE.md` mục Narration):
  - Giọng theo ngôn ngữ của video, chọn ở trang Cài đặt (tên và id ghi ở đầu phiên). Đổi giọng thì hỏi người dùng. Giọng, lời chào giống nhau mọi tập.
  - Chi phí nằm trong ước tính của kịch bản: người dùng duyệt kịch bản là duyệt luôn chi phí giọng. Tối đa 3 bản đọc cho mỗi lượt viết lại lời dẫn; nhiều hơn thì hỏi.
  - **Đọc cả bản tin trong một lần** (một file văn bản, mỗi tin một đoạn liền, không cắt giữa câu theo cảnh), cùng giọng. `--takes N` tính tiền N bản.
  - Tag: tối đa một tag trung tính đầu mỗi tin (`[serious]`); không dùng tag cảm xúc kịch tính.
  - Chọn bản đọc bằng whisper: đủ chữ, không đọc lọt tag, nhịp vừa cảnh. Đặt câu bằng `audio/voice/plan.json` + `scripts/voice-build.py`; tăng tốc tối đa 3%. Cảnh không đủ chỗ cho câu đọc tự nhiên thì kéo dài cảnh, không đọc nhanh hơn.
  - `plan.json`: mỗi dòng audio phải dừng ở chỗ ngắt có khoảng lặng (thường một dòng mỗi cảnh) vì `voice-build` cắt theo khoảng lặng; phụ đề chia riêng từ mốc từng chữ (`src/captions.json`).
  - Mốc ElevenLabs ở ranh giới đoạn lệch theo **cả hai chiều** (chữ cuối đoạn trước có thể «kéo» sang khoảng nghỉ tới ~0,4 s; chữ đầu đoạn có thể trễ tới 0,6 s): tìm quãng lặng trong cửa sổ ±0,6 s quanh **cả hai** mốc. Quãng lặng < 0,3 s (hai đoạn đọc liền) thì cắt đúng giữa. Phụ âm xát đầu từ («С», «Ш») nhỏ dưới ngưỡng lặng: đo dB tại mọi điểm cắt, và whisper **từng file dòng** để chắc còn chữ đầu, chữ cuối. Sau `voice-build`: không dòng nào chồng dòng trước. *(Điểm tin 13.10.2026 tập 3: «США» đầu tin diesel bị cắt lẹm ở v1.)*
  - Whisper chạy cả file dài có thể **bỏ sót phần đuôi**: nghe theo đoạn ≤ 4 phút. Mốc từng chữ cho `voice-build` lấy từ `take.mp3.alignment.json` của ElevenLabs.
  - Chi phí giọng: báo đúng số `gen.py` ghi, kèm số ký tự quota ElevenLabs đã giảm.
6.3 **Trộn giọng:** `make-audio` tự hạ nhạc dưới giọng. Giọng phải nổi rõ trên nhạc (giọng hơn nhạc trung vị ~20 dB, ≥ 90% khung lời ≥ 10 dB trong dải 300–5000 Hz). `voiceOver` tính so với nhạc **đã hạ** (`duckHi`): tăng `voiceOver` và hạ `duckHi` cùng một lượng thì triệt tiêu nhau; muốn giọng nổi hơn thì tăng `voiceOver`/`clear`. *(Điểm tin 13.10 tập 3: `voiceOver` 12, `duckHi` −7, `clear` 13 → trung vị 19,9 dB, 92 % ≥ 10 dB.)*
6.4 **Tiếng gốc trong video của tin:** chuẩn hoá về mức lời dẫn (~−15,5 LUFS mỗi đoạn) trước khi trộn; QA đo riêng một đoạn tiếng gốc và một đoạn lời dẫn trên chính file MP4 (chênh ≤ ~2 LU).
6.5 **Master** −15 LUFS, true peak ≤ −1,5 dBTP; limiter chạy ở 4× tần số lấy mẫu; bản ghép cuối để trần ~−2,7 dBTP trước khi nén AAC. Tiếng clip do Remotion trộn không đi qua master: sau render, trộn lại cả video (soundtrack + từng đoạn tiếng gốc đã chuẩn hoá) rồi ghép vào hình (`-c:v copy`).

## 7. Kiểm tra trước khi giao (bắt buộc)

1. `npx tsc --noEmit -p .` không báo lỗi.
2. `node scripts/stills.mjs ...`: ảnh tĩnh ở đầu, giữa, cuối mỗi cảnh và ở mỗi lần chuyển cảnh; **tự xem** bảng ghép `out/stills/sheet.jpg`. Soát:
   - chữ không che mặt, dải tít và thẻ chữ không tràn mép;
   - nhãn nguồn đúng cảnh, đúng mục 1.6 (không tên báo, hãng tin, kênh);
   - **không còn logo, watermark, tên báo/kênh nào nhìn thấy được** (mục 1.10), kể cả lúc camera push-in/pan;
   - không còn thương vong, tù binh nhận diện được, mặt trẻ em chưa che;
   - không khung đen ở cuối cảnh video (mục 4.2);
   - hình đúng tin của nó (mục 1.7).
3. Render xong chạy `node scripts/qa.mjs out/<file>.mp4`: đủ số khung hình; không có đoạn đen giữa video; có tiếng; LUFS và peak đạt (`qa.mjs` có thể báo true peak NaN: đo lại bằng `ffmpeg -af ebur128=peak=true`); bảng ghép lấy từ **chính file MP4**; đo riêng độ to một đoạn tiếng gốc, một đoạn lời dẫn, phần mở đầu: chênh nhau ≤ ~2 LU. Có đoạn đen thì trích khung tại đó xem là đen thật hay cảnh tối, tìm nguyên nhân gốc.
4. So từng câu trích trên hình và trong lời dẫn với văn bản gốc (python, mục 1.3).
5. Lời dẫn:
   - whisper nghe lại file cuối **theo đoạn ≤ 4 phút**: đủ mọi câu, không sót đoạn ≥ 4 chữ;
   - bật `vad_filter=True`: whisper large-v3 không có VAD từng bỏ qua cả đoạn lời có nhạc nền (báo thiếu giả). Chỗ báo thiếu thì nghe riêng đoạn ngắn đó bằng một model khác, và đo năng lượng stem giọng trước khi kết luận là mất giọng *(Điểm tin 13.10.2026: menu 8–37 s)*;
   - giọng hơn nhạc ≥ 10 LU khi đang nói, trong dải 300–5000 Hz (đo `out/stem_voice.wav` với `out/stem_score.wav`).
6. Báo cáo đúng sự thật. Chưa kiểm được thì nói là chưa kiểm (ví dụ: Claude không nghe được giọng, chỉ đo được).

## 8. Giao tiếp với người dùng

- Trả lời bằng tiếng Việt, ngắn gọn, đi thẳng vào việc. Người dùng xưng "tao/mày".
- Mỗi lượt kết thúc bằng:
  - làm gì, file nào;
  - bằng chứng đã kiểm (con số, ảnh);
  - tiền nguyên liệu đã tiêu, USD (lượt này và cả dự án: `gen.py cost`);
  - giới hạn còn lại (nói thật);
  - việc người dùng cần làm ở cổng duyệt (bỏ hình, duyệt footage ngoài tin, bấm Duyệt), hoặc câu hỏi nếu cần người dùng quyết.
- Lỗi phát hiện ra thì nhận là lỗi, giải thích nguyên nhân gốc, sửa tận gốc (trong engine của video hoặc quy tắc) chứ không vá riêng một chỗ.
- Quyết định thuộc về người dùng (bỏ hay giữ tin nhạy cảm, tiêu tiền lớn) thì hỏi. Việc kỹ thuật có mặc định rõ ràng thì tự làm.
- Chạy headless thì không chờ người dùng giữa chừng: làm hết phần làm được, cuối lượt liệt kê câu hỏi.

## 9. Lược đồ file

Đường dẫn trong mọi file: tương đối với thư mục dự án, dấu `/`. `sources/news.json` và `sources/media.json` do app ghi: chỉ đọc.

### 9.1 Bước 1: `1_script/sources.json` và `1_script/script.json`
```json
{"sources": [{"id": "S1", "type": "web|telegram|statement|video|article", "title": "...", "author": "báo / cơ quan",
   "date": "2026-10-12 14:40 MSK", "url": "...", "file": "sources/news_01_....md", "side": "ru|ua|intl|indep",
   "reliability": "primary|journalism|opinion", "notes": "..."}],
 "claims": [{"id": "C1", "text": "...", "sources": ["S1"], "status": "verified|disputed|unverified", "note": "..."}]}
```
```json
{"title": "...", "logline": "...", "language": "ru", "format": "16:9", "target_sec": 900, "est_sec": 905,
 "video_kind": "single|digest", "title_options": ["..."], "thumbnail_texts": ["..."],
 "acts": [{"id": "T01", "title": "tít của tin", "story": 1, "role": "title"}],
 "beats": [{"id": "b04", "act": "T01", "type": "cold_open|menu|greeting|narration|quote|soundbite|outro",
   "story": 1, "role": "title|thumbnail|title_2|peak|light|regular", "duration_sec": 12,
   "narration": "lời dẫn đúng chữ sẽ đọc", "on_screen_text": "...",
   "quote": {"speaker": "...", "source": "S19", "text": "nguyên văn", "original": "bản gốc nếu là bản dịch", "verified_in": "notes/texts/x.txt"},
   "visual_idea": "ảnh thật nào của tin", "sources": ["S19"]}],
 "voice": {"name": "...", "voice_id": "...", "model": "eleven_v4", "chars": 13000, "est_usd": 1.04},
 "risks": ["..."], "open_questions": ["..."]}
```

### 9.2 Bước 2: `3_scenes/scenes.json`
```json
{"video_kind": "digest",
 "scenes": [{"id": "sc21", "story": 2, "beats": ["b07"], "title": "...", "duration_sec": 8.2,
   "image": "sources/media/clean/m12.jpeg", "clip": {"file": "sources/media/m07.mp4", "in": 3.0, "out": 12.0},
   "visual": "archival|map|card|ai", "camera": "push-in 8%", "source_label": "Заявление: Минобороны РФ",
   "on_screen_text": "...", "narration": "...", "fx": ["whip vào tin"], "sound": ["whoosh"]}],
 "assets": [{"key": "ill_x", "kind": "plate", "model": "openai", "quality": "medium", "aspect": "16:9",
   "prompt": "...", "why": "tin 9 không có ảnh thật", "est_usd": 0.07}],
 "footage_needs": [{"id": "art_16", "type": "archival", "desc": "ảnh trong bài gốc của tin 16", "source_page": "https://...", "scenes": ["sc34"]}],
 "budget": {"est_usd": 1.4, "budget_usd": 5}}
```
`assets` chỉ cho ảnh AI (app cộng `est_usd` để so ngân sách); không có `locations`, nhân vật.

Mỗi cảnh thêm (mục 4.6): `"transition": "dissolve|cut|dip|flash|leak|whip|zoom|wipe|iris|blinds|glitch"` (cách cảnh đó **vào**), `"look": {"grade": "none|teal-orange|bleach|warm|cold|archive|noir|duotone", "feel": ["handheld", "impact@92", "leak", "flare@0.54,0.60", "chroma", "archive"]}` (`@` = khung trong cảnh / toạ độ nguồn sáng), `"text_fx": [{"kind": "MaskTitle|ChapterCard|LowerThird|Typewriter|Scramble|CountUp|PunchWords|PullQuote|Highlight", "text": "...", "at": 1.5, "dur": 4}]`. `scenes.md` có cột «Chuyển cảnh · màu · chữ động».

### 9.3 Bước 3: `4_images/manifest.json`
```json
{"assets": [{"key": "m01", "kind": "archival|map|card|plate", "status": "done|failed|redo|pending",
   "raw": "sources/media/m01.webp", "file": "film/public/img/media/m01.webp", "size": [1280, 790],
   "scenes": ["sc07"], "blurred": false, "usd": 0, "note": "ảnh thật"}],
 "sheets": ["4_images/sheet_media.jpg"]}
```
Thẻ chữ, bản đồ **dựng bằng code** không có file ảnh: `"file"` trỏ vào dữ liệu vẽ ra nó kèm `#<cảnh>` (vd. `"film/src/digest/config.json#sc12"`), app chỉ kiểm file dữ liệu đó có tồn tại; người dùng xem chúng trong các bảng `4_images/sheet_scenes_*.jpg` (ghi vào `sheets`).

### 9.4 Bước 4: `5_footage/footage.json`
```json
{"items": [{"id": "m01", "type": "archival|soundbite|music|sfx", "title": "...", "source_page": "https://...",
   "license": "dùng dạng đưa tin, có bình luận; logo báo/kênh đã che (mục 1.10)", "duration_sec": 12, "resolution": "1280x790",
   "status": "proposed|approved|downloaded|processed|generated|rejected", "file": "sources/media/m01.webp",
   "logo_mask": [{"x": 1120, "y": 24, "w": 140, "h": 60, "t_in": 0, "t_out": 12, "what": "watermark kênh", "method": "crop|blur|overlay"}],
   "clean_file": "sources/media/clean/m01.webp", "scenes": ["sc07"], "note": "..."}],
 "voice": {"voice": "...", "takes": [{"file": "film/audio/voice/take1.mp3", "usd": 1.0, "chosen": true}],
   "plan": "film/audio/voice/plan.json"},
 "music": {"approach": "ElevenLabs sfx: nền bản tin + sting + whoosh", "notes": "..."}}
```

### 9.5 Bước 5: `6_render/render.json`
```json
{"versions": [{"file": "out/<slug>_v1.mp4", "created": "2026-10-13T19:19:00", "duration_sec": 964.6,
   "qa": {"ok": true, "lufs": -15.0, "true_peak": -2.5, "frames": 28938, "black": [], "notes": "..."},
   "sheet": "out/review/contact_v1.jpg", "changes": "bản đầu"}]}
```

### 9.6 `notes/costs.json` (gen.py ghi, chỉ đọc)
```json
{"total_usd": 1.2, "budget_usd": 5,
 "events": [{"at": "...", "step": "footage", "kind": "image|video|tts|sfx|fal", "provider": "fal|elevenlabs|openai",
   "model": "...", "what": "voice", "usd": 1.0, "estimated": false, "files": ["film/audio/voice/take1.mp3"], "request_id": "..."}]}
```

### 9.7 Bước 6: `7_metadata/metadata.json`
```json
{"title": "...", "title_options": [{"title": "...", "why": "..."}],
 "keywords": [{"term": "...", "role": "main|secondary", "evidence": "gợi ý tìm kiếm YouTube"}],
 "description": "dòng 1\ndòng 2\n...\n0:00 ...", "chapters": [{"time": "0:00", "title": "tít của tin"}],
 "tags": ["..."], "hashtags": ["#..."], "category": "News & Politics", "language": "ru",
 "made_for_kids": false, "altered_content": false, "captions": "7_metadata/captions.srt",
 "thumbnails": [{"file": "7_metadata/thumbs/thumb_a.jpg", "text": "...", "story": 7, "plays_at": "7:41", "chosen": true, "why": "..."}],
 "visibility": "schedule|private|unlisted|public", "publish_at": "2026-10-15T18:00:00+03:00",
 "video": "out/<slug>_v<N>.mp4", "notes": "..."}
```
`7_metadata/upload.json` (app ghi khi đăng, chỉ đọc): trạng thái, link video, giờ lên lịch, nhật ký.

## 10. Nhật ký quy tắc (cập nhật mỗi khi người dùng sửa)

Cách cập nhật: sửa đúng mục liên quan ở trên (ngắn gọn, có lý do), rồi thêm một dòng vào đây theo dạng `YYYY-MM-DD · dự án · thay đổi`. Muốn **xóa** quy tắc thì phải hỏi người dùng. Chỉ ghi quy tắc cho video tin tức; điều chỉ đúng với phim tài liệu thuộc bộ quy tắc phim tài liệu.

*Trước 2026-10-14 tin tức và phim tài liệu dùng chung một bộ quy tắc; các dòng dưới đây là những thay đổi của phần tin tức trong bộ chung đó, ghi theo số mục mới.*

- 2026-10-06 · Creater Vid · Ảnh, video từ tin (Telegram, báo) thành danh sách `sources/media.json`; chỉ dùng mục đã tải, xem kỹ từng file, đoạn ngắn có bình luận, không cảnh thương vong hay tù binh nhận diện được → mục 1.5.
- 2026-10-12 · Creater Vid · Thêm kiểu video **Điểm tin 24h** (bản tin tổng hợp từ mục Tin tức, nút 📰), công thức rút từ một bản tin tiếng Nga 180 nghìn view qua Video Watcher: giữ kịch bản và nhịp tin, thay hình tĩnh không khớp lời bằng hình theo từng tin → mục 2.9.
- 2026-10-13 · Điểm tin 24h 13.10.2026 · Rút từ lỗi tự soát ở bước 1: kiểm chứng từng tin bằng thông cáo gốc và phiên bản phía bên kia; không dẫn bản kể lại của milblogger, không dẫn đoạn tóm tắt của công cụ tìm kiếm; đổi giờ máy về giờ Moskva/Kyiv → mục 1.2.
- 2026-10-13 · Điểm tin 24h 13.10.2026 · Rút từ lỗi tự soát ở bước 5–6: kiểm file video app tải bằng ffprobe (bản cụt 12 MB), tải lại từ trang nhúng; clip ngắn hơn cảnh → giãn tốc độ, soát khung cuối; whisper kiểm video cuối bật VAD và kiểm chéo chỗ báo thiếu → mục 1.5, 4.2, 7.5.
- 2026-10-13 · Creater Vid · Trước khán giả không nêu tên kênh Telegram, chỉ nêu báo, hãng tin nổi tiếng; tuyên bố của một bên vẫn nói rõ bên nào; thêm ô **Trọng tâm điểm tin** → mục 1.6, 2.9.
- 2026-10-13 · Creater Vid · Video tin dùng hết ảnh, video thật của các tin (app tự duyệt và tải; Claude lấy thêm ảnh trong bài gốc), không bận tâm Content ID (người dùng tự edit), ảnh AI chỉ khi tin không có ảnh thật → mục 1.5, 1.7, 2.9.
- 2026-10-13 · Điểm tin 24h 13.10.2026 (tập 3) · Rút từ lỗi tự soát ở bước 1: lời dẫn «theo cơ quan X» phải so với thông cáo của chính X, đọc bản mới nhất của bài gốc (đính chính); trích dịch so chuỗi với nguyên văn gốc → mục 1.2, 1.3.
- 2026-10-13 · Điểm tin 24h 13.10.2026 (tập 3) · Rút từ lỗi tự soát ở bước 5–6: xem trước nội dung hình trước khi gán (ảnh «Kyiv» hoá ra Харьков, clip thiếu câu trích); cắt giọng ở quãng lặng quanh cả hai mốc chữ, cắt giữa khi đọc liền, whisper từng file dòng («США» bị cắt lẹm ở v1); clip có tiếng giữ khung đầu/cuối; `voiceOver` và `duckHi` triệt tiêu nhau → mục 1.5, 4.2, 6.2, 6.3.
- 2026-10-13 · Điểm tin 24h 13.10.2026 (tập 3) · Rút từ lỗi tự soát ở bước 7 (nay là bước 6): tin mới sau giờ chốt (Сибига) trả lời câu hỏi của thumbnail → tra lại tin của tựa/thumbnail, thêm «Дополнение»; YouTube đếm ngoặc kép trong thẻ; khung phụ đề dài tách theo mốc chữ → mục 2.6.
- 2026-10-14 · Creater Vid · Người dùng yêu cầu tách hẳn hai mảng: video tin tức và phim tài liệu là hai dạng khác nhau, mỗi dạng một bộ quy tắc riêng, không áp chung. Bộ quy tắc này tách từ bộ chung v25: giữ mọi quy tắc tin tức (1.11–1.13, 2.9 cũ → 1.5–1.7, 2.9), viết lại phần chung cho tin (0, 1.1–1.4, 1.8, 2, 3–9); quy trình riêng 6 bước, bỏ bước tuyển nhân vật (kịch bản tin → bảng hình → hình thật → giọng đọc & âm thanh → dựng & render → metadata). Mục 2.8 «Tin nóng» là bản đầu, chưa thử trên video thật.
- 2026-10-14 · Creater Vid · Người dùng yêu cầu tự đăng YouTube qua profile GPM Login: metadata thêm `publish_at`, `visibility`, `category` đúng tên trong Studio, thumbnail `chosen`; app (không phải Claude) đăng → mục 2.6, 9.7.
- 2026-10-14 · Creater Vid · Người dùng yêu cầu: thời lượng chọn khi tạo dự án là **mức tối thiểu** (VD 1200 s = từ 1200 s trở lên), kịch bản tối ưu cho hay nhất, không bắt buộc gói gọn → mục 2.1, 2.8, 2.9.
- 2026-10-15 · Điểm tin 24h 14.10.2026 · Thẻ chữ dựng bằng code bị app báo «không thấy file»: quy ước `file` = dữ liệu vẽ + `#cảnh`, xem qua bảng ghép → mục 9.3.
- 2026-10-15 · Creater Vid · Render theo đoạn, tuần tự trong lượt; không kết thúc lượt khi còn lệnh chạy nền (lỗi ở dự án phim tài liệu Giáo phái tổng hợp) → mục 2.5.
- 2026-10-17 · Điểm tin 24h 16.10.2026 · Người dùng chọn: bản đồ phẳng navy sơ sài → mọi cảnh bản đồ dựng 3D bằng MapLibre (đèn đêm, địa hình, bay vào + nghiêng), bản phẳng nâng cấp làm dự phòng `flat`; chỉ vẽ biên giới quốc tế → mục 4.4.
- 2026-10-17 · Điểm tin 24h 16.10.2026 · Người dùng chọn bản đồ 3D «giống Google Maps» mức 1: giữ nền đêm khi nhìn rộng, lao xuống mục tiêu thì ảnh vệ tinh Sentinel-2 + nhà 3D; bộ mẫu chuyển vào `engine/templates/news-map`, maplibre cài trong engine → mục 4.4.
- 2026-10-17 · Điểm tin 24h 17.10.2026 · Render v2 chậm (đoạn 1 quá 10 phút) vì mỗi tab Chrome tự tải lại tile bản đồ 3D → bộ đệm tile trên đĩa trong engine; đo cảnh 445 khung: 116 s → 47 s khi đệm ấm, hết thiếu khối nhà → mục 4.4.
- 2026-10-20 · Điểm tin 24h 19.10.2026 (2) · Người dùng góp ý: bước 6 mất ~40 phút vì agent nền tra 7 chủ đề sau giờ chốt mà Claude chính ngồi chờ (viết metadata chỉ ~5 phút) → không agent nền, không chờ; dựng xong metadata thì tự kiểm lại một lượt nhanh (≤ ~5 phút) chỉ tin của tựa/thumbnail/tin mở đầu, tin chỉ cần còn đúng tới lúc đăng → mục 2.6.
- 2026-11-03 · Creater Vid · Người dùng yêu cầu: tin sát từ khóa ô Trọng tâm nhất phải phát đầu tiên để thu hút người xem → app xếp hạng độ sát, đánh dấu ▶ TIN MỞ ĐẦU trong `digest.md`, tin này bắt buộc mở video và mở menu tiêu đề → mục 2.9.
- 2026-10-20 · (chung hai loại video) · Người dùng muốn hiệu ứng chuyên nghiệp hơn cho mọi video, Claude tự chọn hợp từng cảnh → bộ Motion kit trong engine (`src/kit`, ENGINE.md "Motion kit"): chuyển cảnh, chữ động, cảm giác máy; tin tức giữ đúng màu ảnh thật → mục 4.3, 4.6, 5.7, 2.2, 9.2.
- 2026-11-10 · Creater Vid · Người dùng yêu cầu: không vi phạm chính sách spam, lừa đảo, gây hiểu lầm của YouTube; bỏ hoàn toàn tên mọi báo, hãng tin, kênh (kể cả báo lớn) khỏi lời dẫn, chữ trên hình, nhãn và metadata — tên riêng như Путин, НАТО vẫn dùng; vẫn dùng ảnh thật của báo nhưng bắt buộc che logo, watermark báo/kênh → mục 1.6, 1.7, 1.8, 1.9 (mới), 1.10 (mới), 2.4, 2.6, 2.8, 2.9, 5.3, 7.2, 9.2, 9.4.
