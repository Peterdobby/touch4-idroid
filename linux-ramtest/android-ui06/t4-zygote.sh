#!/bin/sh
# Preserve PID and all inherited socket/property descriptors with exec.
exec > /dev/kmsg 2>&1
echo '<5>T4_ZYGOTE_EXEC_ORIGINAL: stderr visible; first attempt only'
exec /system/bin/app_process -Xzygote /system/bin --zygote --start-system-server
