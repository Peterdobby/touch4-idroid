#!/bin/sh
# At boot, when the image carries /alp: Bluetooth on, discoverable, audio out of
# the speaker.
[ -x /alp/usr/lib/bluetooth/bluetoothd ] || exit 0
exec >/tmp/bt-boot.log 2>&1
# after Wi-Fi, so its power saving can be switched on (shared antenna)
n=0
while ! grep -qE 'wifi ready|no network|no wlan0|exit' /tmp/wifi.log 2>/dev/null && [ $n -lt 90 ]; do
	sleep 1; n=$((n + 1))
done
sound-up
cd /lib/bluetooth || exit 1
for m in af_alg algif_hash algif_skcipher algif_aead ecc ecdh_generic bluetooth btintel hci_uart; do
	grep -q "^$(echo $m | tr - _) " /proc/modules || insmod $m.ko
done
timeout 40 n81-bt up 1500000 1 || exit 1
bt-services
