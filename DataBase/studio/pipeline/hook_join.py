"""Nối hook: one hook of a highlight becomes the cold open of that highlight's ZOOMED clip.

The hook (its original cut, not zoomed) plays first, then a transition (ffmpeg xfade on the picture, acrossfade on
the sound) into the zoomed highlight, with a sound effect made by ElevenLabs whose loudest moment sits in the middle
of the transition. The output sits next to the zoomed clip: <zoomed stem>_HOOK<NN>.mp4 (NN = the hook's number under its
highlight). A highlight that is not zoomed yet is refused: the user zooms it first.

Settings: hook_join_transition (xfade name), hook_join_duration (s), hook_join_sfx (a file of assets/sfx or a full
path, empty = assets/sfx/transition.mp3), hook_join_sfx_volume (0–2).
"""
from __future__ import annotations

import logging
import re
import subprocess
import threading
from pathlib import Path

from .. import config, db
from ..util import ffprobe_duration, media_ok, now_iso
from .compile_video import FPS, H, W, _audio_args, _video_encoder

log = logging.getLogger("studio.hookjoin")

TRANSITIONS = {"slideright": "Kéo từ trái sang phải", "fade": "Mờ chéo (mượt nhất)", "fadewhite": "Lóe trắng",
               "fadeblack": "Qua đen",
               "smoothleft": "Trượt trái", "smoothright": "Trượt phải", "zoomin": "Zoom vào",
               "circleopen": "Mở tròn", "dissolve": "Hòa tan", "radial": "Quét tròn"}
SFX_DIR = config.BASE_DIR / "assets" / "sfx"
DEFAULT_SFX = "transition.mp3"             # made with ElevenLabs sound generation the first time it is needed
DEFAULT_SFX_PROMPT = ("Smooth cinematic whoosh transition for a podcast clip: soft airy swoosh that rises and passes "
                      "by, ending in a gentle deep low-end thud. Clean, warm, modern documentary style, no hiss, "
                      "no distortion, no music.")
DEFAULT_SFX_SEC = 2.0
_NO_WIN = 0x08000000 if hasattr(subprocess, "CREATE_NO_WINDOW") else 0

_lock = threading.Lock()                   # one join at a time (each re-encodes a whole highlight)
_state: dict[int, dict] = {}               # hook id -> {"status", "msg", "out", "error"}


def generate_sfx(prompt: str, out: Path, seconds: float | None = DEFAULT_SFX_SEC) -> Path:
    """A sound effect from ElevenLabs (sound generation) through Creater Vid's gen.py and its ElevenLabs key."""
    from .compile_video import CREATER_PY, GEN_PY
    if not CREATER_PY.is_file() or not GEN_PY.is_file():
        raise RuntimeError(f"không thấy Creater Vid ({GEN_PY}) để tạo sound effect bằng ElevenLabs")
    out.parent.mkdir(parents=True, exist_ok=True)
    cmd = [CREATER_PY, "-X", "utf8", GEN_PY, "sfx", "--prompt", prompt, "--out", out, "--influence", "0.6",
           "--what", f"jre-studio hook sfx {out.stem}"]
    if seconds:
        cmd += ["--seconds", f"{seconds:g}"]
    # cwd = the sfx folder: no project.json above it, so gen.py keeps no film budget/ledger for this call
    p = subprocess.run([str(x) for x in cmd], cwd=out.parent, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=300, creationflags=_NO_WIN)
    if p.returncode != 0 or not out.is_file():
        msg = (p.stdout + "\n" + p.stderr).strip().splitlines()
        raise RuntimeError("ElevenLabs: " + " · ".join(msg[-3:])[:500])
    return out


def sfx_choices() -> list[str]:
    """Sound effect files offered in Settings (assets/sfx)."""
    return sorted(f.name for f in SFX_DIR.glob("*") if f.suffix.lower() in (".mp3", ".wav", ".m4a", ".ogg"))


def _sfx() -> Path:
    """Settings hook_join_sfx: a file name in assets/sfx or a full path; empty = transition.mp3 (ElevenLabs)."""
    own = (db.get_setting("hook_join_sfx") or "").strip().strip('"')
    p = Path(own) if own and Path(own).is_absolute() else SFX_DIR / (own or DEFAULT_SFX)
    if p.is_file():
        return p
    if own:
        raise RuntimeError(f"không thấy file sound effect trong Cài đặt: {own}")
    return generate_sfx(DEFAULT_SFX_PROMPT, p)


def _peak(path: Path) -> float:
    """Energy centre of a sound, in seconds: put in the middle of the picture transition, a long whoosh sits across
    it and a riser lands its hit on it."""
    p = subprocess.run([str(config.FFMPEG), "-v", "error", "-i", str(path), "-ac", "1", "-ar", "8000", "-f", "s16le", "-"],
                       capture_output=True, creationflags=_NO_WIN)
    import array
    a = array.array("h", p.stdout[: len(p.stdout) // 2 * 2])
    win = 160                                              # 20 ms at 8 kHz
    tot = mom = 0.0
    for i in range(0, max(0, len(a) - win), win):
        e = float(sum(x * x for x in a[i:i + win]))
        tot += e
        mom += e * (i + win / 2) / 8000
    return mom / tot if tot else 0.0


def hooks_of(highlight_id: int) -> list[dict]:
    return db.rows("SELECT * FROM segments WHERE parent_id=? AND kind='hook' AND status NOT IN ('archived') "
                   "ORDER BY start_sec, id", (highlight_id,))


def _hook_no(hook: dict) -> int:
    m = re.search(r"HOOK[ _-]?(\d+)", hook.get("title") or "", re.I)
    if m:
        return int(m.group(1))
    ids = [h["id"] for h in hooks_of(hook["parent_id"])]
    return ids.index(hook["id"]) + 1 if hook["id"] in ids else 1


def out_path(hook: dict, highlight: dict) -> Path | None:
    if not highlight.get("clip_zoomed_path"):
        return None
    z = Path(highlight["clip_zoomed_path"])
    return z.with_name(f"{z.stem}_HOOK{_hook_no(hook):02d}.mp4")


def _sources(hook_id: int) -> tuple[dict, dict, Path, Path]:
    hook = db.row("SELECT * FROM segments WHERE id=?", (hook_id,))
    if not hook or hook["kind"] != "hook" or not hook.get("parent_id"):
        raise ValueError("không phải hook của một đoạn highlight")
    hl = db.row("SELECT * FROM segments WHERE id=?", (hook["parent_id"],))
    if not hl:
        raise ValueError("không thấy đoạn highlight của hook này")
    zoomed = Path(hl["clip_zoomed_path"]) if hl.get("clip_zoomed_path") else None
    if not zoomed or not zoomed.is_file():
        raise ValueError(f"đoạn highlight #{hl['rank'] or '–'} chưa có bản zoom: bấm 🔍 Zoom đoạn này trước rồi nối hook")
    # the hook opens on the ORIGINAL cut (wide shot, not zoomed); its zoomed file only if the cut is gone
    hc = Path(hook["clip_path"]) if hook.get("clip_path") else None
    hz = Path(hook["clip_zoomed_path"]) if hook.get("clip_zoomed_path") else None
    hsrc = hc if hc and hc.is_file() else hz if hz and hz.is_file() else None
    if not hsrc or not hsrc.is_file():
        raise ValueError("hook chưa có clip trên máy (chưa cắt hoặc file đã bị xoá)")
    return hook, hl, hsrc, zoomed


def status(hook_id: int) -> dict:
    st = dict(_state.get(hook_id) or {})
    if st.get("status") != "running":
        hook = db.row("SELECT * FROM segments WHERE id=?", (hook_id,))
        hl = db.row("SELECT * FROM segments WHERE id=?", (hook["parent_id"],)) if hook and hook.get("parent_id") else None
        out = out_path(hook, hl) if hook and hl else None
        if out and out.is_file():
            st.setdefault("status", "done")
            st["out"] = str(out)
    return st


def start(hook_id: int, transition: str | None = None) -> dict:
    try:
        hook, hl, hsrc, zoomed = _sources(hook_id)
    except ValueError as e:
        return {"error": str(e)}
    if (_state.get(hook_id) or {}).get("status") == "running":
        return {"error": "hook này đang được nối"}
    trans = transition if transition in TRANSITIONS else (db.get_setting("hook_join_transition") or "slideright")
    _state[hook_id] = {"status": "running", "msg": "đang chờ tới lượt…"}
    threading.Thread(target=_job, args=(hook, hl, hsrc, zoomed, trans), name=f"hookjoin-{hook_id}", daemon=True).start()
    return {"message": f"đang nối {('hook ' + str(_hook_no(hook)))} vào bản zoom của đoạn #{hl['rank'] or '–'}"
                       + ("" if hsrc == Path(hook.get("clip_path") or "") else " (bản cắt gốc của hook không còn: dùng bản zoom)")}


def _note(hl: dict, kind: str, what: str, body: str = "") -> None:
    from .. import notify
    from .orchestrator import ep_label, ep_link
    notify.notify(kind, f"{what}: đoạn #{hl.get('rank') or '?'} {(hl.get('title') or '')[:60]}",
                  f"{ep_label(hl['episode_id'])} · {body}", ep_link(hl["episode_id"], hl["id"]))


def _job(hook: dict, hl: dict, hsrc: Path, zoomed: Path, trans: str) -> None:
    hid = hook["id"]
    out = out_path(hook, hl)
    with db.tx() as c:
        c.execute("INSERT INTO jobs(episode_id, stage, status, progress, message, attempts, started_at) VALUES(?,?,?,?,?,?,?)",
                  (hl["episode_id"], "hookjoin", "running", 0, f"nối hook {_hook_no(hook)} → đoạn #{hl['rank']}", 1, now_iso()))
        job_id = c.execute("SELECT last_insert_rowid()").fetchone()[0]

    def progress(pct: float, msg: str) -> None:
        _state[hid] = {"status": "running", "msg": msg, "pct": pct}
        with db.tx() as c:
            c.execute("UPDATE jobs SET progress=?, message=? WHERE id=?", (pct, msg[:500], job_id))

    try:
        with _lock:
            join(hsrc, zoomed, out, trans, progress)
        _state[hid] = {"status": "done", "out": str(out), "msg": "xong"}
        with db.tx() as c:
            c.execute("UPDATE jobs SET status='done', progress=100, message=?, finished_at=? WHERE id=?",
                      (f"nối hook {_hook_no(hook)} xong: {out.name}"[:500], now_iso(), job_id))
        log.info("hook %s joined -> %s", hid, out)
        _note(hl, "done", f"Nối hook {_hook_no(hook)} vào bản zoom xong", out.name)
    except Exception as e:  # noqa: BLE001
        log.error("hook join %s failed: %s", hid, e)
        _state[hid] = {"status": "failed", "error": str(e)[:500]}
        _note(hl, "error", f"Nối hook {_hook_no(hook)} lỗi", str(e)[:300])
        with db.tx() as c:
            c.execute("UPDATE jobs SET status='failed', error=?, finished_at=? WHERE id=?", (str(e)[:2000], now_iso(), job_id))


def _fps(video: Path) -> str:
    """The clip's frame rate as ffmpeg writes it (30000/1001 for the zoomed clips), else 30."""
    ffprobe = str(config.FFPROBE) if config.FFPROBE.exists() else "ffprobe"
    p = subprocess.run([ffprobe, "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=r_frame_rate",
                        "-of", "default=nw=1:nk=1", str(video)], capture_output=True, text=True, creationflags=_NO_WIN)
    r = (p.stdout or "").strip()
    return r if re.fullmatch(r"\d+(/\d+)?", r) and not r.startswith("0") else str(FPS)


def join(hook: Path, main: Path, out: Path, trans: str = "fade", progress=None) -> Path:
    """hook → transition (+ sound effect) → main, re-encoded to 1080p at the main clip's frame rate, H.264 High
    yuv420p (what Windows' player and YouTube expect) / AAC 48k stereo."""
    d = max(0.2, min(2.0, db.setting_float("hook_join_duration") or 0.6))
    vol = max(0.0, min(2.0, db.setting_float("hook_join_sfx_volume") or 0.8))
    hd, md = ffprobe_duration(hook), ffprobe_duration(main)
    if hd <= d + 0.5 or md <= d:
        raise RuntimeError(f"clip quá ngắn để chuyển cảnh (hook {hd:.1f}s, đoạn {md:.1f}s)")
    sfx = _sfx()
    off = hd - d                                             # the transition starts here and ends at hd
    delay = max(0, int((off + d / 2 - _peak(sfx)) * 1000))   # loudest moment of the sound = middle of the transition
    norm = (f"scale={W}:{H}:force_original_aspect_ratio=decrease,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2,setsar=1,"
            f"fps={_fps(main)},format=yuv420p,settb=AVTB")
    aud = "aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo"
    graph = (f"[0:v]{norm}[v0];[1:v]{norm}[v1];[v0][v1]xfade=transition={trans}:duration={d}:offset={off:.3f},"
             "format=yuv420p[v];"
             f"[0:a]{aud}[a0];[1:a]{aud}[a1];[a0][a1]acrossfade=d={d}:c1=tri:c2=tri[ax];"
             f"[2:a]{aud},volume={vol},adelay={delay}|{delay}[s];"
             "[ax][s]amix=inputs=2:duration=first:normalize=0,alimiter=limit=0.97[a]")
    total = hd + md - d
    tmp = out.with_suffix(".tmp.mp4")
    cmd = [str(x) for x in (config.FFMPEG, "-v", "error", "-y", "-nostats", "-progress", "pipe:1",
                            "-i", hook, "-i", main, "-i", sfx, "-filter_complex", graph, "-map", "[v]", "-map", "[a]",
                            *_video_encoder(), "-pix_fmt", "yuv420p", "-profile:v", "high", *_audio_args(),
                            "-movflags", "+faststart", tmp)]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8",
                         errors="replace", creationflags=_NO_WIN)
    err: list[str] = []
    threading.Thread(target=lambda: err.extend(p.stderr), daemon=True).start()
    for line in p.stdout:
        if line.startswith("out_time_us=") and progress:
            try:
                sec = int(line.split("=", 1)[1]) / 1e6
            except ValueError:
                continue
            pct = max(0.0, min(99.0, sec / total * 100))
            progress(pct, f"đang dựng {pct:.0f}% ({int(sec)}/{int(total)}s)")
    p.wait()
    if p.returncode != 0 or not media_ok(tmp, total):
        from ..util import ffmpeg_error_summary
        tmp.unlink(missing_ok=True)
        raise RuntimeError(ffmpeg_error_summary("".join(err)) or f"ffmpeg lỗi ({p.returncode})")
    tmp.replace(out)
    return out
