#!/usr/bin/env python3
"""Replace StatusBarOverrides.archive through a single AirTraffic session.

The plain deploy fails when the destination already exists (Cocoa move refuses
to overwrite), and SpringBoard may recreate the archive from its in-memory
record after a move-out. This tool chains both moves in one AirTraffic session:

  1. ../../../Library/SpringBoard/StatusBarOverrides.archive -> airlift-recovered-<token>
  2. ../../airlift-src-<token>/p0/p1/p2/link              -> airlift-link-<token>
  3. ../../airlift-src-<token>/payload                    -> airlift-link-<token>/StatusBarOverrides.archive

The old archive is captured in the media sandbox (and can be read), and the new
payload lands in a destination that was just vacated.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import secrets
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for candidate in (ROOT / "tools", Path(__file__).resolve().parent):
    if candidate.is_dir() and str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from airlift_carrier_deploy import (  # noqa: E402
    AIRTRAFFIC_HOST,
    build_books_plist,
    build_streaming_zip,
    collect_books_snapshot,
    native,
    operation_ok,
    respring_device,
    run_json,
    select_device,
    zip_info,
)
from statusbar_variant_lab import build_variant_archive, parse_value  # noqa: E402

ARCHIVE_IDENTIFIER = "../../../Library/SpringBoard/StatusBarOverrides.archive"
TARGET_DIR = "/var/mobile/Library/SpringBoard"
TARGET_LEAF = "StatusBarOverrides.archive"


def replace_archive(udid: str, payload: bytes, *, save_old: Path | None = None) -> dict:
    token = secrets.token_hex(10)
    source = f"airlift-src-{token}"
    link = f"airlift-link-{token}"
    recovered = f"airlift-recovered-{token}"
    link_ident = f"../../{source}/p0/p1/p2/link"
    payload_ident = f"../../{source}/payload"

    result: dict = {"token": token}
    with tempfile.TemporaryDirectory(prefix="airlift-replace-") as tmp:
        work = Path(tmp)
        zip_path = work / "stage.zip"
        books_path = work / "Books.plist"
        zip_path.write_bytes(build_streaming_zip(TARGET_DIR, payload))
        books_path.write_bytes(
            build_books_plist([ARCHIVE_IDENTIFIER, link_ident, payload_ident])
        )

        snapshot, snap = collect_books_snapshot(udid, work)
        result["snapshotOk"] = operation_ok(snap)
        stage = native(
            "stage", udid, source, link, recovered,
            os.fspath(zip_path), os.fspath(books_path), os.fspath(snapshot),
        )
        result["stageOk"] = operation_ok(stage)
        if not result["stageOk"]:
            result["stage"] = stage.get("operation", {})
            native("cleanup", udid, source, link, recovered, os.fspath(snapshot))
            return result

        atc = run_json(
            [
                os.fspath(AIRTRAFFIC_HOST), udid,
                ARCHIVE_IDENTIFIER, recovered,
                link_ident, link,
                payload_ident, f"{link}/{TARGET_LEAF}",
            ],
            timeout=180,
        )
        result["atcOk"] = atc.get("exitCode") == 0 and bool(atc.get("ok"))
        result["atc"] = {k: v for k, v in atc.items() if k != "exitCode"}

        old_read = native("read", udid, recovered, "4194304")
        old_op = old_read.get("operation", {})
        result["oldArchiveReadable"] = bool(old_op.get("ok"))
        if old_op.get("ok"):
            old_bytes = base64.b64decode(old_op.get("base64", ""))
            result["oldArchiveSize"] = len(old_bytes)
            if save_old is not None:
                save_old.write_bytes(old_bytes)
                result["oldArchiveSavedTo"] = os.fspath(save_old)

        probe = native("info", udid, f"{link}/{TARGET_LEAF}")
        op = probe.get("operation", {})
        result["newArchiveSize"] = op.get("fields", {}).get("st_size")
        result["newArchivePresent"] = op.get("status") != 8

        cleanup = native("cleanup", udid, source, link, recovered, os.fspath(snapshot))
        result["cleanupOk"] = operation_ok(cleanup)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", required=True)
    parser.add_argument("--set", action="append", default=[], metavar="KEY=VALUE")
    parser.add_argument("--omit", action="append", default=[], metavar="KEY")
    parser.add_argument("--save-old", type=Path)
    parser.add_argument("--no-respring", action="store_true")
    parser.add_argument("--udid")
    args = parser.parse_args()

    fields = {}
    for item in args.set:
        key, _, value = item.partition("=")
        fields[key] = parse_value(value)

    payload = build_variant_archive(args.name, fields, set(args.omit))
    device = select_device(args.udid)
    result = replace_archive(device["udid"], payload, save_old=args.save_old)
    print(json.dumps(result, indent=2))
    if result.get("atcOk") and not args.no_respring:
        print("respring:", respring_device(device["udid"], quiet=True))
    return 0 if result.get("atcOk") else 2


if __name__ == "__main__":
    sys.exit(main())
