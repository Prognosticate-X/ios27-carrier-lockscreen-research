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
| **iPhone 14 Pro** | `iPhone15,2` | 灵动岛 (Dynamic Island) | **Single SIM**: Full-height 4 bars<br>**Dual SIM**: Stacked 4 bars (Primary) + 4 dots (Secondary)<br>**Control Center**: `[P] Testname` + `[S] Test for name` | 🟢 **Verified** (Simulator + Archive) |
| **iPhone 16 Pro Max** | `iPhone17,2` | 灵动岛 (Dynamic Island) | **Single SIM**: Full-height 4 bars | 🟢 **Verified** (Simulator) / 🛡️ Protected |
| **iPhone SE (3rd gen)** | `iPhone14,6` | 经典顶部状态栏 (Classic) | Top-left Carrier String + 4 bars | 🟢 **Verified** (Legacy Layout) |

### 📸 Empirical Visual Verification (iOS 27.0 Release)

| Control Center Dual SIM (iPhone 14 Pro, iOS 27.0) | Classic Status Bar (iPhone SE, iOS 27.0) |
|:---:|:---:|
| <img src="assets/iphone14pro_controlcenter_testname.png" width="360" alt="iPhone 14 Pro iOS 27 Dual SIM Control Center" /> | <img src="assets/iphone_se_carrier_screenshot.png" width="360" alt="iPhone SE iOS 27 Carrier Screenshot" /> |
| **Dual SIM Custom Carrier**: `[P] Testname` & `[S] Test for name` | **Single SIM Custom Carrier**: `中国广电 5G` |

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
- **`systemstatusd` Memory Sync & Cache Invalidation**: On iOS 27, the `systemstatusd` system daemon maintains publisher records in memory. If updating `StatusBarOverrides.archive` live on a running system, restarting both `systemstatusd` and `SpringBoard` prevents in-memory cache overwriting the newly written archive.

### 3. AirLift Physical Deployment Architecture & Sandbox Bypass (实机免越狱传输管道)

#### 3.1 为什么实机必须依赖 AirLift？(Why AirLift is Essential for Physical Devices)
- **模拟器 vs 真机差异**：在 Mac 本地 CoreSimulator 调试时，宿主机拥有直接文件系统读写权限（`~/Library/Developer/CoreSimulator/...`）；但在物理 iPhone 上，iOS 沙箱机制禁止外部 USB 直接写入系统目录 `/var/mobile/Library/SpringBoard/`。
- **AirLift 的定位（运输载具）**：AirLift 利用 Apple 原生媒体同步协议漏洞，充当了**免越狱将定制文件送入 SpringBoard 的“特许运输车”**。

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

#### 3.2 AirTraffic Books 路径遍历逃逸原理 (Path Traversal Exploit)
AirLift 利用了 iOS 媒体同步服务（`com.apple.atc` / AirTraffic）在处理 Books（电子书）同步资产时的相对路径校验缺陷：
1. **构造定制 Zip 归档**：在 StreamingZip 中埋入指向目标父目录的跨级符号链接：
   `p0/p1/p2/link -> ../../../var/mobile/Library/SpringBoard`
2. **通过 AFC 暂存**：通过 `com.apple.streaming_zip_conduit` 服务解压至 `/var/mobile/Media` 临时目录。
3. **触发 AirTraffic 同步**：通过 `airtraffic_host` 模拟 iTunes 同步会话，向 `com.apple.atc` 发送 `FileComplete` 消息。
4. **两阶段原子移动**：iOS 底层 `-[ATAirlock processCompletedAsset:]` 顺着符号链接将 payload 移动至沙箱外部的 `/var/mobile/Library/SpringBoard/StatusBarOverrides.archive`。
5. **权限合法性**：AirTraffic 守护进程以 `mobile:mobile` (uid 501) 运行，恰好与 SpringBoard 目录的属主完全一致，无须提升至 root 即可完成写入！

#### 3.3 为什么其他 AirLift 项目失败，而我们成功？(The "Payload vs Vehicle" Breakthrough)
- **行业误区（运送了报废零件）**：PyAirLift、GoldenNugget 等项目虽然掌握了 AirLift 载具，但他们送入的是已被 iOS 27 废弃的旧版 3944 字节 C 结构体（`statusBarOverrides`），导致 SpringBoard 无法识别，误以为是 AirLift 在 iOS 27 上失效。
- **我们的协同突破（全新零件 + 合适载具）**：我们将逆向破解出的现代 `StatusBarOverrides.archive` 二进制归档作为载荷，与 AirLift 深度整合，成功打通了 iOS 27 实机免越狱定制闭环。

#### 3.4 ATAirlock `rename` 限制应对策略 (Existing-File Overwrite Mitigation)
- **底层机制**：Cocoa `[NSFileManager moveItemAtPath:toPath:error:]` 在目标文件已存在时会返回 `NSFileWriteFileExistsError`。
- **我们的应对方案**：
  1. **出厂洁净态**：全新或未定制的 iOS 27 设备上默认不存在 `StatusBarOverrides.archive`，首次部署天然满足创建条件。
  2. **系统自愈清理**：利用 SpringBoard 逆向发现的 `_queue_writeOutArchiveRecord:` 自愈机制，通过下发空归档触发 SpringBoard 主动调用 `removeItemAtURL:` 删除目标文件，重置为空白状态后再行部署。

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

### 2. Standalone Archive Generator & Simulator Deployer (`generate_statusbar_archive.py`)
```bash
# Generate a custom archive file
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
│   ├── iphone14pro_controlcenter_testname.png         # iPhone 14 Pro iOS 27 Control Center Dual SIM ("Testname" / "Test for name")
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
