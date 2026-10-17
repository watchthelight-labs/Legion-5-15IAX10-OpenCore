# <wtl> project: legion-5-15iax10-opencore | file: scripts/dsdt_patches.py | author: watchthelight </wtl>
"""DSDT byte patches for OpenCore ACPI > Patch, and a tester that applies them to a dumped DSDT.

Used with ACPICA 20160930 acpiexec (the ACPICA version inside macOS AppleACPIPlatform) to check
that the DSDT loads before a patch goes onto the USB stick.

  python3 scripts/dsdt_patches.py DSDT.aml DSDT-patched.aml
Patches are (comment, find hex, replace hex); each find must occur exactly once.
The entries in EFI/OC/config.plist come from opencore_entries() below.
"""
import sys

PATCHES = [
    # Device (PC02) (the PCH PCIe root, _UID 2, present in Windows) sits inside If (PCHA != Zero).
    # ACPICA 20160930 defers module-level If blocks until after the table load, so every
    # Scope (_SB.PC02...) later in the DSDT fails and the whole DSDT is rejected (I-028).
    # Turn the If into Scope (\_SB) of the same length (5-byte name + two Noop opcodes).
    ("If (PCHA != Zero) { Device (PC02) } -> Scope (_SB)",
     "A04E2F92935043484100" "5B82432F50433032", "104E2F5C5F53425FA3A3" "5B82432F50433032"),
    # Same pattern at table root: If (PCHA != Zero) { Name (MNVB) ... Scope (_SB.PC02) { RP01.. } }.
    # Turn it into Scope (\) (root = 5C 00, then five Noops).
    ("If (PCHA != Zero) { MNVB, Scope (_SB.PC02) } -> Scope (Root)",
     "A08D6B1692935043484100" "084D4E5642", "108D6B165C00A3A3A3A3A3" "084D4E5642"),
    # Scope (PC02.I2C0) { Device (TCON) }: I2C0 is External here (an SSDT defines it, loaded after
    # the DSDT). Retarget to \_SB.PC00.LPCB (same depth, exists at load); TCON is unused by macOS.
    ("Scope (PC02.I2C0) -> Scope (PC00.LPCB)", "10400D2E5043303249324330", "10400D2E504330304C504342"),
    # ACPICA 20160930 never runs a bare Store in a Device body, so these Names stay 0 in macOS.
    # SBRG = 0 sends every sideband (PCR) access, including XHCI._PS0/_PS3, to low RAM, and
    # PU2C = 0 skips every If (One <= PU2C) { Device (HSxx) } in RHUB, so the USB ports
    # (keyboard on HS05) get no ACPI nodes. Swap Name + Store for a Method that reads the source at
    # call time; ^^ because a Method is its own scope. Padding Noops sit after the Return.
    ("PC00.SBSC: SBRG = \\SBRG -> Method (SBRG)",
     "085342524700705C5342524753425247", "140F5342524700A45C53425247A3A3A3"),
    ("PC02.SBPC: SBRG = ^SBRG -> Method (SBRG)",
     "085342524700705E5342524753425247", "140F5342524700A45E5E53425247A3A3"),
    ("PC02.XHCI: DUWS/PU2C/PU3C stores -> Methods",
     "08445557530008505532430008505533430008414857410108505049440A4F"
     "705C4455575344555753705E5055324350553243705E5055334350553343",
     "08414857410108505049440A4F140C4455575300A45C44555753"
     "140D5055324300A45E5E5055324314145055334300A45E5E50553343A3A3A3A3A3A3A3"),
]


# SSDT patches: (comment, find hex, replace hex), each find unique across all firmware SSDTs.
SSDT_PATCHES = [
    # Lenovo's USB table (SSDT-22, OEM CB-01) marks HS05, the port of the internal ITE keyboard
    # (048D:C195), as not connectable: _UPC = GUPC (Zero, 0xFF). Windows ignores that; macOS turns
    # the port off. N-17 made the table load, so the keyboard port went dark. Make it GUPC (One, 0xFF):
    # connectable, internal.
    ("SSDT-22 HS05 _UPC: not connectable -> connectable internal",
     "48533035140E5F55504300A447555043000AFF", "48533035140E5F55504300A447555043010AFF"),
    # N-58 (I-045): the same GUPC (Zero, 0xFF) hides three more ports that Windows uses. HS14 carries the MT7925
    # Bluetooth (USB 0489:E111, Windows evidence N-23), HS11 the Chicony webcam, HS02 a USB-A port. Each find occurs
    # once in SSDT-22 (offsets 0xB1D, 0xA5B, 0x819 in the N-13 dump). 13 ports on PC02.XHCI then, under the 15 limit.
    ("SSDT-22 HS14 _UPC (Bluetooth 0489:E111): not connectable -> connectable internal",
     "48533134140E5F55504300A447555043000AFF", "48533134140E5F55504300A447555043010AFF"),
    ("SSDT-22 HS11 _UPC (webcam): not connectable -> connectable internal",
     "48533131140E5F55504300A447555043000AFF", "48533131140E5F55504300A447555043010AFF"),
    ("SSDT-22 HS02 _UPC (USB-A port): not connectable -> connectable internal",
     "48533032140E5F55504300A447555043000AFF", "48533032140E5F55504300A447555043010AFF"),
]


# Shutdown-restart fix (ACPI/SSDT-FIXSHUTDOWN.dsl), applied from N-92 through opencore_entries():
# rename the firmware Method (_PTS, 1) to ZPTS so the SSDT's _PTS wraps it. Find = name + ArgCount byte,
# occurs once in the N-13 DSDT (offset 0x4AECC, after the 14 4C 25 Method header). The ADBG "_PTS=" strings
# are not hit because they are not followed by 0x01.
FIXSHUTDOWN_PATCHES = [
    ("Method (_PTS, 1) -> ZPTS (SSDT-FIXSHUTDOWN wraps it)", "5F50545301", "5A50545301"),
]


def opencore_entries():
    """PATCHES and SSDT_PATCHES as OpenCore ACPI > Patch dicts (each Find unique, so Count 1)."""
    tables = [(PATCHES, b"DSDT"), (SSDT_PATCHES, b"SSDT"), (FIXSHUTDOWN_PATCHES, b"DSDT")]   # N-92 adds the _PTS rename
    return [{"Base": "", "BaseSkip": 0, "Comment": c, "Count": 1, "Enabled": True,
             "Find": bytes.fromhex(f), "Limit": 0, "Mask": b"", "OemTableId": b"",
             "Replace": bytes.fromhex(r), "ReplaceMask": b"", "Skip": 0, "TableLength": 0,
             "TableSignature": sig} for patches, sig in tables for c, f, r in patches]


def main():
    d = bytearray(open(sys.argv[1], "rb").read())
    for comment, f, r in PATCHES:
        fb, rb = bytes.fromhex(f), bytes.fromhex(r)
        assert len(fb) == len(rb), comment
        n = d.count(fb)
        if n != 1:
            raise SystemExit(f"{comment}: find occurs {n} times")
        i = d.find(fb)
        d[i:i + len(fb)] = rb
        print(f"{comment}: patched at {i:#x}")
    d[9] = 0
    d[9] = (-sum(d)) & 0xFF
    open(sys.argv[2], "wb").write(d)


if __name__ == "__main__":
    main()
