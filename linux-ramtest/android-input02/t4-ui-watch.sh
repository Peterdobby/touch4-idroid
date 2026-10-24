#!/bin/sh
# All outputs and files are RAM only. Keep the first real failure readable.
exec > /dev/kmsg 2>&1
echo '<5>T4_INPUT_WATCH_02: original Android; first failure will be held'
. /sbin/t4-input-common.sh
scan_input_nodes
phase=2
pulse_input
i=0
while [ "$i" -lt 120 ]; do
    /sbin/busybox sleep 5
    i=$((i+1))
    pulse_input
    zygote=$(/system/bin/getprop init.svc.zygote)
    boot=$(/system/bin/getprop sys.boot_completed)
    echo "<5>T4_UI_STATE tick=$i zygote=$zygote boot=$boot"
    if [ "$zygote" = "stopped" ]; then
        /system/bin/setprop ctl.stop t4-critical-log
        /sbin/busybox sleep 1
        echo '<3>T4_FIRST_FRAMEWORK_FAILURE_BEGIN'
        /system/bin/logcat -b main -b system -d -v brief AndroidRuntime:V SystemServer:V Zygote:V dalvikvm:W libc:V DEBUG:V '*:E' > /data/local/tmp/first-framework-failure.txt 2>&1
        /sbin/busybox tail -n 60 /data/local/tmp/first-framework-failure.txt
        echo '<3>T4_FIRST_FAILURE_SUMMARY_BEGIN'
        /sbin/busybox grep -E 'FATAL|Fatal|Exception|Caused by|cannot |Unable|unable|failed|Failure|Error|terminated|Exit zygote' /data/local/tmp/first-framework-failure.txt | /sbin/busybox tail -n 18
        echo '<3>T4_FIRST_FAILURE_SUMMARY_END: photograph this screen; zygote retry disabled'
        break
    fi
    if [ "$boot" = "1" ]; then
        echo '<5>T4_ANDROID_FRAMEWORK_BOOT_COMPLETED: screen verification still required'
        phase=3
        pulse_input
        /system/bin/am start -W -a android.settings.SETTINGS > /data/local/tmp/t4-settings-test.txt 2>&1
        phase=4
        pulse_input
        /sbin/busybox sleep 5
        /system/bin/input keyevent 3
        /system/bin/am start -W -a android.intent.action.MAIN -c android.intent.category.HOME
        /system/bin/dumpsys activity > /data/local/tmp/activity.txt 2>&1
        /sbin/busybox grep 'mResumedActivity' /data/local/tmp/activity.txt
        /sbin/busybox cat /proc/bus/input/devices > /data/local/tmp/t4-input-devices.txt
        /system/bin/dumpsys input > /data/local/tmp/t4-input-framework.txt 2>&1
        /sbin/busybox ls -l /dev/input > /data/local/tmp/t4-input-nodes.txt 2>&1
        echo '<5>T4_INPUT_BOOT_READY: key test ready; automatic MENU injection disabled'
        phase=5
        pulse_input
        break
    fi
done
# Retain one small RAM diagnostic snapshot; never overwrite the desktop with logs.
while :; do
    pulse_input
    /sbin/busybox cat /sys/class/input/input*/t4_status > /data/local/tmp/t4-input-status.txt 2>/dev/null
    /sbin/busybox sleep 1
done
