# iOS 27.0 Carrier Name / Lock Screen Footnote Research & Local Agent Handoff

> Project Objective: Target the **iPhone 16 Pro Max (A18 Pro) + iOS 27.0 Release** to research and, where possible, achieve two customization goals:
>
> 1. Modify the carrier display text at the top of the lock screen (Carrier Name).
> 2. Modify the text above the bottom home bar on the lock screen (Lock Screen Footnote).
>
> Historical tool: Nugget. The original Nugget path broke after upgrading to iOS 27.
>
> This document serves as a handoff to local Agents for further reverse engineering research, code analysis, experimental design, and tool development.

---

## 1. User Current Device & Objectives

### Device

- Device: iPhone 16 Pro Max
- SoC: Apple A18 Pro
- OS: iOS 27.0 Release
- The target device is not a Beta test device; **iOS 27.0 Release** must be treated as the ultimate compatibility target.

### Goal A: Carrier Name

Replace the carrier text at the top of the system status bar / lock screen:

```text
China Mobile
AT&T
Verizon
...
```

with a user-specified custom string.

### Goal B: Lock Screen Footnote

Modify the text displayed in the bottom area of the lock screen, above the bottom home bar / navigation indicator.

---

# 2. Current Core Conclusions

## 2.1 Original Nugget

Do not continue using the original Nugget legacy restore path on iOS 27.0 Release.

Public projects have explicitly warned that the legacy partial restore path has changed in iOS 27, and continuing to use it may result in data loss and other issues.

The research direction should pivot from:

```text
Nugget GUI
```

toward:

```text
iOS 27 System Architecture
+
Restore / File Write Primitive
+
SystemStatusUI
+
Speakeasy
+
Carrier Data Source
```

---

# 3. Separate Research for the Two Features

```text
                 iOS 27 Customization
                          |
              +-----------+-----------+
              |                       |
        Lock Screen              Carrier Name
         Footnote                     |
              |                       |
    Apple-supported path       Reverse Engineering
              |                       |
   SharedDeviceConfiguration   SystemStatusUI
   / Configuration Profile       Speakeasy
                                CommCenter
                                Carrier Bundle
                                FeatureFlags
```

Do not assume both features still share the same underlying mechanism simply because both were previously provided by Nugget.

---

# 4. Lock Screen Footnote

Apple officially provides corresponding Device Management / Configuration Profile capabilities:

```text
Payload domain:
com.apple.shareddeviceconfiguration

Key:
LockScreenFootnote
```

This mechanism is used for the footnote on the Login Window / Lock Screen.

Important constraints:

- Official management capabilities typically involve Supervision / Device Management.
- On standard personal iPhones, one cannot simply assume that installing a plain `.mobileconfig` will definitely take effect.
- This is an independent route with higher priority and relatively lower risk.

## GoldenNugget

Multiple GoldenNugget forks still retain:

```text
SpringBoard Options
    -> Set Lock Screen Footnote
```

Therefore, verifying this feature should take priority over researching jailbreaks just to implement Footnote.

---

# 5. Carrier Name: The Key Technical Issue at Present

The legacy route was roughly:

```text
Carrier
   |
statusBarOverrides
   |
Classic Status Bar
   |
Custom Carrier String
```

iOS 27 introduced / reinforced a new status bar architecture:

```text
SpringBoard
    |
SystemStatusUI
    |
Carrier / Wi-Fi / Cellular / Battery / etc.
```

Public reverse engineering research indicates that `Speakeasy` is an important feature gate between the legacy Status Bar and the new SystemStatusUI.

Conceptual model:

```text
SpringBoard
    |
    +-- Speakeasy enabled
    |       |
    |       +--> SystemStatusUI
    |
    +-- legacy path
            |
            +--> classic status bar
                    |
                    +--> statusBarOverrides
```

Therefore, Carrier Name research must first answer:

1. Does a consumption path for `statusBarOverrides` still exist in iOS 27.0 Release?
2. What specific mechanism is `Speakeasy` in the Release build?
3. Is `Speakeasy` controlled by `/var/preferences/FeatureFlags/Settings.plist`?
4. Can this flag be rewritten via existing restore / file-write primitives?
5. If Speakeasy cannot be toggled off, does SystemStatusUI have a direct Carrier provider / display-name override?
6. Who ultimately provides the carrier display string: CommCenter, Carrier Bundle, MobileGestalt, SystemStatusUI provider, or another service?

---

# 6. GoldenNugget Fork Differences as the Primary Research Entry Point

Currently, at least two directions warrant comparison.

## Fork A

Repository:

```text
awesomenull-dev/GoldenNugget
```

Its public notes state that Status Bar features on iOS 27+ are restricted, with the core reason involving missing write permissions for the Speakeasy feature flag.

## Fork B

Repository:

```text
phanquocviet8x/GoldenNugget
```

Its README once marked:

```text
Status Bar (patched on iOS 27)
Change carrier name
```

However, its public research notes also pointed out that the Carrier Name path is constrained by:

```text
Speakeasy
SystemStatusUI
FeatureFlags
write permission
```

among other factors.

Therefore, one cannot determine whether Fork B has implemented Carrier Name on iOS 27.0 Release solely based on its README.

### Primary Task

Perform a complete Git diff between the two forks.

Recommendation:

```bash
git clone https://github.com/awesomenull-dev/GoldenNugget.git GoldenNugget-A
git clone https://github.com/phanquocviet8x/GoldenNugget.git GoldenNugget-B

diff -ru GoldenNugget-A GoldenNugget-B
```

Focus searches on:

```bash
grep -Rni "Speakeasy" .
grep -Rni "StatusBar" .
grep -Rni "carrier" .
grep -Rni "statusBarOverrides" .
grep -Rni "FeatureFlags" .
grep -Rni "SystemStatusUI" .
grep -Rni "27.0" .
```

Goal:

> Locate the actual code changes in Fork B behind the claimed "patched on iOS 27", and determine whether it is a genuinely functional path or an incomplete implementation / README desynchronized with code.

---

# 7. `Speakeasy` Research Roadmap

Confirm whether the following model is accurate:

```text
FeatureFlags
    |
    +-- SpringBoard
            |
            +-- Speakeasy
                    |
                    +-- SystemStatusUI
```

Focus inspection on:

```text
/var/preferences/FeatureFlags/Settings.plist
```

However, do not simply assume:

```text
Speakeasy = false
```

will automatically resolve the issue.

It must be confirmed via reverse engineering iOS 27.0 firmware:

- Key name
- Domain
- Read path
- Write path
- SpringBoard consumption location
- Whether fallback exists
- Whether other gates exist

---

# 8. SystemStatusUI Reverse Engineering

This is the long-term core track for Carrier Name.

Targets:

```text
SystemStatusUI.framework
```

and related binaries:

```text
SpringBoard.app
SpringBoardFoundation.framework
SpringBoardServices.framework
CommCenter
Carrier Bundles
```

Static analysis tools:

- strings
- nm
- otool
- Hopper
- Ghidra
- IDA (if available)

For example:

```bash
strings SystemStatusUI | grep -i carrier
strings SystemStatusUI | grep -i operator
strings SystemStatusUI | grep -i status
strings SystemStatusUI | grep -i speakeasy
```

Further:

```bash
nm -arch arm64 SystemStatusUI
otool -ov SystemStatusUI
```

Focus on symbols conceptually similar to:

```text
CarrierStatusProvider
CarrierLabel
OperatorName
CarrierDisplayName
CellularStatus
StatusItem
StatusBarItem
```

Do not merely grep for strings.

Establish the call relationships:

```text
Who provides carrier identity
        |
Who transforms it into a display string
        |
Who delivers the display string to SystemStatusUI
        |
Who ultimately renders the UI
```

---

# 9. Dynamic Analysis Roadmap

If static analysis reveals candidate methods such as:

```text
-[XXX carrierDisplayName]
```

or similar providers:

```text
CarrierProvider
CellularStatusProvider
OperatorNameProvider
```

Next phase research:

```text
SystemStatusUI
      |
Carrier provider
      |
operatorName
      |
display string
```

Observe:

- Callers
- Invocation timing
- Return values
- Whether overrides exist
- Whether fallbacks exist
- Whether Preferences are read
- Whether CommCenter is read
- Whether MobileGestalt is read

The ultimate objective is to pinpoint the minimal override point.

If a jailbreak / tweak environment becomes available in the future, the ideal architecture would be:

```text
SystemStatusUI
      |
CarrierProvider
      |
Hook carrierDisplayName
      |
return custom string
```

This avoids modifying system files entirely.

---

# 10. Carrier Bundle Roadmap

Investigate:

```text
Carrier Bundle
      |
CommCenter
      |
Carrier identity
      |
SystemStatusUI
```

Focus on:

```text
CFBundleDisplayName
CarrierName
OperatorName
```

and other carrier metadata.

However, do not assume modifying the Carrier Bundle will directly alter the final display.

It must be verified whether:

```text
Carrier Bundle
   |
CommCenter
   |
returned carrier identity
   |
SystemStatusUI
```

this chain truly exists.

---

# 11. MobileGestalt Roadmap

`bad_query` / MobileGestalt editor represents an important avenue, but MobileGestalt cannot be directly equated with Carrier Name.

Research workflow:

```text
MobileGestalt keys
       |
Search Carrier / StatusBar / Operator
       |
Confirm whether SystemStatusUI reads it
       |
If read:
    Research write primitives
```

Do not modify MobileGestalt keys blindly.

---

# 12. `bad_query` / Sandbox Escape Roadmap

The public `bad_query` project verified portions across:

```text
iOS 26.x
iOS 27.0 beta 1
beta 2
beta 3
beta 4
```

However, iOS 27.0 Release must be verified independently.

Crucially:

```text
27.0 DB4
     |
     +--> exploit works
     |
     v
iOS 27.0 Release
     |
     +--> Apple changed something
```

Therefore, performing a diff is highly valuable:

```text
DB4 vs iOS 27.0 Release
```

for binary and system behavior changes.

Investigate:

- ContainerManager
- MobileHouseArrest
- sandbox
- file provider
- backup / restore
- AFC
- system service IPC
- feature flag access

The goal is not necessarily finding a kernel exploit.

Prioritize finding:

> Whether there exists an Apple service that inherently possesses system file write permissions and can be leveraged by ordinary device operations via IPC / restore / management interfaces.

---

# 13. WorkPlot / Erosion

These projects, based on `bad_query`-class capabilities, were verified against iOS 27 Betas.

However, one cannot equate:

```text
iOS 27 Beta
```

with:

```text
iOS 27.0 Release
```

The current device is running Release; thus, independent verification is required.

Do not run unconfirmed exploits directly on a daily driver device.

---

# 14. Restore / File Write Roadmap

Research:

```text
Backup
Restore
Sparse Restore
BookRestore
MobileDevice
AFC
HouseArrest
ContainerManager
MDM
Configuration Profile
```

Specifically answer:

```text
Target file
    |
Can it be modified via standard backup?
    |
Can it be written back via restore?
    |
Is it rejected by an allowlist?
    |
Is it purged by Security Recovery?
```

Key targets:

```text
/var/preferences/FeatureFlags/Settings.plist
```

and configuration files potentially related to StatusBar / SystemStatusUI.

---

# 15. A Critical Experimental Design

If an:

```text
iOS 27.0 DB4
```

test device can be acquired, prioritize testing:

```text
DB4
 |
bad_query
 |
GoldenNugget
 |
StatusBar
 |
Speakeasy
```

Then:

```text
DB4
 |
Release
 |
Identical tests
```

Compare:

- File existence
- File permissions
- Container mapping
- Sandbox profile
- Service behavior
- Restore behavior
- Security Recovery behavior
- FeatureFlags write behavior

This yields far more value than blindly attempting Carrier plist edits.

---

# 16. Recommended Overall Research Tree

```text
                           iOS 27.0 Carrier
                                  |
                +-----------------+-----------------+
                |                                   |
         Data Source                         UI / Rendering
                |                                   |
       +--------+---------+                  SystemStatusUI
       |        |         |                         |
   CommCenter Carrier  MobileGestalt          Carrier Provider
       |        |         |                         |
       +--------+---------+                         |
                |                                   |
          Carrier Identity                      Display String
                                                    |
                                             Final UI Rendering
```

Concurrently:

```text
                  Status Bar Architecture
                           |
                    Speakeasy Gate
                           |
             +-------------+-------------+
             |                           |
       SystemStatusUI             Classic StatusBar
             |                           |
       New Carrier UI            statusBarOverrides
```

The ultimate goal is finding any single controllable point within these paths.

---

# 17. Track Priorities

Local Agents are advised to execute in the following sequence.

## P0 — Codebase Fact Verification

1. Clone both GoldenNugget forks.
2. Complete diff.
3. Identify the iOS 27 Status Bar patch.
4. Verify whether README matches actual code.

## P1 — Firmware Static Analysis

1. Acquire exact iOS 27.0 IPSW.
2. Extract SystemStatusUI.
3. Analyze SpringBoard.
4. Search Speakeasy.
5. Search Carrier / Operator / StatusBar.
6. Construct call graph.

## P2 — Feature Flag

Research:

```text
/var/preferences/FeatureFlags/Settings.plist
```

Confirm whether:

```text
Speakeasy
SpeakeasyNewStatusBar
```

exist, along with their specific consumption locations.

## P3 — Write Primitives

Research:

```text
backup
restore
AFC
HouseArrest
ContainerManager
MDM
Configuration Profile
```

Confirm whether legitimate / non-jailbreak existing write paths exist.

## P4 — Exploit

Only if P0–P3 cannot resolve the issue, proceed to investigate:

```text
bad_query
sandbox escape
kernel exploit
jailbreak
```

## P5 — Tool Development

Final objective:

```text
iOS 27 Carrier Customizer
```

Ideal features:

```text
Read Current Carrier
Backup Relevant State
Set Custom Carrier
Verify
Restore Original
```

along with an independent:

```text
Lock Screen Footnote Customizer
```

---

# 18. Safety & Experimental Principles

Since this is a primary daily driver iPhone:

### Do Not

- Run Nugget restore without confirmed compatibility.
- Modify system plists without a complete backup.
- Modify files related to Apple ID / Keychain / DataProtection.
- Use "iOS 27 Nugget patched" binaries of unknown origin.
- Treat Beta exploits as Release exploits.
- Write to `/var/preferences` without knowing the recovery path.
- Run experiments carrying high bootloop risk directly on the daily driver device.

### Recommended

```text
Static Analysis
    ↓
Simulation / Test Environment
    ↓
Reproducible Experiment
    ↓
Minimal Write
    ↓
Verification
    ↓
Primary Device
```

Save prior to every write:

```text
Original file
SHA-256
Device backup
Experiment log
iOS build
Tool commit
```

---

# 19. Local Agent Phase 1 Prompt

The following content can be handed directly to a local Agent:

> You are researching system UI customization on an iPhone 16 Pro Max (A18 Pro) running iOS 27.0 Release.
>
> Objectives:
>
> 1. Modify Lock Screen Footnote.
> 2. Modify Lock Screen / Status Bar Carrier Name.
>
> Do not assume Nugget remains effective on iOS 27.
>
> During Phase 1, directly executing restore, system plist writes, exploits, or other high-risk operations on the primary daily driver device is prohibited.
>
> Phase 1 is strictly restricted to static code analysis.
>
> Tasks:
>
> 1. Clone:
>    - awesomenull-dev/GoldenNugget
>    - phanquocviet8x/GoldenNugget
>
> 2. Perform a complete diff between the two projects.
>
> 3. Search:
>    - Speakeasy
>    - SpeakeasyNewStatusBar
>    - SystemStatusUI
>    - statusBarOverrides
>    - Carrier
>    - Operator
>    - FeatureFlags
>    - LockScreenFootnote
>
> 4. Answer definitively:
>    - What did phanquocviet8x actually modify under the claimed "patched on iOS 27"?
>    - Can this patch truly modify Carrier Name on iOS 27.0 Release?
>    - What write primitive does it depend on?
>    - Does it rely on Beta-only exploits?
>    - Does the README match the actual code?
>
> 5. After obtaining the iOS 27.0 Release IPSW, analyze:
>    - SpringBoard
>    - SystemStatusUI
>    - SpringBoardFoundation
>    - SpringBoardServices
>    - CommCenter
>    - Carrier Bundles
>
> 6. Search and establish:
>
>    SIM
>    -> CommCenter
>    -> Carrier Identity
>    -> SystemStatusUI
>    -> Carrier Display String
>    -> Final UI
>
> 7. Research:
>
>    /var/preferences/FeatureFlags/Settings.plist
>
>    Determine the specific implementation, read points, and write constraints of Speakeasy.
>
> 8. Investigate whether `statusBarOverrides` is still consumed by SpringBoard in iOS 27.0 Release.
>
> 9. Investigate why `bad_query` broke from iOS 27 beta 4 to iOS 27.0 Release, focusing on:
>    - sandbox
>    - ContainerManager
>    - MobileHouseArrest
>    - backup / restore
>    - file-write primitive
>
> 10. Deliver final output documents:
>
>    - architecture.md
>    - golden-nugget-diff.md
>    - speakeasy-analysis.md
>    - systemstatusui-analysis.md
>    - carrier-data-flow.md
>    - exploit-surface.md
>    - viable-paths.md
>    - risk-register.md
>
> Every conclusion must distinguish between:
>
> - Confirmed
> - Confirmed from Code
> - Confirmed from Firmware
> - Community Report
> - Hypothesis
>
> Do not treat README claims as facts.
>
> If a viable route is discovered, provide first:
>
> 1. Principle
> 2. Prerequisites
> 3. Required permissions
> 4. Required exploits
> 5. Whether it supports iOS 27.0 Release
> 6. Risks
> 7. Recovery procedure
>
> Only then consider tool development.
>
> The priority goal is not "executing quickly", but identifying the minimal, truly verifiable modification path on iOS 27.0 Release.

---

# 20. Success Criteria

Final research success must not be defined as:

> "Someone online said it works."

It must be defined as:

```text
iPhone 16 Pro Max
        |
iOS 27.0 Release
        |
Without relying on unverified Beta exploits
        |
Capable of modifying Carrier Display String
        |
Capable of restoring original state
```

and:

```text
iPhone 16 Pro Max
        |
iOS 27.0 Release
        |
LockScreenFootnote
        |
Successfully modified
        |
Successfully restored
```

---

# 21. Research Log Template

Record for each experiment:

```text
Date:
Device:
iOS:
Build:
Tool:
Git Commit:
Operation:
Target:
Original SHA256:
Modified SHA256:
Result:
Reboot Result:
Respring Result:
Data Loss:
Recovery:
Notes:
```

---

# 22. Most Critical Current Technical Hypotheses

### Hypothesis H1

`statusBarOverrides` still exists, and if `Speakeasy` is disabled / bypassed, the legacy Status Bar can be reused.

### Hypothesis H2

`Speakeasy` is a modifiable Feature Flag.

### Hypothesis H3

Even if Speakeasy cannot be modified, a Carrier display-name provider exists within SystemStatusUI that can be modified via configuration or future hooks.

### Hypothesis H4

Carrier Name originates from CommCenter / Carrier Bundle rather than being generated entirely internally by SystemStatusUI.

### Hypothesis H5

The primary difference between iOS 27.0 Release and 27.0 beta 4 is that Apple patched the public sandbox / file-write primitives, rather than completely altering the Status Bar architecture.

All of these require experimental verification and cannot be assumed as facts.

---

# 23. Conclusion

The most valuable pursuit right now is not continuing to look for "another Nugget".

What is truly worth researching is:

```text
                 iOS 27.0
                    |
            +-------+-------+
            |               |
        Speakeasy       SystemStatusUI
            |               |
       FeatureFlags      Carrier Provider
            |               |
       Legacy Status     Display String
            |               |
   statusBarOverrides    Final Carrier
```

Where:

**P0: GoldenNugget two forks code diff**

↓

**P1: Speakeasy / FeatureFlags**

↓

**P2: SystemStatusUI Carrier provider**

↓

**P3: File-write / restore primitives on iOS 27.0 Release**

↓

**P4: If necessary, sandbox escape / jailbreak**

This is currently the most systematic, verifiable, and lowest-risk research route.

---

## Reference Projects / Resources

- Nugget: https://github.com/leminlimez/Nugget
- GoldenNugget (awesomenull-dev): https://github.com/awesomenull-dev/GoldenNugget
- GoldenNugget (phanquocviet8x): https://github.com/phanquocviet8x/GoldenNugget
- bad_query: https://github.com/forcequitOS/bad_query
- WorkPlot: https://github.com/gievano/WorkPlot
- Erosion: https://github.com/jailbreakdotparty/Erosion
- Apple Device Management — Lock Screen Message: https://developer.apple.com/documentation/devicemanagement/lockscreenmessage
