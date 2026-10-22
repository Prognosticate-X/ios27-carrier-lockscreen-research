# 通用型 iOS 27 运营商与锁屏定制套件 (Universal iOS 27 Suite)

[English](README.md) | [简体中文](README_ZH.md) | [技术文档中心 (Docs Hub)](docs/README.md)

[![iOS 27 兼容](https://img.shields.io/badge/iOS-27.x%20Final-blue.svg)](https://apple.com/ios)
[![方案类型](https://img.shields.io/badge/%E6%96%B9%E6%A1%88-%E5%85%8D%E8%B6%8A%E7%8B%B1%20%7C%20Backup%20%2B%20AirLift-success.svg)](#-上游合并与真机验证状态)
[![实测状态](https://img.shields.io/badge/%E7%8A%B6%E6%80%81-%E7%89%A9%E7%90%86%E7%9C%9F%E6%9C%BA%E7%AB%AF%E5%88%B0%E7%AB%AF%E9%AA%8C%E8%AF%81%E9%80%9A%E8%BF%87-success.svg)](#-上游合并与真机验证状态)
[![适配设备](https://img.shields.io/badge/%E8%AE%BE%E5%A4%87-%E5%85%A8%E6%9C%BA%E5%9E%8B%E9%80%9A%E7%94%A8%20(%E7%81%B5%E5%8A%A8%E5%B2%9B%20%2B%20%E7%BB%8F%E5%85%B8%E5%B1%8F)-orange.svg)](#-通用硬件与状态栏适配矩阵)

> 面向 **所有 iOS 27.x 设备**（涵盖灵动岛全系与经典刘海/Home键机型）的免越狱底层逆向工程研究框架与自动化工具链，支持持久化定制 **蜂窝网络运营商名称 (Carrier Name)**（单卡/双卡）与 **锁屏底部脚注 (Lock Screen Footnote)**。

---

## 🎯 核心支持状态与摘要 (Executive Summary)

| 定制目标 | iOS 27 状态 | 核心实现机制 | 适用性与范围 |
|---|:---:|---|---|
| **锁屏底部脚注 (Footnote)** | 🟢 **完全可用** | `com.apple.shareddeviceconfiguration` 体系下的 `SharedDeviceConfiguration.plist` | **全机型通用 (100%)** — Apple 官方标准描述文件 (`.mobileconfig`) 或 `SysSharedContainerDomain` 保护性备份注入，完全免越狱零风险。 |
| **运营商名称覆写 (StatusBarOverrides)** | 🟢 **物理真机实测通过** | 现代 `StatusBarOverrides.archive` (`_SBSystemStatusStatusBarOverridesArchiveRecord`) | **物理真机端到端全量验证通过** — 已被主流定制套件 [GoldenNugget](https://github.com/GoldenNugget-Team/GoldenNugget)（v9.5.1 / v9.5.2）在 Commit [`55dfdeab`](https://github.com/GoldenNugget-Team/GoldenNugget/commit/55dfdeab6a9b0c50d55f80ae4aaaa42cc8e083c4) 中正式采纳；核心维护者 `@awesomenull` 在 Commit [`dbb000cb`](https://github.com/GoldenNugget-Team/GoldenNugget/commit/dbb000cb248e91a0ad53378a5f5d227d1540d562) 中正式更新实测结论为 **“Verified end-to-end by me and other users”**。通过 `HomeDomain` 备份恢复管道或本地 AirLift 管道均可完成投递。 |
| **VPN 徽标完整保留** | 🟢 **已修复 (100% 透传)** | 纯净 Overlay 透传：`suppressedBackgroundActivityIdentifiers = []` + 省略 `vpnEntry` | **全机型通用 (100%)** — 彻底修复了 GoldenNugget 及历史归档导致控制中心与状态栏 VPN 图标丢失的缺陷；默认 `--vpn auto` 原生透传系统真实 VPN 状态。 |
| **动态运营商与真实基带信号 (上游)** | 🔴 **实机证伪 (免越狱封锁)** | 已签名 carrier bundle + `/var/wireless/Library/Preferences/` 下的 CommCenter 状态 | **非越狱条件下无可用写入路径** — 反汇编证实 `dataByApplyingOverlay:` 为 entry 对象指针原子覆写；CommCenter 运行在 `_wireless` (UID 257) 下且配置受 SSV 保护，备份注入无法跨越沙箱。详见 [动态运营商终局报告](docs/ZH/04_research_handoffs/2026-10-21_dynamic-carrier-and-vpn-resolution.md)。 |

---

## 📱 通用硬件与状态栏适配矩阵

本项目支持所有能够运行 **iOS 27.x**（Build `24A300`, `24A434`, `24A435`, `24A437`, `24A446` 及更高版本）的设备：

| 设备家族 | 覆盖机型 | 屏幕形态 | 蜂窝网络信号渲染行为 | 实测验证状态 |
|---|---|---|---|---|
| **灵动岛机型 (Pro 系列)** | iPhone 14/15/16 Pro & Pro Max | 灵动岛 (Dynamic Island) | **单卡**：右耳显示全高 4 格竖条信号。<br>**双卡**：原生上下叠放，4 竖条（主卡）+ 4 圆点（副卡）。<br>**文字展示**：锁屏时钟左耳跑马灯轮播；控制中心展开完整双卡标签。 | 🟢 **真机验证 (iPhone 16 Pro Max / 14 Pro) + 模拟器** |
| **灵动岛机型 (数字系列)** | iPhone 15/15 Plus, 16/16 Plus | 灵动岛 (Dynamic Island) | 渲染行为与 Pro 系列一致，响应式适配屏幕边界。 | 🟢 **完全兼容** |
| **经典刘海 / Home 键机型** | iPhone 13/14/Plus, iPhone SE (2/3代) | 经典状态栏 (Classic/Notch) | 状态栏左上角直接常驻显示完整运营商文字（如 `中国广电 5G` + 4格信号）。 | 🟢 **模拟器验证通过** |

---

## 🚀 上游合并与真机验证状态 (Upstream Adoption)

本项目对 `SBSystemStatusStatusBarOverridesArchiver` 的逆向工程突破，彻底打破了社区过去“Speakeasy 彻底封杀 iOS 27 状态栏”的定论：

1. **GoldenNugget 官方主线合并与发版**：[GoldenNugget-Team/GoldenNugget](https://github.com/GoldenNugget-Team/GoldenNugget) 已在 Commit [`55dfdeab`](https://github.com/GoldenNugget-Team/GoldenNugget/commit/55dfdeab6a9b0c50d55f80ae4aaaa42cc8e083c4) 中正式采纳本仓库研究成果，并在 **GoldenNugget v9.5.1 与 v9.5.2** 中向全量用户发布支持。
2. **端到端物理真机验证确认**：在 Commit [`dbb000cb`](https://github.com/GoldenNugget-Team/GoldenNugget/commit/dbb000cb248e91a0ad53378a5f5d227d1540d562) 与官方文档 [`docs/iOS27_StatusBar_Research.md`](https://github.com/GoldenNugget-Team/GoldenNugget/blob/main/docs/iOS27_StatusBar_Research.md) 中，GoldenNugget 核心维护者 `@awesomenull` 正式确认状态为：**`"Verified end-to-end by me and other users"`**。
3. **HomeDomain 备份恢复管道突破**：GoldenNugget 团队验证确认 `/var/mobile/Library/SpringBoard/StatusBarOverrides.archive` 属于标准 `HomeDomain`，可通过系统备份恢复管道（`MobileBackup2`）直接投递，彻底绕过 AirTraffic ATAirlock 的 rename 覆盖限制。
4. **AirLift 通道真机端到端实测**：本仓库自身的原生 AirLift 独立通道也在 **iPhone 16 Pro Max（iOS 27.0, 24A437）** 与 **iPhone 14 Pro（iOS 27.0.1, 24A446）** 上完成了有线 USB 部署验证与持久化测试。

---

## 📸 视觉效果实测截图

| 控制中心双卡展开 (iPhone 14 Pro 实测) | 经典顶部状态栏 (iPhone SE 实测) |
|:---:|:---:|
| <img src="assets/iphone14pro_controlcenter_testname.png" width="360" alt="iPhone 14 Pro iOS 27 控制中心双卡" /> | <img src="assets/iphone_se_carrier_screenshot.png" width="360" alt="iPhone SE 状态栏" /> |
| **双卡自定义运营商**：`[P] Testname` 与 `[S] Test for name` | **单卡自定义运营商**：`中国广电 5G` |

---

## 🏗️ 核心架构与底层机制

### 1. 现代 StatusBarOverrides.archive 架构
iOS 27 不再使用旧版 3944 字节的 C 结构体，而是采用 **NSKeyedArchiver 二进制 Property List**：
- **目标路径**：`/var/mobile/Library/SpringBoard/StatusBarOverrides.archive`
- **属主权限**：`mobile:mobile` (0644)
- **根类对象**：`_SBSystemStatusStatusBarOverridesArchiveRecord`
  - `statusBarData`: `STStatusBarData`（包含 `cellularEntry` 与可选的 `secondaryCellularEntry`）
  - `suppressedBackgroundActivityIdentifiers`: `NSSet`（置空以确保 VPN 等系统活动项不被抑制）

### 2. SpringBoard Overlay 机制与 VPN 原生透传修复
```text
┌────────────────────────────────────────────────────────────────────────┐
│                   SpringBoard Overlay Processing                       │
│                                                                        │
│   Native System Status Items                StatusBarOverrides.archive │
│   (CommCenter, Baseband, VPN)               (_SBSystemStatus...Record) │
│               │                                         │              │
│               ▼                                         ▼              │
│   [Base STStatusBarData] ─────────────► [-[STStatusBarData             │
│   - cellularEntry (live baseband)        dataByApplyingOverlay:]]      │
│   - vpnEntry (live VPN connection)                      │              │
│               │                                         │              │
│               ├─────────────────────────────────────────┤              │
│               ▼                                         ▼              │
│   [cellularEntry: Pointer Replace]        [vpnEntry: Native Passthrough]
│   • cellularEntry 被整块指针替换            • overlay.vpnEntry == nil      │
│   • 渲染自定义运营商名称                    • cbz 跳过替换，100% 透传真实VPN│
│   • 静态声明无法解耦飞行模式                • 彻底解决 GoldenNugget 丢失问题│
└────────────────────────────────────────────────────────────────────────┘
```
- **原子替换特性**：反汇编 `-[STStatusBarData dataByApplyingOverlay:]` (`0x20e4ac960`) 证明覆盖是以条目指针为单位整块替换。静态归档要求 `status=5, enabled=true`，因此开启飞行模式后文字仍常驻。
- **VPN 丢失修复**：早期工具因序列化空 `vpnEntry` 或向抑制集合注入 VPN 标识导致图标消失。本工具在默认 `auto` 模式下**彻底省略 `vpnEntry`**，SpringBoard 自动保留真实 VPN 状态项，连接时正常点亮，断开时正常隐藏。

---

## 🛠️ 工具链与快速上手指南

### 1. 物理真机通用部署 (`tools/airlift_carrier_deploy.py`)
```bash
# 编译本地原生 AirLift 辅助模块 (首次运行必选)
cd airlift && make && cd ..

# 单卡部署：设置运营商名称 (默认 --vpn auto 完整保留系统真实 VPN 状态)
python3 tools/airlift_carrier_deploy.py -c "中国移动 5G" -b 4 -t 5g

# 双卡部署：设置主卡与副卡名称及角标
python3 tools/airlift_carrier_deploy.py \
  -c "主卡 5G" --badge "P" \
  -s "副卡 5G" --secondary-badge "S"

# 重置 / 恢复官方原生运营商
python3 tools/airlift_carrier_deploy.py --reset

# 二次更换文字时自动覆写 (突破 ATAirlock rename 限制)
python3 tools/airlift_carrier_deploy.py -c "新运营商 5G" --force-overwrite

# 单独触发 SpringBoard 重启以加载覆写
python3 tools/airlift_carrier_deploy.py --respring
```

### 2. 现代可视化 Web GUI 控制台 (`tools/gui_server.py`)
```bash
python3 tools/gui_server.py
```
- **核心特性**：免安装依赖、自动探测 USB 物理直连设备、支持中英双语界面。
- **功能集成**：一键极速部署、两阶段自动覆写、一键系统复位、VPN 徽标状态控制（自动透传 / 强制显示 / 隐藏）、锁屏脚注 `.mobileconfig` 导出。

### 3. 独立归档生成与模拟器调试 (`tools/generate_statusbar_archive.py`)
```bash
# 生成自定义归档文件 (默认 auto 自动保留真实 VPN 徽标)
python3 tools/generate_statusbar_archive.py -c " Apple 5G" -b 4 -t 5g -o custom.archive

# 生成并直接部署至当前运行的 iOS 27 模拟器
python3 tools/generate_statusbar_archive.py -c "TestCarrier" --deploy-simulator booted

# 逆向反序列化检查现有归档结构
python3 tools/generate_statusbar_archive.py -i custom.archive
```

---

## 📁 规范化仓库结构与技术文档中心

全量底层逆向工程报告、实机实验记录与阶段性交接文档已按**技术分类**与**时间线**规范化整理，并提供全量双语版本：

👉 **[前往完整技术文档中心 (Docs Hub)](docs/README.md)** | **[中文文档目录 (ZH)](docs/ZH/README.md)** | **[English Docs (EN)](docs/EN/README.md)**

```text
docs/
├── README.md                              # 技术文档中心主索引导航
├── ZH/                                    # 简体中文全量文档 (按时间线与类型分类)
│   ├── 01_architecture_and_solutions/     # 架构设计、安全红线与可行性评估
│   ├── 02_reverse_engineering/            # 系统二进制反汇编、数据流与门控逆向
│   ├── 03_hardware_and_verification/      # 物理机实测、灵动岛渲染机制与生态审计
│   └── 04_research_handoffs/              # 历次研究交接、进度快照与终局交付
└── EN/                                    # Full English Documentation
    ├── 01_architecture_and_solutions/     # Architecture, Safety Boundaries & Verdicts
    ├── 02_reverse_engineering/            # Binary Disassembly, Data Flow & Gating Analysis
    ├── 03_hardware_and_verification/      # Hardware Verification, Dynamic Island & Audits
    └── 04_research_handoffs/              # Chronological Research Handoffs & Snapshots
```

---

## ⚠️ 主力机安全守则与已知局限性

1. **绝对安全性保障**：本工具链仅向 SpringBoard 用户专属目录（`mobile:mobile`）写入 UI 状态栏归档，**严禁且绝不触碰 `/var/preferences` 等系统敏感目录**，杜绝触发 Apple 在 iOS 27 上新增的 Security State Recovery 全盘抹除逻辑。
2. **首次部署生效时机**：SpringBoard 仅在自身启动加载时读取一次 `StatusBarOverrides.archive`。首次注入后必须触发一次 SpringBoard 重启（`--respring` 或 GUI 专属按钮）；一旦被采纳，覆写状态会在后续整机重启后持续保持。
3. **静态覆写与飞行模式**：`StatusBarOverrides.archive` 属于静态视图层覆写，开启飞行模式后自定义文字仍会保持显示。若需完全不破坏主卡基带动态格数与飞行模式联动，推荐在双卡设备上将副卡卡槽作为个性化展示卡槽。
4. **关于 `--partial` 选项**：该模式在反序列化时会将缺失字段赋值为 0，导致 5G/LTE 等制式文字被抑制，且仍无法解耦飞行模式，因此**不建议在生产环境中使用**。

---

## 🔗 参考项目与致谢 (References)

- **AirLift 核心与通道技术**：[AirLift (0xjohnnydev/airlift)](https://github.com/0xjohnnydev/airlift) 与 [PyAirLift (awesomenull-dev/PyAirLift)](https://github.com/awesomenull-dev/PyAirLift)。
- **社区定制套件**：[GoldenNugget (GoldenNugget-Team/GoldenNugget)](https://github.com/GoldenNugget-Team/GoldenNugget) 与 [GoldenNugget-Mobile](https://github.com/GoldenNugget-Team/GoldenNugget-mobile)。
- **iOS 通讯协议栈**：[pymobiledevice3 (doronz88/pymobiledevice3)](https://github.com/doronz88/pymobiledevice3)。
- **官方管理规范**：[Apple Device Management Schema](https://github.com/apple/device-management)。

---

## 📜 许可证与免责声明

本项目遵循 MIT 许可证。所有研究与工具仅供**个人学习、防御性安全研究与技术探索**使用。Apple、iPhone、iOS、SpringBoard 及 Dynamic Island 是 Apple Inc. 的注册商标。