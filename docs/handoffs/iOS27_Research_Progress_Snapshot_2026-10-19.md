# iOS 27 运营商显示域研究进度快照（2026-10-19）

- 设备：iPhone 14 Pro（iPhone15,2）/ iOS 27.0.1（24A446）/ USB
- 当前 HEAD：`42b3c91`（研究结论）；此前 `97475c4`、`09bc5e5`、`a7a50d9`
- 设备状态：无静态覆写，锁屏原生 `中国联通`；12 个实验域已写回空字典；USB 正常

---

## 1. 本轮已经确认的事实

1. **CommCenter 数据模型（备份取证）**
   - 本机 PLMN `46001`（`LastKnownServingMcc=460`、`Mnc=1`、`CarrierBundleName='46001'`）。
   - CommCenter 的持久化状态全部在 `WirelessDomain`（`/var/wireless/Library/Preferences/com.apple.commcenter.*`）。
   - 整个 17,511 行备份清单中不存在 `com.apple.operator_1` / `com.apple.carrier_1` 偏好域；`com.apple.commcenter.plist` 里的 `com.apple.carrier_1` 只是字符串 `'46001'`。
   - 运营商显示名的数据源是已签名系统 bundle `/System/Library/Carrier Bundles/iPhone/46001/carrier.plist`。
   - 结论：**数据源层（CommCenter）在非越狱/mobile 上下文中不可写**；HomeDomain 偏好注入无效。

2. **显示域（StatusBarOverrides）通道**
   - AirLift 可写 `/var/mobile/Library/SpringBoard/StatusBarOverrides.archive`；探针名 `ZZTEST9` 成功显示在锁屏。
   - 仅重启 SpringBoard 不能清除已被系统采纳的覆写；用户空间/整机重启可以。
   - 通过 CoreDevice `send-signal-to-process` 可在不重启整机的情况下冷启动 cfprefsd / CommCenter / SpringBoard。

3. **工具与文档**
   - `tools/commcenter_carrier_inject.py`、`tools/device_path_probe.py`、`tools/device_ui.py`、`tools/commcenter_preference_builder.py`。
   - 17 项离线单测全部通过。
   - 交接文档：`docs/handoffs/iOS27_CommCenter_Preference_Injection_2026-10-19.md`。

---

## 2. 重要修正：研究方向一直是“显示域”，旧版 Nugget 并非天生静态

此前文档（以及上一轮口头结论）把“静态”当成 Nugget 方案的本质，这个表述不准确。正确的时间线是：

| 版本 | 覆写载体 | 覆盖粒度 | 不修改信号格时 | 飞行模式 |
|---|---|---|---|---|
| iOS ≤ 16（旧 Nugget/Cowabunga） | `statusBarOverrides`（3944 字节 `StatusBarOverrideData` C 结构体） | **逐字段 override flags**（只置位要覆盖的字段） | **真实信号格**（未置位的字段继续取实时数据） | 运营商名随蜂窝条目消失，不会常驻 |
| iOS 17+/27（现代 archive） | `StatusBarOverrides.archive`（`NSKeyedArchiver` → `STStatusBarData`） | **整个 `STStatusBarDataCellularEntry` 对象替换** | 若写入完整 entry，则信号格被固定；缺省字段解码为 0/NO | `enabled/status` 被钉死，可能常驻 |

因此：

- **“显示域覆盖”本身不是问题**；问题是 iOS 27 把“逐字段覆写”换成了“整 entry 覆写”，丢掉了旧版的字段级回退语义。
- 我们要找的是：**iOS 27 的显示域里是否还存在等价的“部分覆写”入口**（archive 层、SpringBoard 归档器层、或 SystemStatus 合并层）。

---

## 3. 控制实验结果（BARS1，2026-10-19 15:26–15:31）

部署 `-c BARS1 -b 1 -t lte`（`displayValue=1`、`type=LTE`）后，respring，分别观察锁屏、Control Center、飞行模式：

| 渲染面 | 运营商名 | 信号指示 |
|---|---|---|
| 锁屏 | `BARS1` | **4 点（满格，实时值）** —— `displayValue=1` **未生效** |
| Control Center | `BARS1 LTE+` | **1 格** —— `displayValue=1` **生效** |
| 飞行模式：锁屏 | `BARS1` + ✈ | 蜂窝指示消失，但 **名称仍常驻** |
| 飞行模式：CC | ✈ `BARS1` | 信号格消失，但 **名称仍常驻** |

结论：

1. **锁屏的蜂窝信号指示器不消费 archive 的 `displayValue`**，而是继续使用实时遥测数据；Control Center 则消费覆写 entry（1 格、`LTE+`）。
   这修正了此前“信号格在所有渲染面都被钉死”的说法：至少在 iPhone 14 Pro / 27.0.1 上，**锁屏=实时信号，CC=覆写值**。
2. **飞行模式下运营商名仍然常驻**（锁屏与 CC 都是）。原因是覆写 entry 把 `enabled/status` 钉成了“已连接”，而名称的显隐并不跟随实时蜂窝状态。
3. 因此用户记忆中的旧版 Nugget 行为在 iOS 27 上**只复现了一半**：
   - ✅ 锁屏真实信号格（旧版：未覆盖字段透传）；
   - ❌ 飞行模式不常驻（旧版：名称随蜂窝条目消失；现代 archive 不会）。

### 3.2 `5G` 制式文字跟随蜂窝数据开关（2026-10-19 15:40 实测）

CC 顶部 `中国联通 5G` 与 Wi-Fi 同时出现的原因**不是归档覆写**，而是蜂窝数据开关处于打开状态（连接模块中的蜂窝图标为绿色）：

- 蜂窝数据 **开**：`中国联通 5G` + Wi-Fi 图标（制式文字显示）；
- 蜂窝数据 **关**：`中国联通` + Wi-Fi 图标（制式文字消失）；
- 重新打开：`5G` 回来。

佐证：当前磁盘上的 `StatusBarOverrides.archive` 是 **429 字节的空 reset 记录**（`statusBarData` 为空），通过 SpringBoard 过滤备份提取并解码确认，没有钉住任何字段。

另外，**状态栏（锁屏）**在 Wi-Fi 连接时不显示制式文字；**Control Center** 在蜂窝数据开启时会显示。此前把该现象归因于覆写残留是不准确的。

## 3.0 部分 entry 突破：自定义名称 + 实时信号（15:50–15:53）

在解决“写回竞争”后，成功实测了**部分 entry**（只写部分字段）的语义：

| 变体 | entry 字段 | 锁屏 | Control Center |
|---|---|---|---|
| **V4** | `string` + `enabled=true` + `status=5`，**省略 `displayValue`/`type`** | **V4 + 实时 4 点** | **V4 + 实时 4 格，无制式文字** |
| V5 | 只有 `string`/`crossfadeString` | 名称消失 | 名称消失 |
| V6 | `string` + `enabled=true`，省略 `status` | 名称消失 | 名称消失 |
| V7 | `string` + `enabled=true` + `status=-1`（哨兵） | 名称消失 | — |

关键发现：

1. **`displayValue` 缺失时回退实时**：SpringBoard 把缺失字段解码为 0 并写回完整记录（1078B，`displayValue=0, type=0`），但 UI 显示的仍是**实时 4 格**。也就是说 `displayValue=0` 被当成“无覆写/实时”，而不是 0 格。
2. **`type` 缺失时制式文字被抑制**：CC 不再显示 `5G/LTE`，也不会回退成实时制式（与 bars 不同）。
3. **名称渲染必须 `enabled=true` 且 `status=5`**：缺 `enabled`（V5）或 `status`（V6）都会让名称完全消失；`status=-1` 也不行（无哨兵）。
4. 因此现阶段可达到的最优组合是：**自定义名称 + 真实信号格（锁屏与 CC 均实时）+ CC 无制式文字**；但 `status=5` 是静态的，所以**飞行模式下名称仍常驻**。

### 3.0.1 新增的实机原语（重要）

1. **归档移出（读+删）**：AirTraffic `FileComplete` 的 source 可以是媒体目录之外的相对路径——`../../../Library/SpringBoard/StatusBarOverrides.archive` 会被 ATAirlock 解析为真实归档路径，并移动到 Media。移动后即可通过 AFC **读取归档内容和删除它**（目标变为 `status=8`）。
2. **单会话原子替换**：在同一次 `airtraffic_host` 调用里依次派发 ①旧归档移出 ②软链移入 ③新 payload 移入，把“目标消失→新文件写入”的窗口压到约 1 秒。工具：`tools/airlift_archive_replace.py`。
3. **击穿实时域缓存**：只替换磁盘归档不够——`systemstatusd` 的实时覆写域会通过 `diskRecord recordByApplyingRecord:liveRecord`（live 优先）把旧记录盖回来。必须先 `SIGSTOP` SpringBoard、`SIGKILL` `systemstatusd`，完成替换后再 `SIGKILL` SpringBoard，才能让新的部分 entry 生效。
4. **`recordByApplyingRecord:` 反汇编确认**（模拟器 SpringBoard，`0x5b5b50`）：实现就是 `[statusBarData dataByApplyingOverlay:other.statusBarData]`，即 **entry 级原子合并**；`isEmpty`（`0x5b5b08`）= `statusBarData.isEmpty` 且 suppressed 集合为空。

### 3.0.3b SystemStatusUI 反汇编：名称显隐的精确条件（16:18）

`STUIStatusBarCellularItem`（SystemStatusUI，独立 2.1MB 二进制）关键逻辑：

- `applyUpdate:toDisplayItem:`（`0x2c1c`）的 name 分支（`0x3024`）：
  `if (displayItem.isEnabled && entry.string.length > 0 && !entry.isBootstrapCellular) { [serviceNameView setText:entry.string]; [serviceNameView setAlternateText:entry.crossfadeString]; } else { displayItem.enabled = NO; }`
- `_signalViewShouldBeEnabledForEntry:forceShowingDisabledSignalBars:signalMode:`（`0x2aa8`）的信号谓词：
  - `status == 0` → 禁用；
  - `status == 1` → 仅当 force/showsDisabledSignalBars 时启用；
  - `status == 2` → 启用（signalMode 0）；
  - `status == 3` → 启用（signalMode 1）；
  - `status == 4` → 禁用；
  - `status == 5` → 启用（signalMode 2，若传入 signalMode 指针）；
  - `isBootstrapCellular` 时只有 `status == 5` 才启用。

实测补充：status=2 仍然**不显示名称**（S2），而 status=5 显示（V4）。因此 name 分支依赖的 `displayItem.isEnabled` 在上游比信号谓词更严格——实际只有“已注册”（status=5）才会启用名称显示项。status=0/1/2/-1 全部隐藏名称。

### 3.0.3 `status` 取值矩阵结论（16:13）

| `status` | 名称显示 |
|---|---|
| **5** | ✅ 显示（V4） |
| 0（缺失） | ❌ 不显示 |
| 1 | ❌ 不显示（S1 实测） |
| -1 | ❌ 不显示（V7 哨兵实测） |

因此 **carrier string 的渲染实际只在 `status=5`（已注册）时成立**（status=2 也不显示，说明名称显示项的 enabled 由上游注册状态决定）。`status` 是静态写入的字段，没有任何“跟随实时蜂窝状态”的哨兵或回退入口。

结论：

- **静态归档能做到**：自定义运营商名 + 锁屏/CC 实时信号格（`displayValue` 省略）+ CC 无制式文字（`type` 省略）。
- **静态归档做不到**：飞行模式下自动隐藏名称（必须钉死 `status=5`，条目永远被视为“已连接”）。
- 若未来要实现真正的飞行模式联动，只能在运行期动态发布 `STStatusBarOverridesStatusDomain`（tweak/注入），或者修改数据源层（本次已验证不可写）。

### 3.0.2 归档器合并/写回逻辑（objdump 已完整还原）

`-[SBSystemStatusStatusBarOverridesArchiver _queue_setupObservingAndReconcileInitialState]`（`0x5b50d4`，模拟器 SpringBoard）的实际流程：

1. `live = [self._overridesDomain data]._sbSystemStatusStatusBarOverridesArchiveRecord`（**实时覆写域**记录）
2. `disk = [self _queue_readStatusBarOverridesArchiveRecord]`（磁盘归档记录）
3. 两者都存在时：`merged = [disk recordByApplyingRecord:live]` → `[self _queue_writeOutArchiveRecord:merged]` → 发布 `merged`。
   - `recordByApplyingRecord:` 内部是 `[self.statusBarData dataByApplyingOverlay:other.statusBarData]`（`0x5b5b50`），**entry 级原子合并**，且 **live 覆盖 disk**。
4. 只有 live：`_queue_writeOutArchiveRecord:live` → 发布。
5. 只有 disk：直接发布 disk，**不调用 writeOut**。

`_queue_writeOutArchiveRecord:`（`0x5b53e4`）：

- `record == nil || [record isEmpty]` → `[[NSFileManager defaultManager] removeItemAtURL:_archiveFileURL error:]`（自删）；
- 否则 → `archivedDataWithRootObject:requiringSecureCoding:` 后 `writeToURL:options:`。

Hopper 伪代码补充确认（`_queue_readStatusBarOverridesArchiveRecord` / `initWithStatusBarData:`）：

- 读取时先尝试 `_SBSystemStatusStatusBarOverridesArchiveRecord`；失败则**回退旧格式** `STStatusBarData`；仍失败才返回 nil。
- `initWithStatusBarData:andSuppressedBackgroundActivityIdentifiers:` 在 `[record isEmpty]` 时**直接返回 nil**（并打日志 "is empty!"）。因此空 reset 归档在读取阶段就变成 nil，等价于“没有磁盘记录”，后面自然不会触发 writeOut/自删。
- `_queue_writeOutArchiveRecord:` 先做 `BSEqualObjects` 去重；只有记录为 nil/空才 `removeItemAtURL:`。
- `_queue_persistUpdatedArchiveRecord:` 同样先去重，再写盘。

这解释了本轮遇到的所有现象：

- **为什么空 reset 归档一直留在磁盘**：启动时只有 disk 记录（空），走“只有 disk”分支，直接发布、不 writeOut，所以不会触发自删。
- **为什么新归档被覆盖回旧值**：`systemstatusd` 的 live 域里仍有旧记录，合并时 live 优先，随后 writeOut 把旧记录写回磁盘。
- **为什么必须“冻结 SpringBoard + 杀 systemstatusd + 替换 + 杀 SpringBoard”**：只有让 live 域为空、并让 SpringBoard 重新启动，才能让磁盘上的新记录（部分 entry）成为权威来源。

### 3.0.2 仍未解决

- 飞行模式联动：`status=5` 必须静态写入才能渲染名称，静态归档没有“跟随实时状态”的入口。
- 需要进一步确认 `status` 的取值语义（1–4）以及 SystemStatusUI 对 `string` 显隐的判定，看是否存在能跟随实时蜂窝状态的组合；若不存在，则飞行模式联动只能依赖运行期动态发布（tweak/注入），超出当前非越狱能力。

## 3.1 为什么锁屏能保持实时信号（新假设）

锁屏渲染面在视图层把“信号强度”和“运营商字符串”拆开了：信号取实时 `STTelephonyStatusDomain`，字符串取 `STStatusBarOverridesStatusDomain`。这与 UIKitCore 层“整 entry 原子替换”的结论并不矛盾——原子替换发生在 **overrides 域内部**，而锁屏的蜂窝信号视图可能绑定的是实时域。

这意味着下一步的关键问题是：**字符串的显隐是否可以绑定到实时蜂窝状态**，从而在飞行模式下自动隐藏，而不影响信号/网络类型。

## 4. 下一步实验与逆向清单

### A. 显示域部分覆写（优先）
1. `控制实验：`-b 0/1/3` 确认 `displayValue` 生效面` → 已完成：锁屏不生效（实时），CC 生效（覆写）。
2. `部分 entry 实验` → 已完成并产品化：CLI `--partial`、独立生成器 `--partial`、GUI「保留实时信号格（部分覆写）」复选框。
3. **状态取值实验**：枚举 `enabled/status` 组合（true/5、true/0、false/0、省略），确认字符串显隐是否跟随实时蜂窝状态，寻找“飞行模式自动隐藏”的组合。
4. **Sentinel 实验**：尝试 `displayValue = -1 / 255 / 0xFFFF` 等特殊值，观察是否被 UI 解释为“未覆写”。
5. **归档器合并语义**：复核 `-[_SBSystemStatusStatusBarOverridesArchiveRecord recordByApplyingRecord:]` 与 `-[SBSystemStatusStatusBarOverridesArchiver _queue_setupObservingAndReconcileInitialState]`，确认磁盘记录与实时覆写记录的合并顺序，以及是否能保留实时字段。
6. **类结构核对**：对 iOS 27 的 `STStatusBarDataCellularEntry` / `STStatusBarData` 做运行时 ivar 枚举（模拟器 `simctl spawn` 小工具或 dsc 提取），确认是否存在 `flags/override` 类字段或“未设置”哨兵。

### B. 飞行模式联动
1. 若锁屏/CC 的信号为实时，但运营商名在飞行模式下常驻，则需要找到让 `cellularEntry` 在蜂窝关闭时不被发布的方式；
2. 观察 `enabled/status` 的取值组合（true/5、false/0、省略等）对飞行模式渲染的影响；
3. 结合 `systemstatusd` 的发布时序（是否在蜂窝关闭时重新发布覆写域）。

### C. 若 A/B 均失败
- 保持现状结论：iOS 27 的显示域覆写在 `STStatusBarData` 层级是整对象替换，无法恢复旧版逐字段语义；数据源层不可写。
- 静态方案作为唯一可用交付，并在 README 中明确“锁屏/CC 渲染面差异”的实测结论。

---

## 5. 复现命令

```bash
# 编译 AirLift 原生 helper
cd airlift && make && cd ..

# 部署指定信号格 + 名称（锁屏/CC 对比实验）
python3 tools/airlift_carrier_deploy.py --device 00008120-000934CA3E60C01E \
  -c "BARS1" -b 1 -t lte

# 唤醒 + 截图（锁屏）
python3 tools/device_ui.py screenshot .artifacts/screens/bars1_lock.png

# 打开控制中心再截图
python3 tools/device_ui.py open-cc
python3 tools/device_ui.py screenshot .artifacts/screens/bars1_cc.png

# 恢复原生
python3 tools/airlift_carrier_deploy.py --device 00008120-000934CA3E60C01E --reset
xcrun devicectl device reboot --device 00008120-000934CA3E60C01E --style userspace
```

---

## 6. 交付状态（2026-10-19 收尾）

- `--partial` 已实现于 `tools/airlift_carrier_deploy.py`、`airlift/airlift_carrier_deploy.py`、`tools/generate_statusbar_archive.py`；
- GUI 新增中英双语「保留实时信号格（部分覆写）」复选框（请求字段 `partial`，后端透传到归档生成器）；
- 单测 18 项全部通过（新增 partial archive 字段断言）；
- README / README_ZH / 研究状态已更新推荐配置、GUI 用法与飞行模式限制说明。

### 3.0.4 控制中心“5G + Wi-Fi 并排”是原生行为（16:43 验证）

- 从设备取出当时磁盘上的归档：内容为 **S2**（`status=2` 的部分 entry），但它并未生效（生效时名称应为 S2）。
- 移除该归档并重启 SpringBoard 后，锁屏显示 `中国联通` + Wi-Fi，**无 5G/LTE**；控制中心状态栏仍显示 `中国联通 5G` + Wi-Fi，且制式在两次截图间由 4G 变为 5G（实时值）。
- 结论：iOS 27 的控制中心状态栏原生就同时渲染“运营商 + 实时制式 + Wi-Fi”；锁屏/主屏状态栏只显示运营商 + Wi-Fi。全量 entry 会把 `type` 钉死，`--partial` 省略 `type` 后制式文字被抑制（不是回退实时）。
