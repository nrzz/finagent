# FinAgent one-click start (Windows PowerShell)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host ""
Write-Host "========================================"
Write-Host " FinAgent - Easy Start"
Write-Host " Download -> run -> use"
Write-Host "========================================"
Write-Host ""

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
  Write-Host "Python not found. Install 3.11+ from https://www.python.org/downloads/ (Add to PATH)." -ForegroundColor Red
  exit 1
}
if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
  Write-Host "Node.js not found. Install LTS from https://nodejs.org/" -ForegroundColor Red
  exit 1
}

if (-not (Test-Path "backend\.venv\Scripts\python.exe")) {
  Write-Host "[1/4] Creating Python environment..."
  python -m venv backend\.venv
} else {
  Write-Host "[1/4] Python environment ready."
}

Write-Host "[2/4] Installing / updating app..."
& backend\.venv\Scripts\python -m pip install -q -U pip
& backend\.venv\Scripts\pip install -q -e "backend[dev]"

if (-not (Test-Path "frontend\node_modules")) {
  Write-Host "[3/4] Installing website packages..."
  Push-Location frontend
  npm install
  npm run build
  Pop-Location
} elseif (-not (Test-Path "frontend\dist\index.html")) {
  Write-Host "[3/4] Building the website UI..."
  Push-Location frontend
  npm run build
  Pop-Location
} else {
  Write-Host "[3/4] Website UI ready."
}

$lan = (Get-NetIPAddress -AddressFamily IPv4 |
  Where-Object { $_.IPAddress -notlike "127.*" -and $_.PrefixOrigin -ne "WellKnown" } |
  Select-Object -First 1 -ExpandProperty IPAddress)

Write-Host "[4/4] Starting FinAgent..."
Write-Host "----------------------------------------"
Write-Host " PC browser:   http://127.0.0.1:8000"
if ($lan) { Write-Host " Phone / APK:  http://${lan}:8000" }
Write-Host " APK download: GitHub Releases (FinAgent-android.apk) — no Android Studio"
Write-Host " Keep this window open. Ctrl+C to stop."
Write-Host "----------------------------------------"

Start-Process "http://127.0.0.1:8000"
$env:PYTHONPATH = Join-Path $PSScriptRoot "backend\src"
$env:FINAGENT_DATA_DIR = Join-Path $PSScriptRoot "data"
& backend\.venv\Scripts\python -m uvicorn finagent.main:app --host 0.0.0.0 --port 8000 --app-dir backend\src
