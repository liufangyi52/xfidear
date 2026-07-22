param(
  [int]$BackendPort = 8000,
  [int]$FrontendPort = 5173,
  [switch]$SkipInstall
)

$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$Frontend = Join-Path $Root "frontend"
$Backend = Join-Path $Root "backend"
$Venv = Join-Path $Root ".venv"
$Python = Join-Path $Venv "Scripts\python.exe"
$Pip = Join-Path $Venv "Scripts\pip.exe"

function Require-Command([string]$Name, [string]$InstallHint) {
  if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
    throw "$Name was not found. $InstallHint"
  }
}

Require-Command "python" "Install Python 3.11+ and add it to PATH."
Require-Command "node" "Install Node.js 20+ and add it to PATH."
Require-Command "npm" "Install Node.js 20+; npm is included with Node.js."

if (-not (Test-Path $Python)) {
  Write-Host "Creating local Python virtual environment..."
  python -m venv $Venv
}

if (-not $SkipInstall) {
  Write-Host "Installing backend dependencies into .venv..."
  & $Pip install -r (Join-Path $Backend "requirements.txt")

  Write-Host "Installing frontend dependencies into frontend\node_modules..."
  Push-Location $Frontend
  npm install
  Pop-Location
}

Write-Host "Initializing local SQLite database..."
Push-Location $Root
& $Python -m backend.scripts.init_db
Pop-Location

$backendCommand = "Set-Location '$Root'; &'$Python' -m uvicorn backend.main:app --host 0.0.0.0 --port $BackendPort"
$frontendCommand = "Set-Location '$Frontend'; npm run dev -- --host 127.0.0.1 --port $FrontendPort"

Write-Host "Opening backend and frontend terminal windows..."
Start-Process powershell -ArgumentList @("-NoExit", "-ExecutionPolicy", "Bypass", "-Command", $backendCommand)
Start-Process powershell -ArgumentList @("-NoExit", "-ExecutionPolicy", "Bypass", "-Command", $frontendCommand)

Write-Host ""
Write-Host "Project is starting:"
Write-Host "  Frontend: http://127.0.0.1:$FrontendPort/"
Write-Host "  Backend:  http://127.0.0.1:$BackendPort/api/health"
Write-Host "  LAN API:  http://<your-lan-ip>:$BackendPort/api/health"
Write-Host ""
Write-Host "Close the two opened PowerShell windows to stop the services."
