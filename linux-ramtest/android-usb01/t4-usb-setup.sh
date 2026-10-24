#!/bin/sh
# Configure only an ADB gadget; no storage function or network transport.
exec > /dev/kmsg 2>&1
bb=/sbin/busybox
base=/sys/class/android_usb/android0
n=0
while [ ! -e "$base/enable" ] && [ "$n" -lt 10 ]; do
    "$bb" sleep 1
    n=$((n+1))
done
if [ ! -e "$base/enable" ]; then
    echo '<3>T4_USB_SETUP_NO_GADGET: inspect U on screen'
    exit 1
fi
echo 0 > "$base/enable"
echo 18d1 > "$base/idVendor" || exit 1
echo 0001 > "$base/idProduct" || exit 1
echo T4RAMUSB01 > "$base/iSerial" || exit 1
echo 'iDroid T4 RAM' > "$base/iProduct" || exit 1
echo adb > "$base/functions" || exit 1
# Original adbd expects /dev/android_adb. ueventd normally creates it.
if [ ! -c /dev/android_adb ] && [ -f /sys/class/misc/android_adb/dev ]; then
    IFS=: read -r major minor < /sys/class/misc/android_adb/dev
    case "$minor" in ''|*[!0-9]*) exit 1;; esac
    [ "$major" = 10 ] && [ "$minor" -le 255 ] || exit 1
    [ ! -e /dev/android_adb ] || exit 1
    "$bb" mknod /dev/android_adb c "$major" "$minor" || exit 1
fi
[ -c /dev/android_adb ] || exit 1
echo 1 > "$base/enable" || exit 1
/system/bin/setprop ctl.start adbd || exit 1
echo '<5>T4_USB_ADB_REQUESTED: USB enumeration/ADB handshake require hardware verification'
exit 0
