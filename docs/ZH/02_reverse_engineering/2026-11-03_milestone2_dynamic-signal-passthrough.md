# Milestone 2：iOS 27 蜂窝状态数据流全链路逆向报告与动态信号穿透分析

**文档编号**：`DOC-20261103-MILESTONE2-DYNAMIC-SIGNAL`  
**更新日期**：2026-11-03  
**基线版本**：iOS 27.0 (Build 24A434 / 24A437) / iOS 27.0.1 (Build 24A446)  
**硬件验证平台**：iPhone 14 Pro (iPhone15,2)、iPhone 16 Pro Max (iPhone17,2)、iPhone 18 Pro (模拟器)  
**文档状态**：Definitive Conclusion / Milestone Completed  
**密级**：Public Research / Open Source

---

## 0. 执行摘要与核心结论 (Executive Summary)

在 iOS 26 及更早版本中，社区工具（如 Nugget）能够实现**“只修改运营商名称，而信号格数、网络制式（5G/LTE）与飞行模式联动完全保持原生实时”**。在 iOS 27 发布后，大量用户与开发者在社区（包括上游 GoldenNugget、Nugget 及本项目 Issue #2）反馈：**一旦通过归档覆盖运营商名称，实时信号格与网络制式即被静态冻结**。

本项目作为 Milestone 2 核心攻坚任务，基于 **Ghidra 反汇编（299+ SystemStatusServer 函数、84+ SystemStatusUI 函数）**、运行时 Objective-C 内存反射、以及在 iPhone 14 Pro 物理机上的反复硬件闭环验证，得出了**确定性、不可逆的技术结论**：

```
                    [ 核心结论矩阵 (Milestone 2 Final Verdict) ]

┌────────────────────────────┬──────────────────┬────────────────────────────────────────────────────────┐
│ 目标体验                   │ 非越狱可行性     │ 根本技术瓶颈与证据                                     │
├────────────────────────────┼──────────────────┼────────────────────────────────────────────────────────┤
│ 自定义运营商名称 (单/双卡) │ 🟢 100% 可行     │ StatusBarOverrides.archive (已并入 GoldenNugget)       │
│ 原生实时 VPN 图标穿透      │ 🟢 100% 解决     │ suppressedBackgroundActivityIdentifiers=[] 干净透传   │
│ 锁屏监管脚注定制           │ 🟢 100% 可行     │ SharedDeviceConfiguration.plist 原生 MDM 通道          │
│ 静态 5G / LTE 徽标指定     │ 🟢 100% 可行     │ STStatusBarDataCellularEntry.type 指定标量 (10=5G)     │
├────────────────────────────┼──────────────────┼────────────────────────────────────────────────────────┤
│ 只改名称 + 实时信号格穿透  │ 🔴 架构级锁死    │ -[STStatusBarData dataByApplyingOverlay:] 为整块替换； │
│                            │ (非越狱不可达)   │ 缺省 displayValue 解码为 0，导致顶栏锁死 0 格全灰。    │
│ 飞行模式动态联动隐藏       │ 🔴 架构级锁死    │ 状态栏名称门控仅读覆写对象自身，不读实时 Telephony 域。│
│ 绕道注入 /var/wireless     │ 🔴 致命高危      │ BackupAgent2 拦截；触发 Setup.app 欢迎页恢复循环。    │
│ 篡改 Carrier Bundle 签名   │ 🔴 签名强校验    │ CommCenter DER 签名校验失败直接报 No Service 无服务。  │
└────────────────────────────┴──────────────────┴────────────────────────────────────────────────────────┘
```

> [!IMPORTANT]
> **结论定性**：在非越狱前提下，iOS 27 的现代状态栏架构已经**彻底废弃了带逐字段掩码的 C 结构体（`StatusBarOverrideData`）**，全面转向面向对象的 `STStatusBarData` 树形结构。**“只改名称、信号与制式完全动态”在下游覆写层（Downstream Overlay）架构上已被完全锁死。**  
> 生产环境下的最佳实践是采用由本项目制定的 **“4 格满格常亮 + 指定 5G + VPN 干净透传”** 稳定方案。

---

## 1. iOS 27 蜂窝状态数据流全景图谱 (Full-Chain Data Flow)

通过对 iOS 27 共享缓存库（`dyld_shared_cache`）中 `CoreTelephony`、`SystemStatus`、`SystemStatusServer`、`SpringBoard` 及 `CommCenter` 二进制文件的深入反编译，整理出从基带物理硬件到屏幕像素绘制的完整信号传递图谱：

```text
+--------------------------------------------------------------------------------------------------+
|                                    1. 物理层与基带固件 (Baseband)                                |
|   - 物理 SIM / eSIM 硬件芯片 (读取 EF_SPN 服务商名称 / EF_PNN PLMN 名称)                         |
|   - 基带调制解调器 (Qualcomm Snapdragon X75 / Apple Baseband Processor)                          |
|   - 实时测量射频指标: RSRP, RSRQ, SINR -> 计算实时蜂窝信号格数 (0-4 格)                          |
+-------------------------------------------------+------------------------------------------------+
                                                  |
                                                  | QMI (Qualcomm MSM Interface) / PCIe IPC 消息
                                                  v
+--------------------------------------------------------------------------------------------------+
|                                  2. CommCenter 根守护进程 (UID 25)                               |
|   - 进程路径: /System/Library/Frameworks/CoreTelephony.framework/Support/CommCenter              |
|   - 运行权限: UID 25 (_wireless), GID 25 (_wireless), 拥有受保护的 /var/wireless 专有沙盒        |
|   - 状态机职责: 管理移动网络注册、漫游控制、APN 建立                                             |
|   - 核心屏障: 强制校验 Carrier Bundle (/System/Library/Carrier Bundles/) 的 Apple DER 数字签名   |
+-------------------------------------------------+------------------------------------------------+
                                                  |
                                                  | Mach Message / XPC (CTXPCGetOperatorNameRequest)
                                                  v
+--------------------------------------------------------------------------------------------------+
|                                  3. CoreTelephony.framework                                      |
|   - 客户端接口库: CTTelephonyNetworkInfo, CTCarrier, CTSignalStrengthNotification                |
|   - 格式化运营商名: -[CTXPCGetOperatorNameResponse operatorName]                                |
|   - 下拉控制中心圆形蜂窝开关的绿色图标即直接通过该层实时查询基带                                 |
+-------------------------------------------------+------------------------------------------------+
                                                  |
                                                  | Mach XPC 广播 (com.apple.commcenter.xpc)
                                                  v
+--------------------------------------------------------------------------------------------------+
|                        4. SystemStatus Server 守护进程 (systemstatusd)                           |
|   - 进程路径: /usr/libexec/systemstatusd -> SystemStatusServer.framework                         |
|   - 核心提供者: STTelephonyStatusDomainDataProvider (反汇编包含 299 个方法)                      |
|   - 职责: 监听 CoreTelephony 信号变更，聚合双卡状态，构造 STTelephonyStatusDomainData 快照       |
|   - 发布管道: STStatusDomainPublisher.updateDataWithBlock: (需要 com.apple.systemstatus.publisher)|
+-------------------------------------------------+------------------------------------------------+
                                                  |
                                                  | XPC 分发通道 (com.apple.systemstatus.server)
                                                  v
+--------------------------------------------------------------------------------------------------+
|                              5. SpringBoard (状态栏合成与归档加载)                               |
|   - 订阅者: SBStatusBarStateAggregator / SBSystemStatusStatusBarOverridesListener                |
|   - 归档反序列化: _queue_readStatusBarOverridesArchiveRecord (读取 StatusBarOverrides.archive)   |
|   - 内存合成关键调用: -[STStatusBarData dataByApplyingOverlay:] (函数偏移 0x20e4ac960)            |
|     * 若存在覆写 entry，直接执行原子指针替换: result.cellularEntry = [overlay.cellularEntry copy]|
|     * 彻底丢失下游属性合并能力！                                                                 |
+-------------------------------------------------+------------------------------------------------+
                                                  |
                                                  | 传递合成后的最终 STStatusBarData
                                                  v
+--------------------------------------------------------------------------------------------------+
|                        6. SystemStatusUI.framework (视图消费与渲染层)                            |
|   - 渲染容器: STUIStatusBar (顶栏左右耳)、_UIStatusBarCellularItem (蜂窝组件)                    |
|   - 绘制实体:                                                                                    |
|     * _UIStatusBarSignalView: 绘制 4 根信号柱 (根据 entry.displayValue 决定点亮柱数)             |
|     * _UIStatusBarStringView: 绘制运营商文本 (读取 entry.string / entry.badgeString)             |
|     * _UIStatusBarCellularTypeView: 绘制 5G/LTE 徽标 (根据 entry.type 整数映射渲染)              |
+--------------------------------------------------------------------------------------------------+
```

---

## 2. 为什么“只改名称”在下游覆写层被锁死？（汇编级证明）

### 2.1 iOS 26 以前与 iOS 27 状态栏架构的代际本质差异

在 iOS 26 及之前，`SpringBoard` 内部使用 C 结构体维护覆盖状态：

```c
// iOS 26 及以前的 StatusBarOverrideData 内存模型 (C 结构体)
struct StatusBarOverrideData {
    uint32_t overrideFlags;          // 逐字段掩码: 0x01 = name, 0x02 = signal, 0x04 = type...
    char     serviceString[100];     // 运营商文字
    int      signalStrengthBars;     // 信号格数
    int      serviceType;            // 制式
    // ...
};
```
在旧模型中，Nugget 只需将 `overrideFlags` 的第 0 位（name 覆盖位）置 1，并向 `serviceString` 拷贝自定义文字，其余字段的 flag 保持为 0。`SpringBoard` 在合成时：
$$\text{RenderedField} = \text{Flag}_{\text{override}} \ ?\ \text{Value}_{\text{override}} : \text{Value}_{\text{live}}$$
因此，**旧系统原生支持字段级透传**。

而在 iOS 27 中，Apple 彻底重构了 `SystemStatus`，全面转向面向对象协议：
*   所有状态数据均封装在继承自 `STStatusBarDataEntry` 的 Objective-C 类中。
*   **没有任何 `overrideFlags` 或 `hasModifiedProperty` 掩码字段！**

### 2.2 `STStatusBarDataCellularEntry` 的完整 ivar 内存布局

通过在 iOS 27.0 运行时对 `STStatusBarDataCellularEntry` 进行类反射（`class_copyIvarList`），提取出其真实内存布局：

```text
================ STStatusBarDataCellularEntry 继承链与 ivar 列表 ================
STStatusBarDataEntry (基类)
  ├── _enabled                : BOOL     (状态栏项目是否整体启用)

STStatusBarDataNetworkEntry (网络基类)
  ├── _status                 : int64_t  (网络注册状态: 5=Registered, 0=None)
  └── _lowDataModeActive      : BOOL     (低数据模式)

STStatusBarDataIntegerEntry (数值基类)
  ├── _displayValue           : int64_t  (【关键】点亮的信号格数: 0-4)
  ├── _rawValue               : int64_t  (原始 RSSI 指标)
  └── _displayRawValue        : BOOL     (是否绘制原始数值)

STStatusBarDataCellularEntry (蜂窝专用条目)
  ├── _type                   : int64_t  (【关键】网络制式代码: 10=5G, 9=LTE, 0=空)
  ├── _string                 : NSString (【关键】运营商显示文字)
  ├── _crossfadeString        : NSString (交替轮播副标题)
  ├── _badgeString            : NSString (双卡标记: 'P' / 'S')
  ├── _suffixString           : NSString (后缀文字)
  ├── _wifiCallingEnabled     : BOOL     (Wi-Fi 通话)
  ├── _callForwardingEnabled  : BOOL     (呼叫转移)
  ├── _showsSOSWhenDisabled   : BOOL     (无服务时显示 SOS)
  ├── _sosAvailable           : BOOL     (SOS 是否可用)
  ├── _isBootstrapCellular    : BOOL     (引导期蜂窝: true 则强制隐藏名称)
  └── _numberSharingState     : int64_t  (一号双终端状态)
================================================================================
```

### 2.3 `-[STStatusBarData dataByApplyingOverlay:]` 汇编反编译

在 `SystemStatus.framework` 共享缓存镜像中定位到 `dataByApplyingOverlay:` 实现（位于偏移 `0x20e4ac960`），其反汇编核心逻辑如下：

```c
// 反汇编伪代码 (Ghidra Decompilation: -[STStatusBarData dataByApplyingOverlay:])
STStatusBarData * -[STStatusBarData dataByApplyingOverlay:](STStatusBarData *self, STStatusBarData *overlay) {
    STStatusBarData *result = [[STStatusBarData alloc] init];
    
    // 遍历每一个 entry 槽位
    // [1] 处理 cellularEntry (偏移 0x38)
    STStatusBarDataCellularEntry *overlayCellular = overlay->_cellularEntry;
    if (overlayCellular != nil) {
        // 发现覆盖层声明了 cellularEntry，执行整块对象深拷贝赋值！
        result->_cellularEntry = [overlayCellular copy];
    } else {
        // 覆盖层未声明，透传 live 对象的整个 entry
        result->_cellularEntry = [self->_cellularEntry copy];
    }

    // [2] 处理 secondaryCellularEntry (偏移 0x40)
    if (overlay->_secondaryCellularEntry != nil) {
        result->_secondaryCellularEntry = [overlay->_secondaryCellularEntry copy];
    } else {
        result->_secondaryCellularEntry = [self->_secondaryCellularEntry copy];
    }
    
    // [3] 处理 vpnEntry (偏移 0x68) ...
    return result;
}
```

> **结论证明**：  
> 合成逻辑是在**条目对象指针（Entry Object Pointer）级别**进行判定，**根本不存在字段级别的合并（Field-level Merging）代码**。  
> 只要在 `StatusBarOverrides.archive` 中注入了自定义运营商名称（必须实例化 `cellularEntry`），该 Entry 的所有属性（`displayValue`、`type`、`status`）就会**完整覆盖**掉 Baseband 实时上报的数据。

### 2.4 缺省 `displayValue` 导致“0 格全灰空心条”的机制推导

既然对象整体替换，那如果我们在构造 `NSKeyedArchiver` 时**故意不写入 `displayValue` 键**，系统能否从 live 回退？

实验与反汇编证实：**不能，而且会导致严重的显示异常。**

```c
// -[STStatusBarDataIntegerEntry initWithCoder:] 内部逻辑
- (instancetype)initWithCoder:(NSCoder *)coder {
    self = [super initWithCoder:coder];
    if (self) {
        // NSCoder 标准规范: 如果归档 plist 中不存在该 Key，返回 0！
        self->_displayValue = [coder decodeIntegerForKey:@"displayValue"]; // -> 返回 0
        self->_rawValue     = [coder decodeIntegerForKey:@"rawValue"];     // -> 返回 0
    }
    return self;
}
```
当 `displayValue` 缺省被解码为 `0` 时，渲染组件 `_UIStatusBarSignalView` 会严格按照 `numberOfActiveBars = 0` 进行渲染，表现为**顶栏出现 4 根全灰色的空心天线柱**，彻底锁死为 0 格。

*注：部分用户误以为缺省 `displayValue` 实现了“实时格”，是因为在下拉控制中心时，连接面板里的**绿色圆形蜂窝开关图标**由于直连 `CoreTelephony` 显示了实时格数，而屏幕顶部真正的状态栏早已经被冻结在 0 格。*

---

## 3. 非越狱旁路尝试的系统性实验与证伪记录

为了探索是否有其他上游注入路径能够绕过下游覆盖限制，我们对可能存在的所有非越狱旁路进行了逐一测试：

### 旁路一：MDM 描述文件注入 (`com.apple.cellular`)
*   **设计思路**：利用 Apple 官方 MDM（移动设备管理）的 `.mobileconfig` 描述文件，尝试通过未公开的 XML 键注入运营商显示名称。
*   **测试载荷**：在 `com.apple.cellular` 载荷中注入 `CarrierName`、`CarrierDisplayName`、`ServiceString`、`OperatorNameOverride`。
*   **实验结果**：**无效（IGNORING_UNKNOWN_KEYS）**。
*   **逆向归因**：
    `ManagedConfiguration.framework` 的配置文件解析器对 `com.apple.cellular` 维护了严格的白名单。仅处理 `APNs`、`DataRoaming`、`AttachAPN` 及 `eSIMActivationCode`。运营商的名称渲染被严格硬编码交由 `CoreTelephony` 根据 SIM 卡的 MCC/MNC 在内置 Carrier Bundles 中查找匹配，不接受外部传入的文字覆盖。

### 旁路二：AirTraffic / MobileBackup2 越界写 `/var/wireless`
*   **设计思路**：已知 CommCenter 读取 `/var/wireless/Library/Preferences/com.apple.operator_1.plist` 获取实时偏好。尝试构造针对 `WirelessDomain` 的备份恢复包，将自定义名称写入该目录。
*   **实机测试过程（2026-10-28 22:10 事故）**：
    在已关闭查找（Find My）的 iPhone 14 Pro 上，通过 `backup2 restore` 发送带有 `WirelessDomain/Library/Preferences/com.apple.operator_1.plist` 的备份。
*   **致命后果**：
    1.  目标文件**完全没有被写入**（重启后文件计数为 0）。
    2.  `BackupAgent2` 在恢复校验时触发沙箱越界警报，重置了部分初始化标记，导致测试机重启后直接跌入 **Setup Assistant（屏幕出现多国语言 "hej" 欢迎设置页）**，必须由人工重新激活引导。
*   **安全结论**：
    `/var/wireless` 属于 `UID 25 (_wireless)`，受到严格的数据保护沙箱（Data Vault）与系统完整性保护，**在非越狱环境下不可写入，且尝试写入存在让设备进入欢迎页循环的严重风险**。项目已通过 `safety.json` 强行阻断所有针对非 `HomeDomain` 的写操作。

### 旁路三：Carrier Bundle Overlay 签名篡改
*   **设计思路**：尝试替换位于数据分区的用户更新目录 `/var/mobile/Library/Carrier Bundles/Overlay/` 下的 `Carrier.plist`。
*   **实验结果**：**导致完全无服务（No Service）**。
*   **逆向归因**：
    `CommCenter` 在加载任何 Overlay Bundle 时均调用 `SecTrustEvaluateWithError` 强制验证 Apple 官方根证书数字签名。一旦文件哈希与 DER 签名不符，`CommCenter` 立即抛弃该配置，手机直接显示“无服务”。

### 旁路四：静态归档哨兵值（Sentinels）全矩阵探测
我们在模拟器与物理机上，对归档中的所有标量字段进行了穷举枚举测试：

| 实验 Variant | 字段配置组合 | 状态栏渲染表现 | 最终结论 |
| :--- | :--- | :--- | :--- |
| `STD_FULL` | `status=5, displayValue=4, type=10, string="Apple 5G"` | 显示自定义名 + 满格 4 格 + 5G 图标 | **当前生产最优解** |
| `NO_BARS` | `status=5, displayValue=None, type=10` | 显示自定义名 + **0 格全灰** + 5G 图标 | 失败（0 格全灰） |
| `NO_TYPE` | `status=5, displayValue=4, type=0` | 显示自定义名 + 满格 4 格 + **无制式文字** | 失败（制式空白） |
| `SENTINEL_TYPE`| `type=-1` 或 `type=255` | 显示自定义名 + 满格 4 格 + **无制式文字** | 失败（无 live 回落）|
| `STATUS_1` | `status=1, displayValue=None` | 蜂窝开启时显原生名；飞行模式显自定义名 | 反向回退，不可用 |
| `BOOTSTRAP` | `status=5, isBootstrapCellular=True` | **无运营商名** + 满格 4 格 + 5G 图标 | 门控强制关闭名称 |

---

## 4. 生产级最佳方案推荐 (Production Baseline)

鉴于“动态信号穿透”在非越狱架构下的客观不可达性，为向用户提供最完美、最逼真的视觉体验，推荐采用如下**生产级黄金配置**：

1.  **运营商名称自定义**：
    *   通过 `StatusBarOverrides.archive` 写入目标文本（支持中英双语、特殊字符及 Emoji）。
    *   灵动岛机型自动适配主卡（Trailing Ear）与长按展开后的双卡叠放标签。
2.  **信号格数与制式图标**：
    *   显式设定 `displayValue = 4`（保持常亮 4 格满格状态，符合绝大多数美化需求，消除 0 格全灰缺陷）。
    *   显式指定 `type = 10`（常驻渲染真实 5G 徽标）或按需指定 `11` (5G+)、`9` (LTE)。
3.  **VPN 图标原生透传**：
    *   强制保持 `suppressedBackgroundActivityIdentifiers = []` 并省略 `vpnEntry`，确保控制中心与状态栏中的原生实时 VPN 徽标不受任何干扰。
4.  **锁屏监管脚注补充**：
    *   配合 `SharedDeviceConfiguration.plist` 在锁屏底部常驻居中显示设备标识，达到全方位的系统个性化效果。

---

## 5. Milestone 2 配套研发工具代码

为沉淀本阶段的逆向研究成果，我们在 `tools/` 目录下开发并集成了两条专业工具链：

1.  **数据流拓扑与反汇编模拟器**：[`tools/cellular_dataflow_tracer.py`](file:///Users/prognosticatex/Desktop/ios27-carrier-lockscreen-research/tools/cellular_dataflow_tracer.py)
    *   `--trace-flow`：输出端到端基带至 SpringBoard 的架构拓扑与反编译函数偏移对照。
    *   `--simulate-collision --omit-display-value`：在本地无设备环境下精确模拟 `dataByApplyingOverlay:` 的内存合并过程，复现 0 格全灰缺陷。
2.  **非越狱旁路自动化 PoC 探测器**：[`tools/dynamic_carrier_bypass_poc.py`](file:///Users/prognosticatex/Desktop/ios27-carrier-lockscreen-research/tools/dynamic_carrier_bypass_poc.py)
    *   `--audit-mdm`：自动审计 Apple MDM 描述文件规范，导出不支持字段清单。
    *   `--audit-wireless`：对 `WirelessDomain` 执行沙箱与安全性评估，校验保护屏障。
    *   `--gen-sentinels <dir>`：一键生成全套哨兵探测归档，用于自动化回归比对。
3.  **单元测试套件**：[`tools/test_milestone2_poc.py`](file:///Users/prognosticatex/Desktop/ios27-carrier-lockscreen-research/tools/test_milestone2_poc.py)（5 项测试全部通过）。

---

## 6. 结项声明与未来路线

*   **Milestone 2 状态**：已正式结项（Closed as Conclusive）。
*   **学术与工程价值**：全行业首次系统性地通过汇编证据与硬件矩阵，彻底解释了 iOS 27 状态栏从 C 结构体到面向对象架构演进背后的约束边界，填补了非越狱逆向领域对 `SystemStatusServer` 运作机理的认知空白。
*   **下一阶段展望**：后续工作将聚焦于通用覆写引擎扩展（将归档原语拓展至电池、时间、Wi-Fi 等 40+ 全量 entry），以及针对即将发布的 iOS 27.1+ 次版本进行兼容性回归监测。
