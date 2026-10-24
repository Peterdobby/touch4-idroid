# T4_ANDROID_UI_05 — keep tested UI04 kernel; expose first framework failure

Hardware IMG_8194 confirms UI04 original dynamic services run, inherited framebuffer opens, and real Dalvik Zygote preloads 51 drawable and 15 color resources. Zygote then exits; sys.boot_completed and desktop remain unconfirmed. The old monitor repeatedly tails ten GC lines, so the cause is missing from the photo. The kernel's no-RTC message alone is not a proven cause: drivers/rtc/alarm.c already performed software do_settimeofday and returns that result when no RTC is installed.

UI05 changes diagnostic userspace only. Kernel zImage, uncompressed Image, vmlinux and config are copied from manifest-verified UI04. No kernel build, hardware/display/TLS changes, original system binary changes or service library substitutions.

## Boot

Enter hardware DFU, then:

```sh
cd .
python3 phase1/run.py --boot --published
python3 linux-ramtest/run.py --build T4_ANDROID_UI_05 --boot
```

Critical logcat starts before class android. It prints actual framework/native warnings and selected important tags directly to /dev/kmsg, excluding repeated Dalvik GC debug lines. Full main/system logs also rotate in RAM. Zygote is exec'd through the existing static busybox shell with stdout/stderr redirected to kmsg, preserving PID, arguments, environment and inherited property/socket descriptors.

Zygote is oneshot: if it exits, init marks it stopped without retry. This does not stop a healthy persistent Zygote or impose a boot deadline. The static monitor notices stopped, stops the critical reader, dumps the relevant native/Java error buffer once, prints the last 18 matching root-cause lines between T4_FIRST_FAILURE_SUMMARY_BEGIN/END and then waits quietly. Photograph that block, especially FATAL, Exception, Caused by or cannot/Unable. This build exposes the failure; it does not claim the still-unknown framework defect is fixed.

If actual boot_completed=1 occurs, existing HOME launch and dumpsys checks remain. Only a real visible Launcher establishes desktop success. No fake UI or pixels.

## Rebuild/check

```sh
python3 linux-ramtest/android-ui05/build.py
python3 linux-ramtest/android-ui05/test_package.py
python3 linux-ramtest/android-ui05/test_repair.py
python3 linux-ramtest/run.py --build T4_ANDROID_UI_05 --check
```

Input UI04 initramfs is pinned by manifest. Only four root overlays change: init.rc, t4-ui-watch.sh, and two new shell wrappers. Every system file, original Android init, metadata, linker/libc/ODEX remains byte-for-byte intact. All earlier artifacts are protected by hash checks.

RAM-only restrictions retained: kernel blocks native storage registrations/write/erase; no block device nodes or configured physical volumes; /data and /cache are tmpfs. No NAND/NOR/install/erase/partition changes. Original OpeniBoot and its boot commands are unchanged.

Source references: research/idroid-legacy/platform_system_core/logcat/logcat.cpp supports multiple buffers, tag filters and dump mode. init/signal_handler.c checks SVC_ONESHOT before automatic restart, and init/init.c service exec handles socket/property fd inheritance. Android 2.3.7 vm/native/dalvik_system_Zygote.c (saved under research/idroid-legacy/analysis/dalvik-2.3.7) shows system-server death can terminate its zygote parent; that is a possible chain, not proven by this photo. Full source URL: https://android.googlesource.com/platform/dalvik/+/android-2.3.7_r1/vm/native/dalvik_system_Zygote.c
