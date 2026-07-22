@echo off
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Xfplus\scripts\rebuild-portable-frontend.ps1"
pause