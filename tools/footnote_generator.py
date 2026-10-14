"""iOS Lock Screen Footnote Configuration Profile Synthesizer.

Generates signed or unsigned .mobileconfig profiles for custom lock screen footnote text
using Apple's official com.apple.shareddeviceconfiguration payload specification.
"""

from __future__ import annotations

import plistlib
import uuid
from pathlib import Path


def generate_footnote_profile(
    footnote_text: str,
    organization: str = "Prognosticate-X",
    display_name: str = "Lock Screen Footnote",
) -> bytes:
    """Generate a valid Apple configuration profile with LockScreenFootnote."""
    payload_uuid = str(uuid.uuid4()).upper()
    profile_uuid = str(uuid.uuid4()).upper()

    profile_dict = {
        "PayloadContent": [
            {
                "PayloadIdentifier": f"com.{organization.lower().replace(' ', '')}.footnote",
                "PayloadType": "com.apple.shareddeviceconfiguration",
                "PayloadUUID": payload_uuid,
                "PayloadVersion": 1,
                "LockScreenFootnote": footnote_text,
            }
        ],
        "PayloadDisplayName": display_name,
        "PayloadIdentifier": f"com.{organization.lower().replace(' ', '')}.profile",
        "PayloadOrganization": organization,
        "PayloadType": "Configuration",
        "PayloadUUID": profile_uuid,
        "PayloadVersion": 1,
        "PayloadRemovalDisallowed": False,
    }

    return plistlib.dumps(profile_dict, fmt=plistlib.FMT_XML)


def save_footnote_profile(
    footnote_text: str,
    output_path: Path | str,
    organization: str = "Prognosticate-X",
) -> Path:
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = generate_footnote_profile(footnote_text, organization=organization)
    out.write_bytes(payload)
    return out
