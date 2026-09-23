"""Paths, ports and defaults for JRE Studio.

Values here are the code defaults. Anything the user changes in the UI is stored
in the `settings` table and read through `get_setting()` in db.py, which falls back
to these defaults.
"""
from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent          # E:\DataBase
DB_PATH = BASE_DIR / "studio.db"
WORK_DIR = BASE_DIR / "work"                                 # transient files (transcript txt for Claude, run logs)
LOG_DIR = BASE_DIR / "logs"
SKILLS_DIR = BASE_DIR / ".claude" / "skills"

# Media root: where episodes, transcripts, cutlists and clip folders live.
MEDIA_ROOT = Path(os.environ.get("STUDIO_MEDIA_ROOT", r"E:\Dowload New\YouTube"))

# Existing tools (kept as they are, driven over HTTP / subprocess)
TOOLS_ROOT = Path(r"E:\Tool")
TOOL_SERVER_HELPER = TOOLS_ROOT / "_tool_server.py"
CUTTER_DIR = TOOLS_ROOT / "video-cutter-portable"
ZOOM_DIR = TOOLS_ROOT / "podcast-zoom-tool"
DOWNLOADER_DIR = TOOLS_ROOT / "Youtube Dowloader"

PORT_DOWNLOADER = 5001
PORT_CUTTER = 5002
PORT_ZOOM = 5003
PORT_STUDIO = 5004

# Interpreter that has faster-whisper + CUDA runtime wheels (the one Tool Manager uses for the Cutter).
PY_CUTTER = Path(r"C:\Users\nguye\AppData\Local\Python\pythoncore-3.14-64\python.exe")
PY_ZOOM = ZOOM_DIR / ".venv" / "Scripts" / "python.exe"
WHISPER_WORKER = CUTTER_DIR / "whisper_worker.py"
FFMPEG = CUTTER_DIR / "ffmpeg" / "ffmpeg.exe"
FFPROBE = CUTTER_DIR / "ffmpeg" / "ffprobe.exe"

# Claude Code CLI installed with `npm i -g --prefix E:\Tool\claude-cli @anthropic-ai/claude-code`
# (kept outside AppData because the desktop app's MSIX sandbox virtualizes AppData writes).
CLAUDE_CLI_DIR = TOOLS_ROOT / "claude-cli"

# Skill plugin folder of the desktop app (source of truth for SKILL.md files; ids may change).
# The desktop app is an MSIX package: seen from inside it the folder is under %APPDATA%\Claude, but its
# physical location (what Studio sees when launched from Tool Manager) is the package's LocalCache.
DESKTOP_SKILLS_GLOBS = [
    os.path.join(os.environ.get("APPDATA", r"C:\Users\nguye\AppData\Roaming"),
                 r"Claude\local-agent-mode-sessions\skills-plugin\*\*\skills"),
    os.path.join(os.environ.get("LOCALAPPDATA", r"C:\Users\nguye\AppData\Local"),
                 r"Packages\Claude_*\LocalCache\Roaming\Claude\local-agent-mode-sessions\skills-plugin\*\*\skills"),
]
DESKTOP_SKILLS_GLOB = DESKTOP_SKILLS_GLOBS[0]

# Pipeline defaults (overridable in settings table)
DEFAULT_SETTINGS = {
    "media_root": str(MEDIA_ROOT),
    "whisper_model": "large-v3",
    "whisper_language": "en",
    "max_segments": "12",
    "zoom_hooks": "1",              # 1 = zoom hook clips too
    "review_gate": "0",             # 1 = wait for manual approval of the cutlist before cutting
    "zoom_factor": "2.0",
    "zoom_smoothing_speed": "0.05",
    "zoom_analysis_fps": "10",
    "zoom_max_faces": "4",
    "zoom_min_switch_duration": "0.5",
    "zoom_mar_threshold": "0.12",
    "delete_original_clip_after_zoom": "0",
    "disk_warn_gb": "50",
    "claude_cli": "claude",
    "claude_max_turns": "80",
    "claude_allowed_tools": "Read,Write,Glob,Grep,WebSearch,WebFetch",
    "claude_permission_mode": "acceptEdits",
    "claude_model": "",             # empty = CLI default
    "select_retry": "1",
    "watch_enabled": "1",
    "file_stable_seconds": "30",
}

VIDEO_EXTS = {".mp4", ".mkv", ".webm", ".mov", ".m4v"}
