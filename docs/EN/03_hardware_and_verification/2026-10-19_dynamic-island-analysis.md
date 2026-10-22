# Technical Deep Dive and Implementation Guide: iPhone 14 Pro (Dynamic Island) and iOS 27 Carrier Name

> **Target Device**: iPhone 14 Pro (`iPhone15,2`, Apple A16 Bionic)  
> **Display Characteristics**: Dynamic Island (pill-and-hole cutout display), notchless  
> **Operating System**: iOS 27.0 (Build `24A434` / `24A435` / `24A437`)  
> **Test Environment**: CoreSimulator sandbox deep verification + physical device AirLift jailbreak-free persistence pipeline  

---

## 1. Dynamic Island Status Bar Typesetting and Carrier Name Display Mechanism

### 1.1 Screen Hardware Layout Constraints
The iPhone 14 Pro abandoned the traditional notch cutout in favor of a centered "pill + hole" Dynamic Island physical occlusion:
- **Screen Physical Resolution**: `1179 x 2556` pixels (@3x)
- **Total Status Bar Height**: `160 px` (53.3 pt)
- **Physical Occlusion Area**: The centered Dynamic Island occupies the top `x: 380 ~ 800` region, making it impossible to place conventional icons or text in the center of the status bar.

Consequently, SpringBoard splits the status bar into two physical "ears":
- **Leading Ear (Left Ear)**: Time (or carrier text upon Lock Screen wake-up or in specific modes), location indicator, audio recording pill.
- **Trailing Ear (Right Ear)**: Cellular signal (single-SIM 4 vertical bars / dual-SIM stacked dot matrix), Wi-Fi fan icon, battery level pill.

### 1.2 Actual Carrier Name Rendering Entry Points Across Scenarios
Through runtime analysis of `SystemStatusUI.framework` within the iPhone 14 Pro virtualized environment, the Carrier Name string (`STStatusBarDataCellularEntry.string`) is presented at the following hierarchy levels in iOS 27:
1. **Lock Screen Header**:
   - When in the lock screen state, the large primary clock is centered on the screen.
   - The status bar left ear does not need to duplicate the small digital time, so SpringBoard renders the primary/secondary carrier names (e.g., `China Mobile 5G` or `China Mobile | China Unicom`) in the upper-left corner as a marquee or static label.
2. **Control Center Header**:
   - When pulling down from the top-right corner to invoke Control Center, the system suspends the Dynamic Island top bar and displays the full primary and secondary carrier names on the top left of the expanded Control Center.
   - **Empirical Verification**: Dual-SIM customized carriers `[P] Testname` and `[S] Test for name` have been successfully rendered on iOS 27.0 (iPhone 14 Pro).
   ![iPhone 14 Pro iOS 27 Dual SIM Control Center](../../../assets/iphone14pro_controlcenter_testname.png)
3. **Settings -> Cellular**:
   - Reads system carrier configuration state.

---

## 2. Behavioral Differences in Single-SIM vs. Dual-SIM Cellular Data Structures (STStatusBarData)

SpringBoard dynamically determines the cellular network topology based on the contents of `STStatusBarData` in `StatusBarOverrides.archive`:

### 2.1 Single SIM Mode
- **Field Configuration**: Only provides `cellularEntry`, omitting `secondaryCellularEntry`.
- **Rendering Characteristics**:
  - The trailing ear cellular icon renders as the standard **4-bar full-height gradient vertical signal bars**.
  - Signal strength is governed by `displayValue` (0 ~ 4) — **this conclusion requires revision/re-verification based on physical device testing on 2026-10-19**: After deploying with `-b 3`, the lock screen right ear still showed 4 dots (full bars), suggesting that the lock screen rendering surface might not consume the archive's `displayValue`, but rather uses real-time telemetry data. Final conclusions pending controlled experiments comparing `-b 0/1` across lock screen and Control Center rendering surfaces.
  - Radio access technology (`type: 10` corresponding to 5G, `type: 9` corresponding to LTE) dynamically displays when Wi-Fi is disconnected or hidden.
- **Archive Size**: ~975 bytes.

### 2.2 Dual SIM Mode
- **Field Configuration**: Configures both `cellularEntry` (primary SIM) and `secondaryCellularEntry` (secondary SIM).
  - Allows specifying separate `badgeString` values (such as `"P"`, `"S"`, `"Primary"`, `"Secondary"`).
  - Allows specifying individual signal bar counts (e.g., primary 4 bars, secondary 3 bars) and network types.
- **Rendering Characteristics**:
  - The trailing ear cellular icon automatically transitions to Apple's native dual-SIM **stacked indicator**:
    - **Upper**: Primary SIM 4-bar mini vertical signal bars.
    - **Lower**: Secondary SIM 4 horizontally arranged solid/hollow dots.
- **Archive Size**: ~1090 bytes.

---

## 3. SpringBoard Archive Handling Mechanism and Lifecycle Reverse Engineering Conclusions

Through key methods in `SpringBoard.framework`:
- `-[SBSystemStatusStatusBarOverridesArchiver _queue_setupObservingAndReconcileInitialState]` (address `0x5b50d4`)
- `-[SBSystemStatusStatusBarOverridesArchiver _queue_persistUpdatedArchiveRecord:]` (address `0x5b52d8`)
- `-[SBSystemStatusStatusBarOverridesArchiver _queue_writeOutArchiveRecord:]` (address `0x5b53e4`)
- `-[SBSystemStatusStatusBarOverridesArchiver _queue_readStatusBarOverridesArchiveRecord]` (address `0x5b5688`)

we reach the following definitive conclusions:

### 3.1 Read & Publish
Upon SpringBoard initialization (Respring or reboot), `_queue_readStatusBarOverridesArchiveRecord` is invoked:
```objc
data = [NSData dataWithContentsOfURL:archiveFileURL options:0 error:&error];
record = [NSKeyedUnarchiver unarchivedObjectOfClass:[_SBSystemStatusStatusBarOverridesArchiveRecord class]
                                           fromData:data
                                              error:&error];
```
Once `STStatusBarData` is successfully deserialized, SpringBoard calls `_overridesPublisher updateDataWithBlock:` to push the override data into the `SystemStatus` publication domain, whereupon `SystemStatusUI` executes rendering.

### 3.2 Auto-Eviction on Empty
Explicit self-healing logic exists in `_queue_writeOutArchiveRecord:`:
```objc
if (record == nil || [record isEmpty]) {
    [[NSFileManager defaultManager] removeItemAtURL:archiveFileURL error:&error];
}
```
When the system state is reset (e.g. receiving a purge notification or writing an empty archive), SpringBoard proactively calls `removeItemAtURL:` on disk to completely delete `StatusBarOverrides.archive`, restoring the factory default carrier state.

---

## 4. AirLift Physical Device Jailbreak-Free Deployment Pipeline (`airlift_carrier_deploy.py`)

For verification on the upcoming iPhone 14 Pro physical test device, a dedicated deployment tool has been prepared and integrated into `tools/airlift_carrier_deploy.py` and `airlift/airlift_carrier_deploy.py`.

### 4.1 Deployment Sequence Diagram
```mermaid
sequenceDiagram
    autonumber
    participant Host as Mac Host (airlift_carrier_deploy.py)
    participant AFC as iOS AFC Service (var/mobile/Media)
    participant ATC as iOS AirTraffic Daemon (Books)
    participant SB as iOS SpringBoard (var/mobile/Library/SpringBoard)

    Note over Host: 1. Safety pre-flight checks (block primary device, verify 14 Pro)
    Host->>Host: 2. Construct StatusBarOverrides.archive (bplist)
    Host->>Host: 3. Construct StreamingZip (containing ../../../var/mobile/Library/SpringBoard symlink)
    Host->>AFC: 4. stage: Extract via com.apple.streaming_zip_conduit to Media temporary directory
    Host->>AFC: 5. Write Books/Sync/Books.plist asset manifest
    Host->>ATC: 6. Trigger AirTraffic sync (airtraffic_host)
    ATC->>SB: 7. Exploit directory traversal to move payload to SpringBoard/StatusBarOverrides.archive
    Host->>AFC: 8. finish-deploy: Verify target file existence, clean up Media symlink & temp tree, restore Books database
    Host->>SB: 9. devicectl device reboot --style userspace (trigger SpringBoard reload)
    SB-->>Host: 10. SpringBoard starts and reads archive; Dynamic Island status bar renders custom carrier in real time!
```

### 4.2 Physical Device Deployment Command Examples

#### Single-SIM Customization (China Mobile 5G Example)
```bash
python3 tools/airlift_carrier_deploy.py -c "中国移动 5G" -b 4 -t 5g
```

#### Dual-SIM Customization (Primary China Mobile + Secondary China Unicom)
```bash
python3 tools/airlift_carrier_deploy.py \
  -c "中国移动 5G" --badge "主卡" \
  -s "中国联通 5G" --secondary-badge "副卡"
```

#### One-Click Restore to System Default Carrier
```bash
python3 tools/airlift_carrier_deploy.py --reset
```

#### Local Validation & Packaging Mode (No Device Connection Required)
```bash
python3 tools/airlift_carrier_deploy.py -c "中国广电 5G" --dry-run
```

---

## 5. Safety Principles and Blocking Policies

1. **Absolute Primary Device Block**:
   - The host tool enforces a built-in `PRIMARY_PHONE_BLOCKLIST`.
   - Whether via auto-scanning or manual `--device` specification, any action involving the primary device triggers an exception and terminates execution immediately: zero contact, zero operations.
2. **Unprivileged Directory Safeguards**:
   - Operation targets are strictly confined to `/var/mobile/Library/SpringBoard` under `mobile:mobile` permissions; writing to root-owned `/var/preferences` is strictly avoided, thoroughly eliminating the risk of an iOS 27 Security State Recovery Wipe.
3. **Zero Contamination of Books Database**:
   - Before and after deployment, `snapshot-books` and `RestoreBooksState` strictly snapshot and restore the original Books state, leaving zero dirty residual data.
