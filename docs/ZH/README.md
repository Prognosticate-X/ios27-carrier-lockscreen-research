# iOS 27 定制套件技术文档目录 (中文)

本目录汇总了本项目针对 **iOS 27.x 锁屏运营商（Carrier Name）** 与 **锁屏脚注（Lock Screen Footnote）** 展开的全链路逆向分析、实机验证及架构决策文档。所有文档均按照研究时间线排序并按技术类型分类归档。

[English Documentation (英文版)](../EN/README.md)

> **最新状态（2026-10-28）**：当前结论、开放问题与下一阶段研究轨道以 [2026-10-28 研究路线图](04_research_handoffs/2026-10-28_next-research-roadmap.md) 为准；历史文档保留为证据链，部分文档顶部已标注 Superseded。

---

## 📑 文档分类索引

### 1. 架构设计与裁决方案 (Architecture & Solutions)

| 归档日期 | 文档名称 | 核心主题与说明 |
|:---:|---|---|
| 2026-09-26 | [`2026-09-26_risk-register.md`](01_architecture_and_solutions/2026-09-26_risk-register.md) | **设备安全守则与风险登记册**：确立主力设备测试红线，规避系统恢复抹盘风险。 |
| 2026-09-28 | [`2026-09-28_viable-paths.md`](01_architecture_and_solutions/2026-09-28_viable-paths.md) | **定制技术路线可行性全面评估**：梳理 Speakeasy、Carrier Bundle、StatusBarOverrides 等五条路线。 |
| 2026-09-28 | [`2026-09-28_architecture.md`](01_architecture_and_solutions/2026-09-28_architecture.md) | **系统定制整体架构与安全边界全景图**：包含 SpringBoard Overlay 机制与 VPN 状态原生透传架构图。 |
| 2026-09-30 | [`2026-09-30_carrier-footnote-solution.md`](01_architecture_and_solutions/2026-09-30_carrier-footnote-solution.md) | **锁屏定制终局方案与技术裁决报告**：明确锁屏脚注官方通道与现代 StatusBarOverrides.archive 标准。 |

---

### 2. 逆向工程与协议分析 (Reverse Engineering & Protocols)

| 归档日期 | 文档名称 | 核心主题与说明 |
|:---:|---|---|
| 2026-09-28 | [`2026-09-28_carrier-data-flow.md`](02_reverse_engineering/2026-09-28_carrier-data-flow.md) | **Carrier Name 完整数据流逆向分析**：从 SIM 卡 SPN 到 CommCenter、SystemStatusUI 的全链路追踪。 |
| 2026-09-28 | [`2026-09-28_speakeasy-analysis.md`](02_reverse_engineering/2026-09-28_speakeasy-analysis.md) | **Speakeasy Gate 与 FeatureFlags 剖析**：分析 iOS 27 全新状态栏门控开关及写入防护机制。 |
| 2026-09-28 | [`2026-09-28_systemstatusui-analysis.md`](02_reverse_engineering/2026-09-28_systemstatusui-analysis.md) | **SystemStatusUI 现代状态栏发布/订阅模型逆向**：分析 STStatusBarData 与发布者架构。 |
| 2026-10-14 | [`2026-10-14_commcenter-reverse-engineering.md`](02_reverse_engineering/2026-10-14_commcenter-reverse-engineering.md) | **CommCenter 动态运营商 ARM64e 深度反汇编**：定位 `InterCarrierRoamingDisplayNames` 核心函数与偏好层。 |
| **2026-10-29** | [`2026-10-29_rea-alternative-paths-analysis.md`](02_reverse_engineering/2026-10-29_rea-alternative-paths-analysis.md) | **REA + Ghidra 非 StatusBarOverrides 路径全量逆向报告**：反编译 `SystemStatusServer` (299 函数) 与 `SystemStatusUI` (84 函数)，结合 14 Pro 真机取证完成全路径裁决。 |

---

### 3. 硬件验证与生态审计 (Hardware Verification & Ecosystem Audits)

| 归档日期 | 文档名称 | 核心主题与说明 |
|:---:|---|---|
| 2026-09-28 | [`2026-09-28_golden-nugget-diff.md`](03_hardware_and_verification/2026-09-28_golden-nugget-diff.md) | **GoldenNugget Fork 差异与真实性审计**：澄清社区所谓 "patched on iOS 27" 的代码真相。 |
| 2026-10-19 | [`2026-10-19_empirical-verification.md`](03_hardware_and_verification/2026-10-19_empirical-verification.md) | **实机与虚拟机动态验证与归档突破**：CoreSimulator 与物理设备端到端验证突破记录。 |
| 2026-10-19 | [`2026-10-19_dynamic-island-analysis.md`](03_hardware_and_verification/2026-10-19_dynamic-island-analysis.md) | **iPhone 14 Pro 灵动岛蜂窝网络渲染机制分析**：分析单卡 4 格竖条与双卡上下叠放指示器布局。 |
| **2026-10-29** | [`2026-10-29_displayvalue-omission-hardware-verification.md`](03_hardware_and_verification/2026-10-29_displayvalue-omission-hardware-verification.md) | **iPhone 14 Pro 实机验证：`displayValue` 省略 vs `displayValue=4` 的真相**：证伪 GoldenNugget `0fe4d303` 省略 `displayValue` 保留实时信号栏假设（实测解码为 `0` 格灰条，只有控制中心绿色蜂窝按钮为真实实时信号）。 |

---

### 4. 历次研究交接与进度快照 (Chronological Research Handoffs)

| 归档日期 | 文档名称 | 核心主题与说明 |
|:---:|---|---|
| 2026-09-25 | [`2026-09-25_carrier-lockscreen-handoff.md`](04_research_handoffs/2026-09-25_carrier-lockscreen-handoff.md) | **初期研究交接文档**：初始问题梳理、Nugget 路径失效分析与 Agent 研究规划。 |
| 2026-09-28 | [`2026-09-28_carrier-footnote-handoff.md`](04_research_handoffs/2026-09-28_carrier-footnote-handoff.md) | **第二阶段研究交接文档**：聚焦 AirLift 路径遍历利用与 SpringBoard 归档结构定位。 |
| 2026-09-30 | [`2026-09-30_carrier-footnote-latest.md`](04_research_handoffs/2026-09-30_carrier-footnote-latest.md) | **第三阶段研究交接文档**：梳理现代二进制归档格式细节与自愈清理机制。 |
| 2026-10-14 | [`2026-10-14_dynamic-carrier-status.md`](04_research_handoffs/2026-10-14_dynamic-carrier-status.md) | **动态运营商研究状态报告**：上游 CommCenter 逆向突破与实机测试分步路线图。 |
| 2026-10-19 | [`2026-10-19_research-progress-snapshot.md`](04_research_handoffs/2026-10-19_research-progress-snapshot.md) | **显示域研究进度快照**：iPhone 14 Pro 实机锁屏/控制中心显示行为对比与部分覆写探针。 |
| 2026-10-19 | [`2026-10-19_commcenter-preference-injection.md`](04_research_handoffs/2026-10-19_commcenter-preference-injection.md) | **CommCenter 偏好层实机实验交接**：12 域偏好注入实测阴性记录与底层沙箱边界取证。 |
| 2026-10-21 | [`2026-10-21_dynamic-carrier-and-vpn-resolution.md`](04_research_handoffs/2026-10-21_dynamic-carrier-and-vpn-resolution.md) | **终局逆向结论与 VPN 徽标修复交付**：证明 `cellularEntry` 指针原子替换，彻底修复 VPN 丢失缺陷。 |
| **2026-10-28** | [`2026-10-28_next-research-roadmap.md`](04_research_handoffs/2026-10-28_next-research-roadmap.md) | **最新进展审计与下一阶段研究路线图**：安全/实验台审计、飞行模式限时证伪、通用 entry 覆写引擎、兼容性与交付硬化。 |
| **2026-10-28** | [`2026-10-28_airplane-mode-status-matrix.md`](04_research_handoffs/2026-10-28_airplane-mode-status-matrix.md) | **飞行模式联动矩阵实验记录**：REA + Ghidra 名称门控反汇编；`status` 0–5/255 实机矩阵；`status=1` 为 live-fallback；未找到可用的飞行模式联动组合。 |
| **2026-10-28** | [`2026-10-28_name-only-live-override.md`](04_research_handoffs/2026-10-28_name-only-live-override.md) | **Nugget 式“只改名称、其余全实时”路线研究**：运行时枚举证明无字段级 flags；WirelessDomain 备份注入已实机证伪且会触发 Setup Assistant。 |
