@echo off
title FinAgent - Build Android APK
cd /d "%~dp0"

echo.
echo  ========================================
echo   FinAgent - Build Android APK
echo  ========================================
echo.
echo  You need:
echo   1) FinAgent website running (START.bat)
echo   2) Android Studio (this script can open it)
echo.
echo  Tip: On your phone you can also just open
echo  http://YOUR-PC-IP:8000 in Chrome — no APK needed.
echo.

where node >nul 2>&1
if errorlevel 1 (
  echo [ERROR] Node.js not found. Install from https://nodejs.org/
  pause
  exit /b 1
)

if not exist "frontend\node_modules\" (
  echo Installing website packages...
  pushd frontend
  call npm install
  popd
)

echo [1/3] Building website UI...
pushd frontend
call npm run build
if errorlevel 1 (
  echo Build failed.
  popd
  pause
  exit /b 1
)

if not exist "android\gradlew.bat" (
  echo [2/3] Creating Android project (first time)...
  call npx cap add android
) else (
  echo [2/3] Android project already present.
)

echo Syncing UI into Android app...
call npx cap sync android
if errorlevel 1 (
  echo Capacitor sync failed.
  popd
  pause
  exit /b 1
)
popd

echo [3/3] Opening Android Studio...
echo.
echo  FIRST TIME ONLY - Android Studio welcome wizard:
echo   - Click through until it installs the Android SDK
echo   - Then open this project if it is not already open:
echo     D:\Projects\finagent\frontend\android
echo     (or your unzipped path\frontend\android)
echo.
echo  THEN BUILD THE APK:
echo   1. Wait until Gradle finishes syncing (bottom progress bar)
echo   2. Menu: Build -^> Build Bundle(s) / APK(s) -^> Build APK(s)
echo   3. When done, click "locate" to find the APK file
echo   4. Copy that APK to your phone and install it
echo   5. Open FinAgent on phone -^> Settings -^> Device / APK
echo      Set server URL to http://YOUR-PC-IP:8000  (see START.bat window)
echo.
echo  Emulator tip: use http://10.0.2.2:8000 as the server URL.
echo.

pushd frontend
call npx cap open android
popd

echo.
echo If Android Studio did not open, install it from:
echo   https://developer.android.com/studio
echo then run this file again.
echo.
pause
