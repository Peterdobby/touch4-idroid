# T4_ANDROID_TOUCH_02

Build locally without accessing USB or recompiling the booted TOUCH01 kernel:

```sh
python3 linux-ramtest/android-touch02/build.py
```

Output: `build/T4_ANDROID_TOUCH_02/`. The builder verifies the pinned TOUCH01
manifest, reproduces its handoff byte for byte, and retains its exact kernel,
configuration, core patches, Android libraries, startup configuration, and ADB.
It changes only these RAM archive entries:

- `/sbin/t4-touch-input`: IRQ-ready real-frame polling, FIFO50, correct ARM signal
  return, and checked uinput event writes.
- `/sbin/t4-zygote.sh`: preload the guarded RAM framebuffer power compatibility
  library before Android changes UID.
- `/system/usr/keylayout/t4-ram-keys.kl`: physical Home, Power, Menu, volume mapping.
- `/sbin/t4-ram-power.so`: added guarded display ON fallback for the exact TOUCH
  RAM images when the inherited framebuffer exists and both power ABIs are absent.

The helper is rebuilt with the new archive CRC and length and the TOUCH02 command
line; the verified upload protocol is reused. `cpio-overlay-validation.json` and
`manifest.json` record what changed and the preserved artifact hashes. Every
other CPIO record is retained byte for byte; block device nodes are rejected.
Existing TOUCH01, published OpeniBoot, and ADB01 files are not overwritten.

Live RAM overlay testing briefly operated the Android desktop, then touch
stalled again. A fresh TOUCH02 RAM boot and sustained touch/button use still
require physical verification. This build does not claim that work complete.
