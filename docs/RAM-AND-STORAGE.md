# RAM and storage

The project combines a persistent boot menu with an Android runtime in RAM. Their persistence boundaries are different.

## Installation

Inside an existing Kit SSH ramdisk, the installer reads the main system version, device identity, kernel, DRA, NVRAM, and available space. After confirmation, it adds boot files and submits the complete boot image set through the existing Apple interface: LLB first, followed by the other six images.

Local files include `/boot/t4/android.img3` and, for the 5.1.1 route, `/boot/t4/ios-iboot.img3`. The original MENU03 route for 7.1.2 also uses a matching local DeviceTree file.

The menu and boot files persist on the device. The installer does not erase, repartition, replace the original iOS kernelcache, or set NVRAM variables.

## Android runtime

The menu reads `android.img3` through the existing iBoot file interface, verifies it, places the kernel, initramfs, and related sections in RAM, then hands control to Linux and Android. Booting reads files stored on NAND; Android's runtime remains in RAM, with no implemented persistent Android data partition.

| Use case | Current behavior |
| --- | --- |
| Desktop, real touch input, Home, and volume buttons | Tested on hardware |
| ADB shell | Tested on hardware |
| Changing settings, installing apps, or creating data | Uses RAM for the current session; not retained after reboot |
| Accessing the complete iOS user storage from Android | Not implemented |
| Rebooting without USB | Menu remains; Android reloads its RAM environment |

Available memory must hold the kernel, unpacked system files, applications, and temporary data together. Long-term use, full suspend/resume, and protection of runtime data against power loss have not been validated.

## saved/ layout

| Directory | Purpose |
| --- | --- |
| `saved/build/` | Builds, images, and diagnostic outputs |
| `saved/packages/` | Imported complete local installer packages |
| `saved/state/` | Installation logs, component caches, and audit records |
| `saved/releases/` | Tool packages and frozen successful snapshots |
| `saved/downloads/` | Download cache |
| `saved/private/` | Local configuration, tickets, and calibration |
| `saved/history/` | Historical materials |

Git tracks documentation and empty directory markers only. Generated files and private data are excluded. Existing read-only backups are not a complete NAND/NOR dump.
