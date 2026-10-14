"""Display metrics and width calculation for iOS status bar & Dynamic Island.

Provides terminal and UI width heuristics to detect whether custom carrier strings
will overflow or be truncated on modern Dynamic Island and classic notch devices.
"""

from __future__ import annotations

import unicodedata
from typing import NamedTuple


class DisplayWidthResult(NamedTuple):
    text: str
    display_width: int
    recommended_max: int
    is_overflow_risk: bool
    warning_message: str | None


def get_visual_width(text: str) -> int:
    """Calculate the approximate monospace rendering columns of a string.

    Wide characters (CJK, full-width), Apple Private Use glyphs ( \uF8FF),
    and common emojis count as 2 units; ASCII and half-width characters count as 1 unit.
    """
    if not text:
        return 0
    width = 0
    for char in text:
        # Check Apple logo / private use area icon
        if ord(char) in (0xF8FF, 0x2605):  #  or ★
            width += 2
            continue
        eaw = unicodedata.east_asian_width(char)
        if eaw in ("W", "F"):
            width += 2
        elif unicodedata.category(char) in ("So", "Sk"):
            width += 2
        else:
            width += 1
    return width


DYNAMIC_ISLAND_SINGLE_SIM_SAFE_WIDTH = 12
DYNAMIC_ISLAND_DUAL_SIM_SAFE_WIDTH = 8
CLASSIC_NOTCH_SAFE_WIDTH = 18


def check_dynamic_island_overflow(
    carrier_text: str | None,
    badge: str | None = None,
    is_dual_sim: bool = False,
    is_dynamic_island: bool = True,
) -> DisplayWidthResult:
    """Evaluate whether the given carrier string risks truncation on iOS lockscreen."""
    if not carrier_text:
        return DisplayWidthResult(
            text="",
            display_width=0,
            recommended_max=DYNAMIC_ISLAND_SINGLE_SIM_SAFE_WIDTH,
            is_overflow_risk=False,
            warning_message=None,
        )

    full_text = f"[{badge}] {carrier_text}" if badge else carrier_text
    width = get_visual_width(full_text)

    if is_dynamic_island:
        max_safe = DYNAMIC_ISLAND_DUAL_SIM_SAFE_WIDTH if is_dual_sim else DYNAMIC_ISLAND_SINGLE_SIM_SAFE_WIDTH
    else:
        max_safe = CLASSIC_NOTCH_SAFE_WIDTH

    if width > max_safe:
        msg = (
            f"Visual width of '{full_text}' is {width} units (recommended max: {max_safe} for "
            f"{'Dynamic Island' if is_dynamic_island else 'Classic Notch'}). "
            f"Note: Text will display in full in Control Center, but may truncate or ticker on Lock Screen."
        )
        return DisplayWidthResult(
            text=full_text,
            display_width=width,
            recommended_max=max_safe,
            is_overflow_risk=True,
            warning_message=msg,
        )

    return DisplayWidthResult(
        text=full_text,
        display_width=width,
        recommended_max=max_safe,
        is_overflow_risk=False,
        warning_message=None,
    )
