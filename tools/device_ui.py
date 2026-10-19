#!/usr/bin/env python3
"""Device UI automation helper for the iOS 27 carrier research.

Thin wrapper over pymobiledevice3's CoreDevice HID / screen-capture services.
Coordinates are screen-normalised (0..65535) so they are resolution independent.

Typical verification loop:
    python3 tools/device_ui.py screenshot before.png
    python3 tools/device_ui.py open-cc && python3 tools/device_ui.py screenshot cc.png

Requires an unlocked device for touch dispatch.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PMD = ROOT / ".venv" / "bin" / "pymobiledevice3"

#: Normalised anchors for an iPhone-class screen.
CC_OPEN_FROM = (58500, 1500)     # top-right edge (battery area)
CC_OPEN_TO = (58500, 26000)
CC_CLOSE_FROM = (50000, 60000)   # swipe up from the lower area
CC_CLOSE_TO = (50000, 15000)


def run(*arguments: str, timeout: int = 120) -> int:
    command = [str(PMD), "developer", "core-device", *arguments, "--userspace"]
    completed = subprocess.run(command, check=False, text=True, capture_output=True, timeout=timeout)
    if completed.stdout.strip():
        print(completed.stdout.strip())
    if completed.returncode != 0 and completed.stderr.strip():
        print(completed.stderr.strip(), file=sys.stderr)
    return completed.returncode


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    screenshot = sub.add_parser("screenshot")
    screenshot.add_argument("output", type=Path)

    swipe = sub.add_parser("swipe")
    swipe.add_argument("x1", type=int)
    swipe.add_argument("y1", type=int)
    swipe.add_argument("x2", type=int)
    swipe.add_argument("y2", type=int)
    swipe.add_argument("--steps", type=int, default=25)
    swipe.add_argument("--duration", type=float, default=0.35)

    tap = sub.add_parser("tap")
    tap.add_argument("x", type=int)
    tap.add_argument("y", type=int)

    sub.add_parser("open-cc")
    sub.add_parser("close-cc")

    args = parser.parse_args()

    if args.command == "screenshot":
        args.output.parent.mkdir(parents=True, exist_ok=True)
        return run("screen-capture", "screenshot", str(args.output))
    if args.command == "swipe":
        return run(
            "universal-hid-service", "swipe",
            str(args.x1), str(args.y1), str(args.x2), str(args.y2),
            "--steps", str(args.steps), "--duration", str(args.duration),
        )
    if args.command == "tap":
        return run("universal-hid-service", "tap", str(args.x), str(args.y))
    if args.command == "open-cc":
        return run(
            "universal-hid-service", "drag",
            str(CC_OPEN_FROM[0]), str(CC_OPEN_FROM[1]),
            str(CC_OPEN_TO[0]), str(CC_OPEN_TO[1]),
            "--steps", "20", "--duration", "0.4",
        )
    if args.command == "close-cc":
        return run(
            "universal-hid-service", "drag",
            str(CC_CLOSE_FROM[0]), str(CC_CLOSE_FROM[1]),
            str(CC_CLOSE_TO[0]), str(CC_CLOSE_TO[1]),
            "--steps", "20", "--duration", "0.3",
        )
    return 2


if __name__ == "__main__":
    sys.exit(main())
