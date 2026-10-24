#!/bin/bash
set -u
BASE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="${T4_PYTHON:-python3}"
command -v "$PYTHON" >/dev/null 2>&1 || { echo '需要 Python 3.9 或更新版本。'; exit 1; }
if [ "$#" -gt 0 ]; then exec "$PYTHON" "$BASE/backend.py" "$@"; fi
PORT="${T4_SSH_PORT:-6414}"
KIT="${T4_KIT_DIR:-}"
while :; do
    printf '\nT4 Android 安装工具 02.4 · 自动下载启动组件\n'
    printf 'SSH 127.0.0.1:%s | 现有 Kit DRA6 / SSH ramdisk\n\n' "$PORT"
    printf '  1) 自动识别 iOS、准备匹配组件并检查（不写持久存储）\n'
    printf '  2) 一次完成持久安装：iOS / Android / Console\n'
    printf '  3) 离线准备启动组件（不用连接设备，不下载完整 IPSW）\n'
    printf '  4) 设置 SSH 端口 / Kit 路径\n'
    printf '  5) 校验电脑端工具包\n'
    printf '  0) 退出\n\n'
    read -r -p '请选择 [0-5]: ' CHOICE || exit 0
    OPTIONS=(--port "$PORT")
    if [ -n "$KIT" ]; then OPTIONS+=(--kit "$KIT"); fi
    case "$CHOICE" in
        1) "$PYTHON" "$BASE/backend.py" check "${OPTIONS[@]}" ;;
        2) "$PYTHON" "$BASE/backend.py" install "${OPTIONS[@]}" ;;
        3)
            read -r -p '目标 iOS 版本 [5.1.1]: ' VERSION || exit 0
            VERSION="${VERSION:-5.1.1}"
            "$PYTHON" "$BASE/backend.py" prepare --version "$VERSION" "${OPTIONS[@]}"
            ;;
        4)
            read -r -p "SSH 端口 [${PORT}]: " VALUE || exit 0
            if [ -n "$VALUE" ]; then PORT="$VALUE"; fi
            read -r -p "Kit 文件夹 [${KIT}，留空自动寻找]: " VALUE || exit 0
            if [ -n "$VALUE" ]; then KIT="$VALUE"; fi
            ;;
        5) "$PYTHON" "$BASE/backend.py" verify ;;
        0) exit 0 ;;
        *) echo '请输入 0-5。' ;;
    esac
done
