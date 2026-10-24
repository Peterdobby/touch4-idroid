# T4_ANDROID_INIT_02 — RAM-only Android init environment

Built against the existing Linux 3.0.8 T4 source, with original `androidi4.zip` init and busybox.

## Build

From the project root:

```sh
python3 linux-ramtest/android-init02/build.py
python3 linux-ramtest/android-init02/test_package.py
build/t4-arm-tests-venv/bin/python linux-ramtest/android-init02/test_memset_arm.py
build/t4-arm-tests-venv/bin/python linux-ramtest/android-init02/test_probe_arm.py
python3 linux-ramtest/run.py --build T4_ANDROID_INIT_02 --check
```

The isolated source is `sources/iDroid-kernel-T4_ANDROID_INIT_02/`. The reviewable source delta is `build/T4_ANDROID_INIT_02/native-userspace-prerequisites.patch`. Build script never opens USB. Existing successful artifacts are hash-checked and preserved.

## Boot

Put the device into hardware DFU, then:

```sh
python3 phase1/run.py --boot --published
python3 linux-ramtest/run.py --build T4_ANDROID_INIT_02 --boot
```

If public OpeniBoot is already running, use only the second command. Do not boot zImage directly with phase1. Host log is printed by run.py; Linux printk continues on the device screen after the ACM handoff.

## Changes from INIT_01

- CONFIG_NET, CONFIG_UNIX, CONFIG_TMPFS enabled; no IP stack/network interfaces needed.
- Original `/init` SHA256 d67ec53adf54cbdb9e38c6cce4d324f5f1c4908abd4630169c438134057c520f unchanged as `/android-init`.
- Real `/sbin/ueventd` invokes the original binary via argv[0]; coldboot marker is not fabricated.
- Original static busybox provides `/bin/sh`. Sanitized initDroid.sh only makes `/dev/kmsg` inside tmpfs and logs a marker. Original disk script is omitted.
- RAM tmpfs /data and /cache, /data/property prepared before property_service initialization.
- Original property service and signal initialization retained; no bypass of check_startup and no replacement PID1 to hide its exit.
- Proven memset C ABI, early noalign, inherited display gate policy and NAND registration/write/erase stubs integrated into native source. No kernel address-dependent resident patches remain. Six proven zImage handoff probes remain with instruction and CRC checks.
- First kernel Oops halts with PC/LR/DFAR instead of recursively dumping.

## Evidence and limits

Offline native ARM memset: 8288 cases passed, actual native SLUB init_object passed.
Bootstrap/service ARM emulation: success/failure branches passed, including failed Unix connect and wrong parent.
Package checks: original init hash, no block device CPIO entries, only tmpfs rc mounts, protected prior hashes, compressed Image and six executable probes passed.

Hardware result for this new variant is PENDING. Look for `ANDROID_INIT_ENVIRONMENT_CONFIRMED` (real coldboot file, /data/property, connected property_service socket) followed by repeated `ANDROID_INIT_SERVICE_REACHED` from a service parented by PID1. This tests Android init only; no servicemanager/zygote/framework started.

Legacy source comparison: `research/idroid-legacy/analysis/T4-userland-comparison.md`.
