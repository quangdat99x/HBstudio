ĐỊNH DẠNG ĐẦU RA CỦA STUDIO (bắt buộc, THAY cho mọi phần "xuất cutlist" / "format đầu ra" của skill nếu khác):
Skill ở trên quyết định CHỌN ĐOẠN NÀO và VÌ SAO (gu nội dung, tiêu chí, thời lượng, cách cắt). Còn cách IN phân tích
và cách GHI file thì theo đúng mục này, vì Studio đọc tự động.

A. HỒ SƠ KHÁCH MỜI: in một khối mở đầu bằng dòng `HỒ SƠ KHÁCH MỜI` (nếu skill có Guest Card thì in đúng format của
skill dưới tiêu đề đó; skill không có thì 5–8 dòng: danh tính, chuyên môn chính, khán giả đến nghe họ vì điều gì).

B. PHÂN TÍCH TỪNG ĐOẠN: mỗi đoạn highlight in MỘT LẦN, theo content_rank tăng dần, đúng khung:

N. **Tiêu đề ngắn tiếng Việt hoặc tiếng Anh**
Start: (hh:mm:ss) "câu nguyên văn mở đầu đoạn"
End: (hh:mm:ss) "câu nguyên văn kết đoạn"
**Tóm tắt:** 2–4 câu tiếng Việt, viết thẳng, có tên riêng.
**Tại sao đoạn này đắt:** lý do theo tiêu chí của skill.
**HOOK COLD OPEN:** 1–2 lát, mỗi lát một dòng `(hh:mm:ss – hh:mm:ss) "câu nguyên văn" — loại hook`
**Keyword hạt nhân:** `cụm tìm kiếm tiếng anh` · Reach R1|R2|R3 · KGC high|medium

(N = content_rank, 1 = hay nhất. Có thể thêm dòng/mục riêng của skill vào giữa, nhưng giữ đủ các dòng trên.)

C. CUTLIST: MỘT file JSON (đường dẫn ở phần YÊU CẦU), layout `flat_hooks`: hook và highlight chung một mảng
`segments[]`; với mỗi đoạn theo content_rank tăng dần, đẩy 1–2 hook của nó vào TRƯỚC rồi mới tới chính đoạn đó.

```json
{
  "version": 2,
  "cutlist_layout": "flat_hooks",
  "source": "<tên skill>",
  "episode": {
    "id": "<episode_id>",
    "guest": "<tên khách>",
    "source_video": "<tên file video>",
    "guest_profile": {"identity": "1 câu tiếng Việt", "expertise_tier1": ["..."], "audience_wants": ["..."],
                      "audience_ignores": ["..."], "confidence": "Cao|Trung bình|Thấp"}
  },
  "segments": [
    {"rank": 1, "kind": "hook", "parent_rank": 2, "hook_rank": 1, "start": "00:28:12", "end": "00:28:24",
     "duration_sec": 12, "title": "HOOK 01 — <title đoạn cha>", "summary_vi": "1 câu",
     "hook_type": "shock_claim", "is_segment_opening": false, "quote_en": "nguyên văn", "hook_en": "nguyên văn (= quote_en)",
     "summary_en": "1 câu: vì sao giữ chân người xem 10 giây đầu", "core_keyword": "<của đoạn cha>",
     "topics": ["<của đoạn cha>"], "value_axis": "<của đoạn cha>"},
    {"rank": 2, "kind": "highlight", "content_rank": 1, "start": "00:21:54", "end": "00:35:41",
     "title": "Tiêu đề ngắn cho Cutter", "summary_vi": "1 câu tiếng Việt viết thẳng",
     "hooks": [{"rank": 1, "flat_rank": 1, "start": "00:28:12", "end": "00:28:24", "duration_sec": 12,
                "quote_en": "nguyên văn", "type": "shock_claim", "is_segment_opening": false, "why": "1 câu tiếng Anh"}],
     "core_keyword": "cụm người ta gõ tìm, chữ thường", "keyword_reach": "R3", "keyword_credibility": "high",
     "keyword_reason": "1–2 câu tiếng Anh", "satellite_keywords": [], "topics": ["2–5 cụm tiếng Anh"],
     "hook_en": "câu Start nguyên văn", "summary_en": "1–2 câu tiếng Anh", "intensity": 8,
     "value_axis": "authority|persona|story|...", "cq": 8, "gtf": 9, "final_score": 7.2,
     "fit_reason": "1 câu tiếng Anh"}
  ]
}
```

Luật của file:
1. `rank` liên tục 1..N theo vị trí trong mảng, tính cả hook. Mọi entry có `kind` (`hook`|`highlight`) và `title`.
2. Entry hook: `parent_rank` = rank của highlight đứng ngay sau nhóm hook; `title` bắt đầu `HOOK 01 — ` hoặc
   `HOOK 02 — `; dài 5–25 giây; nằm TRỌN trong [start, end] của đoạn cha; `hook_type` ∈ shock_claim · fact_bomb ·
   story_teaser · curiosity_question · conflict. Không khai cq/gtf/final_score/content_rank/hooks trên entry hook.
3. Entry highlight: `content_rank` tăng dần theo thứ tự xuất hiện; `hooks[]` lồng khớp tuyệt đối với các entry hook
   phẳng (start, end, duration_sec, quote_en, type, is_segment_opening). Skill không có thang CQ/GTF thì tự chấm 1–10
   theo tiêu chí của skill, `final_score` = cq × gtf / 10.
4. Timestamp `hh:mm:ss` tra thẳng từ transcript, không ước lượng.
