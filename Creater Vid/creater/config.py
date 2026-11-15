"""Paths, port and defaults of Creater Vid.

Values here are the code defaults. Anything changed on the Settings page is stored in the `settings` table and read
through `db.get_setting()`, which falls back to these defaults.
"""
from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent          # <Tool>\Creater Vid
DB_PATH = Path(os.environ.get("CREATER_DB_PATH") or (BASE_DIR / "creater.db"))   # override for tests
LOG_DIR = BASE_DIR / "logs"
WORK_DIR = BASE_DIR / "work"                                 # transient files (probe runs, setup logs)
ENGINE_DIR = BASE_DIR / "engine"                             # Remotion + three.js film engine (template of film/)
# The two kinds of video are two separate desks of the app: own projects, own workflow (workflow.FLOWS) and own
# rulebook (working copy <projects_root>\<rules_file>, first version from the seed). One rule never applies to the other.
KINDS = {
    "doc": {"label": "Phim tài liệu", "icon": "🎬", "home": "/doc", "rules_file": "RULEBOOK.doc.md",
            "seed": BASE_DIR / "RULEBOOK.doc.seed.md"},
    "news": {"label": "Tin tức", "icon": "📰", "home": "/news", "rules_file": "RULEBOOK.news.md",
             "seed": BASE_DIR / "RULEBOOK.news.seed.md"},
}
GEN_PY = BASE_DIR / "gen.py"                                 # asset generator headless turns run (ElevenLabs, fal.ai)
PARALLAX_PY = BASE_DIR / "parallax" / "parallax.py"          # still image -> 3D camera clip (depth + layers, local GPU)
LAYERKIT_PY = BASE_DIR / "staged" / "layerkit.py"            # image model paints each depth layer of a scene separately

PORT = 5010

# Tools shared with the rest of the machine: the Tool folder this app lives in (E:\Tool)
TOOLS_ROOT = BASE_DIR.parent
# Claude Code CLI installed with `npm i -g --prefix E:\Tool\claude-cli @anthropic-ai/claude-code`
# (kept outside AppData because the Claude desktop app's MSIX sandbox virtualizes AppData writes).
CLAUDE_CLI_DIR = TOOLS_ROOT / "claude-cli"
FFMPEG_FALLBACK = TOOLS_ROOT / "video-cutter-portable" / "ffmpeg" / "ffmpeg.exe"
FFPROBE_FALLBACK = TOOLS_ROOT / "video-cutter-portable" / "ffmpeg" / "ffprobe.exe"

DEFAULT_SETTINGS = {
    # projects (renders, images and footage are heavy: E: is nearly full, D: has room)
    "projects_root": r"K:\VideoLab\creater-projects",
    "budget_usd": "5",               # USD of generated assets (voice, images, video) a project may spend without asking
    "language": "en",                # language of everything on screen and of the narration
    "audience": "YouTube, khán giả Mỹ",
    "format": "16:9",
    "target_sec": "180",
    "style": "",                     # default style string appended to every image prompt (empty = Claude proposes one)
    "auto_advance": "0",             # 1 = new projects run every step without waiting for approval
    # how the pictures are made: layered = characters cut out and staged on painted plates (engine 3D);
    # fullframe = one finished image per scene (characters painted in) turned into a 3D camera clip (parallax/);
    # stacked = the image model paints 2-4 depth layers of a scene separately, the engine stacks them (staged/);
    # dossier = real photos and documents staged as evidence on a desk (engine src/dossier), AI only where no picture can exist
    "pipeline": "layered",
    # generation APIs (gen.py reads the keys; they are never shown to Claude nor sent back to the browser)
    "elevenlabs_api_key": "",
    "elevenlabs_base_url": "https://api.elevenlabs.io",   # or the address of an ElevenLabs-compatible reseller
    "fal_api_key": "",
    "openai_api_key": "",            # optional: GPT Image directly (model ids "openai:<model>")
    "openai_base_url": "https://api.openai.com/v1",   # or the /v1 address of an OpenAI-compatible reseller
    "google_api_key": "",            # optional: Gemini / Nano Banana directly (model ids "google:<model>")
    "tts_model": "eleven_v4",
    # narrator per language of the video: {"en": {"id", "name", "owner"}, ...} (owner = library voice owner, to add it)
    "voices": '{"en": {"id": "JBFqnCBsd6RMkjVDRZzb", "name": "George"}, '
              '"ru": {"id": "cQBwjaYSTY9mh3fUvHS3", "name": "Artsiom - e-learning, documentary"}}',
    # image models: a fal endpoint id, or "openai:<model>" / "google:<model>" to call OpenAI or Google directly
    "image_model_draft": "bytedance/seedream/v5/flash/text-to-image",    # cheap: casting candidates, sketches
    "image_model": "fal-ai/nano-banana-pro",                             # main images
    "image_model_edit": "fal-ai/nano-banana-pro/edit",                   # variants edited from a master image
    "video_model": "fal-ai/kling-video/v3/standard/image-to-video",
    # "gemini-web:<mode>" image models: gemini.google.com with the user's Gemini plan (creater/gemini_web.py)
    "gemini_web_profile": "",        # Chrome profile folder signed in to Google (empty = work\gemini_web\profile)
    "gemini_web_mode": "hidden",     # hidden (window off screen) | headless (no window) | show
    "gemini_web_fallback": "",       # model used when Gemini web fails (limit reached, signed out...); empty = stop and say why
    "gemini_web_delogo": "1",        # 1 = blur the Gemini mark in the bottom-right corner of the pictures
    "gemini_web_repair_model": "sonnet",   # Claude model that finds new selectors when Gemini changes its page
    "provider_status": "{}",         # last result of the Check buttons, per provider (JSON)
    # Telegram API (your own account): downloads the videos the public web preview of a channel will not serve
    "telegram_api_id": "",
    "telegram_api_hash": "",
    "telegram_phone": "",
    # Claude Code headless
    "claude_cli": "claude",
    "claude_permission_mode": "acceptEdits",
    "claude_allowed_tools": "Read,Write,Edit,Glob,Grep,Bash",
    "claude_model": "opus",          # default model of every step (alias or full id, empty = CLI default)
    "claude_effort": "high",         # low | medium | high | xhigh | max
    "claude_fallback_model": "",
    "claude_max_turns": "400",
    "claude_parallel": "4",
    # model of the subagents a turn spawns (Agent/Task tool: research, fact checks, evidence, source texts in the script
    # step), per desk. "inherit" = the turn's own model. Subagents make ~70% of the script step's tokens, but a blind
    # A/B on a documentary (2026-11-10) scored Sonnet subagents 5/10 vs Opus 8.5 on fact checks and 5.5 vs 9 on
    # evidence, and Sonnet saved summaries instead of verbatim texts: documentaries keep Opus. News: not tested yet.
    "subagent_model_doc": "inherit",
    "subagent_model_news": "sonnet",
    # "step" = every step run starts a new Claude session (a chat resumes the session of its step); "project" = one
    # session for the whole project (the old way: by the last steps every tool call re-read 700k-950k tokens).
    "claude_session_mode": "step",
    # Claude model / effort come only from these settings (projects no longer choose their own):
    # model_<desk>_<step> / effort_<desk>_<step>, empty = the desk default below, then claude_model / claude_effort
    "model_desk_doc": "", "effort_desk_doc": "xhigh",
    "model_desk_news": "", "effort_desk_news": "medium",
    # (the per-desk, per-step keys are added below from DESK_STEP_KEYS)
    # local tools
    "bgremove_python": str(TOOLS_ROOT / "bgremove" / ".venv" / "Scripts" / "python.exe"),     # torch + BiRefNet: scripts/cutout.py, free
    "whisper_python": r"C:\Python314\python.exe",  # faster-whisper + CUDA
    "ffmpeg": "",                    # empty = PATH, then E:\Tool\video-cutter-portable\ffmpeg
    # optional source: the Hổ Báo Studio highlight database (read-only, through its CLI)
    "jre_python": str(TOOLS_ROOT / "DataBase" / ".venv" / "Scripts" / "python.exe"),
    "jre_hldb": str(TOOLS_ROOT / "DataBase" / "hldb.py"),
    # YouTube through GPM Login profiles (creater/publish.py, creater/yt_gpm.py)
    "gpm_api": "http://127.0.0.1:9495",   # GPM Login local API
    "yt_visibility": "schedule",     # default of an upload: schedule (at metadata.publish_at) | private | unlisted | public
    "yt_time_doc": "20:00",          # publishing hour used when metadata has no usable publish_at (machine local time)
    "yt_time_news": "18:00",
    "yt_last_doc": "", "yt_last_news": "",   # channel picked for the last project of each desk: "<profile_id>|<channel_id>"
    # Telegram bot (creater/tgbot.py): step-by-step projects send their approvals to the user's chat
    "tg_bot_token": "",              # from @BotFather
    "tg_bot_on": "1",
    "tg_bot_chat": "", "tg_bot_chat_name": "",   # the paired chat (set by /start <code>, never typed)
    "tg_bot_pair": "",               # pairing code shown on the Settings page
    # news desk (the Tin tức page)
    "news_enabled": "1",             # 1 = the poller keeps every enabled topic up to date in the background
    "news_max_age_h": "48",          # items published longer ago than this are not taken in
    "news_keep_days": "14",          # items older than this are forgotten (starred ones and those made into videos stay)
}

SECRET_KEYS = ("elevenlabs_api_key", "elevenlabs_keys", "fal_api_key", "openai_api_key", "google_api_key", "telegram_api_hash",
               "tg_bot_token")
# a key left empty on the Settings page can come from the environment instead
SECRET_ENV = {"elevenlabs_api_key": "ELEVENLABS_API_KEY", "fal_api_key": "FAL_KEY", "openai_api_key": "OPENAI_API_KEY",
              "google_api_key": "GEMINI_API_KEY"}

STEP_SETTING_KEYS = ("script", "cast", "scenes", "images", "footage", "render", "metadata", "chat")
# steps of each desk that have their own Claude model / effort on the Settings page ("chat" = turns that answer a message)
DESK_STEP_KEYS = {"doc": ("script", "cast", "scenes", "images", "footage", "render", "metadata", "chat"),
                  "news": ("script", "scenes", "images", "footage", "render", "metadata", "chat")}
for _desk, _steps in DESK_STEP_KEYS.items():
    for _step in _steps:
        DEFAULT_SETTINGS.setdefault(f"model_{_desk}_{_step}", "")
        DEFAULT_SETTINGS.setdefault(f"effort_{_desk}_{_step}", "")
PIPELINES = {"layered": "Ghép lớp (nhân vật tách nền + nền vẽ)", "fullframe": "Ảnh liền khối → 3D",
             "stacked": "Xếp lớp: GPT vẽ từng lớp → camera 3D",
             "dossier": "Hồ sơ tư liệu: ảnh, tài liệu thật dựng 2.5D"}
