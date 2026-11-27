#!/bin/bash
# RAM-only boot of N81AP from kDFU. Nothing is written to NAND.
set -eu
R="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
# Legacy iOS Kit checkout: LEGACY_IOS_KIT, default ~/Legacy-iOS-Kit
K="${LEGACY_IOS_KIT:-$HOME/Legacy-iOS-Kit}/bin/linux/x86_64"
T="$R"
export IRECOVERY="$K/irecovery"
# the Kit's irecovery needs the Kit's libraries; load/console use the system's.
export T4_IRECOVERY_LIBS="$K/lib"
case "${1:-}" in
    check)     python3 "$T/phase1/run.py" --published --kdfu --check ;;
    openiboot) python3 "$T/phase1/run.py" --published --kdfu --boot ;;
    stage)     python3 "$T/linux-ramtest/run.py" --stage ;;
    linux)     python3 "$T/linux-ramtest/run.py" --boot ;;
    # Linux 6.17: linux-n81/modern/build.sh + package.py
    stage617|linux617)
        P="$R/linux-n81/work/pkg"
        mode=--stage; [ "$1" = linux617 ] && mode=--boot
        read -r stage start < "$P/entries"
        "$P/linux-usb" "$mode" "$P/zImage" "$P/initramfs.cpio.gz" "$P/handoff.bin" "$stage" "$start" ;;
    *) echo "usage: $0 check|openiboot|stage|linux|stage617|linux617" >&2; exit 2 ;;
esac
