#!/bin/sh
# Route the original daemon's startup errors to the existing RAM kernel log.
exec > /dev/kmsg 2>&1
echo '<5>T4_ADBD_EXEC: original androidi4 daemon; USB transport; RAM-only'
exec /sbin/adbd
