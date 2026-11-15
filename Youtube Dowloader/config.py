"""
Centralized configuration for YouTube Downloader.
All paths, constants, and tunable parameters in one place.
"""
import os

# ── Paths ────────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FFMPEG_DIR = os.path.join(BASE_DIR, 'ffmpeg')
HISTORY_FILE = os.path.join(BASE_DIR, 'history.csv')
DEFAULT_DOWNLOAD_DIR = r"K:\Downloads\YouTube"

# ── Download settings ────────────────────────────────────────────────────
MAX_CONCURRENT_DOWNLOADS = 3       # Concurrent download threads
DOWNLOAD_RETRIES = 10              # yt-dlp retry count per fragment
FRAGMENT_RETRIES = 10              # Fragment-level retries
CONCURRENT_FRAGMENTS = 2           # Parallel HLS fragments (fallback only; bursts get the IP bot-flagged)
SOCKET_TIMEOUT = 60                # Network timeout in seconds

# ── 4G dongle (backup line for YouTube) ──────────────────────────────────
# While it is plugged in, YouTube traffic goes through it. When YouTube asks
# to "confirm you're not a bot", the tool reboots it for a new mobile IP and
# retries, before falling back to cookies.
DONGLE_HOST = '192.168.100.1'      # Admin address of the "HiMI 4G UFI" dongle
DONGLE_PASSWORD = ''               # Its admin password; empty = never reboot it
DONGLE_RESET_EVERY = 600           # At most one reboot per 10 minutes

# ── Proxies (proxies.txt, one per line) ──────────────────────────────────
# When proxies.txt has entries, every YouTube job goes through one of them
# (round-robin). A proxy YouTube bot-checks is rested and the job moves on to
# the next one, before the 4G dongle and cookies are tried.
PROXY_COOLDOWN = 1800              # Rest a bot-checked proxy for 30 minutes
PROXY_TRIES = 3                    # Proxies one job tries before giving up on them

# ── Flask ─────────────────────────────────────────────────────────────────
SECRET_KEY = 'yt-dl-desktop-2026'
HOST = '127.0.0.1'
PORT = 0  # 0 = auto-pick a free port (pywebview handles this)

# ── Desktop window ────────────────────────────────────────────────────────
WINDOW_TITLE = 'YouTube Downloader'
WINDOW_WIDTH = 1000
WINDOW_HEIGHT = 720
WINDOW_MIN_SIZE = (800, 560)
