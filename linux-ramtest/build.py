#!/usr/bin/env python3
"""Build an isolated observable N81 Linux RAM experiment, without USB access."""
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import zlib

ROOT=Path(__file__).resolve().parent.parent
HERE=Path(__file__).resolve().parent
OUT=ROOT/'saved/build/T4_LINUX_RAM_02'
ORIGINAL=ROOT/'saved/sources/iDroid-kernel-idroid-3.0.0'
SRC=ROOT/'saved/sources/iDroid-kernel-T4_LINUX_RAM_02'
CROSS=os.environ.get('CROSS',str(ROOT/'saved/toolchain/arm-eabi-4.8/bin/arm-eabi-'))
EXPECTED_BASE='cd32dbac3d10a81b64226ffa4057fa8e202e699e3ff2182a7560eea077d5fbe1'

def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()

def cpio_entry(name,data=b'',mode=0o100644,rdev=(0,0),ino=1):
    n=name.encode()+b'\0'
    fields=[ino,mode,0,0,1,0,len(data),0,0,*rdev,len(n),0]
    b=b'070701'+b''.join(f'{v:08x}'.encode() for v in fields)+n
    b+=b'\0'*((-len(b))%4);b+=data;b+=b'\0'*((-len(b))%4)
    return b

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rebuild-kernel',action='store_true',help='rebuild in a new kernel source tree instead of reusing checked version 01 kernel/initramfs')
    options=parser.parse_args()
    reuse=not options.rebuild_kernel
    OUT.mkdir(exist_ok=True)
    base=(ROOT/'saved/build/phase1-published/openiboot.bin').read_bytes()
    assert hashlib.sha256(base).hexdigest()==EXPECTED_BASE
    # Verify the original native boot_linux ABI against its machine code,
    # not offsets taken from a differently linked self-built ELF.
    u=lambda off:struct.unpack_from('<I',base,off)[0]
    got=0x2e52+u(0x2ff0)
    assert [got+u(p) for p in (0x2ff4,0x3014,0x3018,0x300c)]==[
        0x3fb4c,0x3fb50,0x3fb5c,0x3fb60]
    assert (0x29c6+u(0x29f8)+u(0x2a00))==0x3fb58
    assert base[0x2fa0:0x2fa8]==bytes.fromhex('0020391c1a1c2047')
    if not reuse:
        if not SRC.exists():
            print('Copying kernel to isolated experimental source tree',flush=True)
            shutil.copytree(ORIGINAL,SRC,ignore=shutil.ignore_patterns(
                '*.o','*.a','*.cmd','vmlinux','vmlinux.o','System.map','.tmp*',
                'Image','zImage','piggy.gzip','__pycache__'))
        if not (SRC/'.t4-linux-source').exists():
            mach=SRC/'arch/arm/mach-s5l8930'
            font=(ORIGINAL/'drivers/video/console/font_8x8.c').read_text(encoding='latin-1')
            body=font.split('fontdata_8x8[FONTDATAMAX] = {',1)[1].split('};',1)[0]
            body=re.sub(r'/\*.*?\*/','',body,flags=re.S)
            vals=[int(x,16) for x in re.findall(r'0x[0-9a-fA-F]+',body)]
            assert len(vals)==2048
            (mach/'include/mach/t4_ramfont.h').write_text(
                '/* Linux VGA 8x8 font; see drivers/video/console/font_8x8.c and COPYING. */\n'
                '#ifndef T4_RAMFONT_H\n#define T4_RAMFONT_H\n'
                'static const unsigned char t4_ramfont[2048]={'+','.join(map(str,vals))+'};\n#endif\n')
            shutil.copy2(HERE/'ramfb.c',mach/'t4-ramfb.c')
            shutil.copy2(HERE/'uncompress.h',mach/'include/mach/uncompress.h')
            p=mach/'Makefile';p.write_text(p.read_text()+'\nobj-$(CONFIG_MACH_IPOD_TOUCH_4G) += t4-ramfb.o\n')
            p=mach/'mach-ipodtouch4g.c';s=p.read_text()
            assert '/* RAM-only bring-up: do not probe' in s
            s=s.replace('static void __init ipt4g_init(void)',
                'extern void t4_ramfb_reserve(void);\n'
                'extern void t4_ramfb_console_init(void);\n'
                'static void __init t4_map_io(void) {\n'
                ' t4_ramfb_console_init();\n s5l8930_map_io();\n}\n\n'
                'static void __init ipt4g_init(void)')
            s=s.replace('s5l8930_register_mipi_dsim(&video_mode, 2, 57, 1, 3);',
                        '/* RAM test: preserve the already running OpeniBoot display. */')
            s=s.replace('s5l8930_register_clcd(&video_mode, 24, &clcd_info);','')
            s=s.replace('.map_io\t\t= s5l8930_map_io,',
                        '.reserve = t4_ramfb_reserve,\n\t.map_io = t4_map_io,')
            assert '.reserve = t4_ramfb_reserve' in s
            p.write_text(s)
            # Keep all other N81 board support and original RAM-only NAND removal.
            (SRC/'.t4-linux-source').write_text('T4_LINUX_RAM_01\n')
        assert (SRC/'.t4-linux-source').exists()
        # Keep editable diagnostic implementations in sync on incremental builds.
        mach=SRC/'arch/arm/mach-s5l8930'
        shutil.copy2(HERE/'ramfb.c',mach/'t4-ramfb.c')
        shutil.copy2(HERE/'uncompress.h',mach/'include/mach/uncompress.h')
        config=(SRC/'.config').read_text()
        for marker in ['CONFIG_MACH_IPOD_TOUCH_4G=y','# CONFIG_MTD is not set',
                       'CONFIG_BLK_DEV_INITRD=y','CONFIG_FONT_8x8=y']:
            assert marker in config,marker
        # Build the existing N81 configuration, with diagnostic console changes only.
        with (OUT/'kernel-build.log').open('wb') as log:
            result=subprocess.run(['make','-j4','ARCH=arm','CROSS_COMPILE='+CROSS,
                'HOSTCFLAGS=-I'+str(ROOT/'tools/host-include'),'zImage'],
                cwd=SRC,stdout=log,stderr=subprocess.STDOUT)
        if result.returncode:
            print((OUT/'kernel-build.log').read_text(errors='replace')[-6000:])
            raise SystemExit('Kernel build failed; see '+str(OUT/'kernel-build.log'))
        for src,dest in [('arch/arm/boot/zImage','zImage'),('vmlinux','vmlinux'),('.config','kernel.config')]:
            shutil.copy2(SRC/src,OUT/dest)
        # Build PID 1 from source; no libc and no block-device operations.
        subprocess.run([CROSS+'gcc','-nostdlib','-static','-fno-use-linker-plugin',
            '-mcpu=cortex-a8','-marm','-Os','-fno-builtin','-Wl,--build-id=none',
            '-Wl,-e,_start',str(HERE/'init.c'),'-o',str(OUT/'init')],check=True)
        archive=b''.join([cpio_entry('dev',mode=0o40755,ino=1),
            cpio_entry('dev/console',mode=0o20600,rdev=(5,1),ino=2),
            cpio_entry('dev/kmsg',mode=0o20600,rdev=(1,11),ino=3),
            cpio_entry('init',(OUT/'init').read_bytes(),mode=0o100755,ino=4),
            cpio_entry('TRAILER!!!',ino=5)])
        initrd=gzip.compress(archive,compresslevel=9,mtime=0)
        (OUT/'initramfs.cpio.gz').write_bytes(initrd)
        kernel_source=str(SRC)
    else:
        previous=ROOT/'saved/build/T4_LINUX_RAM_01'
        prior=json.loads((previous/'manifest.json').read_text())
        for name in ('zImage','vmlinux','kernel.config','init','initramfs.cpio.gz'):
            assert sha(previous/name)==prior['files'][name]['sha256'],name
            shutil.copy2(previous/name,OUT/name)
        archive=gzip.decompress((OUT/'initramfs.cpio.gz').read_bytes())
        initrd=(OUT/'initramfs.cpio.gz').read_bytes()
        kernel_source=prior['source']
        (OUT/'kernel-reuse.json').write_text(json.dumps({
            'from':str(previous),'reason':'adapter command-line fix only; kernel/initramfs unchanged',
            'files':{n:prior['files'][n] for n in ('zImage','vmlinux','kernel.config','init','initramfs.cpio.gz')}},indent=2)+'\n')
    subprocess.run(['cc','-Wall','-Wextra','-Werror',str(HERE/'test_cmdline.c'),
                    '-o',str(OUT/'test-cmdline')],check=True)
    test=subprocess.check_output([str(OUT/'test-cmdline')])
    (OUT/'cmdline-test.log').write_bytes(test)
    print(test.decode(),end='')
    kernel=(OUT/'zImage').read_bytes()
    (OUT/'sizes.h').write_text('\n'.join(f'#define {k} {v}u' for k,v in {
        'KERNEL_SIZE':len(kernel),'KERNEL_CRC':zlib.crc32(kernel),
        'NATIVE_BOOT_CRC':zlib.crc32(base[0x2e3c:0x3030]),
        'INITRD_SIZE':len(initrd),'INITRD_CRC':zlib.crc32(initrd),
        'INITRD_UNPACKED_SIZE':len(archive)}.items())+'\n')
    subprocess.run([CROSS+'gcc','-nostdlib','-fno-use-linker-plugin','-mcpu=cortex-a8',
        '-mthumb','-Os','-fno-builtin','-fno-unwind-tables',
        '-fno-asynchronous-unwind-tables','-Wl,-Ttext=0x44000000',
        '-Wl,-N','-Wl,--build-id=none','-Wl,-e,t4_linux_stage',
        '-I'+str(OUT),str(HERE/'handoff.c'),'-o',str(OUT/'handoff.elf')],check=True)
    elf=(OUT/'handoff.elf').read_bytes()
    phoff=struct.unpack_from('<I',elf,28)[0];ps,pn=struct.unpack_from('<HH',elf,42)
    seg=[struct.unpack_from('<8I',elf,phoff+i*ps) for i in range(pn)]
    seg=[p for p in seg if p[0]==1 and p[5]]
    end=max(p[2]+p[5] for p in seg); image=bytearray(end-0x44000000)
    for p in seg:image[p[2]-0x44000000:p[2]-0x44000000+p[4]]=elf[p[1]:p[1]+p[4]]
    (OUT/'handoff.bin').write_bytes(image)
    syms=subprocess.check_output([CROSS+'nm',str(OUT/'handoff.elf')],text=True)
    addrs={l.split()[2]:int(l.split()[0],16)|1 for l in syms.splitlines() if len(l.split())==3 and l.split()[2] in ['t4_linux_stage','t4_linux_start']}
    assert len(addrs)==2
    # Host helper has a fixed RAM-only command sequence, no general shell.
    import shlex
    usb=ROOT/'saved/research/libusb-1.0.29'
    flags=['-I'+str(usb/'libusb'),str(usb/'libusb/.libs/libusb-1.0.a'),
        '-framework','IOKit','-framework','CoreFoundation','-framework','Security']
    if not (usb/'libusb/.libs/libusb-1.0.a').exists():
        flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','libusb-1.0'],text=True))
    subprocess.run(['cc','-Wall','-Wextra','-Werror',str(HERE/'usb.c'),'-o',str(OUT/'linux-usb')]+flags,check=True)
    files=['zImage','vmlinux','kernel.config','init','initramfs.cpio.gz','handoff.bin','handoff.elf','linux-usb']
    m={'variant':'T4_LINUX_RAM_02','status':'built; hardware Linux execution unconfirmed',
       'source':kernel_source,'kernel_reused_from_01':reuse,'baseline_sha256':EXPECTED_BASE,'machine_id':3564,
       'kernel_address':0x42000000,'initrd_staging_address':0x43000000,
       'handoff_address':0x44000000,'entries':addrs,
       'native_boot_linux_thumb':0x2e3d,'initrd_final_address':0x48000000,
       'files':{n:{'bytes':(OUT/n).stat().st_size,'sha256':sha(OUT/n)} for n in files}}
    (OUT/'manifest.json').write_text(json.dumps(m,indent=2)+'\n')
    print('Built isolated RAM experiment:',OUT)
    print('Hardware status: NOT TESTED; use linux-ramtest/run.py --stage or --boot')

if __name__=='__main__':main()
