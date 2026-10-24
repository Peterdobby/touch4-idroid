#!/usr/bin/env python3
"""Run native memset + native SLUB init_object from this new kernel in ARM emulator."""
from pathlib import Path
import json,struct
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_PROT_ALL
from unicorn.arm_const import *
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'saved/build/T4_ANDROID_UI_04'
m=json.loads((OUT/'manifest.json').read_text());ks=m['kernel_symbols']
uc=Uc(UC_ARCH_ARM,UC_MODE_ARM);uc.ctl_set_cpu_model(UC_CPU_ARM_CORTEX_A8)
image=(OUT/'Image.expected').read_bytes();data=0xc4000000;stack=0xc4110000;stop=0x01000000
for a,s in [(0xc0000000,0x800000),(data,0x40000),(stack-0x10000,0x10000),(stop,0x1000)]:uc.mem_map(a,s,UC_PROT_ALL)
uc.mem_write(0xc0008000,image)
regs=[UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_R4,UC_ARM_REG_R5,UC_ARM_REG_R6,UC_ARM_REG_R7,UC_ARM_REG_R8,UC_ARM_REG_R9,UC_ARM_REG_R10,UC_ARM_REG_R11,UC_ARM_REG_R12]
def call(entry,args):
 uc.reg_write(UC_ARM_REG_CPSR,0xd3)
 for i,r in enumerate(regs):uc.reg_write(r,0x10100000+i*0x010101)
 for r,v in zip(regs,args):uc.reg_write(r,v&0xffffffff)
 saved=[uc.reg_read(r) for r in regs[4:12]]
 uc.reg_write(UC_ARM_REG_SP,stack);uc.reg_write(UC_ARM_REG_LR,stop)
 uc.emu_start(entry,stop,count=1000000)
 assert uc.reg_read(UC_ARM_REG_PC)==stop
 assert uc.reg_read(UC_ARM_REG_SP)==stack
 assert [uc.reg_read(r) for r in regs[4:12]]==saved
 assert uc.reg_read(UC_ARM_REG_CPSR)&0xdf==0xd3
 return uc.reg_read(UC_ARM_REG_R0)
sizes=list(range(130))+[191,192,193,255,256,257,511,512,513,1023,1024,1025,4095,4096,4097,65535,65536,65537]
count=0
for align in range(8):
 for n in sizes:
  for fill in [0,0x6b,0xa5,0xbb,0xff,0x123456bb,-1]:
   dest=data+0x100+align;uc.mem_write(dest-32,bytes([0x93])*(n+64))
   assert call(ks['memset'],[dest,fill,n])==dest
   assert bytes(uc.mem_read(dest-32,n+64))==bytes([0x93])*32+bytes([fill&255])*n+bytes([0x93])*32,(align,n,fill)
   count+=1
cache=bytearray(128)
for off,v in [(4,0x80010400),(16,28),(48,32)]:struct.pack_into('<I',cache,off,v)
cacheaddr=data+0x30000;dest=data+0x100
uc.mem_write(cacheaddr,bytes(cache));uc.mem_write(dest,bytes([0x5a])*96)
call(ks['init_object'],[cacheaddr,dest,0xbb])
assert bytes(uc.mem_read(dest,96))==bytes([0x6b])*27+b'\xa5'+bytes([0xbb])*4+bytes([0x5a])*64
result={'native_memset_cases':count,'native_slub_init_object_passed':True,'hardware_tested':False}
(OUT/'memset-arm-test.json').write_text(json.dumps(result,indent=2)+'\n');print(result)
