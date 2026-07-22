$ErrorActionPreference = "SilentlyContinue"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$Runtime = Join-Path $Root "runtime"
$PidFile = Join-Path $Runtime "pids.json"

if (-not (Test-Path $PidFile)) {
  Write-Host "No runtime\pids.json found. Nothing to stop."
  exit 0
}

$pids = Get-Content -Raw $PidFile | ConvertFrom-Json
foreach ($name in @("frontend", "backend")) {
  $pidValue = [int]$pids.$name
  if ($pidValue -gt 0) {
    $process = Get-Process -Id $pidValue -ErrorAction SilentlyContinue
    if ($process) {
      Write-Host "Stopping $name process $pidValue..."
      Stop-Process -Id $pidValue -Force
    }
  }
}

Remove-Item -LiteralPath $PidFile -Force
Write-Host "Stopped local project services."
