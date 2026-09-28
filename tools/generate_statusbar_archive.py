#!/usr/bin/env python3
"""
generate_statusbar_archive.py
Generates iOS 27 compatible StatusBarOverrides.archive binary property list
for carrier name and cellular status bar customizations.
"""

import sys
import plistlib

def build_status_bar_archive(carrier_name: str, signal_bars: int = 4, network_type: int = 10) -> bytes:
    """
    Constructs an NSKeyedArchiver bplist containing:
      - _SBSystemStatusStatusBarOverridesArchiveRecord
      - STStatusBarData
      - STStatusBarDataCellularEntry
    """
    objects = [
        "$null",  # 0
        {         # 1: _SBSystemStatusStatusBarOverridesArchiveRecord
            "$class": plistlib.UID(9),
            "statusBarData": plistlib.UID(2),
            "suppressedBackgroundActivityIdentifiers": plistlib.UID(7),
        },
        {         # 2: STStatusBarData
            "$class": plistlib.UID(6),
            "cellularEntry": plistlib.UID(3),
        },
        {         # 3: STStatusBarDataCellularEntry
            "$class": plistlib.UID(5),
            "badgeString": plistlib.UID(0),
            "callForwardingEnabled": False,
            "crossfadeString": plistlib.UID(4),
            "displayRawValue": 0,
            "displayValue": signal_bars,
            "enabled": True,
            "isBootstrapCellular": False,
            "lowDataModeActive": False,
            "numberSharingState": 0,
            "rawValue": 0,
            "showsSOSWhenDisabled": False,
            "sosAvailable": False,
            "status": 5,  # Connected
            "string": plistlib.UID(4),
            "suffixString": plistlib.UID(0),
            "type": network_type,  # 10 = 5G, 9 = LTE, etc.
            "wifiCallingEnabled": False,
        },
        carrier_name,  # 4
        {         # 5: Class metadata for STStatusBarDataCellularEntry
            "$classes": [
                "STStatusBarDataCellularEntry",
                "STStatusBarDataNetworkEntry",
                "STStatusBarDataIntegerEntry",
                "STStatusBarDataEntry",
                "NSObject",
            ],
            "$classname": "STStatusBarDataCellularEntry",
        },
        {         # 6: Class metadata for STStatusBarData
            "$classes": ["STStatusBarData", "NSObject"],
            "$classname": "STStatusBarData",
        },
        {         # 7: suppressedBackgroundActivityIdentifiers (empty NSSet)
            "$class": plistlib.UID(8),
            "NS.objects": [],
        },
        {         # 8: Class metadata for NSSet
            "$classes": ["NSSet", "NSObject"],
            "$classname": "NSSet",
        },
        {         # 9: Class metadata for _SBSystemStatusStatusBarOverridesArchiveRecord
            "$classes": [
                "_SBSystemStatusStatusBarOverridesArchiveRecord",
                "NSObject",
            ],
            "$classname": "_SBSystemStatusStatusBarOverridesArchiveRecord",
        },
    ]

    plist_dict = {
        "$archiver": "NSKeyedArchiver",
        "$version": 100000,
        "$top": {"root": plistlib.UID(1)},
        "$objects": objects,
    }

    return plistlib.dumps(plist_dict, fmt=plistlib.FMT_BINARY)


def main():
    if len(sys.argv) < 2:
        print("Usage: generate_statusbar_archive.py <carrier_name> [output_file]")
        sys.exit(1)

    carrier_name = sys.argv[1]
    out_path = sys.argv[2] if len(sys.argv) > 2 else "StatusBarOverrides.archive"

    archive_data = build_status_bar_archive(carrier_name)
    with open(out_path, "wb") as f:
        f.write(archive_data)

    print(f"Successfully generated '{out_path}' for carrier '{carrier_name}' ({len(archive_data)} bytes)")


if __name__ == "__main__":
    main()
