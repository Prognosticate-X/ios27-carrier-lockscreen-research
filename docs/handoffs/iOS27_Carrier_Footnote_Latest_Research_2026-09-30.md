# iOS 27.0 Carrier Name / Lock Screen Footnote 最新研究交接文档

更新时间：2026-09-30  
目标设备：iPhone 16 Pro Max / iOS 27.0 / Build 24A437

## 核心结论

本轮研究有四个重要更新：

1. **PyAirLift 已明确处理 iOS 27.0 / 24A437。**
2. **AirLift 的关键限制被进一步确认：底层 ATAirlock 使用 rename 机制，不能简单覆盖一个已经存在的目标文件。** 因此“AirLift → 直接覆盖 `/var/mobile/Library/SpringBoard/statusBarOverrides`”不能视为已验证方案。
3. **GoldenNugget-Mobile 已成为 Footnote 的核心研究对象**：它是 iOS 27 on-device customization 项目，并明确包含 `Set Lock Screen Footnote`。
4. **Carrier Name 应扩大到 SystemStatusUI / Speakeasy / CommCenter / Carrier Bundle 的完整 data-flow，而不能继续只盯着 `statusBarOverrides`。**

---

# 1. AirLift

项目：

https://github.com/0xjohnnydev/airlift

公开资料显示其能力包括：

- 已配对 Mac
- USB / Wi-Fi
- 不要求完整 Jailbreak
- iPhone 不需要额外 App
- 可访问部分 `/var/mobile`
- `/var/mobile/Library`
- `/var/mobile/Library/Preferences`
- `/var/mobile/Library/SpringBoard`
- `/var/mobile/Containers`
- `/var/mobile/Containers/Data/Application`
- `/var/mobile/Containers/Shared/AppGroup`
- `/var/tmp`

定义：

```text
AirLift != Jailbreak
AirLift != 任意系统文件写权限
AirLift = 特定 AirTraffic sandbox / path validation 绕过
```

---

# 2. PyAirLift：24A437 已进入工具链

项目：

https://github.com/awesomenull-dev/PyAirLift

PyAirLift 是 AirLift 的 Python 实现，可结合 `pymobiledevice3` 使用。

公开 compatibility check 已出现：

```text
version: 27.0
build: 24A437
```

因此：

```text
AirLift / PyAirLift 识别 iOS 27.0 / 24A437
= Confirmed
```

但这不等于：

```text
iPhone 16 Pro Max / 24A437
+
Carrier Name / Footnote
= 已成功
```

目标设备上的最终验证仍为：

```text
Unknown
```

---

# 3. 关键限制：不能简单 overwrite 已存在文件

PyAirLift / ATAirlock 的文件写入利用 rename 机制，因此核心限制是：

```text
只能写入目标目录中不存在的新文件名
```

所以：

```text
目标文件不存在
→ create / rename
→ 可行
```

但：

```text
目标文件已经存在
→ 简单 overwrite
→ 不可直接成立
```

这会直接影响：

```text
/var/mobile/Library/SpringBoard/statusBarOverrides
```

等旧 Nugget 配置文件。

因此此前：

```text
AirLift
→ 直接覆盖 statusBarOverrides
```

必须降级为：

```text
Hypothesis / Restricted
```

Agent 必须研究：

```text
A. delete 原文件是否可行
B. rename 原文件是否可行
C. symlink workaround
D. 创建 SpringBoard 会自动读取的新文件
E. backup / restore 间接替换
F. 其他 daemon 是否能完成 overwrite
G. GoldenNugget-Mobile 是否已有 workaround
```

---

# 4. GoldenNugget-Mobile：当前 Footnote 最重要项目

项目：

https://github.com/GoldenNugget-Team/GoldenNugget-mobile

它是 iOS 27 on-device customization 项目，公开资料中明确存在：

```text
Set Lock Screen Footnote
```

并使用 AirLift 相关技术。

当前公开功能表没有明确把：

```text
Change Carrier Name
```

列为同等级的 Mobile 功能。

因此目前出现很清晰的信号：

```text
AirLift
  +
iOS 27 on-device customization
  +
Lock Screen Footnote
```

已经进入实际项目。

Agent 应直接 clone：

```bash
git clone https://github.com/GoldenNugget-Team/GoldenNugget-mobile.git
```

然后：

```bash
grep -Rni "LockScreenFootnote" .
grep -Rni "Footnote" .
grep -Rni "shareddeviceconfiguration" .
grep -Rni "AirLift" .
grep -Rni "Airlift" .
grep -Rni "restore" .
grep -Rni "SpringBoard" .
grep -Rni "respring" .
grep -Rni "rename" .
grep -Rni "backup" .
```

必须追踪：

```text
UI
→ Footnote action
→ payload / plist
→ target file
→ write mechanism
→ refresh / respring
→ rollback
```

---

# 5. Apple 官方 LockScreenFootnote

Apple Device Management schema：

```text
com.apple.shareddeviceconfiguration
```

包含：

```text
LockScreenFootnote
```

参考：

https://github.com/apple/device-management/blob/release/mdm/profiles/com.apple.shareddeviceconfiguration.yaml

这是 Apple 官方配置体系中的正式字段，并非 Nugget 自创字段。

需要继续确认：

1. iOS 27 实际文件来源
2. GoldenNugget-Mobile 实际写入位置
3. 是否需要 supervised
4. 是否通过 configuration profile
5. 是否可以被 AirLift 间接修改
6. SpringBoard 如何刷新

当前证据：

```text
Apple LockScreenFootnote
= Confirmed

GoldenNugget iOS 27 Footnote feature
= Confirmed

iPhone 16 Pro Max / 24A437 实际成功
= Unknown
```

---

# 6. Carrier Name：官方 GoldenNugget

项目：

https://github.com/GoldenNugget-Team/GoldenNugget

官方 README 当前明确说明：

```text
Status Bar
disabled on iOS 27+
```

原因涉及：

```text
Speakeasy feature flag
write permissions
```

历史功能包括：

```text
Change carrier name
Change secondary carrier name
```

因此当前官方路线：

```text
Carrier Name
→ legacy Status Bar
→ iOS 27
→ Speakeasy
→ write permission problem
→ Status Bar disabled
```

当前等级：

```text
Official GoldenNugget Carrier Name on iOS 27
= Not Working / Disabled
```

---

# 7. phanquocviet8x GoldenNugget

项目：

https://github.com/phanquocviet8x/GoldenNugget

其 README 声称：

```text
Status Bar (patched on iOS 27)

Change carrier name
Change secondary carrier name
```

但尚无足够可靠证据证明：

```text
iPhone 16 Pro Max
+
iOS 27.0 Final
+
24A437
+
Carrier Name
```

已成功。

因此：

```text
Claimed / Unverified
```

必须通过源码 diff，而不是 README 判断。

---

# 8. Carrier Name：研究范围扩大

不能再只研究：

```text
statusBarOverrides
```

应建立完整 data-flow：

```text
Cellular / CommCenter
        ↓
Carrier configuration
        ↓
Carrier Bundle
        ↓
CoreTelephony / Telephony
        ↓
SystemStatusUI
        ↓
Speakeasy
        ↓
Carrier display
        ↓
Lock Screen / Status Bar
```

核心问题：

> `statusBarOverrides` 在 iOS 27 的实际 data-flow 中究竟处于哪一层？

---

# 9. iOS 27.0 Carrier Bundle：新的研究入口

项目：

https://github.com/VCTGomes/ios-carrier-bundle

以及：

https://github.com/dwilliamsuk/ios-carrier-bundles

公开数据已经包含：

```text
iOS 27.0 / 24A437
```

传统系统路径：

```text
/System/Library/Carrier Bundles/iPhone/
```

Carrier Bundle 可能涉及：

- APN
- VoLTE
- VoWiFi
- 5G
- RCS
- tethering
- voicemail
- emergency call behavior
- carrier-specific configuration / strings

部分公开数据还包含 iPhone 16 / iPhone 16 Pro Max 对应文件。

但不要直接假设：

```text
Carrier Bundle
→ Carrier Name
```

真正需要研究：

```text
Carrier Bundle
→ CommCenter
→ CoreTelephony
→ SystemStatusUI
```

或者是否存在中间缓存 / generated state。

也不要因为发现 Carrier Bundle 就直接修改：

```text
/System/Library/Carrier Bundles/iPhone/
```

AirLift 已确认的 `/var/mobile` 能力不能直接推出对系统分区的写权限。

---

# 10. AirCard-iOS

项目：

https://github.com/Mak5er/AirCard-iOS

使用：

```text
AirliftFFI.xcframework
```

面向：

```text
iOS 27.0+
```

并用于实际设备定制。

重点研究：

```text
AirLift initialization
AirliftFFI
Rust core
file write
rollback
refresh / respring
```

尤其检查它或依赖项目有没有解决：

```text
existing file overwrite
```

这个问题。

---

# 11. 旧 exploit 路线

## bad_query

https://github.com/forcequitOS/bad_query

iOS 27 beta sandbox escape 研究，当前不作为 Final 24A437 第一优先级。

## WorkPlot

https://github.com/gievano/WorkPlot

早期 iOS 27 exploit / sandbox 研究。

## Erosion

https://github.com/jailbreakdotparty/Erosion

同样作为历史研究参考。

当前优先级：

```text
AirLift > bad_query / WorkPlot / Erosion
```

---

# 12. 当前重新排序后的路线

## P0 — GoldenNugget-Mobile Footnote

```text
GoldenNugget-Mobile
→ LockScreenFootnote
→ actual target file
→ AirLift / restore mechanism
→ refresh
```

这是目前最接近实际可执行路线的部分。

## P1 — PyAirLift overwrite 限制

必须解决：

```text
existing file
→ 为什么不能 overwrite
→ 是否有 delete / rename / restore workaround
```

## P2 — GoldenNugget 两分支 Carrier Name diff

```text
GoldenNugget-Team
vs
phanquocviet8x/GoldenNugget
```

重点：

```text
Carrier
StatusBar
Speakeasy
FeatureFlags
SystemStatusUI
statusBarOverrides
```

## P3 — SystemStatusUI / Speakeasy

如果 `statusBarOverrides` 已失效：

```text
SystemStatusUI
+
Speakeasy
+
Carrier provider
```

成为主线。

## P4 — Carrier Bundle / CommCenter

建立：

```text
Carrier Bundle
↓
CommCenter
↓
CoreTelephony
↓
SystemStatusUI
```

data-flow。

## P5 — 实机实验

只在静态分析完成后进行：

```text
read
→ backup
→ hash
→ minimal write
→ refresh
→ verify
```

---

# 13. 当前证据矩阵

| 项目 | 状态 | 证据等级 |
|---|---|---|
| AirLift iOS 27 | 公开项目 | Confirmed |
| PyAirLift 24A437 | compatibility check | Confirmed |
| AirLift `/var/mobile/Library/SpringBoard` | README | Confirmed |
| AirLift 直接覆盖已有文件 | ATAirlock rename 限制 | Not Working / Restricted |
| AirCard-iOS + AirLift | 实际 iOS 27 项目 | Confirmed |
| GoldenNugget-Mobile | iOS 27 on-device | Confirmed |
| GoldenNugget-Mobile Footnote | 功能列表 | Confirmed as feature |
| Apple LockScreenFootnote | 官方 schema | Confirmed |
| 24A437 + iPhone 16 Pro Max Footnote | 未找到可靠实机证据 | Unknown |
| 旧 statusBarOverrides Carrier Name | 历史有效 | Confirmed historically |
| 官方 GoldenNugget iOS 27 Carrier Name | Status Bar disabled | Not Working |
| phanquocviet8x Carrier Name patch | README 声称 | Claimed / Unverified |
| 24A437 + iPhone 16 Pro Max Carrier Name | 未找到可靠实机证据 | Unknown |
| iOS 27 Carrier Bundle 数据 | 已公开 | Confirmed |
| Carrier Bundle → Carrier Name 直接关系 | 未证实 | Hypothesis |
| Speakeasy → 新 Status Bar | 需要继续逆向 | Highly Likely / Needs verification |

---

# 14. 安全要求

任何实机实验前：

```text
1. 完整备份 iPhone
2. 记录 iOS Build
3. 记录 Device Model
4. 保存原始文件
5. SHA-256
6. 保存修改日志
7. 准备 rollback
```

不要首先操作：

```text
MobileGestalt
Keychain
Data Protection
Apple Account
iCloud
系统关键数据库
```

不要直接执行未知：

```text
restore
exploit
jailbreak
system file deletion
```

---

# 15. 本地 Agent 下一阶段任务

## Task A — GoldenNugget-Mobile

找到：

```text
LockScreenFootnote
→ target file
→ write method
→ refresh method
→ rollback
```

## Task B — PyAirLift

审查：

```text
ATAirlock
rename
write
file existence
path validation
```

寻找：

```text
existing-file workaround
```

## Task C — GoldenNugget Diff

比较：

```text
GoldenNugget-Team
vs
phanquocviet8x/GoldenNugget
```

重点：

```text
Carrier
StatusBar
Speakeasy
FeatureFlags
SystemStatusUI
statusBarOverrides
```

## Task D — Carrier Bundle

获取 iOS 27.0 / 24A437 Carrier Bundle。

针对：

```text
iPhone 16 Pro Max
```

做：

```text
plist diff
strings
CarrierName
OperatorName
StatusBar
```

## Task E — SystemStatusUI

如果可以取得 iOS 27.0 对应系统二进制，分析：

```text
SystemStatusUI
SpringBoard
CommCenter
CoreTelephony
```

建立 Carrier display data-flow。

---

# 16. 最终 Agent 产物

生成：

```text
iOS27_Carrier_Footnote_Solution.md
```

建议：

```text
# Executive Summary
# Device / Build
# Current iOS 27 Architecture
# AirLift Analysis
# PyAirLift Analysis
# GoldenNugget-Mobile Analysis
# GoldenNugget Diff
# Carrier Name Data Flow
# statusBarOverrides
# Speakeasy
# SystemStatusUI
# Carrier Bundles
# LockScreenFootnote
# File Paths
# Write Mechanism
# Refresh Mechanism
# Working Methods
# Failed Methods
# Device Compatibility
# Risk Assessment
# Backup / Recovery
# Step-by-Step Experiment
# Rollback Procedure
# Final Conclusion
```

最终必须使用：

```text
Confirmed
Highly Likely
Claimed / Unverified
Hypothesis
Not Working
Unknown
```

所有“已验证”必须注明：

```text
iOS version
Build
Device
Repository
Commit / Release
```

如果 README 与源码冲突，以源码和可复现实验为准。

---

# 17. 关键项目

- AirLift: https://github.com/0xjohnnydev/airlift
- PyAirLift: https://github.com/awesomenull-dev/PyAirLift
- AirCard-iOS: https://github.com/Mak5er/AirCard-iOS
- GoldenNugget-Team: https://github.com/GoldenNugget-Team/GoldenNugget
- GoldenNugget-Mobile: https://github.com/GoldenNugget-Team/GoldenNugget-mobile
- phanquocviet8x GoldenNugget: https://github.com/phanquocviet8x/GoldenNugget
- iOS Carrier Bundle: https://github.com/VCTGomes/ios-carrier-bundle
- iOS Carrier Bundles: https://github.com/dwilliamsuk/ios-carrier-bundles
- bad_query: https://github.com/forcequitOS/bad_query
- WorkPlot: https://github.com/gievano/WorkPlot
- Erosion: https://github.com/jailbreakdotparty/Erosion

---

# 18. Agent 执行 Prompt

你现在接手：

```text
Device:
iPhone 16 Pro Max

OS:
iOS 27.0

Build:
24A437
```

目标：

```text
1. Lock Screen Carrier / Operator Name
2. Lock Screen Bottom Footnote
```

不要直接使用旧 Nugget restore 流程。

首先 clone：

```text
AirLift
PyAirLift
AirCard-iOS
GoldenNugget-Team
GoldenNugget-Mobile
phanquocviet8x/GoldenNugget
iOS 27 Carrier Bundles
```

进行源码级 data-flow analysis。

必须优先解决：

```text
1. GoldenNugget-Mobile 的 Footnote 到底写入什么文件？
2. AirLift 如何处理已经存在的目标文件？
3. GoldenNugget 的 iOS 27 Carrier patch 到底改了什么？
4. statusBarOverrides 在 iOS 27.0 Final 是否仍有效？
5. SystemStatusUI / Speakeasy 的 Carrier 数据源是什么？
6. Carrier Bundle / CommCenter / CoreTelephony / SystemStatusUI 如何连接？
```

任何成功结论必须注明：

```text
iOS version
Build
Device
Repository
Commit / Release
```

没有 24A437 实机证据就标记：

```text
Unknown
```

README 与源码冲突时，以源码和可复现实验为准。

最终输出：

```text
iOS27_Carrier_Footnote_Solution.md
```

并使用六级证据分类：

```text
Confirmed
Highly Likely
Claimed / Unverified
Hypothesis
Not Working
Unknown
```
