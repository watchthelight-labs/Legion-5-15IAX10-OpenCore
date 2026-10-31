# How this EFI works

This is the reasoning behind `EFI/OC/config.plist`, written so I can answer "why is this set" for any line of it. Everything below is what the published config does. Where the README says something different, this file follows the config and says so.

## Boot chain

The laptop has two EFI partitions on the internal NVMe. The first one (200 MiB) belongs to Windows and holds Windows Boot Manager plus a custom shim; OpenCore never touches it. The second is a separate FAT32 partition made for OpenCore, and this repository is its `EFI` folder.

1. The Lenovo firmware starts whatever is first in its boot order. `Misc > Boot > LauncherOption Full` makes OpenCore add its own firmware boot entry and keep it first, so that is OpenCore (`EFI/BOOT/BOOTx64.efi` then `EFI/OC/OpenCore.efi`).
2. OpenCore loads its drivers from `UEFI > Drivers`: `OpenRuntime.efi` (needed by the Booter quirks and the NVRAM handling), `OpenHfsPlus.efi` (to read the HFS+ installer and recovery volumes), `ResetNvramEntry.efi` and `ToggleSipEntry.efi` (two picker entries), and `LegionCbmrFix.efi`. The last one is from this org: the Lenovo BIOS loads Microsoft's cloud recovery driver (`cbmr_driver.efi`) at 0x180000000 on every boot and macOS later panics on its pages, so the driver unloads that image and reserves its range before macOS starts.
3. With `ShowPicker false` and `Timeout 0` OpenCore boots the default entry (the one Startup Disk sets) straight away. Holding Option or Esc while it starts brings up the text picker (`PollAppleHotKeys true`, `PickerMode Builtin`).
4. boot.efi loads the kernel collection, OpenCore applies the kernel patches and kext injections described below, and ExitBootServices hands the machine to XNU.

Windows is started from the firmware menu (F12, Windows Boot Manager), never through OpenCore, because OpenCore would hand it the Mac SMBIOS.

A USB stick with a known-good copy of the same EFI is the rescue path: F12, pick the stick. The stick's copy differs in two places, `LauncherOption Disabled` (so booting from it does not register the stick in the firmware boot order) and `ShowPicker true` (so it always offers a choice).

## ACPI

### Tables added

| Table | What it does | Why |
|---|---|---|
| `SSDT-PLUG-ALT.aml` | OpenCorePkg's sample, unchanged: 64 `Processor` objects `CP00` to `CP3F` under `\_SB`, visible only to Darwin, with `plugin-type = 1` on `CP00` | Arrow Lake declares its CPUs as `Device (ACPI0007)`. macOS wants `Processor` objects, and the plugin type loads the XCPM power management plugin |
| `SSDT-EC-USBX-LAPTOP.aml` | a device named `EC` (`_HID "ACID0001"`) under `\_SB.PC00.LPCB`, plus `\_SB.USBX` with the four USB sleep and wake power values; both Darwin only | macOS expects a device called `EC`. The real controller is `EC0` and stays untouched, as Dortania advises for laptops; a fake one with a harmless ID satisfies the check without touching the real embedded controller |
| `SSDT-RTCAWAC.aml` | an `_INI` at the root that sets `STAS = 1` under Darwin | The DSDT has both an AWAC clock and a legacy `PNP0B00` RTC, gated by `STAS`. With 1, AWAC turns off and the DSDT's own RTC turns on, which `AppleRTC` can use. An earlier version added a second RTC device as well, which duplicated the DSDT one and gave wrong years |
| `APIC-legacy.aml` | a replacement MADT: 24 type-0 Local APIC entries, the IOAPIC and the two interrupt source overrides copied as they are, and one type-4 Local APIC NMI entry for all CPUs | see below |
| `SSDT-FIXSHUTDOWN.aml` | a new `_PTS` that calls the firmware one (renamed to `ZPTS`), then, under Darwin and only for S5, clears PME enable on both xHCI controllers (`\_SB.PC02.XHCI` and `\_SB.PC00.TXHC`) | Without it Apple menu Shut Down came back as a restart: a controller still had PME enabled at S5 and woke the machine straight up. macOS does not clear it, Windows and Linux do. The pattern is RehabMan's FixShutdown from Dortania's post-install guide, extended to both controllers |

`SSDT-FIXSHUTDOWN` and the `_PTS` rename only work as a pair. With the rename alone the OS has no `_PTS`; with the table alone it fails to load because `ZPTS` does not exist.

### The MADT rewrite

This was the first real wall. Every early boot stopped right after `EXITBS:START` with no kernel output at all, whatever Booter quirk I changed. The cause is in XNU: it counts CPUs only from MADT type-0 (Processor Local APIC) entries (`acpi_count_enabled_logical_processors` in `osfmk/i386/acpi.c`). This firmware writes only type-9 (x2APIC) entries, 48 of them, so XNU found zero CPUs and panicked in per-CPU setup before the console existed.

`scripts/x2apic_to_lapic.py` reads the firmware MADT and writes one type-0 entry for each enabled type-9 entry, in firmware order, with Processor ID = the x2APIC UID and APIC ID = the x2APIC ID (it refuses if an ID does not fit in a byte). The table header keeps the firmware's OEM IDs (`LENOVO`, `CB-01`). `ACPI > Delete` drops the firmware table by signature `APIC` and OEM table ID `CB-01`, and `ACPI > Add` puts the rewritten one in its place. The next boot ran about 10 seconds into the kernel and registered all 24 CPUs. If a BIOS update changes the MADT, the table has to be rebuilt from a new dump.

### The 11 patches

All of them come from `scripts/dsdt_patches.py`, which also applies them to a dumped DSDT so the result can be loaded in `acpiexec` before a boot. The ACPICA to test against is 20160930, the version inside macOS's `AppleACPIPlatform`. Each find string occurs exactly once, so every entry has `Count 1`, and each replacement has the same length as the original.

- **Two `If (PCHA != Zero)` blocks become scopes.** The PCH PCIe root `Device (PC02)` and a root-level block with `MNVB` and `Scope (_SB.PC02)` sit inside module-level `If` statements. ACPICA 20160930 runs those only after the table has loaded, so every later `Scope (_SB.PC02...)` failed and macOS rejected the whole DSDT. The symptom was a silent hang after a `\_SB.UBTC._CRS AE_NOT_FOUND` error. The patch turns each `If` into a `Scope` of the same length, padded with `Noop`.
- **`Scope (PC02.I2C0)` is retargeted to `PC00.LPCB`.** `I2C0` is defined in an SSDT that loads after the DSDT, so the scope did not resolve. The only thing inside it is `TCON`, which macOS does not use.
- **Three `Name` + `Store` pairs become methods.** The same old ACPICA never runs a bare `Store` in a `Device` body, so those names stayed 0 under macOS. `SBRG = 0` in `PC00.SBSC` and `PC02.SBPC` sent every sideband register access, including the xHCI `_PS0` and `_PS3`, to low RAM. `PU2C = 0` in `PC02.XHCI` skipped every `If (One <= PU2C) { Device (HSxx) }`, so the USB ports had no ACPI nodes. Each patch replaces the name with a method that returns the source value when it is called.
- **Four `_UPC` fixes in Lenovo's USB table (SSDT-22).** HS05 (the internal ITE keyboard), HS14 (MT7925 Bluetooth), HS11 (webcam) and HS02 (a USB-A port) return `GUPC (Zero, 0xFF)`: not connectable. Windows ignores that; macOS turns the port off. The patch changes the first argument to `One`. That makes 13 ports on `PC02.XHCI`, under the 15-port limit, so no port limit patch is needed.
- **`_PTS` to `ZPTS`** for the shutdown fix above. The find is the name plus the argument count byte (`_PTS` then `01`), so the `"_PTS="` debug strings in the DSDT are not hit.

`ACPI > Quirks` are all off except `ResetLogoStatus`.

## Booter quirks

| Quirk | Value | Why |
|---|---|---|
| `ForceExitBootServices` | true | It retries ExitBootServices with a fresh memory map if the firmware changed it in between. It went in during the `EXITBS:START` hunt and stayed. That hang turned out to be the MADT, so this quirk is a precaution here, not a proven fix |
| `SetupVirtualMap` | false | Dortania's list for firmware from 2020 on, where it can hang at ExitBootServices |
| `DevirtualiseMmio` | false | leaves all firmware MMIO regions mapped for runtime services; `MmioWhitelist` is empty |
| `ResizeAppleGpuBars` | 0 | Resizable BAR stays on in the BIOS and the RTX 5070 comes up with an 8 GB BAR1. 0 makes OpenCore report the BARs to macOS as 1 MB (the value is a power of two in MB); NvGfx resizes BAR1 itself later |
| `RebuildAppleMemoryMap`, `SyncRuntimePermissions`, `ProtectUefiServices`, `ProvideCustomSlide`, `EnableSafeModeSlide`, `AvoidRuntimeDefrag`, `FixupAppleEfiImages` | true | the usual set for current Intel firmware |

## Kernel

### CPU

- `Emulate > Cpuid1Data` is `55 06 0A 00` with mask `FF FF FF FF` on EAX only. That reports CPUID leaf 1 EAX as `0x000A0655`: family 6, model 0xA5, stepping 5, a Comet Lake. XNU rejects the real family 6 model 0xC6 (Arrow Lake-HX); the Comet Lake value is the usual spoof for Intel CPUs newer than macOS knows.
- `ProvideCurrentCpuInfo` makes OpenCore patch the kernel with the real core and thread count (MSR 0x35, 24 cores and 24 threads here), the TSC frequency and the bus frequency, which XNU cannot work out on a hybrid CPU. OpenCore's documentation requires it for Alder Lake and newer. The README says the boot hangs at `EXITBS:START` without it; that hang was the MADT, and the quirk on its own did not change it.
- `AppleXcpmCfgLock` patches XCPM so it does not write MSR 0xE2, which panics when the firmware has CFG lock set.
- `PlatformInfo > Generic > ProcessorType` is `0x0F01`. With the Comet Lake spoof, OpenCore's automatic choice was a type that macOS names "Unknown" with 24 cores. 0x0F01 shows as a Xeon W, which RestrictEvents (`revpatch=cpuname`, NVRAM `revcpuname`) then renames to the real name.
- `CpuTscSync` (kext) syncs the TSC across cores. The first boot that reached the kernel panicked with "Non-monotonic time" in `AppleACPICPU::start`; the firmware leaves a non-zero `IA32_TSC_ADJUST`.

### Memory and devices

- `DisableIoMapper` and `DisableIoMapperMapping` (both true): with AppleVTD active, the NVIDIA driver saw IOMMU-translated addresses in the BARs and refused the card. With VT-d hidden from macOS, the RTX 5070 initialises.
- `DisableLinkeditJettison`: Lilu and its plugins need the kernel's `__LINKEDIT` after boot.
- `PanicNoKextDump` and `PowerTimeoutKernelPanic`: a panic shows its backtrace instead of a long kext list, and a driver that stalls a power change gets a log line instead of a panic.
- `SetApfsTrimTimeout 0`: APFS skips the trim of all free space at mount. After a partition resize that trim took about 20 s of every boot.
- `Scheme`: `KernelCache Auto`, `FuzzyMatch true`, no custom kernel. `Kernel > Patch`, `Block` and `Force` are empty.

### Kexts, in load order

OpenCore injects the kexts in the order of `Kernel > Add`, and a kext has to come after everything it links against.

| # | Kext | What it is for |
|---|---|---|
| 0 | Lilu | patching framework; everything with a Lilu dependency comes after it |
| 1 | CpuTscSync | TSC sync, see above |
| 2, 3 | VirtualSMC, SMCBatteryManager | an SMC for macOS; battery through the ACPI battery methods |
| 4 | WhateverGreen | keeps the Intel iGPU usable when the firmware hands the panel to it (see the GPU section) |
| 5 | RestrictEvents | `revpatch=sbvmm,cpuname`: software updates with a non-Mac model, and the CPU name |
| 6 | ECEnabler | lets SMCBatteryManager read the EC's multi-byte battery fields |
| 7 | NVMeFix | power management for the WD SN7100S |
| 8 | RealtekRTL8111 | Ethernet |
| 9 | MCEReporterDisabler | plist only: keeps Apple's machine-check reporter from attaching; it came in with the first config, following OpCore-Simplify's choice for this kind of CPU |
| 10 | LegionITEKbdFix | plist only: keeps Apple's HID driver off interface 1 of the ITE keyboard (`048D:C195`, the HID LampArray interface); part of the set that got the internal keyboard typing |
| 11 to 13 | VoodooPS2Controller, its Keyboard plugin, VoodooInput | the PS/2 keyboard device the DSDT declares; VoodooInput is the shared input layer, loaded once from here |
| 14, 15 | VoodooGPIO, VoodooI2CServices | VoodooI2C's own plugins, loaded first because VoodooI2C links against them |
| 16 | VoodooI2C | I2C bus driver for the touchpad (`ELAN06FA` on `PC02.I2C1`, `8086:7F4D`). Its bundled VoodooInput is not loaded, because two copies would collide |
| 17 | VoodooI2CHID | HID over I2C |
| 18 | LegionI2CArrowLake | plist only: a VoodooI2C personality for the Arrow Lake-HX I2C IDs with the Ice Lake timing values, so it comes after VoodooI2C |
| 19 | MtkWlan | MT7925 Wi-Fi |
| 20 | AMFIPass | lets WindowServer load NvGfx's ad hoc signed Metal plugin |
| 21 | AppleALC | ALC257 audio on Sequoia (`alcid=18`); it loads on Tahoe too, but Tahoe has no AppleHDA and uses VoodooHDA from `/Library/Extensions` |
| 22 | LegionCpuProbe | read-only CPU power probe; optional |
| 23 | BlueToolFixup | lets `bluetoothd` accept a non-Apple controller |
| 24 | LegionBtFix | patches `bluetoothd` on Tahoe; `MinKernel 25.0.0`, `MaxKernel 25.99.99`, so Sequoia never loads it |
| 25 | MtkBt | loads the MT7925 Bluetooth firmware so `bluetoothd` finds a working controller |

The graphics driver is not here. NvGfx is installed from its own package into the system, not injected by OpenCore.

The README's kext table also lists MtkWlanNative 0.4.15 and LegionCpuPower 0.4.1, and the README's Wi-Fi row names the boot-args `mtkfe=native mtknativeif=1`. The published config has none of these yet: it is the kext list of 2026-10-17, and the README says it is due a refresh.

## NVRAM, security and SMBIOS

- `boot-args`: `-v keepsyms=1 debug=0x100` (verbose boot, and a panic stays on screen with symbols), `-vi2c-force-polling` (VoodooGPIO has no Arrow Lake GPIO data, so the touchpad is polled instead of using its interrupt pin), `revpatch=sbvmm,cpuname revcpu=1` for RestrictEvents, the NvGfx set (`nvfb=1 nvaccel=1 nvfbheads=4 -nvkmsnosmooth -nvaccelnoheadless nvrmacpibl=1 nvrmphysctl=1 nvrmnvpcf=1 nvrmtgp=1 nvfbhidpi=1 nvrmdiag=1`, documented in NvGfx), the AMFI settings its plugin needs (`amfi_get_out_of_my_way=0x1 amfi=0x80 ipc_control_port_options=0`), and `alcid=18`.
- `csr-active-config` is `0x0A43`: untrusted kexts, unrestricted file system, unrestricted NVRAM, unapproved kexts and unauthenticated root. NvGfx and VoodooHDA live in the system, not in OpenCore, and need the kext bits.
- `NVRAM > Delete` lists every key that `Add` sets, so the config's values replace the stored ones at each boot. `WriteFlash false` means those values are set for the boot only and not written into the firmware's variable store.
- `UEFI > Quirks > RequestBootVarRouting` keeps macOS's Startup Disk writes in OpenCore's own GUID, so macOS cannot rearrange the firmware boot order. `ReleaseUsbOwnership` takes the xHCI controllers from the firmware's legacy USB handling. `ResizeGpuBars -1` leaves the BAR sizes as the firmware set them.
- `Misc > Security`: `SecureBootModel Disabled` (Secure Boot is off in the BIOS; OpenCore and the drivers are unsigned), `Vault Optional`, `ScanPolicy 0`, `DmgLoading Signed`, `BlacklistAppleUpdate true` (with `run-efi-updater No`, macOS updates never try to flash Apple firmware).
- `Misc > Debug`: `Target 67` writes the OpenCore log to `opencore-*.txt` on the EFI partition and shows warnings and errors on screen (`DisplayLevel` 0x80000002). The file is useful with a DEBUG build of OpenCore and harmless with a RELEASE one.
- `PlatformInfo`: `MacBookPro16,1`, `UpdateSMBIOSMode Create`, `SpoofVendor true`. The four identity fields carry OpenCore's sample placeholders, written by `scripts/sanitize_config.py`; generate your own with GenSMBIOS before the first boot.

## Discrete or Hybrid

The BIOS GPU mode decides which GPU drives the internal panel, and the firmware does not always keep the same one between boots. The OpenCore log tells which one it got: `Current FB at 0x6000000000` is the RTX 5070, `Current FB at 0x70800000` is the Intel iGPU.

- **Discrete:** the panel is on the RTX 5070 and NvGfx drives it with Metal. This config is set up for that case: the NvGfx boot-args, `ResizeAppleGpuBars 0`, the IOMMU quirks and AMFIPass are all there for it.
- **Hybrid:** the panel is on the iGPU (`8086:7D67`), and macOS has no accelerated driver for it. This config does not load one; the Intel work is in [WTLIntelGfx](https://github.com/watchthelight-labs/WTLIntelGfx). The config makes sure macOS at least keeps the iGPU: there is no `-wegnoigpu`, and WhateverGreen is loaded. An early config had `-wegnoigpu`, and on a Hybrid boot WindowServer found no framebuffer at all and stayed on the verbose console.

Nothing in the config changes between the two modes. The same EFI boots both, and the result depends on the BIOS setting. For a daily system, set Discrete in the BIOS.

## Updates and rollback

- **A kext or driver:** keep the old bundle next to the new one (renamed, for example `MtkWlan.kext.bak`), copy the new one into `EFI/OC/Kexts`, and boot. If a new kext needs a `Kernel > Add` entry, add it in its place in the load order and run `ocvalidate` from the same OpenCore release.
- **OpenCore itself:** replace `BOOTx64.efi`, `OpenCore.efi` and the four OpenCore drivers from one release together, then `ocvalidate` the config against that release's schema.
- **The stick:** only a config that has booted from the internal partition is copied to the stick (rsync of the whole `EFI` folder), and then the stick's `LauncherOption` and `ShowPicker` are set back as described above.
- **macOS updates:** most kexts here do not care. Two do: LegionBtFix patches specific `bluetoothd` code and is limited to Darwin 25, and MtkWlanNative checks the build it runs on. Both were checked on 26.7.2 (25G332) before being released for it.
- **Rollback:** F12 and the stick. It boots the same macOS volume with the last known-good EFI, and from there the internal EFI partition can be mounted (`diskutil mount`) and the `.bak` copy put back.
- **ACPI after a BIOS update:** the MADT has to be rebuilt with `x2apic_to_lapic.py` from a fresh dump, and `dsdt_patches.py` run against the new DSDT and SSDTs. A find that no longer occurs exactly once means the table changed and that patch needs a new look.

`MANIFEST.txt` has the sha256 of every file on the EFI partition this config was taken from (2026-10-17), apart from `config.plist` and the logs.
