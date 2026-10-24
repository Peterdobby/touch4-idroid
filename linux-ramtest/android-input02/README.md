# T4_ANDROID_INPUT_02

INPUT01 device feedback: Launcher displayed, no physical input, no ADB. The local host upload log selects INPUT01 with its expected handoff hash; it contains no post-handoff Linux/Android logs. Hardware input is still unconfirmed.

## Boot

Enter hardware DFU, then:

```sh
cd .
python3 phase1/run.py --boot --published
python3 linux-ramtest/run.py --build T4_ANDROID_INPUT_02 --boot
```

## Changes

- Preserve the proven UI07 Android init, libraries, APK/ODEX, RAM clock, software EGL and prior kernel fixes. The CPIO changes only input/watch/preflight scripts and a dedicated keylayout.
- Create or fix only the matching `t4-ram-keys` RAM `/dev/input/eventN` character node using its actual sysfs device number. Require character major13, evdev minor64..95, numeric event suffix and matching device name. Leave pre-existing non-character entries untouched. Set owner1000, group1004, mode0660 so SystemServer can open the node without relying solely on supplementary groups.
- Retain read-only GPIO polling and debouncing. Read the first eight GPIO pin states for diagnostics; key generation still uses the public-menu pins0..3. No GPIO direction/pull/reset/IRQ/clock programming.
- Render a live HUD into the first48 rows of pixel RAM after normal Android scanout. No display-controller initialization or register access. `OPEN` traverses the input handles and checks evdev specifically; VT keyboard opens are excluded.
- Add a root-only sysfs pulse accepting three bounded numeric diagnostic values in RAM. Watch sends progress before framework queries and around one Settings launch/Home return. A Settings command returning does not establish that the activity rendered.
- Initialize `evdev_read` byte count to0, including its nonblocking path used by EventHub. This is a real uninitialized C variable in the inherited source. The actual prior compiled read happens to pass the same ARM regression, so it is not established as this hardware failure's cause.
- Snapshot hashes of modified kernel source before make and assert unchanged after building. Regenerate all handoff addresses from actual ELF.

## Reading the HUD

| Field | Meaning |
|---|---|
| P | GPIO poll count; normally advancing |
| RAW | active-low pressed mask for pins0..7; low four generate keys |
| EV | key press/release edge count, not proof of Android consumption |
| REG |1 registered; negative errno means setup failed;0 means not initialized |
| OPEN | evdev handle opened; VT console excluded; expected reader is EventHub |
| HB | watch process progress; stopping can mean a blocked framework query or watcher failure |
| NODE | number of matching evdev nodes prepared in RAM |
| F | scanout/HUD frame count, not Android redraw count |
| PH |1 preframework,2 waiting,3 Settings requested,4 command returned,5 Home/dumpsys returned |

If RAW changes but EV does not, inspect actual GPIO bits and key/debounce mapping. If EV advances and OPEN=0, inspect node/permissions/EventHub open. OPEN=1 only proves an evdev handle is open, not event delivery into a focused Android activity. If P/F advance while HB stops, the kernel is still progressing and the watch may be blocked. A photo/video of the HUD while pressing Volume keys is needed to choose the next fix.

Navigation remains Volume Up/Down -> DPAD Up/Down; Home tap -> Center, hold0.8s -> Home; Power tap -> Back, hold0.8s -> Menu. Long press suppresses tap. Touch is not initialized; its N81 firmware/power/reset/calibration prerequisites remain unresolved.

## ADB finding

`kernel.config` explicitly has `# CONFIG_USB_SUPPORT is not set`. The active init.rc has no adbd service. `arch/arm/mach-s5l8930/cpu.c` also comments out the USB device platform registration. Thus this build does not implement Android USB ADB. Installing ADB on another host cannot supply the missing device-side path. OpeniBoot ACM ends at handoff and is a separate USB implementation. INPUT02 keeps USB disabled while isolating input; it does not claim to repair ADB.

## Build and offline checks

```sh
python3 linux-ramtest/android-input02/build.py
build/t4-arm-tests-venv/bin/python linux-ramtest/android-input02/test_keys_arm.py
build/t4-arm-tests-venv/bin/python linux-ramtest/android-input02/test_evdev_arm.py
build/t4-arm-tests-venv/bin/python linux-ramtest/android-input02/test_hud_arm.py
python3 linux-ramtest/android-input02/test_node_script.py
python3 linux-ramtest/android-input02/test_package.py
python3 linux-ramtest/android-input02/test_repair.py
python3 linux-ramtest/run.py --build T4_ANDROID_INPUT_02 --check
```

`build/T4_ANDROID_INPUT_02/OFFLINE-RESULTS.json` records actual checks and mock limits. The HUD ARM test checks exact glyph pixels, changing counters and writes confined to the top48 rows. Separate fb tests mock the HUD to verify the inherited full-frame RGBX/RGB565 conversion and bounds. Node script tests mock node/owner operations in an isolated temporary fixture. Evdev tests execute old/new native ARM reads and verify that OPEN excludes an active VT keyboard handle. None establish physical input or USB success.

Input-only native delta: `build/T4_ANDROID_INPUT_02/input02-only.patch`. All device runtime file/node/diagnostic changes are in RAM. No NAND/NOR/install/erase/partition/physical-storage or RTC operations.
