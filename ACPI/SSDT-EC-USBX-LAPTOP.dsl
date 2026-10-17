/*
 * <wtl> project: legion-hackintosh | file: native/acpi/SSDT-EC-USBX-LAPTOP.dsl | author: watchthelight </wtl>
 * Legion 5 15IAX10: fake "EC" device for macOS (the real controller is \_SB.PC00.LPCB.EC0
 * and stays untouched, as Dortania advises for laptops) plus USBX USB power properties.
 * Based on OpenCorePkg Docs/AcpiSamples/Source/SSDT-EC-USBX.dsl.
 */
DefinitionBlock ("", "SSDT", 2, "LEGION", "SsdtEC", 0x00001000)
{
    External (_SB_.PC00.LPCB, DeviceObj)

    Scope (\_SB.PC00.LPCB)
    {
        Device (EC)
        {
            Name (_HID, "ACID0001")
            Method (_STA, 0, NotSerialized)
            {
                If (_OSI ("Darwin"))
                {
                    Return (0x0F)
                }
                Else
                {
                    Return (Zero)
                }
            }
        }
    }

    Scope (\_SB)
    {
        Device (USBX)
        {
            Name (_ADR, Zero)
            Method (_DSM, 4, NotSerialized)
            {
                If ((Arg2 == Zero))
                {
                    Return (Buffer (One) { 0x03 })
                }

                Return (Package (0x08)
                {
                    "kUSBSleepPowerSupply", 0x13EC,
                    "kUSBSleepPortCurrentLimit", 0x0834,
                    "kUSBWakePowerSupply", 0x13EC,
                    "kUSBWakePortCurrentLimit", 0x0834
                })
            }

            Method (_STA, 0, NotSerialized)
            {
                If (_OSI ("Darwin"))
                {
                    Return (0x0F)
                }
                Else
                {
                    Return (Zero)
                }
            }
        }
    }
}
