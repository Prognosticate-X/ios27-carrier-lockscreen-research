# iOS 27 运营商与状态栏定制：最新进展审计与下一阶段研究路线图

**文档编号**：`DOC-20261028-ROADMAP`  
**更新日期**：2026-10-28  
**基线提交**：`ff75611`（2026-10-22，`main`）  
**文档状态**：Active / Living Document  
**适用范围**：iOS 27.0–27.x，非越狱、非 TrollStore、非内核执行权限前提  
**目标读者**：项目维护者、逆向研究者、工具链贡献者

> 本文是「当前状态」与「下一步方向」的单一入口。2026-09-25 至 2026-10-21 的历史文档保留为证据链；其中被后续实验推翻或更新的结论，以本文与最新实验记录为准。
>
> **阅读顺序建议**：先读第 0、1、2 节，再按第 3 节选择研究轨道；第 5 节是可直接执行的标准实验协议，第 8 节是未来 72 小时行动清单。

---

## 0. 结论摘要

1. **静态覆写路线已经成熟，不再是研究瓶颈。** `StatusBarOverrides.archive` 的路径、格式、读取、合并、渲染和物理机交付均已闭环；上游 GoldenNugget 也已集成。当前问题不是「能不能改」，而是「还能改多少、在哪些版本/机型上可靠、如何交付」。
2. **飞行模式联动大概率不可达，应作为「限时证伪」而不是长期目标。** 现有证据表明：名称可见性由覆写条目自身的 `enabled/status` 决定，静态归档没有「跟随实时蜂窝状态」的字段；真正的动态发布需要 `com.apple.systemstatus.publisher` entitlement。下一阶段应投入 10 个工作日做一次决定性矩阵实验，无论正负都形成结论文档，然后关闭或产品化。
3. **最高价值的新方向是「通用状态栏覆写引擎」。** `STStatusBarData` 在 iOS 27 中至少有 40 余个候选 entry（电池、Wi-Fi、时间、日期、飞行模式、VPN、卫星、热点、定位、旋转锁等）。当前工具只用了 `cellularEntry/secondaryCellularEntry/vpnEntry`。把同一原语扩展到全量 entry，是把单点工具升级为平台能力的最短路径。
4. **当前最大的风险在工程与实验方法，不在系统机制。** 审计发现：主力设备黑名单默认是空的（与文档宣称的「内置黑名单」不符）；实验台只重启 SpringBoard、没有清理 `systemstatusd` 的 live domain，可能导致矩阵实验出现假阴性；部分文档仍停留在「待物理验证」的旧结论。
5. **未来两周的行动顺序**：安全与实验台修复 → 飞行模式矩阵 → 全量 entry 枚举 → 27.1/新硬件回归 → 上游 PR 与文档治理。

### 0.1 优先级总览

| 优先级 | 轨道 | 要解决的问题 | 成功判据 | 预估投入 | 成功概率 |
|:---:|---|---|---|:---:|:---:|
| **P0** | Track 0 安全与实验台 | 黑名单空、purge 缺失、实验可复现性 | 主力设备零接触；同一 variant 连续 3 次结果一致 | 2–3 天 | 高 |
| **P0** | Track A 飞行模式证伪 | 静态归档能否让名称随蜂窝状态隐藏 | 找到可行组合，或形成不可达证明 | 10 个工作日 | 低（约 10–15%） |
| **P1** | Track B 通用覆写引擎 | 40+ entry 哪些可用、哪些安全 | ≥5 个非蜂窝 entry 稳定渲染 | 2–4 周 | 高 |
| **P1** | Track C 兼容性矩阵 | 27.0.x / 27.1+ / 新机型 / 各显示面 | 发布前矩阵全绿 | 持续 | 高 |
| **P1** | Track D 交付硬化 | AirLift 覆盖写、备份恢复、回滚 | 10/10 次成功应用与回滚 | 2–3 周 | 高 |
| **P2** | Track E/F/G | 官方通道、上游、文档与 CI | 上游 PR、状态页、CI 绿 | 持续 | 中高 |

> **2026-10-28 目标修正**：用户明确要求复刻 Nugget 在 iOS 26 及以下的行为——**只改名称，信号、制式、飞行联动全部实时**。运行时枚举已证明 `STStatusBarDataCellularEntry` 没有字段级 flags；`WirelessDomain` 备份注入已实测**证伪且不安全**：既未写入目标文件，又把 14 Pro 置入 Setup Assistant。非越狱边界内目前没有可用的“只改名称、其余全 live”方案。详见 [Nugget 式“只改名称”路线研究](2026-10-28_name-only-live-override.md)。Track B 的优先级应从“通用 entry 引擎”调整为“名称-only live 保持 + 上游 live 源注入”。

---

## 1. 本地现状审计（2026-10-28）

### 1.1 已确认事实

| 主题 | 结论 | 证据等级 | 关键证据 |
|---|---|:---:|---|
| 归档路径 | `/var/mobile/Library/SpringBoard/StatusBarOverrides.archive` | Confirmed | 物理机 + 模拟器 |
| 归档格式 | `NSKeyedArchiver` → `_SBSystemStatusStatusBarOverridesArchiveRecord` → `STStatusBarData` | Confirmed | 反序列化 + SpringBoard 反汇编 |
| 读取时机 | SpringBoard 启动早期读取一次；空记录触发自删除 | Confirmed | `_queue_readStatusBarOverridesArchiveRecord` / `_queue_writeOutArchiveRecord:` |
| 覆盖语义 | `dataByApplyingOverlay:` 以 entry 对象为单位整块替换，无字段级合并 | Confirmed | `0x20e4ac960` 反汇编 |
| 名称显示条件 | 经验上需要 `enabled=true`、`status=5`、非空 `string`、`isBootstrapCellular=false` | Confirmed（经验） | V4/V5/V6/V7 实验 + SystemStatusUI 门控 |
| 显示面差异 | 锁屏信号格读实时域；控制中心信号格读覆写值；锁屏通常不显示制式文字，控制中心在蜂窝数据开启时显示 | Confirmed | BARS1 实验 |
| Partial 模式 | 省略 `displayValue` 信号格回退实时；省略 `type` 制式文字被抑制；名称仍在飞行模式常驻 | Confirmed | V4 实验 |
| VPN 透传 | `suppressedBackgroundActivityIdentifiers=[]` 且省略 `vpnEntry` 时原生 VPN 徽标正常 | Confirmed | 物理机 + 21 项单测 |
| 双卡 | `cellularEntry` + `secondaryCellularEntry` 可渲染双卡叠放/徽标 | Confirmed | iPhone 14 Pro 物理机 |
| 物理交付 | AirLift 可写；GoldenNugget 走 HomeDomain 备份恢复 | Confirmed | 14 Pro 实机 / 上游集成 |
| 锁屏脚注 | 官方 `com.apple.shareddeviceconfiguration` 通道 | Confirmed | 配置文件 + 备份注入 |
| 上游采用 | GoldenNugget 9.5.1/9.5.2 集成归档格式并完成实机验证 | Confirmed（外部） | 上游 commit / docs |

### 1.2 仍未解决或未闭环

| 编号 | 问题 | 当前状态 | 影响 |
|:---:|---|---|---|
| Q1 | 飞行模式联动（名称随蜂窝关闭而隐藏） | 静态归档下未找到入口 | 核心体验缺口 |
| Q2 | `status` 取值 0–4、6、255 的语义 | 仅验证 5 与 -1；其余未系统枚举 | 可能藏着条件显示组合 |
| Q3 | `displayValue/type/rawValue/displayRawValue` 的哨兵值 | 未系统枚举 | 可能藏着「未覆写」语义 |
| Q4 | `isBootstrapCellular`、`sosAvailable`、`showsSOSWhenDisabled` 的交互 | 仅知 `isBootstrapCellular=true` 会隐藏名称 | 可能是另一条显示路径 |
| Q5 | live domain 合并/回写时序 | 已知 live 优先；未做逐帧观测 | 决定「能否借 live 域实现条件显示」 |
| Q6 | `STStatusBarData` 全量 entry 的可用性 | 仅用 3 个 entry | 平台化机会 |
| Q7 | iOS 27.1+ / iPhone 17/18 的兼容性 | 本机无 27.1 运行时；17 Pro Max 归属未确认 | 「Universal」声明风险 |
| Q8 | 交付通道的可靠性 | AirLift 受 rename/覆盖限制；备份恢复未在本仓库实现 | 用户体验与失败率 |
| Q9 | 脚注的长度、Unicode、多行、监督模式边界 | 仅有基础验证 | 官方通道的完整产品化 |
| Q10 | 历史文档与 README 的时效性 | 多处仍写「待物理验证」或「AirLift 受限」 | 误导后续研究者 |

### 1.3 代码与实验台审计（本次新增）

> 这一节是本次审计最重要的发现。**在修复 S1/S2 之前，不建议在物理机上运行任何新的批量矩阵实验。**

| 编号 | 严重度 | 发现 | 证据 | 建议 |
|:---:|:---:|---|---|---|
| S1 | **P0 安全** | 主力设备黑名单默认是空的 | `tools/airlift_carrier_deploy.py:378-383`：`PRIMARY_PHONE_BLOCKLIST = frozenset(_ENV_BLOCKLIST)`，仅从 `AIRLIFT_BLOCKED_UDIDS` 读取；当前环境该变量未设置 | 改为「默认 fail-closed」：未配置黑名单时拒绝所有写操作；或读取本地 `~/.config/ios27-carrier/safety.json`；增加单测，确保空环境也拒绝主力 UDID |
| S2 | **P0 方法** | 实验台没有清理 `systemstatusd` live domain | `statusbar_variant_lab.py` 只调用 `deploy_carrier() + respring_device()`；`respring_device()` 只终止 SpringBoard（`tools/airlift_carrier_deploy.py:841-881`） | 增加 `purge_live_domain()`：SIGSTOP SpringBoard → SIGKILL `systemstatusd` → 替换归档 → SIGKILL SpringBoard；失败时回退 userspace reboot。集成到 lab / replace / GUI |
| S3 | P1 方法 | variant lab 使用普通 deploy，不是原子替换 | `statusbar_variant_lab.py:158` 调用 `deploy_carrier`，目标文件已存在时可能受 ATAirlock rename 限制 | 改用 `airlift_archive_replace.replace_archive()`，或给 lab 增加 `--replace` |
| S4 | P1 维护 | 两份 deploy 脚本完全相同但各自维护 | `tools/airlift_carrier_deploy.py` 与 `airlift/airlift_carrier_deploy.py` md5 均为 `b503181e…` | 保留一份为源，另一份改为 thin wrapper 或构建时复制；加 CI 校验 |
| S5 | P1 兼容 | 硬件数据库缺少 iPhone 17/18 系列 | `has_dynamic_island` 列表止于 `iPhone17,4`（iPhone 16 系列） | 补 `iPhone18,x` / `iPhone19,x`；改为按「是否有灵动岛」的运行时能力探测，而非硬编码 |
| S6 | P2 文案 | `--partial` 的中文 GUI 提示与 README 不一致 | GUI 一处说「信号格与制式回退实时」，另一处说「制式文字被抑制」；README 明确「不建议生产使用」 | 统一为「信号格回退实时；制式文字被抑制；名称仍常驻飞行模式」，并标注 Experimental |
| S7 | P1 文档 | 多份文档仍停留在旧结论 | `2026-09-30_carrier-footnote-solution.md` 仍称 carrier name「Pending Physical Verification」；`2026-09-28_architecture.md` 仍称 AirLift「subject to rename limitations」；`2026-09-28_viable-paths.md` Route 3 仍「Pending」 | 加「Superseded by 2026-10-21 / 2026-10-28」横幅；在 docs hub 顶部指向本文 |
| S8 | P1 工程 | 没有 CI、没有设备测试、没有自动截图/OCR 回归 | 仓库无 `.github/`；`device_ui.py` 与 `ocr.swift` 未串联 | 加 GitHub Actions（仅离线单测 + plist 往返 + 链接检查）；设备测试用本地脚本，不进 CI |
| S9 | P1 交付 | 没有本仓库的 `MobileBackup2` 备份恢复管线 | 仅有 AirLift；`commcenter_preference_builder.py` 只生成 HomeDomain 结构 | 实现 filtered backup + Manifest.db 注入 + restore + rollback，作为 AirLift 的兜底 |
| S10 | P2 体验 | 应用后需要 respring/reboot，且 respring 有时不足以清除 live 缓存 | 2026-10-19 文档明确记录；当前 CLI 默认 respring | 把「可靠应用」做成显式状态机：apply → verify → 失败则 userspace reboot；GUI 显示当前阶段 |

> **2026-10-28 进展**：S1（`safety.json` + fail-closed + 直调用 guard）、S2（`exp_status_matrix` 的 live-domain purge）、S4（`airlift/` wrapper）已落地；S3 已由新实验台覆盖；S5 已补 iPhone 17/18 型号。S6–S10 仍待办。

### 1.4 实验室资产

| 设备 | 型号 | 系统 | 状态 | 用途 | 写入许可 |
|---|---|---|---|:---:|---|
| iPhone 14 Pro | iPhone15,2 | 27.0.1（24A446） | USB connected | 主测试机 | ✅ 允许（仅本机） |
| iPhone 16 Pro Max | iPhone17,2 | 27.0（24A437） | available (paired) | 日常主力 / 只读对照 | ❌ 禁止写入 |
| iPhone 17 Pro Max | iPhone18,2 | 27.0（24A437） | 连接状态不稳定 | 新硬件兼容候选 | ⚠️ 需所有者确认归属后再定 |
| iPhone 18 Pro（模拟器） | iPhone19,2 | 27.0（24A434） | Booted | 快速矩阵 / 反汇编对照 | ✅ 允许（模拟器） |
| iPhone SE（模拟器） | — | 27.0 | 可按需启动 | 经典刘海/Home 键对照 | ✅ 允许（模拟器） |
| Xcode | 27.0（27A266a） | iOS SDK 27.0 | 已安装 | 构建 / 模拟器 | — |

当前环境：Python 3.12.13；`PYTHONPATH=tools:airlift python3 -m unittest tools/test_airlift_features.py` → **21 tests OK**；无 iOS 27.1 runtime/SDK。

### 1.5 阶段性判断

项目目前处于 **「方案已闭环、证据链未闭环、工程化脆弱」** 的阶段：

- **方案层**：静态覆写 + VPN 透传 + 双卡 + 脚注，均可交付。
- **证据层**：飞行模式、status 语义、全量 entry、27.1 兼容性仍未闭环。
- **工程层**：安全护栏、实验复现性、交付兜底、文档时效性存在明显缺口。

因此，下一阶段不应继续「无边界地找动态方案」，而应 **先修实验台与安全，再做限时证伪，最后把原语平台化**。

---

## 2. 核心研究问题与假设

| 编号 | 研究问题 | 主要假设 | 现有证据 | 验证方法 | 决策门 |
|:---:|---|---|---|---|---|
| RQ1 | 静态归档能否让名称可见性跟随实时蜂窝状态？ | H1：不能；名称门控只读覆写条目的 `displayItem.isEnabled/string/isBootstrapCellular`，不读 `STTelephonyStatusDomain` | 反汇编 + V4/V5/V6/V7 + 飞行模式常驻 | Track A 矩阵 + live 域观测 | 找到组合 → 产品化；否则关闭 |
| RQ1a | 是否存在 `status` 哨兵或特殊组合？ | H1a：0–4/6/255 中可能有「未注册/搜索中」语义，但不提供 live 绑定 | 仅验证 5 与 -1 | Track A1 全枚举 | 任一组合在飞行模式隐藏且保留信号 → 成功 |
| RQ1b | 能否利用 live domain 的合并/回写？ | H1b：live 域优先，但只在特定事件发布 `cellularEntry`；可利用窗口极窄 | `recordByApplyingRecord:` 反汇编 | Track A3 逐帧日志 + 归档 diff | 能量化窗口 → 评估；否则否 |
| RQ1c | 是否存在替代 entry/显示路径？ | H1c：`bootstrapCellularEntry`/`secondaryCellularEntry`/`satelliteEntry`/`rawStringView` 可能有独立门控 | `STUIStatusBarCellularItem` 有 `rawStringView`、`isBootstrapCellular`；`STStatusBarData` 有 40+ entry | Track A4/A5 | 找到独立路径 → 产品化 |
| RQ2 | `STStatusBarData` 的全量覆写面有多大？ | H2：多数 entry 可被归档接受，但部分被忽略或不安全 | `strings` 枚举到 40+ 候选 entry | Track B 逐 entry 实验 | ≥5 个非蜂窝 entry 稳定 → 平台化 |
| RQ3 | iOS 27.1+ / 新硬件是否改变语义？ | H3：可能改 schema、补 AirLift、改显示门控 | 本机只有 27.0/27.0.1 | Track C canary | 版本矩阵全绿才发布 |
| RQ4 | 哪种交付通道最可靠？ | H4：备份恢复对「覆盖已有文件」更稳；AirLift 对首次安装更轻 | GoldenNugget 已验证 HomeDomain；本仓库只有 AirLift | Track D A/B 对比 | 10/10 成功 + 可回滚 → 采纳 |
| RQ5 | 官方配置通道是否有运营商名称键？ | H5：没有；只有脚注有官方键 | Apple Device Management schema 未见 carrier name | Track E schema 审计 | 找到官方键 → 优先级最高；否则关闭 |
| RQ6 | 动态发布是否有非越狱路径？ | H6：没有；需要 `com.apple.systemstatus.publisher` entitlement | 现有沙箱/签名证据 | Track A6 entitlement 审计 | 无 → 明确写入「Out of scope」 |

### 2.1 对 RQ1 的强先验

从 `SystemStatusUI` 的名称门控看，名称显示只依赖三件事：

1. `displayItem.isEnabled`（由覆写条目的 `enabled/status` 推导）；
2. `entry.string.length > 0`；
3. `!entry.isBootstrapCellular`。

它**没有**读取 `STTelephonyStatusDomain` 的实时注册状态。因此，除非存在以下三种例外之一，静态归档不可能实现「飞行模式自动隐藏」：

- **例外 A**：某个 `status`/哨兵值会让 `displayItem.isEnabled` 在运行时重新绑定 live 状态（目前无证据）；
- **例外 B**：live domain 在飞行模式切换时发布一个 `cellularEntry`，与磁盘记录合并后覆盖名称（需要逐帧验证）；
- **例外 C**：另一个 entry（bootstrap/secondary/satellite/raw）有独立的、与 live 状态耦合的门控。

Track A 的核心任务就是**逐一排除 A/B/C**。如果三者都排除，RQ1 可以正式关闭，并把「动态名称」标注为「需要运行时注入，超出非越狱边界」。

### 2.2 停止清单（Negative Knowledge）

以下路线已在本地或实机上得到阴性结论。除非出现新的 iOS 大版本、新的写入原语或新的 entitlement，否则不再投入：

| 路线 | 结论 | 关键证据 | 何时可重新评估 |
|---|---|---|---|
| Speakeasy / FeatureFlags 静态写入 | 不可行 | `/var/preferences` 非 mobile 可写；BackupAgent 白名单；sparse restore 触发 Security State Recovery | Apple 放开 FeatureFlags 写路径（可能性极低） |
| CommCenter CFPreferences 注入 | 阴性 | 14 Pro / 27.0.1 上 12 域注入 + 冷重启 cfprefsd/CommCenter/SpringBoard 均无效；真实数据在 `/var/wireless` 与签名 carrier bundle | 获得 `_wireless` 写权限或 CommCenter 注入能力 |
| Carrier Bundle Overlay / 签名篡改 | 高风险、不可行 | 签名校验失败会导致 No Service；SSV 只读 | 出现可过签名的 overlay 机制 |
| AFC 读取 media 之外的文件 | 仅 stat | `read`/`list` 在 media 外失败；内容读取走备份 | AFC 权限模型改变 |
| 运行时发布 `STStatusBarOverridesStatusDomain` | 越狱/TrollStore 级 | 需要 `com.apple.systemstatus.publisher` entitlement | 出现非越狱的 publisher 通道 |
| 静态归档飞行模式联动 | 当前证据倾向不可行 | 名称门控不读 live telephony；Track A 尚未最终结案 | Track A 找到 A/B/C 例外 |
| `--partial` 作为默认生产模式 | 不推荐 | 制式文字被抑制；名称仍常驻飞行模式 | 找到制式回退的哨兵值 |

---

## 3. 研究轨道

### Track 0 — 安全与实验台（P0，2–3 天）

**目标**：让任何后续实验都满足「主力设备零接触、结果可复现、失败可回滚」。

**任务**：

1. **S1 修复：fail-closed 黑名单**
   - 新增 `DEFAULT_BLOCKED_UDIDS` 或本地 `safety.json`；
   - 未配置黑名单时，写操作直接拒绝，并打印配置方法；
   - 保留 `AIRLIFT_BLOCKED_UDIDS` 作为追加，而不是唯一来源；
   - 单测：空环境 + 主力 UDID → 必须抛错；14 Pro UDID → 允许。
2. **S2 修复：可靠 purge**
   - 新增 `purge_live_domain(udid)`：
     1. 读取 SpringBoard PID；
     2. `SIGSTOP` SpringBoard；
     3. 通过 CoreDevice 找到并 `SIGKILL` `systemstatusd`；
     4. 替换归档（原子替换）；
     5. `SIGKILL` SpringBoard，等待新 PID；
     6. 若任一步失败，回退 `devicectl reboot --style userspace`。
   - 集成到 `deploy_carrier`、`replace_archive`、`statusbar_variant_lab`、GUI 的 deploy/reset。
3. **S3 修复：variant lab 改用原子替换**
   - 增加 `--replace` / `--purge`；
   - 输出 JSON 结果（variant、字段、 purge 方式、截图路径、OCR 文本）。
4. **S4 修复：单一源**
   - `tools/` 为唯一源；`airlift/` 改为 wrapper；
   - CI 校验两份文件 hash 一致（或不再保留第二份）。
5. **S5 修复：硬件数据库**
   - 补 iPhone 17/18 系列；
   - 用 `MobileGestalt`/`devicectl` 能力探测替代硬编码列表。
6. **观测能力**
   - 归档 SHA-256、文件大小、mtime；
   - 设备 build/UDID/名称；
   - 截图 + OCR + 手工复核标记；
   - 统一结果 JSON schema。

**验收**：

- 空环境黑名单测试通过；
- 14 Pro 连续 3 次 apply → purge → 截图，结果一致；
- 不产生 `airlift-*` 残留；
- 所有写路径默认带 `--dry-run` 预检。

---

### Track A — 飞行模式联动终局验证（P0，10 个工作日）

**目标**：要么找到「名称随蜂窝关闭而隐藏，同时保留实时信号/制式」的静态组合；要么给出可复核的不可达证明。

#### A1. `status` / `enabled` / 字段矩阵

在 14 Pro + iPhone 18 Pro 模拟器上，使用 Track 0 的可靠 purge，逐项测试：

| 维度 | 取值 | 说明 |
|---|---|---|
| `status` | -1, 0, 1, 2, 3, 4, 5, 6, 255 | 重点：0–4 是否隐藏名称但保留信号 |
| `enabled` | true / false / 省略 | 省略与 false 是否等价 |
| `displayValue` | 0, 1, 3, 4, -1, 255, 65535, 省略 | 找「未覆写」哨兵 |
| `type` | 0, 9, 10, -1, 255, 省略 | 找制式回退语义 |
| `rawValue` / `displayRawValue` | 0, -1, 255, 省略 | 是否影响 rawStringView |
| `isBootstrapCellular` | true / false / 省略 | 名称门控的直接开关 |
| `sosAvailable` / `showsSOSWhenDisabled` | true/false 组合 | 是否改变「无服务」分支 |
| `string` / `crossfadeString` | 非空 / 空 / 仅 crossfade | 名称与交替显示 |
| `suffixString` / `badgeString` | 有/无 | 是否影响名称布局与隐藏 |

**判定**：每个 variant 至少在 4 个状态下截图：蜂窝开 + Wi-Fi 关、蜂窝开 + Wi-Fi 开、飞行模式、无服务（模拟器 `--cellularMode failed`）。记录名称、信号格、制式、飞行图标。

#### A2. 显示面矩阵

| 显示面 | 进入方式 | 关注点 |
|---|---|---|
| 锁屏 | 唤醒 | 名称/信号格/制式/飞行图标 |
| 控制中心 | 右上角下拉 | 名称/信号格/制式/VPN |
| 主屏幕 | 解锁 | 左上角是否显示名称 |
| 通知中心 | 左上角下拉 | 是否复用锁屏布局 |
| StandBy / 待机 | 横放充电 | 名称是否显示、是否被裁切 |
| 灵动岛展开 | 长按 | 双卡名称/徽标 |

#### A3. live domain 观测

- 用 `log stream` / `log collect` 抓 `systemstatusd`、`SpringBoard`、`STStatusBarOverridesStatusDomain` 相关日志；
- 在飞行模式切换前后，记录：
  - 磁盘归档 SHA-256 是否变化；
  - `systemstatusd` 是否重新发布 `cellularEntry`；
  - SpringBoard 是否回写合并后的记录；
- 如果发现「飞行模式切换 → live 域发布 cellularEntry → 磁盘被回写」的窗口，量化窗口长度与可重复性。

**注意**：不要只靠「改文件 + respring」判断阴性；必须确认 live 域已被清空，否则结果不可信。

#### A4. 替代 entry / 显示路径

- `secondaryCellularEntry`：单卡设备伪造副卡，观察是否出现独立名称/徽标；主卡保持 live 时，名称是否仍常驻。
- `satelliteEntry` / `tetheringEntry`：是否可承载自定义文本。
- `airplaneModeEntry`：显式覆写飞行模式条目，是否影响名称分支。
- `bootstrapCellularEntry`（若存在/可解码）：是否只在启动早期显示。
- `rawStringView` / `rawValue`：是否提供独立的原始字符串显示通道。

#### A5. 二进制分析清单

| 目标 | 方法 | 产出 |
|---|---|---|
| `STUIStatusBarCellularItem applyUpdate:toDisplayItem:`（`0x2c1c`） | Hopper/otool 反汇编 | 名称门控的完整伪代码 |
| `_signalViewShouldBeEnabledForEntry:forceShowingDisabledSignalBars:signalMode:`（`0x2aa8`） | 反汇编 | status 如何影响信号视图 |
| `STUIStatusBarCellularCondensedItem` / `ExpandedItem` | 反汇编 | 灵动岛/双卡名称门控 |
| `STStatusBarDataCellularEntry` 的 ivar/property | 模拟器运行时反射或 dsc 提取 | 完整字段表、默认值、未初始化语义 |
| `STStatusBarData` 的 top-level key | 运行时反射 | 是否存在 top-level carrier/service 字段 |
| `_SBSystemStatusStatusBarOverridesArchiver` 的 merge/persist | 反汇编 + 日志 | 磁盘与 live 的优先级、回写条件 |
| `STStatusBarDataCellularType` / `NetworkStatus` 枚举 | symbols/strings | status 取值语义 |

#### A6. entitlement 审计

- 确认 `com.apple.systemstatus.publisher` 是否可由非系统进程获取；
- 确认是否存在其他 entitlement / XPC 服务可发布 `STStatusBarOverridesStatusDomain`；
- 结论只用于「是否可能在非越狱环境做动态发布」，不用于实际注入。

#### A 的决策门

| 结果 | 判定 | 后续 |
|---|---|---|
| 找到组合：飞行模式隐藏 + 实时信号/制式保留 | 成功 | 产品化为 `--dynamic-name` 或独立模式；补文档与回归 |
| 找到组合：飞行模式隐藏，但制式/信号降级 | 部分成功 | 评估是否值得作为可选模式；默认仍用 full/partial |
| 未找到组合，但证明 live 域/entitlement 不可用 | 不可达 | 写「关闭备忘录」；从 roadmap 移除；保留双卡副卡 workaround |
| 实验不稳定/无法复现 | 方法问题 | 先修 Track 0，再重跑；不得下结论 |

**时间盒**：10 个工作日。到期无论结果如何，必须产出 `2026-11-XX_airplane-mode-verdict.md`。

**2026-10-28 试点结果**：已完成 REA + Ghidra 名称门控反汇编，并在 iPhone 14 Pro / 27.0.1 上跑完 `status` 0–5/255 的矩阵。结论是：`status=5` 自定义名常驻；`status=1` 是 live-fallback（蜂窝开显示原生名，飞行模式显示覆写名，方向相反）；0/2/3/4 会隐藏名称并改变蜂窝指示。**没有找到「蜂窝开显示自定义名 + 飞行模式自动隐藏」的静态组合。** 详见 [2026-10-28 飞行模式矩阵实验记录](2026-10-28_airplane-mode-status-matrix.md)。

---

### Track B — 通用状态栏覆写引擎（P1，2–4 周）

**目标**：把 `StatusBarOverrides.archive` 从「改运营商名」升级为「可控的状态栏数据覆写层」。

**B1. 全量 entry 枚举**

以 iOS 27.0 模拟器 `SystemStatusUI` 的字符串为起点（见附录 A），逐项验证：

- entry 是否被 `STStatusBarData` 接受；
- 是否需要额外字段才能渲染；
- 在锁屏/控制中心/主屏的可见性；
- 是否影响系统稳定性；
- 是否属于「安全敏感」（VPN、定位、录音、隐私指示器）。

**B2. 候选优先顺序**

1. **低风险、高可见**：`batteryEntry`、`mainBatteryEntry`、`wifiEntry`、`timeEntry`、`shortTimeEntry`、`dateEntry`；
2. **中风险、强需求**：`airplaneModeEntry`、`rotationLockEntry`、`alarmEntry`、`quietModeEntry`、`bluetoothEntry`、`airPlayEntry`；
3. **高风险、默认关闭**：`vpnEntry`、`locationEntry`、`sensorActivityEntry`、`backgroundActivityEntry`、`satelliteEntry`、`tetheringEntry`。

**B3. Schema 与工具**

- 新增 `tools/statusbar_schema.py`：entry → class → 字段 → 类型 → 默认值 → 安全级别；
- 生成器支持 `--entry-json` / `--schema`；
- GUI 增加「Advanced / 高级覆写」折叠面板；
- 预设系统扩展为「状态栏主题」而不是「运营商预设」。

**B4. 安全分类**

| 级别 | 含义 | 默认 |
|---|---|---|
| Safe | 纯外观，不误导安全状态 | 允许 |
| Caution | 可能误导网络/电池状态 | 需确认 |
| Sensitive | VPN/定位/隐私/录音指示器 | 默认禁止，需显式 `--allow-sensitive` |

**B5. 验收**

- ≥5 个非蜂窝 entry 在 14 Pro + 模拟器稳定渲染；
- 不引起 SpringBoard 崩溃/循环；
- `--reset` 可一键恢复；
- 新增 ≥10 个单测（plist 往返、字段省略、敏感条目拒绝）。

---

### Track C — 兼容性与回归矩阵（P1，持续）

**目标**：让「Universal」成为可验证的矩阵，而不是一句口号。

**C1. 版本矩阵**

| 版本 | Build | 状态 | 必测项 |
|---|---|---|---|
| 27.0 | 24A300 / 24A434 / 24A435 / 24A437 | 部分已测 | archive 读取、名称、VPN、双卡 |
| 27.0.1 | 24A446 | 已测（14 Pro） | 同上 + AirLift 覆盖写 |
| 27.1+ / 27.2 | 待发布/待安装 | 未测（14 Pro 已提示 27.2 可用） | schema diff、AirLift 是否仍可用、显示门控 |

**C2. 设备矩阵**

- 灵动岛：iPhone 14 Pro / 16 Pro Max（只读）/ 17 Pro Max（待确认）/ 18 Pro 模拟器；
- 经典刘海：iPhone 13/14 / SE 模拟器；
- 单卡 / 双卡 / eSIM / 无服务 / 飞行模式 / Wi-Fi Calling / 漫游。

**C2.5 文本边界**：超长名称、CJK、emoji、RTL、组合字符、零宽字符、徽标、后缀；记录截断/滚动/缩放行为，作为发布前的视觉回归项。

**C3. 自动化证据**

- `device_ui.py` 截图 → `ocr.swift` 识别 → 结果 JSON；
- 关键 variant 保存 golden screenshot；
- 对名称、信号格、制式、飞行图标分别打标签；
- 人工复核只针对 OCR 低置信度样本。

**C4. AirLift 可用性 canary**

每个新 build 先跑只读/低风险探测：

1. `devicectl list devices` 能识别；
2. `snapshot-books` 成功；
3. `stage` 成功；
4. `info` 能 stat 目标；
5. 仅在 14 Pro 上跑一次 reset 归档写入 + purge + 恢复。

**C5. 发布门**

- 27.0.x 矩阵全绿；
- 27.1 canary 至少通过「生成 → 写入 → 读取 → 回滚」；
- 新机型至少通过模拟器 + 一台物理机；
- 文档矩阵与实际一致。

---

### Track D — 交付通道硬化（P1，2–3 周）

**目标**：把「能写」变成「可重复、可回滚、可解释失败」。

**D1. 本仓库的备份恢复管线**

- 使用 `.venv` 中的 `pymobiledevice3`：
  1. 创建 filtered backup（仅 `Library/SpringBoard` / 必要域）；
  2. 在备份的 `Manifest.db` 中注入 `StatusBarOverrides.archive` 记录；
  3. 恢复到 14 Pro；
  4. 触发 SpringBoard 重读；
  5. 验证 + 回滚。
- 与 GoldenNugget 的 HomeDomain 方案做字节级对比；
- 记录备份耗时、失败模式、是否需要信任/解锁。

**D2. AirLift 硬化**

- 原子替换 + purge + 重试 + 幂等；
- 失败时清理 `airlift-*` 与 Books 状态；
- 明确「首次安装」与「覆盖更新」两条路径；
- 对 ATAirlock rename 限制给出可操作的错误提示。

**D3. 设备端可行性（探索）**

- 评估 AirCard 式 `AirliftFFI` 在本机自配对/开发者模式下的可行性；
- 只做可行性报告，不承诺消费级产品；
- 关键问题：无宿主时能否触发 SpringBoard/systemstatusd 重载。

**D4. 验收**

- 14 Pro 上 10/10 次 apply + rollback；
- 无数据丢失、无残留、无 Security State Recovery；
- 失败时能在 60 秒内恢复到原生状态；
- 文档给出「失败排查树」。

---

### Track E — 官方通道与锁屏脚注（P2，1 周）

**E1. Apple Device Management schema 审计**

- 检索 `com.apple.shareddeviceconfiguration`、`com.apple.cellular`、`CarrierSettings` 等 payload；
- 确认是否存在 carrier display name / operator name 的官方键；
- 若没有，明确记录「官方通道只覆盖脚注，不覆盖运营商名」。

**E2. 脚注边界测试**

- 长度上限、换行、Unicode、emoji、RTL；
- 监督 vs 非监督；
- 与 Focus / StandBy / Always-On 的交互；
- 配置文件安装/移除/重装；
- 备份注入路径；
- 企业 MDM 推送更新。

**E3. 交付**

- `footnote_generator.py` 增加长度/字符校验；
- 文档增加兼容性表与回滚步骤；
- 明确「脚注 ≠ 运营商名」的能力边界。

---

### Track F — 上游与生态（P2，持续）

**F1. GoldenNugget**

- 提交 VPN passthrough 修复（`suppressedBackgroundActivityIdentifiers=[]` + 省略 `vpnEntry`）；
- 提交 `--partial` / 双卡 / 归档生成器的可复用逻辑；
- 对比他们的 archive schema 与本仓库的差异；
- 用同一台 14 Pro 做交叉验证。

**F2. AirLift**

- 反馈 ATAirlock rename/覆盖限制与 iOS 27.1 兼容性；
- 提供最小复现与日志；
- 跟踪上游修复。

**F3. 测试向量**

- 在 `examples/` 增加：
  - 单卡 full / partial / vpn auto；
  - 双卡；
  - reset；
  - 一个「已知会失败」的反例（用于测试错误处理）。
- 增加 `tools/validate_archive.py`：解码 + 断言 + SHA-256。

**F4. 交叉验证**

- 与社区用户/其他工具维护者交换 archive 样本；
- 记录「同一样本在不同工具/版本」的渲染差异。

---

### Track G — 文档与发布工程（P1，持续）

**G1. 状态页**

- 本文作为「当前状态」入口；
- 历史文档加 `Superseded` 横幅（只加在顶部，不改历史内容）；
- docs hub 顶部加「Latest status → 2026-10-28 roadmap」。

**G2. README 修正**

- 黑名单描述与实际代码一致；
- AirLift 限制与备份恢复路径的表述一致；
- `--partial` 统一为 Experimental；
- 版本矩阵与「Universal」措辞一致。

**G3. CI**

- 离线单测（21+）；
- plist 归档往返；
- 文档链接检查；
- Python lint / type check（可选）；
- 不把设备测试放进公共 CI。

**G4. 发布清单**

- 版本号、变更日志、兼容矩阵、已知问题、回滚步骤；
- 每个 release 附一个可复现的最小实验记录。

---

## 4. 优先级与建议时间表

| 阶段 | 时间 | 轨道 | 关键交付 | 决策门 |
|:---:|---|---|---|---|
| **Phase 0** | 10/28–10/31 | Track 0、G1/G2 | fail-closed 黑名单、purge、lab 修复、文档横幅 | 单测 + 14 Pro 三次一致 |
| **Phase 1** | 11/01–11/14 | Track A、B1–B2 | 飞行模式矩阵、status 语义、entry schema 初稿 | 10 个工作日后出 A verdict |
| **Phase 2** | 11/15–11/28 | Track B3–B5、C、D1–D2 | 通用覆写 GUI/CLI、兼容矩阵、备份恢复管线 | 10/10 apply/rollback |
| **Phase 3** | 12/01–12/15 | D3、E、F、G3 | 设备端可行性报告、上游 PR、CI、release | 27.0.x 全绿 + 27.1 canary |
| **Ongoing** | 持续 | C4/C5、F、G | AirLift canary、上游跟踪、文档更新 | 每个新 build 必跑 |

> 如果 Track A 在 11/14 前得到明确阴性结论，Phase 1 的后半段可直接转向 Track B，不必等待。

---

## 5. 标准实验协议

### 5.1 预检清单

- [ ] 目标设备是 14 Pro 测试机，不是主力机；
- [ ] `AIRLIFT_BLOCKED_UDIDS` 或 `safety.json` 已设置；
- [ ] 设备已解锁、已信任、USB 连接稳定；
- [ ] 已记录 UDID、型号、iOS 版本、build；
- [ ] 已导出当前 `StatusBarOverrides.archive`（或确认不存在）；
- [ ] 已截取原生基线：锁屏、控制中心、主屏；
- [ ] 电量 > 50%，关闭低电量模式；
- [ ] 已确认没有其他写操作在跑。

### 5.2 应用与 purge 序列（Track 0 完成后）

~~~text
1. 生成 variant payload
2. 原子替换归档（move-out old → move-in new）
3. purge live domain：
   SIGSTOP SpringBoard
   SIGKILL systemstatusd
   SIGKILL SpringBoard
4. 等待 SpringBoard 新 PID
5. 校验磁盘归档 SHA-256 / 大小
6. 截图 + OCR
7. 切换蜂窝/飞行模式，重复截图
8. 记录结果 JSON
~~~

如果 purge 失败，回退：

~~~bash
xcrun devicectl device reboot --device "$UDID" --style userspace
~~~

### 5.3 结果记录 schema

~~~json
{
  "variant": "V_STATUS_0",
  "device": {"udid": "...", "model": "iPhone15,2", "ios": "27.0.1", "build": "24A446"},
  "fields": {"status": 0, "enabled": true, "displayValue": "omitted", "type": "omitted"},
  "apply": {"archiveSha256": "...", "size": 0, "purge": "systemstatusd+SpringBoard", "ok": true},
  "observations": [
    {"surface": "lockscreen", "airplane": false, "wifi": false, "name": "CUSTOM", "bars": 4, "type": null},
    {"surface": "lockscreen", "airplane": true,  "wifi": false, "name": "CUSTOM", "bars": 0, "type": null}
  ],
  "ocrConfidence": 0.97,
  "manualReview": true,
  "notes": ""
}
~~~

### 5.4 判定规则

- **阳性**：目标行为在至少 2 个显示面、连续 3 次实验中稳定出现；
- **阴性**：在 purge 成功、归档校验通过、至少 2 个显示面均无目标行为，且连续 3 次一致；
- **不确定**：purge 失败、归档未生效、OCR 低置信度、结果不一致 → 不计入结论，先修方法。

### 5.5 安全规则

1. **主力设备零接触**：16 Pro Max 不写入；17 Pro Max 归属确认前不写入。
2. **不碰 `/var/preferences`**：不尝试 FeatureFlags、Security State Recovery 触发路径。
3. **不碰签名载体**：不改 carrier bundle、不改 SSV、不注入 CommCenter。
4. **优先 userspace reboot**：避免 full reboot 后的 USB Restricted。
5. **每次实验可回滚**：保留原归档、Books 快照、设备截图。
6. **敏感 entry 默认关闭**：VPN/定位/录音/隐私指示器需显式允许。

### 5.6 回滚

~~~bash
# 恢复原生（Track 0 完成后）
python3 tools/airlift_carrier_deploy.py --device "$UDID" --reset --force-overwrite
xcrun devicectl device reboot --device "$UDID" --style userspace

# 清理 AirLift 残留
python3 tools/airlift_carrier_deploy.py --device "$UDID" --clean-device
~~~

---

## 6. 资源、风险与依赖

### 6.1 资源

| 资源 | 现状 | 缺口 |
|---|---|---|
| 测试机 | 14 Pro 27.0.1 | 缺 27.1+ 设备 |
| 新硬件 | 17 Pro Max 27.0（待确认） | 归属/许可 |
| 模拟器 | 18 Pro / SE 27.0 | 缺 27.1 runtime |
| 逆向工具 | otool/nm/strings/Hopper（可选） | 缺自动化 dsc 提取脚本 |
| 设备自动化 | devicectl / pymobiledevice3 / AirLift | 缺可靠 purge 封装 |
| OCR | `ocr.swift` | 缺批量/置信度评估 |
| 时间 | — | Track A 10 天；Track B/D 各 2–3 周 |

### 6.2 风险

| 风险 | 概率 | 影响 | 缓解 |
|---|:---:|---|---|
| 误写主力设备 | 低但后果高 | 数据/设备风险 | Track 0 fail-closed；双人复核；不自动选设备 |
| AirLift 在 27.1 被修补 | 中 | 交付中断 | 备份恢复兜底；canary；上游跟踪 |
| 27.1 改 archive schema | 中 | 工具失效 | schema 自动发现；版本适配层；回归矩阵 |
| purge 不稳定导致假阴性 | 高 | 结论错误 | Track 0 修复；三次一致；日志佐证 |
| 设备不可用/被锁 | 中 | 进度延误 | 模拟器先行；预约设备窗口 |
| OCR 误判 | 中 | 证据不可信 | 人工复核低置信度；golden screenshot |
| 敏感 entry 误导用户 | 中 | 信任/安全问题 | 安全分级；默认关闭；显式警告 |
| 上游 schema 分叉 | 中 | 兼容性问题 | 交叉验证；测试向量；PR 对齐 |
| 文档继续腐化 | 高 | 研究者误导 | 状态页 + Superseded 横幅 + 发布检查 |

### 6.3 依赖

- iOS 27.1+ runtime / IPSW（用于 Track C）；
- 17 Pro Max 的归属确认（用于新硬件矩阵）；
- GoldenNugget 维护者的响应（用于 Track F）；
- 设备端 AirLift/AirCard 的资料（用于 Track D3）。

---

## 7. 交付物清单

| 类别 | 交付物 | 对应轨道 | 验收 |
|---|---|---|---|
| 代码 | fail-closed 安全护栏 + 单测 | Track 0 | 空环境拒绝主力 UDID |
| 代码 | `purge_live_domain` + lab/replace/GUI 集成 | Track 0 | 三次一致 |
| 代码 | `statusbar_schema.py` + 通用生成器 | Track B | ≥5 entry 稳定 |
| 代码 | 备份恢复管线 | Track D | 10/10 apply/rollback |
| 代码 | CI（单测/链接/plist 往返） | Track G | 绿 |
| 文档 | 飞行模式 verdict（正/负） | Track A | 可复核 |
| 文档 | 兼容性矩阵 | Track C | 覆盖 27.0.x/27.1 |
| 文档 | 状态页 + Superseded 横幅 | Track G | docs hub 可导航 |
| 文档 | 脚注兼容性说明 | Track E | 含边界与回滚 |
| 上游 | GoldenNugget PR / issue | Track F | 已提交并有链接 |
| 发布 | v1.x release + changelog | Track G | 矩阵全绿 |

---

## 8. 未来 72 小时行动清单

1. **修 S1（最优先）**：在 `tools/airlift_carrier_deploy.py` 实现 fail-closed 黑名单；新增单测；确认空环境下无法选中 16 Pro Max。
2. **修 S2**：实现 `purge_live_domain()`，先在 14 Pro 上用 reset 归档验证；再接入 `statusbar_variant_lab`。
3. **建基线**：在 14 Pro 上记录 build、原生归档（如有）、锁屏/CC/主屏截图、当前 VPN 状态。
4. **跑 A1 的前 8 个 variant**：`status=0..5, -1, 255`，固定 `enabled=true`、`displayValue/type` 省略；每个 variant 用可靠 purge；先模拟器后 14 Pro。
5. **写 verdict 草稿**：无论正负，先把实验记录写成 `2026-11-XX_airplane-mode-verdict.md` 的骨架。
6. **文档治理**：给 2026-09-30 / 2026-09-28 的旧结论加 Superseded 横幅；在 docs hub 顶部加本文链接。
7. **上游**：给 GoldenNugget 开一个 issue/PR 草稿，附 VPN 修复的最小 diff 与测试向量。

---

## 附录 A：iOS 27.0（24A434）`SystemStatusUI` 中观察到的候选 entry 键

> 来源：`strings -a SystemStatusUI`。这些是**候选键**，不保证全部被 `STStatusBarData` 接受或渲染；Track B 需逐项验证。

~~~text
activityEntry              airPlayEntry              airplaneModeEntry
alarmEntry                 announceNotificationsEntry assistantEntry
avatarEntry                backNavigationEntry       backgroundActivityEntry
batteryEntry               bluetoothEntry            carPlayEntry
cellularEntry              controlCenterEntry        dateEntry
disabledEntry              displayWarningEntry       electronicTollCollectionEntry
externalPrivacyEntry       externalWirelessChargersEntry
forwardNavigationEntry     liquidDetectionEntry      locationEntry
lockEntry                  mainBatteryEntry          menuBarEntry
nikeEntry                  personNameEntry           quietModeEntry
radarEntry                 ringerSilenceEntry        rotationLockEntry
satelliteEntry             secondaryCellularEntry    sensorActivityEntry
shortTimeEntry             studentEntry              tetheringEntry
thermalEntry               timeEntry                 ttyEntry
voiceControlEntry          vpnEntry                  weatherEntry
wifiEntry
~~~

此外，`STStatusBarDataCellularEntry` 的初始化器暴露了以下字段：

~~~text
type
stringValue
suffixStringValue
crossfadeStringValue
badgeStringValue
wifiCalling
callForwarding
showsSOSWhenDisabled
sosAvailable
isBootstrapCellular
status
numberSharingState
lowDataMode
rawValue
displayValue
displayRawValue
~~~

`STUIStatusBarCellularItem` 还持有 `serviceNameView`、`signalView`、`numberSharingView`、`networkTypeView`、`sosView`、`warningView`、`callForwardingView`、`rawStringView`，并提供 `nameDisplayIdentifier` / `typeDisplayIdentifier` / `rawDisplayIdentifier` 等 display identifier。这些是 Track A5/B1 的直接入口。

---

## 附录 B：实验矩阵模板

| Variant | status | enabled | displayValue | type | isBootstrap | 其他 | 预期 | 实际（锁屏） | 实际（CC） | 飞行模式 | 结论 |
|---|:---:|:---:|:---:|:---:|:---:|---|---|---|---|---|---|
| V0 | 5 | true | 4 | 10 | false | baseline full | 名称+4格+5G | | | | |
| V1 | 5 | true | omit | omit | false | partial | 名称+实时格+无制式 | | | | |
| V2 | 0 | true | omit | omit | false | status 0 | ? | | | | |
| V3 | 1 | true | omit | omit | false | status 1 | ? | | | | |
| V4 | 2 | true | omit | omit | false | status 2 | ? | | | | |
| V5 | 3 | true | omit | omit | false | status 3 | ? | | | | |
| V6 | 4 | true | omit | omit | false | status 4 | ? | | | | |
| V7 | -1 | true | omit | omit | false | sentinel | 预期隐藏 | | | | |
| V8 | 255 | true | omit | omit | false | sentinel | ? | | | | |
| V9 | 5 | true | -1 | -1 | false | sentinel | ? | | | | |
| V10 | 5 | true | 65535 | 255 | false | sentinel | ? | | | | |
| V11 | 5 | true | omit | omit | true | bootstrap | 预期隐藏 | | | | |
| V12 | 5 | false | omit | omit | false | disabled | 预期隐藏 | | | | |
| V13 | 5 | omit | omit | omit | false | omitted enabled | 预期隐藏 | | | | |
| V14 | 5 | true | omit | omit | false | +airplaneModeEntry | ? | | | | |
| V15 | 5 | true | omit | omit | false | +secondaryCellularEntry | ? | | | | |

---

## 附录 C：证据索引与时效性

| 文档 | 主题 | 时效性 | 备注 |
|---|---|:---:|---|
| `2026-09-28_speakeasy-analysis.md` | Speakeasy/FeatureFlags | 仍有效 | 结论：FeatureFlags 静态写入不可行 |
| `2026-09-28_systemstatusui-analysis.md` | 现代状态栏架构 | 仍有效 | 基础架构 |
| `2026-09-28_carrier-data-flow.md` | 数据流 | 仍有效 | 上游链路 |
| `2026-09-28_viable-paths.md` | 路线评估 | **部分过期** | Route 3 已由后续分析覆盖；Route 5 已升级为已交付 |
| `2026-09-28_architecture.md` | 架构与边界 | **部分过期** | AirLift 限制表述需更新为「已实机验证 + 覆盖写限制」 |
| `2026-09-30_carrier-footnote-solution.md` | 脚注/运营商裁决 | **部分过期** | carrier name 仍写「Pending Physical Verification」；已被 2026-10-19/10-21 覆盖 |
| `2026-10-14_commcenter-reverse-engineering.md` | CommCenter 逆向 | 仍有效 | 上游路径关闭的证据 |
| `2026-10-14_dynamic-carrier-status.md` | 动态运营商计划 | **部分过期** | Route A 已于 2026-10-19 判定阴性 |
| `2026-10-19_research-progress-snapshot.md` | 显示域快照 | 仍有效 | 表面差异与 partial 证据 |
| `2026-10-19_commcenter-preference-injection.md` | 偏好注入 | 仍有效 | 阴性结论 |
| `2026-10-19_dynamic-island-analysis.md` | 灵动岛渲染 | 仍有效 | 双卡布局 |
| `2026-10-19_empirical-verification.md` | 模拟器/实机突破 | 仍有效 | 归档格式发现 |
| `2026-10-21_dynamic-carrier-and-vpn-resolution.md` | 终局结论 + VPN | **当前有效** | 原子替换 + VPN 修复 |
| **本文 2026-10-28** | 状态审计 + 路线图 | **当前有效** | 单一入口 |

---

## 附录 D：一句话结论

> **不要再把「飞行模式联动」当作未完成的功能吊在路线图上；把它当作一个 10 天内必须结案的证伪实验。真正值得投入的，是把已经验证的归档原语扩展成通用状态栏覆写引擎，并把交付、兼容性和安全护栏做成可重复的工程。**
