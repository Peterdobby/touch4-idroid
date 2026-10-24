# T4_ANDROID_INPUT_01

UI07 Launcher is visible in the user's IMG_8199.jpeg. Physical input has not been verified. Its native board file had GPIO key and SPI touch registration commented out. This isolated kernel adds a polling evdev driver instead of activating unverified GPIO IRQ configuration.

## Boot

Enter hardware DFU, then:

```sh
cd .
python3 phase1/run.py --boot --published
python3 linux-ramtest/run.py --build T4_ANDROID_INPUT_01 --boot
```

## Temporary navigation map

| Physical action | Android action |
|---|---|
| Volume Up / Down | DPAD Up / Down |
| Home tap, released | DPAD Center |
| Home held about 0.8 seconds | Home |
| Power tap, released | Back |
| Power held about 0.8 seconds | Menu |

Volume functions are deliberately remapped only in this test. No touch or power/suspend behavior is implemented. Long hold suppresses the tap action. Keys already held at handoff are suppressed until released. Volume repeats use the input core. GPIO samples every 20 ms, debounce two samples.

## Evidence for pins and Android path

- `t4-menu/public-overlay/menu.c:pressed/poll`: tested public RAM menu reads physical `0xbfa00000 + pin*4`, pins 0,1,2,3, active low.
- `research/openiBoot-c5cee8c/plat-a4/buttons.c:buttons_is_pushed`, hardware/buttons.h and gpio.c: matching semantics.
- UI04 board `mach-ipodtouch4g.c:buttons`: unused Home definition was pin7 and had no active_low field. It remains untouched; the old driver is not activated.
- `cpu.c:s5l8930_iodesc` already maps PA_GPIO to VA_GPIO; `t4-keys.c` only performs raw reads of four existing registers. No GPIO direction, pull, interrupt, reset or clock changes.
- `research/idroid-legacy/platform_frameworks_base/libs/ui/EventHub.cpp:openDevice` recognizes EV_KEY and loads a layout matching the input device name. `t4-ram-keys.kl` maps the exported scan codes.
- Existing original ueventd rule `/dev/input/* 0660 root input` retained. New node is created by evdev/ueventd coldboot; no physical block nodes added.
- Driver status: `/sys/class/input/input*/t4_status`, read-only. Bounded event logs are in the kernel ring. Watch saves device list, node permissions, dumpsys input and polling counters to `/data/local/tmp/t4-input-*` in RAM.

## Touch blockers found locally

The old `zephyr2` SPI board registration is commented out. Its `mt_power` callback is empty. `drivers/input/touchscreen/zephyr2.c:zephyr2_probe` requires `zephyr2.bin`, which is absent from the prepared androidi4 system; neither ZEPHYR symbol is enabled in the proven kernel config. `zephyr2_setup` calls power(0) twice despite its off/on comment; do not treat that driver as complete. Embedded calibration and reset/IRQ wiring still need N81 verification. No SPI touch initialization or firmware upload is attempted in INPUT01.

## Build and checks

```sh
python3 linux-ramtest/android-input01/build.py
build/t4-arm-tests-venv/bin/python linux-ramtest/android-input01/test_keys_arm.py
python3 linux-ramtest/android-input01/test_package.py
python3 linux-ramtest/android-input01/test_repair.py
python3 linux-ramtest/run.py --build T4_ANDROID_INPUT_01 --check
```

The build compiles the isolated native kernel and regenerates all handoff addresses from its actual ELF. It pins UI07 CPIO and all DSO/clock payload bytes; only the watch script changes and a dedicated keylayout is added. The watch no longer injects MENU automatically. Original userspace init, libraries, APK/ODEX files and display/TLS fixes are retained.

`build/T4_ANDROID_INPUT_01/input-only.patch` is the input-only native source delta. `OFFLINE-RESULTS.json` records completed tests. GPIO test uses simulated registers; physical keys, clocks and touch remain hardware test questions. The inherited modpost section mismatch warning was also present in UI04.

No NAND/NOR/install/erase/partition/storage or physical RTC operations. UI07 artifacts and source remain unchanged.
