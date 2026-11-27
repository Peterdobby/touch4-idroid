# Mainline-based Linux on iPod touch 4G (N81AP)

Linux **6.17** on the iPod touch 4G, booted RAM-only from kDFU by a **Linux**
host, with touch, Wi-Fi, speaker audio, Bluetooth (including audio to
headphones) and an LVGL phone interface (`../phone-ui`). Nothing is written to
NAND or NOR: rebooting returns to iOS.

Everything below was confirmed on one iPod4,1 running iOS 6.1.6 (10B500).

| Feature | State | Notes |
| --- | --- | --- |
| Kernel | Linux 6.17.0-rc1 | `archeYR/linux` `apple-n90` + N81 device tree, see `modern/` |
| Display | `simpledrm`, `/dev/fb0`, 640x960 | framebuffer left by OpeniBoot |
| Buttons | Home, top, volume | GPIO; `buttons/n81-buttons` publishes them as an evdev device |
| Touch | works | user-space SPI driver, `touch/` |
| USB | serial shell (`0525:a4a7`) | survives unplug/replug with patch 0004 |
| Wi-Fi | WPA2 2.4 GHz, DHCP, joins at boot | BCM4329, `wifi/` |
| Audio | speaker, ALSA with DMA | CS42L59 codec, `audio/` |
| Bluetooth | scan, pair, A2DP sink and source | BCM4329 on UART1, BlueZ + BlueALSA, `bluetooth/` |
| Coexistence | Wi-Fi stays up during Bluetooth scans and audio | `wifi/wifi-tune.sh` |
| Phone UI | starts at boot | `../phone-ui` |
| Storage | **none** | no NAND driver: everything lives in RAM |
| Camera, battery, brightness, headphone jack, microphone | not done | |

## What you need

- A Linux PC (tested on Ubuntu 26.04, x86_64) with `arm-linux-gnueabi-gcc`,
  Python 3, libusb-1.0 and Docker (for the Bluetooth user land).
- [Legacy iOS Kit](https://github.com/LukeZGD/Legacy-iOS-Kit) checked out in
  `~/Legacy-iOS-Kit` (or set `LEGACY_IOS_KIT`), to put the device into kDFU.
- The iPod jailbroken with OpenSSH (kDFU is entered over SSH).
- Inputs this repository cannot ship, taken from **your own** device or
  firmware, under `saved/` (ignored by Git):
  - `saved/build/phase1-published/openiboot.bin` and the iBSS from this
    repository's phase 1 (see `../phase1`);
  - `saved/research/touch-bringup/n81-fw/zephyr2.bin` and `MtCl.bin`: touch
    firmware and calibration (`../tools/extract-t4-touch-firmware.py`);
  - `saved/research/wifi/`: `wifi/4329b1/loco.bin`, `loco.txt` and `macaddr`
    from the device's `/usr/share/firmware/wifi/`;
  - `saved/research/bluetooth/n81-bt.hcd`: the Bluetooth patch RAM, embedded
    in iOS's `/usr/sbin/BlueTool` (`n81-bt.addr`: optional fixed address);
  - `saved/downloads/busybox-armv7`: Alpine `busybox-static` 1.37.0-r31.
  - `saved/sources/iDroid-kernel-T4_LINUX_RAM_02/`: the iDroid 3.0 kernel
    source this repository builds (the text menu uses its `font_8x16.c`);
  - `saved/toolchain/`: GCC 4.8.5 nolibc, for the handoff stub (see
    `../docs/BUILDING.md`).
- `linux-n81/work/wifi-networks`: `NAME<tab>PASSWORD` per line. Only derived
  WPA2 keys go into the image.

## Build

```sh
mkdir -p linux-n81/work/src/linux && cd linux-n81/work/src
curl -fsSL -o linux.tar.gz https://codeload.github.com/archeYR/linux/tar.gz/8e79d535d2068ae9b9475d2e6850a6edd67fad5b
# sha256 8de3787fbc1db68b07facdbfebe4115d12b2b97bbd2f8009d88f638c118ce57a
tar -xzf linux.tar.gz -C linux --strip-components=1
cd ../../..
bash linux-n81/bluetooth/make-userland.sh   # Alpine armv7 BlueZ/BlueALSA (Docker)
make -C phone-ui -j8 TARGET=device          # optional: the phone interface
bash linux-n81/modern/build.sh               # kernel + root file system in one zImage
python3 linux-n81/modern/package.py          # payload for the RAM loader
```

The whole system is built into the kernel (xz) because the loader takes a
kernel of at most 12 MiB and an external initramfs of at most 1 MiB: OpeniBoot
copies the initramfs to `0x08000000` and the framebuffer starts at `0x08104000`.
`gui/build.py` leaves out the parts of the Bluetooth user land nothing uses.

## Boot

Once, so that a normal user can talk to OpeniBoot and to the serial gadget:

```sh
echo 'SUBSYSTEM=="usb", ATTR{idVendor}=="0525", ATTR{idProduct}=="1280", TAG+="uaccess", ENV{ID_MM_DEVICE_IGNORE}="1"
SUBSYSTEM=="usb", ATTR{idVendor}=="0525", ATTR{idProduct}=="a4a7", ENV{ID_MM_DEVICE_IGNORE}="1"
SUBSYSTEM=="tty", ATTRS{idVendor}=="0525", ATTRS{idProduct}=="a4a7", TAG+="uaccess"' | sudo tee /etc/udev/rules.d/60-ipod-linux.rules
sudo udevadm control --reload
```

With only the iPod connected (the Kit picks the device by itself), iOS running
and unlocked:

```sh
(cd ~/Legacy-iOS-Kit && bash restore.sh --kdfu)   # SSH password, then replug
linux-n81/boot.sh check
linux-n81/boot.sh openiboot   # success: OPENIBOOT_CONSOLE_CONFIRMED
linux-n81/boot.sh stage617    # uploads and checks; Linux not started yet
linux-n81/boot.sh linux617    # hands over to Linux
```

About 60 s later the serial gadget appears and the phone interface is on the
screen. To return to iOS, hold Home and the top button.

```sh
linux-n81/shell.py                    # interactive shell, Ctrl-] quits
linux-n81/shell.py -c 'uname -a'      # one command
linux-n81/shell.py --push FILE /tmp/FILE
python3 linux-n81/bluetooth/send.py IPOD_IP FILE /tmp/FILE   # faster, over Wi-Fi
```

A screenshot is `cat /dev/fb0` (640x960, BGRX).

## Layout

| Path | What |
| --- | --- |
| `modern/` | kernel build, N81 device tree, kernel options, patches |
| `gui/menu.c` | PID 1: starts the services, opens `/bin/start-ui` or a text menu |
| `gui/build.py` | the root file system built into the kernel |
| `touch/` | touch driver (user space) |
| `wifi/` | Wi-Fi tool, boot script, tuning |
| `audio/` | ALSA driver, player, bring-up tools |
| `bluetooth/` | controller tool, BlueZ/BlueALSA services, `bt-audio` |
| `buttons/` | buttons as an input device |
| `tools/qemu-trace.py` | traces iOS in qemu-ios to find register sequences |
| `build.py`, `init.S` | the first Linux 3.0 experiments (see below) |

## How the drivers were found

When a peripheral had no public driver, iOS 6.1.6 was run in the qemu-ios
emulator (the engine of [LightTouch](https://github.com/blake-lucas/LightTouch))
and every write to the device was logged (`tools/qemu-trace.py`), or values were
read with its debugger at the point where the iOS driver sends them. Reading the
disassembled kexts alone missed registers more than once.

## Linux 3.0 (earlier)

Before moving to 6.17 the same tools booted this repository's iDroid 3.0 kernel
with `../patches/kernel-n81-boot-fixes.patch` (memset, alignment, display
clocks, stop at the first Oops, NAND stack removed) and
`../patches/kernel-n81-usb-serial.patch` (S3C HSOTG serial gadget). The
framebuffer console now clears the screen and spaces lines
(`../linux-ramtest/ramfb.c`).

```sh
python3 linux-n81/gui/build.py saved/build/gui
CROSS=$PWD/saved/toolchain/gcc-4.8.5-nolibc/arm-linux-gnueabi/bin/arm-linux-gnueabi- \
  python3 linux-ramtest/build.py --rebuild-kernel --initramfs saved/build/gui/initramfs.cpio.gz
linux-n81/boot.sh openiboot && linux-n81/boot.sh stage && linux-n81/boot.sh linux
```

If `stage` fails with `ACM OUT failed: LIBUSB_ERROR_TIMEOUT`, the loader now
resets the USB connection to OpeniBoot and retries.
