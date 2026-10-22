# SystemStatusUI & Modern Status Bar Subsystem Reverse Engineering Analysis

## 1. Architectural Positioning

In iOS 26/27, Apple completely overhauled the status bar architecture operating atop SpringBoard:
- **Legacy Architecture (Classic):** Tightly coupled to internal `UIKit` `UIStatusBar` and `StatusBarServer`, where state was directly driven by local binary structures and `statusBarOverrides`.
- **Modern Architecture (Modern):** Based on a microservices bus Publish-Subscribe (Pub/Sub) model composed of `SystemStatus.framework` + `SystemStatusServer.framework` + `SystemStatusUI.framework`.

---

## 2. Core Frameworks & Division of Responsibilities

| Framework | Responsibilities & Key Classes |
|---|---|
| **SystemStatus.framework** | **Data Models & Clients**:<br>- `STStatusDomain` (Base class)<br>- `STStatusDomainPublisher` (Publish interface)<br>- `ST*StatusDomainData` (Immutable data payloads conforming to `NSSecureCoding`)<br>- `STMutable*StatusDomainData` (Mutable builder classes) |
| **SystemStatusServer.framework** | **Central Status Bus**:<br>- `STLocalStatusServer` (Local bus)<br>- `STStatusDomainXPCClientHandle` (Cross-process XPC handler)<br>- `STDataAccessStatusDomainDataProviderTransformer` (Data stream transformer) |
| **SystemStatusUI.framework** | **UI View Renderer**:<br>- Inherits/composes `_UIStatusBar` series components<br>- Observes `STStatusDomain` data mutations and updates respective StatusItem views (Carrier, Wi-Fi, Battery, etc.) |

---

## 3. Runtime Mechanism & Sequence

```text
SpringBoard / Daemon
       │
       ▼
STStatusDomainPublisher
  .updateDataWithBlock: -> [STMutableStatusDomainData setXxx:]
       │
       ▼ (IPC / In-Process)
STLocalStatusServer
  .publishData:forPublisherClient:domain:withChangeContext:completion:
       │
       ▼
DataTransformer Provider
  .modifyDataTransformer:forDomain:usingBlock:
       │
       ▼ (Diff & Notify)
SystemStatusUI / _UIStatusBar
  .itemDidUpdate: -> updates Label / Icon
```

### 3.1 Implications for Carrier Customization
1. **SystemStatusUI Maintains No Persisted Plists:**
   Unlike legacy architectures, the modern stack contains no `com.apple.SystemStatusUI.plist` or `carrierText` configuration keys.
2. **Purely Transient In-Memory State:**
   `STTelephonyStatusDomainData` represents transient in-memory state whose lifecycle is tied to real-time communication with `CommCenter`. Every time the device wakes from the lock screen or cellular network changes occur, the bus dispatches a fresh Domain snapshot to the UI.
3. **Injection Complexity:**
   Without disabling Speakeasy to fall back to reading `statusBarOverrides`, one would have to hook `CTCarrier` / `STStatusDomainPublisher` dynamically in memory or hijack XPC messages; purely static file overwriting cannot tamper with this dynamic bus.
