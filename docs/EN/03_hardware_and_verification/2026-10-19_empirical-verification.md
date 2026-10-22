# iOS 27 Carrier Name Physical/Virtual Machine Dynamic Verification & Architectural Breakthrough Report

**Test Environment**:
- **Host OS**: macOS Sequoia 15.x / Darwin 24.x (Apple Silicon)
- **Virtualization Target**: CoreSimulator iOS 27.0 Release (`Build 24A434`, arm64)
- **Devices Tested**:
  - `iPhone 16 Pro Max (Carrier Test)`: UDID `9E7BB711-41E9-442F-BCA4-53E2D6F61994` (Dynamic Island device)
  - `iPhone SE (3rd generation) Test`: UDID `DB9CA10D-B2A4-472E-81CA-7074513D8AB7` (Classic non-notched device)
- **Core Conclusion**: **Major Breakthrough** — The assertion by legacy tools (GoldenNugget 8.3/9.5) that "iOS 27 Speakeasy completely blocks Carrier Name" is a misjudgment. The genuine reason is that iOS 27 refactored the status bar override storage format, migrating from the traditional 3944-byte C struct to a modern `NSKeyedArchiver` serialized archive file `StatusBarOverrides.archive`. This file is owned by `mobile:mobile`, falling completely within AirLift's jailbreak-free writing scope!

---

## 1. Core Architectural Discovery: Legacy vs. Modern Override Formats

| Dimension | Legacy Mechanism (iOS 16 & Earlier) | Modern Mechanism (iOS 27.0 Actual Runtime) |
| :--- | :--- | :--- |
| **Persistence File** | `/var/mobile/Library/SpringBoard/statusBarOverrides` | `/var/mobile/Library/SpringBoard/StatusBarOverrides.archive` |
| **File Size** | Fixed 3944 bytes | Dynamic bplist (~900 - 1100 bytes) |
| **Underlying Format** | Raw C struct (`StatusBarOverrideData`) | `NSKeyedArchiver` serialized binary Property List |
| **Responsible Component** | `UIStatusBarServer` / `SpringBoard` | `SBSystemStatusStatusBarOverridesArchiver` inside `SpringBoard.framework` |
| **Service Pipeline** | Mach Port / C struct memory mapping | Pub/Sub publisher in `SystemStatus.framework` (`STStatusBarOverridesStatusDomainPublisher`) |
| **Historical Reason for Failure** | iOS 27 SpringBoard ignores legacy C structs and only recognizes `.archive` | Community projects continued writing C structs to the legacy path, causing changes to be completely ignored and misdiagnosed as "FeatureFlag blocking" |

---

## 2. In-Depth Reverse Engineering: `SpringBoard.framework` Archive Loading Logic

Through assembly disassembly of `SpringBoard.framework/SpringBoard` from the iOS 27.0 Simulator runtime libraries:

### 2.1 Archive File Reading (`_queue_readStatusBarOverridesArchiveRecord`)
Disassembled symbol: `-[SBSystemStatusStatusBarOverridesArchiver _queue_readStatusBarOverridesArchiveRecord]` (address `0x5b5688`):
1. Read path: `[self _archiveFileURL]` resolves to `~/Library/SpringBoard/StatusBarOverrides.archive`.
2. Deserialization: Prioritizes calling `[NSKeyedUnarchiver unarchivedObjectOfClass:[_SBSystemStatusStatusBarOverridesArchiveRecord class] fromData:error:]`.
3. Fallback fault tolerance: If top-level wrapper class is not defined, falls back to calling `[NSKeyedUnarchiver unarchivedObjectOfClass:[STStatusBarData class] fromData:error:]`.
4. Fallback conversion: If `STStatusBarData` is extracted, automatically constructs wrapper object: `[[_SBSystemStatusStatusBarOverridesArchiveRecord alloc] initWithStatusBarData:data andSuppressedBackgroundActivityIdentifiers:nil]`.

### 2.2 State Reconciliation and Publishing (`_queue_setupObservingAndReconcileInitialState`)
Disassembled symbol: `-[SBSystemStatusStatusBarOverridesArchiver _queue_setupObservingAndReconcileInitialState]` (address `0x5b50d4`):
1. Upon SpringBoard startup, observes system live status domain data (`STStatusBarOverridesStatusDomain`).
2. When override data exists on disk, invokes:
   ```objc
   reconciledRecord = [diskRecord recordByApplyingRecord:liveDomainRecord];
   ```
3. Publishes changes via internal publisher:
   ```objc
   [self._overridesPublisher updateDataWithBlock:^(STMutableStatusBarOverridesStatusDomainData *data) {
       // Update status bar cellular and carrier text
   }];
   ```

---

## 3. Dynamic Empirical Verification

### 3.1 Archive File Dynamic Injection Test (iPhone 16 Pro Max)
1. **Injection Test**:
   Constructed a standard `_SBSystemStatusStatusBarOverridesArchiveRecord` serialization payload via Python:
   - Target payload: `carrier_name = "CHINA_MOBILE_5G"`, `signal_bars = 4`, `type = 10 (5G)`.
   - Injection path: `<SimData>/Library/SpringBoard/StatusBarOverrides.archive`.
2. **SpringBoard Process Termination & Restart (SIGKILL)**:
   SpringBoard restarts and initializes, logging as follows:
   ```text
   SpringBoard: [com.apple.SpringBoard:StatusBarish] Style change requested outside of SBWindowSceneStatusBarSettingsAssertion
   SpringBoard: [com.apple.SpringBoard:StatusBarish] Saved the status bar overrides archive.
   ```
   **Result**: SpringBoard successfully read the archive file upon startup without any parsing exceptions, and persistently preserved the override state!

### 3.2 Visual UI Rendering Verification (iPhone SE 3rd Gen)
Because iPhone 16 Pro Max features the Dynamic Island, the top-left status bar area on the home screen is reserved exclusively for the time display, and carrier name is typically displayed upon pulling down Control Center or under specific lockscreen trigger states.

To obtain the most direct visual status bar text rendering evidence, the classic `iPhone SE (3rd Gen)` was launched in the iOS 27 simulator environment and loaded with the status overrides:
- **Visual Result**: The top-left corner of the status bar rendered **`CHINA MOBILE 5G`** completely, clearly, and flawlessly, immediately followed by the Wi-Fi icon and centered time!
- **Screenshot Evidence**: Saved at `assets/iphone_se_carrier_screenshot.png`.

---

## 4. Implementation Roadmap (AirLift Delivery)

### 4.1 Perfect Permissions and Path Alignment
- Real device target path: `/var/mobile/Library/SpringBoard/StatusBarOverrides.archive`
- Ownership & Permissions: `mobile:mobile` (0644)
- **AirLift Out-of-Bounds Capability**: AirTraffic Books unarchiving directory traversal escape operates with top-level permissions of `mobile:mobile`, and its default landing area is precisely `/var/mobile/Library/SpringBoard`!
- **Completely Bypasses `/var/preferences` Restrictions**: No longer requires writing to `FeatureFlags/Settings.plist` owned by `root:wheel`, nor does it require tampering with `CommCenter` certificate signatures!

### 4.2 Automated Payload Generation Script
Cross-platform payload generation tool developed: `tools/generate_statusbar_archive.py`:
```bash
python3 tools/generate_statusbar_archive.py "中国广电 5G" StatusBarOverrides.archive
```
The generated `.archive` file can be directly dispatched via the AirLift transport channel.

---

## 5. Timeline of Override Granularity (Important Addendum: 2026-10-19)

Earlier sections of this document discuss "status bar overrides" as a single entity, but override granularity underwent a pivotal change between iOS versions that must be distinguished:

| Version | Override Carrier/Container | Override Granularity | Behavior of Uncovered Fields |
|---|---|---|---|
| iOS ≤ 16 | `statusBarOverrides` (3944-byte `StatusBarOverrideData` C struct) | **Field-by-field override flags** | Continues using live baseband data (real signal bars, airplane mode synchronization) |
| iOS 17+ / 27 | `StatusBarOverrides.archive` (`NSKeyedArchiver` → `STStatusBarData`) | **Entire `STStatusBarDataCellularEntry` object replacement** | Missing fields decode as 0/NO, no field-level fallback |

Therefore:

- The assertion that "the Nugget solution is static" is **only true for the modern archive on iOS 27**; legacy Nugget, when not choosing to modify signal bars, could indeed preserve real signal and airplane mode behavior (consistent with community empirical testing).
- The static nature of the modern archive stems from the object-level semantics of `STStatusBarData`, rather than the concept of "display domain override" itself.
- Current open question: Does iOS 27 still have a partial override entry point (archive sentinel values, `recordByApplyingRecord:` merging, or different rendering surfaces between lockscreen/CC)? See `../04_research_handoffs/2026-10-19_research-progress-snapshot.md`.
