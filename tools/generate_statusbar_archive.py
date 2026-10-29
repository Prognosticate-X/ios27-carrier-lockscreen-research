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

MAX_CARRIER_LENGTH = 64
MAX_BADGE_LENGTH = 8

def _parse_bars_arg(value: Optional[str]) -> Optional[int]:
    if value is None:
        return None
    normalized = str(value).strip().lower()
    if normalized in ("", "omit", "none"):
        return None
    try:
        bars = int(normalized)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"Invalid signal bars '{value}': must be 0-4 or 'omit'.") from exc
    if not (0 <= bars <= 4):
        raise argparse.ArgumentTypeError(f"Signal bars must be between 0 and 4 (got {bars}), or 'omit'.")
    return bars


def build_cellular_archive(
    primary_carrier: Optional[str] = None,
    primary_bars: Optional[int] = 4,
    primary_type: Optional[int] = 10,
    primary_badge: Optional[str] = None,
    secondary_carrier: Optional[str] = None,
    secondary_bars: Optional[int] = 4,
    secondary_type: Optional[int] = 10,
    secondary_badge: Optional[str] = None,
    is_reset: bool = False,
    partial: bool = False,
    vpn: Optional[bool] = None,
) -> bytes:
    """
    Constructs an NSKeyedArchiver bplist compliant with iOS 27 SpringBoard.
    Defaults to primary_bars=4 (4 full lit bars in status bar) and primary_type=10 (5G).
    Note: Physical iPhone 14 Pro verification proved that omitting displayValue
    (primary_bars=None) decodes as 0 via -[NSCoder decodeIntegerForKey:@"displayValue"],
    rendering 0 lit bars (4 dimmed bars) in the top status bar.
    """
    if primary_carrier and len(primary_carrier) > MAX_CARRIER_LENGTH:
        raise ValueError(f"Primary carrier name exceeds maximum length of {MAX_CARRIER_LENGTH} characters.")
    if secondary_carrier and len(secondary_carrier) > MAX_CARRIER_LENGTH:
        raise ValueError(f"Secondary carrier name exceeds maximum length of {MAX_CARRIER_LENGTH} characters.")
    if primary_badge and len(primary_badge) > MAX_BADGE_LENGTH:
        raise ValueError(f"Primary badge exceeds maximum length of {MAX_BADGE_LENGTH} characters.")
    if secondary_badge and len(secondary_badge) > MAX_BADGE_LENGTH:
        raise ValueError(f"Secondary badge exceeds maximum length of {MAX_BADGE_LENGTH} characters.")

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
        p_entry: Dict[str, Any] = {
            "badgeString": uid_p_badge,
            "callForwardingEnabled": False,
            "crossfadeString": uid_p_str,
            "displayRawValue": 0,
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
            "wifiCallingEnabled": False,
        }
        if primary_bars is not None:
            p_entry["displayValue"] = int(primary_bars)
        if primary_type is not None:
            p_entry["type"] = int(primary_type)
        if partial:
            p_entry.pop("displayValue", None)
            p_entry.pop("type", None)
        uid_p_entry = add_obj(p_entry)
        data_dict["cellularEntry"] = uid_p_entry

    # Secondary entry
    if secondary_carrier:
        uid_s_str = add_obj(secondary_carrier)
        uid_s_badge = add_obj(secondary_badge) if secondary_badge else plistlib.UID(0)
        s_entry: Dict[str, Any] = {
            "badgeString": uid_s_badge,
            "callForwardingEnabled": False,
            "crossfadeString": uid_s_str,
            "displayRawValue": 0,
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
            "wifiCallingEnabled": False,
        }
        if secondary_bars is not None:
            s_entry["displayValue"] = int(secondary_bars)
        if secondary_type is not None:
            s_entry["type"] = int(secondary_type)
        if partial:
            s_entry.pop("displayValue", None)
            s_entry.pop("type", None)
        uid_s_entry = add_obj(s_entry)
        data_dict["secondaryCellularEntry"] = uid_s_entry

    uid_vpn_entry = None
    if vpn is not None:
        v_entry = {
            "enabled": bool(vpn),
        }
        uid_vpn_entry = add_obj(v_entry)
        data_dict["vpnEntry"] = uid_vpn_entry

    # Add Classes to objects
    uid_cls_entry = add_obj(cls_entry)
    cls_vpn = {
        "$classes": ["STStatusBarDataEntry", "NSObject"],
        "$classname": "STStatusBarDataEntry",
    }
    uid_cls_vpn = add_obj(cls_vpn)
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
    if uid_vpn_entry is not None:
        objects[uid_vpn_entry.data]["$class"] = uid_cls_vpn

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
    parser.add_argument("-b", "--bars", type=_parse_bars_arg, default=4, help="Primary Signal bars (0-4, default: 4; or 'omit' to omit displayValue)")
    parser.add_argument("-t", "--type", default="5g", choices=list(NETWORK_TYPES.keys()), help="Primary Network type (default: 5g)")
    parser.add_argument("--badge", help="Primary SIM badge (e.g. 'P', '1', '主卡')")
    parser.add_argument("-s", "--secondary-carrier", help="Secondary Carrier name string (Dual SIM)")
    parser.add_argument("--secondary-bars", type=_parse_bars_arg, default=4, help="Secondary Signal bars (0-4, default: 4; or 'omit' to omit displayValue)")
    parser.add_argument("--secondary-type", default="5g", choices=list(NETWORK_TYPES.keys()), help="Secondary Network type (default: 5g)")
    parser.add_argument("--secondary-badge", help="Secondary SIM badge (e.g. 'S', '2', '副卡')")
    parser.add_argument("--reset", action="store_true", help="Generate an empty reset archive to restore system default")
    parser.add_argument("--partial", action="store_true", help="Partial override: omit both displayValue and type")
    parser.add_argument("--vpn", choices=["auto", "on", "off"], default="auto", help="VPN indicator mode: 'auto' (default, native live passthrough, unsuppressed), 'on' (force show VPN icon), 'off' (force hide VPN icon)")
    parser.add_argument("-i", "--inspect", help="Inspect an existing archive file")
    parser.add_argument("-o", "--output", default="StatusBarOverrides.archive", help="Output archive path")
    parser.add_argument("--deploy-simulator", nargs="?", const="booted", help="Deploy archive directly to a booted simulator (or specify UDID) and reload SpringBoard")

    args = parser.parse_args()

    if args.inspect:
        inspect_archive(args.inspect)
        return

    if not args.carrier and not args.secondary_carrier and not args.reset:
        parser.print_help()
        print("\n[Error] Must specify at least -c/--carrier, -s/--secondary-carrier, or --reset")
        sys.exit(1)

    vpn_mode = True if args.vpn == "on" else (False if args.vpn == "off" else None)

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
        partial=args.partial,
        vpn=vpn_mode,
    )

    with open(args.output, "wb") as f:
        f.write(payload)

    status_str = "RESET (Default Carrier)" if args.reset else f"Primary='{args.carrier}', Secondary='{args.secondary_carrier}'"
    print(f"[✓] Generated '{args.output}' successfully ({len(payload)} bytes). Mode: {status_str}")

    if args.deploy_simulator:
        import subprocess, re
        sim_target = args.deploy_simulator
        if sim_target == "booted":
            out = subprocess.check_output(["xcrun", "simctl", "list", "devices"], text=True)
            booted_matches = re.findall(r"\(([0-9A-F\-]{36})\)\s+\(Booted\)", out)
            if not booted_matches:
                print("[!] No booted simulator found to deploy.")
                return
            sim_target = booted_matches[0]
            print(f"[*] Detected booted simulator: {sim_target}")

        import os
        sim_sb_dir = os.path.expanduser(f"~/Library/Developer/CoreSimulator/Devices/{sim_target}/data/Library/SpringBoard")
        os.makedirs(sim_sb_dir, exist_ok=True)
        dest_archive = os.path.join(sim_sb_dir, "StatusBarOverrides.archive")
        with open(dest_archive, "wb") as f:
            f.write(payload)
        print(f"[✓] Copied archive to {dest_archive}")

        # Safely reload simulator systemstatusd and SpringBoard
        try:
            subprocess.run(["xcrun", "simctl", "spawn", sim_target, "killall", "-9", "systemstatusd"], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            subprocess.run(["xcrun", "simctl", "spawn", sim_target, "killall", "-9", "SpringBoard"], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass
        subprocess.run(["killall", "-9", "SpringBoard"], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print(f"[✓] Reloaded SpringBoard and systemstatusd for simulator {sim_target}. Changes applied!")


if __name__ == "__main__":
    main()
