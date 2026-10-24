# T4_ANDROID_ADB_01

Built from the physical-ACM-confirmed T4_USB_ACM_01 source. Android userspace is
pinned to INPUT03 (which preserves the original androidi4 init/system and UI07
JNI fixes). This version enables only the Android ADB USB function. Physical
ADB enumeration and a root shell are now confirmed on2026-10-20. See
build/T4_ANDROID_ADB_01/HARDWARE-RESULT.json.

## Boot and verify

Enter hardware DFU, then:

```sh
cd .
python3 phase1/run.py --boot --published
python3 linux-ramtest/run.py --build T4_ANDROID_ADB_01 --boot
python3 tools/t4-adb-check.py --wait 90
```

The checker uses standard adb server port5037 and macOS ADB_LIBUSB=1, waits for serial
**T4RAMADB01** in state **device**, then runs:

```sh
tools/adb-host-adb01/adb -P 5037 -s T4RAMADB01 shell 'echo T4_ADB_SHELL_OK; id; uname -r'
```

Success is **T4_ADB_SHELL_CONFIRMED** and the actual shell marker, rather than
USB enumeration alone. Host output is saved in logs/adb-check-*.log.
An interactive shell is then:

```sh
tools/adb-host-adb01/adb -P 5037 -s T4RAMADB01 shell
```

This image uses VID:PID**18d1:0001**, serialT4RAMADB01, functions=adb.
ACM01's0525:a4a7 serial port is not provided alongside ADB. Do not run the ACM
verifier against this image. No network, MTP or mass-storage function is enabled.

The host adb was downloaded from Google's official Platform-Tools package;
version37.0.1-15733141 runs on this Mac. tools/adb-host-adb01/DOWNLOAD.json pins
its archive/binary SHA256 and source:
https://developer.android.com/tools/releases/platform-tools . No global SDK or
PATH installation is required; no adb server was started by offline tests.

## Changes and evidence

- A4 PHY/link glue, platform contract and clock implementation are byte-identical
  to ACM01. Its delayed IRQ registration/initialized endpoint fix is retained.
  No controller reverse engineering or USB stack replacement was performed.
- The UDC's automatic post-bind pullup is disabled only for CONFIG_USB_G_ANDROID.
  android_bind already requests disconnect; its sysfs enable action first binds
  the ADB config/function, then calls the existing proven A4 pullup/session path.
  Serial's automatic connection remains unchanged in its preserved build.
- Config selects USB_G_ANDROID instead of USB_G_SERIAL. supported_functions
  contains only adb_function; existing android.c and f_adb.c are unchanged from
  ACM01. The HUD label identifies ADB01.
- Original static androidi4 /sbin/adbd is unmodified: SHA256
  54de8a66a99a842ce81616e09fd0525b45515bfc1aa29d830de8a3b499756137.
  ro.secure=0 is limited to this RAM debug image. No root/remount/install command
  is required to inspect the running kernel and framework.
- INPUT03 CPIO changes only init.rc/default.prop and adds adbd plus two tiny
  scripts. Setup starts after ifup lo, independently of system_server success.
  It configures ADB sysfs, creates only verified character nodes in RAM as needed,
  and starts adbd via init. The wrapper execs the original daemon with stdout/
  stderr directed to /dev/kmsg, preserving init's restart supervision.
- Legacy adb shell uses /dev/ptmx. Original Android init already mounts devpts;
  setup checks it and uses a pseudo-filesystem-only fallback if needed. Missing
  ptmx must match actual sysfs dev5:2. android_adb must match actual misc major10
  and a valid minor. Unknown numbers/path conflicts abort rather than guessing.

HUD: U10=UDC probe returned; U20=Android composite bound (still disconnected until
setup). A bit1=open daemon, bit2=host configured ADB; A3 is necessary progress,
not proof of CNXN or shell. If offline, photograph U/IRQ/SET/A and the last
T4_ADB01_READY / T4_ADBD_EXEC / error lines. The host verifier times out and
records failure instead of reporting a USB descriptor as shell success.

## Offline checks completed

Actual ARM probe/IRQ regression reproduces old USB01 PCc013bb64/DFARc on its
old binary, then verifies this build's synchronous IRQ safety and allocation/
clock/platform/ID/IRQ failure paths. An actual ARM UDC gadget bind is executed
with OS/register fixtures: DCTL stays disconnected until explicit pullup,
which then clears disconnect and requests session. This is not a physical USB
or complete adbd protocol emulation.

Actual ARM A4 PHY/FIFO/reset/pullup tests, six setup-script fixtures (PTY fallback,
invalid nodes, absent gadget), full CPIO/metadata/413 ODEX dependency checks,
handoff-address checks and four host-verifier fixtures all pass. Protected
OpeniBoot/ACM01/UI/input builds and all original Android system payloads are
hash-verified. Offline tests do not execute the device or establish ADB success.

```sh
python3 linux-ramtest/android-adb01/build.py
build/t4-arm-tests-venv/bin/python linux-ramtest/android-adb01/test_irq_order.py
build/t4-arm-tests-venv/bin/python linux-ramtest/android-adb01/test_usb_arm.py
python3 linux-ramtest/android-adb01/test_setup_script.py
python3 linux-ramtest/android-adb01/test_usb_bundle.py
python3 linux-ramtest/android-adb01/test_package.py
python3 linux-ramtest/android-adb01/test_repair.py
python3 linux-ramtest/android-adb01/test_host_check.py
python3 linux-ramtest/run.py --build T4_ANDROID_ADB_01 --check
```

Outputs: build/T4_ANDROID_ADB_01/{zImage,handoff.bin,initramfs.cpio.gz,vmlinux,
manifest.json,adb01-vs-acm01.patch,OFFLINE-RESULTS.json,NEXT-BOOT.txt}.
Use the checked RAM loader above; these are not standalone DFU native images.
No NAND/NOR, partition, install, erase, physical filesystem or RTC operations
were added. Touch is still not initialized; this version's purpose is ADB.

## macOS official adb backend fix — physically verified

The downloaded official Google37.0.1 binary is byte-identical to the archive
entry (SHA2561811e253b21b12cbfda7201ebaf86c10e7ddcb5c606a7a81f7c82b4c429c2d3b).
No ADB binary was patched. This Mac terminated its default legacy USB backend
with EXC_GUARD / INVALID_NAME inside IOUSBLib's IOUSBInterfaceClass destructor.
Using the officially supported ADB_LIBUSB=1 setting starts the server normally.
The user's .zshrc now exports that setting (prior file backed up), and the host
checker explicitly sets it on macOS. Standard port5037 keeps ordinary `adb`
and the checker on the same server. No iPod firmware change was needed.

Physical results: T4RAMADB01 device, T4_ADB_SHELL_OK, uid=0(root) gid=0(root),
Linux3.0.8. USB enumeration alone is no longer the only evidence.
Official backend switch reference:
https://developer.android.com/tools/releases/platform-tools#revisions
