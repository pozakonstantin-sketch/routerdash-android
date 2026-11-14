# Security notes

- Never commit router credentials, API tokens, SSH private keys, signing keystores or passwords.
- Never log passwords, session tokens, private keys or file contents.
- Preserve strict SSH host-key checking. Unknown keys require explicit approval; changed keys must be rejected.
- Prefer HTTPS with a valid certificate or a trusted VPN. Plain HTTP exposes credentials and session traffic.
- Keep credentials in Android Keystore-backed encrypted storage.
- File sync must not silently delete files; resolve conflicts explicitly and validate the external SSD mount before writing.
- Review permissions and background execution behavior whenever targetSdk changes.
