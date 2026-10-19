# iOS 27 动态运营商名称（真实信号 + 飞行模式联动）深度逆向研究报告

> **研究日期**：2026-10-14  
> **研究背景**：解决现有 `StatusBarOverrides.archive` 方案在开启飞行模式后运营商名称依然“写死”常驻、以及信号格数被静态固定为满格（4 格）而无法反映真实基带信号的架构瓶颈。  
> **逆向对象**：`UIKitCore` (`0x1c70d9000`)、`SystemStatus.framework` (`0x2a4726000`)、`CoreTelephony.framework` (`0x1a737b000`)、`libCommCenterBase.dylib` (`0x1b3d3e000`) 及内存 `dyld_shared_cache` 全量 4,088 个系统镜像。

---

## 1. 问题现象与第一性根因剖析

在物理真机（iPhone 16 Pro Max / iOS 27.0 `24A437`）与模拟器实测中，通过 `/var/mobile/Library/SpringBoard/StatusBarOverrides.archive` 注入自定义运营商名称存在两项实质性体验缺陷：

1. **开启飞行模式后运营商名称仍“写死”在屏幕顶部/控制中心**：
   打开飞行模式后，真实蜂窝网络已断开，但锁屏顶栏与控制中心依然渲染自定义的 Carrier Name，不会随飞行模式隐藏。
2. **信号格数永久固定为满格（4 格），无法显示真实实时信号**：
   即使在自动化工具（`tools/gui_server.py`）中选择“信号格数：默认 (不变)”，状态栏信号依然永久固定为 4 格满信号，不随真实基带信号强弱波动。

### 1.1 工具层面的直接 Bug（`tools/gui_server.py`）
在 `tools/gui_server.py` 中，前端下拉框 `<select id="primaryBars">` 的“默认 (不变)”选项值为 `""`（传给后端 JSON 为 `null` / `None`），但后端第 1123 行存在硬编码回退：
```python
primary_bars=body.get("bars") if body.get("bars") is not None else 4
```
且 `build_cellular_archive()` 在构造 `STStatusBarDataCellularEntry` 时硬编码了 `enabled: True`、`status: 5`（已连接）、`displayValue: 4`（满格）和 `type: 10`（5G）。

### 1.2 架构层面的根本限制（`STStatusBarData` 整对象原子替换）
更核心的问题在于：即便修改 Python 脚本不传 `4`，`StatusBarOverrides.archive` 在 iOS 27 的 `SystemStatus` 架构下能否实现“仅覆盖 `string`（运营商名），而让 `displayValue`（信号格数）和 `enabled`（飞行模式显隐）继续走真实基带数据”？

我们直接对 `dyld_shared_cache` 中的状态栏合并逻辑进行了汇编级反编译验证。

---

## 2. 阶段一（方向 3 证伪）：`StatusBarData` 覆写合并机制反汇编

在 `UIKitCore`（基址 `0x1c70d9000`，与 `SystemStatus` 共享相同的 `StatusBarData` 实体模型）中，核心合并方法位于：
- `-[_UIStatusBarData _applyUpdate:keys:]` (`0x1c8014748 .. 0x1c801487c`)
- `-[_UIStatusBarData applyUpdate:]` (`0x1c801487c .. 0x1c80148f4`)
- `-[_UIStatusBarData dataByApplyingOverlay:]` (`0x1c80148f4 .. 0x1c8014a98`)
- `-[_UIStatusBarData dataByApplyingUpdate:keys:]` (`0x1c8014a98 .. 0x1c8014c10`)
- `-[_UIStatusBarDataAggregator _updatedDataFromData:delayedKeys:]` (`0x1c80153f4 .. 0x1c80155f0`)

### 2.1 关键汇编指令与选择器解析
```text
=== -[_UIStatusBarData _applyUpdate:keys:] (0x1c8014748..0x1c801487c) ===
  0x1c80147ac: BL 0x1ca7cd040 ; objc_msgSend$countByEnumeratingWithState:objects:count:
  0x1c80147b0: CBZ x0, 0x1c8014838
  0x1c80147ec: BL 0x1ca7cdc30 ; objc_msgSend$valueForKey:
  0x1c80147f8: CBZ x0, 0x1c801480c
  0x1c8014808: BL 0x1ca7ceb30 ; objc_msgSend$setValue:forKey:

=== -[_UIStatusBarData dataByApplyingOverlay:] (0x1c80148f4..0x1c8014a98) ===
  0x1c8014958: BL 0x1ca9024e0 ; objc_msgSend$existingEntryKeys
  0x1c8014970: BL 0x1ca7cd040 ; objc_msgSend$countByEnumeratingWithState:objects:count:
  0x1c80149b4: BL 0x1ca7cdc30 ; objc_msgSend$valueForKey:
  0x1c80149c4: CBZ x25, 0x1c8014a0c
  0x1c80149d4: BL 0x1ca7ccfe0 ; objc_msgSend$copy
  0x1c80149ec: BL 0x1ca7cdc30 ; objc_msgSend$valueForKey:
  0x1c8014a04: BL 0x1ca7ceb30 ; objc_msgSend$setValue:forKey:
```

### 2.2 证伪结论
1. **以顶层 Entry 对象为最小合并粒度**：`dataByApplyingOverlay:` 与 `_applyUpdate:keys:` 遍历的是顶层 `entryKeys`（如 `"cellularEntry"`、`"secondaryCellularEntry"`、`"airplaneModeEntry"`）。只要覆写归档中 `cellularEntry != nil`，系统就通过 `setValue:forKey:` 将**整个 `STStatusBarDataCellularEntry` 实例指针**替换掉实时数据，**不存在任何字段级（Field-level）合并逻辑**。
2. **反序列化无哨兵透传值**：在 `-[_UIStatusBarDataCellularEntry initWithCoder:]`（`0x1c80108ac`）及其父类 `-[_UIStatusBarDataIntegerEntry initWithCoder:]`（`0x1c800f3c4`）中，`displayValue`、`rawValue`、`type`、`status`、`enabled` 均为基础整型/布尔值。若在归档中省略这些键，`NSKeyedUnarchiver` 默认解码为 `0` / `NO`（即 0 格信号或禁用条目），不会回退读取实时 `STTelephonyStatusDomain`。
3. **裁决**：**`StatusBarOverrides.archive` 在架构原理上注定是全量静态 Mock 覆写**。要实现“真实信号 + 飞行模式联动”，必须放弃在 `StatusBarOverrides` 层修补，将逆向切入点上移至上游数据源。

---

## 3. 阶段二（方向 1 排查）：`SystemStatus` 默认键与 `CTSimLabel` 边界

我们对 `SystemStatus.framework`（`0x2a4726000`）与 `CoreTelephony.framework`（`0x1a737b000`）进行了运行时反射与符号排查：

1. **`STSystemStatusDefaults`（`SystemStatus.framework`）**：
   - 继承自 `BSAbstractDefaultDomain`，通过 `-_bindAndRegisterDefaults` 仅绑定了 3 个布尔属性：
     - `shouldEnableInternalBundles` (`TB,D,N`)
     - `shouldEnableUnknownBundles` (`TB,D,N`)
     - `shouldEnableUnknownBackgroundActivities` (`TB,D,N`)
   - **结论**：`SystemStatus` 内部不存在用于单独覆写运营商文本的 `NSUserDefaults` 键。
2. **`CTSimLabel` 与 `CTXPCSetSimLabelRequest`（`CoreTelephony.framework`）**：
   - 符号地址：`-[CTSimLabel initWithId:andText:andDidSetup:]` (`0x1a73a109c`)、`-[CTXPCSetSimLabelRequest performRequestWithHandler:completionHandler:]` (`0x1a73dcbdc`)。
   - **结论**：该机制控制的是 eSIM / 双卡的自定义标签（对应状态栏角标 `badgeString`，如 `"主卡"`、`"副卡"`、`"P"`、`"S"`），无法替换主运营商名称 `operatorName`。

---

## 4. 阶段三（方向 2 深度突破）：`CommCenter` / `libCommCenterBase` 运营商名称合成与配置契约

全量扫描内存中 4,088 个 `dyld_shared_cache` 镜像后确认，蜂窝运营商名称的最终权威源头位于 `CoreTelephony.framework`（`0x1a737b000`）与 `libCommCenterBase.dylib`（`0x1b3d3e000`）。

### 4.1 `CoreTelephony` 获取运营商名的 XPC 契约
反汇编 `_CTServerConnectionCopyCurrentOperatorName`（`0x1a746fe38 .. 0x1a7470100`）与 `-[CTXPCGetOperatorNameRequest performRequestWithHandler:completionHandler:]`（`0x1a741701c`）：
- 客户端向 `CommCenter` 发送 XPC 字典请求：
  - `kRequest` (`0x1a7502b46`) = `"kRegistrationGetProperty"` (`0x1a7512c26`)
  - 属性键：`"kRegistrationOperatorName"` (`0x1a7513473`) 与 `"kRegistrationLocalize"` (`0x1a751348d`)
- 紧随其后的分支（`0x1a74700a0`）支持请求 `"kRegistrationProviderName"` (`0x1a7512d9b`) 并传入 `"kRegistrationUseCarrierBundle"` (`0x1a7512db5`)。

### 4.2 `NetworkListOperator::getLocalizedCompositeName` (`0x1b3db050c`) 逐行反汇编还原
在 `libCommCenterBase.dylib` 中，函数 `_ZNK19NetworkListOperator25getLocalizedCompositeNameERKNSt3__110shared_ptrIK8RegistryEEN10subscriber7SimSlotE`（`0x1b3db050c .. 0x1b3db09ec`）揭示了 `CommCenter` 内置的一条**基于字典映射的运营商名称覆写机制**：

```text
  0x1b3db0548: BL 0x1b3dc4910 ; Registry::throwIfNotInitialized()
  0x1b3db0550: ADRP x8, 0x1f5adf000
  0x1b3db0554: ADD x8, x8, #0x998 -> 0x1f5adf998 (__ZTI24CarrierSettingsInterface)
  0x1b3db0590: BL 0x1b3d54da4 ; unordered_map::find(CarrierSettingsInterface RTTI)
  0x1b3db0654: LDR x16, [x23, #0x0] ; 读取 CarrierSettingsInterface 虚表 (vtable)
  0x1b3db0664: LDR x9, [x16, #0x50]!; 虚表偏移 +0x50 (copyValueForKey)
  0x1b3db0668: ADRP x3, 0x1f5ae6000
  0x1b3db066c: ADD x3, x3, #0xdd0 -> 0x1f5ae6dd0 CFSTR("InterCarrierRoamingDisplayNames")
  0x1b3db067c: MOV w2, #0x5          ; BundleType = 5 (Operator Bundle)
  0x1b3db068c: BLRAA x9, x16         ; 调用 CarrierSettingsInterface->copyValueForKey(...)
  0x1b3db06a4: LDR x8, [sp, #0x80]
  0x1b3db06a8: CBZ x8, 0x1b3db06e8   ; 若字典为空则跳回 getCompositeName()
  0x1b3db06b8: BL 0x1b3d5af0c ; MCCAndMNC::MCCAndMNC(MCC, MNC)
  0x1b3db06c4: BL 0x1b3d5b318 ; MCCAndMNC::getStringValue() (如 "46000", "46001")
  0x1b3db0810: BL 0x1ba87c500 ; CFDictionaryGetValue(dict, cfPlmnString)
  0x1b3db0818: CBZ x0, 0x1b3db086c
  0x1b3db0820: BL 0x1ba87c560 ; CFGetTypeID(val)
  0x1b3db0828: BL 0x1ba87f3f0 ; CFStringGetTypeID()
  0x1b3db0830: B.NE 0x1b3db086c
  0x1b3db0854: BL 0x1ba88b230 ; 将命中的自定义 CFString 转换为返回字符串！
```

**关键机制解读**：
- 当 `Operator` 配置中存在 `InterCarrierRoamingDisplayNames` 字典时，`CommCenter` 会将当前基带注册的 `MCC+MNC`（例如中国移动 `"46000"`、中国联通 `"46001"`、中国电信 `"46011"`）作为 Key 查表。
- 一旦字典命中对应的 `CFString`，**直接用该字符串替代默认运营商名称返回**，且由于该逻辑运行在 `CommCenter` 网络注册层，**真实信号格数与飞行模式脱网隐藏完全不受影响**。

### 4.3 `CarrierSettingsInterface` (`0x1b3dd4228`) 与 `/var/mobile/Library/Preferences/` 映射表
反汇编 `CarrierSettingsInterface`（`0x1b3dd4228 .. 0x1b3dd430c`）及 `__DATA_CONST.__const` 段（`0x1ebc2de68 .. 0x1ebc2ded8`、`0x1ebc33f28 .. 0x1ebc33f48`）发现：
1. **卡槽与偏好设置域名映射**：
   - 在 `0x1b3dd42c8` 与 `0x1b3dd42ec` 处，通过 `SimSlot` 索引全局表，对应 `/var/mobile/Library/Preferences/` 下的如下 Plist 域：
     - `0x1ebc2de68`: `com.apple.carrier` / `com.apple.carrier_1` / `com.apple.carrier_2`
     - `0x1ebc2de80`: `com.apple.operator` / `com.apple.operator_1` / `com.apple.operator_2`
     - `0x1ebc2dea8`: `com.apple.carrier.merged` / `com.apple.carrier_1.merged` / `com.apple.carrier_2.merged`
     - `0x1ebc2dec0`: `com.apple.operator.merged` / `com.apple.operator_1.merged` / `com.apple.operator_2.merged`
   - 在 `CoreTelephony` 的 `-[CTMessageCenter sendMMS:]`（`0x1a73d487c .. 0x1a73d48a0`）中，系统通过 `_CFStringGetMobileUser()`（`@"mobile"`）直接调用 `CFPreferencesCopyValue(key, @"com.apple.carrier_1", @"mobile", kCFPreferencesAnyHost)`。
2. **`CommCenter` 专用持久化偏好域（`0x1b3da4108 .. 0x1b3da485c`）**：
   - `DevicePersistentCopyValue` (`0x1b3da4394`) -> `CFSTR("com.apple.commcenter.device_specific_nobackup")` (`0x1f5ae5ad0`)
   - `AttachAPNDevicePersistentCopyValue` (`0x1b3da43c0`) -> `CFSTR("com.apple.commcenter.attach_apn")` (`0x1f5ae5c50`)
   - `CarrierBundleDevicePersistentCopyValue` (`0x1b3da43ec`) -> `CFSTR("com.apple.commcenter.carrier_bundle")` (`0x1f5ae5c70`)
   - `CountryBundleDevicePersistentCopyValue` (`0x1b3da4418`) -> `CFSTR("com.apple.commcenter.country_bundle")` (`0x1f5ae5c90`)
3. **`VerifyBundles` 校验开关（`0x1a73856f0 .. 0x1a7385774`）**：
   - `CTSettingSetVerifyCarrierBundles` (`0x1a73856f0`) 与 `CTSettingCopyVerifyCarrierBundles` (`0x1a7385748`) 通过 `_CTServerConnectionPreferencesSetValue` (`0x1a74b1350`) 发送 `kSettingsModelPreferencesSetValue` 请求，操作键 `CFSTR("VerifyBundles")` (`0x1f4a067f0`)。

---

## 5. 下一阶段实验与验证路线图

由于 `/var/mobile/Library/Preferences/` 属主同样为 `mobile:mobile`（UID 501），完全处于 AirLift 路径遍历写原语与 `HomeDomain` 备份恢复的可达范围内，下一阶段实机/固件验证按以下优先级推进：

1. **路线 A（真机 `/var/mobile/Library/Preferences/` 偏好层探测与注入验证）**：
   - **Step 1**：使用 `airlift_carrier_deploy.py --reset` 清除 `StatusBarOverrides.archive`，恢复真实信号格数与飞行模式自动隐藏基线。
   - **Step 2**：针对 `/var/mobile/Library/Preferences/` 下的 `com.apple.operator_1.merged.plist`、`com.apple.operator_1.plist` 及 `com.apple.commcenter.carrier_bundle.plist`，测试注入 `InterCarrierRoamingDisplayNames`（映射当前 SIM 卡 `MCC+MNC`）、`StatusBarImages` 与 `CarrierName`，验证 `cfprefsd` / `CommCenter` 重载后是否在不破坏 `.bundle` 签名的前提下动态更新 `operatorName`。
2. **路线 B（离线提取 iOS 27 `CommCenter` 主程序反编译 `NetworkNameFactory` 与 `CarrierSettings` 子类）**：
   - `libCommCenterBase.dylib` 中的 `__ZTV24CarrierSettingsInterface` (`0x1f5adf8c8`) 与 `__ZTV27NetworkNameFactoryInterface` (`0x1f5adf858`) 为纯虚接口，具体派生类编译在 iOS 固件 `/System/Library/Frameworks/CoreTelephony.framework/Support/CommCenter` 主程序中。获取 iOS 27 IPSW 提取该二进制后，可直接定位虚表 `+0x50` 的具体实现，100% 确认免验签缓存键的读取优先级。

---

## 6. 实机验证状态与边界修正（2026-10-19 / iPhone 14 Pro / iOS 27.0.1 24A446）

在把本文档的静态结论落到真机之前，先做了三项边界测量，结果修正了若干前提：

1. **偏好域并不存在**：`/var/mobile/Library/Preferences/` 下 `com.apple.operator_1.plist`、`com.apple.operator_1.merged.plist`、`com.apple.carrier_1.plist`、`com.apple.carrier_1.merged.plist`、`com.apple.commcenter.carrier_bundle.plist`、`com.apple.commcenter.device_specific_nobackup.plist` 全部返回 `ENOENT`（通过 AirLift 软链 stat，status=8）。`/var/wireless/Library/Preferences/` 与 `/var/preferences/` 下的同名域同样不存在。
   → 因此 §5 路线 A 的实际语义是 **新建 CFPreferences 域**，而不是修改既有 merged 缓存。
2. **AFC 读通道失效**：在 24A446 上，AFC daemon 对 media 沙箱之外只有 metadata 权限；`read` 与目录 `list` 均失败，仅 `stat` 可穿过软链。因此无法用 AFC 回读偏好 plist 内容，字节级验证必须改用 MobileBackup2 备份。
3. **静态覆写与动态注入的判定隔离**：`StatusBarOverrides.archive` 的优先级高于实时蜂窝域，必须先用 reset 归档 + 用户空间重启确认锁屏回到原生 `中国联通`，才能把“锁屏文字变化”归因于 CommCenter 偏好注入，否则会得到假阴性。

已就绪的注入工具：`tools/commcenter_carrier_inject.py`（只读工具 `tools/device_path_probe.py`、视觉验证 `tools/device_ui.py`）。完整实验协议见 [`handoffs/iOS27_CommCenter_Preference_Injection_2026-10-19.md`](handoffs/iOS27_CommCenter_Preference_Injection_2026-10-19.md)。

### 6.1 实机结果：偏好层注入阴性

在 iPhone 14 Pro / iOS 27.0.1（24A446）、中国联通（46001）上：

- 12 个候选域（base / slot1 / slot2 × `operator` / `carrier` × 普通 / `.merged`）全部创建成功（`status=8 → 10`）；
- payload 同时包含 `InterCarrierRoamingDisplayNames`、`CarrierName`、`ShowCarrierName`；
- 设备解锁状态下，通过 CoreDevice 信号通道冷启动 `cfprefsd`（两个实例）、`CommCenter`、`SpringBoard`；
- 锁屏运营商名仍为 `中国联通`。

因此，§4.2 的“偏好层查表”在当前构建上**不是可用的重命名入口**。三种候选解释（bundle 来源 / 仅漫游触发 / 文件被 cfprefsd 忽略）需要 §6 的下一步分别验证；其中 `CommCenter` 主程序的 `CarrierSettingsInterface` 实现是路线 B 的核心目标。

新增可复用原语：CoreDevice `send-signal-to-process` 可冷启动任意用户态守护进程，用于区分“缓存”与“真实不生效”。

### 6.2 备份取证：真实数据模型（决定性）

受信过滤备份（`Manifest.db` 17,511 行）显示：

- 本机 PLMN `46001`（`LastKnownServingMcc=460`、`Mnc=1`、`CarrierBundleName='46001'`）；
- CommCenter 的持久化状态全部位于 `WirelessDomain`（`/var/wireless/Library/Preferences/com.apple.commcenter.*`）；
- 整个 manifest 中**不存在** `com.apple.operator_1` / `com.apple.carrier_1` 域；`com.apple.commcenter.plist` 中的 `com.apple.carrier_1` 只是字符串 `'46001'`；
- 运营商显示名来自已签名系统 bundle `/System/Library/Carrier Bundles/iPhone/46001/carrier.plist`（含 `signatures` 与 `.der.pri`）。

**结论**：§4.3 中“`/var/mobile/Library/Preferences/` 映射”在当前 iOS 27.0.1 上不成立——该目录不是运营商数据层。真正的数据层（`/var/wireless` 与密封 bundle）在非越狱/mobile 上下文中不可写，因此本文档描述的上游动态路线**没有可落地的注入原语**；静态 `StatusBarOverrides` 仍是唯一可用方案。

后续若要继续：需 IPSW 提取 `carrier.plist` 与 `CommCenter` 主程序，确认 `InterCarrierRoamingDisplayNames` 的读取位置与门控（纯研究，不改变不可写结论）。