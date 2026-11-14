# Testing and verification

The source baseline was imported from `feat/android-routerdash` in the former combined repository. Importing source is not proof of runtime correctness.

## Required checks
- [ ] Standalone CI debug build succeeds.
- [ ] Install on a clean Android device.
- [ ] LuCI first connection, authentication, expired session and re-authentication.
- [ ] Biometric unlock and fallback.
- [ ] Dashboard metrics, DHCP clients, disks, services, VPN, firewall and logs.
- [ ] SSH host-key first approval, reconnect and changed-key rejection.
- [ ] SFTP upload/download, conflicts and interrupted transfer.
- [ ] Confirm sync does not automatically delete files.
- [ ] SSD mount validation; no writes to overlay when SSD absent.
- [ ] Background photo upload opt-in and reboot behavior.
- [ ] Widget refresh and actions.
- [ ] Wi-Fi/VPN connectivity and unreachable-router behavior.
- [ ] Android 16 and Android 17.

Record device/OS, commit, steps, result and logs. Distinguish compile checks from runtime checks. Never report unchecked items as passed.
