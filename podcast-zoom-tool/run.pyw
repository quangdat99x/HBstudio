"""
Podcast Auto-Zoom Tool — Native Webview Launcher
Double-click this file to start the tool.
Opens in a native desktop window (webview). No browser needed.
"""

import os
import sys
import time
import shutil
import threading
import io
import traceback
import logging

# Ensure we run from the script's directory
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(SCRIPT_DIR)

# ── Bootstrap: re-launch under the bundled venv (Python 3.12) ──
# This tool's dependencies (mediapipe, opencv, numpy<2) have no wheels for
# Python 3.14, so double-clicking run.pyw with the default interpreter fails
# with "connection" errors (Flask never starts). If a .venv exists and we are
# not already running inside it, re-spawn ourselves with the venv's pythonw.
def _ensure_venv():
    venv_pyw = os.path.join(SCRIPT_DIR, '.venv', 'Scripts', 'pythonw.exe')
    if not os.path.exists(venv_pyw):
        return  # No venv set up — fall through and hope deps are present.
    # Already running inside the venv?
    try:
        if os.path.samefile(sys.executable, venv_pyw):
            return
    except OSError:
        pass
    if os.path.normcase(os.path.abspath(sys.executable)) == \
       os.path.normcase(os.path.abspath(venv_pyw)):
        return
    # Re-launch this script with the venv interpreter and exit this process.
    import subprocess
    subprocess.Popen([venv_pyw, os.path.abspath(__file__)], cwd=SCRIPT_DIR)
    sys.exit(0)


_ensure_venv()

# Add current directory to path
sys.path.insert(0, SCRIPT_DIR)

# Hide cmd/console windows for every subprocess call on Windows.
# Must run before any module that may spawn ffmpeg/ffprobe/whisper.
from core import _no_console  # noqa: F401

# ── Logging setup: ALWAYS log to a file so errors are never lost ──
LOG_PATH = os.path.join(SCRIPT_DIR, 'debug.log')
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(LOG_PATH, encoding='utf-8', mode='w'),
    ]
)
logger = logging.getLogger('PodcastZoom')

# Redirect stdout/stderr to the log file as well
# (.pyw files may have None for stdout/stderr)
if not sys.stdout or not hasattr(sys.stdout, 'write'):
    sys.stdout = open(LOG_PATH, 'a', encoding='utf-8')
    sys.stderr = sys.stdout
else:
    # Ensure stdout/stderr use UTF-8 with error replacement
    # to prevent 'charmap' codec errors on Windows
    try:
        if hasattr(sys.stdout, 'buffer'):
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        if hasattr(sys.stderr, 'buffer'):
            sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    except Exception:
        pass

PORT = 5555
HOST = '127.0.0.1'

# Track Flask startup status
_flask_started = threading.Event()
_flask_error = None


class Api:
    """
    Python API exposed to webview JavaScript as window.pywebview.api.
    All public methods here become callable from JS.
    """

    def select_folder(self):
        """
        Open native folder picker dialog.
        Called from JS: await window.pywebview.api.select_folder()
        """
        import webview
        try:
            active_window = webview.windows[0]
            result = active_window.create_file_dialog(
                webview.FOLDER_DIALOG
            )
            if result:
                # result is a tuple of selected paths
                path = result[0] if isinstance(result, (list, tuple)) else str(result)
                return {'success': True, 'path': str(path)}
            return {'success': False, 'error': 'cancelled'}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def save_video(self, job_id):
        """
        Open native 'Save As' dialog and copy the processed video.
        Called from JS: await window.pywebview.api.save_video(jobId)
        """
        import webview
        try:
            from app import jobs
            if job_id not in jobs:
                return {'success': False, 'error': 'Job not found'}

            job = jobs[job_id]
            if job['status'] != 'complete':
                return {'success': False, 'error': 'Job not complete'}

            source_path = job['output_path']
            if not os.path.exists(source_path):
                return {'success': False, 'error': 'Output file not found'}

            original_name = os.path.splitext(job['original_filename'])[0]
            default_name = f"{original_name}_zoomed.mp4"

            active_window = webview.windows[0]
            result = active_window.create_file_dialog(
                webview.SAVE_DIALOG,
                save_filename=default_name,
                file_types=('Video Files (*.mp4)',),
            )

            if result:
                save_path = result if isinstance(result, str) else str(result)
                if not save_path.lower().endswith('.mp4'):
                    save_path += '.mp4'
                shutil.copy2(source_path, save_path)
                return {'success': True, 'path': save_path}
            else:
                return {'success': False, 'error': 'cancelled'}

        except Exception as e:
            return {'success': False, 'error': str(e)}


def start_flask():
    """Run Flask server in a background thread."""
    global _flask_error
    try:
        logger.info("Importing Flask app...")
        from app import app
        logger.info(f"Starting Flask on {HOST}:{PORT}")
        _flask_started.set()
        app.run(host=HOST, port=PORT, debug=False, use_reloader=False)
    except Exception as e:
        _flask_error = str(e)
        logger.error(f"Flask server failed to start: {e}")
        logger.error(traceback.format_exc())
        _flask_started.set()  # Unblock the main thread even on error


def wait_for_flask(timeout=15):
    """Wait until Flask is actually responding, or timeout."""
    import urllib.request
    import urllib.error

    start = time.time()
    while time.time() - start < timeout:
        if _flask_error:
            logger.error(f"Flask startup error detected: {_flask_error}")
            return False
        try:
            resp = urllib.request.urlopen(f'http://{HOST}:{PORT}/', timeout=2)
            resp.close()
            logger.info("Flask server is responding!")
            return True
        except (urllib.error.URLError, ConnectionRefusedError, OSError):
            time.sleep(0.5)
    logger.error(f"Flask did not respond within {timeout}s")
    return False


def main():
    global _flask_error

    logger.info("=" * 50)
    logger.info("Podcast Auto-Zoom Tool starting...")
    logger.info(f"Script dir: {SCRIPT_DIR}")
    logger.info(f"Python: {sys.executable}")
    logger.info(f"Python version: {sys.version}")
    logger.info("=" * 50)

    # Check webview availability
    try:
        import webview
        logger.info(f"pywebview version: {webview.__version__ if hasattr(webview, '__version__') else 'unknown'}")
    except ImportError as e:
        logger.error(f"pywebview not installed: {e}")
        _show_error_msgbox(
            "Missing Dependency",
            "pywebview is not installed.\n\nRun: pip install pywebview>=5.0"
        )
        return

    # Pre-download dependencies
    logger.info("Checking dependencies...")
    try:
        from core.ffmpeg_utils import ensure_ffmpeg
        ffmpeg_path = ensure_ffmpeg()
        logger.info(f"[OK] FFmpeg: {ffmpeg_path}")
    except Exception as e:
        logger.error(f"FFmpeg check failed: {e}")
        logger.error(traceback.format_exc())

    try:
        from core.face_detector import ensure_model
        model_path = ensure_model()
        logger.info(f"[OK] FaceLandmarker model: {model_path}")
    except Exception as e:
        logger.error(f"Face model check failed: {e}")
        logger.error(traceback.format_exc())

    # Start Flask in a background daemon thread
    logger.info("Starting Flask server thread...")
    flask_thread = threading.Thread(target=start_flask, daemon=True)
    flask_thread.start()

    # Wait for Flask to be ready (with retry)
    flask_ready = wait_for_flask(timeout=15)

    if not flask_ready:
        error_msg = _flask_error or "Server did not respond in time"
        logger.error(f"Cannot start: {error_msg}")

        # Show error page in webview instead of blank page
        error_html = f"""
        <html>
        <head><title>Podcast Zoom - Error</title></head>
        <body style="background:#1a1a2e;color:#e0e0e0;font-family:Segoe UI,sans-serif;
                      display:flex;align-items:center;justify-content:center;height:100vh;margin:0;">
          <div style="text-align:center;max-width:600px;padding:40px;">
            <h1 style="color:#ff6b6b;font-size:28px;">⚠ Server Failed to Start</h1>
            <p style="font-size:16px;line-height:1.6;color:#aaa;">
              The Flask server could not start. Error details:
            </p>
            <pre style="background:#0d0d1a;padding:20px;border-radius:8px;text-align:left;
                        font-size:13px;color:#ff9999;overflow-x:auto;white-space:pre-wrap;">
{error_msg}
            </pre>
            <p style="color:#888;margin-top:20px;font-size:14px;">
              Check <code>debug.log</code> in the tool folder for full details.<br>
              Path: {LOG_PATH.replace(chr(92), '/')}
            </p>
          </div>
        </body>
        </html>
        """
        window = webview.create_window(
            'Podcast Auto-Zoom - Error',
            html=error_html,
            width=700,
            height=500,
        )
        webview.start()
        return

    # Create API instance and pass via js_api parameter
    api = Api()

    # Create native webview window with JS API bridge
    logger.info("Creating webview window...")
    window = webview.create_window(
        'Podcast Auto-Zoom',
        f'http://{HOST}:{PORT}',
        width=1100,
        height=780,
        min_size=(900, 600),
        resizable=True,
        text_select=False,
        js_api=api,
    )

    # Start webview (blocks until window is closed)
    logger.info("Webview started, waiting for user to close window...")
    webview.start()
    logger.info("Window closed. Exiting.")


def _show_error_msgbox(title, message):
    """Show a simple error message box on Windows."""
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(0, message, title, 0x10)
    except Exception:
        pass


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        logger.error(f"Unhandled exception: {e}")
        logger.error(traceback.format_exc())
        _show_error_msgbox("Podcast Zoom - Fatal Error", str(e))
