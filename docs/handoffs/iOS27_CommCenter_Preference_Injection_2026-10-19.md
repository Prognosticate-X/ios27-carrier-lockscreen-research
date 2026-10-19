# iOS 27.0.1 动态运营商（CommCenter 偏好层）实机实验交接文档

更新时间：2026-10-19  
目标设备：iPhone 14 Pro（iPhone15,2）/ iOS 27.0.1 / Build 24A446 / USB  
主机工具：本仓库 AirLift 原生 helper + pymobiledevice3 11.36.0（`.venv`，userspace tunnel，无需 root）

> 本文档记录“路线 A：真机 `/var/mobile/Library/Preferences/` 偏好层注入”的最新可复现事实。
> 目标仍是：让自定义运营商名称在 **真实基带信号** 与 **飞行模式联动** 下显示，而不是 `StatusBarOverrides.archive` 的静态钉死。

---

## 1. 本轮新增工具

| 工具 | 作用 | 状态 |
|---|---|---|
| `tools/device_path_probe.py` | 通过 AirLift 路径穿越软链做 **只读** 侦察：`--stat` / `--list` / `--read`，带只读目录白名单 | 已实机验证 |
| `tools/commcenter_carrier_inject.py` | 生成并写入 `InterCarrierRoamingDisplayNames` 运营商偏好 plist（仅限 Preferences 目录与 8 个域名） | 已离线验证（dry-run/单测），实机注入待解锁 |
| `tools/device_ui.py` | 通过 CoreDevice HID 打开控制中心、点击、截图，用于视觉验证 | 截图已实机验证；触摸待解锁 |
| `airlift/Sources/airtraffic_host.m` | 允许只派发 1 个 asset（`argc >= 4`），从而只移动软链、不写任何目标文件，实现纯读侦察 | 已实机验证 |

测试：`cd tools && python3 -m unittest test_airlift_features`（17 项全部通过，其中 6 项为新增覆盖）。

---

## 2. 已经实机证实的结论

### 2.1 AFC 的读取边界（iOS 27.0.1 / 24A446）

- 把 staging 软链移动到 `/var/mobile/Media/airlift-link-*` 后，**stat 可以穿过软链**：
  - `/var/mobile/Library/Preferences/.GlobalPreferences.plist` → 返回完整字段（20845 bytes）。
  - `/var/mobile/Library/SpringBoard/StatusBarOverrides.archive` → `status=10`（存在，但不可 stat）。
  - 不存在的文件（如 `com.apple.operator_1.plist`）→ `status=8`。
- 但是 **`read` 与目录 `list` 对 media 沙箱之外的路径一律失败**（实测表现等价于 AFC daemon 对 media 之外只有元数据权限）。
- 结论：AFC 不能再被当作 `/var/mobile/Library` 的读通道；README 中“读出并逐字节比对”的说法在当前构建上不可复现，CLI 的 `Byte Verification: unavailable` 是诚实的。

### 2.2 现有偏好域名在“干净”设备上并不存在

对以下路径做 `--stat`，全部返回 `status=8`（ENOENT）：

- `com.apple.operator_1.plist` / `com.apple.operator_1.merged.plist`
- `com.apple.carrier_1.plist` / `com.apple.carrier_1.merged.plist`
- `com.apple.commcenter.carrier_bundle.plist`
- `com.apple.commcenter.device_specific_nobackup.plist`
- `/var/wireless/Library/Preferences/`、`/var/preferences/` 下的同名域

这意味着：**注入 = 新建域文件**，而不是覆盖已有文件；同时也说明这些“merged”缓存并非每次联网都会落盘，研究文档里“已存在该 plist、可直接改”的假设需要修正。

### 2.3 AirLift 写入在 24A446 上可用，且 `StatusBarOverrides` 确实控制锁屏文字

- 部署自定义名 `ZZTEST9` 后，**iPhone 14 Pro 锁屏左上角立即显示 ZZTEST9**（截图 `.artifacts/screens/probe_zztest9.png`）。
- 说明：ATAirlock 覆盖已有 `StatusBarOverrides.archive` 在该构建上至少成功过一次；锁屏是无需解锁即可观察的验证面。
- 失败路径：部署 `--reset` 后仅 respring，锁屏仍显示 ZZTEST9。原因可能是 reset 写入被 ATAirlock 的 rename 拒绝，也可能是 `systemstatusd`/SpringBoard 的内存缓存未清除；**必须用用户空间/整机重启做判定**，仅 respring 不足以确认 reset 生效。

### 2.4 整机重启会把设备打回 USB 受限状态

- `xcrun devicectl device reboot --style full` 之后，设备在 4 分钟内持续 `unavailable`，`usbmux list` 为空；
- 需要 **在设备上输入锁屏密码解锁** 才恢复 AFC/CoreDevice/RSD。
- 对比：`--style userspace` 的重启会保留配对与 USB 数据访问，设备可自动重连（本轮已实测）。
- 结论：后续实验应优先使用 **userspace reboot**；只有确需冷启动时才用 full reboot，并预留人工解锁。

### 2.5 目标网络

锁屏截图显示当前运营商为 **中国联通**（`中国联通`），对应 PLMN：

```text
46001（主）, 46006, 46009, 46010
```

---

## 2.6 首轮注入实测（14:41–14:45）

设备解锁后执行了首轮完整注入：

```bash
python3 tools/commcenter_carrier_inject.py --udid 00008120-000934CA3E60C01E \
  -c DYNTEST --plmn china_unicom --plmn 46006 --plmn 46009 --plmn 46010
# → 4 个 operator 域（slot1/2 的普通 + .merged）全部落盘
xcrun devicectl device reboot --device 00008120-000934CA3E60C01E --style userspace
```

结果与观察：

1. **文件确实创建**：注入前 4 个目标域均为 `status=8`（ENOENT），注入后变为 `status=10`（EPERM，存在但元数据被拒）；随后补写的 `com.apple.carrier_1.plist` 同样如此。作为对照，Preferences 目录中已知存在的 `com.apple.Accessibility.plist`、`com.apple.mobiletimer.plist`、`com.apple.Preferences.plist` 也全部返回 `status=10`，不存在的文件才返回 8。
2. **首轮判定为阴性**：userspace 重启后锁屏仍显示 `中国联通`（`DYNTEST` 未出现）。
3. **最可能的原因——数据保护时序**：重启后设备一直停留在锁屏、**尚未发生过首次解锁**。iOS 偏好文件默认属于 `NSFileProtectionCompleteUntilFirstUserAuthentication`（class C），在“本次启动后首次解锁”之前不可读；而 `.GlobalPreferences.plist` 属于始终可读的 class A（锁屏下仍能 stat 到 20845 bytes）。CommCenter/cfprefsd 在启动时读不到新建域，因此该阴性结果**不能**用来否定 `InterCarrierRoamingDisplayNames` 假设。
4. **另一个需要排除的可能**：若 ATAirlock 以 root 身份创建文件（0600），则 mobile 用户的 cfprefsd 永远读不到。解锁后对目标域做一次 `stat` 即可区分：class C + mobile 属主 → 解锁后可读到 `st_size=126`；root 属主 → 解锁后仍为 EPERM。

因此下一轮实验必须满足：**设备已解锁 → 写入 → 解锁状态下触发 CommCenter 重载 → 立即观察**，而不是“写入后重启再锁屏观察”。

## 2.7 扩展域 + 强制重载：仍为阴性（15:00–15:02）

设备解锁期间把实验推到最强条件：

1. **域覆盖到全部候选**：base 域（`com.apple.operator` / `com.apple.carrier` 普通与 `.merged`）+ slot1 域，payload 同时包含 `InterCarrierRoamingDisplayNames`、`CarrierName`、`ShowCarrierName`（165 bytes）。
2. **强制冷启动所有相关缓存**：通过 CoreDevice `send-signal-to-process` 对两个 `cfprefsd`、`CommCenter`、`SpringBoard` 发送 SIGTERM，四个进程全部由 launchd 重新拉起（新 PID 1321/1322/1323 + 新 SpringBoard）。
3. **结果**：等待 12s 后截图，锁屏仍显示 `中国联通`，`DYNTEST2` 未出现。

**结论**：在 iPhone 14 Pro / iOS 27.0.1（24A446）+ 中国联通（46001 本网）上，向 `com.apple.operator`/`com.apple.carrier` 偏好域注入 `InterCarrierRoamingDisplayNames` 或 `CarrierName`，**即使 cfprefsd/CommCenter/SpringBoard 全部冷启动也不会改变运营商显示名**。

按可能性排序的解释：

1. `CarrierSettingsInterface` 的 Operator bundle 数据来自**已签名 carrier bundle**（`Operator.plist` 等），而不是 CFPreferences 域；
2. `InterCarrierRoamingDisplayNames` 只在**跨运营商漫游**场景被查询，本网（46001）不会命中；
3. ATAirlock 创建的文件属主/保护类不被 cfprefsd 接受（要排除这一点需要 root 视角，备份 manifest 的文件元数据是唯一可行通道）。

**清理**：12 个候选域（base/slot1/slot2 × operator/carrier × 普通/.merged）已全部写回**空字典**，设备锁屏保持原生 `中国联通`。

**新增可复用能力**：CoreDevice 信号通道可以在不重启整机的情况下重启 cfprefsd/CommCenter/SpringBoard，用于验证任何“缓存/重载”假设：

```bash
.venv/bin/pymobiledevice3 developer core-device list-processes --userspace
.venv/bin/pymobiledevice3 developer core-device send-signal-to-process <pid> 15 --userspace
```

## 3. 待执行的关键实验（设备解锁后即可执行）

前置：设备已解锁、点过“信任此电脑”。

### Step 0 — 读取侧侦察（可选但推荐）

```bash
# 过滤备份：只保留 Preferences / Carrier Bundles / SpringBoard 等路径
.venv/bin/pymobiledevice3 backup2 backup .artifacts/backup \
  --udid 00008120-000934CA3E60C01E \
  --only-regex 'Library/Preferences' \
  --only-regex 'Library/Carrier Bundles' \
  --only-regex 'Library/SpringBoard'
```

用途：确认运营商 bundle / 偏好域的真实落盘结构；备份是当前唯一可用的 HomeDomain 读通道。

### Step 1 — 清除静态覆写，确认原生基线

```bash
python3 tools/airlift_carrier_deploy.py --device 00008120-000934CA3E60C01E \
  --reset --force-overwrite          # 部署空归档
xcrun devicectl device reboot --device 00008120-000934CA3E60C01E --style userspace
```

预期：锁屏显示 `中国联通`，信号格为真实基带值；`--stat` 归档应为 `status=8`。

### Step 2 — 注入 CommCenter PLMN 映射

```bash
python3 tools/commcenter_carrier_inject.py \
  -c "联通 Dynamic" \
  --plmn china_unicom --plmn 46006 --plmn 46009 --plmn 46010
```

写入 `com.apple.operator_1.plist` 与 `com.apple.operator_1.merged.plist`（以及 slot 2 的同名域）。
每次写入都通过 staging 软链 `stat` 校验目标长度；失败会明确报错。

### Step 3 — 重启并观察

```bash
xcrun devicectl device reboot --device 00008120-000934CA3E60C01E --style userspace
# 等 20-30s 后：
python3 tools/device_ui.py screenshot .artifacts/screens/cc_after_inject.png
```

判定：

- 锁屏显示 `联通 Dynamic` → `InterCarrierRoamingDisplayNames` 机制成立，进入飞行模式联动验证；
- 仍显示 `中国联通` → 该域名/键不在 CommCenter 实际读取路径上，记录阴性结果并转入路线 B。

### Step 4 — 飞行模式与真实信号（成功时）

```bash
python3 tools/device_ui.py open-cc        # 从右上角下滑
python3 tools/device_ui.py screenshot .artifacts/screens/cc.png
```

控制中心可直接看到运营商名、真实信号格与飞行模式按钮；坐标以截图为准再微调。

### 回滚

偏好域文件无法通过 AFC 删除；写回 `{}`（空字典）即可让 CommCenter 读不到任何键，等价于关闭覆写：

```bash
python3 - <<'PY'
import plistlib
from tools.commcenter_carrier_inject import deploy_preference
payload = plistlib.dumps({}, fmt=plistlib.FMT_BINARY)
for domain in ("com.apple.operator_1.plist", "com.apple.operator_1.merged.plist"):
    print(domain, deploy_preference("00008120-000934CA3E60C01E", domain, payload)["ok"])
PY
```

---

## 3.5 备份取证：真实数据模型（15:16–15:20）

在设备解锁并完成“信任此电脑”后，过滤备份成功（`Manifest.db` 17,511 行，24 MB）。关键证据：

1. **本机网络参数**（`WirelessDomain/Library/Preferences/com.apple.commcenter.plist`）：
   - `LastKnownServingMcc = 460`，`LastKnownServingMnc = 1` → **PLMN 46001**
   - `CarrierBundleName = '46001'`
   - `LastKnownICCID = '89860124801663304064'`
2. **CommCenter 的真实持久化偏好全部位于 `WirelessDomain`**（`/var/wireless/Library/Preferences/`）：
   - `com.apple.commcenter.plist`、`com.apple.commcenter.data.plist`、`com.apple.commcenter.lazuli.plist`、`com.apple.commcenter.travel.plist`、`com.apple.commcenter.country_bundle.plist`、`com.apple.CommCenter.counts.plist`、`com.apple.CommCenter.quickswitch.plist`、`com.apple.commcenter.callservices.plist`
   - 整个 manifest 中**不存在**任何 `com.apple.operator_1` / `com.apple.carrier_1` 域文件。
3. **`com.apple.carrier_1` 只是字符串**：在 `com.apple.commcenter.plist` 里该键的值是 `'46001'`（当前激活的 carrier bundle 标识），不是设置字典。
4. **运营商数据源是已签名 carrier bundle**：`/System/Library/Carrier Bundles/iPhone/46001/` 包含 `carrier.plist`、`overrides_D73_D74_D27_D28.plist`、`signatures`、`overrides_*.der.pri`——位于 Sealed System Volume，mobile 不可写。
5. **我们创建的 12 个 HomeDomain 域不在备份清单里**（尽管 stat 显示存在：存在=10、缺失=8）。backupd 是否因属主/系统域名单跳过它们仍未能确定，但无论哪种情况，它们都不是 CommCenter 的运营商数据来源。

### 结论（最终）

- iOS 27.0.1 上运营商显示名来自**已签名 carrier bundle**；CommCenter 的运行时状态在 **`/var/wireless`**（属于 `_wireless`，AirLift 的 mobile 上下文不可写）。
- 因此 **路线 A（HomeDomain CFPreferences 注入）在无越狱、无提权写原语的前提下不可行**；`InterCarrierRoamingDisplayNames` 即使存在于 bundle 的 `carrier.plist` 中，也无法在不破坏签名的前提下注入。
- 动态运营商（真实信号 + 飞行模式联动）在本项目的非越狱能力边界内**没有可用写入路径**；静态 `StatusBarOverrides.archive` 仍是唯一可工作的方案，其“信号钉死/飞行模式常驻”的限制保持不变。

## 4. 当前状态与结论（更新于 15:05）

- **路线 A 判定：本网重命名阴性**。CFPreferences 偏好域注入（含 base/slot 域、`InterCarrierRoamingDisplayNames` + `CarrierName` + `ShowCarrierName`、cfprefsd/CommCenter/SpringBoard 强制冷启动）均未改变运营商名。
- **不能据此宣布机制彻底死亡**：仍存在“bundle 来源”“仅漫游触发”“文件属主/保护类被忽略”三种可能；其中前两种需要 `CommCenter` 主程序反编译（路线 B），第三种需要备份 manifest 元数据（需要设备解锁 + 信任弹窗密码）。
- **设备当前状态**：无静态覆写，锁屏原生 `中国联通`；12 个实验域已写回空字典；USB 已连接。
- **下一步优先级**：
  1. 若你愿意在手机上完成一次“信任此电脑”并保持解锁，我可跑过滤备份，解析 `Manifest.db` 中 12 个域文件的 `Mode/OwnerID/GroupID/ProtectionClass`，一次性排除“属主/保护类”假设；
  2. 否则转向路线 B：`pymobiledevice3 developer fetch-symbols` 拉取 24A446 的 dyld shared cache，提取 `libCommCenterBase.dylib` 并复核 `getLocalizedCompositeName` 的调用条件；必要时下载 IPSW 提取 `CommCenter` 主程序。

## 5. 原“待执行”清单

- 截至本文档写入时，设备因 **full reboot 处于 USB 受限状态**，需要用户在设备上解锁后恢复连接。
- 偏好注入脚本、payload、单测、验证流程均已就绪；解锁后可直接执行 Step 0–3。
- 若 Step 3 为阴性，下一步建议：
  1. 用 `pymobiledevice3 developer fetch-symbols` 拉取 24A446 的 dyld shared cache，复核 `libCommCenterBase` 中 `getLocalizedCompositeName` 的调用条件（是否仅漫游生效）；
  2. 由于 `CommCenter` 主程序不在 DSC 内，必要时下载对应 IPSW 提取二进制做离线反编译；
  3. 继续排查 `/var/wireless`、`/var/preferences` 体系下由 `_wireless` 用户持有的真实偏好域。

---

## 5. 安全边界

- 偏好注入工具只允许 `/var/mobile/Library/Preferences` 与固定的 8 个 `com.apple.operator_*/carrier_*` 域名，payload 上限 512 KiB。
- 写入走已审计的 AirLift Books/AirTraffic 通道，staging 结束后恢复 `Books.plist` 原始快照，不残留 `airlift-*` 目录。
- 所有设备侧实验均在测试机 iPhone 14 Pro 上进行；日常主力机 iPhone 16 Pro Max 未参与。

---

## 6. 下一轮实验协议（修订版，必须保持解锁）

```bash
# 0) 设备解锁并保持解锁；先确认目标域可读（class 假设）
python3 tools/device_path_probe.py --udid 00008120-000934CA3E60C01E \
  --stat /var/mobile/Library/Preferences/com.apple.operator_1.merged.plist
#    可读 → 返回 st_size（126）；仍 EPERM → 需怀疑 root 属主

# 1) 重新注入（含 CarrierName 变体，作为第二个假设）
python3 tools/commcenter_carrier_inject.py --udid 00008120-000934CA3E60C01E \
  -c DYNTEST --plmn china_unicom --include-carrier-name

# 2) 不重启，先尝试强制 CommCenter 重新读取：
#    a. 用 HID 切换飞行模式（开→关），迫使重新注册与运营商名解析
python3 tools/device_ui.py open-cc
python3 tools/device_ui.py screenshot .artifacts/screens/cc_before_toggle.png
#    b. 若无效，再用 CoreDevice/DVT 向 CommCenter 发送信号（需确认权限）
.venv/bin/pymobiledevice3 developer core-device list-processes --userspace | grep CommCenter

# 3) 每次操作后立即截图控制中心（运营商名 + 真实信号格）
python3 tools/device_ui.py screenshot .artifacts/screens/cc_after.png
```

判定顺序：解锁可读性 → 飞行模式重载 → 进程重启 → 最后才考虑“域/键不成立”。