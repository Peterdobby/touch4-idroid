#!/bin/bash
set -u
BASE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="${T4_PYTHON:-python3}"
command -v "$PYTHON" >/dev/null 2>&1 || { echo 'Python 3.9 or newer is required.'; exit 1; }
if [ "$#" -gt 0 ]; then exec "$PYTHON" "$BASE/backend.py" "$@"; fi
PORT="${T4_SSH_PORT:-6414}"
KIT="${T4_KIT_DIR:-}"
while :; do
    printf '\nT4 Android Installer 02.4 - automatic component preparation\n'
    printf 'SSH 127.0.0.1:%s | Existing Kit DRA6 / SSH ramdisk\n\n' "$PORT"
    printf '  1) Detect iOS, prepare matching components and check\n'
    printf '  2) Install the iOS / Android / Console menu\n'
    printf '  3) Prepare boot components\n'
    printf '  4) Set SSH port / Kit path\n'
    printf '  5) Verify package\n'
    printf '  0) Exit\n\n'
    read -r -p 'Choose [0-5]: ' CHOICE || exit 0
    OPTIONS=(--port "$PORT")
    if [ -n "$KIT" ]; then OPTIONS+=(--kit "$KIT"); fi
    case "$CHOICE" in
        1) "$PYTHON" "$BASE/backend.py" check "${OPTIONS[@]}" ;;
        2) "$PYTHON" "$BASE/backend.py" install "${OPTIONS[@]}" ;;
        3)
            read -r -p 'Target iOS version [5.1.1]: ' VERSION || exit 0
            VERSION="${VERSION:-5.1.1}"
            "$PYTHON" "$BASE/backend.py" prepare --version "$VERSION" "${OPTIONS[@]}"
            ;;
        4)
            read -r -p "SSH port [${PORT}]: " VALUE || exit 0
            if [ -n "$VALUE" ]; then PORT="$VALUE"; fi
            read -r -p "Kit folder [${KIT}, leave empty to search automatically]: " VALUE || exit 0
            if [ -n "$VALUE" ]; then KIT="$VALUE"; fi
            ;;
        5) "$PYTHON" "$BASE/backend.py" verify ;;
        0) exit 0 ;;
        *) echo 'Enter a number from 0 to 5.' ;;
    esac
done
