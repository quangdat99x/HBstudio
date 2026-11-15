"""
yt-dlp engine: core download and info extraction logic.

Every request runs without cookies first (works for nearly every video and
never puts the Google account at risk). If YouTube bot-checks that attempt and
the 4G dongle is plugged in, the dongle is rebooted for a new IP and the
attempt retried; only then come cookies.txt and the installed browsers.
yt-dlp keeps itself up to date, because YouTube breaks it every few weeks and
each fix ships as a new release.
"""
import importlib
import importlib.metadata
import os
import re
import shutil
import subprocess
import sys
import threading
import time

import yt_dlp

from config import (
    FFMPEG_DIR,
    DOWNLOAD_RETRIES, FRAGMENT_RETRIES, CONCURRENT_FRAGMENTS, SOCKET_TIMEOUT,
    DONGLE_PASSWORD, DONGLE_RESET_EVERY, PROXY_TRIES,
)
from core import dongle, proxies

# Ensure FFmpeg is on PATH
if os.path.isdir(FFMPEG_DIR) and FFMPEG_DIR not in os.environ.get('PATH', ''):
    os.environ['PATH'] = FFMPEG_DIR + os.pathsep + os.environ.get('PATH', '')


# ── Cookie / anti-bot handling ───────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COOKIES_FILE = os.path.join(BASE_DIR, 'cookies.txt')

# Browsers to try reading cookies from, in priority order.
# Firefox works most reliably on Windows (no App-Bound Encryption).
_BROWSER_ORDER = ['firefox', 'chrome', 'edge', 'brave']

# yt-dlp needs a JavaScript runtime to solve YouTube's "n" challenge. Without
# one it is left with the JS-less clients (android_vr, now visionos), whose
# media URLs YouTube keeps capping at ~1 MB. Only deno is enabled by default,
# so point yt-dlp at whichever runtime is actually installed.
_JS_RUNTIME_ORDER = ['deno', 'node', 'bun', 'quickjs']


def _detect_js_runtimes() -> dict:
    found = {}
    for name in _JS_RUNTIME_ORDER:
        path = shutil.which(name)
        if path:
            found[name] = {'path': path}
    return found


JS_RUNTIMES = _detect_js_runtimes()


# ── Keeping yt-dlp current ───────────────────────────────────────────────
# YouTube breaks yt-dlp every few weeks and the fix always ships as a new
# release. On 2026-08-17 it capped android_vr media links at ~1 MB, so every
# cookie-less download died with 403 and fell through to the cookie sources:
# it looked like a cookie problem for weeks while yt-dlp 2026.08.19 had long
# fixed it. So check PyPI once a day, again whenever YouTube blocks every
# source, and swap the new version in without restarting the server.
UPDATE_STAMP = os.path.join(BASE_DIR, '.ytdlp_update_check')
_ROUTINE_UPDATE_EVERY = 24 * 3600
_FAILURE_UPDATE_EVERY = 3600
_NO_WINDOW = getattr(subprocess, 'CREATE_NO_WINDOW', 0)

_update_lock = threading.Lock()
# Cleared while pip swaps the package, so no job imports a half-installed yt-dlp.
_ytdlp_ready = threading.Event()
_ytdlp_ready.set()


def _version_key(v: str) -> tuple:
    """yt-dlp calls itself '2026.08.19', pip says '2026.8.19': compare numbers."""
    return tuple(int(p) for p in (v or '').split('.') if p.isdigit())


def _installed_ytdlp_version() -> str:
    """Version on disk, which runs ahead of the loaded one after an upgrade."""
    importlib.invalidate_caches()
    try:
        return importlib.metadata.version('yt-dlp')
    except importlib.metadata.PackageNotFoundError:
        return ''


def _ytdlp_modules() -> dict:
    return {name: mod for name, mod in sys.modules.items()
            if name.split('.')[0] in ('yt_dlp', 'yt_dlp_ejs', 'yt_dlp_plugins')}


def _reload_ytdlp():
    """Drop every loaded yt-dlp module and import the version now on disk.

    Jobs already running keep their references to the old modules and finish
    on the old code; everything started afterwards gets the new one.
    """
    global yt_dlp
    old = _ytdlp_modules()
    for name in old:
        del sys.modules[name]
    importlib.invalidate_caches()
    try:
        yt_dlp = importlib.import_module('yt_dlp')
    except Exception:
        # A release that won't even import must not take the tool down.
        for name in _ytdlp_modules():
            del sys.modules[name]
        sys.modules.update(old)
        raise


def update_ytdlp(min_interval: float = _ROUTINE_UPDATE_EVERY) -> bool:
    """pip-upgrade yt-dlp, unless that was already tried within min_interval.

    Returns True when a different yt-dlp than before is now loaded.
    """
    with _update_lock:
        try:
            due = time.time() - os.path.getmtime(UPDATE_STAMP) >= min_interval
        except OSError:
            due = True
        _ytdlp_ready.clear()
        try:
            if due:
                try:
                    with open(UPDATE_STAMP, 'w', encoding='utf-8') as f:
                        f.write(time.strftime('%Y-%m-%d %H:%M:%S'))
                    subprocess.run(
                        [sys.executable, '-m', 'pip', 'install', '-U', '--quiet',
                         '--disable-pip-version-check', 'yt-dlp[default]'],
                        capture_output=True, timeout=300, creationflags=_NO_WINDOW,
                    )
                except (OSError, subprocess.SubprocessError):
                    pass
            installed = _installed_ytdlp_version()
            if not installed or _version_key(installed) == _version_key(yt_dlp.version.__version__):
                return False
            try:
                _reload_ytdlp()
            except Exception:
                return False
            return True
        finally:
            _ytdlp_ready.set()


def start_background_update():
    """Run the daily check off the request path; call once at server start."""
    threading.Thread(target=update_ytdlp, name='ytdlp-update', daemon=True).start()


class _WarningCollector:
    """Minimal yt-dlp logger that keeps warnings and errors so we can surface them."""

    def __init__(self):
        self.warnings = []
        self.errors = []

    def debug(self, msg):
        pass

    def info(self, msg):
        pass

    def warning(self, msg):
        self.warnings.append(str(msg))

    def error(self, msg):
        self.errors.append(str(msg))

    def saw(self, needle: str) -> bool:
        n = needle.lower()
        return any(n in w.lower() for w in self.warnings)


def _cookiefile_valid() -> bool:
    """True if cookies.txt exists and looks like it has real cookie lines."""
    try:
        if not os.path.isfile(COOKIES_FILE):
            return False
        with open(COOKIES_FILE, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    return True
    except Exception:
        pass
    return False


def _cookie_strategies():
    """
    Yield (label, opts_patch) cookie strategies to try in order.
    Always starts with 'no cookies' (works for non-flagged videos),
    then cookies.txt, then each installed browser.
    """
    strategies = [('no-cookies', {})]
    if _cookiefile_valid():
        strategies.append(('cookies.txt', {'cookiefile': COOKIES_FILE}))
    for br in _BROWSER_ORDER:
        strategies.append((f'browser:{br}', {'cookiesfrombrowser': (br,)}))
    return strategies


# Failures that mean "this cookie source was rejected" — worth retrying with
# the next one instead of giving up. A bare 403 on the media URL belongs here:
# it means YouTube handed yt-dlp a client whose URLs are already dead.
_RETRYABLE_PATTERNS = (
    'sign in to confirm',
    'not a bot',
    'cookies',
    '403',
    'forbidden',
    'requested format is not available',
    'page needs to be reloaded',
    'po token',
    'only images are available',
    'unable to download video data',
)


def _is_retryable_error(msg: str) -> bool:
    """True if another cookie source might succeed where this one failed."""
    m = (msg or '').lower()
    return any(p in m for p in _RETRYABLE_PATTERNS)


def _is_bot_error(msg: str) -> bool:
    m = (msg or '').lower()
    return 'sign in to confirm' in m or 'not a bot' in m


# Failures of the media rather than of the page: the other set of formats
# (https vs HLS) may still download where this one did not.
_MEDIA_ERROR_PATTERNS = (
    '403',
    'forbidden',
    '401',
    'unauthorized',
    'requested format is not available',
    'fragment',
    'unable to download video data',
    # yt-dlp closes the file when one fragment gives up while other threads
    # are still appending to it, which hides the fragment's real error.
    'write to closed file',
)


def _is_media_error(msg: str) -> bool:
    m = (msg or '').lower()
    return any(p in m for p in _MEDIA_ERROR_PATTERNS)


# ── Helpers ──────────────────────────────────────────────────────────────
def extract_video_id(url: str) -> str:
    """Extract YouTube video ID from various URL formats."""
    patterns = [
        r'(?:v=|/v/|youtu\.be/|/embed/)([a-zA-Z0-9_-]{11})',
        r'(?:shorts/)([a-zA-Z0-9_-]{11})',
    ]
    for p in patterns:
        m = re.search(p, url)
        if m:
            return m.group(1)
    return url


def sanitize_filename(name: str) -> str:
    """Remove invalid characters for Windows filenames."""
    name = re.sub(r'[<>:"/\\|?*]', '', name)
    name = re.sub(r'[\x00-\x1f]', '', name)
    name = re.sub(r'[\u200b-\u200f\u2028-\u202f\u2060\ufeff]', '', name)
    name = re.sub(r'[^\u0000-\uffff]', '', name)
    name = name.strip().rstrip('. ')
    if len(name) > 200:
        name = name[:200]
    return name or 'video'


def format_duration(seconds) -> str:
    """Format duration in seconds to HH:MM:SS or MM:SS."""
    if not seconds:
        return "00:00"
    s = int(seconds)
    h, remainder = divmod(s, 3600)
    m, sec = divmod(remainder, 60)
    if h > 0:
        return f"{h:02d}:{m:02d}:{sec:02d}"
    return f"{m:02d}:{sec:02d}"


# ── Build yt-dlp options ─────────────────────────────────────────────────
def _base_opts(logger=None) -> dict:
    """Build base yt-dlp options — simple and clean."""
    opts = {
        'quiet': True,
        'no_warnings': True,
        'ffmpeg_location': FFMPEG_DIR,
        'socket_timeout': SOCKET_TIMEOUT,
        'retries': DOWNLOAD_RETRIES,
        'fragment_retries': FRAGMENT_RETRIES,
        'file_access_retries': 5,
        'extractor_retries': 5,
        'continuedl': True,
        'noprogress': False,
        # Needed to solve YouTube's "n" challenge; without it every media URL
        # comes back 403. Falls back to fetching the solver from GitHub when
        # the yt-dlp-ejs package isn't installed locally.
        'remote_components': ['ejs:github'],
    }
    if JS_RUNTIMES:
        opts['js_runtimes'] = JS_RUNTIMES
    # With the 4G dongle plugged in, YouTube traffic always goes through it,
    # whichever connection Windows prefers for everything else.
    source = dongle.local_ip()
    if source:
        opts['source_address'] = source
    if logger is not None:
        opts['logger'] = logger
        opts['no_warnings'] = False
    return opts


def _diagnose(error_msg: str, collector) -> str:
    """Turn a raw yt-dlp failure into something the user can act on.

    error_msg is what the cookie-less attempt died of. The cookie sources
    after it mostly fail on reading browser cookies, which says nothing about
    what YouTube objected to; blaming cookies for every failure is what kept
    sending the user to refresh cookies that were never the problem.
    """
    if 'write to closed file' in (error_msg or '') and collector is not None and collector.errors:
        error_msg = collector.errors[-1]
    m = (error_msg or '').lower()
    version = yt_dlp.version.__version__

    if not JS_RUNTIMES:
        return (
            "Thiếu JavaScript runtime nên yt-dlp không giải được mã bảo vệ của YouTube "
            "(mọi link tải đều trả về 403). Hãy cài Node.js (https://nodejs.org) "
            "hoặc Deno rồi khởi động lại tool."
        )

    if _is_bot_error(m) or (proxies.available() and _is_proxy_error(m)):
        hint = ''
        if proxies.available():
            st = proxies.status()
            hint += (f"Đã thử proxy nhưng bị chặn/lỗi ({st['ready']}/{st['total']} proxy còn dùng được, "
                     "proxy bị chặn sẽ nghỉ 30 phút). Proxy datacenter thường bị YouTube chặn sẵn, "
                     "nên dùng proxy residential/mobile. ")
        if dongle.local_ip():
            hint = (
                "Đổi IP 4G lần này không qua được (tool chỉ khởi động lại dongle tối đa "
                f"1 lần mỗi {DONGLE_RESET_EVERY // 60} phút). " if DONGLE_PASSWORD else
                "Điền DONGLE_PASSWORD trong config.py để tool tự khởi động lại dongle 4G "
                "lấy IP mới. "
            )
        if collector is not None and collector.saw('no longer valid'):
            return (
                "YouTube yêu cầu xác thực chống bot và cookie YouTube đã hết hạn "
                "(YouTube đã xoay vòng phiên đăng nhập). " + hint + "Bấm nút 'Đăng nhập & lấy "
                "cookie tự động' ở mục Cookie YouTube, đăng nhập lại là tool tự lưu cookie mới."
            )
        return (
            "YouTube yêu cầu xác thực chống bot. " + hint + "Bấm nút "
            "'Đăng nhập & lấy cookie tự động' ở mục Cookie YouTube để làm mới cookie."
        )

    if any(p in m for p in ('403', 'forbidden', '401', 'unauthorized', 'requested format is not available')):
        return (
            f"YouTube chặn link tải (403/401) với cả định dạng https lẫn HLS (yt-dlp {version}). "
            "Không phải lỗi cookie: YouTube vừa đổi cách chặn. Tool tự cài bản vá yt-dlp "
            "khi gặp lỗi này (thường có sau 1–3 ngày), cứ thử lại sau vài giờ."
        )

    if 'format' in m:
        return (
            f"Không tìm thấy định dạng video (yt-dlp {version}). "
            "Tool tự cài bản vá yt-dlp khi có, thử lại sau vài giờ."
        )

    return error_msg


# ── New 4G IP when YouTube bot-checks us ─────────────────────────────────
# Rebooting the dongle cuts every connection through it, and YouTube media
# links only work from the IP that fetched them. So a reboot waits until every
# running job is stuck on the same bot check, and new jobs wait for it to end.
_RESET_WAIT = 300  # how long a blocked job waits for the others to get blocked or finish

_jobs = threading.Condition()
_active_jobs = 0
_blocked_jobs = 0
_resetting = False
_reset_count = 0
_reset_ok = False
_last_reset = 0.0


def _enter_job():
    global _active_jobs
    with _jobs:
        while _resetting:
            _jobs.wait()
        _active_jobs += 1


def _leave_job():
    global _active_jobs
    with _jobs:
        _active_jobs -= 1
        _jobs.notify_all()


def _new_ip_for_blocked_job(notify=None) -> bool:
    """Called by a job that hit the bot check: reboot the dongle for a new IP,
    or share the result of the reboot another blocked job does.

    True when the job should retry on a new IP.
    """
    global _blocked_jobs, _resetting, _reset_count, _reset_ok, _last_reset
    if not dongle.available():
        return False
    with _jobs:
        seen = _reset_count
        _blocked_jobs += 1
        _jobs.notify_all()
        try:
            deadline = time.monotonic() + _RESET_WAIT
            while True:
                if _reset_count != seen:  # another blocked job just rebooted it
                    return _reset_ok
                if not _resetting:
                    if time.time() - _last_reset < DONGLE_RESET_EVERY:
                        return False  # rebooted moments ago; the new IP is blocked too
                    if _blocked_jobs >= _active_jobs:
                        break  # every running job is stuck: safe to cut the line
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return False  # others keep downloading through this IP
                _jobs.wait(remaining)
            _resetting = True
            _last_reset = time.time()
        finally:
            _blocked_jobs -= 1

    ok = False
    try:
        if notify:
            notify('Đang đổi IP 4G (khởi động lại dongle ~1 phút)…')
        ok = dongle.reset_ip(log=lambda msg: print(msg, flush=True))
    except Exception as e:
        print(f'[dongle] lỗi khi đổi IP: {e}', flush=True)
    finally:
        with _jobs:
            _resetting = False
            _reset_ok = ok
            _reset_count += 1
            _jobs.notify_all()
    return ok


_PROXY_ERRORS = ('proxy', 'tunnel connection failed', 'unable to connect', 'timed out',
                 'connection refused', 'connection reset', '407')


def _is_proxy_error(msg: str) -> bool:
    m = (msg or '').lower()
    return any(p in m for p in _PROXY_ERRORS)


def _try_proxies(run, notify=None):
    """run({'proxy': p}) on up to PROXY_TRIES proxies from the pool.

    A proxy that is bot-checked or unreachable is benched and the next one is
    tried. Returns (result, error) like _try_sources.
    """
    tried, error = [], ''
    for _ in range(PROXY_TRIES):
        p = proxies.pick(exclude=tried)
        if not p:
            break
        tried.append(p)
        print(f'[proxy] using {proxies.mask(p)}', flush=True)
        try:
            return run({'proxy': p}), ''
        except Exception as e:
            error = str(e)
        if not (_is_bot_error(error) or _is_proxy_error(error)):
            return None, error  # private/deleted/etc.: another proxy won't help
        proxies.bench(p)
        print(f'[proxy] {proxies.mask(p)} blocked/failed, benched', flush=True)
        if notify:
            notify(f'Proxy bị YouTube chặn, đổi proxy khác ({len(tried)}/{PROXY_TRIES})…')
    return None, error or 'Không còn proxy nào dùng được (tất cả đang bị nghỉ).'


def _try_sources(run, notify=None):
    """Call run(cookie_patch) with each cookie source until one succeeds.

    Returns (result, error): result is None when every source failed, and
    error is what the cookie-less attempt died of.
    """
    first_error = ''
    for label, patch in _cookie_strategies():
        if not patch and proxies.available():
            # Cookie-less attempts go through the proxy pool first. Cookies
            # stay on the own line: one Google account showing up from many
            # IPs is what gets an account flagged.
            result, error = _try_proxies(run, notify)
            if result is not None:
                return result, ''
            first_error = first_error or error
            if not (_is_bot_error(error) or _is_proxy_error(error)):
                if not _is_retryable_error(error):
                    break
                continue
            # Every proxy tried was blocked: fall through to the own line.
        try:
            return run(patch), ''
        except Exception as e:
            error = str(e)
        if not patch and _is_bot_error(error) and _new_ip_for_blocked_job(notify):
            # The bot check is tied to the IP: a fresh 4G IP gets past it
            # without spending the user's cookies.
            try:
                return run(patch), ''
            except Exception as e:
                error = str(e)
        first_error = first_error or error
        # A block worth retrying — move on to the next cookie source.
        # Anything else (private/deleted/etc.) won't be fixed by cookies.
        if not _is_retryable_error(error):
            break
    return None, first_error


def _run_with_sources(run, notify=None):
    """_try_sources, and once more if YouTube blocked every source and a
    newer yt-dlp turned out to be available."""
    _ytdlp_ready.wait(timeout=600)
    _enter_job()
    try:
        used = yt_dlp.version.__version__
        result, error = _try_sources(run, notify)
        if result is None and _is_retryable_error(error):
            update_ytdlp(_FAILURE_UPDATE_EVERY)
            # Also retry when another job's update swapped a new version in meanwhile.
            if yt_dlp.version.__version__ != used:
                result, error = _try_sources(run, notify)
        return result, error
    finally:
        _leave_job()


# ── Public API ───────────────────────────────────────────────────────────
def get_video_info(url: str) -> dict:
    """Fetch video metadata without downloading.

    Tries cookie strategies in order so YouTube's "confirm you're not a bot"
    block is bypassed when cookies.txt or a logged-in browser is available.
    """
    collector = _WarningCollector()

    def _extract(patch):
        opts = _base_opts(collector)
        opts['extract_flat'] = False
        opts.update(patch)
        with yt_dlp.YoutubeDL(opts) as ydl:
            return ydl.extract_info(url, download=False)

    info, error = _run_with_sources(_extract)
    if info is None:
        return {'success': False, 'error': _diagnose(error, collector), 'url': url}

    # Collect resolutions
    formats = []
    seen = set()
    for f in info.get('formats', []):
        h = f.get('height')
        if h and f.get('vcodec') != 'none':
            res = f"{h}p"
            if res not in seen:
                seen.add(res)
                formats.append({'resolution': res, 'height': h})
    formats.sort(key=lambda x: x['height'], reverse=True)

    return {
        'success': True,
        'title': info.get('title', 'Unknown'),
        'channel': info.get('uploader', 'Unknown'),
        'duration': info.get('duration', 0),
        'duration_formatted': format_duration(info.get('duration', 0)),
        'thumbnail': info.get('thumbnail', ''),
        'url': url,
        'formats': formats,
        'view_count': info.get('view_count', 0),
    }


def download_video(
    task_id: str,
    url: str,
    download_dir: str,
    max_resolution: str,
    title_hint: str,
    progress_callback=None,
) -> dict:
    """
    Download a video with progress tracking.

    Returns: {'success': bool, 'filepath': str, 'error': str}
    """
    height = int(max_resolution.replace('p', ''))
    # Tried in order, moving on only when the formats themselves fail.
    # https (DASH) first: ~60 large range requests per episode is gentle on
    # YouTube. But YouTube keeps capping the https links of whichever client
    # yt-dlp relies on at ~1 MB (android_vr since 2026-08-17, visionos on and
    # off since), and then HLS still works. HLS costs thousands of small
    # requests, though, and YouTube answers a burst of them with 401s (hence
    # the retry backoff below), so it is only the fallback.
    format_chain = (
        f'bestvideo[height<={height}][protocol=https]+bestaudio[protocol=https]',
        f'bestvideo[height<={height}][protocol^=m3u8]+bestaudio[protocol^=m3u8]',
        f'bestvideo[height<={height}]+bestaudio/best[height<={height}]/'
        f'bestvideo+bestaudio/best',
    )
    video_id = extract_video_id(url)

    def _progress_hook(d):
        if not progress_callback:
            return
        if d['status'] == 'downloading':
            total = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
            downloaded = d.get('downloaded_bytes', 0)
            speed = d.get('speed', 0)
            eta = d.get('eta', 0)
            percent = (downloaded / total * 100) if total > 0 else 0
            # HLS/DASH report per-fragment byte totals, so the first fragment
            # would read as 100%. Count fragments instead when we have them.
            frag_i, frag_n = d.get('fragment_index'), d.get('fragment_count')
            if frag_n:
                percent = (frag_i or 0) / frag_n * 100
            speed_str = ""
            if speed:
                if speed > 1024 * 1024:
                    speed_str = f"{speed / 1024 / 1024:.1f} MB/s"
                else:
                    speed_str = f"{speed / 1024:.1f} KB/s"
            progress_callback(task_id, 'downloading', round(percent, 1), speed_str, eta)
        elif d['status'] == 'finished':
            progress_callback(task_id, 'merging', 100, '', 0)

    collector = _WarningCollector()

    def _build_opts(format_sel, cookie_patch, use_id_filename=False):
        if use_id_filename:
            outtmpl = os.path.join(download_dir, f'{video_id}.%(ext)s')
        else:
            safe_title = sanitize_filename(title_hint) if title_hint else '%(title)s'
            outtmpl = os.path.join(download_dir, f'{safe_title}.%(ext)s')

        opts = _base_opts(collector)
        opts.update({
            'format': format_sel,
            'outtmpl': outtmpl,
            'progress_hooks': [_progress_hook],
            'merge_output_format': 'mp4',
            'windowsfilenames': True,
            'check_formats': False,
            'concurrent_fragment_downloads': CONCURRENT_FRAGMENTS,
            # A fragment that stays unavailable must fail the download:
            # skipping it would silently leave a gap in the video.
            'skip_unavailable_fragments': False,
            # Back off 1, 2, 4 … 30 s between retries. Retrying at once burns
            # all attempts inside a single second, while YouTube's 401 bursts
            # and this connection's resets clear after a second or two.
            'retry_sleep_functions': {
                'http': lambda n: min(2 ** n, 30),
                'fragment': lambda n: min(2 ** n, 30),
            },
        })
        opts.update(cookie_patch)
        return opts

    def _do_download(opts):
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            base, _ = os.path.splitext(filename)
            return info, base + '.mp4'

    def _download(format_sel, patch):
        try:
            return _do_download(_build_opts(format_sel, patch))
        except OSError as e:
            if e.errno != 22:  # Invalid filename
                raise
            if progress_callback:
                progress_callback(task_id, 'downloading', 0, '', 0)
            return _do_download(_build_opts(format_sel, patch, use_id_filename=True))

    def _run(patch):
        for i, format_sel in enumerate(format_chain):
            try:
                return _download(format_sel, patch)
            except Exception as e:
                if i == len(format_chain) - 1 or not _is_media_error(str(e)):
                    raise

    def _notify(msg):
        if progress_callback:
            progress_callback(task_id, 'downloading', 0, msg, 0)

    # Try each cookie strategy; bot blocks fall through to the next one.
    result, error = _run_with_sources(_run, _notify)
    if result is None:
        return {'success': False, 'error': _diagnose(error, collector)}

    info, filename = result
    return {
        'success': True,
        'filepath': filename,
        'title': info.get('title', title_hint),
        'video_id': video_id,
    }


def clear_cache() -> bool:
    """Clear yt-dlp cache."""
    try:
        with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
            ydl.cache.remove()
        return True
    except Exception:
        return False
