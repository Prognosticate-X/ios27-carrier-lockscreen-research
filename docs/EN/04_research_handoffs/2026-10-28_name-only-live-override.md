# iOS 27 “Name-Only, Everything Else Live” Research (Replicating Nugget)

**Document ID**: `DOC-20261028-NAME-ONLY`  
**Date**: 2026-10-28  
**Device**: iPhone 14 Pro (iPhone15,2) / iOS 27.0.1 (24A446)  
**Goal**: replicate Nugget's iOS 26-and-earlier behavior — **change only the carrier name, while signal bars, radio-type icon, and Airplane-Mode behavior all come from live data**.  
**Related**: [2026-10-28 Research Roadmap](2026-10-28_next-research-roadmap.md) · [2026-10-28 Airplane-Mode Matrix](2026-10-28_airplane-mode-status-matrix.md)

> **Device note**: the USB-attached device is an **iPhone 14 Pro**, not an iPhone 14 Pro Max; no 14 Pro Max is present. The primary 16 Pro Max and the 17 Pro Max are blocked in `safety.json`.

---

## ⚠️ 2026-10-28 22:10 Incident Record (Read First)

With Find My already disabled, after running a `backup2 restore --system` of a minimal backup (`Manifest.db` + `IsFullBackup=True`):

1. The 14 Pro rebooted into **Setup Assistant**: `Setup.app` and `budd` are running, the screen shows a "hej" welcome page, and no carrier name.
2. The target file was **not written**: a subsequent filtered backup shows zero records for `WirelessDomain/Library/Preferences/com.apple.operator_1.plist`; WirelessDomain still has only the original 22 records.
3. Conclusion: **iOS 27 backup restore neither safely writes WirelessDomain nor leaves the device usable; do not repeat this experiment.**

**Recovery guidance**: stop all writes; have the user complete Setup Assistant on-device, or restore from an existing full backup via Finder / Apple Devices. Do not choose “Erase and Set Up” unless the test device's data is known to be disposable.

---

---

## 1. Why Nugget Worked on iOS 26 and Earlier

The legacy `statusBarOverrides` file is a `StatusBarOverrideData` C struct with **per-field override flags**:

- Set only `serviceString` and its name flag;
- Do not set `signalStrength`, `serviceType`, `enabled/status`, etc.;
- The system keeps using live data for those fields.

The name is static, but signal, radio type, and Airplane-Mode coupling remain real.

iOS 27's modern status bar uses `STStatusBarData` + `StatusBarOverrides.archive`:

- `dataByApplyingOverlay:` replaces the **whole `STStatusBarDataCellularEntry` object**;
- Missing fields decode to `0/false` in `initWithCoder:`;
- There is no “not overridden” flag.

So the legacy field-level pass-through semantics are gone.

---

## 2. Runtime Data-Model Evidence

Objective-C runtime enumeration of `SystemStatus.framework` on the iOS 27.0 simulator (24A434):

`STStatusBarDataCellularEntry` ivars:

~~~text
_wifiCallingEnabled      : B
_callForwardingEnabled   : B
_showsSOSWhenDisabled    : B
_sosAvailable            : B
_isBootstrapCellular     : B
_type                    : q
_string                  : NSString
_suffixString            : NSString
_crossfadeString         : NSString
_badgeString             : NSString
_numberSharingState      : q
~~~

Superclass chain:

~~~text
STStatusBarDataEntry          -> _enabled : B
STStatusBarDataIntegerEntry   -> _displayRawValue : B, _rawValue : q, _displayValue : q
STStatusBarDataNetworkEntry   -> _lowDataModeActive : B, _status : q
~~~

**There is no `flags` / `hasString` / `overrideString` / “unset” boolean field.**  
Name, radio type, signal, and enabled/status all live inside one atomic entry. That is why a static archive cannot change only the name.

---

## 3. Additional Experiments (iPhone 14 Pro / 27.0.1)

| Variant | Fields | Result | Conclusion |
|---|---|---|---|
| `NOSTATUS` | `enabled=true`, omit `status/displayValue/type` | No name, no cellular bars | Omitting `status` hides the whole cellular item |
| `NOENABLED` | omit `enabled/status/displayValue/type` | No name, no cellular bars | Omitting `enabled` also hides the item |
| `type=0` | `status=5, enabled=true`, omit `displayValue`, `type=0` | Name + live bars, **no radio-type text** | 0 means “no type” |
| `type=-1` | same, `type=-1` | Name + live bars, **no radio-type text** | No live fallback |
| `type=255` | same, `type=255` | Name + live bars, **no radio-type text** | No live fallback |
| `type=10` | same, `type=10` | Name + live bars + **5G** | Radio type is static when set |
| `status=1` | `enabled=true`, omit `displayValue/type` | Cellular on: **native name + live bars/type**; Airplane: **custom name** | Live-fallback in the opposite direction |
| `status=5 + isBootstrapCellular=true` | omit `displayValue/type` | No name, bars present | The name gate is directly disabled |

Conclusion: **Neither partial mode nor omitting `displayValue` can preserve live radio-type text or Airplane-Mode hiding; `status=1` is a reverse live-fallback, not a custom-name mode.**

> **2026-10-29 iPhone 14 Pro Hardware Correction (Important)**: Side-by-side physical hardware verification (see [`2026-10-29_displayvalue-omission-hardware-verification.md`](../03_hardware_and_verification/2026-10-29_displayvalue-omission-hardware-verification.md)) proved that the "live bars" observed when omitting `displayValue` in the table above actually came from the **green circular cellular toggle icon inside the Control Center connectivity card** (which queries `CoreTelephony` directly and always displays live `2` bars), whereas the **top status bar and Control Center top-left** are pinned to **`0` greyed-out empty bars** because `-[NSCoder decodeIntegerForKey:@"displayValue"]` returns `0` when the key is omitted. Therefore, `displayValue = 4` remains the recommended default.

---

## 4. New Upstream Lead: WirelessDomain

### 4.1 Backup Forensics

A filtered `pymobiledevice3 backup2 backup --only-regex` backup shows that `Manifest.db` contains:

~~~text
WirelessDomain  Library/Preferences/com.apple.commcenter.plist
WirelessDomain  Library/Preferences/com.apple.commcenter.data.plist
WirelessDomain  Library/Preferences/com.apple.CommCenter.counts.plist
... 22 records total
~~~

Key metadata:

- `UserID=25`, `GroupID=25` (not `mobile` 501);
- `ProtectionClass=4`;
- `com.apple.commcenter.plist` is currently `3269` bytes;
- `com.apple.operator_1.plist` / `com.apple.carrier_1.plist` **do not exist**.

This means CommCenter's real preference domain is `/var/wireless/Library/Preferences`, and that domain is included in the backup manifest. The 2026-10-19 injection test only wrote HomeDomain (`/var/mobile/Library/Preferences`), which CommCenter does not read.

### 4.2 Minimal Backup Restore Experiment

A minimal backup was built with four records:

- `WirelessDomain` root / `Library` / `Library/Preferences` directories;
- A new `WirelessDomain/Library/Preferences/com.apple.operator_1.plist` containing:

~~~xml
<dict>
  <key>InterCarrierRoamingDisplayNames</key>
  <dict>
    <key>46001</key><string>WIFITEST</string>
    ...
  </dict>
  <key>CarrierName</key><string>WIFITEST</string>
  <key>ShowCarrierName</key><true/>
</dict>
~~~

Command:

~~~bash
pymobiledevice3 backup2 restore .artifacts/backup/wireless-test \
  --no-reboot --no-settings --no-remove --skip-apps --no-copy
~~~

Device response:

~~~text
MBErrorDomain/211
Find My iPhone must be disabled before restoring
~~~

**This is the current hard blocker: backup restore requires Find My iPhone to be turned off first.**

### 4.3 Next Validation If Find My Is Disabled

1. Disable Find My iPhone on the 14 Pro test device (requires the Apple ID password);
2. Re-run the minimal restore, writing only `com.apple.operator_1.plist`;
3. Cold-restart both `cfprefsd` instances + `CommCenter` + `SpringBoard` via CoreDevice;
4. Capture Lock Screen / Control Center:
   - If **WIFITEST + live signal/type/Airplane behavior** appears → success; the live name comes from WirelessDomain;
   - If the native name remains → the key is not on CommCenter's read path; test a merged `com.apple.commcenter.plist` injection next;
   - If No Service appears → immediately restore the original backup / remove the injected file.

Risk: even with `--no-remove`, a backup restore is intrusive; do it only on the test device, with a full local backup first.

---

## 5. Other Paths

| Path | Feasibility | Notes |
|---|---|---|
| `WirelessDomain` backup injection | **Falsified and unsafe** | The restore puts the device into Setup Assistant and does not write the target file (see incident); do not repeat |
| Carrier Bundle Overlay display name | Low | Signature checks / No Service; a display-only overlay has not been found |
| Runtime publish to `STStatusBarOverridesStatusDomain` | Not on stock iOS | Requires `com.apple.systemstatus.publisher` entitlement |
| Legacy `statusBarOverrides` C struct | Infeasible | Speakeasy forces the modern status bar; SpringBoard ignores it |
| Disable Speakeasy/FeatureFlags | Infeasible | `/var/preferences` root write protection + Security State Recovery |
| `UIStatusBar_Base(Snapshots) sb_setLocalDataOverrides:` | Not applicable | Snapshot-only, not a system-wide live publisher |

---

## 6. Available Paths Now

The WirelessDomain backup-injection path is **falsified and unsafe**: it did not write the target file and put the test device into Setup Assistant. There is currently no usable non-jailbroken static/backup path.

The remaining options are:

1. **Accept static partial mode**: custom name + live signal bars, but radio-type text cannot be live and the name persists in Airplane Mode;
2. **Jailbreak/TrollStore runtime-publisher prototype**: requires an entitlement and is outside the stock-iOS delivery boundary;
3. **Wait for Apple to change the status-bar data model or expose an official configuration surface** (no evidence today).

No further device writes until the test device is recovered.

---

## 7. Evidence and Tools

- Runtime introspection: `.artifacts/introspect/introspect.m` (ivars/properties/methods)
- Minimal backup: `.artifacts/backup/wireless-test/`
- Harness: [`tools/exp_status_matrix.py`](../../../tools/exp_status_matrix.py)
- REA wrapper: [`tools/rea.sh`](../../../tools/rea.sh)
- Screenshots: `.artifacts/screens/NOSTATUS-lock-*.png`, `.artifacts/screens/T0-cc-*.png`, `.artifacts/screens/T_1-cc-*.png`

---

## 8. One-Sentence Conclusion

> **Nugget's name-only behavior depends on legacy per-field override flags; iOS 27's `STStatusBarDataCellularEntry` is an atomic object with no hidden flags. WirelessDomain backup injection is falsified and puts the device into Setup Assistant; within the non-jailbroken boundary there is currently no usable “name-only, everything else live” solution.**
