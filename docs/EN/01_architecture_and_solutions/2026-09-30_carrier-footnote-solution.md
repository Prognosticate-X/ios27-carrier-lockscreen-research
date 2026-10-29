# iOS 27.0 Lock Screen Carrier Name & Lock Screen Footnote Definitive Research Solution & Technical Verdict Report

> ⚠️ **Superseded (2026-10-28)**: The carrier-name verdict in this report (“Pending Physical Verification”) was superseded by the 2026-10-19 / 2026-10-21 physical experiments and disassembly. Use the [2026-10-28 roadmap](../04_research_handoffs/2026-10-28_next-research-roadmap.md) and the [2026-10-21 final verdict](../04_research_handoffs/2026-10-21_dynamic-carrier-and-vpn-resolution.md) instead; this document is retained as the historical evidence chain.

> **Target Device**: iPhone 16 Pro Max (A18 Pro)  
> **Operating System**: iOS 27.0 Release / Build `24A437`  
> **Verification Baseline**: Non-jailbroken environment, primary device zero-risk safety guidelines, source-level audit, and runtime reflection  
> **Report Date**: 2026-09-28  

---

## 1. Executive Summary

Addressing the two system UI customization targets on the iPhone 16 Pro Max (A18 Pro) running **iOS 27.0 Final (24A437)**, static reverse engineering audits were conducted across the **AirLift** sandbox escape mechanism, **AirCard-iOS** runtime implementation, **GoldenNugget-Team / phanquocviet8x** dual-fork source diffs, and system dyld shared cache binaries (`CoreTelephony`, `SystemStatus`, `SystemStatusUI`, `SpringBoard`). The definitive technical verdicts are as follows:

| Customization Target | Verdict Status | Tag | Core Conclusion & Technical Rationale |
|---|---|---|---|
| **Lock Screen Footnote** | **Fully Viable** | `Confirmed` | Governed by Apple's official device management architecture (`com.apple.shareddeviceconfiguration`). Operates stably on iOS 27.0 Final via official `.mobileconfig` configuration profile or protected backup injection (Manifest.db injection) without requiring any jailbreak or high-risk privilege escalation. (Note: Specific enterprise environments may require Supervised Mode). |
| **Carrier Name Override** | **Major Discovery (Pending Physical Verification)** | `Hypothesis (Simulator Verified, Physical Unconfirmed)` | **Format validity confirmed via iOS 27 dynamic reverse engineering and simulator verification**! The root cause of legacy tool failures lies in writing the obsolete 3944-byte C-struct (`statusBarOverrides`) deprecated in iOS 27. iOS 27 adopts a modern `NSKeyedArchiver` archive at `/var/mobile/Library/SpringBoard/StatusBarOverrides.archive`. SpringBoard natively parses this archive via `SBSystemStatusStatusBarOverridesArchiver` and publishes it to `SystemStatusUI`. Owned by `mobile:mobile`, this file resides within AirLift's permitted write domain. **However, physical hardware deployment is constrained by AirTraffic ATAirlock's rename overwrite limitation (inability to trivially overwrite existing files); the physical device end-to-end pipeline still requires empirical verification and cannot be asserted as an accomplished fact.** |

---

## 2. Device / Build (Target Device & System Baseline)

- **Device**: iPhone 16 Pro Max (`iPhone17,2`)
- **SoC**: Apple A18 Pro (`T8140`) / `arm64e`
- **OS**: iOS 27.0 Release (Final)
- **Build Number**: `24A437`
- **Device Role**: User's primary daily driver, strictly enforcing the highest level of data loss and wipe prevention policies.

---

## 3. Current iOS 27 Architecture (iOS 27 Status Bar & Configuration Architecture Landscape)

```text
                                      iOS 27.0 Final (24A437)
                                                 │
        ┌────────────────────────────────────────┴────────────────────────────────────────┐
        ▼                                                                                 ▼
【Lock Screen Footnote】                                                          【Carrier Name Pipeline】
  (Bottom Lock Screen Footnote)                                                     (Top Status Bar Carrier Display)
        │                                                                                 │
  Apple Profile Domain                                                             SpringBoard Startup
  com.apple.shareddeviceconfiguration                                                     │
        │                                                                SBSystemStatusStatusBarOverridesArchiver
  SharedDeviceConfiguration.plist                                                (_queue_readStatusBarOverridesArchiveRecord)
        │                                                                                 │
  ┌─────┴────────────────────────┐                                            ┌───────────┴───────────┐
  ▼                              ▼                                            ▼                       ▼
Official Profile Channel     Protected Backup Injection Pipeline       [Modern Archive File] (Newly Discovered) [Legacy C-Struct File]
(.mobileconfig)          (SysSharedContainerDomain)              StatusBarOverrides.archive    statusBarOverrides
  │                              │                               (NSKeyedArchiver bplist)       (3944B Raw Binary)
  └──────────────┬───────────────┘                                            │                       │
                 ▼                                                            ▼                       ▼
      SpringBoard Lock Screen Render                             STStatusBarOverridesDomain     SpringBoard Ignored
       (Instant effect, zero risk)                                      Publisher Pipeline        (Legacy format deprecated)
                                                                              │
                                                                       SystemStatusUI
                                                                              │
                                                                      Status Bar Carrier Text Render
                                                                  (AirLift Writable / Owned by mobile)
```

---

## 4. AirLift Analysis (In-Depth AirLift Sandbox Escape Analysis)

- **Project Source**: `0xjohnnydev/airlift`
- **Operating Principle**: Sandbox escape exploiting path validation defects in the iOS 27.0 media transfer pipeline (AirTraffic / Books sync service).
- **Vulnerability Root Cause**:
  In `-[ATAirlock processCompletedAsset:]`, the Books sync asset identifier (`asset.identifier`) directly accepts the `Persistent ID` supplied by macOS `Books.plist` without validating for `..` relative path traversals:
  ```objc
  NSString *source = [@"/var/mobile/Media/Airlock/Book" stringByAppendingPathComponent:asset.identifier];
  NSString *destination = [[@"/var/mobile/Media/" stringByAppendingPathComponent:asset.path] stringByStandardizingPath];
  if (![destination hasPrefix:@"/var/mobile/Media/"]) return;
  [fileManager moveItemAtPath:source toPath:destination error:&error];
  ```
  By crafting symlinks targeting `../../../target` (`p0/p1/p2/link`) within a customized Zip package, the two-phase asset movement causes the target payload to traverse the symlink and write outside the sandbox directory.
- **Permissions & Scope Boundaries**:
  - **Execution Identity**: `mobile:mobile` (uid 501, gid 501).
  - **Permitted Write Paths**:
    - `/var/mobile/Library/SpringBoard` (Default AirLift target)
    - `/var/mobile/Library/Preferences`
    - `/var/mobile/Containers/Data/Application`
    - `/var/mobile/Containers/Shared/AppGroup`
    - `/var/tmp`
  - **Strictly Blocked Paths**:
    - Cannot write to `/var/preferences` (owned by `root:wheel`).
    - Cannot modify `com.apple.MobileGestalt.plist`.
    - Cannot penetrate non-mobile system shared group containers `/var/containers/Shared/SystemGroup/`.

---

## 5. AirCard-iOS Analysis (AirCard-iOS Integration Analysis)

- **Project Source**: `EpochME/aircard-ios`
- **Technical Substance**: Encapsulates low-level AirLift primitives as `AirliftFFI.xcframework`, combining with iOS 27.0 local Developer Mode and Bonjour pairing capabilities to achieve on-device elevated file writes without an external computer.
- **Covered Features**: Apple Pay card face replacement (Passbook cache writing), lock screen dialer keypad theming, and PosterBoard wallpaper database modification.
- **Relevance to Current Task**:
  The success of AirCard-iOS demonstrates the **stability of AirLift writes within `/var/mobile`**; however, its customization points are exclusively concentrated in user-level caches and application data containers, and **it cannot cross boundaries to alter configurations of system daemons (CommCenter / FeatureFlags)**.

---

## 6. GoldenNugget Diff (Comparative Audit of Both GoldenNugget Codebases)

A complete branch comparison conducted between `GoldenNugget-Team/GoldenNugget` and `phanquocviet8x/GoldenNugget` revealed:

1. **Git Topology Facts**:
   - Fork B (`phanquocviet8x`) HEAD commit is `0c449b9` (Tag 8.3).
   - Fork A (`GoldenNugget-Team`) is 270+ commits ahead, currently at `8de3c60` (Tag 9.5+).
   - Fork B is a direct ancestor node in Fork A's commit history; Fork B contains **no original or custom added code**.
2. **"patched on iOS 27" Semantic Reality**:
   - Commit trace: Commit `c37b709` (author `awesomenull`), commit message `revert readme.md`.
   - Context in English: **"Status Bar (patched on iOS 27)"** signifies that **"the status bar mechanism was patched/blocked by Apple on iOS 27"**, serving as a statement of a known defect rather than a patch added by the tool.
3. **Code Logic Verification**:
   In `status_bar_tweak.py`, encountering iOS 27.0+ executes a direct `return flag_plist` (no-op). Neither codebase can modify the status bar on iOS 27.0 Release.

---

## 7. Carrier Name Reverse Engineering (Carrier Name Reverse Engineering Analysis)

Reflective reverse engineering performed against the iOS 27 / macOS 27 dyld shared cache and runtime frameworks (`CoreTelephony`, `SystemStatus`, `SystemStatusServer`, `SystemStatusUI`) established the complete data chain:

1. **Origin**: SIM card internal `EF_SPN` / `EF_PNN` parsed by the cellular baseband.
2. **Master Control**: `CommCenter` daemon loads the Carrier Bundle and merges SIM metadata to produce the final Operator Name.
3. **Distribution**: `CoreTelephony` answers SpringBoard's XPC queries (`CTXPCGetOperatorNameResponse`).
4. **Publishing**: SpringBoard's Telephony module calls `STStatusDomainPublisher.updateDataWithBlock:`, registering `STTelephonyStatusDomainData` with `STLocalStatusServer`.
5. **Consumption**: `SystemStatusUI.framework` subscribes to domain events, driving `_UIStatusBarCellularItem` to render the carrier string.

---

## 8. statusBarOverrides (Empirical Status of Legacy Override File)

- **Physical Path**: `/var/mobile/Library/SpringBoard/statusBarOverrides`
- **Format**: C structure `StatusBarOverrideData` (containing the `serviceString` field).
- **AirLift Write Capability**: `Confirmed`. AirLift can write this binary file into the SpringBoard directory.
- **System Read Status**: `Not Working`. SpringBoard enforces Speakeasy by default on iOS 27.0; the main execution flow completely bypasses this file.

---

## 9. Speakeasy (Gating Mechanism & FeatureFlags Lockdown)

- **Gating Pseudo-code**:
  ```objc
  if (isEnabled("SpringBoard", "Speakeasy") || isEnabled("SpringBoard", "SpeakeasyNewStatusBar")) {
      use SystemStatusUI;          // Modern status bar
  } else {
      use Classic Status Bar;      // Classic status bar, reads statusBarOverrides
  }
  ```
- **Hardcoded Storage**: `FeatureFlags.framework` reads exclusively from `/var/preferences/FeatureFlags/Settings.plist`.
- **Fourfold Blockade**:
  1. AirLift cannot write to `/var/preferences` (permissions restricted to `mobile`).
  2. BackupAgent2 whitelist blocks access (restricted to only 10 system files).
  3. Sparse restore triggers iOS 27 Security Recovery Wipe (clears `/var/preferences` and causes data loss).
  4. CoreFoundation preferences (cfprefs / MCX) are completely ignored by the framework.

---

## 10. SystemStatusUI (Modern UI Consumer Analysis)

- **Pure In-Memory Bus**: `SystemStatusUI` functions as a view listener built upon `STStatusDomain`, with no architectural design for reading plist files from disk.
- **Infeasible via File Modification**: Carrier text displayed on the status bar is dynamically generated by `CommCenter` and dispatched onto the in-memory bus. In the absence of dynamic memory injection or runtime hooking (i.e., in a non-jailbroken state), carrier text published to the UI cannot be intercepted or modified on disk.

---

## 11. LockScreenFootnote (Lock Screen Footnote In-Depth Mechanism)

- **Official Specification**: Apple MDM `com.apple.shareddeviceconfiguration`
- **Target File**:
  `/var/containers/Shared/SystemGroup/systemgroup.com.apple.configurationprofiles/Library/ConfigurationProfiles/SharedDeviceConfiguration.plist`
- **File Content**:
  ```xml
  <?xml version="1.0" encoding="UTF-8"?>
  <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
  <plist version="1.0">
  <dict>
      <key>LockScreenFootnote</key>
      <string>Custom Lock Screen Text</string>
  </dict>
  </plist>
  ```
- **Activation Mechanism**: SpringBoard natively parses this key-value pair and renders it directly above the bottom Home Bar on the lock screen. Requires no jailbreak and introduces zero risk of security wipes.

---

## 12. File Paths (Quick Reference of Critical System Absolute Paths)

| Logical Identifier | Absolute Device Path | Owner & Permissions | Access Viability (AirLift) |
|---|---|---|---|
| `statusBarOverrides` | `/var/mobile/Library/SpringBoard/statusBarOverrides` | `mobile:mobile` (0644) | **Read/Write** (Ignored by system) |
| `FeatureFlags` | `/var/preferences/FeatureFlags/Settings.plist` | `root:wheel` (0644) | **Inaccessible** (Boundary exceeded) |
| `Carrier Bundle Overlay` | `/var/mobile/Library/Carrier Bundles/Overlay/` | `mobile:mobile` (0755) | **Writable** (Signature validation failure causes "No Service") |
| `Footnote (Shared)` | `/var/containers/Shared/SystemGroup/systemgroup.com.apple.configurationprofiles/Library/ConfigurationProfiles/SharedDeviceConfiguration.plist` | `mobile:mobile` (0644) | **Restricted** (System group container; Profile/Backup recommended) |

---

## 13. Required Permissions (Required Permissions & Boundaries)

- **Permissions Granted by AirLift**: `mobile` user permissions (sandbox escape tier, non-root, non-kernel).
- **Permissions Required for Carrier Name Override**:
  - Path A (Disable Speakeasy): Requires `root` permissions to write to `/var/preferences` while evading boot-time Security Recovery self-checks.
  - Path B (Tamper with Carrier Bundle): Requires kernel-level code execution or `CommCenter` process injection to bypass Apple root certificate signature checks (`CommCenterPatch`).
- **Permissions Required for Footnote**: Standard configuration profile authorization, or standard unencrypted user backup restore permissions.

---

## 14. Working Methods (Confirmed Working Solutions)

### Solution: Lock Screen Footnote Official Configuration Profile / Backup Injection Customization
- **Viability**: `Confirmed`
- **Method 1 (Computer-Free Configuration Profile)**:
  Install a signed `.mobileconfig` profile containing `com.apple.shareddeviceconfiguration` using Apple Configurator or directly via Safari.
- **Method 2 (Protected Backup Pipeline)**:
  Utilize GoldenNugget 9.5 to inject the constructed `SharedDeviceConfiguration.plist` into the unencrypted backup's `Manifest.db` (mapped as `SysSharedContainerDomain-systemgroup.com.apple.configurationprofiles`), followed by a Phase 3 restore.

---

## 15. Failed Methods (Catalogue of Confirmed Failed/Blocked Paths)

| Attempted Path | Failure Reason | Final Status |
|---|---|---|
| **AirLift writing statusBarOverrides** | SpringBoard enables Speakeasy by default and never reads this file | `Not Working` |
| **AirLift modifying FeatureFlags** | `/var/preferences` is owned by root, exceeding AirLift's mobile permissions | `Not Working` |
| **Nugget legacy sparse restore writing FeatureFlags** | Triggers iOS 27 Security Recovery Wipe, wiping `/var/preferences` entirely | `Not Working` |
| **Tampering with Carrier Bundle Overlay** | CommCenter enforces strict digital signature checks at launch; invalid signatures break baseband, causing "No Service" | `Not Working` |
| **GoldenNugget Fork B status bar customization** | Code contains hardcoded return (no-op) for iOS 27.0+ | `Not Working` |

---

## 16. Device Compatibility (Device Compatibility Evaluation)

- **iPhone 16 Pro Max / A18 Pro (24A437)**:
  - Lock Screen Footnote: **100% compatible and supported** (Based on official configuration profile specification; specific policies requiring Supervised Mode can pair with Configurator).
  - Carrier Name Override: **Simulator verified; physical device remains in experimental phase (`Hypothesis / Unconfirmed on Physical Devices`)**. Core challenges center on ATAirlock file overwrite limits and physical AirTraffic sync pipeline reliability.
- **A18 Pro Hardware Security Attributes**: Hardware-enforced PAC and PPL eliminate the feasibility of blindly spraying userland memory to alter SpringBoard.

---

## 17. Risk Assessment (Risk Level Evaluation)

| Operation Item | Risk Level | Potential Hazard | Mitigation & Prevention Strategy |
|---|---|---|---|
| Install Footnote Profile | **Minimal** | Text layout aesthetic mismatch | Remove profile in Settings for instant restoration |
| Protected Backup Injection for Footnote | **Low** | Restore process takes ~3 minutes | Maintain full unencrypted backup for immediate rollback |
| Attempt AirLift overwrite of Carrier Bundle | **High** | Cellular disconnect, SIM unrecognized | **Strictly prohibited on primary device** |
| Attempt sparse restore write to FeatureFlags | **Critical** | Triggers system security wipe, losing Apple ID and photos | **Absolutely prohibited** |

---

## 18. Backup / Recovery (Backup & Safety Assurance Procedures)

Prior to conducting any operation on the primary iPhone 16 Pro Max:
1. **Full Encrypted Backup**: Perform a complete local backup containing keychain and passwords using Finder / Apple Devices.
2. **Record Device Snapshot**:
   ```text
   Device: iPhone 16 Pro Max (iPhone17,2)
   iOS Build: 24A437
   Baseband Version: 1.00.07 (or current version)
   Pairing UDID: Record for reference
   ```

---

## 19. Step-by-Step Experiment: Lock Screen Footnote Verification Workflow

### Step 1: Generate Configuration Payload
Author a compliant `SharedDeviceConfiguration.plist`:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>LockScreenFootnote</key>
    <string>Prognosticate-X · iOS 27.0</string>
</dict>
</plist>
```

### Step 2: Generate Distributable Configuration Profile `footnote.mobileconfig`
Wrap into a standard Profile Payload:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>PayloadContent</key>
    <array>
        <dict>
            <key>PayloadType</key>
            <string>com.apple.shareddeviceconfiguration</string>
            <key>PayloadVersion</key>
            <integer>1</integer>
            <key>PayloadIdentifier</key>
            <string>com.prognosticate.footnote</string>
            <key>PayloadUUID</key>
            <string>A1B2C3D4-E5F6-7A8B-9C0D-1E2F3A4B5C6D</string>
            <key>LockScreenFootnote</key>
            <string>Prognosticate-X · iOS 27.0</string>
        </dict>
    </array>
    <key>PayloadDisplayName</key>
    <string>Lock Screen Footnote</string>
    <key>PayloadIdentifier</key>
    <string>com.prognosticate.profile</string>
    <key>PayloadType</key>
    <string>Configuration</string>
    <key>PayloadUUID</key>
    <string>B2C3D4E5-F6A7-8B9C-0D1E-2F3A4B5C6D7E</string>
    <key>PayloadVersion</key>
    <integer>1</integer>
</dict>
</plist>
```

### Step 3: Installation and Verification
1. Send to iPhone 16 Pro Max via AirDrop.
2. Navigate to "Settings" ➔ "Profile Downloaded" ➔ Tap "Install".
3. Lock and wake the screen; verify the custom footnote text renders above the bottom Home Bar.

---

## 20. Rollback Procedure (Rollback & Restoration Steps)

- **Profile Rollback**:
  Navigate to iPhone "Settings" ➔ "General" ➔ "VPN & Device Management" ➔ Select `Lock Screen Footnote` ➔ Tap "Remove Profile". The lock screen text reverts immediately to default.
- **Backup Injection Rollback**:
  If applied via the backup injection pipeline, simply clear the `LockScreenFootnote` key in the plist and perform another restore, or restore the original protected backup.

---

## 21. Final Conclusion (Technical Verdict & Summary)

1. **Verdict on Carrier Name (Major Breakthrough but Pending Physical Verification)**:
   On **iOS 27.0 Release (24A437)**, CoreSimulator runtime reverse disassembly and dynamic injection verification proved that **Carrier Name customization can take effect via modern persisted archives**:
   - Historically, open-source communities (GoldenNugget, etc.) wrote the obsolete 3944-byte legacy C-struct (`statusBarOverrides`), leading SpringBoard to ignore it and creating the false assumption that it was permanently blocked by Speakeasy.
   - The truly valid payload format is `StatusBarOverrides.archive` serialized via `NSKeyedArchiver`, containing `_SBSystemStatusStatusBarOverridesArchiveRecord` and `STStatusBarDataCellularEntry`.
   - The physical filesystem path `/var/mobile/Library/SpringBoard/StatusBarOverrides.archive` is owned by `mobile:mobile`, which resides inside **AirLift's (AirTraffic Books escape pipeline)** permitted write domain, requiring no root elevation and zero modifications to `FeatureFlags`.
   - **Key Constraints & Objective Reality**: Physical device deployment is constrained by the rename mechanism utilized by ATAirlock (inability to directly overwrite existing destination files). Therefore, end-to-end physical device deployment and rollback mechanisms require further empirical testing; this conclusion is currently categorized as `Hypothesis (Simulator Verified, Physical Device Unconfirmed)`.
   - The standard payload generator tool `tools/generate_statusbar_archive.py` has been implemented, enabling one-click generation and packaging verification within a safe, isolated environment.

2. **Verdict on Lock Screen Footnote (Fully Viable)**:
   Without jailbreak and without relying on any exploit tools, utilizing Apple's official `com.apple.shareddeviceconfiguration` architecture delivers the 100% customization objective stably, safely, and elegantly. Installing via an official `.mobileconfig` profile takes effect immediately (supervised mode can be paired via Configurator for enterprise-restricted devices).
