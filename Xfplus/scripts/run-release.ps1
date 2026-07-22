param(
  [int]$Port = 8000
)

$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$Venv = Join-Path $Root ".venv"
$Python = Join-Path $Venv "Scripts\python.exe"
$Pip = Join-Path $Venv "Scripts\pip.exe"
$Wheelhouse = Join-Path $Root "wheelhouse"
$Requirements = Join-Path $Root "backend\requirements.txt"
$InstallMarker = Join-Path $Venv ".deps-installed"

function Require-Command([string]$Name, [string]$Hint) {
  if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
    throw "$Name was not found. $Hint"
  }
}

Require-Command "python" "请先安装 Python 3.11+，并勾选 Add Python to PATH。"

if (-not (Test-Path $Python)) {
  Write-Host "Creating local virtual environment in package..."
  python -m venv $Venv
}

if (-not (Test-Path $InstallMarker)) {
  if (-not (Test-Path $Wheelhouse)) {
    throw "wheelhouse directory is missing. 请确认发布包完整。"
  }
  Write-Host "Installing backend dependencies from bundled wheelhouse..."
  & $Pip install --no-index --find-links $Wheelhouse -r $Requirements
  New-Item -ItemType File -Path $InstallMarker -Force | Out-Null
}

Push-Location $Root
try {
  Write-Host "Initializing SQLite database..."
  & $Python -m backend.scripts.init_db

  $Url = "http://127.0.0.1:$Port/app"
  Write-Host ""
  Write-Host "Project is running at $Url"
  Write-Host "Close this window to stop the service."
  Write-Host ""
  Start-Process $Url
  & $Python -m uvicorn backend.main:app --host 127.0.0.1 --port $Port
}
finally {
  Pop-Location
}
