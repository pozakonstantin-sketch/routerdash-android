# RouterDash for Android

Standalone native Android client for OpenWrt routers.

> This repository contains **only the Android application**. The OpenWrt LuCI package and web dashboard remain in [luci-app-routerdash](https://github.com/pozakonstantin-sketch/luci-app-routerdash).

## Project

- Android application ID: `ru.routerdash.android`
- Current source baseline: version `2.5.1`, versionCode `12`
- Kotlin, Android Gradle Plugin, Jetpack Compose, Material 3
- minSdk 26; compileSdk / targetSdk 36
- JDK 17; Gradle 8.13
- LuCI JSON-RPC / ubus for router data; SSH/SFTP for terminal and file transfer

## Features in the current source baseline

- Router overview, network, DHCP clients, disks, packages, services, VPN, firewall and system logs
- SSH terminal with host-key verification
- Phone ↔ router SSD file transfer over SFTP, with manual conflict handling and no mirror deletion
- Optional background photo upload
- Android home-screen widget and biometric authentication support

Feature descriptions reflect the current source baseline and are not a claim that every function has passed device-level testing.

## Build

Open this repository root in Android Studio (JDK 17 and Android SDK Platform 36 required), or run:

```sh
gradle --no-daemon assembleDebug
```

Debug APK: `app/build/outputs/apk/debug/app-debug.apk`.

GitHub Actions builds a debug APK on pushes and pull requests. Signed release builds require the four repository Actions secrets documented in [release signing](docs/store/release-signing.md).

## Documentation

- [Build instructions](docs/BUILD.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Testing and known limitations](docs/TESTING.md)
- [Security](docs/SECURITY.md)
- [Release process](docs/RELEASE.md)
- [Privacy policy](docs/privacy-policy.md)
- [Google Play listing](docs/store/google-play.md)
- [RuStore listing](docs/store/rustore.md)
- [Hermes / OpenCode agent guide](AGENTS.md)

## Security notes

Connect to the router through a trusted LAN, VPN, or HTTPS endpoint. Plain HTTP does not encrypt credentials in transit. Never commit signing keys, passwords, router credentials, or private configuration files.

## License

See [LICENSE](LICENSE).
