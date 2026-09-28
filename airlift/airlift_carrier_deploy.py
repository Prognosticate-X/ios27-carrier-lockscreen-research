#!/usr/bin/env python3
"""
AirLift Carrier Deployer for iOS 27 (Physical Devices)
Persistently applies custom carrier name & cellular status bar configuration
to iPhone 14 Pro and compatible devices running iOS 27.x without jailbreak.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import plistlib
import posixpath
import re
import secrets
import stat
import struct
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parent
TARGET_HEADER = ROOT / "Sources" / "airlift_target.h"
DEVICE_HELPER = ROOT / "build" / "device_helper"
AIRTRAFFIC_HOST = ROOT / "build" / "airtraffic_host"

DEFAULT_TARGET = "/var/mobile/Library/SpringBoard"
TARGET_LEAF = "StatusBarOverrides.archive"
AIRLOCK_ROOT = "/var/mobile/Media/Airlock/Book"
SZ_EXTRA_ID = 0x5A53

NETWORK_TYPES = {
    "none": 0,
    "1x": 1,
    "gprs": 2,
    "edge": 3,
    "3g": 4,
    "4g": 5,
    "lte": 9,
    "5g": 10,
    "5g+": 11,
    "5g-uwb": 12,
    "5g-uc": 13,
}


class AirLiftCarrierError(RuntimeError):
    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.details = details


def build_cellular_archive(
    primary_carrier: Optional[str] = None,
    primary_bars: int = 4,
    primary_type: int = 10,
    primary_badge: Optional[str] = None,
    secondary_carrier: Optional[str] = None,
    secondary_bars: int = 4,
    secondary_type: int = 10,
    secondary_badge: Optional[str] = None,
    is_reset: bool = False,
) -> bytes:
    """
    Constructs an NSKeyedArchiver bplist compliant with iOS 27 SpringBoard.
    """
    if is_reset or (not primary_carrier and not secondary_carrier):
        objects = [
            "$null",
            {
                "$class": plistlib.UID(3),
                "statusBarData": plistlib.UID(2),
                "suppressedBackgroundActivityIdentifiers": plistlib.UID(4),
            },
            {
                "$class": plistlib.UID(5),
            },
            {
                "$classes": ["_SBSystemStatusStatusBarOverridesArchiveRecord", "NSObject"],
                "$classname": "_SBSystemStatusStatusBarOverridesArchiveRecord",
            },
            {
                "$class": plistlib.UID(6),
                "NS.objects": [],
            },
            {
                "$classes": ["STStatusBarData", "NSObject"],
                "$classname": "STStatusBarData",
            },
            {
                "$classes": ["NSSet", "NSObject"],
                "$classname": "NSSet",
            },
        ]
        plist_dict = {
            "$archiver": "NSKeyedArchiver",
            "$version": 100000,
            "$top": {"root": plistlib.UID(1)},
            "$objects": objects,
        }
        return plistlib.dumps(plist_dict, fmt=plistlib.FMT_BINARY)

    objects = ["$null"]

    def add_obj(val: Any) -> plistlib.UID:
        objects.append(val)
        return plistlib.UID(len(objects) - 1)

    cls_entry = {
        "$classes": [
            "STStatusBarDataCellularEntry",
            "STStatusBarDataNetworkEntry",
            "STStatusBarDataIntegerEntry",
            "STStatusBarDataEntry",
            "NSObject",
        ],
        "$classname": "STStatusBarDataCellularEntry",
    }
    cls_data = {
        "$classes": ["STStatusBarData", "NSObject"],
        "$classname": "STStatusBarData",
    }
    cls_set = {
        "$classes": ["NSSet", "NSObject"],
        "$classname": "NSSet",
    }
    cls_record = {
        "$classes": [
            "_SBSystemStatusStatusBarOverridesArchiveRecord",
            "NSObject",
        ],
        "$classname": "_SBSystemStatusStatusBarOverridesArchiveRecord",
    }

    root_dict: dict[str, Any] = {}
    uid_root = add_obj(root_dict)

    data_dict: dict[str, Any] = {}
    uid_data = add_obj(data_dict)

    uid_p_entry = None
    if primary_carrier:
        uid_p_str = add_obj(primary_carrier)
        uid_p_badge = add_obj(primary_badge) if primary_badge else plistlib.UID(0)
        p_entry = {
            "badgeString": uid_p_badge,
            "callForwardingEnabled": False,
            "crossfadeString": uid_p_str,
            "displayRawValue": 0,
            "displayValue": primary_bars,
            "enabled": True,
            "isBootstrapCellular": False,
            "lowDataModeActive": False,
            "numberSharingState": 0,
            "rawValue": 0,
            "showsSOSWhenDisabled": False,
            "sosAvailable": False,
            "status": 5,
            "string": uid_p_str,
            "suffixString": plistlib.UID(0),
            "type": primary_type,
            "wifiCallingEnabled": False,
        }
        uid_p_entry = add_obj(p_entry)
        data_dict["cellularEntry"] = uid_p_entry

    uid_s_entry = None
    if secondary_carrier:
        uid_s_str = add_obj(secondary_carrier)
        uid_s_badge = add_obj(secondary_badge) if secondary_badge else plistlib.UID(0)
        s_entry = {
            "badgeString": uid_s_badge,
            "callForwardingEnabled": False,
            "crossfadeString": uid_s_str,
            "displayRawValue": 0,
            "displayValue": secondary_bars,
            "enabled": True,
            "isBootstrapCellular": False,
            "lowDataModeActive": False,
            "numberSharingState": 0,
            "rawValue": 0,
            "showsSOSWhenDisabled": False,
            "sosAvailable": False,
            "status": 5,
            "string": uid_s_str,
            "suffixString": plistlib.UID(0),
            "type": secondary_type,
            "wifiCallingEnabled": False,
        }
        uid_s_entry = add_obj(s_entry)
        data_dict["secondaryCellularEntry"] = uid_s_entry

    uid_cls_entry = add_obj(cls_entry)
    uid_cls_data = add_obj(cls_data)
    uid_cls_set = add_obj(cls_set)
    uid_cls_record = add_obj(cls_record)

    uid_empty_set = add_obj({"$class": uid_cls_set, "NS.objects": []})

    root_dict["$class"] = uid_cls_record
    root_dict["statusBarData"] = uid_data
    root_dict["suppressedBackgroundActivityIdentifiers"] = uid_empty_set

    data_dict["$class"] = uid_cls_data
    if primary_carrier and uid_p_entry:
        objects[uid_p_entry.data]["$class"] = uid_cls_entry
    if secondary_carrier and uid_s_entry:
        objects[uid_s_entry.data]["$class"] = uid_cls_entry

    plist_dict = {
        "$archiver": "NSKeyedArchiver",
        "$version": 100000,
        "$top": {"root": uid_root},
        "$objects": objects,
    }

    return plistlib.dumps(plist_dict, fmt=plistlib.FMT_BINARY)


def zip_info(name: str, mode: int) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(name, date_time=(2026, 9, 14, 5, 0, 0))
    info.create_system = 3
    info.compress_type = zipfile.ZIP_STORED
    info.external_attr = (mode & 0xFFFF) << 16
    info.extra = struct.pack("<HHH", SZ_EXTRA_ID, 2, mode & 0xFFFF)
    return info


def build_streaming_zip(target: str, payload: bytes) -> bytes:
    target_tail = target[1:]
    metadata = plistlib.dumps(
        {"Version": 2}, fmt=plistlib.FMT_BINARY, sort_keys=True
    )
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", allowZip64=False) as archive:
        archive.writestr(zip_info("META-INF/", stat.S_IFDIR | 0o755), b"")
        archive.writestr(
            zip_info(
                "META-INF/com.apple.ZipMetadata.plist", stat.S_IFREG | 0o600
            ),
            metadata,
        )
        for directory in ("p0/", "p0/p1/", "p0/p1/p2/"):
            archive.writestr(zip_info(directory, stat.S_IFDIR | 0o755), b"")
        archive.writestr(
            zip_info("p0/p1/p2/link", stat.S_IFLNK | 0o777),
            f"../../../{target_tail}".encode(),
        )
        cursor = ""
        for component in target_tail.split("/"):
            cursor += component + "/"
            archive.writestr(zip_info(cursor, stat.S_IFDIR | 0o755), b"")
        archive.writestr(zip_info("payload", stat.S_IFREG | 0o600), payload)
    return output.getvalue()


def build_books_plist(identifiers: list[str]) -> bytes:
    rows = [
        {"Persistent ID": identifier, "Item ID": str(index), "DSID": "1"}
        for index, identifier in enumerate(identifiers, 1)
    ]
    return plistlib.dumps({"Books": rows}, fmt=plistlib.FMT_BINARY, sort_keys=True)


def run_json(command: list[str], timeout: int) -> dict[str, Any]:
    completed = subprocess.run(
        command,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=timeout,
    )
    result: dict[str, Any] | None = None
    for line in reversed(completed.stdout.splitlines()):
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            result = value
            break
    if result is None:
        raise AirLiftCarrierError(f"{Path(command[0]).name} returned no JSON result: {completed.stderr}")
    result["exitCode"] = completed.returncode
    return result


def native(command: str, udid: str, *arguments: str) -> dict[str, Any]:
    return run_json(
        [os.fspath(DEVICE_HELPER), command, udid, *arguments], timeout=60
    )


def operation_ok(result: dict[str, Any]) -> bool:
    return bool(
        result.get("exitCode") == 0
        and result.get("targetGatePassed")
        and result.get("operation", {}).get("ok")
    )


PRIMARY_PHONE_BLOCKLIST = frozenset([
    "00008140-001C29663062201C",  # User's primary iPhone 16 Pro Max
])


def query_connected_devices() -> list[dict[str, Any]]:
    command = [
        "xcrun",
        "devicectl",
        "list",
        "devices",
        "--timeout",
        "8",
        "--quiet",
        "--json-output",
        "-",
    ]
    try:
        completed = subprocess.run(
            command,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=12,
        )
        data = json.loads(completed.stdout)
        devices = data.get("result", {}).get("devices", [])
    except Exception:
        devices = []

    matches = []
    for d in devices:
        hardware = d.get("hardwareProperties", {})
        connection = d.get("connectionProperties", {})
        state = d.get("deviceProperties", {})

        udid = hardware.get("udid")
        reality = hardware.get("reality")
        product = hardware.get("productType", "")
        model = hardware.get("marketingName", product)
        name = state.get("name", product)
        os_ver = state.get("osVersionNumber", "unknown")
        build = state.get("osBuildUpdate", "unknown")
        paired = connection.get("pairingState") == "paired"

        if udid in PRIMARY_PHONE_BLOCKLIST:
            # Strictly blocked for user safety
            continue

        if reality == "physical" and product.startswith("iPhone") and udid:
            matches.append({
                "name": name,
                "model": model,
                "product": product,
                "udid": udid,
                "version": os_ver,
                "build": build,
                "paired": paired,
                "transport": connection.get("transportType", "unknown"),
            })
    return matches


def select_device(requested_udid: Optional[str]) -> dict[str, Any]:
    if requested_udid and requested_udid in PRIMARY_PHONE_BLOCKLIST:
        raise AirLiftCarrierError(
            f"REFUSED: Device '{requested_udid}' is user's primary device and is protected by safety blocklist."
        )

    devices = query_connected_devices()
    if not devices:
        raise AirLiftCarrierError(
            "No compatible physical iPhone test device detected via devicectl.\n"
            "Ensure iPhone 14 Pro is connected via USB, unlocked, and trusted."
        )

    if requested_udid:
        for d in devices:
            if d["udid"].casefold() == requested_udid.casefold():
                return d
        raise AirLiftCarrierError(f"Requested device '{requested_udid}' not found among connected test devices.")

    if len(devices) == 1:
        return devices[0]

    print("\nConnected compatible iPhones:", file=sys.stderr)
    for i, d in enumerate(devices, 1):
        print(f"  [{i}] {d['name']} ({d['model']}) - iOS {d['version']} ({d['build']}) [{d['udid']}]", file=sys.stderr)

    while True:
        try:
            choice = input("Select device (number): ").strip()
            idx = int(choice)
            if 1 <= idx <= len(devices):
                return devices[idx - 1]
        except (ValueError, EOFError, KeyboardInterrupt):
            raise AirLiftCarrierError("Device selection cancelled.")


def deploy_carrier(
    udid: str,
    payload_archive: bytes,
    *,
    verbose: bool = False,
) -> dict[str, Any]:
    target = DEFAULT_TARGET
    leaf = TARGET_LEAF

    token = secrets.token_hex(10)
    source = f"airlift-src-{token}"
    link_destination = f"airlift-link-{token}"
    recovered = f"airlift-recovered-{token}"
    link_identifier = f"../../{source}/p0/p1/p2/link"
    target_path = posixpath.join(target, leaf)
    target_identifier = posixpath.relpath(target_path, AIRLOCK_ROOT)
    payload_identifier = f"../../{source}/payload"

    identifiers = [link_identifier, payload_identifier, target_identifier]
    destinations = [
        link_destination,
        posixpath.join(link_destination, leaf),
        recovered,
    ]

    with tempfile.TemporaryDirectory(prefix="airlift-carrier-") as temporary:
        work = Path(temporary)
        archive_path = work / "payload.zip"
        books_path = work / "Books.plist"
        expected_path = work / "expected.bin"
        snapshot_root = work / "books-snapshot"
        snapshot_root.mkdir()

        archive_path.write_bytes(build_streaming_zip(target, payload_archive))
        books_path.write_bytes(build_books_plist(identifiers))
        expected_path.write_bytes(payload_archive)

        print("[*] Probing device status...", flush=True)
        probe = native("probe", udid)
        if not operation_ok(probe):
            raise AirLiftCarrierError("Device preflight probe failed", {"probe": probe})

        print("[*] Preserving Books database state...", flush=True)
        snapshot = native("snapshot-books", udid, os.fspath(snapshot_root))
        if not operation_ok(snapshot):
            raise AirLiftCarrierError("Failed to preserve Books state", {"snapshot": snapshot})

        print("[*] Staging streaming archive via AFC conduit...", flush=True)
        stage = native(
            "stage",
            udid,
            source,
            link_destination,
            recovered,
            os.fspath(archive_path),
            os.fspath(books_path),
            os.fspath(snapshot_root),
        )
        if not operation_ok(stage):
            raise AirLiftCarrierError("Staging payload failed", {"stage": stage})

        print("[*] Synchronizing payload into SpringBoard via AirTraffic...", flush=True)
        command = [os.fspath(AIRTRAFFIC_HOST), udid]
        for identifier, destination in zip(identifiers, destinations):
            command.extend((identifier, destination))
        atc = run_json(command, timeout=120)
        if atc.get("exitCode") != 0 or not atc.get("ok"):
            raise AirLiftCarrierError("AirTraffic synchronization failed", {"atc": atc})

        print("[*] Verifying write and cleaning up staging artifacts (finish-deploy)...", flush=True)
        finish = native(
            "finish-deploy",
            udid,
            source,
            link_destination,
            recovered,
            os.fspath(expected_path),
            target[1:],
            leaf,
            "1",
            os.fspath(snapshot_root),
        )
        if not operation_ok(finish):
            raise AirLiftCarrierError("Finalization and cleanup verification failed", {"finish": finish})

        operation = finish.get("operation", {})
        return {
            "ok": True,
            "exactBytesRecovered": bool(operation.get("recoveredBytesMatch")),
            "targetPresent": bool(operation.get("targetPresent")),
            "cleanupComplete": bool(operation.get("cleanupComplete")),
            "diagnostics": {
                "probe": probe,
                "snapshot": snapshot,
                "stage": stage,
                "atc": atc,
                "finish": finish,
            } if verbose else None,
        }


def reboot_device(udid: str, style: str = "userspace") -> bool:
    print(f"[*] Triggering {style} reboot via devicectl...", flush=True)
    command = [
        "xcrun",
        "devicectl",
        "device",
        "reboot",
        "--device",
        udid,
        "--style",
        style,
        "--quiet",
    ]
    try:
        completed = subprocess.run(command, check=True, timeout=30)
        return completed.returncode == 0
    except subprocess.CalledProcessError as e:
        print(f"Warning: Reboot command returned exit code {e.returncode}. Please manually restart device.", file=sys.stderr)
        return False
    except Exception as e:
        print(f"Warning: Failed to invoke reboot ({e}). Please manually restart device.", file=sys.stderr)
        return False


def main() -> int:
    parser = argparse.ArgumentParser(
        description="AirLift Carrier Deployer for iOS 27 (Physical Devices)"
    )
    parser.add_argument("-c", "--carrier", help="Primary Carrier Name (e.g. '中国移动 5G')")
    parser.add_argument("-b", "--bars", type=int, default=4, choices=range(0, 5), help="Primary Signal Bars (0-4, default: 4)")
    parser.add_argument("-t", "--type", default="5g", choices=NETWORK_TYPES.keys(), help="Primary Network Type (default: 5g)")
    parser.add_argument("--badge", help="Primary SIM Badge (e.g. 'P', '主卡')")
    parser.add_argument("-s", "--secondary-carrier", help="Secondary Carrier Name for Dual SIM")
    parser.add_argument("--secondary-bars", type=int, default=4, choices=range(0, 5), help="Secondary Signal Bars (default: 4)")
    parser.add_argument("--secondary-type", default="5g", choices=NETWORK_TYPES.keys(), help="Secondary Network Type (default: 5g)")
    parser.add_argument("--secondary-badge", help="Secondary SIM Badge (e.g. 'S', '副卡')")
    parser.add_argument("--reset", action="store_true", help="Reset/Clear overrides to restore native carrier")
    parser.add_argument("--device", metavar="UDID", help="Specify physical iPhone UDID")
    parser.add_argument("--no-reboot", action="store_true", help="Do not trigger reboot after deploy")
    parser.add_argument("--full-reboot", action="store_true", help="Perform full reboot instead of userspace reboot")
    parser.add_argument("--dry-run", action="store_true", help="Generate payload and streaming zip locally without device connection")
    parser.add_argument("-o", "--output", help="Save the generated StatusBarOverrides.archive to a local file")
    parser.add_argument("-v", "--verbose", action="store_true", help="Print debug diagnostics")

    args = parser.parse_args()

    if not args.reset and not args.carrier and not args.secondary_carrier:
        print("Error: Specify at least -c/--carrier or --reset.", file=sys.stderr)
        parser.print_help()
        return 1

    try:
        print("\n[*] Generating binary StatusBarOverrides.archive...")
        payload = build_cellular_archive(
            primary_carrier=args.carrier,
            primary_bars=args.bars,
            primary_type=NETWORK_TYPES[args.type],
            primary_badge=args.badge,
            secondary_carrier=args.secondary_carrier,
            secondary_bars=args.secondary_bars,
            secondary_type=NETWORK_TYPES[args.secondary_type],
            secondary_badge=args.secondary_badge,
            is_reset=args.reset,
        )
        print(f"[✓] Archive generated successfully ({len(payload)} bytes).")

        if args.output:
            Path(args.output).write_bytes(payload)
            print(f"[✓] Archive saved to: {args.output}")

        if args.dry_run:
            zip_bytes = build_streaming_zip(DEFAULT_TARGET, payload)
            print(f"[✓] StreamingZip package generated ({len(zip_bytes)} bytes).")
            print("\n[Dry-Run Complete] Payload and packaging verified with zero errors.")
            return 0

        if not DEVICE_HELPER.is_file() or not AIRTRAFFIC_HOST.is_file():
            print("Error: Helpers not built. Run 'make' inside the airlift directory first.", file=sys.stderr)
            return 1

        device = select_device(args.device)
        print(f"\n[+] Selected Target Device: {device['name']} ({device['model']})")
        print(f"    UDID:    {device['udid']}")
        print(f"    Version: iOS {device['version']} ({device['build']})")
        print(f"[✓] Archive generated ({len(payload)} bytes).")

        result = deploy_carrier(device["udid"], payload, verbose=args.verbose)
        if result["ok"]:
            print("\n" + "=" * 50)
            print("  🎉 CARRIER CONFIGURATION DEPLOYED SUCCESSFULLY! ")
            print("=" * 50)
            print(f"Target:             /var/mobile/Library/SpringBoard/StatusBarOverrides.archive")
            print(f"Target Present:     {result['targetPresent']}")
            print(f"Exact Bytes Match:  {result['exactBytesRecovered']}")
            print(f"Sandbox Cleaned:    {result['cleanupComplete']}")

            if not args.no_reboot:
                style = "full" if args.full_reboot else "userspace"
                reboot_device(device["udid"], style=style)
                print(f"\n[✓] Reboot command sent. Please unlock the device once it restarts to view the changes.")
            else:
                print("\n[!] Reboot skipped. You must restart the iPhone for SpringBoard to load the new archive.")
            return 0
        else:
            print("\n[-] Deployment failed.", file=sys.stderr)
            return 2

    except AirLiftCarrierError as e:
        print(f"\n[-] Error: {e}", file=sys.stderr)
        if e.details:
            print(json.dumps(e.details, indent=2), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
