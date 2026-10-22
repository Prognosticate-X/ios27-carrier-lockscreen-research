# iOS 27 动态运营商名称（真实信号 + 飞行模式联动）逆向研究状态报告

> **保存时间**：2026-10-14  
> **研究目标**：解决现有 `StatusBarOverrides.archive` 方案在开启飞行模式后修改的 Carrier Name 仍“写死”常驻、以及信号格数永久固定为满格（4 格）而非真实基带信号的两大核心问题，重新确立上游动态逆向方向。  
> **已分析模块**：`UIKitCore` (`0x1c70d9000`)、`SystemStatus.framework` (`0x2a4726000`)、`CoreTelephony.framework` (`0x1a737b000`)、`libCommCenterBase.dylib` (`0x1b3d3e000`) 及本机内存 `dyld_shared_cache` 全量 4,088 个镜像。

---

## 一、 现有方案两大痛点的根因定位

### 1. 为什么开启飞行模式后，修改后的 Carrier Name 依然常驻显示？
- **机制根因**：`StatusBarOverrides.archive` 注入的是 `SystemStatus` 的最高优先级静态覆盖域（`STStatusBarOverridesStatusDomain`）。
- **合并行为**：当归档中包含 `cellularEntry`（`STStatusBarDataCellularEntry`）且内部设置了 `enabled: True`、`status: 5`、`string: "自定义名称"` 时，`SystemStatusUI` 会无视实时蜂窝域（`STTelephonyStatusDomain`）的脱网状态，强制将蜂窝条目保持为“启用且已连接”，导致开启飞行模式后锁屏与控制中心依然死死钉住自定义的运营商名。

### 2. 为什么 GUI 工具中信号选择“默认 (不变)”，实际却永久满格显示？
- **工具代码层 Bug（`tools/gui_server.py`）**：
  前端 `<select id="primaryBars">` 的“默认 (不变)”选项值为 `""`（后端接收为 `None`），但 `tools/gui_server.py` 第 1123 行写了：
  ```python
  primary_bars=body.get("bars") if body.get("bars") is not None else 4
  ```
  当用户选择“默认 (不变)”时，后台静默将其回退硬编码成了 `4`（满格）并固定 `type: 10`（5G）。
- **数据结构层限制（`STStatusBarDataCellularEntry`）**：
  在 `STStatusBarData` 中，运营商文字（`string`）、信号格数（`displayValue`）、网络制式（`type`）与启用状态（`enabled`）封装在同一个原子对象 `STStatusBarDataCellularEntry` 内，无法在 `StatusBarOverrides.archive` 中仅覆写文字而让信号格数透传真实基带数据。

---

## 二、 三条逆向方向的辩证裁决与汇编证据

| 逆向方向 | 核心分析模块与符号地址 | 辩证裁决 | 汇编级核心证据与结论 |
| :--- | :--- | :--- | :--- |
| **方向 3：`StatusBarOverrides` 字段级透传** | `UIKitCore` (`0x1c70d9000`)<br>`dataByApplyingOverlay:` (`0x1c80148f4`)<br>`_applyUpdate:keys:` (`0x1c8014748`) | **彻底证伪 (Dead End)** | 汇编证实合并逻辑仅遍历顶层 `entryKeys`，只要覆写包中 `cellularEntry != nil`，即调用 `setValue:forKey:`（`0x1c8014a04`）**整块替换**实时对象指针；`initWithCoder:`（`0x1c80108ac`）对缺省整型字段仅解码为 `0`，不存在字段级回退透传。 |
| **方向 1：`SystemStatus` / `SpringBoard` 默认键覆写** | `SystemStatus` (`0x2a4726000`)<br>`STSystemStatusDefaults` | **主名称证伪 / 仅角标可用** | `STSystemStatusDefaults`（继承自 `BSAbstractDefaultDomain`）仅注册了 3 个 Bundle 布尔开关属性，无运营商文本覆写键；`CoreTelephony` 的 `CTSimLabel`（`0x1a73a109c`）仅控制双卡角标（`[P]`/`[S]`），不改变主运营商名称。 |
| **方向 2：`CommCenter` / `CoreTelephony` 偏好与映射层** | `libCommCenterBase` (`0x1b3d3e000`)<br>`CoreTelephony` (`0x1a737b000`) | **唯一可行主方向 (Viable Upstream)** | 定位到 `NetworkListOperator::getLocalizedCompositeName`（`0x1b3db050c`）的 `InterCarrierRoamingDisplayNames` 查表替换分支，以及 `/var/mobile/Library/Preferences/` 下的 `com.apple.operator_1(.merged).plist` 映射机制（`0x1ebc2de68`）。修改位于 `CommCenter` 层，**100% 保留真实信号与飞行模式联动**。 |

---

## 三、 核心汇编逆向细节（方向 2：`CommCenter` 运营商名称解析）

### 1. `NetworkListOperator::getLocalizedCompositeName` (`0x1b3db050c..0x1b3db09ec`)
反汇编还原显示，`CommCenter` 在合成运营商显示名称时内置了按 `MCC+MNC`（移动国家码+网络码）字典覆写名称的逻辑：
- **`0x1b3db0550..0x1b3db0590`**：通过 RTTI 符号 `__ZTI24CarrierSettingsInterface`（`0x1f5adf998`）从 `Registry` 哈希表中获取 `CarrierSettingsInterface` 服务实例（`x23`）。
- **`0x1b3db0668..0x1b3db068c`**：
  - 加载键名 `x3 = CFSTR("InterCarrierRoamingDisplayNames")`（`0x1f5ae6dd0`）。
  - 设置 `w2 = 5`（`MOV w2, #5`，代表 `Operator` Bundle 类型），调用 `CarrierSettingsInterface` 虚表偏移 `+0x50` 读取覆写字典。
- **`0x1b3db06b8..0x1b3db0854`**：
  - 调用 `MCCAndMNC::MCCAndMNC`（`0x1b3d5af0c`）与 `MCCAndMNC::getStringValue()`（`0x1b3d5b318`），生成当前注册网络的 PLMN 字符串（如中国移动 `"46000"`、中国联通 `"46001"`、中国电信 `"46011"`）。
  - 在 `0x1b3db0810` 调用 `CFDictionaryGetValue` 查表，并在 `0x1b3db0820..0x1b3db0830` 校验返回值类型为 `CFStringGetTypeID()`（`0x1ba87f3f0`）。**若命中，直接将该自定义字符串作为运营商名称返回（`0x1b3db0854`）！**

### 2. `CarrierSettingsInterface` (`0x1b3dd4228..0x1b3dd430c`) 与 `/var/mobile/Library/Preferences/` 映射
- **卡槽域名映射（`0x1b3dd42c8` & `0x1b3dd42ec`）**：
  根据 `SimSlot`（主卡 `1` / 副卡 `2`）索引 `__DATA_CONST.__const` 段（`0x1ebc33f28` / `0x1ebc33f48` 及 `0x1ebc2de68..0x1ebc2ded8`）中的 `CFPreferences` 域名表：
  - **主卡（Slot 1）**：`com.apple.carrier_1`、`com.apple.operator_1`、`com.apple.carrier_1.merged`、`com.apple.operator_1.merged`
  - **副卡（Slot 2）**：`com.apple.carrier_2`、`com.apple.operator_2`、`com.apple.carrier_2.merged`、`com.apple.operator_2.merged`
- **`CommCenter` 持久化偏好域（`0x1b3da4108..0x1b3da485c`）**：
  - `DevicePersistentCopyValue` (`0x1b3da4394`) -> `com.apple.commcenter.device_specific_nobackup`
  - `CarrierBundleDevicePersistentCopyValue` (`0x1b3da43ec`) -> `com.apple.commcenter.carrier_bundle`
  - `CountryBundleDevicePersistentCopyValue` (`0x1b3da4418`) -> `com.apple.commcenter.country_bundle`
- **`VerifyBundles` 校验开关（`0x1a73856f0..0x1a7385774`）**：
  - `CTSettingSetVerifyCarrierBundles` / `CTSettingCopyVerifyCarrierBundles` 通过 `_CTServerConnectionPreferencesSetValue`（`0x1a74b1350`）读写 `VerifyBundles`（`0x1f4a067f0`）。

---

## 四、 下一步推进计划（待开展）

1. **路线 A（真机 `/var/mobile/Library/Preferences/` 偏好层安全探测与注入实验）**：
   - **Step 1（恢复真实信号与飞行模式基线）**：在测试机上执行 `python3 tools/airlift_carrier_deploy.py --reset` 并重启 `SpringBoard`，清除 `StatusBarOverrides.archive`。
   - **Step 2（上游偏好注入验证）**：由于 `/var/mobile/Library/Preferences/` 属主为 `mobile:mobile`（UID 501），完全在 AirLift 与 `HomeDomain` 备份恢复的可写范围内，测试向 `com.apple.operator_1.merged.plist` / `com.apple.operator_1.plist` / `com.apple.commcenter.carrier_bundle.plist` 注入 `InterCarrierRoamingDisplayNames`、`StatusBarImages` 与 `CarrierName`，验证 `cfprefsd` / `CommCenter` 重载后是否在不破坏 `.bundle` 签名的前提下动态生效。
2. **路线 B（离线反编译 iOS 27 `CommCenter` 主程序）**：
   - 提取 iOS 27 IPSW 中的 `/System/Library/Frameworks/CoreTelephony.framework/Support/CommCenter` 可执行文件，反编译纯虚接口 `CarrierSettingsInterface` (`__ZTV24CarrierSettingsInterface` @ `0x1f5adf8c8`) 与 `NetworkNameFactoryInterface` (`__ZTV27NetworkNameFactoryInterface` @ `0x1f5adf858`) 的具体实现子类，100% 确定免验签缓存键的读取顺序。

---

## 五、2026-10-19 实机验证进展（iPhone 14 Pro / iOS 27.0.1 / 24A446）

> 完整交接文档（含可复现命令与回滚方式）：[`../04_research_handoffs/2026-10-19_commcenter-preference-injection.md`](../04_research_handoffs/2026-10-19_commcenter-preference-injection.md)

### 1. 已实测确认

1. **测试机与网络**：iPhone 14 Pro（iPhone15,2），iOS 27.0.1（24A446）；当前 SIM 为 **中国联通**（PLMN `46001`/`46006`/`46009`/`46010`）。
2. **验证面成立**：iPhone 14 Pro 锁屏左上角直接渲染运营商名，无需解锁即可通过 CoreDevice 截图验证渲染结果。
3. **AFC 读取边界**：通过 AirLift 软链可对 `/var/mobile/Library/` 做 `stat`（`status=8` 不存在、`status=10` 存在但不可 stat），但 `read`/`list` 在 media 沙箱之外一律失败；因此 **当前构建不存在“回读偏好层 plist 内容”的 AFC 通道**。
4. **偏好域在干净设备上不存在**：`com.apple.operator_1(.merged)`、`com.apple.carrier_1(.merged)`、`com.apple.commcenter.carrier_bundle`、`com.apple.commcenter.device_specific_nobackup` 全部 `status=8`；`/var/wireless/Library/Preferences` 与 `/var/preferences` 下的同名域同样不存在。
5. **AirLift 写入通道复验**：探针名 `ZZTEST9` 成功写入 `StatusBarOverrides.archive` 并显示在锁屏，说明 24A446 上 ATAirlock 的覆盖写入在这个路径上可行。
6. **仅 respring 不能清除静态覆写**：部署 `--reset` 空归档后 respring，锁屏仍显示旧覆写，必须用户空间/整机重启才能让系统重新读取归档（`systemstatusd` 内存态）。
7. **整机重启的运维代价**：`devicectl reboot --style full` 后设备进入 USB 受限状态，`usbmux`/CoreDevice 均不可见，必须在设备上输入锁屏密码才恢复；`--style userspace` 不会打断 USB 连接。

### 2. 对原假设的修正

- 原研究报告假设“`com.apple.operator_1.merged.plist` 已存在，可直接改”。实测表明该文件在干净设备上**不存在**；路线 A 的实际动作是**新建 CFPreferences 域文件**。
- 因此“注入后 cfprefsd 是否会把这个新域提供给 CommCenter”以及“CommCenter 的 `CarrierSettingsInterface` 究竟读 `mobile` 用户域还是 `_wireless` 用户域”成为两个必须由实机结果回答的问题。
- 新增工具 `tools/commcenter_carrier_inject.py` 已按“新建域”模型实现：只写 `InterCarrierRoamingDisplayNames`（可选 `CarrierName`），payload 上限 512 KiB，仅允许 Preferences 目录与 8 个 `com.apple.operator_*`/`carrier_*` 域名。

### 3. 两轮实机注入与最终判定（2026-10-19 14:41–15:05）

**第一轮（operator 域 + 用户空间重启）**：写入 4 个 `com.apple.operator_{1,2}{,.merged}.plist`（`46001/46006/46009/46010 → DYNTEST`）与 `com.apple.carrier_1.plist`，目标域从 `status=8` 变为 `status=10`；userspace 重启后锁屏仍为 `中国联通`。当时判断可能是“首次解锁前偏好不可读”的时序问题。

**第二轮（全部候选域 + 全链路冷启动，设备解锁）**：

1. 覆盖 base 域（`com.apple.operator` / `com.apple.carrier` 普通与 `.merged`）与 slot1 域，payload 同时含 `InterCarrierRoamingDisplayNames` + `CarrierName` + `ShowCarrierName`（165 bytes）。
2. 通过 CoreDevice `send-signal-to-process` 对两个 `cfprefsd`、`CommCenter`、`SpringBoard` 发送 SIGTERM，四个进程全部由 launchd 重新拉起。
3. 结果：锁屏仍显示 `中国联通`，`DYNTEST2` 未出现。

**判定**：在 iPhone 14 Pro / iOS 27.0.1（24A446）+ 中国联通（46001 本网）上，**CFPreferences 偏好域注入（`InterCarrierRoamingDisplayNames` 或 `CarrierName`）不会改变运营商显示名**，即使 cfprefsd/CommCenter/SpringBoard 全部冷启动。

### 4. 备份取证与最终结论（15:16–15:20）

设备解锁并完成“信任此电脑”后，过滤备份成功（`Manifest.db` 17,511 行）。真实数据模型：

1. **网络参数**：`LastKnownServingMcc = 460`、`LastKnownServingMnc = 1`（PLMN 46001），`CarrierBundleName = '46001'`。
2. **CommCenter 状态位置**：全部在 **`WirelessDomain`**（`/var/wireless/Library/Preferences/`）：
   `com.apple.commcenter.plist`、`.data`、`.lazuli`、`.travel`、`.country_bundle`、`com.apple.CommCenter.counts`、`.quickswitch`、`.callservices`。
3. **不存在 `operator`/`carrier` 偏好域**：整个 manifest 中没有 `com.apple.operator_1` / `com.apple.carrier_1` 文件；`com.apple.commcenter.plist` 里的 `com.apple.carrier_1` 只是字符串 `'46001'`。
4. **运营商显示名来源**：已签名系统 bundle `/System/Library/Carrier Bundles/iPhone/46001/carrier.plist`（附 `overrides_D73_D74_D27_D28.plist`、`signatures`、`.der.pri`），位于 Sealed System Volume。
5. **我们创建的 12 个 HomeDomain 域不在备份清单中**（尽管 stat 显示存在：存在=10、缺失=8）；无论 backupd 是出于属主还是系统域名单跳过，它们都不是 CommCenter 的运营商数据来源。

**最终结论**：

- 在非越狱、无提权写原语的能力边界内，**动态运营商（真实信号 + 飞行模式联动）没有可用写入路径**：真正的数据在 `/var/wireless`（`_wireless` 属主）与密封的已签名 carrier bundle 中，mobile/AirLift 均不可写；`InterCarrierRoamingDisplayNames` 即使存在于 bundle 中，也无法在不破坏签名的前提下注入。
- 静态 `StatusBarOverrides.archive` 仍是唯一可工作的非越狱方案，其“信号钉死、飞行模式常驻”的限制保持不变。
- 若未来获得以下任一原语，本路线可重新评估：① 对 `/var/wireless` 的 root 写；② 能通过签名校验的 carrier bundle overlay；③ 运行期注入 `CommCenter`（越狱/tweak）。
- 仍可选的纯研究（无写入能力）：通过 IPSW 提取 `carrier.plist` 与 `CommCenter` 主程序，确认 `InterCarrierRoamingDisplayNames` 的真实读取位置与门控条件；这不会改变上述“不可写”的结论。

---

## 六、推荐交付配置：部分 entry（2026-10-19 最终）

经过实机验证与 SystemStatusUI 反汇编，非越狱条件下的最佳配置是**部分 entry**：

`~bash
python3 tools/airlift_carrier_deploy.py -c "自定义名称" --partial
`~

或使用 GUI，勾选「保留实时信号格（部分覆写）」。

效果：

- 自定义运营商名称；
- 锁屏与 Control Center 的**信号格回退实时**（省略 `displayValue`）；
- Control Center **不显示制式文字**（省略 `type`）；
- 飞行模式下名称仍常驻（名称渲染要求 `enabled=true` 且 `status=5`，静态归档没有跟随实时状态的哨兵）。

因此：真实信号格已用纯静态归档解决；飞行模式联动只能依赖运行期发布 `STStatusBarOverridesStatusDomain`（需要 `com.apple.systemstatus.publisher` entitlement，属于越狱/TrollStore 级能力）。
