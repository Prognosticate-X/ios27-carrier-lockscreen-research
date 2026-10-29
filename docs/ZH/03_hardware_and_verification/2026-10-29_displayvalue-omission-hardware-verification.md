# iPhone 14 Pro 实机验证报告：`displayValue` 省略（GoldenNugget `0fe4d303`）vs `displayValue=4` 的真相

**文档编号**：`DOC-20261029-DISPLAYVALUE-VERIFICATION`  
**验证日期**：2026-10-29  
**验证设备**：iPhone 14 Pro（`iPhone15,2`，UDID: `00008120-000934CA3E60C01E`）/ iOS `27.0.1`（Build `24A446`）  
**关联文档**：[2026-10-29 非 StatusBarOverrides 路径全量逆向](../../02_reverse_engineering/2026-10-29_rea-alternative-paths-analysis.md) · [2026-10-28 “只改名称、其余全实时”路线研究](../../04_research_handoffs/2026-10-28_name-only-live-override.md)

---

## 1. 背景：为什么要对“省略 `displayValue`”进行实机自动化验证？

在检索社区同源仓库时，我们注意到 `awesomenull-dev/GoldenNugget` 的 Commit `0fe4d303`（*"Remove cellular bars override from status bar"*）声称：只需从 `STStatusBarDataCellularEntry` 序列化字典中删除 `displayValue` 键（仅保留 `status = 5, type = 10, string = ...`），即可移除状态栏信号格覆写，使信号格数回退至真实基带实时跳动。此前本仓库的 `--partial` 实验记录中也曾将省略 `displayValue` 记为“实时信号格”。

为严格验证该假设在真实 iOS 27 硬件上的表现，我们在连接的 **iPhone 14 Pro（iOS 27.0.1 `24A446`）** 上执行了全流程自动化部署、字节级回读校验与同机 AB 对照截图。

---

## 2. 自动化实机验证流水线

1. **安全护栏与环境就绪**：
   - 预检 [`safety.json`](../../../safety.json) 黑名单，确保主力机（iPhone 16 Pro Max / iPhone 17 Pro Max）100% 物理隔离。
   - 自动开启测试机开发者模式（`pymobiledevice3 amfi enable-developer-mode`）并挂载 DDI 调试镜像。
2. **字节级落盘回读校验（Byte-for-Byte Readback）**：
   - 使用 [`tools/airlift_carrier_deploy.py`](../../../tools/airlift_carrier_deploy.py) 与 [`tools/airlift_archive_replace.py`](../../../tools/airlift_archive_replace.py) 将生成的归档写入 `/var/mobile/Library/SpringBoard/StatusBarOverrides.archive`。
   - 从真机逆向回读已落盘文件，确认与本地生成归档 **`961 bytes == 961 bytes`（100% 字节级一致）**。
3. **双守护进程原子刷新与 UI 自动采集**：
   - 执行 `SIGSTOP SpringBoard -> SIGKILL systemstatusd -> SIGKILL SpringBoard` 彻底清除 `systemstatusd` 内存旧缓存。
   - 通过 [`tools/device_ui.py`](../../../tools/device_ui.py) 自动唤醒锁屏、下拉打开控制中心并采集高清实机截图。

---

## 3. 真机实测结果：证伪 GoldenNugget `0fe4d303` 的“实时信号栏”假设

![displayValue 实机对比图](../../../assets/ios27_displayvalue_verification_20261029.png)

### 3.1 为什么省略 `displayValue` 会导致顶部状态栏变成 `0` 格灰条？

1. **对象级原子替换**：
   SpringBoard 的 `-[STStatusBarData dataByApplyingOverlay:]`（`0x20e4ac960`）以整个 `STStatusBarDataCellularEntry` 对象指针为单位做替换，不存在逐字段合并。
2. **`NSCoder` 反序列化默认返回 `0`**：
   当归档中省略 `displayValue` 键时，`-[STStatusBarDataIntegerEntry initWithCoder:]` 调用 `-[NSCoder decodeIntegerForKey:@"displayValue"]`。在 Objective-C 的 `NSKeyedUnarchiver` 中，当目标键不存在时，**该方法不会读取真实基带信号，而是直接返回整数默认值 `0`**！
3. **视觉混淆的真正来源（顶部状态栏 vs 控制中心绿色蜂窝按钮）**：
   - **顶部状态栏（锁屏右上角 & 控制中心左上角 `中国移动 5G` 旁）**：读取的是 `STStatusBarDataCellularEntry.displayValue`。省略 `displayValue` 时，此处永远锁死为 **`0` 格全灰空心条**；设为 `displayValue = 4` 时，此处永远固定显示 **`4` 格纯白满格条**。
   - **控制中心连接卡片内的「绿色圆形蜂窝数据开关图标」**：该按钮**不走 `StatusBarOverrides` 通道**，而是直接向 `CoreTelephony` 查询真实基带信号强度。在实测截图中，无论 `displayValue` 是省略还是设为 `4`，该绿色按钮始终实时显示当时室内真实的 **`2` 格亮白 + `2` 格暗灰**信号！
   - **结论**：社区测试者之所以误以为省略 `displayValue`（或开启 `--partial`）能让状态栏变成“实时信号条”，是因为将控制中心绿色蜂窝开关上的实时 `2` 格信号误判成了状态栏覆写回退结果，而忽略了顶部状态栏本身已被锁死为 `0` 格灰条。

---

## 4. 修正后的三种模式真机实测对照表

| 方案对比 | 自定义运营商名 | 顶部状态栏信号条（右上角 / 控制中心左上角） | 控制中心「绿色蜂窝按钮」图标 | `5G` / `LTE` 图标显示 | 原生 VPN 动态徽标 | 适用场景与结论 |
| :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| **默认满格模式**<br>(`bars=4, type=5g`) | ✅ | ❌ **固定 4 格满格白条**<br>（非真实） | ✅ **真实实时信号**<br>（实测显示真实 2 格） | ✅（显示 `5G`） | ✅（省略 `vpnEntry`） | **推荐生产默认**：顶部状态栏保持满格美观，查看真实信号可下拉看绿色蜂窝图标 |
| **省略 `displayValue` 模式**<br>(`--bars omit` / GoldenNugget `0fe4d303`) | ✅ | ❌ **固定 0 格全灰空心条**<br>（被解码为 `0`，非实时！） | ✅ **真实实时信号**<br>（实测显示真实 2 格） | ✅（显示 `5G`） | ✅（省略 `vpnEntry`） | **不推荐日常使用**：顶部状态栏始终显示 0 格无信号灰条 |
| **`--partial` 模式**<br>(`partial=True`) | ✅ | ❌ **固定 0 格全灰空心条**<br>（同样被解码为 `0`） | ✅ **真实实时信号**<br>（实测显示真实 2 格） | ❌（`5G` 消失） | ✅（省略 `vpnEntry`） | **不推荐日常使用**：顶部状态栏为 0 格灰条且丢失 `5G`/`LTE` 角标 |

---

## 5. 工具链最终校准

基于上述 iPhone 14 Pro 实机铁证，本仓库工具链已完成如下校准：
- [`tools/generate_statusbar_archive.py`](../../../tools/generate_statusbar_archive.py) 与 [`tools/airlift_carrier_deploy.py`](../../../tools/airlift_carrier_deploy.py)：默认恢复为 `primary_bars=4`（`displayValue = 4` + `type = 10`），确保顶部状态栏正常点亮 4 格白条；同时保留 `--bars omit` 供研究人员复现 `displayValue` 省略行为。
- [`tools/gui_server.py`](../../../tools/gui_server.py)：Web 控制台默认选中 `4 格 (默认满格)`，并将 `省略 displayValue (实测0格)` 标注说明置于选项底部。
