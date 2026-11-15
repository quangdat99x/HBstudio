"""
Video Cutter Portable — Cắt video thủ công theo timestamp
Bước 1: Tạo transcript bằng Whisper (tùy chọn)
Bước 2: Cắt video theo timestamp
"""

import json
import logging
import os
import re
import subprocess
import sys
import threading
import time
from pathlib import Path

from flask import Flask, jsonify, request, render_template, abort, send_file

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

# File-based logger — works even under pythonw (no console)
LOG_FILE = BASE_DIR / "cutter.log"
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(str(LOG_FILE), encoding="utf-8"),
    ],
)
log = logging.getLogger("cutter")

# ffmpeg: check bundled first, then system PATH
FFMPEG_BUNDLED = BASE_DIR / "ffmpeg" / "ffmpeg.exe"
FFMPEG_CMD = str(FFMPEG_BUNDLED) if FFMPEG_BUNDLED.exists() else "ffmpeg"

# ---------------------------------------------------------------------------
# Hardware encoder (NVENC) detection
# ---------------------------------------------------------------------------
_nvenc_available = None  # cached across calls; None = not checked yet


def _check_nvenc_available() -> bool:
    """Real one-frame encode test — a compiled-in h264_nvenc can still fail at
    runtime with no NVIDIA GPU/driver present, so listing encoders isn't enough."""
    global _nvenc_available
    if _nvenc_available is not None:
        return _nvenc_available
    try:
        creationflags = subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0
        result = subprocess.run(
            [FFMPEG_CMD, "-hide_banner", "-loglevel", "error",
             "-f", "lavfi", "-i", "nullsrc=s=256x256:d=0.1",
             "-c:v", "h264_nvenc", "-f", "null", "-"],
            capture_output=True, timeout=15, creationflags=creationflags,
        )
        _nvenc_available = (result.returncode == 0)
    except Exception:
        _nvenc_available = False
    log.info(f"NVENC hardware encoder available: {_nvenc_available}")
    return _nvenc_available


def video_encode_args(crf: int = 18) -> list:
    """Video-encode args, preferring GPU NVENC (RTX cards) over CPU libx264.
    `crf` is on the libx264 quality scale; NVENC's -cq runs ~1 point hotter
    at the same visual quality, so it is nudged up by 1 when GPU is used."""
    if _check_nvenc_available():
        return ["-c:v", "h264_nvenc", "-preset", "p5", "-tune", "hq",
                "-rc", "vbr", "-cq", str(crf + 1), "-b:v", "0"]
    return ["-c:v", "libx264", "-preset", "medium", "-crf", str(crf)]


_physical_cores_cache = None


def _physical_cores() -> int:
    """Real CPU cores (i7-14700: 20). Budgets count cores, not hyper-threads."""
    global _physical_cores_cache
    if _physical_cores_cache is None:
        try:
            out = subprocess.run(["powershell", "-NoProfile", "-Command",
                                  "(Get-CimInstance Win32_Processor | Measure-Object NumberOfCores -Sum).Sum"],
                                 capture_output=True, text=True, timeout=20,
                                 creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout
            _physical_cores_cache = max(1, int(out.strip()))
        except Exception:
            _physical_cores_cache = max(1, (os.cpu_count() or 2) // 2)
    return _physical_cores_cache


def _cut_workers() -> int:
    """How many segments to cut at once. Read from <Tool>/cpu_budget.json:
    `cut_workers` fixes the number; otherwise (cores - reserve_cores) / cores-per-cut, 1..4.
    One libx264 'medium' 1080p encode uses ~6 cores well; with NVENC the GPU encodes and
    each cut only needs ~3 cores for decoding (consumer NVENC allows 8 sessions)."""
    budget = {}
    for name in ("cpu_budget.json", "cpu_budget.local.json"):   # shared through Git, then this machine only
        try:
            with open(BASE_DIR.parent / name, encoding="utf-8") as fh:
                budget.update(json.load(fh))
        except Exception:
            pass
    if budget.get("cut_workers"):
        try:
            return max(1, min(8, int(budget["cut_workers"])))
        except (TypeError, ValueError):
            pass
    reserve = float(budget.get("reserve_cores", 2))
    per_cut = 3.0 if _check_nvenc_available() else 6.0
    return max(1, min(4, int((_physical_cores() - reserve) / per_cut)))


app = Flask(__name__)

# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------
state = {
    "video_path": None,
    "transcript": [],
    "cutting": {
        "status": "idle",
        "progress": 0,
        "results": [],
        "output_dir": None,
        "error": None,
    },
    # Multi-source batch mode (folder of episodes + multi-source cutlist)
    "video_folder": None,
    "folder_videos": {},  # {basename: fullpath} of videos found in the selected folder
    "cutting_multi": {
        "status": "idle",
        "progress": 0,
        "results": [],
        "output_dir": None,
        "error": None,
    },
    "whisper": {
        "status": "idle",        # idle | running | done | error
        "progress": 0,
        "message": "",
        "error": None,
        "model": None,
        "segments_count": 0,
    },
    # Whisper subprocess tracking
    "_whisper_proc": None,
    "_whisper_status_file": None,
    # Whisper queue
    "whisper_queue": [],
    "_queue_running": False,
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def parse_timestamp(ts: str) -> float:
    """Convert HH:MM:SS or MM:SS or seconds to float seconds."""
    ts = ts.strip()
    # Already a number
    try:
        return float(ts)
    except ValueError:
        pass
    parts = ts.split(":")
    if len(parts) == 3:
        h, m, s = parts
        return int(h) * 3600 + int(m) * 60 + float(s)
    elif len(parts) == 2:
        m, s = parts
        return int(m) * 60 + float(s)
    return 0.0


def fmt_timestamp(sec: float) -> str:
    """Convert seconds to HH:MM:SS."""
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = int(sec % 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def load_transcript_file(path: str) -> list:
    """Load transcript from .json or .txt file."""
    path = Path(path)
    if not path.exists():
        return []

    if path.suffix.lower() == ".json":
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        # Format: {segments: [{start, end, text}]} or [{start, end, text}]
        if isinstance(data, dict):
            return data.get("segments", [])
        elif isinstance(data, list):
            return data
        return []

    elif path.suffix.lower() == ".txt":
        # Format: [HH:MM:SS] text per line
        segments = []
        lines = path.read_text(encoding="utf-8").splitlines()
        for i, line in enumerate(lines):
            match = re.match(r"\[(\d{2}:\d{2}:\d{2})\]\s*(.*)", line)
            if match:
                start = parse_timestamp(match.group(1))
                text = match.group(2).strip()
                # End = next line's start, or start + 10s
                end = start + 10.0
                if i + 1 < len(lines):
                    next_match = re.match(r"\[(\d{2}:\d{2}:\d{2})\]", lines[i + 1])
                    if next_match:
                        end = parse_timestamp(next_match.group(1))
                segments.append({"start": start, "end": end, "text": text})
        return segments

    elif path.suffix.lower() == ".srt":
        # Parse SRT format
        content = path.read_text(encoding="utf-8")
        blocks = re.split(r"\n\n+", content.strip())
        segments = []
        for block in blocks:
            lines = block.strip().split("\n")
            if len(lines) >= 3:
                time_match = re.match(
                    r"(\d{2}:\d{2}:\d{2}),\d+ --> (\d{2}:\d{2}:\d{2}),\d+",
                    lines[1],
                )
                if time_match:
                    start = parse_timestamp(time_match.group(1))
                    end = parse_timestamp(time_match.group(2))
                    text = " ".join(lines[2:]).strip()
                    segments.append({"start": start, "end": end, "text": text})
        return segments

    return []


def find_transcript_for_video(video_path: str) -> str | None:
    """Auto-find transcript file matching the video name."""
    video = Path(video_path)
    stem = video.stem
    folder = video.parent

    # Try these patterns in order
    candidates = [
        folder / f"{stem}.transcript.json",
        folder / f"{stem}.json",
        folder / "transcript.json",
        folder / f"{stem}.transcript.txt",
        folder / f"{stem}.txt",
        folder / "transcript.txt",
        folder / f"{stem}.srt",
    ]

    for c in candidates:
        if c.exists():
            return str(c)
    return None


VIDEO_EXTENSIONS = {".mp4", ".mkv", ".webm", ".avi", ".mov", ".flv", ".ts", ".m4v"}


def _scan_video_folder(folder: str) -> dict:
    """Scan a folder (non-recursive) for video files. Returns {basename: fullpath}."""
    result = {}
    try:
        for entry in os.scandir(folder):
            if entry.is_file() and Path(entry.name).suffix.lower() in VIDEO_EXTENSIONS:
                result[entry.name] = entry.path
    except Exception as e:
        log.error(f"_scan_video_folder error: {e}")
    return result


def _resolve_source_video(name: str, episode_id: str = "") -> str | None:
    """Resolve a cutlist segment's `source_video` filename against the videos
    found in the currently selected source folder (case-insensitive, with a
    stem-only fallback for minor extension mismatches).

    Real-world cutlists mix naming conventions across episodes — some carry
    the actual downloaded filename, some a "clean" slug guessed by the LLM
    (e.g. `JRE_1883_Ryan_Graves.mp4` vs the real
    `Joe Rogan Experience #1883 - Ryan Graves.mp4`), and some are left as an
    unfilled placeholder. The episode number is the one thing that reliably
    survives all of these, so it's used as a last-resort fallback: if exactly
    one video in the folder contains that number as a standalone token, match it.
    """
    videos = state.get("folder_videos") or {}
    if not videos:
        return None

    if name:
        if name in videos:
            return videos[name]
        lower_map = {k.lower(): v for k, v in videos.items()}
        if name.lower() in lower_map:
            return lower_map[name.lower()]
        stem = Path(name).stem.lower()
        matches = [v for k, v in videos.items() if Path(k).stem.lower() == stem]
        if len(matches) == 1:
            return matches[0]

    m = re.search(r"(\d{3,5})", episode_id or "")
    if m:
        num = m.group(1)
        num_pattern = re.compile(rf"(?<!\d){re.escape(num)}(?!\d)")
        num_matches = [v for k, v in videos.items() if num_pattern.search(k)]
        if len(num_matches) == 1:
            return num_matches[0]

    return None


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    return render_template("index.html")


def _open_folder_dialog(title="Chọn thư mục lưu"):
    """Open a native Windows folder-picker dialog. Returns folder path or empty string."""
    _cflags = subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0

    # Strategy 1: PowerShell — force UTF-8 output so Vietnamese paths survive
    try:
        ps_script = (
            "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; "
            "Add-Type -AssemblyName System.Windows.Forms; "
            "$f = New-Object System.Windows.Forms.FolderBrowserDialog; "
            f"$f.Description = '{title}'; "
            "$f.ShowNewFolderButton = $true; "
            "if ($f.ShowDialog() -eq 'OK') { Write-Output $f.SelectedPath }"
        )
        result = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_script],
            capture_output=True, text=True, encoding='utf-8', errors='replace',
            timeout=120, creationflags=_cflags,
        )
        path = result.stdout.strip()
        if path:
            return path
        if result.returncode != 0:
            print(f"[Folder dialog error] {result.stderr.strip()}", flush=True)
    except Exception as e:
        print(f"[Folder dialog exception] {e}", flush=True)

    # Strategy 2: tkinter subprocess — explicitly set stdout to UTF-8
    try:
        script = f'''
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import tkinter as tk
from tkinter import filedialog
root = tk.Tk()
root.withdraw()
root.attributes("-topmost", True)
f = filedialog.askdirectory(title={repr(title)})
print(f or "")
root.destroy()
'''
        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True, text=True, encoding='utf-8', errors='replace',
            timeout=120,
        )
        return result.stdout.strip()
    except Exception as e:
        print(f"[Folder dialog tkinter exception] {e}", flush=True)
        return ""


@app.route("/api/pick-folder", methods=["POST"])
def pick_folder():
    """Open native folder picker dialog."""
    data = request.json or {}
    title = data.get("title", "Chọn thư mục lưu")
    folder = _open_folder_dialog(title)
    if not folder:
        return jsonify({"error": "Không chọn thư mục nào"}), 400
    return jsonify({"folder": folder})


@app.route("/api/select-source-folder", methods=["POST"])
def select_source_folder():
    """Open native folder picker, scan it for video files — used by the
    multi-source batch cutting flow (folder chứa nhiều tập + cutlist đa nguồn)."""
    folder = _open_folder_dialog("Chọn thư mục chứa các tập video")
    if not folder or not os.path.isdir(folder):
        return jsonify({"error": "Không chọn thư mục nào"}), 400

    videos = _scan_video_folder(folder)
    state["video_folder"] = folder
    state["folder_videos"] = videos

    if not videos:
        return jsonify({"error": f"Không tìm thấy video nào trong thư mục: {folder}"}), 400

    return jsonify({
        "folder": folder,
        "count": len(videos),
        "videos": sorted(videos.keys()),
    })


def _open_file_dialog(title, filetypes_filter, ps_filter):
    """
    Open a native Windows file-picker dialog.
    Strategy 1: PowerShell — force UTF-8 output so Vietnamese paths survive.
    Strategy 2: tkinter subprocess fallback.
    Returns selected path string or empty string.
    """
    _cflags = subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0

    # --- Strategy 1: PowerShell ---
    try:
        ps_script = (
            "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; "
            "Add-Type -AssemblyName System.Windows.Forms; "
            "$f = New-Object System.Windows.Forms.OpenFileDialog; "
            f"$f.Title = '{title}'; "
            f"$f.Filter = '{ps_filter}'; "
            "$f.Multiselect = $false; "
            "if ($f.ShowDialog() -eq 'OK') { Write-Output $f.FileName }"
        )
        result = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_script],
            capture_output=True, text=True, encoding='utf-8', errors='replace',
            timeout=120, creationflags=_cflags,
        )
        path = result.stdout.strip()
        if path:
            return path
        if result.returncode != 0:
            print(f"[PowerShell dialog error] {result.stderr.strip()}", flush=True)
    except Exception as e:
        print(f"[PowerShell dialog exception] {e}", flush=True)

    # --- Strategy 2: tkinter subprocess — explicitly set stdout to UTF-8 ---
    try:
        script = f'''
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import tkinter as tk
from tkinter import filedialog
root = tk.Tk()
root.withdraw()
root.attributes("-topmost", True)
f = filedialog.askopenfilename(
    title={repr(title)},
    filetypes={repr(filetypes_filter)},
)
print(f or "")
root.destroy()
'''
        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True, text=True, encoding='utf-8', errors='replace',
            timeout=120,
        )
        if result.stderr.strip():
            print(f"[tkinter dialog stderr] {result.stderr.strip()}", flush=True)
        return result.stdout.strip()
    except Exception as e:
        print(f"[tkinter dialog exception] {e}", flush=True)
        return ""


@app.route("/api/select-video", methods=["POST"])
def select_video():
    """Open native file dialog to pick a video file."""
    try:
        video_path = _open_file_dialog(
            title="Chọn video",
            filetypes_filter=[
                ("Video files", "*.mp4 *.mkv *.webm *.avi *.mov *.flv"),
                ("All files", "*.*"),
            ],
            ps_filter="Video Files (*.mp4;*.mkv;*.webm;*.avi;*.mov;*.flv)|*.mp4;*.mkv;*.webm;*.avi;*.mov;*.flv|All Files (*.*)|*.*",
        )

        if not video_path or not os.path.exists(video_path):
            return jsonify({"error": "Không chọn file nào"}), 400

        state["video_path"] = video_path
        state["transcript"] = []  # Clear old transcript for new video

        # Auto-find transcript
        transcript_path = find_transcript_for_video(video_path)
        transcript = []
        transcript_file = None
        if transcript_path:
            transcript = load_transcript_file(transcript_path)
            transcript_file = os.path.basename(transcript_path)
            state["transcript"] = transcript

        return jsonify({
            "video_path": video_path,
            "video_name": os.path.basename(video_path),
            "transcript_found": bool(transcript),
            "transcript_file": transcript_file,
            "transcript_count": len(transcript),
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/load-transcript", methods=["POST"])
def load_transcript():
    """Manually load a transcript file."""
    try:
        path = _open_file_dialog(
            title="Chọn file transcript",
            filetypes_filter=[
                ("Transcript files", "*.json *.txt *.srt"),
                ("All files", "*.*"),
            ],
            ps_filter="Transcript Files (*.json;*.txt;*.srt)|*.json;*.txt;*.srt|All Files (*.*)|*.*",
        )

        if not path or not os.path.exists(path):
            return jsonify({"error": "Không chọn file nào"}), 400

        transcript = load_transcript_file(path)
        if not transcript:
            return jsonify({"error": "Không đọc được transcript từ file này"}), 400

        state["transcript"] = transcript

        return jsonify({
            "transcript_file": os.path.basename(path),
            "transcript_count": len(transcript),
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/transcript")
def get_transcript():
    """Return currently loaded transcript."""
    return jsonify({"segments": state["transcript"]})


@app.route("/api/video")
def serve_video():
    """Stream video file for HTML5 player with range support."""
    video_path = state.get("video_path")
    if not video_path or not os.path.exists(video_path):
        abort(404)

    file_size = os.path.getsize(video_path)
    range_header = request.headers.get("Range")

    if range_header:
        match = re.search(r"bytes=(\d+)-(\d*)", range_header)
        if match:
            start = int(match.group(1))
            end = int(match.group(2)) if match.group(2) else file_size - 1
            end = min(end, file_size - 1)
            length = end - start + 1

            with open(video_path, "rb") as f:
                f.seek(start)
                data = f.read(length)

            from flask import Response
            resp = Response(
                data,
                206,
                mimetype="video/mp4",
                content_type="video/mp4",
            )
            resp.headers["Content-Range"] = f"bytes {start}-{end}/{file_size}"
            resp.headers["Accept-Ranges"] = "bytes"
            resp.headers["Content-Length"] = length
            return resp

    return send_file(video_path, mimetype="video/mp4")


@app.route("/api/cut", methods=["POST"])
def cut_video():
    """Start cutting video into segments."""
    data = request.json
    segments = data.get("segments", [])
    output_folder = data.get("output_folder", "")
    video_path = state.get("video_path")

    if not video_path or not os.path.exists(video_path):
        return jsonify({"error": "Chưa chọn video"}), 400
    if not segments:
        return jsonify({"error": "Chưa có đoạn cắt nào"}), 400

    # Check ffmpeg
    try:
        subprocess.run([FFMPEG_CMD, "-version"], capture_output=True, timeout=5)
    except Exception:
        return jsonify({
            "error": "Không tìm thấy ffmpeg! Hãy đặt ffmpeg.exe vào thư mục ffmpeg/ của tool."
        }), 400

    # IMPORTANT: Reset cutting state SYNCHRONOUSLY before starting the thread.
    # This prevents a race condition where the frontend polls and sees
    # stale "done" status from a previous export run.
    state["cutting"] = {
        "status": "running",
        "progress": 0,
        "results": [],
        "output_dir": None,
        "error": None,
        "current_segment": 0,
        "total_segments": len(segments),
        "segment_progress": 0,
        "segment_title": "",
        "speed": "",
        "eta": "",
    }

    write_sidecars = bool(data.get("write_sidecars", False))
    log.info(f"cut_video: starting thread, {len(segments)} segments, output_folder='{output_folder}', sidecars={write_sidecars}")

    thread = threading.Thread(
        target=_run_cutting,
        args=(video_path, segments, state["transcript"], output_folder),
        kwargs={"write_sidecars": write_sidecars},
        daemon=True,
    )
    thread.start()

    log.info(f"cut_video: thread started, thread={thread.name}")
    return jsonify({"status": "started", "total": len(segments)})


@app.route("/api/cut-headless", methods=["POST"])
def cut_headless():
    """Cut without the GUI state: JSON {video_path, output_dir, segments:[{index,start,end,title}], write_sidecars}.

    Used by Hổ Báo Studio. Does not touch the manually selected video/transcript of the UI.
    """
    data = request.json or {}
    video_path = str(data.get("video_path") or "")
    output_dir = str(data.get("output_dir") or "")
    segments = data.get("segments", [])
    write_sidecars = bool(data.get("write_sidecars", False))
    if not video_path or not os.path.exists(video_path):
        return jsonify({"error": f"Không thấy video: {video_path}"}), 400
    if not output_dir:
        return jsonify({"error": "Thiếu output_dir"}), 400
    if not segments:
        return jsonify({"error": "Chưa có đoạn cắt nào"}), 400
    if state["cutting"].get("status") == "running":
        return jsonify({"error": "Đang cắt một job khác, thử lại sau"}), 409
    transcript = []
    if write_sidecars:
        tpath = find_transcript_for_video(video_path)
        if tpath:
            transcript = load_transcript_file(tpath)
    state["cutting"] = {
        "status": "running", "progress": 0, "results": [], "output_dir": None, "error": None,
        "current_segment": 0, "total_segments": len(segments), "segment_progress": 0,
        "segment_title": "", "speed": "", "eta": "",
    }
    log.info(f"cut_headless: {len(segments)} segments of {os.path.basename(video_path)} -> {output_dir}")
    thread = threading.Thread(
        target=_run_cutting,
        args=(video_path, segments, transcript, ""),
        kwargs={"write_sidecars": write_sidecars, "exact_output_dir": output_dir},
        daemon=True,
    )
    thread.start()
    return jsonify({"status": "started", "total": len(segments), "output_dir": output_dir})


def _extract_ffmpeg_error(stderr: str) -> str:
    """Extract meaningful error messages from FFmpeg stderr, filtering out stats."""
    if not stderr:
        return "Lỗi không xác định"

    # FFmpeg stderr contains encoding stats (libx264, aac, etc.) which are NOT errors.
    # Real errors typically contain these patterns:
    error_patterns = [
        r"Error .+",
        r"Invalid .+",
        r"No such file .+",
        r"Permission denied.*",
        r"Conversion failed.*",
        r".*: No such file or directory",
        r".*moov atom not found.*",
        r".*could not find codec.*",
        r".*Unrecognized option.*",
        r".*received signal \d+.*",
    ]

    lines = stderr.strip().split("\n")
    error_lines = []

    for line in lines:
        line_stripped = line.strip()
        # Skip encoding statistics lines
        if any(skip in line_stripped for skip in [
            "libx264", "libx265", "[aac", "kb/s:", "Qavg:",
            "Weighted P-Frames", "ref P L", "ref B L",
            "i4 v,h", "i8c dc", "coded y", "SSIM",
            "mb I", "mb P", "mb B", "final ratefactor",
        ]):
            continue
        # Check for known error patterns
        for pat in error_patterns:
            if re.search(pat, line_stripped, re.IGNORECASE):
                error_lines.append(line_stripped)
                break

    if error_lines:
        return "\n".join(error_lines[-5:])  # Last 5 error lines

    # Check for signal termination
    if "received signal" in stderr:
        return "FFmpeg bị dừng giữa chừng (received signal). Có thể do đóng cửa sổ app hoặc hệ thống dừng tiến trình."

    return "Lỗi không xác định từ FFmpeg"


# Keep track of active ffmpeg processes so we don't leave zombies
_active_ffmpeg_procs = []


def _parse_ffmpeg_progress_time(time_str: str) -> float:
    """Parse FFmpeg progress time format (HH:MM:SS.us) to seconds."""
    try:
        parts = time_str.strip().split(":")
        if len(parts) == 3:
            h, m, s = parts
            return int(h) * 3600 + int(m) * 60 + float(s)
        return 0.0
    except (ValueError, IndexError):
        return 0.0


def _run_cutting(video_path: str, segments: list, transcript: list, output_folder: str = "",
                 write_sidecars: bool = False, exact_output_dir: str = ""):
    """Background worker: cut video segments with ffmpeg (real-time progress).

    write_sidecars: also write NN_title.txt / .json / .manifest.json next to each clip
    (off by default; only the documentary flow with /viet-prompt-v2 needs them).
    exact_output_dir: use this folder as-is (no per-video subfolder, no time suffix);
    Hổ Báo Studio uses it so a re-run lands in the same episode folder.
    seg["index"] (optional) fixes the NN prefix of the clip file name.

    Uses a temp progress file instead of pipe:1 to avoid Windows pipe deadlock.
    FFmpeg writes heavily to stderr (encoding stats), and reading stdout for
    progress while stderr's 4KB pipe buffer fills causes a deadlock on Windows.
    """
    import tempfile
    import traceback

    try:
        log.info(f"=== BẮT ĐẦU CẮT === Tổng số đoạn: {len(segments)}")
        log.info(f"Video: {video_path}")
        log.info(f"Output folder: '{output_folder}'")
        for idx, s in enumerate(segments):
            log.info(f"  Đoạn {idx+1}: start={s.get('start')}, end={s.get('end')}, title={s.get('title', '')}")

        # State was already reset synchronously in cut_video() to prevent race conditions.
        # Just update the output directory here.

        # Use the exact folder (Studio) or user-chosen folder / default with a per-video subfolder
        if exact_output_dir:
            output_dir = Path(exact_output_dir)
        else:
            base_dir = Path(output_folder) if output_folder and os.path.isdir(output_folder) else OUTPUT_DIR
            video_stem = Path(video_path).stem
            safe_stem = re.sub(r'[<>:"/\\|?*]', '_', video_stem)[:80].strip()
            output_dir = base_dir / safe_stem
            if output_dir.exists():
                output_dir = base_dir / f"{safe_stem}_{time.strftime('%H%M%S')}"
        output_dir.mkdir(parents=True, exist_ok=True)
        state["cutting"]["output_dir"] = str(output_dir.absolute())
        log.info(f"Output dir: {output_dir}")

        total = len(segments)

        # Several segments are cut side by side (one FFmpeg each, see _cut_workers): a single libx264/NVENC
        # FFmpeg leaves most of a 20-core CPU idle. `running` holds the live per-segment progress that
        # _publish() folds into state["cutting"] (overall %, titles, ETA) for the UI and Hổ Báo Studio.
        lock = threading.Lock()
        running: dict = {}
        seg_secs = []
        for s in segments:
            try:
                seg_secs.append(max(0.0, parse_timestamp(s["end"]) - parse_timestamp(s["start"])))
            except Exception:
                seg_secs.append(0.0)
        total_sec = sum(seg_secs) or 1.0
        counters = {"started": 0, "finished_sec": 0.0}
        job_start = time.time()

        def _publish():
            with lock:
                cs = state["cutting"]
                live = list(running.values())
                done_sec = counters["finished_sec"] + sum(
                    r["duration"] * r["st"].get("segment_progress", 0) / 100 for r in live)
                cs["progress"] = max(cs.get("progress") or 0, min(99, int(done_sec / total_sec * 100)))
                cs["current_segment"] = counters["started"]
                if len(live) == 1:
                    cs["segment_title"] = live[0]["title"]
                elif live:
                    cs["segment_title"] = f"{len(live)} đoạn song song: " + ", ".join(r["title"][:25] for r in live)
                cs["segment_progress"] = (int(sum(r["st"].get("segment_progress", 0) for r in live) / len(live))
                                          if live else 100)
                cs["speed"] = " ".join(r["st"].get("speed", "") for r in live).strip()
                elapsed = time.time() - job_start
                if done_sec > 1 and elapsed > 2:
                    remaining = (total_sec - done_sec) * elapsed / done_sec
                    if remaining < 60:
                        cs["eta"] = f"~{int(remaining)}s"
                    elif remaining < 3600:
                        cs["eta"] = f"~{int(remaining // 60)}m{int(remaining % 60)}s"
                    else:
                        cs["eta"] = f"~{int(remaining // 3600)}h{int((remaining % 3600) // 60)}m"

        def _cut_one(i, seg):
            log.info(f"--- Bắt đầu xử lý đoạn {i+1}/{total} ---")
            progress_file = None
            stderr_file = None
            stderr_fh = None
            try:
                title = seg.get("title", f"clip_{i+1}").strip()
                safe_title = re.sub(r"[^\w\s-]", "", title)[:50].strip()
                safe_title = re.sub(r"\s+", "_", safe_title) or f"clip_{i+1}"
                try:
                    clip_no = int(seg.get("index") or (i + 1))
                except (TypeError, ValueError):
                    clip_no = i + 1

                start_sec = parse_timestamp(seg["start"])
                end_sec = parse_timestamp(seg["end"])

                if end_sec <= start_sec:
                    raise ValueError(f"Thời gian kết thúc ({seg['end']}) phải sau thời gian bắt đầu ({seg['start']})")

                output_file = str(output_dir / f"{clip_no:02d}_{safe_title}.mp4")

                duration = end_sec - start_sec

                # Register this segment's live progress (folded into state["cutting"] by _publish)
                seg_st = {"segment_progress": 0, "speed": "", "eta": ""}
                with lock:
                    counters["started"] += 1
                    running[i] = {"title": title or f"Đoạn {i+1}", "duration": duration, "st": seg_st}
                _publish()

                # Use temp files for progress and stderr to avoid pipe deadlock
                progress_file = os.path.join(tempfile.gettempdir(), f"vc_ffprog_{os.getpid()}_{i}.log")
                stderr_file = os.path.join(tempfile.gettempdir(), f"vc_ffstderr_{os.getpid()}_{i}.log")

                # Clean up any leftover files
                for f in [progress_file, stderr_file]:
                    if os.path.exists(f):
                        try:
                            os.remove(f)
                        except Exception:
                            pass

                cmd = [
                    FFMPEG_CMD, "-y",
                    "-ss", str(start_sec),
                    "-i", video_path,
                    "-t", str(duration),
                    *video_encode_args(18),
                    "-force_key_frames", "expr:eq(n,0)",
                    "-c:a", "aac",
                    "-b:a", "192k",
                    "-strict", "-2",
                    "-movflags", "+faststart",
                    "-avoid_negative_ts", "make_zero",
                    "-progress", progress_file,
                    output_file,
                ]

                creationflags = 0
                if hasattr(subprocess, "CREATE_NO_WINDOW"):
                    creationflags = subprocess.CREATE_NO_WINDOW

                # Redirect stderr to a file to avoid pipe buffer deadlock on Windows
                stderr_fh = open(stderr_file, "w", encoding="utf-8", errors="replace")

                log.info(f"Đoạn {i+1}: Chạy FFmpeg cmd: {' '.join(cmd)}")
                proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=stderr_fh,
                    creationflags=creationflags,
                )
                log.info(f"Đoạn {i+1}: FFmpeg PID={proc.pid}")
                _active_ffmpeg_procs.append(proc)

                encode_start_time = time.time()

                # Poll the progress file periodically instead of reading pipes
                try:
                    last_read_pos = 0
                    while proc.poll() is None:
                        time.sleep(0.3)

                        if os.path.exists(progress_file):
                            try:
                                with open(progress_file, "r", encoding="utf-8", errors="replace") as pf:
                                    pf.seek(last_read_pos)
                                    new_content = pf.read()
                                    if new_content:
                                        last_read_pos = pf.tell()
                                        _update_progress_from_content(
                                            new_content, duration, i, total,
                                            segments, encode_start_time, cutting_state=seg_st
                                        )
                                        _publish()
                            except (IOError, OSError):
                                pass

                    # Final read after process completes
                    if os.path.exists(progress_file):
                        try:
                            with open(progress_file, "r", encoding="utf-8", errors="replace") as pf:
                                pf.seek(last_read_pos)
                                final_content = pf.read()
                                if final_content:
                                    _update_progress_from_content(
                                        final_content, duration, i, total,
                                        segments, encode_start_time, cutting_state=seg_st
                                    )
                        except (IOError, OSError):
                            pass

                except Exception as poll_err:
                    log.error(f"Progress poll error: {poll_err}")
                    try:
                        proc.wait(timeout=3600)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                        proc.wait()

                finally:
                    if proc in _active_ffmpeg_procs:
                        _active_ffmpeg_procs.remove(proc)
                    if stderr_fh:
                        try:
                            stderr_fh.close()
                            stderr_fh = None
                        except Exception:
                            pass
                    log.info(f"Đoạn {i+1}: FFmpeg kết thúc, returncode={proc.returncode if proc else 'N/A'}")

                # Read stderr from file for error info
                stderr = ""
                try:
                    if os.path.exists(stderr_file):
                        with open(stderr_file, "r", encoding="utf-8", errors="replace") as f:
                            stderr = f.read()
                except Exception:
                    pass

                returncode = proc.returncode

                if returncode == 0:
                    clip_transcript = []
                    for s in transcript:
                        if s["start"] < end_sec and s["end"] > start_sec:
                            clip_transcript.append(s)

                    if write_sidecars and clip_transcript:
                        txt_file = str(output_dir / f"{clip_no:02d}_{safe_title}.txt")
                        with open(txt_file, "w", encoding="utf-8") as f:
                            f.write(f"Tên: {title}\n")
                            f.write(f"Thời gian: {seg['start']} → {seg['end']}")
                            duration_sec = end_sec - start_sec
                            f.write(f" ({int(duration_sec // 60)} phút {int(duration_sec % 60)} giây)\n")
                            f.write(f"Video gốc: {os.path.basename(video_path)}\n\n")
                            f.write("--- Transcript ---\n")
                            for s in clip_transcript:
                                f.write(f"[{fmt_timestamp(s['start'])}] {s['text']}\n")

                        # Also export JSON transcript for the clip
                        json_file = str(output_dir / f"{clip_no:02d}_{safe_title}.json")
                        clip_segments = [
                            {
                                "start": float(s["start"]),
                                "end": float(s["end"]),
                                "text": s["text"],
                            }
                            for s in clip_transcript
                        ]
                        json_data = {
                            "title": title,
                            "source_video": os.path.basename(video_path),
                            "clip_start": start_sec,
                            "clip_end": end_sec,
                            "clip_start_hms": fmt_timestamp(start_sec),
                            "clip_end_hms": fmt_timestamp(end_sec),
                            "duration": end_sec - start_sec,
                            "segments": clip_segments,
                        }
                        with open(json_file, "w", encoding="utf-8") as f:
                            json.dump(json_data, f, ensure_ascii=False, indent=2)

                    # ── Skeleton manifest for documentary builder ──
                    # Build manifest.json with explicit timestamps (relative to
                    # clip start), ready for /viet-prompt-v2 skill without
                    # needing to re-run Whisper in the documentary builder.
                    manifest_fn = None
                    manifest_segs = 0
                    try:
                        import skeleton_builder
                        if write_sidecars and clip_transcript:
                            manifest_data = skeleton_builder.build_skeleton_from_whisper_segments(
                                clip_transcript,
                                clip_start_sec=start_sec,  # shift absolute → relative
                            )
                            if manifest_data:
                                manifest_path = str(output_dir / f"{clip_no:02d}_{safe_title}.manifest.json")
                                with open(manifest_path, "w", encoding="utf-8") as mf:
                                    json.dump(manifest_data, mf, ensure_ascii=False, indent=2)
                                manifest_fn = os.path.basename(manifest_path)
                                manifest_segs = manifest_data['total_segments']
                                log.info(
                                    f"Đoạn {i+1}: Manifest skeleton → {manifest_fn} "
                                    f"({manifest_segs} segments, "
                                    f"sha1={manifest_data['_locked_sha1'][:12]}...)"
                                )
                        elif write_sidecars:
                            log.info(f"Đoạn {i+1}: Không có transcript → bỏ qua manifest")
                    except Exception as me:
                        log.warning(f"Đoạn {i+1}: Manifest generation failed: {me}")

                    state["cutting"]["results"].append({
                        "index": clip_no,
                        "title": title,
                        "file": output_file,
                        "start": seg["start"],
                        "end": seg["end"],
                        "status": "done",
                        "manifest_file": manifest_fn,
                        "manifest_segments": manifest_segs,
                    })
                    log.info(f"Đoạn {i+1}/{total} OK: {output_file}")
                else:
                    output_exists = os.path.exists(output_file) and os.path.getsize(output_file) > 1024

                    if output_exists and "received signal" in (stderr or ""):
                        state["cutting"]["results"].append({
                            "index": clip_no,
                            "title": title,
                            "file": output_file,
                            "start": seg["start"],
                            "end": seg["end"],
                            "status": "done",
                            "warning": "FFmpeg bị dừng nhưng file đã được tạo",
                        })
                    else:
                        error_msg = _extract_ffmpeg_error(stderr)
                        log.error(f"Đoạn {i+1}/{total} LỖI (code {returncode}): {error_msg}")
                        state["cutting"]["results"].append({
                            "index": clip_no,
                            "title": title,
                            "error": error_msg,
                            "status": "error",
                        })

            except Exception as e:
                log.error(f"Đoạn {i+1} EXCEPTION: {e}")
                log.error(f"Đoạn {i+1} Traceback:\n{traceback.format_exc()}")
                state["cutting"]["results"].append({
                    "index": i + 1,
                    "title": seg.get("title", f"clip_{i+1}"),
                    "error": str(e),
                    "status": "error",
                })

            finally:
                if stderr_fh:
                    try:
                        stderr_fh.close()
                    except Exception:
                        pass
                for f in [progress_file, stderr_file]:
                    if f and os.path.exists(f):
                        try:
                            os.remove(f)
                        except Exception:
                            pass

            with lock:
                running.pop(i, None)
                counters["finished_sec"] += seg_secs[i]
            _publish()
            log.info(f"--- Hoàn tất đoạn {i+1}/{total}, progress={state['cutting']['progress']}% ---")

        workers = max(1, min(_cut_workers(), total))
        log.info(f"Cắt {total} đoạn, {workers} đoạn song song")
        # Longest segments first so a long highlight doesn't start last and run alone at the end
        order = sorted(range(total), key=lambda k: seg_secs[k], reverse=True)
        if workers == 1:
            for i in range(total):
                _cut_one(i, segments[i])
        else:
            from concurrent.futures import ThreadPoolExecutor
            with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="cut") as pool:
                list(pool.map(lambda k: _cut_one(k, segments[k]), order))
        state["cutting"]["results"].sort(key=lambda r: int(r.get("index") or 0))

        state["cutting"]["progress"] = 100
        state["cutting"]["status"] = "done"
        done_count = len([r for r in state['cutting']['results'] if r['status'] == 'done'])
        error_count = len([r for r in state['cutting']['results'] if r['status'] == 'error'])
        log.info(f"=== HOÀN TẤT === {done_count}/{total} đoạn thành công, {error_count} lỗi")

    except Exception as fatal_err:
        # Top-level catch: set status to "error" so frontend stops spinner
        log.error(f"!!! FATAL ERROR: {fatal_err}")
        log.error(f"Traceback:\n{traceback.format_exc()}")
        state["cutting"]["status"] = "error"
        state["cutting"]["error"] = f"Lỗi nghiêm trọng: {fatal_err}"


def _update_progress_from_content(
    content: str, duration: float, seg_idx: int, total: int,
    segments: list, encode_start_time: float, cutting_state: dict = None
):
    """Parse FFmpeg progress file content and update state.

    `cutting_state` lets batch/multi-source cutting report into its own
    `state["cutting_multi"]` dict instead of the single-video `state["cutting"]`
    — defaults to the latter so existing single-video call sites are unaffected.
    """
    cs = cutting_state if cutting_state is not None else state["cutting"]
    for line in content.strip().split("\n"):
        line = line.strip()
        if not line:
            continue

        if line.startswith("out_time="):
            out_time_str = line.split("=", 1)[1]
            encoded_sec = _parse_ffmpeg_progress_time(out_time_str)
            if duration > 0:
                seg_pct = min(100, int((encoded_sec / duration) * 100))
                cs["segment_progress"] = seg_pct

                # Calculate overall progress:
                # completed segments + current segment partial
                overall = ((seg_idx + seg_pct / 100) / total) * 100
                cs["progress"] = min(99, int(overall))

                # ETA calculation
                elapsed = time.time() - encode_start_time
                if encoded_sec > 0.5 and elapsed > 1:
                    rate = encoded_sec / elapsed  # seconds of video per second of wall time
                    remaining_this_seg = (duration - encoded_sec) / rate if rate > 0 else 0
                    # Estimate remaining segments (assume same speed)
                    remaining_segs = 0
                    for j in range(seg_idx + 1, total):
                        s_start = parse_timestamp(segments[j]["start"])
                        s_end = parse_timestamp(segments[j]["end"])
                        remaining_segs += max(0, s_end - s_start)
                    remaining_total = remaining_this_seg + (remaining_segs / rate if rate > 0 else 0)
                    if remaining_total < 60:
                        cs["eta"] = f"~{int(remaining_total)}s"
                    elif remaining_total < 3600:
                        cs["eta"] = f"~{int(remaining_total // 60)}m{int(remaining_total % 60)}s"
                    else:
                        cs["eta"] = f"~{int(remaining_total // 3600)}h{int((remaining_total % 3600) // 60)}m"

        elif line.startswith("speed="):
            speed_val = line.split("=", 1)[1].strip()
            if speed_val and speed_val != "N/A":
                cs["speed"] = speed_val


def _run_multi_cutting(segments: list, output_folder: str, theme: str = ""):
    """Background worker: batch-cut segments that each carry their own resolved
    source video path (`_resolved_path`, set by /api/cut-multi), writing every
    clip into ONE flat output folder — numbered by the segment's global `order`
    field so the resulting files sort straight into the compiled arc's final
    assembly sequence, ready to drag into an editor."""
    import tempfile
    import traceback

    cs = state["cutting_multi"]

    try:
        log.info(f"=== BẮT ĐẦU CẮT ĐA NGUỒN === Tổng số đoạn: {len(segments)}")
        log.info(f"Output folder: '{output_folder}'")

        base_dir = Path(output_folder) if output_folder and os.path.isdir(output_folder) else OUTPUT_DIR
        theme_slug = re.sub(r'[<>:"/\\|?*]', '_', theme)[:60].strip() if theme else ""
        folder_name = f"compilation_{theme_slug}" if theme_slug else f"compilation_{time.strftime('%Y%m%d_%H%M%S')}"
        output_dir = base_dir / folder_name
        if output_dir.exists():
            output_dir = base_dir / f"{folder_name}_{time.strftime('%H%M%S')}"
        output_dir.mkdir(parents=True, exist_ok=True)
        cs["output_dir"] = str(output_dir.absolute())
        log.info(f"Output dir: {output_dir}")

        total = len(segments)
        transcript_cache: dict = {}  # video_path -> transcript list

        for i, seg in enumerate(segments):
            video_path = seg["_resolved_path"]
            order = int(seg.get("order", i + 1))
            episode_id = seg.get("episode_id") or Path(video_path).stem
            safe_episode = re.sub(r"[^\w-]", "_", episode_id)[:40].strip() or "ep"

            progress_file = None
            stderr_file = None
            stderr_fh = None
            proc = None
            try:
                title = seg.get("title", f"clip_{i+1}").strip()
                safe_title = re.sub(r"[^\w\s-]", "", title)[:50].strip()
                safe_title = re.sub(r"\s+", "_", safe_title) or f"clip_{i+1}"

                start_sec = parse_timestamp(seg["start"])
                end_sec = parse_timestamp(seg["end"])

                if end_sec <= start_sec:
                    raise ValueError(f"Thời gian kết thúc ({seg['end']}) phải sau thời gian bắt đầu ({seg['start']})")

                output_file = str(output_dir / f"{order:02d}_{safe_episode}_{safe_title}.mp4")
                duration = end_sec - start_sec

                cs["current_segment"] = i + 1
                cs["segment_title"] = f"[{episode_id}] {title}" if episode_id else (title or f"Đoạn {i+1}")
                cs["segment_progress"] = 0
                cs["speed"] = ""
                cs["eta"] = ""

                progress_file = os.path.join(tempfile.gettempdir(), f"vc_mprog_{os.getpid()}_{i}.log")
                stderr_file = os.path.join(tempfile.gettempdir(), f"vc_mstderr_{os.getpid()}_{i}.log")
                for f in [progress_file, stderr_file]:
                    if os.path.exists(f):
                        try:
                            os.remove(f)
                        except Exception:
                            pass

                cmd = [
                    FFMPEG_CMD, "-y",
                    "-ss", str(start_sec),
                    "-i", video_path,
                    "-t", str(duration),
                    *video_encode_args(18),
                    "-force_key_frames", "expr:eq(n,0)",
                    "-c:a", "aac",
                    "-b:a", "192k",
                    "-strict", "-2",
                    "-movflags", "+faststart",
                    "-avoid_negative_ts", "make_zero",
                    "-progress", progress_file,
                    output_file,
                ]

                creationflags = subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0
                stderr_fh = open(stderr_file, "w", encoding="utf-8", errors="replace")

                log.info(f"Đoạn {i+1}: [{episode_id}] Chạy FFmpeg cmd: {' '.join(cmd)}")
                proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=stderr_fh,
                    creationflags=creationflags,
                )
                _active_ffmpeg_procs.append(proc)

                encode_start_time = time.time()

                try:
                    last_read_pos = 0
                    while proc.poll() is None:
                        time.sleep(0.3)
                        if os.path.exists(progress_file):
                            try:
                                with open(progress_file, "r", encoding="utf-8", errors="replace") as pf:
                                    pf.seek(last_read_pos)
                                    new_content = pf.read()
                                    if new_content:
                                        last_read_pos = pf.tell()
                                        _update_progress_from_content(
                                            new_content, duration, i, total,
                                            segments, encode_start_time, cutting_state=cs,
                                        )
                            except (IOError, OSError):
                                pass

                    if os.path.exists(progress_file):
                        try:
                            with open(progress_file, "r", encoding="utf-8", errors="replace") as pf:
                                pf.seek(last_read_pos)
                                final_content = pf.read()
                                if final_content:
                                    _update_progress_from_content(
                                        final_content, duration, i, total,
                                        segments, encode_start_time, cutting_state=cs,
                                    )
                        except (IOError, OSError):
                            pass

                except Exception as poll_err:
                    log.error(f"Progress poll error: {poll_err}")
                    try:
                        proc.wait(timeout=3600)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                        proc.wait()

                finally:
                    if proc in _active_ffmpeg_procs:
                        _active_ffmpeg_procs.remove(proc)
                    if stderr_fh:
                        try:
                            stderr_fh.close()
                            stderr_fh = None
                        except Exception:
                            pass
                    log.info(f"Đoạn {i+1}: FFmpeg kết thúc, returncode={proc.returncode if proc else 'N/A'}")

                stderr = ""
                try:
                    if os.path.exists(stderr_file):
                        with open(stderr_file, "r", encoding="utf-8", errors="replace") as f:
                            stderr = f.read()
                except Exception:
                    pass

                returncode = proc.returncode

                if returncode == 0:
                    # Best-effort per-clip transcript export (auto-found per source video, cached)
                    if video_path not in transcript_cache:
                        tpath = find_transcript_for_video(video_path)
                        transcript_cache[video_path] = load_transcript_file(tpath) if tpath else []
                    vtranscript = transcript_cache[video_path]
                    clip_transcript = [s for s in vtranscript if s["start"] < end_sec and s["end"] > start_sec]

                    if clip_transcript:
                        txt_file = str(output_dir / f"{order:02d}_{safe_episode}_{safe_title}.txt")
                        with open(txt_file, "w", encoding="utf-8") as f:
                            f.write(f"Tên: {title}\n")
                            f.write(f"Tập: {episode_id}\n")
                            f.write(f"Video gốc: {os.path.basename(video_path)}\n")
                            f.write(f"Thời gian: {seg['start']} → {seg['end']}\n\n")
                            f.write("--- Transcript ---\n")
                            for s in clip_transcript:
                                f.write(f"[{fmt_timestamp(s['start'])}] {s['text']}\n")

                    cs["results"].append({
                        "index": i + 1,
                        "order": order,
                        "episode_id": episode_id,
                        "title": title,
                        "file": output_file,
                        "start": seg["start"],
                        "end": seg["end"],
                        "status": "done",
                    })
                    log.info(f"Đoạn {i+1}/{total} OK: {output_file}")
                else:
                    output_exists = os.path.exists(output_file) and os.path.getsize(output_file) > 1024

                    if output_exists and "received signal" in (stderr or ""):
                        cs["results"].append({
                            "index": i + 1,
                            "order": order,
                            "episode_id": episode_id,
                            "title": title,
                            "file": output_file,
                            "start": seg["start"],
                            "end": seg["end"],
                            "status": "done",
                            "warning": "FFmpeg bị dừng nhưng file đã được tạo",
                        })
                    else:
                        error_msg = _extract_ffmpeg_error(stderr)
                        log.error(f"Đoạn {i+1}/{total} LỖI (code {returncode}): {error_msg}")
                        cs["results"].append({
                            "index": i + 1,
                            "order": order,
                            "episode_id": episode_id,
                            "title": title,
                            "error": error_msg,
                            "status": "error",
                        })

            except Exception as e:
                log.error(f"Đoạn {i+1} EXCEPTION: {e}")
                log.error(f"Đoạn {i+1} Traceback:\n{traceback.format_exc()}")
                cs["results"].append({
                    "index": i + 1,
                    "episode_id": episode_id,
                    "title": seg.get("title", f"clip_{i+1}"),
                    "error": str(e),
                    "status": "error",
                })

            finally:
                if stderr_fh:
                    try:
                        stderr_fh.close()
                    except Exception:
                        pass
                for f in [progress_file, stderr_file]:
                    if f and os.path.exists(f):
                        try:
                            os.remove(f)
                        except Exception:
                            pass

            try:
                cs["progress"] = int((i + 1) / total * 100)
            except Exception:
                pass
            log.info(f"--- Hoàn tất đoạn {i+1}/{total}, progress={cs['progress']}% ---")

        cs["status"] = "done"
        done_count = len([r for r in cs["results"] if r["status"] == "done"])
        error_count = len([r for r in cs["results"] if r["status"] == "error"])
        log.info(f"=== HOÀN TẤT CẮT ĐA NGUỒN === {done_count}/{total} đoạn thành công, {error_count} lỗi")

    except Exception as fatal_err:
        log.error(f"!!! FATAL ERROR (multi): {fatal_err}")
        log.error(f"Traceback:\n{traceback.format_exc()}")
        cs["status"] = "error"
        cs["error"] = f"Lỗi nghiêm trọng: {fatal_err}"


@app.route("/api/cut/status")
def cut_status():
    return jsonify(state["cutting"])


@app.route("/api/debug-log")
def debug_log():
    """Return the last 50 lines of the log file for debugging."""
    try:
        if LOG_FILE.exists():
            lines = LOG_FILE.read_text(encoding="utf-8").splitlines()
            return jsonify({"lines": lines[-50:]})
    except Exception as e:
        return jsonify({"error": str(e)})
    return jsonify({"lines": []})


@app.route("/api/open-folder", methods=["POST"])
def open_folder():
    """Open output folder in Windows Explorer."""
    folder = state["cutting"].get("output_dir") or str(OUTPUT_DIR)
    if os.path.exists(folder):
        os.startfile(folder)
    return jsonify({"status": "ok"})


# ---------------------------------------------------------------------------
# Whisper Queue (batch transcription)
# ---------------------------------------------------------------------------
def _open_multifile_dialog(title, filetypes_filter, ps_filter):
    """Open a native Windows multi-select file picker. Returns list of paths."""
    _cflags = subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0

    # Strategy 1: PowerShell with Multiselect=$true, paths separated by |
    try:
        ps_script = (
            "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; "
            "Add-Type -AssemblyName System.Windows.Forms; "
            "$f = New-Object System.Windows.Forms.OpenFileDialog; "
            f"$f.Title = '{title}'; "
            f"$f.Filter = '{ps_filter}'; "
            "$f.Multiselect = $true; "
            "if ($f.ShowDialog() -eq 'OK') { Write-Output ($f.FileNames -join '|') }"
        )
        result = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_script],
            capture_output=True, text=True, encoding='utf-8', errors='replace',
            timeout=120, creationflags=_cflags,
        )
        raw = result.stdout.strip()
        if raw:
            return [p for p in raw.split("|") if p and os.path.exists(p)]
    except Exception as e:
        print(f"[MultiFile dialog exception] {e}", flush=True)

    # Strategy 2: tkinter with multiple=True
    try:
        script = f'''
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import tkinter as tk
from tkinter import filedialog
root = tk.Tk()
root.withdraw()
root.attributes("-topmost", True)
files = filedialog.askopenfilenames(
    title={repr(title)},
    filetypes={repr(filetypes_filter)},
)
print("|".join(files))
root.destroy()
'''
        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True, text=True, encoding='utf-8', errors='replace',
            timeout=120,
        )
        raw = result.stdout.strip()
        if raw:
            return [p for p in raw.split("|") if p and os.path.exists(p)]
    except Exception as e:
        print(f"[MultiFile tkinter exception] {e}", flush=True)

    return []


@app.route("/api/whisper/queue/add", methods=["POST"])
def whisper_queue_add():
    """Open multi-select file dialog to add videos to the whisper queue."""
    data = request.json or {}
    model = data.get("model", "base")
    language = data.get("language", "auto")

    video_paths = _open_multifile_dialog(
        title="Thêm video vào hàng đợi Whisper (giữ Ctrl để chọn nhiều file)",
        filetypes_filter=[
            ("Video files", "*.mp4 *.mkv *.webm *.avi *.mov *.flv"),
            ("All files", "*.*"),
        ],
        ps_filter="Video Files (*.mp4;*.mkv;*.webm;*.avi;*.mov;*.flv)|*.mp4;*.mkv;*.webm;*.avi;*.mov;*.flv|All Files (*.*)|*.*",
    )

    if not video_paths:
        return jsonify({"error": "Không chọn file nào"}), 400

    import uuid
    added = []
    for video_path in video_paths:
        item = {
            "id": str(uuid.uuid4())[:8],
            "video_path": video_path,
            "video_name": os.path.basename(video_path),
            "model": model,
            "language": language,
            "status": "pending",
            "progress": 0,
            "message": "Chờ xử lý...",
            "transcript_path": None,
            "segments_count": 0,
            "error": None,
        }
        state["whisper_queue"].append(item)
        added.append(item)
        log.info(f"Queue: added {item['video_name']} (id={item['id']})")

    return jsonify({"status": "added", "added": len(added), "queue_length": len(state["whisper_queue"])})


@app.route("/api/whisper/queue/status")
def whisper_queue_status():
    return jsonify({
        "queue": state["whisper_queue"],
        "running": state["_queue_running"],
    })


@app.route("/api/whisper/queue/clear", methods=["POST"])
def whisper_queue_clear():
    if not state["_queue_running"]:
        state["whisper_queue"] = []
    return jsonify({"status": "ok"})


@app.route("/api/whisper/queue/remove", methods=["POST"])
def whisper_queue_remove():
    data = request.json or {}
    item_id = data.get("id")
    state["whisper_queue"] = [x for x in state["whisper_queue"] if x["id"] != item_id or x["status"] == "running"]
    return jsonify({"status": "ok", "queue": state["whisper_queue"]})


@app.route("/api/whisper/queue/start", methods=["POST"])
def whisper_queue_start():
    if state["_queue_running"]:
        return jsonify({"error": "Đang chạy rồi"}), 400

    data = request.json or {}
    model = data.get("model", "base")
    language = data.get("language", "auto")

    pending = [x for x in state["whisper_queue"] if x["status"] == "pending"]
    if not pending:
        return jsonify({"error": "Không có video nào đang chờ trong hàng"}), 400

    # Apply model/language to all pending items
    for item in pending:
        item["model"] = model
        item["language"] = language

    state["_queue_running"] = True
    thread = threading.Thread(target=_run_whisper_queue, daemon=True)
    thread.start()

    return jsonify({"status": "started", "count": len(pending)})


def _run_whisper_queue():
    """Process all pending items in whisper_queue sequentially."""
    import tempfile

    try:
        while True:
            item = next((x for x in state["whisper_queue"] if x["status"] == "pending"), None)
            if not item:
                break

            item["status"] = "running"
            item["progress"] = 0
            item["message"] = "Đang khởi động Whisper..."

            video_path = item["video_path"]
            model = item["model"]
            language = item["language"]
            log.info(f"Queue: processing {item['video_name']} model={model} lang={language}")

            status_file = os.path.join(
                tempfile.gettempdir(), f"vc_queue_{os.getpid()}_{item['id']}.json"
            )
            worker_script = str(BASE_DIR / "whisper_worker.py")

            cmd = [sys.executable, worker_script, video_path, model, language, status_file, FFMPEG_CMD]

            creationflags = 0
            if hasattr(subprocess, "CREATE_NO_WINDOW"):
                creationflags = subprocess.CREATE_NO_WINDOW

            try:
                proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    creationflags=creationflags,
                )

                def _drain(p):
                    for line in p.stdout:
                        line = line.rstrip()
                        if line:
                            log.info(f"  [q/{item['id']}] {line}")

                drain_thread = threading.Thread(target=_drain, args=(proc,), daemon=True)
                drain_thread.start()

                while proc.poll() is None:
                    time.sleep(1)
                    if os.path.exists(status_file):
                        try:
                            with open(status_file, "r", encoding="utf-8") as f:
                                d = json.load(f)
                            item["progress"] = d.get("progress", 0)
                            item["message"] = d.get("message", "Đang xử lý...")
                            item["segments_count"] = d.get("segments_count", 0)
                        except Exception:
                            pass

                proc.wait()
                drain_thread.join(timeout=3)

                # Read final result
                segments = []
                if os.path.exists(status_file):
                    try:
                        with open(status_file, "r", encoding="utf-8") as f:
                            d = json.load(f)
                        if d.get("segments"):
                            segments = d["segments"]
                            item["segments_count"] = d.get("segments_count", len(segments))
                    except Exception:
                        pass

                if proc.returncode == 0 and segments:
                    video_p = Path(video_path)
                    clean_segs = [
                        {"start": s["start"], "end": s["end"], "text": s["text"]}
                        for s in segments
                    ]

                    # Save .transcript.json
                    transcript_path = video_p.parent / f"{video_p.stem}.transcript.json"
                    with open(transcript_path, "w", encoding="utf-8") as f:
                        json.dump(
                            {"video": video_p.name, "model": model, "segments": clean_segs},
                            f, ensure_ascii=False, indent=2,
                        )

                    # Save .transcript.txt (timestamped)
                    txt_path = video_p.parent / f"{video_p.stem}.transcript.txt"
                    with open(txt_path, "w", encoding="utf-8") as f:
                        f.write(f"# Transcript: {video_p.name}\n")
                        f.write(f"# Model: {model}\n\n")
                        for seg in clean_segs:
                            f.write(f"[{fmt_timestamp(seg['start'])}] {seg['text']}\n")

                    item["status"] = "done"
                    item["progress"] = 100
                    item["transcript_path"] = str(transcript_path)
                    item["message"] = f"Xong! {len(segments)} đoạn → {transcript_path.name} + .txt"
                    log.info(f"Queue: {video_p.name} done ({len(segments)} segs) → json + txt")
                else:
                    item["status"] = "error"
                    item["error"] = f"Whisper lỗi (exit {proc.returncode})"
                    item["message"] = item["error"]
                    log.error(f"Queue: {item['video_name']} failed (exit {proc.returncode})")

            except Exception as e:
                item["status"] = "error"
                item["error"] = str(e)
                item["message"] = f"Lỗi: {e}"
                log.error(f"Queue item {item['id']} exception: {e}")
            finally:
                for f in [status_file, status_file + ".stop", status_file + ".tmp"]:
                    try:
                        if os.path.exists(f):
                            os.remove(f)
                    except Exception:
                        pass

    finally:
        state["_queue_running"] = False
        log.info("Whisper queue finished.")


# ---------------------------------------------------------------------------
# Whisper Transcription
# ---------------------------------------------------------------------------
@app.route("/api/whisper/check")
def whisper_check():
    """Check if faster-whisper is installed and GPU is available."""
    info = {"installed": False, "gpu": False, "device": "CPU", "models": []}
    try:
        import faster_whisper  # noqa: F401
        info["installed"] = True
        info["models"] = ["tiny", "base", "small", "medium", "large-v3"]

        # Best-effort GPU detection: try to init a tiny test with cuda
        gpu_detected = False
        gpu_name = None

        # Method 1: torch (most reliable)
        try:
            import torch
            if torch.cuda.is_available():
                gpu_detected = True
                gpu_name = torch.cuda.get_device_name(0)
        except Exception:
            pass

        # Method 2: ctranslate2 CUDA device check (no model load needed)
        if not gpu_detected:
            try:
                import ctranslate2
                specs = ctranslate2.get_supported_compute_types("cuda")
                if specs:  # non-empty means CUDA runtime is available
                    gpu_detected = True
            except Exception:
                pass

        if gpu_detected:
            info["gpu"] = True
            info["device"] = f"GPU ({gpu_name})" if gpu_name else "GPU (CUDA)"

    except ImportError:
        pass
    return jsonify(info)


@app.route("/api/transcribe", methods=["POST"])
def transcribe_video():
    """Start Whisper transcription in a separate subprocess (isolates ctranslate2 from pywebview)."""
    video_path = state.get("video_path")
    if not video_path or not os.path.exists(video_path):
        return jsonify({"error": "Chưa chọn video"}), 400

    if state["whisper"]["status"] == "running":
        return jsonify({"error": "Đang chạy Whisper, vui lòng đợi"}), 400

    data = request.json or {}
    model_name = data.get("model", "base")
    language = data.get("language", "vi")

    # Status file for IPC with worker subprocess
    import tempfile
    status_file = os.path.join(tempfile.gettempdir(), f"vc_whisper_{os.getpid()}.json")
    stop_file = status_file + ".stop"

    # Clean up any leftover stop file
    if os.path.exists(stop_file):
        os.remove(stop_file)

    # Reset state
    state["whisper"] = {
        "status": "running",
        "progress": 0,
        "message": f"Đang khởi động Whisper ({model_name})...",
        "error": None,
        "model": model_name,
        "segments_count": 0,
    }
    state["_whisper_status_file"] = status_file

    # Write initial status
    with open(status_file, "w", encoding="utf-8") as f:
        json.dump(state["whisper"], f, ensure_ascii=False)

    # Launch monitoring thread (which spawns the subprocess)
    worker_script = str(BASE_DIR / "whisper_worker.py")
    thread = threading.Thread(
        target=_monitor_whisper_subprocess,
        args=(video_path, model_name, language, status_file, worker_script),
        daemon=True,
    )
    thread.start()

    return jsonify({"status": "started", "model": model_name})


@app.route("/api/transcribe/status")
def transcribe_status():
    """Poll whisper status from the subprocess status file."""
    status_file = state.get("_whisper_status_file")
    if status_file and os.path.exists(status_file) and state["whisper"]["status"] == "running":
        try:
            with open(status_file, "r", encoding="utf-8") as f:
                worker_data = json.load(f)
            # Sync fields
            for k in ("progress", "message", "error", "segments_count"):
                if k in worker_data:
                    state["whisper"][k] = worker_data[k]
            # If worker finished, absorb result
            if worker_data.get("status") in ("done", "error"):
                state["whisper"]["status"] = worker_data["status"]
                if worker_data.get("segments"):
                    state["transcript"] = worker_data["segments"]
                _cleanup_whisper_files()
        except (json.JSONDecodeError, IOError):
            pass  # file mid-write, ignore
    return jsonify(state["whisper"])


@app.route("/api/transcribe/stop", methods=["POST"])
def stop_whisper():
    """Stop the Whisper worker subprocess."""
    # Create stop sentinel file (worker checks this between segments)
    status_file = state.get("_whisper_status_file")
    if status_file:
        stop_file = status_file + ".stop"
        try:
            with open(stop_file, "w") as f:
                f.write("stop")
            print("[Whisper] Stop sentinel created.", flush=True)
        except Exception:
            pass

    # Also kill the process directly for immediate stop
    proc = state.get("_whisper_proc")
    if proc and proc.poll() is None:
        print("[Whisper] Terminating worker process...", flush=True)
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=3)
        print("[Whisper] Worker terminated.", flush=True)

    state["_whisper_proc"] = None

    # Check if worker saved partial results before dying
    if status_file and os.path.exists(status_file):
        try:
            with open(status_file, "r", encoding="utf-8") as f:
                d = json.load(f)
            if d.get("segments"):
                state["transcript"] = d["segments"]
        except Exception:
            pass

    _cleanup_whisper_files()

    state["whisper"] = {
        "status": "idle",
        "progress": 0,
        "message": "Đã dừng Whisper.",
        "error": None,
        "model": None,
        "segments_count": 0,
    }
    return jsonify({"status": "stopped"})


def _cleanup_whisper_files():
    """Remove temporary IPC files."""
    status_file = state.get("_whisper_status_file")
    if status_file:
        for f in [status_file, status_file + ".stop", status_file + ".tmp"]:
            try:
                if os.path.exists(f):
                    os.remove(f)
            except Exception:
                pass
        state["_whisper_status_file"] = None


def _monitor_whisper_subprocess(
    video_path: str,
    model_name: str,
    language: str,
    status_file: str,
    worker_script: str,
):
    """Launch whisper_worker.py and monitor it until completion."""
    cmd = [
        sys.executable,
        worker_script,
        video_path,
        model_name,
        language,
        status_file,
        FFMPEG_CMD,
    ]
    print(f"[Whisper] Launching subprocess: {os.path.basename(sys.executable)} whisper_worker.py", flush=True)
    print(f"[Whisper] Model={model_name}, Language={language}", flush=True)

    creationflags = 0
    if hasattr(subprocess, "CREATE_NO_WINDOW"):
        creationflags = subprocess.CREATE_NO_WINDOW

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            creationflags=creationflags,
        )
        state["_whisper_proc"] = proc

        # Stream stdout from worker
        for line in proc.stdout:
            line = line.rstrip()
            if line:
                print(f"  [worker] {line}", flush=True)

        proc.wait()
        state["_whisper_proc"] = None

        rc = proc.returncode
        print(f"[Whisper] Worker exited with code {rc}", flush=True)

        if rc != 0:
            # Worker crashed — update status file with error
            try:
                with open(status_file, "r", encoding="utf-8") as f:
                    d = json.load(f)
                if d.get("status") not in ("done", "error"):
                    d["status"] = "error"
                    d["error"] = f"Whisper worker crashed (exit code {rc})"
                    with open(status_file, "w", encoding="utf-8") as f:
                        json.dump(d, f, ensure_ascii=False)
            except Exception:
                # Status file doesn't exist or is corrupt — set error directly
                state["whisper"]["status"] = "error"
                state["whisper"]["error"] = f"Whisper worker crashed (exit code {rc})"

    except Exception as e:
        print(f"[Whisper] Failed to launch worker: {e}", flush=True)
        state["whisper"]["status"] = "error"
        state["whisper"]["error"] = f"Không thể khởi động Whisper: {e}"


@app.route("/api/save-transcript", methods=["POST"])
def save_transcript():
    """Save transcript to file in user-chosen format (json, txt, txt_plain)."""
    data = request.json or {}
    fmt = data.get("format", "json")  # "json", "txt", or "txt_plain"
    save_folder = data.get("folder", "")  # user-chosen folder

    video_path = state.get("video_path")
    segments = state.get("transcript", [])

    if not segments:
        return jsonify({"error": "Chưa có transcript để lưu"}), 400
    if not video_path:
        return jsonify({"error": "Chưa chọn video"}), 400

    video_p = Path(video_path)
    whisper_model = state["whisper"].get("model", "N/A")

    # Determine save directory
    out_dir = Path(save_folder) if save_folder and os.path.isdir(save_folder) else video_p.parent

    ext = "json" if fmt == "json" else "txt"
    transcript_path = out_dir / f"{video_p.stem}.transcript.{ext}"

    if fmt == "txt":
        # TXT with timestamps: [HH:MM:SS] text
        with open(transcript_path, "w", encoding="utf-8") as f:
            f.write(f"# Transcript: {video_p.name}\n")
            f.write(f"# Model: {whisper_model}\n\n")
            for seg in segments:
                f.write(f"[{fmt_timestamp(seg['start'])}] {seg['text']}\n")

    elif fmt == "txt_plain":
        # TXT plain text only, no timestamps
        with open(transcript_path, "w", encoding="utf-8") as f:
            for seg in segments:
                f.write(f"{seg['text']}\n")

    else:
        # JSON with full data (strip word-level data to keep file clean)
        clean_segments = [
            {"start": s["start"], "end": s["end"], "text": s["text"]}
            for s in segments
        ]
        transcript_data = {
            "video": video_p.name,
            "model": whisper_model,
            "segments": clean_segments,
        }
        with open(transcript_path, "w", encoding="utf-8") as f:
            json.dump(transcript_data, f, ensure_ascii=False, indent=2)

    print(f"[Transcript] Saved ({fmt}): {transcript_path}", flush=True)
    return jsonify({
        "status": "ok",
        "path": str(transcript_path),
        "filename": transcript_path.name,
    })


@app.route("/api/export-prompts", methods=["POST"])
def export_prompts():
    """Pick a manifest.json, export its prompts to a CSV file next to it."""
    manifest_path = _open_file_dialog(
        title="Chọn file manifest.json đã điền prompt",
        filetypes_filter=[
            ("Manifest JSON", "*.manifest.json *.json"),
            ("All files", "*.*"),
        ],
        ps_filter="Manifest JSON (*.manifest.json;*.json)|*.manifest.json;*.json|All Files (*.*)|*.*",
    )

    if not manifest_path or not os.path.exists(manifest_path):
        return jsonify({"error": "Không chọn file nào"}), 400

    try:
        import csv as _csv
        with open(manifest_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        segments = data.get("segments", [])
        if not segments:
            return jsonify({"error": "Manifest không có segments"}), 400

        filled = sum(1 for s in segments if s.get("prompt", "").strip())

        mp = Path(manifest_path)
        stem = mp.stem
        if stem.endswith(".manifest"):
            stem = stem[: -len(".manifest")]
        txt_path = mp.parent / f"{stem}.prompts.txt"

        # One prompt per line — paste directly into image generation flow.
        # Empty segments get a placeholder so line number = segment id stays in sync.
        with open(txt_path, "w", encoding="utf-8") as f:
            for s in segments:
                prompt = s.get("prompt", "").strip()
                f.write((prompt if prompt else "(no prompt)") + "\n")

        log.info(f"export-prompts: {txt_path.name} ({filled}/{len(segments)} filled)")
        return jsonify({
            "status": "ok",
            "txt_path": str(txt_path),
            "txt_filename": txt_path.name,
            "total_segments": len(segments),
            "filled_prompts": filled,
            "empty_prompts": len(segments) - filled,
            "manifest_name": mp.name,
        })

    except Exception as e:
        log.error(f"export-prompts error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/import-cutlist", methods=["POST"])
def import_cutlist():
    """Open a file dialog to pick a .cutlist.json and return its segments."""
    path = _open_file_dialog(
        title="Chọn file cutlist (.json) từ skill JRE",
        filetypes_filter=[
            ("Cut list JSON", "*.json"),
            ("All files", "*.*"),
        ],
        ps_filter="Cut list JSON (*.json)|*.json|All Files (*.*)|*.*",
    )

    if not path or not os.path.exists(path):
        return jsonify({"error": "Không chọn file nào"}), 400

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        return jsonify({"error": f"Không đọc được file: {e}"}), 400

    # Support both full cutlist format and bare array
    if isinstance(data, list):
        segments = data
    elif isinstance(data, dict):
        segments = data.get("segments", [])
    else:
        return jsonify({"error": "Định dạng file không hợp lệ"}), 400

    if not segments:
        return jsonify({"error": "File không có đoạn cắt nào"}), 400

    # Validate each segment has start/end/title
    clean = []
    for i, seg in enumerate(segments):
        if not isinstance(seg, dict):
            continue
        clean.append({
            "start": str(seg.get("start", "00:00:00")),
            "end":   str(seg.get("end",   "00:00:00")),
            "title": str(seg.get("title", f"Clip {i+1}")),
        })

    if not clean:
        return jsonify({"error": "Không có đoạn hợp lệ trong file"}), 400

    source = data.get("source", "") if isinstance(data, dict) else ""
    return jsonify({"segments": clean, "count": len(clean), "source": source})


@app.route("/api/import-cutlist-multi", methods=["POST"])
def import_cutlist_multi():
    """Open a file dialog to pick a MULTI-SOURCE cutlist (.json) — each segment
    names its own `source_video` — as exported by the tong-hop-rabbit-hole
    skill's compiled arc. Segments are cross-checked against whichever folder
    was selected via /api/select-source-folder, if any."""
    path = _open_file_dialog(
        title="Chọn file cutlist đa nguồn (.json) từ skill tong-hop-rabbit-hole",
        filetypes_filter=[
            ("Cut list JSON", "*.json"),
            ("All files", "*.*"),
        ],
        ps_filter="Cut list JSON (*.json)|*.json|All Files (*.*)|*.*",
    )

    if not path or not os.path.exists(path):
        return jsonify({"error": "Không chọn file nào"}), 400

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        return jsonify({"error": f"Không đọc được file: {e}"}), 400

    if not isinstance(data, dict):
        return jsonify({"error": "Định dạng file không hợp lệ — cần object có 'segments'"}), 400

    raw_segments = data.get("segments", [])
    if not raw_segments:
        return jsonify({"error": "File không có đoạn cắt nào"}), 400

    clean = []
    for i, seg in enumerate(raw_segments):
        if not isinstance(seg, dict):
            continue
        source_video = str(seg.get("source_video", "")).strip()
        if not source_video:
            continue
        episode_id = str(seg.get("episode_id", ""))
        resolved = _resolve_source_video(source_video, episode_id)
        clean.append({
            "order": int(seg.get("order", i + 1)),
            "episode_id": episode_id,
            "source_video": source_video,
            "start": str(seg.get("start", "00:00:00")),
            "end": str(seg.get("end", "00:00:00")),
            "title": str(seg.get("title", f"Clip {i+1}")),
            "matched": resolved is not None,
        })

    if not clean:
        return jsonify({"error": "Không có đoạn hợp lệ (thiếu source_video) trong file — đây có phải cutlist đa nguồn không?"}), 400

    clean.sort(key=lambda s: s["order"])

    return jsonify({
        "segments": clean,
        "count": len(clean),
        "theme": data.get("theme", ""),
        "source_episodes": data.get("source_episodes", []),
        "folder_selected": bool(state.get("folder_videos")),
    })


@app.route("/api/cut-multi", methods=["POST"])
def cut_multi():
    """Batch-cut segments that each name their own source_video, resolved
    against the folder selected via /api/select-source-folder. Every clip is
    written into ONE flat output folder, numbered by the segment's global
    `order` so the files sort directly into the compiled arc's final order."""
    data = request.json or {}
    segments = data.get("segments", [])
    output_folder = data.get("output_folder", "")
    theme = data.get("theme", "")

    if not state.get("folder_videos"):
        return jsonify({"error": "Chưa chọn thư mục nguồn — bấm \"Chọn Thư Mục Chứa Các Tập\" trước"}), 400
    if not segments:
        return jsonify({"error": "Chưa có đoạn cắt nào"}), 400

    missing = []
    resolved_segments = []
    for seg in segments:
        video_path = _resolve_source_video(seg.get("source_video", ""), seg.get("episode_id", ""))
        if not video_path:
            missing.append(seg.get("source_video", "?"))
        else:
            resolved_segments.append({**seg, "_resolved_path": video_path})

    if missing:
        return jsonify({
            "error": "Không tìm thấy video nguồn trong thư mục đã chọn: " + ", ".join(sorted(set(missing))),
        }), 400

    try:
        subprocess.run([FFMPEG_CMD, "-version"], capture_output=True, timeout=5)
    except Exception:
        return jsonify({
            "error": "Không tìm thấy ffmpeg! Hãy đặt ffmpeg.exe vào thư mục ffmpeg/ của tool."
        }), 400

    state["cutting_multi"] = {
        "status": "running",
        "progress": 0,
        "results": [],
        "output_dir": None,
        "error": None,
        "current_segment": 0,
        "total_segments": len(resolved_segments),
        "segment_progress": 0,
        "segment_title": "",
        "speed": "",
        "eta": "",
    }

    log.info(f"cut_multi: starting thread, {len(resolved_segments)} segments, output_folder='{output_folder}'")

    thread = threading.Thread(
        target=_run_multi_cutting,
        args=(resolved_segments, output_folder, theme),
        daemon=True,
    )
    thread.start()

    return jsonify({"status": "started", "total": len(resolved_segments)})


@app.route("/api/cut-multi/status")
def cut_multi_status():
    return jsonify(state["cutting_multi"])


@app.route("/api/open-folder-multi", methods=["POST"])
def open_folder_multi():
    """Open the batch (multi-source) cutting output folder in Windows Explorer."""
    folder = state["cutting_multi"].get("output_dir") or str(OUTPUT_DIR)
    if os.path.exists(folder):
        os.startfile(folder)
    return jsonify({"status": "ok"})


@app.route("/api/open-file-location", methods=["POST"])
def open_file_location():
    """Open the folder containing a given file path in Windows Explorer."""
    data = request.json or {}
    file_path = data.get("path", "")
    folder = os.path.dirname(file_path)
    if folder and os.path.exists(folder):
        os.startfile(folder)
    return jsonify({"status": "ok"})


def _get_duration(video_path: str) -> float:
    """Get video duration in seconds using ffprobe or ffmpeg."""
    try:
        ffprobe = FFMPEG_CMD.replace("ffmpeg", "ffprobe")
        result = subprocess.run(
            [ffprobe, "-v", "quiet", "-print_format", "json",
             "-show_format", video_path],
            capture_output=True, text=True, timeout=30,
        )
        data = json.loads(result.stdout)
        return float(data["format"]["duration"])
    except Exception:
        return 0.0


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    port = 5555
    url = f"http://localhost:{port}"
    print(f"\n  [Video Cutter]")
    print(f"  Output: {OUTPUT_DIR}\n")

    def _start_flask_server():
        """Start Flask in a background thread."""
        app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False)

    def _run_browser_mode():
        """Fallback: run Flask in main thread, open browser."""
        print(f"  URL: {url}\n")
        import webbrowser
        webbrowser.open(url)
        app.run(host="127.0.0.1", port=port, debug=False)

    # ------------------------------------------------------------------
    # Try pywebview first (native window), fall back to browser
    # ------------------------------------------------------------------
    try:
        import webview

        # Start Flask in background daemon thread
        server = threading.Thread(target=_start_flask_server, daemon=True)
        server.start()
        time.sleep(1)  # Wait for Flask to start

        print(f"  Mode: Native Window (pywebview)")
        print(f"  URL:  {url}\n")

        # Create native desktop window
        webview.create_window(
            "Video Cutter",
            url,
            width=1100,
            height=850,
            min_size=(800, 600),
        )
        webview.start()

        # ---- webview.start() returned — user closed the window ----
        print("  Đã đóng cửa sổ.")

    except ImportError:
        # pywebview not installed — pure browser mode
        print("  Mode: Browser (pywebview chưa cài)")
        _run_browser_mode()
    except Exception as e:
        # pywebview crashed on init — fall back to browser
        print(f"  [!] pywebview lỗi: {e}")
        print(f"  → Chuyển sang chế độ browser...\n")
        _run_browser_mode()
