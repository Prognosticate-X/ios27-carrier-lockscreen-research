#!/usr/bin/env python3
"""Device-side resilience check for the AirLift deploy pipeline.

WARNING: this writes a *reset* StatusBarOverrides.archive to the connected
iPhone (the same payload the GUI reset button uses) and then cleans the staging
artifacts up again. It only runs when --yes is passed.

Scenario A: the device Books preimage drifts between the snapshot and the
            staging attempt; the pipeline must roll back, re-snapshot and
            succeed on the next attempt.
Scenario B: AirTraffic fails; the pipeline must roll back every staging
            artifact and leave the device exactly as it found it.

Usage: python3 tools/airlift_resilience_check.py --yes [UDID]
"""

from __future__ import annotations

import json
import os
import plistlib
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import airlift_carrier_deploy as A  # noqa: E402


def airlift_entries(udid: str) -> list[str]:
    result = A.native("list", udid, ".")
    return [
        entry["name"]
        for entry in result.get("operation", {}).get("entries", [])
        if "airlift-" in entry["name"]
    ]


def inject_drift(udid: str, snapshot_root: Path) -> dict:
    """Restore a Books preimage that differs from the captured snapshot."""
    drift_root = snapshot_root.parent / f"drift-{snapshot_root.name}"
    shutil.copytree(snapshot_root, drift_root, dirs_exist_ok=True)
    manifest = plistlib.loads((drift_root / "manifest.plist").read_bytes())
    row = manifest["files"]["Books/Sync/Books.plist"]
    row["exists"] = True
    blob = plistlib.dumps(
        {
            "Books": [
                {
                    "Persistent ID": "../../airlift-src-" + "0" * 20 + "/payload",
                    "Item ID": "4242",
                    "DSID": "1",
                }
            ]
        },
        fmt=plistlib.FMT_BINARY,
        sort_keys=True,
    )
    (drift_root / row["localName"]).write_bytes(blob)
    row["size"] = len(blob)
    (drift_root / "manifest.plist").write_bytes(plistlib.dumps(manifest, fmt=plistlib.FMT_BINARY))
    return A.native("restore-books", udid, os.fspath(drift_root))


def scenario_a(udid: str) -> None:
    print("\n=== Scenario A: Books preimage drift triggers a retry ===")
    real_native = A.native
    state = {"injected": False, "stage_failures": 0}

    def drifting_native(command, *args, **kwargs):
        result = real_native(command, *args, **kwargs)
        if command == "snapshot-books" and not state["injected"]:
            state["injected"] = True
            drift = inject_drift(udid, Path(args[1]))
            print("   injected drift:", json.dumps(drift.get("operation", {}))[:160])
        if command == "stage" and not result.get("operation", {}).get("ok"):
            state["stage_failures"] += 1
            print("   stage failed:", json.dumps(result.get("operation", {}))[:200])
        return result

    A.native = drifting_native
    try:
        result = A.deploy_carrier(udid, A.build_cellular_archive(is_reset=True), verbose=True)
        print("   deploy ok:", result["ok"], "| targetPresent:", result["targetPresent"],
              "| cleanupComplete:", result["cleanupComplete"])
    finally:
        A.native = real_native
    print("   stage failures observed:", state["stage_failures"])
    print("   leftover staging entries:", airlift_entries(udid))


def scenario_b(udid: str) -> None:
    print("\n=== Scenario B: AirTraffic failure triggers a rollback ===")
    real_run_json = A.run_json

    def failing_run_json(command, timeout):
        if Path(command[0]).name == "airtraffic_host":
            print("   simulating AirTraffic transport failure")
            return {"ok": False, "error": "simulated transport failure", "exitCode": 1}
        return real_run_json(command, timeout)

    A.run_json = failing_run_json
    try:
        A.deploy_carrier(udid, A.build_cellular_archive(is_reset=True), verbose=False)
        print("   ERROR: deploy unexpectedly succeeded")
    except A.AirLiftCarrierError as error:
        print("   raised:", error)
        rollback = (error.details or {}).get("rollback")
        if rollback is None:
            print("   rollback result: (not attached to this error)")
    finally:
        A.run_json = real_run_json
    print("   leftover staging entries:", airlift_entries(udid))


def main() -> int:
    arguments = sys.argv[1:]
    if "--yes" not in arguments:
        print(__doc__)
        print("Refusing to write to the device without --yes.")
        return 2
    positional = [value for value in arguments if not value.startswith("-")]
    udid = positional[0] if positional else A.select_device(None)["udid"]
    scenario_a(udid)
    scenario_b(udid)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
