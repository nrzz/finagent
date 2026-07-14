@echo off
title FinAgent - Build Android APK
cd /d "%~dp0"

echo.
echo  ========================================
echo   FinAgent - Build Android APK
echo   (Developers / maintainers)
echo  ========================================
echo.
echo  End users: download FinAgent-android.apk from
echo  GitHub Releases — no Android Studio needed.
echo  See HOW-TO-USE.md
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

if not exist "android\local.properties" (
  if exist "D:\Android\Sdk" (
    echo sdk.dir=D:\\Android\\Sdk> android\local.properties
    echo Using SDK D:\Android\Sdk
  ) else if exist "%LOCALAPPDATA%\Android\Sdk" (
    echo sdk.dir=%LOCALAPPDATA:\=\\%\\Android\\Sdk> android\local.properties
    echo Using SDK %LOCALAPPDATA%\Android\Sdk
  ) else (
    echo [WARN] No Android SDK found. Set sdk.dir in frontend\android\local.properties
  )
)

echo Syncing UI into Android app...
call npx cap sync android
if errorlevel 1 (
  echo Capacitor sync failed.
  popd
  pause
  exit /b 1
)

echo [3/3] Building release APK with Gradle...
pushd android
if defined JAVA_HOME goto :gradle
if exist "C:\Program Files\Microsoft\jdk-17.0.19.10-hotspot" set "JAVA_HOME=C:\Program Files\Microsoft\jdk-17.0.19.10-hotspot"
:gradle
set "ANDROID_HOME=D:\Android\Sdk"
if not exist "%ANDROID_HOME%" set "ANDROID_HOME=%LOCALAPPDATA%\Android\Sdk"
call gradlew.bat assembleRelease --no-daemon
if errorlevel 1 (
  echo.
  echo Gradle build failed. Opening Android Studio instead...
  popd
  call npx cap open android
  popd
  pause
  exit /b 1
)
popd
popd

if exist "frontend\android\app\build\outputs\apk\release\app-release.apk" (
  copy /Y "frontend\android\app\build\outputs\apk\release\app-release.apk" "FinAgent-android.apk" >nul
  echo.
  echo  SUCCESS — APK ready:
  echo    %cd%\FinAgent-android.apk
  echo  Copy to your phone, install, then Settings -^> Device / APK
  echo  set server URL from START.bat ^(e.g. http://192.168.1.7:8000^)
  echo.
) else (
  echo APK not found after build.
)

pause
