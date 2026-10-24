#!/bin/sh
# Original logcat reads actual logger nodes. Output goes to RAM kernel log.
exec > /dev/kmsg 2>&1
echo '<5>T4_CRITICAL_LOG_READY: framework warnings/errors; no repeated GC tail'
exec /system/bin/logcat -b main -b system -v brief AndroidRuntime:V SystemServer:I ActivityManager:I PackageManager:I WindowManager:I SurfaceFlinger:I Zygote:V libc:V DEBUG:V dalvikvm:W '*:W'
