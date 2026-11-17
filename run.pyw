"""
🎬 Tool Manager — Launcher for all video tools.
Double-click to open. Manages YouTube Downloader, Video Cutter, Podcast Zoom.
"""
import os
import sys
import time
import subprocess
import threading
import io
import json
import socket
import signal
import urllib.request
import urllib.error

# Ensure we run from the script's directory
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE_DIR)
sys.path.insert(0, BASE_DIR)

# Fix encoding for .pyw (no console)
if not sys.stdout or not hasattr(sys.stdout, 'write'):
    sys.stdout = open(os.devnull, 'w', encoding='utf-8')
    sys.stderr = open(os.devnull, 'w', encoding='utf-8')
elif hasattr(sys.stdout, 'buffer'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

HELPER_SCRIPT = os.path.join(BASE_DIR, '_tool_server.py')

# Windows groups taskbar buttons by AppUserModelID. Without one of our own,
# every window counts as plain pythonw.exe and opens beside the pinned
# shortcut as a separate button with the Python logo. The Start-menu shortcut
# carries the same ID and the same icon.
APP_ID = 'VideoTools.ToolManager'
ICON_PATH = os.path.join(BASE_DIR, 'toolmanager.ico')
LOG_DIR = os.path.join(BASE_DIR, 'logs')


def _wait_for_port(host, port, timeout=20):
    """Block until a TCP port accepts connections, or timeout expires."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=1):
                return True
        except OSError:
            time.sleep(0.2)
    return False


def _port_open(port, host='127.0.0.1'):
    """True when something already answers on the tool's port (e.g. started by Hổ Báo Studio)."""
    try:
        with socket.create_connection((host, port), timeout=0.3):
            return True
    except OSError:
        return False


def _pid_on_port(port):
    """PID of the process LISTENING on a local TCP port, via netstat (no extra packages)."""
    try:
        flags = subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
        out = subprocess.run(['netstat', '-ano', '-p', 'TCP'], capture_output=True, text=True,
                             timeout=10, creationflags=flags).stdout
        for line in out.splitlines():
            parts = line.split()
            if len(parts) >= 5 and parts[0] == 'TCP' and parts[1].endswith(f':{port}') and parts[3] == 'LISTENING':
                return int(parts[4])
    except Exception:
        pass
    return None


def _http_json(url, payload=None, timeout=10):
    """Tiny JSON helper. POST when payload given, GET otherwise."""
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode('utf-8')
        headers['Content-Type'] = 'application/json'
    req = urllib.request.Request(url, data=data, headers=headers,
                                 method='POST' if payload is not None else 'GET')
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode('utf-8'))


def _open_folder_dialog(initial_dir=''):
    """Open a native folder picker. Returns chosen path or ''."""
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

TOOLS = {
    'downloader': {
        'name': 'YouTube Downloader',
        'icon': '📥',
        'desc': 'Download video từ YouTube với nhiều định dạng và chất lượng',
        'dir': os.path.join(BASE_DIR, 'Youtube Dowloader'),
        'port': 5001,
        'type': 'socketio',
    },
    'cutter': {
        'name': 'Video Cutter',
        'icon': '✂️',
        'desc': 'Cắt video theo timestamp, hỗ trợ Whisper transcript',
        'dir': os.path.join(BASE_DIR, 'video-cutter-portable'),
        'port': 5002,
        'type': 'flask',
    },
    'zoomer': {
        'name': 'Podcast Zoom',
        'icon': '🔍',
        'desc': 'Auto-zoom vào người đang nói trong video podcast',
        'dir': os.path.join(BASE_DIR, 'podcast-zoom-tool'),
        'port': 5003,
        'type': 'flask',
    },
    'studio': {
        'name': 'Hổ Báo Studio',
        'icon': '🎬',
        'desc': 'Pipeline tự động: video → transcript → chọn nội dung → cắt → zoom → kho highlight',
        'dir': os.path.join(BASE_DIR, 'DataBase'),
        'port': 5004,
        'type': 'flask',
    },
    'creater': {
        'name': 'Creater Vid',
        'icon': '🎥',
        'desc': 'Làm phim tài liệu 6 bước: kịch bản → nhân vật → phân cảnh → hình ảnh → footage → render',
        'dir': os.path.join(BASE_DIR, 'Creater Vid'),
        'port': 5010,
        'type': 'flask',
    },
    'watcher': {
        'name': 'Video Watcher',
        'icon': '👁️',
        'desc': 'Cho Claude "xem" video: cắt cảnh, contact sheet, transcript, nhịp dựng → mổ xẻ công thức để bắt chước',
        'dir': os.path.join(BASE_DIR, 'video-watcher'),
        'port': 5011,
        'type': 'flask',
    },
    'dub': {
        'name': 'Lồng Tiếng',
        'icon': '🎙️',
        'desc': 'Thuyết minh video: Whisper → dịch → giọng ElevenLabs → khớp thời gian, hạ tiếng gốc',
        'dir': os.path.join(BASE_DIR, 'voice-dub'),
        'port': 5013,
        'type': 'flask',
    },
}


class Api:
    """Python API exposed to webview JS via window.pywebview.api"""

    def __init__(self):
        self.processes = {}
        self.windows = {}   # tool_id -> webview window, so we can close it too
        self.logs = {}      # tool_id -> open log file handle
        self.quick_download_dir = None

    def start_tool(self, tool_id):
        """Start a tool's Flask server as a subprocess."""
        # Already running?
        if tool_id in self.processes and self.processes[tool_id].poll() is None:
            return {'success': True, 'already': True, 'port': TOOLS[tool_id]['port']}

        tool = TOOLS.get(tool_id)
        if not tool:
            return {'success': False, 'error': 'Tool not found'}

        if not os.path.isdir(tool['dir']):
            return {'success': False, 'error': f"Folder not found: {tool['dir']}"}

        # Started elsewhere (Hổ Báo Studio launches Cutter/Zoom/Downloader on demand): reuse it.
        if _port_open(tool['port']):
            return {'success': True, 'already': True, 'external': True, 'port': tool['port']}

        try:
            creationflags = 0
            if hasattr(subprocess, 'CREATE_NO_WINDOW'):
                creationflags = subprocess.CREATE_NO_WINDOW

            # A tool that ships its own .venv (podcast-zoom-tool needs Python 3.12
            # for mediapipe, Hổ Báo Studio pins 3.12 too) runs on that interpreter.
            python_exe = sys.executable
            venv_python = os.path.join(tool['dir'], '.venv', 'Scripts', 'python.exe')
            if os.path.exists(venv_python):
                python_exe = venv_python

            # Keep the server's output. A tool that dies silently is
            # impossible to diagnose and leaves its window showing nothing but
            # "Failed to fetch" on every click.
            os.makedirs(LOG_DIR, exist_ok=True)
            log_path = os.path.join(LOG_DIR, f'{tool_id}.log')
            log_file = open(log_path, 'a', encoding='utf-8', errors='replace')
            log_file.write(
                f"\n===== {time.strftime('%Y-%m-%d %H:%M:%S')} start {tool_id} =====\n"
            )
            log_file.flush()

            proc = subprocess.Popen(
                [python_exe, HELPER_SCRIPT, tool['dir'], str(tool['port']), tool['type']],
                cwd=tool['dir'],
                creationflags=creationflags,
                stdout=log_file,
                stderr=subprocess.STDOUT,
            )
            self.processes[tool_id] = proc
            self.logs[tool_id] = log_file
        except Exception as e:
            return {'success': False, 'error': str(e)}

        # Only report success once the port actually answers, otherwise the
        # window opens against a server that never came up.
        if not _wait_for_port('127.0.0.1', tool['port'], timeout=30):
            if proc.poll() is not None:
                err = (f'Server tắt ngay khi khởi động (mã {proc.returncode}). '
                       f'Xem log: {log_path}')
            else:
                err = f'Server không phản hồi sau 30 giây. Xem log: {log_path}'
            return {'success': False, 'error': err, 'log': log_path}

        # The port answers but our process is gone: someone else owns it, and
        # "Stop" would then leave a server we cannot control still running.
        if proc.poll() is not None:
            port = tool['port']
            return {
                'success': False,
                'error': (f'Cổng {port} đang bị một tiến trình khác chiếm. '
                          f'Đóng tiến trình đó rồi thử lại. Xem log: {log_path}'),
                'log': log_path,
            }

        return {'success': True, 'port': tool['port'], 'pid': proc.pid}

    def _close_window(self, tool_id):
        """Destroy a tool's window if it is still open."""
        win = self.windows.pop(tool_id, None)
        if not win:
            return
        try:
            win.destroy()
        except Exception:
            pass

    def stop_tool(self, tool_id):
        """Stop a tool's subprocess and close the window that talks to it."""
        # The window must go with the server: a window left open on a stopped
        # server can only answer "Failed to fetch".
        self._close_window(tool_id)

        log = self.logs.pop(tool_id, None)
        if log:
            try:
                log.close()
            except Exception:
                pass

        proc = self.processes.get(tool_id)
        if not proc or proc.poll() is not None:
            # Not ours (started by Hổ Báo Studio) but still serving: stop it by the PID on its port.
            port = TOOLS[tool_id]['port'] if tool_id in TOOLS else None
            pid = _pid_on_port(port) if port and _port_open(port) else None
            if pid:
                flags = subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
                subprocess.run(['taskkill', '/PID', str(pid), '/T', '/F'], capture_output=True, creationflags=flags)
            self.processes.pop(tool_id, None)
            return {'success': True}
        try:
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=3)
        except Exception:
            pass
        self.processes.pop(tool_id, None)
        return {'success': True}

    def open_tool(self, tool_id):
        """Open tool in a webview window, starting its server if needed."""
        import webview
        tool = TOOLS.get(tool_id)
        if not tool:
            return {'success': False, 'error': 'Tool not found'}

        # A window with no live server behind it can only show "Failed to
        # fetch", so make sure the server answers before opening one.
        proc = self.processes.get(tool_id)
        if not proc or proc.poll() is not None:
            start_res = self.start_tool(tool_id)
            if not start_res.get('success'):
                return start_res

        existing = self.windows.get(tool_id)
        if existing:
            try:
                existing.show()
                return {'success': True, 'already': True}
            except Exception:
                self.windows.pop(tool_id, None)

        url = f"http://127.0.0.1:{tool['port']}"
        try:
            win = webview.create_window(
                tool['name'],
                url,
                width=1100,
                height=800,
                min_size=(800, 600),
                text_select=True,   # pywebview disables text selection by default
            )
            self.windows[tool_id] = win
            win.events.closed += lambda *a: self.windows.pop(tool_id, None)
            return {'success': True}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def get_status(self):
        """Get running status of all tools."""
        result = {}
        for tid in TOOLS:
            own = tid in self.processes and self.processes[tid].poll() is None
            running = own or _port_open(TOOLS[tid]['port'])
            result[tid] = {
                'running': running,
                'external': running and not own,
                'port': TOOLS[tid]['port'],
                'name': TOOLS[tid]['name'],
            }
        return result

    def choose_download_folder(self):
        """Open a native folder picker for the quick-download location."""
        path = _open_folder_dialog(self.quick_download_dir or '')
        if not path:
            return {'success': False, 'error': 'Không chọn thư mục nào'}
        self.quick_download_dir = path
        return {'success': True, 'path': path}

    def get_default_download_dir(self):
        """Read the downloader's default folder without starting its server."""
        try:
            import importlib.util
            cfg_path = os.path.join(TOOLS['downloader']['dir'], 'config.py')
            spec = importlib.util.spec_from_file_location('downloader_config', cfg_path)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            return {'default_dir': mod.DEFAULT_DOWNLOAD_DIR}
        except Exception:
            return {'default_dir': os.path.join(os.path.expanduser('~'), 'Downloads', 'YouTube')}

    def quick_download(self, urls_text, resolution='1080p'):
        """Auto-start downloader (if needed) and submit URLs for download."""
        urls = [u.strip() for u in (urls_text or '').splitlines() if u.strip()]
        if not urls:
            return {'success': False, 'error': 'Chưa nhập link nào'}

        port = TOOLS['downloader']['port']
        start_res = self.start_tool('downloader')
        if not start_res.get('success'):
            return start_res

        if not _wait_for_port('127.0.0.1', port, timeout=25):
            return {'success': False, 'error': 'Downloader chưa sẵn sàng (timeout)'}

        try:
            payload = {
                'urls': [{'url': u, 'title': ''} for u in urls],
                'max_resolution': resolution,
            }
            if self.quick_download_dir:
                payload['download_dir'] = self.quick_download_dir
            result = _http_json(f'http://127.0.0.1:{port}/api/download',
                                payload=payload, timeout=15)
            return {
                'success': True,
                'task_ids': result.get('task_ids', []),
                'download_dir': result.get('download_dir', ''),
                'submitted': len(urls),
            }
        except Exception as e:
            return {'success': False, 'error': f'Không thể gửi yêu cầu: {e}'}

    def get_quick_tasks(self):
        """Poll the downloader for current task statuses. Empty if not running."""
        proc = self.processes.get('downloader')
        if not proc or proc.poll() is not None:
            return {'tasks': {}}
        port = TOOLS['downloader']['port']
        try:
            return _http_json(f'http://127.0.0.1:{port}/api/tasks', timeout=3)
        except Exception:
            return {'tasks': {}}

    # ------------------------------------------------------------ đồng bộ code giữa các máy (_sync.py)
    def sync_status(self, fetch=True):
        import _sync
        try:
            return _sync.status(fetch=bool(fetch))
        except Exception as e:
            return {'ok': False, 'error': str(e)}

    def sync_startup(self):
        """Lúc mở Tool Manager: máy này sạch mà máy kia có bản mới thì kéo về luôn."""
        import _sync
        try:
            res = _sync.startup_pull()
        except Exception as e:
            return {'ok': False, 'error': str(e)}
        res['restart_manager'] = self._manager_changed(res.get('pulled') or [])
        return res

    def sync_now(self):
        """Commit → kéo bản mới → đẩy lên, rồi khởi động lại các tool đang chạy có code vừa đổi."""
        import _sync
        try:
            res = _sync.sync()
        except Exception as e:
            return {'ok': False, 'error': str(e)}
        pulled = res.get('pulled') or []
        if res.get('ok') and pulled:
            dirs = _sync.tool_dirs_changed(pulled)
            restarted = []
            for tid, tool in TOOLS.items():
                if os.path.basename(tool['dir']) not in dirs:
                    continue
                if not (_port_open(tool['port']) or (tid in self.processes and self.processes[tid].poll() is None)):
                    continue
                self.stop_tool(tid)
                time.sleep(1)
                if self.start_tool(tid).get('success'):
                    restarted.append(tool['name'])
            res['restarted'] = restarted
            res['restart_manager'] = self._manager_changed(pulled)
        res['status'] = self.sync_status(fetch=False)
        return res

    # ------------------------------------------------------------ thư mục data của máy này (_data_root.py)
    def data_root_info(self):
        import _data_root
        return _data_root.describe()

    def choose_data_root(self):
        """Chọn thư mục data của máy này. Bên trong luôn theo một format (YouTube\\..., VideoLab\\creater-projects),
        Studio và Creater Vid đọc lại ngay, không cần khởi động lại."""
        import _data_root
        cur = _data_root.data_root()
        path = _open_folder_dialog(str(cur) if cur else '')
        if not path:
            return {'success': False, 'error': 'Không chọn thư mục nào'}
        p = os.path.normpath(path)
        note = ''
        # chọn nhầm thư mục media của Studio (...\YouTube có Full/Clips) hay thư mục dự án: lấy thư mục data chứa nó
        if os.path.basename(p).lower() == 'youtube' and os.path.isdir(os.path.join(p, 'Clips')):
            p, note = os.path.dirname(p), 'đã lấy thư mục cha của YouTube'
        elif os.path.basename(p).lower() == 'creater-projects':
            p, note = os.path.dirname(os.path.dirname(p)), 'đã lấy thư mục chứa VideoLab'
        try:
            root = _data_root.set_data_root(p)
        except Exception as e:
            return {'success': False, 'error': str(e)}
        return {'success': True, 'note': note, **_data_root.describe(), 'data_root': str(root)}

    @staticmethod
    def _manager_changed(files):
        return any(f in ('run.pyw', '_sync.py', '_sync_main.json', '_tool_server.py', '_data_root.py') for f in files)

    def cleanup(self):
        """Stop all tools on exit."""
        for tid in list(self.processes.keys()):
            self.stop_tool(tid)


DASHBOARD_HTML = r"""<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="UTF-8">
<title>Tool Manager</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

  * { margin:0; padding:0; box-sizing:border-box; }

  body {
    font-family: 'Inter', -apple-system, sans-serif;
    background: #0a0a0f;
    color: #e0e0e0;
    height: 100vh;
    overflow: hidden;
    user-select: none;
    -webkit-user-select: none;
  }

  .app {
    display: flex;
    flex-direction: column;
    height: 100vh;
    padding: 24px 32px;
    gap: 24px;
  }

  /* Header */
  .header {
    text-align: center;
    flex-shrink: 0;
  }
  .header h1 {
    font-size: 28px;
    font-weight: 700;
    background: linear-gradient(135deg, #60a5fa, #a78bfa, #f472b6);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
  }
  .header p {
    color: #666;
    font-size: 13px;
    margin-top: 4px;
  }
  .sync-bar { display: flex; justify-content: center; align-items: center; gap: 10px; margin-top: 8px; }
  .sync-btn {
    display: inline-flex; align-items: center; gap: 6px; padding: 5px 12px; border-radius: 8px;
    border: 1px solid #2a2a40; background: #16162a; color: #c7d2fe; font: 500 12px 'Inter', sans-serif; cursor: pointer;
  }
  .sync-btn:hover { background: #20203a; color: #fff; }
  .sync-btn:disabled { opacity: .6; cursor: wait; }
  .sync-btn .spinner { display: none; width: 11px; height: 11px; border: 2px solid #555; border-top-color: #a5b4fc;
                       border-radius: 50%; animation: spin .8s linear infinite; }
  .sync-btn.loading .spinner { display: inline-block; }
  .sync-info { font-size: 12px; color: #777; max-width: 760px; text-align: left; user-select: text; -webkit-user-select: text; }
  .sync-info.warn { color: #fbbf24; }
  .sync-info.err { color: #f87171; }
  .sync-info.ok { color: #4ade80; }

  /* Cards Grid */
  .cards {
    display: grid;
    grid-template-columns: repeat(6, 1fr);
    gap: 14px;
    flex: 1;
    min-height: 0;
  }
  /* Cửa sổ mặc định (1160px) không đủ chỗ cho 6 thẻ một hàng → 3 × 2. */
  @media (max-width: 1400px) {
    .cards { grid-template-columns: repeat(3, 1fr); }
    .cards .card {
      display: grid; grid-template-columns: 56px 1fr; align-items: center; justify-items: start;
      grid-template-areas: "icon name" "icon status" "desc desc" "act act";
      padding: 14px 18px; gap: 4px 12px;
    }
    .cards .card-icon { grid-area: icon; width: 56px; height: 56px; font-size: 30px; }
    .cards .card-name { grid-area: name; text-align: left; }
    .cards .status { grid-area: status; }
    .cards .card-desc { grid-area: desc; text-align: left; overflow: hidden; display: -webkit-box;
                        -webkit-line-clamp: 2; -webkit-box-orient: vertical; margin-top: 4px; }
    .cards .card-actions { grid-area: act; width: 100%; margin-top: 6px; }
  }

  .card {
    background: #12121a;
    border: 1px solid #1e1e2e;
    border-radius: 16px;
    padding: 28px 24px;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 16px;
    transition: all 0.3s ease;
    position: relative;
    overflow: hidden;
  }
  .card::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 3px;
    background: var(--accent);
    opacity: 0;
    transition: opacity 0.3s;
  }
  .card:hover {
    border-color: #2a2a3e;
    transform: translateY(-2px);
    box-shadow: 0 8px 32px rgba(0,0,0,0.4);
  }
  .card:hover::before { opacity: 1; }

  .card.running {
    border-color: var(--accent);
    box-shadow: 0 0 20px color-mix(in srgb, var(--accent) 15%, transparent);
  }
  .card.running::before { opacity: 1; }

  .card[data-tool="downloader"] { --accent: #f87171; }
  .card[data-tool="cutter"]     { --accent: #fbbf24; }
  .card[data-tool="zoomer"]     { --accent: #34d399; }
  .card[data-tool="studio"]     { --accent: #a78bfa; }
  .card[data-tool="creater"]    { --accent: #f472b6; }
  .card[data-tool="watcher"]    { --accent: #38bdf8; }
  .card[data-tool="dub"]        { --accent: #f472b6; }

  .card-icon {
    font-size: 40px;
    width: 72px;
    height: 72px;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 16px;
    background: #1a1a28;
    border: 1px solid #252536;
  }

  .card-name {
    font-size: 17px;
    font-weight: 600;
    color: #f0f0f0;
  }
  .card-desc {
    font-size: 12px;
    color: #555;
    text-align: center;
    line-height: 1.5;
    flex: 1;
  }

  /* Status indicator */
  .status {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 12px;
    font-weight: 500;
    padding: 4px 12px;
    border-radius: 20px;
    background: #1a1a28;
  }
  .status-dot {
    width: 8px; height: 8px;
    border-radius: 50%;
    background: #444;
    transition: background 0.3s;
  }
  .card.running .status-dot {
    background: #34d399;
    box-shadow: 0 0 8px #34d39988;
    animation: pulse 2s infinite;
  }
  @keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.5; }
  }

  .status-text { color: #888; }
  .card.running .status-text { color: #34d399; }

  /* Buttons */
  .card-actions {
    display: flex;
    gap: 8px;
    width: 100%;
  }
  .btn {
    flex: 1;
    padding: 10px 0;
    border: none;
    border-radius: 10px;
    font-family: inherit;
    font-size: 13px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
  }

  .btn-start {
    background: var(--accent);
    color: #000;
  }
  .btn-start:hover { filter: brightness(1.15); transform: scale(1.02); }
  .btn-start:active { transform: scale(0.98); }
  .btn-start.loading {
    opacity: 0.7;
    pointer-events: none;
  }

  .btn-open {
    background: #1e1e30;
    color: #ccc;
    border: 1px solid #2a2a40;
  }
  .btn-open:hover { background: #282840; color: #fff; }

  .btn-stop {
    background: #2a1a1a;
    color: #f87171;
    border: 1px solid #3a2020;
  }
  .btn-stop:hover { background: #3a2020; }

  .btn:disabled {
    opacity: 0.3;
    pointer-events: none;
  }

  /* Spinner */
  .spinner {
    width: 14px; height: 14px;
    border: 2px solid transparent;
    border-top-color: currentColor;
    border-radius: 50%;
    animation: spin 0.6s linear infinite;
    display: none;
  }
  .btn-start.loading .spinner { display: block; }
  .btn-start.loading .btn-label { display: none; }

  @keyframes spin { to { transform: rotate(360deg); } }

  /* Footer */
  .footer {
    text-align: center;
    font-size: 11px;
    color: #333;
    flex-shrink: 0;
  }

  /* Quick Download */
  .quick {
    background: #12121a;
    border: 1px solid #1e1e2e;
    border-radius: 16px;
    padding: 16px 20px;
    flex-shrink: 0;
    display: flex;
    flex-direction: column;
    gap: 10px;
    position: relative;
    overflow: hidden;
  }
  .quick::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 2px;
    background: #f87171;
    opacity: 0.7;
  }
  .quick-head {
    display: flex;
    align-items: center;
    gap: 10px;
    font-size: 13px;
    font-weight: 600;
    color: #f0f0f0;
  }
  .quick-head .badge {
    margin-left: auto;
    display: flex;
    align-items: center;
    gap: 5px;
    font-family: inherit;
    font-size: 11px;
    font-weight: 500;
    color: #888;
    background: none;
    border: 1px solid #2a2a3e;
    border-radius: 8px;
    padding: 4px 10px;
    cursor: pointer;
    transition: all 0.2s;
  }
  .quick-head .badge:hover {
    background: #1a1a28;
    border-color: #3a3a50;
    color: #ccc;
  }
  .quick-row {
    display: flex;
    gap: 8px;
    align-items: stretch;
  }
  .quick-url {
    flex: 1;
    min-height: 38px;
    max-height: 90px;
    padding: 9px 12px;
    background: #0c0c14;
    border: 1px solid #2a2a3e;
    border-radius: 10px;
    color: #e0e0e0;
    font-family: inherit;
    font-size: 13px;
    resize: vertical;
    outline: none;
    transition: border-color 0.2s;
  }
  .quick-url:focus { border-color: #f87171; }
  .quick-url::placeholder { color: #444; }
  .quick-url, .quick-select, .quick-task-title {
    user-select: text;
    -webkit-user-select: text;
  }

  .quick-select {
    background: #0c0c14;
    border: 1px solid #2a2a3e;
    border-radius: 10px;
    color: #e0e0e0;
    padding: 0 10px;
    font-family: inherit;
    font-size: 13px;
    outline: none;
    cursor: pointer;
  }
  .quick-btn {
    padding: 0 18px;
    background: #f87171;
    color: #000;
    border: none;
    border-radius: 10px;
    font-family: inherit;
    font-size: 13px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s;
    display: flex;
    align-items: center;
    gap: 6px;
    white-space: nowrap;
  }
  .quick-btn:hover { filter: brightness(1.15); }
  .quick-btn:disabled { opacity: 0.4; cursor: not-allowed; }
  .quick-btn .spinner { width: 14px; height: 14px;
    border: 2px solid transparent; border-top-color: currentColor;
    border-radius: 50%; animation: spin 0.6s linear infinite; display: none; }
  .quick-btn.loading .spinner { display: block; }

  .quick-tasks {
    display: flex;
    flex-direction: column;
    gap: 6px;
    max-height: 140px;
    overflow-y: auto;
  }
  .quick-tasks::-webkit-scrollbar { width: 6px; }
  .quick-tasks::-webkit-scrollbar-thumb { background: #2a2a3e; border-radius: 3px; }
  .quick-task {
    display: flex;
    align-items: center;
    gap: 10px;
    font-size: 12px;
    padding: 6px 10px;
    background: #0c0c14;
    border: 1px solid #1e1e2e;
    border-radius: 8px;
  }
  .quick-task-title {
    flex: 1;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    color: #ccc;
  }
  .quick-task-bar {
    width: 100px;
    height: 6px;
    background: #1a1a28;
    border-radius: 3px;
    overflow: hidden;
    flex-shrink: 0;
  }
  .quick-task-bar > div {
    height: 100%;
    background: #f87171;
    transition: width 0.3s;
  }
  .quick-task-pct {
    width: 38px;
    text-align: right;
    color: #888;
    font-variant-numeric: tabular-nums;
    flex-shrink: 0;
  }
  .quick-task.completed .quick-task-bar > div { background: #34d399; }
  .quick-task.completed .quick-task-pct { color: #34d399; }
  .quick-task.error .quick-task-bar > div { background: #ef4444; width: 100% !important; }
  .quick-task.error .quick-task-pct { color: #ef4444; }
</style>
</head>
<body>
<div class="app">

  <div class="header">
    <h1>🎬 Tool Manager</h1>
    <p>Quản lý YouTube Downloader · Video Cutter · Podcast Zoom · Hổ Báo Studio · Creater Vid · Video Watcher</p>
    <div class="sync-bar">
      <button class="sync-btn" id="sync-btn" onclick="syncNow()" title="Chỉ máy chính được đẩy code lên GitHub; máy khác chỉ kéo bản của máy chính về">
        <span class="spinner"></span><span class="label">🔄 Đồng bộ code</span></button>
      <span class="sync-info" id="sync-info">đang kiểm tra bản mới…</span>
    </div>
    <div class="sync-bar">
      <button class="sync-btn" id="data-btn" onclick="chooseDataRoot()" title="Thư mục chứa data của máy này (video, clip, cutlist, dự án). Bên trong luôn cùng một format trên mọi máy">
        <span class="spinner"></span><span class="label">📁 Thư mục data</span></button>
      <span class="sync-info" id="data-info">…</span>
    </div>
  </div>

  <div class="cards">
    <!-- Downloader -->
    <div class="card" data-tool="downloader" id="card-downloader">
      <div class="card-icon">📥</div>
      <div class="card-name">YouTube Downloader</div>
      <div class="card-desc">Download video từ YouTube với nhiều định dạng và chất lượng</div>
      <div class="status">
        <span class="status-dot"></span>
        <span class="status-text">Stopped</span>
      </div>
      <div class="card-actions">
        <button class="btn btn-start" onclick="startTool('downloader')">
          <span class="spinner"></span>
          <span class="btn-label">▶ Start</span>
        </button>
        <button class="btn btn-open" onclick="openTool('downloader')" disabled>Mở</button>
        <button class="btn btn-stop" onclick="stopTool('downloader')" disabled>■ Stop</button>
      </div>
    </div>

    <!-- Cutter -->
    <div class="card" data-tool="cutter" id="card-cutter">
      <div class="card-icon">✂️</div>
      <div class="card-name">Video Cutter</div>
      <div class="card-desc">Cắt video theo timestamp, hỗ trợ Whisper transcript tự động</div>
      <div class="status">
        <span class="status-dot"></span>
        <span class="status-text">Stopped</span>
      </div>
      <div class="card-actions">
        <button class="btn btn-start" onclick="startTool('cutter')">
          <span class="spinner"></span>
          <span class="btn-label">▶ Start</span>
        </button>
        <button class="btn btn-open" onclick="openTool('cutter')" disabled>Mở</button>
        <button class="btn btn-stop" onclick="stopTool('cutter')" disabled>■ Stop</button>
      </div>
    </div>

    <!-- Zoomer -->
    <div class="card" data-tool="zoomer" id="card-zoomer">
      <div class="card-icon">🔍</div>
      <div class="card-name">Podcast Zoom</div>
      <div class="card-desc">Auto-zoom vào người đang nói trong video podcast</div>
      <div class="status">
        <span class="status-dot"></span>
        <span class="status-text">Stopped</span>
      </div>
      <div class="card-actions">
        <button class="btn btn-start" onclick="startTool('zoomer')">
          <span class="spinner"></span>
          <span class="btn-label">▶ Start</span>
        </button>
        <button class="btn btn-open" onclick="openTool('zoomer')" disabled>Mở</button>
        <button class="btn btn-stop" onclick="stopTool('zoomer')" disabled>■ Stop</button>
      </div>
    </div>

    <!-- Studio -->
    <div class="card" data-tool="studio" id="card-studio">
      <div class="card-icon">🎬</div>
      <div class="card-name">Hổ Báo Studio</div>
      <div class="card-desc">Pipeline tự động: video → transcript → chọn nội dung → cắt → zoom → kho highlight</div>
      <div class="status">
        <span class="status-dot"></span>
        <span class="status-text">Stopped</span>
      </div>
      <div class="card-actions">
        <button class="btn btn-start" onclick="startTool('studio')">
          <span class="spinner"></span>
          <span class="btn-label">▶ Start</span>
        </button>
        <button class="btn btn-open" onclick="openTool('studio')" disabled>Mở</button>
        <button class="btn btn-stop" onclick="stopTool('studio')" disabled>■ Stop</button>
      </div>
    </div>

    <!-- Creater Vid -->
    <div class="card" data-tool="creater" id="card-creater">
      <div class="card-icon">🎥</div>
      <div class="card-name">Creater Vid</div>
      <div class="card-desc">Làm phim tài liệu 6 bước: kịch bản → nhân vật → phân cảnh → hình ảnh → footage → render</div>
      <div class="status">
        <span class="status-dot"></span>
        <span class="status-text">Stopped</span>
      </div>
      <div class="card-actions">
        <button class="btn btn-start" onclick="startTool('creater')">
          <span class="spinner"></span>
          <span class="btn-label">▶ Start</span>
        </button>
        <button class="btn btn-open" onclick="openTool('creater')" disabled>Mở</button>
        <button class="btn btn-stop" onclick="stopTool('creater')" disabled>■ Stop</button>
      </div>
    </div>

    <!-- Video Watcher -->
    <div class="card" data-tool="watcher" id="card-watcher">
      <div class="card-icon">👁️</div>
      <div class="card-name">Video Watcher</div>
      <div class="card-desc">Cho Claude "xem" video: cắt cảnh, contact sheet, transcript, nhịp dựng → mổ xẻ công thức để bắt chước</div>
      <div class="status">
        <span class="status-dot"></span>
        <span class="status-text">Stopped</span>
      </div>
      <div class="card-actions">
        <button class="btn btn-start" onclick="startTool('watcher')">
          <span class="spinner"></span>
          <span class="btn-label">▶ Start</span>
        </button>
        <button class="btn btn-open" onclick="openTool('watcher')" disabled>Mở</button>
        <button class="btn btn-stop" onclick="stopTool('watcher')" disabled>■ Stop</button>
      </div>
    </div>

    <!-- Lồng Tiếng -->
    <div class="card" data-tool="dub" id="card-dub">
      <div class="card-icon">🎙️</div>
      <div class="card-name">Lồng Tiếng</div>
      <div class="card-desc">Thuyết minh video: Whisper → dịch → giọng ElevenLabs → khớp thời gian, hạ tiếng gốc</div>
      <div class="status">
        <span class="status-dot"></span>
        <span class="status-text">Stopped</span>
      </div>
      <div class="card-actions">
        <button class="btn btn-start" onclick="startTool('dub')">
          <span class="spinner"></span>
          <span class="btn-label">▶ Start</span>
        </button>
        <button class="btn btn-open" onclick="openTool('dub')" disabled>Mở</button>
        <button class="btn btn-stop" onclick="stopTool('dub')" disabled>■ Stop</button>
      </div>
    </div>
  </div>

  <!-- Quick Download -->
  <div class="quick">
    <div class="quick-head">
      <span>📥 Tải nhanh từ YouTube</span>
      <button class="badge" id="quick-folder-btn" onclick="chooseQuickFolder()" title="Chọn thư mục lưu">
        <span>📁</span><span id="quick-folder">~/Downloads/YouTube</span>
      </button>
    </div>
    <div class="quick-row">
      <textarea class="quick-url" id="quick-url" rows="1"
        placeholder="Dán link YouTube vào đây (mỗi link một dòng)..."></textarea>
      <select class="quick-select" id="quick-res">
        <option value="2160p">4K</option>
        <option value="1440p">2K</option>
        <option value="1080p" selected>1080p</option>
        <option value="720p">720p</option>
        <option value="480p">480p</option>
        <option value="360p">360p</option>
      </select>
      <button class="quick-btn" id="quick-btn" onclick="quickDownload()">
        <span class="spinner"></span>
        <span class="label">Tải</span>
      </button>
    </div>
    <div class="quick-tasks" id="quick-tasks"></div>
  </div>

  <div class="footer">Nhấn Start để khởi động tool · Nhấn Mở để mở giao diện · Nhấn Stop để tắt</div>
</div>

<script>
  // Track tasks we've submitted so we can render even if downloader is stopped later
  const knownTasks = {};

  // Wait for pywebview API to be ready
  window.addEventListener('pywebviewready', () => {
    // Poll status every 2 seconds
    setInterval(refreshStatus, 2000);
    setInterval(refreshQuickTasks, 1200);
    refreshStatus();
    initQuickFolder();
    syncStartup();
    setInterval(() => syncCheck(true), 15 * 60 * 1000);   // 15 phút xem máy kia có bản mới không
    showDataRoot();
  });

  // ---------------------------------------------------------------- thư mục data của máy này
  function setDataInfo(d, extra) {
    const el = document.getElementById('data-info');
    if (!d || !d.data_root) {
      el.textContent = '⚠ chưa chọn thư mục data cho máy này: Studio và Creater Vid đang dùng đường dẫn trong Cài đặt của chúng';
      el.className = 'sync-info warn'; return;
    }
    el.textContent = (d.exists ? '' : '⚠ không thấy thư mục · ') + d.data_root + '  →  YouTube\\Full · Cutlists · Clips · Tong-hop  ·  VideoLab\\creater-projects' + (extra ? ' · ' + extra : '');
    el.className = 'sync-info' + (d.exists ? '' : ' err');
  }
  async function showDataRoot() {
    try { setDataInfo(await window.pywebview.api.data_root_info()); } catch (e) {}
  }
  async function chooseDataRoot() {
    const btn = document.getElementById('data-btn');
    btn.disabled = true;
    try {
      const r = await window.pywebview.api.choose_data_root();
      if (r.success) setDataInfo(r, (r.note ? r.note + ' · ' : '') + 'đã lưu, Studio/Creater Vid dùng ngay');
      else if (r.error !== 'Không chọn thư mục nào') alert('Lỗi: ' + r.error);
    } catch (e) { alert('Lỗi: ' + e); }
    finally { btn.disabled = false; }
  }

  // ---------------------------------------------------------------- đồng bộ code giữa các máy
  function setSyncInfo(text, cls) {
    const el = document.getElementById('sync-info');
    el.textContent = text; el.className = 'sync-info' + (cls ? ' ' + cls : '');
  }
  function describeSync(st) {
    if (!st || !st.ok) return [(st && st.error) || 'không đọc được trạng thái Git', 'err'];
    setSyncRole(st);
    const bits = [];
    if (st.is_main === false) {   // máy phụ: chỉ kéo code máy chính, không đẩy
      if (st.behind) bits.push('⬇ máy chính có ' + st.behind + ' cập nhật mới');
      const n = (st.changes || []).length;
      if (n) bits.push('✏ ' + n + ' file bị sửa trên máy phụ (sẽ sao lưu rồi bỏ, không đẩy lên được)');
      else if (st.ahead) bits.push(st.ahead + ' commit trên máy phụ (sẽ sao lưu rồi bỏ)');
      if (st.fetch_error) bits.push('không kết nối được GitHub: ' + st.fetch_error);
      if (!bits.length) return ['✓ code đã khớp máy chính ' + st.main_machine + (st.last_remote ? ' (bản ' + st.last_remote + ')' : ''), 'ok'];
      return [bits.join(' · ') + ' → bấm Lấy code máy chính', st.fetch_error ? 'err' : 'warn'];
    }
    if (st.behind) bits.push('⬇ GitHub có ' + st.behind + ' cập nhật mới');
    if (st.changes && st.changes.length) bits.push('✏ ' + st.changes.length + ' file sửa trên máy này chưa đẩy');
    else if (st.ahead) bits.push('⬆ ' + st.ahead + ' commit chưa đẩy');
    if (st.fetch_error) bits.push('không kết nối được GitHub: ' + st.fetch_error);
    if (!bits.length) return ['✓ code đã khớp GitHub' + (st.last_remote ? ' (bản mới nhất ' + st.last_remote + ')' : ''), 'ok'];
    return [bits.join(' · ') + ' → bấm Đồng bộ', st.fetch_error ? 'err' : 'warn'];
  }
  let syncIsMain = true, syncLast = null;
  function setSyncRole(st) {
    syncLast = st;
    syncIsMain = st.is_main !== false;
    const btn = document.getElementById('sync-btn');
    btn.querySelector('.label').textContent = syncIsMain ? '🔄 Đồng bộ code (máy chính)' : '⬇ Lấy code máy chính';
    btn.title = syncIsMain
      ? 'Máy chính: commit code sửa trên máy này và đẩy lên GitHub. Máy khác chỉ kéo bản này về'
      : 'Máy phụ: lấy đúng code của máy chính ' + st.main_machine + ' từ GitHub. File sửa trên máy này được sao lưu vào _sync_backup rồi bỏ';
  }
  async function syncCheck(fetch) {
    try { const st = await window.pywebview.api.sync_status(fetch); const [t, c] = describeSync(st); setSyncInfo(t, c); }
    catch (e) { setSyncInfo('lỗi kiểm tra: ' + e, 'err'); }
  }
  async function syncStartup() {
    try {
      const r = await window.pywebview.api.sync_startup();
      if (r.pulled && r.pulled.length) {
        if (r.status && r.status.ok) setSyncRole(r.status);
        setSyncInfo('⬇ đã tự cập nhật ' + r.pulled.length + ' file từ máy chính' +
          (r.restart_manager ? ' · đóng và mở lại Tool Manager để dùng bản mới' : ''), 'ok');
      } else { const [t, c] = describeSync(r.status || r); setSyncInfo(t, c); }
    } catch (e) { setSyncInfo('lỗi kiểm tra: ' + e, 'err'); }
  }
  async function syncNow() {
    const btn = document.getElementById('sync-btn');
    if (!syncIsMain && syncLast && ((syncLast.changes || []).length || syncLast.ahead) &&
        !confirm('Máy này là máy phụ, không được đẩy code lên GitHub.\n\nCác file sửa trên máy này sẽ được sao lưu vào ' +
                 'C:\\Tool\\_sync_backup\\ rồi bỏ, code về đúng bản của máy chính ' + syncLast.main_machine + '.\n\nTiếp tục?')) return;
    btn.disabled = true; btn.classList.add('loading');
    setSyncInfo('đang đồng bộ (lần đầu có thể mở trình duyệt để đăng nhập GitHub)…');
    try {
      const r = await window.pywebview.api.sync_now();
      if (!r.ok) { setSyncInfo('✗ ' + r.error, 'err'); return; }
      if (r.status && r.status.ok) setSyncRole(r.status);
      let t = '✓ ' + r.message;
      if (r.restarted && r.restarted.length) t += ' · đã khởi động lại: ' + r.restarted.join(', ');
      const badReq = (r.requirements || []).filter(x => !x.ok);
      if (badReq.length) t += ' · cài package lỗi: ' + badReq.map(x => x.file).join(', ');
      if (r.restart_manager) t += ' · Tool Manager có bản mới: đóng và mở lại';
      setSyncInfo(t, badReq.length ? 'warn' : 'ok');
    } catch (e) { setSyncInfo('✗ ' + e, 'err'); }
    finally { btn.disabled = false; btn.classList.remove('loading'); }
  }

  async function initQuickFolder() {
    try {
      const res = await window.pywebview.api.get_default_download_dir();
      if (res.default_dir) document.getElementById('quick-folder').textContent = res.default_dir;
    } catch(e) {}
  }

  async function chooseQuickFolder() {
    const btn = document.getElementById('quick-folder-btn');
    const folderEl = document.getElementById('quick-folder');
    btn.disabled = true;
    try {
      const res = await window.pywebview.api.choose_download_folder();
      if (res.success) folderEl.textContent = res.path;
    } catch(e) {
      alert('Lỗi: ' + e);
    } finally {
      btn.disabled = false;
    }
  }

  async function refreshStatus() {
    try {
      const status = await window.pywebview.api.get_status();
      for (const [tid, info] of Object.entries(status)) {
        updateCardUI(tid, info.running);
      }
    } catch(e) {}
  }

  function updateCardUI(toolId, running) {
    const card = document.getElementById('card-' + toolId);
    if (!card) return;
    const btnStart = card.querySelector('.btn-start');
    const btnOpen  = card.querySelector('.btn-open');
    const btnStop  = card.querySelector('.btn-stop');
    const statusText = card.querySelector('.status-text');

    if (running) {
      card.classList.add('running');
      statusText.textContent = 'Running';
      btnStart.disabled = true;
      btnStart.classList.remove('loading');
      btnOpen.disabled = false;
      btnStop.disabled = false;
    } else {
      card.classList.remove('running');
      statusText.textContent = 'Stopped';
      btnStart.disabled = false;
      btnStart.classList.remove('loading');
      btnOpen.disabled = true;
      btnStop.disabled = true;
    }
  }

  async function startTool(toolId) {
    const card = document.getElementById('card-' + toolId);
    const btnStart = card.querySelector('.btn-start');
    btnStart.classList.add('loading');
    btnStart.disabled = true;

    try {
      const res = await window.pywebview.api.start_tool(toolId);
      if (res.success) {
        // start_tool only returns once the server answers on its port
        await refreshStatus();
        await openTool(toolId);
      } else {
        alert('Lỗi: ' + (res.error || 'Không thể khởi động'));
        btnStart.classList.remove('loading');
        btnStart.disabled = false;
      }
    } catch(e) {
      alert('Lỗi: ' + e);
      btnStart.classList.remove('loading');
      btnStart.disabled = false;
    }
  }

  async function openTool(toolId) {
    try {
      await window.pywebview.api.open_tool(toolId);
    } catch(e) {
      alert('Lỗi mở tool: ' + e);
    }
  }

  async function stopTool(toolId) {
    try {
      await window.pywebview.api.stop_tool(toolId);
      refreshStatus();
    } catch(e) {
      alert('Lỗi: ' + e);
    }
  }

  async function quickDownload() {
    const urlEl = document.getElementById('quick-url');
    const btn   = document.getElementById('quick-btn');
    const resEl = document.getElementById('quick-res');
    const folderEl = document.getElementById('quick-folder');
    const raw = urlEl.value.trim();
    if (!raw) {
      urlEl.focus();
      return;
    }
    btn.classList.add('loading');
    btn.disabled = true;

    try {
      const res = await window.pywebview.api.quick_download(raw, resEl.value);
      if (res.success) {
        if (res.download_dir) folderEl.textContent = res.download_dir;
        // Seed knownTasks so they show up before the first poll
        (res.task_ids || []).forEach(tid => {
          knownTasks[tid] = { status: 'queued', progress: 0, title: '', url: '' };
        });
        urlEl.value = '';
        renderQuickTasks();
        refreshQuickTasks();
      } else {
        alert('Lỗi: ' + (res.error || 'Không tải được'));
      }
    } catch(e) {
      alert('Lỗi: ' + e);
    } finally {
      btn.classList.remove('loading');
      btn.disabled = false;
    }
  }

  async function refreshQuickTasks() {
    try {
      const res = await window.pywebview.api.get_quick_tasks();
      const tasks = res.tasks || {};
      // Merge server snapshot into knownTasks (server is source of truth)
      for (const [tid, info] of Object.entries(tasks)) {
        knownTasks[tid] = info;
      }
      renderQuickTasks();
    } catch(e) {}
  }

  function renderQuickTasks() {
    const container = document.getElementById('quick-tasks');
    const entries = Object.entries(knownTasks);
    if (entries.length === 0) {
      container.innerHTML = '';
      return;
    }
    // Newest tasks first (UUID-ish ids aren't time-sorted, so just keep insertion order reversed)
    container.innerHTML = entries.map(([tid, t]) => {
      const pct = Math.max(0, Math.min(100, Number(t.progress || 0)));
      const status = t.status || 'queued';
      const title = t.filename || t.title || t.url || tid;
      const cls = status === 'completed' ? 'completed'
                : status === 'error' ? 'error' : '';
      const pctText = status === 'error' ? 'lỗi'
                    : status === 'completed' ? '✓'
                    : pct.toFixed(0) + '%';
      const tooltip = status === 'error' ? (t.error || 'Lỗi') : title;
      return `
        <div class="quick-task ${cls}" title="${escapeHtml(tooltip)}">
          <div class="quick-task-title">${escapeHtml(title)}</div>
          <div class="quick-task-bar"><div style="width:${pct}%"></div></div>
          <div class="quick-task-pct">${pctText}</div>
        </div>`;
    }).reverse().join('');
  }

  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, c => ({
      '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'
    }[c]));
  }
</script>
</body>
</html>
"""


def main():
    import ctypes
    import webview

    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)
    except (AttributeError, OSError):
        pass

    api = Api()

    window = webview.create_window(
        '🎬 Tool Manager',
        html=DASHBOARD_HTML,
        width=1160,
        height=720,
        min_size=(820, 620),
        resizable=True,
        text_select=False,
        js_api=api,
    )

    # Cleanup all subprocesses when the main window closes
    def on_closed():
        api.cleanup()

    window.events.closed += on_closed

    # Applies to every window, the tool windows opened later included.
    webview.start(icon=ICON_PATH)


if __name__ == '__main__':
    main()
