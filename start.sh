#!/bin/bash
set -u
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="${T4_PYTHON:-python3}"
RUNTIME="${T4_INSTALLER_DIR:-$ROOT/saved/packages/T4-Android-Installer-02}"
STATE="$ROOT/saved/state/installer02"
PORT="${T4_SSH_PORT:-6414}"
KIT="${T4_KIT_DIR:-}"

if [ "${1:-}" = "--help" ]; then
    echo 'Usage: bash start.sh [verify|check|install|prepare] [options]'
    echo 'First import your own 02.4 package with tools/import-installer.py.'
    exit 0
fi
if [ ! -f "$RUNTIME/backend.py" ] || [ ! -f "$RUNTIME/manifest.json" ]; then
    echo 'No owner-device package has been imported. First run:'
    echo '  python3 tools/import-installer.py /path/to/T4-Android-Installer-02.4.zip'
    echo 'The source checkout requires a separate package; see docs/INSTALLING.md.'
    exit 2
fi
if [ "$#" -gt 0 ]; then
    exec "$PYTHON" "$RUNTIME/backend.py" "$@" --state-dir "$STATE"
fi
while :; do
    printf '\nT4 Android · Installer 02.4\n'
    printf 'SSH 127.0.0.1:%s | Logs and cache: saved/state/installer02\n\n' "$PORT"
    printf '  1) Detect and check\n  2) Install iOS / Android / Console\n'
    printf '  3) Prepare components\n  4) Set SSH port / Kit path\n  5) Verify package\n  0) Exit\n\n'
    read -r -p 'Choose [0-5]: ' CHOICE || exit 0
    OPTIONS=(--port "$PORT" --state-dir "$STATE")
    if [ -n "$KIT" ]; then OPTIONS+=(--kit "$KIT"); fi
    case "$CHOICE" in
        1) "$PYTHON" "$RUNTIME/backend.py" check "${OPTIONS[@]}" ;;
        2) "$PYTHON" "$RUNTIME/backend.py" install "${OPTIONS[@]}" ;;
        3)
            read -r -p 'Target iOS version [5.1.1]: ' VERSION || exit 0
            "$PYTHON" "$RUNTIME/backend.py" prepare --version "${VERSION:-5.1.1}" "${OPTIONS[@]}"
            ;;
        4)
            read -r -p "SSH port [$PORT]: " VALUE || exit 0
            if [ -n "$VALUE" ]; then PORT="$VALUE"; fi
            read -r -p 'Kit folder (leave empty to search automatically): ' VALUE || exit 0
            if [ -n "$VALUE" ]; then KIT="$VALUE"; fi
            ;;
        5) "$PYTHON" "$RUNTIME/backend.py" verify ;;
        0) exit 0 ;;
        *) echo 'Enter a number from 0 to 5.' ;;
    esac
done
