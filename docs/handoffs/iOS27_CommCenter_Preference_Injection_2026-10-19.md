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

## 4. 当前状态与阻塞

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