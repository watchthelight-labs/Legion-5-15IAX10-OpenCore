/*
 * <wtl> project: legion-hackintosh | file: native/acpi/SSDT-FIXSHUTDOWN.dsl | author: watchthelight </wtl>
 * Legion 5 15IAX10: Apple menu Shut Down comes back as a restart (N-90 -> N-91, 2026-10-16 20:30).
 * Known Hackintosh cause on Intel laptops: an xHCI controller keeps PME_En set when the platform enters
 * S5, signals PME and the PCH powers the machine straight back on. macOS does not clear it, Windows and
 * Linux do. Fix from Dortania OpenCore-Post-Install usb/misc/shutdown.md (RehabMan FixShutdown-USB-SSDT),
 * extended to both live xHCI controllers (ioreg: \_SB.PC02.XHCI@14 PCH, \_SB.PC00.TXHC@D TCSS).
 * PMEE = PCI PMCSR bit 8 (config 0x75 bit 0), defined in the DSDT (PC02.XHCI) and in SSDT TcssSsdt (TXHC).
 *
 * Needs the OpenCore ACPI > Patch rename of the DSDT Method (_PTS, 1) to ZPTS
 * (scripts/acpi/dsdt_patches.py FIXSHUTDOWN_PATCHES). The firmware _PTS still runs first, unchanged.
 * Darwin only and S5 only: other OSes and the (unused) S3/S4 paths see the original behaviour.
 * Rollback: disable this table and the ZPTS patch in config.plist (both are needed together; the
 * rename alone leaves the OS without a _PTS, the table alone fails to load on the missing ZPTS).
 */
DefinitionBlock ("", "SSDT", 2, "LEGION", "FIXSHUT", 0x00000000)
{
    External (ZPTS, MethodObj)                      // 1 Arguments, the renamed firmware _PTS
    External (_SB_.PC02.XHCI.PMEE, FieldUnitObj)
    External (_SB_.PC00.TXHC, DeviceObj)
    External (_SB_.PC00.TXHC._STA, MethodObj)     // 0 Arguments
    External (_SB_.PC00.TXHC.PMEE, FieldUnitObj)

    Method (_PTS, 1, NotSerialized)  // _PTS: Prepare To Sleep
    {
        ZPTS (Arg0)
        If (_OSI ("Darwin"))
        {
            If ((0x05 == Arg0))
            {
                If (CondRefOf (\_SB.PC02.XHCI.PMEE))
                {
                    \_SB.PC02.XHCI.PMEE = Zero
                }

                If (CondRefOf (\_SB.PC00.TXHC.PMEE))
                {
                    If ((\_SB.PC00.TXHC._STA () & 0x01))
                    {
                        \_SB.PC00.TXHC.PMEE = Zero
                    }
                }
            }
        }
    }
}
