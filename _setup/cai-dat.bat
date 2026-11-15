@echo off
cd /d "%~dp0"
title Cai dat Python + Node cho Tool Manager

echo ============================================================
echo  1/3  Python 3.14  -^> C:\Python314  (Python chinh, co PATH)
echo ============================================================
"%~dp0python-3.14-amd64.exe" /passive InstallAllUsers=0 TargetDir=C:\Python314 PrependPath=1 Include_launcher=1 InstallLauncherAllUsers=0 AssociateFiles=1 Shortcuts=1 Include_test=0
echo     ket qua: %errorlevel%

echo ============================================================
echo  2/3  Python 3.12  -^> C:\Python312  (de tao cac .venv)
echo ============================================================
"%~dp0python-3.12.10-amd64.exe" /passive InstallAllUsers=0 TargetDir=C:\Python312 PrependPath=0 Include_launcher=0 AssociateFiles=0 Shortcuts=0 Include_test=0
echo     ket qua: %errorlevel%

echo ============================================================
echo  3/3  Node.js LTS  (Windows se hoi quyen Admin: bam Yes)
echo ============================================================
msiexec /i "%~dp0node-v24.22.1-x64.msi" /passive
echo     ket qua: %errorlevel%

echo.
echo Xong. Quay lai Claude va nhan "cai xong".
pause
