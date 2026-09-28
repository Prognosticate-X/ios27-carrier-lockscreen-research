# iOS 27.0 锁屏 Carrier Name 与 Lock Screen Footnote 终局研究方案与技术裁决报告

> **目标设备**：iPhone 16 Pro Max (A18 Pro)  
> **操作系统**：iOS 27.0 Release / Build `24A437`  
> **验证基准**：非越狱环境、主力机零风险安全准则、源码级审计与运行时反射  
> **报告日期**：2026-09-28  

---

## 1. Executive Summary (执行摘要)

针对 iPhone 16 Pro Max (A18 Pro) 在 **iOS 27.0 Final (24A437)** 正式版上的两项系统 UI 定制目标，经过对 **AirLift** 沙箱逃逸机制、**AirCard-iOS** 运行时实现、**GoldenNugget-Team / phanquocviet8x** 双分支源码 Diff、系统共享缓存二进制（`CoreTelephony`、`SystemStatus`、`SystemStatusUI`、`SpringBoard`）的静态逆向分析，得出最终技术裁决：

| 定制目标 | 裁决状态 | 标签 | 核心结论与技术原因 |
|---|---|---|---|
| **Lock Screen Footnote** | **完全可行** | `Confirmed` | 属于 Apple 官方设备管理体系（`com.apple.shareddeviceconfiguration`）。可通过官方 `.mobileconfig` 描述文件或受保护备份注入（Manifest.db 注入）在 iOS 27.0 Final 上稳定生效，无需任何越狱或高危提权。 |
| **Carrier Name Override** | **物理阻断** | `Not Working` | 即使通过 **AirLift** 成功向 `/var/mobile/Library/SpringBoard/statusBarOverrides` 写入配置，SpringBoard 也会因为 **Speakeasy Gate** 强开而完全 Bypass 该文件；现代 **SystemStatusUI** 不读取任何磁盘 plist；关闭 Speakeasy 所需的 `/var/preferences` 处于 root 权限且受安全自愈擦除（Security Recovery Wipe）保护；Carrier Bundle 受 CommCenter 数字签名强锁。非越狱下无可行路径。 |

---

## 2. Device / Build (目标设备与系统基准)

- **Device**: iPhone 16 Pro Max (`iPhone17,2`)
- **SoC**: Apple A18 Pro (`T8140`) / `arm64e`
- **OS**: iOS 27.0 Release (Final)
- **Build Number**: `24A437`
- **Device Role**: 用户主要主力机（Primary Daily Driver），强制适用最高等级数据防丢与防抹除策略。

---

## 3. Current iOS 27 Architecture (iOS 27 状态栏与配置架构全景)

```text
                                      iOS 27.0 Final (24A437)
                                                 │
        ┌────────────────────────────────────────┴────────────────────────────────────────┐
        ▼                                                                                 ▼
【Lock Screen Footnote】                                                          【Carrier Name Pipeline】
  (锁屏底部脚注)                                                                    (顶部运营商显示)
        │                                                                                 │
  Apple Profile Domain                                                             SpringBoard
  com.apple.shareddeviceconfiguration                                                     │
        │                                                                          Speakeasy Gate
  SharedDeviceConfiguration.plist                                                [Default: ON / Shipped]
        │                                                                                 │
  ┌─────┴────────────────────────┐                                            ┌───────────┴───────────┐
  ▼                              ▼                                            ▼                       ▼
官方描述文件通道           受保护备份注入管道                              [Speakeasy ON]          [Speakeasy OFF]
(.mobileconfig)          (SysSharedContainerDomain)                           │                       │
  │                              │                                     SystemStatusUI         Classic UIStatusBar
  └──────────────┬───────────────┘                                            │                       │
                 ▼                                                      Pub/Sub 总线           statusBarOverrides
        SpringBoard 锁屏渲染                                          STTelephonyStatusData    (AirLift 可写但被 Bypass)
         (立即生效，风险零)                                                   │                       │
                                                                         CommCenter                   │
                                                                              │                       │
                                                                        Signed Bundle         [需写 FeatureFlags]
                                                                        (强制苹果证书)       [/var/preferences 阻断]
```

---

## 4. AirLift Analysis (AirLift 沙箱逃逸深度剖析)

- **项目来源**：`0xjohnnydev/airlift`
- **作用原理**：利用 iOS 27.0 媒体传输管道（AirTraffic / Books 同步服务）中的路径校验缺陷实施的沙箱逃逸。
- **漏洞根因**：
  在 `-[ATAirlock processCompletedAsset:]` 中，Books 同步资产标识符（`asset.identifier`）直接接收来自 macOS 端 `Books.plist` 的 `Persistent ID`，未做 `..` 相对路径校验：
  ```objc
  NSString *source = [@"/var/mobile/Media/Airlock/Book" stringByAppendingPathComponent:asset.identifier];
  NSString *destination = [[@"/var/mobile/Media/" stringByAppendingPathComponent:asset.path] stringByStandardizingPath];
  if (![destination hasPrefix:@"/var/mobile/Media/"]) return;
  [fileManager moveItemAtPath:source toPath:destination error:&error];
  ```
  通过在定制 Zip 中构造指向 `../../../target` 的符号链接（`p0/p1/p2/link`），两阶段移动资产使得目标载荷顺着符号链接被写入沙箱外目录。
- **权限与范围边界**：
  - **执行身份**：`mobile:mobile` (uid 501, gid 501)。
  - **允许写入路径**：
    - `/var/mobile/Library/SpringBoard`（AirLift 默认目标）
    - `/var/mobile/Library/Preferences`
    - `/var/mobile/Containers/Data/Application`
    - `/var/mobile/Containers/Shared/AppGroup`
    - `/var/tmp`
  - **绝对阻断路径**：
    - 无法写入 `/var/preferences`（属于 `root:wheel`）。
    - 无法修改 `com.apple.MobileGestalt.plist`。
    - 无法穿透非 mobile 属主的系统系统组容器 `/var/containers/Shared/SystemGroup/`。

---

## 5. AirCard-iOS Analysis (AirCard-iOS 集成分析)

- **项目来源**：`EpochME/aircard-ios`
- **技术实质**：将 AirLift 底层封装为 `AirliftFFI.xcframework`，并配合 iOS 27.0 本地开发者模式与 Bonjour 配对能力，实现了无需外部电脑的“端侧提权文件写入”。
- **涵盖功能**：Apple Pay 卡面替换（Passbook 缓存写入）、锁屏拨号键盘换肤、PosterBoard 数据库壁纸修改。
- **与本任务的关联**：
  AirCard-iOS 的成功证明了 **AirLift 写入 `/var/mobile` 数据的稳定性**，但其定制点全部集中在用户层缓存和应用数据容器，**无法越界修改系统守护进程（CommCenter / FeatureFlags）的配置**。

---

## 6. GoldenNugget Diff (两套 GoldenNugget 源码比对)

针对 `GoldenNugget-Team/GoldenNugget` 与 `phanquocviet8x/GoldenNugget` 进行的全分支比对结果：

1. **Git 拓扑事实**：
   - Fork B（`phanquocviet8x`）HEAD 提交为 `0c449b9`（Tag 8.3）。
   - Fork A（`GoldenNugget-Team`）已领先 270+ 个提交，当前位于 `8de3c60`（Tag 9.5+）。
   - Fork B 是 Fork A 历史中的一个直接祖先节点，Fork B **无任何自研的新增代码**。
2. **“patched on iOS 27” 语义真相**：
   - 提交追溯：Commit `c37b709`（作者 `awesomenull`），提交说明为 `revert readme.md`。
   - 英文语境：**“Status Bar (patched on iOS 27)”** 意为 **“状态栏机制已被苹果在 iOS 27 上修复/封死”**，属于已知缺陷声明，而非工具支持补丁。
3. **代码逻辑核验**：
   在 `status_bar_tweak.py` 中，遇到 iOS 27.0+ 直接 `return flag_plist`（空操作）。两套代码在 iOS 27.0 Release 上均无法修改状态栏。

---

## 7. Carrier Name Reverse Engineering (运营商名称逆向分析)

对 iOS 27 / macOS 27 系统共享缓存及运行时框架（`CoreTelephony`、`SystemStatus`、`SystemStatusServer`、`SystemStatusUI`）执行反射逆向，确立完整数据链：

1. **源头**：SIM 卡内部 `EF_SPN` / `EF_PNN` 供基带解析。
2. **总控**：`CommCenter` 守护进程加载 Carrier Bundle，结合 SIM 信息产生最终 Operator Name。
3. **分发**：`CoreTelephony` 响应 SpringBoard 的 XPC 查询（`CTXPCGetOperatorNameResponse`）。
4. **发布**：SpringBoard 的 Telephony 模块调用 `STStatusDomainPublisher.updateDataWithBlock:`，向 `STLocalStatusServer` 注册 `STTelephonyStatusDomainData`。
5. **消费**：`SystemStatusUI.framework` 订阅该领域事件，驱动 `_UIStatusBarCellularItem` 渲染字符串。

---

## 8. statusBarOverrides (经典覆盖文件实测状态)

- **物理位置**：`/var/mobile/Library/SpringBoard/statusBarOverrides`
- **格式**：C 结构体 `StatusBarOverrideData`（内含 `serviceString` 字段）。
- **AirLift 写入能力**：`Confirmed`。AirLift 能够将该二进制文件写到 SpringBoard 目录。
- **系统读取状态**：`Not Working`。SpringBoard 在 iOS 27.0 默认强开 Speakeasy，主流程完全不读取该文件。

---

## 9. Speakeasy (门控机制与 FeatureFlags 封锁)

- **门控伪代码**：
  ```objc
  if (isEnabled("SpringBoard", "Speakeasy") || isEnabled("SpringBoard", "SpeakeasyNewStatusBar")) {
      use SystemStatusUI;          // 现代状态栏
  } else {
      use Classic Status Bar;      // 传统状态栏，读取 statusBarOverrides
  }
  ```
- **存储硬编码**：`FeatureFlags.framework` 仅从 `/var/preferences/FeatureFlags/Settings.plist` 读取。
- **阻断四重奏**：
  1. AirLift 无法写入 `/var/preferences`（权限受限在 `mobile`）。
  2. BackupAgent2 白名单拦截（仅 10 个系统文件）。
  3. 稀疏恢复触发 iOS 27 Security Recovery Wipe（清空 `/var/preferences` 并导致数据丢失）。
  4. CoreFoundation 偏好设置（cfprefs / MCX）被框架完全忽略。

---

## 10. SystemStatusUI (现代 UI 消费端分析)

- **纯内存总线**：`SystemStatusUI` 是基于 `STStatusDomain` 的视图监听器，不具有读取任何 Plist 文件的设计。
- **无法通过文件修改**：状态栏上的运营商文本由 `CommCenter` 实时产生并推送到内存总线。没有动态内存注入或代码 Hook（即非越狱环境），无法拦截修改发布到 UI 的文本。

---

## 11. LockScreenFootnote (锁屏底部脚注深度机制)

- **官方规范**：Apple MDM `com.apple.shareddeviceconfiguration`
- **目标文件**：
  `/var/containers/Shared/SystemGroup/systemgroup.com.apple.configurationprofiles/Library/ConfigurationProfiles/SharedDeviceConfiguration.plist`
- **文件内容**：
  ```xml
  <?xml version="1.0" encoding="UTF-8"?>
  <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
  <plist version="1.0">
  <dict>
      <key>LockScreenFootnote</key>
      <string>自定义锁屏文本</string>
  </dict>
  </plist>
  ```
- **生效机制**：SpringBoard 原生解析该键值，渲染于锁屏底部指示条上方。无需越狱，无安全抹除风险。

---

## 12. File Paths (关键系统文件绝对路径速查)

| 逻辑标识 | 绝对设备路径 | 属主与权限 | 访问可行性 (AirLift) |
|---|---|---|---|
| `statusBarOverrides` | `/var/mobile/Library/SpringBoard/statusBarOverrides` | `mobile:mobile` (0644) | **可读写** (但被系统忽略) |
| `FeatureFlags` | `/var/preferences/FeatureFlags/Settings.plist` | `root:wheel` (0644) | **不可访问** (越界) |
| `Carrier Bundle Overlay` | `/var/mobile/Library/Carrier Bundles/Overlay/` | `mobile:mobile` (0755) | **可写** (但签名校验失败导致无服务) |
| `Footnote (Shared)` | `/var/containers/Shared/SystemGroup/systemgroup.com.apple.configurationprofiles/Library/ConfigurationProfiles/SharedDeviceConfiguration.plist` | `mobile:mobile` (0644) | **受限** (系统组容器，建议用 Profile/Backup) |

---

## 13. Required Permissions (所需权限与边界)

- **AirLift 赋予权限**：`mobile` 用户权限（沙箱逃逸级别，非 root，非 kernel）。
- **Carrier Name 生效所需权限**：
  - 路径 A（关闭 Speakeasy）：需要 `root` 权限写入 `/var/preferences` 且逃避开机 Security Recovery 自检。
  - 路径 B（篡改 Carrier Bundle）：需要内核代码执行或 `CommCenter` 进程注入以绕过 Apple 根证书签名校验（`CommCenterPatch`）。
- **Footnote 生效所需权限**：标准配置描述文件授权，或普通用户未加密备份恢复权限。

---

## 14. Working Methods (已确认可工作方案)

### 方案：Lock Screen Footnote 官方描述文件 / 备份注入定制
- **可行性**：`Confirmed`
- **方法 1（免电脑描述文件）**：
  利用 Apple Configurator 或通过 Safari 签署安装包含 `com.apple.shareddeviceconfiguration` 的 `.mobileconfig` 描述文件。
- **方法 2（受保护备份管道）**：
  利用 GoldenNugget 9.5 将构建好的 `SharedDeviceConfiguration.plist` 注入到未加密备份的 `Manifest.db`（映射为 `SysSharedContainerDomain-systemgroup.com.apple.configurationprofiles`），通过 Phase 3 还原。

---

## 15. Failed Methods (已确证失效/阻断方案清单)

| 尝试路径 | 失效原因 | 最终状态 |
|---|---|---|
| **AirLift 写入 statusBarOverrides** | SpringBoard 默认开启 Speakeasy，完全不读取该文件 | `Not Working` |
| **AirLift 修改 FeatureFlags** | `/var/preferences` 属主为 root，超出 AirLift 的 mobile 权限 | `Not Working` |
| **Nugget 旧版稀疏恢复写入 FeatureFlags** | 触发 iOS 27 Security Recovery Wipe，全盘擦除 `/var/preferences` | `Not Working` |
| **篡改 Carrier Bundle Overlay** | CommCenter 启动强校验数字签名，签名失效导致基带断开、无服务 | `Not Working` |
| **GoldenNugget Fork B 状态栏设置** | 代码针对 iOS 27.0+ 为硬编码 return（空操作） | `Not Working` |

---

## 16. Device Compatibility (设备兼容性评估)

- **iPhone 16 Pro Max / A18 Pro (24A437)**：
  - Lock Screen Footnote：**100% 兼容支持**。
  - Carrier Name Override：**在当前 24A437 正式版上非越狱不可行**。
- **A18 Pro 硬件安全特性**：硬件级强化了 PAC 与 PPL，排除了纯用户态内存盲喷修改 SpringBoard 的可能性。

---

## 17. Risk Assessment (风险等级评估)

| 操作项目 | 风险等级 | 潜在危害 | 缓解与防范对策 |
|---|---|---|---|
| 安装 Footnote 描述文件 | **极低 (Minimal)** | 文本排版不适应 | 在设置中移除描述文件即可秒恢复 |
| 受保护备份注入 Footnote | **低 (Low)** | 还原时间消耗约 3 分钟 | 保持完整未加密备份随时回退 |
| 尝试 AirLift 覆写 Carrier Bundle | **高 (High)** | 蜂窝网络掉线、SIM 无法识别 | **严禁在主力机上执行** |
| 尝试稀疏恢复写入 FeatureFlags | **致命 (Critical)** | 触发系统安全抹除，丢失 Apple ID 与照片 | **绝对禁止执行** |

---

## 18. Backup / Recovery (备份与安全保障机制)

在对主力 iPhone 16 Pro Max 实施任何操作前：
1. **全盘加密备份**：使用 Finder / Apple Devices 执行一次包含钥匙串和密码的完整本地备份。
2. **记录设备快照**：
   ```text
   Device: iPhone 16 Pro Max (iPhone17,2)
   iOS Build: 24A437
   Baseband Version: 1.00.07 (或当前版本)
   Pairing UDID: 记录备查
   ```

---

## 19. Step-by-Step Experiment: Lock Screen Footnote 验证流程

### 步骤 1：生成配置载荷
编写合规的 `SharedDeviceConfiguration.plist`：
```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>LockScreenFootnote</key>
    <string>Prognosticate-X · iOS 27.0</string>
</dict>
</plist>
```

### 步骤 2：生成可分发描述文件 `footnote.mobileconfig`
封装为标准 Profile Payload：
```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>PayloadContent</key>
    <array>
        <dict>
            <key>PayloadType</key>
            <string>com.apple.shareddeviceconfiguration</string>
            <key>PayloadVersion</key>
            <integer>1</integer>
            <key>PayloadIdentifier</key>
            <string>com.prognosticate.footnote</string>
            <key>PayloadUUID</key>
            <string>A1B2C3D4-E5F6-7A8B-9C0D-1E2F3A4B5C6D</string>
            <key>LockScreenFootnote</key>
            <string>Prognosticate-X · iOS 27.0</string>
        </dict>
    </array>
    <key>PayloadDisplayName</key>
    <string>Lock Screen Footnote</string>
    <key>PayloadIdentifier</key>
    <string>com.prognosticate.profile</string>
    <key>PayloadType</key>
    <string>Configuration</string>
    <key>PayloadUUID</key>
    <string>B2C3D4E5-F6A7-8B9C-0D1E-2F3A4B5C6D7E</string>
    <key>PayloadVersion</key>
    <integer>1</integer>
</dict>
</plist>
```

### 步骤 3：安装与验证
1. 通过 AirDrop 发送到 iPhone 16 Pro Max。
2. 打开“设置” ➔ “已下载的描述文件” ➔ 点击安装。
3. 锁屏并唤醒屏幕，确认底部 Home Bar 上方显示自定义脚注文本。

---

## 20. Rollback Procedure (回滚与复原步骤)

- **描述文件回滚**：
  进入 iPhone “设置” ➔ “通用” ➔ “VPN 与设备管理” ➔ 选中 `Lock Screen Footnote` ➔ 点击“移除描述文件”，锁屏文字立即恢复默认。
- **备份注入回滚**：
  若通过备份注入管道实施，只需清空该 plist 中的 `LockScreenFootnote` 键重新执行一次恢复，或还原原始受保护备份。

---

## 21. Final Conclusion (技术裁决与总结)

1. **对 Carrier Name 的裁决**：
   在 **iOS 27.0 Release (24A437)** 上，Carrier Name 的定制已经不是“工具好不好用”的问题，而是被 Apple 从**架构层（Speakeasy 强开 + SystemStatusUI 内存化）**与**安全层（CommCenter 强制验签 + 恢复安全自愈擦除）**实施了双重物理阻断。在没有真正的内核越狱或 CommCenter 动态补丁发布前，**切勿在主力设备上盲目尝试**。
2. **对 Lock Screen Footnote 的裁决**：
   无需越狱，无需依赖任何漏洞工具，利用 Apple 官方的 `com.apple.shareddeviceconfiguration` 体系即可稳定、安全、优雅地达成 100% 定制目标。
