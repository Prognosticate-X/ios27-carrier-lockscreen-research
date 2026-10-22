# iOS 27 Speakeasy Gate 与 FeatureFlags 深度技术剖析

## 1. 架构总览：两套状态栏与 Speakeasy 门控

在 iOS 26/27 架构中，SpringBoard 内部共存两套完全不同的状态栏子系统：

```
                             SpringBoard
                                  │
                   ┌──────────────┴──────────────┐
                   ▼                             ▼
        Modern SystemStatusUI          Classic UIStatusBar
        - iOS 26/27 现代架构           - iOS 17 及以前旧架构
        - 无用户级可配置 plist         - 消费 statusBarOverrides
        - 仅受 FeatureFlags 控制       - 支持自定义运营商文本
                   ▲                             ▲
                   │                             │
                   └────── Speakeasy Gate ───────┘
```

### 1.1 门控逆向伪代码 (SpringBoard dyld_shared_cache)
```objc
if (isEnabled("SpringBoard", "Speakeasy")) {
    use SystemStatusUI;          // 现代状态栏
} else if (isEnabled("SpringBoard", "SpeakeasyNewStatusBar")) {
    use SystemStatusUI;          // 现代状态栏
} else {
    use Classic Status Bar;      // 传统状态栏，支持 statusBarOverrides
}
```

### 1.2 默认开关状态
- 域配置文件：`/System/Library/FeatureFlags/Domain/SpringBoard.plist`
- 关键 Feature Flag 状态：
  - `SpeakeasyAttributionManager`: `FeatureComplete` (Default: ON)
  - `SpeakeasyNewStatusBar`: `FeatureComplete` (Default: ON)
  - `SpeakeasyStatusBarWindowRotation`: `FeatureComplete` (Default: ON)
  - `Speakeasy` (基础 Flag): **未在 Domain plist 中声明** → 依照 iOS 机制直接回退默认启用（FeatureComplete = 默认开启）。

---

## 2. FeatureFlags.framework 存储与查询原理

### 2.1 唯一持久化存储路径
```text
/var/preferences/FeatureFlags/Settings.plist
```
- 整个 `FeatureFlags.framework` 编译二进制（dyld cache chunk .50）中，硬编码的配置存储路径**仅有且只有**上述文件。
- 不存在 `Global.plist`、不查询 CoreFoundation Preferences (`cfprefs`)、不读取 `ManagedPreferencesDomain`、亦无运行时回退路径。

### 2.2 交付渠道实测闭环（13 轮测试总结）

| 交付通道 | 测试方式 | 系统反应 | 最终结果 |
|---|---|---|---|
| **SystemPreferencesDomain** | 注入备份并在 Mobilebackup2 中恢复 | BackupAgent2 维护有硬编码白名单（仅 10 个系统路径如 SystemConfiguration/*） | **静默丢弃 (Dropped)** |
| **Sparse Restore (无域跨目录)** | 暂存到 `/private/var/backup/...` 并在重启时写入 `/var/preferences` | 重启后触发 iOS 27 Security State Recovery | **全盘清空 (Wiped)** |
| **RootDomain** | 注入备份并走 RootDomain 路径 | BackupAgent 白名单严格拒绝 `preferences/*` | **拦截拒绝 (Blocked)** |
| **ManagedPreferencesDomain (MCX)** | 注入 `mobile/com.apple.FeatureFlags.plist` | 文件成功写入设备，但 SpringBoard 启动时从不查询该域 | **完全不读取 (Ignored)** |
| **HomeDomain Preferences** | 注入 `com.apple.FeatureFlags.plist` | 文件成功写入设备，但 FeatureFlags.framework 从不查询 cfprefs | **完全不读取 (Ignored)** |

**结论：** 在没有越狱、没有 sandbox escape、没有内核写原语的情况下，通过用户空间备份/恢复修改 `Speakeasy` 开关在数学与逻辑上**完全不可行**。
