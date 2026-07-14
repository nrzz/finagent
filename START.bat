@echo off
title FinAgent - One Click Start
cd /d "%~dp0"

echo.
echo  ========================================
echo   FinAgent - Easy Start
echo   Download -^> double-click -^> use
echo  ========================================
echo.

where python >nul 2>&1
if errorlevel 1 (
  echo [ERROR] Python was not found.
  echo.
  echo  Install Python 3.11 or newer:
  echo    https://www.python.org/downloads/
  echo  IMPORTANT: check "Add python.exe to PATH"
  echo  Then run this file again.
  echo.
  pause
  exit /b 1
)

where node >nul 2>&1
if errorlevel 1 (
  echo [ERROR] Node.js was not found.
  echo.
  echo  Install the LTS version:
  echo    https://nodejs.org/
  echo  Then run this file again.
  echo.
  pause
  exit /b 1
)

if not exist "backend\.venv\Scripts\python.exe" (
  echo [1/4] Creating Python environment (first time only)...
  python -m venv backend\.venv
  if errorlevel 1 (
    echo Failed to create virtual environment.
    pause
    exit /b 1
  )
) else (
  echo [1/4] Python environment ready.
)

echo [2/4] Installing / updating app...
backend\.venv\Scripts\python -m pip install -q -U pip
backend\.venv\Scripts\pip install -q -e "backend[dev]"
if errorlevel 1 (
  echo Backend install failed. Check your internet connection and try again.
  pause
  exit /b 1
)

if not exist "frontend\node_modules\" (
  echo [3/4] Installing website packages (first time)...
  pushd frontend
  call npm install
  if errorlevel 1 (
    echo npm install failed.
    popd
    pause
    exit /b 1
  )
  call npm run build
  popd
) else if not exist "frontend\dist\index.html" (
  echo [3/4] Building the website UI...
  pushd frontend
  call npm run build
  popd
) else (
  echo [3/4] Website UI ready.
)

if not exist "frontend\dist\index.html" (
  echo Frontend build failed.
  pause
  exit /b 1
)

echo [4/4] Starting FinAgent...
echo.

REM Show LAN IP for phone / APK testing
set "LANIP="
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /c:"IPv4"') do (
  for /f "tokens=1" %%b in ("%%a") do (
    if not defined LANIP set "LANIP=%%b"
  )
)

echo  ----------------------------------------
echo   PC browser:   http://127.0.0.1:8000
if defined LANIP (
  echo   Phone / APK:  http://%LANIP%:8000
  echo                 ^(same Wi-Fi as this PC^)
)
echo  ----------------------------------------
echo   First visit = Setup Wizard
echo   Keep this window OPEN while using the app
echo   Press Ctrl+C to stop
echo.
echo   Android APK? Double-click BUILD-APK.bat
echo   Beginner guide: HOW-TO-USE.md
echo  ----------------------------------------
echo.

start "" "http://127.0.0.1:8000"
set PYTHONPATH=%~dp0backend\src
set FINAGENT_DATA_DIR=%~dp0data
backend\.venv\Scripts\python -m uvicorn finagent.main:app --host 0.0.0.0 --port 8000 --app-dir backend\src

pause
