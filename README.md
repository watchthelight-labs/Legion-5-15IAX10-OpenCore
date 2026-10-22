# Legion 5 15IAX10 OpenCore

The OpenCore EFI, ACPI tables and config for running macOS on a Lenovo Legion 5 15IAX10 (machine type 83F0, BIOS S2CN26WW): Intel Core Ultra 9 275HX (Arrow Lake-HX), NVIDIA RTX 5070 Laptop (`10DE:2D18`), Intel iGPU (`8086:7D67`), MediaTek MT7925 Wi-Fi and Bluetooth, Realtek RTL8111 Ethernet, WD SN7100S NVMe, 2560x1600 165 Hz panel. It runs macOS Tahoe 26.7.1 (25G241) as my daily system, with macOS Sequoia 15.8.1 also booting from the same EFI. This is the config as it runs here, with the machine identity replaced by placeholders.

Most of the hardware needed its own driver, which is why this org exists. The config ties them together.

## What works

| Part | How | State |
|---|---|---|
| Boot | OpenCore 1.0.8 on its own EFI partition; Comet Lake CPUID spoof, `ProvideCurrentCpuInfo`, a classic MADT in place of the firmware's x2APIC-only one, 11 ACPI patches | boots Tahoe and Sequoia; [LegionCbmrFix](https://github.com/watchthelight-labs/LegionCbmrFix) unloads a firmware driver that otherwise panics macOS |
| Graphics | [NvGfx](https://github.com/watchthelight-labs/NvGfx) (fork of NullMoth's NVIDIA driver) on the RTX 5070 | Metal 3, 2560x1600 at 165 Hz, 115 W; the Dock's blur draws as blocks |
| Wi-Fi | [MtkWlan](https://github.com/watchthelight-labs/MtkWlan) 0.9.0 | open networks and (host-tested) WPA2-PSK as an Ethernet-class interface; no Wi-Fi menu, no AirDrop |
| Bluetooth | [MtkBt](https://github.com/watchthelight-labs/MtkBt) + BlueToolFixup + [LegionBtFix](https://github.com/watchthelight-labs/LegionBtFix) | pairing, LE, AirPods (audio only with the workaround in LegionBtFix) |
| Audio | Tahoe: [VoodooHDA-Legion](https://github.com/watchthelight-labs/VoodooHDA-Legion) in `/Library/Extensions`; Sequoia: AppleALC with `alcid=18` | speakers and volume; microphone detected, jack and HDMI untested |
| Touchpad | VoodooI2C + VoodooI2CHID + [LegionI2CArrowLake](https://github.com/watchthelight-labs/LegionI2CArrowLake) | works, polled (`-vi2c-force-polling`) |
| Keyboard | the ITE 8258 USB controller with [LegionITEKbdFix](https://github.com/watchthelight-labs/LegionITEKbdFix); VoodooPS2 for the PS/2 device the DSDT declares | types; no backlight control; the arrow keys and F-key dome on my unit are hardware faults |
| Ethernet | RealtekRTL8111 | works |
| Battery, EC | VirtualSMC + SMCBatteryManager + ECEnabler, SSDT-EC-USBX | battery shown |
| Shut down | SSDT-FIXSHUTDOWN + `_PTS` rename | powers off (before: restarted) |
| CPU | 24 cores, name via RestrictEvents, `ProcessorType 0x0F01` | works; turbo stays near 3.7 GHz single-core, not yet understood |
| Sleep | disabled (`pmset sleep 0 hibernatemode 0 standby 0`) | not supported |
| Webcam, SD, Thunderbolt | USB port enabled for the webcam | untested |

Windows stays on its own ESP and is started with F12 and Windows Boot Manager, never from the OpenCore picker (the Mac SMBIOS would leak into it).

## What is in the EFI

`EFI/OC/config.plist` is the live config with the four identity fields set to OpenCore's sample placeholders. Everything else is as it boots here, including the `DEBUG` logging target (it writes `opencore-*.txt` to the EFI partition; harmless with a RELEASE build).

### ACPI

| Table | What |
|---|---|
| `SSDT-PLUG-ALT.aml` | OpenCorePkg sample: CPU power management plugin on Alder Lake and newer |
| `SSDT-EC-USBX-LAPTOP.aml` | fake EC for macOS and USBX power properties; the real EC stays untouched |
| `SSDT-RTCAWAC.aml` | `STAS = 1` under Darwin: the DSDT's legacy RTC instead of AWAC |
| `APIC-legacy.aml` | the firmware's MADT rewritten with type-0 Local APIC entries (`scripts/x2apic_to_lapic.py`); XNU counts CPUs only from those, and this firmware emits x2APIC entries only, so the kernel saw 0 CPUs and died before the console. The firmware table is deleted |
| `SSDT-FIXSHUTDOWN.aml` | clears the xHCI controllers' PME enable at S5, so Shut Down powers off instead of restarting; needs the `_PTS` to `ZPTS` rename below |

The `.dsl` sources are in `ACPI/`. The 11 `ACPI > Patch` entries come from `scripts/dsdt_patches.py`, each with its reason: two module-level `If (PCHA != Zero)` blocks turned into scopes (macOS's ACPICA rejected the whole DSDT otherwise), a scope retarget, three `Name` + `Store` pairs turned into methods (sideband and USB port visibility), four `_UPC` fixes in Lenovo's USB table so the keyboard (HS05), Bluetooth (HS14), webcam (HS11) and a USB-A port (HS02) are connectable under macOS, and the `_PTS` rename.

### Kexts (`Kernel > Add`, in load order)

Binaries are not in this repository. Get each from its release page; the versions are the ones running here.

| Kext | Version | From |
|---|---|---|
| Lilu | 1.7.2 | acidanthera |
| CpuTscSync | 1.1.2 | acidanthera (the first boots panicked with "Non-monotonic time") |
| VirtualSMC, SMCBatteryManager | 1.3.8 | acidanthera |
| WhateverGreen | 1.7.1 | acidanthera (the iGPU stays visible; the firmware sometimes hands the panel to it) |
| RestrictEvents | 1.1.6 | acidanthera (`revpatch=sbvmm,cpuname`) |
| ECEnabler | 1.0.6 | 1Revenger1 |
| NVMeFix | 1.1.3 | acidanthera |
| RealtekRTL8111 | 3.0.4 | Mieze |
| MCEReporterDisabler | 0.5 | plist only |
| LegionITEKbdFix | 1.0.0 | this org |
| VoodooPS2Controller (+ Keyboard, VoodooInput) | 2.3.7 | acidanthera |
| VoodooI2C (+ VoodooGPIO, VoodooI2CServices), VoodooI2CHID | 2.9.1 | VoodooI2C |
| LegionI2CArrowLake | 1.1.0 | this org |
| MtkWlan | 0.9.0 | this org |
| AMFIPass | 1.4.1 | dortania (lets WindowServer load the ad hoc signed Metal plugin) |
| AppleALC | 1.9.8 | acidanthera (audio on Sequoia; no effect on Tahoe) |
| LegionCpuProbe | 1.0.0 | this org, read-only MSR probe for the turbo question; optional |
| BlueToolFixup | 2.7.2 | acidanthera (BrcmPatchRAM release) |
| LegionBtFix | 0.2.0 | this org, `MinKernel 25.0.0`, `MaxKernel 25.99.99` |
| MtkBt | 0.2.0 | this org |

Audio on Tahoe is VoodooHDA in `/Library/Extensions`, not injected by OpenCore. Graphics is NvGfx's installer package.

### Drivers and tools

`OpenRuntime.efi`, `OpenHfsPlus.efi`, `ResetNvramEntry.efi`, `ToggleSipEntry.efi` from OpenCore 1.0.8; `LegionCbmrFix.efi` 1.0.0 from this org. `OpenShell.efi` as the only tool.

### Settings worth knowing

- `Kernel > Emulate`: `Cpuid1Data` spoofs a Comet Lake CPU (family 6 model 0xA5); XNU rejects the real family 6 model 0xC6.
- `Kernel > Quirks`: `ProvideCurrentCpuInfo` (hybrid CPUs need it; without it the boot hangs at `EXITBS:START`), `DisableIoMapper` and `DisableIoMapperMapping` (with AppleVTD on, the NVIDIA driver reads IOMMU addresses from the BARs and refuses the card), `AppleXcpmCfgLock`, `DisableLinkeditJettison`, `PanicNoKextDump`, `PowerTimeoutKernelPanic`, `SetApfsTrimTimeout -1`.
- `Booter > Quirks`: `ForceExitBootServices` (a real hang at ExitBootServices without it), `ResizeAppleGpuBars 0` (the RTX 5070 boots with an 8 GB BAR1; NvGfx resizes it back up itself), `SetupVirtualMap` off, `DevirtualiseMmio` off, the usual rest on.
- `UEFI > Quirks`: `ReleaseUsbOwnership`, `RequestBootVarRouting`, `ResizeGpuBars -1`.
- `Misc > Boot`: no picker (`ShowPicker false`, hold Option or Esc while OpenCore starts to get it), `LauncherOption Full` so OpenCore stays first in the firmware boot order, `Timeout 0`.
- `Misc > Security`: `SecureBootModel Disabled`, `Vault Optional`, `ScanPolicy 0`.
- `NVRAM`: `csr-active-config 0x0A43` (unsigned and unapproved kexts, for NvGfx and VoodooHDA), `WriteFlash false`, the two BlueToolFixup keys, `revcpuname` for the CPU name.
- `PlatformInfo`: `MacBookPro16,1`, `ProcessorType 0x0F01` (the Comet Lake spoof makes OpenCore pick a type macOS cannot name with 24 cores).
- `boot-args`: `-v keepsyms=1 debug=0x100` (a panic stays on screen), `-vi2c-force-polling`, `revpatch=sbvmm,cpuname revcpu=1`, the NvGfx set (`nvfb=1 nvaccel=1 nvfbheads=4 -nvkmsnosmooth -nvaccelnoheadless nvrmacpibl=1 nvrmphysctl=1 nvrmnvpcf=1 nvrmtgp=1 nvfbhidpi=1 nvrmdiag=1`), the AMFI relaxations NvGfx's plugin needs (`amfi_get_out_of_my_way=0x1 amfi=0x80 ipc_control_port_options=0`), and `alcid=18` for Sequoia.

## BIOS

Secure Boot off (OpenCore and the drivers are unsigned). The panel can be driven by either GPU and the firmware changes its mind between boots; NvGfx handles the NVIDIA case, WhateverGreen keeps the iGPU usable for the other. Legion Space on Windows was set to GPU Working Mode dGPU, Performance profile. Resizable BAR stays on.

## Using it

1. Read the [OpenCore install guide](https://dortania.github.io/OpenCore-Install-Guide/) first; this repository replaces the "build your EFI" part for this laptop, nothing else.
2. Build `EFI/OC/Kexts/` from the table above, `EFI/OC/Drivers/` and `EFI/BOOT/BOOTx64.efi` from OpenCore 1.0.8 (DEBUG if you want the logs) and LegionCbmrFix. `MANIFEST.txt` lists the sha256 of every file on my EFI partition, so you can check yours against it.
3. Generate your own identity with GenSMBIOS for `MacBookPro16,1` and put it in `PlatformInfo > Generic` (the four placeholder fields). Do not boot with the placeholders.
4. Boot from USB (F12), install, then copy the EFI to its own partition. The Windows ESP on this laptop is 200 MiB and holds a custom boot shim, so I made a second EFI partition for OpenCore and let `LauncherOption Full` register it first in the firmware boot order.
5. After the first desktop: `sudo pmset -a sleep 0 hibernatemode 0 disksleep 0 standby 0`, then the NvGfx package, VoodooHDA, and `mtkwifi` from the driver repos.

Rollback: F12 and pick the USB stick with a known-good copy of this EFI. Nothing here writes to firmware NVRAM.

## Scripts

- `scripts/dsdt_patches.py`: the patch list with reasons, and a tester that applies them to a dumped DSDT so you can load the result in `acpiexec` before booting.
- `scripts/x2apic_to_lapic.py`: builds `APIC-legacy.aml` from the firmware MADT.
- `scripts/sanitize_config.py`: what produced `EFI/OC/config.plist` from the live one.

## Credits

acidanthera (OpenCore, Lilu and the kexts above), Dortania (the guides and the shutdown fix pattern, RehabMan's FixShutdown), VoodooI2C, Mieze, 1Revenger1, NullMoth Systems (the NVIDIA driver NvGfx forks), the Clover team (VoodooHDA), thanhnndev (itlmt7925, the first MT7925 driver for macOS), saspol ([UltraWake](https://github.com/saspol/UltraWake), the Arrow Lake GPE 0x6B/0x6E self-wake analysis we will follow when sleep is turned on), johnfanv2 and the [LenovoLegionLinux](https://github.com/johnfanv2/LenovoLegionLinux) contributors (the S2CN EC and WMI fan map).

## Licence

The `.dsl` sources, scripts and config in this repository are ISC (`LICENSE`). `SSDT-PLUG-ALT.aml` is compiled from OpenCorePkg's sample (BSD-3-Clause).
