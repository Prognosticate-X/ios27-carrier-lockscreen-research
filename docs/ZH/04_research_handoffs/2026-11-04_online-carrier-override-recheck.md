# iOS 27 在线运营商覆写复核

**日期**：2026-11-04  
**设备**：iPhone 14 Pro（iPhone15,2）/ iOS 27.0.1（24A446）  
**用途**：复核 `status=5` 自定义名称和 `status=1` 在线行为；所有有效部署均清理 `systemstatusd` live domain。

## 结论

- 找到可复现的在线锁屏自定义名称方法：`status=5`、`enabled=true`，并同时设置 `string` 与 `crossfadeString`。`ALTTEST` 成功显示在锁屏与控制中心。
- 该配置没有实现“其余全实时”：实验明确写入了 `displayValue=4` 和 `type=10`，所以四格和 5G 文案是归档值，不能据此认定蜂窝信号格或制式仍实时。
- 再次确认 purge 后的在线 `status=1` 样本与 2026-10-28 文档结论不一致：锁屏无运营商文字；控制中心显示实验名、无 5G 文案，信号格呈淡色点。在线基线是“中国移动 5G”，飞行模式关闭。此前“在线时回退到原生名称”的结论不能直接推广到本次网络状态；需要继续检查 SIM/运营商差异。
- 试验结束后已恢复原始 `StatusBarOverrides.archive`，重新清理 live domain；最终控制中心显示“中国移动 5G”、蜂窝信号格与 Wi‑Fi，飞行模式关闭。

## 有效样本

基线在线状态：控制中心显示“中国移动 5G”、蜂窝信号格和 Wi‑Fi。

| 变体 | 字段 | 锁屏 | 控制中心 |
|---|---|---|---|
| `PURGE-LIVE3` | `status=5`, `enabled=true`, `displayValue=4`, `type=10`, `string=ALTTEST`, `crossfadeString=ALTTEST` | 显示 `ALTTEST`；四格、Wi‑Fi、电量图标可见 | 显示 `ALTTEST 5G`；四格、Wi‑Fi 可见 |
| `PURGE-LIVE1` | `status=1`, `enabled=true`, `crossfadeString=ALTTEST`；省略 `displayValue/type`（`string` 使用变体名） | 没有运营商文字；蜂窝格呈淡色点 | 显示变体名 `PURGE-LIVE1`，没有 5G 文案；蜂窝格呈淡色点 |
| `PURGE-LIVE1-ONLINE-RETEST` | 同上；在线前基线已确认“中国移动 5G”、飞行模式关闭 | 没有运营商文字；蜂窝格呈淡色点 | 显示变体名（名称过长而被截断），没有 5G 文案；蜂窝格呈淡色点 |

## 方法与证据

有效部署由 `tools/exp_status_matrix.py` 执行：保存前一归档、原子替换、SIGSTOP SpringBoard、SIGKILL `systemstatusd` 和 SpringBoard，再截图。变体和截图保存在 `.artifacts/archives/` 与 `.artifacts/screens/`：

- `old-PURGE-LIVE3-20261104-054517.archive`：实验前原归档
- `PURGE-LIVE3-lock-20261104-054517.png`、`PURGE-LIVE3-cc-20261104-054517.png`
- `old-PURGE-LIVE1-20261104-055924.archive`：实验前原归档
- `PURGE-LIVE1-lock-20261104-055924.png`、`PURGE-LIVE1-cc-20261104-055924.png`
- `PURGE-LIVE1-ONLINE-RETEST-lock-20261104-072651.png`、`PURGE-LIVE1-ONLINE-RETEST-cc-20261104-072651.png`
- `final-cc-after-restore.png`：原归档恢复后核验
- `final-online-restored-retest.png`：在线复测后再次恢复原归档

早先直接使用 `statusbar_variant_lab.py --deploy` 的在线截图只重启 SpringBoard，未清理 `systemstatusd`，因此本记录不把它们作为结论证据。

## 后续要点

要验证“自定义名称 + 实时信号与制式 + 飞行模式自动隐藏”，仍需用 purge 实验台做可比对的状态矩阵，并确认每张截图的飞行模式实际状态。当前已确认 `status=5` 能稳定改名，但其显示字段是静态值；尚未找到满足全部目标的静态归档组合。`status=1` 的结果可能受 SIM/运营商和显示面影响，需在原 10-28 网络条件下复现。
