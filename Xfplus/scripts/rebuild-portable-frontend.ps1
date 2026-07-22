$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$Frontend = Join-Path $Root "frontend"
$NodeHome = Join-Path $Root "portable_runtime\node"
$NpmCmd = Join-Path $NodeHome "npm.cmd"

if (-not (Test-Path $NpmCmd)) { throw "Portable npm was not found: $NpmCmd" }

Push-Location $Frontend
try {
  $env:Path = "$NodeHome;$env:Path"
  & $NpmCmd run build
}
finally {
  Pop-Location
}