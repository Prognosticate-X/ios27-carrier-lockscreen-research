# iOS 27 Dynamic Carrier Name (Real-Time Signal + Airplane Mode Synchronization) Reverse Engineering Status Report

> **Saved Date**: 2026-10-14  
> **Research Objective**: Resolve the two core pain points of the existing `StatusBarOverrides.archive` approach — namely, that the custom Carrier Name remains permanently fixed even after entering Airplane Mode, and the signal bars are permanently frozen at full strength (4 bars) rather than reflecting real-time baseband telemetry — thereby re-establishing an upstream dynamic reverse engineering direction.  
> **Analyzed Modules**: `UIKitCore` (`0x1c70d9000`), `SystemStatus.framework` (`0x2a4726000`), `CoreTelephony.framework` (`0x1a737b000`), `libCommCenterBase.dylib` (`0x1b3d3e000`), and all 4,088 images across the local in-memory `dyld_shared_cache`.  

---

## 1. Root-Cause Analysis of Two Major Pain Points in the Existing Solution

### 1. Why does the modified Carrier Name remain displayed after enabling Airplane Mode?
- **Architectural Root Cause**: `StatusBarOverrides.archive` injects into the highest-priority static override domain of `SystemStatus` (`STStatusBarOverridesStatusDomain`).
- **Merging Behavior**: When the archive contains `cellularEntry` (`STStatusBarDataCellularEntry`) with `enabled: True`, `status: 5`, and `string: "Custom Name"` set internally, `SystemStatusUI` disregards the disconnected state of the live cellular domain (`STTelephonyStatusDomain`) and forces the cellular entry to remain "enabled and connected". Consequently, after toggling Airplane Mode, the Lock Screen and Control Center remain obstinately pinned to the customized carrier name.

### 2. Why does the GUI tool show permanently full signal bars when "Default (Unchanged)" is selected?
- **Tooling Code-Level Bug (`tools/gui_server.py`)**:
  The frontend `<select id="primaryBars">` option value for "Default (Unchanged)" is `""` (received by the backend as `None`), but line 1123 of `tools/gui_server.py` had:
  ```python
  primary_bars=body.get("bars") if body.get("bars") is not None else 4
  ```
  When the user selected "Default (Unchanged)", the backend silently fell back to hardcoding it as `4` (full bars) and fixing `type: 10` (5G).
- **Data Structure-Level Constraint (`STStatusBarDataCellularEntry`)**:
  Inside `STStatusBarData`, carrier text (`string`), signal bar count (`displayValue`), radio type (`type`), and enabled state (`enabled`) are encapsulated within the same atomic `STStatusBarDataCellularEntry` object. It is impossible within `StatusBarOverrides.archive` to override solely the text while allowing the signal bar count to pass through live baseband data.

---

## 2. Dialectical Assessment and Disassembly Evidence Across Three Reverse Engineering Directions

| Reverse Engineering Direction | Core Analyzed Modules & Symbol Addresses | Dialectical Verdict | Assembly-Level Core Evidence & Conclusions |
| :--- | :--- | :--- | :--- |
| **Direction 3: `StatusBarOverrides` Field-Level Pass-Through** | `UIKitCore` (`0x1c70d9000`)<br>`dataByApplyingOverlay:` (`0x1c80148f4`)<br>`_applyUpdate:keys:` (`0x1c8014748`) | **Completely Refuted (Dead End)** | Assembly proves merge logic only iterates top-level `entryKeys`. As long as `cellularEntry != nil` in the override payload, `setValue:forKey:` (`0x1c8014a04`) is called to **wholly replace** the live object pointer. `initWithCoder:` (`0x1c80108ac`) decodes missing integer fields simply to `0`, with no field-level fallback pass-through. |
| **Direction 1: `SystemStatus` / `SpringBoard` Default Keys Override** | `SystemStatus` (`0x2a4726000`)<br>`STSystemStatusDefaults` | **Refuted for Primary Name / Badge Only** | `STSystemStatusDefaults` (inheriting from `BSAbstractDefaultDomain`) registers only 3 Bundle boolean toggle properties, with no carrier text override key. `CoreTelephony`'s `CTSimLabel` (`0x1a73a109c`) controls only dual-SIM badges (`[P]`/`[S]`), without modifying the primary carrier name. |
| **Direction 2: `CommCenter` / `CoreTelephony` Preferences & Mapping Layer** | `libCommCenterBase` (`0x1b3d3e000`)<br>`CoreTelephony` (`0x1a737b000`) | **Sole Viable Primary Direction (Viable Upstream)** | Pinpointed to the `InterCarrierRoamingDisplayNames` table-lookup substitution branch in `NetworkListOperator::getLocalizedCompositeName` (`0x1b3db050c`), along with the `com.apple.operator_1(.merged).plist` mapping mechanism under `/var/mobile/Library/Preferences/` (`0x1ebc2de68`). Modifications at the `CommCenter` layer **100% preserve live signal and Airplane Mode synchronization**. |

---

## 3. Core Assembly Reverse Engineering Details (Direction 2: `CommCenter` Carrier Name Resolution)

### 1. `NetworkListOperator::getLocalizedCompositeName` (`0x1b3db050c..0x1b3db09ec`)
Disassembly recovery reveals that when composing the carrier display name, `CommCenter` incorporates built-in logic to override names via a dictionary lookup indexed by `MCC+MNC` (Mobile Country Code + Mobile Network Code):
- **`0x1b3db0550..0x1b3db0590`**: Obtains the `CarrierSettingsInterface` service instance (`x23`) from the `Registry` hash table using RTTI symbol `__ZTI24CarrierSettingsInterface` (`0x1f5adf998`).
- **`0x1b3db0668..0x1b3db068c`**:
  - Loads key name `x3 = CFSTR("InterCarrierRoamingDisplayNames")` (`0x1f5ae6dd0`).
  - Sets `w2 = 5` (`MOV w2, #5`, representing `Operator` Bundle type), calling `CarrierSettingsInterface` vtable offset `+0x50` to read the override dictionary.
- **`0x1b3db06b8..0x1b3db0854`**:
  - Calls `MCCAndMNC::MCCAndMNC` (`0x1b3d5af0c`) and `MCCAndMNC::getStringValue()` (`0x1b3d5b318`) to generate the PLMN string of the currently registered network (e.g., China Mobile `"46000"`, China Unicom `"46001"`, China Telecom `"46011"`).
  - Calls `CFDictionaryGetValue` at `0x1b3db0810` for lookup, and validates return type at `0x1b3db0820..0x1b3db0830` via `CFStringGetTypeID()` (`0x1ba87f3f0`). **If matched, it directly returns this custom string as the carrier name (`0x1b3db0854`)!**

### 2. `CarrierSettingsInterface` (`0x1b3dd4228..0x1b3dd430c`) and `/var/mobile/Library/Preferences/` Mapping
- **SIM Slot Domain Mapping (`0x1b3dd42c8` & `0x1b3dd42ec`)**:
  Indexes the `CFPreferences` domain table in the `__DATA_CONST.__const` section (`0x1ebc33f28` / `0x1ebc33f48` and `0x1ebc2de68..0x1ebc2ded8`) according to `SimSlot` (primary `1` / secondary `2`):
  - **Primary SIM (Slot 1)**: `com.apple.carrier_1`, `com.apple.operator_1`, `com.apple.carrier_1.merged`, `com.apple.operator_1.merged`
  - **Secondary SIM (Slot 2)**: `com.apple.carrier_2`, `com.apple.operator_2`, `com.apple.carrier_2.merged`, `com.apple.operator_2.merged`
- **`CommCenter` Persistent Preference Domains (`0x1b3da4108..0x1b3da485c`)**:
  - `DevicePersistentCopyValue` (`0x1b3da4394`) -> `com.apple.commcenter.device_specific_nobackup`
  - `CarrierBundleDevicePersistentCopyValue` (`0x1b3da43ec`) -> `com.apple.commcenter.carrier_bundle`
  - `CountryBundleDevicePersistentCopyValue` (`0x1b3da4418`) -> `com.apple.commcenter.country_bundle`
- **`VerifyBundles` Verification Switch (`0x1a73856f0..0x1a7385774`)**:
  - `CTSettingSetVerifyCarrierBundles` / `CTSettingCopyVerifyCarrierBundles` read/write `VerifyBundles` (`0x1f4a067f0`) via `_CTServerConnectionPreferencesSetValue` (`0x1a74b1350`).

---

## 4. Next-Step Action Plan (Pending Execution)

1. **Route A (Safe Probing & Injection Experiment on Physical Device `/var/mobile/Library/Preferences/` Layer)**:
   - **Step 1 (Restore Live Signal and Airplane Mode Baseline)**: Run `python3 tools/airlift_carrier_deploy.py --reset` on test device and restart `SpringBoard` to clear `StatusBarOverrides.archive`.
   - **Step 2 (Upstream Preference Injection Verification)**: Since `/var/mobile/Library/Preferences/` is owned by `mobile:mobile` (UID 501), falling completely within the writable scope of AirLift and `HomeDomain` backup restore, test injecting `InterCarrierRoamingDisplayNames`, `StatusBarImages`, and `CarrierName` into `com.apple.operator_1.merged.plist` / `com.apple.operator_1.plist` / `com.apple.commcenter.carrier_bundle.plist` to verify whether changes take effect dynamically after `cfprefsd` / `CommCenter` reload without breaking `.bundle` signatures.
2. **Route B (Offline Decompilation of iOS 27 `CommCenter` Main Binary)**:
   - Extract `/System/Library/Frameworks/CoreTelephony.framework/Support/CommCenter` executable from iOS 27 IPSW; decompile concrete implementation subclasses of pure virtual interfaces `CarrierSettingsInterface` (`__ZTV24CarrierSettingsInterface` @ `0x1f5adf8c8`) and `NetworkNameFactoryInterface` (`__ZTV27NetworkNameFactoryInterface` @ `0x1f5adf858`) to confirm with 100% certainty the lookup order for unverified cache keys.

---

## 5. Physical Device Verification Progress on 2026-10-19 (iPhone 14 Pro / iOS 27.0.1 / 24A446)

> Complete handoff document (including reproducible commands and rollback procedure): [`../04_research_handoffs/2026-10-19_commcenter-preference-injection.md`](../04_research_handoffs/2026-10-19_commcenter-preference-injection.md)

### 1. Empirically Confirmed

1. **Test Device & Network**: iPhone 14 Pro (iPhone15,2), iOS 27.0.1 (24A446); current SIM is **China Unicom** (PLMN `46001`/`46006`/`46009`/`46010`).
2. **Verification Surface Established**: The iPhone 14 Pro Lock Screen directly renders the carrier name in the top-left corner, enabling visual verification via CoreDevice screenshots without unlocking.
3. **AFC Read Boundary**: Using AirLift symlinks, `/var/mobile/Library/` can be queried via `stat` (`status=8` does not exist, `status=10` exists but cannot be stat'd), but `read`/`list` fail unconditionally outside the media sandbox; therefore **no AFC channel currently exists to "read back CFPreferences plist contents" in the current build**.
4. **Preference Domains Non-Existent on Clean Device**: `com.apple.operator_1(.merged)`, `com.apple.carrier_1(.merged)`, `com.apple.commcenter.carrier_bundle`, `com.apple.commcenter.device_specific_nobackup` all returned `status=8`; domains of the same name under `/var/wireless/Library/Preferences` and `/var/preferences` were likewise absent.
5. **AirLift Write Channel Re-Verified**: Probe name `ZZTEST9` was successfully written to `StatusBarOverrides.archive` and displayed on the Lock Screen, proving that ATAirlock overwrite writing remains viable on this path in 24A446.
6. **Respring Alone Cannot Clear Static Overrides**: Deploying a `--reset` empty archive followed by respring still left the old override displayed on the Lock Screen. A userspace or full reboot is required for the system to re-read the archive (`systemstatusd` in-memory state).
7. **Operational Cost of Full Reboot**: Following `devicectl reboot --style full`, the device enters a USB Restricted state where neither `usbmux` nor CoreDevice can detect it until the passcode is entered on device; `--style userspace` does not interrupt USB connectivity.

### 2. Revisions to Initial Hypotheses

- The original research assumed that "`com.apple.operator_1.merged.plist` already exists and can be modified in-place". Empirical testing proved this file **does not exist** on a clean device; Route A actually involves **creating a new CFPreferences domain file**.
- Consequently, whether "cfprefsd would serve this newly created domain to CommCenter upon injection" and "whether CommCenter's `CarrierSettingsInterface` reads from the `mobile` user domain or `_wireless` user domain" became two questions that had to be answered by physical testing.
- The new tool `tools/commcenter_carrier_inject.py` was implemented following the "create new domain" paradigm: writes only `InterCarrierRoamingDisplayNames` (optionally `CarrierName`), payload capped at 512 KiB, restricted exclusively to the Preferences directory and 8 `com.apple.operator_*`/`carrier_*` domain names.

### 3. Two Rounds of Physical Injection and Final Verdict (2026-10-19 14:41–15:05)

**Round 1 (operator domain + userspace reboot)**: Wrote four `com.apple.operator_{1,2}{,.merged}.plist` (`46001/46006/46009/46010 → DYNTEST`) and `com.apple.carrier_1.plist`. Target domains shifted from `status=8` to `status=10`. Following userspace reboot, Lock Screen still displayed `China Unicom`. At the time, this was hypothesized to be a timing issue where "preferences are unreadable before first unlock".

**Round 2 (All candidate domains + full cold restart with device unlocked)**:

1. Covered base domains (`com.apple.operator` / `com.apple.carrier` standard and `.merged`) along with slot 1 domains, with payload containing `InterCarrierRoamingDisplayNames` + `CarrierName` + `ShowCarrierName` (165 bytes).
2. Sent SIGTERM to both `cfprefsd` instances, `CommCenter`, and `SpringBoard` via CoreDevice `send-signal-to-process`; all four processes were respawned cleanly by launchd.
3. Result: Lock Screen still displayed `China Unicom`; `DYNTEST2` did not appear.

**Verdict**: On iPhone 14 Pro / iOS 27.0.1 (24A446) + China Unicom (46001 home network), **CFPreferences domain injection (`InterCarrierRoamingDisplayNames` or `CarrierName`) does not alter the carrier display name**, even after complete cold restarts of cfprefsd, CommCenter, and SpringBoard.

### 4. Backup Forensics and Definitive Conclusion (15:16–15:20)

After unlocking the device and completing "Trust This Computer", filtered backup completed successfully (`Manifest.db` with 17,511 entries). The ground-truth data model:

1. **Network Parameters**: `LastKnownServingMcc = 460`, `LastKnownServingMnc = 1` (PLMN 46001), `CarrierBundleName = '46001'`.
2. **CommCenter State Location**: Resides entirely in **`WirelessDomain`** (`/var/wireless/Library/Preferences/`):
   `com.apple.commcenter.plist`, `.data`, `.lazuli`, `.travel`, `.country_bundle`, `com.apple.CommCenter.counts`, `.quickswitch`, `.callservices`.
3. **Absence of `operator`/`carrier` Preference Domains**: No `com.apple.operator_1` / `com.apple.carrier_1` files exist anywhere in the manifest; `com.apple.carrier_1` inside `com.apple.commcenter.plist` is merely the string `'46001'`.
4. **Carrier Display Name Origin**: Signed system bundle `/System/Library/Carrier Bundles/iPhone/46001/carrier.plist` (accompanied by `overrides_D73_D74_D27_D28.plist`, `signatures`, `.der.pri`), situated on the Sealed System Volume (SSV).
5. **The 12 HomeDomain domains we created do not appear in the backup manifest** (even though stat confirms their presence: exists=10, absent=8); whether backupd skips them due to ownership or system domain whitelisting, they are not the data source for CommCenter's carrier name.

**Definitive Conclusion**:

- Within the capability boundary of unprivileged, non-jailbroken write primitives, **there is no viable write path for dynamic carrier names (live signal + airplane mode synchronization)**: The true data resides in `/var/wireless` (`_wireless` ownership) and sealed, signed carrier bundles, neither of which is writable by mobile/AirLift. Even if `InterCarrierRoamingDisplayNames` exists within bundles, it cannot be injected without breaking signatures.
- The static `StatusBarOverrides.archive` remains the sole functional non-jailbroken solution, with its limitations ("frozen signal bars, persistent during airplane mode") remaining unchanged.
- Should any of the following primitives become available in the future, this route may be re-evaluated: (1) Root write access to `/var/wireless`; (2) A carrier bundle overlay capable of passing signature verification; (3) Runtime injection into `CommCenter` (jailbreak/tweak).
- Optional pure-research path remaining (no write capability): Extract `carrier.plist` and the `CommCenter` main executable from IPSW to confirm the exact read location and gating conditions of `InterCarrierRoamingDisplayNames`; this will not change the "non-writable" conclusion above.

---

## 6. Recommended Delivery Configuration: Partial Entry (2026-10-19 Final)

Following physical verification and SystemStatusUI disassembly, the optimal configuration under non-jailbroken conditions is **partial entry**:

```bash
python3 tools/airlift_carrier_deploy.py -c "Custom Name" --partial
```

Or via the GUI by checking "Preserve Live Signal Bars (Partial Override)".

Effects:

- Custom carrier name;
- Signal bars on Lock Screen and Control Center **fall back to real-time telemetry** (omits `displayValue`);
- Control Center **does not display radio type text** (omits `type`);
- Name remains persistent in Airplane Mode (rendering the name requires `enabled=true` and `status=5`, and the static archive lacks sentinels that mirror real-time state).

Therefore: Live signal bars have been solved with a purely static archive; Airplane Mode synchronization can only be achieved via runtime publication to `STStatusBarOverridesStatusDomain` (which requires the `com.apple.systemstatus.publisher` entitlement, a jailbreak / TrollStore-tier capability).
