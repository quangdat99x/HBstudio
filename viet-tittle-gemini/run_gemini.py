"""Chạy skill viet-tittle bằng Gemini API (thay cho Claude) để so sánh output.

Gemini chỉ làm Bước 0–3 (phân tích, title, description, timestamps, tags,
kế hoạch thumbnail bằng chữ). Bước 4 (dựng mock + Canva) cần công cụ trên máy
nên bỏ qua.

API key: biến môi trường GEMINI_API_KEY, hoặc file .env cạnh script này
(dòng GEMINI_API_KEY=...).

Ví dụ:
  python -X utf8 run_gemini.py --cutlist "K:\\YouTube\\cutlist_JRE-2568.json" --rank 3
  python -X utf8 run_gemini.py --list-models
"""
import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILL = Path.home() / ".claude/skills/synced/0e035aae-cb33-43d2-accd-2bc2948e3e9d_b08d1a3b-94b2-4652-8190-ce14b840f358/viet-tittle/SKILL.md"
API = "https://generativelanguage.googleapis.com/v1beta"

NOTE = """

---

## GHI CHÚ KHI CHẠY QUA API (không có công cụ máy tính)

Bạn đang chạy qua API, KHÔNG có Canva, không đọc được video, không chạy được
script trên máy. Vì vậy:
- Làm đầy đủ Bước 0, 1, 2, 3 đúng như skill yêu cầu.
- Bước 3: ô giữa ghi subject + gợi ý nguồn ảnh (dùng Google Search nếu cần);
  ô trái/phải chỉ ghi biểu cảm cần tìm + khoảng thời gian (theo clip) có khả năng
  có biểu cảm đó, dựa vào transcript.
- BỎ QUA Bước 4 (mock + Canva), chỉ ghi một dòng "Bước 4: bỏ qua (chạy qua API)".
- Có thể dùng Google Search để kiểm chính tả tên riêng.
- Không hỏi lại người dùng: thiếu gì thì ghi ⚠️ rồi làm tiếp.
"""


def load_key():
    key = os.environ.get("GEMINI_API_KEY")
    env = HERE / ".env"
    if not key and env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("GEMINI_API_KEY="):
                key = line.split("=", 1)[1].strip().strip('"')
    if not key:
        sys.exit(f"Thiếu GEMINI_API_KEY (biến môi trường hoặc {env})")
    return key


def call(path, key, body=None):
    req = urllib.request.Request(
        f"{API}/{path}",
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Content-Type": "application/json", "x-goog-api-key": key},
    )
    try:
        with urllib.request.urlopen(req, timeout=600) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        sys.exit(f"HTTP {e.code}: {e.read().decode('utf-8', 'replace')[:2000]}")


def hms(sec):
    sec = int(sec)
    return f"{sec // 3600:02d}:{sec % 3600 // 60:02d}:{sec % 60:02d}"


def to_sec(t):
    h, m, s = (int(x) for x in t.split(":"))
    return h * 3600 + m * 60 + s


def build_prompt(cutlist_path, rank):
    cut = json.loads(Path(cutlist_path).read_text(encoding="utf-8"))
    seg = next((s for s in cut["segments"] if s.get("rank") == rank), None)
    if not seg or seg.get("kind") == "hook":
        sys.exit(f"rank {rank} không phải đoạn highlight trong cutlist")
    tr_path = Path(cutlist_path).parent / (Path(cut["episode"]["source_video"]).stem + ".transcript.json")
    tr = json.loads(tr_path.read_text(encoding="utf-8"))
    a, b = to_sec(seg["start"]), to_sec(seg["end"])
    lines = [f"[{hms(x['start'])}] {x['text'].strip()}" for x in tr["segments"] if a - 2 <= x["start"] <= b]
    ep_name = Path(cut["episode"]["source_video"]).stem
    cut_view = {"episode": cut["episode"], "segment": seg}
    return seg, (
        f"chạy wf VIẾT TITTLE\n\n"
        f"Tập: {ep_name}\n"
        f"Thời gian: {seg['start']} → {seg['end']}\n\n"
        f"### Cutlist (đoạn đang xử lý)\n```json\n{json.dumps(cut_view, ensure_ascii=False, indent=1)}\n```\n\n"
        f"### Transcript (timestamp gốc của tập)\n" + "\n".join(lines)
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cutlist")
    ap.add_argument("--rank", type=int)
    ap.add_argument("--model", default="gemini-2.5-pro")
    ap.add_argument("--no-search", action="store_true", help="tắt Google Search grounding")
    ap.add_argument("--list-models", action="store_true")
    ap.add_argument("--out", help="file .md kết quả (mặc định: outputs/<tập>_<rank>_<model>.md)")
    args = ap.parse_args()
    key = load_key()

    if args.list_models:
        for m in call("models?pageSize=200", key).get("models", []):
            if "generateContent" in m.get("supportedGenerationMethods", []):
                print(m["name"].removeprefix("models/"), "-", m.get("displayName", ""))
        return
    if not (args.cutlist and args.rank):
        ap.error("cần --cutlist và --rank")

    seg, prompt = build_prompt(args.cutlist, args.rank)
    body = {
        "systemInstruction": {"parts": [{"text": SKILL.read_text(encoding="utf-8") + NOTE}]},
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.7},
    }
    if not args.no_search:
        body["tools"] = [{"google_search": {}}]

    t0 = time.time()
    res = call(f"models/{args.model}:generateContent", key, body)
    took = time.time() - t0
    cand = res.get("candidates", [{}])[0]
    text = "".join(p.get("text", "") for p in cand.get("content", {}).get("parts", []))
    usage = res.get("usageMetadata", {})

    ep = Path(args.cutlist).stem.removeprefix("cutlist_")
    out = Path(args.out) if args.out else HERE / "outputs" / f"{ep}_{args.rank}_{args.model}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        f"<!-- model={args.model} · {took:.0f}s · tokens in={usage.get('promptTokenCount')} "
        f"out={usage.get('candidatesTokenCount')} think={usage.get('thoughtsTokenCount')} · "
        f"finish={cand.get('finishReason')} · đoạn: {seg['title']} -->\n\n{text}\n",
        encoding="utf-8",
    )
    (out.with_suffix(".prompt.txt")).write_text(prompt, encoding="utf-8")
    print(f"OK {took:.0f}s · tokens in={usage.get('promptTokenCount')} out={usage.get('candidatesTokenCount')} → {out}")


if __name__ == "__main__":
    main()
