# Audio on N81

**Works (heard on hardware):** the speaker, through an ALSA driver with DMA
(`driver/snd-n81.c`): S16_LE stereo 44.1 kHz, volume in "Speaker Playback
Volume". No headphone jack and no microphone yet.

- `driver/build.sh` builds the ALSA core, OSS emulation, the driver and
  `n81-play`; `modern/build.sh` calls it and builds everything into the image.
- At boot PID 1 runs `sound-up`, which loads the modules.
- `n81-play FILE.wav` | `-t` (test scale) | `-v 0-100`.
- `beep.c` is the PIO test, without ALSA, used to find the sequence.

DMA: CDMA at `0x87000000`, channel `0x1a` (`+0x1a000`); bit 26 of `0x87000000`
enables the channel (before any access to it), configuration `0x000400a6`,
destination `0x84500410`, control `0x11` starts, `0x14` aborts (bit `0x200000`
confirms), `0x02` resets. 32-byte descriptors `{next, 3, address, size}` in a
ring; the DMA sees RAM at `0x40000000`. A first version of the driver (reset
before enabling the channel, control `0x19`, abort `0x1c`) hung the device; it
was not isolated which of the three caused it.

## How it works

- Cirrus CS42L59 codec on I2C0 `0x4a`. It is the I2S **master**; the rate is in
  register `0x0a` (`0x0b` = 44.1 kHz, `0x13` = 22.05 kHz).
- I2S0 at `0x84500400`, PMGR gate `0xbf101094` (off after boot).
- **`0x84500810` = `0x28000300`** turns on the codec clock. Without it the
  codec produces no BCLK/LRCK and the FIFO does not move. Idle: `0x20000300`.
- `TXCON=0x03100099`, `RXCON=0x1000`, `CLKCON=0x181`, `TXCOM=6`; one 16-bit
  sample per write at `+0x10`; FIFO level at `+0x3c`, bits 7-11.
- The PMGR NCO is **not** used (iOS does not program it on this device).
- Speaker amplifier: GPIO 161 = `0x203` playing, `0x202` stopped.
- Codec volumes `0x1d`-`0x22`: `0x40` is mute; speaker at `0x21` (`0x78` =
  -4 dB, the maximum iOS uses).
- There is no separate I2C amplifier on this model.

## Where the sequence came from

From iOS 6.1.6 itself, running in the qemu-ios emulator (the engine of
`github.com/blake-lucas/LightTouch`, release v0.0.15) with every codec and MMIO
write logged: `../tools/qemu-trace.py`. It runs in a container
(`../tools/qemu-trace.Dockerfile`) without network, after preparing the
emulated device with that release's `firmwarekit create` from Apple's IPSW. The
work folder is mounted at `/lab` with `app/` (the extracted AppImage) and `dev/`
(the prepared device). For another peripheral, adjust the script's `keep`
filter.

Reading the registers from the disassembled kext alone was not enough: it missed
`0x84500810` and part of the codec writes.
