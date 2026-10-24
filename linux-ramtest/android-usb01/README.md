# T4_ANDROID_USB_01 — first native USB/ADB port test

The prior USB_SUPPORT-off builds could not enumerate Android ADB. INPUT03 also reported PH9, which combines command deadlines and boot-property failure; without its RAM command-status file that does not identify a specific failing Android command. This variant adds an independent USB path to collect real kernel/framework logs.

## Boot

Enter hardware DFU:

```sh
cd .
python3 phase1/run.py --boot --published
python3 linux-ramtest/run.py --build T4_ANDROID_USB_01 --boot
```

Host checks with adb already installed:

```sh
adb devices -l
adb -s T4RAMUSB01 shell dmesg > USB01-dmesg.txt
adb -s T4RAMUSB01 logcat -b main -b system -d > USB01-logcat.txt
adb -s T4RAMUSB01 pull /data/local/tmp/t4-command-status.txt .
```

Run the last three commands only if the first lists `T4RAMUSB01 device`. No actual hardware boot or ADB handshake was performed by the build agent.

## Native changes and evidence

- Enable device-side USB gadget, S3C HSOTG UDC and Android composite; USB host and storage classes remain disabled. Register the existing N81 USB platform device (physical0x86100000, IRQ13), matching `openiBoot-c5cee8c/usb-synopsys/includes/hardware/usb.h`.
- Port the A4 PHY sequence from `research/openiBoot-c5cee8c/plat-a4/usbphy.c` and its hardware header. A4 clock encodings12/24/48MHz are0/1/2, unlike the generic Samsung header. Read Linux xusbxti rate and reject unknown references before any PHY write. Release only PCGCCTL stop bits left by OpeniBoot shutdown. PHY writes are confined to the documented A4 PHY and USB blocks.
- Actual published OpeniBoot log `logs/phase1-published-20261019-211342.log` records HWCFG3=0x07e800e8 and HWCFG4=0xdbf08030: FIFO depth2024 words and dedicated FIFOs. Generic driver allocated RX2048 plus NP1024 plus16*768 words. USB01 uses RX512, NP128, eight dedicated128-word FIFOs:1664 words, with capacity validation before writes. This is a test allocation, not hardware-proven throughput.
- Make reset/FIFO errors propagate. Fix two inherited FIFO flush loops that logged zero timeout but continued indefinitely. Mask global USB IRQs on failed reset-time FIFO initialization. Keep IRQ disabled through PHY/core/endpoint initialization; enable the USB IRQ number, not request_irq's return code. Endpoint IRQ array traversal stays within9 allocated entries.
- Add gadget pullup callback and retain software-disconnected state until userspace configures ADB. Add missing configuration/connect return checks and reject sysfs enable when composite binding never succeeded.
- Expose only adb in supported_functions. MTP, mass-storage, RNDIS and other function entries are absent from that array and never initialized by android_init_functions. Seven native NAND/VFL/register/write/erase stubs are still asserted by the builder; MTD/MMC/SCSI/ATA/USB storage remain off. No physical block device nodes are supplied.
- Retain prior GPIO keys, TLS, memset/noalign, framebuffer and Android JNI fixes. Extend RAM-only HUD to64 rows with USB diagnostics. No LCD/MIPI initialization changes.

## Userspace

Start from exact INPUT03 CPIO. Change only init.rc/default.prop and add the original `androidi4` static `/sbin/adbd` plus `t4-usb-setup.sh`. Original adbd SHA256 is54de8a66a99a842ce81616e09fd0525b45515bfc1aa29d830de8a3b499756137. It expects /dev/android_adb, matching the existing f_adb misc device. Daemon is root for this RAM diagnostic image (ro.secure=0), allowing dmesg/framework/input inspection. No physical storage driver is activated. Its legacy local control listener is not a USB handshake result; setup selects USB transport and does not configure a network transport.

USB setup runs independently on boot before framework success is required. It only writes Android gadget sysfs attributes, optionally creates the actual major10 misc char node in RAM, and starts adbd through init's property control. VID:PID18d1:0001, serialT4RAMUSB01, functions=adb. Unknown or absent device numbers abort. The bounded INPUT03 watcher remains unchanged and PH9 still needs its real command-status file to distinguish failure causes.

## HUD

U10=UDC probe complete; U20=Android composite bound; negative U=first recorded USB error. IRQ counts USB ISR entries, SET counts EP0 requests, A bit0 means daemon opened its misc node, bit1 means host configured the ADB function. A=3 does not establish protocol handshake or shell functionality. Photo these four fields if enumeration fails. Existing P/RAW/EV/OPEN/HB/PH fields retain their meanings.

## Build/check

```sh
python3 linux-ramtest/android-usb01/build.py
build/t4-arm-tests-venv/bin/python linux-ramtest/android-usb01/test_usb_arm.py
python3 linux-ramtest/android-usb01/test_usb_bundle.py
python3 linux-ramtest/android-usb01/test_setup_script.py
python3 linux-ramtest/android-usb01/test_package.py
python3 linux-ramtest/android-usb01/test_repair.py
python3 linux-ramtest/run.py --build T4_ANDROID_USB_01 --check
```

OFFLINE-RESULTS.json records native ARM USB tests (mocked register/clock/log/delay services), HUD glyph/bounds tests, existing key/evdev/TLS/memset/noalign/fb regressions, original adbd/package integrity and prior hashes. Host USB setup fixtures redirect every path and mock mknod/setprop; they do not operate USB. Five mock OpeniBoot host transport cases verify staging/refusals, not Android USB enumeration. USB01 remains hardware-unverified.

Input-to-USB source delta is `build/T4_ANDROID_USB_01/usb01-only.patch`. Existing UI07/INPUT01/02/03 outputs are preserved. All device runtime modifications are RAM-only. No NAND/NOR/install/erase/partition/physical-storage/RTC operations.

Touch is deliberately not initialized: verified N81 firmware/calibration, power/reset and SPI/IRQ bring-up are still required. See research/t4-touch/STATUS.md. No date or number of successful test cycles can be inferred from compilation.
