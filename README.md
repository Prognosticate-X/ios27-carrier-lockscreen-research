# iOS 27 Carrier & Lock Screen Customization Research

> Systematic reverse engineering and implementation research for customizing **Carrier Name** and **Lock Screen Footnote** on **iPhone 16 Pro Max (A18 Pro) + iOS 27.0 Release**.

---

## 🎯 Executive Summary & Status

| Customization Target | Status on iOS 27.0 Release | Core Mechanism | Viability |
|---|---|---|---|
| **Lock Screen Footnote** | 🟢 **VIABLE** | `SharedDeviceConfiguration.plist` under `com.apple.shareddeviceconfiguration` | **High** — Native Apple profile support; writable via Configuration Profile or Protective Backup Injection into `SysSharedContainerDomain`. |
| **Carrier Name Override** | 🟢 **VERIFIED (BREAKTHROUGH)** | Modern `StatusBarOverrides.archive` (`_SBSystemStatusStatusBarOverridesArchiveRecord`) | **High (AirLift Path)** — Confirmed working on iOS 27 CoreSimulator (iPhone 14 Pro / iPhone 16 Pro Max) & physical deployment pipeline ready. SpringBoard actively loads `StatusBarOverrides.archive` from `/var/mobile/Library/SpringBoard/` (owned by `mobile:mobile`). Fully writable without root or FeatureFlags! |

---

## 📱 Hardware & Display Validation Matrix

| Target Device | Model ID | Display Type | Cellular Icon Rendering | Status on iOS 27 |
|---|---|---|---|---|
| **iPhone 14 Pro** | `iPhone15,2` | 灵动岛 (Dynamic Island) | **Single SIM**: Full-height 4 bars<br>**Dual SIM**: Stacked 4 bars (Primary) + 4 dots (Secondary) | 🟢 **Verified** (Simulator + Archive) |
| **iPhone 16 Pro Max** | `iPhone17,2` | 灵动岛 (Dynamic Island) | **Single SIM**: Full-height 4 bars | 🟢 **Verified** (Simulator) / 🛡️ Protected |
| **iPhone SE (3rd gen)** | `iPhone14,6` | 经典顶部状态栏 (Classic) | Top-left Carrier String + 4 bars | 🟢 **Verified** (Legacy Layout) |

---

## 🏗️ Architecture & Core Mechanics

### 1. Modern StatusBarOverrides.archive Architecture
Unlike iOS 14-16 which expected a raw 3944-byte C struct in `statusBarOverrides`, iOS 27 uses an **NSKeyedArchiver binary property list**:
- **Path**: `/var/mobile/Library/SpringBoard/StatusBarOverrides.archive`
- **Ownership**: `mobile:mobile` (0644)
- **Root Class**: `_SBSystemStatusStatusBarOverridesArchiveRecord`
  - `statusBarData`: `STStatusBarData` (from `SystemStatus.framework`)
  - `suppressedBackgroundActivityIdentifiers`: `NSSet` (empty)
- **Cellular Entries**:
  - `cellularEntry`: Primary `STStatusBarDataCellularEntry`
    - `string` / `crossfadeString`: Custom Carrier Name UTF-8 string
    - `displayValue`: Signal bars (0-4)
    - `type`: Network type (10 = 5G, 9 = LTE, etc.)
    - `badgeString`: SIM badge (e.g. `"P"`, `"主卡"`)
    - `status`: Connection state (5 = Connected)
    - `enabled`: `true`
  - `secondaryCellularEntry`: Secondary `STStatusBarDataCellularEntry` (enables Apple's native Dual SIM stacked UI)

### 2. SpringBoard Archiver Reverse Engineering
Reverse engineering of `SBSystemStatusStatusBarOverridesArchiver` in `SpringBoard.framework`:
- **Startup Read (`0x5b5688`)**: On launch, SpringBoard unarchives `StatusBarOverrides.archive`, updates `STStatusBarOverridesStatusDomainPublisher`, and publishes directly to `SystemStatusUI`.
- **Auto-Eviction on Reset (`0x5b5444`)**: If the decoded record is empty or invalid, SpringBoard automatically calls `removeItemAtURL:`, clearing the file and restoring factory carrier defaults.
- **Delivery via AirLift**: `airlift` utilizes an AirTraffic Books path traversal exploit (`p0/p1/p2/link -> ../../../var/mobile/Library/SpringBoard`) to write `StatusBarOverrides.archive` into SpringBoard non-interactively without jailbreak.

---

## 🛠️ Toolchain & Quick Start

### 1. Physical Device Deployment (`airlift_carrier_deploy.py`)
```bash
# Compile native helpers (MobileDevice + AirTrafficHost)
cd airlift && make && cd ..

# Single SIM: Set custom carrier name to "中国移动 5G"
python3 tools/airlift_carrier_deploy.py -c "中国移动 5G" -b 4 -t 5g

# Dual SIM: Set primary and secondary carriers with badges
python3 tools/airlift_carrier_deploy.py \
  -c "中国移动 5G" --badge "主卡" \
  -s "中国联通 5G" --secondary-badge "副卡"

# Reset / Restore native carrier settings
python3 tools/airlift_carrier_deploy.py --reset

# Local Dry-Run (verify packaging without connecting a device)
python3 tools/airlift_carrier_deploy.py -c "中国广电 5G" --dry-run
```

### 2. Standalone Archive Generator & Inspector (`generate_statusbar_archive.py`)
```bash
# Generate a custom archive
python3 tools/generate_statusbar_archive.py -c " Apple 5G" -b 4 -t 5g -o custom.archive

# Inspect / Decode an existing archive
python3 tools/generate_statusbar_archive.py -i custom.archive
```

---

## 📁 Repository Structure

```text
.
├── README.md                                          # Project overview, findings, and current status
├── iOS27_Carrier_Footnote_Solution.md                 # Complete technical solution & security verdict
├── iOS27_Carrier_LockScreen_Research_Handoff.md       # Original local agent handoff document
├── tools/                                             # Automation and generator scripts
│   ├── airlift_carrier_deploy.py                      # Physical device AirLift carrier deployment CLI
│   └── generate_statusbar_archive.py                  # iOS 27 StatusBarOverrides.archive bplist generator & inspector
├── airlift/                                           # AirLift exploit & synchronizer subsystem
│   ├── Sources/                                       # Native Objective-C helpers (device_helper.m, airtraffic_host.m)
│   ├── Makefile                                       # Clang build script with MobileDevice & AirTrafficHost
│   └── airlift_carrier_deploy.py                      # AirLift carrier deployer
├── examples/                                          # Ready-to-use sample payloads
│   ├── footnote_sample.mobileconfig                   # Official profile payload for Lock Screen Footnote
│   ├── StatusBarOverrides_sample.archive              # Single SIM modern archive payload
│   ├── StatusBarOverrides_dualsim_sample.archive      # Dual SIM modern archive payload
│   └── StatusBarOverrides_reset_sample.archive        # Reset archive payload (restores defaults)
├── assets/                                            # Empirical screenshots from iOS 27 testing
│   ├── iphone14pro_baseline.png                       # iPhone 14 Pro baseline (iOS 27 Dynamic Island)
│   ├── iphone14pro_singlesim.png                      # iPhone 14 Pro Single SIM solid 4-bars
│   ├── iphone14pro_dualsim.png                        # iPhone 14 Pro Dual SIM stacked bars + dots
│   ├── iphone_se_carrier_screenshot.png               # Visual proof of custom carrier rendering on iOS 27
│   └── simctl_override_screenshot.png                 # iPhone 16 Pro Max Dynamic Island status bar capture
└── docs/                                              # In-depth technical research reports
    ├── iphone14pro-dynamic-island-cellular-analysis.md # iPhone 14 Pro Dynamic Island & cellular entry deep-dive
    ├── ios27-carrier-empirical-verification.md        # Simulator empirical testing & modern archive breakthrough
    ├── architecture.md                                # Full customization architecture & security boundaries
    ├── carrier-data-flow.md                           # SIM -> CommCenter -> SystemStatusUI reverse engineering
    ├── golden-nugget-diff.md                          # Git topology audit of GoldenNugget forks
    ├── speakeasy-analysis.md                          # FeatureFlags framework & Speakeasy gate analysis
    ├── systemstatusui-analysis.md                     # Modern SystemStatus pub/sub architecture breakdown
    ├── viable-paths.md                                # Detailed feasibility assessment for both targets
    └── risk-register.md                               # Primary device safety rules & risk mitigation
```

---

## ⚠️ Primary Device Safety Guidelines

All experiments adhere to strict zero-risk rules:
1. **Hardcoded Device Blocklist**: `airlift_carrier_deploy.py` strictly blocks primary device UDID (`00008140-001C29663062201C`), refusing any connection or operation.
2. **Zero `/var/preferences` Modifications**: We target only `/var/mobile/Library/SpringBoard`, completely avoiding iOS 27 Security State Recovery Wipes.
3. **Pristine State Maintenance**: Books synchronization databases are snapshot and restored cleanly.


---

## 🔗 References & Credits

- [Nugget (leminlimez)](https://github.com/leminlimez/Nugget)
- [GoldenNugget (awesomenull-dev)](https://github.com/awesomenull-dev/GoldenNugget)
- [GoldenNugget (phanquocviet8x)](https://github.com/phanquocviet8x/GoldenNugget)
- [Apple Device Management — LockScreenFootnote](https://developer.apple.com/documentation/devicemanagement/lockscreenmessage)
- [bad_query (forcequitOS)](https://github.com/forcequitOS/bad_query)
- [WorkPlot (gievano)](https://github.com/gievano/WorkPlot)
- [Erosion (jailbreakdotparty)](https://github.com/jailbreakdotparty/Erosion)

---

## 📜 License

This repository is strictly for **educational and defensive research purposes**.
