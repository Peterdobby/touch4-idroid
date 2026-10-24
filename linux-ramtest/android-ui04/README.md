# T4_ANDROID_UI_04 — fix the UI03 kernel vector-page write fault

IMG_8191 is a kernel Oops, not Android startup: PC c002a204 is UI03 __switch_to STR to ffff0ff0; that high vector page is mapped read-only. UI03's offline test mistakenly made it writable. The exact protected write now reproduces in the revised native ARM test, including the identical PC. The arm_syscall TLS store is affected too.

UI04 stores the legacy TLS word through vectors_page + 0xff0, the allocated page's existing writable linear alias, followed by DSB. Both hardware TLS and legacy direct readers remain supported. The high vector PTE and all MMU/display/clock initialization stay unchanged. N81 UP-only guards retained. The revised test maps one shared RAM page at RW linear and RX high addresses, exercises the actual emitted syscall and repeated context switches, checks both TLS views and surrounding page guards, and verifies high permissions stay RX. Only the notifier callback is mocked; actual ARM caches still require device validation.

## Boot from hardware DFU

```sh
cd .
python3 phase1/run.py --boot --published
python3 linux-ramtest/run.py --build T4_ANDROID_UI_04 --boot
```

The entire Android initramfs is pinned byte-for-byte to UI03. No new userspace variables are introduced during this kernel regression repair; init.rc may retain a UI03 marker. Look for T4_DYNAMIC_PROBE_EXIT=0, T4_DYNAMIC_SETPROP_EXIT=0, T4_DYNAMIC_READY_START_FRAMEWORK. These only confirm dynamic preflight; actual desktop success requires visible Launcher. If stopped, photograph the final Oops/T4_USER_FAULT or Android error.

## Rebuild and offline check

```sh
python3 linux-ramtest/android-ui04/build.py
python3 linux-ramtest/android-ui04/test_package.py
python3 linux-ramtest/android-ui04/test_repair.py
build/t4-arm-tests-venv/bin/python linux-ramtest/android-ui04/test_tls_arm.py
python3 linux-ramtest/run.py --build T4_ANDROID_UI_04 --check
```

Native kernel source: sources/iDroid-kernel-T4_ANDROID_UI_04. Precise two-file diff from UI03: build/T4_ANDROID_UI_04/vectors-page-alias.patch. Previous UI03, UI01, INIT04 and public OpeniBoot files preserved; build manifest pins and rechecks their hashes.

RAM-only: original Android system/Launcher2/linker/libc and original init preserved. /data and /cache tmpfs, storage driver registrations and write/erase stubs verified. No physical block device nodes or persistent volumes. USB loader uploads only fixed RAM ranges. Existing CRC acceleration/progress retained. No NAND/NOR writes, installation, formatting or repartitioning.

Hardware status pending. Offline instruction/mapping tests cannot establish real desktop success.
