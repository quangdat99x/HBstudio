@echo off
title Dang nhap Claude Code cho Ho Bao Studio
set "CLAUDE_EXE=%~dp0..\claude-cli\node_modules\@anthropic-ai\claude-code\bin\claude.exe"
if not exist "%CLAUDE_EXE%" (
    echo Khong thay file: %CLAUDE_EXE%
    echo Hay bao lai cho Claude trong app de cai lai CLI.
    pause
    exit /b 1
)
echo ============================================================
echo  Claude Code se mo ngay ben duoi. Khi thay dau nhac cua Claude:
echo    1. Go:  /login   roi Enter
echo    2. Trinh duyet mo ra, dang nhap tai khoan Claude dang dung
echo    3. Quay lai cua so nay, go:  /exit  de thoat
echo  Sau do mo Ho Bao Studio, trang Cai dat se bao "co token".
echo ============================================================
echo.
cd /d "%USERPROFILE%"
"%CLAUDE_EXE%"
echo.
echo Da thoat Claude. Bam phim bat ky de dong cua so.
pause >nul
