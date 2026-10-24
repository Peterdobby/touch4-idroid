# Source after t4-input-common.sh. Only supervise the child created by this call.
command_pid=
any_timeout=0
run_bounded() {
    limit=$1
    output=$2
    shift 2
    "$@" > "$output" 2>&1 &
    command_pid=$!
    elapsed=0
    while "$bb" kill -0 "$command_pid" 2>/dev/null; do
        if [ "$elapsed" -ge "$limit" ]; then
            "$bb" kill -TERM "$command_pid" 2>/dev/null
            "$bb" sleep 1
            pulse_input
            "$bb" kill -KILL "$command_pid" 2>/dev/null
            wait "$command_pid" 2>/dev/null
            echo "T4_COMMAND_TIMEOUT limit=$limit" >> "$output"
            any_timeout=1
            command_pid=
            return 124
        fi
        "$bb" sleep 1
        elapsed=$((elapsed+1))
        pulse_input
    done
    wait "$command_pid"
    result=$?
    command_pid=
    return "$result"
}
stop_watch_child() {
    case "$command_pid" in ''|*[!0-9]*) return ;; esac
    if [ "$command_pid" -gt 1 ]; then
        "$bb" kill -KILL "$command_pid" 2>/dev/null
        wait "$command_pid" 2>/dev/null
    fi
    command_pid=
}
