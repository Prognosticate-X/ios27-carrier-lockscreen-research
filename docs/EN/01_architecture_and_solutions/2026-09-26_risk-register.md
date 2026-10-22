# iOS 27 Customization Research Risk Register & Safety Red Lines

## 1. Core Safety Principles

The user's current device is an **iPhone 16 Pro Max (A18 Pro), iOS 27.0 Release production primary daily driver**. All operations must strictly adhere to the following bottom lines:

1. **Zero Blind Testing Principle:** Strictly prohibit directly executing unverified legacy Nugget Restores or unreviewed binary tools on the primary device.
2. **Zero High-Risk Directory Writing:** Strictly avoid performing sparse restores into sensitive system areas such as `/var/preferences`, `/var/keychains`, etc., to prevent triggering the iOS 27 Security Recovery Wipe (causing Apple ID, lock screen passcode, keychain, and photos to be securely wiped by the system).
3. **Staged and Reversible Principle:** Prior to any on-device testing, full local unencrypted/encrypted device backups must be established; every write operation must record the original file SHA256 and a verified rollback plan.

---

## 2. Risk Register

| Risk ID | Risk Scenario | Severity | Potential Consequences | Prevention & Mitigation Measures |
|---|---|---|---|---|
| **R01** | Directly executing original Nugget Partial Restore on iOS 27 | **Critical** | Triggers system security state recovery, complete data wipe, or bootloop | Forcibly intercept original Nugget workflows; permit only static code analysis and protected backup mechanisms. |
| **R02** | Blindly attempting to overwrite `/var/preferences/FeatureFlags` | **Critical** | BackupAgent error blocking or triggers security wipe | Confirmed unviable in code and historical testing; flagged as permanently blocked, no further attempts. |
| **R03** | Running Beta 4-oriented `bad_query` escape scripts | **High** | Process crash, kernel panic, or sandbox integrity violation | Must first test on non-primary hardware or perform patch diffs on firmware binaries; strictly prohibited on primary device. |
| **R04** | Writing a corrupted `SharedDeviceConfiguration.plist` | **Medium** | SpringBoard fails to parse footnote text or temporary lock screen freeze | Strictly validate format via `plistlib` prior to writing, ensuring only standard Key-Value pairs are injected. |
