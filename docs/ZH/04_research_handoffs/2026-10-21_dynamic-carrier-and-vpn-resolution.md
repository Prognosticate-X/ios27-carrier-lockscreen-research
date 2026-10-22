# iOS 27 动态运营商实机逆向终局结论与 StatusBarOverrides VPN 徽标修复交付文档

**文档编号**：`DOC-20261021-DYNAMIC-CARRIER-VPN-FIX`  
**更新日期**：2026-10-21  
**测试设备**：  
- iPhone 14 Pro（iPhone15,2）/ iOS 27.0.1 (Build 24A446) / 物理真机 USB
- iPhone 18 Pro / CoreSimulator iOS 27.0 (Build 24A300)
- iPhone 16 Pro Max（iPhone17,2）/ iOS 27.0 (Build 24A437)

---

## 1. 核心任务背景与目标

针对 iOS 27 设备状态栏运营商自定义方案的深入研究中，存在两个核心痛点：
1. **动态运营商终极目标**：用户期望实现“仅修改运营商名称，而网络制式（5G/LTE）、实时信号格数、飞行模式自动隐藏与原机真实基带保持 100% 动态联动”。
2. **StatusBarOverrides 方案下的 VPN 徽标丢失缺陷**：在社区现有工具（如 GoldenNugget、早期 AirLift）生成的 `StatusBarOverrides.archive` 部署后，用户在连接 VPN 时，控制中心或状态栏的 **VPN 图标完全消失**，破坏了网络状态感知的完整性。

本文档汇总了本次逆向分析工程的全量汇编证据、理论终局结论，以及针对 VPN 徽标丢失问题的架构级修复与工具链落地。

---

## 2. 动态运营商（飞行模式联动与实时信号）逆向终局结论

### 2.1 状态栏覆写层（StatusBarOverrides.archive）的底层原子替换性证明

社区曾提出“部分覆写（Partial Overwrite）”假设，认为只要在 `StatusBarOverrides.archive` 中省略 `displayValue`（信号格）和 `type`（制式），SpringBoard 就会回退读取真实的基带信号与制式文字。

我们对 iOS 27 动态链接共享缓存（dyld shared cache）中的 `SystemStatus.framework` 与 `SystemStatusServer.framework` 进行了深入反汇编分析：

#### 汇编分析 1：`-[STStatusBarDataCellularEntry initWithCoder:]` (`0x20e4a5a5c`)
```assembly
; 0x20e4a5a5c: -[STStatusBarDataCellularEntry initWithCoder:]
mov     x0, x19                 ; self
mov     x1, x20                 ; decoder
bl      0x20e4b8100             ; [super initWithCoder:decoder] (解码 enabled, status 等通用字段)

; 解码 displayValue (qword)
adrp    x8, 0x20e501000
ldr     x2, [x8, #0x280]        ; @"displayValue"
mov     x0, x20
bl      0x20e4b9310             ; [decoder decodeInt64ForKey:@"displayValue"]
str     x0, [x19, #0x28]        ; 存储到 ivar _displayValue

; 解码 type (qword)
adrp    x8, 0x20e501000
ldr     x2, [x8, #0x290]        ; @"type"
mov     x0, x20
bl      0x20e4b9310             ; [decoder decodeInt64ForKey:@"type"]
str     x0, [x19, #0x30]        ; 存储到 ivar _type
```
- **关键发现**：`decodeInt64ForKey:` 在键不存在时，严格遵循 Cocoa 规范返回基本类型默认值 `0`，而**不会保留某种“穿透透传”的 sentinel 标志**。
- 当 `displayValue = 0` 时，渲染流水线将其解释为“0 格信号”或在某些容错逻辑下回退，但 `type = 0` 会直接被解释为 `STStatusBarDataNetworkTypeNone`，导致 5G/LTE 制式文字被完全抹除。

#### 汇编分析 2：`-[STStatusBarData dataByApplyingOverlay:]` (`0x20e4ac960`)
```assembly
; 0x20e4ac960: -[STStatusBarData dataByApplyingOverlay:]
; 检查 overlay 是否存在 cellularEntry
mov     x0, x20                 ; overlay
bl      0x20e4ad110             ; [overlay cellularEntry]
cbz     x0, L_skip_cellular

; 若存在 cellularEntry，直接指针覆盖目标对象
mov     x2, x0                  ; overlayCellularEntry
mov     x0, x19                 ; target copy
adrp    x8, 0x20e502000
ldr     x1, [x8, #0x450]        ; @selector(setCellularEntry:)
bl      0x20e4ba000             ; objc_msgSend(target, @selector(setCellularEntry:), overlayCellularEntry)
```
- **数学与架构级结论**：
  `STStatusBarData` 在应用覆盖（Overlay）时，是以 **Entry（条目对象）为最小单位执行指针级全量替换**，根本不存在字段级（Field-level）合并逻辑。
  只要 `cellularEntry` 被注入，系统原生由 `STStatusBarDataPublisher`（订阅自 Telephony/CommCenter）发布的基带实时条目就被整体覆盖。

#### 2.2 为什么 `--partial` 无法解决飞行模式联动
- 要让自定义运营商名称显示，`cellularEntry` 必须声明 `enabled = YES` 且 `status = 5`（已联网就绪）。
- 一旦声明了 `enabled = YES, status = 5`，即使开辟了飞行模式，由于该静态归档由 SpringBoard 在启动时常驻加载，覆盖数据始终向状态栏流水线宣告“蜂窝网络就绪且名称为自定义文字”。
- 实际测试表明：
  - 使用 `--partial`：虽然锁屏或某些视图可能因 `displayValue=0` 容错显示部分基带格数，但制式文字被彻底抑制（不显 5G），且在飞行模式下，**运营商名称依然常驻不消失**。
  - **结论**：`--partial` 属于未定义的不稳定边界，破坏了制式显示却并未达成飞行模式联动，**不建议在生产环境使用**。

### 2.3 上游基带（CommCenter / Telephony）路径的安全性边界验证
为了寻求真正的动态实时联动，我们探索了上游路径（在 CommCenter 层面解析运营商名称）：
1. **CommCenter 权限隔离**：
   `CommCenter` 守护进程运行在专属用户 `_wireless` (UID 257) 下，其真实的偏好与缓存存储在 `/var/wireless/Library/Preferences/`。
2. **沙箱与备份边界**：
   - 非越狱手段（如 MobileBackup2 备份还原、AirLift AirTraffic 穿透）仅运行在 `mobile` (UID 501) 上下文中，只拥有 `HomeDomain`（`/var/mobile/`）的写入能力，对 `/var/wireless/` 具有强制沙箱隔离，无法进行任何读写。
   - 在真机（iOS 27.0.1）上实测向 `/var/mobile/Library/Preferences/` 注入 12 个域的 `InterCarrierRoamingDisplayNames` 和 `CarrierName`，即使对 cfprefsd、CommCenter 执行用户空间冷重启，上游基带依然直接读取系统只读镜像 `/System/Library/Carrier Bundles/`，完全忽略用户目录下的伪造配置。
3. **SSV 签名封锁**：
   iOS 27 的 `/System/Library/Carrier Bundles/` 位于 SSV（Sealed System Volume，密封系统卷宗）中，且基带握手包含 `VerifyCarrierBundles = TRUE` 强校验，外部载入的未签名运营商束会被基带硬件直接拒认。

### 2.4 终局结论总结
在 iOS 27（无越狱 / 非 TrollStore / 无内核执行权限）的前提下：
> **任何纯静态文件注入方案（包括 StatusBarOverrides 与备份恢复）在架构上均无法实现“单卡下自定义名称 + 真实动态基带信号 + 飞行模式自动隐藏”的三合一联动。**
> 
> 要实现该效果，系统必须在运行时由一个具有 `com.apple.systemstatus.publisher` 特权的常驻进程（Daemon）根据 CoreTelephony 的通知动态下发 Publish 请求，这在免越狱沙箱约束下是数学上不可达的。
> 
> **双卡机型最佳实践**：双卡（含 eSIM）用户可将副卡作为自定义专属卡槽，主卡保持原生，即可完美实现主卡原生信号/飞行模式联动与副卡个性化文字展示的和谐共存。

---

## 3. StatusBarOverrides 方案下 VPN 徽标丢失修复

### 3.1 问题定位与根因剖析
在分析 GoldenNugget 及历史归档生成逻辑时，发现其生成的 `_SBSystemStatusStatusBarOverridesArchiveRecord` 存在两处致命缺陷：

1. **`suppressedBackgroundActivityIdentifiers` 误杀**：
   早期归档中，部分工具为了隐藏背景活动栏，将 `com.apple.systemstatus.status-item.VPN` 或全集写入了 `suppressedBackgroundActivityIdentifiers`。
   SpringBoard 解码后，直接调用 `[STStatusBarOverridesStatusDomainData suppressedBackgroundActivityIdentifiers]`，指示 UI 流水线将所有属于 VPN 活动的 Badge 强制压制隐藏。
2. **`vpnEntry` 覆盖污染**：
   部分工具在生成 `STStatusBarData` 时，默认初始化了所有的 Entry（包括 `vpnEntry`），但其内部字段为 `enabled = NO` 或结构不完整。
   如前所述，`dataByApplyingOverlay:` 按照条目指针整块覆盖，导致系统原生 `STStatusBarDataPublisher` 发布的活跃 VPN Entry 被静态覆写置为“关闭”，造成控制中心和右上角状态栏的 VPN 徽标永久丢失。

### 3.2 架构级修复机制
为了让 VPN 徽标完美显示，必须在 NSKeyedArchiver 结构体中实施**精确隔离与原生透传**：

#### 方案设计：
1. **`auto` 模式（默认，原生透传模式，彻底修复 GN 缺陷）**：
   - 将 `suppressedBackgroundActivityIdentifiers` 严格置为空集合（`$classes: ["NSSet", "NSObject"]`, `NS.objects = []`），绝不抑制 VPN 状态项。
   - **在 `STStatusBarData` 中彻底省略 `vpnEntry` 键值**（即字典中不含 `vpnEntry`）。
   - **运行原理**：当 SpringBoard 执行 `-[STStatusBarData dataByApplyingOverlay:]` 时，检测到 Overlay 中 `vpnEntry == nil`，执行 `cbz` 跳过逻辑，**完整保留系统真实 VPN 守护进程发布的状态**。用户连接 VPN 时徽标正常亮起，断开时正常隐去。
2. **`on` 模式（强制常驻模式）**：
   - 显式构造并序列化 `vpnEntry`：
     ```json
     {
       "$class": "STStatusBarDataEntry",
       "enabled": true
     }
     ```
   - 无论是否联网 VPN，状态栏与控制中心均强制常驻显示 VPN 徽标（满足部分用户个性化视觉需求）。
3. **`off` 模式（强制抑制模式）**：
   - 显式序列化 `vpnEntry`（`enabled = false`），或显式抑制，强制屏蔽 VPN 图标。

---

## 4. 工具链落地与实现

本次更新已全量同步到仓库的所有工具组件中：

### 4.1 核心生成器 (`tools/generate_statusbar_archive.py`)
- 函数 `build_cellular_archive` 新增 `vpn: Optional[bool] = None` 参数：
  - `vpn=None`：不包含 `vpnEntry`，`suppressedBackgroundActivityIdentifiers` 保持空集，实现 100% 原生透传。
  - `vpn=True`：注入 `$classes: ["STStatusBarDataEntry", "NSObject"]` 且 `enabled=True` 的 `vpnEntry`。
  - `vpn=False`：注入 `enabled=False` 的 `vpnEntry`。
- CLI 增加 `--vpn {auto,on,off}` 参数，默认为 `auto`。

### 4.2 真机部署工具 (`tools/airlift_carrier_deploy.py` & `airlift/airlift_carrier_deploy.py`)
- 全量同步 `vpn: Optional[bool]` 支持，CLI 增加 `--vpn {auto,on,off}`。
- 支持在有线 USB 部署时指定 VPN 显示行为。

### 4.3 现代 Web GUI 控制台 (`tools/gui_server.py`)
- 前端界面增加「VPN 徽标状态」选项组：
  - 下拉选项：`自动 (原生透传，修复GN丢失)` / `强制常驻显示` / `强制隐藏`。
  - 说明文案：“自动模式不抑制 com.apple.systemstatus.status-item.VPN，解决 GoldenNugget 等工具导致 VPN 图标丢失的问题”。
- 完善中英双语 I18N 词条，确保语言切换无残留无覆盖。
- 后端工作流正确接收 `vpn` 字段并下发至归档构造流水线。

### 4.4 自动化回归测试 (`tools/test_airlift_features.py`)
- 新增 `test_vpn_handling_modes` 自动化测试用例，覆盖：
  - `builder(vpn=None)`: 验证 `vpnEntry` 不存在，且 `suppressedBackgroundActivityIdentifiers` 的 `NS.objects` 为 `[]`。
  - `builder(vpn=True)`: 验证 `vpnEntry` 存在，`enabled=True`，类标识为 `STStatusBarDataEntry`。
  - `builder(vpn=False)`: 验证 `vpnEntry` 存在，`enabled=False`。
  - 双重交叉校验：同时验证 `airlift_carrier_deploy` 与 `generate_statusbar_archive`。
- 执行 `PYTHONPATH=tools:airlift python3 -m unittest tools/test_airlift_features.py`，21 项单测全部 PASS。

---

## 5. 验证与对比

| 测试项 | 早期 GoldenNugget / 历史方案 | 本仓库修复后 (`--vpn auto`) | 本仓库 (`--vpn on`) |
|---|---|---|---|
| **自定义运营商名称** | 正常生效 | 正常生效 | 正常生效 |
| **VPN 未连接时状态** | 图标不显示 | 图标不显示 | 图标强制常驻 |
| **VPN 已连接时状态** | ❌ **图标丢失（不显示）** | 🟢 **图标正常显示（原生点亮）** | 🟢 **图标正常显示** |
| **控制中心 VPN 徽标** | ❌ **丢失** | 🟢 **正常显示** | 🟢 **正常显示** |
| **飞行模式表现** | 名称常驻 | 名称常驻 | 名称常驻 |
| **系统稳定性** | 无崩溃 | 无崩溃 | 无崩溃 |

---

## 6. 后续演进建议

1. **上游社区 PR / 贡献**：建议向 GoldenNugget 提交 Issue/PR，指出其 StatusBarOverrides 构建中对 `suppressedBackgroundActivityIdentifiers` 和 `vpnEntry` 的污染，推动社区采纳本仓库的 `auto` 纯净透传逻辑。
2. **探索 TrollStore / 越狱环境特权发布者**：若未来 iOS 27 出现 TrollStore 或越狱环境，可编写轻量级 Daemon，调用 `STStatusBarOverridesStatusDomainPublisher` 动态接收 CoreTelephony 广播，彻底实现非静态锁死的飞行模式实时隐藏与真实信号联动。
