#!/bin/sh
# Turn Bluetooth on if needed and list nearby discoverable devices.
if [ ! -d /sys/class/bluetooth/hci0 ]; then
	cd /lib/bluetooth || exit 1
	for m in ecc ecdh_generic bluetooth btintel hci_uart; do
		grep -q "^$m " /proc/modules || insmod $m.ko || exit 1
	done
	n81-bt up || exit 1
fi
n81-bt visible
echo "searching (about 10 s)..."
n81-bt scan
# the link normally survives (wifi-tune); rejoin only if it did not
if ! n81-wifi link 2>/dev/null | grep -q '^connected'; then
	echo "reconnecting Wi-Fi..."
	n81-wifi join /etc/wifi-networks >/dev/null 2>&1
fi
