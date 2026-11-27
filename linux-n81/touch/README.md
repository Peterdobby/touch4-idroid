# Touch on N81

**Confirmed on hardware:** the controller accepts the device's firmware (family
0x55, 15x10, bcdVersion 0x79, 5000x7500), the driver publishes a uinput device
and the interface follows the finger. `../gui/build.py` puts the driver and the
device data in `/touch` and PID 1 starts it.

`n81-touch.c` adapts the iPhone 4 driver from kpoxo6op/iphone4-linux: it runs in
user space, drives SPI1 through `/dev/mem` and publishes touches through
uinput. On N81 the controller is powered by LDO10, which OpeniBoot already
turns on; the driver only checks it and never writes to regulators.

Firmware and calibration must come from the same device:
`saved/research/touch-bringup/n81-fw/` (`zephyr2.bin`, `MtCl.bin`).

Manual run, for debugging, with Linux up:

```sh
L=linux-n81/work/hosttools/armel/usr/arm-linux-gnueabi   # libc6-dev-armel-cross, unpacked
arm-linux-gnueabi-gcc -static -O2 -march=armv7-a -B$L/lib/ -isystem $L/include -L$L/lib \
  linux-n81/touch/n81-touch.c -o linux-n81/work/n81-touch
F=saved/research/touch-bringup/n81-fw
linux-n81/shell.py --push linux-n81/work/n81-touch /tmp/n81-touch
linux-n81/shell.py --push $F/zephyr2.bin /tmp/fw.bin
linux-n81/shell.py --push $F/MtCl.bin /tmp/cal.bin
linux-n81/shell.py -c 'chmod +x /tmp/n81-touch; /tmp/n81-touch regs'
linux-n81/shell.py -c '/tmp/n81-touch serve /tmp/fw.bin /tmp/cal.bin >/tmp/touch.log 2>&1 &'
```
