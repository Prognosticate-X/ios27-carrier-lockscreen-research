#!/usr/bin/env python3
"""
iOS 27 Upstream CommCenter Preference & PLMN Mapping Builder
Author: Prognosticate-X Research Suite
Objective:
  Implements the reverse-engineered upstream CommCenter PLMN lookup mechanism
  (NetworkListOperator::getLocalizedCompositeName @ 0x247e547e4 in libCommCenterBase.dylib)
  to enable dynamic carrier name customization while preserving authentic baseband
  signal bars and flight mode (airplane mode) network status decoupling.

Target Preference Domains:
  - /var/mobile/Library/Preferences/com.apple.operator_1.merged.plist (Slot 1)
  - /var/mobile/Library/Preferences/com.apple.operator_2.merged.plist (Slot 2)
  - /var/mobile/Library/Preferences/com.apple.commcenter.carrier_bundle.plist
"""

from __future__ import annotations

import argparse
import json
import plistlib
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# Standard Carrier PLMN mappings (MCC + MNC)
KNOWN_PLMNS = {
    # China Carriers
    "china_unicom": ["46001", "46006", "46009", "46010"],
    "china_mobile": ["46000", "46002", "46004", "46007", "46008", "46013"],
    "china_telecom": ["46003", "46005", "46011"],
    "china_broadnet": ["46015"],
    # US Carriers
    "att": ["310410", "310280", "310150"],
    "tmobile": ["310260", "310160", "310200", "310210", "310220", "310230", "310240", "310250", "310270", "310310", "310660"],
    "verizon": ["311480", "310012", "311270", "311271", "311272", "311273", "311274", "311275", "311276", "311277", "311278", "311279", "311280", "311281", "311282", "311283", "311284", "311285", "311286", "311287", "311288", "311289"],
    # UK / Europe / HK
    "cmhk": ["45412", "45413"],
    "csl": ["45400", "45402", "45410"],
    "smartone": ["45406", "45415", "45417"],
    "three_hk": ["45403", "45404", "45405"],
    "vodafone_uk": ["23415"],
    "ee_uk": ["23430", "23433"],
    "o2_uk": ["23410"],
}


def expand_plmns(requested: Optional[List[str]]) -> List[str]:
    """Expands named presets or PLMN strings into a deduplicated list of PLMNs."""
    if not requested or "all" in requested:
        # Return all known PLMNs
        all_plmns: set[str] = set()
        for plmn_list in KNOWN_PLMNS.values():
            all_plmns.update(plmn_list)
        return sorted(list(all_plmns))

    result: set[str] = set()
    for item in requested:
        item_lower = item.lower()
        if item_lower in KNOWN_PLMNS:
            result.update(KNOWN_PLMNS[item_lower])
        elif item.isdigit() and 5 <= len(item) <= 6:
            result.add(item)
        else:
            print(f"[!] Warning: Unknown PLMN or preset '{item}', ignoring.", file=sys.stderr)
    return sorted(list(result))


def build_operator_preferences(
    custom_name: str,
    plmn_list: List[str],
    show_carrier_name: bool = True,
    allow_roaming: bool = True,
) -> Dict[str, Any]:
    """
    Constructs the dictionary representing the operator preferences expected
    by CommCenter's CarrierSettingsInterface (BundleType = 5 / Operator Bundle).
    """
    # 1. Construct InterCarrierRoamingDisplayNames dictionary
    #    CommCenter checks this table matching current registered MCC+MNC
    roaming_dict: Dict[str, str] = {plmn: custom_name for plmn in plmn_list}

    prefs: Dict[str, Any] = {
        "CarrierName": custom_name,
        "ShowCarrierName": show_carrier_name,
        "ShowVirtualNetworkOperator": False,
        "InterCarrierRoamingDisplayNames": roaming_dict,
        "AllowEDGE": True,
        "AllowGPRS": True,
        "ShowDataRoaming": True,
    }

    if allow_roaming:
        prefs["AllowNationalRoaming"] = True
        prefs["AllowInternationalRoaming"] = True

    return prefs


def build_commcenter_bundle_preference(
    carrier_bundle_identifier: str = "com.apple.carrier",
    bundle_version: str = "1.0",
) -> Dict[str, Any]:
    """
    Constructs com.apple.commcenter.carrier_bundle.plist preferences.
    """
    return {
        "CarrierBundleVersion": bundle_version,
        "CarrierBundleIdentifier": carrier_bundle_identifier,
        "LastCarrierBundleUpdateCheck": 1785996866.0,
    }


def save_preferences_bundle(
    custom_name: str,
    output_dir: Path,
    slot: int = 1,
    plmns: Optional[List[str]] = None,
    home_domain_format: bool = False,
) -> List[Path]:
    """
    Generates and outputs operator plist preference files.
    If home_domain_format is True, creates the folder layout:
      HomeDomain/Library/Preferences/<domain>.plist
    """
    resolved_plmns = expand_plmns(plmns)
    prefs_dict = build_operator_preferences(custom_name, resolved_plmns)
    binary_data = plistlib.dumps(prefs_dict, fmt=plistlib.FMT_BINARY)
    xml_data = plistlib.dumps(prefs_dict, fmt=plistlib.FMT_XML)

    target_root = output_dir / "Library" / "Preferences" if home_domain_format else output_dir
    target_root.mkdir(parents=True, exist_ok=True)

    domains = [
        f"com.apple.operator_{slot}.merged.plist",
        f"com.apple.operator_{slot}.plist",
        f"com.apple.carrier_{slot}.merged.plist",
    ]

    written_paths: List[Path] = []
    for domain in domains:
        dest_bin = target_root / domain
        dest_bin.write_bytes(binary_data)
        written_paths.append(dest_bin)

        # Also output XML version for inspection
        dest_xml = target_root / f"{domain}.xml"
        dest_xml.write_bytes(xml_data)

    # Also generate the commcenter carrier bundle preference
    cc_bundle = build_commcenter_bundle_preference()
    cc_path = target_root / "com.apple.commcenter.carrier_bundle.plist"
    cc_path.write_bytes(plistlib.dumps(cc_bundle, fmt=plistlib.FMT_BINARY))
    written_paths.append(cc_path)

    return written_paths


def inspect_preference_file(path: Path) -> None:
    """Inspects and dumps preference plist contents."""
    if not path.is_file():
        print(f"Error: File not found: {path}", file=sys.stderr)
        sys.exit(1)

    data = path.read_bytes()
    try:
        content = plistlib.loads(data)
    except Exception as e:
        print(f"Error decoding plist {path}: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"\n[+] Inspected Preference Plist: {path} ({len(data)} bytes)")
    print(f"    CarrierName: {content.get('CarrierName', '(not set)')}")
    print(f"    ShowCarrierName: {content.get('ShowCarrierName', '(not set)')}")
    roaming = content.get("InterCarrierRoamingDisplayNames", {})
    print(f"    InterCarrierRoamingDisplayNames entries: {len(roaming)}")
    if roaming:
        print("    Sample Mappings:")
        for idx, (plmn, name) in enumerate(roaming.items()):
            if idx >= 10:
                print(f"      ... and {len(roaming) - 10} more PLMN mappings.")
                break
            print(f"      PLMN [{plmn}] -> '{name}'")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="iOS 27 Upstream CommCenter Preference & PLMN Mapping Builder"
    )
    parser.add_argument(
        "-c", "--custom-name",
        type=str,
        help="Custom carrier name to inject into CommCenter PLMN mapping"
    )
    parser.add_argument(
        "--slot",
        type=int,
        choices=[1, 2],
        default=1,
        help="SIM card slot (1 for Primary SIM, 2 for Secondary SIM, default: 1)"
    )
    parser.add_argument(
        "-p", "--plmn",
        action="append",
        help="Target PLMN (e.g. '46001', '46000') or carrier preset ('china_unicom', 'china_mobile', 'china_telecom', 'all')"
    )
    parser.add_argument(
        "-o", "--output-dir",
        type=Path,
        default=Path("build/preferences"),
        help="Directory to output generated preference plist files"
    )
    parser.add_argument(
        "--home-domain",
        action="store_true",
        help="Format output for MobileBackup2 HomeDomain (creates Library/Preferences/ structure)"
    )
    parser.add_argument(
        "-i", "--inspect",
        type=Path,
        help="Inspect and print details of an existing preference plist file"
    )
    parser.add_argument(
        "--list-presets",
        action="store_true",
        help="List available carrier PLMN presets"
    )

    args = parser.parse_args()

    if args.list_presets:
        print("Available Carrier PLMN Presets:")
        for name, plmns in KNOWN_PLMNS.items():
            print(f"  - {name:15}: {', '.join(plmns)}")
        return 0

    if args.inspect:
        inspect_preference_file(args.inspect)
        return 0

    if not args.custom_name:
        parser.error("The -c / --custom-name argument is required when generating preferences.")

    print(f"[*] Building Upstream CommCenter Preferences...")
    print(f"    Custom Name: '{args.custom_name}'")
    print(f"    SIM Slot:    {args.slot}")

    paths = save_preferences_bundle(
        custom_name=args.custom_name,
        output_dir=args.output_dir,
        slot=args.slot,
        plmns=args.plmn,
        home_domain_format=args.home_domain,
    )

    print(f"[✓] Generated {len(paths)} preference files in '{args.output_dir}':")
    for p in paths:
        print(f"    -> {p} ({p.stat().st_size} bytes)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
