# FinAgent one-click start (Windows PowerShell)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host ""
Write-Host "========================================"
Write-Host " FinAgent - Easy Start"
Write-Host " No coding. No config files needed."
Write-Host "========================================"
Write-Host ""

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
  Write-Host "Python not found. Install Python 3.11+ from https://www.python.org/downloads/" -ForegroundColor Red
  exit 1
}
if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
  Write-Host "Node.js not found. Install from https://nodejs.org/" -ForegroundColor Red
  exit 1
}

if (-not (Test-Path "backend\.venv\Scripts\python.exe")) {
  Write-Host "[1/4] Creating Python environment..."
  python -m venv backend\.venv
}

Write-Host "[2/4] Installing / updating app..."
& backend\.venv\Scripts\python -m pip install -q -U pip
& backend\.venv\Scripts\pip install -q -e "backend[dev]"

if (-not (Test-Path "frontend\dist\index.html")) {
  Write-Host "[3/4] Building the website UI (first time only)..."
  Push-Location frontend
  npm install
  npm run build
  Pop-Location
} else {
  Write-Host "[3/4] Website UI already built."
}

Write-Host "[4/4] Starting FinAgent at http://127.0.0.1:8000"
Write-Host "Keep this window open. Press Ctrl+C to stop."
Start-Process "http://127.0.0.1:8000"

$env:PYTHONPATH = Join-Path $PSScriptRoot "backend\src"
$env:FINAGENT_DATA_DIR = Join-Path $PSScriptRoot "data"
& backend\.venv\Scripts\python -m uvicorn finagent.main:app --host 0.0.0.0 --port 8000 --app-dir backend\src
