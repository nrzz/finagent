@echo off
title FinAgent - One Click Start
cd /d "%~dp0"

echo.
echo  ========================================
echo   FinAgent - Easy Start
echo   No coding. No config files needed.
echo  ========================================
echo.

where python >nul 2>&1
if errorlevel 1 (
  echo [ERROR] Python was not found. Install Python 3.11+ from https://www.python.org/downloads/
  echo Make sure "Add Python to PATH" is checked, then run this file again.
  pause
  exit /b 1
)

where node >nul 2>&1
if errorlevel 1 (
  echo [ERROR] Node.js was not found. Install from https://nodejs.org/ then run this again.
  pause
  exit /b 1
)

if not exist "backend\.venv\Scripts\python.exe" (
  echo [1/4] Creating Python environment...
  python -m venv backend\.venv
  if errorlevel 1 (
    echo Failed to create virtual environment.
    pause
    exit /b 1
  )
)

echo [2/4] Installing / updating app...
backend\.venv\Scripts\python -m pip install -q -U pip
backend\.venv\Scripts\pip install -q -e "backend[dev]"
if errorlevel 1 (
  echo Backend install failed.
  pause
  exit /b 1
)

if not exist "frontend\dist\index.html" (
  echo [3/4] Building the website UI (first time only)...
  pushd frontend
  call npm install
  call npm run build
  popd
  if not exist "frontend\dist\index.html" (
    echo Frontend build failed.
    pause
    exit /b 1
  )
) else (
  echo [3/4] Website UI already built.
)

echo [4/4] Starting FinAgent...
echo.
echo  Open your browser to:  http://127.0.0.1:8000
echo  First visit opens the Setup Wizard.
echo  Keep this window open while using FinAgent.
echo  Press Ctrl+C to stop.
echo.

start "" "http://127.0.0.1:8000"
set PYTHONPATH=%~dp0backend\src
set FINAGENT_DATA_DIR=%~dp0data
backend\.venv\Scripts\python -m uvicorn finagent.main:app --host 0.0.0.0 --port 8000 --app-dir backend\src

pause
