#!/bin/sh
# All outputs and logs are RAM files. Read only property/process/service state.
exec > /dev/kmsg 2>&1
echo '<5>T4_UI_WATCH: real Android framework attempt; not yet desktop success'
i=0
while [ "$i" -lt 60 ]; do
    /sbin/busybox sleep 5
    i=$((i+1))
    echo "<5>T4_UI_STATUS tick=$i servicemanager=$(/system/bin/getprop init.svc.servicemanager) sf=$(/system/bin/getprop init.svc.surfaceflinger) zygote=$(/system/bin/getprop init.svc.zygote) boot=$(/system/bin/getprop sys.boot_completed)"
    /sbin/busybox tail -n 10 /data/local/tmp/android.log
    if [ "$(/system/bin/getprop sys.boot_completed)" = "1" ]; then
        echo '<5>T4_ANDROID_FRAMEWORK_BOOT_COMPLETED: screen verification still required'
        /system/bin/input keyevent 82
        /system/bin/input keyevent 3
        /system/bin/am start -W -a android.intent.action.MAIN -c android.intent.category.HOME
        /system/bin/dumpsys activity > /data/local/tmp/activity.txt 2>&1
        /sbin/busybox grep 'mResumedActivity' /data/local/tmp/activity.txt
        break
    fi
done
while :; do /sbin/busybox sleep 60; done
