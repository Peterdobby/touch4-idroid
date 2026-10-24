# Verification status

Last updated: 2026-10-24 (Asia/Shanghai).

| Item | Tested environment |
| --- | --- |
| Device | iPod touch 4G, iPod4,1 / N81AP, Apple A4 |
| OpeniBoot | 0.3, commit `c5cee8c` |
| Base boot environment | Existing Kit DRA6 / DRV6 setup, 10B500 base components |
| Linux / Android | 3.0.8 / 2.3.7, RAM userspace |
| Host | Intel macOS; other environments have not been fully tested |

## Hardware results

1. **iOS 5.1.1 / 9B206, Installer 02.4 / MENU04:** after reboot, OpeniBoot enumerated as `0525:1280` and `version` returned `openiboot 0.3 commit c5cee8c for iPod Touch 4G`. The owner confirmed iOS boot, followed by the menu, Android, touch, and buttons after rebooting with USB disconnected.
2. **iOS 7.1.2 / 11D257, previously tested Kit port / MENU03:** the owner confirmed iOS boot, the unplugged menu, Android, touch, and buttons. This is a specific port; it is not an officially supported stock iOS 7 installation for iPod touch 4G.
3. The Android RAM build's root ADB shell and OpeniBoot ACM command round trips have hardware test records.

Only these exact combinations have hardware results. iOS 4/6, other point releases, and other devices remain unverified. Successfully downloading matching components does not establish that they boot.

## What changed in 02.4

The first 5.1.1 installation received successful firmware-update responses but rebooted into DFU. The generator had replaced the persistent `dtre` with the target 9B206 file while the remaining base images and APTicket still came from 10B500.

Version 02.4 restores the six original base images and changes only the custom menu `ibob`. The target iBoot still loads from a local boot file. OpeniBoot USB/version, iOS boot, and unplugged Android boot were then confirmed. The original iOS kernel, DRA partition, partition table, and NVRAM were not modified.

Update receipts, host simulation checks, USB responses after reboot, visual confirmation, and unplugged boot are recorded separately. This public repository contains a summary without device identifiers. Original logs and frozen snapshots remain in local `saved/` directories.

## Limitations

- Android userspace and user data reside in RAM; changes are lost on reboot.
- Persistent Android userdata/cache has not been implemented. General Android NAND read/write access has not been demonstrated.
- Real touch input requires the correct N1 firmware and device-specific calibration. Another device's calibration is not a substitute.
- ADB host and platform-tools compatibility has not been comprehensively tested.
- Wi-Fi, audio, camera, Bluetooth, complete power management, and long-term stability are not listed as verified features.
- Successful complete packages are bound to the owner's device identity. This repository is not a universal pre-signed installer.

Version 02.4 passed 32 installer-state tests and 22 component/image-set tests. These cover update order, corrupt-package rejection, cache preservation, failure auditing, and RAM locks; they do not replace hardware testing.
