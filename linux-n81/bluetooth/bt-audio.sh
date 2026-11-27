#!/bin/sh
# Audio to a Bluetooth headphone or speaker (BlueALSA A2DP source).
#   bt-audio scan [SECONDS]   list nearby devices: ADDRESS NAME
#   bt-audio connect ADDRESS  pair, trust and connect
#   bt-audio power [on|off]   switch the adapter, or print its state
#   bt-audio paired           paired devices: ADDRESS NAME
#   bt-audio disconnect ADDRESS
#   bt-audio forget ADDRESS   remove the pairing
#   bt-audio current          address of the connected audio output, if any
#   bt-audio volume up|down
#   bt-audio play FILE...     MP3 files under /tmp, to the headphone, else speaker
ctl() { timeout "${T:-20}" chroot /alp /usr/bin/bluetoothctl "$@" 2>&1; }

current() {
	chroot /alp /usr/bin/bluealsa-cli list-pcms 2>/dev/null |
		sed -n 's|.*/dev_\([0-9A-F_]*\)/a2dpsrc/sink$|\1|p' | head -n 1 | tr _ :
}

case $1 in
scan)
	timeout $((${2:-12} + 3)) chroot /alp /usr/bin/bluetoothctl --timeout "${2:-12}" scan on >/dev/null 2>&1
	# unnamed devices show their address as name: leave them out
	ctl devices | sed -n 's/^Device \([0-9A-F:]*\) \(.*\)/\1 \2/p' | grep -vE ' ([0-9A-F]{2}-){5}[0-9A-F]{2}$'
	;;
connect)
	ctl info "$2" | grep -q 'Paired: yes' || T=40 ctl pair "$2" | tail -n 2
	ctl trust "$2" >/dev/null
	T=30 ctl connect "$2" | tail -n 1
	sleep 2
	[ "$(current)" = "$2" ] && echo connected || { echo "no audio output"; exit 1; }
	;;
power)
	if [ -n "$2" ]; then
		ctl power "$2" | grep -q succeeded || { echo "failed"; exit 1; }
	elif ctl show | grep -q 'Powered: yes'; then
		echo on
	else
		echo off
	fi
	;;
paired)
	ctl devices Paired | sed -n 's/^Device \([0-9A-F:]*\) \(.*\)/\1 \2/p'
	;;
disconnect)
	ctl disconnect "$2" | grep -q 'Successful' || { echo "not disconnected"; exit 1; }
	;;
forget)
	ctl remove "$2" | grep -q 'removed' || { echo "not removed"; exit 1; }
	;;
current)
	current
	;;
volume)
	# up or down, on whatever is playing: the headphone, else the speaker
	step=8
	[ "$2" = down ] && step=-8
	pcm=$(chroot /alp /usr/bin/bluealsa-cli list-pcms 2>/dev/null | grep 'a2dpsrc/sink$' | head -n 1)
	if [ -n "$pcm" ]; then
		v=$(chroot /alp /usr/bin/bluealsa-cli volume "$pcm" | sed -n 's/^Volume: L: \([0-9]*\).*/\1/p')
		v=$((${v:-40} + step))
		[ $v -lt 0 ] && v=0
		[ $v -gt 127 ] && v=127
		chroot /alp /usr/bin/bluealsa-cli volume "$pcm" $v $v
	else
		v=$(($(cat /tmp/volume 2>/dev/null || echo 70) + step))
		[ $v -lt 0 ] && v=0
		[ $v -gt 100 ] && v=100
		echo $v >/tmp/volume
		n81-play -v $v
	fi
	;;
play)
	shift
	to=$(current)
	if [ -n "$to" ]; then device=bluealsa:DEV=$to,PROFILE=a2dp; else device=plughw:0,0; fi
	exec chroot /alp /usr/bin/mpg123 -q -o alsa -a "$device" "$@"
	;;
*)
	echo "usage: bt-audio scan | power [on|off] | paired | connect|disconnect|forget ADDRESS | current | volume up|down | play FILE..." >&2
	exit 2
	;;
esac
