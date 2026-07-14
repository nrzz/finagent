# Releases & Android APK (maintainers)

## What end users need

| Goal | Do this | Android Studio? |
|------|---------|-----------------|
| Run FinAgent | `START.bat` / Docker | No |
| Phone browser | Open PC LAN URL from `START.bat` | No |
| Phone app icon | Download **FinAgent-android.apk** from [GitHub Releases](../../releases) | **No** |
| Hack the Android project | `BUILD-APK.bat` | Yes |

End users should **never** need Android Studio. The APK is a thin Capacitor shell; they point it at their own PC in **Settings → Device / APK**.

## Git flow to publish a version

```bash
# 1. main is green (CI)
git checkout main
git pull

# 2. tag a semver release
git tag v0.1.0
git push origin v0.1.0
```

Pushing `v*` runs [`.github/workflows/release.yml`](../../.github/workflows/release.yml):

1. Builds the web UI  
2. Generates Capacitor Android + **FinAgent-android.apk**  
3. Attaches the APK to the GitHub Release  
4. Builds/pushes the Docker image to GHCR  

Manual APK-only build (no tag): GitHub → **Actions → Release → Run workflow**.

## Local APK (this machine)

```bash
cd frontend
npm run build && npx cap sync android
cd android && ./gradlew assembleRelease   # or assembleDebug
```

Or double-click `BUILD-APK.bat` (developers).

## Signing

CI ships a **debug-signed** community APK so installs work without a private keystore.  
For Play Store / stronger signing later, add repo secrets and wire `signingConfigs.release` (optional).
