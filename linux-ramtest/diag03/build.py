#!/usr/bin/env python3
"""Build numbered RAM handoff diagnostics; do not access USB or overwrite 02."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import zlib

ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
OUT=ROOT/'saved/build/T4_LINUX_DIAG_03'
PREV=ROOT/'saved/build/T4_LINUX_RAM_02'
CROSS=os.environ.get('CROSS',str(ROOT/'saved/toolchain/arm-eabi-4.8/bin/arm-eabi-'))
NAME='T4_LINUX_DIAG_03'

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    OUT.mkdir(exist_ok=True)
    prior=json.loads((PREV/'manifest.json').read_text())
    for n in ['zImage','initramfs.cpio.gz','init','kernel.config','vmlinux']:
        assert sha(PREV/n)==prior['files'][n]['sha256'],n
        shutil.copy2(PREV/n,OUT/('zImage.original' if n=='zImage' else n))
    kernel=bytearray((OUT/'zImage.original').read_bytes())
    assert kernel[:12]==struct.pack('<3I',*[0xe1a00000]*3)
    assert struct.unpack_from('<I',kernel,0x24)[0]==0x016f2818
    # Only three header NOPs change; the probe resumes at untouched offset 0x0c.
    kernel[:12]=struct.pack('<3I',0xe59fc000,0xe12fff1c,0x44000000)
    (OUT/'zImage').write_bytes(kernel)
    initrd=(OUT/'initramfs.cpio.gz').read_bytes()
    base=(ROOT/'saved/build/phase1-published/openiboot.bin').read_bytes()
    assert hashlib.sha256(base).hexdigest()==prior['baseline_sha256']
    (OUT/'sizes.h').write_text('\n'.join(f'#define {k} {v}u' for k,v in {
        'KERNEL_SIZE':len(kernel),'KERNEL_CRC':zlib.crc32(kernel),
        'NATIVE_BOOT_CRC':zlib.crc32(base[0x2e3c:0x3030]),
        'INITRD_SIZE':len(initrd),'INITRD_CRC':zlib.crc32(initrd),
        'INITRD_UNPACKED_SIZE':struct.unpack_from('<I',initrd,len(initrd)-4)[0]}.items())+'\n')
    define='-DT4_TEST_NAME="'+NAME+'"'
    subprocess.run([CROSS+'gcc','-nostdlib','-fno-use-linker-plugin','-mcpu=cortex-a8',
        '-mthumb','-Os','-fno-builtin','-fno-unwind-tables','-fno-asynchronous-unwind-tables',
        '-Wl,-Ttext=0x44000000','-Wl,-N','-Wl,--build-id=none','-Wl,-e,t4_linux_stage',
        define,'-I'+str(OUT),'-I'+str(Path(prior['source'])/'arch/arm/mach-s5l8930/include'),
        str(HERE/'entry.S'),str(HERE/'handoff.c'),'-o',str(OUT/'handoff.elf')],check=True)
    elf=(OUT/'handoff.elf').read_bytes()
    phoff=struct.unpack_from('<I',elf,28)[0];ps,pn=struct.unpack_from('<HH',elf,42)
    seg=[struct.unpack_from('<8I',elf,phoff+i*ps) for i in range(pn)]
    seg=[p for p in seg if p[0]==1 and p[5]]
    assert min(p[2] for p in seg)==0x44000000
    end=max(p[2]+p[5] for p in seg);image=bytearray(end-0x44000000)
    for p in seg:image[p[2]-0x44000000:p[2]-0x44000000+p[4]]=elf[p[1]:p[1]+p[4]]
    assert len(image)<=65536
    (OUT/'handoff.bin').write_bytes(image)
    symbols=subprocess.check_output([CROSS+'nm',str(OUT/'handoff.elf')],text=True)
    symbols={l.split()[2]:int(l.split()[0],16) for l in symbols.splitlines() if len(l.split())==3}
    assert symbols['t4_zimage_probe']==0x44000000
    assert not subprocess.check_output([CROSS+'nm','-u',str(OUT/'handoff.elf')],text=True).strip()
    usb=ROOT/'saved/research/libusb-1.0.29'
    flags=['-I'+str(usb/'libusb'),str(usb/'libusb/.libs/libusb-1.0.a'),
        '-framework','IOKit','-framework','CoreFoundation','-framework','Security']
    subprocess.run(['cc','-Wall','-Wextra','-Werror',define,str(HERE.parent/'usb.c'),
        '-o',str(OUT/'linux-usb')]+flags,check=True)
    subprocess.run(['cc','-Wall','-Wextra','-Werror',define,str(HERE.parent/'test_cmdline.c'),
        '-o',str(OUT/'test-cmdline')],check=True)
    (OUT/'cmdline-test.log').write_bytes(subprocess.check_output([str(OUT/'test-cmdline')]))
    dis=subprocess.check_output([CROSS+'objdump','-d',str(OUT/'handoff.elf')],text=True)
    (OUT/'handoff.disasm').write_text(dis)
    files=['zImage','zImage.original','initramfs.cpio.gz','init','kernel.config','vmlinux','handoff.bin','handoff.elf','linux-usb']
    manifest={'variant':NAME,'status':'built; hardware result pending',
        'baseline_sha256':prior['baseline_sha256'],'source':prior['source'],
        'machine_id':3564,'entries':{n:symbols[n]|1 for n in ['t4_linux_stage','t4_linux_start']},
        'kernel_probe_arm':symbols['t4_zimage_probe'],'zimage_modified_range':[0,12],
        'zimage_resume_address':0x0200000c,'native_functions':{
            'EnterCriticalSection':0x4c1,'exit_modules':0x391,
            'arm_disable_caches':0x829,'mmu_disable':0x12da1},
        'files':{n:{'bytes':(OUT/n).stat().st_size,'sha256':sha(OUT/n)} for n in files}}
    (OUT/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print('Built',OUT,'; no USB access; checkpoints are not Linux boot evidence.')
if __name__=='__main__':main()
