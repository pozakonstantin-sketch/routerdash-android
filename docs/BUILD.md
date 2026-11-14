# Build RouterDash Android

Requirements: JDK 17, Android SDK Platform 36, Build Tools 36.0.0, Gradle 8.13.

From repository root:

```sh
gradle --no-daemon clean assembleDebug
```

APK: `app/build/outputs/apk/debug/app-debug.apk`.

Install on a connected device:

```sh
adb install -r app/build/outputs/apk/debug/app-debug.apk
```

Release signing: see [store/release-signing.md](store/release-signing.md). Never commit keystores or passwords.
