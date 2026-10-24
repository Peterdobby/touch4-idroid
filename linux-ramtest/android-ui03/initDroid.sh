#!/bin/sh
# Sanitized replacement: only nodes in the /dev tmpfs, no block devices or mounts.
/sbin/busybox mknod /dev/kmsg c 1 11
/sbin/busybox chmod 0600 /dev/kmsg
echo '<5>T4_ANDROID_RAM_PREPARED: original busybox, RAM /dev only' > /dev/kmsg
exit 0
