#!/usr/bin/env python3
"""Verify the emitted ARM hooks and compressed Image independently; no USB."""
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import zlib

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'saved/build/T4_LINUX_DIAG_05'
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
for name in ['header_probe','enabled_probe','decompress_probe','decompressed_probe','putstr_probe','kernel_probe']:
    p=symbols[name]
    assert u32(helper,p)==0xe92d5fff
    assert u32(helper,p+4)==0xe10f0000
    assert u32(helper,p+8)==0xe92d0003
    assert u32(helper,p+24)==0xe8bd0003
    assert u32(helper,p+28)==0xe128f000
    assert u32(helper,p+32)==0xe8bd5fff
assert u32(helper,symbols['enabled_probe']+36)==0xe1a0f00c
assert u32(helper,symbols['putstr_probe']+36)==0xe12fff1e
assert u32(helper,symbols['kernel_probe']+36)==0xeafffffe
for name,lr,dest in [('decompress_probe',0x02000164,0x02000b0c),
                     ('decompressed_probe',0x02000168,0x02000620)]:
    p=symbols[name]
    assert [u32(helper,p+i) for i in (36,40,44,48)]==[0xe51fe000,0xe51ff000,lr,dest]
for previous in ['T4_LINUX_RAM_02','T4_LINUX_DIAG_03','T4_LINUX_DIAG_04']:
    old=ROOT/'saved/build'/previous
    m=json.loads((old/'manifest.json').read_text())
    for name,entry in m['files'].items():
        assert hashlib.sha256((old/name).read_bytes()).hexdigest()==entry['sha256'],(previous,name)
print('LAYOUT_PASSED: compressed Image, patch boundaries, register/flags preservation, replay targets, deliberate stop; 02/03/04 unchanged')
