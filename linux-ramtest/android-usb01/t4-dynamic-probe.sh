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
    checked=0
    for name in ro.FOREGROUND_APP_ADJ ro.VISIBLE_APP_ADJ ro.PERCEPTIBLE_APP_ADJ ro.HEAVY_WEIGHT_APP_ADJ ro.SECONDARY_SERVER_ADJ ro.BACKUP_APP_ADJ ro.HOME_APP_ADJ ro.HIDDEN_APP_MIN_ADJ ro.EMPTY_APP_ADJ ro.FOREGROUND_APP_MEM ro.VISIBLE_APP_MEM ro.PERCEPTIBLE_APP_MEM ro.HEAVY_WEIGHT_APP_MEM ro.SECONDARY_SERVER_MEM ro.BACKUP_APP_MEM ro.HOME_APP_MEM ro.HIDDEN_APP_MEM ro.EMPTY_APP_MEM; do
        value=$(/system/bin/getprop "$name")
        case "$value" in
            ''|*[!0-9]*)
                echo "<3>T4_AMS_PROPERTY_INVALID: $name='$value'"
                status=1
                ;;
            *)
                case "$name" in
                    *_MEM)
                        if [ "$value" -le 0 ]; then
                            echo "<3>T4_AMS_PROPERTY_INVALID: $name must be positive"
                            status=1
                        fi
                        ;;
                esac
                ;;
        esac
        checked=$((checked+1))
    done
    if [ "$status" = "0" ]; then
        echo "<5>T4_AMS_PROPERTIES_READY=$checked"
    fi
fi
if [ "$status" = "0" ]; then
    epoch=$(/sbin/busybox cat /sbin/t4-ram-epoch)
    /sbin/t4-ramclock "$epoch"
    if [ "$?" != "0" ]; then
        echo '<4>T4_RAM_CLOCK_UNSET: continuing with existing Linux software time'
    fi
    if [ ! -d /sys/class/power_supply ]; then
        echo '<5>T4_BATTERY_HW_UNAVAILABLE: native fallback UNKNOWN; no charging control'
    fi
    /bin/sh /sbin/t4-input-prepare.sh
    /system/bin/setprop t4.dynamic.ready 1
    status=$?
    echo "<5>T4_DYNAMIC_SETPROP_EXIT=$status"
    [ "$status" = "0" ] && exit 0
fi
echo '<3>T4_ANDROID_PREFLIGHT_FAILED: framework held; photograph property/fault lines'
while :; do /sbin/busybox sleep 60; done
