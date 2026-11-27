#!/bin/sh
# Answer "yes" to bluetoothctl's pairing and service prompts, as a speaker with
# no keyboard would. Anyone in range can pair while this runs.
log=/tmp/bluetoothctl.log
seen=0
while sleep 1; do
	n=$(grep -ao 'yes/no' $log 2>/dev/null | wc -l)
	if [ "$n" -gt "$seen" ]; then
		echo yes >/alp/run/btctl
		seen=$n
	elif [ "$n" -lt "$seen" ]; then
		seen=$n
	fi
done
