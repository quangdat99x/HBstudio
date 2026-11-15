"""Paths, ports and defaults for Hổ Báo Studio.

Values here are the code defaults. Anything the user changes in the UI is stored
in the `settings` table and read through `get_setting()` in db.py, which falls back
to these defaults.
"""
from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent          # <Tool>\DataBase
DB_PATH = Path(os.environ.get("STUDIO_DB_PATH") or (BASE_DIR / "studio.db"))   # override for tests
WORK_DIR = BASE_DIR / "work"                                 # transient files (transcript txt for Claude, run logs)
LOG_DIR = BASE_DIR / "logs"
SKILLS_DIR = BASE_DIR / ".claude" / "skills"

# Media root: where episodes, transcripts, cutlists and clip folders live.
MEDIA_ROOT = Path(os.environ.get("STUDIO_MEDIA_ROOT", r"K:\YouTube"))

# Existing tools (kept as they are, driven over HTTP / subprocess)
TOOLS_ROOT = BASE_DIR.parent                                 # the Tool folder (E:\Tool)
TOOL_SERVER_HELPER = TOOLS_ROOT / "_tool_server.py"
CUTTER_DIR = TOOLS_ROOT / "video-cutter-portable"
ZOOM_DIR = TOOLS_ROOT / "podcast-zoom-tool"
DOWNLOADER_DIR = TOOLS_ROOT / "Youtube Dowloader"

PORT_DOWNLOADER = 5001
PORT_CUTTER = 5002
PORT_ZOOM = 5003
PORT_STUDIO = 5004
PORT_CREATER = 5010                                           # Creater Vid (phim tài liệu)
CREATER_DIR = TOOLS_ROOT / "Creater Vid"


def _load_data_root_module():
    """<Tool>\\_data_root.py: the data folder of this machine (data_root.local.json) and the layout shared by every
    machine. Loaded by file path because each tool runs in its own interpreter."""
    import importlib.util
    f = TOOLS_ROOT / "_data_root.py"
    if not f.exists():
        return None
    try:
        spec = importlib.util.spec_from_file_location("tool_data_root", f)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    except Exception:  # noqa: BLE001
        return None


DATA_ROOT = _load_data_root_module()


def media_root_locked() -> str | None:
    """<data_root>\\YouTube when this machine has a data folder: it wins over the media_root setting."""
    p = DATA_ROOT.path("studio_media") if DATA_ROOT else None
    return str(p) if p else None

# Interpreter that has faster-whisper + CUDA runtime wheels (the one Tool Manager uses for the Cutter).
PY_CUTTER = Path(r"C:\Python314\python.exe")
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
    # newer desktop builds keep the plugin under LocalAppData\Claude-Data, and Claude Code mirrors it in ~\.claude
    os.path.join(os.environ.get("LOCALAPPDATA", r"C:\Users\nguye\AppData\Local"),
                 r"Claude-Data\*\local-agent-mode-sessions\skills-plugin\*\*\skills"),
    os.path.join(os.path.expanduser("~"), r".claude\skills\synced\*"),
]
DESKTOP_SKILLS_GLOB = DESKTOP_SKILLS_GLOBS[0]

# Pipeline defaults (overridable in settings table)
DEFAULT_SETTINGS = {
    "media_root": str(MEDIA_ROOT),
    "whisper_model": "large-v3",
    "whisper_language": "en",
    "max_segments": "12",
    "zoom_hooks": "1",              # 1 = zoom hook clips too
    "auto_zoom": "0",               # 0 = zoom only what the user picks on the episode page; 1 = zoom every clip right after cutting
    "review_gate": "0",             # 1 = wait for manual approval of the cutlist before cutting
    "zoom_factor": "2.0",
    "zoom_smoothing_speed": "0.05",
    "zoom_analysis_fps": "10",
    "zoom_max_faces": "4",
    "zoom_min_switch_duration": "0.5",
    "zoom_mar_threshold": "0.12",
    "hook_join_transition": "slideright",  # "Nối hook": ffmpeg xfade name of the hook → zoomed highlight transition
    "hook_join_duration": "1.2",     # seconds of that transition
    "hook_join_sfx": "",             # file in assets/sfx or a full path; empty = transition.mp3 (ElevenLabs)
    "hook_join_sfx_volume": "0.7",
    "delete_original_clip_after_zoom": "0",
    "delete_source_after_ready": "0",   # off: topic compilations cut from full episodes. 1 = delete the full source video once every clip of the episode is on disk
    "disk_warn_gb": "50",
    "claude_cli": "claude",
    "claude_max_turns": "80",
    "claude_allowed_tools": "Read,Write,Glob,Grep,WebSearch,WebFetch,Bash(python *),Bash(py *)",
    "claude_permission_mode": "acceptEdits",
    "claude_model": "",             # legacy single setting, empty = CLI default
    "claude_model_select": "fable",  # content selection: best model by default (alias fable = Claude Fable 5.1)
    "claude_effort_select": "xhigh", # low | medium | high | xhigh | max, empty = CLI default
    "claude_model_ask": "",         # model for the Ask-AI page
    "claude_effort_ask": "",
    "claude_fallback_model": "",    # comma-separated fallbacks when the primary model is overloaded
    "google_translate_api_key": "", # official Cloud Translation API key for the select-to-translate popup
    "title_skill": "viet-tittle",   # skill run by the "Viết Title" button on each highlight
    "claude_model_title": "opus",   # model for "Viết Title" (user default: opus); "gemini-*" runs it on the Gemini API
    "gemini_api_key": "",           # Gemini API key for "gemini-*" models (else env GEMINI_API_KEY / E:\Tool\viet-tittle-gemini\.env)
    "gemini_base_url": "",          # empty = Google; a reseller key: its OpenAI-compatible …/v1 (or Gemini-native …/v1beta)
    "claude_effort_title": "high",
    # AI centre image of the thumbnail: rendered by GPT Image through Creater Vid's gen.py (its OpenAI key)
    "thumb_image_model": "openai:gpt-image-2.5-sunburst",
    "thumb_image_quality": "high",  # low | medium | high (high measured $0.042 for one 2:3 image, 2026-10-22)
    "claude_model_groups": "opus",   # "Phân nhóm bằng Claude" on the Khách mời page (user's choice: opus)
    "claude_effort_groups": "medium",
    "claude_model_topic": "sonnet",  # topic compilation from full episodes (reads many windows: cheaper model by default)
    "claude_effort_topic": "medium",
    "claude_model_topic_keywords": "haiku",   # one tiny call that proposes the filter keywords
    "select_retry": "1",
    "watch_enabled": "1",
    "file_stable_seconds": "30",
}

VIDEO_EXTS = {".mp4", ".mkv", ".webm", ".mov", ".m4v"}

# Video tổng hợp (studio/pipeline/compile_video.py): narration goes through Creater Vid's gen.py (its ElevenLabs key)
DEFAULT_SETTINGS.update({
    "claude_model_compile_topic": "sonnet",   # reads the picked highlight, names topic + filter keywords
    "claude_effort_compile_topic": "low",
    "claude_model_compile_scan": "sonnet",    # reads the keyword windows of every transcript (many tokens)
    "claude_effort_compile_scan": "medium",
    "claude_model_compile_arc": "opus",       # builds the arc and writes the narration
    "claude_effort_compile_arc": "high",
    "compile_pad_sec": "120",                 # ± seconds of transcript around every keyword hit
    "compile_max_scan_tokens": "600000",      # windows above this budget: the ones with the fewest hits are dropped
    "compile_voice_id": "",                   # empty = Creater's English narrator voice
    "compile_tts_model": "eleven_v3",         # audio tags ([grave], [whispers] ...) need v3/v4
    "compile_card_text": "1",                 # 1 = show the narration text on the card
    "compile_video_encoder": "auto",          # auto = NVENC when the GPU encodes, x264 = always CPU
})
# Phim tài liệu bổ sung (studio/pipeline/doc_extend.py): Creater Vid makes the film, Studio writes one bridging line
DEFAULT_SETTINGS.update({
    "claude_model_docext_bridge": "sonnet",  # writes the one line that hands the highlight over to the documentary
    "claude_effort_docext_bridge": "low",
    "docext_target_min": "10",               # default documentary length in the dialog (minutes, approximate)
    "docext_budget_usd": "",                 # empty = Creater's own default budget
})
DEFAULT_SETTINGS["compile_require_zoom"] = "1"   # 1 = every clip of a compilation is zoomed (existing zoom, else zoom it first)
