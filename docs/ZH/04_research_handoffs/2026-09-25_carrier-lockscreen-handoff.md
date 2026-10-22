# iOS 27.0 Carrier Name / Lock Screen Footnote Research & Local Agent Handoff

> 项目目标：针对 **iPhone 16 Pro Max（A18 Pro）+ iOS 27.0 正式版**，研究并尽可能实现两个定制目标：
>
> 1. 修改锁屏顶部的运营商显示文本（Carrier Name）。
> 2. 修改锁屏底部导航条上方的文本（Lock Screen Footnote）。
>
> 历史工具：Nugget。升级 iOS 27 后原有 Nugget 路径失效。
>
> 本文档用于交付本地 Agent 做进一步逆向研究、代码分析、实验设计与工具开发。

---

## 1. 用户当前设备与目标

### 设备

- Device: iPhone 16 Pro Max
- SoC: Apple A18 Pro
- OS: iOS 27.0 正式版
- 目标设备不是测试 Beta，必须把 **iOS 27.0 Release** 作为最终兼容目标。

### 目标 A：Carrier Name

希望把系统状态栏/锁屏顶部的运营商文本：

```text
中国移动
AT&T
Verizon
...
```

替换成用户指定的自定义字符串。

### 目标 B：Lock Screen Footnote

希望修改锁屏底部区域、底部导航条上方显示的文本。

---

# 2. 当前核心结论

## 2.1 原版 Nugget

不要在 iOS 27.0 正式版上继续使用原版 Nugget 的旧 restore 路径。

公开项目已经明确警告 iOS 27 的旧 partial restore 路径存在变化，继续使用可能导致数据丢失等问题。

研究方向应该从：

```text
Nugget GUI
```

转向：

```text
iOS 27 System Architecture
+
Restore / File Write Primitive
+
SystemStatusUI
+
Speakeasy
+
Carrier Data Source
```

---

# 3. 两个功能应分开研究

```text
                 iOS 27 Customization
                         |
             +-----------+-----------+
             |                       |
       Lock Screen              Carrier Name
        Footnote                     |
             |                       |
   Apple-supported path       Reverse Engineering
             |                       |
  SharedDeviceConfiguration   SystemStatusUI
  / Configuration Profile       Speakeasy
                               CommCenter
                               Carrier Bundle
                               FeatureFlags
```

不要因为两个功能过去都由 Nugget 提供，就假设它们现在仍然使用同一底层机制。

---

# 4. Lock Screen Footnote

Apple 官方存在对应 Device Management / Configuration Profile 能力：

```text
Payload domain:
com.apple.shareddeviceconfiguration

Key:
LockScreenFootnote
```

该机制用于 Login Window / Lock Screen 的 footnote。

重要限制：

- 官方管理能力通常涉及 Supervision / Device Management。
- 对普通个人 iPhone，不能简单假设安装普通 `.mobileconfig` 就一定生效。
- 这是一个优先级较高、风险相对较低的独立路线。

## GoldenNugget

多个 GoldenNugget fork 仍保留：

```text
SpringBoard Options
    -> Set Lock Screen Footnote
```

因此应优先验证该功能，而不要为了实现 Footnote 去研究 jailbreak。

---

# 5. Carrier Name：当前最关键的技术问题

旧路线大致类似：

```text
Carrier
   |
statusBarOverrides
   |
Classic Status Bar
   |
Custom Carrier String
```

iOS 27 引入/强化了新的状态栏体系：

```text
SpringBoard
    |
SystemStatusUI
    |
Carrier / Wi-Fi / Cellular / Battery / etc.
```

公开逆向研究指出，`Speakeasy` 是旧 Status Bar 与新 SystemStatusUI 之间的重要 feature gate。

概念模型：

```text
SpringBoard
    |
    +-- Speakeasy enabled
    |       |
    |       +--> SystemStatusUI
    |
    +-- legacy path
            |
            +--> classic status bar
                    |
                    +--> statusBarOverrides
```

因此，Carrier Name 的研究必须先回答：

1. iOS 27.0 正式版是否仍存在 `statusBarOverrides` 的消费路径？
2. `Speakeasy` 在正式版中具体是什么机制？
3. `Speakeasy` 是否由 `/var/preferences/FeatureFlags/Settings.plist` 控制？
4. 是否可以通过现有 restore/file-write primitive 改写该 flag？
5. 如果不能关闭 Speakeasy，SystemStatusUI 是否有直接的 Carrier provider / display-name override？
6. Carrier display string 最终由谁提供：CommCenter、Carrier Bundle、MobileGestalt、SystemStatusUI provider 还是其他服务？

---

# 6. GoldenNugget Fork 差异是第一研究入口

目前存在至少两个值得对比的方向。

## Fork A

Repository:

```text
awesomenull-dev/GoldenNugget
```

其公开说明指出 iOS 27+ 的 Status Bar 功能受到限制，核心原因涉及 Speakeasy feature flag 没有写权限。

## Fork B

Repository:

```text
phanquocviet8x/GoldenNugget
```

README 曾标注：

```text
Status Bar (patched on iOS 27)
Change carrier name
```

但是其公开研究资料又指出 Carrier Name 路径受到：

```text
Speakeasy
SystemStatusUI
FeatureFlags
write permission
```

等因素限制。

因此不能仅根据 README 判断 Fork B 已经在 iOS 27.0 正式版实现 Carrier。

### 第一任务

对两个 Fork 做完整 Git diff。

建议：

```bash
git clone https://github.com/awesomenull-dev/GoldenNugget.git GoldenNugget-A
git clone https://github.com/phanquocviet8x/GoldenNugget.git GoldenNugget-B

diff -ru GoldenNugget-A GoldenNugget-B
```

重点搜索：

```bash
grep -Rni "Speakeasy" .
grep -Rni "StatusBar" .
grep -Rni "carrier" .
grep -Rni "statusBarOverrides" .
grep -Rni "FeatureFlags" .
grep -Rni "SystemStatusUI" .
grep -Rni "27.0" .
```

目标：

> 找到 Fork B 所谓 “patched on iOS 27” 的实际代码变化，并判断它是真实可工作的路径，还是未完成/README 与代码不同步。

---

# 7. `Speakeasy` 研究路线

需要确认以下模型是否准确：

```text
FeatureFlags
    |
    +-- SpringBoard
            |
            +-- Speakeasy
                    |
                    +-- SystemStatusUI
```

重点检查：

```text
/var/preferences/FeatureFlags/Settings.plist
```

但不能直接假设：

```text
Speakeasy = false
```

就能解决问题。

必须通过 iOS 27.0 固件逆向确认：

- key 名
- domain
- read path
- write path
- SpringBoard 消费位置
- 是否有 fallback
- 是否存在其他 gate

---

# 8. SystemStatusUI 逆向

这是 Carrier Name 的长期核心路线。

目标：

```text
SystemStatusUI.framework
```

以及相关：

```text
SpringBoard.app
SpringBoardFoundation.framework
SpringBoardServices.framework
CommCenter
Carrier Bundles
```

静态分析工具：

- strings
- nm
- otool
- Hopper
- Ghidra
- IDA（如有）

例如：

```bash
strings SystemStatusUI | grep -i carrier
strings SystemStatusUI | grep -i operator
strings SystemStatusUI | grep -i status
strings SystemStatusUI | grep -i speakeasy
```

进一步：

```bash
nm -arch arm64 SystemStatusUI
otool -ov SystemStatusUI
```

重点寻找概念上类似：

```text
CarrierStatusProvider
CarrierLabel
OperatorName
CarrierDisplayName
CellularStatus
StatusItem
StatusBarItem
```

不要只搜索字符串。

需要建立调用关系：

```text
谁提供 carrier identity
        |
谁转换成 display string
        |
谁把 display string 交给 SystemStatusUI
        |
谁最终渲染 UI
```

---

# 9. 动态分析路线

如果静态分析找到疑似：

```text
-[XXX carrierDisplayName]
```

或类似 provider：

```text
CarrierProvider
CellularStatusProvider
OperatorNameProvider
```

下一阶段研究：

```text
SystemStatusUI
      |
Carrier provider
      |
operatorName
      |
display string
```

观察：

- 调用者
- 调用时机
- 返回值
- 是否存在 override
- 是否存在 fallback
- 是否读取 Preferences
- 是否读取 CommCenter
- 是否读取 MobileGestalt

最终目标是找到最小的 override 点。

如果未来有 jailbreak/tweak 环境，理想结构可能是：

```text
SystemStatusUI
      |
CarrierProvider
      |
Hook carrierDisplayName
      |
return custom string
```

这样不必修改系统文件。

---

# 10. Carrier Bundle 路线

需要调查：

```text
Carrier Bundle
      |
CommCenter
      |
Carrier identity
      |
SystemStatusUI
```

关注：

```text
CFBundleDisplayName
CarrierName
OperatorName
```

以及其他 carrier metadata。

但不能假设修改 Carrier Bundle 就能直接改变最终显示。

必须确认：

```text
Carrier Bundle
   |
CommCenter
   |
returned carrier identity
   |
SystemStatusUI
```

是否真的存在这条链。

---

# 11. MobileGestalt 路线

`bad_query` / MobileGestalt editor 是一个重要方向，但不能把 MobileGestalt 和 Carrier Name 直接等同。

研究流程：

```text
MobileGestalt keys
       |
搜索 Carrier / StatusBar / Operator
       |
确认 SystemStatusUI 是否读取
       |
如果读取：
    研究写入
```

不要盲改 MobileGestalt key。

---

# 12. `bad_query` / sandbox escape 路线

公开 `bad_query` 项目已经验证过部分：

```text
iOS 26.x
iOS 27.0 beta 1
beta 2
beta 3
beta 4
```

但正式版 iOS 27.0 需要单独验证。

非常重要：

```text
27.0 DB4
     |
     +--> exploit works
     |
     v
iOS 27.0 Release
     |
     +--> Apple changed something
```

因此值得做：

```text
DB4 vs iOS 27.0 Release
```

的 binary / system behavior diff。

需要调查：

- ContainerManager
- MobileHouseArrest
- sandbox
- file provider
- backup/restore
- AFC
- system service IPC
- feature flag access

目标不是一定寻找 kernel exploit。

优先寻找：

> 是否存在一个本来就有系统文件写权限的 Apple service，可以通过 IPC/restore/management 接口被普通设备操作利用。

---

# 13. WorkPlot / Erosion

这些项目基于 `bad_query` 类能力，对 iOS 27 Beta 有过验证。

但不能把：

```text
iOS 27 Beta
```

等同于：

```text
iOS 27.0 Release
```

当前设备是 Release，因此需要单独验证。

不要在主力设备上直接运行未经确认的 exploit。

---

# 14. Restore / File Write 路线

需要研究：

```text
Backup
Restore
Sparse Restore
BookRestore
MobileDevice
AFC
HouseArrest
ContainerManager
MDM
Configuration Profile
```

尤其需要回答：

```text
目标文件
    |
能否通过普通 backup 修改？
    |
能否通过 restore 写回？
    |
是否被 allowlist 拒绝？
    |
是否被 Security Recovery 清除？
```

关键目标：

```text
/var/preferences/FeatureFlags/Settings.plist
```

以及可能与 StatusBar/SystemStatusUI 有关的配置文件。

---

# 15. 一个非常重要的实验设计

如果能获得：

```text
iOS 27.0 DB4
```

测试设备，优先进行：

```text
DB4
 |
bad_query
 |
GoldenNugget
 |
StatusBar
 |
Speakeasy
```

然后：

```text
DB4
 |
正式版
 |
同样测试
```

比较：

- 文件是否存在
- 文件权限
- container mapping
- sandbox profile
- service behavior
- restore behavior
- Security Recovery behavior
- FeatureFlags 写入行为

这比盲目尝试 Carrier plist 更有价值。

---

# 16. 推荐的整体研究树

```text
                           iOS 27.0 Carrier
                                  |
                +-----------------+-----------------+
                |                                   |
        数据源/Data Source                     UI/Rendering
                |                                   |
       +--------+---------+                  SystemStatusUI
       |        |         |                         |
   CommCenter Carrier  MobileGestalt          Carrier Provider
       |        |         |                         |
       +--------+---------+                         |
                |                                   |
         Carrier Identity                      Display String
                                                    |
                                             Final UI Rendering
```

与此同时：

```text
                  Status Bar Architecture
                           |
                    Speakeasy Gate
                           |
             +-------------+-------------+
             |                           |
       SystemStatusUI             Classic StatusBar
             |                           |
       New Carrier UI            statusBarOverrides
```

最终要找到其中任意一个可控点。

---

# 17. 路线优先级

建议本地 Agent 按以下顺序工作。

## P0 — 代码事实确认

1. Clone 两个 GoldenNugget fork。
2. 完整 diff。
3. 找出 iOS 27 Status Bar patch。
4. 确认 README 与实际代码是否一致。

## P1 — 固件静态分析

1. 获取准确 iOS 27.0 IPSW。
2. 提取 SystemStatusUI。
3. 分析 SpringBoard。
4. 搜索 Speakeasy。
5. 搜索 Carrier/Operator/StatusBar。
6. 建立调用图。

## P2 — Feature Flag

研究：

```text
/var/preferences/FeatureFlags/Settings.plist
```

确认：

```text
Speakeasy
SpeakeasyNewStatusBar
```

是否存在以及具体消费位置。

## P3 — 写入能力

研究：

```text
backup
restore
AFC
HouseArrest
ContainerManager
MDM
Configuration Profile
```

确认是否有非 jailbreak 的合法/现有写入路径。

## P4 — exploit

只有 P0-P3 无法解决时，再研究：

```text
bad_query
sandbox escape
kernel exploit
jailbreak
```

## P5 — 工具开发

最终目标：

```text
iOS 27 Carrier Customizer
```

理想功能：

```text
Read Current Carrier
Backup Relevant State
Set Custom Carrier
Verify
Restore Original
```

以及独立的：

```text
Lock Screen Footnote Customizer
```

---

# 18. 安全与实验原则

这是主力 iPhone，因此：

### 不要

- 在未确认兼容性的情况下运行 Nugget restore。
- 在没有完整备份的情况下修改系统 plist。
- 修改 Apple ID / Keychain / DataProtection 相关文件。
- 使用来历不明的“iOS 27 Nugget patched”二进制。
- 把 Beta exploit 当成 Release exploit。
- 在不知道恢复路径的情况下写 `/var/preferences`。
- 把 bootloop 风险较高的实验直接放到主力设备。

### 推荐

```text
静态分析
    ↓
模拟/测试环境
    ↓
可重复实验
    ↓
最小写入
    ↓
验证
    ↓
主设备
```

每一次写入前保存：

```text
原始文件
SHA-256
设备备份
实验日志
iOS build
工具 commit
```

---

# 19. 本地 Agent 第一阶段 Prompt

可以直接把下面内容交给本地 Agent：

> 你正在研究 iPhone 16 Pro Max（A18 Pro）运行 iOS 27.0 Release 上的系统 UI 定制问题。
>
> 目标：
>
> 1. 修改 Lock Screen Footnote。
> 2. 修改 Lock Screen / Status Bar Carrier Name。
>
> 不要假设 Nugget 在 iOS 27 仍然有效。
>
> 第一阶段禁止直接对主力设备执行 restore、system plist 写入、exploit 或其他高风险操作。
>
> 第一阶段只做静态代码分析。
>
> 任务：
>
> 1. Clone：
>    - awesomenull-dev/GoldenNugget
>    - phanquocviet8x/GoldenNugget
>
> 2. 完整 diff 两个项目。
>
> 3. 搜索：
>    - Speakeasy
>    - SpeakeasyNewStatusBar
>    - SystemStatusUI
>    - statusBarOverrides
>    - Carrier
>    - Operator
>    - FeatureFlags
>    - LockScreenFootnote
>
> 4. 明确回答：
>    - phanquocviet8x 所谓 “patched on iOS 27” 到底修改了什么？
>    - 这个 patch 是否真的能够在 iOS 27.0 Release 修改 Carrier？
>    - 它依赖什么写入 primitive？
>    - 是否依赖 Beta-only exploit？
>    - README 是否与实际代码一致？
>
> 5. 获取 iOS 27.0 Release IPSW 后分析：
>    - SpringBoard
>    - SystemStatusUI
>    - SpringBoardFoundation
>    - SpringBoardServices
>    - CommCenter
>    - Carrier Bundles
>
> 6. 搜索并建立：
>
>    SIM
>    -> CommCenter
>    -> Carrier Identity
>    -> SystemStatusUI
>    -> Carrier Display String
>    -> Final UI
>
> 7. 研究：
>
>    /var/preferences/FeatureFlags/Settings.plist
>
>    判断 Speakeasy 的具体实现、读取点和写入限制。
>
> 8. 研究 `statusBarOverrides` 是否仍被 iOS 27.0 Release 的 SpringBoard 消费。
>
> 9. 研究 `bad_query` 从 iOS 27 beta 4 到 iOS 27.0 Release 的失效原因，重点关注：
>    - sandbox
>    - ContainerManager
>    - MobileHouseArrest
>    - backup/restore
>    - file-write primitive
>
> 10. 最终输出：
>
>    - architecture.md
>    - golden-nugget-diff.md
>    - speakeasy-analysis.md
>    - systemstatusui-analysis.md
>    - carrier-data-flow.md
>    - exploit-surface.md
>    - viable-paths.md
>    - risk-register.md
>
> 每个结论必须区分：
>
> - 已验证
> - 从代码确认
> - 从固件确认
> - 社区报告
> - 推测
>
> 不要把 README 声明当作事实。
>
> 如果找到可行路线，先给出：
>
> 1. 原理
> 2. 必要条件
> 3. 所需权限
> 4. 所需 exploit
> 5. 是否支持 iOS 27.0 Release
> 6. 风险
> 7. 恢复方案
>
> 再考虑开发工具。
>
> 优先目标不是“尽快执行”，而是找出 iOS 27.0 Release 上真正可验证的最小修改路径。

---

# 20. 成功标准

最终研究成功不应该定义成：

> “网上有人说可以。”

而应该定义为：

```text
iPhone 16 Pro Max
        |
iOS 27.0 Release
        |
无需依赖未验证 Beta exploit
        |
能够修改 Carrier Display String
        |
能够恢复原始状态
```

以及：

```text
iPhone 16 Pro Max
        |
iOS 27.0 Release
        |
LockScreenFootnote
        |
修改成功
        |
恢复成功
```

---

# 21. 研究记录模板

每个实验记录：

```text
Date:
Device:
iOS:
Build:
Tool:
Git Commit:
Operation:
Target:
Original SHA256:
Modified SHA256:
Result:
Reboot Result:
Respring Result:
Data Loss:
Recovery:
Notes:
```

---

# 22. 当前最重要的技术假设

### 假设 H1

`statusBarOverrides` 仍然存在，并且如果关闭/绕过 `Speakeasy`，旧 Status Bar 可以重新使用。

### 假设 H2

`Speakeasy` 是可修改的 Feature Flag。

### 假设 H3

即使不能修改 Speakeasy，SystemStatusUI 中存在 Carrier display-name provider，可以通过配置或未来 hook 修改。

### 假设 H4

Carrier Name 来自 CommCenter / Carrier Bundle，而不是完全由 SystemStatusUI 内部生成。

### 假设 H5

iOS 27.0 Release 与 27.0 beta 4 的主要差异是 Apple 修复了公开 sandbox/file-write primitive，而不是完全改变 Status Bar architecture。

这些都需要实验验证，不能直接作为事实。

---

# 23. 结论

当前最值得挖的不是继续寻找“另一个 Nugget”。

真正值得研究的是：

```text
                 iOS 27.0
                    |
            +-------+-------+
            |               |
        Speakeasy       SystemStatusUI
            |               |
       FeatureFlags      Carrier Provider
            |               |
       Legacy Status     Display String
            |               |
   statusBarOverrides    Final Carrier
```

其中：

**P0：GoldenNugget 两个 fork 的代码差异**

↓

**P1：Speakeasy / FeatureFlags**

↓

**P2：SystemStatusUI Carrier provider**

↓

**P3：iOS 27.0 Release 的 file-write / restore primitive**

↓

**P4：如果必要，再研究 sandbox escape / jailbreak**

这是目前最系统、可验证、且风险最低的研究路线。

---

## 参考项目 / 资料

- Nugget: https://github.com/leminlimez/Nugget
- GoldenNugget (awesomenull-dev): https://github.com/awesomenull-dev/GoldenNugget
- GoldenNugget (phanquocviet8x): https://github.com/phanquocviet8x/GoldenNugget
- bad_query: https://github.com/forcequitOS/bad_query
- WorkPlot: https://github.com/gievano/WorkPlot
- Erosion: https://github.com/jailbreakdotparty/Erosion
- Apple Device Management — Lock Screen Message: https://developer.apple.com/documentation/devicemanagement/lockscreenmessage
