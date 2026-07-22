param(
  [int]$BackendPort = 8000,
  [int]$FrontendPort = 5173,
  [switch]$SkipInstall
)

$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$Frontend = Join-Path $Root "frontend"
$Backend = Join-Path $Root "backend"
$Runtime = Join-Path $Root "runtime"
$Venv = Join-Path $Root ".venv"
$Python = Join-Path $Venv "Scripts\python.exe"
$Pip = Join-Path $Venv "Scripts\pip.exe"

New-Item -ItemType Directory -Force -Path $Runtime | Out-Null

function Test-PortInUse([int]$Port) {
  $connection = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
  return $null -ne $connection
}

function Require-Command([string]$Name, [string]$InstallHint) {
  if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
    throw "$Name was not found. $InstallHint"
  }
}

if (Test-PortInUse $BackendPort) {
  throw "Port $BackendPort is already in use. Run scripts\stop.ps1 or change -BackendPort."
}
if (Test-PortInUse $FrontendPort) {
  throw "Port $FrontendPort is already in use. Run scripts\stop.ps1 or change -FrontendPort."
}

Require-Command "python" "Install Python 3.11+ and add it to PATH."
Require-Command "node" "Install Node.js 20+ and add it to PATH."
Require-Command "npm" "Install Node.js 20+; npm is included with Node.js."

$NodeDir = Split-Path -Parent (Get-Command "node" -ErrorAction Stop).Source
$NpmCmd = Join-Path $NodeDir "npm.cmd"
if (-not (Test-Path $NpmCmd)) {
  $NpmCmd = (Get-Command "npm" -ErrorAction Stop).Source
}

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

$backendOutLog = Join-Path $Runtime "backend.out.log"
$backendErrLog = Join-Path $Runtime "backend.err.log"
$frontendOutLog = Join-Path $Runtime "frontend.out.log"
$frontendErrLog = Join-Path $Runtime "frontend.err.log"
New-Item -ItemType File -Force -Path $backendOutLog, $backendErrLog, $frontendOutLog, $frontendErrLog | Out-Null

Write-Host "Starting backend on http://0.0.0.0:$BackendPort ..."
$backendProcess = Start-Process -FilePath $Python `
  -ArgumentList @("-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "$BackendPort") `
  -WorkingDirectory $Root `
  -RedirectStandardOutput $backendOutLog `
  -RedirectStandardError $backendErrLog `
  -WindowStyle Hidden `
  -PassThru

Write-Host "Starting frontend on http://127.0.0.1:$FrontendPort ..."
$frontendProcess = Start-Process -FilePath $NpmCmd `
  -ArgumentList @("run", "dev", "--", "--host", "127.0.0.1", "--port", "$FrontendPort") `
  -WorkingDirectory $Frontend `
  -RedirectStandardOutput $frontendOutLog `
  -RedirectStandardError $frontendErrLog `
  -WindowStyle Hidden `
  -PassThru

@{
  backend = $backendProcess.Id
  frontend = $frontendProcess.Id
  backend_port = $BackendPort
  frontend_port = $FrontendPort
} | ConvertTo-Json | Set-Content -Encoding UTF8 (Join-Path $Runtime "pids.json")

Start-Sleep -Seconds 3
Write-Host ""
Write-Host "Project is running:"
Write-Host "  Frontend: http://127.0.0.1:$FrontendPort/"
Write-Host "  Backend:  http://127.0.0.1:$BackendPort/api/health"
Write-Host "  LAN API:  http://<your-lan-ip>:$BackendPort/api/health"
Write-Host ""
Write-Host "Logs:"
Write-Host "  $backendOutLog"
Write-Host "  $backendErrLog"
Write-Host "  $frontendOutLog"
Write-Host "  $frontendErrLog"
Write-Host ""
Write-Host "Stop with: powershell -ExecutionPolicy Bypass -File scripts\stop.ps1"
