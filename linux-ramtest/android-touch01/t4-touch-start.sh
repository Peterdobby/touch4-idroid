#!/bin/sh
# /dev and /data are RAM filesystems in this build. No block-device operation.
bb=/sbin/busybox
if [ ! -e /sys/class/misc/uinput/dev ]; then
    echo '<3>T4_INPUT: kernel uinput missing' > /dev/kmsg
    exit 1
fi
node=$("$bb" cat /sys/class/misc/uinput/dev)
[ "$node" = '10:223' ] || exit 1
if [ ! -e /dev/uinput ]; then
    "$bb" mknod /dev/uinput c 10 223 || exit 1
fi
exec /sbin/t4-touch-input
