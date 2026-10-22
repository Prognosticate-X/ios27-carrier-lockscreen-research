# iOS 27 Carrier Name Complete Data Flow & Reverse Engineering Analysis

## 1. Core Pipeline Overview (Data Flow Diagram)

Through static reverse engineering of the iOS 27 / macOS 27 dyld shared cache and runtime frameworks (`CoreTelephony`, `SystemStatus`, `SystemStatusServer`, `SpringBoard`), a strictly layered pipeline governing the generation and consumption of the Carrier Display String was established:

```text
               +---------------------------------------+
               |        1. Physical SIM / eSIM         |
               |      - EF_SPN (Service Provider Name) |
               |      - EF_PNN (PLMN Network Name)     |
               +-------------------+-------------------+
                                   |
                                   v
               +---------------------------------------+
               |         2. Baseband Firmware          |
               |      - Parses MCC / MNC / IMSI        |
               +-------------------+-------------------+
                                   |
                                   v (QMI / IPC)
               +---------------------------------------+
               |       3. CommCenter (Root Daemon)     |
               |  - Manages all cellular calls & state |
               |  - Loads Carrier Bundle (Strict Sig)  |
               |  - Resolves final Operator Name       |
               +-------------------+-------------------+
                                   |
                                   | Mach Message / XPC
                                   | (CTXPCGetOperatorNameRequest)
                                   v
               +---------------------------------------+
               |       4. CoreTelephony.framework      |
               |  - CTTelephonyNetworkInfo             |
               |  - CTCarrier (carrierName, MCC, MNC)  |
               |  - CTXPCGetOperatorNameResponse       |
               +-------------------+-------------------+
                                   |
                                   | XPC Notification
                                   v
               +---------------------------------------+
               |     5. SpringBoard (Status Publisher) |
               |  - SBTelephonyManager                 |
               |  - STTelephonyStatusDomainPublisher   |
               +-------------------+-------------------+
                                   |
                                   | updateDataWithBlock:
                                   v
               +---------------------------------------+
               |       6. SystemStatus.framework       |
               |  - STLocalStatusServer (Status Bus)   |
               |  - STTelephonyStatusDomainData        |
               +-------------------+-------------------+
                                   |
                                   | in-process / XPC dispatch
                                   v
               +---------------------------------------+
               |      7. SystemStatusUI.framework      |
               |  - STUIStatusBar                      |
               |  - _UIStatusBarCellularItem           |
               |  - _UIStatusBarStringView             |
               |  (Renders Carrier Text onto lock      |
               |   screen / status bar)                |
               +-------------------+-------------------+
```

---

## 2. Reverse Engineering Technical Details of Critical Nodes

### 2.1 CommCenter and Carrier Bundle Signature Barrier
- **Carrier Bundle Paths:**
  - System Built-in: `/System/Library/Carrier Bundles/iPhone/` (Located on Sealed System Volume, read-only)
  - User Updates: `/var/mobile/Library/Carrier Bundles/Overlay/` (Located on writable data volume)
- **Fatal Signature Validation:**
  The `CommCenter` daemon strictly mandates that all Carrier Bundles (including `Carrier.plist`) carry Apple official root certificate digital signatures.
  If `CarrierName` or `CFBundleDisplayName` in `Carrier.plist` is tampered with via backup restore or file injection, `CommCenter` will reject loading the bundle during boot self-check, resulting in immediate "No Service" or fallback to an empty default configuration.
  **Conclusion:** Without a live jailbreak injecting `CommCenterPatch`, modifying carrier names by tampering with Carrier Bundles is impossible.

### 2.2 CoreTelephony Data Structure Verification
At runtime, the core response class structures of CoreTelephony were successfully reflected:
- **`CTCarrier`**:
  - `@carrierName`
  - `- (NSString *)carrierName`
  - `- (NSString *)mobileCountryCode`
  - `- (NSString *)mobileNetworkCode`
- **`CTXPCGetOperatorNameRequest`**:
  - `- performRequestWithHandler:completionHandler:`
- **`CTXPCGetOperatorNameResponse`**:
  - `@operatorName`
  - `- (NSString *)operatorName`
  - `- (NSString *)ct_shortName`

### 2.3 SystemStatus Publisher-Consumer Architecture
iOS 27 completely decouples the status bar into a microservices architecture:
1. **Publisher:** SpringBoard's Telephony Manager listens to CoreTelephony broadcasts; upon obtaining `operatorName`, it constructs `STTelephonyStatusDomainData` and invokes `STStatusDomainPublisher.updateDataWithBlock:`.
2. **Server:** `STLocalStatusServer` receives updates, triggers `modifyDataTransformer:`, and maintains versioning and snapshots across domains.
3. **Consumer:** `SystemStatusUI.framework` subscribes to domain events, triggering property re-binding in `_UIStatusBar` components to render text onto the top of the lock screen.

---

## 3. Why Legacy StatusBar Overrides Fail

Prior to iOS 17:
SpringBoard directly read `HomeDomain/Library/SpringBoard/statusBarOverrides` (C structure `StatusBarOverrideData`, containing the `serviceString` field).

In iOS 27:
- The `Speakeasy` gating is forcefully enabled by default, causing SpringBoard to bypass `statusBarOverrides`.
- Only when `Speakeasy` is OFF does execution branch into the legacy pathway.
- However, because `FeatureFlags/Settings.plist` is blocked by both sandbox limits and the Security Recovery Wipe self-healing mechanism, ordinary tools cannot disable Speakeasy.
