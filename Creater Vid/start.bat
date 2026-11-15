@echo off
rem Creater Vid: start the app on http://127.0.0.1:5010 and open it in the browser.
cd /d "%~dp0"
start "" http://127.0.0.1:5010
".venv\Scripts\python.exe" app.py
