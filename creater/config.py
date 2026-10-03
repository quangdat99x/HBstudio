"""Paths, port and defaults of Creater Vid.

Values here are the code defaults. Anything changed on the Settings page is stored in the `settings` table and read
through `db.get_setting()`, which falls back to these defaults.
"""
from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent          # E:\Creater Vid
DB_PATH = Path(os.environ.get("CREATER_DB_PATH") or (BASE_DIR / "creater.db"))   # override for tests
LOG_DIR = BASE_DIR / "logs"
WORK_DIR = BASE_DIR / "work"                                 # transient files (probe runs, setup logs)
ENGINE_DIR = BASE_DIR / "engine"                             # Remotion + three.js film engine (template of film/)
RULEBOOK_SEED = BASE_DIR / "RULEBOOK.seed.md"                # first version of the rulebook

PORT = 5010

# Tools shared with the rest of the machine (E:\Tool)
TOOLS_ROOT = Path(r"E:\Tool")
# Claude Code CLI installed with `npm i -g --prefix E:\Tool\claude-cli @anthropic-ai/claude-code`
# (kept outside AppData because the Claude desktop app's MSIX sandbox virtualizes AppData writes).
CLAUDE_CLI_DIR = TOOLS_ROOT / "claude-cli"
FFMPEG_FALLBACK = TOOLS_ROOT / "video-cutter-portable" / "ffmpeg" / "ffmpeg.exe"
FFPROBE_FALLBACK = TOOLS_ROOT / "video-cutter-portable" / "ffmpeg" / "ffprobe.exe"

DEFAULT_SETTINGS = {
    # projects (renders, images and footage are heavy: E: is nearly full, D: has room)
    "projects_root": r"D:\VideoLab\creater-projects",
    "credit_budget": "40",           # Higgsfield credits a project may spend without asking
    "language": "en",                # language of everything on screen and of the narration
    "audience": "YouTube, khán giả Mỹ",
    "format": "16:9",
    "target_sec": "180",
    "style": "",                     # default style string appended to every image prompt (empty = Claude proposes one)
    "voice_name": "Alistair",
    "voice_id": "d9d5c263-f84e-4752-97b5-3750fcc6fd2f",
    "auto_advance": "0",             # 1 = new projects run every step without waiting for approval
    # Claude Code headless
    "claude_cli": "claude",
    "claude_permission_mode": "acceptEdits",
    "claude_allowed_tools": "Read,Write,Edit,Glob,Grep,Bash",
    "claude_model": "opus",          # default model of every step (alias or full id, empty = CLI default)
    "claude_effort": "high",         # low | medium | high | xhigh | max
    "claude_fallback_model": "",
    "claude_max_turns": "400",
    # per-step overrides, empty = the defaults above (keys: model_<step>, effort_<step>)
    "model_script": "", "effort_script": "xhigh",
    "model_cast": "", "effort_cast": "",
    "model_scenes": "", "effort_scenes": "",
    "model_images": "", "effort_images": "",
    "model_footage": "", "effort_footage": "",
    "model_render": "", "effort_render": "",
    "model_chat": "", "effort_chat": "",
    # local tools
    "bgremove_python": r"E:\Tool\bgremove\.venv\Scripts\python.exe",     # torch + BiRefNet: scripts/cutout.py, 0 credits
    "whisper_python": r"C:\Users\nguye\AppData\Local\Python\pythoncore-3.14-64\python.exe",  # faster-whisper + CUDA
    "ffmpeg": "",                    # empty = PATH, then E:\Tool\video-cutter-portable\ffmpeg
    # optional source: the JRE Studio highlight database (read-only, through its CLI)
    "jre_python": r"E:\DataBase\.venv\Scripts\python.exe",
    "jre_hldb": r"E:\DataBase\hldb.py",
    # last Higgsfield check (written by the probe on the Settings page)
    "hf_balance": "", "hf_plan": "", "hf_checked_at": "",
}

STEP_SETTING_KEYS = ("script", "cast", "scenes", "images", "footage", "render", "chat")
