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

## 3.1 为什么锁屏能保持实时信号（新假设）

锁屏渲染面在视图层把“信号强度”和“运营商字符串”拆开了：信号取实时 `STTelephonyStatusDomain`，字符串取 `STStatusBarOverridesStatusDomain`。这与 UIKitCore 层“整 entry 原子替换”的结论并不矛盾——原子替换发生在 **overrides 域内部**，而锁屏的蜂窝信号视图可能绑定的是实时域。

这意味着下一步的关键问题是：**字符串的显隐是否可以绑定到实时蜂窝状态**，从而在飞行模式下自动隐藏，而不影响信号/网络类型。

## 4. 下一步实验与逆向清单

### A. 显示域部分覆写（优先）
1. ~~控制实验：`-b 0/1/3` 确认 `displayValue` 生效面~~ → 已完成：锁屏不生效（实时），CC 生效（覆写）。
2. **部分 entry 实验**：archive 中只写 `string` + `enabled=true` + `status=5`，省略 `displayValue`/`type`，观察锁屏与 CC 是 0 格、隐藏还是回退实时。
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