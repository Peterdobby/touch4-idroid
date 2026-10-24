#!/bin/bash
# macOS Bash 3.2 compatible. The Python backend owns all device operations.
set -u
BASE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="${T4_PYTHON:-python3}"
if ! command -v "$PYTHON" >/dev/null 2>&1; then
    echo "需要 Python 3。请先安装 Python 3，再运行本工具。" >&2
    exit 1
fi
if [ "$#" -gt 0 ]; then
    exec "$PYTHON" "$BASE/backend.py" "$@"
fi
PORT="${T4_SSH_PORT:-6414}"
KIT="${T4_KIT_DIR:-}"
while :; do
    printf '\nT4 Android 安装工具 01 · iOS / Android / Console\n'
    printf 'SSH: 127.0.0.1:%s  |  已有 Kit SSH ramdisk\n\n' "$PORT"
    printf '  1) 检查设备、自动识别 iOS（不写持久存储）\n'
    printf '  2) 安装菜单和 Android（更新启动固件）\n'
    printf '  3) 修改 SSH 端口或 Kit 路径\n'
    printf '  4) 校验电脑端安装包\n'
    printf '  0) 退出\n\n'
    read -r -p '请选择 [0-4]: ' CHOICE || exit 0
    EXTRA=(--port "$PORT")
    if [ -n "$KIT" ]; then EXTRA+=(--kit "$KIT"); fi
    case "$CHOICE" in
        1) "$PYTHON" "$BASE/backend.py" check "${EXTRA[@]}" ;;
        2) "$PYTHON" "$BASE/backend.py" install "${EXTRA[@]}" ;;
        3)
            read -r -p "SSH 端口 [$PORT]: " VALUE || exit 0
            if [ -n "$VALUE" ]; then PORT="$VALUE"; fi
            read -r -p "Legacy-iOS-Kit 文件夹 [${KIT}，留空自动寻找]: " VALUE || exit 0
            if [ -n "$VALUE" ]; then KIT="$VALUE"; fi
            ;;
        4) "$PYTHON" "$BASE/backend.py" verify ;;
        0) exit 0 ;;
        *) echo '请输入 0-4。' ;;
    esac
done
