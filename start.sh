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
    echo '尚未导入本机安装包。请先运行：'
    echo '  python3 tools/import-installer.py /path/to/T4-Android-Installer-02.4.zip'
    echo '公开仓库不附带固件、票据或设备校准，详见 docs/INSTALLING.md。'
    exit 2
fi
if [ "$#" -gt 0 ]; then
    exec "$PYTHON" "$RUNTIME/backend.py" "$@" --state-dir "$STATE"
fi
while :; do
    printf '\nT4 Android · Installer 02.4\n'
    printf 'SSH 127.0.0.1:%s | 日志与缓存：saved/state/installer02\n\n' "$PORT"
    printf '  1) 识别与检查\n  2) 持久安装 iOS / Android / Console\n'
    printf '  3) 离线准备组件\n  4) 设置 SSH 端口 / Kit 路径\n  5) 校验安装包\n  0) 退出\n\n'
    read -r -p '请选择 [0-5]: ' CHOICE || exit 0
    OPTIONS=(--port "$PORT" --state-dir "$STATE")
    if [ -n "$KIT" ]; then OPTIONS+=(--kit "$KIT"); fi
    case "$CHOICE" in
        1) "$PYTHON" "$RUNTIME/backend.py" check "${OPTIONS[@]}" ;;
        2) "$PYTHON" "$RUNTIME/backend.py" install "${OPTIONS[@]}" ;;
        3)
            read -r -p '目标 iOS 版本 [5.1.1]: ' VERSION || exit 0
            "$PYTHON" "$RUNTIME/backend.py" prepare --version "${VERSION:-5.1.1}" "${OPTIONS[@]}"
            ;;
        4)
            read -r -p "SSH 端口 [$PORT]: " VALUE || exit 0
            if [ -n "$VALUE" ]; then PORT="$VALUE"; fi
            read -r -p 'Kit 文件夹（留空自动寻找）: ' VALUE || exit 0
            if [ -n "$VALUE" ]; then KIT="$VALUE"; fi
            ;;
        5) "$PYTHON" "$RUNTIME/backend.py" verify ;;
        0) exit 0 ;;
        *) echo '请输入 0-5。' ;;
    esac
done
