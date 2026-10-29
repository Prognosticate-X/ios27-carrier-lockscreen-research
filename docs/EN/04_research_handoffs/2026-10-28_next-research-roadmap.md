# iOS 27 Carrier & Status Bar Customization: Latest-State Audit and Next-Phase Research Roadmap

**Document ID**: `DOC-20261028-ROADMAP`  
**Update Date**: 2026-10-28  
**Baseline Commit**: `ff75611` (2026-10-22, `main`)  
**Status**: Active / Living Document  
**Scope**: iOS 27.0–27.x, non-jailbroken, no TrollStore, no kernel execution  
**Audience**: Maintainers, reverse engineers, toolchain contributors

> This document is the single entry point for the current state and next-phase direction. The historical documents from 2026-09-25 through 2026-10-21 remain as the evidence chain. Where a later experiment supersedes an earlier conclusion, this document and the latest experiment record take precedence.
>
> **Suggested reading order**: Sections 0–2 for the audit and questions, Section 3 for the research tracks, Section 5 for the executable protocol, and Section 8 for the next-72-hours checklist.

---

## 0. Executive Summary

1. **The static override path is mature; it is no longer the research bottleneck.** The path, format, read/merge/render pipeline, and physical-device delivery of `StatusBarOverrides.archive` are closed. GoldenNugget has integrated the format. The remaining questions are how far the primitive can extend, which versions/devices it covers, and how reliably it can be delivered.
2. **Airplane-mode synchronization is probably unreachable; treat it as a time-boxed falsification, not an open-ended goal.** Current evidence indicates that name visibility is determined by the override entry's own `enabled/status` fields and that a static archive has no field that follows live cellular state. True dynamic publishing requires the `com.apple.systemstatus.publisher` entitlement. Spend 10 working days on a decisive matrix, publish the verdict either way, then close or productize it.
3. **The highest-value new direction is a general status-bar override engine.** iOS 27's `STStatusBarData` carries at least 40 candidate entries (battery, Wi-Fi, time, date, airplane mode, VPN, satellite, tethering, location, rotation lock, and more). The current tooling uses only `cellularEntry/secondaryCellularEntry/vpnEntry`. Extending the same primitive to the full entry surface is the shortest path from a single-purpose tool to a platform.
4. **The biggest immediate risks are engineering and experimental-method risks, not system-mechanism risks.** The audit found that the primary-device blocklist is empty by default, contrary to the documentation; the experiment harness restarts SpringBoard but does not purge `systemstatusd`'s live domain, which can produce false negatives; and several documents still carry superseded conclusions.
5. **Next two weeks**: safety/harness fixes → airplane-mode matrix → full entry enumeration → 27.1/new-hardware regression → upstream PR and documentation governance.

### 0.1 Priority Overview

| Priority | Track | Problem | Success Criterion | Effort | Probability |
|:---:|---|---|---|:---:|:---:|
| **P0** | Track 0: Safety & harness | Empty blocklist, missing purge, reproducibility | Zero contact with primary device; 3 identical runs per variant | 2–3 days | High |
| **P0** | Track A: Airplane-mode falsification | Can a static archive hide the name with cellular state? | A working combination or a reproducible impossibility argument | 10 working days | Low (~10–15%) |
| **P1** | Track B: General override engine | Which of the 40+ entries work, and which are safe? | ≥5 non-cellular entries render reliably | 2–4 weeks | High |
| **P1** | Track C: Compatibility matrix | 27.0.x / 27.1+ / new devices / surfaces | Matrix green before release | Ongoing | High |
| **P1** | Track D: Delivery hardening | AirLift overwrite, backup restore, rollback | 10/10 successful apply and rollback | 2–3 weeks | High |
| **P2** | Track E/F/G | Official channels, upstream, docs, CI | Upstream PR, status page, green CI | Ongoing | Medium-high |

> **2026-10-28 goal correction**: The user explicitly wants Nugget's iOS 26-and-earlier behavior: **change only the name while signal, radio type, and Airplane-Mode coupling stay live**. Runtime enumeration has shown that `STStatusBarDataCellularEntry` has no field-level flags. **WirelessDomain backup injection is now falsified and unsafe**: it did not write the target file and put the 14 Pro into Setup Assistant. There is currently no usable non-jailbroken “name-only, everything else live” solution. See [Nugget-Style Name-Only Research](2026-10-28_name-only-live-override.md). Track B should be re-scoped from “general entry engine” to “name-only live preservation + upstream live-source injection”.

---

## 1. Local-State Audit (2026-10-28)

### 1.1 Verified Facts

| Topic | Conclusion | Evidence Level | Key Evidence |
|---|---|:---:|---|
| Archive path | `/var/mobile/Library/SpringBoard/StatusBarOverrides.archive` | Confirmed | Physical device + simulator |
| Archive format | `NSKeyedArchiver` → `_SBSystemStatusStatusBarOverridesArchiveRecord` → `STStatusBarData` | Confirmed | Deserialization + SpringBoard disassembly |
| Read timing | Read once early during SpringBoard startup; empty record triggers self-deletion | Confirmed | `_queue_readStatusBarOverridesArchiveRecord` / `_queue_writeOutArchiveRecord:` |
| Override semantics | `dataByApplyingOverlay:` replaces the entire entry object; no field-level merge | Confirmed | `0x20e4ac960` disassembly |
| Name visibility | Empirically requires `enabled=true`, `status=5`, non-empty `string`, `isBootstrapCellular=false` | Confirmed (empirical) | V4/V5/V6/V7 + SystemStatusUI gate |
| Surface split | Lock Screen signal bars read live telemetry; Control Center reads the override; Lock Screen usually hides the radio-type text, while Control Center shows it when Cellular Data is on | Confirmed | BARS1 experiment |
| Partial mode | Omitting `displayValue` falls back to live bars; omitting `type` suppresses the radio-type label; the name still persists in Airplane Mode | Confirmed | V4 experiment |
| VPN passthrough | Empty `suppressedBackgroundActivityIdentifiers` plus omitted `vpnEntry` preserves the native VPN badge | Confirmed | Physical device + 21 unit tests |
| Dual SIM | `cellularEntry` + `secondaryCellularEntry` render the stacked indicator/badges | Confirmed | iPhone 14 Pro physical device |
| Physical delivery | AirLift works; GoldenNugget uses HomeDomain backup restore | Confirmed | iPhone 14 Pro physical / upstream integration |
| Lock Screen footnote | Official `com.apple.shareddeviceconfiguration` channel | Confirmed | Profile + backup injection |
| Upstream adoption | GoldenNugget 9.5.1/9.5.2 integrated the archive format and verified it on hardware | Confirmed (external) | Upstream commits/docs |

### 1.2 Open or Unclosed Questions

| ID | Question | Current State | Impact |
|:---:|---|---|---|
| Q1 | Airplane-mode synchronization (name hides when cellular is off) | No static entry point found | Core UX gap |
| Q2 | Semantics of `status` values 0–4, 6, 255 | Only 5 and -1 tested; no systematic enumeration | May hide a conditional-display combination |
| Q3 | Sentinel values for `displayValue/type/rawValue/displayRawValue` | Not systematically enumerated | May hide an "un-overridden" semantic |
| Q4 | Interactions of `isBootstrapCellular`, `sosAvailable`, `showsSOSWhenDisabled` | Only known that `isBootstrapCellular=true` hides the name | May be another display path |
| Q5 | Live-domain merge/write-back timing | Live takes precedence; no per-frame observation | Decides whether the live domain can be exploited |
| Q6 | Availability of the full `STStatusBarData` entry surface | Only 3 entries used | Platform opportunity |
| Q7 | iOS 27.1+ / iPhone 17/18 compatibility | No 27.1 runtime locally; 17 Pro Max ownership unconfirmed | "Universal" claim at risk |
| Q8 | Delivery reliability | AirLift rename/overwrite limits; no backup pipeline in this repo | UX and failure rate |
| Q9 | Footnote length, Unicode, multiline, supervision boundaries | Only basic verification | Full productization of the official channel |
| Q10 | Staleness of historical docs and README | Several places still say "pending physical verification" or "AirLift limited" | Misleads future researchers |

### 1.3 Code and Harness Audit (New in This Round)

> This is the most important part of the audit. **Do not run any new physical-device batch matrix before S1/S2 are fixed.**

| ID | Severity | Finding | Evidence | Recommendation |
|:---:|:---:|---|---|---|
| S1 | **P0 safety** | The primary-device blocklist is empty by default | `tools/airlift_carrier_deploy.py:378-383`: `PRIMARY_PHONE_BLOCKLIST = frozenset(_ENV_BLOCKLIST)`, read only from `AIRLIFT_BLOCKED_UDIDS`; the variable is unset in the current environment | Make it fail-closed: refuse all writes when no blocklist is configured, or read a local `~/.config/ios27-carrier/safety.json`. Add a test that the primary UDID is rejected even with an empty environment |
| S2 | **P0 method** | The harness does not purge `systemstatusd`'s live domain | `statusbar_variant_lab.py` calls `deploy_carrier() + respring_device()`; `respring_device()` only terminates SpringBoard (`tools/airlift_carrier_deploy.py:841-881`) | Add `purge_live_domain()`: SIGSTOP SpringBoard → SIGKILL `systemstatusd` → replace archive → SIGKILL SpringBoard; fall back to a userspace reboot. Integrate into lab/replace/GUI |
| S3 | P1 method | The variant lab uses plain deploy, not atomic replace | `statusbar_variant_lab.py:158` calls `deploy_carrier`; an existing target may hit the ATAirlock rename limit | Use `airlift_archive_replace.replace_archive()` or add `--replace` to the lab |
| S4 | P1 maintenance | Two identical deploy scripts are maintained separately | `tools/airlift_carrier_deploy.py` and `airlift/airlift_carrier_deploy.py` both hash to `b503181e…` | Keep one source; make the other a thin wrapper or generate it at build time; add a CI hash check |
| S5 | P1 compatibility | The hardware database lacks iPhone 17/18 families | `has_dynamic_island` stops at `iPhone17,4` (iPhone 16 series) | Add `iPhone18,x` / `iPhone19,x`; prefer capability detection over a hardcoded list |
| S6 | P2 copy | The Chinese GUI text for `--partial` contradicts the README | One GUI hint says bars and type fall back live; another says the type label is suppressed; the README says "not recommended for production" | Unify: "bars fall back live; type label suppressed; name persists in Airplane Mode"; mark Experimental |
| S7 | P1 docs | Several docs still carry old conclusions | `2026-09-30_carrier-footnote-solution.md` still calls carrier name "Pending Physical Verification"; `2026-09-28_architecture.md` still says AirLift is "subject to rename limitations"; `2026-09-28_viable-paths.md` Route 3 is still "Pending" | Add "Superseded by 2026-10-21 / 2026-10-28" banners; link this roadmap at the top of the docs hub |
| S8 | P1 engineering | No CI, no device tests, no automated screenshot/OCR regression | No `.github/`; `device_ui.py` and `ocr.swift` are not wired together | Add GitHub Actions for offline unit tests, plist round-trip, link checks. Keep device tests local |
| S9 | P1 delivery | No first-party `MobileBackup2` pipeline | AirLift only; `commcenter_preference_builder.py` only generates HomeDomain structures | Implement filtered backup + Manifest.db injection + restore + rollback as an AirLift fallback |
| S10 | P2 UX | Applying requires respring/reboot, and respring sometimes does not clear the live cache | Documented on 2026-10-19; the CLI defaults to respring | Make "reliable apply" an explicit state machine: apply → verify → userspace reboot on failure; show the stage in the GUI |

> **2026-10-28 progress**: S1 (`safety.json` + fail-closed + direct-call guard), S2 (live-domain purge in `exp_status_matrix`), and S4 (the `airlift/` wrapper) are implemented; S3 is covered by the new harness; S5 added iPhone 17/18 model IDs. S6–S10 remain open.

### 1.4 Lab Inventory

| Device | Model | OS | State | Use | Write allowed |
|---|---|---|---|:---:|---|
| iPhone 14 Pro | iPhone15,2 | 27.0.1 (24A446) | USB connected | Primary test device | ✅ This device only |
| iPhone 16 Pro Max | iPhone17,2 | 27.0 (24A437) | available (paired) | Daily driver / read-only control | ❌ No writes |
| iPhone 17 Pro Max | iPhone18,2 | 27.0 (24A437) | Connection unstable | New-hardware candidate | ⚠️ Owner confirmation required |
| iPhone 18 Pro (simulator) | iPhone19,2 | 27.0 (24A434) | Booted | Fast matrix / disassembly reference | ✅ Simulator |
| iPhone SE (simulator) | — | 27.0 | Start on demand | Notch/Home-button control | ✅ Simulator |
| Xcode | 27.0 (27A266a) | iOS SDK 27.0 | Installed | Build/simulator | — |

Current environment: Python 3.12.13; `PYTHONPATH=tools:airlift python3 -m unittest tools/test_airlift_features.py` → **21 tests OK**; no iOS 27.1 runtime/SDK.

### 1.5 Stage Assessment

The project is at the stage of **"solution closed, evidence chain not closed, engineering fragile"**:

- **Solution layer**: static override + VPN passthrough + dual SIM + footnote are all deliverable.
- **Evidence layer**: Airplane Mode, status semantics, full entry surface, and 27.1 compatibility remain open.
- **Engineering layer**: safety guardrails, experimental reproducibility, delivery fallback, and documentation freshness have clear gaps.

The next phase should therefore **fix the harness and safety first, run a time-boxed falsification, then platformize the primitive**, rather than continue an unbounded search for a dynamic solution.

---

## 2. Research Questions and Hypotheses

| ID | Research question | Main hypothesis | Evidence | Method | Decision gate |
|:---:|---|---|---|---|---|
| RQ1 | Can a static archive make name visibility follow live cellular state? | H1: No. The name gate reads only the override entry's `displayItem.isEnabled/string/isBootstrapCellular`, not `STTelephonyStatusDomain` | Disassembly + V4/V5/V6/V7 + Airplane Mode persistence | Track A matrix + live-domain observation | Combination found → productize; otherwise close |
| RQ1a | Is there a `status` sentinel or special combination? | H1a: 0–4/6/255 may carry "not registered/searching" semantics, but no live binding | Only 5 and -1 tested | Track A1 full enumeration | Any combination hides in Airplane Mode while preserving bars → success |
| RQ1b | Can the live-domain merge/write-back be exploited? | H1b: Live takes precedence, but only publishes `cellularEntry` on specific events; the window is narrow | `recordByApplyingRecord:` disassembly | Track A3 logs + archive diff | Measure the window → evaluate; otherwise no |
| RQ1c | Are there alternate entries/display paths? | H1c: `bootstrapCellularEntry` / `secondaryCellularEntry` / `satelliteEntry` / `rawStringView` may have independent gates | `STUIStatusBarCellularItem` has `rawStringView` and `isBootstrapCellular`; `STStatusBarData` has 40+ entries | Track A4/A5 | Independent path found → productize |
| RQ2 | How large is the full `STStatusBarData` override surface? | H2: Most entries are accepted, but some are ignored or unsafe | 40+ candidate entries from `strings` | Track B per-entry experiments | ≥5 stable non-cellular entries → platformize |
| RQ3 | Do iOS 27.1+ / new devices change the semantics? | H3: Schema, AirLift, and display gates may change | Only 27.0/27.0.1 locally | Track C canary | Full version matrix before release |
| RQ4 | Which delivery channel is most reliable? | H4: Backup restore is more reliable for overwriting existing files; AirLift is lighter for first install | GoldenNugget verified HomeDomain; this repo only has AirLift | Track D A/B comparison | 10/10 success + rollback → adopt |
| RQ5 | Is there an official carrier-name key? | H5: No; only the footnote has an official key | Apple Device Management schema shows no carrier name | Track E schema audit | Official key found → top priority; otherwise close |
| RQ6 | Is there a non-jailbroken dynamic publishing path? | H6: No; it requires `com.apple.systemstatus.publisher` | Existing sandbox/signature evidence | Track A6 entitlement audit | No → mark "out of scope" |

### 2.1 Strong Prior for RQ1

The `SystemStatusUI` name gate depends on exactly three things:

1. `displayItem.isEnabled` (derived from the override entry's `enabled/status`);
2. `entry.string.length > 0`;
3. `!entry.isBootstrapCellular`.

It does **not** read the live registration state from `STTelephonyStatusDomain`. Therefore, barring one of the following three exceptions, a static archive cannot auto-hide the name in Airplane Mode:

- **Exception A**: a `status`/sentinel value causes `displayItem.isEnabled` to be rebound to live state at runtime (no evidence yet);
- **Exception B**: the live domain publishes a `cellularEntry` on Airplane Mode transitions, and the merged record overwrites the name (needs frame-by-frame verification);
- **Exception C**: another entry (bootstrap/secondary/satellite/raw) has an independent gate coupled to live state.

Track A's core job is to **rule out A/B/C one by one**. If all three are ruled out, RQ1 can be formally closed and "dynamic name" marked as **requiring runtime injection, beyond the non-jailbroken boundary**.

### 2.2 Negative-Knowledge Stop List

The following paths already have negative results locally or on hardware. Do not reinvest unless a new iOS major version, a new write primitive, or a new entitlement appears:

| Path | Verdict | Key evidence | Re-evaluate when |
|---|---|---|---|
| Speakeasy / FeatureFlags static write | Infeasible | `/var/preferences` is not writable by mobile; BackupAgent whitelist; sparse restore triggers Security State Recovery | Apple opens a FeatureFlags write path (very unlikely) |
| CommCenter CFPreferences injection | Negative | 12-domain injection + cold restarts of cfprefsd/CommCenter/SpringBoard on 14 Pro / 27.0.1 had no effect; real data lives in `/var/wireless` and the signed carrier bundle | `_wireless` write access or CommCenter injection capability appears |
| Carrier Bundle Overlay / signature tampering | High risk, infeasible | Signature failure causes No Service; SSV is read-only | A signable overlay mechanism appears |
| AFC read outside media | Stat only | `read`/`list` fail outside media; use backup for content | AFC permission model changes |
| Runtime publishing of `STStatusBarOverridesStatusDomain` | Jailbreak/TrollStore tier | Requires the `com.apple.systemstatus.publisher` entitlement | A non-jailbroken publisher channel appears |
| Static-archive Airplane Mode sync | Current evidence points to infeasible | The name gate does not read live telephony; Track A has not formally closed yet | Track A finds an A/B/C exception |
| `--partial` as the default production mode | Not recommended | Radio-type text is suppressed; the name still persists in Airplane Mode | A sentinel for radio-type fallback is found |

---

## 3. Research Tracks

### Track 0 — Safety and Harness (P0, 2–3 days)

**Goal**: make every later experiment satisfy "zero contact with the primary device, reproducible results, rollback on failure".

**Tasks**:

1. **S1 fix: fail-closed blocklist**
   - Add `DEFAULT_BLOCKED_UDIDS` or a local `safety.json`;
   - Refuse all write operations when no blocklist is configured, and print how to configure it;
   - Keep `AIRLIFT_BLOCKED_UDIDS` as an additive source, not the only source;
   - Test: empty environment + primary UDID → must fail; 14 Pro UDID → allowed.
2. **S2 fix: reliable purge**
   - Add `purge_live_domain(udid)`:
     1. read the SpringBoard PID;
     2. `SIGSTOP` SpringBoard;
     3. find and `SIGKILL` `systemstatusd` via CoreDevice;
     4. replace the archive atomically;
     5. `SIGKILL` SpringBoard and wait for a new PID;
     6. fall back to `devicectl reboot --style userspace` if any step fails.
   - Integrate into `deploy_carrier`, `replace_archive`, `statusbar_variant_lab`, and the GUI deploy/reset paths.
3. **S3 fix: variant lab uses atomic replace**
   - Add `--replace` / `--purge`;
   - Emit JSON (variant, fields, purge method, screenshot paths, OCR text).
4. **S4 fix: single source**
   - Make `tools/` the only source; turn `airlift/` into a wrapper;
   - Add a CI check for hash equality (or remove the duplicate).
5. **S5 fix: hardware database**
   - Add iPhone 17/18 families;
   - Prefer `MobileGestalt`/`devicectl` capability detection over a hardcoded list.
6. **Observability**
   - Archive SHA-256, size, mtime;
   - Device build/UDID/name;
   - Screenshots + OCR + manual-review flag;
   - Unified result JSON schema.

**Acceptance**:

- Empty-environment blocklist test passes;
- 14 Pro: 3 consecutive apply → purge → screenshot runs produce identical results;
- No `airlift-*` residue;
- Every write path has a `--dry-run` preflight.

---

### Track A — Airplane-Mode Falsification (P0, 10 working days)

**Goal**: either find a static combination that hides the name when cellular is off while preserving live bars/type, or produce a reproducible impossibility argument.

#### A1. `status` / `enabled` / Field Matrix

Run on the 14 Pro + iPhone 18 Pro simulator, using the reliable purge from Track 0:

| Dimension | Values | Notes |
|---|---|---|
| `status` | -1, 0, 1, 2, 3, 4, 5, 6, 255 | Focus: do 0–4 hide the name while preserving bars? |
| `enabled` | true / false / omitted | Is omitted equivalent to false? |
| `displayValue` | 0, 1, 3, 4, -1, 255, 65535, omitted | Find an "un-overridden" sentinel |
| `type` | 0, 9, 10, -1, 255, omitted | Find radio-type fallback semantics |
| `rawValue` / `displayRawValue` | 0, -1, 255, omitted | Does it affect rawStringView? |
| `isBootstrapCellular` | true / false / omitted | Direct gate for the name |
| `sosAvailable` / `showsSOSWhenDisabled` | true/false combinations | Does it change the "no service" branch? |
| `string` / `crossfadeString` | non-empty / empty / crossfade only | Name and alternating display |
| `suffixString` / `badgeString` | present/absent | Layout and hiding effects |

**Judgment**: screenshot each variant in at least four states: cellular on + Wi-Fi off, cellular on + Wi-Fi on, Airplane Mode, and no service (simulator `--cellularMode failed`). Record name, bars, radio type, and airplane icon.

#### A2. Surface Matrix

| Surface | How to open | Focus |
|---|---|---|
| Lock Screen | Wake | Name/bars/type/airplane icon |
| Control Center | Swipe down from top-right | Name/bars/type/VPN |
| Home Screen | Unlock | Is the name shown at top-left? |
| Notification Center | Swipe down from top-left | Does it reuse the Lock Screen layout? |
| StandBy | Horizontal charging | Name rendering/cropping |
| Dynamic Island expanded | Long press | Dual-SIM names/badges |

#### A3. Live-Domain Observation

- Capture `systemstatusd`, `SpringBoard`, and `STStatusBarOverridesStatusDomain` logs with `log stream` / `log collect`;
- Around Airplane Mode transitions, record:
  - whether the on-disk archive SHA-256 changes;
  - whether `systemstatusd` republishes `cellularEntry`;
  - whether SpringBoard writes back a merged record.
- If a "Airplane Mode transition → live publishes cellularEntry → disk write-back" window exists, quantify its length and repeatability.

**Caution**: do not declare a negative result from "replace file + respring" alone; confirm the live domain was purged, or the result is not trustworthy.

#### A4. Alternate Entries / Display Paths

- `secondaryCellularEntry`: fake a second SIM on a single-SIM device and observe whether an independent name/badge appears; check whether the primary live name still persists.
- `satelliteEntry` / `tetheringEntry`: can they carry a custom string?
- `airplaneModeEntry`: does explicitly overriding the airplane entry affect the name branch?
- `bootstrapCellularEntry` (if present/decodable): is it only shown early at boot?
- `rawStringView` / `rawValue`: is there an independent raw-string display path?

#### A5. Binary Analysis Checklist

| Target | Method | Output |
|---|---|---|
| `STUIStatusBarCellularItem applyUpdate:toDisplayItem:` (`0x2c1c`) | Hopper/otool disassembly | Complete pseudocode for the name gate |
| `_signalViewShouldBeEnabledForEntry:forceShowingDisabledSignalBars:signalMode:` (`0x2aa8`) | Disassembly | How status affects the signal view |
| `STUIStatusBarCellularCondensedItem` / `ExpandedItem` | Disassembly | Dynamic Island/dual-SIM name gates |
| `STStatusBarDataCellularEntry` ivars/properties | Simulator runtime reflection or dsc extraction | Complete field table, defaults, uninitialized semantics |
| `STStatusBarData` top-level keys | Runtime reflection | Is there a top-level carrier/service field? |
| `_SBSystemStatusStatusBarOverridesArchiver` merge/persist | Disassembly + logs | Disk/live precedence and write-back conditions |
| `STStatusBarDataCellularType` / `NetworkStatus` enums | Symbols/strings | Status value semantics |

#### A6. Entitlement Audit

- Confirm whether `com.apple.systemstatus.publisher` can be obtained by a non-system process;
- Confirm whether any other entitlement/XPC service can publish `STStatusBarOverridesStatusDomain`;
- Use the result only to decide whether dynamic publishing is possible without a jailbreak; do not attempt injection.

#### Track A Decision Gate

| Result | Verdict | Next |
|---|---|---|
| Combination hides in Airplane Mode with live bars/type preserved | Success | Productize as `--dynamic-name` or a separate mode; add docs and regression |
| Combination hides but degrades bars/type | Partial | Evaluate as an opt-in mode; keep full/partial defaults |
| No combination, and live domain/entitlement unavailable | Unreachable | Write a closure memo; remove from the roadmap; keep the dual-SIM secondary-slot workaround |
| Unstable/irreproducible | Method problem | Fix Track 0 and rerun; do not conclude |

**Timebox**: 10 working days. Produce `2026-11-XX_airplane-mode-verdict.md` regardless of outcome.

**2026-10-28 pilot result**: REA + Ghidra decompiled the name gate, and the `status` 0–5/255 matrix was run on iPhone 14 Pro / 27.0.1. Result: `status=5` pins the custom name; `status=1` is a live-fallback mode (native name when cellular is on, override name in Airplane Mode—the opposite direction); 0/2/3/4 hide the name and degrade the cellular indicator. **No static combination produced “custom name with cellular on + automatic hide in Airplane Mode”.** See the [2026-10-28 Airplane-Mode Matrix](2026-10-28_airplane-mode-status-matrix.md).

---

### Track B — General Status-Bar Override Engine (P1, 2–4 weeks)

**Goal**: turn `StatusBarOverrides.archive` from "change the carrier name" into "a controllable status-bar data override layer".

**B1. Full Entry Enumeration**

Start from the iOS 27.0 simulator `SystemStatusUI` strings (Appendix A) and verify each entry:

- Is it accepted by `STStatusBarData`?
- Does it need extra fields to render?
- Is it visible on Lock Screen / Control Center / Home Screen?
- Does it affect system stability?
- Is it security-sensitive (VPN, location, recording, privacy indicators)?

**B2. Candidate Priority**

1. **Low risk, high visibility**: `batteryEntry`, `mainBatteryEntry`, `wifiEntry`, `timeEntry`, `shortTimeEntry`, `dateEntry`;
2. **Medium risk, strong demand**: `airplaneModeEntry`, `rotationLockEntry`, `alarmEntry`, `quietModeEntry`, `bluetoothEntry`, `airPlayEntry`;
3. **High risk, off by default**: `vpnEntry`, `locationEntry`, `sensorActivityEntry`, `backgroundActivityEntry`, `satelliteEntry`, `tetheringEntry`.

**B3. Schema and Tooling**

- Add `tools/statusbar_schema.py`: entry → class → fields → types → defaults → safety level;
- Generator supports `--entry-json` / `--schema`;
- GUI adds an "Advanced" collapsible panel;
- Presets expand from "carrier presets" to "status-bar themes".

**B4. Safety Classification**

| Level | Meaning | Default |
|---|---|---|
| Safe | Pure appearance; does not misrepresent security state | Allowed |
| Caution | May misrepresent network/battery state | Confirm required |
| Sensitive | VPN/location/privacy/recording indicators | Denied by default; `--allow-sensitive` required |

**B5. Acceptance**

- ≥5 non-cellular entries render reliably on 14 Pro + simulator;
- No SpringBoard crash/loop;
- `--reset` restores everything;
- ≥10 new unit tests (plist round-trip, omitted fields, sensitive-entry rejection).

---

### Track C — Compatibility and Regression Matrix (P1, ongoing)

**Goal**: make "Universal" a verifiable matrix, not a slogan.

**C1. Version Matrix**

| Version | Build | Status | Must-test |
|---|---|---|---|
| 27.0 | 24A300 / 24A434 / 24A435 / 24A437 | Partially tested | Archive read, name, VPN, dual SIM |
| 27.0.1 | 24A446 | Tested (14 Pro) | Same + AirLift overwrite |
| 27.1+ / 27.2 | TBD | Untested (the 14 Pro reports 27.2 available) | Schema diff, AirLift viability, display gates |

**C2. Device Matrix**

- Dynamic Island: iPhone 14 Pro / 16 Pro Max (read-only) / 17 Pro Max (pending approval) / 18 Pro simulator;
- Classic notch: iPhone 13/14 / SE simulator;
- Single SIM / dual SIM / eSIM / no service / Airplane Mode / Wi-Fi Calling / roaming.

**C2.5 Text edge cases**: very long names, CJK, emoji, RTL, combining marks, zero-width characters, badges, suffix strings; record truncation/marquee/shrink behavior as pre-release visual regressions.

**C3. Automated Evidence**

- `device_ui.py` screenshot → `ocr.swift` → result JSON;
- Save golden screenshots for key variants;
- Label name, bars, radio type, and airplane icon separately;
- Manual review only for low-confidence OCR samples.

**C4. AirLift Viability Canary**

For each new build, run a low-risk probe first:

1. `devicectl list devices` detects the device;
2. `snapshot-books` succeeds;
3. `stage` succeeds;
4. `info` can stat the target;
5. Only on the 14 Pro, run one reset-archive write + purge + restore.

**C5. Release Gate**

- 27.0.x matrix green;
- 27.1 canary passes at least "generate → write → read → rollback";
- New devices pass simulator + at least one physical device;
- Documentation matrix matches reality.

---

### Track D — Delivery Hardening (P1, 2–3 weeks)

**Goal**: turn "can write" into "repeatable, rollback-safe, and explainable on failure".

**D1. First-Party Backup Restore Pipeline**

- Use `pymobiledevice3` from `.venv`:
  1. create a filtered backup (only `Library/SpringBoard` and necessary domains);
  2. inject a `StatusBarOverrides.archive` record into the backup's `Manifest.db`;
  3. restore to the 14 Pro;
  4. trigger SpringBoard to reload;
  5. verify + roll back.
- Compare byte-for-byte with GoldenNugget's HomeDomain approach;
- Record backup duration, failure modes, trust/unlock requirements.

**D2. AirLift Hardening**

- Atomic replace + purge + retry + idempotency;
- Clean up `airlift-*` and Books state on failure;
- Separate "first install" from "overwrite update";
- Give actionable errors for the ATAirlock rename limit.

**D3. On-Device Feasibility (exploratory)**

- Evaluate AirCard-style `AirliftFFI` with local pairing/developer mode;
- Deliver a feasibility report only; do not promise a consumer product;
- Key question: can SpringBoard/systemstatusd be reloaded without a host?

**D4. Acceptance**

- 10/10 apply + rollback on the 14 Pro;
- No data loss, no residue, no Security State Recovery;
- Restore to native within 60 seconds on failure;
- A documented failure-triage tree.

---

### Track E — Official Channels and Lock Screen Footnote (P2, 1 week)

**E1. Apple Device Management Schema Audit**

- Search `com.apple.shareddeviceconfiguration`, `com.apple.cellular`, `CarrierSettings`, and related payloads;
- Confirm whether an official carrier-display-name/operator-name key exists;
- If not, record that the official channel covers only the footnote, not the carrier name.

**E2. Footnote Boundary Tests**

- Length limit, line breaks, Unicode, emoji, RTL;
- Supervised vs unsupervised;
- Interaction with Focus / StandBy / Always-On;
- Profile install/remove/reinstall;
- Backup injection;
- Enterprise MDM push updates.

**E3. Deliverables**

- Add length/character validation to `footnote_generator.py`;
- Add a compatibility table and rollback steps to the docs;
- State the "footnote ≠ carrier name" boundary clearly.

---

### Track F — Upstream and Ecosystem (P2, ongoing)

**F1. GoldenNugget**

- Submit the VPN passthrough fix (empty `suppressedBackgroundActivityIdentifiers` + omitted `vpnEntry`);
- Submit reusable logic for `--partial` / dual SIM / archive generation;
- Diff their archive schema against ours;
- Cross-validate on the same 14 Pro.

**F2. AirLift**

- Report the ATAirlock rename/overwrite limit and iOS 27.1 compatibility;
- Provide a minimal repro and logs;
- Track upstream fixes.

**F3. Test Vectors**

- Add to `examples/`:
  - single-SIM full / partial / vpn auto;
  - dual SIM;
  - reset;
  - a known-failing counterexample for error-handling tests.
- Add `tools/validate_archive.py`: decode + assert + SHA-256.

**F4. Cross-Validation**

- Exchange archive samples with community users/maintainers;
- Record rendering differences for the same sample across tools/versions.

---

### Track G — Documentation and Release Engineering (P1, ongoing)

**G1. Status Page**

- This document is the "current state" entry point;
- Add `Superseded` banners to historical docs (top only; do not rewrite history);
- Add "Latest status → 2026-10-28 roadmap" at the top of the docs hub.

**G2. README Corrections**

- Align the blocklist description with the code;
- Align AirLift-limit wording with the backup-restore path;
- Mark `--partial` as Experimental consistently;
- Align the version matrix with "Universal" wording.

**G3. CI**

- Offline unit tests (21+);
- Plist round-trip;
- Documentation link check;
- Optional Python lint/type check;
- Do not put device tests in public CI.

**G4. Release Checklist**

- Version, changelog, compatibility matrix, known issues, rollback steps;
- Each release attaches a minimal reproducible experiment record.

---

## 4. Priority and Proposed Schedule

| Phase | Dates | Tracks | Key Deliverables | Gate |
|:---:|---|---|---|---|
| **Phase 0** | 10/28–10/31 | Track 0, G1/G2 | Fail-closed blocklist, purge, lab fix, doc banners | Unit tests + 3 consistent runs on 14 Pro |
| **Phase 1** | 11/01–11/14 | Track A, B1–B2 | Airplane-mode matrix, status semantics, entry schema draft | A verdict after 10 working days |
| **Phase 2** | 11/15–11/28 | Track B3–B5, C, D1–D2 | General override GUI/CLI, compatibility matrix, backup pipeline | 10/10 apply/rollback |
| **Phase 3** | 12/01–12/15 | D3, E, F, G3 | On-device feasibility report, upstream PR, CI, release | 27.0.x green + 27.1 canary |
| **Ongoing** | — | C4/C5, F, G | AirLift canary, upstream tracking, docs | Run on every new build |

> If Track A reaches a clear negative by 11/14, Phase 1's second half can move directly to Track B without waiting.

---

## 5. Standard Experiment Protocol

### 5.1 Preflight Checklist

- [ ] Target is the 14 Pro test device, not the primary device;
- [ ] `AIRLIFT_BLOCKED_UDIDS` or `safety.json` is configured;
- [ ] Device unlocked, trusted, USB stable;
- [ ] UDID, model, iOS version, build recorded;
- [ ] Current `StatusBarOverrides.archive` exported (or confirmed absent);
- [ ] Native baseline screenshots: Lock Screen, Control Center, Home Screen;
- [ ] Battery > 50%, Low Power Mode off;
- [ ] No other write operation running.

### 5.2 Apply and Purge Sequence (after Track 0)

~~~text
1. Generate the variant payload
2. Atomically replace the archive (move-out old → move-in new)
3. Purge the live domain:
   SIGSTOP SpringBoard
   SIGKILL systemstatusd
   SIGKILL SpringBoard
4. Wait for a new SpringBoard PID
5. Verify the on-disk archive SHA-256 / size
6. Screenshot + OCR
7. Toggle cellular/Airplane Mode, repeat screenshots
8. Write the result JSON
~~~

If purge fails, fall back to:

~~~bash
xcrun devicectl device reboot --device "$UDID" --style userspace
~~~

### 5.3 Result Schema

~~~json
{
  "variant": "V_STATUS_0",
  "device": {"udid": "...", "model": "iPhone15,2", "ios": "27.0.1", "build": "24A446"},
  "fields": {"status": 0, "enabled": true, "displayValue": "omitted", "type": "omitted"},
  "apply": {"archiveSha256": "...", "size": 0, "purge": "systemstatusd+SpringBoard", "ok": true},
  "observations": [
    {"surface": "lockscreen", "airplane": false, "wifi": false, "name": "CUSTOM", "bars": 4, "type": null},
    {"surface": "lockscreen", "airplane": true,  "wifi": false, "name": "CUSTOM", "bars": 0, "type": null}
  ],
  "ocrConfidence": 0.97,
  "manualReview": true,
  "notes": ""
}
~~~

### 5.4 Judgment Rules

- **Positive**: the target behavior appears on at least 2 surfaces and in 3 consecutive runs;
- **Negative**: purge succeeded, archive verification passed, at least 2 surfaces show no target behavior, and 3 consecutive runs agree;
- **Inconclusive**: purge failed, archive not applied, low OCR confidence, or inconsistent results → do not count; fix the method first.

### 5.5 Safety Rules

1. **Zero contact with the primary device**: no writes to the 16 Pro Max; no writes to the 17 Pro Max until ownership is confirmed.
2. **Do not touch `/var/preferences`**: no FeatureFlags attempts, no Security State Recovery triggers.
3. **Do not touch signed carriers**: no carrier-bundle edits, no SSV edits, no CommCenter injection.
4. **Prefer userspace reboot**: avoid USB Restricted after a full reboot.
5. **Every experiment is rollback-safe**: keep the original archive, Books snapshot, and screenshots.
6. **Sensitive entries off by default**: VPN/location/recording/privacy indicators require explicit opt-in.

### 5.6 Rollback

~~~bash
# Restore native (after Track 0)
python3 tools/airlift_carrier_deploy.py --device "$UDID" --reset --force-overwrite
xcrun devicectl device reboot --device "$UDID" --style userspace

# Clean AirLift residue
python3 tools/airlift_carrier_deploy.py --device "$UDID" --clean-device
~~~

---

## 6. Resources, Risks, and Dependencies

### 6.1 Resources

| Resource | Current | Gap |
|---|---|---|
| Test device | 14 Pro 27.0.1 | No 27.1+ device |
| New hardware | 17 Pro Max 27.0 (unconfirmed) | Ownership/permission |
| Simulators | 18 Pro / SE 27.0 | No 27.1 runtime |
| RE tools | otool/nm/strings/Hopper (optional) | No automated dsc extraction script |
| Device automation | devicectl / pymobiledevice3 / AirLift | No reliable purge wrapper |
| OCR | `ocr.swift` | No batch/confidence evaluation |
| Time | — | Track A 10 days; Track B/D 2–3 weeks each |

### 6.2 Risks

| Risk | Probability | Impact | Mitigation |
|---|:---:|---|---|
| Accidental write to primary device | Low but severe | Data/device risk | Track 0 fail-closed; two-person review; no auto device selection |
| AirLift patched on 27.1 | Medium | Delivery interruption | Backup fallback; canary; upstream tracking |
| 27.1 changes the archive schema | Medium | Tool failure | Schema auto-discovery; version adapter; regression matrix |
| Unstable purge causes false negatives | High | Wrong conclusions | Track 0 fix; 3-run consistency; log evidence |
| Device unavailable/locked | Medium | Schedule slip | Simulator first; book device windows |
| OCR misread | Medium | Unreliable evidence | Manual review of low-confidence samples; golden screenshots |
| Sensitive entry misleads users | Medium | Trust/safety | Safety levels; off by default; explicit warnings |
| Upstream schema divergence | Medium | Compatibility | Cross-validation; test vectors; PR alignment |
| Documentation rot | High | Misleads researchers | Status page + Superseded banners + release check |

### 6.3 Dependencies

- iOS 27.1+ runtime/IPSW (Track C);
- 17 Pro Max ownership confirmation (new-hardware matrix);
- GoldenNugget maintainer response (Track F);
- On-device AirLift/AirCard material (Track D3).

---

## 7. Deliverables Checklist

| Category | Deliverable | Track | Acceptance |
|---|---|---|---|
| Code | Fail-closed safety guard + tests | Track 0 | Primary UDID rejected in an empty environment |
| Code | `purge_live_domain` + lab/replace/GUI integration | Track 0 | 3 consistent runs |
| Code | `statusbar_schema.py` + general generator | Track B | ≥5 entries stable |
| Code | Backup-restore pipeline | Track D | 10/10 apply/rollback |
| Code | CI (unit/link/plist round-trip) | Track G | Green |
| Docs | Airplane-mode verdict (positive/negative) | Track A | Reproducible |
| Docs | Compatibility matrix | Track C | Covers 27.0.x/27.1 |
| Docs | Status page + Superseded banners | Track G | Docs hub navigable |
| Docs | Footnote compatibility note | Track E | Boundaries + rollback |
| Upstream | GoldenNugget PR/issue | Track F | Submitted with links |
| Release | v1.x release + changelog | Track G | Matrix green |

---

## 8. Next-72-Hours Action List

1. **Fix S1 first**: implement a fail-closed blocklist in `tools/airlift_carrier_deploy.py`; add a unit test; confirm the 16 Pro Max cannot be selected in an empty environment.
2. **Fix S2**: implement `purge_live_domain()`; validate with a reset archive on the 14 Pro; integrate into `statusbar_variant_lab`.
3. **Baseline**: record the 14 Pro build, native archive (if present), Lock Screen/CC/Home screenshots, and current VPN state.
4. **Run the first 8 A1 variants**: `status=0..5, -1, 255` with `enabled=true` and omitted `displayValue/type`; use the reliable purge; simulator first, then 14 Pro.
5. **Draft the verdict**: start `2026-11-XX_airplane-mode-verdict.md` now, regardless of outcome.
6. **Documentation governance**: add Superseded banners to the 2026-09-30/2026-09-28 conclusions; link this roadmap at the top of the docs hub.
7. **Upstream**: open a GoldenNugget issue/PR draft with the minimal VPN fix diff and test vectors.

---

## Appendix A: Candidate Entry Keys Observed in iOS 27.0 (24A434) `SystemStatusUI`

> Source: `strings -a SystemStatusUI`. These are **candidate keys**; not all are guaranteed to be accepted or rendered by `STStatusBarData`. Track B must validate each one.

~~~text
activityEntry              airPlayEntry              airplaneModeEntry
alarmEntry                 announceNotificationsEntry assistantEntry
avatarEntry                backNavigationEntry       backgroundActivityEntry
batteryEntry               bluetoothEntry            carPlayEntry
cellularEntry              controlCenterEntry        dateEntry
disabledEntry              displayWarningEntry       electronicTollCollectionEntry
externalPrivacyEntry       externalWirelessChargersEntry
forwardNavigationEntry     liquidDetectionEntry      locationEntry
lockEntry                  mainBatteryEntry          menuBarEntry
nikeEntry                  personNameEntry           quietModeEntry
radarEntry                 ringerSilenceEntry        rotationLockEntry
satelliteEntry             secondaryCellularEntry    sensorActivityEntry
shortTimeEntry             studentEntry              tetheringEntry
thermalEntry               timeEntry                 ttyEntry
voiceControlEntry          vpnEntry                  weatherEntry
wifiEntry
~~~

In addition, the `STStatusBarDataCellularEntry` initializer exposes:

~~~text
type
stringValue
suffixStringValue
crossfadeStringValue
badgeStringValue
wifiCalling
callForwarding
showsSOSWhenDisabled
sosAvailable
isBootstrapCellular
status
numberSharingState
lowDataMode
rawValue
displayValue
displayRawValue
~~~

`STUIStatusBarCellularItem` also holds `serviceNameView`, `signalView`, `numberSharingView`, `networkTypeView`, `sosView`, `warningView`, `callForwardingView`, and `rawStringView`, with `nameDisplayIdentifier` / `typeDisplayIdentifier` / `rawDisplayIdentifier` and related display identifiers. These are direct entry points for Track A5/B1.

---

## Appendix B: Experiment Matrix Template

| Variant | status | enabled | displayValue | type | isBootstrap | Other | Expected | Actual (Lock Screen) | Actual (CC) | Airplane Mode | Verdict |
|---|:---:|:---:|:---:|:---:|:---:|---|---|---|---|---|---|
| V0 | 5 | true | 4 | 10 | false | baseline full | name + 4 bars + 5G | | | | |
| V1 | 5 | true | omit | omit | false | partial | name + live bars + no type | | | | |
| V2 | 0 | true | omit | omit | false | status 0 | ? | | | | |
| V3 | 1 | true | omit | omit | false | status 1 | ? | | | | |
| V4 | 2 | true | omit | omit | false | status 2 | ? | | | | |
| V5 | 3 | true | omit | omit | false | status 3 | ? | | | | |
| V6 | 4 | true | omit | omit | false | status 4 | ? | | | | |
| V7 | -1 | true | omit | omit | false | sentinel | expect hidden | | | | |
| V8 | 255 | true | omit | omit | false | sentinel | ? | | | | |
| V9 | 5 | true | -1 | -1 | false | sentinel | ? | | | | |
| V10 | 5 | true | 65535 | 255 | false | sentinel | ? | | | | |
| V11 | 5 | true | omit | omit | true | bootstrap | expect hidden | | | | |
| V12 | 5 | false | omit | omit | false | disabled | expect hidden | | | | |
| V13 | 5 | omit | omit | omit | false | omitted enabled | expect hidden | | | | |
| V14 | 5 | true | omit | omit | false | +airplaneModeEntry | ? | | | | |
| V15 | 5 | true | omit | omit | false | +secondaryCellularEntry | ? | | | | |

---

## Appendix C: Evidence Index and Freshness

| Document | Topic | Freshness | Notes |
|---|---|:---:|---|
| `2026-09-28_speakeasy-analysis.md` | Speakeasy/FeatureFlags | Current | Static FeatureFlags writes are infeasible |
| `2026-09-28_systemstatusui-analysis.md` | Modern status-bar architecture | Current | Foundation |
| `2026-09-28_carrier-data-flow.md` | Data flow | Current | Upstream chain |
| `2026-09-28_viable-paths.md` | Path evaluation | **Partially stale** | Route 3 superseded; Route 5 upgraded to delivered |
| `2026-09-28_architecture.md` | Architecture/boundaries | **Partially stale** | AirLift wording should be "verified on hardware + overwrite limits" |
| `2026-09-30_carrier-footnote-solution.md` | Footnote/carrier verdict | **Partially stale** | Carrier name still says "Pending Physical Verification"; superseded by 2026-10-19/10-21 |
| `2026-10-14_commcenter-reverse-engineering.md` | CommCenter RE | Current | Evidence for the closed upstream path |
| `2026-10-14_dynamic-carrier-status.md` | Dynamic carrier plan | **Partially stale** | Route A found negative on 2026-10-19 |
| `2026-10-19_research-progress-snapshot.md` | Display-domain snapshot | Current | Surface split and partial evidence |
| `2026-10-19_commcenter-preference-injection.md` | Preference injection | Current | Negative result |
| `2026-10-19_dynamic-island-analysis.md` | Dynamic Island rendering | Current | Dual-SIM layout |
| `2026-10-19_empirical-verification.md` | Simulator/physical breakthrough | Current | Archive format discovery |
| `2026-10-21_dynamic-carrier-and-vpn-resolution.md` | Final verdict + VPN | **Current** | Atomic replacement + VPN fix |
| **This document, 2026-10-28** | State audit + roadmap | **Current** | Single entry point |

---

## Appendix D: One-Sentence Conclusion

> **Stop carrying "Airplane Mode synchronization" as an unfinished feature on the roadmap; treat it as a 10-day falsification that must be closed. The real investment is to extend the already-verified archive primitive into a general status-bar override engine and to make delivery, compatibility, and safety guardrails repeatable engineering.**
