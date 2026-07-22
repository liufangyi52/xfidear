param(
  [int]$Port = 8000
)

$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$PythonHome = Join-Path $Root "portable_runtime\python"
$PythonExe = Join-Path $PythonHome "python.exe"
$SitePackages = Join-Path $PythonHome "Lib\site-packages"

if (-not (Test-Path $PythonExe)) {
  throw "Portable Python was not found: $PythonExe"
}

$env:PYTHONHOME = $PythonHome
$env:PYTHONPATH = "$SitePackages;$Root"

Push-Location $Root
try {
  Write-Host "Initializing local SQLite database..."
  & $PythonExe -m backend.scripts.init_db
  $Url = "http://127.0.0.1:$Port/app"
  Write-Host ""
  Write-Host "Project is running at $Url"
  Write-Host "Close this window to stop the service."
  Write-Host ""
  Start-Process $Url
  & $PythonExe -m uvicorn backend.main:app --host 127.0.0.1 --port $Port
}
finally {
  Pop-Location
}