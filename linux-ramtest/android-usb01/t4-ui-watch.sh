#!/bin/sh
# Command diagnostics and settings are under RAM /data only.
exec > /dev/kmsg 2>&1
. /sbin/t4-input-common.sh
. /sbin/t4-watch-bounded.sh
trap 'stop_watch_child; exit 0' INT TERM
scan_input_nodes
phase=2
pulse_input
echo '<5>T4_INPUT_WATCH_03: INPUT02 kernel retained; bounded userspace checks'
i=0
while [ "$i" -lt 120 ]; do
    "$bb" sleep 5
    i=$((i+1))
    pulse_input
    run_bounded 3 /data/local/tmp/t4-boot-property.txt /system/bin/getprop sys.boot_completed
    boot=$("$bb" cat /data/local/tmp/t4-boot-property.txt)
    [ "$boot" = 1 ] && break
done
if [ "$boot" = 1 ]; then
    # Avoid logical sleep while the inherited framebuffer remains visibly lit.
    # The original svc updates Android's stay-awake setting in RAM /data.
    phase=3
    pulse_input
    run_bounded 6 /data/local/tmp/t4-stayon.txt /system/bin/svc power stayon true
    stayon_result=$?
    phase=4
    pulse_input
    # No -W wait, no automatic Settings launch and no synchronous input command.
    run_bounded 10 /data/local/tmp/t4-home.txt /system/bin/am start -a android.intent.action.MAIN -c android.intent.category.HOME
    home_result=$?
    phase=5
    pulse_input
    run_bounded 5 /data/local/tmp/t4-input-framework.txt /system/bin/dumpsys input
    input_result=$?
    run_bounded 5 /data/local/tmp/t4-window.txt /system/bin/dumpsys window
    window_result=$?
    run_bounded 5 /data/local/tmp/t4-power.txt /system/bin/dumpsys power
    power_result=$?
    echo "stayon=$stayon_result home=$home_result input=$input_result window=$window_result power=$power_result timeouts=$any_timeout" > /data/local/tmp/t4-command-status.txt
    echo "<5>T4_INPUT03_CHECKS stayon=$stayon_result home=$home_result input=$input_result window=$window_result power=$power_result timeouts=$any_timeout"
    if [ "$any_timeout" = 0 ]; then phase=8;else phase=9;fi
else
    phase=9
    echo '<3>T4_INPUT03_BOOT_PROPERTY_NOT_CONFIRMED'
fi
pulse_input
while :; do
    pulse_input
    "$bb" cat /sys/class/input/input*/t4_status > /data/local/tmp/t4-input-status.txt 2>/dev/null
    "$bb" sleep 1
done
