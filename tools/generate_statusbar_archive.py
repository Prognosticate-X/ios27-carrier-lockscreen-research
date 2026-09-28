#!/usr/bin/env python3
"""
iOS 27 StatusBarOverrides.archive Generator & Inspector
Supports:
  - Single SIM (Primary Carrier)
  - Dual SIM (Primary + Secondary Carrier, Badges, Bars, Network Types)
  - Inspecting / Validating existing archives
  - Reset / Clear mode (generates empty archive to restore native carrier)
"""

import argparse
import plistlib
import sys
from typing import Optional, Dict, Any

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
        # Empty record that clears overrides
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

    # Build objects array dynamically
    objects = ["$null"] # 0

    def add_obj(val):
        objects.append(val)
        return plistlib.UID(len(objects) - 1)

    # Reserve UIDs for top-level classes
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

    # Root record placeholder
    root_dict = {}
    uid_root = add_obj(root_dict)

    # Status data dictionary
    data_dict = {}
    uid_data = add_obj(data_dict)

    # Primary entry
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

    # Secondary entry
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

    # Add Classes to objects
    uid_cls_entry = add_obj(cls_entry)
    uid_cls_data = add_obj(cls_data)
    uid_cls_set = add_obj(cls_set)
    uid_cls_record = add_obj(cls_record)

    # Empty suppressedBackgroundActivityIdentifiers set
    uid_empty_set = add_obj({"$class": uid_cls_set, "NS.objects": []})

    # Fixup classes in dictionaries
    root_dict["$class"] = uid_cls_record
    root_dict["statusBarData"] = uid_data
    root_dict["suppressedBackgroundActivityIdentifiers"] = uid_empty_set

    data_dict["$class"] = uid_cls_data
    if primary_carrier:
        objects[uid_p_entry.data]["$class"] = uid_cls_entry
    if secondary_carrier:
        objects[uid_s_entry.data]["$class"] = uid_cls_entry

    plist_dict = {
        "$archiver": "NSKeyedArchiver",
        "$version": 100000,
        "$top": {"root": uid_root},
        "$objects": objects,
    }

    return plistlib.dumps(plist_dict, fmt=plistlib.FMT_BINARY)


def inspect_archive(path: str):
    """Parses and pretty-prints an existing StatusBarOverrides.archive"""
    with open(path, "rb") as f:
        data = plistlib.load(f)
    print(f"=== Archive Inspection: {path} ===")
    objects = data.get("$objects", [])
    top = data.get("$top", {}).get("root")
    print(f"Top Root UID: {top}")
    for idx, obj in enumerate(objects):
        if isinstance(obj, dict):
            classname = obj.get("$classname") or obj.get("$class")
            print(f"  [{idx}] dict (class: {classname})")
            for k, v in obj.items():
                if k not in ("$class", "$classes", "$classname"):
                    target_val = objects[v.data] if isinstance(v, plistlib.UID) and v.data < len(objects) else v
                    print(f"       {k} = {target_val} (raw: {v})")
        else:
            print(f"  [{idx}] {type(obj).__name__}: {obj}")


def main():
    parser = argparse.ArgumentParser(
        description="iOS 27 StatusBarOverrides.archive Generator & Tool"
    )
    parser.add_argument("-c", "--carrier", help="Primary Carrier name string")
    parser.add_argument("-b", "--bars", type=int, default=4, help="Primary Signal bars (0-4)")
    parser.add_argument("-t", "--type", default="5g", choices=list(NETWORK_TYPES.keys()), help="Primary Network type")
    parser.add_argument("--badge", help="Primary SIM badge (e.g. 'P', '1', '主卡')")
    parser.add_argument("-s", "--secondary-carrier", help="Secondary Carrier name string (Dual SIM)")
    parser.add_argument("--secondary-bars", type=int, default=4, help="Secondary Signal bars (0-4)")
    parser.add_argument("--secondary-type", default="5g", choices=list(NETWORK_TYPES.keys()), help="Secondary Network type")
    parser.add_argument("--secondary-badge", help="Secondary SIM badge (e.g. 'S', '2', '副卡')")
    parser.add_argument("--reset", action="store_true", help="Generate an empty reset archive to restore system default")
    parser.add_argument("-i", "--inspect", help="Inspect an existing archive file")
    parser.add_argument("-o", "--output", default="StatusBarOverrides.archive", help="Output archive path")

    args = parser.parse_args()

    if args.inspect:
        inspect_archive(args.inspect)
        return

    if not args.carrier and not args.secondary_carrier and not args.reset:
        parser.print_help()
        print("\n[Error] Must specify at least -c/--carrier, -s/--secondary-carrier, or --reset")
        sys.exit(1)

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

    with open(args.output, "wb") as f:
        f.write(payload)

    status_str = "RESET (Default Carrier)" if args.reset else f"Primary='{args.carrier}', Secondary='{args.secondary_carrier}'"
    print(f"[✓] Generated '{args.output}' successfully ({len(payload)} bytes). Mode: {status_str}")


if __name__ == "__main__":
    main()
