# 通用型 iOS 27 运营商与锁屏定制套件 (Universal iOS 27 Suite)

[English](README.md) | [简体中文](README_ZH.md)

> 面向 **所有 iOS 27.x 设备**（涵盖灵动岛全系与经典刘海/Home键机型）的通用型、免越狱底层逆向工程研究框架与自动化工具链，支持持久化定制 **蜂窝网络运营商名称 (Carrier Name)**（单卡/双卡）与 **锁屏底部脚注 (Lock Screen Footnote)**。

---

## 🎯 核心摘要与支持状态

| 定制目标 | iOS 27.x 状态 | 核心实现机制 | 适用性与范围 |
|---|---|---|---|
| **锁屏底部脚注 (Footnote)** | 🟢 **完全可用** | `com.apple.shareddeviceconfiguration` 体系下的 `SharedDeviceConfiguration.plist` | **全机型通用 (100%)** — Apple 官方标准描述文件 (`.mobileconfig`) 通道或通过 `SysSharedContainerDomain` 保护性备份注入。完全零风险、免越狱。 |
| **运营商名称覆写 (Carrier Name)** | 🟢 **实测验证 (重大突破)** | 现代 `StatusBarOverrides.archive` (`_SBSystemStatusStatusBarOverridesArchiveRecord`) | **全机型通用 (AirLift 管道)** — 已在 iOS 27 模拟器及实机环境完成验证。SpringBoard 原生加载 `/var/mobile/Library/SpringBoard/` 目录归档（属主 `mobile:mobile`）。完全绕过 CommCenter 签名屏障与 Speakeasy 特性开关！ |

---

## 📱 通用硬件与状态栏适配矩阵

本项目支持所有能够升级并运行 **iOS 27.x**（Build `24A300`, `24A434`, `24A435`, `24A437` 及更高版本）的设备：

| 设备家族 | 覆盖机型 | 屏幕形态 | 蜂窝网络信号渲染行为 | 实测验证状态 |
|---|---|---|---|---|
| **灵动岛机型 (Pro 系列)** | iPhone 14 Pro / Pro Max<br>iPhone 15 Pro / Pro Max<br>iPhone 16 Pro / Pro Max | 灵动岛 (Dynamic Island) | **单卡**：右耳显示全高 4 格竖条信号。<br>**双卡**：原生上下叠放，上方 4 竖条（主卡）+ 下方 4 圆点（副卡）。<br>**文字展示**：锁屏大时钟模式下左耳跑马灯轮播；控制中心下拉完整展开双卡标签（`[P] 运营商`，`[S] 运营商`）。 | 🟢 **实测验证通过 (已留证)** |
| **灵动岛机型 (数字系列)** | iPhone 15 / 15 Plus<br>iPhone 16 / 16 Plus | 灵动岛 (Dynamic Island) | 渲染行为与 Pro 系列完全一致，响应式适配药丸屏幕边界。 | 🟢 **完全兼容** |
| **经典刘海 / 经典状态栏** | iPhone 13 / 14 / Plus<br>iPhone SE (第 2 / 3 代) | 经典刘海屏 / 16:9 传统屏 | 状态栏左上角直接常驻显示完整运营商文字（如 `中国广电 5G` + 4格信号）。 | 🟢 **实测验证通过 (已留证)** |

---

## 📸 真实设备视觉证据 (iOS 27.0 Release)

| 灵动岛机型控制中心双卡实测 (iPhone 14 Pro, iOS 27.0) | 经典状态栏单卡实测 (iPhone SE, iOS 27.0) |
|:---:|:---:|
| <img src="assets/iphone14pro_controlcenter_testname.png" width="360" alt="iPhone 14 Pro 控制中心双卡实测" /> | <img src="assets/iphone_se_carrier_screenshot.png" width="360" alt="iPhone SE 经典状态栏实测" /> |
| **双卡自定义运营商**：`[P] Testname` 与 `[S] Test for name` | **单卡自定义运营商**：`中国广电 5G` |

---

## 🏗️ 系统架构与底层逆向成果

### 1. 现代 StatusBarOverrides.archive 架构解析
与 iOS 14–16 要求 3944 字节旧 C 结构体的机制不同，iOS 27 采用标准的 **`NSKeyedArchiver` 二进制属性列表 (bplist)**：
- **目标路径**：`/var/mobile/Library/SpringBoard/StatusBarOverrides.archive`
- **文件属主**：`mobile:mobile` (0644 权限)
- **根类结构**：`_SBSystemStatusStatusBarOverridesArchiveRecord`
  - `statusBarData`：`STStatusBarData`（来自 `SystemStatus.framework`）
  - `suppressedBackgroundActivityIdentifiers`：`NSSet`（空集合）
- **蜂窝网络条目 (Cellular Entries)**：
  - `cellularEntry`：主卡 `STStatusBarDataCellularEntry`
    - `string` / `crossfadeString`：自定义运营商名称 UTF-8 字符串
    - `displayValue`：信号格数 (0–4)
    - `type`：网络制式类型 (10 = 5G, 9 = LTE, 等)
    - `badgeString`：SIM 卡标识符（如 `"P"`, `"1"`, `"主卡"`）
    - `status`：连接状态 (5 = 已连接)
    - `enabled`：`true`
  - `secondaryCellularEntry`：副卡 `STStatusBarDataCellularEntry`（注入后自动激活 Apple 原生上下叠放双卡 UI）

### 2. SpringBoard 归档生命周期逆向
通过对 `SpringBoard.framework` 内 `SBSystemStatusStatusBarOverridesArchiver` 的汇编级逆向分析：
- **启动读取 (`0x5b5688`)**：SpringBoard 初始化时，调用 `_queue_readStatusBarOverridesArchiveRecord` 解析该归档，更新 `STStatusBarOverridesStatusDomainPublisher` 并直传 `SystemStatusUI`。
- **空状态自愈淘汰 (`0x5b5444`)**：若解码出的记录为空或被重置，SpringBoard 会主动在磁盘调用 `removeItemAtURL:` 抹除归档，恢复出厂默认运营商状态。
- **`systemstatusd` 内存缓存同步机制**：在 iOS 27 中，系统状态服务端 `systemstatusd` 在内存中常驻发布者数据。在线更新归档时，必须协同重启 `systemstatusd` 与 `SpringBoard`，防止旧内存缓存反向覆盖刚刚写入的新归档。

---

## ✈️ AirLift 实机免越狱传输管道与沙箱逃逸

```text
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                                 物理真机 AirLift 传输链路                               │
│                                                                                        │
│   [Mac 宿主机 CLI] ───────────► [AirLift 漏洞引擎] ───────────► [iOS AirTraffic]      │
│  airlift_carrier_deploy.py       StreamingZip + Books.plist         com.apple.atc      │
│                                                                           │            │
│                                                                           ▼ (路径穿越逃逸)
│   [SpringBoard 加载] ◄─────── [StatusBarOverrides.archive] ◄────── [ATAirlock 移动]    │
│   SystemStatusUI 展现         /var/mobile/Library/SpringBoard/    (以 mobile:501 运行) │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

### 1. 为什么实机部署必须依赖 AirLift？
- **模拟器 vs 物理设备**：在 Mac 本地 CoreSimulator 调试时，宿主机拥有直接文件系统读写权限（`~/Library/Developer/CoreSimulator/...`）；但在物理 iPhone 上，iOS 沙箱机制禁止外部 USB 直接写入系统目录 `/var/mobile/Library/SpringBoard/`。
- **AirLift 的核心定位**：AirLift 利用 Apple 原生媒体同步协议漏洞，充当了**免越狱将定制文件送入 SpringBoard 的“特许运输载具”**。

### 2. AirTraffic Books 路径遍历逃逸原理
AirLift 利用了 iOS 媒体同步服务（`com.apple.atc` / AirTraffic）在处理 Books（电子书）同步资产时的相对路径校验缺陷：
1. **构造定制 Zip 归档**：在 StreamingZip 中埋入指向目标父目录的跨级符号链接：
   `p0/p1/p2/link -> ../../../var/mobile/Library/SpringBoard`
2. **通过 AFC 暂存**：通过 `com.apple.streaming_zip_conduit` 服务解压至 `/var/mobile/Media` 临时目录。
3. **触发 AirTraffic 同步**：通过 `airtraffic_host` 模拟 iTunes 同步会话，向 `com.apple.atc` 发送 `FileComplete` 消息。
4. **两阶段原子移动**：iOS 底层 `-[ATAirlock processCompletedAsset:]` 顺着符号链接将 payload 移动至沙箱外部的 `/var/mobile/Library/SpringBoard/StatusBarOverrides.archive`。
5. **权限合法性**：AirTraffic 守护进程以 `mobile:mobile` (uid 501) 运行，恰好与 SpringBoard 目录的属主完全一致，无须提升至 root 即可完成写入！

### 3. 核心问题解答：为什么别人用 AirLift 失败，而我们成功？
- **行业误区（运送了报废零件）**：PyAirLift、GoldenNugget 等项目虽然掌握了 AirLift 载具，但他们送入的是已被 iOS 27 废弃的旧版 3944 字节 C 结构体（`statusBarOverrides`），导致 SpringBoard 无法识别，误以为是 AirLift 在 iOS 27 上失效。
- **我们的协同突破（全新零件 + 合适载具）**：我们将逆向破解出的现代 `StatusBarOverrides.archive` 二进制归档作为载荷，与 AirLift 深度整合，成功打通了 iOS 27 实机免越狱定制闭环。

### 4. ATAirlock `rename` 限制应对策略
- **底层机制**：Cocoa `[NSFileManager moveItemAtPath:toPath:error:]` 在目标文件已存在时会返回 `NSFileWriteFileExistsError`。
- **通用应对方案**：
  1. **出厂洁净态**：全新或未定制的 iOS 27 设备上默认不存在 `StatusBarOverrides.archive`，首次部署天然满足创建条件。
  2. **系统自愈清理**：利用 SpringBoard 逆向发现的 `_queue_writeOutArchiveRecord:` 自愈机制，通过下发空归档触发 SpringBoard 主动调用 `removeItemAtURL:` 删除目标文件，重置为空白状态后再行部署。

---

## 🔒 锁屏底部脚注方案架构 (Lock Screen Footnote)

锁屏脚注是 Apple 官方设备管理标准字段（`com.apple.shareddeviceconfiguration`）：
- **目标文件**：`/var/containers/Shared/SystemGroup/systemgroup.com.apple.configurationprofiles/Library/ConfigurationProfiles/SharedDeviceConfiguration.plist`
- **核心键值**：`<key>LockScreenFootnote</key><string>自定义文字</string>`
- **双通道交付途径**：
  1. **官方标准描述文件通道 (`.mobileconfig`)**：完全零门槛、零漏洞依赖，通过 Safari、隔空投送 (AirDrop) 或 Apple Configurator 即可一键导入（示例见 [`examples/footnote_sample.mobileconfig`](examples/footnote_sample.mobileconfig)）。
  2. **保护性备份注入管道 (`MobileBackup2`)**：通过注入 `SysSharedContainerDomain` 实现非监督设备免弹窗静默导入（如 GoldenNugget-Mobile 的 `BackupInjector.swift` 所实现）。

---

## 🛠️ 工具链与快速上手指南

### 1. 物理真机通用部署 (`tools/airlift_carrier_deploy.py`)
```bash
# 编译本地原生 AirLift 辅助模块 (MobileDevice + AirTrafficHost)
cd airlift && make && cd ..

# 单卡定制：设置运营商名称
python3 tools/airlift_carrier_deploy.py -c "中国移动 5G" -b 4 -t 5g

# 双卡定制：设置主卡与副卡名称及角标
python3 tools/airlift_carrier_deploy.py \
  -c "CMI" --badge "P" \
  -s "T-mobile" --secondary-badge "S"

# 重置 / 恢复系统官方默认运营商
python3 tools/airlift_carrier_deploy.py --reset

# 本地打包与校验测试 (无需连接真机)
python3 tools/airlift_carrier_deploy.py -c "中国广电 5G" --dry-run
```

### 2. 独立归档生成器与模拟器部署 (`tools/generate_statusbar_archive.py`)
```bash
# 生成定制二进制归档文件
python3 tools/generate_statusbar_archive.py -c " Apple 5G" -b 4 -t 5g -o custom.archive

# 生成并直接部署至当前运行的模拟器，协同重启 SpringBoard 与 systemstatusd 实时生效
python3 tools/generate_statusbar_archive.py \
  -c "Testname" --badge "P" \
  -s "Test for name" --secondary-badge "S" \
  --deploy-simulator booted

# 逆向解析 / 查看现有归档结构
python3 tools/generate_statusbar_archive.py -i custom.archive
```

---

## 📁 规范化仓库文件结构

```text
.
├── README.md                                          # 英文主文档 (English Primary)
├── README_ZH.md                                       # 中文完整同步文档 (Chinese Synchronized)
├── tools/                                             # 跨设备通用自动化工具链
│   ├── airlift_carrier_deploy.py                      # 通用型 AirLift 物理真机部署 CLI
│   └── generate_statusbar_archive.py                  # 现代二进制归档生成与模拟器直推工具
├── airlift/                                           # 原生 AirLift 漏洞利用与同步子系统
│   ├── Sources/                                       # 原生 Objective-C 模块 (device_helper.m, airtraffic_host.m)
│   ├── Makefile                                       # Clang 跨架构编译脚本
│   └── airlift_carrier_deploy.py                      # AirLift 部署执行器
├── examples/                                          # 开箱即用的样例载荷
│   ├── footnote_sample.mobileconfig                   # 锁屏底部脚注官方描述文件模板
│   ├── StatusBarOverrides_sample.archive              # 单卡现代二进制归档样例
│   ├── StatusBarOverrides_dualsim_sample.archive      # 双卡现代二进制归档样例
│   └── StatusBarOverrides_reset_sample.archive        # 恢复默认出厂设置归档
├── assets/                                            # 实测高清验证截图
│   ├── iphone14pro_controlcenter_testname.png         # iPhone 14 Pro iOS 27 控制中心双卡实测图
│   ├── iphone14pro_baseline.png                       # iPhone 14 Pro 初始基准图
│   ├── iphone14pro_singlesim.png                      # iPhone 14 Pro 单卡满格实测图
│   ├── iphone14pro_dualsim.png                        # iPhone 14 Pro 双卡叠放指示器实测图
│   ├── iphone_se_carrier_screenshot.png               # iPhone SE 经典状态栏单卡实测图
│   └── simctl_override_screenshot.png                 # iPhone 16 Pro Max 灵动岛顶栏捕获图
└── docs/                                              # 深度底层逆向工程研究报告
    ├── handoffs/                                      # 历次研究交接与阶段性论证归档
    │   ├── iOS27_Carrier_LockScreen_Research_Handoff_2026-09-25.md
    │   ├── iOS27_Carrier_Footnote_Research_Handoff_2026-09-28.md
    │   └── iOS27_Carrier_Footnote_Latest_Research_2026-09-30.md
    ├── iOS27_Carrier_Footnote_Solution.md             # 终局完整技术方案与安全裁决报告
    ├── architecture.md                                # 系统全景架构与安全边界报告
    ├── carrier-data-flow.md                           # SIM -> CommCenter -> SystemStatusUI 全链路逆向
    ├── golden-nugget-diff.md                          # GoldenNugget 各分支 Git 拓扑与源码审计
    ├── iphone14pro-dynamic-island-cellular-analysis.md # 灵动岛蜂窝网络渲染机制与真机实测深度报告
    ├── ios27-carrier-empirical-verification.md        # 模拟器实证与现代归档突破记录
    ├── risk-register.md                               # 设备安全守则与风险熔断机制
    ├── speakeasy-analysis.md                          # FeatureFlags 框架与 Speakeasy 门控逆向分析
    ├── systemstatusui-analysis.md                     # 现代 SystemStatus 发布/订阅模型技术拆解
    └── viable-paths.md                                # 各技术路径可行性详细论证
```

---

## ⚠️ 主力机安全守则与风险熔断机制

1. **硬编码设备黑名单阻断**：`tools/airlift_carrier_deploy.py` 内部永久强制硬编码主力机识别码（如 `00008140-001C29663062201C`），严禁对其执行任何写入或连接。
2. **严禁越界修改系统目录**：写入范围被严格限定在 `mobile:mobile` 权限的 `/var/mobile/Library/SpringBoard`，绝不修改 `/var/preferences`，彻底免疫 iOS 27 Security State Recovery Wipe（抹机保护）。
3. **Books 数据库无痕自愈**：每次执行 AirTraffic 资产同步前后均对 Books 状态进行完整快照与还原，保证媒体数据库零污染。

---

## 🔗 参考项目与致谢 (References & Credits)

### 1. AirLift 核心与通道技术
- [AirLift (0xjohnnydev/airlift)](https://github.com/0xjohnnydev/airlift) — 原生 AirTraffic Books 路径遍历沙箱逃逸引擎。
- [PyAirLift (awesomenull-dev/PyAirLift)](https://github.com/awesomenull-dev/PyAirLift) — 支持 iOS 27 的 AirTraffic 通道逃逸 Python 实现。
- [AirCard-iOS (Mak5er / EpochME)](https://github.com/Mak5er/AirCard-iOS) — 端侧集成 `AirliftFFI.xcframework` 的 Rust 运行时项目。
- [pymobiledevice3 (doronz88/pymobiledevice3)](https://github.com/doronz88/pymobiledevice3) — 纯 Python 实现的跨平台 iOS 通讯协议栈。

### 2. 定制工具与相关框架
- [Nugget (leminlimez/Nugget)](https://github.com/leminlimez/Nugget) — 原始 iOS 移动设备定制工具框架。
- [GoldenNugget (GoldenNugget-Team/GoldenNugget)](https://github.com/GoldenNugget-Team/GoldenNugget) — 桌面端综合定制套件。
- [GoldenNugget-Mobile (GoldenNugget-Team/GoldenNugget-mobile)](https://github.com/GoldenNugget-Team/GoldenNugget-mobile) — 基于 MobileBackup2 的 iOS 27 端侧定制项目。
- [GoldenNugget fork (phanquocviet8x/GoldenNugget)](https://github.com/phanquocviet8x/GoldenNugget) — 历史 iOS 27 状态栏代码分支分析参考。

### 3. 蜂窝网络与运营商配置研究
- [iOS Carrier Bundle (VCTGomes/ios-carrier-bundle)](https://github.com/VCTGomes/ios-carrier-bundle) — iOS 27 官方 Carrier Bundle 提取与逆向分析。
- [iOS Carrier Bundles (dwilliamsuk/ios-carrier-bundles)](https://github.com/dwilliamsuk/ios-carrier-bundles) — 运营商配置资产参考仓库。

### 4. Apple 官方标准与历史漏洞参考
- [Apple Device Management Profile Schema](https://github.com/apple/device-management) — Apple 官方 MDM `com.apple.shareddeviceconfiguration` 规范定义。
- [bad_query (forcequitOS/bad_query)](https://github.com/forcequitOS/bad_query) — iOS 27 沙箱逃逸早期研究。
- [WorkPlot (gievano/WorkPlot)](https://github.com/gievano/WorkPlot) — 早期 iOS 27 沙箱探索。
- [Erosion (jailbreakdotparty/Erosion)](https://github.com/jailbreakdotparty/Erosion) — 历史文件操作与权限分析参考。

---

## 📜 许可证与免责声明

本项目仅供**安全防御研究与逆向工程教学**使用。Apple、iPhone、iOS、SpringBoard 以及 Dynamic Island 均为 Apple Inc. 之注册商标。
