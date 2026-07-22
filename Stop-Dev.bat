@echo off
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Xfplus\scripts\stop-portable-dev.ps1"
pause