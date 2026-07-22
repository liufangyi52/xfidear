param(
  [int]$BackendPort = 8000,
  [int]$FrontendPort = 5173
)

$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$Frontend = Join-Path $Root "frontend"
$Runtime = Join-Path $Root "runtime"
$PythonHome = Join-Path $Root "portable_runtime\python"
$PythonExe = Join-Path $PythonHome "python.exe"
$SitePackages = Join-Path $PythonHome "Lib\site-packages"
$NodeHome = Join-Path $Root "portable_runtime\node"
$NpmCmd = Join-Path $NodeHome "npm.cmd"
$PidFile = Join-Path $Runtime "pids.json"

if (-not (Test-Path $PythonExe)) { throw "Portable Python was not found: $PythonExe" }
if (-not (Test-Path $NpmCmd)) { throw "Portable npm was not found: $NpmCmd" }

New-Item -ItemType Directory -Force -Path $Runtime | Out-Null
if (Test-Path $PidFile) {
  Write-Host "Existing runtime\pids.json detected. Stopping old dev processes first..."
  & (Join-Path $PSScriptRoot "stop-portable-dev.ps1")
}

$backendCommand = "Set-Location '$Root'; `$env:PYTHONHOME = '$PythonHome'; `$env:PYTHONPATH = '$SitePackages;$Root'; &'$PythonExe' -m backend.scripts.init_db; &'$PythonExe' -m uvicorn backend.main:app --reload --host 0.0.0.0 --port $BackendPort"
$frontendCommand = "Set-Location '$Frontend'; `$env:Path = '$NodeHome;' + `$env:Path; &'$NpmCmd' run dev -- --host 127.0.0.1 --port $FrontendPort"

$backendProcess = Start-Process powershell -ArgumentList @("-NoExit", "-ExecutionPolicy", "Bypass", "-Command", $backendCommand) -PassThru
$frontendProcess = Start-Process powershell -ArgumentList @("-NoExit", "-ExecutionPolicy", "Bypass", "-Command", $frontendCommand) -PassThru

@{
  backend = $backendProcess.Id
  frontend = $frontendProcess.Id
  backend_port = $BackendPort
  frontend_port = $FrontendPort
} | ConvertTo-Json | Set-Content -Encoding UTF8 $PidFile

Write-Host ""
Write-Host "Development mode is starting:"
Write-Host "  Frontend: http://127.0.0.1:$FrontendPort/"
Write-Host "  Backend:  http://127.0.0.1:$BackendPort/api/health"
Write-Host ""
Write-Host "Close the two opened PowerShell windows or run Stop-Dev.bat to stop them."