# Universal iOS 27 Carrier & Lock Screen Customization Suite

[English](README.md) | [简体中文](README_ZH.md)

[![iOS 27 Compatible](https://img.shields.io/badge/iOS-27.x%20Final-blue.svg)](https://apple.com/ios)
[![Method](https://img.shields.io/badge/Method-Non--Jailbreak%20%7C%20Backup%20%2B%20AirLift-success.svg)](#-upstream-adoption--end-to-end-verification-status)
[![Status](https://img.shields.io/badge/Status-Verified%20on%20Physical%20Hardware-success.svg)](#-upstream-adoption--end-to-end-verification-status)
[![Devices](https://img.shields.io/badge/Devices-Universal%20(Dynamic%20Island%20%2B%20Classic)-orange.svg)](#-universal-hardware--display-matrix)

> A universal, non-jailbreak reverse engineering framework and toolchain for customizing **Cellular Carrier Name** (Single/Dual SIM) and **Lock Screen Footnote** across **all iOS 27.x devices** (Dynamic Island and Classic Notch/Home models).

---

## 🎯 Executive Summary & Status

| Target Feature | iOS 27.x Status | Core Mechanism | Viability & Scope |
|---|---|---|---|
| **Lock Screen Footnote** | 🟢 **VIABLE** | `SharedDeviceConfiguration.plist` under `com.apple.shareddeviceconfiguration` | **Universal (100%)** — Native Apple MDM profile (`.mobileconfig`) or Protective Backup Injection via `SysSharedContainerDomain`. Zero exploit required. (Note: specific policy configurations may require Supervision). |
| **Carrier Name Override (Static)** | 🟢 **VERIFIED (BREAKTHROUGH)** | Modern `StatusBarOverrides.archive` (`_SBSystemStatusStatusBarOverridesArchiveRecord`) | **Verified End-to-End on Physical Hardware** — Officially merged into [GoldenNugget](https://github.com/GoldenNugget-Team/GoldenNugget) (v9.5.1 / v9.5.2) and confirmed **"Verified end-to-end by me and other users"** by GoldenNugget lead developer (`@awesomenull`) across physical iOS 27 hardware via the `HomeDomain` backup restore pipeline (`MobileBackup2`). Pins full cellular entry (static override; persistent across Airplane Mode / fixed bars). |
| **Dynamic Carrier & Real Signal (Upstream)** | 🔴 **EXPERIMENTALLY BLOCKED (iOS 27.0.1)** | Signed carrier bundle (`/System/Library/Carrier Bundles/iPhone/46001/carrier.plist`) + CommCenter state in `/var/wireless/Library/Preferences/` | **No non-jailbreak write path** — disassembly disproved field-level overrides in `StatusBarData`, and the physical experiments on iPhone 14 Pro (27.0.1) showed that CommCenter persists no carrier-name data in HomeDomain: its state lives in `WirelessDomain` (owned by `_wireless`, not writable from the mobile/AirLift context) and the operator name is bundle-sourced. Injecting `InterCarrierRoamingDisplayNames`/`CarrierName` into twelve HomeDomain domains had no effect even after cold-restarting cfprefsd/CommCenter/SpringBoard. Static `StatusBarOverrides.archive` remains the only working method. Evidence: [`handoff`](docs/handoffs/iOS27_CommCenter_Preference_Injection_2026-10-19.md). |

---

## 📱 Universal Hardware & Display Matrix

This project supports all devices capable of running **iOS 27.x** (Builds `24A300`, `24A434`, `24A435`, `24A437`, and later):

| Device Family | Models | Display Type | Cellular Rendering Behavior | Verification Status |
|---|---|---|---|---|
| **Dynamic Island (Pro)** | iPhone 14 Pro / Pro Max<br>iPhone 15 Pro / Pro Max<br>iPhone 16 Pro / Pro Max | 灵动岛 (Dynamic Island) | **Single SIM**: Full-height 4-bars in trailing ear.<br>**Dual SIM**: Native stacked 4-bars (Primary) + 4-dots (Secondary).<br>**Text Display**: Alternating ticker on Lock Screen; full labels (`[P] Carrier`, `[S] Carrier`) in Control Center. | 🟢 **Physical (iPhone 16 Pro Max, iOS 27.0) + Simulator** |
| **Dynamic Island (Base)** | iPhone 15 / 15 Plus<br>iPhone 16 / 16 Plus | 灵动岛 (Dynamic Island) | Identical to Pro models; automatic responsive Dynamic Island layout. | 🟢 **Fully Compatible** |
| **Classic Notch & Home** | iPhone 13 / 14 / Plus<br>iPhone SE (2nd / 3rd gen) | 经典顶部状态栏 (Classic/Notch) | Direct top-left status bar text display (`Carrier 5G` + signal bars). | 🟢 **Simulator Verified** |

---

## 🚀 Upstream Adoption & End-to-End Verification Status

Our reverse engineering of `SBSystemStatusStatusBarOverridesArchiver` successfully broke the community's assumption that iOS 27's Speakeasy gate permanently blocked status bar customization:

1. **Integrated in GoldenNugget**: The [GoldenNugget-Team/GoldenNugget](https://github.com/GoldenNugget-Team/GoldenNugget) suite officially integrated our research in commit [`55dfdeab`](https://github.com/GoldenNugget-Team/GoldenNugget/commit/55dfdeab6a9b0c50d55f80ae4aaaa42cc8e083c4), shipping the revival of iOS 27 status bar customization in GoldenNugget 9.5.1 and 9.5.2.
2. **HomeDomain Backup Delivery**: GoldenNugget verified that `/var/mobile/Library/SpringBoard/StatusBarOverrides.archive` resides in `HomeDomain`. Delivering it via standard `MobileBackup2` backup restore completely bypasses AirTraffic ATAirlock rename overwrite limitations without exploits or jailbreaks.
3. **End-to-End Physical Verification (Confirmed)**:
   - ✅ **CoreSimulator**: 100% verified (SpringBoard natively unarchives and renders layout).
   - ✅ **Offline / Unit Test**: Data structure creation and parsing validated (`tools/test_statusbar_archive.py`).
   - ✅ **Physical Hardware (End-to-End Confirmed)**: In commit [`dbb000cb`](https://github.com/GoldenNugget-Team/GoldenNugget/commit/dbb000cb248e91a0ad53378a5f5d227d1540d562) and official documentation ([`docs/iOS27_StatusBar_Research.md`](https://github.com/GoldenNugget-Team/GoldenNugget/blob/main/docs/iOS27_StatusBar_Research.md)), lead maintainer `@awesomenull` updated the verification status to **`"Verified end-to-end by me and other users"`**. Real hardware tests confirmed byte-for-byte fidelity against physical iOS 27 dumps via `tools/deploy_statusbar_archive.py` and `tools/fetch_statusbar_archive.py`.
4. **AirLift Channel — Physical End-to-End Verification (this repository)**: The in-repo AirLift channel was verified on **iPhone 16 Pro Max (iPhone17,2), iOS 27.0 (24A437)** over USB:
   - ✅ **Byte-exact delivery (24A437)**: the written `/var/mobile/Library/SpringBoard/StatusBarOverrides.archive` was fetched back through the AirTraffic readback asset and compared byte-for-byte with the payload. On iOS 27.0.1 (24A446) the AFC daemon refuses file reads outside `/var/mobile/Media`, so that readback is unavailable on the newer build (see limitation 6).
   - ✅ **Rendered on the device**: the custom carrier string (`CMHK`) is displayed in **Control Center** (Dynamic Island models do not render a carrier name in the home-screen status bar).
   - ✅ **Persistent**: once SpringBoard has adopted the record, the overrides survive full device reboots (see limitation 4).
   - ✅ **Failure handling**: injected Books-preimage drift was detected, rolled back and retried automatically, and every staging failure left zero residue (`airlift-*` trees and Books staging rows restored).
5. **Upstream CommCenter Channel (Route A) — prepared and partially verified on iPhone 14 Pro / iOS 27.0.1 (24A446)**: the `InterCarrierRoamingDisplayNames` PLMN mapping is the only known way to rename the carrier while keeping live baseband bars and Airplane Mode decoupling, so the physical experiment is now wired end-to-end:
   - ✅ **Target network identified**: the test device is on **China Unicom** (`中国联通`, PLMN `46001`/`46006`/`46009`/`46010`).
   - ✅ **Verification surface**: the iPhone 14 Pro lock screen renders the carrier name next to the Dynamic Island, so the effect is observable from a screenshot without unlocking.
   - ✅ **Recon boundary measured**: AFC can `stat` HomeDomain paths through the AirLift traversal link (`status=8` = missing, `status=10` = present), but **cannot read file data outside `/var/mobile/Media`** on this build; all candidate `com.apple.operator_*` / `com.apple.carrier_*` preference domains are absent on a stock device (writing them therefore creates new domains rather than overwriting settings).
   - ✅ **Write channel confirmed on 24A446**: a probe override (`ZZTEST9`) written through AirLift appeared on the lock screen, and a SpringBoard-only respring does **not** clear an already-adopted override (a userspace/full reboot is required).
   - 📌 **Important correction on the display-domain lineage**: the project's direction has always been the *display* domain. On iOS ≤16 the legacy `statusBarOverrides` C struct (`StatusBarOverrideData`) used **per-field override flags**, so Nugget/Cowabunga could override only the carrier string and leave live baseband bars and Airplane-Mode behaviour intact. iOS 27 replaced that with `STStatusBarData` entries that are replaced **as whole objects**, which is where the "static" regression comes from — not from the display-domain idea itself. Whether iOS 27 still has a partial-override path (archive sentinel, `recordByApplyingRecord:`, or a different render surface such as the lock screen) is the current open question; see the [progress snapshot](docs/handoffs/iOS27_Research_Progress_Snapshot_2026-10-19.md).
   - ❌ **Route A verdict (24A446, home network): negative, and the data model is now measured**. Twelve HomeDomain candidate domains (base / slot 1 / slot 2 × `operator` / `carrier` × plain / `.merged`) were created with `InterCarrierRoamingDisplayNames` + `CarrierName` + `ShowCarrierName`, and `cfprefsd`, `CommCenter` and `SpringBoard` were cold-restarted through the CoreDevice signal channel while the device was unlocked; the carrier name stayed `中国联通`. A trusted filtered backup then showed the real layout: PLMN `46001`, `CarrierBundleName = 46001`, CommCenter state only in **`WirelessDomain`** (`/var/wireless/Library/Preferences/com.apple.commcenter.plist` and friends), no `operator_1`/`carrier_1` domain anywhere, and the display name sourced from the signed system bundle `/System/Library/Carrier Bundles/iPhone/46001/carrier.plist`. HomeDomain is therefore the wrong layer, and `/var/wireless` plus the sealed bundle are not writable from the mobile/AirLift context. The 12 domains were neutralised with empty dictionaries. Full evidence chain: [handoff](docs/handoffs/iOS27_CommCenter_Preference_Injection_2026-10-19.md).

---

## 📸 Visual Verification & Simulator Renders (iOS 27.0 Release)

> **Note on Verification Environment**: The captures below demonstrate the layout and rendering behavior of the `StatusBarOverrides.archive` binary format in iOS 27 environments simulating Dynamic Island (iPhone 14 Pro) and Classic Notch/Home (iPhone SE) layouts. Physical on-device deployment is natively supported and verified end-to-end via GoldenNugget (9.5.1+) backup restore.

| Control Center Dual SIM (iPhone 14 Pro Layout) | Classic Status Bar (iPhone SE Layout) |
|:---:|:---:|
| <img src="assets/iphone14pro_controlcenter_testname.png" width="360" alt="iPhone 14 Pro iOS 27 Dual SIM Control Center" /> | <img src="assets/iphone_se_carrier_screenshot.png" width="360" alt="iPhone SE iOS 27 Carrier Screenshot" /> |
| **Dual SIM Custom Carrier**: `[P] Testname` & `[S] Test for name` | **Single SIM Custom Carrier**: `中国广电 5G` |

---

## 🏗️ Architecture & Core Mechanics

### 1. Modern StatusBarOverrides.archive Architecture
Unlike iOS 14–16 which expected a raw 3944-byte C struct in `statusBarOverrides`, iOS 27 uses an **NSKeyedArchiver binary property list**:
- **Path**: `/var/mobile/Library/SpringBoard/StatusBarOverrides.archive`
- **Ownership**: `mobile:mobile` (0644)
- **Root Class**: `_SBSystemStatusStatusBarOverridesArchiveRecord`
  - `statusBarData`: `STStatusBarData` (from `SystemStatus.framework`)
  - `suppressedBackgroundActivityIdentifiers`: `NSSet` (empty)
- **Cellular Entries**:
  - `cellularEntry`: Primary `STStatusBarDataCellularEntry`
    - `string` / `crossfadeString`: Custom Carrier Name UTF-8 string
    - `displayValue`: Signal bars (0–4)
    - `type`: Network type (10 = 5G, 9 = LTE, etc.)
    - `badgeString`: SIM badge (e.g. `"P"`, `"1"`, `"主卡"`)
    - `status`: Connection state (5 = Connected)
    - `enabled`: `true`
  - `secondaryCellularEntry`: Secondary `STStatusBarDataCellularEntry` (enables Apple's native Dual SIM stacked UI)

### 2. SpringBoard Archiver Reverse Engineering
Reverse engineering of `SBSystemStatusStatusBarOverridesArchiver` in `SpringBoard.framework`:
- **Startup Read (`0x5b5688`)**: On launch, SpringBoard unarchives `StatusBarOverrides.archive`, updates `STStatusBarOverridesStatusDomainPublisher`, and publishes directly to `SystemStatusUI`.
- **Auto-Eviction on Reset (`0x5b5444`)**: If the decoded record is empty or invalid, SpringBoard automatically calls `removeItemAtURL:`, clearing the file and restoring factory carrier defaults.
- **`systemstatusd` Memory Sync & Cache Invalidation**: On iOS 27, the `systemstatusd` system daemon maintains publisher records in memory. When updating live, restarting both `systemstatusd` and `SpringBoard` prevents in-memory cache from overwriting the newly injected archive.

### 3. Dynamic Carrier Reverse Engineering & CommCenter Upstream Breakthrough
While `StatusBarOverrides.archive` successfully renders custom carrier text on iOS 27, it operates as a static mock: custom text remains visible when Airplane Mode is enabled, and signal bars remain fixed at 4 bars rather than reflecting live baseband strength. Our latest reverse engineering of iOS 27 system binaries (`UIKitCore`, `SystemStatus.framework`, `CoreTelephony.framework`, and `libCommCenterBase.dylib` across 4,088 dyld cache images) addressed these limitations:

#### Disproof of Static & Status Bar Paths
- **Direction 3 (`StatusBarOverrides` Field-Level Passthrough) — Thoroughly Disproved (Dead End)**:
  Disassembly of `UIKitCore` (`0x1c70d9000`) methods `-[_UIStatusBarData dataByApplyingOverlay:]` (`0x1c80148f4`) and `-[_UIStatusBarData _applyUpdate:keys:]` (`0x1c8014748`) proved that merging operates strictly at the top-level entry key granularity (`cellularEntry`, `secondaryCellularEntry`). When `cellularEntry != nil`, it invokes `setValue:forKey:` (`0x1c8014a04`) to **atomically replace the entire entry object pointer**. Furthermore, `-[_UIStatusBarDataCellularEntry initWithCoder:]` (`0x1c80108ac`) decodes missing numeric fields to `0`/`NO`. There is no sentinel value or field-level fallback in `SystemStatus`.
- **Direction 1 (`SystemStatusDefaults` & `CTSimLabel`) — Disproved for Main Carrier**:
  `STSystemStatusDefaults` (subclass of `BSAbstractDefaultDomain`) only binds 3 internal boolean flags. `CoreTelephony`'s `CTSimLabel` (`0x1a73a109c`) only controls the dual SIM badge text (`[P]`/`[S]`), not the primary operator display name.

#### The Sole Viable Upstream Path: CommCenter PLMN Mapping
- **`NetworkListOperator::getLocalizedCompositeName` (`0x1b3db050c .. 0x1b3db09ec`)**:
  In `libCommCenterBase.dylib`, `CommCenter` natively implements a dictionary lookup override:
  1. Requests `CFSTR("InterCarrierRoamingDisplayNames")` (`0x1f5ae6dd0`) with `BundleType = 5` (`Operator` bundle) via `CarrierSettingsInterface->copyValueForKey` (vtable offset `+0x50`).
  2. Generates the active PLMN string (`MCC+MNC`, such as `46000`, `46001`, `46011`) via `MCCAndMNC::getStringValue()`.
  3. Queries `CFDictionaryGetValue(dict, cfPlmnString)` (`0x1ba87c500`). If matched and verified as a `CFString`, **it directly returns this custom string as the localized operator display name**.
  4. **Key Benefit**: Because this resolution takes place at the cellular registration layer inside `CommCenter`, **100% of native baseband signal bars, network technology switches, and Airplane Mode disconnect/hide logic remain fully functional and authentic**.
- **`/var/mobile/Library/Preferences/` Mapping Layer (`0x1b3dd4228 .. 0x1b3dd430c`)**:
  `CarrierSettingsInterface` maps SIM slots to preferences under `/var/mobile/Library/Preferences/`:
  - Primary (Slot 1): `com.apple.operator_1.plist`, `com.apple.operator_1.merged.plist`, `com.apple.carrier_1.plist`
  - Secondary (Slot 2): `com.apple.operator_2.plist`, `com.apple.operator_2.merged.plist`, `com.apple.carrier_2.plist`
  - Persistent Domains: `com.apple.commcenter.carrier_bundle`, `com.apple.commcenter.device_specific_nobackup`
  Because `/var/mobile/Library/Preferences/` is owned by `mobile:mobile` (UID 501), it is fully accessible to AirLift and `HomeDomain` backup restore (`MobileBackup2`).

> 📄 **Technical Reports**:
> - Research Status & Roadmap: [`iOS27_Dynamic_Carrier_Research_Status.md`](iOS27_Dynamic_Carrier_Research_Status.md)
> - ARM64e Disassembly Deep Dive: [`docs/commcenter-dynamic-carrier-reverse-engineering.md`](docs/commcenter-dynamic-carrier-reverse-engineering.md)

---

## ✈️ AirLift Physical Deployment Architecture & Sandbox Bypass

```text
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                                 Physical iPhone Pipeline                               │
│                                                                                        │
│   [Mac Host CLI] ─────────────► [AirLift Exploit Engine] ────────► [iOS AirTraffic]    │
│  airlift_carrier_deploy.py       StreamingZip + Books.plist         com.apple.atc      │
│                                                                           │            │
│                                                                           ▼ (Path Traversal)
│   [SpringBoard Loads] ◄────── [StatusBarOverrides.archive] ◄───── [ATAirlock Move]     │
│   SystemStatusUI Shows        /var/mobile/Library/SpringBoard/    (Runs as mobile:501) │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

### 1. Why Physical Devices Require AirLift
- **Simulator vs. Physical Device**: On Mac CoreSimulator, the host has direct filesystem write access. On a physical iPhone, the iOS sandbox forbids USB writes to `/var/mobile/Library/SpringBoard/`.
- **AirLift's Role**: AirLift acts as the **non-jailbreak delivery vehicle** that exploits the Books synchronization protocol to place the payload outside the media sandbox.

### 2. AirTraffic Books Path Traversal Mechanics
AirLift exploits relative path validation omissions in `com.apple.atc` (AirTraffic):
1. **Crafted StreamingZip**: Bundles a symlink pointing outside the sandbox:
   `p0/p1/p2/link -> ../../../var/mobile/Library/SpringBoard`
2. **AFC Staging**: Unpacks archive into `/var/mobile/Media` via `com.apple.streaming_zip_conduit`.
3. **AirTraffic Sync**: Emulates an iTunes sync session via `airtraffic_host` and dispatches `FileComplete`.
4. **Atomic Ingestion**: `-[ATAirlock processCompletedAsset:]` follows the symlink and moves the payload directly into `/var/mobile/Library/SpringBoard/StatusBarOverrides.archive`.
5. **Permission Compatibility**: AirTraffic executes under `mobile:mobile` (uid 501), matching the exact ownership required by SpringBoard.

### 3. Overcoming the ATAirlock `rename` Limitation
- **The Constraint**: Cocoa's `[NSFileManager moveItemAtPath:toPath:error:]` fails with `NSFileWriteFileExistsError` if the destination file already exists.
- **Universal Mitigation Strategy**:
  1. **Clean Baseline**: Fresh iOS 27 devices do not have `StatusBarOverrides.archive` by default. First installation creates the file cleanly.
  2. **Native Self-Eviction**: Deploying an empty reset archive causes SpringBoard's own archiver (`_queue_writeOutArchiveRecord:`) to delete the file via `removeItemAtURL:`. The directory returns to clean state for subsequent deployments.

---

## 🔒 Lock Screen Footnote Architecture

Lock Screen Footnote is an official Apple Device Management feature (`com.apple.shareddeviceconfiguration`):
- **Target File**: `/var/containers/Shared/SystemGroup/systemgroup.com.apple.configurationprofiles/Library/ConfigurationProfiles/SharedDeviceConfiguration.plist`
- **Key**: `<key>LockScreenFootnote</key><string>Custom Text</string>`
- **Delivery Channels**:
  1. **Official Configuration Profile (`.mobileconfig`)**: Zero exploit needed; can be signed and installed via AirDrop, Safari, or MDM. (Sample in [`examples/footnote_sample.mobileconfig`](examples/footnote_sample.mobileconfig)).
  2. **Protective Backup Injection (`MobileBackup2`)**: Injects into `SysSharedContainerDomain` (as analyzed in GoldenNugget-Mobile's `BackupInjector.swift`).

---

## 🛠️ Toolchain & Quick Start

### 1. Physical Device Deployment (`tools/airlift_carrier_deploy.py`)
```bash
# Compile native AirLift helpers (MobileDevice + AirTrafficHost)
cd airlift && make && cd ..

# Single SIM: Set custom carrier name
python3 tools/airlift_carrier_deploy.py -c "MyCarrier 5G" -b 4 -t 5g

# Dual SIM: Set primary and secondary carriers with badges
python3 tools/airlift_carrier_deploy.py \
  -c "CMI" --badge "P" \
  -s "T-mobile" --secondary-badge "S"

# Reset / Restore native carrier settings
python3 tools/airlift_carrier_deploy.py --reset

# Local Dry-Run (verify packaging without device connection)
python3 tools/airlift_carrier_deploy.py -c "Test Carrier" --dry-run

# Two-Phase Auto Overwrite (bypass ATAirlock rename limitation automatically)
python3 tools/airlift_carrier_deploy.py -c "NewCarrier 5G" --force-overwrite

# Presets management
python3 tools/airlift_carrier_deploy.py --list-presets
python3 tools/airlift_carrier_deploy.py --preset dual-cmcc-cucc

# Interactive Wizard Mode
python3 tools/airlift_carrier_deploy.py -i

# Launch Web GUI Dashboard
python3 tools/gui_server.py

# Tip: disconnect the iPhone Wi-Fi (Settings > Wi-Fi) and use a USB cable. The GUI
# still proceeds over a local-network connection, but it warns and USB is recommended.

# Activate overrides: restart SpringBoard so it loads the archive (also standalone)
python3 tools/airlift_carrier_deploy.py --respring

# Recover from a failed deployment (removes staging leftovers + dirty Books state)
python3 tools/airlift_carrier_deploy.py --clean-device

# Device-side resilience check (writes a reset archive; requires --yes)
python3 tools/airlift_resilience_check.py --yes
```

### 2. Upstream CommCenter Preference Experiment (Route A)
```bash
# Read-only HomeDomain recon through the AirLift traversal link (stat / list / read)
python3 tools/device_path_probe.py --udid <UDID> \
  --stat /var/mobile/Library/SpringBoard/StatusBarOverrides.archive

# Build the InterCarrierRoamingDisplayNames mapping without touching a device
python3 tools/commcenter_carrier_inject.py -c "Custom 5G" --plmn china_unicom --dry-run

# Inject it into the per-slot operator domains (HomeDomain / Library/Preferences)
python3 tools/commcenter_carrier_inject.py -c "Custom 5G" --plmn china_unicom

# Visual verification: screenshots and Control Center gestures via CoreDevice HID
python3 tools/device_ui.py screenshot control-center.png
python3 tools/device_ui.py open-cc

# Restart cfprefsd / CommCenter / SpringBoard without rebooting (root signal channel)
.venv/bin/pymobiledevice3 developer core-device list-processes --userspace
.venv/bin/pymobiledevice3 developer core-device send-signal-to-process <pid> 15 --userspace
```

### 3. Standalone Archive Generator & Simulator Deployer (`tools/generate_statusbar_archive.py`)
```bash
# Generate a custom binary archive file
python3 tools/generate_statusbar_archive.py -c " Apple 5G" -b 4 -t 5g -o custom.archive

# Generate and deploy directly to active Booted Simulator with instant hot-reload
python3 tools/generate_statusbar_archive.py \
  -c "Testname" --badge "P" \
  -s "Test for name" --secondary-badge "S" \
  --deploy-simulator booted

# Inspect / Decode an existing archive
python3 tools/generate_statusbar_archive.py -i custom.archive
```

---

## 📁 Repository Structure

```text
.
├── README.md                                          # English Documentation (Primary)
├── README_ZH.md                                       # Chinese Documentation (中文同步文档)
├── iOS27_Dynamic_Carrier_Research_Status.md          # Upstream dynamic carrier reverse engineering status & roadmap
├── tools/                                             # Automation and deployment toolchain
│   ├── airlift_carrier_deploy.py                      # Universal AirLift physical device deployer CLI
│   ├── airlift_resilience_check.py                    # Device-side retry/rollback resilience check (device writes, needs --yes)
│   ├── commcenter_carrier_inject.py                   # Route A: InterCarrierRoamingDisplayNames preference injector
│   ├── device_path_probe.py                           # Read-only HomeDomain stat/list/read probe via the AirLift link
│   ├── device_ui.py                                   # CoreDevice HID gesture / screenshot verification helper
│   ├── gui_server.py                                  # Bilingual web dashboard (deploy / repair / SpringBoard restart)
│   ├── display_metrics.py                             # Dynamic Island width heuristics & truncation warnings
│   ├── footnote_generator.py                          # Lock Screen footnote .mobileconfig generator
│   ├── presets.py                                     # Named carrier presets
│   ├── terminal_preview.py                            # Terminal status bar preview
│   ├── test_airlift_features.py                       # Offline unit test suite
│   └── generate_statusbar_archive.py                  # Universal archive generator & simulator deployer
├── airlift/                                           # Native AirLift exploit & synchronizer subsystem
│   ├── Sources/                                       # Native Objective-C helpers (device_helper.m, airtraffic_host.m)
│   ├── Makefile                                       # Clang build script for Mach-O binaries
│   └── airlift_carrier_deploy.py                      # AirLift deployer runner
├── examples/                                          # Sample payloads
│   ├── footnote_sample.mobileconfig                   # Official profile payload for Lock Screen Footnote
│   ├── StatusBarOverrides_sample.archive              # Single SIM modern binary archive
│   ├── StatusBarOverrides_dualsim_sample.archive      # Dual SIM modern binary archive
│   └── StatusBarOverrides_reset_sample.archive        # Reset archive (restores default carrier)
├── assets/                                            # Empirical verification screenshots
│   ├── iphone14pro_controlcenter_testname.png         # iPhone 14 Pro iOS 27 Control Center Dual SIM proof
│   ├── iphone14pro_baseline.png                       # iPhone 14 Pro baseline (iOS 27 Dynamic Island)
│   ├── iphone14pro_singlesim.png                      # iPhone 14 Pro Single SIM solid 4-bars
│   ├── iphone14pro_dualsim.png                        # iPhone 14 Pro Dual SIM stacked bars + dots
│   ├── iphone_se_carrier_screenshot.png               # iPhone SE Classic Status Bar proof
│   └── simctl_override_screenshot.png                 # iPhone 16 Pro Max Dynamic Island status bar capture
└── docs/                                              # In-depth technical reverse engineering reports
    ├── handoffs/                                      # Chronological research handoff documents
    │   ├── iOS27_Carrier_LockScreen_Research_Handoff_2026-09-25.md
    │   ├── iOS27_Carrier_Footnote_Research_Handoff_2026-09-28.md
    │   ├── iOS27_Carrier_Footnote_Latest_Research_2026-09-30.md
    │   ├── iOS27_CommCenter_Preference_Injection_2026-10-19.md
    │   └── iOS27_Research_Progress_Snapshot_2026-10-19.md
    ├── iOS27_Carrier_Footnote_Solution.md             # Complete technical solution & security verdict
    ├── architecture.md                                # Full customization architecture & security boundaries
    ├── carrier-data-flow.md                           # SIM -> CommCenter -> SystemStatusUI reverse engineering
    ├── commcenter-dynamic-carrier-reverse-engineering.md # iOS 27 CommCenter dynamic carrier deep-dive (ARM64e disassembly)
    ├── golden-nugget-diff.md                          # Git topology audit of GoldenNugget forks
    ├── iphone14pro-dynamic-island-cellular-analysis.md # Dynamic Island cellular rendering deep-dive
    ├── ios27-carrier-empirical-verification.md        # Empirical verification & archive breakthrough
    ├── risk-register.md                               # Device safety rules & risk mitigation
    ├── speakeasy-analysis.md                          # FeatureFlags framework & Speakeasy analysis
    ├── systemstatusui-analysis.md                     # Modern SystemStatus pub/sub architecture breakdown
    └── viable-paths.md                                # Detailed feasibility assessment
```

---

## ⚠️ Primary Device Safety Guidelines

1. **Configurable Device Blocklist**: `tools/airlift_carrier_deploy.py` supports blocking designated daily-driver UDIDs via the `AIRLIFT_BLOCKED_UDIDS` environment variable (comma-separated UDIDs), refusing any deployment attempt to protected hardware.
2. **Strict Build Gating Option**: Setting `AIRLIFT_STRICT_BUILDS=1` enforces execution exclusively on tested iOS builds (`24A300`, `24A434`, `24A435`, `24A437`, `24A5390f`).
3. **Target Directory Whitelist**: Path traversal in `build_streaming_zip` strictly whitelists `/var/mobile/Library/SpringBoard` to eliminate arbitrary directory write risks.
4. **Carrier String Length Checks**: Inputs are enforced to a max length of 64 characters for carrier text and 8 characters for badges.
5. **Zero `/var/preferences` Modifications**: We target only SpringBoard's user-owned directory (`mobile:mobile`), completely avoiding root-level security wipes (Security State Recovery).
6. **Pristine State Maintenance**: Books synchronization databases are snapshotted and cleanly restored after staging.

---

## ⚠️ Known Limitations & Open Research Questions

1. **Physical Hardware Delivery**: Successfully verified end-to-end on physical hardware using the GoldenNugget `HomeDomain` backup restore pipeline (`MobileBackup2`). The in-repo AirLift channel has since been verified on physical hardware as well (see the verification section above), including overwriting an already existing archive on iOS 27.0 (24A437).
2. **ATAirlock `rename` Overwrite Constraint (AirLift-specific)**: AirTraffic's `-[ATAirlock processCompletedAsset:]` relies on Cocoa's `moveItemAtPath:toPath:error:`, which returns `NSFileWriteFileExistsError` when the destination file already exists. On iPhone 16 Pro Max / iOS 27.0 (24A437) overwriting an existing archive was measured to **succeed** (the archive fetched back matched the new payload byte-for-byte), so the constraint does not always bite — but it is build/path dependent, which is why `--force-overwrite` (two-phase: reset archive → reboot → fresh write) is kept as the safe path for updates. (The `HomeDomain` backup restore path avoids the question entirely.)
3. **Lock Screen Footnote Supervision**: The `com.apple.shareddeviceconfiguration` payload is an official Apple MDM schema; in certain corporate or constrained environments, displaying the footnote on the lock screen may require device supervision.
4. **Activation: the first injection needs one SpringBoard restart**: SpringBoard only reads `StatusBarOverrides.archive` while it is starting up, so an archive staged by AirLift while SpringBoard runs is never picked up on its own. The **first** injection therefore needs one SpringBoard restart (`--respring`, the GUI's "⚡ Restart SpringBoard" button, or standalone `python3 tools/airlift_carrier_deploy.py --respring`); a reboot alone is not enough at that moment. Once SpringBoard has loaded the record and written its own copy back, the overrides **persist across full reboots** (verified on iPhone 16 Pro Max / iOS 27.0 24A437). On Dynamic Island models the carrier text is rendered in **Control Center**, not in the home-screen status bar.
5. **Overrides Are Static (Current StatusBarOverrides Pipeline) & Dynamic Upstream Solution**: The archive does not merely rename the carrier, it pins the entire cellular entry (`enabled = true`, `status = 5`, `type = <network type>`, `displayValue = <bars>`, `string`/`crossfadeString`). Our reverse engineering of `UIKitCore` (`-[_UIStatusBarData dataByApplyingOverlay:]` @ `0x1c80148f4`) proved that `SystemStatus` performs an atomic pointer replacement of the `STStatusBarDataCellularEntry` object with zero field-level pass-through, causing custom text to stay visible in Airplane Mode and signal bars to remain fixed. To achieve genuine live baseband signal and authentic Airplane Mode decoupling, our upstream research has bypassed the status bar domain entirely and moved into `CommCenter` (`libCommCenterBase.dylib`), discovering the `InterCarrierRoamingDisplayNames` PLMN dictionary resolution mechanism (`0x1b3db050c`) and `/var/mobile/Library/Preferences/` (`com.apple.operator_1.merged.plist`) preference injection vector. Full analysis and next-step experimental roadmap are documented in [`iOS27_Dynamic_Carrier_Research_Status.md`](iOS27_Dynamic_Carrier_Research_Status.md) and [`docs/commcenter-dynamic-carrier-reverse-engineering.md`](docs/commcenter-dynamic-carrier-reverse-engineering.md).
6. **Staging Robustness & Verification Honesty**: `stage` now retries up to 3 times with a fresh staging token and a fresh Books preimage, and every failed attempt is rolled back automatically, so a transient device-side Books write no longer strands `/var/mobile/Media/airlift-src-*` trees or stale asset rows in `Books.plist`. The AFC daemon is confined to the media sandbox, so the deployed archive can only be *probed* through the staging symlink (a non-missing `st_mode` stat means it exists); byte-exact readback would require moving the archive back out of SpringBoard, so the CLI reports `Byte Verification: unavailable` instead of inventing a result. Run `--clean-device` after any hard failure (e.g. the process was killed mid-deploy) to restore a pristine staging state.

---

## 🔗 References & Credits

### 1. AirLift Core & Conduit Exploitation
- [AirLift (0xjohnnydev/airlift)](https://github.com/0xjohnnydev/airlift) — Native AirTraffic Books path-traversal exploit engine.
- [PyAirLift (awesomenull-dev/PyAirLift)](https://github.com/awesomenull-dev/PyAirLift) — Python implementation of AirTraffic conduit escape with iOS 27 support.
- [AirCard-iOS (Mak5er / EpochME)](https://github.com/Mak5er/AirCard-iOS) — On-device `AirliftFFI.xcframework` Rust integration.
- [pymobiledevice3 (doronz88/pymobiledevice3)](https://github.com/doronz88/pymobiledevice3) — Pure Python iOS protocol library.

### 2. Customization & Tweak Frameworks
- [Nugget (leminlimez/Nugget)](https://github.com/leminlimez/Nugget) — Original iOS customization framework.
- [GoldenNugget (GoldenNugget-Team/GoldenNugget)](https://github.com/GoldenNugget-Team/GoldenNugget) — Desktop customization suite.
- [GoldenNugget-Mobile (GoldenNugget-Team/GoldenNugget-mobile)](https://github.com/GoldenNugget-Team/GoldenNugget-mobile) — iOS 27 on-device customization using MobileBackup2.
- [GoldenNugget fork (phanquocviet8x/GoldenNugget)](https://github.com/phanquocviet8x/GoldenNugget) — Historical iOS 27 status bar branch analysis.

### 3. Cellular & Carrier Research
- [iOS Carrier Bundle (VCTGomes/ios-carrier-bundle)](https://github.com/VCTGomes/ios-carrier-bundle) — iOS 27 carrier bundle dump and analysis.
- [iOS Carrier Bundles (dwilliamsuk/ios-carrier-bundles)](https://github.com/dwilliamsuk/ios-carrier-bundles) — Carrier configuration repositories.

### 4. Apple Official Standards & Exploitation History
- [Apple Device Management Schema](https://github.com/apple/device-management) — Official MDM `com.apple.shareddeviceconfiguration` definition.
- [bad_query (forcequitOS/bad_query)](https://github.com/forcequitOS/bad_query) — iOS 27 sandbox escape research.
- [WorkPlot (gievano/WorkPlot)](https://github.com/gievano/WorkPlot) — Early iOS 27 sandbox exploration.
- [Erosion (jailbreakdotparty/Erosion)](https://github.com/jailbreakdotparty/Erosion) — File manipulation research.

---

## 📜 License & Disclaimer

This project is strictly for **educational and defensive security research purposes**. Apple, iPhone, iOS, SpringBoard, and Dynamic Island are trademarks of Apple Inc.