#!/usr/bin/env python3
"""Execute native arm_syscall(set_tls) and __switch_to from old/new ELF.
Only atomic_notifier_call_chain is mocked. Hardware TLS is Unicorn CP15;
legacy word and saved thread_info are real emulated memory. No USB/MMIO.
"""
from pathlib import Path
import json,struct,subprocess
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import *
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'saved/build/T4_ANDROID_UI_03'
CROSS=str(ROOT/'saved/toolchain/arm-eabi-4.8/bin/arm-eabi-')
STOP=0x1000000;A=0xc5000000;B=A+0x2000;REGS=A+0x4000
def run(name,legacy):
    folder=ROOT/'saved/build'/name
    sy={s[2]:int(s[0],16) for line in subprocess.check_output([CROSS+'nm',str(folder/'vmlinux')],text=True).splitlines() if len(s:=line.split())==3}
    uc=Uc(UC_ARCH_ARM,UC_MODE_ARM);uc.ctl_set_cpu_model(UC_CPU_ARM_CORTEX_A8)
    for a,n in [(0xc0000000,0x800000),(A,0x10000),(STOP,4096),(0xffff0000,4096)]:uc.mem_map(a,n)
    uc.mem_write(0xc0008000,(folder/'Image.expected').read_bytes())
    def put(a,v):uc.mem_write(a,struct.pack('<I',v&0xffffffff))
    def get(a):return struct.unpack('<I',uc.mem_read(a,4))[0]
    def word(a):return get(a)
    # Read the offsets from the compiled context-switch instructions.
    start=sy['__switch_to'];assert word(start)&0xfffff000==0xe281c000
    save=word(start)&0xfff;assert word(start+4)&0xfffff000==0xe5923000
    tp=word(start+4)&0xfff
    def hook(uc,pc,size,user):
        if pc==sy['atomic_notifier_call_chain']:
            uc.reg_write(UC_ARM_REG_R0,0);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
    uc.hook_add(UC_HOOK_CODE,hook)
    def set_tls(thread,value):
        put(REGS,value);uc.reg_write(UC_ARM_REG_CPSR,0xd3)
        uc.reg_write(UC_ARM_REG_SP,thread+0x1ff0);uc.reg_write(UC_ARM_REG_LR,STOP)
        uc.reg_write(UC_ARM_REG_R0,0xf0005);uc.reg_write(UC_ARM_REG_R1,REGS)
        uc.emu_start(sy['arm_syscall'],STOP,count=1000)
        assert uc.reg_read(UC_ARM_REG_PC)==STOP and uc.reg_read(UC_ARM_REG_R0)==0
        assert get(thread+tp)==value
        assert uc.reg_read(UC_ARM_REG_C13_C0_3)==value
        assert get(0xffff0ff0)==(value if legacy else 0)
    def switch(prev,nxt,value):
        put(nxt+tp,value)
        uc.mem_write(nxt+save,struct.pack('<10I',*[0]*8,nxt+0x1ff0,STOP))
        uc.reg_write(UC_ARM_REG_CPSR,0xd3);uc.reg_write(UC_ARM_REG_SP,prev+0x1ff0)
        uc.reg_write(UC_ARM_REG_LR,STOP)
        for r,v in [(UC_ARM_REG_R0,0x123456),(UC_ARM_REG_R1,prev),(UC_ARM_REG_R2,nxt)]:uc.reg_write(r,v)
        uc.emu_start(start,STOP,count=1000)
        assert uc.reg_read(UC_ARM_REG_PC)==STOP and uc.reg_read(UC_ARM_REG_R0)==0x123456
        assert uc.reg_read(UC_ARM_REG_SP)==nxt+0x1ff0
        assert uc.reg_read(UC_ARM_REG_C13_C0_3)==value
        assert get(0xffff0ff0)==(value if legacy else 0)
    set_tls(A,0xb0011a48)
    switch(A,B,0xafd4d47c);switch(B,A,0xb0011a48)
    set_tls(A,0x46002000);switch(A,B,0x47004000);switch(B,A,0x46002000)
    return {'syscall_and_two_thread_context_switches':'passed','legacy_word_matches_hardware_TLS':legacy,'thread_info_offsets':{'cpu_save':save,'tp_value':tp}}
old=run('T4_ANDROID_UI_01',False);new=run('T4_ANDROID_UI_03',True)
result={'unfixed_native_kernel':old,'fixed_native_kernel':new,'mock':'atomic_notifier_call_chain only','hardware':'pending'}
(OUT/'tls-arm-test.json').write_text(json.dumps(result,indent=2)+'\n')
print('TLS_ARM_PASSED: original loses legacy TLS; native fix keeps syscall + repeated context switches synchronized')
