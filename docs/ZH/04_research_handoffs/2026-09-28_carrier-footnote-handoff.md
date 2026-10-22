# iOS 27.0 锁屏 Carrier Name / Lock Screen Footnote 研究交接文档

> 目标设备：iPhone 16 Pro Max / iOS 27.0 / Build 24A437
>
> 目标：1. 修改锁屏顶部 Carrier Name；2. 修改锁屏底部 Lock Screen Footnote。
>
> 本文档供本地 Agent 继续源码审查、逆向分析和实机验证。

## 1. 当前结论

截至 2026-09-28，最值得继续研究的路线已经从旧版 Nugget / `bad_query` 转向：

```text
AirLift
  ↓
iOS 27.0 AirTraffic sandbox escape / 文件访问
  ↓
/var/mobile/Library/SpringBoard
  ↓
SpringBoard / SystemStatusUI 配置
  ├─ Carrier Name
  └─ Lock Screen Footnote
```

关键问题不是“有没有工具”，而是：

- iOS 27.0 Final 是否仍读取 `statusBarOverrides`
- 新的 `Speakeasy` / `SystemStatusUI` 是否绕过旧状态栏路径
- Footnote 的真实配置位置是否仍可被 AirLift 访问
- GoldenNugget 所谓 iOS 27 patch 到底修改了什么

目前**没有足够证据证明两项功能都可以直接在 iPhone 16 Pro Max / iOS 27.0 Final 上成功**。

## 2. AirLift

项目：

https://github.com/0xjohnnydev/airlift

AirLift 是针对 iOS 27.0 AirTraffic 的 sandbox escape / 文件访问工具，不是传统美化工具。

公开资料显示其重点能力包括：

- 已配对 Mac
- USB / Wi-Fi
- 不要求完整 Jailbreak
- iPhone 不需要安装额外 App
- 可访问部分 `/var/mobile` 子路径
- 包含 `/var/mobile/Library`
- 包含 `/var/mobile/Library/Preferences`
- 包含 `/var/mobile/Library/SpringBoard`
- 包含 `/var/mobile/Containers`
- 包含 `/var/mobile/Containers/Data/Application`
- 包含 `/var/mobile/Containers/Shared/AppGroup`
- 包含 `/var/tmp`

重要限制：公开资料显示它不能随意修改所有系统数据，例如 `MobileGestalt.plist`。

因此：

```text
AirLift != Jailbreak
AirLift != 任意系统文件写权限
AirLift = 特定 sandbox / path validation 绕过
```

必须继续验证：

1. 能否读取 `/var/mobile/Library/SpringBoard/statusBarOverrides`
2. 能否覆盖该文件
3. 能否访问 Footnote 相关配置
4. 修改后 SpringBoard 是否读取
5. 是否需要 respring / reboot
6. iOS 27.0 Final 24A437 是否保持相同行为

## 3. AirCard-iOS

项目：

https://github.com/EpochME/aircard-ios

该项目使用 AirLift 相关的 `AirliftFFI.xcframework`，用于 iOS 27 定制，例如 Wallet、锁屏密码键盘主题、PosterBoard 等。

价值：

```text
AirLift 已经被其他项目作为实际 iOS 27 定制基础设施使用。
```

但 AirCard-iOS 成功并不能直接证明 Carrier Name / Footnote 可修改。

应重点研究：

- AirLift 初始化
- AirliftFFI
- 文件读写 API
- sandbox escape 后路径处理
- iOS 27 compatibility check
- rollback / restore

## 4. GoldenNugget 必须源码对比

### GoldenNugget-Team

https://github.com/GoldenNugget-Team/GoldenNugget

公开资料显示 iOS 27+ Status Bar 存在限制，并涉及 `Speakeasy`；Lock Screen Footnote 仍有相关功能。

### phanquocviet8x GoldenNugget

https://github.com/phanquocviet8x/GoldenNugget

其公开说明声称：

```text
Status Bar
patched on iOS 27
Change carrier name
```

但其研究说明又涉及 Carrier Name 被系统限制、Speakeasy、SystemStatusUI、exploit / jailbreak 等问题。

因此必须源码验证：

> “patched on iOS 27” 是否真正实现 Carrier Name 修改，而不是只保留功能入口。

建议：

```bash
git clone https://github.com/GoldenNugget-Team/GoldenNugget.git GoldenNugget-Team
git clone https://github.com/phanquocviet8x/GoldenNugget.git GoldenNugget-phan
diff -ru GoldenNugget-Team GoldenNugget-phan

grep -Rni "Speakeasy" GoldenNugget-Team GoldenNugget-phan
grep -Rni "StatusBar" GoldenNugget-Team GoldenNugget-phan
grep -Rni "carrier" GoldenNugget-Team GoldenNugget-phan
grep -Rni "statusBarOverrides" GoldenNugget-Team GoldenNugget-phan
grep -Rni "FeatureFlags" GoldenNugget-Team GoldenNugget-phan
grep -Rni "SystemStatusUI" GoldenNugget-Team GoldenNugget-phan
grep -Rni "LockScreenFootnote" GoldenNugget-Team GoldenNugget-phan
grep -Rni "27.0" GoldenNugget-Team GoldenNugget-phan
```

最终必须确定：

```text
Carrier Name 实际修改路径
Footnote 实际修改路径
iOS 27 修改点
Speakeasy 绕过方式
是否依赖 restore
是否依赖 MobileGestalt
是否依赖 jailbreak
是否能改成 AirLift direct-write
```

## 5. Carrier Name：旧路线

历史 Nugget / GoldenNugget 的重要路径：

```text
HomeDomain
└── Library
    └── SpringBoard
        └── statusBarOverrides
```

概念路径：

```text
/var/mobile/Library/SpringBoard/statusBarOverrides
```

第一优先级研究：

```text
AirLift
  ↓
statusBarOverrides
  ↓
Carrier-related entry
  ↓
SpringBoard / SystemStatusUI
  ↓
Carrier Name
```

注意：这只是研究假设，不是已证明的 iOS 27.0 Final 方案。

## 6. iOS 27 新状态栏架构

需要重点研究：

```text
SpringBoard
  ├─ legacy Status Bar
  │    └─ statusBarOverrides
  │
  └─ Speakeasy
       └─ SystemStatusUI
            └─ Carrier provider / display string
```

必须回答：

### 情况 A

SystemStatusUI 仍读取 `statusBarOverrides`。

→ AirLift + `statusBarOverrides` 可能直接解决 Carrier Name。

### 情况 B

Speakeasy / SystemStatusUI 完全绕过 `statusBarOverrides`。

→ 需要逆向 SystemStatusUI 的 Carrier provider / display string。

### 情况 C

Speakeasy feature flag 控制 legacy/new UI。

→ 如果能安全切回 legacy，可能恢复旧路线。

## 7. Speakeasy

重点搜索：

```text
Speakeasy
SpeakeasyNewStatusBar
FeatureFlags
SystemStatusUI
```

公开逆向资料曾涉及类似：

```text
/var/preferences/FeatureFlags/Settings.plist
```

但不要假设这些路径、key 或写入方法在 iOS 27.0 Final 24A437 仍有效。

必须从：

- 当前 GoldenNugget 源码
- 当前系统二进制
- 实机文件
- 相关公开逆向资料

重新确认。

## 8. Lock Screen Footnote

历史 Apple 配置体系存在：

```text
com.apple.shareddeviceconfiguration
LockScreenFootnote
```

GoldenNugget 也保留：

```text
Set Lock Screen Footnote
```

必须确定：

1. 官方支持方式
2. 是否要求 supervised / MDM
3. 实际 plist / configuration profile 路径
4. iOS 27 是否改变存储位置
5. GoldenNugget 实际写入什么
6. AirLift 是否可以访问
7. 修改后需要什么刷新机制
8. 是否存在 iOS 27.0 Final 实机成功案例

## 9. CarrierSIM 旁证

近期公开资料出现 CarrierSIM 一类基于 AirLift 的 iOS 27.0 Carrier configuration 修改项目。

其目标不是 Carrier Name，而是运营商配置 / 5G capability。

研究价值：

```text
AirLift
  ↓
Carrier configuration
  ↓
iOS 27 实际系统行为变化
```

但不要将其成功直接推导为 Carrier Name 可修改；必须分别确认文件、daemon、缓存和 UI provider。

## 10. 旧 exploit 路线优先级

### bad_query

https://github.com/forcequitOS/bad_query

主要是 iOS 27 beta sandbox escape 研究。当前公开资料与 Final 24A437 的直接兼容性需要重新验证。

### WorkPlot

https://github.com/gievano/WorkPlot

早期 iOS 27 exploit / sandbox 研究。

### Erosion

https://github.com/jailbreakdotparty/Erosion

同样可作为 exploit 历史资料，但当前优先级低于 AirLift。

## 11. 推荐优先级

```text
P0
├─ GoldenNugget 源码 diff
├─ 找到 Carrier Name 写入路径
└─ 找到 LockScreenFootnote 写入路径

P1
├─ AirLift 源码
├─ AirliftFFI
└─ AirCard-iOS 集成

P2
├─ statusBarOverrides
├─ SystemStatusUI
├─ Speakeasy
└─ FeatureFlags

P3
└─ 测试设备进行最小化只读 / 无害写入验证

P4
├─ Carrier Name
└─ Lock Screen Footnote

P5
└─ 若以上失败，再考虑 exploit / jailbreak
```

## 12. 设备实验策略

### 第一阶段：只读

验证：

```text
AirLift
  ↓
/var/mobile/Library/SpringBoard/
```

只读，不修改。

### 第二阶段：无害文件

验证：

```text
write
read
delete
```

例如建立测试文件并确认完整生命周期。

### 第三阶段：备份目标文件

任何系统配置修改前：

```text
original file
  ↓
SHA-256
  ↓
local backup
  ↓
modified copy
```

记录：

```text
iOS version
Build
device model
file path
file size
SHA256
timestamp
```

## 13. 不要首先做的事情

不要直接：

```text
修改 MobileGestalt
删除系统 plist
restore 整个 HomeDomain
修改未知 FeatureFlags
执行来源不明 jailbreak / exploit binary
```

尤其不要在没有恢复方案时修改：

```text
SpringBoard
SystemStatusUI
MobileGestalt
Data Protection
Keychain
Apple Account
iCloud
```

相关关键文件。

## 14. 本地 Agent 必须回答的问题

### Carrier Name

```text
1. iOS 27.0 24A437 是否仍存在 statusBarOverrides？
2. SpringBoard 是否读取它？
3. SystemStatusUI 是否读取它？
4. Speakeasy 是否绕过它？
5. GoldenNugget 的 iOS 27 patch 实际修改了什么？
6. AirLift 是否可以读写该文件？
7. 修改后需要 respring 还是 reboot？
8. 是否有实际成功案例？
9. 成功案例对应什么 iOS Build？
10. 是否适用于 iPhone 16 Pro Max / A18 Pro？
```

### Lock Screen Footnote

```text
1. LockScreenFootnote 当前真实配置来源是什么？
2. 是否仍使用 com.apple.shareddeviceconfiguration？
3. 实际 plist / database 路径是什么？
4. iOS 27 是否改变存储位置？
5. GoldenNugget 实际写入什么？
6. AirLift 是否能访问？
7. 修改后需要什么刷新机制？
8. 是否有 iOS 27.0 Final 实际成功案例？
```

## 15. 最终 Agent 产物

最终形成：

```text
iOS27_Carrier_Footnote_Solution.md
```

建议结构：

```text
# Executive Summary
# Device / Build
# Current iOS 27 Architecture
# AirLift Analysis
# AirCard-iOS Analysis
# GoldenNugget Diff
# Carrier Name Reverse Engineering
# statusBarOverrides
# Speakeasy
# SystemStatusUI
# LockScreenFootnote
# File Paths
# Required Permissions
# Working Methods
# Failed Methods
# Device Compatibility
# Risk Assessment
# Backup / Recovery
# Step-by-Step Experiment
# Rollback Procedure
# Final Conclusion
```

每一项结论必须标注：

```text
Confirmed
Highly Likely
Hypothesis
Not Working
Unknown
```

所有“已验证”必须注明：

```text
iOS version
Build
Device
Project
Commit / Release
```

不要把 beta 版本结果当作 iOS 27.0 Final 结果。

## 16. 关键仓库

- AirLift: https://github.com/0xjohnnydev/airlift
- AirCard-iOS: https://github.com/EpochME/aircard-ios
- GoldenNugget-Team: https://github.com/GoldenNugget-Team/GoldenNugget
- phanquocviet8x/GoldenNugget: https://github.com/phanquocviet8x/GoldenNugget
- bad_query: https://github.com/forcequitOS/bad_query
- WorkPlot: https://github.com/gievano/WorkPlot
- Erosion: https://github.com/jailbreakdotparty/Erosion

## 17. Agent 执行 Prompt

你现在接手的是一个 iPhone 16 Pro Max / iOS 27.0 Build 24A437 的系统定制逆向研究任务。

目标：

1. 修改 Lock Screen 顶部 Carrier Name
2. 修改 Lock Screen Bottom Footnote

不要直接假设旧 Nugget 路线仍然有效。

优先研究：

```text
AirLift
AirCard-iOS
GoldenNugget-Team
phanquocviet8x/GoldenNugget
statusBarOverrides
Speakeasy
SystemStatusUI
LockScreenFootnote
```

首先进行源码静态分析。

必须回答：

```text
A. Carrier Name 的实际数据路径
B. Footnote 的实际数据路径
C. iOS 27 新状态栏架构
D. statusBarOverrides 是否仍被读取
E. Speakeasy 的具体作用
F. GoldenNugget 的 iOS 27 patch 到底改了什么
G. AirLift 是否能完成必要的 read/write
H. 是否存在 iOS 27.0 Final 24A437 实机成功案例
```

如果发现可行路线：

1. 给出原始文件路径
2. 给出原始数据结构
3. 给出修改前后示例
4. 给出 AirLift 操作方式
5. 给出 SpringBoard 刷新方式
6. 给出完整 rollback
7. 给出风险
8. 明确是否需要 jailbreak

如果无法实现，不要简单写“不可行”，必须说明：

```text
哪个环节阻断
为什么阻断
是权限问题 / 文件不存在 / UI 不读取 / daemon 覆盖 / feature flag / exploit 限制
有没有替代路径
```

最终形成可执行的：

```text
iOS27_Carrier_Footnote_Solution.md
```
