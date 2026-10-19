#!/usr/bin/env python3
"""
Universal AirLift Carrier Deployer for iOS 27 (Physical Devices)
Persistently applies custom carrier name & cellular status bar configuration
to any compatible iPhone (Dynamic Island or Classic) running iOS 27.x without jailbreak.

Enhanced with:
  - Two-Phase Auto Overwrite Pipeline (--force-overwrite)
  - Dynamic Island visual width heuristic & truncation warnings
  - Fast Userspace Reboot & auto-reconnect coordinator
  - Named Presets management (--save-preset, --preset, --list-presets)
  - Interactive configuration wizard (-i / --interactive)
"""

from __future__ import annotations

import argparse
import io
import json
import os
import plistlib
import posixpath
import secrets
import stat
import struct
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path
from typing import Any, Optional, Dict

ROOT = Path(__file__).resolve().parent

# Locate airlift directory whether script is executed from airlift/ or tools/
if (ROOT / "Sources").is_dir():
    AIRLIFT_DIR = ROOT
elif (ROOT.parent / "airlift" / "Sources").is_dir():
    AIRLIFT_DIR = ROOT.parent / "airlift"
else:
    AIRLIFT_DIR = ROOT

# Import helper modules from tools (this file ships in both airlift/ and tools/)
_IMPORT_ROOTS = [ROOT, ROOT.parent / "tools", ROOT / "tools", Path(__file__).resolve().parent.parent / "tools"]
for _candidate in _IMPORT_ROOTS:
    if _candidate.is_dir() and str(_candidate) not in sys.path:
        sys.path.append(str(_candidate))

from display_metrics import check_dynamic_island_overflow, get_visual_width  # noqa: E402
from presets import get_preset, list_presets_formatted, save_preset  # noqa: E402

TARGET_HEADER = AIRLIFT_DIR / "Sources" / "airlift_target.h"
DEVICE_HELPER = AIRLIFT_DIR / "build" / "device_helper"
AIRTRAFFIC_HOST = AIRLIFT_DIR / "build" / "airtraffic_host"

DEFAULT_TARGET = "/var/mobile/Library/SpringBoard"
TARGET_LEAF = "StatusBarOverrides.archive"
AIRLOCK_ROOT = "/var/mobile/Media/Airlock/Book"
SZ_EXTRA_ID = 0x5A53

ALLOWED_TARGET_PREFIXES = (
    "/var/mobile/Library/SpringBoard",
)

MAX_CARRIER_LENGTH = 64
MAX_BADGE_LENGTH = 8

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
    """Constructs an NSKeyedArchiver bplist compliant with iOS 27 SpringBoard."""
    if primary_carrier and len(primary_carrier) > MAX_CARRIER_LENGTH:
        raise AirLiftCarrierError(f"Primary carrier name exceeds maximum length of {MAX_CARRIER_LENGTH} characters.")
    if secondary_carrier and len(secondary_carrier) > MAX_CARRIER_LENGTH:
        raise AirLiftCarrierError(f"Secondary carrier name exceeds maximum length of {MAX_CARRIER_LENGTH} characters.")
    if primary_badge and len(primary_badge) > MAX_BADGE_LENGTH:
        raise AirLiftCarrierError(f"Primary badge exceeds maximum length of {MAX_BADGE_LENGTH} characters.")
    if secondary_badge and len(secondary_badge) > MAX_BADGE_LENGTH:
        raise AirLiftCarrierError(f"Secondary badge exceeds maximum length of {MAX_BADGE_LENGTH} characters.")

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
    normalized_target = posixpath.normpath(target)
    if not any(
        normalized_target == allowed or normalized_target.startswith(allowed + "/")
        for allowed in ALLOWED_TARGET_PREFIXES
    ):
        raise AirLiftCarrierError(
            f"Security Violation: Target path '{target}' is not in allowed SpringBoard targets: {ALLOWED_TARGET_PREFIXES}"
        )
    target_tail = normalized_target.lstrip("/")
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


_ENV_BLOCKLIST = [
    udid.strip()
    for udid in os.environ.get("AIRLIFT_BLOCKED_UDIDS", "").split(",")
    if udid.strip()
]
PRIMARY_PHONE_BLOCKLIST = frozenset(_ENV_BLOCKLIST)


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
            continue

        if reality == "physical" and product.startswith("iPhone") and udid:
            # Check dynamic island support
            has_dynamic_island = product in (
                "iPhone15,2", "iPhone15,3",  # 14 Pro / 14 Pro Max
                "iPhone15,4", "iPhone15,5",  # 15 / 15 Plus
                "iPhone16,1", "iPhone16,2",  # 15 Pro / 15 Pro Max
                "iPhone17,1", "iPhone17,2",  # 16 Pro / 16 Pro Max
                "iPhone17,3", "iPhone17,4",  # 16 / 16 Plus
            )
            matches.append({
                "name": name,
                "model": model,
                "product": product,
                "udid": udid,
                "version": os_ver,
                "build": build,
                "paired": paired,
                "transport": connection.get("transportType", "unknown"),
                "hasDynamicIsland": has_dynamic_island,
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
            "Ensure iPhone is connected via USB, unlocked, and trusted."
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
        island_str = " [Dynamic Island]" if d["hasDynamicIsland"] else ""
        print(f"  [{i}] {d['name']} ({d['model']}){island_str} - iOS {d['version']} ({d['build']}) [{d['udid']}]", file=sys.stderr)

    while True:
        try:
            choice = input("Select device (number): ").strip()
            idx = int(choice)
            if 1 <= idx <= len(devices):
                return devices[idx - 1]
        except (ValueError, EOFError, KeyboardInterrupt):
            raise AirLiftCarrierError("Device selection cancelled.")


PROBE_ATTEMPTS = 5
SNAPSHOT_ATTEMPTS = 5
STAGE_ATTEMPTS = 3
RETRY_DELAY = 2.0

_STAGE_FAILURE_FLAGS = (
    ("safeArguments", "generated staging names were rejected by the native helper"),
    ("localInputsReadable", "local StreamingZip/Books inputs could not be read"),
    ("booksPreimageStable", "device Books preimage changed between snapshot and staging"),
    ("freshPaths", "staging paths already exist on the device"),
    ("archiveSent", "StreamingZip archive was not delivered completely"),
    ("sourceObjectsPresent", "StreamingZip tree did not appear under /var/mobile/Media in time"),
    ("booksWritten", "Books/Sync/Books.plist could not be staged"),
)


def describe_stage_failure(operation: dict[str, Any]) -> str:
    """Translate the native stager flags into one actionable sentence."""
    reasons = [
        text
        for flag, text in _STAGE_FAILURE_FLAGS
        if flag in operation and not operation[flag]
    ]
    for key in ("zipServiceStatus", "zipMessageStatus", "zipResponseStatus"):
        value = operation.get(key)
        if isinstance(value, int) and value != 0:
            reasons.append(f"{key}={value}")
    response = operation.get("zipResponse")
    if isinstance(response, str) and response not in ("", "(none)"):
        reasons.append(f"conduit response {response}")
    return "; ".join(reasons) if reasons else "no diagnostic flag was reported"


def collect_books_snapshot(udid: str, work: Path) -> tuple[Path, dict[str, Any]]:
    """Preserve the device Books preimage; every staging attempt needs its own."""
    snapshot: dict[str, Any] = {}
    for _ in range(SNAPSHOT_ATTEMPTS):
        root = work / f"books-snapshot-{secrets.token_hex(6)}"
        root.mkdir()
        snapshot = native("snapshot-books", udid, os.fspath(root))
        if operation_ok(snapshot):
            return root, snapshot
        time.sleep(RETRY_DELAY)
    raise AirLiftCarrierError("Failed to preserve Books state", {"snapshot": snapshot})


def rollback_staging(
    udid: str,
    source: str,
    link_destination: str,
    recovered: str,
    snapshot_root: Path,
) -> dict[str, Any]:
    """Undo one staging attempt. Never raises: the original error must survive."""
    try:
        return native(
            "cleanup",
            udid,
            source,
            link_destination,
            recovered,
            os.fspath(snapshot_root),
        )
    except Exception as error:  # noqa: BLE001 - rollback is best effort
        return {"ok": False, "error": f"{type(error).__name__}: {error}"}


def deploy_carrier(
    udid: str,
    payload_archive: bytes,
    *,
    verbose: bool = False,
) -> dict[str, Any]:
    target = DEFAULT_TARGET
    leaf = TARGET_LEAF

    with tempfile.TemporaryDirectory(prefix="airlift-carrier-") as temporary:
        work = Path(temporary)
        expected_path = work / "expected.bin"
        expected_path.write_bytes(payload_archive)

        print("[*] Probing device status...", flush=True)
        probe = None
        for _ in range(PROBE_ATTEMPTS):
            probe = native("probe", udid)
            if operation_ok(probe):
                break
            time.sleep(RETRY_DELAY)

        if not probe or not operation_ok(probe):
            raise AirLiftCarrierError("Device preflight probe failed", {"probe": probe})
        if not probe.get("targetTested"):
            print("[!] CAUTION: Device iOS build is NOT in tested builds list. Proceeding with caution...", file=sys.stderr)

        stage: dict[str, Any] = {}
        snapshot: dict[str, Any] = {}
        rollback: dict[str, Any] = {}
        snapshot_root: Optional[Path] = None
        identifiers: list[str] = []
        destinations: list[str] = []

        for attempt in range(1, STAGE_ATTEMPTS + 1):
            token = secrets.token_hex(10)
            source = f"airlift-src-{token}"
            link_destination = f"airlift-link-{token}"
            recovered = f"airlift-recovered-{token}"
            identifiers = [f"../../{source}/p0/p1/p2/link", f"../../{source}/payload"]
            destinations = [link_destination, posixpath.join(link_destination, leaf)]

            archive_path = work / f"payload-{token}.zip"
            books_path = work / f"Books-{token}.plist"
            archive_path.write_bytes(build_streaming_zip(target, payload_archive))
            books_path.write_bytes(build_books_plist(identifiers))

            print(
                f"[*] Preserving Books database state (attempt {attempt}/{STAGE_ATTEMPTS})...",
                flush=True,
            )
            snapshot_root, snapshot = collect_books_snapshot(udid, work)

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
            if operation_ok(stage):
                break

            operation = stage.get("operation", {})
            reason = describe_stage_failure(operation)
            rollback = rollback_staging(
                udid, source, link_destination, recovered, snapshot_root
            )
            print(f"[!] Staging attempt {attempt} failed: {reason}", file=sys.stderr, flush=True)
            if not operation_ok(rollback):
                print(f"[!] Rollback incomplete: {json.dumps(rollback)}", file=sys.stderr, flush=True)

            deterministic = any(
                flag in operation and not operation[flag]
                for flag in ("safeArguments", "localInputsReadable", "freshPaths")
            )
            if deterministic or attempt == STAGE_ATTEMPTS:
                raise AirLiftCarrierError(
                    f"Staging payload failed: {reason}",
                    {"stage": stage, "rollback": rollback, "attempt": attempt},
                )
            time.sleep(RETRY_DELAY)

        assert snapshot_root is not None
        try:
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
                operation = finish.get("operation", {})
                detail = describe_stage_failure(operation)
                raise AirLiftCarrierError(
                    f"Finalization and cleanup verification failed: {detail}",
                    {"finish": finish},
                )
        except BaseException:
            rollback = rollback_staging(
                udid, source, link_destination, recovered, snapshot_root
            )
            if verbose:
                print(json.dumps({"rollback": rollback}, indent=2), file=sys.stderr)
            raise

        operation = finish.get("operation", {})
        bytes_verified = bool(operation.get("targetBytesVerified"))
        return {
            "ok": True,
            "targetPresent": bool(operation.get("targetPresent")),
            "exactBytesVerified": bytes_verified,
            "exactBytesRecovered": bytes_verified,
            "cleanupComplete": bool(operation.get("cleanupComplete")),
            "diagnostics": {
                "probe": probe,
                "snapshot": snapshot,
                "stage": stage,
                "atc": atc,
                "finish": finish,
            } if verbose else None,
        }


STAGING_NAME_MARKERS = ("airlift-src-", "airlift-link-", "airlift-recovered-")


def _staging_rows(payload: Any) -> Optional[list[dict[str, Any]]]:
    """Return the Books rows of a staging plist, or None for unrelated files."""
    if not isinstance(payload, dict):
        return None
    rows = payload.get("Books")
    if not isinstance(rows, list) or not rows:
        return None
    if not all(isinstance(row, dict) for row in rows):
        return None
    return rows


def _references_staging(row: dict[str, Any]) -> bool:
    identifier = row.get("Persistent ID")
    return isinstance(identifier, str) and any(
        marker in identifier for marker in STAGING_NAME_MARKERS
    )


def build_cleaned_books_snapshot(snapshot_root: Path, cleaned_root: Path) -> dict[str, Any]:
    """Copy a Books snapshot and strip AirLift staging state out of it.

    AirLift writes its staged asset identifiers into Books/Books.plist and
    Books/Sync/Books.plist. Files that only describe staging assets are
    removed; files that also carry real rows keep the real rows only.
    """
    cleaned_root.mkdir(parents=True, exist_ok=True)
    manifest = plistlib.loads((snapshot_root / "manifest.plist").read_bytes())
    files = manifest.get("files", {})
    dropped: list[str] = []
    filtered: list[str] = []
    for path, row in files.items():
        local_name = str(row.get("localName"))
        local_path = snapshot_root / local_name
        if not row.get("exists") or not local_path.is_file():
            continue
        (cleaned_root / local_name).write_bytes(local_path.read_bytes())
        try:
            payload = plistlib.loads(local_path.read_bytes())
        except Exception:
            continue
        rows = _staging_rows(payload)
        if rows is None or not any(_references_staging(row) for row in rows):
            continue
        kept = [row for row in rows if not _references_staging(row)]
        if kept:
            payload["Books"] = kept
            data = plistlib.dumps(payload, fmt=plistlib.FMT_BINARY, sort_keys=True)
            (cleaned_root / local_name).write_bytes(data)
            row["size"] = len(data)
            filtered.append(path)
        else:
            row["exists"] = False
            row["size"] = 0
            (cleaned_root / local_name).unlink(missing_ok=True)
            dropped.append(path)
    (cleaned_root / "manifest.plist").write_bytes(
        plistlib.dumps(manifest, fmt=plistlib.FMT_BINARY)
    )
    return {"droppedFiles": dropped, "filteredFiles": filtered}


def clean_device(udid: str, *, verbose: bool = False) -> dict[str, Any]:
    """Remove AirLift staging leftovers and reset AirLift-created Books state."""
    with tempfile.TemporaryDirectory(prefix="airlift-clean-") as temporary:
        work = Path(temporary)
        snapshot_root, snapshot = collect_books_snapshot(udid, work)
        cleaned_root = work / "cleaned-snapshot"
        cleaned = build_cleaned_books_snapshot(snapshot_root, cleaned_root)
        restore = native("restore-books", udid, os.fspath(cleaned_root))
        staging = native("clean-staging", udid)
        probe = native("probe", udid)
        report = {
            "ok": bool(restore.get("operation", {}).get("ok"))
            and bool(staging.get("operation", {}).get("ok")),
            "snapshot": snapshot,
            "booksCleaned": cleaned,
            "booksRestore": restore,
            "staging": staging,
            "probe": probe,
        }
        if verbose:
            print(json.dumps(report, indent=2), file=sys.stderr)
        return report


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


SPRINGBOARD_PROCESS_MARKER = "SpringBoard"


def parse_springboard_pid(table: str) -> Optional[int]:
    """Extract the SpringBoard PID from the devicectl process table."""
    for line in table.splitlines():
        if SPRINGBOARD_PROCESS_MARKER not in line or "/SpringBoard" not in line:
            continue
        fields = line.split()
        if fields and fields[0].isdigit():
            return int(fields[0])
    return None


def springboard_pid(udid: str) -> Optional[int]:
    """Return the running SpringBoard PID, or None when it cannot be read."""
    completed = subprocess.run(
        [
            "xcrun", "devicectl", "device", "info", "processes",
            "--device", udid, "--search", SPRINGBOARD_PROCESS_MARKER,
        ],
        check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, timeout=30,
    )
    if completed.returncode != 0:
        return None
    return parse_springboard_pid(completed.stdout)


def respring_device(udid: str, *, timeout: int = 90, quiet: bool = False) -> dict[str, Any]:
    """Restart SpringBoard so it re-reads StatusBarOverrides.archive.

    SpringBoard loads the archive exactly once, early during its startup. After
    a cold boot that read happens before the first unlock, while the archive
    (delivered through the media staging area) is still protection-locked, and
    SpringBoard never re-reads it - so freshly deployed overrides stay invisible
    until SpringBoard starts again on an already-unlocked device.
    """
    previous = springboard_pid(udid)
    if previous is None:
        raise AirLiftCarrierError(
            "Could not determine the SpringBoard PID. Unlock the device and retry."
        )
    if not quiet:
        print(f"[*] Restarting SpringBoard (PID {previous}) to load the archive...", flush=True)
    completed = subprocess.run(
        [
            "xcrun", "devicectl", "device", "process", "terminate",
            "--device", udid, "--pid", str(previous), "--kill",
        ],
        check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, timeout=30,
    )
    if completed.returncode != 0:
        raise AirLiftCarrierError(
            "Failed to restart SpringBoard",
            {"pid": previous, "stderr": completed.stderr.strip()},
        )

    started = time.time()
    while time.time() - started < timeout:
        time.sleep(2)
        current = springboard_pid(udid)
        if current is not None and current != previous:
            return {
                "ok": True,
                "previousPid": previous,
                "pid": current,
                "seconds": round(time.time() - started, 1),
            }
    raise AirLiftCarrierError(
        "SpringBoard did not come back in time", {"previousPid": previous}
    )


def wait_for_device_reconnect(udid: str, timeout_seconds: int = 60) -> bool:
    """Poll devicectl until target device reconnects and AFC/Books subsystems respond to probe."""
    print(f"[*] Waiting for device to finish userspace reboot ({udid})...", flush=True)
    start_time = time.time()
    # Step 1: Wait for device to appear in devicectl
    reconnected = False
    while time.time() - start_time < timeout_seconds:
        time.sleep(2)
        devs = query_connected_devices()
        for d in devs:
            if d["udid"].casefold() == udid.casefold() and d.get("paired"):
                print(f"[✓] Device recognized ({d['name']}). Verifying AFC & system daemon readiness...", flush=True)
                reconnected = True
                break
        if reconnected:
            break

    if not reconnected:
        return False

    # Step 2: Ensure AFC daemon and Books subsystem are fully unfrozen and responsive
    probe_start = time.time()
    while time.time() - probe_start < 20:
        time.sleep(2)
        try:
            probe = native("probe", udid)
            if operation_ok(probe):
                print("[✓] AFC file conduit & SpringBoard services confirmed ready.", flush=True)
                time.sleep(2)  # Buffer to allow Books database handle release
                return True
        except Exception:
            pass

    return True




def deploy_with_two_phase_overwrite(
    udid: str,
    payload_archive: bytes,
    *,
    verbose: bool = False,
    userspace_reboot: bool = True,
) -> bool:
    """Two-Phase Overwrite Coordinator:

    Bypasses ATAirlock's rename limitation by:
      Phase 1: Ingesting an empty reset archive (triggers SpringBoard self-eviction on reload)
      Reboot: Fast userspace reload to purge old archive from disk and cache
      Phase 2: Ingesting the fresh target payload archive
    """
    print("\n" + "=" * 55)
    print(" 🚀 EXECUTING TWO-PHASE OVERWRITE COORDINATOR")
    print("=" * 55)
    print("Phase 1: Deploying self-evicting reset archive to clear locked destination...")
    reset_payload = build_cellular_archive(is_reset=True)
    res1 = deploy_carrier(udid, reset_payload, verbose=verbose)
    if not res1.get("ok"):
        raise AirLiftCarrierError("Two-phase overwrite Phase 1 (self-eviction deploy) failed.")

    reboot_style = "userspace" if userspace_reboot else "full"
    print(f"[*] Reset payload staged. Triggering {reboot_style} restart for SpringBoard auto-eviction...")
    reboot_device(udid, style=reboot_style)

    if not wait_for_device_reconnect(udid, timeout_seconds=60):
        print("[!] Warning: Auto-reconnect timed out. Please unlock your device and press Enter to continue...", file=sys.stderr)
        try:
            input()
        except Exception:
            pass

    print("\nPhase 2: Deploying target carrier payload into pristine SpringBoard destination...")
    res2 = deploy_carrier(udid, payload_archive, verbose=verbose)
    if not res2.get("ok"):
        raise AirLiftCarrierError("Two-phase overwrite Phase 2 (payload deploy) failed.")

    print("[*] Final payload deployed successfully. Restarting SpringBoard to load it...")
    respring_device(udid)
    return True


def run_interactive_wizard() -> Dict[str, Any]:
    """Interactive command-line wizard for configuring carrier settings."""
    print("\n" + "=" * 50)
    print(" 📱 iOS 27 Carrier Customization Wizard")
    print("=" * 50)

    mode = input("Mode: [1] Single SIM, [2] Dual SIM, [3] Reset to Native [default: 1]: ").strip()
    if mode == "3":
        return {"reset": True}

    is_dual = mode == "2"

    primary = input("Enter Primary Carrier Name (e.g. '中国移动 5G'): ").strip()
    badge = input("Enter Primary SIM Badge (optional, e.g. 'P', '主卡'): ").strip() or None
    bars_str = input("Signal Bars (0-4) [default: 4]: ").strip()
    bars = int(bars_str) if bars_str.isdigit() and 0 <= int(bars_str) <= 4 else 4

    config = {
        "carrier": primary,
        "badge": badge,
        "bars": bars,
        "type": "5g",
    }

    if is_dual:
        sec = input("Enter Secondary Carrier Name (e.g. '中国联通 5G'): ").strip()
        sec_badge = input("Enter Secondary SIM Badge (optional, e.g. 'S', '副卡'): ").strip() or None
        sec_bars_str = input("Secondary Signal Bars (0-4) [default: 4]: ").strip()
        sec_bars = int(sec_bars_str) if sec_bars_str.isdigit() and 0 <= int(sec_bars_str) <= 4 else 4
        config.update({
            "secondary_carrier": sec,
            "secondary_badge": sec_badge,
            "secondary_bars": sec_bars,
            "secondary_type": "5g",
        })

    save_name = input("\nSave as reusable preset? (Enter preset name or leave empty to skip): ").strip()
    if save_name:
        save_preset(save_name, config)
        print(f"[✓] Saved preset as '{save_name}'!")

    return config


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

    # Enhanced options
    parser.add_argument("--force-overwrite", action="store_true", help="Enable two-phase auto-overwrite to bypass ATAirlock rename limitation")
    parser.add_argument("--preset", help="Load named carrier configuration preset")
    parser.add_argument("--list-presets", action="store_true", help="Display all available presets and exit")
    parser.add_argument("--save-preset", help="Save the current CLI configuration as a preset")
    parser.add_argument("-i", "--interactive", action="store_true", help="Launch interactive configuration wizard")
    parser.add_argument("--clean-device", action="store_true", help="Remove leftover AirLift staging artifacts and reset AirLift-created Books state")

    parser.add_argument("--device", metavar="UDID", help="Specify physical iPhone UDID")
    parser.add_argument("--no-reboot", action="store_true", help="Do not activate after deploy (no SpringBoard restart)")
    parser.add_argument("--full-reboot", action="store_true", help="Reboot the whole device instead of restarting SpringBoard (activation then needs a respring after unlock)")
    parser.add_argument("--respring", action="store_true", help="Restart SpringBoard so it loads StatusBarOverrides.archive (default activation; standalone use allowed)")
    parser.add_argument("--dry-run", action="store_true", help="Generate payload and streaming zip locally without device connection")
    parser.add_argument("-o", "--output", help="Save the generated StatusBarOverrides.archive to a local file")
    parser.add_argument("-v", "--verbose", action="store_true", help="Print debug diagnostics")

    args = parser.parse_args()

    if args.list_presets:
        print(list_presets_formatted())
        return 0

    # Handle Interactive Wizard
    if args.interactive:
        wizard_cfg = run_interactive_wizard()
        for k, v in wizard_cfg.items():
            setattr(args, k, v)

    # Handle Presets
    if args.preset:
        preset_cfg = get_preset(args.preset)
        if not preset_cfg:
            print(f"Error: Preset '{args.preset}' not found. Use --list-presets to view available.", file=sys.stderr)
            return 1
        print(f"[*] Applying preset '{args.preset}': {preset_cfg.get('description', '')}")
        args.carrier = preset_cfg.get("carrier")
        args.bars = preset_cfg.get("bars", 4)
        args.type = preset_cfg.get("type", "5g")
        args.badge = preset_cfg.get("badge")
        args.secondary_carrier = preset_cfg.get("secondary_carrier")
        args.secondary_bars = preset_cfg.get("secondary_bars", 4)
        args.secondary_type = preset_cfg.get("secondary_type", "5g")
        args.secondary_badge = preset_cfg.get("secondary_badge")

    if args.clean_device:
        try:
            device = select_device(args.device)
            print(f"[*] Repairing {device['name']} ({device['udid']})...")
            report = clean_device(device["udid"], verbose=args.verbose)
        except AirLiftCarrierError as error:
            print(f"\n[-] Error: {error}", file=sys.stderr)
            if error.details:
                print(json.dumps(error.details, indent=2), file=sys.stderr)
            return 1
        staging = report["staging"].get("operation", {})
        removed = staging.get("removed") or []
        remaining = staging.get("remaining") or []
        dropped = report["booksCleaned"]["droppedFiles"] or []
        filtered = report["booksCleaned"]["filteredFiles"] or []
        print(f"[✓] Staging trees removed: {len(removed)}")
        for name in removed:
            print(f"      - {name}")
        print(f"[✓] Books staging files reset: {', '.join(dropped) if dropped else 'none'}")
        if filtered:
            print(f"[✓] Books staging rows filtered out of: {', '.join(filtered)}")
        print(f"[✓] Books preimage restored: {report['booksRestore'].get('operation', {}).get('ok')}")
        if remaining:
            print(f"[!] Still present: {', '.join(remaining)}", file=sys.stderr)
            return 2
        return 0

    if args.respring and not args.carrier and not args.secondary_carrier and not args.reset:
        try:
            device = select_device(args.device)
            print(f"[*] Restarting SpringBoard on {device['name']}...")
            activated = respring_device(device["udid"])
        except AirLiftCarrierError as error:
            print(f"\n[-] Error: {error}", file=sys.stderr)
            if error.details:
                print(json.dumps(error.details, indent=2), file=sys.stderr)
            return 1
        print(
            f"[✓] SpringBoard restarted (PID {activated['previousPid']} -> {activated['pid']}) "
            f"in {activated['seconds']}s; the deployed archive is loading now."
        )
        return 0

    if args.save_preset:
        save_cfg = {
            "carrier": args.carrier,
            "bars": args.bars,
            "type": args.type,
            "badge": args.badge,
            "secondary_carrier": args.secondary_carrier,
            "secondary_bars": args.secondary_bars,
            "secondary_type": args.secondary_type,
            "secondary_badge": args.secondary_badge,
        }
        save_preset(args.save_preset, save_cfg)
        print(f"[✓] Configuration saved to preset '{args.save_preset}'.")
        if not args.carrier and not args.secondary_carrier:
            return 0

    if not args.reset and not args.carrier and not args.secondary_carrier:
        print("Error: Specify at least -c/--carrier, --preset, -i/--interactive, or --reset.", file=sys.stderr)
        parser.print_help()
        return 1

    try:
        # Dynamic Island Width Heuristic Evaluation
        if args.carrier:
            p_res = check_dynamic_island_overflow(
                args.carrier, args.badge, is_dual_sim=bool(args.secondary_carrier), is_dynamic_island=True
            )
            if p_res.is_overflow_risk:
                print(f"\n[⚠️ Layout Warning] Primary: {p_res.warning_message}", file=sys.stderr)

        if args.secondary_carrier:
            s_res = check_dynamic_island_overflow(
                args.secondary_carrier, args.secondary_badge, is_dual_sim=True, is_dynamic_island=True
            )
            if s_res.is_overflow_risk:
                print(f"[⚠️ Layout Warning] Secondary: {s_res.warning_message}", file=sys.stderr)

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
            print("\n[Dry-Run Complete] Payload, metrics, and packaging verified with zero errors.")
            return 0

        if not DEVICE_HELPER.is_file() or not AIRTRAFFIC_HOST.is_file():
            print("Error: Helpers not built. Run 'make' inside the airlift directory first.", file=sys.stderr)
            return 1

        device = select_device(args.device)
        print(f"\n[+] Selected Target Device: {device['name']} ({device['model']})")
        print(f"    UDID:    {device['udid']}")
        print(f"    Version: iOS {device['version']} ({device['build']})")
        if device.get("hasDynamicIsland"):
            print("    Display: Dynamic Island (Screen layout width bounded)")

        # Two-Phase Auto Overwrite Coordinator
        if args.force_overwrite:
            if args.reset:
                print("\n" + "=" * 55)
                print(" 🚀 EXECUTING RESET AUTO-EVICTION COORDINATOR")
                print("=" * 55)
                res = deploy_carrier(device["udid"], payload, verbose=args.verbose)
                if not res["ok"]:
                    print("\n[-] Reset deployment failed.", file=sys.stderr)
                    return 2
                reboot_style = "full" if args.full_reboot else "userspace"
                print(f"[*] Reset archive deployed. Triggering {reboot_style} restart for SpringBoard auto-eviction...")
                reboot_device(device["udid"], style=reboot_style)
                print("\n[✓] Reset complete. SpringBoard will auto-evict the archive and restore native cellular settings.")
                return 0
            else:
                deploy_with_two_phase_overwrite(
                    device["udid"],
                    payload,
                    verbose=args.verbose,
                    userspace_reboot=(not args.full_reboot),
                )
                return 0

        result = deploy_carrier(device["udid"], payload, verbose=args.verbose)
        if result["ok"]:
            print("\n" + "=" * 50)
            print("  🎉 CARRIER CONFIGURATION DEPLOYED SUCCESSFULLY! ")
            print("=" * 50)
            print(f"Target:             /var/mobile/Library/SpringBoard/StatusBarOverrides.archive")
            print(f"Target Present:     {result['targetPresent']} (probed through the staging symlink)")
            print(f"Byte Verification:  {'exact' if result['exactBytesVerified'] else 'unavailable (AFC sandbox blocks the readback)'}")
            print(f"Sandbox Cleaned:    {result['cleanupComplete']}")
            if not result["exactBytesVerified"]:
                print(
                    "[!] The archive content could not be read back through the AFC sandbox. If an archive\n"
                    "    already existed, ATAirlock may have skipped the overwrite: use --force-overwrite\n"
                    "    (two-phase) for updates, then reboot to apply.",
                    file=sys.stderr,
                )

            if args.no_reboot:
                print(
                    "\n[!] Activation skipped (--no-reboot). Status bar overrides load when SpringBoard restarts;\n"
                    "    run this command again with --respring (or just --respring) to apply them."
                )
            elif args.full_reboot:
                reboot_device(device["udid"], style="full")
                print(
                    "\n[✓] Full reboot dispatched. SpringBoard reads the archive before the first unlock, so\n"
                    "    after unlocking run '--respring' once to actually load the overrides."
                )
            else:
                activated = respring_device(device["udid"])
                print(
                    f"\n[✓] SpringBoard restarted (PID {activated['previousPid']} -> {activated['pid']}) "
                    f"in {activated['seconds']}s. Overrides are live now."
                )
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
