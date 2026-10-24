# T4_ANDROID_UI_01 — real Android 2.3.7 framework / Launcher RAM attempt

Hardware desktop status: PENDING. This build is based on the proven INIT04 native fixes and original androidi4 init, full system and Launcher2. No fabricated desktop or substitute shell UI.

## Boot (hardware DFU)

```sh
cd .
python3 phase1/run.py --boot --published
python3 linux-ramtest/run.py --build T4_ANDROID_UI_01 --boot
```

The 46 MB compressed system takes longer to upload and verify than the old tiny initramfs. The host prints upload progress. The stage permits 120 seconds for RAM CRC validation. After handoff, allow framework startup to progress and photograph the final screen if no desktop appears.

## Build/check

```sh
python3 linux-ramtest/android-ui01/build.py
python3 linux-ramtest/android-ui01/test_package.py
python3 linux-ramtest/android-ui01/test_repair.py
build/t4-arm-tests-venv/bin/python linux-ramtest/android-ui01/test_noalign_arm.py
build/t4-arm-tests-venv/bin/python linux-ramtest/android-ui01/test_memset_arm.py
build/t4-arm-tests-venv/bin/python linux-ramtest/android-ui01/test_fb_arm.py
python3 linux-ramtest/run.py --build T4_ANDROID_UI_01 --check
```

Source: sources/iDroid-kernel-T4_ANDROID_UI_01. Existing INIT04 binaries/source remain intact.

## Userspace

Original Android init and 718 original system records, including Launcher2, SystemUI, framework, services, linker and shared libraries. System uid/gid/modes/mtimes and contents preserved except software-only egl.cfg, boot properties and empty vold config overlays. Original NAND/loop/host-volume scripts are omitted. All 413 ODEX dependency names/order/signatures match the configured bootclasspath; VM build 23 is verified against Android 2.3.7 DalvikVersion.h. All 200 native ELF dependency closures are present.

Original ueventd creates real binder/ashmem/log/graphics nodes. RC starts servicemanager, standalone SurfaceFlinger, zygote/system_server, media, installd, debuggerd, netd, keystore, logcat and a monitor. The standalone SF is selected with system_init.startsurfaceflinger=0 to avoid duplicate registration. vold has empty configuration: no physical volumes. /data and /cache are capped tmpfs. Framework logs rotate in RAM at /data/local/tmp/android.log*. No rild/WiFi/Bluetooth/camera services are started.

## Kernel/display

Native INIT04 memset/noalign/clock/storage guards retained. Binder, ashmem, Android logger, VFP/NEON, evdev, cgroups, Unix/INET and generic Android alarm enabled. Platform suspend/runtime PM remains disabled because that old Samsung PM implementation requires missing platform headers and is not necessary for this RAM display attempt. Alarm's wakelock calls use the kernel's native no-PM stubs. Physical networking and panel initialization are not added.

New fbdev driver exposes /dev/graphics/fb0 over a page-aligned RAM shadow buffer. It copies actual Android pixels to the existing 640x960 display at 10 Hz, supports RGBX8888 and RGB565 fallback and never accesses display MMIO. Native printk keeps the screen until userspace writes nonzero pixels; closing the framebuffer restores diagnostics. A first fatal Oops restores native console output. fbcon is disabled to avoid drawing over Android. Touchscreen hardware remains outside this first display test.

## RAM bounds

Kernel upload 0x42000000; decompression input low 0x02000000; Image 0x8000. Helper 0x44000000..0x44010000, info 0x43f00000. Large initrd upload 0x44800000 aliases physical 0x04800000, ends below 0x48000000. This avoids the public OpeniBoot heap starting 0x48000000, its stack/page table at the top of RAM, and the inherited framebuffer observed at 0x48104580. The initrd is used in place, not copied over the LCD. Interval and CRC checks enforce the bounds.

## Success evidence

A real Launcher desktop on the device is the actual goal. sys.boot_completed=1 and dumpsys activity mResumedActivity are supporting evidence. An unchanged boot marker, host upload completion, T4_FB_READY or even a first userspace frame alone does not prove a desktop.

Offline checks pass; this does not assert hardware success. All device operations are DFU/USB RAM upload and execution, with native storage registration/write/erase entry guards retained. No NAND/NOR installation, formatting, partitioning or persistent system/data image is used.
