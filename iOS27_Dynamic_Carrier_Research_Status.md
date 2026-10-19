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

> 完整交接文档（含可复现命令与回滚方式）：[`docs/handoffs/iOS27_CommCenter_Preference_Injection_2026-10-19.md`](docs/handoffs/iOS27_CommCenter_Preference_Injection_2026-10-19.md)

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

### 3. 首轮注入结果（2026-10-19 14:41–14:45）

- 已向 4 个 `com.apple.operator_{1,2}{,.merged}.plist` 写入 `InterCarrierRoamingDisplayNames`（46001/46006/46009/46010 → `DYNTEST`），并补写 `com.apple.carrier_1.plist`；目标域从 `status=8`（不存在）变为 `status=10`（存在但元数据被拒），与已知偏好文件（`Accessibility`/`mobiletimer`/`Preferences` 均为 10）一致。
- userspace 重启后锁屏仍为 `中国联通`，`DYNTEST` 未出现。
- **该阴性结果不能否定假设**：偏好文件默认是 class C（`CompleteUntilFirstUserAuthentication`），本次启动后尚未首次解锁，cfprefsd/CommCenter 在启动时不可读这些新域；而 class A 的 `.GlobalPreferences.plist` 锁屏下仍可 stat 到 20845 bytes。
- 另一个待排除项：若 ATAirlock 以 root 属主创建文件（0600），mobile 的 cfprefsd 将永远读不到；解锁后对目标域做 stat 可区分（class C + mobile → 可读；root → 仍 EPERM）。

### 4. 待执行（设备解锁后，修订版）

1. 解锁后先 `stat` 目标域：可读（`st_size=126`）说明 class C + mobile 属主，机制测试有效；仍 EPERM 则需怀疑 root 属主并改用备份恢复写入；
2. 解锁状态下重新注入（可加 `--include-carrier-name` 变体），**不重启**，先用飞行模式切换/进程重启强制 CommCenter 重载，再截图控制中心；
3. 若仍无效，再用过滤备份读取真实偏好内容，并转向路线 B（DSC/IPSW 离线反编译 `CommCenter` 主程序，确认 `CarrierSettingsInterface` 的真实域名与 bundle 来源）。