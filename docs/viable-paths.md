# iOS 27 定制可行路线与方案评估

## 1. 目标 A：Lock Screen Footnote（可行性极高）

### 1.1 技术机制
- **官方规范：** Apple Device Management `com.apple.shareddeviceconfiguration`
- **目标文件：**
  `/var/containers/Shared/SystemGroup/systemgroup.com.apple.configurationprofiles/Library/ConfigurationProfiles/SharedDeviceConfiguration.plist`
- **备份映射：**
  - Domain: `SysSharedContainerDomain-systemgroup.com.apple.configurationprofiles`
  - RelPath: `Library/ConfigurationProfiles/SharedDeviceConfiguration.plist`
- **Payload 格式：**
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

### 1.2 写入与交付途径
1. **途径 1（GoldenNugget 9.5 保护性备份注入管道）：**
   在未加密保护备份的 `Manifest.db` 中直接注入 `SysSharedContainerDomain-...` 记录，由 Phase 3 的受保护备份恢复回写。
2. **途径 2（官方描述文件 / 监督模式）：**
   通过 Configurator 或 MDM 描述文件安装（`SharedDeviceConfiguration`），这是 Apple 原生允许且不破坏系统完整性的安全方式。

---

## 2. 目标 B：Carrier Name（困难重重，多路线排查）

### 2.1 路线 1：Speakeasy 关闭回退 Classic 状态栏
- **现状：** **已被证伪/彻底封死。**
- **理由：** 必须写入 `/var/preferences/FeatureFlags/Settings.plist`，但 BackupAgent 白名单 + Security Recovery Wipe 彻底阻断了非越狱写入。

### 2.2 路线 2：Carrier Bundle / CommCenter 覆盖
- **现状：** 待固件逆向与数据流梳理。
- **机制：**
  运营商显示文本来自 SIM 卡 SPN (Service Provider Name) 或 `Carrier Bundles`（位于 `/System/Library/Carrier Bundles/` 或 `/var/mobile/Library/Carrier Bundles/`）。
- **可行性挑战：**
  - 系统 Carrier Bundle 在只读系统卷（SSV），无法修改。
  - 用户 Carrier Bundle 位于 `/var/mobile/Library/Carrier Bundles/Overlay`，需排查该目录是否允许通过常规备份恢复或是否有格式校验与数字签名。

### 2.3 路线 3：SystemStatusUI 现代状态栏直接配置
- **现状：** 待逆向分析。
- **机制：** 分析 `SystemStatusUI.framework` 内部是否存在未公开的 Debug / Internal Preference 键（如读取 `com.apple.springboard` 或 `com.apple.SystemStatusUI` 的特定 plist）。

### 2.4 路线 4：基于 `bad_query` 漏洞的写原语
- **现状：** 极高风险 / 需环境验证。
- **背景：** `bad_query` 在 iOS 27 Beta 1-4 上曾有沙箱逃逸写原语，但在 Release 正式版上 Apple 已修复 ContainerManager / HouseArrest 逻辑。
- **原则：** 主力设备坚决禁止直接运行未经 Release 验证的 PoC。

### 2.5 路线 5：现代 `StatusBarOverrides.archive` 归档管道
- **现状：** **已实测验证通过，已被主流开源套件（GoldenNugget）主线正式合并**。
- **机制：** SpringBoard 内置 `SBSystemStatusStatusBarOverridesArchiver`，会从 `/var/mobile/Library/SpringBoard/StatusBarOverrides.archive` 反序列化 `STStatusBarData` 并发布至 `SystemStatusUI`。
- **交付途径：**
  - **途径 A（GoldenNugget HomeDomain 备份恢复管道，推荐）：** 该归档文件归属 `HomeDomain`，可通过标准 `MobileBackup2` 备份恢复直接送入系统，无须越狱或漏洞逃逸，且彻底绕过了 AirTraffic 的 rename 覆盖限制。已被 GoldenNugget 主线合并并在真机测试通过。
  - **途径 B（AirLift 独立通道）：** 通过 AirTraffic Books 同步管道写入，受限于 ATAirlock rename 覆盖限制，需依赖首次安装或空归档自删复位机制。
  - **途径 C（CoreSimulator 模拟器）：** 宿主直写，开发调试验证。
