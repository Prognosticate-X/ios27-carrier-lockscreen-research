# iOS 27 Carrier & Lock Screen Documentation Hub

Welcome to the technical documentation repository for the iOS 27 Carrier & Lock Screen Customization Suite.

[简体中文文档目录 (Chinese Documentation Index)](ZH/README.md) | [English Documentation Index (英文文档目录)](EN/README.md)

---

## 📁 Repository Documentation Matrix / 文档分类矩阵

```text
docs/
├── README.md                      # Documentation Hub & Sitemap (This File)
├── ZH/                            # 简体中文全量技术文档
│   ├── README.md                  # 中文文档导航与目录树
│   ├── 01_architecture_and_solutions/  # 架构设计、安全红线与可行性方案裁决
│   ├── 02_reverse_engineering/         # 系统二进制反汇编、数据流与门控逆向
│   ├── 03_hardware_and_verification/   # 物理机实测、灵动岛渲染机制与生态审计
│   └── 04_research_handoffs/           # 历次研究交接、进度快照与终局交付
└── EN/                            # Full English Technical Documentation
    ├── README.md                  # English Documentation Sitemap & Navigation
    ├── 01_architecture_and_solutions/  # Architecture, Safety Boundaries & Verdicts
    ├── 02_reverse_engineering/         # Binary Disassembly, Data Flow & Gating Analysis
    ├── 03_hardware_and_verification/   # Hardware Verification, Dynamic Island & Audits
    └── 04_research_handoffs/           # Chronological Research Handoffs & Snapshots
```

---

## 📌 Quick Document Locator / 核心文档速查表

| Subject / 主题 | Chinese Document / 中文文档 | English Document / 英文文档 | Date / 归档日期 |
|---|---|---|:---:|
| **Overall Architecture & VPN Passthrough**<br>系统定制整体架构与 VPN 原生透传 | [`docs/ZH/01_architecture_and_solutions/2026-09-28_architecture.md`](ZH/01_architecture_and_solutions/2026-09-28_architecture.md) | [`docs/EN/01_architecture_and_solutions/2026-09-28_architecture.md`](EN/01_architecture_and_solutions/2026-09-28_architecture.md) | 2026-09-28 |
| **Viable Paths & Feasibility Evaluation**<br>定制技术路线可行性全面评估 | [`docs/ZH/01_architecture_and_solutions/2026-09-28_viable-paths.md`](ZH/01_architecture_and_solutions/2026-09-28_viable-paths.md) | [`docs/EN/01_architecture_and_solutions/2026-09-28_viable-paths.md`](EN/01_architecture_and_solutions/2026-09-28_viable-paths.md) | 2026-09-28 |
| **Lock Screen Footnote Technical Verdict**<br>锁屏底部脚注终局方案与官方规范 | [`docs/ZH/01_architecture_and_solutions/2026-09-30_carrier-footnote-solution.md`](ZH/01_architecture_and_solutions/2026-09-30_carrier-footnote-solution.md) | [`docs/EN/01_architecture_and_solutions/2026-09-30_carrier-footnote-solution.md`](EN/01_architecture_and_solutions/2026-09-30_carrier-footnote-solution.md) | 2026-09-30 |
| **CommCenter ARM64e Disassembly Deep Dive**<br>CommCenter 动态运营商汇编级深度逆向 | [`docs/ZH/02_reverse_engineering/2026-10-14_commcenter-reverse-engineering.md`](ZH/02_reverse_engineering/2026-10-14_commcenter-reverse-engineering.md) | [`docs/EN/02_reverse_engineering/2026-10-14_commcenter-reverse-engineering.md`](EN/02_reverse_engineering/2026-10-14_commcenter-reverse-engineering.md) | 2026-10-14 |
| **Dynamic Island Cellular Rendering Heuristics**<br>灵动岛机型蜂窝网络渲染与单双卡指示器 | [`docs/ZH/03_hardware_and_verification/2026-10-19_dynamic-island-analysis.md`](ZH/03_hardware_and_verification/2026-10-19_dynamic-island-analysis.md) | [`docs/EN/03_hardware_and_verification/2026-10-19_dynamic-island-analysis.md`](EN/03_hardware_and_verification/2026-10-19_dynamic-island-analysis.md) | 2026-10-19 |
| **Dynamic Carrier Conclusion & VPN Fix Handoff**<br>动态运营商终局结论与 VPN 徽标修复交付 | [`docs/ZH/04_research_handoffs/2026-10-21_dynamic-carrier-and-vpn-resolution.md`](ZH/04_research_handoffs/2026-10-21_dynamic-carrier-and-vpn-resolution.md) | [`docs/EN/04_research_handoffs/2026-10-21_dynamic-carrier-and-vpn-resolution.md`](EN/04_research_handoffs/2026-10-21_dynamic-carrier-and-vpn-resolution.md) | 2026-10-21 |
