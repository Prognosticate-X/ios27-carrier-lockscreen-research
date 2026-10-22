# iOS 27 Carrier Name 完整数据流与逆向分析

## 1. 核心链路总览 (Data Flow Diagram)

通过对 iOS 27 / macOS 27 系统共享缓存及运行时（CoreTelephony、SystemStatus、SystemStatusServer、SpringBoard）的静态逆向分析，Carrier Display String 的生成与消费存在严格分层的管道：

```text
               +---------------------------------------+
               |        1. 物理 SIM / eSIM 硬件        |
               |      - EF_SPN (Service Provider Name) |
               |      - EF_PNN (PLMN Network Name)     |
               +-------------------+-------------------+
                                   |
                                   v
               +---------------------------------------+
               |          2. 基带固件 (Baseband)       |
               |      - 解析 MCC / MNC / IMSI          |
               +-------------------+-------------------+
                                   |
                                   v (QMI / IPC)
               +---------------------------------------+
               |          3. CommCenter (根守护进程)   |
               |  - 负责所有蜂窝电话逻辑与网络注册     |
               |  - 载入 Carrier Bundle (签名强校验)   |
               |  - 解析最终 Operator Name             |
               +-------------------+-------------------+
                                   |
                                   | Mach Message / XPC
                                   | (CTXPCGetOperatorNameRequest)
                                   v
               +---------------------------------------+
               |          4. CoreTelephony.framework   |
               |  - CTTelephonyNetworkInfo             |
               |  - CTCarrier (carrierName, MCC, MNC)  |
               |  - CTXPCGetOperatorNameResponse       |
               +-------------------+-------------------+
                                   |
                                   | XPC Notification
                                   v
               +---------------------------------------+
               |       5. SpringBoard (状态栏发布端)   |
               |  - SBTelephonyManager                 |
               |  - STTelephonyStatusDomainPublisher   |
               +-------------------+-------------------+
                                   |
                                   | updateDataWithBlock:
                                   v
               +---------------------------------------+
               |       6. SystemStatus.framework       |
               |  - STLocalStatusServer (状态总线服务) |
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
               |  (最终将 Carrier Text 绘制到锁屏/顶栏)|
               +-------------------+-------------------+
```

---

## 2. 关键节点逆向技术细节

### 2.1 CommCenter 与 Carrier Bundle 的签名屏障
- **Carrier Bundle 路径：**
  - 系统内置：`/System/Library/Carrier Bundles/iPhone/`（位于 Sealed System Volume，只读）
  - 用户更新：`/var/mobile/Library/Carrier Bundles/Overlay/`（位于数据卷）
- **致命签名校验：**
  `CommCenter` 守护进程强制要求所有 Carrier Bundle（包含 `Carrier.plist`）携带 Apple 官方根证书数字签名。
  若通过备份恢复或文件注入篡改 `Carrier.plist` 中的 `CarrierName` 或 `CFBundleDisplayName`，`CommCenter` 会在启动自检时拒绝加载该 Bundle，导致手机直接无服务（No Service）或回退至默认空配置。
  **结论：** 在没有运行中越狱注入 `CommCenterPatch` 的情况下，无法通过篡改 Carrier Bundle 达成改名。

### 2.2 CoreTelephony 数据结构验证
在运行时成功反射出 CoreTelephony 的核心响应类结构：
- **`CTCarrier`**：
  - `@carrierName`
  - `- (NSString *)carrierName`
  - `- (NSString *)mobileCountryCode`
  - `- (NSString *)mobileNetworkCode`
- **`CTXPCGetOperatorNameRequest`**：
  - `- performRequestWithHandler:completionHandler:`
- **`CTXPCGetOperatorNameResponse`**：
  - `@operatorName`
  - `- (NSString *)operatorName`
  - `- (NSString *)ct_shortName`

### 2.3 SystemStatus 发布者-消费者架构
iOS 27 将状态栏彻底解耦为微服务架构：
1. **Publisher（发布端）：** SpringBoard 内的 Telephony Manager 监听 CoreTelephony 广播，获得 `operatorName` 后，构建 `STTelephonyStatusDomainData`，调用 `STStatusDomainPublisher.updateDataWithBlock:`。
2. **Server（总线服务）：** `STLocalStatusServer` 接收更新，触发 `modifyDataTransformer:`，维护各 Domain 的版本与快照。
3. **Consumer（消费渲染）：** `SystemStatusUI.framework` 订阅该 Domain，触发 `_UIStatusBar` 组件的属性重绑，将文本渲染在锁屏顶部。

---

## 3. 为什么传统 StatusBar 覆盖失效？

在 iOS 17 之前：
SpringBoard 会直接读取 `HomeDomain/Library/SpringBoard/statusBarOverrides`（C 结构体 `StatusBarOverrideData`，内含 `serviceString` 字段）。

在 iOS 27：
- `Speakeasy` 门控默认强开，SpringBoard 绕过 `statusBarOverrides`。
- 只有当 `Speakeasy` 为 OFF 时才会进入传统分支。
- 但由于 `FeatureFlags/Settings.plist` 被沙箱与安全自愈机制（Security Recovery Wipe）双重拦截，普通工具无法关闭 Speakeasy。
