/*
 * <wtl> project: legion-hackintosh | file: native/acpi/SSDT-RTCAWAC.dsl | author: watchthelight </wtl>
 * Legion 5 15IAX10: the DSDT has an AWAC clock and a legacy PNP0B00 RTC, both gated by STAS
 * (AWAC active when STAS == 0, RTC active when STAS == 1). Under Darwin set STAS = 1 so AWAC
 * turns off and the DSDT RTC turns on (N-23 ioreg: AppleRTC binds to it). Same approach as
 * OpenCorePkg SSDT-AWAC-DISABLE.dsl. The extra RTC0 used up to N-23 duplicated it (I-030).
 */
DefinitionBlock ("", "SSDT", 2, "LEGION", "RTCAWAC", 0x00000000)
{
    External (STAS, IntObj)

    Scope (\)
    {
        Method (_INI, 0, NotSerialized)
        {
            If (_OSI ("Darwin"))
            {
                STAS = One
            }
        }
    }
}
