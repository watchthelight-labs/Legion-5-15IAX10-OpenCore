# Changelog

## 2026-10-27

- `SetApfsTrimTimeout` is 0 now (was -1). APFS no longer trims the free space at mount: the boot scan takes 0 s instead of about 20 s, and the login window comes up 41 s after the root mount instead of 58 s. On macOS 12 and later only 0 (skip) or -1 (default) are honoured.
- README status and kext table brought up to the running versions: Wi-Fi menu through MtkWlan 0.12.1 and MtkWlanNative 0.4.13, MtkBt 0.2.4, LegionCpuProbe 1.1.0, LegionCpuPower 0.4.1, audio through AppleALC `alcid=18`.

## 2026-10-17

- First published state: the EFI and config as they boot macOS Tahoe 26.7.1 and Sequoia 15.8.1 on the Legion 5 15IAX10 (the config that ran boot N-94 of my notebook on 2026-10-17). Includes the shutdown fix (SSDT-FIXSHUTDOWN plus the `_PTS` rename), the four `_UPC` port fixes, the MADT rewrite, the DSDT scope patches, and the kext list for all the drivers in this org.
