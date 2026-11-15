"""
Helper script — launches a tool's Flask server on a given port.
Called by run.pyw launcher. Do NOT run this directly.
"""
import sys
import os
import subprocess

if len(sys.argv) < 4:
    print("Usage: _tool_server.py <tool_dir> <port> <type>")
    sys.exit(1)

tool_dir = sys.argv[1]
port = int(sys.argv[2])
tool_type = sys.argv[3]  # 'flask' or 'socketio'

# ── Bootstrap: If tool has .venv and we're not inside it, re-launch inside .venv ──
# (Some tools like podcast-zoom-tool have strict Python version requirements)
def _ensure_tool_venv():
    venv_python = os.path.join(tool_dir, '.venv', 'Scripts', 'python.exe')
    if not os.path.exists(venv_python):
        return  # No venv — proceed with current interpreter
    # Are we already running inside the venv?
    try:
        if os.path.samefile(sys.executable, venv_python):
            return
    except OSError:
        pass
    if os.path.normcase(os.path.abspath(sys.executable)) == \
       os.path.normcase(os.path.abspath(venv_python)):
        return
    # Re-launch this script with the tool's venv interpreter
    subprocess.Popen(
        [venv_python, os.path.abspath(__file__)] + sys.argv[1:],
        cwd=tool_dir
    )
    sys.exit(0)

_ensure_tool_venv()

# Set working directory and Python path so imports work
os.chdir(tool_dir)
sys.path.insert(0, tool_dir)

# Suppress encoding errors on Windows (pythonw has no console)
import io
if not sys.stdout or not hasattr(sys.stdout, 'write'):
    sys.stdout = open(os.devnull, 'w', encoding='utf-8')
    sys.stderr = open(os.devnull, 'w', encoding='utf-8')
elif hasattr(sys.stdout, 'buffer'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

if tool_type == 'socketio':
    from app import app, socketio
    socketio.run(app, host='127.0.0.1', port=port, debug=False, allow_unsafe_werkzeug=True)
else:
    from app import app
    app.run(host='127.0.0.1', port=port, debug=False, use_reloader=False)
