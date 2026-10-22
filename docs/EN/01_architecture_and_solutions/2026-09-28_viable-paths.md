# iOS 27 Viable Paths & Feasibility Evaluation

## 1. Target A: Lock Screen Footnote (Extremely High Feasibility)

### 1.1 Technical Mechanism
- **Official Specification:** Apple Device Management `com.apple.shareddeviceconfiguration`
- **Target File:**
  `/var/containers/Shared/SystemGroup/systemgroup.com.apple.configurationprofiles/Library/ConfigurationProfiles/SharedDeviceConfiguration.plist`
- **Backup Mapping:**
  - Domain: `SysSharedContainerDomain-systemgroup.com.apple.configurationprofiles`
  - RelPath: `Library/ConfigurationProfiles/SharedDeviceConfiguration.plist`
- **Payload Format:**
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

### 1.2 Delivery & Injection Channels
1. **Channel 1 (GoldenNugget 9.5 Protected Backup Injection Pipeline):**
   Directly inject the `SysSharedContainerDomain-...` record into the `Manifest.db` of an unencrypted protected backup, restored and written back via Phase 3 protected backup restore.
2. **Channel 2 (Official Configuration Profile / Supervised Mode):**
   Install via Apple Configurator or an MDM profile (`SharedDeviceConfiguration`), representing Apple's natively supported, secure approach that preserves system integrity.

---

## 2. Target B: Carrier Name (Formidable Challenges, Multi-Path Investigation)

### 2.1 Route 1: Speakeasy Disabling Fallback to Classic Status Bar
- **Status:** **Falsified / Permanently Blocked.**
- **Rationale:** Requires writing to `/var/preferences/FeatureFlags/Settings.plist`, but BackupAgent whitelisting + Security Recovery Wipe completely block non-jailbreak writes.

### 2.2 Route 2: Carrier Bundle / CommCenter Overwrite
- **Status:** **Thoroughly Falsified via On-Device Reverse Engineering & Preference Injection (Infeasible without Jailbreak).**
- **Mechanism & Falsification Evidence:**
  - Physical device testing (iPhone 14 Pro, iOS 27.0.1) verified: CommCenter runs under `_wireless` (UID 257), storing state and cache in `/var/wireless/Library/Preferences/`. Non-jailbreak backup injection targets HomeDomain (`/var/mobile/`), which is completely ignored by CommCenter.
  - System Carrier Bundles reside on the SSV (Sealed System Volume) read-only volume and are protected by strict `VerifyCarrierBundles = TRUE` validation; unsigned bundles are rejected directly by the baseband. See [`../04_research_handoffs/2026-10-19_commcenter-preference-injection.md`](../04_research_handoffs/2026-10-19_commcenter-preference-injection.md).

### 2.3 Route 3: SystemStatusUI Modern Status Bar Direct Configuration
- **Status:** Pending reverse engineering analysis.
- **Mechanism:** Analyze whether `SystemStatusUI.framework` contains undisclosed Debug / Internal Preference keys (such as reading specific plists from `com.apple.springboard` or `com.apple.SystemStatusUI`).

### 2.4 Route 4: Write Primitives Based on the bad_query Vulnerability
- **Status:** Extremely High Risk / Requires Environmental Verification.
- **Background:** `bad_query` possessed sandbox escape write primitives on iOS 27 Beta 1-4, but Apple patched the ContainerManager / HouseArrest logic in the production Release version.
- **Principle:** Running unverified PoCs on primary hardware is strictly prohibited without Release verification.

### 2.5 Route 5: Modern StatusBarOverrides.archive Archival Pipeline
- **Status:** **Formally merged into mainline and released by mainstream open-source suite (GoldenNugget v9.5.1/v9.5.2); verified end-to-end on physical hardware by developer and users.**
- **Mechanism:** SpringBoard features a built-in `SBSystemStatusStatusBarOverridesArchiver` that deserializes `STStatusBarData` from `/var/mobile/Library/SpringBoard/StatusBarOverrides.archive` and publishes it to `SystemStatusUI`.
- **Reverse Engineering Analysis & Dynamic Limitations (Definitive Findings):**
  - **Proof of Atomic Replacement**: Disassembly of `-[STStatusBarData dataByApplyingOverlay:]` (`0x20e4ac960`) proves that the override completely replaces the entire `cellularEntry` pointer as an atomic unit, with no field-level fallback. In static archives, displaying the name requires `status=5, enabled=true`; consequently, after entering Airplane Mode, the name remains statically persistent and cannot auto-hide.
  - **`--partial` Mode Evaluation**: Omitting `displayValue` / `type` defaults them to 0 during decoding, suppressing the 5G/LTE radio technology label while still failing to hide in Airplane Mode; therefore, it is not recommended for production use.
  - **VPN Indicator Loss Fix**: Earlier solutions such as early GoldenNugget injected VPN identifiers into `suppressedBackgroundActivityIdentifiers` or serialized incomplete `vpnEntry` records, causing the system VPN icon to disappear. This repository has completely resolved this issue: under the default `auto` mode, the suppressed set is cleared and `vpnEntry` is left unmentioned, allowing the system native real VPN icon to pass through 100%; explicit control is also supported via `--vpn {auto,on,off}`. See [`../04_research_handoffs/2026-10-21_dynamic-carrier-and-vpn-resolution.md`](../04_research_handoffs/2026-10-21_dynamic-carrier-and-vpn-resolution.md).
- **Delivery Channels:**
  - **Channel A (GoldenNugget HomeDomain Backup Restore Pipeline, Officially Recommended):** This archive file belongs to `HomeDomain` and can be delivered directly into the system via standard `MobileBackup2` restore without jailbreak or exploit escapes, completely bypassing AirTraffic's rename overwrite restrictions. It has been merged into GoldenNugget mainline (v9.5.1+) and fully tested on physical hardware.
  - **Channel B (AirLift Standalone Channel):** Written via the AirTraffic Books sync pipeline; subject to ATAirlock rename overwrite limitations, requiring reliance on initial installation or empty-archive self-deletion reset mechanisms (`--force-overwrite`).
  - **Channel C (CoreSimulator):** Direct host filesystem write; format deserialization and status bar UI rendering have both been empirically verified.
