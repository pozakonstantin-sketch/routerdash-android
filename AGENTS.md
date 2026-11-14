# Agent instructions — RouterDash Android

This repository contains only the native Android client. OpenWrt LuCI packages, ucode controllers, and router-side scripts stay in https://github.com/pozakonstantin-sketch/luci-app-routerdash.

## Compatibility
- Keep applicationId and namespace `ru.routerdash.android`.
- minSdk 26; compileSdk/targetSdk 36 unless owner approves a migration.
- JDK 17, Gradle 8.13, AGP 8.13.2, Kotlin 2.2.21.
- Never commit credentials, signing keys, keystores, local.properties, or router access details.

## Rules
1. Inspect before editing; preserve existing behavior.
2. Make small, reviewable changes.
3. Never claim build/test/device/router validation without evidence.
4. Run `gradle --no-daemon assembleDebug` after code changes.
5. Preserve strict SSH host-key verification; changed keys must be rejected.
6. File sync must never silently delete source or destination files; resolve conflicts explicitly.
7. Keep secrets in Android Keystore-backed encrypted storage; never log secrets.
8. Test network failure, expired sessions, missing SFTP, unavailable SSD mount, interrupted transfers, and Android background restrictions.
9. Keep the UI native; do not replace it with WebView.

Report changed files, exact commands, pass/fail results, remaining risks, and artifact paths. A successful compile is not proof of runtime correctness.
