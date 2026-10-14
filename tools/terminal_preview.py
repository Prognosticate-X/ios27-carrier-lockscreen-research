"""Terminal ASCII & ANSI visual previewer for iOS Lock Screen & Control Center."""

from __future__ import annotations

from display_metrics import get_visual_width


def render_terminal_preview(
    carrier: str,
    badge: str | None = None,
    bars: int = 4,
    secondary_carrier: str | None = None,
    secondary_badge: str | None = None,
    secondary_bars: int = 4,
    footnote: str | None = None,
    is_dynamic_island: bool = True,
) -> str:
    """Render an ANSI-colored preview box mimicking iPhone Lock Screen and Control Center."""
    bar_symbol = "●" * bars + "○" * (4 - bars)
    sec_bar_symbol = "●" * secondary_bars + "○" * (4 - secondary_bars)

    p_badge_str = f"[{badge}] " if badge else ""
    s_badge_str = f"[{secondary_badge}] " if secondary_badge else ""

    island_art = "[  Dynamic Island  ]" if is_dynamic_island else "[   Classic Notch   ]"

    lines = [
        "",
        "┌────────────────────────────────────────────────────────┐",
        f"│ 14:30           {island_art}          5G  {bar_symbol} │",
        "│                                                        │",
        "│   📱 [Lock Screen Preview]                             │",
    ]

    p_full = f"{p_badge_str}{carrier} {bar_symbol}"
    lines.append(f"│   Primary:   \033[1;32m{p_full}\033[0m")
    if secondary_carrier:
        s_full = f"{s_badge_str}{secondary_carrier} {sec_bar_symbol}"
        lines.append(f"│   Secondary: \033[1;36m{s_full}\033[0m")

    if footnote:
        lines.append("│                                                        │")
        lines.append(f"│   📝 Footnote: \033[1;33m{footnote}\033[0m")

    lines.extend([
        "│                                                        │",
        "│                     ───── (Home Bar) ─────             │",
        "└────────────────────────────────────────────────────────┘",
        "",
    ])

    return "\n".join(lines)
