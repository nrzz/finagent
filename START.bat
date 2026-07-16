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

set "NEED_UI_BUILD="
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
  set NEED_UI_BUILD=1
  popd
)

if not exist "frontend\dist\index.html" set NEED_UI_BUILD=1

REM Rebuild when package.json or git HEAD is newer than dist (avoids stale Settings UI)
if not defined NEED_UI_BUILD if exist "frontend\dist\index.html" (
  powershell -NoProfile -Command ^
    "$dist=(Get-Item 'frontend\dist\index.html').LastWriteTime; $stale=$false; if ((Get-Item 'frontend\package.json').LastWriteTime -gt $dist) { $stale=$true }; if ((Test-Path '.git\HEAD') -and ((Get-Item '.git\HEAD').LastWriteTime -gt $dist)) { $stale=$true }; if ($stale) { exit 1 } else { exit 0 }"
  if errorlevel 1 set NEED_UI_BUILD=1
)

if defined NEED_UI_BUILD (
  echo [3/4] Building the website UI...
  pushd frontend
  if not exist "node_modules\" (
    call npm install
    if errorlevel 1 (
      echo npm install failed.
      popd
      pause
      exit /b 1
    )
  )
  call npm run build
  if errorlevel 1 (
    echo Frontend build failed.
    popd
    pause
    exit /b 1
  )
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
echo   If Settings/Trade look wrong after an update:
echo   press Ctrl+Shift+R (hard refresh) once.
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
echo   Android APK for phones:
echo     Prefer GitHub Releases → FinAgent-android.apk
echo     ^(no Android Studio^). Or phone browser / PWA.
echo   Developers: BUILD-APK.bat
echo   Beginner guide: HOW-TO-USE.md
echo  ----------------------------------------
echo.

start "" "http://127.0.0.1:8000"
set PYTHONPATH=%~dp0backend\src
set FINAGENT_DATA_DIR=%~dp0data
backend\.venv\Scripts\python -m uvicorn finagent.main:app --host 0.0.0.0 --port 8000 --app-dir backend\src

pause
