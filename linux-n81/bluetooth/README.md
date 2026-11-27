# Bluetooth on N81 (BCM4329 on UART1)

**Works on hardware:** the iPod shows up as `iPod-Linux`; a phone pairs and
plays through the speaker (A2DP sink, SBC 44.1 kHz), and the iPod pairs with
headphones and plays to them (A2DP source), both from the phone interface's
Settings and from the shell (`bt-audio`). Wi-Fi stays connected.

- Patch RAM: "BCM4329B1 ... Olympic Loco N81 Module", 101 `0xfc4c` + `0xfc4e`
  commands embedded in iOS 10B500's `/usr/sbin/BlueTool`. Put it in
  `saved/research/bluetooth/n81-bt.hcd`. Without it scans find nothing.
- User land: `make-userland.sh` builds an Alpine 3.20 armv7 tree with D-Bus,
  BlueZ 5.76, BlueALSA and mpg123 (Docker); `../gui/build.py` builds it into the
  kernel as `/alp`, leaving out the programs nothing runs.
- At boot `bt-boot` waits for Wi-Fi, loads the modules, brings the controller up
  at 1.5 Mbit/s (`n81-bt up`) and runs `bt-services` (D-Bus, bluetoothd,
  BlueALSA, a pairing agent, speaker output).
- `bt-audio scan | power [on|off] | paired | connect|disconnect|forget ADDRESS |
  current | volume up|down | play FILE...` is what the phone interface uses.
  `play` goes to the connected headphones, else the speaker.
- While services run, anyone in range can pair (`bt-accept` answers yes).

## Hardware notes

- UART1 `0x82600000`, IRQ 0x17; gate `0xbf1010d4` already on.
- `UCON` needs bit 10 (clock source, as iBoot leaves it); with 24 MHz and
  divisor 12 that gives 115200. The kernel driver cleared it: patch 0012.
- The device tree needs `clk_uart_baud0` on UART1; without it the driver does
  not change speed and does not say so.
- Reset on GPIO 8, wake on GPIO 7, RTS on GPIO 56 low.
- Answers from ROM without firmware: Broadcom, Bluetooth 2.1.

## Coexistence with Wi-Fi (shared antenna)

- What keeps Wi-Fi up during a scan is `bcn_timeout` in the Wi-Fi firmware; the
  default is 2 s and a scan holds the antenna for more than 10 s.
- `../wifi/wifi-tune.sh` applies the values iOS 6.1.6 sends (`PM 2`,
  `bcn_timeout 8`, `pm2_*`, `assoc_listen 15`, roaming), read with the qemu-ios
  debugger in AppleBCMWLAN's send function. Packet loss during a scan fell from
  16% to 4-8%. With power saving off A2DP cut out (35 kB/s instead of 44.5).
- The `btc_params` from the device tree are sent too (patch 0013); alone they
  were not enough. `btc_mode` returns -52 on this firmware.
- Alpine's BlueALSA (4.2.0 and 4.3.1) runs off its stack when looking up
  FDK-AAC with a near-empty environment; `bt-services` pads the environment.
