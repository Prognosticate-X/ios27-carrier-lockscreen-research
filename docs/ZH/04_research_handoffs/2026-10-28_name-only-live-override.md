# iOS 27 “只改名称、其余全实时”路线研究（Nugget 行为复刻）

**文档编号**：`DOC-20261028-NAME-ONLY`  
**日期**：2026-10-28  
**目标设备**：iPhone 14 Pro（iPhone15,2）/ iOS 27.0.1（24A446）  
**目标**：复刻 Nugget 在 iOS 26 及以下的行为——**只修改运营商名称，信号格、制式图标、飞行模式联动全部来自真实 live 数据**。  
**关联**：[2026-10-28 研究路线图](2026-10-28_next-research-roadmap.md) · [2026-10-28 飞行模式矩阵](2026-10-28_airplane-mode-status-matrix.md)

> **设备说明**：实际 USB 连接的是 **iPhone 14 Pro**，不是 iPhone 14 Pro Max；当前没有 14 Pro Max 出现。主力 16 Pro Max 与 17 Pro Max 已在 `safety.json` 黑名单。

---

## ⚠️ 2026-10-28 22:10 事故记录（重要，先读）

在 Find My 已关闭的前提下，执行一版 `backup2 restore --system` 的最小备份（`Manifest.db` + `IsFullBackup=True`）后：

1. 14 Pro 重启后进入了 **Setup Assistant**：`Setup.app` 与 `budd` 正在运行，屏幕显示 "hej" 欢迎页，无运营商名称。
2. 目标文件 **并没有被写入**：随后生成的过滤备份中，`WirelessDomain/Library/Preferences/com.apple.operator_1.plist` 记录为 0；WirelessDomain 仍只有原来的 22 条记录。
3. 结论：**iOS 27 的备份恢复既没有安全写入 WirelessDomain，还会把设备置于 Setup Assistant。不要重复这条实验。**

**设备恢复建议**：立即停止所有写入；由用户在设备上完成 Setup Assistant，或用 Finder / Apple Devices 从既有完整备份恢复。除非确认测试机数据可丢弃，不要选择“抹掉并重新设置”。

---

---

## 1. 为什么 Nugget 在 iOS 26 及以下能做到

旧版 `statusBarOverrides` 是 `StatusBarOverrideData` C 结构，带**逐字段 override flags**：

- 只设置 `serviceString` 和对应的 name 标志；
- `signalStrength`、`serviceType`、`enabled/status` 等字段不设置，系统继续使用 live 数据；
- 因此名称是静态的，但信号、制式、飞行模式联动都是真实的。

iOS 27 的现代状态栏改成了 `STStatusBarData` + `StatusBarOverrides.archive`：

- `dataByApplyingOverlay:` 以 **整个 `STStatusBarDataCellularEntry` 对象**为单位替换；
- 缺失字段在 `initWithCoder:` 中解码为 `0/false`，没有“未覆写”标志；
- 因此不存在旧版的字段级 pass-through。

---

## 2. 运行时数据模型取证

用模拟器 + Objective-C runtime 枚举 `SystemStatus.framework`（iOS 27.0，24A434）：

`STStatusBarDataCellularEntry` 的 ivars：

~~~text
_wifiCallingEnabled      : B
_callForwardingEnabled   : B
_showsSOSWhenDisabled    : B
_sosAvailable            : B
_isBootstrapCellular     : B
_type                    : q
_string                  : NSString
_suffixString            : NSString
_crossfadeString         : NSString
_badgeString             : NSString
_numberSharingState      : q
~~~

父类链：

~~~text
STStatusBarDataEntry          -> _enabled : B
STStatusBarDataIntegerEntry   -> _displayRawValue : B, _rawValue : q, _displayValue : q
STStatusBarDataNetworkEntry   -> _lowDataModeActive : B, _status : q
~~~

**没有任何 `flags` / `hasString` / `overrideString` / “未设置”布尔字段。**  
名称、制式、信号、enabled/status 全部属于同一个原子 entry。这是静态归档无法只改名称的根本原因。

---

## 3. 补充实验（iPhone 14 Pro / 27.0.1）

| Variant | 字段 | 结果 | 结论 |
|---|---|---|---|
| `NOSTATUS` | `enabled=true`，省略 `status/displayValue/type` | 无名称、无蜂窝格 | 省略 `status` 会隐藏整个蜂窝 item |
| `NOENABLED` | 省略 `enabled/status/displayValue/type` | 无名称、无蜂窝格 | 省略 `enabled` 同样隐藏 item |
| `type=0` | `status=5, enabled=true`，省略 `displayValue`，`type=0` | 名称 + 实时格，**无制式文字** | 0 被当作“无制式” |
| `type=-1` | 同上，`type=-1` | 名称 + 实时格，**无制式文字** | 无 live 回落 |
| `type=255` | 同上，`type=255` | 名称 + 实时格，**无制式文字** | 无 live 回落 |
| `type=10` | 同上，`type=10` | 名称 + 实时格 + **5G** | 制式是静态写入的 |
| `status=1` | `enabled=true`，省略 `displayValue/type` | 蜂窝开：**原生名 + 实时格/制式**；飞行模式：**自定义名** | live-fallback 方向相反 |
| `status=5 + isBootstrapCellular=true` | 省略 `displayValue/type` | 无名称、有格 | 名称门控直接关闭 |

结论：**partial 模式与省略 `displayValue` 模式均无法解决“实时制式文字”和“飞行模式隐藏”；`status=1` 是反向 live-fallback，不是自定义名模式。**

> **2026-10-29 iPhone 14 Pro 实机复核修正（重要）**：经同机 AB 截图比对（详见 [`2026-10-29_displayvalue-omission-hardware-verification.md`](../03_hardware_and_verification/2026-10-29_displayvalue-omission-hardware-verification.md)），上表中省略 `displayValue` 时所观察到的“实时格”实际上来自**下拉控制中心连接卡片内的「绿色圆形蜂窝开关图标」**（该图标直接查询 `CoreTelephony`，无论是否覆写均实时显示真实 2 格信号）；而**顶部状态栏与控制中心左上角**由于 `-[NSCoder decodeIntegerForKey:@"displayValue"]` 在缺省键时返回 `0`，实际上被锁死在 **`0` 格全灰空心条**（并非实时跳动）。因此默认生产配置应保持 `displayValue = 4`。

---

## 4. 新的上游线索：WirelessDomain

### 4.1 备份取证

用 `pymobiledevice3 backup2 backup --only-regex` 生成过滤备份后，`Manifest.db` 中确实存在：

~~~text
WirelessDomain  Library/Preferences/com.apple.commcenter.plist
WirelessDomain  Library/Preferences/com.apple.commcenter.data.plist
WirelessDomain  Library/Preferences/com.apple.CommCenter.counts.plist
... 共 22 条
~~~

关键元数据：

- `UserID=25`、`GroupID=25`（不是 `mobile` 501）；
- `ProtectionClass=4`；
- `com.apple.commcenter.plist` 当前大小 `3269`；
- `com.apple.operator_1.plist` / `com.apple.carrier_1.plist` **不存在**。

这说明：**CommCenter 的真实偏好域在 `/var/wireless/Library/Preferences`，且该域会进入备份清单**。之前 2026-10-19 的注入实验只写了 HomeDomain（`/var/mobile/Library/Preferences`），CommCenter 当然不读。

### 4.2 最小备份恢复实验

构造了一个只包含 4 条记录的备份：

- `WirelessDomain` 根目录 / `Library` / `Library/Preferences` 目录；
- 新增 `WirelessDomain/Library/Preferences/com.apple.operator_1.plist`，内容为：

~~~xml
<dict>
  <key>InterCarrierRoamingDisplayNames</key>
  <dict>
    <key>46001</key><string>WIFITEST</string>
    ...
  </dict>
  <key>CarrierName</key><string>WIFITEST</string>
  <key>ShowCarrierName</key><true/>
</dict>
~~~

执行：

~~~bash
pymobiledevice3 backup2 restore .artifacts/backup/wireless-test \
  --no-reboot --no-settings --no-remove --skip-apps --no-copy
~~~

设备返回：

~~~text
MBErrorDomain/211
Find My iPhone must be disabled before restoring
~~~

**这是当前唯一的硬阻塞：备份恢复要求先关闭“查找我的 iPhone”。**

### 4.3 如果关闭 Find My，下一步怎么验证

1. 在 14 Pro 测试机上关闭“查找我的 iPhone”（需要 Apple ID 密码）；
2. 重跑最小备份恢复，只写入 `com.apple.operator_1.plist`；
3. 通过 CoreDevice 冷重启两个 `cfprefsd` + `CommCenter` + `SpringBoard`；
4. 截图锁屏/CC：
   - 如果显示 **WIFITEST + 实时信号/制式/飞行联动** → 成功，说明 live 名称来自 WirelessDomain；
   - 如果仍显示原生名 → 该 key 不在 CommCenter 读取路径，改测 `com.apple.commcenter.plist` 合并注入；
   - 如果出现 No Service → 立即恢复原始备份/删除注入文件。

风险：备份恢复即使带 `--no-remove` 也有一定侵入性；只在测试机做，并先做完整本地备份。

---

## 5. 其他路径评估

| 路径 | 可行性 | 说明 |
|---|---|---|
| `WirelessDomain` 备份注入 | **已证伪且不安全** | 恢复会把设备置入 Setup Assistant，且目标文件未写入（见事故记录）；不要重复 |
| Carrier Bundle Overlay 显示名 | 低 | 签名校验/No Service；只改显示名的 overlay 尚未找到 |
| 运行时发布 `STStatusBarOverridesStatusDomain` | 非越狱不可行 | 需要 `com.apple.systemstatus.publisher` entitlement |
| 旧版 `statusBarOverrides` C 结构 | 不可行 | Speakeasy 强制现代状态栏，SpringBoard 不读 |
| Speakeasy/FeatureFlags 关闭 | 不可行 | `/var/preferences` root 写保护 + Security State Recovery |
| `UIStatusBar_Base(Snapshots) sb_setLocalDataOverrides:` | 不适用 | 只用于快照，不是系统级 live 发布 |

---

## 6. 当前可用路径

WirelessDomain 备份注入已经**证伪且不安全**：既没有写入目标文件，又把测试机置入 Setup Assistant。非越狱的静态/备份路径目前没有可用方案。

剩下的选择只有：

1. **接受静态 partial**：自定义名称 + 实时信号格，但制式文字无法实时、飞行模式名称常驻；
2. **越狱/TrollStore 运行时 publisher 原型**：需要 entitlement，超出 stock iOS 交付边界；
3. **等待 Apple 改变状态栏数据模型/官方配置面**（当前无证据）。

在测试机恢复之前，不再进行任何设备写入。

---

## 7. 证据与工具

- 运行时枚举：`.artifacts/introspect/introspect.m`（类 ivars/properties/methods）
- 最小备份：`.artifacts/backup/wireless-test/`
- 实验台：[`tools/exp_status_matrix.py`](../../../tools/exp_status_matrix.py)
- REA 包装器：[`tools/rea.sh`](../../../tools/rea.sh)
- 相关截图：`.artifacts/screens/NOSTATUS-lock-*.png`、`.artifacts/screens/T0-cc-*.png`、`.artifacts/screens/T_1-cc-*.png`

---

## 8. 一句话结论

> **Nugget 的“只改名称”依赖旧版逐字段 override flags；iOS 27 的 `STStatusBarDataCellularEntry` 是原子对象，运行时也没有隐藏 flags。`WirelessDomain` 备份注入已被证伪且会把设备置入 Setup Assistant；非越狱边界内目前没有可用的“只改名称、其余全 live”方案。**
