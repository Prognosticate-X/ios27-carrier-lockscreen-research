# iOS 27.0.1 Dynamic Carrier (CommCenter Preference Layer) Physical Device Experiment Handoff Document

Updated: 2026-10-19  
Target Device: iPhone 14 Pro (iPhone15,2) / iOS 27.0.1 / Build 24A446 / USB  
Host Tooling: Repository AirLift native helper + pymobiledevice3 11.36.0 (`.venv`, userspace tunnel, rootless)

> This document records the latest reproducible facts regarding "Route A: Physical Device `/var/mobile/Library/Preferences/` Preference Layer Injection".  
> The objective remains: Displaying a custom carrier name alongside **real baseband signal** and **Airplane Mode synchronization**, rather than the static pinning of `StatusBarOverrides.archive`.

---

## 1. Newly Added Tools in This Cycle

| Tool | Purpose | Status |
|---|---|---|
| `tools/device_path_probe.py` | Performs **read-only** reconnaissance via AirLift directory traversal symlink: `--stat` / `--list` / `--read`, with read-only directory whitelisting | Empirically verified on physical device |
| `tools/commcenter_carrier_inject.py` | Generates and writes `InterCarrierRoamingDisplayNames` carrier preference plists (strictly limited to the Preferences directory and 8 domain names) | Verified offline (dry-run/unit tests); physical device injection pending unlock |
| `tools/device_ui.py` | Opens Control Center, taps, and captures screenshots via CoreDevice HID for visual verification | Screenshotting verified on device; touch inputs pending unlock |
| `airlift/Sources/airtraffic_host.m` | Allows dispatching only 1 asset (`argc >= 4`), thereby moving only the symlink without writing any target file to achieve pure read-only reconnaissance | Empirically verified on physical device |

Tests: `cd tools && python3 -m unittest test_airlift_features` (all 17 passed, 6 of which provide new coverage).

---

## 2. Empirically Confirmed Conclusions on Physical Device

### 2.1 AFC Read Boundary (iOS 27.0.1 / 24A446)

- After moving the staging symlink to `/var/mobile/Media/airlift-link-*`, **stat can traverse through the symlink**:
  - `/var/mobile/Library/Preferences/.GlobalPreferences.plist` → Returns complete fields (20845 bytes).
  - `/var/mobile/Library/SpringBoard/StatusBarOverrides.archive` → `status=10` (exists, but stat is rejected).
  - Non-existent files (such as `com.apple.operator_1.plist`) → `status=8`.
- However, **`read` and directory `list` fail unconditionally on paths outside the media sandbox** (empirically equivalent to the AFC daemon having only metadata permissions outside media).
- Conclusion: AFC can no longer be used as a read channel for `/var/mobile/Library`; the claim in the README regarding "reading out and comparing byte-by-byte" is not reproducible on the current build, and the CLI's `Byte Verification: unavailable` is honest.

### 2.2 Existing Preference Domains Do Not Exist on a "Clean" Device

Running `--stat` on the following paths returned `status=8` (ENOENT) across the board:

- `com.apple.operator_1.plist` / `com.apple.operator_1.merged.plist`
- `com.apple.carrier_1.plist` / `com.apple.carrier_1.merged.plist`
- `com.apple.commcenter.carrier_bundle.plist`
- `com.apple.commcenter.device_specific_nobackup.plist`
- Domains of the same name under `/var/wireless/Library/Preferences/` and `/var/preferences/`

This implies: **Injection = creating new domain files**, rather than overwriting existing ones. It also indicates that these "merged" caches are not flushed to disk upon every cellular connection, requiring revision of the research document's assumption that "this plist already exists and can be modified in-place".

### 2.3 AirLift Writing Is Functional on 24A446, and `StatusBarOverrides` Genuinely Controls Lock Screen Text

- After deploying the custom name `ZZTEST9`, **the iPhone 14 Pro Lock Screen immediately displayed ZZTEST9 in the top-left corner** (screenshot `.artifacts/screens/probe_zztest9.png`).
- Implication: ATAirlock overwriting an existing `StatusBarOverrides.archive` succeeded at least once on this build; the Lock Screen is a verification surface that can be observed without unlocking the device.
- Failure path: After deploying `--reset` followed only by respring, the Lock Screen still displayed ZZTEST9. The cause may be that the reset write was rejected by ATAirlock's rename, or that `systemstatusd`/SpringBoard's in-memory cache was not cleared; **judgment must be made using a userspace or full reboot**, as respring alone is insufficient to confirm that reset has taken effect.

### 2.4 Full Reboot Puts Device Back into USB Restricted State

- Following `xcrun devicectl device reboot --style full`, the device remained `unavailable` for 4 minutes, and `usbmux list` was empty;
- Requires **entering passcode on device to unlock** before AFC/CoreDevice/RSD recover.
- Contrast: `--style userspace` reboot preserves pairing and USB data access, allowing the device to reconnect automatically (empirically verified in this round).
- Conclusion: Subsequent experiments should prioritize **userspace reboot**; full reboot should only be used when cold booting is strictly necessary, with manual unlocking planned.

### 2.5 Target Network

Lock screen screenshots show the current carrier as **China Unicom** (`中国联通`), corresponding to PLMNs:

```text
46001 (Primary), 46006, 46009, 46010
```

---

## 2.6 First Round Injection Empirical Test (14:41–14:45)

Following device unlock, the first full injection round was executed:

```bash
python3 tools/commcenter_carrier_inject.py --udid 00008120-000934CA3E60C01E \
  -c DYNTEST --plmn china_unicom --plmn 46006 --plmn 46009 --plmn 46010
# → 4 operator domains (slot1/2 standard + .merged) successfully written to disk
xcrun devicectl device reboot --device 00008120-000934CA3E60C01E --style userspace
```

Results and observations:

1. **Files Were Indeed Created**: Prior to injection, the 4 target domains were all `status=8` (ENOENT); after injection, they shifted to `status=10` (EPERM, existing but metadata query rejected); the subsequently written `com.apple.carrier_1.plist` behaved identically. As a control, known existing files in the Preferences directory such as `com.apple.Accessibility.plist`, `com.apple.mobiletimer.plist`, and `com.apple.Preferences.plist` also returned `status=10`, while only non-existent files returned 8.
2. **First Round Result Was Negative**: Following userspace reboot, the Lock Screen still displayed `China Unicom` (`DYNTEST` did not appear).
3. **Most Probable Cause — Data Protection Timing**: Following reboot, the device remained at the Lock Screen and **had not undergone first unlock**. iOS preference files belong to `NSFileProtectionCompleteUntilFirstUserAuthentication` (class C) by default, rendering them unreadable prior to "first unlock after current boot"; whereas `.GlobalPreferences.plist` belongs to class A, which is always readable (can still be stat'd at 20845 bytes while locked). CommCenter/cfprefsd could not read newly created domains at boot time, so this negative result **cannot** be used to dismiss the `InterCarrierRoamingDisplayNames` hypothesis.
4. **Another Possibility to Rule Out**: If ATAirlock creates files as root (0600), the mobile user's cfprefsd will never be able to read them. Performing a `stat` on target domains after unlock can distinguish this: class C + mobile ownership → readable as `st_size=126` after unlock; root ownership → remains EPERM after unlock.

Therefore, the next round of experiments must satisfy: **Device unlocked → Write → Trigger CommCenter reload while unlocked → Observe immediately**, rather than "write, reboot, and observe at lock screen".

## 2.7 Extended Domains + Forced Reload: Still Negative (15:00–15:02)

During the unlocked window, the experiment was pushed to maximum rigor:

1. **Domain Coverage Expanded to All Candidates**: Base domains (`com.apple.operator` / `com.apple.carrier` standard and `.merged`) + slot 1 domains, with payload containing `InterCarrierRoamingDisplayNames`, `CarrierName`, and `ShowCarrierName` (165 bytes).
2. **Forced Cold Restart of All Relevant Caches**: Sent SIGTERM via CoreDevice `send-signal-to-process` to both `cfprefsd` instances, `CommCenter`, and `SpringBoard`; all four processes were respawned cleanly by launchd (new PIDs 1321/1322/1323 + new SpringBoard).
3. **Result**: Captured screenshot after waiting 12s; Lock Screen still displayed `China Unicom`, and `DYNTEST2` did not appear.

**Conclusion**: On iPhone 14 Pro / iOS 27.0.1 (24A446) + China Unicom (46001 home network), injecting `InterCarrierRoamingDisplayNames` or `CarrierName` into `com.apple.operator`/`com.apple.carrier` preference domains **does not alter the carrier display name, even after cold restarts of cfprefsd, CommCenter, and SpringBoard**.

Explanations ranked by likelihood:

1. `CarrierSettingsInterface` Operator bundle data originates from **signed carrier bundles** (`Operator.plist`, etc.), rather than CFPreferences domains;
2. `InterCarrierRoamingDisplayNames` is queried exclusively during **inter-carrier roaming** scenarios, and does not match on the home network (46001);
3. File ownership or protection class created by ATAirlock is not accepted by cfprefsd (ruling this out requires a root perspective; file metadata in backup manifests is the only viable channel).

**Cleanup**: All 12 candidate domains (base/slot1/slot2 × operator/carrier × standard/.merged) were written back as **empty dictionaries**; device Lock Screen retained native `China Unicom`.

**New Reusable Capability**: The CoreDevice signaling channel can restart cfprefsd/CommCenter/SpringBoard without rebooting the whole device, useful for testing any cache/reload hypotheses:

```bash
.venv/bin/pymobiledevice3 developer core-device list-processes --userspace
.venv/bin/pymobiledevice3 developer core-device send-signal-to-process <pid> 15 --userspace
```

## 3. Key Experiments to Execute (Executable Once Device Is Unlocked)

Prerequisites: Device unlocked, tapped "Trust This Computer".

### Step 0 — Read-Side Reconnaissance (Optional but Recommended)

```bash
# Filtered backup: Retain only Preferences / Carrier Bundles / SpringBoard paths
.venv/bin/pymobiledevice3 backup2 backup .artifacts/backup \
  --udid 00008120-000934CA3E60C01E \
  --only-regex 'Library/Preferences' \
  --only-regex 'Library/Carrier Bundles' \
  --only-regex 'Library/SpringBoard'
```

Purpose: Confirm real on-disk structure of carrier bundles / preference domains; backup is currently the sole available HomeDomain read channel.

### Step 1 — Clear Static Overrides, Establish Native Baseline

```bash
python3 tools/airlift_carrier_deploy.py --device 00008120-000934CA3E60C01E \
  --reset --force-overwrite          # Deploy empty archive
xcrun devicectl device reboot --device 00008120-000934CA3E60C01E --style userspace
```

Expected: Lock Screen displays `China Unicom`, signal bars reflect real baseband value; archive `--stat` should return `status=8`.

### Step 2 — Inject CommCenter PLMN Mapping

```bash
python3 tools/commcenter_carrier_inject.py \
  -c "联通 Dynamic" \
  --plmn china_unicom --plmn 46006 --plmn 46009 --plmn 46010
```

Writes `com.apple.operator_1.plist` and `com.apple.operator_1.merged.plist` (along with slot 2 equivalent domains).
Each write verifies target length via staging symlink `stat`; explicit error raised upon failure.

### Step 3 — Reboot and Observe

```bash
xcrun devicectl device reboot --device 00008120-000934CA3E60C01E --style userspace
# Wait 20-30s:
python3 tools/device_ui.py screenshot .artifacts/screens/cc_after_inject.png
```

Judgment:

- Lock Screen displays `联通 Dynamic` → `InterCarrierRoamingDisplayNames` mechanism succeeds; proceed to Airplane Mode synchronization verification;
- Lock Screen still displays `China Unicom` → This domain/key is not on CommCenter's actual read path; record negative result and pivot to Route B.

### Step 4 — Airplane Mode & Live Signal (Upon Success)

```bash
python3 tools/device_ui.py open-cc        # Swipe down from top right
python3 tools/device_ui.py screenshot .artifacts/screens/cc.png
```

Control Center displays carrier name, live signal bars, and Airplane Mode button directly; fine-tune coordinates based on screenshots.

### Rollback

Preference domain files cannot be deleted via AFC; writing back `{}` (empty dictionary) prevents CommCenter from reading any keys, equivalent to disabling overrides:

```bash
python3 - <<'PY'
import plistlib
from tools.commcenter_carrier_inject import deploy_preference
payload = plistlib.dumps({}, fmt=plistlib.FMT_BINARY)
for domain in ("com.apple.operator_1.plist", "com.apple.operator_1.merged.plist"):
    print(domain, deploy_preference("00008120-000934CA3E60C01E", domain, payload)["ok"])
PY
```

---

## 3.5 Backup Forensics: Ground-Truth Data Model (15:16–15:20)

After unlocking the device and completing "Trust This Computer", filtered backup succeeded (`Manifest.db` with 17,511 entries, 24 MB). Key evidence:

1. **Device Network Parameters** (`WirelessDomain/Library/Preferences/com.apple.commcenter.plist`):
   - `LastKnownServingMcc = 460`, `LastKnownServingMnc = 1` → **PLMN 46001**
   - `CarrierBundleName = '46001'`
   - `LastKnownICCID = '89860124801663304064'`
2. **CommCenter's True Persistent Preferences Reside Entirely in `WirelessDomain`** (`/var/wireless/Library/Preferences/`):
   - `com.apple.commcenter.plist`, `com.apple.commcenter.data.plist`, `com.apple.commcenter.lazuli.plist`, `com.apple.commcenter.travel.plist`, `com.apple.commcenter.country_bundle.plist`, `com.apple.CommCenter.counts.plist`, `com.apple.CommCenter.quickswitch.plist`, `com.apple.commcenter.callservices.plist`
   - Across the entire manifest, **no** `com.apple.operator_1` / `com.apple.carrier_1` domain files exist.
3. **`com.apple.carrier_1` Is Merely a String**: In `com.apple.commcenter.plist`, this key's value is `'46001'` (currently active carrier bundle identifier), not a settings dictionary.
4. **Carrier Data Source Is a Signed Carrier Bundle**: `/System/Library/Carrier Bundles/iPhone/46001/` contains `carrier.plist`, `overrides_D73_D74_D27_D28.plist`, `signatures`, `overrides_*.der.pri` — situated on the Sealed System Volume, non-writable by mobile.
5. **The 12 HomeDomain Domains We Created Are Not in the Backup Manifest** (even though stat indicates presence: exists=10, missing=8). Whether backupd skips them due to ownership or system domain whitelisting remains unconfirmed, but either way, they are not the data source for CommCenter's carrier name.

### Conclusion (Definitive)

- On iOS 27.0.1, the carrier display name originates from **signed carrier bundles**; CommCenter's runtime state resides in **`/var/wireless`** (belonging to `_wireless`, which AirLift's mobile context cannot write).
- Therefore, **Route A (HomeDomain CFPreferences Injection) is unviable without a jailbreak or privileged write primitive**; even if `InterCarrierRoamingDisplayNames` exists within the bundle's `carrier.plist`, it cannot be injected without breaking signatures.
- Dynamic carrier names (live signal + airplane mode synchronization) have **no available write path** within this project's non-jailbroken capability boundary; the static `StatusBarOverrides.archive` remains the sole working solution, with its limitations ("frozen signal bars / persistent during airplane mode") remaining unchanged.

## 4. Current Status and Conclusions (Updated at 15:05)

- **Route A Verdict: Negative for Home Network Renaming**. CFPreferences domain injection (including base/slot domains, `InterCarrierRoamingDisplayNames` + `CarrierName` + `ShowCarrierName`, and forced cold restarts of cfprefsd/CommCenter/SpringBoard) did not alter the carrier name.
- **This alone does not declare the mechanism entirely dead**: Three possibilities remain: "bundle origin", "triggered only during roaming", or "file owner/protection class ignored"; the first two require decompiling the `CommCenter` binary (Route B), while the third requires backup manifest metadata (requiring device unlock + trust prompt password).
- **Device Current State**: No static overrides, native Lock Screen `China Unicom`; 12 experimental domains restored to empty dicts; USB connected.
- **Next Priorities**:
  1. If willing to perform "Trust This Computer" and maintain unlocked state, I can run a filtered backup, parse `Mode/OwnerID/GroupID/ProtectionClass` for the 12 domain files in `Manifest.db`, ruling out the "ownership/protection class" hypothesis once and for all;
  2. Otherwise pivot to Route B: Fetch dyld shared cache for 24A446 via `pymobiledevice3 developer fetch-symbols`, extract `libCommCenterBase.dylib` and re-verify invocation conditions of `getLocalizedCompositeName`; download IPSW to extract `CommCenter` main binary if necessary.

## 5. Original "Pending Execution" Checklist

- As of writing this document, device was in **USB Restricted state due to full reboot**, requiring passcode entry to restore connectivity.
- Preference injection script, payload, unit tests, and verification procedures were all ready; Steps 0–3 could be executed upon unlocking.
- If Step 3 proves negative, recommended next steps:
  1. Fetch DSC for 24A446 using `pymobiledevice3 developer fetch-symbols`, re-verifying invocation conditions of `getLocalizedCompositeName` in `libCommCenterBase` (whether only active during roaming);
  2. Since `CommCenter` binary is not inside DSC, download corresponding IPSW if needed to extract binary for offline reverse engineering;
  3. Continue investigating true preference domains owned by the `_wireless` user under `/var/wireless` and `/var/preferences`.

---

## 6. Safety Boundaries

- Preference injection tool strictly restricts writes to `/var/mobile/Library/Preferences` and 8 designated `com.apple.operator_*/carrier_*` domain names, with payload capped at 512 KiB.
- Writing utilizes the audited AirLift Books/AirTraffic channel; restores original `Books.plist` snapshot upon completing staging, leaving zero residual `airlift-*` directories.
- All device-side experiments are performed on the iPhone 14 Pro test device; primary device iPhone 16 Pro Max was not involved.

---

## 7. Next-Round Experiment Protocol (Revised Version, Device Must Remain Unlocked)

```bash
# 0) Unlock device and keep unlocked; verify readability of target domain first (protection class hypothesis)
python3 tools/device_path_probe.py --udid 00008120-000934CA3E60C01E \
  --stat /var/mobile/Library/Preferences/com.apple.operator_1.merged.plist
#    Readable → Returns st_size (126); Still EPERM → Suspect root ownership

# 1) Re-inject (including CarrierName variant as second hypothesis)
python3 tools/commcenter_carrier_inject.py --udid 00008120-000934CA3E60C01E \
  -c DYNTEST --plmn china_unicom --include-carrier-name

# 2) Without rebooting, attempt forcing CommCenter to reload:
#    a. Toggle Airplane Mode via HID (ON → OFF), forcing re-registration and carrier name resolution
python3 tools/device_ui.py open-cc
python3 tools/device_ui.py screenshot .artifacts/screens/cc_before_toggle.png
#    b. If ineffective, send signal to CommCenter via CoreDevice/DVT (permissions to be verified)
.venv/bin/pymobiledevice3 developer core-device list-processes --userspace | grep CommCenter

# 3) Capture screenshot of Control Center immediately after each action (carrier name + live signal bars)
python3 tools/device_ui.py screenshot .artifacts/screens/cc_after.png
```

Judgment sequence: Unlock readability → Airplane Mode reload → Process restart → Only then consider "domain/key invalid".
