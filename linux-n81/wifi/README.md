# Wi-Fi on N81

**Confirmed on hardware:** BCM4329 with the device's `loco` firmware
4.221.54.26, WPA2 2.4 GHz, DHCP, ping and DNS; the PC reaches the iPod over the
network. About 6 ms to the router with power saving off.

BCM4329b1 on SDIO. Driver patches and the tool come from
kpoxo6op/iphone4-linux `kernel/n90-wifi`; patches 0009 and 0010 are needed for
this firmware (`minioctl`). Firmware and NVRAM are the device's own
(`/usr/share/firmware/wifi/4329b1/loco.*`), kept out of Git.

Networks go in `linux-n81/work/wifi-networks` (`NAME<tab>PASSWORD`, 2.4 GHz,
WPA2). `modern/build.sh` builds the drivers, firmware and derived keys into the
kernel, and `wifi-up.sh` joins at boot without a PC. `wifi-tune.sh` then applies
the power-saving, beacon and roaming settings iOS 6.1.6 sends to the firmware
(read with the qemu-ios debugger), which keep Bluetooth audio from cutting out.
`up.py` is only for debugging.

The connection sometimes drops on its own; `n81-wifi join /etc/wifi-networks`
reconnects.
