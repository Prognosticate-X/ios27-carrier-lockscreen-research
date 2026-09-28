# iOS 27 定制研究风险登记与安全红线

## 1. 核心安全原则

用户当前设备为 **iPhone 16 Pro Max（A18 Pro），iOS 27.0 Release 正式版主力机**。所有操作必须恪守以下底线：

1. **零盲试原则：** 坚决禁止在主力设备上直接执行未验证的旧版 Nugget Restore 或未经审查的二进制工具。
2. **零高危目录写入：** 坚决不向 `/var/preferences`、`/var/keychains` 等敏感系统区域执行稀疏恢复，防止触发 iOS 27 Security Recovery Wipe（导致 Apple ID、锁屏密码、钥匙串和照片被系统安全抹掉）。
3. **分阶段与可逆原则：** 所有上机测试前必须具有完整的设备本地未加密/加密备份，每一次写入必须记录原始文件 SHA256 与回滚方案。

---

## 2. 风险登记表 (Risk Register)

| 风险编号 | 风险场景 | 严重级别 | 潜在后果 | 防控与缓解措施 |
|---|---|---|---|---|
| **R01** | 在 iOS 27 上直接执行原版 Nugget 的 Partial Restore | **严重 (Critical)** | 触发系统安全状态恢复，全盘数据清空或 Bootloop | 强制拦截原版 Nugget 流程，仅允许静态代码分析和受保护备份机制。 |
| **R02** | 盲目尝试覆写 `/var/preferences/FeatureFlags` | **严重 (Critical)** | BackupAgent 报错阻断或触发安全抹除 | 已在代码与历史测试中证实不可行，标记为永久阻断，不再尝试。 |
| **R03** | 运行面向 Beta 4 的 `bad_query` 逃逸脚本 | **高 (High)** | 进程崩溃、系统 Panic 或沙箱完整性破坏 | 必须先在非主力机或基于固件二进制做补丁 Diff，严禁主力机试跑。 |
| **R04** | 写入损坏的 `SharedDeviceConfiguration.plist` | **中 (Medium)** | SpringBoard 无法解析脚注文本或锁屏短暂卡死 | 写入前严格通过 `plistlib` 校验格式，确保仅注入标准 Key-Value。 |
