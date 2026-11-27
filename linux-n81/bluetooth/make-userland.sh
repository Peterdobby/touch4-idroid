#!/bin/bash
# Build the Alpine armv7 Bluetooth userland (D-Bus, BlueZ, BlueALSA) in a
# container, as saved/research/bluetooth/userland.tar.gz (not in
# Git). Alpine 3.20: BlueZ 5.76, bluez-alsa 4.2.0.
set -euo pipefail
OUT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)/saved/research/bluetooth"
mkdir -p "$OUT"
docker run --rm -v "$OUT:/work" alpine:3.20 sh -ec '
apk add --no-cache alpine-keys >/dev/null
R=/tmp/root; mkdir -p $R/etc/apk
for c in main community; do echo https://dl-cdn.alpinelinux.org/alpine/v3.20/$c; done >$R/etc/apk/repositories
apk --arch armv7 --root $R --initdb --no-scripts --keys-dir /usr/share/apk/keys/armv7 \
    --repositories-file $R/etc/apk/repositories add musl dbus bluez bluez-alsa bluez-alsa-utils mpg123 alsa-utils >/dev/null
rm -rf $R/usr/share/man $R/usr/share/doc $R/var/cache $R/lib/apk $R/usr/share/sounds $R/usr/include \
    $R/usr/lib/girepository-1.0 $R/usr/lib/libgirepository* $R/usr/lib/bluetooth/bluetooth-meshd \
    $R/usr/libexec/bluetooth/obexd $R/usr/share/locale $R/usr/share/gettext $R/usr/share/glib-2.0
# only what bt-services runs needs to exist; the rest of BusyBox is ours
rm -f $R/bin/busybox

tar -C $R -czf /work/userland.tar.gz .
chmod 644 /work/userland.tar.gz'
ls -l "$OUT/userland.tar.gz"
