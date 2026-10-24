# T4_ANDROID_INIT_03: restore proven early boot visibility

INIT02 hardware result: user reports screen remains at #15. INIT02 removed checkpoints 16–24, temporary diagnostic mappings and the pre-paging native console call. Therefore #15 alone does not establish the exact failed function.

This repair copies and hash-checks the exact INIT02 kernel and initramfs. No kernel or Android userspace source is rebuilt or changed. It restores INIT01's executable checkpoint adapters and identical diagnostic mapping function. ELF symbols and original ARM instructions determine every changed native target. It also NOPs the later duplicate call to t4_ramfb_console_init, so the same console is registered once.

## Build/check

```sh
python3 linux-ramtest/android-init03/build.py
python3 linux-ramtest/android-init03/test_repair.py
build/t4-arm-tests-venv/bin/python linux-ramtest/android-init03/test_memset_arm.py
build/t4-arm-tests-venv/bin/python linux-ramtest/android-init03/test_probe_arm.py
python3 linux-ramtest/run.py --build T4_ANDROID_INIT_03 --check
```

Requires existing pinned build/T4_ANDROID_INIT_02 inputs. To rebuild those from isolated source use linux-ramtest/android-init02/build.py first.

## Boot from hardware DFU

```sh
python3 phase1/run.py --boot --published
python3 linux-ramtest/run.py --build T4_ANDROID_INIT_03 --boot
```

With public OpeniBoot already running, execute only the last command.

## Evidence

Restored markers 16 (kernel entry), 17 (CPU lookup), 18 (ATAG verification), 19 (page tables and temporary mappings), 20 (virtual execution), 21 (start_kernel), 22 (setup_arch), 23 (early parameters/native console next), 24 (native console ready). Marker 24 is a printk line. After it, normal Linux/Android init messages own the screen.

Goal: ANDROID_INIT_ENVIRONMENT_CONFIRMED and repeated ANDROID_INIT_SERVICE_REACHED. Hardware result is PENDING. If it stops again, photograph the complete last marker/line; the exact native failure is not yet established by the INIT02 observation.

No NAND/NOR/partition/install/erase operations. Original seven native storage registration/write/erase stubs retained. Prior successful binaries preserved.
