#!/usr/bin/env python3
"""Status-bar archive variant lab (research).

Builds StatusBarOverrides.archive payloads with an arbitrary field subset so we
can measure, on-device, whether iOS 27 falls back to live telephony data for
fields that are omitted from the cellular entry.

Examples:
    python3 tools/statusbar_variant_lab.py --name V4 --omit displayValue --omit type --deploy
    python3 tools/statusbar_variant_lab.py --name V2 --set status=0 --deploy
    python3 tools/statusbar_variant_lab.py --name V3 --set enabled=false --deploy
"""

from __future__ import annotations

import argparse
import plistlib
import sys
from pathlib import Path
from typing import Any, Dict, Set

ROOT = Path(__file__).resolve().parent.parent
for candidate in (ROOT / "tools", Path(__file__).resolve().parent):
    if candidate.is_dir() and str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from airlift_carrier_deploy import deploy_carrier, respring_device, select_device  # noqa: E402

DEFAULT_FIELDS: Dict[str, Any] = {
    "badgeString": None,
    "callForwardingEnabled": False,
    "displayRawValue": 0,
    "displayValue": 4,
    "enabled": True,
    "isBootstrapCellular": False,
    "lowDataModeActive": False,
    "numberSharingState": 0,
    "rawValue": 0,
    "showsSOSWhenDisabled": False,
    "sosAvailable": False,
    "status": 5,
    "suffixString": None,
    "type": 10,
    "wifiCallingEnabled": False,
}


def parse_value(text: str) -> Any:
    lowered = text.lower()
    if lowered in ("true", "yes"):
        return True
    if lowered in ("false", "no"):
        return False
    if lowered in ("none", "null"):
        return None
    try:
        return int(text, 0)
    except ValueError:
        return text


def build_variant_archive(name: str, fields: Dict[str, Any], omit: Set[str]) -> bytes:
    entry = dict(DEFAULT_FIELDS)
    entry.update(fields)
    entry["string"] = name
    entry["crossfadeString"] = name

    objects: list[Any] = ["$null"]

    def add(value: Any) -> plistlib.UID:
        objects.append(value)
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
    cls_data = {"$classes": ["STStatusBarData", "NSObject"], "$classname": "STStatusBarData"}
    cls_set = {"$classes": ["NSSet", "NSObject"], "$classname": "NSSet"}
    cls_record = {
        "$classes": ["_SBSystemStatusStatusBarOverridesArchiveRecord", "NSObject"],
        "$classname": "_SBSystemStatusStatusBarOverridesArchiveRecord",
    }

    root: Dict[str, Any] = {}
    uid_root = add(root)
    data: Dict[str, Any] = {}
    uid_data = add(data)

    uid_name = add(name)
    entry_obj: Dict[str, Any] = {}
    uid_entry = add(entry_obj)
    for key, value in entry.items():
        if key in omit:
            continue
        if value is None:
            entry_obj[key] = plistlib.UID(0)
        elif key in ("string", "crossfadeString"):
            entry_obj[key] = uid_name
        else:
            entry_obj[key] = value
    data["cellularEntry"] = uid_entry

    uid_cls_entry = add(cls_entry)
    uid_cls_data = add(cls_data)
    uid_cls_set = add(cls_set)
    uid_cls_record = add(cls_record)
    uid_empty_set = add({"$class": uid_cls_set, "NS.objects": []})

    root["$class"] = uid_cls_record
    root["statusBarData"] = uid_data
    root["suppressedBackgroundActivityIdentifiers"] = uid_empty_set
    data["$class"] = uid_cls_data
    entry_obj["$class"] = uid_cls_entry

    return plistlib.dumps(
        {
            "$archiver": "NSKeyedArchiver",
            "$version": 100000,
            "$top": {"root": uid_root},
            "$objects": objects,
        },
        fmt=plistlib.FMT_BINARY,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", required=True)
    parser.add_argument("--set", action="append", default=[], metavar="KEY=VALUE")
    parser.add_argument("--omit", action="append", default=[], metavar="KEY")
    parser.add_argument("--deploy", action="store_true")
    parser.add_argument("--udid")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    fields: Dict[str, Any] = {}
    for item in args.set:
        key, _, value = item.partition("=")
        fields[key] = parse_value(value)
    omit = set(args.omit)

    payload = build_variant_archive(args.name, fields, omit)
    print(f"variant {args.name}: {len(payload)} bytes, set={fields}, omit={sorted(omit)}")

    if args.output:
        args.output.write_bytes(payload)
        print(f"written to {args.output}")

    if args.deploy:
        device = select_device(args.udid)
        result = deploy_carrier(device["udid"], payload)
        print(f"deploy ok={result['ok']} targetPresent={result.get('targetPresent')}")
        if result["ok"]:
            restart = respring_device(device["udid"], quiet=True)
            print(f"respring ok={restart.get('ok')} pid={restart.get('before')}->{restart.get('after')}")
        return 0 if result["ok"] else 2
    return 0


if __name__ == "__main__":
    sys.exit(main())