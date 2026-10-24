# T4_ANDROID_UI_03 — original androidi4 bionic TLS compatibility

UI01 hardware photo IMG_8190 shows dynamic services repeatedly SIGSEGV (wait status 0xb). Static original init/busybox remain alive. Original libc __libc_preinit at 0xafd14dc8 directly loads TLS from 0xffff0ff0; current Linux CPU_32v6K updates only TPIDRURO. Legacy iDroid kernel_common updates both on ARM set_tls and on every context switch. UI03 ports that narrow UP-only compatibility to N81, preserving the original Android files.

## Boot from hardware DFU

```sh
cd .
python3 phase1/run.py --boot --published
python3 linux-ramtest/run.py --build T4_ANDROID_UI_03 --boot
```

Pre-Linux CRC remains enabled, with byte-table acceleration and visible 1 MiB progress at 6A/6B. Original init starts a static-shell preflight running original dynamic getprop and setprop. Both must return 0 before class android starts the real framework. Failure leaves a quiet static service and up to eight native T4_USER_FAULT records with PC/LR/SP/DFAR, rather than repeatedly launching everything. First eight fault logs do not change signal delivery.

Expected preflight lines: T4_DYNAMIC_PROBE_EXIT=0, T4_DYNAMIC_SETPROP_EXIT=0, T4_DYNAMIC_READY_START_FRAMEWORK. These do not prove Android desktop success. Actual Launcher on device remains the goal and requires hardware verification. Photograph the final error if no desktop.

## Rebuild and offline check

```sh
python3 linux-ramtest/android-ui03/build.py
python3 linux-ramtest/android-ui03/test_package.py
python3 linux-ramtest/android-ui03/test_repair.py
build/t4-arm-tests-venv/bin/python linux-ramtest/android-ui03/test_tls_arm.py
build/t4-arm-tests-venv/bin/python linux-ramtest/android-ui03/test_crc_arm.py
python3 linux-ramtest/run.py --build T4_ANDROID_UI_03 --check
```

Sources: sources/iDroid-kernel-T4_ANDROID_UI_03; previous UI01 and INIT04 unchanged. Native source diff: build/T4_ANDROID_UI_03/native-userspace-prerequisites.patch. Old iDroid evidence: research/idroid-legacy/kernel_common/arch/arm/kernel/traps.c and entry-armv.S. Exact original ELF analysis: research/runtime-analysis/.

Kernel/native entry, display framebuffer driver, package layout, original Android init, original linker/libc/system/ODEX content remain those of UI01. Only native kernel TLS compatibility, bounded user-fault logs, framework preflight and RAM CRC speed/progress change. Native hardware TLS support is retained; legacy mirror guarded CONFIG_MACH_IPOD_TOUCH_4G && !CONFIG_SMP. No shared TLS mirror is enabled for SMP.

Full system and all service output are in RAM CPIO/tmpfs; physical MTD/MMC/SCSI/ATA/USB storage disabled and Apple storage registration/write/erase stubs verified. No installation, physical block device nodes, persistent volume actions, NAND/NOR writes or LCD/MMIO reinitialization. /data and /cache are RAM tmpfs. Default software EGL and Launcher2 are original androidi4; touch remains unported.

Offline execution models syscalls, kuser atomics and mappings; it is not a hardware or complete Linux userspace validation. In that model four original programs fault at libc PC 0xafd14dd0 reading 0xc without the TLS mirror; original getprop exits 0 with it. Hardware result pending.
