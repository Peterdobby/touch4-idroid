#!/usr/bin/env python3
"""UI03: legacy bionic TLS compatibility; fast CRC; preserve RAM-only baseline."""
import hashlib,json,os,shutil,struct,subprocess,zlib,difflib
from pathlib import Path
from initramfs import prepare
ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
NAME='T4_ANDROID_UI_03'
OUT=ROOT/'saved/build'/NAME
SOURCE=ROOT/'saved/sources/iDroid-kernel-T4_ANDROID_UI_03'
CROSS=os.environ.get('CROSS',str(ROOT/'saved/toolchain/arm-eabi-4.8/bin/arm-eabi-'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    OUT.mkdir(exist_ok=True)
    # Preserve the proven baselines and verify them again after building.
    protected=[ROOT/'saved/build/phase1-published/openiboot.bin',ROOT/'saved/build/phase1-published/openiboot-native.bin',ROOT/'saved/build/T4_LINUX_DIAG_12/zImage',ROOT/'saved/build/T4_ANDROID_INIT_01/zImage',ROOT/'saved/build/T4_ANDROID_INIT_04/zImage',ROOT/'saved/build/T4_ANDROID_INIT_04/handoff.bin',ROOT/'saved/build/T4_ANDROID_INIT_04/initramfs.cpio.gz',ROOT/'saved/build/T4_ANDROID_UI_01/zImage',ROOT/'saved/build/T4_ANDROID_UI_01/handoff.bin',ROOT/'saved/build/T4_ANDROID_UI_01/initramfs.cpio.gz']
    protected={str(p):sha(p) for p in protected if p.exists()}
    previous=ROOT/'saved/build/T4_ANDROID_INIT_04'
    oldmanifest=json.loads((previous/'manifest.json').read_text())
    with (OUT/'kernel-build.log').open('wb') as log:
        subprocess.run(['make','-j6','ARCH=arm','CROSS_COMPILE='+CROSS,'HOSTCFLAGS=-I'+str(ROOT/'tools/host-include'),'zImage'],cwd=SOURCE,stdout=log,stderr=subprocess.STDOUT,check=True)
    prepare(ROOT,HERE,OUT,CROSS)
    for src,dst in [('arch/arm/boot/zImage','zImage.original'),('arch/arm/boot/Image','Image.expected'),('vmlinux','vmlinux'),('.config','kernel.config')]:
        shutil.copy2(SOURCE/src,OUT/dst)
    config=(OUT/'kernel.config').read_text()
    for n in ['NET','UNIX','TMPFS','PROC_FS','SYSFS','UNIX98_PTYS','ANDROID_BINDER_IPC','ASHMEM','ANDROID_LOGGER','VFP','NEON','INPUT_EVDEV']:assert f'CONFIG_{n}=y\n' in config,n
    for n in ['MTD','MMC','SCSI','ATA','USB_STORAGE','FRAMEBUFFER_CONSOLE','SUSPEND','PM_RUNTIME']:assert f'CONFIG_{n}=y\n' not in config,n
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
    word=lambda va:struct.unpack_from('<I',decompressed,va-0xc0008000)[0]
    def bl_target(va):
        w=word(va);assert w>>24==0xeb,hex(va)
        delta=w&0xffffff
        if delta&0x800000:delta-=0x1000000
        return va+8+delta*4
    def find_call(start,limit,target):
        calls=[va for va in range(start,start+limit,4) if word(va)>>24==0xeb and bl_target(va)==target]
        assert len(calls)==1,(hex(start),hex(target),calls)
        return calls[0]
    # Guard the compiler regression itself: one live MRC before and one
    # after the native control-register write, never a reused saved value.
    handler=ks['t4_early_noalign']
    reads=[va for va in range(handler,handler+0x50,4) if word(va)&0xffff0fff==0xee110f10]
    noalign_call=find_call(handler,0x50,ks['noalign_setup'])
    assert len(reads)==2 and reads[0]<noalign_call<reads[1], 'stale SCTLR read regression'
    debug=find_call(ks['start_kernel'],0x80,ks['debug_objects_early_init'])
    arch=find_call(ks['start_kernel'],0x100,ks['setup_arch'])
    sanity=find_call(ks['setup_arch'],0x600,ks['sanity_check_meminfo'])
    assert bl_target(debug+4)==ks['cgroup_init_early']
    assert word(arch-4)&0xfffff000==0xe28d0000
    ldr=word(sanity-4);assert ldr&0xfffff000==0xe59f7000
    assert word(ks['__mmap_switched'])==0xe28f3040 and word(ks['__mmap_switched']+4)==0xe8b300f0
    assert bl_target(ks['t4_map_io']+4)==ks['t4_ramfb_console_init']
    addresses={'CORE_SWITCHED':ks['__mmap_switched'],'CORE_SWITCHED_DATA':ks['__mmap_switched_data'],
        'CORE_SWITCHED_RESUME':ks['__mmap_switched']+8,'CORE_DEBUG_OBJECTS':ks['debug_objects_early_init'],
        'CORE_DEBUG_RETURN':debug+8,'CORE_DEBUG_RESUME':ks['cgroup_init_early'],'CORE_ARCH_ARG_INSN':word(arch-4),
        'CORE_ARCH_RETURN':arch+4,'CORE_SETUP_ARCH':ks['setup_arch'],
        'CORE_CONSOLE_INIT':ks['t4_ramfb_console_init'],'CORE_ARCH_R7_LITERAL':sanity+4+(ldr&0xfff),
        'CORE_ARCH_SANITY_RETURN':sanity+4,'CORE_SANITY_CHECK':ks['sanity_check_meminfo']}
    (OUT/'core-addresses.h').write_text('\n'.join('#define '+k+' '+hex(v) for k,v in addresses.items())+'\n')
    patches=[]
    for va,vector in [(ks['stext'],0x44000018),(ks['stext']+12,0x4400001c),
            (ks['stext']+36,0x44000020),(ks['__mmap_switched'],0x44000024),
            (debug,0x44000028),(arch-4,0x4400002c),(sanity-4,0x44000030)]:
        patches.append((va-0xc0000000,word(va),word(va+4),0xe51ff004,vector))
    # Console is now initialized before paging_init as in INIT01. Suppress only
    # its second call in t4_map_io; keep native board CPU/clock/UART calls intact.
    va=ks['t4_map_io']+4
    patches.append((va-0xc0000000,word(va),word(va+4),0xe1a00000,word(va+4)))
    instrumented=bytearray(decompressed)
    for a,b,c,d,e in patches:struct.pack_into('<2I',instrumented,a-0x8000,d,e)
    (OUT/'Image.instrumented').write_bytes(instrumented)
    (OUT/'core-patches.h').write_text('static const unsigned core_patches[][5]={\n'+
        '\n'.join('{'+','.join(hex(v)+'u' for v in row)+'},' for row in patches)+'\n};\n'+
        '#define CORE_PATCH_COUNT '+str(len(patches))+'u\n'+
        '#define IMAGE_INSTRUMENTED_CRC '+str(zlib.crc32(instrumented))+'u\n'+
        '#define KERNEL_BANNER_VA '+hex(ks['linux_banner'])+'u\n'+
        '#define KERNEL_PRINTK_VA '+hex(ks['printk'])+'u\n')
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
    for i,n in enumerate(['t4_zimage_probe','t4_after_enable','t4_before_decompress','t4_after_decompress','t4_putstr','t4_before_kernel','t4_core_entry','t4_processor_ok','t4_atags_pages','t4_mmap_switched','t4_early_c','t4_printk_returned','t4_start_native_console']):assert symbols[n]==0x44000000+4*i
    assert not subprocess.check_output([CROSS+'nm','-u',str(OUT/'handoff.elf')],text=True).strip()
    usb=ROOT/'saved/research/libusb-1.0.29'
    subprocess.run(['cc','-Wall','-Wextra','-Werror',define,extra,str(HERE/'usb.c'),'-o',str(OUT/'linux-usb'),
        '-I'+str(usb/'libusb'),str(usb/'libusb/.libs/libusb-1.0.a'),'-framework','IOKit','-framework','CoreFoundation','-framework','Security'],check=True)
    subprocess.run(['cc','-Wall','-Wextra','-Werror',define,extra,str(HERE.parent/'test_cmdline.c'),'-o',str(OUT/'test-cmdline')],check=True)
    (OUT/'cmdline-test.log').write_bytes(subprocess.check_output([str(OUT/'test-cmdline')]))
    (OUT/'handoff.disasm').write_text(subprocess.check_output([CROSS+'objdump','-d',str(OUT/'handoff.elf')],text=True))
    # Reviewable source delta against the previously successful Linux source.
    delta=[]
    for rel in sorted(set(json.loads((HERE/'native-fixes.json').read_text())+['arch/arm/mach-s5l8930/Makefile','arch/arm/mach-s5l8930/t4-ramfb.c','arch/arm/mach-s5l8930/t4-android-fb.c'])):
        old=ROOT/'saved/sources/iDroid-kernel-T4_LINUX_RAM_01'/rel;new=SOURCE/rel
        delta.extend(difflib.unified_diff((old.read_text().splitlines(True) if old.exists() else []),new.read_text().splitlines(True),fromfile='a/'+rel,tofile='b/'+rel))
    (OUT/'native-userspace-prerequisites.patch').write_text(''.join(delta))
    files=['Image.instrumented','core-addresses.h','core-patches.h','zImage','zImage.original','Image.expected','initramfs.cpio.gz','init','kernel.config','vmlinux','handoff.bin','handoff.elf','linux-usb','android-init','init.rc','android-input.json','native-userspace-prerequisites.patch']
    manifest={'variant':NAME,'status':'built; hardware result pending','baseline_sha256':hashlib.sha256(base).hexdigest(),
        'repair':'mirror hardware TLS to legacy 0xffff0ff0 on set_tls and every context switch, as legacy iDroid; bounded user fault logging; table CRC with visible progress',
        'source':str(SOURCE),'machine_id':3564,'entries':{n:symbols[n]|1 for n in ['t4_linux_stage','t4_linux_start']},
        'zimage_modified_ranges':ranges,'gzip_offset':gz,'expected_image_crc32':f'{zlib.crc32(decompressed):08x}',
        'kernel_runtime_patches':patches,'core_addresses':addresses,
        'unchanged_inputs':{n:oldmanifest['files'][n]['sha256'] for n in ['android-init']},
        'ram_layout':{'kernel_upload':0x42000000,'kernel_decompress_input':0x02000000,'kernel_image':0x8000,'initrd_upload':0x44800000,'initrd_physical':0x04800000,'initrd_limit':0x03800000,'helper':0x44000000,'display_info':0x43f00000,'framebuffer_min_physical':0x08000000},'native_fixes':json.loads((HERE/'native-fixes.json').read_text()),
        'storage_stubs':stubs,'prerequisites':['binder','ashmem','logger','VFP/NEON','evdev','alarm','cgroups','inherited fbdev'],'kernel_symbols':{n:ks[n] for n in ['t4_early_noalign','noalign_setup','cr_alignment','cr_no_alignment','panic','printk','memset','init_object','sys_socket','sys_bind','sys_socketpair','sys_connect','sys_ni_syscall']},
        'preserved_display_gates':[11,15,17,18],'intentional_stop':None,
        'success':'actual Launcher visible on device; sys.boot_completed=1 and dumpsys resumed activity are supporting evidence only',
        'protected_baselines':protected,'files':{n:{'bytes':(OUT/n).stat().st_size,'sha256':sha(OUT/n)} for n in files}}
    for p,d in protected.items():assert sha(Path(p))==d,p
    (OUT/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print('Built',OUT,'; original Android init preserved; no USB access.')
if __name__=='__main__':main()
