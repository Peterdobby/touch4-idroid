#!/usr/bin/env python3
"""Verify the emitted ARM hooks and compressed Image independently; no USB."""
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import zlib

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'saved/build/T4_LINUX_DIAG_10'
u32=lambda b,p:struct.unpack_from('<I',b,p)[0]
original=(OUT/'zImage.original').read_bytes()
patched=(OUT/'zImage').read_bytes()
helper=(OUT/'handoff.bin').read_bytes()
manifest=json.loads((OUT/'manifest.json').read_text())
assert original==(ROOT/'saved/build/T4_LINUX_RAM_02/zImage').read_bytes()
assert len(original)==len(patched)
allowed={i for a,b in manifest['zimage_modified_ranges'] for i in range(a,b)}
assert all(a==b or p in allowed for p,(a,b) in enumerate(zip(original,patched)))
assert original[0x318:0x328]==patched[0x318:0x328]
assert original[0x560:0x7e0]==patched[0x560:0x7e0]  # original cache cleanup/off
assert original[0x469b:]==patched[0x469b:]  # compressed input and GOT unchanged
image=zlib.decompress(patched[0x469b:0xd0a95],31)
assert image==(OUT/'Image.expected').read_bytes()
assert f'{zlib.crc32(image):08x}'==manifest['expected_image_crc32']=='f1b0975d'
for i in range(4):
    assert u32(patched,i*8)==0xe51ff004
    assert u32(patched,i*8+4)==0x44000000+4*i
for site,target in [(0x328,8),(0x160,16),(0x164,24)]:
    instr=u32(patched,site)
    assert instr>>24==0xea
    delta=instr&0xffffff
    if delta&0x800000:delta-=0x1000000
    assert site+8+delta*4==target
for site,vector in [(0x7e0,0x44000010),(0x170,0x44000014)]:
    assert u32(patched,site)==0xe51ff004 and u32(patched,site+4)==vector
nm=subprocess.check_output([str(ROOT/'saved/toolchain/arm-eabi-4.8/bin/arm-eabi-nm'),str(OUT/'handoff.elf')],text=True)
symbols={s[2]:int(s[0],16)-0x44000000 for l in nm.splitlines() if len(s:=l.split())==3}
for name in ['header_probe','enabled_probe','decompress_probe','decompressed_probe','putstr_probe','kernel_probe',
             'core_probe','processor_probe','atags_return','pages_return','switched_probe','early_c_probe','printk_probe','native_console_entry','native_console_ready']:
    p=symbols[name]
    assert u32(helper,p)==0xe92d5fff
    assert u32(helper,p+4)==0xe10f0000
    assert u32(helper,p+8)==0xe92d0003
    assert u32(helper,p+24)==0xe8bd0003
    assert u32(helper,p+28)==0xe128f000
    assert u32(helper,p+32)==0xe8bd5fff
assert u32(helper,symbols['enabled_probe']+36)==0xe1a0f00c
assert u32(helper,symbols['putstr_probe']+36)==0xe12fff1e
assert u32(helper,symbols['kernel_probe']+36)==0xe1a01007
for name,lr,dest in [('decompress_probe',0x02000164,0x02000b0c),
                     ('decompressed_probe',0x02000168,0x02000620)]:
    p=symbols[name]
    assert [u32(helper,p+i) for i in (36,40,44,48)]==[0xe51fe000,0xe51ff000,lr,dest]
assert patched==(ROOT/'saved/build/T4_LINUX_DIAG_05/zImage').read_bytes()
modified=(OUT/'Image.instrumented').read_bytes()
expected=bytearray(image)
for addr,a,b,new0,new1 in manifest['core_patches']:
    assert struct.unpack_from('<2I',image,addr-0x8000)==(a,b)
    struct.pack_into('<2I',expected,addr-0x8000,new0,new1)
assert modified==expected
assert len(helper)<=0x8000
assert u32(helper,symbols['core_probe']+36)==0xe321f0d3
assert u32(helper,symbols['core_probe']+40)==0xee109f10
assert u32(helper,symbols['processor_probe']+36)==0xe1b0a005
assert u32(helper,symbols['printk_probe']+36)==0xe28d000c
# Decode absolute PC-relative literal loads to check physical/virtual resumes.
def literal(p):
    ins=u32(helper,p)
    assert (ins&0xff7f0000)==0xe51f0000,hex(ins)
    delta=ins&0xfff
    return u32(helper,p+8+(delta if ins&(1<<23) else -delta))
assert literal(symbols['core_probe']+44)==0x8008
assert literal(symbols['processor_probe']+40)==0x8014
assert literal(symbols['atags_pages_probe']+4)==0x8138
assert literal(symbols['atags_return']+40)==0x804c
assert literal(symbols['pages_return']+40)==0x802c
assert literal(symbols['switched_entry'])==0x44010000
assert literal(symbols['switched_probe']+36)==0xc0008180
assert literal(symbols['switched_probe']+40)==0xc00081c8
assert u32(helper,symbols['switched_probe']+44)==0xe8b300f0
assert literal(symbols['switched_probe']+48)==0xc0008188
assert literal(symbols['early_c_probe']+40)==0xc0014de0
assert u32(helper,symbols['debug_objects_return'])==0xf10c0080
assert literal(symbols['debug_objects_return']+4)==0xc0008600
assert literal(symbols['debug_objects_return']+8)==0xc0008604
assert literal(symbols['printk_probe']+40)==0xc0008658
assert literal(symbols['printk_probe']+44)==0xc000b1f0
assert literal(symbols['native_console_entry']+52)==0xc000d8ec
assert literal(symbols['native_console_ready']+36)==0xc000b7fc
assert u32(helper,symbols['native_console_ready']+40)==0xe5977000
assert literal(symbols['native_console_ready']+44)==0xc000b5a8
assert literal(symbols['native_console_ready']+48)==0xc000ca78
# Correct native return paths remain in kernel space after low mappings vanish.
assert u32(modified,0xd850-0x8000)==0xe51ff004
assert u32(modified,0xd854-0x8000)==0xc3e00004
assert u32(modified,0xca50-0x8000)==0xc3e00000
assert u32(modified,0xd8a0-0x8000)==0xc3e00008
resident=(OUT/'resident.bin').read_bytes()
assert resident in helper
rnm=subprocess.check_output([str(ROOT/'saved/toolchain/arm-eabi-4.8/bin/arm-eabi-nm'),str(OUT/'resident.elf')],text=True)
rs={s[2]:int(s[0],16) for l in rnm.splitlines() if len(s:=l.split())==3}
assert [rs[n] for n in ['resident_io_entry','resident_board_entry','resident_reserve_entry','resident_gate_entry']]==[0xc3e00000,0xc3e00004,0xc3e00008,0xc3e0000c]
assert u32(modified,0x29a98-0x8000)==0xe51ff004 and u32(modified,0x29a9c-0x8000)==0xc3e0000c
for p,va in [(0x86b8,0xc3e00010),(0x8744,0xc3e00014),(0x24e34,0xc3e00018)]:
    assert [u32(modified,p-0x8000),u32(modified,p-0x8000+4)]==[0xe51ff004,va]
# Resident probes preserve registers/flags and replay native call sites.
def r_literal(p):
    ins=u32(resident,p);assert (ins&0xff7f0000)==0xe51f0000
    delta=ins&0xfff
    return u32(resident,p+8+(delta if ins&(1<<23) else -delta))
for name,stage in [('percpu_returned',0),('irq_begin',1),('irq_desc_returned',2),('vic_returned',3)]:
    p=rs[name]-0xc3e00000
    assert [u32(resident,p+i) for i in (0,4,8,12,20,24,28)]==[
        0xe92d5fff,0xe10f0000,0xe92d0003,0xe3a00000+stage,
        0xe8bd0003,0xe128f000,0xe8bd5fff]
p=rs['percpu_returned']-0xc3e00000
assert u32(resident,p+32)==0xe3a00000
assert r_literal(p+36)==0xc00086c0 and r_literal(p+40)==0xc0134ddc
for name,lr,dest in [('irq_begin',rs['irq_desc_returned'],0xc000ff14),
                     ('irq_desc_returned',rs['vic_returned'],0xc000ae00),
                     ('vic_returned',0xc000874c,0xc000874c)]:
    p=rs[name]-0xc3e00000
    assert r_literal(p+32)==lr and r_literal(p+36)==dest
assert u32(resident,rs['original_fb_reserve']-0xc3e00000)==0xe92d4008
assert bytes.fromhex('a8441ac0') in resident and bytes.fromhex('a4d800c0') in resident
nm_kernel=subprocess.check_output([str(ROOT/'saved/toolchain/arm-eabi-4.8/bin/arm-eabi-nm'),str(OUT/'vmlinux')],text=True)
ksyms={s[2]:int(s[0],16) for l in nm_kernel.splitlines() if len(s:=l.split())==3}
for name in manifest['storage_stubs']:
    p=ksyms[name]-0xc0008000
    result=0xe3a00000 if name in ['h2fmi_mod_init','register_vfl','s5l8930_register_h2fmi'] else 0xe3e00012
    assert [u32(modified,p),u32(modified,p+4)]==[result,0xe12fff1e],name
for entry,fn in [('__initcall_h2fmi_mod_init6','h2fmi_mod_init'),('__initcall_register_vfl7','register_vfl')]:
    assert u32(image,ksyms[entry]-0xc0008000)==ksyms[fn]
for previous in ['T4_LINUX_RAM_02','T4_LINUX_DIAG_03','T4_LINUX_DIAG_04','T4_LINUX_DIAG_05','T4_LINUX_DIAG_06','T4_LINUX_DIAG_07','T4_LINUX_DIAG_08','T4_LINUX_DIAG_09']:
    old=ROOT/'saved/build'/previous
    m=json.loads((old/'manifest.json').read_text())
    for name,entry in m['files'].items():
        assert hashlib.sha256((old/name).read_bytes()).hexdigest()==entry['sha256'],(previous,name)
print('LAYOUT_PASSED: original compressed Image, NAND guards, ARM probes and native resumes; all 02 through 09 artifacts unchanged')
