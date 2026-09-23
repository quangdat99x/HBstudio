"""Small helpers shared by ingest, pipeline and UI."""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Optional

from . import config


def now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


# ---------------------------------------------------------------- timestamps
def hms_to_sec(value) -> float:
    """Accepts 'HH:MM:SS', 'MM:SS', 'H:MM:SS.s' or a number. Raises ValueError otherwise."""
    if value is None:
        raise ValueError("empty timestamp")
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip().replace("，", ",")
    if re.fullmatch(r"\d+(\.\d+)?", s):
        return float(s)
    parts = s.split(":")
    if not 1 <= len(parts) <= 3 or not all(re.fullmatch(r"\d+(\.\d+)?", p.strip()) for p in parts):
        raise ValueError(f"bad timestamp: {value!r}")
    parts = [float(p) for p in parts]
    while len(parts) < 3:
        parts.insert(0, 0.0)
    h, m, sec = parts
    return h * 3600 + m * 60 + sec


def sec_to_hms(sec: float) -> str:
    sec = max(0, int(round(sec)))
    return f"{sec // 3600:02d}:{(sec % 3600) // 60:02d}:{sec % 60:02d}"


# ---------------------------------------------------------------- episodes
_RE_JRE = re.compile(r"Joe Rogan Experience\s*#\s*(\d+)\s*-\s*(.+?)\s*$", re.I)
_RE_MMA = re.compile(r"JRE MMA Show\s*#\s*(\d+)\s*(?:with|-)?\s*(.+?)\s*$", re.I)
_RE_ID = re.compile(r"^(JREMMA|JRE)-(\d+)$", re.I)
_RE_SUFFIX = re.compile(r"(?:_\d{6})+$")            # Cutter adds _HHMMSS when a folder already exists
_RE_PAREN = re.compile(r"\s*\(\d+\)$")               # downloader adds " (1)" for duplicates


def clean_stem(name: str) -> str:
    """Strip extension, Cutter time suffix and ' (1)' duplicate marker from a video/folder name."""
    stem = Path(name).stem if "." in name and not name.endswith(")") else name
    if stem.lower().endswith((".mp4", ".mkv", ".webm", ".mov")):
        stem = stem.rsplit(".", 1)[0]
    stem = _RE_SUFFIX.sub("", stem)
    stem = _RE_PAREN.sub("", stem)
    return stem.strip()


def parse_episode_name(name: str) -> Optional[dict]:
    """Parse a JRE video/folder name into {episode_id, podcast_id, number, guest}. None if not JRE."""
    stem = clean_stem(name)
    m = _RE_JRE.search(stem)
    if m:
        return {"episode_id": f"JRE-{int(m.group(1))}", "podcast_id": "JRE",
                "number": int(m.group(1)), "guest": m.group(2).strip()}
    m = _RE_MMA.search(stem)
    if m:
        return {"episode_id": f"JREMMA-{int(m.group(1))}", "podcast_id": "JREMMA",
                "number": int(m.group(1)), "guest": m.group(2).strip()}
    return None


def parse_episode_id(episode_id: str) -> Optional[dict]:
    m = _RE_ID.match((episode_id or "").strip())
    if not m:
        return None
    pod = m.group(1).upper()
    return {"episode_id": f"{pod}-{int(m.group(2))}", "podcast_id": pod, "number": int(m.group(2))}


# ---------------------------------------------------------------- Cutter naming (must match app.py)
def cutter_safe_title(title: str, index: int) -> str:
    safe = re.sub(r"[^\w\s-]", "", (title or "").strip())[:50].strip()
    safe = re.sub(r"\s+", "_", safe) or f"clip_{index}"
    return safe


def cutter_safe_stem(video_stem: str) -> str:
    return re.sub(r'[<>:"/\\|?*]', "_", video_stem)[:80].strip()


def clip_filename(index: int, title: str) -> str:
    return f"{index:02d}_{cutter_safe_title(title, index)}.mp4"


# ---------------------------------------------------------------- text
def strip_diacritics(text: str) -> str:
    """Vietnamese-aware ASCII folding: 'người khổng lồ' -> 'nguoi khong lo'."""
    if not text:
        return ""
    text = text.replace("đ", "d").replace("Đ", "D")
    nfd = unicodedata.normalize("NFD", text)
    return "".join(ch for ch in nfd if unicodedata.category(ch) != "Mn")


def norm_key(text: str) -> str:
    return re.sub(r"\s+", " ", strip_diacritics(text or "").lower()).strip()


def slugify(text: str, max_len: int = 60) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", strip_diacritics(text or "").lower()).strip("-")
    return s[:max_len].strip("-") or "item"


def sha1_file(path: Path) -> str:
    h = hashlib.sha1()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def read_json(path: Path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    tmp.replace(path)


# ---------------------------------------------------------------- media
def ffprobe_duration(path: Path) -> float:
    ffprobe = str(config.FFPROBE) if config.FFPROBE.exists() else "ffprobe"
    try:
        out = subprocess.run(
            [ffprobe, "-v", "quiet", "-print_format", "json", "-show_format", str(path)],
            capture_output=True, text=True, timeout=60,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        return float(json.loads(out.stdout)["format"]["duration"])
    except Exception:
        return 0.0


def find_transcript(video_path: Path) -> Optional[Path]:
    stem = video_path.stem
    for cand in (video_path.with_name(f"{stem}.transcript.json"),
                 video_path.with_name(f"{stem}.transcript.txt")):
        if cand.exists():
            return cand
    return None


_RE_TXT_LINE = re.compile(r"^\[(\d{1,2}:\d{2}:\d{2})\]\s*(.*)$")


def load_transcript(path: Path) -> list[dict]:
    """Return [{start, end, text}] from a Whisper .transcript.json or .transcript.txt."""
    if path.suffix.lower() == ".json":
        data = read_json(path)
        segs = data.get("segments", data) if isinstance(data, dict) else data
        return [{"start": float(s["start"]), "end": float(s["end"]), "text": str(s.get("text", "")).strip()}
                for s in segs if "start" in s and "end" in s]
    lines = []
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for raw in f:
            m = _RE_TXT_LINE.match(raw.strip())
            if m:
                lines.append({"start": hms_to_sec(m.group(1)), "end": None, "text": m.group(2)})
    for i, ln in enumerate(lines):
        ln["end"] = lines[i + 1]["start"] if i + 1 < len(lines) else ln["start"] + 5.0
    return lines


def transcript_to_txt(video_name: str, model: str, segments: list[dict]) -> str:
    out = [f"# Transcript: {video_name}", f"# Model: {model}", ""]
    out += [f"[{sec_to_hms(s['start'])}] {s['text']}" for s in segments]
    return "\n".join(out) + "\n"


def slice_transcript(segments: list[dict], start: float, end: float) -> str:
    parts = [f"[{sec_to_hms(s['start'])}] {s['text']}" for s in segments
             if s["start"] < end and (s["end"] or s["start"]) > start]
    return "\n".join(parts)
