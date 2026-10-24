#!/usr/bin/env python3
"""Check the final machine code, not just the assembly text. No USB access."""
import json
from pathlib import Path
import struct
import subprocess

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'saved/build/T4_LINUX_DIAG_04'
u32=lambda b,p:struct.unpack_from('<I',b,p)[0]
original=(OUT/'zImage.original').read_bytes()
patched=(OUT/'zImage').read_bytes()
helper=(OUT/'handoff.bin').read_bytes()
assert original==(ROOT/'saved/build/T4_LINUX_RAM_02/zImage').read_bytes()
assert len(original)==len(patched)
assert patched[0x20:0x64]==original[0x20:0x64]
assert patched[0x318:0x328]==original[0x318:0x328]
assert patched[0x32c:]==original[0x32c:]
for i in range(4):
    assert u32(patched,i*8)==0xe51ff004
    assert u32(patched,i*8+4)==0x44000000+4*i
for site,target in [(0x64,8),(0x314,16),(0x328,24)]:
    instr=u32(patched,site)
    assert instr>>24==0xea  # B, never BL: original LR survives inline hooks.
    delta=instr&0xffffff
    if delta&0x800000:delta-=0x1000000
    assert site+8+delta*4==target
nm=subprocess.check_output([str(ROOT/'saved/toolchain/arm-eabi-4.8/bin/arm-eabi-nm'),str(OUT/'handoff.elf')],text=True)
symbols={s[2]:int(s[0],16)-0x44000000 for l in nm.splitlines() if len(s:=l.split())==3}
for name in ['header_probe','cache_probe','enable_probe','enabled_probe']:
    p=symbols[name]
    assert u32(helper,p)==0xe92d5fff  # save r0-r12, LR
    assert u32(helper,p+4)==0xe10f0000  # MRS CPSR
    assert u32(helper,p+8)==0xe92d0003  # eight-byte aligned stack
    assert u32(helper,p+24)==0xe8bd0003
    assert u32(helper,p+28)==0xe128f000  # restore original NZCVQ flags
    assert u32(helper,p+32)==0xe8bd5fff
assert u32(helper,symbols['enable_probe']+36)==0x1e031f10
assert u32(helper,symbols['enabled_probe']+36)==0xeafffffe
# The original kernel uses r3 for the section table at this exact boundary.
assert u32(original,0x310)==0x1e023f10
assert [u32(original,p) for p in (0x318,0x31c,0x320,0x324)]==[
    0xee010f10,0xee110f10,0xe3a00000,0xee070f95]
print('LAYOUT_PASSED: veneers, B targets, registers, CPSR flags, original SCTLR sequence, payload extent')
