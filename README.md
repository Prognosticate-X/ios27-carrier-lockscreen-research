# iOS 27 Carrier & Lock Screen Customization Research

> Systematic reverse engineering and implementation research for customizing **Carrier Name** and **Lock Screen Footnote** on **iPhone 16 Pro Max (A18 Pro) + iOS 27.0 Release**.

---

## 🎯 Executive Summary & Status

| Customization Target | Status on iOS 27.0 Release | Core Mechanism | Viability |
|---|---|---|---|
| **Lock Screen Footnote** | 🟢 **VIABLE** | `SharedDeviceConfiguration.plist` under `com.apple.shareddeviceconfiguration` | **High** — Native Apple profile support; writable via Configuration Profile or Protective Backup Injection into `SysSharedContainerDomain`. |
| **Carrier Name Override** | 🟢 **VERIFIED (BREAKTHROUGH)** | Modern `StatusBarOverrides.archive` (`_SBSystemStatusStatusBarOverridesArchiveRecord`) | **High (AirLift Path)** — Empirical simulator tests prove SpringBoard actively loads `StatusBarOverrides.archive`. Target path `/var/mobile/Library/SpringBoard/` is owned by `mobile:mobile`, completely writable via AirLift without root/FeatureFlags! |

---

## 🏗️ Architecture & Core Mechanics

### 1. Carrier Display String Data Flow
Our static reverse engineering of iOS/macOS 27 shared caches and runtime frameworks (`CoreTelephony`, `SystemStatus`, `SystemStatusServer`, `SystemStatusUI`) revealed the end-to-end data pipeline:

```text
               +---------------------------------------+
               |        1. 物理 SIM / eSIM 硬件        |
               |      - EF_SPN (Service Provider Name) |
               |      - EF_PNN (PLMN Network Name)     |
               +-------------------+-------------------+
                                   |
                                   v
               +---------------------------------------+
               |          2. 基带固件 (Baseband)       |
               |      - 解析 MCC / MNC / IMSI          |
               +-------------------+-------------------+
                                   |
                                   v (QMI / IPC)
               +---------------------------------------+
               |          3. CommCenter (根守护进程)   |
               |  - 载入 Carrier Bundle (强制签名校验) |
               |  - 决定最终 Operator Name             |
               +-------------------+-------------------+
                                   |
                                   | Mach Message / XPC (CTXPCGetOperatorNameRequest)
                                   v
               +---------------------------------------+
               |          4. CoreTelephony.framework   |
               |  - CTTelephonyNetworkInfo / CTCarrier |
               |  - CTXPCGetOperatorNameResponse       |
               +-------------------+-------------------+
                                   |
                                   | XPC 状态广播
                                   v
               +---------------------------------------+
               |       5. SpringBoard (状态栏发布端)   |
               |  - SBTelephonyManager                 |
               |  - STTelephonyStatusDomainPublisher   |
               +-------------------+-------------------+
                                   |
                                   | updateDataWithBlock:
                                   v
               +---------------------------------------+
               |       6. SystemStatus.framework       |
               |  - STLocalStatusServer (总线状态服务) |
               |  - STTelephonyStatusDomainData        |
               +-------------------+-------------------+
                                   |
                                   | in-process / XPC dispatch
                                   v
               +---------------------------------------+
               |      7. SystemStatusUI.framework      |
               |  - STUIStatusBar                      |
               |  - _UIStatusBarCellularItem           |
               |  - 最终将 Carrier Text 绘制到锁屏顶栏 |
               +-------------------+-------------------+
```

### 2. Speakeasy Gate & The FeatureFlags Deadlock

```text
                      SpringBoard
                          |
                   Speakeasy Gate
                          |
               +----------+----------+
               |                     |
         Speakeasy = ON        Speakeasy = OFF
         (System Default)      (Requires Settings.plist)
               |                     |
         SystemStatusUI        Classic StatusBar
         (Modern Pub/Sub)            |
               |             statusBarOverrides
       In-Memory Transient     (Raw C Struct)
          Domain Data
```

1. **Gate Logic:** SpringBoard evaluates `isEnabled("SpringBoard", "Speakeasy")`. Base flag defaults to **ON** (`FeatureComplete`).
2. **Sole Store Path:** `FeatureFlags.framework` queries `/var/preferences/FeatureFlags/Settings.plist` **only**. It does not query cfprefs or MCX.
3. **Write Barrier:** 
   - `BackupAgent2` enforces a strict 10-path allowlist (`SystemPreferencesDomain`), silently dropping custom files.
   - Sparse restore triggers iOS 27 **Security State Recovery (Wipe)**, completely erasing `/var/preferences`.

---

## 🔬 Research Phases & Progress

| Priority | Phase | Status | Key Deliverable / Outcome |
|:---:|---|:---:|---|
| **P0** | **Code Diff & Fork Audit** | ✅ Completed | Audited `awesomenull-dev` vs `phanquocviet8x`. Proved "patched on iOS 27" meant *patched by Apple* (blocked), not patched by tool. |
| **P1** | **Static Reverse Engineering** | ✅ Completed | Mapped `CoreTelephony` -> `SystemStatus` -> `SystemStatusUI` runtime classes & data flow. |
| **P2** | **Feature Flags & Speakeasy** | ✅ Completed | Documented 13 test runs confirming `/var/preferences` write barrier. |
| **P3** | **Write Primitives on Release** | ✅ Completed | Evaluated `SysSharedContainerDomain` and `HomeDomain` injection survivability. |
| **P4** | **Carrier Bundle & Exploits** | 🔄 Documented | Verified `CommCenter` digital signature requirement on `Carrier.plist` (fails without `CommCenterPatch`). |
| **P5** | **Footnote Customization Tool** | 🟢 Ready | Path verified for `LockScreenFootnote` delivery via profiles/backup injection. |

---

## 🔑 Key Technical Hypotheses (Evaluated)

| # | Hypothesis | Result | Verification Detail |
|:---:|---|:---:|---|
| **H1** | `statusBarOverrides` still exists in iOS 27.0 Release. | **CONFIRMED** | Legacy string and decoding logic still present in dyld chunk `.01`, but dormant behind Speakeasy. |
| **H2** | `Speakeasy` is modifiable via Feature Flags on non-JB device. | **REFUTED** | `/var/preferences/FeatureFlags/Settings.plist` cannot be written without triggering Security Recovery Wipe or BackupAgent drops. |
| **H3** | `SystemStatusUI` has an unauthenticated plist override for Carrier. | **REFUTED** | SystemStatusUI is a purely in-memory subscriber to `STLocalStatusServer` domain data. |
| **H4** | Carrier Name comes from SIM/Baseband/CommCenter, not SystemStatusUI. | **CONFIRMED** | `CTXPCGetOperatorNameResponse` is produced by `CommCenter`. Carrier Bundles enforce Apple digital signatures. |
| **H5** | iOS 27.0 Release patched the restore file-write primitive. | **CONFIRMED** | Apple introduced aggressive Security State Recovery wipes on `/var/preferences` and tightened domain allowlists. |

---

## 📁 Repository Structure

```text
.
├── README.md                                          # Project overview, findings, and current status
├── iOS27_Carrier_Footnote_Solution.md                 # Complete technical solution & security verdict
├── iOS27_Carrier_LockScreen_Research_Handoff.md       # Original local agent handoff document
├── tools/                                             # Automation and generator scripts
│   └── generate_statusbar_archive.py                  # iOS 27 StatusBarOverrides.archive bplist generator
├── assets/                                            # Empirical screenshots from iOS 27 testing
│   ├── iphone_se_carrier_screenshot.png               # Visual proof of custom carrier rendering on iOS 27
│   └── simctl_override_screenshot.png                 # iPhone 16 Pro Max Dynamic Island status bar capture
└── docs/                                              # In-depth technical research reports
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

All experiments on the primary **iPhone 16 Pro Max** must adhere to the [Risk Register](docs/risk-register.md):
1. **Zero Blind Restores:** Never run legacy Nugget sparse restores on iOS 27.0 Release.
2. **No `/var/preferences` Staging:** Avoid triggering iOS 27 Security State Recovery (which wipes Apple ID, Keychain, Photos, and settings).
3. **Full Encrypted & Unencrypted Backups:** Retain full local device backups prior to any testing.
4. **Reversible Operations First:** Prioritize official configuration profile and `SysSharedContainerDomain` paths.

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
