# GoldenNugget Fork 差异与 iOS 27 真实性审计报告

**报告目标：** 厘清 `awesomenull-dev/GoldenNugget` (Fork A) 与 `phanquocviet8x/GoldenNugget` (Fork B) 的代码差异，明确 Fork B 中 “Status Bar (patched on iOS 27)” 的事实真相。

---

## 1. Git 拓扑与版本事实

通过对两个本地克隆仓库的 Git 历史与 commit graph 分析：

- **Fork A (`awesomenull-dev/GoldenNugget`)**：
  - HEAD Commit: `a0912ee8a891e272546f3f12ae6b9fefcf0e82fc`
  - Release Tag: `9.5`
- **Fork B (`phanquocviet8x/GoldenNugget`)**：
  - HEAD Commit: `0c449b9451e71cd6f6d46fdab19b0533ed4ba4fb`
  - Release Tag: `8.3`

### 关键拓扑结论：
1. **Merge Base：** `git merge-base HEAD forkB/main` 的结果恰为 `0c449b9451e71cd6f6d46fdab19b0533ed4ba4fb`（即 Fork B 的 HEAD）。
2. **分支关系：** Fork B 的 `main` 分支是 Fork A 历史中的一个**纯祖先节点**（Ancestor）。
3. **Commit 差异：**
   - Fork B 相比 Fork A **没有**任何独立新增的提交（`HEAD..forkB/main` 输出为空）。
   - Fork A 比 Fork B 领先了 **270+ 个提交**（包含从 8.3 到 9.5 的重大重构：声明式 Tweak Registry、智能保护备份缓存、PosterBoard 数据库注入管道等）。

---

## 2. 所谓 “Status Bar (patched on iOS 27)” 的真相

### 2.1 README 变动的来源
通过 `git log -S "Status Bar (patched on iOS 27)" -p -n 1 -- README.md` 追溯：
- **提交哈希：** `c37b7095de10a5424ebea57368e4484738cf8f63` (Tag: `8.2.1`)
- **作者：** `awesomenull <idrustamgames@gmail.com>`
- **提交信息：** `revert readme.md`
- **Diff 内容：**
  ```diff
  -- Status Bar (iOS 27: blocked by Speakeasy gate — see RESEARCH_SUMMARY.md)
  +- Status Bar (patched on iOS 27)
     - Change carrier name
     - Change secondary carrier name
     ...
  ```

### 2.2 词义与语义澄清
- 在安全与越狱社区中，**"patched on iOS 27"** 的本意是：**“该机制已在 iOS 27 上被 Apple 封堵修复（patched by Apple）”**。
- 社区部分用户或二次传播者将其误译/误读为：*“GoldenNugget 在 iOS 27 上被打上了补丁以支持 Status Bar”*。
- 提交者在同一时期的提交 `86a0f70` 中附带了完整的实测文档 `RESEARCH_SUMMARY.md`，其第一句话与结论便是：
  > `Status: BLOCKED - Requires exploit/jailbreak to proceed`  
  > `The iOS 27 status bar tweak is impossible without an exploit.`

### 2.3 代码层面的实现核验
在 Fork B 的实际代码文件 `src/tweaks/status_bar/status_bar_tweak.py` 中：
```python
# iOS 27: the status bar is Speakeasy, a SpringBoard feature flag — 
# but writing the SpeakeasyNewStatusBar flag fails due to no write permissions.
# The feature is disabled on iOS 27+.
def apply_tweak(self, flag_plist: dict = None, version: str = "27.0") -> dict:
    if not self.enabled or flag_plist is None:
        return flag_plist
    if Version(version) >= Version("27.0"):
        return flag_plist   # <--- 直接 return 原字典，实质为空操作 (no-op)
    category = flag_plist.setdefault("SpringBoard", {})
    category["SpeakeasyNewStatusBar"] = self.get_speakeasy_payload()
    return flag_plist
```
并且在 `get_speakeasy_payload` 的注释中明确写道：
> `TODO(ios27): the actual dict schema is not confirmed — the keys below are guesses mirroring the classic statusBarOverrides plist format...`

在 Fork A（v9.5 重构后）中，作者已将上述死代码完全剥离，直接确认状态栏在 iOS 27+ 无法写入：
```python
# iOS 27+: the status bar is Speakeasy, a SpringBoard feature flag, but
# writing SpeakeasyNewStatusBar fails due to no write permissions, so the
# feature is disabled.
def apply_tweak(self, flag_plist: dict = None, version: str = "27.0") -> dict:
    return flag_plist
```

---

## 3. 核心问题明确解答

| 审计问题 | 明确答复与事实 |
|---|---|
| **phanquocviet8x 所谓 “patched on iOS 27” 到底修改了什么？** | **实质未修改任何状态栏生效逻辑。** phanquocviet8x 仅是 fork 了 awesomenull 的某次中间提交，README 上的文字来自 awesomenull 的提交，表示“该功能被苹果封堵”。 |
| **这个 patch 是否真的能够在 iOS 27.0 Release 修改 Carrier？** | **绝对不能。** 代码内部遇到 `Version(version) >= Version("27.0")` 直接返回空操作。 |
| **它依赖什么写入 primitive？** | 依赖原版 Nugget 的 `Mobilebackup2` 稀疏恢复（Sparse Restore）。但该通道在 iOS 27 上已被苹果通过 BackupAgent 白名单和 Security Recovery wipe 彻底封死。 |
| **是否依赖 Beta-only exploit？** | 否，它甚至没有集成任何 exploit，纯粹是旧版备份恢复逻辑在 iOS 27 上遭遇失效后的残留死代码。 |
| **README 是否与实际代码一致？** | **存在严重误导/脱节。** 如果将 README 的 "patched" 理解为支持，则与代码完全矛盾；如果理解为 "patched by Apple"，则与代码行为一致。 |
