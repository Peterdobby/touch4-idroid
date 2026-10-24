# T4_ANDROID_UI_06 — restore ActivityManager memory properties

IMG_8196 gives the first real framework failure: system_server reaches Power Manager and Activity Manager, then ActivityManagerService.<clinit> throws NumberFormatException reading an empty integer. The local legacy ActivityManagerService.java line 371 reads ro.FOREGROUND_APP_MEM; all nine ro.*_MEM keys were omitted from the simplified RAM init.rc. The nine ADJ keys were already present. Both original androidi4 ramdisk init.rc and old iDroid vendor_apple/common/init.rc contain identical values.

UI06 restores those nine original thresholds (in 4 KiB pages): foreground 2048, visible 3072, perceptible/heavy 4096, secondary/backup/home 6144, hidden 7168, empty 8192. The preflight reads all 18 required properties through real original getprop before allowing t4.dynamic.ready=1; numeric nonempty values are required and MEM values must be positive. It prints T4_AMS_PROPERTIES_READY=18 on success. No original Java, ODEX, APK, init ELF or kernel binary is patched.

## Boot

Enter hardware DFU, then:

```sh
cd .
python3 phase1/run.py --boot --published
python3 linux-ramtest/run.py --build T4_ANDROID_UI_06 --boot
```

Look for T4_AMS_PROPERTIES_READY=18 followed by framework startup. Actual desktop still requires real visible Launcher. If another failure appears, first-failure capture from UI05 remains enabled: photograph the T4_FIRST_FAILURE_SUMMARY_BEGIN/END block. A healthy zygote is not timed out; an exited one is held without automatic retry.

## Build/check

```sh
python3 linux-ramtest/android-ui06/build.py
python3 linux-ramtest/android-ui06/test_ams_properties.py
python3 linux-ramtest/android-ui06/test_package.py
python3 linux-ramtest/android-ui06/test_repair.py
python3 linux-ramtest/run.py --build T4_ANDROID_UI_06 --check
```

Native source/ELF/image/config are pinned to hardware-tested UI04. Compared with tested UI05, only init.rc and sbin/t4-dynamic-probe.sh change. Original Android system files, metadata, init, linker/libc, all 413 ODEX dependency references and every old successful artifact stay intact. File hashes and all storage entry stubs are checked by build/tests.

Regression: test_ams_properties.py derives requirements from ActivityManagerService source, reproduces empty integer conversion from UI05, verifies actual services.odex contains all required property names, matches both original init.rc references, and checks values are set before starting preflight/framework. This is an offline configuration regression; it does not claim hardware desktop success.

RAM-only rules unchanged: no NAND/NOR/install/erase/partition operations; no physical block devices/volumes configured; /data and /cache tmpfs. The added setprop actions update Android RAM properties, with no lowmemorykiller driver, RTC, display or hardware initialization changes.

Evidence: experiments/android-ui05-ams-missing-memory-properties/IMG_8196.jpeg. Root source delta: build/T4_ANDROID_UI_06/ams-properties.patch. Actual references: research/idroid-legacy/platform_frameworks_base/services/java/com/android/server/am/ActivityManagerService.java:346–379, research/idroid-legacy/vendor_apple/common/init.rc:193–213 and build/android-prepared/ramdisk-text/init.rc:193–213.
