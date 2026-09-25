# iOS 27 Carrier & Lock Screen Customization Research

> Reverse engineering research for customizing Carrier Name and Lock Screen Footnote on **iPhone 16 Pro Max (A18 Pro) + iOS 27.0 Release**.

## 🎯 Research Objectives

| # | Target | Description |
|---|--------|-------------|
| A | **Carrier Name** | Replace the carrier text (e.g. 中国移动, AT&T, Verizon) on the status bar / lock screen with a custom string |
| B | **Lock Screen Footnote** | Modify the text displayed above the home indicator on the lock screen |

## 📋 Background

The legacy tool **Nugget** previously provided both customizations, but its partial restore path broke on iOS 27.0. This project documents a systematic, safety-first research approach to find new viable paths on the release firmware.

## 🏗️ Architecture Overview

```
                     iOS 27.0 Carrier Name
                            |
              +-------------+-------------+
              |                           |
        Data Source                   UI / Rendering
              |                           |
     +--------+--------+          SystemStatusUI
     |        |        |                 |
 CommCenter  Carrier  MobileGestalt  CarrierProvider
             Bundle                      |
              |                     Display String
        Carrier Identity                 |
                                   Final Rendering
```

### Speakeasy Gate (Status Bar Architecture)

```
                  SpringBoard
                      |
               Speakeasy Gate
                      |
           +----------+----------+
           |                     |
     SystemStatusUI        Classic StatusBar
           |                     |
     New Carrier UI       statusBarOverrides
```

## 🔬 Research Priorities

| Priority | Phase | Description |
|----------|-------|-------------|
| **P0** | Code Diff | Compare GoldenNugget forks to identify iOS 27 patches |
| **P1** | Static Analysis | Reverse engineer `SystemStatusUI`, `SpringBoard`, `Speakeasy` from iOS 27.0 IPSW |
| **P2** | Feature Flags | Investigate `Speakeasy` / `SpeakeasyNewStatusBar` in FeatureFlags |
| **P3** | Write Primitives | Research non-jailbreak file-write paths (backup/restore, AFC, MDM, etc.) |
| **P4** | Exploits | Only if P0–P3 fail: sandbox escape, kernel exploit, jailbreak |
| **P5** | Tooling | Build a safe, user-friendly customization tool |

## 📁 Repository Structure

```
.
├── README.md                                          # This file
└── iOS27_Carrier_LockScreen_Research_Handoff.md       # Full research handoff document
```

## 🔑 Key Technical Hypotheses

- **H1**: `statusBarOverrides` still exists; disabling `Speakeasy` may re-enable the legacy status bar path.
- **H2**: `Speakeasy` is a modifiable Feature Flag (`/var/preferences/FeatureFlags/Settings.plist`).
- **H3**: `SystemStatusUI` contains a hookable Carrier display-name provider.
- **H4**: Carrier Name originates from `CommCenter` / Carrier Bundle, not generated internally by `SystemStatusUI`.
- **H5**: iOS 27.0 Release vs beta 4 — Apple patched the file-write primitive, not the status bar architecture itself.

> ⚠️ All hypotheses require experimental verification. Do not treat them as facts.

## 🔗 Related Projects & References

| Project | Link |
|---------|------|
| Nugget | [leminlimez/Nugget](https://github.com/leminlimez/Nugget) |
| GoldenNugget (Fork A) | [awesomenull-dev/GoldenNugget](https://github.com/awesomenull-dev/GoldenNugget) |
| GoldenNugget (Fork B) | [phanquocviet8x/GoldenNugget](https://github.com/phanquocviet8x/GoldenNugget) |
| bad_query | [forcequitOS/bad_query](https://github.com/forcequitOS/bad_query) |
| WorkPlot | [gievano/WorkPlot](https://github.com/gievano/WorkPlot) |
| Erosion | [jailbreakdotparty/Erosion](https://github.com/jailbreakdotparty/Erosion) |
| Apple Lock Screen Message | [Apple Docs](https://developer.apple.com/documentation/devicemanagement/lockscreenmessage) |

## ⚠️ Safety Guidelines

This research targets a **primary device** — all experiments must follow:

1. **Static analysis first** — no blind modifications
2. **Full backup** before any write operation
3. **SHA-256 verification** of all modified files
4. **No Beta-only exploits** on Release firmware
5. **Reversibility confirmed** before every change
6. **Experiment logging** with device, iOS build, tool commit, and results

## 📜 License

This repository is for **educational and research purposes only**. Use at your own risk.
