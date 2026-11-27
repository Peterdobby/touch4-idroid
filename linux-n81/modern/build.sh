#!/bin/bash
# Build Linux 6.17 (archeYR/linux apple-n90, 8e79d535) for N81AP. No USB access.
# Expects linux-n81/work/src/linux (see README) and flex/bison on PATH or in
# linux-n81/work/hosttools/root.
set -euo pipefail
M="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
W="$M/../work"
S="$W/src/linux"
O="$W/build"
H="$W/hosttools/root/usr"
if [ -x "$H/bin/bison" ]; then
    export PATH="$H/bin:$PATH" M4="$H/bin/m4" BISON_PKGDATADIR="$H/share/bison"
    export LD_LIBRARY_PATH="$H/lib/x86_64-linux-gnu${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
fi
make=(make -C "$S" O="$O" ARCH=arm CROSS_COMPILE=arm-linux-gnueabi-)
dts="$S/arch/arm/boot/dts/samsung"
# Apply each patch once; stop if the tree matches neither state.
for p in "$M"/patches/*.patch; do
    patch -d "$S" -p1 -R -f -s --dry-run < "$p" >/dev/null 2>&1 && continue
    patch -d "$S" -p1 -N -s < "$p"
done
cp "$M/s5l8930-apple-n81.dts" "$dts/"
grep -q s5l8930-apple-n81 "$dts/Makefile" ||
    sed -i 's/s5l8930-apple-n90\.dtb/s5l8930-apple-n90.dtb \\\n\ts5l8930-apple-n81.dtb/' "$dts/Makefile"
"${make[@]}" s5l8930_defconfig >/dev/null
eval "options=($(grep -v '^#' "$M/config.sh" | tr '\n' ' '))"
"$S/scripts/config" --file "$O/.config" "${options[@]}"
"${make[@]}" olddefconfig >/dev/null
"${make[@]}" -j"$(nproc)" zImage modules samsung/s5l8930-apple-n81.dtb
rm -rf "$W/modules" && mkdir -p "$W/modules"
find "$O" -name '*.ko' -exec cp {} "$W/modules/" \;
for ko in "$W"/modules/*.ko; do arm-linux-gnueabi-strip --strip-debug "$ko"; done
# Second pass: build the root filesystem (needs the modules above) into the
# kernel, so nothing has to be copied over USB after boot.
bash "$M/../audio/driver/build.sh"
L="$W/hosttools/armel/usr/arm-linux-gnueabi"
arm-linux-gnueabi-gcc -static -O2 -Wall -march=armv7-a -B"$L/lib/" -isystem "$L/include" -L"$L/lib" \
    "$M/../bluetooth/n81-bt.c" -o "$W/n81-bt"
arm-linux-gnueabi-gcc -static -O2 -march=armv7-a -B"$L/lib/" -isystem "$L/include" -L"$L/lib" \
    "$M/../wifi/n81-wifi.c" -o "$W/n81-wifi"
arm-linux-gnueabi-gcc -static -O2 -Wall -march=armv7-a -D_FILE_OFFSET_BITS=64 -B"$L/lib/" -isystem "$L/include" -L"$L/lib" \
    "$M/../buttons/n81-buttons.c" -o "$W/n81-buttons"
G="$M/../../saved/build/gui"
python3 "$M/../gui/build.py" --full "$G"
"$S/scripts/config" --file "$O/.config" --set-str INITRAMFS_SOURCE "$(realpath "$G/rootfs.cpio")" -e INITRAMFS_COMPRESSION_XZ
"${make[@]}" olddefconfig >/dev/null
"${make[@]}" -j"$(nproc)" zImage
cat "$O/arch/arm/boot/zImage" "$O/arch/arm/boot/dts/samsung/s5l8930-apple-n81.dtb" > "$W/zImage-n81"
ls -l "$W/zImage-n81"
