#!/usr/bin/env python3
"""Bring up Wi-Fi on the running iPod over the USB serial shell.

Pushes the driver modules, this device's firmware and the tool to RAM, powers
the BCM4329, scans, joins the first known network and requests an address.
Passwords stay on the host: only the derived WPA2 keys are copied.

  up.py            everything
  up.py scan       load and scan only
"""
import hashlib
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
SHELL = ROOT / 'linux-n81/shell.py'
WORK = ROOT / 'linux-n81/work'
FIRMWARE = ROOT / 'saved/research/wifi'
NETWORKS = WORK / 'wifi-networks'
MODULES = ('cfg80211', 'brcmutil', 'brcmfmac', 'brcmfmac-wcc', 'sdhci-pltfm', 'sdhci-s5l8930')
UDHCPC = '''#!/bin/sh
case "$1" in
deconfig) ifconfig $interface 0.0.0.0 up ;;
bound|renew)
    ifconfig $interface $ip netmask ${subnet:-255.255.255.0}
    for r in $router; do route add default gw $r dev $interface; break; done
    : > /tmp/resolv.conf
    for d in $dns; do echo "nameserver $d" >> /tmp/resolv.conf; done
    mkdir -p /etc && cp /tmp/resolv.conf /etc/resolv.conf ;;
esac
'''


def device(command, timeout=60, check=True):
    result = subprocess.run([sys.executable, str(SHELL), '--timeout', str(timeout), '-c', command])
    if check and result.returncode:
        sys.exit(f'device command failed ({result.returncode}): {command}')
    return result.returncode


def push(content, remote):
    with tempfile.NamedTemporaryFile() as f:
        f.write(content)
        f.flush()
        subprocess.run([sys.executable, str(SHELL), '--push', f.name, remote], check=True, timeout=300)


def keys():
    lines = []
    if NETWORKS.is_file():
        for line in NETWORKS.read_text().splitlines():
            if line.startswith('#') or '\t' not in line:
                continue
            ssid, password = line.split('\t', 1)
            key = hashlib.pbkdf2_hmac('sha1', password.encode(), ssid.encode(), 4096, 32)
            lines.append(f'{ssid}\t{key.hex()}\n')
    return ''.join(lines).encode()


def load():
    if device('test -e /sys/class/net/wlan0', check=False) == 0:
        return
    device('mkdir -p /tmp/wifi /lib/firmware/brcm')
    for name in MODULES:
        push((WORK / f'modules/{name}.ko').read_bytes(), f'/tmp/wifi/{name}.ko')
    push((FIRMWARE / 'wifi/4329b1/loco.bin').read_bytes(), '/lib/firmware/brcm/brcmfmac4329-sdio.bin')
    nvram = (FIRMWARE / 'wifi/4329b1/loco.txt').read_text().rstrip('\n')
    nvram += '\nmacaddr=' + (FIRMWARE / 'macaddr').read_text().strip() + '\n'
    push(nvram.encode(), '/lib/firmware/brcm/brcmfmac4329-sdio.txt')
    push((WORK / 'n81-wifi').read_bytes(), '/tmp/wifi/n81-wifi')
    push(UDHCPC.encode(), '/tmp/wifi/udhcpc.sh')
    device('cd /tmp/wifi && chmod +x n81-wifi udhcpc.sh && '
           'for m in cfg80211 brcmutil brcmfmac brcmfmac-wcc; do insmod $m.ko || exit 1; done')
    # Chip power is PMU GPIO register 0x58, bit 1 (the tool prints before/after).
    push((WORK / 'wlan-power').read_bytes(), '/tmp/wifi/wlan-power')
    device('chmod +x /tmp/wifi/wlan-power && /tmp/wifi/wlan-power on')
    device('cd /tmp/wifi && insmod sdhci-pltfm.ko && '
           'insmod sdhci-s5l8930.ko fixed=1 max_mhz=12 single_block=1')
    device('n=0; while [ ! -e /sys/class/net/wlan0 ] && [ $n -lt 30 ]; do sleep 1; n=$((n+1)); done; '
           'dmesg | grep -iE "sdhci|mmc|brcm|wl0" | tail -n 15; test -e /sys/class/net/wlan0')


def main():
    load()
    device('ifconfig wlan0 up && /tmp/wifi/n81-wifi scan')
    if 'scan' in sys.argv[1:]:
        return
    known = keys()
    if not known:
        sys.exit(f'no network configured; add "NAME<tab>PASSWORD" to {NETWORKS}')
    push(known, '/tmp/wifi/networks')
    device('/tmp/wifi/n81-wifi join /tmp/wifi/networks && sleep 2 && /tmp/wifi/n81-wifi link', 90)
    # With power saving on, pings took up to 2 s; off, 6 ms to the router.
    device('/tmp/wifi/n81-wifi power off')
    device('udhcpc -i wlan0 -s /tmp/wifi/udhcpc.sh -n -q -t 8 && ifconfig wlan0 && route -n', 90)
    device('ping -c 3 -W 3 1.1.1.1; ping -c 2 -W 3 example.com', 60, check=False)


if __name__ == '__main__':
    main()
