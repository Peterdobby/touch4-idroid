#!/usr/bin/env python3
"""Execute the actual Thumb table-CRC/progress code; mock drawing only."""
from pathlib import Path
import json,struct,subprocess,zlib
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import *
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'saved/build/T4_ANDROID_UI_06'
nm=subprocess.check_output([str(ROOT/'saved/toolchain/arm-eabi-4.8/bin/arm-eabi-nm'),str(OUT/'handoff.elf')],text=True)
sy={s[2]:int(s[0],16) for line in nm.splitlines() if len(s:=line.split())==3}
uc=Uc(UC_ARCH_ARM,UC_MODE_ARM);uc.ctl_set_cpu_model(UC_CPU_ARM_CORTEX_A8)
for a,n in [(0x44000000,0x10000),(0x44800000,0x300000),(0x1000000,4096)]:uc.mem_map(a,n)
uc.mem_write(0x44000000,(OUT/'handoff.bin').read_bytes());labels=[]
def hook(uc,pc,size,user):
    if pc==sy['mark']:
        a=uc.reg_read(UC_ARM_REG_R1);s=bytes(uc.mem_read(a,40)).split(b'\0',1)[0].decode()
        labels.append(s);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
uc.hook_add(UC_HOOK_CODE,hook)
data=bytes(range(256))*8193;uc.mem_write(0x44800000,data)
uc.mem_write(0x1000000,b'CRC\0')
for n in [0,1,9,255,256,1048576,1048577,len(data)]:
    labels.clear();uc.reg_write(UC_ARM_REG_CPSR,0xd3);uc.reg_write(UC_ARM_REG_SP,0x4400fff0)
    uc.reg_write(UC_ARM_REG_LR,0x1000100)
    for r,v in zip([UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3],[0x44800000,n,6,0x1000000]):uc.reg_write(r,v)
    uc.emu_start(sy['t4_crc32_progress']|1,0x1000100,count=max(10000,n*16))
    assert uc.reg_read(UC_ARM_REG_PC)==0x1000100
    assert uc.reg_read(UC_ARM_REG_R0)==zlib.crc32(data[:n]),n
    total=(n+1048575)//1048576
    assert len(labels)==total+1 and labels[0]==f'CRC00/{total:02}' and labels[-1]==f'CRC{total:02}/{total:02}',labels
(OUT/'crc-arm-test.json').write_text(json.dumps({'native_Thumb_table_CRC_matches_zlib':True,'sizes_tested':[0,1,9,255,256,1048576,1048577,len(data)],'every_1MiB_progress_verified':True,'drawing':'mocked','hardware':'pending'},indent=2)+'\n')
print('CRC_ARM_PASSED: real Thumb CRC == zlib; zero/boundary/multiple chunks; visible progress labels')
