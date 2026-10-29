#!/usr/bin/env python3
"""Apply one StatusBarOverrides variant with a live-domain purge.

This is a research harness, not a production deployer. It:
  1. enforces the local primary-device blocklist,
  2. saves the previous archive,
  3. atomically replaces the archive through AirTraffic,
  4. kills systemstatusd's live override domain,
  5. restarts SpringBoard and captures Lock Screen/Control Center evidence.

Usage:
  python3 tools/exp_status_matrix.py --name EXP5 --set status=5 \
      --omit displayValue --omit type --screenshot
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# Import the maintained implementation from tools/ only. The legacy
# airlift/airlift_carrier_deploy.py file is a thin wrapper (see S4 in the
# 2026-10-28 roadmap); never let it shadow the safety-checked module.
for candidate in (ROOT / "tools",):
    if candidate.is_dir() and str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from airlift_carrier_deploy import (  # noqa: E402
    AirLiftCarrierError,
    PRIMARY_PHONE_BLOCKLIST,
    build_cellular_archive,
    select_device,
    springboard_pid,
)
from airlift_archive_replace import replace_archive  # noqa: E402
from statusbar_variant_lab import build_variant_archive, parse_value  # noqa: E402

DEVICE_UDID = "00008120-000934CA3E60C01E"  # iPhone 14 Pro test device
PYMOBILEDEVICE3 = ROOT / ".venv" / "bin" / "pymobiledevice3"
SYSTEMSTATUS_MARKER = "SystemStatusServer.framework/Support/systemstatusd"


def run(command: list[str], *, timeout: int = 60) -> subprocess.CompletedProcess:
    return subprocess.run(command, check=False, text=True, capture_output=True, timeout=timeout)


def core_processes() -> list[dict]:
    completed = run([str(PYMOBILEDEVICE3), "developer", "core-device", "list-processes", "--userspace"])
    if completed.returncode != 0:
        raise AirLiftCarrierError("Could not list CoreDevice processes", {"stderr": completed.stderr[-800:]})
    return json.loads(completed.stdout)


def find_pid(marker: str) -> int | None:
    for process in core_processes():
        url = process.get("executableURL", {}).get("relative", "")
        if marker in url:
            return int(process["processIdentifier"])
    return None


def signal(pid: int, sig: int) -> dict:
    completed = run(
        [str(PYMOBILEDEVICE3), "developer", "core-device", "send-signal-to-process", str(pid), str(sig), "--userspace"]
    )
    return {"pid": pid, "signal": sig, "ok": completed.returncode == 0, "stderr": completed.stderr[-500:]}


def wait_for_springboard(previous: int | None, timeout: float = 60.0) -> int | None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        pid = springboard_pid(DEVICE_UDID)
        if pid is not None and pid != previous:
            return pid
        time.sleep(2)
    return None


def screenshot(path: Path) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    completed = run([sys.executable, str(ROOT / "tools" / "device_ui.py"), "screenshot", str(path)], timeout=60)
    return completed.returncode == 0 and path.is_file()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name")
    parser.add_argument("--reset", action="store_true", help="Deploy an empty reset archive instead of a variant")
    parser.add_argument("--set", action="append", default=[], metavar="KEY=VALUE")
    parser.add_argument("--omit", action="append", default=[], metavar="KEY")
    parser.add_argument("--screenshot", action="store_true")
    parser.add_argument("--control-center", action="store_true")
    parser.add_argument("--device", default=DEVICE_UDID)
    args = parser.parse_args()

    if args.reset:
        args.name = args.name or "RESET"
    elif not args.name:
        parser.error("--name is required unless --reset is used")

    fields = {}
    for item in args.set:
        key, _, value = item.partition("=")
        fields[key] = parse_value(value)

    payload = (
        build_cellular_archive(is_reset=True)
        if args.reset
        else build_variant_archive(args.name, fields, set(args.omit))
    )
    stamp = time.strftime("%Y%m%d-%H%M%S")
    old_path = ROOT / ".artifacts" / "archives" / f"old-{args.name}-{stamp}.archive"
    old_path.parent.mkdir(parents=True, exist_ok=True)

    device = select_device(args.device)
    print(json.dumps({
        "blocked": sorted(PRIMARY_PHONE_BLOCKLIST),
        "selected": {k: device.get(k) for k in ("udid", "model", "version", "build")},
        "variant": args.name,
        "fields": fields,
        "omit": sorted(set(args.omit)),
        "payloadBytes": len(payload),
    }, ensure_ascii=False, indent=2), flush=True)

    sb_before = springboard_pid(args.device)
    systemstatus_before = find_pid(SYSTEMSTATUS_MARKER)
    print(f"[*] SpringBoard={sb_before} systemstatusd={systemstatus_before}", flush=True)

    result = replace_archive(args.device, payload, save_old=old_path)
    print("[*] replace:", json.dumps({k: v for k, v in result.items() if k != "atc"}, ensure_ascii=False), flush=True)
    if not result.get("atcOk"):
        print("[!] AirTraffic replace failed; leaving the device's current archive untouched.", flush=True)
        return 2

    # Kill the live override domain, then restart SpringBoard so the new disk
    # record becomes authoritative (see 2026-10-19 handoff, section 3.0.1).
    signals = []
    if sb_before is not None:
        signals.append(signal(sb_before, 19))  # SIGSTOP
    new_systemstatus = find_pid(SYSTEMSTATUS_MARKER)
    if new_systemstatus is not None:
        signals.append(signal(new_systemstatus, 9))  # SIGKILL
    if sb_before is not None:
        signals.append(signal(sb_before, 9))  # SIGKILL
    print("[*] signals:", json.dumps(signals, ensure_ascii=False), flush=True)

    sb_after = wait_for_springboard(sb_before)
    print(f"[*] SpringBoard after purge: {sb_after}", flush=True)
    time.sleep(4)

    # Wake the screen (tap center) before capture; the lock screen remains.
    run([sys.executable, str(ROOT / "tools" / "device_ui.py"), "tap", "32768", "32768"], timeout=30)
    time.sleep(2)

    artifacts = []
    if args.screenshot:
        lock = ROOT / ".artifacts" / "screens" / f"{args.name}-lock-{stamp}.png"
        if screenshot(lock):
            artifacts.append(str(lock))
    if args.control_center:
        run([sys.executable, str(ROOT / "tools" / "device_ui.py"), "open-cc"], timeout=30)
        time.sleep(2)
        cc = ROOT / ".artifacts" / "screens" / f"{args.name}-cc-{stamp}.png"
        if screenshot(cc):
            artifacts.append(str(cc))

    print(json.dumps({
        "variant": args.name,
        "oldArchive": str(old_path) if old_path.exists() else None,
        "newArchiveSize": result.get("newArchiveSize"),
        "springboard": {"before": sb_before, "after": sb_after},
        "systemstatusd": {"before": systemstatus_before, "restarted": new_systemstatus},
        "artifacts": artifacts,
    }, ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
