#!/usr/bin/env python3
"""Rebuild Android init RAM test 02. Offline only; never opens USB."""
import hashlib,json,os,shutil,struct,subprocess,zlib,difflib
from pathlib import Path
from initramfs import prepare
ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
NAME='T4_ANDROID_INIT_02'
OUT=ROOT/'saved/build'/NAME
SOURCE=ROOT/'saved/sources/iDroid-kernel-T4_ANDROID_INIT_02'
CROSS=os.environ.get('CROSS',str(ROOT/'saved/toolchain/arm-eabi-4.8/bin/arm-eabi-'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    OUT.mkdir(exist_ok=True)
    # Preserve the proven baselines and verify them again after building.
    protected=[ROOT/'saved/build/phase1-published/openiboot.bin',ROOT/'saved/build/phase1-published/openiboot-native.bin',ROOT/'saved/build/T4_LINUX_DIAG_12/zImage',ROOT/'saved/build/T4_ANDROID_INIT_01/zImage']
    protected={str(p):sha(p) for p in protected if p.exists()}
    with (OUT/'kernel-build.log').open('wb') as log:
        subprocess.run(['make','-j6','ARCH=arm','CROSS_COMPILE='+CROSS,
            'HOSTCFLAGS=-I'+str(ROOT/'tools/host-include'),'zImage'],cwd=SOURCE,stdout=log,stderr=subprocess.STDOUT,check=True)
    for src,dst in [('arch/arm/boot/zImage','zImage.original'),('arch/arm/boot/Image','Image.expected'),('vmlinux','vmlinux'),('.config','kernel.config')]:
        shutil.copy2(SOURCE/src,OUT/dst)
    config=(OUT/'kernel.config').read_text()
    for n in ['NET','UNIX','TMPFS','PROC_FS','SYSFS','UNIX98_PTYS']:assert f'CONFIG_{n}=y\n' in config,n
    for n in ['INET','NETDEVICES','MTD','MMC','SCSI','ATA']:assert f'CONFIG_{n}=y\n' not in config,n
    prepare(ROOT,HERE,OUT,CROSS)
    nm=subprocess.check_output([CROSS+'nm',str(OUT/'vmlinux')],text=True)
    ks={s[2]:int(s[0],16) for l in nm.splitlines() if len(s:=l.split())==3}
    for n in ['sys_socket','sys_bind','sys_socketpair','sys_connect']:assert ks[n]!=ks['sys_ni_syscall'],n
    original=(OUT/'zImage.original').read_bytes();kernel=bytearray(original)
    decompressed=(OUT/'Image.expected').read_bytes()
    gz=original.index(b'\x1f\x8b\x08')
    assert gz==0x469b and zlib.decompress(original[gz:],31)==decompressed
    # All NAND/VFL registrations and public write/erase entries are native stubs.
    stubs={n:0 for n in ['h2fmi_mod_init','register_vfl','s5l8930_register_h2fmi']}
    stubs.update({n:-19 for n in ['apple_nand_write_page','apple_nand_erase_block','h2fmi_nand_write','h2fmi_nand_erase']})
    for n,ret in stubs.items():
        words=struct.unpack_from('<2I',decompressed,ks[n]-0xc0008000)
        assert words==(0xe3a00000 if ret==0 else 0xe3e00012,0xe12fff1e),(n,words)
    assert ks['stext']==0xc0008000 and ks['memset']!=ks['__t4_memset_body']
    assert kernel[:32]==struct.pack('<8I',*[0xe1a00000]*8)
    assert struct.unpack_from('<I',kernel,0x24)[0]==0x016f2818
    for i in range(4):struct.pack_into('<2I',kernel,i*8,0xe51ff004,0x44000000+i*4)
    patches={0x328:(0xe1a0f00c,8),0x160:(0xeb000269,16),0x164:(0xeb00012d,24)}
    for site,(expected,target) in patches.items():
        assert struct.unpack_from('<I',kernel,site)[0]==expected,hex(site)
        struct.pack_into('<I',kernel,site,0xea000000|(((target-site-8)//4)&0xffffff))
    for site,expected,vector in [(0x7e0,(0xe92d4ff0,0xe3a0363f),0x44000010),(0x170,(0xe1a01007,0xe1a02008),0x44000014)]:
        assert struct.unpack_from('<2I',kernel,site)==expected,hex(site)
        struct.pack_into('<2I',kernel,site,0xe51ff004,vector)
    ranges=[[0,32],[0x160,0x168],[0x170,0x178],[0x328,0x32c],[0x7e0,0x7e8]]
    allowed={i for a,b in ranges for i in range(a,b)}
    assert all(a==b or i in allowed for i,(a,b) in enumerate(zip(kernel,original)))
    assert kernel[gz:]==original[gz:] and kernel[0x318:0x328]==original[0x318:0x328]
    assert kernel[0x560:0x7e0]==original[0x560:0x7e0]
    (OUT/'zImage').write_bytes(kernel)
    initrd=(OUT/'initramfs.cpio.gz').read_bytes();base=(ROOT/'saved/build/phase1-published/openiboot.bin').read_bytes()
    assert hashlib.sha256(base).hexdigest()=='cd32dbac3d10a81b64226ffa4057fa8e202e699e3ff2182a7560eea077d5fbe1'
    (OUT/'sizes.h').write_text('\n'.join(f'#define {k} {v}u' for k,v in {
        'KERNEL_SIZE':len(kernel),'KERNEL_CRC':zlib.crc32(kernel),'IMAGE_SIZE':len(decompressed),'IMAGE_CRC':zlib.crc32(decompressed),
        'NATIVE_BOOT_CRC':zlib.crc32(base[0x2e3c:0x3030]),'INITRD_SIZE':len(initrd),'INITRD_CRC':zlib.crc32(initrd),
        'INITRD_UNPACKED_SIZE':struct.unpack_from('<I',initrd,len(initrd)-4)[0]}.items())+'\n')
    define='-DT4_TEST_NAME="'+NAME+'"';extra='-DT4_EXTRA_ARGS=" slub_debug=FZPU noalign"'
    subprocess.run([CROSS+'gcc','-nostdlib','-fno-use-linker-plugin','-mcpu=cortex-a8','-mthumb','-Os','-fno-builtin',
        '-fno-unwind-tables','-fno-asynchronous-unwind-tables','-Wl,-T,'+str(HERE/'handoff.ld'),'-Wl,-N','-Wl,--build-id=none',
        '-Wl,-e,t4_linux_stage',define,extra,'-I'+str(OUT),'-I'+str(SOURCE/'arch/arm/mach-s5l8930/include'),
        str(HERE/'entry.S'),str(HERE/'handoff.c'),'-o',str(OUT/'handoff.elf')],check=True)
    elf=(OUT/'handoff.elf').read_bytes();ph=struct.unpack_from('<I',elf,28)[0];ps,pn=struct.unpack_from('<HH',elf,42)
    seg=[struct.unpack_from('<8I',elf,ph+i*ps) for i in range(pn)];seg=[p for p in seg if p[0]==1 and p[5]]
    assert min(p[2] for p in seg)==0x44000000
    image=bytearray(max(p[2]+p[5] for p in seg)-0x44000000)
    for p in seg:image[p[2]-0x44000000:p[2]-0x44000000+p[4]]=elf[p[1]:p[1]+p[4]]
    assert len(image)<=0x8000
    (OUT/'handoff.bin').write_bytes(image)
    symbols=subprocess.check_output([CROSS+'nm',str(OUT/'handoff.elf')],text=True)
    symbols={s[2]:int(s[0],16) for l in symbols.splitlines() if len(s:=l.split())==3}
    for i,n in enumerate(['t4_zimage_probe','t4_after_enable','t4_before_decompress','t4_after_decompress','t4_putstr','t4_before_kernel']):assert symbols[n]==0x44000000+4*i
    assert not subprocess.check_output([CROSS+'nm','-u',str(OUT/'handoff.elf')],text=True).strip()
    usb=ROOT/'saved/research/libusb-1.0.29'
    subprocess.run(['cc','-Wall','-Wextra','-Werror',define,extra,str(HERE.parent/'usb.c'),'-o',str(OUT/'linux-usb'),
        '-I'+str(usb/'libusb'),str(usb/'libusb/.libs/libusb-1.0.a'),'-framework','IOKit','-framework','CoreFoundation','-framework','Security'],check=True)
    subprocess.run(['cc','-Wall','-Wextra','-Werror',define,extra,str(HERE.parent/'test_cmdline.c'),'-o',str(OUT/'test-cmdline')],check=True)
    (OUT/'cmdline-test.log').write_bytes(subprocess.check_output([str(OUT/'test-cmdline')]))
    (OUT/'handoff.disasm').write_text(subprocess.check_output([CROSS+'objdump','-d',str(OUT/'handoff.elf')],text=True))
    # Reviewable source delta against the previously successful Linux source.
    delta=[]
    for rel in json.loads((HERE/'native-fixes.json').read_text()):
        old=ROOT/'saved/sources/iDroid-kernel-T4_LINUX_RAM_01'/rel;new=SOURCE/rel
        delta.extend(difflib.unified_diff(old.read_text().splitlines(True),new.read_text().splitlines(True),fromfile='a/'+rel,tofile='b/'+rel))
    (OUT/'native-userspace-prerequisites.patch').write_text(''.join(delta))
    files=['zImage','zImage.original','Image.expected','initramfs.cpio.gz','init','kernel.config','vmlinux','handoff.bin','handoff.elf','linux-usb','android-init','t4-probe','init.rc','android-input.json','native-userspace-prerequisites.patch']
    manifest={'variant':NAME,'status':'built; hardware result pending','baseline_sha256':hashlib.sha256(base).hexdigest(),
        'source':str(SOURCE),'machine_id':3564,'entries':{n:symbols[n]|1 for n in ['t4_linux_stage','t4_linux_start']},
        'zimage_modified_ranges':ranges,'gzip_offset':gz,'expected_image_crc32':f'{zlib.crc32(decompressed):08x}',
        'kernel_runtime_patches':[],'native_fixes':json.loads((HERE/'native-fixes.json').read_text()),
        'storage_stubs':stubs,'kernel_symbols':{n:ks[n] for n in ['memset','init_object','sys_socket','sys_bind','sys_socketpair','sys_connect','sys_ni_syscall']},
        'preserved_display_gates':[11,15,17,18],'intentional_stop':None,
        'success':'ANDROID_INIT_ENVIRONMENT_CONFIRMED and continuing ANDROID_INIT_SERVICE_REACHED; not Android framework',
        'protected_baselines':protected,'files':{n:{'bytes':(OUT/n).stat().st_size,'sha256':sha(OUT/n)} for n in files}}
    for p,d in protected.items():assert sha(Path(p))==d,p
    (OUT/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print('Built',OUT,'; original Android init preserved; no USB access.')
if __name__=='__main__':main()
