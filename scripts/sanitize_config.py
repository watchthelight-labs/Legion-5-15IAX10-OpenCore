#!/usr/bin/env python3
# <wtl> project: legion-5-15iax10-opencore | file: scripts/sanitize_config.py | author: watchthelight </wtl>
"""Copy an OpenCore config.plist with the machine identity replaced by OpenCore's sample placeholders.

  python3 scripts/sanitize_config.py <live config.plist> <EFI/OC/config.plist>

Replaces PlatformInfo > Generic SystemSerialNumber, MLB, SystemUUID and ROM. Everything else is
copied as it is. Refuses to write if any of the four still looks like a real value afterwards.
"""
import plistlib
import sys

PLACEHOLDERS = {
    "SystemSerialNumber": "W00000000001",
    "MLB": "M0000000000000001",
    "SystemUUID": "00000000-0000-0000-0000-000000000000",
    "ROM": bytes.fromhex("112233445566"),
}


def main(src, dst):
    with open(src, "rb") as f:
        c = plistlib.load(f)
    g = c["PlatformInfo"]["Generic"]
    for key, value in PLACEHOLDERS.items():
        g[key] = value
    for key, value in PLACEHOLDERS.items():
        if g[key] != value:
            sys.exit(f"{key} still differs from the placeholder")
    with open(dst, "wb") as f:
        plistlib.dump(c, f)
    print(f"wrote {dst}: identity replaced by placeholders (fill in your own with GenSMBIOS before booting)")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
