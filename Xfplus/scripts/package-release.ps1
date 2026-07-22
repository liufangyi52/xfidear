param(
  [string]$PackageName = "EmergencyMonitoring-Portable"
)

$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$Frontend = Join-Path $Root "frontend"
$Backend = Join-Path $Root "backend"
$ReleaseRoot = Join-Path $Root "release"
$PackageDir = Join-Path $ReleaseRoot $PackageName
$Wheelhouse = Join-Path $PackageDir "wheelhouse"
$VenvPython = Join-Path $Root ".venv\Scripts\python.exe"

function Assert-InsideRoot([string]$PathToCheck) {
  $resolvedRoot = [System.IO.Path]::GetFullPath($Root)
  $resolvedTarget = [System.IO.Path]::GetFullPath($PathToCheck)
  if (-not $resolvedTarget.StartsWith($resolvedRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Refusing to write outside workspace: $resolvedTarget"
  }
}

if (-not (Test-Path $VenvPython)) {
  throw "Local .venv was not found. Please run scripts\start-foreground.ps1 once before packaging."
}

Write-Host "Building frontend dist..."
Push-Location $Frontend
try {
  npm run build
}
finally {
  Pop-Location
}

Assert-InsideRoot $PackageDir
if (Test-Path $PackageDir) {
  Remove-Item -LiteralPath $PackageDir -Recurse -Force
}
New-Item -ItemType Directory -Path $PackageDir | Out-Null

Write-Host "Copying backend and frontend dist..."
Copy-Item -Path $Backend -Destination (Join-Path $PackageDir "backend") -Recurse
New-Item -ItemType Directory -Path (Join-Path $PackageDir "frontend") | Out-Null
New-Item -ItemType Directory -Path (Join-Path $PackageDir "scripts") | Out-Null
Copy-Item -Path (Join-Path $Frontend "dist") -Destination (Join-Path $PackageDir "frontend\dist") -Recurse
Copy-Item -Path (Join-Path $Root "scripts\run-release.ps1") -Destination (Join-Path $PackageDir "scripts\run-release.ps1")

Write-Host "Building offline wheelhouse..."
New-Item -ItemType Directory -Path $Wheelhouse | Out-Null
& $VenvPython -m pip wheel --wheel-dir $Wheelhouse -r (Join-Path $Backend "requirements.txt")
foreach ($pyVersion in @("3.11", "3.12", "3.13")) {
  Write-Host "Downloading Windows wheels for Python $pyVersion..."
  & $VenvPython -m pip download `
    --dest $Wheelhouse `
    --only-binary=:all: `
    --platform win_amd64 `
    --implementation cp `
    --python-version $pyVersion `
    -r (Join-Path $Backend "requirements.txt")
}

@(
  "@echo off",
  "setlocal",
  "powershell -NoProfile -ExecutionPolicy Bypass -File ""%~dp0scripts\run-release.ps1""",
  "pause"
) | Set-Content -Encoding ASCII (Join-Path $PackageDir "Start.bat")

Copy-Item -Path (Join-Path $Root ".env") -Destination (Join-Path $PackageDir ".env")

@(
  "# Emergency Monitoring Portable Package",
  "",
  "## How to run",
  "",
  "1. Extract the whole folder.",
  "2. Double click Start.bat.",
  "3. Browser will open: http://127.0.0.1:8000/app",
  "",
  "## Requirements",
  "",
  "- Windows",
  "- Windows 64-bit Python 3.11, 3.12, or 3.13 installed and available in PATH",
  "",
  "No npm install is needed.",
  "Frontend has already been built into frontend/dist.",
  "Backend Python dependencies are bundled in wheelhouse/.",
  "On first run, dependencies are installed into this package's local .venv/.",
  "",
  "## Demo accounts",
  "",
  "- city_demo / 123456",
  "- county_admin_demo / 123456",
  "- community_admin_demo / 123456",
  "- resident_demo / 123456",
  "- tourist_demo / 123456",
  "",
  "## Note",
  "",
  "The package includes the current .env file from the sender.",
  "Send it only to trusted people if .env contains real API keys."
) | Set-Content -Encoding ASCII (Join-Path $PackageDir "README.txt")

$ZipPath = Join-Path $ReleaseRoot "$PackageName.zip"
Assert-InsideRoot $ZipPath
if (Test-Path $ZipPath) {
  Remove-Item -LiteralPath $ZipPath -Force
}
Compress-Archive -Path $PackageDir -DestinationPath $ZipPath -Force

Write-Host ""
Write-Host "Release package created:"
Write-Host "  $PackageDir"
Write-Host "Release zip created:"
Write-Host "  $ZipPath"
