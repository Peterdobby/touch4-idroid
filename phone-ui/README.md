# Phone interface for linux-n81

[ESP-Brookesia](https://github.com/espressif/esp-brookesia) (Apache-2.0), a
phone-style launcher for LVGL 8.4, ported to Linux on the iPod: `/dev/fb0`,
the touch and button input devices, and the platform's command-line tools.
`../linux-n81` builds it into the boot image and opens it at boot.

Apps, from Espressif's phone example (Apache-2.0):

- **Music Player**: LVGL's music demo playing MP3 files from `/tmp/music`
  through `bt-audio` (headphones if connected, else the speaker); real track
  lengths, next track at the end, volume buttons. Changes in `music.patch` and
  `music/`. The spectrum is only an animation.
- **Calculator**: unchanged.
- **Settings**: the example's main and Bluetooth screens, unchanged, with new
  logic in `setting/` on top of `bt-audio`: Bluetooth on/off, search, pair,
  connect, disconnect, forget. Only the Bluetooth item is shown.

The status bar shows the network time and the Wi-Fi state. There is no battery
reading yet, so there is no battery icon.

## Build

```sh
phone-ui/fetch.sh                    # LVGL 8.4, ESP-Brookesia 0.4.2, the example apps
phone-ui/fetch-cxx.sh                # armel C++ compiler, unpacked without installing
make -C phone-ui -j8                 # PC preview: phone-ui/build/phone/phone
make -C phone-ui -j8 TARGET=device   # phone-ui/build/phone-device/phone for the iPod
```

The device build is a static armv7 binary and uses the armel libc that
`linux-n81` unpacks in `linux-n81/work/hosttools`.

Preview on the PC: `phone --shot DIR [X,Y ...]` saves the home screen, then taps
each point and saves the screen after each tap. With
`BT_AUDIO="sh $PWD/phone-ui/setting/bt-audio-stub.sh"` the Settings app talks to
a fake Bluetooth instead of `bt-audio`.

## What the platform provides

| What | How |
| --- | --- |
| Screen | `/dev/fb0`, 640x960, 32 bits |
| Touch | evdev whose name contains `multitouch` (grabbed with `EVIOCGRAB`) |
| Buttons | evdev `n81-buttons` (Home = `KEY_HOMEPAGE`) |
| Time | system clock, set from the network; time zone in `TZ` (`start-ui`) |
| Wi-Fi | `n81-wifi link`, `n81-wifi scan` |
| Bluetooth and audio | `bt-audio` |
| Sound | `n81-play -v 0..100` |
