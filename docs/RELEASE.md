# Release process

1. Verify CI and complete the device checklist in [TESTING.md](TESTING.md).
2. Increment `versionCode` and confirm version metadata.
3. Confirm the intended long-term signing certificate.
4. Configure the four Actions secrets described in [store/release-signing.md](store/release-signing.md).
5. Create a tag such as `android-v2.5.2` only after owner approval.
6. Run the release workflow and verify APK/AAB signatures and SHA-256 sums.
7. Review store listing, privacy policy, screenshots and Data safety declarations.
8. Do not publish without explicit owner approval.

Secrets from the previous repository are not copied automatically.
