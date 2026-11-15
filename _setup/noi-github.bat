@echo off
cd /d "%~dp0"
title Noi bo tool vao GitHub de dong bo giua cac may
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0noi-github.ps1" %*
echo.
pause
