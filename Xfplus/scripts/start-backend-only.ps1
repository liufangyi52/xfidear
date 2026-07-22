param(
  [int]$BackendPort = 8000
)

$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$Python = Join-Path $Root ".venv\Scripts\python.exe"

Set-Location $Root
& $Python -m uvicorn backend.main:app --host 127.0.0.1 --port $BackendPort
