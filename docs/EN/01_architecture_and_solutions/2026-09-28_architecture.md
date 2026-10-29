# iOS 27 System Customization Overall Architecture and Safety Boundaries Overview

> ⚠️ **Partially superseded (2026-10-28)**: The AirLift delivery description predates the later physical verification and overwrite-limit findings. See the [2026-10-28 roadmap](../04_research_handoffs/2026-10-28_next-research-roadmap.md) and the [2026-10-21 final verdict](../04_research_handoffs/2026-10-21_dynamic-carrier-and-vpn-resolution.md).

## 1. System Customization Panoramic Architecture

```text
                                  iOS 27.0 Release
                                         │
        ┌────────────────────────────────┴────────────────────────────────┐
        ▼                                                                 ▼
[Lock Screen Footnote Configuration]                             [Top Status Bar (Carrier Name)]
        │                                                                 │
  SharedDeviceConfiguration                                        SpringBoard Startup
        │                                                                 │
  Apple MDM / Profile Domain                                      SBSystemStatusStatusBarOverridesArchiver
        │                                                                 │
+-------+-------+                                                +--------+--------+
|               |                                                |                 |
Profile      Backup Injection                             Modern Archive (.archive)  Legacy C-Struct (Deprecated)
(.mobileconfig) (Manifest.db)                                    │                 │
│               │                                         SpringBoard Parsing  Completely Ignored
+-------┬-------+                                                │                 │
        │                                                STStatusPublisher   (Speakeasy Forced Enabled)
        ▼                                                        │
SpringBoard Lock Screen                                   SystemStatusUI
Footer Text Label                                                │
(Official Channel, Stable)                                (Empirically verified in Simulator /
                                                           Physical hardware subject to ATAirlock
                                                           rename overwrite limitations)
```

---

## 2. Implementation Condition Matrix for the Two Targets

| Dimension | Target A: Lock Screen Footnote | Target B: Carrier Name Override |
|---|---|---|
| **Technical Mechanism** | `SharedDeviceConfiguration.plist` | Modern `StatusBarOverrides.archive` (`_SBSystemStatusStatusBarOverridesArchiveRecord`) |
| **System Domain** | Official Device Management (MDM / ConfigurationProfiles) | SpringBoard Modern Status Bar Publisher Architecture (`SystemStatus` / `SystemStatusUI`) |
| **Storage Path** | `/var/containers/Shared/SystemGroup/.../` | `/var/mobile/Library/SpringBoard/StatusBarOverrides.archive` |
| **Signature / Integrity** | No mandatory digital signature; protected by container permissions | No code signing requirement; owned by `mobile:mobile` (0644) |
| **iOS 27 Delivery Channel** | **Available** (Unencrypted protected backup injection or configuration profile) | **Verified on Physical Hardware / Mainline Integration** (Modern archive adopted into GoldenNugget mainline and released in v9.5.1/v9.5.2, verified end-to-end on physical hardware via `HomeDomain` backup restore pipeline; standalone AirLift channel subject to ATAirlock rename limitations) |
| **Primary Device Safety Risk** | **Extremely Low** (Standard official configuration profile, can be rolled back in seconds) | **Low** (Standard backup restore pipeline carries no jailbreak privilege escalation risk, or standalone AirLift pipeline) |

---

## 2.1 Status Bar Override Overlay Mechanism and VPN State Passthrough

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
│   [cellularEntry: Pointer Replace]        [vpnEntry: Native Passthrough]│
│   • Entire cellularEntry is overridden    • overlay.vpnEntry == nil    │
│   • Displays custom carrier text          • Skips replace, 100% passes │
│   • Static props cannot decouple airplane   through system VPN         │
│     mode                                  • Fully resolves GoldenNugget│
│                                             missing icon defect        │
└────────────────────────────────────────────────────────────────────────┘
```
- **Atomic Replacement Property**: `-[STStatusBarData dataByApplyingOverlay:]` (`0x20e4ac960`) operates at the Entry object level. If `cellularEntry` is present, it triggers an entire pointer overwrite; under static conditions, it is impossible to decouple automatic Airplane Mode hiding while coexisting with real signal.
- **VPN State Item Decoupling & Fix**:
  - Earlier tools (such as early GoldenNugget) wrote VPN activity identifiers into `suppressedBackgroundActivityIdentifiers` or serialized incomplete `vpnEntry` records in the archive, causing the VPN badge in Control Center and the status bar to permanently vanish.
  - Fix Solution: Set `suppressedBackgroundActivityIdentifiers` to an empty set in `_SBSystemStatusStatusBarOverridesArchiveRecord`, and completely omit `vpnEntry` in `STStatusBarData`. When SpringBoard applies the overlay, detecting `vpnEntry == nil` automatically executes a `cbz` skip, fully preserving the live status published by the underlying real VPN daemon so that the icon lights up normally when the user connects to a VPN. Explicit control is supported via `--vpn {auto,on,off}`. See [`../04_research_handoffs/2026-10-21_dynamic-carrier-and-vpn-resolution.md`](../04_research_handoffs/2026-10-21_dynamic-carrier-and-vpn-resolution.md).

---

## 3. iOS 27 Backup and Restore Safety Boundary Changes

In the iOS 27.0 Release production version, Apple implemented four layers of hardening against legacy customization tools (such as Nugget / CowabungaLite):

1. **Security State Recovery (Self-Healing Recovery):**
   When the system detects residual files from sparse restores across directories located in sensitive system directories such as `/var/preferences` during the boot phase, it automatically triggers reset logic that wipes the entire directory, causing all written modifications to be lost.
2. **BackupAgent2 Whitelist Tightening:**
   `SystemPreferencesDomain` is restricted to 10 hardcoded system file paths; `RootDomain` is strictly prohibited from writing to `preferences/*`.
3. **AppDomain Sparse Restore Interception:**
   Starting from iOS 27 beta 6 and subsequent production release versions, sparse restores submitted directly to AppDomain are outright rejected (`MBErrorDomain/205`).
4. **Surviving Viable Path:**
   "Three-phase protected backup injection (Manifest.db In-Place Injection)" implemented via GoldenNugget 9.5, injecting standard files into legitimate protected domains (such as `HomeDomain`, `SysSharedContainerDomain-...`), is currently the only stable channel without jailbreaking.
