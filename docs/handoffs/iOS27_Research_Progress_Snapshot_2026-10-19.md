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

## 3. 新的关键观察（待控制实验确认）

本轮 `ZZTEST9` 部署时指定 `-b 3 -t lte`，但锁屏右上角的蜂窝指示器仍显示 **4 点（满格）**。这提示：

- 锁屏状态栏的蜂窝指示器**可能并不消费 archive 里的 `displayValue`**，而是继续使用实时遥测域数据；
- 若属实，则“显示域改名 + 锁屏真实信号”在 iOS 27 上**可能已经部分成立**，剩下的问题只在飞行模式常驻与 Control Center 模块。

必须用控制实验确认（而不是从单张截图推断）：

1. 部署 `-b 1` / `-b 0` 的 archive，respring，锁屏截图对比蜂窝指示器；
2. Control Center 打开后再截图，比较锁屏与 CC 两个渲染面；
3. 若锁屏为真实信号而 CC 为固定值，则说明两个渲染面走不同数据源，需要分别对待。

---

## 4. 下一步实验与逆向清单

### A. 显示域部分覆写（优先）
1. **控制实验**：`-b 0/1/3` 三组 archive，分别截锁屏与 CC，确认 `displayValue` 在哪些渲染面生效。
2. **部分 entry 实验**：archive 中只写 `string` + `enabled=true` + `status=5`，省略 `displayValue`/`type`，观察锁屏与 CC 是 0 格、隐藏还是回退实时。
3. **Sentinel 实验**：尝试 `displayValue = -1 / 255 / 0xFFFF` 等特殊值，观察是否被 UI 解释为“未覆写”。
4. **归档器合并语义**：复核 `-[_SBSystemStatusStatusBarOverridesArchiveRecord recordByApplyingRecord:]` 与 `-[SBSystemStatusStatusBarOverridesArchiver _queue_setupObservingAndReconcileInitialState]`，确认磁盘记录与实时覆写记录的合并顺序，以及是否能保留实时字段。
5. **类结构核对**：对 iOS 27 的 `STStatusBarDataCellularEntry` / `STStatusBarData` 做运行时 ivar 枚举（模拟器 `simctl spawn` 小工具或 dsc 提取），确认是否存在 `flags/override` 类字段或“未设置”哨兵。

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
