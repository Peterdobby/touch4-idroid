#!/bin/sh
# Runs on the iPod at boot: load the BCM4329, join a known network, get an address.
exec >/tmp/wifi.log 2>&1
cd /lib/wifi || exit 1
for m in cfg80211 brcmutil; do insmod $m.ko || exit 1; done
# Coexistence with Bluetooth on the shared antenna: bcom.btc.params from this
# model's iOS device tree (index,value pairs).
insmod brcmfmac.ko btc_params=6,65,8,45000,9,15000,10,20000 || exit 1
insmod brcmfmac-wcc.ko || exit 1
wlan-power on || exit 1
insmod sdhci-pltfm.ko && insmod sdhci-s5l8930.ko fixed=1 max_mhz=12 single_block=1 || exit 1
n=0
while [ ! -e /sys/class/net/wlan0 ] && [ $n -lt 30 ]; do sleep 1; n=$((n + 1)); done
[ -e /sys/class/net/wlan0 ] || { echo "no wlan0"; exit 1; }
ifconfig wlan0 up
[ -s /etc/wifi-networks ] || { echo "no network configured"; exit 0; }
n=0
until n81-wifi join /etc/wifi-networks; do
	n=$((n + 1))
	[ $n -lt 10 ] || { echo "gave up connecting"; exit 1; }
	sleep 5
done
# power saving, beacon and roaming settings as iOS sets them (Bluetooth shares the antenna)
wifi-tune
udhcpc -i wlan0 -s /lib/wifi/udhcpc.sh -b -p /tmp/udhcpc.pid
# no battery-backed clock here: set the time from the network, if reachable
ntpd -n -q -p a.st1.ntp.br &
echo "wifi ready"
