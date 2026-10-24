# T4_ANDROID_UI_07 — consolidated related startup fixes

This build groups the exposed startup failures and audits related native registration rather than only changing the latest error line. UI04's tested kernel is copied byte-for-byte. Original Android init, APK/ODEX/DEX, kernel/display/TLS setup and older artifacts are preserved. Only two hash-pinned userspace DSOs receive bounded native fixes; init configuration and a small RAM-clock tool also change.

## Boot

Enter hardware DFU, then:

```sh
cd .
python3 phase1/run.py --boot --published
python3 linux-ramtest/run.py --build T4_ANDROID_UI_07 --boot
```

Markers: T4_AMS_PROPERTIES_READY=18, T4_RAM_CLOCK_READY, T4_DYNAMIC_READY_START_FRAMEWORK. Battery: UNKNOWN is expected until a real battery driver exists. A real visible Launcher is the success condition; offline checks and boot_completed alone do not prove it. First-failure capture from UI05 remains, with oneshot Zygote and a held T4_FIRST_FAILURE_SUMMARY block if framework startup fails.

## Included fixes and classification

| Evidence | Cause and treatment |
|---|---|
| AMS NumberFormatException (IMG_8196) | Retain all 18 original ADJ/MEM properties; preflight validates every integer before framework. Values match androidi4 and vendor_apple exactly. |
| BatteryService.native_update missing (IMG_8197) | Original Battery JNI returns early if /sys/class/power_supply cannot open, and JNI_OnLoad ignores failure. Continue original class/field/native registration even without the class directory. Battery update reports UNKNOWN, present=false, no AC/USB or readings; no fabricated charge value or charging control. |
| Zygote setreuid errno 2 warnings | Original setreuid/setregid JNI wrappers report errno even after successful libc calls. Both now return zero on success and the real errno on failure. Real failures are retained, not converted to success. |
| SurfaceFlinger KDSETMODE/VT_ACTIVATE EPERM | Android service lacks a controlling tty/CAP_SYS_TTY_CONFIG. Standalone SF runs as root for this RAM experiment so its existing VT fallback can use the kernel's console ioctls. Other service UIDs stay unchanged. No kernel permission checks relaxed. |
| System clock before 1970, no RTC message | Freestanding tool invokes only Linux settimeofday before framework. Epoch is build time (SOURCE_DATE_EPOCH can pin it). No RTC/alarm ioctl, device access, physical clock update or persistence. |
| DropBox NPE, installd EOF after fatal | Reporting/disconnect cascades: SystemServer creates Battery before DropBox; native installd logs EOF when the crashed client disconnects. No fake DropBox service or blanket Java exception suppression. Fix the primary crash and retain logs if anything remains. |
| Missing sensor HAL / fb sleep-wake sysfs | Unsupported hardware features. Source has an empty sensor-list path and SF falls back to VT with mCanDraw/mScreenAcquired true. These messages may remain; they are not evidence of JNI signature mismatch. No sensor, suspend, LCD, audio, WiFi or storage driver work is added. |

## Batch native verification

research/runtime-analysis/server_jni_audit.py runs the actual original/patched ARM/Thumb JNI_OnLoad and registration/update code. It validates 9 server JNI groups, 59 native signatures and 84 cached method/field IDs against actual core/framework/services DEX, including native/static/instance flags and inherited members. The original failure reproduces as 8 registrations when power_supply is absent. The patched library registers 9; existing empty-directory behavior is unchanged. Battery values are checked as unknown/not present, with no device reads.

Additional actual ARM tests exercise both original and patched Zygote identity wrappers: successful libc return with errno=2 reproduces the original false warning; patched return is zero; EPERM/ENOENT/EINVAL failures remain errors. Arguments, callee-saved registers and stack are checked. The software-clock ELF is executed with an explicit syscall model; only settimeofday, stdout write and exit occur. Invalid epochs/failed calls are tested. These are interface mocks, not a full live Dalvik or hardware boot.

## Rebuild/check

```sh
python3 linux-ramtest/android-ui07/build.py
build/t4-arm-tests-venv/bin/python linux-ramtest/android-ui07/test_bundle.py
build/t4-arm-tests-venv/bin/python linux-ramtest/android-ui07/test_zygote_ids.py
python3 linux-ramtest/android-ui07/test_ams_properties.py
python3 linux-ramtest/android-ui07/test_package.py
python3 linux-ramtest/android-ui07/test_repair.py
python3 linux-ramtest/run.py --build T4_ANDROID_UI_07 --check
```

For byte-identical clock input during rebuild, set SOURCE_DATE_EPOCH to the integer saved in build/T4_ANDROID_UI_07/ram-clock-epoch. Clock seed is build time and intentionally volatile.

## Reproducible native compatibility

native_compat.py verifies exact original DSO SHA256, instruction bytes and sizes before patching. Battery change is two Thumb instructions and one recovery log string; field/native registration and actual update code remain original. Zygote changes occupy only the two original 32-byte wrappers; replacements are assembled from zygote-id-fix.S and keep JNI table/function addresses, ELF layout and prelink footer. Source-level return/control-flow equivalents are supplied in battery-source-equivalent.patch and zygote-id-source-equivalent.patch. The existing firmware DSOs are reused, not claimed to be a fresh full Android/AOSP build. The assembly omits an unnecessary initial errno reset while preserving corrected return semantics.

Artifacts: native-compat.json, jni-audit.json, bundle-test.json, zygote-ids-arm-test.json, compatibility-audit.json and userspace-bundle.patch under build/T4_ANDROID_UI_07. Full originals under build/android-prepared/system-root remain untouched.

## RAM-only restrictions

No NAND/NOR writes, installation, erase, partition changes, persistent system/data images or RTC writes. Kernel storage registration/write/erase stubs remain verified; no physical block devices/volumes configured. Original system files and patched DSOs are packed into RAM CPIO; /data and /cache are tmpfs. Root SF permission is scoped to this experimental RAM build. Physical battery/charging/thermal monitoring is not implemented or represented as working. Hardware desktop status remains pending user verification.
