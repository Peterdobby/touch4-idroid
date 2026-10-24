# T4_ANDROID_INPUT_03

Hardware INPUT02 feedback: idle RAW=b0; Home=b1, Power=b2, VolumeUp=b4, VolumeDown=b8; EV increases, OPEN=1, PH=3 and Settings visible. This establishes GPIO mapping, software edge generation and an opened evdev handle. It does not establish EventHub event consumption or focused-window delivery.

PH3 in INPUT02 is exactly the point before `/system/bin/am start -W -a android.settings.SETTINGS`. Its caller had not advanced to the later Home command. Visible Settings shows that an activity could render, but does not establish why its start-and-wait completion remained blocked.

## Boot

Enter hardware DFU, then:

```sh
cd .
python3 phase1/run.py --boot --published
python3 linux-ramtest/run.py --build T4_ANDROID_INPUT_03 --boot
```

The HUD still says IN02 because its native kernel is pinned byte-for-byte. No GPIO, driver, display, timer or kernel entry changes are made.

## Changed userspace only

Replace the watch script and add one shell supervisor. Remove the automatic Settings launch, `am -W`, and synchronous `input keyevent` call. Request HOME without `-W`. Run all Android diagnostic commands under bounded supervision, keeping the RAM diagnostic heartbeat advancing while waiting. On deadline send TERM and then KILL to the specific spawned child and reap it; watcher cancellation also cleans that child. Android shell wrappers use exec app_process, so the supervised PID is retained. Kernel tasks in an uninterruptible wait cannot be made cancellable by a shell timeout; no physical success is inferred from host tests.

Use original `svc power stayon true` to acquire a temporary full wake lock and set Android's keep-awake-while-powered setting. The setting is in RAM `/data`; no physical battery/power-register or RTC implementation is added. This tests a logical screen-off confound with the inherited display kept physically lit. It is not established as the physical input failure's cause.

Temporary files: `/data/local/tmp/t4-stayon.txt`, `t4-home.txt`, `t4-input-framework.txt`, `t4-window.txt`, `t4-power.txt`, `t4-command-status.txt`; all RAM. PH2 waits for boot property,3 stay-awake,4 Home,5 dumpsys,8 all supervised commands returned,9 a timeout or boot property not confirmed. PH8 does not assert successful UI input.

Navigation mapping is unchanged: Volume Up/Down navigate, short Home confirms, long Home returns Home, short Power returns Back, long Power opens Menu. Touch and ADB remain disabled as documented in INPUT02.

## Build/check

```sh
python3 linux-ramtest/android-input03/build.py
python3 linux-ramtest/android-input03/test_bounded.py
python3 linux-ramtest/android-input03/test_bundle.py
python3 linux-ramtest/android-input03/test_package.py
python3 linux-ramtest/android-input03/test_repair.py
python3 linux-ramtest/run.py --build T4_ANDROID_INPUT_03 --check
```

The bundle test verifies actual kernel/Image/vmlinux/config and Android DSO/clock/init byte equality with INPUT02. Exactly one previous CPIO file changes and one guard file is added; all other bytes/modes/owners remain unchanged. The supervisor test runs harmless real host subprocesses, including a TERM-ignoring stalled child, and checks return codes, deadline kill/reap, ongoing pulse and cancellation cleanup. Native tests were already completed for the identical INPUT02 kernel. Mock USB protocol tests pass all five stage/boot/refusal cases and do not test Android USB.

No prior artifacts overwritten; no NAND/NOR/install/erase/partition/physical-storage or physical RTC operations. Hardware control result pending.
