"""Re-cut HOOK 01 of a highlight around a new focus (title runs with "🎯 Trọng tâm").

The title run returns `focus_hook` {start, end, quote_en, why} in episode time. HOOK 01 (the parent's first hook by
cut order) takes those times: its old clip and zoomed clip go to the Recycle Bin, the new clip is cut with ffmpeg
under the same file name, the segment row and the episode cutlist file are updated (so a later re-import does not
bring the old hook back). Source, best first: the full episode video, the highlight's original clip, its zoomed clip
(then the new hook is already zoomed). A hook cut from an unzoomed source is returned in `zoom_ids` so the caller can
queue it for zoom when the rest of the episode is zoomed.
"""
from __future__ import annotations

import json
import logging
import shutil
import subprocess
from pathlib import Path

from .. import config, db
from ..util import (clip_filename, discard_broken, ffmpeg_error_summary, hms_to_sec, media_ok, now_iso, read_json,
                    sec_to_hms, slice_transcript, write_json)
from .cut import episode_clip_folder

log = logging.getLogger("studio.hook_recut")
MIN_SEC, MAX_SEC = 3.0, 40.0


def _ffmpeg() -> str:
    return str(config.FFMPEG) if Path(config.FFMPEG).exists() else (shutil.which("ffmpeg") or "ffmpeg")


def _cut(src: Path, offset: float, dur: float, out: Path) -> Path:
    """Cut into a temp file next to `out` and return it; the caller moves it in place once the old clip is gone."""
    tmp = out.with_name(out.stem + ".part.mp4")
    cmd = [_ffmpeg(), "-hide_banner", "-loglevel", "error", "-y", "-ss", f"{offset:.3f}", "-i", str(src),
           "-t", f"{dur:.3f}", "-map", "0:v:0", "-map", "0:a:0?", "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
           "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(tmp)]
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=600)
    if p.returncode or not media_ok(tmp, dur):
        if tmp.exists():
            tmp.unlink()
        raise RuntimeError("ffmpeg cắt hook lỗi: " + ffmpeg_error_summary(p.stderr or "file ra hỏng", 300))
    return tmp


def _update_cutlist(ep: dict, hook: dict, start: float, end: float, quote: str, why: str) -> str | None:
    """Point the hook's entry (and the parent's `hooks` list) in the episode cutlist at the new times."""
    path = Path(ep.get("cutlist_path") or hook.get("cutlist_path") or "")
    if not path.is_file():
        return None
    data = read_json(path)
    old_s, old_e = hook["start_hms"], hook["end_hms"]
    new = {"start": sec_to_hms(start), "end": sec_to_hms(end), "duration_sec": round(end - start),
           "quote_en": quote, "hook_en": quote, "hook_type": "focus", "why": why}
    hit = 0
    for s in data.get("segments") or []:
        if s.get("start") == old_s and s.get("end") == old_e:
            s.update({k: v for k, v in new.items() if k != "why"}, summary_en=why)
            hit += 1
        for h in s.get("hooks") or []:
            if h.get("start") == old_s and h.get("end") == old_e:
                h.update({k: v for k, v in new.items() if k not in ("hook_en", "hook_type")}, type="focus")
                hit += 1
    if not hit:
        return None
    backup = path.with_name(path.name + f".bak-{now_iso()[:19].replace(':', '')}-pre-focus")
    shutil.copy2(path, backup)
    write_json(path, data)
    return path.name


def recut(seg: dict, ep: dict, focus_hook, update=None) -> dict:
    """Returns {"ok", "message", "zoom_ids"}; raises RuntimeError with a short reason when nothing was changed."""
    say = update or (lambda _m: None)
    if not isinstance(focus_hook, dict) or not focus_hook.get("start") or not focus_hook.get("end"):
        raise RuntimeError("kết quả không có focus_hook (start/end) nên giữ nguyên hook cũ")
    start, end = hms_to_sec(focus_hook["start"]), hms_to_sec(focus_hook["end"])
    if end - start < MIN_SEC or end - start > MAX_SEC:
        raise RuntimeError(f"hook mới dài {end - start:.0f}s, ngoài khoảng {MIN_SEC:.0f}–{MAX_SEC:.0f}s nên giữ hook cũ")
    if start < (seg["start_sec"] or 0) - 2 or end > (seg["end_sec"] or 0) + 2:
        raise RuntimeError(f"hook mới {focus_hook['start']} → {focus_hook['end']} nằm ngoài đoạn nên giữ hook cũ")
    hook = db.row("SELECT * FROM segments WHERE parent_id=? AND kind='hook' AND status!='archived' ORDER BY rank LIMIT 1",
                  (seg["id"],))
    if not hook or not hook.get("rank"):
        raise RuntimeError("đoạn này chưa có HOOK nào để thay")

    video = Path(ep["video_path"]) if ep.get("video_path") and Path(ep["video_path"]).is_file() else None
    clip = Path(seg["clip_path"]) if seg.get("clip_path") and Path(seg["clip_path"]).is_file() else None
    zoomed = Path(seg["clip_zoomed_path"]) if seg.get("clip_zoomed_path") and Path(seg["clip_zoomed_path"]).is_file() else None
    if video:
        src, offset, is_zoomed = video, start, False
    elif clip or zoomed:
        src, offset, is_zoomed = (clip, start - seg["start_sec"], False) if clip else (zoomed, start - seg["start_sec"], True)
    else:
        raise RuntimeError("không còn video gốc lẫn clip của đoạn để cắt hook")

    folder = episode_clip_folder(ep)
    out = folder / clip_filename(hook["rank"], hook["title"])
    if is_zoomed:
        out = out.with_name(out.stem + "_zoomed.mp4")
    say(f"cắt lại HOOK {focus_hook['start']} → {focus_hook['end']} từ {src.name}")
    folder.mkdir(parents=True, exist_ok=True)
    tmp = _cut(src, max(0.0, offset), end - start, out)
    trashed = []
    for old in {hook.get("clip_path"), hook.get("clip_zoomed_path"), str(out)}:
        if old and Path(old).is_file():
            trashed.append(discard_broken(Path(old)))
    tmp.replace(out)

    quote = str(focus_hook.get("quote_en") or "").strip()
    why = str(focus_hook.get("why") or "").strip()
    lines = db.rows("SELECT start_sec AS start, end_sec AS end, text FROM transcript_lines WHERE episode_id=? "
                    "AND end_sec>=? AND start_sec<=? ORDER BY seq", (ep["id"], start, end))
    raw = {}
    try:
        raw = json.loads(hook.get("raw_json") or "{}")
    except ValueError:
        pass
    raw.update({"start": sec_to_hms(start), "end": sec_to_hms(end), "duration_sec": round(end - start),
                "quote_en": quote, "hook_en": quote, "hook_type": "focus", "summary_en": why})
    with db.tx() as c:
        c.execute("""UPDATE segments SET start_sec=?, end_sec=?, start_hms=?, end_hms=?, duration_sec=?, quote_en=?, hook_en=?,
                     hook_type='focus', summary_en=?, transcript=?, raw_json=?, clip_path=?, clip_zoomed_path=?,
                     status=?, updated_at=? WHERE id=?""",
                  (start, end, sec_to_hms(start), sec_to_hms(end), round(end - start, 2), quote, quote, why,
                   slice_transcript(lines, start, end) or None, json.dumps(raw, ensure_ascii=False),
                   None if is_zoomed else str(out), str(out) if is_zoomed else None,
                   "zoomed" if is_zoomed else "cut", now_iso(), hook["id"]))
    cl = None
    try:
        cl = _update_cutlist(ep, hook, start, end, quote, why)
    except Exception as e:  # noqa: BLE001
        log.warning("cutlist not updated for hook %s: %s", hook["id"], e)
    want_zoom = (not is_zoomed and db.setting_bool("zoom_hooks") and bool(zoomed))
    label = hook["title"].split("—")[0].strip() or "HOOK"
    msg = (f"{label} cắt lại {sec_to_hms(start)} → {sec_to_hms(end)} ({end - start:.0f}s) từ "
           f"{'video gốc' if video else 'clip đoạn đã zoom' if is_zoomed else 'clip đoạn'}: {out.name}"
           + (f" · clip cũ: {'; '.join(trashed)}" if trashed else "")
           + (f" · đã sửa cutlist {cl}" if cl else " · không sửa được file cutlist")
           + (" · đang xếp zoom" if want_zoom else ""))
    log.info(msg)
    return {"ok": True, "message": msg, "zoom_ids": [hook["id"]] if want_zoom else [], "hook_id": hook["id"]}
