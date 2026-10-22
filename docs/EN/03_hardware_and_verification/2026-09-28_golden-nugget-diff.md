# GoldenNugget Fork Differences and iOS 27 Authenticity Audit Report

**Report Objective:** Clarify the code differences between `awesomenull-dev/GoldenNugget` (Fork A) and `phanquocviet8x/GoldenNugget` (Fork B), and ascertain the ground truth regarding "Status Bar (patched on iOS 27)" in Fork B.

---

## 1. Git Topology and Version Facts

Through analysis of the Git history and commit graph across both locally cloned repositories:

- **Fork A (`awesomenull-dev/GoldenNugget`)**:
  - HEAD Commit: `a0912ee8a891e272546f3f12ae6b9fefcf0e82fc`
  - Release Tag: `9.5`
- **Fork B (`phanquocviet8x/GoldenNugget`)**:
  - HEAD Commit: `0c449b9451e71cd6f6d46fdab19b0533ed4ba4fb`
  - Release Tag: `8.3`

### Key Topological Conclusions:
1. **Merge Base:** `git merge-base HEAD forkB/main` yields exactly `0c449b9451e71cd6f6d46fdab19b0533ed4ba4fb` (i.e., Fork B's HEAD).
2. **Branch Relationship:** Fork B's `main` branch is a **pure ancestor node** within Fork A's history.
3. **Commit Discrepancy:**
   - Fork B has **no** independent or newly added commits compared to Fork A (`HEAD..forkB/main` output is empty).
   - Fork A is ahead of Fork B by **270+ commits** (encompassing major refactors from 8.3 to 9.5: declarative Tweak Registry, smart protected backup caching, PosterBoard database injection pipeline, etc.).

---

## 2. The Truth Behind "Status Bar (patched on iOS 27)"

### 2.1 Origin of the README Changes
Tracing via `git log -S "Status Bar (patched on iOS 27)" -p -n 1 -- README.md`:
- **Commit Hash:** `c37b7095de10a5424ebea57368e4484738cf8f63` (Tag: `8.2.1`)
- **Author:** `awesomenull <idrustamgames@gmail.com>`
- **Commit Message:** `revert readme.md`
- **Diff Contents:**
  ```diff
  -- Status Bar (iOS 27: blocked by Speakeasy gate — see RESEARCH_SUMMARY.md)
  +- Status Bar (patched on iOS 27)
     - Change carrier name
     - Change secondary carrier name
     ...
  ```

### 2.2 Semantic and Lexical Clarification
- In the security and jailbreak community, **"patched on iOS 27"** originally means: **"This mechanism has been blocked/fixed by Apple on iOS 27 (patched by Apple)"**.
- Some community users or secondary distributors misinterpreted/mistranslated this as: *"GoldenNugget was patched on iOS 27 to support Status Bar."*
- The author included a comprehensive empirical verification document `RESEARCH_SUMMARY.md` in commit `86a0f70` during the same period, whose opening line and conclusion are:
  > `Status: BLOCKED - Requires exploit/jailbreak to proceed`  
  > `The iOS 27 status bar tweak is impossible without an exploit.`

### 2.3 Code-Level Implementation Verification
In Fork B's actual code file `src/tweaks/status_bar/status_bar_tweak.py`:
```python
# iOS 27: the status bar is Speakeasy, a SpringBoard feature flag — 
# but writing the SpeakeasyNewStatusBar flag fails due to no write permissions.
# The feature is disabled on iOS 27+.
def apply_tweak(self, flag_plist: dict = None, version: str = "27.0") -> dict:
    if not self.enabled or flag_plist is None:
        return flag_plist
    if Version(version) >= Version("27.0"):
        return flag_plist   # <--- Directly returns original dict, substantively a no-op
    category = flag_plist.setdefault("SpringBoard", {})
    category["SpeakeasyNewStatusBar"] = self.get_speakeasy_payload()
    return flag_plist
```
And in the comment for `get_speakeasy_payload`, it is explicitly stated:
> `TODO(ios27): the actual dict schema is not confirmed — the keys below are guesses mirroring the classic statusBarOverrides plist format...`

In Fork A (post-v9.5 refactoring), the author completely stripped the dead code above, directly confirming that the status bar cannot be written on iOS 27+:
```python
# iOS 27+: the status bar is Speakeasy, a SpringBoard feature flag, but
# writing SpeakeasyNewStatusBar fails due to no write permissions, so the
# feature is disabled.
def apply_tweak(self, flag_plist: dict = None, version: str = "27.0") -> dict:
    return flag_plist
```

---

## 3. Explicit Answers to Core Questions

| Audit Question | Explicit Answer & Facts |
|---|---|
| **What did phanquocviet8x actually modify regarding "patched on iOS 27"?** | **Substantively, no status bar execution logic was modified.** phanquocviet8x merely forked an intermediate commit from awesomenull. The text in the README originated from awesomenull's commit, signifying that "this feature was blocked by Apple". |
| **Can this patch genuinely modify the Carrier on iOS 27.0 Release?** | **Absolutely not.** The internal code encounters `Version(version) >= Version("27.0")` and directly returns a no-op. |
| **What write primitive does it rely on?** | It relies on the original Nugget's `Mobilebackup2` Sparse Restore. However, on iOS 27, this vector was completely sealed off by Apple via BackupAgent whitelisting and Security Recovery wipes. |
| **Does it depend on a Beta-only exploit?** | No. It does not integrate any exploits whatsoever; it is purely vestigial dead code left behind after legacy backup restoration logic broke on iOS 27. |
| **Does the README align with the actual code?** | **There is severe disconnect / misleading phrasing.** If the README's "patched" is interpreted as "supported", it completely contradicts the code; if interpreted as "patched by Apple", it matches the code's behavior. |
