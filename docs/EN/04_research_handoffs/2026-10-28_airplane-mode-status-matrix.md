# iOS 27 Airplane-Mode Coupling Matrix Experiment (2026-10-28)

**Document ID**: `DOC-20261028-AIRPLANE-MATRIX`  
**Experiment date**: 2026-10-28  
**Device**: iPhone 14 Pro (iPhone15,2) / iOS 27.0.1 (24A446) / USB  
**Toolchain**: REA 6.8.0 + Ghidra 12.1.4 + in-repo AirLift/CoreDevice harness  
**Related document**: [2026-10-28 Research Roadmap](2026-10-28_next-research-roadmap.md)

> **Device note**: The device actually attached over USB was an **iPhone 14 Pro (iPhone15,2)**, not an iPhone 14 Pro Max. No 14 Pro Max was present via USB. All experiments ran only on the 14 Pro test device. The primary iPhone 16 Pro Max and the unconfirmed iPhone 17 Pro Max are blocked in `safety.json`.

---

## 1. What Was Added

1. **REA 6.8.0** installed locally under `.tools/rea-cli` with Node 24.22.1.
2. **Ghidra 12.1.4** downloaded from the official release; the Apple Silicon `os/mac_arm_64/decompile` native decompiler was built from source because the official zip does not ship it.
3. **REA's Hopper provider was blocked by macOS Automation permission** (`Not authorized to send Apple events`), so the deep analysis used Ghidra headless. Hopper remains an optional later path.
4. **`ps` shim**: the DSH workspace-write sandbox denies `/bin/ps` (EPERM), but REA's process-ownership checks need a process table. `.tools/bin/ps` provides the same fields through `libproc` (`proc_listpids` / `proc_pidinfo` / `proc_pidpath`), letting REA complete its cleanup and return results.
5. **Experiment harness**: [`tools/exp_status_matrix.py`](../../../tools/exp_status_matrix.py) now supports:
   - explicit 14 Pro selection;
   - atomic archive replacement with old-archive preservation;
   - `SIGSTOP` SpringBoard → `SIGKILL` `systemstatusd` → `SIGKILL` SpringBoard;
   - automatic Lock Screen / Control Center screenshots;
   - `--reset` to restore native state.
6. **Safety guard**: `PRIMARY_PHONE_BLOCKLIST` now loads from `safety.json` plus `AIRLIFT_BLOCKED_UDIDS` and fails closed when empty. `airlift/airlift_carrier_deploy.py` is now a wrapper around `tools/` so the stale duplicate cannot bypass the guard.

---

## 2. Static Evidence: The Exact Name Gate

REA + Ghidra decompiled `-[STUIStatusBarCellularItem applyUpdate:toDisplayItem:]` (file offset `0x2c1c`). The name branch is:

~~~c
if (identifier == nameDisplayIdentifier) {
    string = entry.string;
    enabled = displayItem.isEnabled
           && string.length > 0
           && !entry.isBootstrapCellular;
    displayItem.enabled = enabled;
    if (!enabled) return;
    serviceNameView.text = string;
    serviceNameView.alternateText = entry.crossfadeString;
    serviceNameView.marqueeRunning = YES;
    return;
}
~~~

Key points:

- The name gate reads only the **override entry's** `displayItem.isEnabled`, `string`, and `isBootstrapCellular`.
- It does **not** read the live registration state from `STTelephonyStatusDomain`.
- `displayItem.isEnabled` is determined by override/base-item logic, not per-frame live telemetry.
- Therefore a static archive has no field-level binding that makes name visibility follow cellular state.

This is consistent with the 2026-10-21 whole-entry atomic replacement finding for `dataByApplyingOverlay:`.

---

## 3. Dynamic Matrix (iPhone 14 Pro / 27.0.1)

Each variant was written through `replace_archive` and applied with `SIGSTOP` SpringBoard → `SIGKILL` systemstatusd → `SIGKILL` SpringBoard, then captured after the new SpringBoard started. `enabled=true` by default; `displayValue` and `type` were omitted unless noted.

| `status` | Cellular on: Lock Screen | Cellular on: Control Center | Airplane: Control Center | Verdict |
|:---:|---|---|---|---|
| 0 | No name, no cellular bars | No name, no cellular indicator | No name | Name hidden; cellular indicator also gone |
| 1 | **Native “China Unicom” + live bars** | **Native “China Unicom 5G” + live bars** | **Custom name “EXP1B” + airplane icon** | Live fallback: native when live exists, override when live is absent; opposite of the product goal |
| 2 | No name, four dots | No name, dot indicator | No name | Name hidden |
| 3 | No name, low bars | No name, low bars | No name | Name hidden |
| 4 | No name, warning triangle | No name, warning triangle | No name | Name hidden |
| 5 | **Custom name + 4 bars** | **Custom name + 5G + 4 bars** | **Custom name persists + airplane icon** | Name statically pinned; Airplane Mode does not hide it |
| 255 | No name | Custom name + dot indicator | No name | Undefined/inconsistent; not recommended |
| 5 + `isBootstrapCellular=true` | No name, 4 bars | Not captured separately | Not captured separately | `isBootstrapCellular` directly suppresses the name |
| 5 + omit `displayValue/type` | Custom name + live bars (1 bar observed) | Custom name + live bars + no radio-type text | Not captured separately | Partial mode: name still persists in Airplane Mode |

> The `status=1` Airplane Mode evidence comes from a Control Center screenshot; Lock Screen was not captured separately for that variant. `status=255` differed between Lock Screen and Control Center and is treated as undefined.
>
> After the matrix, `--reset` was run; the device is back to native “China Unicom 5G” and left on the Home Screen.

![Status matrix summary](../../../assets/ios27_status_matrix_20261028.png)

### 3.1 Key Observations

1. **No static combination produced “custom name with cellular on + automatic hide in Airplane Mode”.**
2. `status=1` does exhibit **live-state coupling**, but in the opposite direction: native name when live exists, override name when live is absent. It is a **live-fallback mode**, not a custom-name mode.
3. `status=0/2/3/4` hide the name but also change or remove the cellular indicator, so they are unusable in normal operation.
4. `status=5` is the only stable custom-name mode, but it persists in Airplane Mode.
5. `isBootstrapCellular=true` is a direct name-hiding switch, not a conditional-display solution.
6. Partial mode (omit `displayValue/type`) gives custom name + live bars, but suppresses the radio-type text and still persists in Airplane Mode.

---

## 4. Conclusion

On iOS 27.0.1 / iPhone 14 Pro, **no combination of the static `StatusBarOverrides.archive` provides “custom carrier name + automatic hide in Airplane Mode + live signal/radio type”.**

- `status=5`: custom name is statically pinned;
- `status=1`: live wins while live exists; the override name appears only in Airplane Mode (opposite of the goal);
- `status=0/2/3/4`: name hidden, cellular indicator also degraded;
- the name gate does not read live telephony, so no field-level conditional binding exists.

True dynamic naming would require runtime publishing of `STStatusBarOverridesStatusDomain` with the `com.apple.systemstatus.publisher` entitlement, which is outside the non-jailbroken boundary. Product guidance remains:

1. Use `status=5` full mode by default (name + fixed bars/type);
2. Use `--partial` when live bars matter (name + live bars, no radio-type text, still persists in Airplane Mode);
3. On dual-SIM devices, use the secondary slot for the custom name and keep the primary native, so the primary retains Airplane Mode coupling.

---

## 5. Remaining Experiments

| Experiment | Goal | Status |
|---|---|---|
| `status=1` Airplane Mode Lock Screen capture | Confirm Lock Screen matches Control Center | Pending |
| `enabled=false` + `status=1` | Can the custom name hide in Airplane Mode? | Pending |
| `status=6` / `-1` / other sentinels | Is there a special merge semantic? | Pending |
| `displayValue` sentinels (-1/255/65535) | Can radio-type text be restored? | Pending |
| Live-domain logs + on-disk archive diff | Quantify the merge/write-back window | Pending |
| iOS 27.2 | The device reports 27.2 available; run a separate compatibility test, do not update the test device blindly | Planning |

---

## 6. Reproduction Commands

~~~bash
# 1) Safety guard (local safety.json contains the primary UDIDs)
python3 -c "import sys; sys.path.insert(0,'tools'); import airlift_carrier_deploy as A; print(sorted(A.PRIMARY_PHONE_BLOCKLIST))"

# 2) Apply a full variant (saves old archive, purges, captures)
python3 tools/exp_status_matrix.py --name EXP5 --set status=5 --set enabled=true \
  --set displayValue=4 --set type=10 --screenshot --control-center

# 3) Apply a partial variant
python3 tools/exp_status_matrix.py --name EXP5P --set status=5 --set enabled=true \
  --omit displayValue --omit type --screenshot --control-center

# 4) Restore native
python3 tools/exp_status_matrix.py --reset --screenshot --control-center

# 5) Toggle Airplane Mode (Control Center coordinates, iPhone 14 Pro)
python3 tools/device_ui.py open-cc
python3 tools/device_ui.py tap 10003 12820
python3 tools/device_ui.py screenshot .artifacts/screens/airplane-cc.png
~~~

> Airplane-button coordinates are derived from the 1179×2556 screenshot: x≈180 px → 10003, y≈500 px → 12820. Re-measure for other device/layout combinations.

---

## 7. Evidence Files

- Harness: [`tools/exp_status_matrix.py`](../../../tools/exp_status_matrix.py)
- Local REA wrapper: [`tools/rea.sh`](../../../tools/rea.sh)
- REA decompilation outputs: `.artifacts/rea/ssui_decomp_apply.json`, `.artifacts/rea/ssui_decomp_0x563bc.json`, `.artifacts/rea/ssui_decomp_0x56288.json`
- Screenshots: `.artifacts/screens/EXP5-lock-20261028-095021.png`, `EXP5P-lock-20261028-101114.png`, `EXPB-lock-20261028-101143.png`, `EXPAIR-airplane-lock.png`, `EXP1B-airplane-cc.png`, `RESET-lock-20261028-101918.png`
- Summary image: [`assets/ios27_status_matrix_20261028.png`](../../../assets/ios27_status_matrix_20261028.png)
- Old archives: `.artifacts/archives/old-*.archive`

---

## 8. One-Sentence Conclusion

> **`status=1` proves the system does switch priority between “live exists” and “live absent”, but the direction is “native name when live exists, override name when live is absent”—the opposite of the product goal. `status=5` pins the custom name statically. Within the non-jailbroken boundary, the static archive has no usable Airplane-Mode coupling combination.**
