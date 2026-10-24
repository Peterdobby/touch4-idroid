#!/bin/sh
# Static busybox shell survives even if the original dynamic loader fails.
# All scratch files live in the RAM /data tmpfs.
exec > /dev/kmsg 2>&1
echo '<5>T4_DYNAMIC_PROBE_BEGIN: original androidi4 getprop'
/system/bin/getprop ro.secure > /data/local/tmp/dynamic-probe.txt 2>&1
status=$?
echo "<5>T4_DYNAMIC_PROBE_EXIT=$status"
/sbin/busybox cat /data/local/tmp/dynamic-probe.txt
if [ "$status" = "0" ]; then
    /system/bin/setprop t4.dynamic.ready 1
    status=$?
    echo "<5>T4_DYNAMIC_SETPROP_EXIT=$status"
    [ "$status" = "0" ] && exit 0
fi
echo '<3>T4_DYNAMIC_PROBE_FAILED: framework not started; photograph T4_USER_FAULT PC/LR'
while :; do /sbin/busybox sleep 60; done
