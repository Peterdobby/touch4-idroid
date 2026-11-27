#!/usr/bin/env python3
"""Package zImage+DTB and an initramfs for the existing OpeniBoot RAM loader.

Reuses linux-ramtest/handoff.c and usb.c unchanged. No USB access.
"""
import gzip
import hashlib
import lzma
from pathlib import Path
import shlex
import struct
import subprocess
import sys
import zlib

ROOT = Path(__file__).resolve().parents[2]
T = ROOT
RAMTEST = T / 'linux-ramtest'
OUT = ROOT / 'linux-n81/work/pkg'
CROSS = str(T / 'saved/toolchain/gcc-4.8.5-nolibc/arm-linux-gnueabi/bin/arm-linux-gnueabi-')
BASE_SHA = 'cd32dbac3d10a81b64226ffa4057fa8e202e699e3ff2182a7560eea077d5fbe1'


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    kernel = (ROOT / 'linux-n81/work/zImage-n81').read_bytes()
    # Everything is inside the kernel. OpeniBoot copies this archive to
    # 0x08000000 and the framebuffer starts at 0x08104000: keep it (near) empty.
    initrd = (T / 'saved/build/gui/empty.cpio.gz').read_bytes()
    base = (T / 'saved/build/phase1-published/openiboot.bin').read_bytes()
    assert hashlib.sha256(base).hexdigest() == BASE_SHA
    assert struct.unpack_from('<I', kernel, 0x24)[0] == 0x016f2818, 'not a zImage'
    assert len(kernel) <= 12 * 1024 * 1024, 'kernel exceeds the loader limit'
    assert len(initrd) <= 0x100000, 'initramfs would overlap the framebuffer'
    (OUT / 'zImage').write_bytes(kernel)
    (OUT / 'initramfs.cpio.gz').write_bytes(initrd)
    sizes = {'KERNEL_SIZE': len(kernel), 'KERNEL_CRC': zlib.crc32(kernel),
             'NATIVE_BOOT_CRC': zlib.crc32(base[0x2e3c:0x3030]),
             'INITRD_SIZE': len(initrd), 'INITRD_CRC': zlib.crc32(initrd),
             'INITRD_UNPACKED_SIZE': len(lzma.decompress(initrd) if initrd[:6] == b'\xfd7zXZ\0'
                                         else gzip.decompress(initrd))}
    (OUT / 'sizes.h').write_text(''.join(f'#define {k} {v}u\n' for k, v in sizes.items()))
    elf = OUT / 'handoff.elf'
    subprocess.run([CROSS + 'gcc', '-nostdlib', '-fno-use-linker-plugin', '-mcpu=cortex-a8',
                    '-mthumb', '-Os', '-fno-builtin', '-fno-unwind-tables',
                    '-fno-asynchronous-unwind-tables', '-Wl,-Ttext=0x44000000', '-Wl,-N',
                    '-Wl,--build-id=none', '-Wl,-e,t4_linux_stage', f'-I{OUT}',
                    str(RAMTEST / 'handoff.c'), '-o', str(elf)], check=True)
    subprocess.run([CROSS + 'objcopy', '-O', 'binary', str(elf), str(OUT / 'handoff.bin')], check=True)
    symbols = subprocess.check_output([CROSS + 'nm', str(elf)], text=True)
    entry = {s[2]: int(s[0], 16) | 1 for line in symbols.splitlines()
             if len(s := line.split()) == 3}
    (OUT / 'entries').write_text(f"{entry['t4_linux_stage']:#x} {entry['t4_linux_start']:#x}\n")
    flags = shlex.split(subprocess.check_output(
        ['pkg-config', '--cflags', '--libs', 'libusb-1.0'], text=True))
    subprocess.run(['cc', '-Wall', '-Wextra', '-Werror', str(RAMTEST / 'usb.c'),
                    '-o', str(OUT / 'linux-usb')] + flags, check=True)
    print('Packaged', OUT, {'kernel': len(kernel), 'initramfs': len(initrd)})


if __name__ == '__main__':
    main()
