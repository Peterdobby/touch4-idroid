#!/bin/sh
# Start D-Bus, bluetoothd and BlueALSA from the Alpine tree in /alp (RAM).
A=/alp
[ -x $A/usr/lib/bluetooth/bluetoothd ] || { echo "no /alp"; exit 1; }
for d in dev proc sys tmp lib/modules; do
	mkdir -p $A/$d
done
# bluetoothctl parses arguments with wordexp(), which runs /bin/sh: give the
# tree the image's BusyBox (its /bin/sh points there)
[ -x $A/bin/busybox ] || cp /bin/busybox $A/bin/busybox
grep -q " $A/dev " /proc/mounts || for d in dev proc sys tmp; do mount --bind /$d $A/$d; done
# apk ran without its install scripts: create what they would have
grep -q '^root:' $A/etc/passwd 2>/dev/null || echo 'root:x:0:0:root:/root:/bin/sh' >>$A/etc/passwd
grep -q '^messagebus:' $A/etc/passwd || echo 'messagebus:x:100:101::/dev/null:/sbin/nologin' >>$A/etc/passwd
grep -q '^root:' $A/etc/group 2>/dev/null || echo 'root:x:0:' >>$A/etc/group
grep -q '^messagebus:' $A/etc/group || echo 'messagebus:x:101:' >>$A/etc/group
grep -q '^audio:' $A/etc/group || echo 'audio:x:18:' >>$A/etc/group
[ -s $A/etc/machine-id ] || echo 4e383169706f64000000000000000001 >$A/etc/machine-id
mkdir -p $A/run/dbus $A/run/bluealsa $A/var/lib/bluetooth $A/var/lib/bluealsa $A/root
# no alpine-baselayout: /var/run must be /run, as on any Alpine system
[ -L $A/var/run ] || { rm -rf $A/var/run; ln -s /run $A/var/run; }
ifconfig lo 127.0.0.1 up
# each daemon in its own session, so it outlives the shell that started it
alive() { for pid in $(pidof $1); do grep -q ") Z " /proc/$pid/stat || return 0; done; return 1; }
run() { # NAME COMMAND...
	name=$1; shift
	alive $name || setsid chroot $A "$@" </dev/null >/tmp/$name.log 2>&1 &
	sleep 3
}
alive dbus-daemon || rm -f $A/run/dbus/*
run dbus-daemon /usr/bin/dbus-daemon --system --nofork --nopidfile
run bluetoothd /usr/lib/bluetooth/bluetoothd -n
# BlueALSA (4.2.0 and 4.3.1 on Alpine) searches FDK-AAC's module table past the
# end of its buffer on the main stack. With the near-empty environment of this
# chroot the search runs off the top of the stack and segfaults; padding the
# environment keeps it in mapped memory.
PAD=$(head -c 8000 /dev/zero | tr '\000' x) run bluealsa /usr/bin/bluealsa -p a2dp-source -p a2dp-sink
# bluetoothctl holds the pairing agent while it runs: keep one, fed by a FIFO
if ! alive bluetoothctl; then
	rm -f $A/run/btctl; mkfifo $A/run/btctl
	setsid sh -c "exec 3<>$A/run/btctl; exec chroot $A /usr/bin/bluetoothctl --agent=NoInputNoOutput <&3" >/tmp/bluetoothctl.log 2>&1 &
	sleep 3
fi
echo default-agent >$A/run/btctl
for c in "power on" "system-alias iPod-Linux" "pairable on" "discoverable-timeout 0" "discoverable on"; do
	timeout 10 chroot $A /usr/bin/bluetoothctl $c 2>&1 | grep -q succeeded || echo "failed: $c"
done
# nobody types here: accept pairing and service requests
pgrep -f bin/bt-accept >/dev/null 2>&1 || setsid sh /bin/bt-accept </dev/null >/dev/null 2>&1 &
# what arrives over A2DP goes to the speaker (plughw converts 48 kHz to 44.1)
alive bluealsa-aplay || setsid chroot $A /usr/bin/bluealsa-aplay --pcm=plughw:0,0 00:00:00:00:00:00 </dev/null >/tmp/bluealsa-aplay.log 2>&1 &
n81-play -v 70 2>/dev/null
sleep 2
for p in dbus-daemon bluetoothd bluealsa bluealsa-aplay; do alive $p && echo "$p ok" || { echo "$p did NOT start"; tail -n 3 /tmp/$p.log; }; done
