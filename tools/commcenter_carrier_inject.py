#!/usr/bin/env python3
"""Upstream CommCenter carrier-name injection over AirLift (iOS 27).

Research hypothesis (Route A of the dynamic-carrier investigation):

    NetworkListOperator::getLocalizedCompositeName() asks
    CarrierSettingsInterface for the Operator bundle value
    "InterCarrierRoamingDisplayNames" and, when the current PLMN string
    (MCC+MNC) is a key of that CFDictionary whose value is a CFString, returns
    that string as the operator display name.

Because the substitution happens inside CommCenter at the registration layer,
the status bar keeps rendering live baseband bars and the cellular entry still
disappears in Airplane Mode -- unlike the static StatusBarOverrides.archive.

This tool writes that mapping into the per-slot operator preference domains
that live in the HomeDomain preference directory (owner mobile:mobile):

    /var/mobile/Library/Preferences/com.apple.operator_1.plist
    /var/mobile/Library/Preferences/com.apple.operator_1.merged.plist

The write rides the already verified AirLift Books/AirTraffic path traversal.
Only the two preference directories and a fixed set of domain filenames are
allowed; every staging artefact is rolled back after the write.
"""

from __future__ import annotations

import argparse
import json
import os
import plistlib
import posixpath
import secrets
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

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
from commcenter_preference_builder import KNOWN_PLMNS, expand_plmns  # noqa: E402

PREFERENCE_DIR = "/var/mobile/Library/Preferences"

#: Domains that CommCenter's CarrierSettingsInterface is believed to consult.
ALLOWED_DOMAINS = (
    "com.apple.operator_1.plist",
    "com.apple.operator_1.merged.plist",
    "com.apple.operator_2.plist",
    "com.apple.operator_2.merged.plist",
    "com.apple.carrier_1.plist",
    "com.apple.carrier_1.merged.plist",
    "com.apple.carrier_2.plist",
    "com.apple.carrier_2.merged.plist",
)

MAX_PREFERENCE_BYTES = 512 * 1024


def build_staging_zip(target_dir: str, payload: bytes) -> bytes:
    """StreamingZip payload for the AirTraffic link, restricted to Preferences."""
    normalized = posixpath.normpath(target_dir)
    if normalized != PREFERENCE_DIR:
        raise AirLiftCarrierError(f"Refusing to write outside {PREFERENCE_DIR}: {target_dir}")
    if not payload or len(payload) > MAX_PREFERENCE_BYTES:
        raise AirLiftCarrierError(
            f"Preference payload must be 1..{MAX_PREFERENCE_BYTES} bytes, got {len(payload)}"
        )
    target_tail = normalized.lstrip("/")
    metadata = plistlib.dumps({"Version": 2}, fmt=plistlib.FMT_BINARY, sort_keys=True)
    import io
    import stat
    import zipfile

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


def build_operator_plist(
    carrier_name: str,
    plmns: List[str],
    *,
    include_carrier_name: bool = False,
) -> bytes:
    """Binary plist holding the InterCarrierRoamingDisplayNames mapping."""
    if not plmns:
        raise AirLiftCarrierError("At least one PLMN is required")
    mapping = {plmn: carrier_name for plmn in plmns}
    payload: Dict[str, Any] = {"InterCarrierRoamingDisplayNames": mapping}
    if include_carrier_name:
        payload["CarrierName"] = carrier_name
    return plistlib.dumps(payload, fmt=plistlib.FMT_BINARY, sort_keys=True)


def deploy_preference(
    udid: str,
    leaf: str,
    payload: bytes,
    *,
    verbose: bool = False,
) -> Dict[str, Any]:
    """Stage, dispatch and clean up one preference-domain write."""
    if leaf not in ALLOWED_DOMAINS:
        raise AirLiftCarrierError(f"Domain '{leaf}' is not in the allowlist {ALLOWED_DOMAINS}")

    token = secrets.token_hex(10)
    source = f"airlift-src-{token}"
    link_destination = f"airlift-link-{token}"
    recovered = f"airlift-recovered-{token}"
    link_identifier = f"../../{source}/p0/p1/p2/link"
    payload_identifier = f"../../{source}/payload"

    result: Dict[str, Any] = {"leaf": leaf, "ok": False}

    with tempfile.TemporaryDirectory(prefix="airlift-pref-") as temporary:
        work = Path(temporary)
        archive_path = work / f"pref-{token}.zip"
        books_path = work / f"Books-{token}.plist"
        archive_path.write_bytes(build_staging_zip(PREFERENCE_DIR, payload))
        books_path.write_bytes(build_books_plist([link_identifier, payload_identifier]))

        snapshot_root, snapshot = collect_books_snapshot(udid, work)
        if not operation_ok(snapshot):
            result["error"] = "Books snapshot failed"
            result["snapshot"] = snapshot
            return result

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
                result["error"] = "staging failed"
                result["stage"] = stage
                return result

            atc = run_json(
                [
                    os.fspath(AIRTRAFFIC_HOST),
                    udid,
                    link_identifier,
                    link_destination,
                    payload_identifier,
                    f"{link_destination}/{leaf}",
                ],
                timeout=120,
            )
            if atc.get("exitCode") != 0 or not atc.get("ok"):
                result["error"] = "AirTraffic dispatch failed"
                result["atc"] = atc
                return result

            probe = native("info", udid, f"{link_destination}/{leaf}")
            operation = probe.get("operation", {})
            fields = operation.get("fields", {})
            observed_size = None
            try:
                observed_size = int(fields.get("st_size", "-1"))
            except (TypeError, ValueError):
                observed_size = None
            status = operation.get("status")
            # In /var/mobile/Library/Preferences a missing file reports status 8
            # (ENOENT) while an existing one reports status 10 (EPERM: the AFC
            # daemon may only see metadata for protected preference files).
            # Content can therefore only be verified when the file is readable
            # (e.g. .GlobalPreferences.plist); otherwise presence is inferred.
            if observed_size == len(payload):
                verified = "size"
            elif status == 10:
                verified = "presence"
            else:
                verified = "missing"
            result["stat"] = operation
            result["observedSize"] = observed_size
            result["expectedSize"] = len(payload)
            result["verified"] = verified
            result["ok"] = verified != "missing"
            if not result["ok"]:
                result["error"] = (
                    "destination still reports ENOENT after the AirTraffic move; "
                    "the rename into Preferences was refused"
                )
        finally:
            cleanup = native(
                "cleanup",
                udid,
                source,
                link_destination,
                recovered,
                os.fspath(snapshot_root),
            )
            result["cleanup"] = cleanup.get("operation", {})
            if verbose:
                print(json.dumps(result, indent=2), file=sys.stderr)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-c", "--carrier-name", required=True)
    parser.add_argument("--plmn", action="append", default=[], help="PLMN or preset name (repeatable)")
    parser.add_argument("--slot", type=int, choices=[1, 2], default=None,
                        help="Restrict to one SIM slot (default: write both domains of the chosen slots)")
    parser.add_argument("--domain", action="append", default=[],
                        help="Explicit preference domain filename (repeatable)")
    parser.add_argument("--include-carrier-name", action="store_true",
                        help="Also write a CarrierName key into the domain")
    parser.add_argument("--dry-run", action="store_true", help="Build payloads only")
    parser.add_argument("--out", type=Path, default=Path("build/preferences"))
    parser.add_argument("--udid")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    plmns = expand_plmns(args.plmn)
    if not plmns:
        parser.error("no valid PLMN resolved from --plmn")

    payload = build_operator_plist(
        args.carrier_name, plmns, include_carrier_name=args.include_carrier_name
    )
    domains: List[str] = list(args.domain)
    if not domains:
        slots = [args.slot] if args.slot else [1, 2]
        domains = [f"com.apple.operator_{slot}{suffix}.plist"
                   for slot in slots for suffix in ("", ".merged")]
    for domain in domains:
        if domain not in ALLOWED_DOMAINS:
            parser.error(f"domain '{domain}' is not allowed")

    print(f"[*] Carrier name : {args.carrier_name!r}")
    print(f"[*] PLMNs        : {len(plmns)} entries ({', '.join(plmns[:8])}{' ...' if len(plmns) > 8 else ''})")
    print(f"[*] Payload      : {len(payload)} bytes binary plist")
    print(f"[*] Domains      : {', '.join(domains)}")

    if args.dry_run:
        args.out.mkdir(parents=True, exist_ok=True)
        for domain in domains:
            (args.out / domain).write_bytes(payload)
        (args.out / "decoded.json").write_text(
            json.dumps(
                {
                    "carrier": args.carrier_name,
                    "plmns": plmns,
                    "domains": domains,
                    "plist": plistlib.loads(payload),
                },
                indent=2,
                sort_keys=True,
            )
        )
        print(f"[✓] Dry run: wrote payloads to {args.out}")
        return 0

    device = select_device(args.udid)
    print(
        f"[*] Device: {device.get('name')} ({device.get('udid')}) "
        f"iOS {device.get('version')} ({device.get('build')})"
    )
    failures = 0
    for domain in domains:
        print(f"[*] Deploying {domain} ...", flush=True)
        result = deploy_preference(device["udid"], domain, payload, verbose=args.verbose)
        if result["ok"]:
            if result["verified"] == "size":
                print(f"[✓] {domain}: written ({result['observedSize']} bytes verified)")
            else:
                print(
                    f"[✓] {domain}: written (presence confirmed; content not readable "
                    f"through the AFC sandbox, expected {result['expectedSize']} bytes)"
                )
        else:
            failures += 1
            print(f"[!] {domain}: FAILED - {result.get('error')}", file=sys.stderr)
        if not operation_ok(result.get("cleanup", {})):
            failures += 1
            print(f"[!] {domain}: cleanup incomplete", file=sys.stderr)
    return 0 if failures == 0 else 2


if __name__ == "__main__":
    sys.exit(main())