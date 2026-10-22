# iOS 27.0 Lock Screen Carrier Name / Lock Screen Footnote Research Handoff Document

> Target Device: iPhone 16 Pro Max / iOS 27.0 / Build 24A437
>
> Objectives: 1. Modify lock screen top Carrier Name; 2. Modify lock screen bottom Lock Screen Footnote.
>
> This document is provided for local Agents to continue source code audits, reverse engineering analysis, and on-device validation.

## 1. Current Conclusions

As of 2026-09-28, the most promising route warranting continued investigation has shifted from legacy Nugget / `bad_query` toward:

```text
AirLift
  ↓
iOS 27.0 AirTraffic sandbox escape / file access
  ↓
/var/mobile/Library/SpringBoard
  ↓
SpringBoard / SystemStatusUI configuration
  ├─ Carrier Name
  └─ Lock Screen Footnote
```

The pivotal question is not "whether tools exist," but rather:

- Does iOS 27.0 Final still read `statusBarOverrides`?
- Does the new `Speakeasy` / `SystemStatusUI` bypass the legacy status bar path?
- Can the authentic configuration location for Footnote still be accessed via AirLift?
- What exactly did GoldenNugget's purported iOS 27 patch modify?

At present, **there is insufficient evidence to prove that either feature can succeed directly on iPhone 16 Pro Max / iOS 27.0 Final**.

## 2. AirLift

Repository:

https://github.com/0xjohnnydev/airlift

AirLift is a sandbox escape / file access tool targeting iOS 27.0 AirTraffic, not a traditional beautification/tweaking tool.

Public documentation indicates its primary capabilities include:

- Paired Mac
- USB / Wi-Fi
- Does not require a full jailbreak
- iPhone requires no additional App installed
- Can access specific `/var/mobile` subpaths:
- Includes `/var/mobile/Library`
- Includes `/var/mobile/Library/Preferences`
- Includes `/var/mobile/Library/SpringBoard`
- Includes `/var/mobile/Containers`
- Includes `/var/mobile/Containers/Data/Application`
- Includes `/var/mobile/Containers/Shared/AppGroup`
- Includes `/var/tmp`

Critical constraint: Public records indicate it cannot arbitrarily modify all system data, such as `MobileGestalt.plist`.

Therefore:

```text
AirLift != Jailbreak
AirLift != Arbitrary system file write permission
AirLift = Specific sandbox / path validation bypass
```

Subsequent verification must determine:

1. Can it read `/var/mobile/Library/SpringBoard/statusBarOverrides`?
2. Can it overwrite this file?
3. Can it access Footnote-related configurations?
4. Does SpringBoard read the changes after modification?
5. Does it require a respring or reboot?
6. Does iOS 27.0 Final 24A437 maintain identical behavior?

## 3. AirCard-iOS

Repository:

https://github.com/EpochME/aircard-ios

This project utilizes AirLift-related `AirliftFFI.xcframework` for iOS 27 customizations, such as Wallet themes, lock screen passcode keypad theming, PosterBoard, etc.

Value:

```text
AirLift has already been adopted by third-party projects as operational iOS 27 customization infrastructure.
```

However, the success of AirCard-iOS does not directly demonstrate that Carrier Name / Footnote are modifiable.

Focus investigation on:

- AirLift initialization
- AirliftFFI
- File read/write APIs
- Post-sandbox-escape path handling
- iOS 27 compatibility check
- Rollback / restore mechanisms

## 4. GoldenNugget Mandatory Source Diff

### GoldenNugget-Team

https://github.com/GoldenNugget-Team/GoldenNugget

Public records show that Status Bar options are restricted on iOS 27+ and involve `Speakeasy`; Lock Screen Footnote features still exist.

### phanquocviet8x GoldenNugget

https://github.com/phanquocviet8x/GoldenNugget

Its public notes claim:

```text
Status Bar
patched on iOS 27
Change carrier name
```

However, its research notes also mention Carrier Name being restricted by the system, Speakeasy, SystemStatusUI, and exploit / jailbreak prerequisites.

Hence, source code verification is mandatory:

> Does "patched on iOS 27" genuinely implement Carrier Name modification, or does it merely retain the UI toggle entry point?

Recommendation:

```bash
git clone https://github.com/GoldenNugget-Team/GoldenNugget.git GoldenNugget-Team
git clone https://github.com/phanquocviet8x/GoldenNugget.git GoldenNugget-phan
diff -ru GoldenNugget-Team GoldenNugget-phan

grep -Rni "Speakeasy" GoldenNugget-Team GoldenNugget-phan
grep -Rni "StatusBar" GoldenNugget-Team GoldenNugget-phan
grep -Rni "carrier" GoldenNugget-Team GoldenNugget-phan
grep -Rni "statusBarOverrides" GoldenNugget-Team GoldenNugget-phan
grep -Rni "FeatureFlags" GoldenNugget-Team GoldenNugget-phan
grep -Rni "SystemStatusUI" GoldenNugget-Team GoldenNugget-phan
grep -Rni "LockScreenFootnote" GoldenNugget-Team GoldenNugget-phan
grep -Rni "27.0" GoldenNugget-Team GoldenNugget-phan
```

Must ultimately determine:

```text
Carrier Name actual modification path
Footnote actual modification path
iOS 27 modification points
Speakeasy bypass mechanism
Whether it relies on restore
Whether it relies on MobileGestalt
Whether it relies on jailbreak
Whether it can be transitioned to AirLift direct-write
```

## 5. Carrier Name: Legacy Route

The historical Nugget / GoldenNugget path was:

```text
HomeDomain
└── Library
    └── SpringBoard
        └── statusBarOverrides
```

Conceptual path:

```text
/var/mobile/Library/SpringBoard/statusBarOverrides
```

Priority research track:

```text
AirLift
  ↓
statusBarOverrides
  ↓
Carrier-related entry
  ↓
SpringBoard / SystemStatusUI
  ↓
Carrier Name
```

Note: This remains a research hypothesis, not a proven iOS 27.0 Final solution.

## 6. iOS 27 New Status Bar Architecture

Crucial areas of investigation:

```text
SpringBoard
  ├─ legacy Status Bar
  │    └─ statusBarOverrides
  │
  └─ Speakeasy
       └─ SystemStatusUI
            └─ Carrier provider / display string
```

Must answer:

### Scenario A

SystemStatusUI still reads `statusBarOverrides`.

→ AirLift + `statusBarOverrides` may resolve Carrier Name directly.

### Scenario B

Speakeasy / SystemStatusUI completely bypasses `statusBarOverrides`.

→ Requires reverse engineering SystemStatusUI's Carrier provider / display string.

### Scenario C

Speakeasy feature flag toggles between legacy and new UI.

→ If safely switchable back to legacy, the old route might be restored.

## 7. Speakeasy

Focus searches on:

```text
Speakeasy
SpeakeasyNewStatusBar
FeatureFlags
SystemStatusUI
```

Public reverse engineering notes previously referenced paths like:

```text
/var/preferences/FeatureFlags/Settings.plist
```

Do not assume these paths, keys, or write techniques remain valid on iOS 27.0 Final 24A437.

Must re-verify from:

- Current GoldenNugget source code
- Current system binaries
- On-device filesystem
- Relevant public reverse engineering research

## 8. Lock Screen Footnote

The historical Apple configuration architecture provides:

```text
com.apple.shareddeviceconfiguration
LockScreenFootnote
```

GoldenNugget also retains:

```text
Set Lock Screen Footnote
```

Must determine:

1. Officially supported mechanism
2. Whether Supervision / MDM is required
3. Actual plist / configuration profile path
4. Whether iOS 27 changed storage locations
5. What GoldenNugget actually writes
6. Whether AirLift can access it
7. What refresh mechanism is required after modification
8. Whether any on-device successful cases exist on iOS 27.0 Final

## 9. CarrierSIM Collateral Evidence

Recent public materials highlight CarrierSIM, an AirLift-based iOS 27.0 carrier configuration modification project.

Its goal is not Carrier Name, but carrier configurations / 5G capability flags.

Research value:

```text
AirLift
  ↓
Carrier configuration
  ↓
Actual iOS 27 system behavioral changes
```

However, do not extrapolate its success directly to Carrier Name feasibility; files, daemons, caches, and UI providers must each be verified independently.

## 10. Legacy Exploit Track Priorities

### bad_query

https://github.com/forcequitOS/bad_query

Primarily iOS 27 beta sandbox escape research. Direct compatibility with Final 24A437 must be re-evaluated.

### WorkPlot

https://github.com/gievano/WorkPlot

Early iOS 27 exploit / sandbox exploration.

### Erosion

https://github.com/jailbreakdotparty/Erosion

Similarly serves as historical exploit reference material, but current priority ranks below AirLift.

## 11. Recommended Priorities

```text
P0
├─ GoldenNugget source diff
├─ Identify Carrier Name write path
└─ Identify LockScreenFootnote write path

P1
├─ AirLift source code
├─ AirliftFFI
└─ AirCard-iOS integration

P2
├─ statusBarOverrides
├─ SystemStatusUI
├─ Speakeasy
└─ FeatureFlags

P3
└─ Minimal read-only / harmless write validation on test device

P4
├─ Carrier Name
└─ Lock Screen Footnote

P5
└─ If above fail, evaluate exploit / jailbreak routes
```

## 12. Device Experimental Strategy

### Phase 1: Read-Only

Verify:

```text
AirLift
  ↓
/var/mobile/Library/SpringBoard/
```

Read-only, no modifications.

### Phase 2: Harmless File

Verify:

```text
write
read
delete
```

For instance, create a test file and confirm its complete lifecycle.

### Phase 3: Backup Target File

Prior to modifying any system configuration:

```text
original file
  ↓
SHA-256
  ↓
local backup
  ↓
modified copy
```

Record:

```text
iOS version
Build
device model
file path
file size
SHA256
timestamp
```

## 13. Things Not to Do First

Do not directly:

```text
Modify MobileGestalt
Delete system plists
Restore entire HomeDomain
Modify unknown FeatureFlags
Execute unverified jailbreak / exploit binaries
```

Especially do not modify critical files without a recovery plan:

```text
SpringBoard
SystemStatusUI
MobileGestalt
Data Protection
Keychain
Apple Account
iCloud
```

## 14. Questions Local Agents Must Answer

### Carrier Name

```text
1. Does statusBarOverrides still exist in iOS 27.0 24A437?
2. Does SpringBoard read it?
3. Does SystemStatusUI read it?
4. Does Speakeasy bypass it?
5. What did GoldenNugget's iOS 27 patch actually modify?
6. Can AirLift read and write this file?
7. Does modification require respring or reboot?
8. Are there actual documented success cases?
9. What iOS Build do those success cases correspond to?
10. Does it apply to iPhone 16 Pro Max / A18 Pro?
```

### Lock Screen Footnote

```text
1. What is the current authentic configuration source for LockScreenFootnote?
2. Does it still use com.apple.shareddeviceconfiguration?
3. What is the actual plist / database path?
4. Did iOS 27 change storage locations?
5. What does GoldenNugget actually write?
6. Can AirLift access it?
7. What refresh mechanism is required after modification?
8. Are there documented success cases on iOS 27.0 Final?
```

## 15. Final Agent Deliverable

Ultimately produce:

```text
iOS27_Carrier_Footnote_Solution.md
```

Suggested structure:

```text
# Executive Summary
# Device / Build
# Current iOS 27 Architecture
# AirLift Analysis
# AirCard-iOS Analysis
# GoldenNugget Diff
# Carrier Name Reverse Engineering
# statusBarOverrides
# Speakeasy
# SystemStatusUI
# LockScreenFootnote
# File Paths
# Required Permissions
# Working Methods
# Failed Methods
# Device Compatibility
# Risk Assessment
# Backup / Recovery
# Step-by-Step Experiment
# Rollback Procedure
# Final Conclusion
```

Each conclusion must be annotated with:

```text
Confirmed
Highly Likely
Hypothesis
Not Working
Unknown
```

All "Confirmed" entries must specify:

```text
iOS version
Build
Device
Project
Commit / Release
```

Do not treat beta version findings as iOS 27.0 Final results.

## 16. Key Repositories

- AirLift: https://github.com/0xjohnnydev/airlift
- AirCard-iOS: https://github.com/EpochME/aircard-ios
- GoldenNugget-Team: https://github.com/GoldenNugget-Team/GoldenNugget
- phanquocviet8x/GoldenNugget: https://github.com/phanquocviet8x/GoldenNugget
- bad_query: https://github.com/forcequitOS/bad_query
- WorkPlot: https://github.com/gievano/WorkPlot
- Erosion: https://github.com/jailbreakdotparty/Erosion

## 17. Agent Execution Prompt

You are taking over a system customization reverse engineering task on iPhone 16 Pro Max / iOS 27.0 Build 24A437.

Objectives:

1. Modify lock screen top Carrier Name
2. Modify lock screen bottom Footnote

Do not assume the legacy Nugget route remains valid.

Prioritize researching:

```text
AirLift
AirCard-iOS
GoldenNugget-Team
phanquocviet8x/GoldenNugget
statusBarOverrides
Speakeasy
SystemStatusUI
LockScreenFootnote
```

First perform source code static analysis.

Must answer:

```text
A. Actual data path for Carrier Name
B. Actual data path for Footnote
C. iOS 27 new status bar architecture
D. Whether statusBarOverrides is still read
E. Specific role of Speakeasy
F. What GoldenNugget's iOS 27 patch actually modified
G. Whether AirLift can complete required read/write operations
H. Whether physical device success cases exist on iOS 27.0 Final 24A437
```

If a viable route is discovered:

1. Provide original file paths
2. Provide original data structures
3. Provide before/after modification examples
4. Provide AirLift operational instructions
5. Provide SpringBoard refresh procedure
6. Provide complete rollback steps
7. Provide risk analysis
8. Clarify whether jailbreak is required

If unfeasible, do not simply state "not viable"; detail:

```text
Which link in the chain is blocked
Why it is blocked
Whether it is permissions / non-existent file / UI not reading / daemon overwriting / feature flag / exploit limitation
Whether alternative paths exist
```

Ultimately compile an executable:

```text
iOS27_Carrier_Footnote_Solution.md
```
