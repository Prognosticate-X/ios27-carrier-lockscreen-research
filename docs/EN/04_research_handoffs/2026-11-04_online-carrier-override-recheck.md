# iOS 27 Online Carrier Override Recheck

**Date**: 2026-11-04  
**Device**: iPhone 14 Pro (iPhone15,2) / iOS 27.0.1 (24A446)  
**Purpose**: Recheck the `status=5` custom name and online `status=1` behavior. Every valid deployment purged the `systemstatusd` live domain.

## Findings

- A reproducible online custom-name configuration was found: `status=5`, `enabled=true`, with both `string` and `crossfadeString` set. `ALTTEST` appeared on both the Lock Screen and in Control Center.
- This configuration did not keep all other fields live: `displayValue=4` and `type=10` were explicitly written, so the four bars and 5G label were archived values. The test does not establish live cellular strength or network type.
- A post-purge online `status=1` sample disagreed with the 2026-10-28 report. The Lock Screen showed no carrier text; Control Center showed the experiment name, no 5G label, and faint cellular dots. The online baseline was China Mobile 5G with Airplane Mode off. The earlier native-name fallback result should not be generalized across this network state; SIM/operator differences need investigation.
- The original `StatusBarOverrides.archive` was restored after the experiment and the live domain purged again. Final verification showed China Mobile 5G, cellular bars, Wi-Fi, and Airplane Mode off.

## Valid Samples

Baseline: Control Center showed China Mobile 5G, cellular bars, and Wi-Fi.

| Variant | Fields | Lock Screen | Control Center |
|---|---|---|---|
| `PURGE-LIVE3` | `status=5`, `enabled=true`, `displayValue=4`, `type=10`, `string=ALTTEST`, `crossfadeString=ALTTEST` | `ALTTEST`; four bars, Wi-Fi, and battery visible | `ALTTEST 5G`; bars and Wi-Fi visible |
| `PURGE-LIVE1` | `status=1`, `enabled=true`, `crossfadeString=ALTTEST`; omit `displayValue/type` (`string` defaults to variant name) | No carrier text; faint cellular dots | Variant name `PURGE-LIVE1`, no 5G; faint cellular dots |
| `PURGE-LIVE1-ONLINE-RETEST` | Same fields; baseline confirmed China Mobile 5G and Airplane Mode off | No carrier text; faint cellular dots | Variant name (truncated due to length), no 5G; faint cellular dots |

## Method and Evidence

Valid deployments used `tools/exp_status_matrix.py`: preserve the prior archive, replace atomically, SIGSTOP SpringBoard, SIGKILL `systemstatusd` and SpringBoard, then capture screenshots. Variants and screenshots are under `.artifacts/archives/` and `.artifacts/screens/`:

- `old-PURGE-LIVE3-20261104-054517.archive` — original archive before experiment
- `PURGE-LIVE3-lock-20261104-054517.png`, `PURGE-LIVE3-cc-20261104-054517.png`
- `old-PURGE-LIVE1-20261104-055924.archive` — original archive before experiment
- `PURGE-LIVE1-lock-20261104-055924.png`, `PURGE-LIVE1-cc-20261104-055924.png`
- `PURGE-LIVE1-ONLINE-RETEST-lock-20261104-072651.png`, `PURGE-LIVE1-ONLINE-RETEST-cc-20261104-072651.png`
- `final-cc-after-restore.png` — verification after restoring the original archive
- `final-online-restored-retest.png` — second restoration check after online retest

Earlier online screenshots made with `statusbar_variant_lab.py --deploy` only restarted SpringBoard and did not purge `systemstatusd`; they are not treated as evidence in this report.

## Next Steps

To verify “custom name + live signal and network type + automatic hiding in Airplane Mode,” run a comparable state matrix through the purge harness and confirm the actual Airplane Mode state for every screenshot. `status=5` reliably changes the name, but its display fields are static. No static archive combination meeting the full goal has been found. The `status=1` result may depend on SIM/operator and display surface; reproduce it under the original 2026-10-28 China Unicom conditions.
