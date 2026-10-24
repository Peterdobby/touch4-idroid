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
OUT=ROOT/'saved/build/T4_LINUX_DIAG_11'
PREV=ROOT/'saved/build/T4_LINUX_RAM_02'
CROSS=os.environ.get('CROSS',str(ROOT/'saved/toolchain/arm-eabi-4.8/bin/arm-eabi-'))
NAME='T4_LINUX_DIAG_11'

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    OUT.mkdir(exist_ok=True)
    prior=json.loads((PREV/'manifest.json').read_text())
    for n in ['zImage','initramfs.cpio.gz','init','kernel.config','vmlinux']:
        assert sha(PREV/n)==prior['files'][n]['sha256'],n
        shutil.copy2(PREV/n,OUT/('zImage.original' if n=='zImage' else n))
    kernel=bytearray((OUT/'zImage.original').read_bytes())
    assert kernel[:32]==struct.pack('<8I',*[0xe1a00000]*8)
    assert struct.unpack_from('<I',kernel,0x24)[0]==0x016f2818
    # Four register-free absolute veneers occupy the eight original header NOPs.
    for i in range(4):
        struct.pack_into('<2I',kernel,i*8,0xe51ff004,0x44000000+i*4)
    patches={0x328:(0xe1a0f00c,8),0x160:(0xeb000269,16),0x164:(0xeb00012d,24)}
    for site,(expected,target) in patches.items():
        assert struct.unpack_from('<I',kernel,site)[0]==expected,hex(site)
        # B preserves LR, unlike BL. The assembly probe replays displaced actions.
        struct.pack_into('<I',kernel,site,0xea000000|(((target-site-8)//4)&0xffffff))
    # Replace only diagnostic putstr, and stop before the final kernel branch.
    for site,expected,vector in [(0x7e0,(0xe92d4ff0,0xe3a0363f),0x44000010),
                                 (0x170,(0xe1a01007,0xe1a02008),0x44000014)]:
        assert struct.unpack_from('<2I',kernel,site)==expected,hex(site)
        struct.pack_into('<2I',kernel,site,0xe51ff004,vector)
    original=(OUT/'zImage.original').read_bytes()
    allowed=(set(range(32))|{p+i for p in patches for i in range(4)}|
             set(range(0x7e0,0x7e8))|set(range(0x170,0x178)))
    assert len(kernel)==len(original)
    assert all(a==b or i in allowed for i,(a,b) in enumerate(zip(kernel,original)))
    # Leave the SCTLR write, read-back and instruction barrier contiguous.
    assert kernel[0x318:0x328]==original[0x318:0x328]
    assert kernel[0x7e8:]==original[0x7e8:]
    assert kernel[0x469b:]==original[0x469b:]
    # Independent expected output: gzip integrity check + exact Image comparison.
    decompressed=zlib.decompress(original[0x469b:0xd0a95],31)
    assert decompressed==(Path(prior['source'])/'arch/arm/boot/Image').read_bytes()
    (OUT/'Image.expected').write_bytes(decompressed)
    # Pin core hooks to the verified ELF and expected ARM words. Applied in RAM
    # only after the original decompressed Image CRC passed, before entering it.
    nm=subprocess.check_output([CROSS+'nm',str(OUT/'vmlinux')],text=True)
    ksyms={s[2]:int(s[0],16) for l in nm.splitlines() if len(s:=l.split())==3}
    assert {n:ksyms[n] for n in ['stext','__mmap_switched','start_kernel','linux_banner']}=={
        'stext':0xc0008000,'__mmap_switched':0xc0008180,
        'start_kernel':0xc00085f4,'linux_banner':0xc01392d7}
    expected={'create_mapping':0xc000c720,'iotable_init':0xc000ca4c,
        's3c_init_cpu':0xc000da74,'s3c24xx_init_clocks':0xc000db38,
        's3c24xx_init_uarts':0xc000dc20,'cpu_id':0xc0019e88,
        's5l8930_uartcfgs':0xc0019ea4,'memblock_reserve':0xc00790b4,
        't4_ramfb_reserve':0xc000d89c,'s5l_clock_gate_toggle_idx':0xc0029a98,
        'noalign_setup':0xc000c4d0,'cr_alignment':0xc018ded4,
        'cr_no_alignment':0xc018ded8,'die':0xc0024e34,
        'setup_per_cpu_areas':0xc00110ec,'early_irq_init':0xc000ff14,
        'init_IRQ':0xc000ae00,'build_all_zonelists':0xc0134ddc,
        'kmem_cache_alloc':0xc007eec8,'con_insert_unipair':0xc01126c4}
    assert all(ksyms[n]==v for n,v in expected.items())
    # Verify protected IDs against the actual native kernel data layout too.
    word=lambda va:struct.unpack_from('<I',decompressed,va-0xc0008000)[0]
    # Pin the suspected first fault and the complete native noalign handler.
    assert word(ksyms['pcpu_dump_alloc_info']+0x20)==0xe58d2027
    assert word(ksyms['kmem_cache_alloc']+0x64)==0xe794c00c
    assert word(ksyms['con_insert_unipair']+0x38)==0xebfdb1f1
    assert [word(ksyms['noalign_setup']+4*i) for i in range(14)]==[
        0xe59f2028,0xe5923000,0xe3c33002,0xe5823000,0xe59f201c,
        0xe5921000,0xe3c11002,0xe5821000,0xee013f10,0xf57ff06f,
        0xe3a00001,0xe12fff1e,0xc018ded4,0xc018ded8]
    assert word(ksyms['s5l_power_zones']+3*12+4)==0x0b
    assert word(ksyms['clk_clcd']+32)==0x0f12
    assert word(ksyms['clk_mipi_dsi']+32)==0x0311
    names=['VIC0','VIC1','VIC2','VIC3','UART0','UART1','UART2',
           'PMGR0','PMGR1','PMGR2','PMGR3','PMGR4','PMGR5','PMGR6',
           'GPIO','USB_PHY','TIMER']
    io=[]
    for i,n in enumerate(names):
        va,pfn,length,kind=struct.unpack_from('<4I',decompressed,ksyms['s5l8930_iodesc']-0xc0008000+i*16)
        io.append({'index':i+1,'name':n,'virtual':f'{va:08x}',
                   'physical':f'{pfn<<12:08x}','bytes':length,'type':kind})
    (OUT/'io-table.json').write_text(json.dumps(io,indent=2)+'\n')
    subprocess.run([CROSS+'gcc','-nostdlib','-fno-use-linker-plugin','-mcpu=cortex-a8',
        '-marm','-Os','-fno-builtin','-fno-unwind-tables','-fno-asynchronous-unwind-tables',
        '-Wl,-T,'+str(HERE/'resident.ld'),'-Wl,-N','-Wl,--build-id=none',
        '-Wl,-e,resident_io_entry',str(HERE/'resident.S'),str(HERE/'resident.c'),
        '-o',str(OUT/'resident.elf')],check=True)
    resident=(OUT/'resident.elf').read_bytes()
    ph=struct.unpack_from('<I',resident,28)[0];sz,count=struct.unpack_from('<HH',resident,42)
    segments=[struct.unpack_from('<8I',resident,ph+i*sz) for i in range(count)]
    segments=[s for s in segments if s[0]==1 and s[5]]
    assert len(segments)==1 and segments[0][2]==0xc3e00000
    seg=segments[0];blob=resident[seg[1]:seg[1]+seg[4]]+bytes(seg[5]-seg[4])
    assert len(blob)<0x10000
    rnm=subprocess.check_output([CROSS+'nm',str(OUT/'resident.elf')],text=True)
    rs={s[2]:int(s[0],16) for l in rnm.splitlines() if len(s:=l.split())==3}
    assert [rs[n] for n in ['resident_io_entry','resident_board_entry','resident_reserve_entry','resident_gate_entry']]==[0xc3e00000,0xc3e00004,0xc3e00008,0xc3e0000c]
    assert [rs[n] for n in ['resident_percpu_entry','resident_irq_entry','resident_fatal_entry']]==[0xc3e00010,0xc3e00014,0xc3e00018]
    assert not subprocess.check_output([CROSS+'nm','-u',str(OUT/'resident.elf')],text=True).strip()
    (OUT/'resident.bin').write_bytes(blob)
    (OUT/'resident-blob.h').write_text('static const unsigned char resident_blob[]={'+
        ','.join(str(b) for b in blob)+'};\n#define RESIDENT_SIZE '+str(len(blob))+'u\n'+
        '#define RESIDENT_CRC '+str(zlib.crc32(blob))+'u\n')
    (OUT/'resident.disasm').write_text(subprocess.check_output([CROSS+'objdump','-d',str(OUT/'resident.elf')],text=True))
    core_patches=[
        (0x8000,0xe321f0d3,0xee109f10,0x44000018),
        (0x800c,0xe1b0a005,0x0a003e53,0x4400001c),
        (0x8024,0xeb000043,0xeb000007,0x44000020),
        (0x8180,0xe28f3040,0xe8b300f0,0x44000024),
        (0x85fc,0xeb0031f7,0xf10c0080,0x44000028),
        (0x8650,0xe28d000c,0xeb000ae5,0x4400002c),
    ]
    core_patches=[(a,b,c,0xe51ff004,d) for a,b,c,d in core_patches]
    # Native console is started after parse_early_param, before paging_init.
    assert ksyms['t4_ramfb_console_init']==0xc000d8ec
    assert ksyms['t4_map_io']==0xc000d850 and ksyms['s5l8930_map_io']==0xc000d538
    core_patches += [
        (0xb5a0,0xe59f7254,0xeb000533,0xe51ff004,0x44000030),
        (0xd850,0xe92d4008,0xeb000024,0xe51ff004,0xc3e00004),
        (0xca4c,0xe92d4070,0xe1a05000,0xe51ff004,0xc3e00000),
        (0xd89c,0xe92d4008,0xe59f3038,0xe51ff004,0xc3e00008),
        (0x29a98,0xe59f2058,0xe350003f,0xe51ff004,0xc3e0000c),
        (0x86b8,0xe3a00000,0xeb04b1c6,0xe51ff004,0xc3e00010),
        (0x8744,0xeb001df2,0xeb0009ac,0xe51ff004,0xc3e00014),
        (0x24e34,0xe92d4ff0,0xe24dd054,0xe51ff004,0xc3e00018),
    ]
    storage_stubs={n:(0xe3a00000 if n in ['h2fmi_mod_init','register_vfl','s5l8930_register_h2fmi'] else 0xe3e00012)
        for n in ['h2fmi_mod_init','register_vfl','s5l8930_register_h2fmi',
                  'apple_nand_write_page','apple_nand_erase_block','h2fmi_nand_write','h2fmi_nand_erase']}
    for n,ins in storage_stubs.items():
        a=ksyms[n]-0xc0000000
        old=struct.unpack_from('<2I',decompressed,a-0x8000)
        core_patches.append((a,*old,ins,0xe12fff1e))
    instrumented=bytearray(decompressed)
    for addr,a,b,new0,new1 in core_patches:
        assert struct.unpack_from('<2I',decompressed,addr-0x8000)==(a,b),hex(addr)
        struct.pack_into('<2I',instrumented,addr-0x8000,new0,new1)
    (OUT/'Image.instrumented').write_bytes(instrumented)
    (OUT/'core-patches.h').write_text(
        'static const unsigned core_patches[][5]={\n'+
        '\n'.join('{'+','.join(hex(v)+'u' for v in row)+'},' for row in core_patches)+
        '\n};\n#define CORE_PATCH_COUNT '+str(len(core_patches))+'u\n'+
        '#define IMAGE_INSTRUMENTED_CRC '+str(zlib.crc32(instrumented))+'u\n'+
        '#define KERNEL_BANNER_VA '+hex(ksyms['linux_banner'])+'u\n')
    (OUT/'zImage').write_bytes(kernel)
    initrd=(OUT/'initramfs.cpio.gz').read_bytes()
    base=(ROOT/'saved/build/phase1-published/openiboot.bin').read_bytes()
    assert hashlib.sha256(base).hexdigest()==prior['baseline_sha256']
    (OUT/'sizes.h').write_text('\n'.join(f'#define {k} {v}u' for k,v in {
        'KERNEL_SIZE':len(kernel),'KERNEL_CRC':zlib.crc32(kernel),
        'IMAGE_SIZE':len(decompressed),'IMAGE_CRC':zlib.crc32(decompressed),
        'NATIVE_BOOT_CRC':zlib.crc32(base[0x2e3c:0x3030]),
        'INITRD_SIZE':len(initrd),'INITRD_CRC':zlib.crc32(initrd),
        'INITRD_UNPACKED_SIZE':struct.unpack_from('<I',initrd,len(initrd)-4)[0]}.items())+'\n')
    define='-DT4_TEST_NAME="'+NAME+'"'
    extra='-DT4_EXTRA_ARGS=" slub_debug=FZPU"'
    subprocess.run([CROSS+'gcc','-nostdlib','-fno-use-linker-plugin','-mcpu=cortex-a8',
        '-mthumb','-Os','-fno-builtin','-fno-unwind-tables','-fno-asynchronous-unwind-tables',
        '-Wl,-T,'+str(HERE/'handoff.ld'),'-Wl,-N','-Wl,--build-id=none','-Wl,-e,t4_linux_stage',
        define,extra,'-I'+str(OUT),'-I'+str(Path(prior['source'])/'arch/arm/mach-s5l8930/include'),
        str(HERE/'entry.S'),str(HERE/'handoff.c'),'-o',str(OUT/'handoff.elf')],check=True)
    elf=(OUT/'handoff.elf').read_bytes()
    phoff=struct.unpack_from('<I',elf,28)[0];ps,pn=struct.unpack_from('<HH',elf,42)
    seg=[struct.unpack_from('<8I',elf,phoff+i*ps) for i in range(pn)]
    seg=[p for p in seg if p[0]==1 and p[5]]
    assert min(p[2] for p in seg)==0x44000000
    end=max(p[2]+p[5] for p in seg);image=bytearray(end-0x44000000)
    for p in seg:image[p[2]-0x44000000:p[2]-0x44000000+p[4]]=elf[p[1]:p[1]+p[4]]
    assert len(image)<=0x8000  # upper half of the mapped 64K is diagnostic stack
    (OUT/'handoff.bin').write_bytes(image)
    symbols=subprocess.check_output([CROSS+'nm',str(OUT/'handoff.elf')],text=True)
    symbols={l.split()[2]:int(l.split()[0],16) for l in symbols.splitlines() if len(l.split())==3}
    assert symbols['t4_zimage_probe']==0x44000000
    for i,n in enumerate(['t4_zimage_probe','t4_after_enable','t4_before_decompress',
                           't4_after_decompress','t4_putstr','t4_before_kernel',
                           't4_core_entry','t4_processor_ok','t4_atags_pages',
                           't4_mmap_switched','t4_early_c','t4_printk_returned','t4_start_native_console']):
        assert symbols[n]==0x44000000+4*i
    assert not subprocess.check_output([CROSS+'nm','-u',str(OUT/'handoff.elf')],text=True).strip()
    usb=ROOT/'saved/research/libusb-1.0.29'
    flags=['-I'+str(usb/'libusb'),str(usb/'libusb/.libs/libusb-1.0.a'),
        '-framework','IOKit','-framework','CoreFoundation','-framework','Security']
    subprocess.run(['cc','-Wall','-Wextra','-Werror',define,extra,str(HERE.parent/'usb.c'),
        '-o',str(OUT/'linux-usb')]+flags,check=True)
    subprocess.run(['cc','-Wall','-Wextra','-Werror',define,extra,str(HERE.parent/'test_cmdline.c'),
        '-o',str(OUT/'test-cmdline')],check=True)
    (OUT/'cmdline-test.log').write_bytes(subprocess.check_output([str(OUT/'test-cmdline')]))
    dis=subprocess.check_output([CROSS+'objdump','-d',str(OUT/'handoff.elf')],text=True)
    (OUT/'handoff.disasm').write_text(dis)
    files=['zImage','zImage.original','Image.expected','Image.instrumented','core-patches.h','resident.bin','resident.elf','io-table.json','initramfs.cpio.gz','init','kernel.config','vmlinux','handoff.bin','handoff.elf','linux-usb']
    manifest={'variant':NAME,'status':'built; hardware result pending',
        'baseline_sha256':prior['baseline_sha256'],'source':prior['source'],
        'machine_id':3564,'entries':{n:symbols[n]|1 for n in ['t4_linux_stage','t4_linux_start']},
        'kernel_probe_arm':symbols['t4_zimage_probe'],
        'zimage_modified_ranges':[[0,32],[0x160,0x168],[0x170,0x178],[0x328,0x32c],[0x7e0,0x7e8]],
        'expected_image_crc32':f'{zlib.crc32(decompressed):08x}',
        'core_patches':core_patches,
        'diagnostic_page_mappings':'helper/INFO identity RAM and inherited high framebuffer only, at checkpoint 19',
        'storage_stubs':list(storage_stubs),
        'resident':{'physical':0x03e00000,'virtual':0xc3e00000,'reserved_bytes':0x100000},
        'preserved_display_gates':[0x0b,0x0f,0x11,0x12],
        'clock_poll_limit':1000000,
        'early_noalign':{'native_function':0xc000c4d0,'require_sctlr_U':True,
            'allowed_sctlr_change':'clear A bit only; updates both saved CR values'},
        'first_fatal':'die redirects to masked first-error diagnostic halt',
        'slub_debug':'FZPU: native sanity/redzone/poison/alloc-free tracking',
        'intentional_stop':None,
        'next_success_evidence':'native kernel console; eventually PID1_REACHED from RAM /init',
        'zimage_resume_address':0x02000020,'native_functions':{
            'EnterCriticalSection':0x4c1,'exit_modules':0x391,
            'arm_disable_caches':0x829,'mmu_disable':0x12da1},
        'files':{n:{'bytes':(OUT/n).stat().st_size,'sha256':sha(OUT/n)} for n in files}}
    (OUT/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print('Built',OUT,'; no USB access; checkpoints are not Linux boot evidence.')
if __name__=='__main__':main()
