@echo off
cd /d "%~dp0"
title Cai Git for Windows (cho cong cu Bash cua Claude)
echo Dang cai Git for Windows... Windows se hoi quyen Admin: bam Yes.
"%~dp0Git-2.56.0.4-64-bit.exe" /SILENT /NORESTART /SP- /COMPONENTS="gitlfs,assoc,assoc_sh"
echo     ket qua: %errorlevel%
echo.
echo Them ffmpeg cua Video Cutter vao PATH cua user (frames.py, Creater Vid can)...
powershell -NoProfile -Command "$d='C:\Tool\video-cutter-portable\ffmpeg'; $p=[Environment]::GetEnvironmentVariable('Path','User'); if (($p -split ';') -notcontains $d) { [Environment]::SetEnvironmentVariable('Path', ($p.TrimEnd(';') + ';' + $d), 'User'); 'da them' } else { 'da co san' }"
echo.
echo Xong. Tat Tool Manager roi mo lai, sau do quay lai Claude va nhan "cai git xong".
pause
