param(
  [string]$PackageName = "Xfplus-Full-Portable-Source"
)

$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$WorkspaceRoot = Resolve-Path (Join-Path $Root "..")
$MiniprogramRoot = Join-Path $WorkspaceRoot "miniprogram"
$PackageDir = Join-Path $WorkspaceRoot $PackageName
$ZipPath = Join-Path $WorkspaceRoot "$PackageName.zip"
$PackageProjectRoot = Join-Path $PackageDir "Xfplus"
$PackageMiniprogramRoot = Join-Path $PackageDir "miniprogram"
$PortableRuntimeRoot = Join-Path $PackageProjectRoot "portable_runtime"
$PortablePythonRoot = Join-Path $PortableRuntimeRoot "python"
$PortableNodeRoot = Join-Path $PortableRuntimeRoot "node"
$Wheelhouse = Join-Path $Root "release\EmergencyMonitoring-Portable\wheelhouse"

function Assert-InsideWorkspace([string]$PathToCheck) {
  $resolvedWorkspace = [System.IO.Path]::GetFullPath($WorkspaceRoot)
  $resolvedTarget = [System.IO.Path]::GetFullPath($PathToCheck)
  if (-not $resolvedTarget.StartsWith($resolvedWorkspace, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Refusing to write outside workspace: $resolvedTarget"
  }
}

function Invoke-RobocopyMirror([string]$Source, [string]$Destination, [string[]]$ExcludeDirs = @(), [string[]]$ExcludeFiles = @()) {
  New-Item -ItemType Directory -Force -Path $Destination | Out-Null
  $arguments = @(
    $Source,
    $Destination,
    "/E",
    "/NFL",
    "/NDL",
    "/NJH",
    "/NJS",
    "/NC",
    "/NS",
    "/NP"
  )
  if ($ExcludeDirs.Count) {
    $arguments += "/XD"
    $arguments += $ExcludeDirs
  }
  if ($ExcludeFiles.Count) {
    $arguments += "/XF"
    $arguments += $ExcludeFiles
  }
  & robocopy @arguments | Out-Null
  $exitCode = $LASTEXITCODE
  if ($exitCode -gt 7) {
    throw "Robocopy failed from $Source to $Destination with exit code $exitCode"
  }
}

function Write-Utf8File([string]$Path, [string[]]$Lines) {
  $targetDir = Split-Path -Parent $Path
  if ($targetDir) {
    New-Item -ItemType Directory -Force -Path $targetDir | Out-Null
  }
  [System.IO.File]::WriteAllText($Path, ($Lines -join [Environment]::NewLine), [System.Text.UTF8Encoding]::new($false))
}

function Write-AsciiFile([string]$Path, [string[]]$Lines) {
  $targetDir = Split-Path -Parent $Path
  if ($targetDir) {
    New-Item -ItemType Directory -Force -Path $targetDir | Out-Null
  }
  [System.IO.File]::WriteAllText($Path, ($Lines -join [Environment]::NewLine), [System.Text.Encoding]::ASCII)
}

if (-not (Test-Path $MiniprogramRoot)) {
  throw "Miniprogram directory was not found: $MiniprogramRoot"
}
if (-not (Test-Path $Wheelhouse)) {
  throw "Wheelhouse directory was not found: $Wheelhouse"
}

$SystemPython = (Get-Command python -ErrorAction Stop).Source
$SystemPythonRoot = Split-Path -Parent $SystemPython
$SystemNode = (Get-Command node -ErrorAction Stop).Source
$SystemNodeRoot = Split-Path -Parent $SystemNode
$SystemNpm = Join-Path $SystemNodeRoot "npm.cmd"

if (-not (Test-Path $SystemNpm)) {
  throw "npm.cmd was not found next to node.exe: $SystemNpm"
}
if (-not (Test-Path (Join-Path $Root "frontend\node_modules"))) {
  throw "frontend\\node_modules was not found. Please install frontend dependencies first."
}

Assert-InsideWorkspace $PackageDir
Assert-InsideWorkspace $ZipPath

Write-Host "Building frontend dist with portable-safe env..."
Push-Location (Join-Path $Root "frontend")
try {
  $env:VITE_API_BASE_URL = "http://127.0.0.1:8000"
  $env:VITE_AMAP_JS_KEY = ""
  npm run build | Out-Host
}
finally {
  Remove-Item Env:VITE_API_BASE_URL -ErrorAction SilentlyContinue
  Remove-Item Env:VITE_AMAP_JS_KEY -ErrorAction SilentlyContinue
  Pop-Location
}

if (Test-Path $PackageDir) {
  Remove-Item -LiteralPath $PackageDir -Recurse -Force
}
if (Test-Path $ZipPath) {
  Remove-Item -LiteralPath $ZipPath -Force
}

Write-Host "Copying Xfplus source tree..."
Invoke-RobocopyMirror $Root $PackageProjectRoot @(
  (Join-Path $Root ".git"),
  (Join-Path $Root ".venv"),
  (Join-Path $Root "runtime"),
  (Join-Path $Root "release"),
  (Join-Path $Root "chrome-measure-profile"),
  (Join-Path $Root "chrome-measure-profile2")
) @(
  ".env"
)

Write-Host "Copying miniprogram source tree..."
Invoke-RobocopyMirror $MiniprogramRoot $PackageMiniprogramRoot

Write-Host "Copying portable Python runtime..."
Invoke-RobocopyMirror $SystemPythonRoot $PortablePythonRoot @(
  (Join-Path $SystemPythonRoot "__pycache__")
)

Write-Host "Copying portable Node.js runtime..."
Invoke-RobocopyMirror $SystemNodeRoot $PortableNodeRoot

Write-Host "Installing backend dependencies into portable Python..."
$PortableSitePackages = Join-Path $PortablePythonRoot "Lib\site-packages"
New-Item -ItemType Directory -Force -Path $PortableSitePackages | Out-Null
& (Join-Path $PortablePythonRoot "python.exe") -m pip install `
  --no-index `
  --find-links $Wheelhouse `
  --target $PortableSitePackages `
  -r (Join-Path $PackageProjectRoot "backend\requirements.txt") | Out-Host
$pipExitCode = $LASTEXITCODE
if ($pipExitCode -ne 0) {
  Write-Host "Bundled wheelhouse was incomplete. Retrying backend dependency install from the default index..."
  & (Join-Path $PortablePythonRoot "python.exe") -m pip install `
    --target $PortableSitePackages `
    -r (Join-Path $PackageProjectRoot "backend\requirements.txt") | Out-Host
  if ($LASTEXITCODE -ne 0) {
    throw "Portable backend dependency install failed."
  }
}

Write-Host "Writing portable-safe env files..."
Write-Utf8File (Join-Path $PackageProjectRoot ".env") @(
  "VITE_API_BASE_URL=http://127.0.0.1:8000",
  "VITE_AMAP_JS_KEY=",
  "AMAP_SERVER_KEY=",
  "AMAP_WEATHER_KEY=",
  "WEATHER_API_KEY=",
  "FRONTEND_ORIGIN=http://127.0.0.1:5173",
  "DATABASE_URL=sqlite:///backend/data/app.db",
  "QWEATHER_LOCATION_ID=101251101",
  "IFLYTEK_APPID=",
  "IFLYTEK_API_KEY=",
  "IFLYTEK_API_SECRET=",
  "IFLYTEK_MODEL=generalv3",
  "DASHSCOPE_API_KEY=",
  "DEEPSEEK_API_KEY=",
  "DEEPSEEK_BASE_URL=https://api.deepseek.com",
  "DEEPSEEK_MODEL=deepseek-chat",
  "FALLBACK_LLM_TYPE=mock",
  "AI_TIMEOUT_SECONDS=15"
)
Write-Utf8File (Join-Path $PackageProjectRoot "frontend\.env.local") @(
  "VITE_API_BASE_URL=http://127.0.0.1:8000",
  "VITE_AMAP_JS_KEY="
)

Write-Host "Writing portable run scripts..."
$PortableScriptDir = Join-Path $PackageProjectRoot "scripts"

Write-Utf8File (Join-Path $PortableScriptDir "start-portable-app.ps1") @(
  'param(',
  '  [int]$Port = 8000',
  ')',
  '',
  '$ErrorActionPreference = "Stop"',
  '$Root = Resolve-Path (Join-Path $PSScriptRoot "..")',
  '$PythonHome = Join-Path $Root "portable_runtime\python"',
  '$PythonExe = Join-Path $PythonHome "python.exe"',
  '$SitePackages = Join-Path $PythonHome "Lib\site-packages"',
  '',
  'if (-not (Test-Path $PythonExe)) {',
  '  throw "Portable Python was not found: $PythonExe"',
  '}',
  '',
  '$env:PYTHONHOME = $PythonHome',
  '$env:PYTHONPATH = "$SitePackages;$Root"',
  '',
  'Push-Location $Root',
  'try {',
  '  Write-Host "Initializing local SQLite database..."',
  '  & $PythonExe -m backend.scripts.init_db',
  '  $Url = "http://127.0.0.1:$Port/app"',
  '  Write-Host ""',
  '  Write-Host "Project is running at $Url"',
  '  Write-Host "Close this window to stop the service."',
  '  Write-Host ""',
  '  Start-Process $Url',
  '  & $PythonExe -m uvicorn backend.main:app --host 127.0.0.1 --port $Port',
  '}',
  'finally {',
  '  Pop-Location',
  '}'
)

Write-Utf8File (Join-Path $PortableScriptDir "start-portable-dev.ps1") @(
  'param(',
  '  [int]$BackendPort = 8000,',
  '  [int]$FrontendPort = 5173',
  ')',
  '',
  '$ErrorActionPreference = "Stop"',
  '$Root = Resolve-Path (Join-Path $PSScriptRoot "..")',
  '$Frontend = Join-Path $Root "frontend"',
  '$Runtime = Join-Path $Root "runtime"',
  '$PythonHome = Join-Path $Root "portable_runtime\python"',
  '$PythonExe = Join-Path $PythonHome "python.exe"',
  '$SitePackages = Join-Path $PythonHome "Lib\site-packages"',
  '$NodeHome = Join-Path $Root "portable_runtime\node"',
  '$NpmCmd = Join-Path $NodeHome "npm.cmd"',
  '$PidFile = Join-Path $Runtime "pids.json"',
  '',
  'if (-not (Test-Path $PythonExe)) { throw "Portable Python was not found: $PythonExe" }',
  'if (-not (Test-Path $NpmCmd)) { throw "Portable npm was not found: $NpmCmd" }',
  '',
  'New-Item -ItemType Directory -Force -Path $Runtime | Out-Null',
  'if (Test-Path $PidFile) {',
  '  Write-Host "Existing runtime\pids.json detected. Stopping old dev processes first..."',
  '  & (Join-Path $PSScriptRoot "stop-portable-dev.ps1")',
  '}',
  '',
  '$backendCommand = "Set-Location ''$Root''; `$env:PYTHONHOME = ''$PythonHome''; `$env:PYTHONPATH = ''$SitePackages;$Root''; &''$PythonExe'' -m backend.scripts.init_db; &''$PythonExe'' -m uvicorn backend.main:app --reload --host 0.0.0.0 --port $BackendPort"',
  '$frontendCommand = "Set-Location ''$Frontend''; `$env:Path = ''$NodeHome;'' + `$env:Path; &''$NpmCmd'' run dev -- --host 127.0.0.1 --port $FrontendPort"',
  '',
  '$backendProcess = Start-Process powershell -ArgumentList @("-NoExit", "-ExecutionPolicy", "Bypass", "-Command", $backendCommand) -PassThru',
  '$frontendProcess = Start-Process powershell -ArgumentList @("-NoExit", "-ExecutionPolicy", "Bypass", "-Command", $frontendCommand) -PassThru',
  '',
  '@{',
  '  backend = $backendProcess.Id',
  '  frontend = $frontendProcess.Id',
  '  backend_port = $BackendPort',
  '  frontend_port = $FrontendPort',
  '} | ConvertTo-Json | Set-Content -Encoding UTF8 $PidFile',
  '',
  'Write-Host ""',
  'Write-Host "Development mode is starting:"',
  'Write-Host "  Frontend: http://127.0.0.1:$FrontendPort/"',
  'Write-Host "  Backend:  http://127.0.0.1:$BackendPort/api/health"',
  'Write-Host ""',
  'Write-Host "Close the two opened PowerShell windows or run Stop-Dev.bat to stop them."'
)

Write-Utf8File (Join-Path $PortableScriptDir "stop-portable-dev.ps1") @(
  '$ErrorActionPreference = "SilentlyContinue"',
  '$Root = Resolve-Path (Join-Path $PSScriptRoot "..")',
  '$PidFile = Join-Path $Root "runtime\pids.json"',
  '',
  'if (-not (Test-Path $PidFile)) {',
  '  Write-Host "No runtime\pids.json found. Nothing to stop."',
  '  exit 0',
  '}',
  '',
  '$pids = Get-Content -Raw $PidFile | ConvertFrom-Json',
  'foreach ($name in @("frontend", "backend")) {',
  '  $pidValue = [int]$pids.$name',
  '  if ($pidValue -gt 0) {',
  '    $process = Get-Process -Id $pidValue -ErrorAction SilentlyContinue',
  '    if ($process) {',
  '      Write-Host "Stopping $name process $pidValue..."',
  '      Stop-Process -Id $pidValue -Force',
  '    }',
  '  }',
  '}',
  '',
  'Remove-Item -LiteralPath $PidFile -Force -ErrorAction SilentlyContinue',
  'Write-Host "Stopped local dev services."'
)

Write-Utf8File (Join-Path $PortableScriptDir "rebuild-portable-frontend.ps1") @(
  '$ErrorActionPreference = "Stop"',
  '$Root = Resolve-Path (Join-Path $PSScriptRoot "..")',
  '$Frontend = Join-Path $Root "frontend"',
  '$NodeHome = Join-Path $Root "portable_runtime\node"',
  '$NpmCmd = Join-Path $NodeHome "npm.cmd"',
  '',
  'if (-not (Test-Path $NpmCmd)) { throw "Portable npm was not found: $NpmCmd" }',
  '',
  'Push-Location $Frontend',
  'try {',
  '  $env:Path = "$NodeHome;$env:Path"',
  '  & $NpmCmd run build',
  '}',
  'finally {',
  '  Pop-Location',
  '}'
)

Write-AsciiFile (Join-Path $PackageDir "Start-App.bat") @(
  '@echo off',
  'setlocal',
  'powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Xfplus\scripts\start-portable-app.ps1"',
  'pause'
)
Write-AsciiFile (Join-Path $PackageDir "Start-Dev.bat") @(
  '@echo off',
  'setlocal',
  'powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Xfplus\scripts\start-portable-dev.ps1"',
  'pause'
)
Write-AsciiFile (Join-Path $PackageDir "Stop-Dev.bat") @(
  '@echo off',
  'setlocal',
  'powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Xfplus\scripts\stop-portable-dev.ps1"',
  'pause'
)
Write-AsciiFile (Join-Path $PackageDir "Rebuild-Frontend.bat") @(
  '@echo off',
  'setlocal',
  'powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Xfplus\scripts\rebuild-portable-frontend.ps1"',
  'pause'
)

Write-Utf8File (Join-Path $PackageDir "README-FIRST.txt") @(
  "This package already includes:",
  "1. Xfplus frontend, backend, data, scripts, and portable runtimes.",
  "2. miniprogram source code.",
  "",
  "Run the web platform directly:",
  "1. Extract the whole zip file.",
  "2. Double click Start-App.bat.",
  "3. The browser opens http://127.0.0.1:8000/app",
  "",
  "Edit and develop:",
  "1. Double click Start-Dev.bat.",
  "2. Frontend: http://127.0.0.1:5173/",
  "3. Backend:  http://127.0.0.1:8000/api/health",
  "4. Rebuild frontend after edits with Rebuild-Frontend.bat.",
  "5. Stop dev mode with Stop-Dev.bat.",
  "",
  "Included by default:",
  "- Portable Python and Node.js.",
  "- frontend/node_modules already included.",
  "- backend dependencies already included.",
  "- Safe .env without sender machine keys.",
  "- AI defaults to mock mode.",
  "",
  "Mini program note:",
  "- Mini program source is in the miniprogram folder.",
  "- Running the mini program still requires WeChat DevTools.",
  "- That is a platform requirement, not a missing project environment.",
  "",
  "Demo accounts:",
  "- city_demo / 123456",
  "- county_admin_demo / 123456",
  "- community_admin_demo / 123456",
  "- resident_demo / 123456",
  "- tourist_demo / 123456"
)

Write-Host "Compressing package..."
tar.exe -a -cf $ZipPath -C $WorkspaceRoot $PackageName
if ($LASTEXITCODE -ne 0) {
  throw "Zip creation failed."
}

Write-Host ""
Write-Host "Complete portable package created:"
Write-Host "  $PackageDir"
Write-Host "Zip created:"
Write-Host "  $ZipPath"
