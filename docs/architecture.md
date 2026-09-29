# iOS 27 系统定制整体架构与安全边界全景图

## 1. 系统定制全景架构

```text
                                  iOS 27.0 Release
                                         │
        ┌────────────────────────────────┴────────────────────────────────┐
        ▼                                                                 ▼
【锁屏底部配置 (Footnote)】                                       【顶部状态栏 (Carrier Name)】
        │                                                                 │
  SharedDeviceConfiguration                                        SpringBoard 启动
        │                                                                 │
  Apple MDM / Profile Domain                                      SBSystemStatusStatusBarOverridesArchiver
        │                                                                 │
+-------+-------+                                                +--------+--------+
|               |                                                |                 |
Profile      Backup Injection                             现代归档 (.archive)  旧 C-Struct (废弃)
(.mobileconfig) (Manifest.db)                                    │                 │
│               │                                         SpringBoard 解析     完全被忽略
+-------┬-------+                                                │                 │
        │                                                STStatusPublisher   (Speakeasy 强开)
        ▼                                                        │
SpringBoard Lock Screen                                   SystemStatusUI
Footer Text Label                                                │
(官方通道，稳定可用)                                       (模拟器实测有效 / 物理机受限于
                                                          ATAirlock rename 覆盖问题)
```

---

## 2. 两个目标的落地条件矩阵

| 维度 | 目标 A：Lock Screen Footnote | 目标 B：Carrier Name Override |
|---|---|---|
| **技术机制** | `SharedDeviceConfiguration.plist` | 现代 `StatusBarOverrides.archive` (`_SBSystemStatusStatusBarOverridesArchiveRecord`) |
| **所属体系** | 官方设备管理 (MDM / ConfigurationProfiles) | SpringBoard 现代状态栏发布者架构 (`SystemStatus` / `SystemStatusUI`) |
| **存储位置** | `/var/containers/Shared/SystemGroup/.../` | `/var/mobile/Library/SpringBoard/StatusBarOverrides.archive` |
| **签名/完整性** | 无强制数字签名，受容器权限保护 | 无代码签名要求，由 `mobile:mobile` (0644) 属主拥有 |
| **iOS 27 交付通道** | **可用**（未加密保护备份注入或描述文件） | **受限/假设验证中**（模拟器可直接写入生效；物理机依赖 AirLift 沙箱逃逸，但受限于 ATAirlock 无法简单覆盖已存在文件的限制，真机端到端尚未完全实证） |
| **主力机安全风险** | **极低**（标准官方配置描述文件，可秒级回滚） | **中-高**（依赖未公开 AirTraffic 逃逸链路；若多次部署需妥善处理文件覆盖与回滚） |

---

## 3. iOS 27 备份与恢复安全边界变化

在 iOS 27.0 Release 正式版中，Apple 针对历史定制工具（如 Nugget / CowabungaLite）实施了四重封堵：

1. **Security State Recovery (安全状态恢复自愈)：**
   当系统在开机阶段检测到跨目录稀疏恢复（Sparse Restore）的残余文件位于 `/var/preferences` 等系统敏感目录时，自动触发重置逻辑，全盘抹除该目录，导致写入全部丢失。
2. **BackupAgent2 白名单收紧：**
   `SystemPreferencesDomain` 限制为硬编码的 10 个系统文件路径；`RootDomain` 严禁向 `preferences/*` 写入。
3. **AppDomain 稀疏恢复拦截：**
   iOS 27 beta 6 及后续正式版中，直接向 AppDomain 提交的稀疏恢复会被直接拒绝（MBErrorDomain/205）。
4. **有效幸存路径：**
   通过 GoldenNugget 9.5 实现的“三阶段受保护备份注入（Manifest.db In-Place Injection）”，向合法的受保护域（如 `HomeDomain`、`SysSharedContainerDomain-...`）注入标准文件是当前在不越狱前提下的唯一稳定通道。
