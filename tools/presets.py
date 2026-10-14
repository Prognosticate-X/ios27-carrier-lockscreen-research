"""Preset management for iOS 27 Carrier & Status Bar configurations.

Supports saving, loading, listing, and validating named carrier presets.
Stored by default in ~/.config/ios27-carrier/presets.json.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

DEFAULT_PRESET_DIR = Path.home() / ".config" / "ios27-carrier"
DEFAULT_PRESET_FILE = DEFAULT_PRESET_DIR / "presets.json"

BUILTIN_PRESETS: Dict[str, Dict[str, Any]] = {
    "cmcc-5g": {
        "description": "中国移动 5G (单卡)",
        "carrier": "中国移动 5G",
        "bars": 4,
        "type": "5g",
        "badge": None,
    },
    "cucc-5g": {
        "description": "中国联通 5G (单卡)",
        "carrier": "中国联通 5G",
        "bars": 4,
        "type": "5g",
        "badge": None,
    },
    "ctcc-5g": {
        "description": "中国电信 5G (单卡)",
        "carrier": "中国电信 5G",
        "bars": 4,
        "type": "5g",
        "badge": None,
    },
    "cbn-5g": {
        "description": "中国广电 5G (单卡)",
        "carrier": "中国广电 5G",
        "bars": 4,
        "type": "5g",
        "badge": None,
    },
    "dual-cmcc-cucc": {
        "description": "移动(主卡) + 联通(副卡) 双卡全满格",
        "carrier": "中国移动 5G",
        "bars": 4,
        "type": "5g",
        "badge": "P",
        "secondary_carrier": "中国联通 5G",
        "secondary_bars": 4,
        "secondary_type": "5g",
        "secondary_badge": "S",
    },
    "apple-vip": {
        "description": " Apple VIP 5G+ 超宽频",
        "carrier": " Apple 5G+",
        "bars": 4,
        "type": "5g+",
        "badge": "★",
    },
}


def ensure_preset_file(path: Path = DEFAULT_PRESET_FILE) -> Path:
    if not path.is_file():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(BUILTIN_PRESETS, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def load_all_presets(path: Path = DEFAULT_PRESET_FILE) -> Dict[str, Dict[str, Any]]:
    ensure_preset_file(path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return BUILTIN_PRESETS.copy()


def get_preset(name: str, path: Path = DEFAULT_PRESET_FILE) -> Optional[Dict[str, Any]]:
    all_presets = load_all_presets(path)
    return all_presets.get(name)


def save_preset(name: str, config: Dict[str, Any], path: Path = DEFAULT_PRESET_FILE) -> None:
    all_presets = load_all_presets(path)
    all_presets[name] = config
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(all_presets, indent=2, ensure_ascii=False), encoding="utf-8")


def list_presets_formatted(path: Path = DEFAULT_PRESET_FILE) -> str:
    presets = load_all_presets(path)
    lines = ["Available Carrier Presets:", "=" * 40]
    for name, item in presets.items():
        desc = item.get("description", "")
        carrier = item.get("carrier", "N/A")
        sec = item.get("secondary_carrier")
        sec_str = f" | Dual: {sec}" if sec else ""
        lines.append(f"  • {name:<18} : {desc} [{carrier}{sec_str}]")
    return "\n".join(lines)
