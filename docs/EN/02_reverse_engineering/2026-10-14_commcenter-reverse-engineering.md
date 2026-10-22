# iOS 27 Dynamic Carrier Name (Live Signal + Airplane Mode Linkage) In-Depth Reverse Engineering Report

> **Research Date**: 2026-10-14  
> **Research Context**: Resolving architectural bottlenecks in the existing `StatusBarOverrides.archive` solution, where custom carrier names remain statically persistent after enabling Airplane Mode and signal bars are statically locked to full strength (4 bars) without reflecting live baseband signal fluctuations.  
> **Reverse Engineering Targets**: `UIKitCore` (`0x1c70d9000`), `SystemStatus.framework` (`0x2a4726000`), `CoreTelephony.framework` (`0x1a737b000`), `libCommCenterBase.dylib` (`0x1b3d3e000`), and all 4,088 system images within the in-memory `dyld_shared_cache`.  

---

## 1. Problem Statement & First-Principles Root Cause Analysis

In empirical tests conducted on physical hardware (iPhone 16 Pro Max / iOS 27.0 `24A437`) and simulator environments, injecting a custom carrier name via `/var/mobile/Library/SpringBoard/StatusBarOverrides.archive` introduced two substantive user experience defects:

1. **Carrier name remains "hardcoded" at the top of the screen / Control Center after turning on Airplane Mode**:
   Upon enabling Airplane Mode, the real cellular connection is severed, yet the lock screen top bar and Control Center continue rendering the custom Carrier Name without hiding.
2. **Signal bars are permanently fixed at full strength (4 bars), failing to display live real-time signal**:
   Even when selecting "Signal Bars: Default (Unchanged)" in the automation tool (`tools/gui_server.py`), the status bar signal remains permanently fixed at 4 full bars and fails to fluctuate with real baseband signal strength.

### 1.1 Direct Bug at Tool Level (`tools/gui_server.py`)
In `tools/gui_server.py`, the frontend dropdown `<select id="primaryBars">` option "Default (Unchanged)" has value `""` (passed to backend JSON as `null` / `None`), but backend line 1123 contained a hardcoded fallback:
```python
primary_bars=body.get("bars") if body.get("bars") is not None else 4
```
Furthermore, `build_cellular_archive()` hardcoded `enabled: True`, `status: 5` (Connected), `displayValue: 4` (Full bars), and `type: 10` (5G) when constructing `STStatusBarDataCellularEntry`.

### 1.2 Fundamental Limitation at Architectural Level (Atomic Entire-Object Replacement in `STStatusBarData`)
The deeper architectural question is: even if the Python script is modified not to pass `4`, can `StatusBarOverrides.archive` under the iOS 27 `SystemStatus` architecture achieve "overriding only `string` (carrier name), while allowing `displayValue` (signal bars) and `enabled` (airplane mode visibility) to track live baseband data"?

We performed assembly-level decompilation verification on the status bar merging logic in `dyld_shared_cache`.

---

## 2. Phase 1 (Direction 3 Falsification): Disassembly of `StatusBarData` Override Merging Mechanism

In `UIKitCore` (base address `0x1c70d9000`, sharing identical `StatusBarData` entity models with `SystemStatus`), core merge methods reside at:
- `-[_UIStatusBarData _applyUpdate:keys:]` (`0x1c8014748 .. 0x1c801487c`)
- `-[_UIStatusBarData applyUpdate:]` (`0x1c801487c .. 0x1c80148f4`)
- `-[_UIStatusBarData dataByApplyingOverlay:]` (`0x1c80148f4 .. 0x1c8014a98`)
- `-[_UIStatusBarData dataByApplyingUpdate:keys:]` (`0x1c8014a98 .. 0x1c8014c10`)
- `-[_UIStatusBarDataAggregator _updatedDataFromData:delayedKeys:]` (`0x1c80153f4 .. 0x1c80155f0`)

### 2.1 Critical Assembly Instructions & Selector Analysis
```text
=== -[_UIStatusBarData _applyUpdate:keys:] (0x1c8014748..0x1c801487c) ===
  0x1c80147ac: BL 0x1ca7cd040 ; objc_msgSend$countByEnumeratingWithState:objects:count:
  0x1c80147b0: CBZ x0, 0x1c8014838
  0x1c80147ec: BL 0x1ca7cdc30 ; objc_msgSend$valueForKey:
  0x1c80147f8: CBZ x0, 0x1c801480c
  0x1c8014808: BL 0x1ca7ceb30 ; objc_msgSend$setValue:forKey:

=== -[_UIStatusBarData dataByApplyingOverlay:] (0x1c80148f4..0x1c8014a98) ===
  0x1c8014958: BL 0x1ca9024e0 ; objc_msgSend$existingEntryKeys
  0x1c8014970: BL 0x1ca7cd040 ; objc_msgSend$countByEnumeratingWithState:objects:count:
  0x1c80149b4: BL 0x1ca7cdc30 ; objc_msgSend$valueForKey:
  0x1c80149c4: CBZ x25, 0x1c8014a0c
  0x1c80149d4: BL 0x1ca7ccfe0 ; objc_msgSend$copy
  0x1c80149ec: BL 0x1ca7cdc30 ; objc_msgSend$valueForKey:
  0x1c8014a04: BL 0x1ca7ceb30 ; objc_msgSend$setValue:forKey:
```

### 2.2 Falsification Conclusions
1. **Top-Level Entry Objects as Minimum Merging Granularity**: `dataByApplyingOverlay:` and `_applyUpdate:keys:` iterate over top-level `entryKeys` (e.g. `"cellularEntry"`, `"secondaryCellularEntry"`, `"airplaneModeEntry"`). As long as `cellularEntry != nil` in the override archive, the system uses `setValue:forKey:` to replace the **entire `STStatusBarDataCellularEntry` instance pointer** over live data; **no field-level merging logic exists whatsoever**.
2. **No Sentinel Passthrough Values in Deserialization**: In `-[_UIStatusBarDataCellularEntry initWithCoder:]` (`0x1c80108ac`) and its superclass `-[_UIStatusBarDataIntegerEntry initWithCoder:]` (`0x1c800f3c4`), `displayValue`, `rawValue`, `type`, `status`, and `enabled` are all primitive integer/boolean types. If omitted from the archive, `NSKeyedUnarchiver` decodes them to defaults `0` / `NO` (meaning 0 signal bars or a disabled entry) without falling back to live `STTelephonyStatusDomain`.
3. **Verdict**: **`StatusBarOverrides.archive` is architecturally destined to be a full static mock override**. Achieving "live signal + Airplane Mode linkage" requires abandoning patches at the `StatusBarOverrides` tier and shifting reverse engineering upstream to the authoritative data source.

---

## 3. Phase 2 (Direction 1 Investigation): `SystemStatus` Default Keys & `CTSimLabel` Boundaries

Runtime reflection and symbol scans were performed across `SystemStatus.framework` (`0x2a4726000`) and `CoreTelephony.framework` (`0x1a737b000`):

1. **`STSystemStatusDefaults` (`SystemStatus.framework`)**:
   - Subclasses `BSAbstractDefaultDomain`, binding only 3 boolean properties via `-_bindAndRegisterDefaults`:
     - `shouldEnableInternalBundles` (`TB,D,N`)
     - `shouldEnableUnknownBundles` (`TB,D,N`)
     - `shouldEnableUnknownBackgroundActivities` (`TB,D,N`)
   - **Conclusion**: `SystemStatus` contains no internal `NSUserDefaults` keys designed for overriding carrier text independently.
2. **`CTSimLabel` & `CTXPCSetSimLabelRequest` (`CoreTelephony.framework`)**:
   - Symbol addresses: `-[CTSimLabel initWithId:andText:andDidSetup:]` (`0x1a73a109c`), `-[CTXPCSetSimLabelRequest performRequestWithHandler:completionHandler:]` (`0x1a73dcbdc`).
   - **Conclusion**: This mechanism manages eSIM / dual-SIM custom labels (corresponding to status bar badge `badgeString`, such as `"Primary"`, `"Secondary"`, `"P"`, `"S"`), and cannot replace the primary carrier name `operatorName`.

---

## 4. Phase 3 (Direction 2 Deep Breakthrough): `CommCenter` / `libCommCenterBase` Carrier Name Synthesis & Configuration Contract

Scanning all 4,088 dyld shared cache images confirmed that the authoritative origin of cellular operator names resides in `CoreTelephony.framework` (`0x1a737b000`) and `libCommCenterBase.dylib` (`0x1b3d3e000`).

### 4.1 `CoreTelephony` Operator Name Retrieval XPC Contract
Disassembly of `_CTServerConnectionCopyCurrentOperatorName` (`0x1a746fe38 .. 0x1a7470100`) and `-[CTXPCGetOperatorNameRequest performRequestWithHandler:completionHandler:]` (`0x1a741701c`):
- The client dispatches an XPC dictionary request to `CommCenter`:
  - `kRequest` (`0x1a7502b46`) = `"kRegistrationGetProperty"` (`0x1a7512c26`)
  - Property keys: `"kRegistrationOperatorName"` (`0x1a7513473`) and `"kRegistrationLocalize"` (`0x1a751348d`)
- The subsequent branch (`0x1a74700a0`) supports requesting `"kRegistrationProviderName"` (`0x1a7512d9b`) with `"kRegistrationUseCarrierBundle"` (`0x1a7512db5`).

### 4.2 `NetworkListOperator::getLocalizedCompositeName` (`0x1b3db050c`) Line-by-Line Disassembly Reconstruction
In `libCommCenterBase.dylib`, the function `_ZNK19NetworkListOperator25getLocalizedCompositeNameERKNSt3__110shared_ptrIK8RegistryEEN10subscriber7SimSlotE` (`0x1b3db050c .. 0x1b3db09ec`) reveals an internal **dictionary-mapping-based carrier name override mechanism** built into `CommCenter`:

```text
  0x1b3db0548: BL 0x1b3dc4910 ; Registry::throwIfNotInitialized()
  0x1b3db0550: ADRP x8, 0x1f5adf000
  0x1b3db0554: ADD x8, x8, #0x998 -> 0x1f5adf998 (__ZTI24CarrierSettingsInterface)
  0x1b3db0590: BL 0x1b3d54da4 ; unordered_map::find(CarrierSettingsInterface RTTI)
  0x1b3db0654: LDR x16, [x23, #0x0] ; Load CarrierSettingsInterface vtable
  0x1b3db0664: LDR x9, [x16, #0x50]!; vtable offset +0x50 (copyValueForKey)
  0x1b3db0668: ADRP x3, 0x1f5ae6000
  0x1b3db066c: ADD x3, x3, #0xdd0 -> 0x1f5ae6dd0 CFSTR("InterCarrierRoamingDisplayNames")
  0x1b3db067c: MOV w2, #0x5          ; BundleType = 5 (Operator Bundle)
  0x1b3db068c: BLRAA x9, x16         ; Call CarrierSettingsInterface->copyValueForKey(...)
  0x1b3db06a4: LDR x8, [sp, #0x80]
  0x1b3db06a8: CBZ x8, 0x1b3db06e8   ; If dict is null, branch to getCompositeName()
  0x1b3db06b8: BL 0x1b3d5af0c ; MCCAndMNC::MCCAndMNC(MCC, MNC)
  0x1b3db06c4: BL 0x1b3d5b318 ; MCCAndMNC::getStringValue() (e.g. "46000", "46001")
  0x1b3db0810: BL 0x1ba87c500 ; CFDictionaryGetValue(dict, cfPlmnString)
  0x1b3db0818: CBZ x0, 0x1b3db086c
  0x1b3db0820: BL 0x1ba87c560 ; CFGetTypeID(val)
  0x1b3db0828: BL 0x1ba87f3f0 ; CFStringGetTypeID()
  0x1b3db0830: B.NE 0x1b3db086c
  0x1b3db0854: BL 0x1ba88b230 ; Convert matched custom CFString to return string!
```

**Key Mechanism Interpretation**:
- When the `Operator` configuration contains an `InterCarrierRoamingDisplayNames` dictionary, `CommCenter` looks up the table using current baseband registered `MCC+MNC` (e.g. China Mobile `"46000"`, China Unicom `"46001"`, China Telecom `"46011"`) as the key.
- Once a matching `CFString` is found in the dictionary, **it is directly returned in place of the default carrier name**; since this logic executes at the `CommCenter` network registration layer, **live signal bars and automatic detachment hiding in Airplane Mode remain completely unaffected**.

### 4.3 `CarrierSettingsInterface` (`0x1b3dd4228`) & `/var/mobile/Library/Preferences/` Mapping Table
Disassembly of `CarrierSettingsInterface` (`0x1b3dd4228 .. 0x1b3dd430c`) and the `__DATA_CONST.__const` section (`0x1ebc2de68 .. 0x1ebc2ded8`, `0x1ebc33f28 .. 0x1ebc33f48`) revealed:
1. **SIM Slot & Preference Domain Mapping**:
   - At `0x1b3dd42c8` and `0x1b3dd42ec`, indexing the global table via `SimSlot` maps to the following plist domains under `/var/mobile/Library/Preferences/`:
     - `0x1ebc2de68`: `com.apple.carrier` / `com.apple.carrier_1` / `com.apple.carrier_2`
     - `0x1ebc2de80`: `com.apple.operator` / `com.apple.operator_1` / `com.apple.operator_2`
     - `0x1ebc2dea8`: `com.apple.carrier.merged` / `com.apple.carrier_1.merged` / `com.apple.carrier_2.merged`
     - `0x1ebc2dec0`: `com.apple.operator.merged` / `com.apple.operator_1.merged` / `com.apple.operator_2.merged`
   - In `CoreTelephony`'s `-[CTMessageCenter sendMMS:]` (`0x1a73d487c .. 0x1a73d48a0`), the system invokes `CFPreferencesCopyValue(key, @"com.apple.carrier_1", @"mobile", kCFPreferencesAnyHost)` directly via `_CFStringGetMobileUser()` (`@"mobile"`).
2. **`CommCenter` Dedicated Persisted Preference Domains (`0x1b3da4108 .. 0x1b3da485c`)**:
   - `DevicePersistentCopyValue` (`0x1b3da4394`) -> `CFSTR("com.apple.commcenter.device_specific_nobackup")` (`0x1f5ae5ad0`)
   - `AttachAPNDevicePersistentCopyValue` (`0x1b3da43c0`) -> `CFSTR("com.apple.commcenter.attach_apn")` (`0x1f5ae5c50`)
   - `CarrierBundleDevicePersistentCopyValue` (`0x1b3da43ec`) -> `CFSTR("com.apple.commcenter.carrier_bundle")` (`0x1f5ae5c70`)
   - `CountryBundleDevicePersistentCopyValue` (`0x1b3da4418`) -> `CFSTR("com.apple.commcenter.country_bundle")` (`0x1f5ae5c90`)
3. **`VerifyBundles` Verification Switch (`0x1a73856f0 .. 0x1a7385774`)**:
   - `CTSettingSetVerifyCarrierBundles` (`0x1a73856f0`) and `CTSettingCopyVerifyCarrierBundles` (`0x1a7385748`) dispatch `kSettingsModelPreferencesSetValue` requests via `_CTServerConnectionPreferencesSetValue` (`0x1a74b1350`), operating on key `CFSTR("VerifyBundles")` (`0x1f4a067f0`).

---

## 5. Next-Phase Experimental & Verification Roadmap

Because `/var/mobile/Library/Preferences/` is also owned by `mobile:mobile` (UID 501), residing fully within the reach of AirLift path traversal write primitives and `HomeDomain` backup restore, next-phase hardware/firmware validation proceeds under the following priorities:

1. **Route A (On-Device `/var/mobile/Library/Preferences/` Preference Layer Probing & Injection Verification)**:
   - **Step 1**: Execute `airlift_carrier_deploy.py --reset` to clear `StatusBarOverrides.archive`, restoring the baseline of live signal bars and automatic Airplane Mode detachment hiding.
   - **Step 2**: Across `com.apple.operator_1.merged.plist`, `com.apple.operator_1.plist`, and `com.apple.commcenter.carrier_bundle.plist` under `/var/mobile/Library/Preferences/`, test injecting `InterCarrierRoamingDisplayNames` (mapping the active SIM card's `MCC+MNC`), `StatusBarImages`, and `CarrierName`, verifying whether `cfprefsd` / `CommCenter` reloading dynamically updates `operatorName` without breaking `.bundle` digital signatures.
2. **Route B (Offline Extraction of iOS 27 `CommCenter` Executable to Decompile `NetworkNameFactory` & `CarrierSettings` Subclasses)**:
   - `__ZTV24CarrierSettingsInterface` (`0x1f5adf8c8`) and `__ZTV27NetworkNameFactoryInterface` (`0x1f5adf858`) in `libCommCenterBase.dylib` are pure virtual interfaces; concrete derived classes are compiled inside the iOS firmware main executable `/System/Library/Frameworks/CoreTelephony.framework/Support/CommCenter`. Extracting this binary from an iOS 27 IPSW will locate the exact implementation at vtable `+0x50`, confirming the read priority of signature-exempt cached keys with 100% certainty.

---

## 6. On-Device Verification Status & Boundary Corrections (2026-10-19 / iPhone 14 Pro / iOS 27.0.1 24A446)

Prior to translating this document's static findings onto physical hardware, three boundary measurements were conducted, correcting several initial premises:

1. **Preference domains do not pre-exist**: Under `/var/mobile/Library/Preferences/`, `com.apple.operator_1.plist`, `com.apple.operator_1.merged.plist`, `com.apple.carrier_1.plist`, `com.apple.carrier_1.merged.plist`, `com.apple.commcenter.carrier_bundle.plist`, and `com.apple.commcenter.device_specific_nobackup.plist` all returned `ENOENT` (via AirLift symlink stat, status=8). Identical domains under `/var/wireless/Library/Preferences/` and `/var/preferences/` likewise do not exist.
   → Consequently, the actual semantics of §5 Route A is **creating new CFPreferences domains**, rather than mutating existing merged caches.
2. **AFC Read Channel Invalidation**: On 24A446, the AFC daemon possesses only metadata privileges outside the media sandbox; `read` and directory `list` operations fail, with only `stat` able to traverse symlinks. AFC cannot read back preference plist contents; byte-level verification must utilize MobileBackup2 backups instead.
3. **Isolation Between Static Override & Dynamic Injection**: `StatusBarOverrides.archive` takes precedence over live cellular domains; one must first deploy a reset archive + userspace reboot to confirm the lock screen reverts to native `中国联通` (China Unicom) before attributing "lock screen text alterations" to CommCenter preference injection, avoiding false negatives.

Ready injection tools: `tools/commcenter_carrier_inject.py` (read-only probe `tools/device_path_probe.py`, visual verification `tools/device_ui.py`). Full experimental protocol in [`../04_research_handoffs/2026-10-19_commcenter-preference-injection.md`](../04_research_handoffs/2026-10-19_commcenter-preference-injection.md).

### 6.1 Hardware Results: Preference Layer Injection Negative

On iPhone 14 Pro / iOS 27.0.1 (24A446), China Unicom (46001):

- All 12 candidate domains (base / slot1 / slot2 × `operator` / `carrier` × standard / `.merged`) were created successfully (`status=8 → 10`);
- Payloads contained `InterCarrierRoamingDisplayNames`, `CarrierName`, and `ShowCarrierName`;
- In an unlocked device state, `cfprefsd` (both instances), `CommCenter`, and `SpringBoard` were cold-restarted via CoreDevice signal channels;
- The lock screen carrier name remained `中国联通` (China Unicom).

Therefore, §4.2's "preference table lookup" is **not a functional renaming entrypoint** on this build. Three candidate explanations (bundle source / roaming-only trigger / files ignored by cfprefsd) require separate verification in §6 next steps; the `CarrierSettingsInterface` implementation in the `CommCenter` main executable remains the primary target of Route B.

Added reusable primitive: CoreDevice `send-signal-to-process` can cold-restart any userspace daemon to distinguish "cached data" from "genuine ineffectiveness".

### 6.2 Backup Forensics: Real Data Model (Decisive)

A trusted filtered backup (`Manifest.db` with 17,511 entries) revealed:

- Device PLMN `46001` (`LastKnownServingMcc=460`, `Mnc=1`, `CarrierBundleName='46001'`);
- CommCenter's persisted state resides entirely in `WirelessDomain` (`/var/wireless/Library/Preferences/com.apple.commcenter.*`);
- Across the entire manifest, `com.apple.operator_1` / `com.apple.carrier_1` domains **do not exist**; `com.apple.carrier_1` in `com.apple.commcenter.plist` is simply the string `'46001'`;
- The carrier display name originates from the signed system bundle `/System/Library/Carrier Bundles/iPhone/46001/carrier.plist` (containing `signatures` and `.der.pri`).

**Conclusion**: The "`/var/mobile/Library/Preferences/` mapping" in §4.3 does not hold on current iOS 27.0.1—that directory is not the carrier data tier. The real data tier (`/var/wireless` and sealed bundles) is non-writable in non-jailbroken / mobile contexts; thus the upstream dynamic route described in this document **has no viable injection primitives**; static `StatusBarOverrides` remains the sole viable solution.

Subsequent steps if continuing: extract `carrier.plist` and `CommCenter` binary from IPSW to confirm read location and gating of `InterCarrierRoamingDisplayNames` (purely for research, does not alter the non-writable conclusion).
