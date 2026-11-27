#!/bin/bash
# Build the ALSA core, OSS emulation and snd-n81 against linux-n81/work/build,
# so they can be loaded into the running kernel. Run modern/build.sh first.
set -euo pipefail
D="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
W="$D/../../work"
H="$W/hosttools/root/usr"
if [ -x "$H/bin/bison" ]; then
    export PATH="$H/bin:$PATH" M4="$H/bin/m4" BISON_PKGDATADIR="$H/share/bison"
    export LD_LIBRARY_PATH="$H/lib/x86_64-linux-gnu${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
fi
make=(make -C "$W/src/linux" O="$W/build" ARCH=arm CROSS_COMPILE=arm-linux-gnueabi-)
eval "options=($(grep -v '^#' "$D/../../modern/config.sh" | tr '\n' ' '))"
"$W/src/linux/scripts/config" --file "$W/build/.config" "${options[@]}"
"${make[@]}" olddefconfig >/dev/null
"${make[@]}" -j"$(nproc)" modules >/dev/null
"${make[@]}" M="$D" modules
mkdir -p "$W/sound"
rm -f "$W"/sound/*.ko
cp "$W"/build/sound/{soundcore,core/*,core/oss/*}.ko "$D/snd-n81.ko" "$W/sound/" 2>/dev/null || true
cp "$D/snd-n81.ko" "$W/sound/"
for ko in "$W"/sound/*.ko; do arm-linux-gnueabi-strip --strip-debug "$ko"; done
"${make[@]}" M="$D" clean >/dev/null
L="$W/hosttools/armel/usr/arm-linux-gnueabi"
arm-linux-gnueabi-gcc -static -O2 -Wall -march=armv7-a -B"$L/lib/" -isystem "$L/include" -L"$L/lib" \
    "$D/../play.c" -o "$W/n81-play"
ls -l "$W/sound" "$W/n81-play"
