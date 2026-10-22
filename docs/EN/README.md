# iOS 27 Customization Suite Documentation Index (English)

This directory houses the comprehensive reverse engineering, empirical verification, architectural blueprints, and chronological research handoffs for **Cellular Carrier Name** and **Lock Screen Footnote** customization on **iOS 27.x**. All documents are classified by technical type and ordered chronologically.

[中文文档目录 (Chinese Documentation Index)](../ZH/README.md)

---

## 📑 Documentation Categories & Index

### 1. Architecture & Solutions

| Date | Document | Core Subject & Overview |
|:---:|---|---|
| 2026-09-26 | [`2026-09-26_risk-register.md`](01_architecture_and_solutions/2026-09-26_risk-register.md) | **Device Safety Guidelines & Risk Register**: Boundaries for testing on daily-driver devices and preventing Security State Recovery wipes. |
| 2026-09-28 | [`2026-09-28_viable-paths.md`](01_architecture_and_solutions/2026-09-28_viable-paths.md) | **Technical Viability Assessment**: Feasibility analysis across Speakeasy, Carrier Bundles, SystemStatusUI, and StatusBarOverrides. |
| 2026-09-28 | [`2026-09-28_architecture.md`](01_architecture_and_solutions/2026-09-28_architecture.md) | **Overall Architecture & Security Boundaries**: System panoramic architecture, SpringBoard Overlay mechanics, and clean VPN passthrough. |
| 2026-09-30 | [`2026-09-30_carrier-footnote-solution.md`](01_architecture_and_solutions/2026-09-30_carrier-footnote-solution.md) | **Final Technical Solution & Security Verdict**: Native MDM profile channel for Footnote and modern binary StatusBarOverrides standard. |

---

### 2. Reverse Engineering & Protocols

| Date | Document | Core Subject & Overview |
|:---:|---|---|
| 2026-09-28 | [`2026-09-28_carrier-data-flow.md`](02_reverse_engineering/2026-09-28_carrier-data-flow.md) | **Carrier Name End-to-End Data Flow**: From SIM SPN to CommCenter and SystemStatusUI rendering pipeline. |
| 2026-09-28 | [`2026-09-28_speakeasy-analysis.md`](02_reverse_engineering/2026-09-28_speakeasy-analysis.md) | **Speakeasy Gate & FeatureFlags Analysis**: Deep dive into iOS 27's new status bar gating and write protections. |
| 2026-09-28 | [`2026-09-28_systemstatusui-analysis.md`](02_reverse_engineering/2026-09-28_systemstatusui-analysis.md) | **SystemStatusUI Modern Status Bar Architecture**: Pub/sub domain models, STStatusBarData, and entry structures. |
| 2026-10-14 | [`2026-10-14_commcenter-reverse-engineering.md`](02_reverse_engineering/2026-10-14_commcenter-reverse-engineering.md) | **CommCenter Dynamic Carrier Disassembly**: Reverse engineering `InterCarrierRoamingDisplayNames` and preference mapping. |

---

### 3. Hardware Verification & Ecosystem Audits

| Date | Document | Core Subject & Overview |
|:---:|---|---|
| 2026-09-28 | [`2026-09-28_golden-nugget-diff.md`](03_hardware_and_verification/2026-09-28_golden-nugget-diff.md) | **GoldenNugget Fork Topology & Authenticity Audit**: Clarifying the truth behind community claims of "patched on iOS 27". |
| 2026-10-19 | [`2026-10-19_empirical-verification.md`](03_hardware_and_verification/2026-10-19_empirical-verification.md) | **Empirical Verification & Archive Breakthrough**: CoreSimulator hot-reload and physical hardware end-to-end confirmation. |
| 2026-10-19 | [`2026-10-19_dynamic-island-analysis.md`](03_hardware_and_verification/2026-10-19_dynamic-island-analysis.md) | **Dynamic Island Cellular Rendering Heuristics**: Single-SIM full-height 4-bars and Dual-SIM stacked indicator analysis on iPhone 14 Pro. |

---

### 4. Chronological Research Handoffs

| Date | Document | Core Subject & Overview |
|:---:|---|---|
| 2026-09-25 | [`2026-09-25_carrier-lockscreen-handoff.md`](04_research_handoffs/2026-09-25_carrier-lockscreen-handoff.md) | **Initial Research Handoff**: Problem definition, Nugget obsolescence analysis, and initial agent research roadmap. |
| 2026-09-28 | [`2026-09-28_carrier-footnote-handoff.md`](04_research_handoffs/2026-09-28_carrier-footnote-handoff.md) | **Phase 2 Research Handoff**: Focusing on AirLift path-traversal primitives and locating SpringBoard archive paths. |
| 2026-09-30 | [`2026-09-30_carrier-footnote-latest.md`](04_research_handoffs/2026-09-30_carrier-footnote-latest.md) | **Phase 3 Research Handoff**: Binary archive serialization details and SpringBoard self-eviction cleanup mechanics. |
| 2026-10-14 | [`2026-10-14_dynamic-carrier-status.md`](04_research_handoffs/2026-10-14_dynamic-carrier-status.md) | **Dynamic Carrier Research Status**: Upstream CommCenter reverse engineering roadmap and stepped validation plan. |
| 2026-10-19 | [`2026-10-19_research-progress-snapshot.md`](04_research_handoffs/2026-10-19_research-progress-snapshot.md) | **Display Domain Progress Snapshot**: Lock Screen vs Control Center rendering divergence and partial override probes. |
| 2026-10-19 | [`2026-10-19_commcenter-preference-injection.md`](04_research_handoffs/2026-10-19_commcenter-preference-injection.md) | **CommCenter Preference Injection Handoff**: 12-domain preference test results and HomeDomain vs WirelessDomain isolation. |
| 2026-10-21 | [`2026-10-21_dynamic-carrier-and-vpn-resolution.md`](04_research_handoffs/2026-10-21_dynamic-carrier-and-vpn-resolution.md) | **Dynamic Carrier Verdict & VPN Badge Resolution**: Mathematical proof of `cellularEntry` atomic replacement and VPN fix. |
