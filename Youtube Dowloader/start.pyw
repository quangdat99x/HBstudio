"""
YouTube Downloader — Silent Desktop Launcher
Run this file (.pyw) to start the app WITHOUT showing a CMD window.
Double-click this file on Windows to launch the desktop app.
"""
import sys
import os

# Ensure the script directory is on the path
script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, script_dir)
os.chdir(script_dir)

# Import and run
from app import app, socketio, _start_desktop, _start_browser

if __name__ == '__main__':
    try:
        import webview  # noqa: F401
        _start_desktop()
    except ImportError:
        _start_browser()
