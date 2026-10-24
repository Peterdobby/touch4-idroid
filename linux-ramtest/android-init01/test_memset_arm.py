#!/usr/bin/env python3
"""Run the actual original/patched ARM instructions; no USB or hardware MMIO."""
from pathlib import Path
import json
import struct
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM, UC_PROT_ALL
from unicorn.arm_const import (
    UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3,
    UC_ARM_REG_R4, UC_ARM_REG_R5, UC_ARM_REG_R6, UC_ARM_REG_R7,
    UC_ARM_REG_R8, UC_ARM_REG_R9, UC_ARM_REG_R10, UC_ARM_REG_R11,
    UC_ARM_REG_R12, UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC,
    UC_ARM_REG_CPSR, UC_CPU_ARM_CORTEX_A8,
)

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'saved/build/T4_LINUX_DIAG_12'
REGS=[UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,
      UC_ARM_REG_R4,UC_ARM_REG_R5,UC_ARM_REG_R6,UC_ARM_REG_R7,
      UC_ARM_REG_R8,UC_ARM_REG_R9,UC_ARM_REG_R10,UC_ARM_REG_R11,
      UC_ARM_REG_R12]
STOP=0x01000000
DATA=0xc4000000
STACK=0xc4110000
CACHE=0xc4030000

def machine(image):
    uc=Uc(UC_ARCH_ARM,UC_MODE_ARM)
    uc.ctl_set_cpu_model(UC_CPU_ARM_CORTEX_A8)
    for addr,size in [(0xc0000000,0x200000),(0xc3e00000,0x10000),
                      (DATA,0x40000),(STACK-0x10000,0x10000),(STOP,0x1000)]:
        uc.mem_map(addr,size,UC_PROT_ALL)
    uc.mem_write(0xc0008000,image)
    uc.mem_write(0xc3e00000,(OUT/'resident.bin').read_bytes())
    return uc

def call(uc,entry,args):
    uc.reg_write(UC_ARM_REG_CPSR,0xd3)
    for i,reg in enumerate(REGS):uc.reg_write(reg,0x10100000+i*0x010101)
    for reg,value in zip(REGS,args):uc.reg_write(reg,value&0xffffffff)
    preserved=[uc.reg_read(reg) for reg in REGS[4:12]]
    uc.reg_write(UC_ARM_REG_SP,STACK)
    uc.reg_write(UC_ARM_REG_LR,STOP)
    uc.emu_start(entry,STOP,count=1000000)
    assert uc.reg_read(UC_ARM_REG_PC)==STOP,'instruction limit exceeded'
    assert uc.reg_read(UC_ARM_REG_SP)==STACK,'stack not restored'
    assert [uc.reg_read(reg) for reg in REGS[4:12]]==preserved,'callee-saved register changed'
    assert uc.reg_read(UC_ARM_REG_CPSR)&0xdf==0xd3,'interrupt/mode changed'
    return uc.reg_read(UC_ARM_REG_R0)

old=machine((OUT/'Image.expected').read_bytes())
new=machine((OUT/'Image.instrumented').read_bytes())
dest=DATA+0x100
old.mem_write(dest,bytes([0x5a])*256)
assert call(old,0xc00e1520,[dest,0x6b,27])==dest+27
assert bytes(old.mem_read(dest,27))==bytes([0x6b])*27
print('ORIGINAL_MEMSET_ABI_FAILURE_REPRODUCED: returns destination+27')

# Exhaustive short lengths for every byte/cacheline alignment, plus large
# fast-loop and boundary cases. Include non-byte int values required by C ABI.
sizes=list(range(130))+[191,192,193,255,256,257,511,512,513,1023,1024,
                       1025,4095,4096,4097,65535,65536,65537]
count=0
for alignment in range(8):
    for size in sizes:
        for fill in [0,0x6b,0xa5,0xbb,0xff,0x123456bb,-1]:
            dest=DATA+0x100+alignment
            new.mem_write(dest-32,bytes([0x93])*(size+64))
            assert call(new,0xc00e1520,[dest,fill,size])==dest
            assert bytes(new.mem_read(dest-32,size+64))==(
                bytes([0x93])*32+bytes([fill&255])*size+bytes([0x93])*32
            ),(alignment,size,fill)
            count+=1
print(f'PATCHED_MEMSET_ARM_PASSED: {count} cases; guards, return, stack, callee registers and IRQ mask')

# Execute the exact emitted SLUB init_object, not a C reimplementation.
# It folds the original object pointer into memset's return at C007DA78.
cache=bytearray(128)
for offset,value in [(4,0x80010400),(16,28),(48,32)]:
    struct.pack_into('<I',cache,offset,value)
dest=DATA+0x100
for uc in [old,new]:
    uc.mem_write(CACHE,bytes(cache))
    uc.mem_write(dest,bytes([0x5a])*96)
    call(uc,0xc007da44,[CACHE,dest,0xbb])
before=bytes(old.mem_read(dest,96));after=bytes(new.mem_read(dest,96))
assert before[:27]==bytes([0x6b])*27
assert before[27:32]==bytes([0x5a])*5
assert before[54]==0xa5 and before[55:59]==bytes([0xbb])*4
assert after==bytes([0x6b])*27+b'\xa5'+bytes([0xbb])*4+bytes([0x5a])*64
print('PHOTO_PATTERN_REPRODUCED: original init_object leaves terminator/redzone at 5a and writes them 27 bytes late')
print('PATCHED_SLUB_INIT_OBJECT_PASSED: original native code now sets a5 terminator and bb redzone at exact offsets')
(OUT/'memset-arm-test.json').write_text(json.dumps({
    'emulator':'Unicorn ARM Cortex-A8; actual pinned kernel and resident machine code',
    'memset_cases':count,'original_bad_return_reproduced':True,
    'original_photo_pattern_reproduced':True,'patched_slub_init_object_passed':True,
    'hardware_tested':False},indent=2)+'\n')
