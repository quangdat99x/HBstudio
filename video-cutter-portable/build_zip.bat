@echo off
cd /d "%~dp0"
title Dong goi Video Cutter

echo.
echo   ========================================
echo    Dong goi Video Cutter
echo   ========================================
echo.

REM Check ffmpeg bundled
if not exist "ffmpeg\ffmpeg.exe" (
    echo   [LOI] Chua co ffmpeg! Dat ffmpeg.exe vao thu muc ffmpeg\
    pause
    exit /b 1
)

echo   [OK] FFmpeg bundled: Co
echo.

set ZIPNAME=VideoCutter.zip
if exist "%ZIPNAME%" del "%ZIPNAME%"

echo   Dang tao file zip...
echo.

REM Dong goi gon nhe: chi code + ffmpeg + static (KHONG co python folder)
powershell -Command "& { Compress-Archive -Path 'app.py','ffmpeg','static','templates','run.bat','requirements.txt','README.txt' -DestinationPath '%ZIPNAME%' -Force; Write-Host '  Tao zip thanh cong!' }"

if exist "%ZIPNAME%" (
    powershell -Command "Write-Host ('  Ket qua: %ZIPNAME% - ' + [math]::Round((Get-Item '%ZIPNAME%').Length / 1MB, 1) + ' MB')"
    echo.
    echo   ========================================
    echo    HOAN THANH!
    echo    Gui file %ZIPNAME% cho nguoi dung.
    echo    Ho chi can:
    echo      1. Cai Python 3.10+ (python.org)
    echo      2. Giai nen va chay run.bat
    echo      Thu vien tu dong cai lan dau chay.
    echo   ========================================
) else (
    echo   [LOI] Tao zip that bai!
)

echo.
pause
