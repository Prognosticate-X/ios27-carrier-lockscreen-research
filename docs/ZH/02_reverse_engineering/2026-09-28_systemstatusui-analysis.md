# SystemStatusUI 与现代状态栏体系逆向分析

## 1. 架构定位

在 iOS 26/27 中，Apple 彻底重构了运行于 SpringBoard 顶部的状态栏架构：
- **旧架构（Classic）：** 紧耦合于 `UIKit` 内部的 `UIStatusBar` 与 `StatusBarServer`，状态由本地二进制结构体与 `statusBarOverrides` 直接驱动。
- **新架构（Modern）：** 基于 `SystemStatus.framework` + `SystemStatusServer.framework` + `SystemStatusUI.framework` 的微服务总线发布-订阅（Pub/Sub）模式。

---

## 2. 核心类库与职责划分

| 框架 | 职责与关键类 |
|---|---|
| **SystemStatus.framework** | **数据模型与客户端**：<br>- `STStatusDomain` (基类)<br>- `STStatusDomainPublisher` (发布接口)<br>- `ST*StatusDomainData` (遵循 `NSSecureCoding` 的不可变数据载荷)<br>- `STMutable*StatusDomainData` (可变构建类) |
| **SystemStatusServer.framework** | **状态中枢总线**：<br>- `STLocalStatusServer` (本地总线)<br>- `STStatusDomainXPCClientHandle` (跨进程 XPC 处理)<br>- `STDataAccessStatusDomainDataProviderTransformer` (数据流转换器) |
| **SystemStatusUI.framework** | **UI 视图渲染器**：<br>- 继承/组合 `_UIStatusBar` 系列组件<br>- 监听 `STStatusDomain` 数据变化并更新各 StatusItem 视图 (Carrier, Wifi, Battery 等) |

---

## 3. 运行机制与序列

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

### 3.1 对 Carrier Customization 的启示
1. **SystemStatusUI 不维护任何持久化 Plist：**
   与旧版不同，新架构不存在所谓 `com.apple.SystemStatusUI.plist` 或 `carrierText` 配置键。
2. **纯内存瞬态状态：**
   `STTelephonyStatusDomainData` 属于内存中的瞬态数据，生命周期与 `CommCenter` 实时通信绑定。每次设备锁屏唤醒或运营商网络变更，总线都会向 UI 推送新的 Domain 快照。
3. **注入难度：**
   若无法关闭 Speakeasy 回退到读取 `statusBarOverrides`，则必须在内存层面动态 Hook `CTCarrier` / `STStatusDomainPublisher` 或劫持 XPC 消息；纯静态文件覆写无法篡改此动态总线。
