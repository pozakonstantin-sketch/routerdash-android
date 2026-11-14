# Architecture

RouterDash is a native Kotlin Android application and communicates directly with the router; it does not embed the LuCI dashboard in a WebView.

- `MainActivity.kt`: application UI and router interaction flows.
- `FileSync.kt`: SFTP file comparison and transfer logic.
- `AutoPhotoSync.kt`: optional background photo upload.
- `RouterDashWidgetProvider.kt`: Android home-screen widget.
- `AndroidManifest.xml`: components and Android permissions.
- `res/`: launcher and widget resources.

Router data uses LuCI JSON-RPC/ubus. SSH terminal and file transfer use SSH/SFTP. Network reachability is provided by the user's LAN or VPN.

Package: `ru.routerdash.android`; imported baseline: 2.5.1 (versionCode 12).
