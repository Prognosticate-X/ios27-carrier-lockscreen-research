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
| **iOS 27 交付通道** | **可用**（未加密保护备份注入或描述文件） | **实机验证通过 / 官方主线集成**（现代归档已被 GoldenNugget 主线采纳并在 v9.5.1/v9.5.2 发布，通过 `HomeDomain` 备份恢复管道实机端到端全量验证通过；独立 AirLift 通道受限于 ATAirlock rename 限制） |
| **主力机安全风险** | **极低**（标准官方配置描述文件，可秒级回滚） | **低**（标准备份恢复管道无越狱提权风险，或独立 AirLift 管道） |

---

## 2.1 状态栏覆写 Overlay 机制与 VPN 状态透传

```text
┌────────────────────────────────────────────────────────────────────────┐
│                   SpringBoard Overlay Processing                       │
│                                                                        │
│   Native System Status Items                StatusBarOverrides.archive │
│   (CommCenter, Baseband, VPN)               (_SBSystemStatus...Record) │
│               │                                         │              │
│               ▼                                         ▼              │
│   [Base STStatusBarData] ─────────────► [-[STStatusBarData             │
│   - cellularEntry (live baseband)        dataByApplyingOverlay:]]      │
│   - vpnEntry (live VPN connection)                      │              │
│               │                                         │              │
│               ├─────────────────────────────────────────┤              │
│               ▼                                         ▼              │
│   [cellularEntry: Pointer Replace]        [vpnEntry: Native Passthrough]
│   • 整个 cellularEntry 被覆盖              • overlay.vpnEntry == nil      │
│   • 显示自定义运营商文字                   • 跳过替换，100% 透传系统 VPN   │
│   • 静态属性无法解耦飞行模式               • 完美解决 GoldenNugget 图标丢失 │
└────────────────────────────────────────────────────────────────────────┘
```
- **原子替换特性**：`-[STStatusBarData dataByApplyingOverlay:]` (`0x20e4ac960`) 采用 Entry 对象级别覆盖。`cellularEntry` 存在即整体指针覆写，静态下无法实现飞行模式自动隐藏与真实信号共存。
- **VPN 状态项解耦修复**：
  - 早期工具（如 GoldenNugget）在归档中向 `suppressedBackgroundActivityIdentifiers` 写入了 VPN 活动标识或写入了残缺 `vpnEntry`，导致控制中心和状态栏的 VPN 徽标永久消失。
  - 修复方案：在 `_SBSystemStatusStatusBarOverridesArchiveRecord` 中将 `suppressedBackgroundActivityIdentifiers` 置为空集，并在 `STStatusBarData` 中彻底省略 `vpnEntry`。SpringBoard 在应用 Overlay 时检测到 `vpnEntry == nil` 自动执行 `cbz` 跳过，完整保留底层真实 VPN 守护进程发布的状态，使用户连接 VPN 时图标正常亮起。支持 `--vpn {auto,on,off}` 显式控制。详见 [`docs/handoffs/iOS27_Dynamic_Carrier_and_VPN_Resolution_2026-10-21.md`](handoffs/iOS27_Dynamic_Carrier_and_VPN_Resolution_2026-10-21.md)。

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
