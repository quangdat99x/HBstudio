"""Video tổng hợp: one highlight the user picked becomes the opening of a long compilation on the same topic.

1. topic    : Claude reads the seed highlight (title, summary, transcript) and names the topic + English filter keywords.
2. scan     : the keyword filter of topic_scan runs over EVERY full transcript (free, local), Claude reads only the
              windows around the hits (in batches, no tools) and returns self-contained passages on the topic.
3. arrange  : Claude builds the arc. The seed is clip 1, the related passages follow as an escalating story, total
              length ≈ the duration the user asked for (30, 60, 90 min...). It writes the narration in English as
              ElevenLabs v3 prompts (audio tags): an intro after the seed clip, one bridge between every pair of
              clips, a short outro. The job stops at "review": the user edits text, drops or adds clips.
4. build    : narration through Creater Vid's gen.py (its ElevenLabs key and English voice). Every clip is a ZOOMED
              one: the zoomed clip of a highlight that contains it, else the passage is cut and sent to Podcast Zoom
              first (compile_require_zoom). Clips are cut from that zoomed file with ffmpeg, narration shown as a card over
              a blurred frame of the next clip, everything normalised (1080p30, AAC 48k, loudnorm) and joined into
              one mp4 + chapters.txt + compilation manifest + cut_multi cutlist.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import shutil
import subprocess
import threading
from pathlib import Path

from .. import config, db, paths, podcasts
from ..util import ffprobe_duration, media_ok, now_iso, sec_to_hms, slugify, write_json
from . import claude_runner, topic_scan

log = logging.getLogger("studio.compile")

OUT_DIR_NAME = "_tong-hop"
CREATER_DIR = config.TOOLS_ROOT / "Creater Vid"
CREATER_PY = CREATER_DIR / ".venv" / "Scripts" / "python.exe"
GEN_PY = CREATER_DIR / "gen.py"
W, H, FPS = 1920, 1080, 30
WORDS_PER_SEC = 2.6            # narration pace used to budget the clip time
FONT = Path(r"C:\Windows\Fonts\georgia.ttf")
_TAG = re.compile(r"\[[^\]\n]{1,40}\]")
_NO_WIN = 0x08000000 if hasattr(subprocess, "CREATE_NO_WINDOW") else 0

_threads: dict[int, threading.Thread] = {}
_stop: set[int] = set()
_encoder: list[str] | None = None


# ---------------------------------------------------------------- small helpers
def _set(job_id: int, **cols) -> None:
    cols["updated_at"] = now_iso()
    with db.tx() as c:
        c.execute(f"UPDATE compile_jobs SET {', '.join(f'{k}=?' for k in cols)} WHERE id=?", (*cols.values(), job_id))


def _note(job_id: int, kind: str, what: str, body: str = "") -> None:
    """🔔 for a compile job (review = the arc waits for the user, done = mp4 built, error)."""
    from .. import notify
    if kind == "error" and job_id in _stop:                # stopped by the user: no alarm
        return
    j = db.row("SELECT topic_vi, topic_en FROM compile_jobs WHERE id=?", (job_id,)) or {}
    name = (j.get("topic_vi") or j.get("topic_en") or f"#{job_id}")[:90]
    if kind != "review":
        notify.resolve(f"compile-review:{job_id}")
    notify.notify(kind, f"{what}: {name}", body, f"/compile/{job_id}",
                  key=f"compile-review:{job_id}" if kind == "review" else None)


def _progress(job_id: int, msg: str) -> None:
    _set(job_id, progress_msg=msg)


def _check_stop(job_id: int) -> None:
    if job_id in _stop:
        raise RuntimeError("dừng theo yêu cầu")


def _parse_obj(text: str) -> dict:
    m = re.findall(r"```json\s*(.*?)```", text or "", re.S)
    raw = m[-1] if m else (text or "")
    a, b = raw.find("{"), raw.rfind("}")
    if a < 0 or b < a:
        raise ValueError("Claude không trả về khối JSON")
    return json.loads(raw[a:b + 1])


def _claude(job_id: int, prompt: str, step: str, model: str, effort: str, runs: list) -> str:
    work = work_dir(job_id)
    res = claude_runner.run(prompt, cwd=config.BASE_DIR, tools="", isolated=True, max_turns=2, timeout=3600,
                            permission_mode="dontAsk", model=model or None, effort=effort or None,
                            log_path=work / f"{step}.jsonl", stop_flag=lambda: job_id in _stop)
    runs.append(res)
    (work / f"{step}.md").write_text(res.get("text") or "", encoding="utf-8")
    if not res.get("ok"):
        raise RuntimeError(f"{step}: {res.get('error')}")
    return res.get("result") or res.get("text") or ""


def _add_usage(job_id: int, runs: list) -> None:
    job = get_job(job_id) or {}
    merged = claude_runner.merge_runs(runs)
    _set(job_id, cost_usd=round(float(job.get("cost_usd") or 0) + float(merged.get("cost_usd") or 0), 4))


def _lines(episode_id: str, start: float, end: float) -> list[tuple]:
    return [(r["start_sec"], r["end_sec"], r["text"]) for r in db.rows(
        "SELECT start_sec, end_sec, text FROM transcript_lines WHERE episode_id=? AND start_sec>=? AND start_sec<=? "
        "ORDER BY seq", (episode_id, start - 1, end))]


def _say_text(text: str) -> str:
    """Narration as shown on screen: no audio tags, no doubled spaces."""
    return re.sub(r"\s+", " ", _TAG.sub("", text or "")).strip()


def _words(text: str) -> int:
    return len(_say_text(text).split())


def work_dir(job_id: int) -> Path:
    p = config.WORK_DIR / "compile" / str(job_id)
    p.mkdir(parents=True, exist_ok=True)
    return p


def out_dir(job: dict) -> Path:
    return paths.tonghop_dir() / f"video-{job['id']}-{slugify(job.get('topic_en') or 'tong-hop', 40)}"


# ---------------------------------------------------------------- reads for the UI
def get_job(job_id: int) -> dict | None:
    return db.row("SELECT * FROM compile_jobs WHERE id=?", (job_id,))


def _src(r: dict) -> None:
    """r["src"]: show of the clip (with the episode title for the support library), for prompts and pages."""
    r["src"] = podcasts.source_label(r.get("podcast_id"), r.get("ep_title"))


def items(job_id: int) -> list[dict]:
    rows = db.rows("SELECT i.*, e.guest, e.podcast_id, COALESCE(e.title, e.source_video) AS ep_title FROM compile_items i "
                   "LEFT JOIN episodes e ON e.id=i.episode_id WHERE job_id=? ORDER BY ord", (job_id,))
    for r in rows:
        _src(r)
        r["start_hms"], r["end_hms"] = sec_to_hms(r["start_sec"]), sec_to_hms(r["end_sec"])
        r["dur"] = round(r["end_sec"] - r["start_sec"])
        r["bridge_words"] = _words(r.get("bridge_text") or "")
    return rows


def candidates(job_id: int, unused_only: bool = False) -> list[dict]:
    rows = db.rows("SELECT c.*, e.guest, e.podcast_id, COALESCE(e.title, e.source_video) AS ep_title "
                   "FROM compile_candidates c LEFT JOIN episodes e ON e.id=c.episode_id "
                   "WHERE job_id=? ORDER BY score DESC, id", (job_id,))
    for r in rows:
        _src(r)
    used = {r["cand_id"] for r in db.rows("SELECT cand_id FROM compile_items WHERE job_id=? AND included=1", (job_id,))}
    out = []
    for r in rows:
        r["start_hms"], r["end_hms"] = sec_to_hms(r["start_sec"]), sec_to_hms(r["end_sec"])
        r["dur"] = round(r["end_sec"] - r["start_sec"])
        r["used"] = r["id"] in used
        if not (unused_only and r["used"]):
            out.append(r)
    return out


def totals(job: dict) -> dict:
    its = [i for i in items(job["id"]) if i["included"]]
    clip_sec = sum(i["dur"] for i in its)
    words = _words(job.get("intro_text") or "") + _words(job.get("outro_text") or "") + \
        sum(_words(i.get("bridge_text") or "") for i in its[:-1])
    narr_sec = round(words / WORDS_PER_SEC) + 2 * (len(its) + 1)
    return {"clips": len(its), "clip_sec": clip_sec, "narr_sec": narr_sec, "total_sec": clip_sec + narr_sec,
            "target_sec": int(job["target_min"] or 0) * 60,
            "episodes": len({i["episode_id"] for i in its}), "guests": len({i.get("guest") for i in its if i.get("guest")})}


def list_jobs(limit: int = 40) -> list[dict]:
    jobs = db.rows("SELECT j.*, s.title AS seed_title FROM compile_jobs j LEFT JOIN segments s ON s.id=j.seed_segment_id "
                   "ORDER BY j.id DESC LIMIT ?", (limit,))
    for j in jobs:
        j["totals"] = totals(j)
    return jobs


def busy(job_id: int) -> bool:
    t = _threads.get(job_id)
    return bool(t and t.is_alive())


# ---------------------------------------------------------------- start
def default_sources(episode_id: str) -> list[str]:
    """Shows a compilation reads by default: the seed's own show plus every support show (the supplementary library)."""
    own = podcasts.for_episode(episode_id)["id"]
    return [own] + [p for p in podcasts.support_ids() if p != own]


def sources(job: dict, s: dict) -> list[str]:
    return podcasts.split_ids(job.get("podcast_ids")) or [_prof(s)["id"]]


def create(seed_segment_id: int, target_min: int, note: str = "", podcast_ids=None) -> dict:
    seed = db.row("SELECT s.*, e.guest FROM segments s JOIN episodes e ON e.id=s.episode_id WHERE s.id=?",
                  (seed_segment_id,))
    if not seed:
        return {"error": "không có đoạn này"}
    if seed["start_sec"] is None or seed["end_sec"] is None:
        return {"error": "đoạn này không có mốc thời gian nên không dựng được"}
    if not 5 <= int(target_min or 0) <= 600:
        return {"error": "thời lượng phải từ 5 đến 600 phút"}
    seed_min = (seed["end_sec"] - seed["start_sec"]) / 60
    if int(target_min) < seed_min + 3:
        return {"error": f"đoạn mở đầu đã dài {seed_min:.0f} phút: chọn thời lượng từ {int(seed_min) + 5} phút trở lên"}
    src = topic_scan.resolve_source(seed["episode_id"], seed["start_sec"], seed["end_sec"])
    if src["kind"] == "missing":
        return {"error": "video gốc của đoạn này đã xoá và không còn clip nào chứa nó"}
    own = podcasts.for_episode(seed["episode_id"])["id"]
    if podcast_ids is None:
        pods = default_sources(seed["episode_id"])
    else:
        pods = podcasts.split_ids(",".join(podcast_ids) if isinstance(podcast_ids, (list, tuple)) else podcast_ids)
    if own not in pods:
        pods.insert(0, own)                            # the seed's own show is always the backbone
    with db.tx() as c:
        job_id = c.execute("INSERT INTO compile_jobs(seed_segment_id, target_min, note, status, progress_msg, cost_usd, "
                           "created_at, updated_at, podcast_ids) VALUES(?,?,?,?,?,?,?,?,?)",
                           (seed_segment_id, int(target_min), (note or "").strip()[:2000], "queued", "đang chờ",
                            0, now_iso(), now_iso(), ",".join(pods))).lastrowid
    _start(job_id, _run_plan)
    return {"ok": True, "id": job_id}


def _start(job_id: int, target, *args) -> dict:
    if busy(job_id):
        return {"error": "video này đang chạy"}
    _stop.discard(job_id)
    t = threading.Thread(target=target, args=(job_id, *args), name=f"compile-{job_id}", daemon=True)
    _threads[job_id] = t
    t.start()
    return {"ok": True}


def stop(job_id: int) -> dict:
    _stop.add(job_id)
    return {"message": "đã gửi lệnh dừng"}


def rearrange(job_id: int, feedback: str = "") -> dict:
    job = get_job(job_id)
    if not job or not db.scalar("SELECT COUNT(*) FROM compile_candidates WHERE job_id=?", (job_id,)):
        return {"error": "chưa có ứng viên để dựng lại mạch"}
    return _start(job_id, _run_arrange_only, (feedback or "").strip()[:3000])


def rescan(job_id: int, keywords: str = "") -> dict:
    if keywords.strip():
        _set(job_id, keywords=", ".join(topic_scan.parse_keywords(keywords)))
    return _start(job_id, _run_plan, True)


def build(job_id: int) -> dict:
    job = get_job(job_id)
    if not job or job["status"] not in ("review", "done", "failed"):
        return {"error": "chỉ dựng được sau khi mạch đã sẵn sàng"}
    if not db.scalar("SELECT COUNT(*) FROM compile_items WHERE job_id=? AND included=1", (job_id,)):
        return {"error": "chưa có đoạn nào trong mạch"}
    return _start(job_id, _run_build)


# ---------------------------------------------------------------- step 1: topic
def _seed(job: dict) -> dict:
    s = db.row("SELECT s.*, e.guest FROM segments s JOIN episodes e ON e.id=s.episode_id WHERE s.id=?",
               (job["seed_segment_id"],))
    s["themes"] = [t[0] for t in db.get_conn().execute(
        "SELECT t.name FROM segment_topics st JOIN topics t ON t.id=st.topic_id WHERE st.segment_id=?", (s["id"],))]
    s["lines"] = _lines(s["episode_id"], s["start_sec"], s["end_sec"])
    return s


def _seed_text(s: dict, limit: int = 24000) -> str:
    body = "\n".join(f"[{sec_to_hms(a)}] {t.strip()}" for a, _, t in s["lines"])
    if len(body) > limit:
        body = body[:limit // 2] + "\n[…]\n" + body[-limit // 2:]
    return "\n".join([
        f"Tập: {s['episode_id']} · khách: {s.get('guest') or '?'} · {sec_to_hms(s['start_sec'])} → {sec_to_hms(s['end_sec'])}",
        f"Title: {s['title']}",
        f"Hook: {s.get('hook_en') or ''}",
        f"Summary: {s.get('summary_en') or s.get('summary_vi') or ''}",
        f"Keyword: {s.get('core_keyword') or ''} · themes: {', '.join(s['themes'])}",
        "Transcript:", body,
    ])


def _prof(s: dict) -> dict:
    """Profile of the seed's show: a compilation stays inside that show."""
    return podcasts.for_episode(s["episode_id"])


def _topic_prompt(s: dict, note: str) -> str:
    return "\n".join([
        f"Người dùng chọn đoạn highlight podcast {_prof(s)['name']} (host {_prof(s)['host']}) dưới đây làm MỞ ĐẦU cho một video TỔNG HỢP dài, gồm nhiều đoạn "
        "từ các tập khác cùng chủ đề. Xác định chủ đề để đi tìm các đoạn liên quan trong toàn bộ transcript.",
        f"Ghi chú của người dùng: {note}" if note else "",
        "",
        "Trả về DUY NHẤT một khối ```json:",
        '{"topic_en":"chủ đề ngắn tiếng Anh, đủ rộng để có nhiều tập nói tới nhưng vẫn đúng mạch của đoạn",'
        '"topic_vi":"chủ đề tiếng Việt","angle_vi":"1-2 câu: mạch/câu hỏi lớn mà video tổng hợp sẽ đi theo",'
        '"keywords":["15-30 từ khoá TIẾNG ANH để lọc transcript: tên riêng, thuật ngữ, từ đồng nghĩa, cách nói thông tục; '
        'dùng * cho đuôi từ (nephil*); tránh từ quá chung gây nhiễu"]}',
        "",
        "<seed>", _seed_text(s), "</seed>",
    ])


# ---------------------------------------------------------------- step 2: scan every transcript
def _support_lines(job: dict, s: dict) -> list[str]:
    """How the clips of other podcasts fit in, when the job reads more than the seed's own show."""
    extra = [p for p in sources(job, s) if p != _prof(s)["id"]]
    if not extra:
        return []
    return [f"NGUỒN: {_prof(s)['name']} là show chính; ngoài ra có podcast bổ trợ ({podcasts.show_names(extra)}). "
            "Thuộc tính show của mỗi vùng/đoạn cho biết nguồn. Đoạn từ podcast bổ trợ dùng để BỔ TRỢ cho show chính: "
            "chuyên gia khác xác nhận, bằng chứng, chi tiết mà show chính chưa có, hoặc phản biện. Chọn chúng khi chúng "
            "thêm được điều gì đó, không chọn đoạn chỉ lặp lại ý đã có ở show chính."]


def _scan_prompt(job: dict, s: dict, batch: list[dict]) -> str:
    return "\n".join([
        f"Bạn đang tìm nguyên liệu cho một video TỔNG HỢP podcast {_prof(s)['name']}, chủ đề «{job['topic_en']}».",
        *_support_lines(job, s),
        f"Mạch của video: {job.get('angle_vi') or ''}",
        f"Video mở đầu bằng đoạn: «{s['title']}» ({s['episode_id']}, khách {s.get('guest') or '?'}): "
        f"{s.get('summary_en') or s.get('summary_vi') or ''}",
        "",
        "Dưới đây là các vùng transcript đã lọc bằng từ khoá (mỗi dòng có mốc [hh:mm:ss] tính từ đầu tập).",
        "Chọn mọi đoạn THẬT SỰ nói về chủ đề, có nội dung riêng (thông tin, câu chuyện, lập luận, tranh luận), đứng "
        "một mình vẫn hiểu được. Bỏ đoạn chỉ nhắc lướt từ khoá, đùa vu vơ, quảng cáo, và đoạn lặp lại y hệt ý của "
        "đoạn mở đầu.",
        "- Mỗi đoạn dài 1 đến 12 phút. Bắt đầu ở dòng mở ý (câu hỏi hoặc câu dẫn), kết thúc ở dòng chốt ý.",
        "- start = mốc dòng đầu tiên, end = mốc dòng CUỐI CÙNG thuộc đoạn. Chép mốc nguyên văn từ transcript.",
        "- Không chọn hai đoạn chồng nhau trong cùng một tập.",
        "- score 1-10: độ hấp dẫn với người xem YouTube Mỹ × mức độ đúng chủ đề.",
        "- point_en: luận điểm/câu chuyện chính của đoạn, 1 câu tiếng Anh (dùng để xếp mạch và viết lời dẫn).",
        "- ends_en: đoạn kết ở ý gì / câu hỏi gì, 1 câu tiếng Anh ngắn.",
        "",
        "Trả về DUY NHẤT một khối ```json chứa mảng (mảng rỗng [] nếu không có đoạn nào):",
        '[{"episode_id":"' + _prof(s)["id"] + '-123","start":"01:02:03","end":"01:09:40","score":8,'
        '"title":"English YouTube-style title","summary_vi":"1-2 câu tóm tắt tiếng Việt",'
        '"point_en":"...","ends_en":"..."}]',
        "",
        *[topic_scan._window_text(w) for w in batch],
    ])


def _trim_windows(wins: list[dict], max_tokens: int) -> tuple[list[dict], int]:
    """Keep the windows with the most keyword hits until the token budget is used (episode order kept)."""
    sizes = [len(topic_scan._window_text(w)) // topic_scan.CHARS_PER_TOKEN for w in wins]
    if sum(sizes) <= max_tokens:
        return wins, 0
    order = sorted(range(len(wins)), key=lambda i: -(wins[i]["hits"] / max(1, sizes[i])))
    keep, used = set(), 0
    for i in order:
        if used + sizes[i] <= max_tokens:
            keep.add(i)
            used += sizes[i]
    return [w for i, w in enumerate(wins) if i in keep], len(wins) - len(keep)


def _scan(job: dict, s: dict, runs: list) -> int:
    job_id = job["id"]
    kws = topic_scan.parse_keywords(job["keywords"])
    pad = db.setting_float("compile_pad_sec") or 120
    wins = topic_scan.find_windows(kws, pad, podcast_ids=sources(job, s))
    # the seed itself is already clip 1: cut its lines out of the windows of its own episode
    for w in wins:
        if w["episode_id"] == s["episode_id"]:
            w["lines"] = [ln for ln in w["lines"] if not (s["start_sec"] - 5 <= ln[0] <= s["end_sec"] + 5)]
    wins = [w for w in wins if len(w["lines"]) >= 8]
    if not wins:
        raise RuntimeError("không dòng transcript nào khớp từ khoá (sửa từ khoá rồi bấm Quét lại)")
    wins, dropped = _trim_windows(wins, db.setting_int("compile_max_scan_tokens") or 600_000)
    batches = topic_scan._batches(wins)
    est = sum(len(topic_scan._window_text(w)) for w in wins) // topic_scan.CHARS_PER_TOKEN
    _set(job_id, n_windows=len(wins), n_episodes=len({w["episode_id"] for w in wins}), est_tokens=est)
    model = db.get_setting("claude_model_compile_scan") or "sonnet"
    effort = db.get_setting("claude_effort_compile_scan") or "medium"
    picked = []
    for i, batch in enumerate(batches, 1):
        _check_stop(job_id)
        _progress(job_id, f"Claude đọc lô {i}/{len(batches)} ({len(batch)} vùng, ~{est // 1000}k token"
                          + (f", bỏ {dropped} vùng ít khớp vì vượt ngân sách" if dropped else "") + ")")
        text = _claude(job_id, _scan_prompt(job, s, batch), f"scan_{i}", model, effort, runs)
        try:
            found = topic_scan._parse_json(text)
        except ValueError as e:
            raise RuntimeError(f"lô {i}: {e}") from e
        picked += [x for x in (topic_scan._snap(it, batch) for it in found) if x]
    picked = [p for p in topic_scan._dedupe(picked) if p["end_sec"] - p["start_sec"] >= 45]
    with db.tx() as c:
        c.execute("DELETE FROM compile_items WHERE job_id=?", (job_id,))
        c.execute("DELETE FROM compile_candidates WHERE job_id=?", (job_id,))
        for it in picked:
            src = topic_scan.resolve_source(it["episode_id"], it["start_sec"], it["end_sec"])
            if src["kind"] == "missing":
                continue
            c.execute("INSERT INTO compile_candidates(job_id, episode_id, start_sec, end_sec, title, summary_vi, point_en, "
                      "ends_en, score, source_kind, source_path, source_offset) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                      (job_id, it["episode_id"], it["start_sec"], it["end_sec"], str(it.get("title") or "")[:200],
                       it.get("summary_vi"), it.get("point_en"), it.get("ends_en"), float(it.get("score") or 0),
                       src["kind"], src["path"], src["offset"]))
    n = db.scalar("SELECT COUNT(*) FROM compile_candidates WHERE job_id=?", (job_id,))
    _set(job_id, n_candidates=n)
    return n


# ---------------------------------------------------------------- step 3: arc + narration
def _edge_lines(episode_id: str, start: float, end: float) -> tuple[str, str]:
    ln = _lines(episode_id, start, end)
    head = " ".join(t.strip() for _, _, t in ln[:3])
    tail = " ".join(t.strip() for _, _, t in ln[-3:])
    return head[:300], tail[:300]


def _arrange_prompt(job: dict, s: dict, cands: list[dict], feedback: str) -> str:
    target = int(job["target_min"]) * 60
    seed_dur = round(s["end_sec"] - s["start_sec"])
    head, tail = _edge_lines(s["episode_id"], s["start_sec"], s["end_sec"])
    pool_sec = sum(c["dur"] for c in cands)
    lines = []
    for c in cands:
        h, t = _edge_lines(c["episode_id"], c["start_sec"], c["end_sec"])
        lines.append(json.dumps({"id": c["id"], "episode": c["episode_id"], "show": c.get("src"),
                                 "guest": c.get("guest"), "dur_sec": c["dur"],
                                 "score": c["score"], "title": c["title"], "point": c.get("point_en"),
                                 "ends": c.get("ends_en"), "opens_with": h, "closes_with": t}, ensure_ascii=False))
    prev = ""
    if feedback:
        cur = [i for i in items(job["id"]) if i["kind"] == "clip" and i["included"]]
        prev = "\n".join([
            "", "MẠCH HIỆN TẠI (bản trước) theo thứ tự: " + ", ".join(str(i["cand_id"]) for i in cur),
            f"YÊU CẦU SỬA CỦA NGƯỜI DÙNG (ưu tiên cao nhất): {feedback}",
        ])
    return "\n".join([
        f"Bạn là biên tập viên kênh YouTube {_prof(s)['channel']} (tổng hợp podcast {_prof(s)['name']}). Dựng một tập TỔNG HỢP chủ đề «{job['topic_en']}» "
        f"dài khoảng {job['target_min']} phút.",
        f"Mạch lớn: {job.get('angle_vi') or ''}",
        f"Ghi chú của người dùng: {job['note']}" if job.get("note") else "",
        "",
        "CẤU TRÚC VIDEO (cố định):",
        f"1. Clip 1 = ĐOẠN NGƯỜI DÙNG CHỌN (seed, {seed_dur} giây) — luôn đứng đầu, không đổi.",
        "2. INTRO: lời dẫn phát NGAY SAU clip 1: định vị đây là tập tổng hợp từ nhiều tập/khách (dùng đúng số tập và "
        "số khách của mạch bạn chọn), gợi câu hỏi lớn của chủ đề ở mức khái quát, nối sang clip 2. 40-70 từ.",
        "3. Các clip liên quan, giữa mỗi cặp clip liền kề có một BRIDGE 15-35 từ.",
        "4. OUTRO sau clip cuối: 20-40 từ, khép lại câu hỏi lớn, mời bình luận/đăng ký nhẹ nhàng (không sến).",
        "",
        "CHỌN VÀ XẾP CLIP:",
        f"- Tổng thời lượng clip (cả seed) ≈ {target - 60 - 15 * 8} đến {target} giây: cộng dur_sec cho khớp. Kho ứng viên "
        f"có {len(cands)} đoạn, tổng {pool_sec // 60} phút" + (" — KHÔNG đủ cho thời lượng yêu cầu: dùng hết đoạn đáng "
                                                                   "dùng và báo trong note_vi." if pool_sec + seed_dur < target * 0.8 else "."),
        "- Xếp thành dòng leo thang theo câu hỏi, KHÔNG xếp theo điểm: Setup (bối cảnh) → Deepening (đào sâu, lật điều "
        "tưởng hiển nhiên) → Twist/doubt (nghi vấn, góc nhìn ngược) → Revelation/payoff (clip chốt có câu nặng nhất).",
        *([f"- Podcast bổ trợ (show khác {_prof(s)['name']}): chỉ là phần BỔ TRỢ, {_prof(s)['name']} vẫn là xương sống "
            "(khoảng 60% thời lượng clip trở lên nếu đủ nguyên liệu). Đặt clip bổ trợ ngay sau clip của show chính mà nó "
            "xác nhận, đào sâu hoặc phản biện. Bridge sang clip bổ trợ phải nói rõ đây là nguồn khác (tên podcast/người "
            "nói nếu có trong dữ liệu), không để người xem tưởng vẫn cùng một cuộc trò chuyện."]
          if [p for p in sources(job, s) if p != _prof(s)["id"]] else []),
        f"- {_prof(s)['host']} là trục nối xuyên các tập: clip kết ở một câu hỏi thì nối sang clip ở tập khác đang trả lời nó.",
        "- Dialectic: hai khách trái quan điểm về cùng một điểm thì đặt cạnh nhau.",
        "- Nhịp: không dồn các clip cường độ cao liền nhau; tránh hai clip liền kề cùng một tập nếu có lựa chọn khác.",
        "- Chống trùng ý: hai clip cùng một luận điểm thì giữ clip mạnh hơn.",
        "",
        "LỜI DẪN — TIẾNG ANH, prompt ElevenLabs v3, một người dẫn chuyện xuyên suốt, giọng trầm, nghiêm túc, tò mò:",
        "- Không SSML, không [pause]. Nhịp bằng dấu \"…\", nhấn bằng chữ IN HOA (ít thôi), ngắt câu tự nhiên.",
        "- Audio tag đặt ngay trước câu nó chi phối, tối đa 2-3 tag mỗi đoạn. Dùng: [curious] [whispers] [sighs] "
        "[exhales] [excited] [sarcastic] [laughs] [grave] [tense] [hushed] [ominous] [low, measured pace]. Giữ tính cách "
        "giọng nhất quán cả tập.",
        f"- Bridge: voice hoá đúng lý do bạn đặt hai clip cạnh nhau (trục {_prof(s)['host']} / dialectic / leo thang). KHÔNG tóm tắt lại "
        "clip vừa xong, KHÔNG nói trước câu đắt của clip sau, chỉ mở đường. Có thể nêu tên khách sắp nói.",
        "- Chỉ dùng dữ kiện có trong title/point/ends/opens_with/closes_with: tuyệt đối không bịa sự kiện, con số, tên.",
        "",
        "Trả về DUY NHẤT một khối ```json:",
        '{"title_en":"YouTube title cho cả tập","intro_v3":"...","outro_v3":"...",'
        '"note_vi":"ghi chú ngắn cho người dùng (vd thiếu nguyên liệu, clip nào gần trùng)",'
        '"arc":[{"id":"seed","role":"cold_open","why_vi":"...","bridge_out_v3":null},'
        '{"id":12,"role":"setup","why_vi":"vì sao đặt ở đây","bridge_out_v3":"bridge sang clip kế (null ở clip cuối)"}]}',
        "Phần tử đầu tiên của arc luôn là seed (bridge_out_v3 của seed = null vì INTRO đứng ngay sau nó). role: "
        "cold_open | setup | deepening | twist | dialectic | revelation.",
        prev,
        "",
        "<seed>", f"Title: {s['title']} · {s['episode_id']} · khách {s.get('guest') or '?'}",
        f"Summary: {s.get('summary_en') or s.get('summary_vi') or ''}", f"opens_with: {head}", f"closes_with: {tail}",
        "</seed>",
        "", "<candidates>", *lines, "</candidates>",
    ])


def _arrange(job: dict, s: dict, runs: list, feedback: str = "") -> None:
    job_id = job["id"]
    cands = candidates(job_id)
    if not cands:
        raise RuntimeError("quét xong nhưng không tìm thấy đoạn liên quan nào còn video nguồn")
    _progress(job_id, f"Claude dựng mạch và viết lời dẫn từ {len(cands)} ứng viên")
    text = _claude(job_id, _arrange_prompt(job, s, cands, feedback), "arrange",
                   db.get_setting("claude_model_compile_arc") or "opus",
                   db.get_setting("claude_effort_compile_arc") or "high", runs)
    data = _parse_obj(text)
    by_id = {c["id"]: c for c in cands}
    arc = [a for a in data.get("arc") or [] if isinstance(a, dict)]
    seed_entry = next((a for a in arc if str(a.get("id")) == "seed"), {"role": "cold_open"})
    rows, seen = [], set()
    for a in arc:
        try:
            cid = int(a.get("id"))
        except (TypeError, ValueError):
            continue
        if cid in by_id and cid not in seen:
            seen.add(cid)
            rows.append((by_id[cid], a))
    if not rows:
        raise RuntimeError("Claude không chọn được clip nào từ danh sách ứng viên")
    src = topic_scan.resolve_source(s["episode_id"], s["start_sec"], s["end_sec"])
    with db.tx() as c:
        c.execute("DELETE FROM compile_items WHERE job_id=?", (job_id,))
        c.execute("INSERT INTO compile_items(job_id, ord, kind, role, cand_id, episode_id, start_sec, end_sec, title, "
                  "summary_vi, why_vi, bridge_text, source_kind, source_path, source_offset) "
                  "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                  (job_id, 1, "seed", "cold_open", None, s["episode_id"], s["start_sec"], s["end_sec"], s["title"],
                   s.get("summary_vi"), seed_entry.get("why_vi") or "đoạn bạn chọn", None,
                   src["kind"], src["path"], src["offset"]))
        for n, (cd, a) in enumerate(rows, 2):
            last = n == len(rows) + 1
            c.execute("INSERT INTO compile_items(job_id, ord, kind, role, cand_id, episode_id, start_sec, end_sec, title, "
                      "summary_vi, why_vi, bridge_text, source_kind, source_path, source_offset) "
                      "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                      (job_id, n, "clip", str(a.get("role") or ""), cd["id"], cd["episode_id"], cd["start_sec"],
                       cd["end_sec"], cd["title"], cd.get("summary_vi"), a.get("why_vi"),
                       None if last else (a.get("bridge_out_v3") or None),
                       cd["source_kind"], cd["source_path"], cd["source_offset"]))
    _set(job_id, title_en=str(data.get("title_en") or "")[:200], intro_text=data.get("intro_v3") or "",
         outro_text=data.get("outro_v3") or "", arc_note=data.get("note_vi") or "")


# ---------------------------------------------------------------- runners
def _run_plan(job_id: int, keep_keywords: bool = False) -> None:
    runs: list = []
    try:
        job = get_job(job_id)
        s = _seed(job)
        if not (keep_keywords and job.get("keywords")):
            _set(job_id, status="topic")
            _progress(job_id, "Claude đọc đoạn bạn chọn để xác định chủ đề và từ khoá")
            data = _parse_obj(_claude(job_id, _topic_prompt(s, job.get("note") or ""), "topic",
                                      db.get_setting("claude_model_compile_topic") or "sonnet",
                                      db.get_setting("claude_effort_compile_topic") or "low", runs))
            kws = [str(k) for k in data.get("keywords") or [] if str(k).strip()]
            if not kws:
                raise RuntimeError("Claude không đưa ra được từ khoá")
            _set(job_id, topic_en=str(data.get("topic_en") or s["title"])[:200], topic_vi=data.get("topic_vi"),
                 angle_vi=data.get("angle_vi"), keywords=", ".join(kws))
        _check_stop(job_id)
        _set(job_id, status="scanning")
        n = _scan(get_job(job_id), s, runs)
        _check_stop(job_id)
        _set(job_id, status="arranging")
        _arrange(get_job(job_id), s, runs)
        _add_usage(job_id, runs)
        _set(job_id, status="review", error=None, progress_msg=f"mạch đã sẵn sàng · {n} ứng viên · "
                                                              f"{claude_runner.describe_run(claude_runner.merge_runs(runs))}")
        _note(job_id, "review", "Video tổng hợp cần duyệt mạch", f"{n} ứng viên · sửa lời dẫn/thứ tự rồi bấm Dựng video")
    except Exception as e:  # noqa: BLE001
        log.exception("compile %s plan failed", job_id)
        if runs:
            _add_usage(job_id, runs)
        _set(job_id, status="failed", error=str(e)[:1000])
        _note(job_id, "error", "Video tổng hợp lỗi", str(e))
    finally:
        _stop.discard(job_id)


def _run_arrange_only(job_id: int, feedback: str) -> None:
    runs: list = []
    try:
        _set(job_id, status="arranging")
        job = get_job(job_id)
        _arrange(job, _seed(job), runs, feedback)
        _add_usage(job_id, runs)
        _set(job_id, status="review", error=None,
             progress_msg=f"đã dựng lại mạch · {claude_runner.describe_run(claude_runner.merge_runs(runs))}")
        _note(job_id, "review", "Đã dựng lại mạch, cần duyệt", "xem lại rồi bấm Dựng video")
    except Exception as e:  # noqa: BLE001
        log.exception("compile %s arrange failed", job_id)
        _set(job_id, status="review" if items(job_id) else "failed", error=str(e)[:1000])
        _note(job_id, "error", "Dựng lại mạch lỗi", str(e))
    finally:
        _stop.discard(job_id)


# ---------------------------------------------------------------- edits from the review screen
def update_item(job_id: int, item_id: int, **fields) -> None:
    cols = {k: v for k, v in fields.items() if k in ("included", "bridge_text")}
    if cols:
        with db.tx() as c:      # the seed always stays in (it is the point of the video)
            c.execute(f"UPDATE compile_items SET {', '.join(f'{k}=?' for k in cols)} WHERE id=? AND job_id=? "
                      "AND NOT (kind='seed' AND ?)", (*cols.values(), item_id, job_id, int("included" in cols)))


def update_job_text(job_id: int, **fields) -> None:
    cols = {k: v for k, v in fields.items() if k in ("intro_text", "outro_text", "title_en")}
    if cols:
        _set(job_id, **cols)


def move_item(job_id: int, item_id: int, delta: int) -> None:
    its = [i for i in items(job_id) if i["kind"] != "seed"]
    idx = next((n for n, i in enumerate(its) if i["id"] == item_id), None)
    if idx is None or not 0 <= idx + delta < len(its):
        return
    its[idx], its[idx + delta] = its[idx + delta], its[idx]
    with db.tx() as c:
        for n, i in enumerate(its, 2):
            c.execute("UPDATE compile_items SET ord=? WHERE id=?", (n, i["id"]))


def add_candidate(job_id: int, cand_id: int) -> dict:
    cd = db.row("SELECT * FROM compile_candidates WHERE id=? AND job_id=?", (cand_id, job_id))
    if not cd:
        return {"error": "không có ứng viên này"}
    if db.scalar("SELECT COUNT(*) FROM compile_items WHERE job_id=? AND cand_id=?", (job_id, cand_id)):
        with db.tx() as c:
            c.execute("UPDATE compile_items SET included=1 WHERE job_id=? AND cand_id=?", (job_id, cand_id))
        return {"ok": True}
    n = (db.scalar("SELECT MAX(ord) FROM compile_items WHERE job_id=?", (job_id,)) or 1) + 1
    with db.tx() as c:
        c.execute("INSERT INTO compile_items(job_id, ord, kind, role, cand_id, episode_id, start_sec, end_sec, title, "
                  "summary_vi, why_vi, bridge_text, source_kind, source_path, source_offset) "
                  "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                  (job_id, n, "clip", "added", cd["id"], cd["episode_id"], cd["start_sec"], cd["end_sec"], cd["title"],
                   cd["summary_vi"], "bạn thêm tay (viết bridge nối vào, hoặc bấm Dựng lại mạch)", None,
                   cd["source_kind"], cd["source_path"], cd["source_offset"]))
    return {"ok": True}


# ---------------------------------------------------------------- step 4: build the video
def _run(cmd: list, cwd: Path | None = None, timeout: int = 7200) -> subprocess.CompletedProcess:
    p = subprocess.run([str(x) for x in cmd], cwd=cwd, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=timeout, creationflags=_NO_WIN)
    if p.returncode != 0:
        from ..util import ffmpeg_error_summary
        raise RuntimeError(ffmpeg_error_summary(p.stderr or p.stdout or "") or f"lệnh lỗi ({p.returncode})")
    return p


def _video_encoder() -> list[str]:
    """NVENC when the GPU encodes (tested once on a tiny clip), else x264."""
    global _encoder
    if _encoder is None:
        _encoder = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20"]
        if (db.get_setting("compile_video_encoder") or "auto") != "x264":
            try:
                _run([config.FFMPEG, "-v", "error", "-f", "lavfi", "-i", "color=black:s=256x256:d=0.2", "-c:v", "h264_nvenc",
                      "-f", "null", "-"], timeout=60)
                _encoder = ["-c:v", "h264_nvenc", "-preset", "p5", "-rc", "vbr", "-cq", "21", "-b:v", "0"]
            except Exception:  # noqa: BLE001
                pass
    return _encoder


def _audio_args() -> list[str]:
    return ["-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2"]


def _key(*parts) -> str:
    return hashlib.sha1("|".join(str(p) for p in parts).encode("utf-8")).hexdigest()[:10]


def _tts(text: str, out: Path) -> float:
    """Narration mp3 through Creater Vid's gen.py (ElevenLabs key + English narrator voice of Creater)."""
    if out.is_file() and out.stat().st_size > 1000:
        return ffprobe_duration(out)
    if not CREATER_PY.is_file() or not GEN_PY.is_file():
        raise RuntimeError(f"không thấy Creater Vid ({GEN_PY}) để đọc lời dẫn bằng ElevenLabs")
    tf = out.with_suffix(".txt")
    tf.write_text(text.strip(), encoding="utf-8")
    cmd = [CREATER_PY, "-X", "utf8", GEN_PY, "tts", "--text-file", tf, "--out", out, "--lang", "en",
           "--what", f"jre-studio compile {out.stem}"]
    if db.get_setting("compile_voice_id"):
        cmd += ["--voice", db.get_setting("compile_voice_id")]
    if db.get_setting("compile_tts_model"):
        cmd += ["--model", db.get_setting("compile_tts_model")]
    # cwd = the parts folder: no project.json above it, so gen.py keeps no film budget/ledger for this call
    p = subprocess.run([str(x) for x in cmd], cwd=out.parent, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=900, creationflags=_NO_WIN)
    if p.returncode != 0 or not out.is_file():
        msg = (p.stdout + "\n" + p.stderr).strip().splitlines()
        raise RuntimeError("ElevenLabs: " + " · ".join(msg[-3:])[:500])
    return ffprobe_duration(out)


def _clip_part(it: dict, out: Path) -> None:
    if out.is_file() and out.stat().st_size > 10000:
        return
    start = max(0.0, it["start_sec"] - (it["source_offset"] or 0))
    dur = it["end_sec"] - it["start_sec"]
    vf = (f"scale={W}:{H}:force_original_aspect_ratio=decrease,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2,setsar=1,"
          f"fps={FPS},format=yuv420p")
    af = (f"aresample=48000,afade=t=in:d=0.15,afade=t=out:st={max(0.0, dur - 0.25):.2f}:d=0.25,"
          "loudnorm=I=-16:TP=-1.5:LRA=11")
    tmp = out.with_suffix(".tmp.mp4")
    _run([config.FFMPEG, "-v", "error", "-y", "-ss", f"{start:.3f}", "-i", it["source_path"], "-t", f"{dur:.3f}",
          "-vf", vf, "-af", af, *_video_encoder(), *_audio_args(), "-movflags", "+faststart", tmp])
    tmp.replace(out)


def _wrap(text: str, width: int = 46) -> str:
    lines, cur = [], ""
    for w in text.split():
        if cur and len(cur) + 1 + len(w) > width:
            lines.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    if cur:
        lines.append(cur)
    return "\n".join(lines)


def _card_part(text: str, voice: Path, voice_sec: float, bg_src: dict | None, out: Path, parts: Path) -> None:
    """Narration card: blurred, darkened frame of the next clip, the narration text, the ElevenLabs voice."""
    if out.is_file() and out.stat().st_size > 10000:
        return
    bg = out.with_suffix(".bg.jpg")
    if bg_src and bg_src.get("path"):
        t = max(0.0, bg_src["start_sec"] - (bg_src["source_offset"] or 0) + 2)
        try:
            _run([config.FFMPEG, "-v", "error", "-y", "-ss", f"{t:.2f}", "-i", bg_src["path"], "-frames:v", "1", bg],
                 timeout=120)
        except Exception:  # noqa: BLE001
            bg.unlink(missing_ok=True)
    font = parts / "font.ttf"
    if not font.exists() and FONT.is_file():
        shutil.copy2(FONT, font)
    show_text = db.get_setting("compile_card_text") != "0" and font.exists()
    txt = out.with_suffix(".card.txt")
    txt.write_text(_wrap(_say_text(text)), encoding="utf-8", newline="\n")     # \r would show as an empty line
    dur = voice_sec + 1.0
    vin = ["-loop", "1", "-i", bg.name] if bg.exists() else ["-f", "lavfi", "-i", f"color=c=0x101014:s={W}x{H}"]
    vf = (f"[0:v]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1,boxblur=24:2,"
          "eq=brightness=-0.28:saturation=0.7")
    if show_text:
        vf += (f",drawtext=fontfile={font.name}:textfile={txt.name}:fontcolor=white:fontsize=50:line_spacing=16:"
               "text_align=C:x=(w-text_w)/2:y=(h-text_h)/2:shadowcolor=black@0.7:shadowx=2:shadowy=2:"
               f"alpha='min(1,t/0.6)'")
    vf += f",fps={FPS},format=yuv420p[v]"
    af = "[1:a]aresample=48000,adelay=400|400,apad,loudnorm=I=-16:TP=-1.5:LRA=11[a]"
    tmp = out.with_suffix(".tmp.mp4")
    _run([config.FFMPEG, "-v", "error", "-y", *vin, "-i", voice.name, "-filter_complex", f"{vf};{af}",
          "-map", "[v]", "-map", "[a]", "-t", f"{dur:.2f}", *_video_encoder(), *_audio_args(), "-movflags", "+faststart",
          tmp.name], cwd=parts)
    tmp.replace(out)


def _plan_parts(job: dict) -> list[dict]:
    """Play order: seed, intro, clip 2, bridge, clip 3, … last clip, outro."""
    its = [i for i in items(job["id"]) if i["included"]]
    plan = []
    for n, it in enumerate(its):
        plan.append({"type": "clip", "item": it})
        nxt = its[n + 1] if n + 1 < len(its) else None
        text = (job.get("intro_text") if n == 0 else it.get("bridge_text")) if nxt else job.get("outro_text")
        if text and _say_text(text):
            plan.append({"type": "narration", "text": text, "next": nxt or it,
                         "label": "intro" if n == 0 and nxt else ("outro" if not nxt else f"bridge {it['ord']}→{nxt['ord']}")})
    return plan


# ---------------------------------------------------------------- zoom: every clip of the video is a zoomed one
def _zoom_cache(parts: Path, episode_id: str, start: float, end: float) -> Path:
    return parts / f"zoom_{episode_id}_{_key(episode_id, round(start, 2), round(end, 2))}.mp4"


def zoomed_source(episode_id: str, start: float, end: float, parts: Path | None = None) -> dict | None:
    """A zoomed file that already covers the passage: the zoomed clip of a highlight containing it (same timeline as
    the highlight), else the passage zoomed by an earlier build of this video. None = it still has to be zoomed."""
    for sg in db.rows("SELECT start_sec, end_sec, clip_zoomed_path FROM segments WHERE episode_id=? AND clip_zoomed_path "
                      "IS NOT NULL AND status NOT IN ('archived') AND start_sec<=? AND end_sec>=? ORDER BY end_sec-start_sec",
                      (episode_id, start + 1, end - 1)):
        if media_ok(Path(sg["clip_zoomed_path"]), sg["end_sec"] - sg["start_sec"]):
            return {"path": sg["clip_zoomed_path"], "offset": float(sg["start_sec"]), "how": "highlight"}
    if parts is not None:
        z = _zoom_cache(parts, episode_id, start, end)
        if media_ok(z, end - start):
            return {"path": str(z), "offset": float(start), "how": "built"}
    return None


def zoom_state(job: dict, its: list[dict]) -> None:
    """For the review page: which clips have a zoomed version already, which will be zoomed at build time."""
    parts = out_dir(job) / "parts"
    for it in its:
        z = zoomed_source(it["episode_id"], it["start_sec"], it["end_sec"], parts)
        it["zoom_how"] = z["how"] if z else None


def _ensure_zoom(job_id: int, clips: list[dict], parts: Path) -> None:
    """Sets play_path/play_offset on every clip: its zoomed version, rendered now through Podcast Zoom when missing
    (passage cut at its original size first, then zoomed with the Studio's zoom settings)."""
    need = []
    for it in clips:
        z = zoomed_source(it["episode_id"], it["start_sec"], it["end_sec"], parts)
        if z:
            it.update(play_path=z["path"], play_offset=z["offset"])
        elif db.get_setting("compile_require_zoom") == "0":
            it.update(play_path=it["source_path"], play_offset=it["source_offset"])
        else:
            need.append(it)
    if not need:
        return
    pairs = []
    for n, it in enumerate(need, 1):
        _check_stop(job_id)
        _progress(job_id, f"cắt đoạn chưa có bản zoom {n}/{len(need)} ({it['episode_id']}) để gửi Podcast Zoom")
        raw = parts / f"raw_{it['episode_id']}_{_key(it['episode_id'], round(it['start_sec'], 2), round(it['end_sec'], 2))}.mp4"
        dur = it["end_sec"] - it["start_sec"]
        if not media_ok(raw, dur):
            tmp = raw.with_suffix(".tmp.mp4")
            _run([config.FFMPEG, "-v", "error", "-y", "-ss", f"{max(0.0, it['start_sec'] - (it['source_offset'] or 0)):.3f}",
                  "-i", it["source_path"], "-t", f"{dur:.3f}", *_video_encoder(), *_audio_args(), "-movflags", "+faststart", tmp])
            tmp.replace(raw)
        pairs.append((raw, _zoom_cache(parts, it["episode_id"], it["start_sec"], it["end_sec"])))
    from .zoom import zoom_files
    failed = zoom_files(pairs, progress_cb=lambda pct, msg: _progress(job_id, f"Podcast Zoom: {msg} ({pct or 0:.0f}%)"),
                        stop_flag=lambda: job_id in _stop)
    if failed:
        raise RuntimeError("zoom lỗi: " + "; ".join(failed)[:600])
    for it, (raw, out) in zip(need, pairs):
        it.update(play_path=str(out), play_offset=float(it["start_sec"]))
        raw.unlink(missing_ok=True)       # the zoomed file is what the video uses; the raw cut was only its input


def _run_build(job_id: int) -> None:
    try:
        job = get_job(job_id)
        folder = out_dir(job)
        parts = folder / "parts"
        parts.mkdir(parents=True, exist_ok=True)
        plan = _plan_parts(job)
        # sources may have changed since the scan (video re-downloaded, source auto-deleted): resolve again
        for p in plan:
            if p["type"] == "clip":
                it = p["item"]
                src = topic_scan.resolve_source(it["episode_id"], it["start_sec"], it["end_sec"])
                if src["kind"] == "missing":
                    raise RuntimeError(f"clip {it['ord']} ({it['episode_id']}): video nguồn không còn trên đĩa")
                it.update(source_kind=src["kind"], source_path=src["path"], source_offset=src["offset"])
        _set(job_id, status="building", error=None)
        _ensure_zoom(job_id, [p["item"] for p in plan if p["type"] == "clip"], parts)
        narr = [p for p in plan if p["type"] == "narration"]
        for n, p in enumerate(narr, 1):
            _check_stop(job_id)
            _progress(job_id, f"ElevenLabs đọc lời dẫn {n}/{len(narr)} ({p['label']})")
            voice = parts / f"voice_{_key(p['text'], db.get_setting('compile_voice_id'), db.get_setting('compile_tts_model'))}.mp3"
            p["voice"], p["voice_sec"] = voice, _tts(p["text"], voice)
        files = []
        for n, p in enumerate(plan, 1):
            _check_stop(job_id)
            if p["type"] == "clip":
                it = p["item"]
                _progress(job_id, f"cắt clip {it['ord']} ({it['episode_id']}, {it['dur'] // 60}:{it['dur'] % 60:02d}) · "
                                  f"phần {n}/{len(plan)}")
                f = parts / f"clip_{_key(it['play_path'], it['start_sec'], it['end_sec'], W, H)}.mp4"
                _clip_part({**it, "source_path": it["play_path"], "source_offset": it["play_offset"]}, f)
            else:
                _progress(job_id, f"dựng khung lời dẫn {p['label']} · phần {n}/{len(plan)}")
                nx = p["next"]
                f = parts / f"card_{_key(p['voice'].name, nx['play_path'], nx['start_sec'], db.get_setting('compile_card_text'))}.mp4"
                _card_part(p["text"], p["voice"], p["voice_sec"],
                           {"path": nx["play_path"], "start_sec": nx["start_sec"], "source_offset": nx["play_offset"]},
                           f, parts)
            p["file"] = f
            files.append(f)
        _check_stop(job_id)
        _progress(job_id, f"ghép {len(files)} phần thành một video")
        lst = parts / "concat.txt"
        lst.write_text("".join(f"file '{f.name}'\n" for f in files), encoding="utf-8")
        slug = slugify(job.get("title_en") or job.get("topic_en") or "tong-hop", 60)
        final = folder / f"{slug}.mp4"
        tmp = folder / f"{slug}.tmp.mp4"
        _run([config.FFMPEG, "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst.name, "-c", "copy",
              "-movflags", "+faststart", tmp.resolve()], cwd=parts)
        tmp.replace(final)
        _write_sidecars(job, plan, folder, slug)
        total = ffprobe_duration(final)
        _set(job_id, status="done", out_dir=str(folder), final_path=str(final), final_sec=total, error=None,
             progress_msg=f"xong · {sec_to_hms(total)} · {final}")
        log.info("compile %s built %s (%.0fs)", job_id, final, total)
        _note(job_id, "done", "Video tổng hợp đã dựng xong", f"{sec_to_hms(total)} · {final.name}")
    except Exception as e:  # noqa: BLE001
        log.exception("compile %s build failed", job_id)
        _set(job_id, status="failed" if not items(job_id) else "review", error=f"dựng lỗi: {e}"[:1000])
        _note(job_id, "error", "Dựng video tổng hợp lỗi", str(e))
    finally:
        _stop.discard(job_id)


def _yt_stamp(sec: float, long: bool) -> str:
    """YouTube description timestamp: 0:00 / 12:34 under an hour, 0:00:00 / 1:02:03 from an hour up."""
    s = int(sec)
    h, m, x = s // 3600, s % 3600 // 60, s % 60
    return f"{h}:{m:02d}:{x:02d}" if long else f"{m}:{x:02d}"


def chapter_lines(plan: list[dict], durs: list[float]) -> list[str]:
    """One chapter per clip. A chapter starts at the narration that leads into its clip (intro / bridge), so a click
    on it lands on the set-up of that clip; the first one is at 0:00 as YouTube requires."""
    long = sum(durs) >= 3600
    t, start, out = 0.0, None, []
    for p, d in zip(plan, durs):
        if start is None:
            start = t
        if p["type"] == "clip":
            it = p["item"]
            title = re.sub(r"\s+", " ", it.get("title") or f"Clip {it.get('ord')}").strip()
            guest = (it.get("guest") or "").strip()
            out.append(f"{_yt_stamp(0 if not out else start, long)} {title}" + (f" ({guest})" if guest and guest not in title else ""))
            start = None
        t += d
    # the outro has no clip after it: it stays in the last chapter
    return out


def _write_chapters(folder: Path, plan: list[dict], durs: list[float]) -> list[str]:
    lines = chapter_lines(plan, durs)
    (folder / "chapters.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    write_json(folder / "timeline.json", [{"type": p["type"], "file": Path(p["file"]).name, "sec": round(d, 3),
                                           "item_id": p["item"]["id"] if p["type"] == "clip" else None,
                                           "label": p.get("label")} for p, d in zip(plan, durs)])
    return lines


def refresh_chapters(job_id: int) -> dict:
    """Re-writes chapters.txt of a built video from the parts it was joined from (parts/concat.txt), e.g. for a video
    built before chapters started at the narration. Clip titles come from the current arc."""
    job = get_job(job_id)
    if not job or not job.get("out_dir"):
        return {"error": "video chưa dựng"}
    if busy(job_id):
        return {"error": "video đang chạy"}
    folder = Path(job["out_dir"])
    lst = folder / "parts" / "concat.txt"
    if not lst.is_file():
        return {"error": "không còn thư mục parts của lần dựng: bấm Dựng lại video"}
    names = re.findall(r"^file '(.+)'$", lst.read_text(encoding="utf-8"), re.M)
    plan = _plan_parts(job)
    kinds = ["clip" if n.startswith("clip_") else "narration" for n in names]
    if kinds != [p["type"] for p in plan]:
        return {"error": "mạch đã đổi so với lần dựng (thêm/bỏ/đổi lời dẫn): bấm Dựng lại video để có mốc đúng"}
    files = [folder / "parts" / n for n in names]
    if not all(f.is_file() for f in files):
        return {"error": "thiếu file phần trong thư mục parts: bấm Dựng lại video"}
    for p, f in zip(plan, files):
        p["file"] = f
    lines = _write_chapters(folder, plan, [ffprobe_duration(f) for f in files])
    return {"ok": True, "chapters": "\n".join(lines), "message": f"đã tạo lại {len(lines)} mốc"}


def _write_sidecars(job: dict, plan: list[dict], folder: Path, slug: str) -> None:
    """chapters.txt (YouTube timestamps), timeline.json, compilation_<slug>.json (arc + narration), cut_multi_<slug>.json."""
    chapters = _write_chapters(folder, plan, [ffprobe_duration(p["file"]) for p in plan])
    clips = [p["item"] for p in plan if p["type"] == "clip"]
    write_json(folder / f"compilation_{slug}.json", {
        "version": 2, "type": "rabbit-hole-compilation", "source": "jre-studio video tổng hợp", "theme": job.get("topic_en"),
        "title": job.get("title_en"), "seed_segment_id": job["seed_segment_id"], "chapters": chapters,
        "source_episodes": sorted({c["episode_id"] for c in clips}),
        "narration": {"engine": "elevenlabs (Creater Vid gen.py)", "voice_id": db.get_setting("compile_voice_id") or "Creater: en",
                      "intro_v3": job.get("intro_text"), "outro_v3": job.get("outro_text")},
        "arc": [{"order": n, "role": c["role"], "episode_id": c["episode_id"], "source_video": Path(c["source_path"]).name,
                 "start": sec_to_hms(c["start_sec"]), "end": sec_to_hms(c["end_sec"]), "title": c["title"],
                 "why": c.get("why_vi"), "bridge_out_v3": c.get("bridge_text") if n < len(clips) else None}
                for n, c in enumerate(clips, 1)],
    })
    full = [c for c in clips if c["source_kind"] == "full"]
    write_json(folder / f"cut_multi_{slug}.json", {
        "version": 2, "type": "multi-source-cutlist", "theme": job.get("topic_en"), "source": "jre-studio video tổng hợp",
        "source_episodes": sorted({c["episode_id"] for c in full}),
        "segments": [{"order": n, "episode_id": c["episode_id"], "source_video": Path(c["source_path"]).name,
                      "start": sec_to_hms(c["start_sec"]), "end": sec_to_hms(c["end_sec"]), "title": c["title"]}
                     for n, c in enumerate(clips, 1) if c["source_kind"] == "full"],
    })


def chapters_text(job: dict) -> str:
    if job.get("out_dir"):
        p = Path(job["out_dir"]) / "chapters.txt"
        if p.is_file():
            return p.read_text(encoding="utf-8")
    return ""


def recover_after_restart() -> None:
    """Threads die with the process: a job cut short goes back to a state the user can resume from."""
    with db.tx() as c:
        c.execute("UPDATE compile_jobs SET status='failed', error='studio khởi động lại giữa chừng' "
                  "WHERE status IN ('queued','topic','scanning')")
        c.execute("UPDATE compile_jobs SET status=CASE WHEN EXISTS(SELECT 1 FROM compile_items i WHERE i.job_id=compile_jobs.id) "
                  "THEN 'review' ELSE 'failed' END, error='studio khởi động lại giữa chừng' WHERE status IN ('arranging','building')")
