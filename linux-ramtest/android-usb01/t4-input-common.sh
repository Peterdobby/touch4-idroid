# Source only. Operate on verified evdev character nodes in RAM /dev.
bb=/sbin/busybox
heartbeat=0
nodes=0
pulse=
phase=0
scan_input_nodes() {
    nodes=0
    pulse=
    "$bb" mkdir -p /dev/input
    for event in /sys/class/input/event*; do
        [ -f "$event/dev" ] || continue
        name=$("$bb" cat "$event/device/name")
        [ "$name" = t4-ram-keys ] || continue
        node=${event##*/}
        suffix=${node#event}
        case "$suffix" in ''|*[!0-9]*) continue ;; esac
        IFS=: read -r major minor < "$event/dev"
        [ "$major" = 13 ] || continue
        case "$minor" in ''|*[!0-9]*) continue ;; esac
        [ "$minor" -ge 64 ] && [ "$minor" -le 95 ] || continue
        if [ ! -c "/dev/input/$node" ]; then
            [ ! -e "/dev/input/$node" ] || continue
            "$bb" mknod "/dev/input/$node" c "$major" "$minor" || continue
        fi
        # SystemServer owns the input node; the input group retains access.
        "$bb" chown 1000:1004 "/dev/input/$node" || continue
        "$bb" chmod 0660 "/dev/input/$node" || continue
        nodes=$((nodes+1))
    done
    for input in /sys/class/input/input*; do
        [ -f "$input/name" ] || continue
        name=$("$bb" cat "$input/name")
        if [ "$name" = t4-ram-keys ] && [ -e "$input/t4_pulse" ]; then
            pulse=$input/t4_pulse
            break
        fi
    done
}
pulse_input() {
    heartbeat=$((heartbeat+1))
    if [ -n "$pulse" ]; then
        echo "$heartbeat $nodes $phase" > "$pulse"
    fi
}
