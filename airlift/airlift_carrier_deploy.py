#!/usr/bin/env python3
"""Compatibility wrapper for the maintained tools/airlift_carrier_deploy.py.

The implementation used to be duplicated byte-for-byte in this directory. That
made safety fixes easy to miss: an import from airlift/ could load an unfixed
copy with an empty PRIMARY_PHONE_BLOCKLIST. Keep this file as a wrapper only;
all behavior lives in tools/.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent.parent / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

_SPEC = importlib.util.spec_from_file_location(
    "_ios27_tools_airlift_carrier_deploy",
    TOOLS / "airlift_carrier_deploy.py",
)
if _SPEC is None or _SPEC.loader is None:
    raise ImportError("could not load tools/airlift_carrier_deploy.py")
_MODULE = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = _MODULE
_SPEC.loader.exec_module(_MODULE)

for _name in dir(_MODULE):
    if not _name.startswith("_"):
        globals().setdefault(_name, getattr(_MODULE, _name))
main = _MODULE.main

if __name__ == "__main__":
    raise SystemExit(main())
