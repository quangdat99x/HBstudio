@echo off
cd /d "%~dp0"

REM ------------------------------------------------------------------
REM  Tim Python tren he thong (uu tien python, roi py launcher)
REM ------------------------------------------------------------------
set PYTHON_CMD=

REM Try "python" first
python --version >nul 2>&1
if not errorlevel 1 (
    set PYTHON_CMD=python
    goto :found
)

REM Try "python3"
python3 --version >nul 2>&1
if not errorlevel 1 (
    set PYTHON_CMD=python3
    goto :found
)

REM Try "py" launcher
py --version >nul 2>&1
if not errorlevel 1 (
    set PYTHON_CMD=py
    goto :found
)

echo.
echo   [LOI] Khong tim thay Python tren he thong!
echo.
echo   Vui long cai Python 3.10+ tu: https://www.python.org/downloads/
echo   Nho tich "Add Python to PATH" khi cai.
echo.
pause
exit /b 1

:found

REM ------------------------------------------------------------------
REM  Kiem tra va cai thu vien can thiet (chi lan dau)
REM ------------------------------------------------------------------
%PYTHON_CMD% -c "import flask" >nul 2>&1
if errorlevel 1 (
    echo.
    echo   ============================
    echo    Video Cutter - Setup
    echo   ============================
    echo.
    echo   [!] Dang cai thu vien can thiet lan dau...
    echo.
    %PYTHON_CMD% -m pip install flask pywebview faster-whisper --quiet
    if errorlevel 1 (
        echo.
        echo   [CANH BAO] Mot so thu vien cai khong thanh cong.
        echo   Tool van co the chay voi tinh nang gioi han.
        echo.
    ) else (
        echo   [OK] Cai thu vien thanh cong!
        echo.
    )
)

REM ------------------------------------------------------------------
REM  Chay tool - an cua so CMD (chay nen)
REM ------------------------------------------------------------------

REM Try pythonw first (no console window at all)
where pythonw >nul 2>&1
if not errorlevel 1 (
    start "" /min pythonw app.py
    exit /b 0
)

REM Fallback: run python minimized
start "" /min %PYTHON_CMD% app.py
exit /b 0
