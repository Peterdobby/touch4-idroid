#!/usr/bin/env python3
"""Real ARM JNI identity wrappers: tolerate errno side effects on success,
while preserving genuine libc failures. Only PLT libc interfaces are mocked.
"""
from pathlib import Path
import json,struct,sys
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import *
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'saved/build/T4_ANDROID_UI_07'
sys.path.insert(0,str(ROOT));from prepare_android import unpack_cpio
import gzip
_,files=unpack_cpio(gzip.decompress((OUT/'initramfs.cpio.gz').read_bytes()))
old=(ROOT/'saved/build/android-prepared/system-root/lib/libandroid_runtime.so').read_bytes();new=files['system/lib/libandroid_runtime.so']
assert len(old)==len(new) and old[:0x5d7c4]==new[:0x5d7c4] and old[0x5d804:]==new[0x5d804:]
BASE=0xad300000;ERRNO=0x03000000;STOP=0x05000000

def run(data,which,status,errno):
    uc=Uc(UC_ARCH_ARM,UC_MODE_ARM);uc.ctl_set_cpu_model(UC_CPU_ARM_CORTEX_A8)
    uc.mem_map(BASE,0x100000);uc.mem_write(BASE,data)
    for a,n in [(ERRNO,4096),(0x04000000,0x10000),(STOP,4096)]:uc.mem_map(a,n)
    calls=[];uc.mem_write(ERRNO,struct.pack('<I',37))
    def hook(uc,pc,size,user):
        if pc==BASE+0x20178:
            uc.reg_write(UC_ARM_REG_R0,ERRNO)
        elif pc==BASE+(0x230ac if which=='setregid' else 0x230b8):
            args=(uc.reg_read(UC_ARM_REG_R0),uc.reg_read(UC_ARM_REG_R1));assert args==(0xffffffff,9999),args
            calls.append(which);uc.mem_write(ERRNO,struct.pack('<I',errno));uc.reg_write(UC_ARM_REG_R0,status&0xffffffff)
        else:return
        # Callers cannot rely on these registers surviving a libc call.
        for reg in [UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_R12]:uc.reg_write(reg,0x12345678)
        uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
    uc.hook_add(UC_HOOK_CODE,hook);uc.reg_write(UC_ARM_REG_CPSR,0x10)
    uc.reg_write(UC_ARM_REG_SP,0x0400f000);uc.reg_write(UC_ARM_REG_LR,STOP)
    for reg,val in [(UC_ARM_REG_R0,0x11111111),(UC_ARM_REG_R1,0x22222222),(UC_ARM_REG_R2,0xffffffff),(UC_ARM_REG_R3,9999),(UC_ARM_REG_R4,0x44444444),(UC_ARM_REG_R5,0x55555555),(UC_ARM_REG_R6,0x66666666)]:uc.reg_write(reg,val)
    uc.emu_start(BASE+(0x5d7c4 if which=='setregid' else 0x5d7e4)|1,STOP,count=1000)
    assert uc.reg_read(UC_ARM_REG_PC)==STOP and uc.reg_read(UC_ARM_REG_SP)==0x0400f000
    assert [uc.reg_read(x) for x in [UC_ARM_REG_R4,UC_ARM_REG_R5,UC_ARM_REG_R6]]==[0x44444444,0x55555555,0x66666666]
    assert calls==[which]
    return uc.reg_read(UC_ARM_REG_R0)
results={}
for name in ['setregid','setreuid']:
    assert run(old,name,0,2)==2 # POSIX allows errno to change on success
    assert run(new,name,0,2)==0
    assert run(new,name,0,0)==0
    for error in [1,2,22]:assert run(new,name,-1,error)==error
    results[name]={'old_false_failure_with_success_and_errno_2':'reproduced','fixed_success_return':'passed','real_failures_1_2_22_preserved':True,'arguments_stack_callee_registers_preserved':True}
(OUT/'zygote-ids-arm-test.json').write_text(json.dumps({'actual_JNI_Thumb_execution':results,'unchanged_binary_ranges':'all bytes outside the two original 32-byte wrappers','libc_setid_and_errno':'mocked with explicit return/errno values; not a live credential transition','hardware':'pending'},indent=2)+'\n')
print('ZYGOTE_IDS_ARM_PASSED: both false errno warnings reproduced/fixed; real failures preserved; original ABI/arguments/registers/stack intact')
