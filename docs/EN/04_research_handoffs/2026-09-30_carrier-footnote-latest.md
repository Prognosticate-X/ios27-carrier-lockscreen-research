# iOS 27.0 Carrier Name / Lock Screen Footnote Latest Research Handoff Document

Updated: 2026-09-30  
Target Device: iPhone 16 Pro Max / iOS 27.0 / Build 24A437

## Core Conclusions

This round of research brings four critical updates:

1. **PyAirLift explicitly handles iOS 27.0 / 24A437.**
2. **A key limitation of AirLift has been further confirmed: The underlying ATAirlock relies on a rename mechanism and cannot simply overwrite an already existing target file.** Therefore, "AirLift → directly overwrite `/var/mobile/Library/SpringBoard/statusBarOverrides`" cannot be treated as a verified approach.
3. **GoldenNugget-Mobile has become the focal research target for Footnote**: It is an iOS 27 on-device customization project and explicitly incorporates `Set Lock Screen Footnote`.
4. **Carrier Name research must expand to encompass the complete data-flow across SystemStatusUI / Speakeasy / CommCenter / Carrier Bundle, rather than continuing to fixate solely on `statusBarOverrides`.**

---

# 1. AirLift

Repository:

https://github.com/0xjohnnydev/airlift

Public documentation indicates its capabilities include:

- Paired Mac
- USB / Wi-Fi
- Does not require a full jailbreak
- iPhone requires no auxiliary App
- Can access specific subpaths of `/var/mobile`
- `/var/mobile/Library`
- `/var/mobile/Library/Preferences`
- `/var/mobile/Library/SpringBoard`
- `/var/mobile/Containers`
- `/var/mobile/Containers/Data/Application`
- `/var/mobile/Containers/Shared/AppGroup`
- `/var/tmp`

Definition:

```text
AirLift != Jailbreak
AirLift != Arbitrary system file write permission
AirLift = Specific AirTraffic sandbox / path validation bypass
```

---

# 2. PyAirLift: 24A437 Integrated into Toolchain

Repository:

https://github.com/awesomenull-dev/PyAirLift

PyAirLift is a Python implementation of AirLift, usable in tandem with `pymobiledevice3`.

Public compatibility checks already list:

```text
version: 27.0
build: 24A437
```

Therefore:

```text
AirLift / PyAirLift recognizes iOS 27.0 / 24A437
= Confirmed
```

However, this does not equate to:

```text
iPhone 16 Pro Max / 24A437
+
Carrier Name / Footnote
= Succeeded
```

Final verification on the target device remains:

```text
Unknown
```

---

# 3. Critical Constraint: Cannot Simply Overwrite Existing Files

PyAirLift / ATAirlock file writes exploit a rename mechanism, yielding this central limitation:

```text
Can only write new filenames that do not already exist in the target directory
```

Therefore:

```text
Target file does not exist
→ create / rename
→ Viable
```

However:

```text
Target file already exists
→ Simple overwrite
→ Does NOT hold directly
```

This directly impacts:

```text
/var/mobile/Library/SpringBoard/statusBarOverrides
```

and similar legacy Nugget configuration files.

Consequently, the previous assumption:

```text
AirLift
→ Directly overwrite statusBarOverrides
```

must be downgraded to:

```text
Hypothesis / Restricted
```

Agents must investigate:

```text
A. Whether deleting the original file is viable
B. Whether renaming the original file is viable
C. Symlink workaround
D. Creating a new file that SpringBoard automatically ingests
E. Indirect replacement via backup / restore
F. Whether another daemon can perform the overwrite
G. Whether GoldenNugget-Mobile already has a workaround
```

---

# 4. GoldenNugget-Mobile: Primary Footnote Candidate Project

Repository:

https://github.com/GoldenNugget-Team/GoldenNugget-mobile

An iOS 27 on-device customization project whose public documentation explicitly includes:

```text
Set Lock Screen Footnote
```

and utilizes AirLift-related techniques.

The current public feature matrix does not explicitly promote:

```text
Change Carrier Name
```

as a peer Mobile capability.

Hence, a very distinct signal emerges:

```text
AirLift
  +
iOS 27 on-device customization
  +
Lock Screen Footnote
```

has already materialized in operational code.

Agents should clone the repository directly:

```bash
git clone https://github.com/GoldenNugget-Team/GoldenNugget-mobile.git
```

Then run:

```bash
grep -Rni "LockScreenFootnote" .
grep -Rni "Footnote" .
grep -Rni "shareddeviceconfiguration" .
grep -Rni "AirLift" .
grep -Rni "Airlift" .
grep -Rni "restore" .
grep -Rni "SpringBoard" .
grep -Rni "respring" .
grep -Rni "rename" .
grep -Rni "backup" .
```

Must trace:

```text
UI
→ Footnote action
→ payload / plist
→ target file
→ write mechanism
→ refresh / respring
→ rollback
```

---

# 5. Apple Official LockScreenFootnote

Apple Device Management schema:

```text
com.apple.shareddeviceconfiguration
```

Contains:

```text
LockScreenFootnote
```

Reference:

https://github.com/apple/device-management/blob/release/mdm/profiles/com.apple.shareddeviceconfiguration.yaml

This is a formal property within Apple's official configuration framework, not a custom property invented by Nugget.

Continued verification required:

1. Actual file source on iOS 27
2. Actual write target used by GoldenNugget-Mobile
3. Whether Supervision is required
4. Whether delivered via configuration profile
5. Whether modifiable indirectly via AirLift
6. How SpringBoard refreshes the display

Current evidence status:

```text
Apple LockScreenFootnote
= Confirmed

GoldenNugget iOS 27 Footnote feature
= Confirmed

iPhone 16 Pro Max / 24A437 actual on-device success
= Unknown
```

---

# 6. Carrier Name: Official GoldenNugget

Repository:

https://github.com/GoldenNugget-Team/GoldenNugget

The official README currently states explicitly:

```text
Status Bar
disabled on iOS 27+
```

The underlying reason involves:

```text
Speakeasy feature flag
write permissions
```

Historical capabilities included:

```text
Change carrier name
Change secondary carrier name
```

Thus, the current official track stands:

```text
Carrier Name
→ legacy Status Bar
→ iOS 27
→ Speakeasy
→ write permission problem
→ Status Bar disabled
```

Current assessment:

```text
Official GoldenNugget Carrier Name on iOS 27
= Not Working / Disabled
```

---

# 7. phanquocviet8x GoldenNugget

Repository:

https://github.com/phanquocviet8x/GoldenNugget

Its README claims:

```text
Status Bar (patched on iOS 27)

Change carrier name
Change secondary carrier name
```

However, there is insufficient credible evidence confirming that:

```text
iPhone 16 Pro Max
+
iOS 27.0 Final
+
24A437
+
Carrier Name
```

has succeeded.

Therefore:

```text
Claimed / Unverified
```

Must be verified via source diff rather than accepted from README claims.

---

# 8. Carrier Name: Expanding Research Scope

Research must no longer fixate solely on:

```text
statusBarOverrides
```

Establish the end-to-end data-flow:

```text
Cellular / CommCenter
        ↓
Carrier configuration
        ↓
Carrier Bundle
        ↓
CoreTelephony / Telephony
        ↓
SystemStatusUI
        ↓
Speakeasy
        ↓
Carrier display
        ↓
Lock Screen / Status Bar
```

Core question:

> Where exactly does `statusBarOverrides` fit in the actual iOS 27 data-flow?

---

# 9. iOS 27.0 Carrier Bundle: New Research Entry Point

Repository:

https://github.com/VCTGomes/ios-carrier-bundle

and:

https://github.com/dwilliamsuk/ios-carrier-bundles

Public datasets already incorporate:

```text
iOS 27.0 / 24A437
```

Traditional system path:

```text
/System/Library/Carrier Bundles/iPhone/
```

Carrier Bundles may involve:

- APN
- VoLTE
- VoWiFi
- 5G
- RCS
- Tethering
- Voicemail
- Emergency call behavior
- Carrier-specific configurations / strings

Certain public datasets also include files corresponding to iPhone 16 / iPhone 16 Pro Max.

Do not immediately assume:

```text
Carrier Bundle
→ Carrier Name
```

What truly requires investigation:

```text
Carrier Bundle
→ CommCenter
→ CoreTelephony
→ SystemStatusUI
```

or whether intermediate caches / generated state exist.

Furthermore, do not attempt to write directly to:

```text
/System/Library/Carrier Bundles/iPhone/
```

merely because the Carrier Bundle was located. AirLift's confirmed `/var/mobile` capability cannot be extrapolated to system partition write privileges.

---

# 10. AirCard-iOS

Repository:

https://github.com/Mak5er/AirCard-iOS

Utilizes:

```text
AirliftFFI.xcframework
```

Targeting:

```text
iOS 27.0+
```

Applied in actual on-device customization.

Prioritize examining:

```text
AirLift initialization
AirliftFFI
Rust core
file write
rollback
refresh / respring
```

Specifically check whether it or its dependencies have resolved the:

```text
existing file overwrite
```

issue.

---

# 11. Legacy Exploit Tracks

## bad_query

https://github.com/forcequitOS/bad_query

iOS 27 beta sandbox escape research; currently not top priority for Final 24A437.

## WorkPlot

https://github.com/gievano/WorkPlot

Early iOS 27 exploit / sandbox exploration.

## Erosion

https://github.com/jailbreakdotparty/Erosion

Serves as historical reference.

Current priority ranking:

```text
AirLift > bad_query / WorkPlot / Erosion
```

---

# 12. Current Reordered Roadmap

## P0 — GoldenNugget-Mobile Footnote

```text
GoldenNugget-Mobile
→ LockScreenFootnote
→ actual target file
→ AirLift / restore mechanism
→ refresh
```

This represents the closest track to an executable implementation.

## P1 — PyAirLift Overwrite Constraint

Must resolve:

```text
existing file
→ Why it cannot overwrite
→ Whether delete / rename / restore workarounds exist
```

## P2 — GoldenNugget Two-Branch Carrier Name Diff

```text
GoldenNugget-Team
vs
phanquocviet8x/GoldenNugget
```

Focus areas:

```text
Carrier
StatusBar
Speakeasy
FeatureFlags
SystemStatusUI
statusBarOverrides
```

## P3 — SystemStatusUI / Speakeasy

If `statusBarOverrides` is defunct:

```text
SystemStatusUI
+
Speakeasy
+
Carrier provider
```

becomes the primary path.

## P4 — Carrier Bundle / CommCenter

Establish the data-flow:

```text
Carrier Bundle
↓
CommCenter
↓
CoreTelephony
↓
SystemStatusUI
```

## P5 — On-Device Experiments

Execute only after static analysis is concluded:

```text
read
→ backup
→ hash
→ minimal write
→ refresh
→ verify
```

---

# 13. Current Evidence Matrix

| Project / Item | Status | Evidence Level |
|---|---|---|
| AirLift iOS 27 | Public project | Confirmed |
| PyAirLift 24A437 | Compatibility check | Confirmed |
| AirLift `/var/mobile/Library/SpringBoard` | README | Confirmed |
| AirLift direct overwrite of existing files | ATAirlock rename constraint | Not Working / Restricted |
| AirCard-iOS + AirLift | Production iOS 27 project | Confirmed |
| GoldenNugget-Mobile | iOS 27 on-device | Confirmed |
| GoldenNugget-Mobile Footnote | Feature list | Confirmed as feature |
| Apple LockScreenFootnote | Official schema | Confirmed |
| 24A437 + iPhone 16 Pro Max Footnote | No reliable on-device evidence found | Unknown |
| Legacy statusBarOverrides Carrier Name | Historically functional | Confirmed historically |
| Official GoldenNugget iOS 27 Carrier Name | Status Bar disabled | Not Working |
| phanquocviet8x Carrier Name patch | README claims | Claimed / Unverified |
| 24A437 + iPhone 16 Pro Max Carrier Name | No reliable on-device evidence found | Unknown |
| iOS 27 Carrier Bundle data | Publicly available | Confirmed |
| Carrier Bundle → Carrier Name direct link | Unproven | Hypothesis |
| Speakeasy → New Status Bar | Requires continued reverse engineering | Highly Likely / Needs verification |

---

# 14. Safety Requirements

Prior to any on-device experiment:

```text
1. Full iPhone backup
2. Record iOS Build
3. Record Device Model
4. Save original file
5. Calculate SHA-256
6. Save modification logs
7. Prepare rollback procedure
```

Do not operate first on:

```text
MobileGestalt
Keychain
Data Protection
Apple Account
iCloud
Core system databases
```

Do not execute unverified:

```text
restore
exploit
jailbreak
system file deletion
```

---

# 15. Local Agent Next Phase Tasks

## Task A — GoldenNugget-Mobile

Identify:

```text
LockScreenFootnote
→ target file
→ write method
→ refresh method
→ rollback
```

## Task B — PyAirLift

Audit:

```text
ATAirlock
rename
write
file existence
path validation
```

Search for:

```text
existing-file workaround
```

## Task C — GoldenNugget Diff

Compare:

```text
GoldenNugget-Team
vs
phanquocviet8x/GoldenNugget
```

Focus on:

```text
Carrier
StatusBar
Speakeasy
FeatureFlags
SystemStatusUI
statusBarOverrides
```

## Task D — Carrier Bundle

Obtain iOS 27.0 / 24A437 Carrier Bundles.

Targeting:

```text
iPhone 16 Pro Max
```

Perform:

```text
plist diff
strings
CarrierName
OperatorName
StatusBar
```

## Task E — SystemStatusUI

If iOS 27.0 system binaries can be extracted, analyze:

```text
SystemStatusUI
SpringBoard
CommCenter
CoreTelephony
```

Establish Carrier display data-flow.

---

# 16. Final Agent Deliverable

Generate:

```text
iOS27_Carrier_Footnote_Solution.md
```

Suggested sections:

```text
# Executive Summary
# Device / Build
# Current iOS 27 Architecture
# AirLift Analysis
# PyAirLift Analysis
# GoldenNugget-Mobile Analysis
# GoldenNugget Diff
# Carrier Name Data Flow
# statusBarOverrides
# Speakeasy
# SystemStatusUI
# Carrier Bundles
# LockScreenFootnote
# File Paths
# Write Mechanism
# Refresh Mechanism
# Working Methods
# Failed Methods
# Device Compatibility
# Risk Assessment
# Backup / Recovery
# Step-by-Step Experiment
# Rollback Procedure
# Final Conclusion
```

Must categorize using the six evidence levels:

```text
Confirmed
Highly Likely
Claimed / Unverified
Hypothesis
Not Working
Unknown
```

All "Confirmed" findings must specify:

```text
iOS version
Build
Device
Repository
Commit / Release
```

If README conflicts with source code, treat source code and reproducible experiments as authoritative.

---

# 17. Key Projects

- AirLift: https://github.com/0xjohnnydev/airlift
- PyAirLift: https://github.com/awesomenull-dev/PyAirLift
- AirCard-iOS: https://github.com/Mak5er/AirCard-iOS
- GoldenNugget-Team: https://github.com/GoldenNugget-Team/GoldenNugget
- GoldenNugget-Mobile: https://github.com/GoldenNugget-Team/GoldenNugget-mobile
- phanquocviet8x GoldenNugget: https://github.com/phanquocviet8x/GoldenNugget
- iOS Carrier Bundle: https://github.com/VCTGomes/ios-carrier-bundle
- iOS Carrier Bundles: https://github.com/dwilliamsuk/ios-carrier-bundles
- bad_query: https://github.com/forcequitOS/bad_query
- WorkPlot: https://github.com/gievano/WorkPlot
- Erosion: https://github.com/jailbreakdotparty/Erosion

---

# 18. Agent Execution Prompt

You are taking over:

```text
Device:
iPhone 16 Pro Max

OS:
iOS 27.0

Build:
24A437
```

Objectives:

```text
1. Lock Screen Carrier / Operator Name
2. Lock Screen Bottom Footnote
```

Do not directly use the legacy Nugget restore procedure.

First clone:

```text
AirLift
PyAirLift
AirCard-iOS
GoldenNugget-Team
GoldenNugget-Mobile
phanquocviet8x/GoldenNugget
iOS 27 Carrier Bundles
```

Conduct source-level data-flow analysis.

Must prioritize solving:

```text
1. What file does GoldenNugget-Mobile's Footnote actually write to?
2. How does AirLift handle existing target files?
3. What did GoldenNugget's iOS 27 Carrier patch actually modify?
4. Is statusBarOverrides still valid in iOS 27.0 Final?
5. What is the Carrier data source for SystemStatusUI / Speakeasy?
6. How do Carrier Bundle / CommCenter / CoreTelephony / SystemStatusUI connect?
```

Any verified conclusion must state:

```text
iOS version
Build
Device
Repository
Commit / Release
```

Without 24A437 on-device evidence, flag as:

```text
Unknown
```

When README conflicts with source code, rely on source code and reproducible experiments.

Final output:

```text
iOS27_Carrier_Footnote_Solution.md
```

Categorized under six evidence levels:

```text
Confirmed
Highly Likely
Claimed / Unverified
Hypothesis
Not Working
Unknown
```
