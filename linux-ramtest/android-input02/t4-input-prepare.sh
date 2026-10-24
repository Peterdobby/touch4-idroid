#!/bin/sh
# Executed before framework startup. All created nodes are RAM evdev chars.
. /sbin/t4-input-common.sh
scan_input_nodes
phase=1
pulse_input
echo "<5>T4_INPUT_PREPARE nodes=$nodes pulse=$pulse; major=13 only; no block nodes"
# Do not hide the desktop if registration failed; the on-screen REG field reports it.
exit 0
