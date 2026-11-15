"""Topic compilation from FULL episodes: keyword filter on the machine first, Claude reads only the windows.

1. find_windows(): regex over transcript_lines (free, local), every hit padded by ±pad seconds, overlaps merged.
2. run_scan(): the windows go to Claude in batches (no tools, isolated); Claude returns the self-contained passages
   that are really about the topic. Times are snapped to transcript lines.
3. Each passage gets a source: the full episode video when it is still on disk, otherwise the highlight clip that
   contains it (offset by the clip start), otherwise "missing" (the source video was deleted and no clip covers it).
4. export_cutlist() writes cut_multi_<slug>.json for Video Cutter (multi-source mode), cut_scan() cuts everything
   through the Cutter's headless API into media_root/Tong-hop/<slug>-<id>/ in compilation order.
"""
from __future__ import annotations

import json
import logging
import re
import threading
import time
from pathlib import Path

from .. import config, db, paths, podcasts
from ..util import now_iso, sec_to_hms, slugify, write_json
from . import claude_runner, tools
from .cut import wait_cutter_idle

log = logging.getLogger("studio.topic_scan")
CHARS_PER_TOKEN = 4
BATCH_TOKENS = 60_000          # transcript tokens per Claude call
PROMPT_OVERHEAD = 1_500        # instructions per call
OUT_DIR_NAME = "_tong-hop"

_threads: dict[int, threading.Thread] = {}
_stop: set[int] = set()


# ---------------------------------------------------------------- keywords + windows
def keyword_regex(keywords: list[str]) -> re.Pattern | None:
    """`ufo, alien*, flying saucer` -> word-boundary regex; `*` = any word ending, spaces = any whitespace."""
    parts = []
    for k in keywords:
        k = k.strip().lower()
        if not k:
            continue
        p = re.escape(k).replace(r"\*", r"\w*").replace(r"\ ", r"\s+")
        parts.append(p)
    if not parts:
        return None
    return re.compile(r"(?<!\w)(?:" + "|".join(parts) + r")(?!\w)", re.I)


def parse_keywords(text: str) -> list[str]:
    return [k.strip() for k in re.split(r"[,\n;]+", text or "") if k.strip()]


def find_windows(keywords: list[str], pad_sec: float = 120, episode_ids: list[str] | None = None,
                 podcast_ids: list[str] | None = None) -> list[dict]:
    """[{episode_id, guest, start, end, hits, lines:[(start, end, text)]}] in episode order.
    podcast_ids limits the scan to those shows (None = every show)."""
    rx = keyword_regex(keywords)
    if not rx:
        return []
    q = "SELECT episode_id, start_sec, end_sec, text FROM transcript_lines"
    where, params = [], []
    if episode_ids:
        where.append(f"episode_id IN ({','.join('?' * len(episode_ids))})")
        params += episode_ids
    if podcast_ids:
        where.append(f"episode_id IN (SELECT id FROM episodes WHERE podcast_id IN ({','.join('?' * len(podcast_ids))}))")
        params += [p.upper() for p in podcast_ids]
    if where:
        q += " WHERE " + " AND ".join(where)
    by_ep: dict[str, list] = {}
    for r in db.get_conn().execute(q + " ORDER BY episode_id, seq", params):
        by_ep.setdefault(r["episode_id"], []).append((r["start_sec"] or 0.0, r["end_sec"] or 0.0, r["text"] or ""))
    meta = {r["id"]: r for r in db.rows("SELECT id, guest, podcast_id, COALESCE(title, source_video) AS title FROM episodes")}
    out = []
    for ep, lines in by_ep.items():
        iv: list[list] = []
        for s, e, t in lines:
            if rx.search(t):
                a, b = s - pad_sec, e + pad_sec
                if iv and a <= iv[-1][1]:
                    iv[-1][1] = max(iv[-1][1], b)
                    iv[-1][2] += 1
                else:
                    iv.append([a, b, 1])
        for a, b, hits in iv:
            win = [ln for ln in lines if ln[0] >= a and ln[0] <= b]
            if win:
                m = meta.get(ep) or {}
                out.append({"episode_id": ep, "guest": m.get("guest") or "", "start": win[0][0], "end": win[-1][1],
                            "hits": hits, "lines": win, "podcast_id": m.get("podcast_id"),
                            "show": podcasts.source_label(m.get("podcast_id"), m.get("title"))})
    return out


def _window_text(w: dict) -> str:
    body = "\n".join(f"[{sec_to_hms(s)}] {t.strip()}" for s, _, t in w["lines"])
    show = str(w.get("show") or "").replace('"', "'")
    return (f'<window episode="{w["episode_id"]}" show="{show}" from="{sec_to_hms(w["start"])}" '
            f'to="{sec_to_hms(w["end"])}">\n{body}\n</window>')


def _pods(podcast_id: str | None) -> list[str] | None:
    """'JRE' or 'JRE,BOTRO' (topic_scans.podcast_id) -> ['JRE', 'BOTRO']; empty = every show."""
    return podcasts.split_ids(podcast_id) or None


def estimate(keywords: list[str], pad_sec: float = 120, episode_ids: list[str] | None = None,
             podcast_id: str | None = None) -> dict:
    wins = find_windows(keywords, pad_sec, episode_ids, _pods(podcast_id))
    chars = sum(len(_window_text(w)) for w in wins)
    tokens = chars // CHARS_PER_TOKEN
    batches = max(1, -(-tokens // BATCH_TOKENS)) if wins else 0
    pods = _pods(podcast_id)
    if pods:
        total_chars = db.scalar("SELECT COALESCE(SUM(LENGTH(t.text)),0) FROM transcript_lines t JOIN episodes e "
                                f"ON e.id=t.episode_id WHERE e.podcast_id IN ({','.join('?' * len(pods))})", pods) or 0
    else:
        total_chars = db.scalar("SELECT COALESCE(SUM(LENGTH(text)),0) FROM transcript_lines") or 0
    per_ep: dict[str, int] = {}
    for w in wins:
        per_ep[w["episode_id"]] = per_ep.get(w["episode_id"], 0) + w["hits"]
    return {"episodes": len(per_ep), "windows": len(wins), "hits": sum(w["hits"] for w in wins),
            "minutes": round(sum(w["end"] - w["start"] for w in wins) / 60),
            "tokens": tokens + batches * PROMPT_OVERHEAD, "batches": batches,
            "full_tokens": total_chars // CHARS_PER_TOKEN,
            "per_episode": sorted(per_ep.items(), key=lambda x: -x[1])}


# ---------------------------------------------------------------- Claude
def _shows(podcast_id: str | None) -> str:
    """'podcast Joe Rogan Experience (host Joe Rogan)' for one show, every show's name for a cross-show scan."""
    pods = _pods(podcast_id)
    if pods and len(pods) == 1:
        return f"podcast {podcasts.label(podcasts.get(pods[0]))}"
    return f"podcast nhiều show ({podcasts.show_names(pods)}; thuộc tính show của mỗi vùng cho biết nguồn)"


def suggest_keywords(topic: str, podcast_id: str | None = None) -> dict:
    prompt = (f"Chủ đề tổng hợp video {_shows(podcast_id)} (transcript tiếng Anh): {topic}\n\n"
              "Liệt kê 12-25 từ khoá TIẾNG ANH để lọc transcript tìm mọi đoạn nói về chủ đề này: từ đồng nghĩa, "
              "thuật ngữ, tên người/tổ chức/sự kiện/địa danh tiêu biểu, cách nói thông tục. Dùng dấu * cho đuôi từ "
              "(abduct* khớp abducted, abduction). Tránh từ quá chung gây nhiễu. "
              "Chỉ trả về một dòng, các từ khoá cách nhau bằng dấu phẩy, không giải thích.")
    res = claude_runner.run(prompt, cwd=config.BASE_DIR, tools="", isolated=True, max_turns=1, timeout=300,
                            permission_mode="dontAsk", model=db.get_setting("claude_model_topic_keywords") or "haiku",
                            fallback_model="")
    line = (res.get("result") or res.get("text") or "").strip().splitlines()
    kws = parse_keywords(line[-1] if line else "")
    return {"ok": bool(kws), "keywords": kws, "error": None if kws else (res.get("error") or "không nhận được từ khoá"),
            "summary": claude_runner.describe_run(res)}


def _prompt(topic: str, batch: list[dict], podcast_id: str | None = None) -> str:
    return "\n".join([
        f"Bạn đang chọn nguyên liệu cho một video TỔNG HỢP nhiều tập {_shows(podcast_id)} theo chủ đề: «{topic}».",
        "Dưới đây là các vùng transcript (đã lọc sẵn bằng từ khoá, mỗi dòng có mốc [hh:mm:ss] tính từ đầu tập).",
        "",
        "Nhiệm vụ: chọn mọi đoạn THẬT SỰ nói về chủ đề, đáng xem, đứng một mình vẫn hiểu được (người xem không "
        "cần nghe đoạn trước). Bỏ đoạn chỉ nhắc lướt qua từ khoá, đùa vu vơ, quảng cáo.",
        "- Mỗi đoạn dài 40 giây đến 8 phút. Bắt đầu ở dòng mở đầu ý (câu hỏi hoặc câu dẫn), kết thúc ở dòng chốt ý.",
        "- start = mốc của dòng đầu tiên, end = mốc của dòng CUỐI CÙNG thuộc đoạn. Chép mốc nguyên văn từ transcript.",
        "- Không chọn hai đoạn chồng nhau trong cùng một tập.",
        "- score 1-10: độ hấp dẫn với người xem YouTube Mỹ + mức độ đúng chủ đề.",
        "",
        "Trả về DUY NHẤT một khối ```json chứa mảng (mảng rỗng [] nếu không có đoạn nào):",
        '[{"episode_id":"' + (batch[0]["episode_id"] if batch else "JRE-2545") + '","start":"01:02:03","end":"01:06:40","score":8,'
        '"title":"English YouTube-style title","summary_vi":"1-2 câu tóm tắt tiếng Việt",'
        '"reason_vi":"vì sao đáng chọn, ngắn"}]',
        "",
        *[_window_text(w) for w in batch],
    ])


def _parse_json(text: str) -> list[dict]:
    m = re.findall(r"```json\s*(.*?)```", text or "", re.S)
    raw = m[-1] if m else text
    a, b = raw.find("["), raw.rfind("]")
    if a < 0 or b < a:
        raise ValueError("Claude không trả về mảng JSON")
    data = json.loads(raw[a:b + 1])
    return [d for d in data if isinstance(d, dict)]


def _batches(wins: list[dict]) -> list[list[dict]]:
    out, cur, size = [], [], 0
    for w in wins:
        t = len(_window_text(w)) // CHARS_PER_TOKEN
        if cur and size + t > BATCH_TOKENS:
            out.append(cur)
            cur, size = [], 0
        cur.append(w)
        size += t
    if cur:
        out.append(cur)
    return out


def _hms(v) -> float:
    from ..util import hms_to_sec
    return float(hms_to_sec(v))


def _snap(item: dict, wins: list[dict]) -> dict | None:
    """Clamp the passage to the window it came from and to whole transcript lines."""
    ep = str(item.get("episode_id") or "").upper()
    try:
        s, e = _hms(item.get("start")), _hms(item.get("end"))
    except Exception:  # noqa: BLE001
        return None
    cands = [w for w in wins if w["episode_id"] == ep and w["start"] - 2 <= s <= w["end"] + 2]
    if not cands or e <= s:
        return None
    lines = cands[0]["lines"]
    first = min(lines, key=lambda ln: abs(ln[0] - s))
    last = min((ln for ln in lines if ln[0] >= first[0]), key=lambda ln: abs(ln[0] - e))
    start, end = first[0], max(last[1], last[0] + 1)
    if end - start < 15:
        return None
    return {**item, "episode_id": ep, "start_sec": start, "end_sec": end}


def _dedupe(items: list[dict]) -> list[dict]:
    items = sorted(items, key=lambda x: -(float(x.get("score") or 0)))
    kept: list[dict] = []
    for it in items:
        if any(k["episode_id"] == it["episode_id"] and it["start_sec"] < k["end_sec"] and k["start_sec"] < it["end_sec"]
               for k in kept):
            continue
        kept.append(it)
    return kept


def resolve_source(episode_id: str, start: float, end: float) -> dict:
    """Full episode video if it is still on disk, else a highlight clip that contains the passage, else missing."""
    ep = db.row("SELECT video_path, source_video FROM episodes WHERE id=?", (episode_id,)) or {}
    if ep.get("video_path") and Path(ep["video_path"]).is_file():
        return {"kind": "full", "path": ep["video_path"], "offset": 0.0}
    for s in db.rows("SELECT start_sec, end_sec, clip_path, clip_zoomed_path FROM segments WHERE episode_id=? "
                     "AND start_sec IS NOT NULL AND status NOT IN ('archived') AND start_sec<=? AND end_sec>=? "
                     "ORDER BY end_sec-start_sec", (episode_id, start + 1, end - 1)):
        for p in (s["clip_path"], s["clip_zoomed_path"]):
            if p and Path(p).is_file():
                return {"kind": "clip", "path": p, "offset": float(s["start_sec"])}
    return {"kind": "missing", "path": None, "offset": 0.0}


# ---------------------------------------------------------------- jobs
def _set(scan_id: int, **cols) -> None:
    cols["updated_at"] = now_iso()
    with db.tx() as c:
        c.execute(f"UPDATE topic_scans SET {', '.join(f'{k}=?' for k in cols)} WHERE id=?", (*cols.values(), scan_id))


def _note(scan_id: int, kind: str, what: str, body: str = "") -> None:
    from .. import notify
    if kind == "error" and scan_id in _stop:
        return
    sc = db.row("SELECT topic FROM topic_scans WHERE id=?", (scan_id,)) or {}
    notify.notify(kind, f"{what}: {(sc.get('topic') or f'#{scan_id}')[:90]}", body, "/compilations")


def start_scan(topic: str, keywords: list[str], pad_sec: float = 120, model: str = "", effort: str = "",
               episode_ids: list[str] | None = None, podcast_id: str | None = None) -> dict:
    if not topic.strip() or not keywords:
        return {"error": "cần chủ đề và ít nhất một từ khoá"}
    if podcast_id and not _pods(podcast_id):
        return {"error": f"không có show {podcast_id}"}
    podcast_id = ",".join(_pods(podcast_id) or []) or None
    est = estimate(keywords, pad_sec, episode_ids, podcast_id)
    if not est["windows"]:
        return {"error": "không có dòng transcript nào khớp từ khoá"}
    model = model or db.get_setting("claude_model_topic") or ""
    effort = effort or db.get_setting("claude_effort_topic") or ""
    with db.tx() as c:
        cur = c.execute("INSERT INTO topic_scans(topic, keywords, pad_sec, episode_ids, model, effort, status, "
                        "n_episodes, n_windows, est_tokens, created_at, updated_at, podcast_id) "
                        "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        (topic.strip(), ", ".join(keywords), pad_sec, ",".join(episode_ids or []), model, effort,
                         "queued", est["episodes"], est["windows"], est["tokens"], now_iso(), now_iso(), podcast_id))
        scan_id = cur.lastrowid
    t = threading.Thread(target=_run_scan, args=(scan_id,), name=f"topic-scan-{scan_id}", daemon=True)
    _threads[scan_id] = t
    t.start()
    return {"ok": True, "id": scan_id, "estimate": est}


def stop(scan_id: int) -> dict:
    _stop.add(scan_id)
    return {"message": "đã gửi lệnh dừng"}


def _run_scan(scan_id: int) -> None:
    sc = db.row("SELECT * FROM topic_scans WHERE id=?", (scan_id,))
    work = config.WORK_DIR / "topic_scans" / str(scan_id)
    work.mkdir(parents=True, exist_ok=True)
    try:
        kws = parse_keywords(sc["keywords"])
        wins = find_windows(kws, sc["pad_sec"], [e for e in (sc["episode_ids"] or "").split(",") if e] or None,
                            _pods(sc.get("podcast_id")))
        batches = _batches(wins)
        runs, picked = [], []
        for i, batch in enumerate(batches, 1):
            if scan_id in _stop:
                raise RuntimeError("dừng theo yêu cầu")
            _set(scan_id, status="running", summary=f"Claude đang đọc lô {i}/{len(batches)} ({len(batch)} vùng)")
            res = claude_runner.run(_prompt(sc["topic"], batch, sc.get("podcast_id")), cwd=config.BASE_DIR, tools="", isolated=True,
                                    max_turns=2, timeout=3600, permission_mode="dontAsk", model=sc["model"] or None,
                                    effort=sc["effort"] or None, log_path=work / f"batch_{i}.jsonl",
                                    stop_flag=lambda: scan_id in _stop)
            runs.append(res)
            (work / f"batch_{i}.md").write_text(res.get("text") or "", encoding="utf-8")
            if not res.get("ok"):
                raise RuntimeError(f"lô {i}: {res.get('error')}")
            try:
                items = _parse_json(res.get("result") or res.get("text") or "")
            except ValueError as e:
                raise RuntimeError(f"lô {i}: {e}") from e
            picked += [x for x in (_snap(it, batch) for it in items) if x]
        merged = claude_runner.merge_runs(runs)
        items = _dedupe(picked)
        with db.tx() as c:
            c.execute("DELETE FROM topic_scan_items WHERE scan_id=?", (scan_id,))
            for n, it in enumerate(items, 1):
                src = resolve_source(it["episode_id"], it["start_sec"], it["end_sec"])
                c.execute("INSERT INTO topic_scan_items(scan_id, ord, episode_id, start_sec, end_sec, title, summary_vi, "
                          "reason_vi, score, source_kind, source_path, source_offset) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                          (scan_id, n, it["episode_id"], it["start_sec"], it["end_sec"], str(it.get("title") or "")[:200],
                           it.get("summary_vi"), it.get("reason_vi"), float(it.get("score") or 0),
                           src["kind"], src["path"], src["offset"]))
        _set(scan_id, status="done", usage_json=json.dumps(merged.get("usage") or {}), cost_usd=merged.get("cost_usd"),
             summary=f"{len(items)} đoạn · {claude_runner.describe_run(merged)}", error=None)
        log.info("topic scan %s done: %d items", scan_id, len(items))
        _note(scan_id, "done", "Quét chủ đề xong", f"tìm được {len(items)} đoạn")
    except Exception as e:  # noqa: BLE001
        log.exception("topic scan %s failed", scan_id)
        _set(scan_id, status="failed", error=str(e)[:1000])
        _note(scan_id, "error", "Quét chủ đề lỗi", str(e))
    finally:
        _stop.discard(scan_id)


# ---------------------------------------------------------------- output
def items(scan_id: int) -> list[dict]:
    rows = db.rows("SELECT i.*, e.guest, e.source_video FROM topic_scan_items i LEFT JOIN episodes e ON e.id=i.episode_id "
                   "WHERE scan_id=? ORDER BY ord", (scan_id,))
    for r in rows:
        r["start_hms"], r["end_hms"] = sec_to_hms(r["start_sec"]), sec_to_hms(r["end_sec"])
        r["dur"] = round(r["end_sec"] - r["start_sec"])
    return rows


def out_dir(scan: dict) -> Path:
    return paths.tonghop_dir() / f"{slugify(scan['topic'])}-{scan['id']}"


def export_cutlist(scan_id: int) -> dict:
    """cut_multi_<slug>.json for Video Cutter (multi-source mode, source folder = media root)."""
    sc = db.row("SELECT * FROM topic_scans WHERE id=?", (scan_id,))
    its = [i for i in items(scan_id) if i["included"]]
    full = [i for i in its if i["source_kind"] == "full"]
    data = {
        "version": 2, "type": "multi-source-cutlist", "theme": sc["topic"], "source": "jre-studio topic scan",
        "source_episodes": sorted({i["episode_id"] for i in full}),
        "segments": [{"order": i["ord"], "episode_id": i["episode_id"], "source_video": Path(i["source_path"]).name,
                      "start": i["start_hms"], "end": i["end_hms"], "title": i["title"]} for i in full],
    }
    folder = out_dir(sc)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"cut_multi_{slugify(sc['topic'])}.json"
    write_json(path, data)
    _set(scan_id, cutlist_path=str(path))
    skipped = len(its) - len(full)
    return {"ok": True, "path": str(path), "count": len(full),
            "note": (f"{skipped} đoạn không có video gốc nên không nằm trong cutlist (dùng nút Cắt trong Studio để cắt "
                     "từ clip highlight)") if skipped else ""}


def start_cut(scan_id: int) -> dict:
    sc = db.row("SELECT * FROM topic_scans WHERE id=?", (scan_id,))
    if not sc:
        return {"error": "không có lượt quét này"}
    if sc["status"] in ("cutting",) or (scan_id in _threads and _threads[scan_id].is_alive()):
        return {"error": "lượt quét này đang chạy"}
    t = threading.Thread(target=_run_cut, args=(scan_id,), name=f"topic-cut-{scan_id}", daemon=True)
    _threads[scan_id] = t
    t.start()
    return {"ok": True, "message": "đang cắt, xem tiến độ ở dòng của lượt quét"}


def _run_cut(scan_id: int) -> None:
    sc = db.row("SELECT * FROM topic_scans WHERE id=?", (scan_id,))
    prev_status = sc["status"]
    try:
        its = [i for i in items(scan_id) if i["included"] and i["source_kind"] in ("full", "clip")]
        # Sources can change after the scan (video re-downloaded, source auto-deleted): resolve again.
        for i in its:
            src = resolve_source(i["episode_id"], i["start_sec"], i["end_sec"])
            i.update(source_kind=src["kind"], source_path=src["path"], source_offset=src["offset"])
        its = [i for i in its if i["source_path"]]
        if not its:
            raise RuntimeError("không có đoạn nào còn nguồn video để cắt")
        folder = out_dir(sc)
        folder.mkdir(parents=True, exist_ok=True)
        groups: dict[str, list[dict]] = {}
        for i in its:
            groups.setdefault(i["source_path"], []).append(i)
        base = tools.ensure_tool("cutter")
        done = 0
        for gi, (video, group) in enumerate(groups.items(), 1):
            if scan_id in _stop:
                raise RuntimeError("dừng theo yêu cầu")
            _set(scan_id, status="cutting", summary=f"cắt nguồn {gi}/{len(groups)} · {done}/{len(its)} đoạn xong")
            wait_cutter_idle(base, stop_flag=lambda: scan_id in _stop)
            payload = {"video_path": video, "output_dir": str(folder), "write_sidecars": False,
                       "segments": [{"index": i["ord"], "title": i["title"] or f"Clip {i['ord']}",
                                     "start": sec_to_hms(max(0.0, i["start_sec"] - i["source_offset"])),
                                     "end": sec_to_hms(i["end_sec"] - i["source_offset"])} for i in group]}
            for _ in range(60):
                res = tools.post_json(f"{base}/api/cut-headless", payload, timeout=60)
                if res.get("_status") != 409:
                    break
                time.sleep(5)
            if res.get("error"):
                raise RuntimeError(f"Cutter từ chối: {res['error']}")
            while True:
                time.sleep(2)
                st = tools.get_json(f"{base}/api/cut/status", timeout=30)
                if st.get("status") in ("done", "error", "idle"):
                    break
            if st.get("status") == "error":
                raise RuntimeError(f"Cutter lỗi: {st.get('error')}")
            with db.tx() as c:
                for r in st.get("results") or []:
                    if r.get("status") == "done" and r.get("file"):
                        c.execute("UPDATE topic_scan_items SET clip_path=? WHERE scan_id=? AND ord=?",
                                  (r["file"], scan_id, int(r.get("index") or 0)))
                        done += 1
        _set(scan_id, status=prev_status if prev_status not in ("cutting",) else "done", out_dir=str(folder),
             summary=(sc["summary"] or "").split(" · cắt ")[0] + f" · cắt {done}/{len(its)} đoạn vào {folder}")
        _note(scan_id, "done", "Cắt đoạn compilation xong", f"{done}/{len(its)} đoạn")
    except Exception as e:  # noqa: BLE001
        log.exception("topic cut %s failed", scan_id)
        _set(scan_id, status=prev_status if prev_status != "cutting" else "done", error=f"cắt lỗi: {e}"[:1000])
        _note(scan_id, "error", "Cắt đoạn compilation lỗi", str(e))
    finally:
        _stop.discard(scan_id)
