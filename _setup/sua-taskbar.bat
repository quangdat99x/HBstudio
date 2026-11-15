@echo off
cd /d "%~dp0"
title Sua nut Tool Manager tren taskbar

echo Taskbar se tat roi hien lai trong vai giay. Cua so dang mo khong bi anh huong.
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0sua-taskbar.ps1"
echo.
if errorlevel 1 (echo CO LOI - chup man hinh nay gui lai.) else (echo Xong. Bam nut tren taskbar de mo Tool Manager.)
pause
