# iOS 27 Carrier Display Domain Research Progress Snapshot (2026-10-19)

- Device: iPhone 14 Pro (iPhone15,2) / iOS 27.0.1 (24A446) / USB
- Current HEAD: `42b3c91` (Research Conclusions); previously `97475c4`, `09bc5e5`, `a7a50d9`
- Device Status: No static overrides, native Lock Screen `China Unicom`; 12 experimental domains restored to empty dicts; USB normal

---

## 1. Facts Confirmed in This Cycle

1. **CommCenter Data Model (Backup Forensics)**
   - Device PLMN `46001` (`LastKnownServingMcc=460`, `Mnc=1`, `CarrierBundleName='46001'`).
   - Persistent state of CommCenter resides entirely in `WirelessDomain` (`/var/wireless/Library/Preferences/com.apple.commcenter.*`).
   - Across the entire 17,511-line backup manifest, no `com.apple.operator_1` / `com.apple.carrier_1` preference domains exist; `com.apple.carrier_1` in `com.apple.commcenter.plist` is merely the string `'46001'`.
   - The data source for carrier display name is the signed system bundle `/System/Library/Carrier Bundles/iPhone/46001/carrier.plist`.
   - Conclusion: **The data source layer (CommCenter) is not writable in non-jailbroken / mobile context**; HomeDomain preference injection is ineffective.

2. **Display Domain (StatusBarOverrides) Channel**
   - AirLift can write to `/var/mobile/Library/SpringBoard/StatusBarOverrides.archive`; probe name `ZZTEST9` successfully displayed on Lock Screen.
   - Merely restarting SpringBoard cannot clear overrides that have already been adopted by the system; userspace or full reboot does.
   - Cold restarts of cfprefsd / CommCenter / SpringBoard can be achieved without rebooting the whole device via CoreDevice `send-signal-to-process`.

3. **Tooling and Documentation**
   - `tools/commcenter_carrier_inject.py`, `tools/device_path_probe.py`, `tools/device_ui.py`, `tools/commcenter_preference_builder.py`.
   - All 17 offline unit tests pass.
   - Handoff doc: `../04_research_handoffs/2026-10-19_commcenter-preference-injection.md`.

---

## 2. Key Correction: The Research Focus Has Always Been the "Display Domain"; Legacy Nugget Was Not Inherently Static

Previous documentation (as well as oral conclusions from the last round) framed "static" as the inherent nature of the Nugget approach. This phrasing is inaccurate. The correct timeline is:

| Version | Override Carrier/Container | Override Granularity | When Signal Bars Are Not Modified | Airplane Mode |
|---|---|---|---|---|
| iOS ≤ 16 (Legacy Nugget/Cowabunga) | `statusBarOverrides` (3944-byte `StatusBarOverrideData` C struct) | **Field-by-field override flags** (only sets flags for fields to override) | **Live signal bars** (unset fields continue fetching real-time data) | Carrier name vanishes alongside cellular entry, does not persist |
| iOS 17+/27 (Modern archive) | `StatusBarOverrides.archive` (`NSKeyedArchiver` → `STStatusBarData`) | **Entire `STStatusBarDataCellularEntry` object replacement** | If writing full entry, signal bars are frozen; omitted fields decode as 0/NO | `enabled/status` pinned, likely persists |

Therefore:

- **"Display domain override" per se is not the problem**; the problem is that iOS 27 replaced "field-by-field overrides" with "whole-entry overrides", discarding the legacy field-level fallback semantics.
- What we need to identify is: **Does an equivalent "partial override" entry point still exist within iOS 27's display domain** (at the archive layer, SpringBoard archiver layer, or SystemStatus merge layer)?

---

## 3. Controlled Experiment Results (BARS1, 2026-10-19 15:26–15:31)

After deploying `-c BARS1 -b 1 -t lte` (`displayValue=1`, `type=LTE`) followed by respring, observed across Lock Screen, Control Center, and Airplane Mode:

| Rendering Surface | Carrier Name | Signal Indicator |
|---|---|---|
| Lock Screen | `BARS1` | **4 dots (Full bars, real-time value)** — `displayValue=1` **did not take effect** |
| Control Center | `BARS1 LTE+` | **1 bar** — `displayValue=1` **took effect** |
| Airplane Mode: Lock Screen | `BARS1` + ✈ | Cellular indicator disappears, but **name remains persistent** |
| Airplane Mode: CC | ✈ `BARS1` | Signal bars disappear, but **name remains persistent** |

Conclusions:

1. **The Lock Screen cellular signal indicator does not consume the archive's `displayValue`**, but rather continues using live telemetry data; Control Center consumes the override entry (1 bar, `LTE+`).
   This refines the earlier assertion that "signal bars are pinned on all rendering surfaces": at least on iPhone 14 Pro / 27.0.1, **Lock Screen = live signal, CC = override value**.
2. **In Airplane Mode, carrier name remains persistent** (on both Lock Screen and CC). This is because the override entry pins `enabled/status` to "connected", and the name's visibility does not track real-time cellular status.
3. Thus the legacy Nugget behavior remembered by users was **only half-reproduced** on iOS 27:
   - ✅ Lock Screen real signal bars (legacy: unset fields pass through);
   - ❌ Airplane Mode non-persistence (legacy: name vanished with cellular entry; modern archive does not).

### 3.2 `5G` Radio Type Text Follows Cellular Data Switch (2026-10-19 15:40 Empirical Test)

The concurrent appearance of `China Unicom 5G` and Wi-Fi at the top of CC was **not caused by archive overrides**, but rather because the Cellular Data toggle was switched on (cellular icon in connectivity module was green):

- Cellular Data **ON**: `China Unicom 5G` + Wi-Fi icon (radio type text displays);
- Cellular Data **OFF**: `China Unicom` + Wi-Fi icon (radio type text disappears);
- Turn back on: `5G` returns.

Supporting evidence: The `StatusBarOverrides.archive` currently on disk is a **429-byte empty reset record** (`statusBarData` is empty), extracted via SpringBoard filtered backup and verified by decoding, with zero fields pinned.

Additionally, the **status bar (Lock Screen)** does not display radio type text when Wi-Fi is connected; **Control Center** displays it when Cellular Data is enabled. Attributing this phenomenon to residual overrides earlier was inaccurate.

## 3.0 Partial Entry Breakthrough: Custom Name + Real-Time Signal (15:50–15:53)

After resolving the "write-back race condition", the semantics of a **partial entry** (writing only a subset of fields) were successfully verified empirically:

| Variant | entry Fields | Lock Screen | Control Center |
|---|---|---|---|
| **V4** | `string` + `enabled=true` + `status=5`, **omits `displayValue`/`type`** | **V4 + real-time 4 dots** | **V4 + real-time 4 bars, no radio type text** |
| V5 | Only `string`/`crossfadeString` | Name disappears | Name disappears |
| V6 | `string` + `enabled=true`, omits `status` | Name disappears | Name disappears |
| V7 | `string` + `enabled=true` + `status=-1` (sentinel) | Name disappears | — |

Key discoveries:

1. **Missing `displayValue` falls back to real-time**: SpringBoard decodes missing fields as 0 and writes back a full record (1078B, `displayValue=0, type=0`), yet the UI still displays **real-time 4 bars**. That is, `displayValue=0` is treated as "no override / live", rather than 0 bars.
2. **Missing `type` suppresses radio type text**: CC no longer displays `5G/LTE`, nor does it fall back to real-time radio type (unlike bars).
3. **Name rendering strictly requires `enabled=true` and `status=5`**: Omitting `enabled` (V5) or `status` (V6) causes the name to vanish completely; `status=-1` also fails (no sentinel).
4. Thus the optimal combination achievable at this stage is: **Custom name + real-time signal bars (both Lock Screen and CC live) + CC without radio type text**; however, because `status=5` is static, **the name remains persistent in Airplane Mode**.

### 3.0.1 Newly Added Physical Device Primitives (Important)

1. **Archive Move-Out (Read + Delete)**: The source for AirTraffic `FileComplete` can be a relative path outside the media directory — `../../../Library/SpringBoard/StatusBarOverrides.archive` is resolved by ATAirlock to the actual archive path and moved into Media. Once moved, AFC can **read the archive contents and delete it** (target transitions to `status=8`).
2. **Single-Session Atomic Replacement**: Dispatches within the same `airtraffic_host` invocation: (1) move out old archive, (2) move in symlink, (3) move in new payload, narrowing the "target vanishes → new file written" window to ~1 second. Tool: `tools/airlift_archive_replace.py`.
3. **Piercing Live Domain Cache**: Merely replacing the disk archive is insufficient — the live override domain in `systemstatusd` overwrites the new disk record via `diskRecord recordByApplyingRecord:liveRecord` (live takes precedence). One must first `SIGSTOP` SpringBoard, `SIGKILL` `systemstatusd`, execute the replacement, and then `SIGKILL` SpringBoard to allow the new partial entry on disk to take effect.
4. **`recordByApplyingRecord:` Disassembly Confirmation** (Simulator SpringBoard, `0x5b5b50`): Implemented simply as `[statusBarData dataByApplyingOverlay:other.statusBarData]`, i.e., **entry-level atomic merge**; `isEmpty` (`0x5b5b08`) = `statusBarData.isEmpty` and suppressed collection is empty.

### 3.0.3b SystemStatusUI Disassembly: Exact Conditions for Name Display (16:18)

Key logic in `STUIStatusBarCellularItem` (SystemStatusUI, standalone 2.1MB binary):

- The name branch (`0x3024`) of `applyUpdate:toDisplayItem:` (`0x2c1c`):
  `if (displayItem.isEnabled && entry.string.length > 0 && !entry.isBootstrapCellular) { [serviceNameView setText:entry.string]; [serviceNameView setAlternateText:entry.crossfadeString]; } else { displayItem.enabled = NO; }`
- Signal predicate in `_signalViewShouldBeEnabledForEntry:forceShowingDisabledSignalBars:signalMode:` (`0x2aa8`):
  - `status == 0` → disabled;
  - `status == 1` → enabled only when force/showsDisabledSignalBars;
  - `status == 2` → enabled (signalMode 0);
  - `status == 3` → enabled (signalMode 1);
  - `status == 4` → disabled;
  - `status == 5` → enabled (signalMode 2, if signalMode pointer provided);
  - When `isBootstrapCellular`, enabled only if `status == 5`.

Empirical addendum: status=2 still **does not display the name** (S2), whereas status=5 displays it (V4). Thus `displayItem.isEnabled`, on which the name branch depends, is strictly more stringent upstream than the signal predicate — in practice, only "registered" (status=5) enables the name display item. status=0/1/2/-1 all hide the name.

### 3.0.3 `status` Value Matrix Conclusions (16:13)

| `status` | Name Display |
|---|---|
| **5** | ✅ Displayed (V4) |
| 0 (Missing) | ❌ Not displayed |
| 1 | ❌ Not displayed (S1 empirical) |
| -1 | ❌ Not displayed (V7 sentinel empirical) |

Therefore, **carrier string rendering is genuinely valid only when `status=5` (registered)** (status=2 also does not display, indicating the name display item's enabled state is determined by upstream registration state). `status` is a statically written field, lacking any sentinel or fallback mechanism that tracks live cellular state.

Conclusions:

- **Static archive can achieve**: Custom carrier name + Lock Screen / CC real-time signal bars (`displayValue` omitted) + CC without radio type text (`type` omitted).
- **Static archive cannot achieve**: Automatic hiding of name in Airplane Mode (must pin `status=5`, entry is perpetually deemed "connected").
- To achieve true Airplane Mode synchronization in the future, one must either publish `STStatusBarOverridesStatusDomain` dynamically at runtime (tweak/injection) or modify the data source layer (verified non-writable this cycle).

### 3.0.2 Archiver Merge/Write-Back Logic (Fully Reconstructed via objdump)

The actual flow of `-[SBSystemStatusStatusBarOverridesArchiver _queue_setupObservingAndReconcileInitialState]` (`0x5b50d4`, Simulator SpringBoard):

1. `live = [self._overridesDomain data]._sbSystemStatusStatusBarOverridesArchiveRecord` (**live override domain** record)
2. `disk = [self _queue_readStatusBarOverridesArchiveRecord]` (disk archive record)
3. When both exist: `merged = [disk recordByApplyingRecord:live]` → `[self _queue_writeOutArchiveRecord:merged]` → publish `merged`.
   - Inside `recordByApplyingRecord:` is `[self.statusBarData dataByApplyingOverlay:other.statusBarData]` (`0x5b5b50`), **entry-level atomic merge**, with **live overriding disk**.
4. Only live exists: `_queue_writeOutArchiveRecord:live` → publish.
5. Only disk exists: Publish disk directly, **without calling writeOut**.

`_queue_writeOutArchiveRecord:` (`0x5b53e4`):

- `record == nil || [record isEmpty]` → `[[NSFileManager defaultManager] removeItemAtURL:_archiveFileURL error:]` (self-deletion);
- Otherwise → `archivedDataWithRootObject:requiringSecureCoding:` followed by `writeToURL:options:`.

Hopper pseudocode supplementary confirmation (`_queue_readStatusBarOverridesArchiveRecord` / `initWithStatusBarData:`):

- When reading, first attempts `_SBSystemStatusStatusBarOverridesArchiveRecord`; upon failure, **falls back to legacy format** `STStatusBarData`; only returns nil if that also fails.
- `initWithStatusBarData:andSuppressedBackgroundActivityIdentifiers:` **directly returns nil** (and logs "is empty!") when `[record isEmpty]`. Therefore, an empty reset archive turns into nil during the read phase, equivalent to "no disk record", which naturally will not trigger writeOut/self-deletion later.
- `_queue_writeOutArchiveRecord:` deduplicates via `BSEqualObjects` first; only calls `removeItemAtURL:` if record is nil/empty.
- `_queue_persistUpdatedArchiveRecord:` likewise deduplicates first before writing to disk.

This explains all phenomena encountered in this cycle:

- **Why the empty reset archive lingered on disk**: At startup, only disk record existed (empty), taking the "only disk" branch, publishing directly without writeOut, thus never triggering self-deletion.
- **Why a new archive was overwritten back to old values**: The live domain in `systemstatusd` still held the old record; during merge, live took precedence, and subsequent writeOut wrote the old record back to disk.
- **Why "Freeze SpringBoard + Kill systemstatusd + Replace + Kill SpringBoard" is required**: Only by emptying the live domain and restarting SpringBoard can the new record (partial entry) on disk become the authoritative source.

### 3.0.2 Still Unresolved

- Airplane Mode synchronization: `status=5` must be statically written to render the name; the static archive lacks an entry point to "mirror live state".
- Requires further confirmation of `status` value semantics (1–4) and SystemStatusUI determination of `string` visibility to see if any combination mirrors live cellular state; if none exists, Airplane Mode synchronization depends exclusively on runtime dynamic publishing (tweak/injection), exceeding current non-jailbroken capabilities.

## 3.1 Why Lock Screen Retains Real-Time Signal (New Hypothesis)

The Lock Screen rendering surface decouples "signal strength" and "carrier string" at the view layer: signal reads live `STTelephonyStatusDomain`, while string reads `STStatusBarOverridesStatusDomain`. This does not contradict UIKitCore's "whole entry atomic replacement" conclusion — atomic replacement occurs **within the overrides domain**, whereas the Lock Screen cellular signal view may be bound to the live domain.

This means the pivotal next question is: **Can the string's visibility be bound to live cellular state**, thereby hiding automatically in Airplane Mode without affecting signal/network type?

## 4. Next-Step Experiments and Reverse Engineering Checklist

### A. Display Domain Partial Override (Priority)
1. Controlled experiment: `-b 0/1/3` to confirm `displayValue` effective surface → Completed: Lock Screen not affected (live), CC affected (override).
2. Partial entry experiment → Completed and productized: CLI `--partial`, standalone generator `--partial`, GUI "Preserve Live Signal Bars (Partial Override)" checkbox.
3. **Status Value Experiment**: Enumerate `enabled/status` combinations (true/5, true/0, false/0, omitted) to confirm whether string visibility tracks live cellular status, searching for an "auto-hide in Airplane Mode" combination.
4. **Sentinel Experiment**: Test special values such as `displayValue = -1 / 255 / 0xFFFF`, observing whether UI interprets them as "un-overridden".
5. **Archiver Merge Semantics**: Re-verify `-[_SBSystemStatusStatusBarOverridesArchiveRecord recordByApplyingRecord:]` and `-[SBSystemStatusStatusBarOverridesArchiver _queue_setupObservingAndReconcileInitialState]` to confirm merge precedence between disk record and live override record, and whether live fields can be retained.
6. **Class Structure Verification**: Enumerate runtime ivars on iOS 27 `STStatusBarDataCellularEntry` / `STStatusBarData` (via simulator `simctl spawn` utility or dsc extraction) to confirm existence of `flags/override` style fields or "unset" sentinels.

### B. Airplane Mode Synchronization
1. If Lock Screen / CC signal is live but carrier name persists in Airplane Mode, find a way to prevent `cellularEntry` from being published when cellular is off;
2. Observe impact of `enabled/status` value combinations (true/5, false/0, omitted, etc.) on Airplane Mode rendering;
3. Combine with `systemstatusd` publishing timing (whether it re-publishes override domain when cellular is disabled).

### C. If Both A & B Fail
- Maintain status quo conclusion: iOS 27 display domain override at `STStatusBarData` level is whole-object replacement, incapable of recovering legacy field-by-field semantics; data source layer is non-writable.
- Static solution stands as the sole deliverable, with empirical findings on "Lock Screen vs CC rendering surface differences" explicitly documented in README.

---

## 5. Reproduction Commands

```bash
# Compile AirLift native helper
cd airlift && make && cd ..

# Deploy specified signal bars + name (Lock Screen / CC comparison experiment)
python3 tools/airlift_carrier_deploy.py --device 00008120-000934CA3E60C01E \
  -c "BARS1" -b 1 -t lte

# Wake device + screenshot (Lock Screen)
python3 tools/device_ui.py screenshot .artifacts/screens/bars1_lock.png

# Open Control Center and screenshot
python3 tools/device_ui.py open-cc
python3 tools/device_ui.py screenshot .artifacts/screens/bars1_cc.png

# Restore native
python3 tools/airlift_carrier_deploy.py --device 00008120-000934CA3E60C01E --reset
xcrun devicectl device reboot --device 00008120-000934CA3E60C01E --style userspace
```

---

## 6. Delivery Status (2026-10-19 Wrap-Up)

- `--partial` implemented across `tools/airlift_carrier_deploy.py`, `airlift/airlift_carrier_deploy.py`, `tools/generate_statusbar_archive.py`;
- GUI added bilingual "Preserve Live Signal Bars (Partial Override)" checkbox (request field `partial`, passed through by backend to archive generator);
- All 18 unit tests pass (added partial archive field assertions);
- README / README_ZH / Research Status updated with recommended configurations, GUI usage, and Airplane Mode limitation notes.

### 3.0.4 Control Center "5G + Wi-Fi Side-by-Side" Is Native Behavior (17:06 Final Verification)

- First move-out read legacy 672B **S2**; subsequent GUI reset wrote it as **429B empty reset record**.
- Final clean state: Moved-out archive is 429B, **without any cellularEntry**; systemstatusd and SpringBoard killed and restarted (live domain purged, no archive).
- Under this state: Lock Screen displays `China Unicom` + Wi-Fi, **no 5G/LTE**; Control Center status bar still displays `China Unicom 5G` + Wi-Fi.
- Conclusion: iOS 27 Control Center status bar natively renders "Carrier + Live Radio Type + Wi-Fi" simultaneously; Lock Screen / Home Screen status bar displays only Carrier + Wi-Fi. Radio type follows the Cellular Data switch (disappears when cellular data is toggled off), rather than hiding automatically when Wi-Fi connects. Full entries pin `type`; `--partial` suppresses radio type text by omitting `type`.
- Cleanup workflow revision: Run move-out first (Books snapshot requires SpringBoard running), then kill systemstatusd/SpringBoard; if helper reports `afcStatus: -1`, execute `xcrun devicectl manage pair --device <udid>` first to re-pair.
