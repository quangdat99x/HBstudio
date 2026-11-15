"""Phim tài liệu bổ sung: a highlight whose hook is already joined gets a documentary that plays right after it.

1. Studio creates a Creater Vid project (documentary desk, picture pipeline `dossier` = real photos, document pages,
   real footage), with the highlight's transcript + analysis as its source and a brief that says the film is the next
   chapter of the highlight (no retelling), and starts step 1. Creater runs its own steps (Tự chạy by default).
2. A poller watches the Creater project. When its render step is approved (auto mode approves it after QA; step by
   step = the user approves it in Creater), the newest render is the documentary.
3. Studio writes ONE bridging line (Claude), reads it with ElevenLabs (Creater's gen.py, same voice as Video tổng
   hợp), shows it on a card over a blurred frame of the documentary, and joins
   [highlight + hook (file never modified)] + [bridge card] + [documentary] → <hooked stem>_DOC.mp4 next to it.
"""
from __future__ import annotations

import json
import logging
import re
import shutil
import sqlite3
import subprocess
import threading
import time
from pathlib import Path

from .. import config, db, podcasts
from ..util import ffprobe_duration, media_ok, now_iso, sec_to_hms
from . import claude_runner, tools
from .compile_video import FONT, H, W, _audio_args, _key, _parse_obj, _say_text, _tts, _video_encoder, _wrap

log = logging.getLogger("studio.docext")

CREATER_DB = config.CREATER_DIR / "creater.db"
POLL_SEC = 30
_NO_WIN = 0x08000000 if hasattr(subprocess, "CREATE_NO_WINDOW") else 0
_HOOKED = re.compile(r"_HOOK\d{2}\.mp4$", re.I)

_threads: dict[int, threading.Thread] = {}
_poller: threading.Thread | None = None
_lock_poller = threading.Lock()
_lock = threading.Lock()                      # one join (full re-encode) at a time


# ---------------------------------------------------------------- small helpers
def _set(job_id: int, **cols) -> None:
    cols["updated_at"] = now_iso()
    with db.tx() as c:
        c.execute(f"UPDATE docext_jobs SET {', '.join(f'{k}=?' for k in cols)} WHERE id=?", (*cols.values(), job_id))


def _note(job_id: int, kind: str, what: str, body: str = "") -> None:
    from .. import notify
    from .orchestrator import ep_label, ep_link
    r = db.row("SELECT s.id, s.rank, s.title, s.episode_id FROM docext_jobs j JOIN segments s ON s.id=j.segment_id "
               "WHERE j.id=?", (job_id,))
    if not r:
        notify.notify(kind, what, body)
        return
    notify.notify(kind, f"{what}: đoạn #{r['rank'] or '?'} {(r['title'] or '')[:60]}",
                  f"{ep_label(r['episode_id'])}" + (f" · {body}" if body else ""), ep_link(r["episode_id"], r["id"]))


def get_job(job_id: int) -> dict | None:
    return db.row("SELECT * FROM docext_jobs WHERE id=?", (job_id,))


def work_dir(job_id: int) -> Path:
    d = config.BASE_DIR / "work" / "docext" / str(job_id)
    d.mkdir(parents=True, exist_ok=True)
    return d


def creater_url(pid: int | None) -> str | None:
    return f"http://127.0.0.1:{config.PORT_CREATER}/p/{pid}" if pid else None


def hooked_files(seg: dict) -> list[str]:
    """The highlight + hook files of a highlight (<zoomed stem>_HOOKNN.mp4 made by Nối hook)."""
    z = seg.get("clip_zoomed_path")
    if not z:
        return []
    z = Path(z)
    if not z.parent.is_dir():
        return []
    return [str(f) for f in sorted(z.parent.glob(f"{z.stem}_HOOK*.mp4")) if _HOOKED.search(f.name)]


def out_path(hooked: str | Path) -> Path:
    h = Path(hooked)
    return h.with_name(f"{h.stem}_DOC.mp4")


def _creater_rows(sql: str, params: tuple = ()) -> list[dict]:
    """Read creater.db directly (same machine): works even while Creater's server is busy rendering."""
    if not CREATER_DB.is_file():
        return []
    conn = sqlite3.connect(f"file:{CREATER_DB}?mode=ro", uri=True, timeout=10)
    conn.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in conn.execute(sql, params)]
    finally:
        conn.close()


STEP_NAMES = {"script": "1 · Kịch bản", "cast": "2 · Nhân vật", "scenes": "3 · Phân cảnh", "images": "4 · Hình ảnh",
              "footage": "5 · Footage & âm thanh", "render": "6 · Dựng & render", "metadata": "7 · Metadata"}
STATUS_VI = {"ready": "chờ chạy", "queued": "trong hàng đợi", "running": "đang chạy", "review": "chờ duyệt",
             "approved": "đã duyệt", "failed": "lỗi", "locked": "chưa tới"}


def creater_steps(pid: int) -> list[dict]:
    return _creater_rows("SELECT step, status, error FROM project_steps WHERE project_id=? ORDER BY rowid", (pid,))


def _creater_progress(pid: int) -> str:
    steps = creater_steps(pid)
    if not steps:
        return "không thấy dự án trong Creater Vid (đã bị xoá?)"
    cur = next((s for s in steps if s["status"] in ("running", "queued", "failed", "review", "ready")), steps[-1])
    busy = _creater_rows("SELECT progress_msg FROM messages WHERE project_id=? AND status IN ('queued','running') "
                         "ORDER BY id DESC LIMIT 1", (pid,))
    msg = f"Creater: bước {STEP_NAMES.get(cur['step'], cur['step'])} · {STATUS_VI.get(cur['status'], cur['status'])}"
    if cur["status"] == "failed" and cur.get("error"):
        msg += f" ({cur['error'][:160]}) — mở dự án Creater để xử lý"
    elif cur["status"] == "review":
        msg += " — mở dự án Creater để duyệt"
    if busy and busy[0].get("progress_msg"):
        msg += f" · {busy[0]['progress_msg'][:160]}"
    return msg


def _latest_render(creater_dir: str) -> Path | None:
    d = Path(creater_dir)
    try:
        r = json.loads((d / "6_render" / "render.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    versions = [v for v in (r.get("versions") or []) if isinstance(v, dict) and v.get("file")]
    for v in reversed(versions):
        f = d / v["file"]
        if f.is_file():
            return f
    return None


# ---------------------------------------------------------------- public API
def jobs_of(segment_id: int) -> list[dict]:
    return db.rows("SELECT * FROM docext_jobs WHERE segment_id=? ORDER BY id DESC", (segment_id,))


def state(segment_id: int) -> dict | None:
    """Latest job of a highlight, for the episode page."""
    js = jobs_of(segment_id)
    if not js:
        return None
    j = dict(js[0])
    j["creater_url"] = creater_url(j.get("creater_pid"))
    if j.get("final_path") and not Path(j["final_path"]).is_file():
        j["final_missing"] = True
    return j


def create(segment_id: int, hooked: str, target_min: int, note: str = "", budget_usd: float | None = None,
           auto_advance: bool = True, use_jre: bool = False, bridge: str = "") -> dict:
    seg = db.row("SELECT * FROM segments WHERE id=?", (segment_id,))
    if not seg or seg["kind"] != "highlight":
        return {"error": "không phải đoạn highlight"}
    choices = hooked_files(seg)
    if not choices:
        return {"error": "đoạn này chưa có bản đã nối hook: bấm 🎬 Nối vào bản zoom ở một hook trước"}
    hooked = hooked if hooked in choices else choices[0]
    busy = db.row("SELECT id FROM docext_jobs WHERE segment_id=? AND status IN ('creating','filming','joining')",
                  (segment_id,))
    if busy:
        return {"error": f"đoạn này đang làm phim tài liệu (job #{busy['id']})"}
    target_min = max(2, min(60, int(target_min or 10)))
    now = now_iso()
    with db.tx() as c:
        c.execute("""INSERT INTO docext_jobs(segment_id, hooked_path, target_min, note, budget_usd, auto_advance, use_jre,
                     status, progress_msg, bridge_text, bridge_user, created_at, updated_at)
                     VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                  (segment_id, hooked, target_min, (note or "").strip() or None, budget_usd, 1 if auto_advance else 0,
                   1 if use_jre else 0, "creating", "đang tạo dự án trong Creater Vid…", (bridge or "").strip() or None,
                   1 if (bridge or "").strip() else 0, now, now))
        job_id = c.execute("SELECT last_insert_rowid()").fetchone()[0]
    _spawn(job_id, _run_create)
    start_poller()
    return {"id": job_id, "message": f"đang tạo dự án phim tài liệu ~{target_min} phút trong Creater Vid"}


def rejoin(job_id: int, bridge: str | None = None) -> dict:
    """Join again (newer render approved in Creater, or a new bridge line). bridge='' = let Claude rewrite it."""
    job = get_job(job_id)
    if not job:
        return {"error": "không thấy job"}
    if job["status"] in ("creating", "joining"):
        return {"error": "job đang chạy"}
    doc = _latest_render(job["creater_dir"] or "") if job.get("creater_dir") else None
    if not doc:
        return {"error": "Creater chưa có bản render nào của phim này"}
    if bridge is not None:
        b = bridge.strip()
        _set(job_id, bridge_text=b or None, bridge_user=1 if b else 0)
    _set(job_id, status="joining", error=None, doc_path=str(doc), progress_msg="chờ tới lượt nối…")
    _spawn(job_id, _run_join)
    return {"message": "đang nối lại phim tài liệu vào sau highlight"}


def stop(job_id: int) -> dict:
    job = get_job(job_id)
    if not job:
        return {"error": "không thấy job"}
    if job["status"] in ("done", "failed", "stopped"):
        return {"message": "job không chạy"}
    _set(job_id, status="stopped", progress_msg="đã dừng theo dõi (dự án trong Creater Vid vẫn còn, dừng nó ở Creater nếu cần)")
    return {"message": "đã dừng theo dõi; dự án Creater giữ nguyên"}


# ---------------------------------------------------------------- step 1: the Creater project
def _source_md(seg: dict, ep: dict) -> str:
    lines = db.rows("SELECT start_sec, text FROM transcript_lines WHERE episode_id=? AND start_sec>=? AND start_sec<=? "
                    "ORDER BY seq", (seg["episode_id"], seg["start_sec"] - 1, seg["end_sec"]))
    body = "\n".join(f"[{sec_to_hms(r['start_sec'])}] {r['text'].strip()}" for r in lines) or (seg.get("transcript") or "")
    hooks = db.rows("SELECT start_sec, end_sec FROM segments WHERE parent_id=? AND kind='hook' AND status!='archived' "
                    "ORDER BY start_sec", (seg["id"],))
    parts = [
        f"# Highlight {podcasts.for_episode(seg['episode_id'])['name']}: {seg['title']}",
        "",
        f"- Tập: {ep.get('id')} · khách mời: {ep.get('guest') or '?'}",
        f"- Thời gian trong tập: {sec_to_hms(seg['start_sec'])} → {sec_to_hms(seg['end_sec'])} "
        f"(~{round((seg['end_sec'] - seg['start_sec']) / 60)} phút)",
        f"- Keyword hạt nhân: {seg.get('core_keyword') or ''}",
        f"- Hook (cold open của video, cắt từ chính đoạn này): "
        + ("; ".join(f"{sec_to_hms(h['start_sec'])}–{sec_to_hms(h['end_sec'])}" for h in hooks) or "không có"),
        "",
        "## Tóm tắt",
        seg.get("summary_vi") or seg.get("summary_en") or "",
        "",
    ]
    if seg.get("analysis_md"):
        parts += ["## Khối phân tích (skill chọn nội dung)", seg["analysis_md"], ""]
    parts += ["## Transcript nguyên văn của đoạn highlight (người xem vừa nghe trọn đoạn này)", "", body]
    return "\n".join(parts)


def _brief(seg: dict, ep: dict, job: dict) -> str:
    prof = podcasts.for_episode(ep or seg["episode_id"])
    b = (
        f"PHIM TÀI LIỆU BỔ SUNG cho đoạn highlight podcast {prof['name']} «{seg['title']}» (tập {ep.get('id')}, "
        f"khách {ep.get('guest') or '?'}). "
        "Phim phát NGAY SAU đoạn highlight (đã có hook cold open) trong CÙNG một video YouTube, nối bằng một câu dẫn ngắn do "
        "Hổ Báo Studio viết. Người xem vừa nghe trọn đoạn highlight: transcript và phân tích ở sources/highlight.md.\n"
        "Yêu cầu:\n"
        "1. Đây là chương tiếp theo, không phải phim độc lập: KHÔNG kể lại, không tóm tắt đoạn highlight, không giới thiệu "
        f"lại {prof['host']} hay khách mời, không cold open kiểu mở đầu kênh. Vào thẳng phần đào sâu.\n"
        "2. Bám sát đúng những gì được nói trong highlight: các văn bản, hiện vật, địa danh, nhân vật, giả thuyết, con số "
        "được nhắc tới. Bổ sung bối cảnh lịch sử, bằng chứng gốc (ảnh hiện vật, trang bản thảo, bài báo khoa học, trang "
        "tài liệu thật), góc nhìn học thuật đối lập, phát hiện mới nhất. Chỗ nào là giả thuyết hay còn tranh cãi thì nói rõ "
        "và kiểm chứng (đúng / sai / chưa rõ) những khẳng định trong highlight.\n"
        "3. Dựng theo HỒ SƠ TƯ LIỆU THẬT (pipeline dossier): ảnh, tài liệu, footage thật là chính; AI chỉ tái hiện cảnh "
        "không thể có ảnh.\n"
        f"4. Thời lượng mục tiêu khoảng {job['target_min']} phút (không cần chính xác, nhưng đừng vượt quá nhiều): chọn "
        "những luận điểm đắt nhất cho vừa thời lượng.\n"
        "5. Không dùng lại clip của chính đoạn highlight này (người xem vừa xem xong).\n"
        f"6. Giọng tiếng Anh, khán giả kênh {prof['channel']} ({prof.get('audience') or 'Mỹ'}). Kết phim gọn, có dư âm, "
        "không kêu gọi subscribe dài."
    )
    if job.get("note"):
        b += f"\nYêu cầu riêng của người dùng: {job['note']}"
    return b


def _run_create(job_id: int) -> None:
    job = get_job(job_id)
    seg = db.row("SELECT * FROM segments WHERE id=?", (job["segment_id"],))
    ep = db.row("SELECT * FROM episodes WHERE id=?", (seg["episode_id"],)) or {}
    base = tools.ensure_tool("creater", timeout=120)
    src = work_dir(job_id) / "highlight.md"
    src.write_text(_source_md(seg, ep), encoding="utf-8")
    payload = {"kind": "doc", "title": f"{seg['title']} (Documentary)", "topic": seg["title"],
               "brief": _brief(seg, ep, job), "language": "en", "format": "16:9", "target_sec": job["target_min"] * 60,
               "pipeline": "dossier", "auto_advance": bool(job["auto_advance"]), "use_jre": bool(job["use_jre"])}
    if job.get("budget_usd") is not None:
        payload["budget_usd"] = job["budget_usd"]
    res = tools.post_json(f"{base}/api/projects", payload, timeout=60)
    if res.get("error") or not res.get("id"):
        raise RuntimeError(f"Creater Vid không tạo được dự án: {res.get('error')}")
    pid = int(res["id"])
    row = (_creater_rows("SELECT dir FROM projects WHERE id=?", (pid,)) or [{}])[0]
    _set(job_id, creater_pid=pid, creater_dir=row.get("dir"), progress_msg="đang gửi tư liệu cho Creater…")
    import requests
    with open(src, "rb") as fh:
        r = requests.post(f"{base}/api/p/{pid}/sources", files=[("files", ("highlight.md", fh, "text/markdown"))],
                          timeout=60)
    if r.status_code >= 400:
        raise RuntimeError(f"Creater Vid không nhận tư liệu: HTTP {r.status_code} {r.text[:200]}")
    run = tools.post_json(f"{base}/api/p/{pid}/run", {"step": "script"}, timeout=60)
    if run.get("error"):
        raise RuntimeError(f"Creater Vid không chạy được bước Kịch bản: {run['error']}")
    _set(job_id, status="filming", progress_msg="Creater: bước 1 · Kịch bản · trong hàng đợi")
    start_poller()
    log.info("docext %s: Creater project %s for segment %s", job_id, pid, seg["id"])


# ---------------------------------------------------------------- step 2: wait for Creater
def start_poller() -> None:
    global _poller
    with _lock_poller:
        if _poller and _poller.is_alive():
            return
        _poller = threading.Thread(target=_poll_loop, name="docext-poller", daemon=True)
        _poller.start()


def _poll_loop() -> None:
    while True:
        try:
            # a job still being created counts: the poller starts with create(), before the job reaches filming
            jobs = db.rows("SELECT * FROM docext_jobs WHERE status IN ('creating','filming')")
            if not jobs:
                return                    # restarted by the next create() / recover
            for job in jobs:
                if job["status"] == "filming":
                    _poll_one(job)
        except Exception as e:  # noqa: BLE001
            log.warning("docext poll: %s", e)
        time.sleep(POLL_SEC)


def _poll_one(job: dict) -> None:
    pid = job.get("creater_pid")
    if not pid:
        return
    steps = {s["step"]: s["status"] for s in creater_steps(pid)}
    if steps.get("render") == "approved":
        doc = _latest_render(job["creater_dir"] or "")
        if doc:
            _set(job["id"], status="joining", doc_path=str(doc), progress_msg="Creater đã render xong · chờ tới lượt nối…")
            _spawn(job["id"], _run_join)
            return
    msg = _creater_progress(pid)
    if not tools.port_open(config.PORT_CREATER):
        msg = "Creater Vid đang tắt — bật lại để phim chạy tiếp · " + msg
    if msg != job.get("progress_msg"):
        _set(job["id"], progress_msg=msg)


# ---------------------------------------------------------------- step 3: bridge line + join
def _bridge_prompt(seg: dict, job: dict) -> str:
    tail = db.rows("SELECT start_sec, text FROM transcript_lines WHERE episode_id=? AND start_sec>=? AND start_sec<=? "
                   "ORDER BY seq", (seg["episode_id"], seg["end_sec"] - 90, seg["end_sec"]))
    tail_txt = "\n".join(f"[{sec_to_hms(r['start_sec'])}] {r['text'].strip()}" for r in tail)
    opening = ""
    try:
        sc = json.loads((Path(job["creater_dir"]) / "1_script" / "script.json").read_text(encoding="utf-8"))
        beats = [b.get("narration", "") for b in (sc.get("beats") or [])[:4] if isinstance(b, dict)]
        opening = f"Title: {sc.get('title', '')}\nLogline: {sc.get('logline', '')}\nThesis: {sc.get('thesis', '')}\n" \
                  "First narration lines:\n" + "\n".join(f"- {_say_text(b)}" for b in beats if b)
    except (OSError, ValueError, TypeError):
        pass
    prof = podcasts.for_episode(seg["episode_id"])
    return (
        f"You write ONE spoken bridging line for a YouTube video of the channel {prof['channel']}.\n"
        f"The video plays a {prof['name']} highlight, then a documentary that digs deeper into the same subject. "
        "Your line is read by a narrator (ElevenLabs v3) between the two, over a blurred frame.\n\n"
        f"HIGHLIGHT: «{seg['title']}» (guest: {seg.get('guest') or '?'})\n"
        f"Summary: {seg.get('summary_en') or seg.get('summary_vi') or ''}\n"
        f"How the highlight ENDS (last 90 s):\n{tail_txt}\n\n"
        f"DOCUMENTARY that follows:\n{opening}\n\n"
        "Rules: English, one or two short sentences, 12–35 words, spoken in about 5–10 seconds. Pick up the thread "
        "the conversation leaves open and turn it into the question the documentary answers. Do not summarise the "
        "highlight, do not repeat the documentary's first line, no invented facts, names or dates, no 'subscribe', "
        "no 'in this video'. At most two ElevenLabs v3 audio tags such as [low], [measured], [intrigued] at the start.\n"
        'Answer with only a JSON block: ```json\n{"bridge": "..."}\n```'
    )


def _write_bridge(job: dict, seg: dict) -> str:
    res = claude_runner.run(_bridge_prompt(seg, job), cwd=config.BASE_DIR, tools="", isolated=True, max_turns=2,
                            timeout=900, permission_mode="dontAsk",
                            model=db.get_setting("claude_model_docext_bridge") or None,
                            effort=db.get_setting("claude_effort_docext_bridge") or None,
                            log_path=work_dir(job["id"]) / "bridge.jsonl")
    if not res.get("ok"):
        raise RuntimeError(f"Claude không viết được câu nối: {res.get('error')}")
    _set(job["id"], cost_usd=round(float(job.get("cost_usd") or 0) + float(res.get("cost_usd") or 0), 4))
    text = (_parse_obj(res.get("result") or res.get("text") or "").get("bridge") or "").strip()
    if not text:
        raise RuntimeError("Claude trả về câu nối rỗng")
    return text


def _fps(video: Path) -> str:
    ffprobe = str(config.FFPROBE) if config.FFPROBE.exists() else "ffprobe"
    p = subprocess.run([ffprobe, "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=r_frame_rate",
                        "-of", "default=nw=1:nk=1", str(video)], capture_output=True, text=True, creationflags=_NO_WIN)
    r = (p.stdout or "").strip()
    return r if re.fullmatch(r"\d+(/\d+)?", r) and not r.startswith("0") else "30"


def _run_ff(cmd: list, cwd: Path | None = None, timeout: int = 1800) -> None:
    p = subprocess.run([str(x) for x in cmd], cwd=cwd, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=timeout, creationflags=_NO_WIN)
    if p.returncode != 0:
        from ..util import ffmpeg_error_summary
        raise RuntimeError(ffmpeg_error_summary(p.stderr or p.stdout or "") or f"ffmpeg lỗi ({p.returncode})")


def _card(text: str, voice: Path, doc: Path, fps: str, work: Path) -> Path:
    """The bridge card: blurred, darkened frame of the documentary's opening, the line on screen, the voice."""
    out = work / "bridge_card.mp4"
    bg = work / "bridge_bg.jpg"
    try:
        _run_ff([config.FFMPEG, "-v", "error", "-y", "-ss", "3", "-i", doc, "-frames:v", "1", bg], timeout=120)
    except Exception:  # noqa: BLE001
        bg.unlink(missing_ok=True)
    font = work / "font.ttf"
    if not font.exists() and FONT.is_file():
        shutil.copy2(FONT, font)
    txt = work / "bridge_card.txt"
    txt.write_text(_wrap(_say_text(text)), encoding="utf-8", newline="\n")
    dur = ffprobe_duration(voice) + 1.2
    vin = ["-loop", "1", "-i", bg.name] if bg.exists() else ["-f", "lavfi", "-i", f"color=c=0x101014:s={W}x{H}"]
    vf = (f"[0:v]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1,boxblur=24:2,"
          "eq=brightness=-0.28:saturation=0.7")
    if font.exists() and db.get_setting("compile_card_text") != "0":
        vf += (f",drawtext=fontfile={font.name}:textfile={txt.name}:fontcolor=white:fontsize=50:line_spacing=16:"
               "text_align=C:x=(w-text_w)/2:y=(h-text_h)/2:shadowcolor=black@0.7:shadowx=2:shadowy=2:"
               "alpha='min(1,t/0.6)'")
    vf += f",fps={fps},format=yuv420p[v]"
    af = "[1:a]aresample=48000,adelay=400|400,apad,loudnorm=I=-16:TP=-1.5:LRA=11[a]"
    _run_ff([config.FFMPEG, "-v", "error", "-y", *vin, "-i", voice.name, "-filter_complex", f"{vf};{af}",
             "-map", "[v]", "-map", "[a]", "-t", f"{dur:.2f}", *_video_encoder(), *_audio_args(), out.name], cwd=work)
    return out


def _join(hooked: Path, card: Path, doc: Path, out: Path, fps: str, progress) -> None:
    """[highlight + hook] + [card] + [documentary] → one MP4, re-encoded once at the highlight's frame rate (the edit,
    picture and sound of the highlight + hook stay exactly as they are; its file on disk is never touched)."""
    norm = (f"scale={W}:{H}:force_original_aspect_ratio=decrease,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2,setsar=1,"
            f"fps={fps},format=yuv420p,settb=AVTB")
    aud = "aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,asetpts=N/SR/TB"
    graph = (f"[0:v]{norm}[v0];[1:v]{norm}[v1];[2:v]{norm}[v2];"
             f"[0:a]{aud}[a0];[1:a]{aud}[a1];[2:a]{aud}[a2];"
             "[v0][a0][v1][a1][v2][a2]concat=n=3:v=1:a=1[v][a]")
    total = ffprobe_duration(hooked) + ffprobe_duration(card) + ffprobe_duration(doc)
    tmp = out.with_suffix(".tmp.mp4")
    cmd = [str(x) for x in (config.FFMPEG, "-v", "error", "-y", "-nostats", "-progress", "pipe:1",
                            "-i", hooked, "-i", card, "-i", doc, "-filter_complex", graph, "-map", "[v]", "-map", "[a]",
                            *_video_encoder(), "-pix_fmt", "yuv420p", "-profile:v", "high", *_audio_args(),
                            "-movflags", "+faststart", tmp)]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8",
                         errors="replace", creationflags=_NO_WIN)
    err: list[str] = []
    threading.Thread(target=lambda: err.extend(p.stderr), daemon=True).start()
    for line in p.stdout:
        if line.startswith("out_time_us="):
            try:
                sec = int(line.split("=", 1)[1]) / 1e6
            except ValueError:
                continue
            pct = max(0.0, min(99.0, sec / total * 100)) if total else 0
            progress(f"đang ghép video {pct:.0f}% ({int(sec // 60)}/{int(total // 60)} phút)")
    p.wait()
    if p.returncode != 0 or not media_ok(tmp, total):
        from ..util import ffmpeg_error_summary
        tmp.unlink(missing_ok=True)
        raise RuntimeError(ffmpeg_error_summary("".join(err)) or f"ffmpeg lỗi ({p.returncode})")
    tmp.replace(out)


def _run_join(job_id: int) -> None:
    job = get_job(job_id)
    seg = db.row("SELECT s.*, e.guest FROM segments s JOIN episodes e ON e.id=s.episode_id WHERE s.id=?",
                 (job["segment_id"],))
    hooked, doc = Path(job["hooked_path"]), Path(job["doc_path"])
    for f, what in ((hooked, "bản highlight + hook"), (doc, "phim tài liệu của Creater")):
        if not f.is_file():
            raise RuntimeError(f"không thấy {what}: {f}")
    work = work_dir(job_id)
    with _lock:
        bridge = job.get("bridge_text") if job.get("bridge_user") else None
        if not bridge:
            _set(job_id, progress_msg="Claude đang viết câu nối…")
            bridge = _write_bridge(job, seg)
            _set(job_id, bridge_text=bridge)
        _set(job_id, progress_msg="ElevenLabs đang đọc câu nối…")
        voice = work / f"bridge_{_key(bridge, db.get_setting('compile_voice_id'))}.mp3"
        _tts(bridge, voice)
        fps = _fps(hooked)
        _set(job_id, progress_msg="đang dựng khung câu nối…")
        card = _card(bridge, voice, doc, fps, work)
        out = out_path(hooked)
        _join(hooked, card, doc, out, fps, lambda m: _set(job_id, progress_msg=m))
    _set(job_id, status="done", final_path=str(out), error=None,
         progress_msg=f"xong: {out.name} ({sec_to_hms(ffprobe_duration(out))})")
    _note(job_id, "done", "Phim tài liệu bổ sung đã nối xong", out.name)
    log.info("docext %s joined -> %s", job_id, out)


# ---------------------------------------------------------------- threads
def _spawn(job_id: int, target) -> None:
    def wrap():
        try:
            target(job_id)
        except Exception as e:  # noqa: BLE001
            log.exception("docext %s failed", job_id)
            _set(job_id, status="failed", error=str(e)[:2000], progress_msg=None)
            _note(job_id, "error", "Phim tài liệu bổ sung lỗi", str(e)[:300])
    t = threading.Thread(target=wrap, name=f"docext-{job_id}", daemon=True)
    _threads[job_id] = t
    t.start()


def recover_after_restart() -> None:
    """Studio restarted: a create that was cut off failed; a join restarts; filming keeps being watched."""
    with db.tx() as c:
        c.execute("UPDATE docext_jobs SET status='failed', error='Studio khởi động lại khi đang tạo dự án Creater' "
                  "WHERE status='creating' AND creater_pid IS NULL")
        c.execute("UPDATE docext_jobs SET status='filming' WHERE status='creating' AND creater_pid IS NOT NULL")
    for j in db.rows("SELECT id FROM docext_jobs WHERE status='joining'"):
        _spawn(j["id"], _run_join)
    if db.row("SELECT id FROM docext_jobs WHERE status='filming'"):
        start_poller()
