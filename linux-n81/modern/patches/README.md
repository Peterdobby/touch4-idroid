0001 and 0003 are copied unchanged from kpoxo6op/iphone4-linux
`kernel/n90-display-power/` (commit c137e1e). The backlight patch is
deliberately not used.

0004 lets the serial gadget survive unplugging the cable (dwc2 did not return
to L0 on USB reset).

0005-0008 are `kernel/n90-wifi/0001-0004` from the same repository (renamed).

0009 retries wpa_auth with PSK only on firmware 4.221.54.26.

0010 falls back to numbered ioctls for wpa_auth, wsec and auth.

0011 avoids a fast control lookup that the old ALSA core here does not support.

0012 keeps the S5L8930 UART clock-source bit (UCON bit 10) that the driver
cleared.

0013 sends the Bluetooth coexistence parameters (`btc_params`) from the iOS
device tree to the Wi-Fi firmware.
