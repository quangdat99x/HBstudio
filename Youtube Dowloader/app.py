"""
YouTube Video Downloader — Desktop App
Flask backend + pywebview native window (no CMD window).
"""
import os
import sys
import json
import uuid
import threading
import traceback
from concurrent.futures import ThreadPoolExecutor

from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO

from config import (
    SECRET_KEY, DEFAULT_DOWNLOAD_DIR, MAX_CONCURRENT_DOWNLOADS,
    WINDOW_TITLE, WINDOW_WIDTH, WINDOW_HEIGHT, WINDOW_MIN_SIZE,
)
from core import engine, history, queue_store

# YouTube breaks yt-dlp every few weeks; pick up the fix without a restart.
engine.start_background_update()
# Mục trong danh sách chờ đang tải lúc server tắt thì quay về "chưa tải".
queue_store.reset_stuck()

# ── Flask app ─────────────────────────────────────────────────────────────
app = Flask(__name__, static_folder='static', template_folder='templates')
app.config['SECRET_KEY'] = SECRET_KEY
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# ── Download state ────────────────────────────────────────────────────────
download_tasks = {}
tasks_lock = threading.Lock()
executor = ThreadPoolExecutor(max_workers=MAX_CONCURRENT_DOWNLOADS)


def _emit_progress(task_id, status, percent, speed='', eta=0, **extra):
    """Emit progress to frontend via SocketIO."""
    data = {
        'task_id': task_id,
        'status': status,
        'percent': percent,
        'speed': speed,
        'eta': eta,
    }
    data.update(extra)
    with tasks_lock:
        if task_id in download_tasks:
            download_tasks[task_id].update({
                'status': status,
                'progress': percent,
                'speed': speed,
            })
    socketio.emit('download_progress', data)


def _download_worker(task_id, url, download_dir, max_res, title, queue_id=None):
    """Worker that downloads a video, reporting any crash back to the UI."""
    try:
        _run_download(task_id, url, download_dir, max_res, title, queue_id)
    except Exception as e:
        # Without this the exception is swallowed by the Future and the task
        # sits at "Đang chờ" forever with nothing shown to the user.
        traceback.print_exc()
        with tasks_lock:
            if task_id in download_tasks:
                download_tasks[task_id]['status'] = 'error'
                download_tasks[task_id]['error'] = str(e)
        _emit_progress(task_id, 'error', 0, error=f'Lỗi nội bộ: {e}')
        if queue_id:
            _queue_finished(queue_id, None, f'Lỗi nội bộ: {e}')


def _queue_finished(queue_id, result, error=None):
    """Ghi kết quả tải vào mục danh sách chờ và báo cho giao diện."""
    if result and result.get('success'):
        item = queue_store.update(
            queue_id, status='done', error=None,
            title=result.get('title') or (queue_store.get(queue_id) or {}).get('title') or '',
            filepath=result['filepath'], done_at=queue_store.now(),
        )
    else:
        item = queue_store.update(queue_id, status='error', error=error or (result or {}).get('error'))
    if item:
        socketio.emit('queue_item', item)


def _run_download(task_id, url, download_dir, max_res, title, queue_id=None):
    """Download one video and emit its progress events."""
    result = engine.download_video(
        task_id=task_id,
        url=url,
        download_dir=download_dir,
        max_resolution=max_res,
        title_hint=title,
        progress_callback=_emit_progress,
    )

    if result['success']:
        # Save to history
        history.save(
            video_id=result.get('video_id', ''),
            title=result.get('title', title),
            url=url,
            filepath=result['filepath'],
            resolution=max_res,
        )
        with tasks_lock:
            if task_id in download_tasks:
                download_tasks[task_id]['status'] = 'completed'
                download_tasks[task_id]['progress'] = 100
                download_tasks[task_id]['filename'] = os.path.basename(result['filepath'])

        _emit_progress(
            task_id, 'completed', 100,
            filename=os.path.basename(result['filepath']),
        )
    else:
        with tasks_lock:
            if task_id in download_tasks:
                download_tasks[task_id]['status'] = 'error'
                download_tasks[task_id]['error'] = result['error']

        _emit_progress(task_id, 'error', 0, error=result['error'])

    if queue_id:
        _queue_finished(queue_id, result)


# ── Routes ────────────────────────────────────────────────────────────────
@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/fetch-info', methods=['POST'])
def fetch_info():
    """Fetch video metadata for a list of URLs."""
    data = request.json
    urls = data.get('urls', [])
    results = []
    for url in urls:
        url = url.strip()
        if not url:
            continue
        info = engine.get_video_info(url)
        if info['success']:
            prev = history.check(url, engine.extract_video_id)
            info['already_downloaded'] = prev is not None
            info['prev_download'] = prev
        results.append(info)
    return jsonify({'results': results})


@app.route('/api/download', methods=['POST'])
def start_download():
    """Start downloading videos via thread pool."""
    data = request.json
    urls = data.get('urls', [])
    download_dir = data.get('download_dir', DEFAULT_DOWNLOAD_DIR)
    max_resolution = data.get('max_resolution', '1080p')

    os.makedirs(download_dir, exist_ok=True)

    task_ids = []
    for item in urls:
        url = item.get('url', '').strip()
        title = item.get('title', '')
        if not url:
            continue

        task_id = str(uuid.uuid4())[:8]
        with tasks_lock:
            download_tasks[task_id] = {
                'url': url,
                'title': title,
                'status': 'queued',
                'progress': 0,
                'speed': '',
                'error': None,
                'filename': None,
            }
        task_ids.append(task_id)

        # Submit to thread pool
        executor.submit(
            _download_worker,
            task_id, url, download_dir, max_resolution, title,
        )

    return jsonify({
        'task_ids': task_ids,
        'download_dir': download_dir,
    })


@app.route('/api/default-dir', methods=['GET'])
def get_default_dir():
    return jsonify({'default_dir': DEFAULT_DOWNLOAD_DIR})


def _open_folder_dialog(initial_dir=''):
    """Open a native folder picker. Returns chosen path or ''."""
    import subprocess
    _cflags = subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0

    # Strategy 1: PowerShell FolderBrowserDialog (UTF-8 output)
    try:
        safe_initial = (initial_dir or '').replace("'", "''")
        ps_script = (
            "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; "
            "Add-Type -AssemblyName System.Windows.Forms; "
            "$f = New-Object System.Windows.Forms.FolderBrowserDialog; "
            "$f.Description = 'Chon thu muc luu video'; "
            "$f.ShowNewFolderButton = $true; "
            f"if ('{safe_initial}' -and (Test-Path '{safe_initial}')) {{ $f.SelectedPath = '{safe_initial}' }}; "
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
    except Exception as e:
        print(f"[Folder dialog PS error] {e}", flush=True)

    # Strategy 2: tkinter fallback
    try:
        script = (
            'import sys,io\n'
            'sys.stdout=io.TextIOWrapper(sys.stdout.buffer,encoding="utf-8",errors="replace")\n'
            'import tkinter as tk\nfrom tkinter import filedialog\n'
            'r=tk.Tk();r.withdraw();r.attributes("-topmost",True)\n'
            'p=filedialog.askdirectory(title="Chon thu muc luu video")\n'
            'print(p or "");r.destroy()\n'
        )
        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True, text=True, encoding='utf-8', errors='replace',
            timeout=120,
        )
        return result.stdout.strip()
    except Exception as e:
        print(f"[Folder dialog tk error] {e}", flush=True)
        return ''


@app.route('/api/choose-folder', methods=['POST'])
def choose_folder():
    """Open a native folder picker and return the chosen path."""
    data = request.json or {}
    initial_dir = data.get('current_dir', '')
    path = _open_folder_dialog(initial_dir)
    if not path:
        return jsonify({'success': False, 'error': 'Không chọn thư mục nào'})
    return jsonify({'success': True, 'path': path})


@app.route('/api/cookies/auto', methods=['POST'])
def cookies_auto():
    """Open a YouTube login window and save that session straight to cookies.txt.

    Runs in its own process: pywebview needs its own main loop, and this server
    may be running headless as a Tool Manager subprocess.
    """
    import subprocess
    script = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          'core', 'cookie_login.py')
    if not os.path.isfile(script):
        return jsonify({'success': False, 'error': 'Thiếu core/cookie_login.py'})

    _cflags = subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
    try:
        proc = subprocess.run(
            [sys.executable, script, engine.COOKIES_FILE],
            capture_output=True, text=True, encoding='utf-8', errors='replace',
            timeout=1000, creationflags=_cflags,
        )
    except subprocess.TimeoutExpired:
        return jsonify({'success': False, 'error': 'Hết thời gian chờ đăng nhập.'})
    except Exception as e:
        return jsonify({'success': False, 'error': f'Không mở được cửa sổ đăng nhập: {e}'})

    # The script prints one JSON line; anything else on stdout is noise.
    for line in reversed((proc.stdout or '').strip().splitlines()):
        try:
            return jsonify(json.loads(line))
        except ValueError:
            continue

    err = (proc.stderr or '').strip().splitlines()
    return jsonify({
        'success': False,
        'error': err[-1] if err else 'Cửa sổ đăng nhập kết thúc mà không trả về kết quả.',
    })


@app.route('/api/tasks', methods=['GET'])
def get_tasks():
    """Return snapshot of all download tasks (used by Tool Manager quick-download)."""
    with tasks_lock:
        snapshot = {tid: dict(t) for tid, t in download_tasks.items()}
    return jsonify({'tasks': snapshot})


@app.route('/api/history', methods=['GET'])
def get_history():
    h = history.load()
    h.reverse()
    return jsonify({'history': h, 'total': len(h)})


@app.route('/api/history/clear', methods=['POST'])
def clear_history():
    try:
        history.clear()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/repair', methods=['POST'])
def repair():
    return jsonify({'success': engine.clear_cache()})


# ── Cookie management ─────────────────────────────────────────────────────
def _open_cookie_file_dialog():
    """Open a native file picker for a cookies.txt file. Returns path or ''."""
    import subprocess
    _cflags = subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0

    # Strategy 1: PowerShell OpenFileDialog (UTF-8 output)
    try:
        ps_script = (
            "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; "
            "Add-Type -AssemblyName System.Windows.Forms; "
            "$f = New-Object System.Windows.Forms.OpenFileDialog; "
            "$f.Title = 'Chon file cookies.txt'; "
            "$f.Filter = 'Cookies (*.txt)|*.txt|All Files (*.*)|*.*'; "
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
    except Exception as e:
        print(f"[Cookie dialog PS error] {e}", flush=True)

    # Strategy 2: tkinter fallback
    try:
        script = (
            'import sys,io\n'
            'sys.stdout=io.TextIOWrapper(sys.stdout.buffer,encoding="utf-8",errors="replace")\n'
            'import tkinter as tk\nfrom tkinter import filedialog\n'
            'r=tk.Tk();r.withdraw();r.attributes("-topmost",True)\n'
            'p=filedialog.askopenfilename(title="Chon file cookies.txt",'
            'filetypes=[("Cookies","*.txt"),("All files","*.*")])\n'
            'print(p or "");r.destroy()\n'
        )
        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True, text=True, encoding='utf-8', errors='replace',
            timeout=120,
        )
        return result.stdout.strip()
    except Exception as e:
        print(f"[Cookie dialog tk error] {e}", flush=True)
        return ''


@app.route('/api/cookies/status', methods=['GET'])
def cookies_status():
    """Report whether cookies.txt exists, is valid, and how old it is."""
    import time
    path = engine.COOKIES_FILE
    valid = engine._cookiefile_valid()
    info = {'exists': os.path.isfile(path), 'valid': valid, 'age_days': None, 'count': 0}
    if info['exists']:
        try:
            mtime = os.path.getmtime(path)
            info['age_days'] = int((time.time() - mtime) / 86400)
            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                info['count'] = sum(
                    1 for ln in f
                    if ln.strip() and not ln.startswith('#') and 'youtube' in ln.lower()
                )
        except Exception:
            pass
    return jsonify(info)


@app.route('/api/cookies/import', methods=['POST'])
def cookies_import():
    """Open a file dialog, copy the chosen cookies.txt into the tool folder."""
    import shutil
    src = _open_cookie_file_dialog()
    if not src or not os.path.isfile(src):
        return jsonify({'success': False, 'error': 'Không chọn file nào'})

    # Validate it looks like a Netscape cookie file before overwriting
    try:
        with open(src, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        has_cookie = any(
            ln.strip() and not ln.startswith('#') for ln in content.splitlines()
        )
        if not has_cookie:
            return jsonify({'success': False, 'error': 'File không chứa cookie hợp lệ'})
        if 'youtube' not in content.lower():
            return jsonify({
                'success': False,
                'error': 'File không có cookie YouTube. Hãy xuất cookie khi đang ở trang youtube.com.'
            })
    except Exception as e:
        return jsonify({'success': False, 'error': f'Không đọc được file: {e}'})

    try:
        if os.path.abspath(src) != os.path.abspath(engine.COOKIES_FILE):
            shutil.copyfile(src, engine.COOKIES_FILE)
    except Exception as e:
        return jsonify({'success': False, 'error': f'Không sao chép được: {e}'})

    # Count youtube cookies
    count = sum(
        1 for ln in content.splitlines()
        if ln.strip() and not ln.startswith('#') and 'youtube' in ln.lower()
    )
    return jsonify({'success': True, 'count': count})


# ── Danh sách chờ ─────────────────────────────────────────────────────────
# Link nhập sẵn, mỗi link tải riêng khi bấm "Tải" (tải cả loạt một lúc dễ bị YouTube chặn).
def _history_check(url):
    return history.check(url, engine.extract_video_id)


@app.route('/api/queue', methods=['GET'])
def queue_list():
    return jsonify({'items': queue_store.load()})


@app.route('/api/queue/import', methods=['POST'])
def queue_import():
    """Nhập danh sách link (mỗi dòng một link). Không gọi YouTube ở bước này."""
    data = request.json or {}
    urls = queue_store.extract_urls(data.get('text', ''))
    if not urls:
        return jsonify({'success': False, 'error': 'Không thấy link nào trong nội dung dán vào.'})
    stats = queue_store.add(urls, engine.extract_video_id, _history_check)
    stats.update(success=True, items=queue_store.load())
    return jsonify(stats)


@app.route('/api/queue/<item_id>/download', methods=['POST'])
def queue_download(item_id):
    """Tải một mục trong danh sách chờ; xong thì tự đánh dấu 'done'."""
    item = queue_store.get(item_id)
    if not item:
        return jsonify({'success': False, 'error': 'Mục này không còn trong danh sách.'})
    if item['status'] == 'downloading':
        return jsonify({'success': False, 'error': 'Mục này đang tải.'})

    data = request.json or {}
    download_dir = data.get('download_dir') or DEFAULT_DOWNLOAD_DIR
    max_resolution = data.get('max_resolution', '1080p')
    os.makedirs(download_dir, exist_ok=True)

    task_id = str(uuid.uuid4())[:8]
    with tasks_lock:
        download_tasks[task_id] = {
            'url': item['url'], 'title': item.get('title') or '', 'status': 'queued',
            'progress': 0, 'speed': '', 'error': None, 'filename': None, 'queue_id': item_id,
        }
    item = queue_store.update(item_id, status='downloading', error=None, task_id=task_id)
    socketio.emit('queue_item', item)
    executor.submit(_download_worker, task_id, item['url'], download_dir, max_resolution,
                    item.get('title') or '', item_id)
    return jsonify({'success': True, 'task_id': task_id, 'item': item})


@app.route('/api/queue/<item_id>/mark', methods=['POST'])
def queue_mark(item_id):
    """Người dùng tự đánh dấu: {"status": "done"} hoặc {"status": "pending"}."""
    status = (request.json or {}).get('status', 'done')
    item = queue_store.mark(item_id, 'done' if status == 'done' else 'pending')
    if not item:
        return jsonify({'success': False, 'error': 'Mục này không còn trong danh sách.'})
    return jsonify({'success': True, 'item': item})


@app.route('/api/queue/<item_id>', methods=['DELETE'])
def queue_remove(item_id):
    return jsonify({'success': queue_store.remove(item_id)})


@app.route('/api/queue/clear-done', methods=['POST'])
def queue_clear_done():
    return jsonify({'success': True, 'removed': queue_store.remove_done()})


# ── Entry point ──────────────────────────────────────────────────────────
def _start_desktop():
    """Launch as native desktop window using pywebview."""
    import webview

    window = webview.create_window(
        WINDOW_TITLE,
        app,
        width=WINDOW_WIDTH,
        height=WINDOW_HEIGHT,
        min_size=WINDOW_MIN_SIZE,
        text_select=True,
    )
    webview.start(private_mode=False)


def _start_browser():
    """Fallback: launch in browser if pywebview is not available."""
    print("\n" + "=" * 50)
    print(f"  YouTube Downloader")
    print(f"  Open: http://127.0.0.1:5000")
    print("=" * 50 + "\n")
    socketio.run(app, host='127.0.0.1', port=5000, debug=False, allow_unsafe_werkzeug=True)


if __name__ == '__main__':
    try:
        import webview  # noqa: F401
        _start_desktop()
    except ImportError:
        print("[!] pywebview not found, falling back to browser mode.")
        print("    Install it with: pip install pywebview")
        _start_browser()
