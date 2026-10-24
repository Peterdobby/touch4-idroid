#!/usr/bin/env python3
"""Actual native TLS code with RX high vectors sharing an RW linear alias.
Reproduce UI03's precise protected store; execute UI04 under identical
protection. Only notifier callback mocked. Caches require hardware validation.
"""
from pathlib import Path
import ctypes,json,mmap,struct,subprocess
from unicorn import Uc,UcError,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE,UC_HOOK_MEM_WRITE_PROT,UC_PROT_READ,UC_PROT_EXEC,UC_PROT_ALL
from unicorn.arm_const import *
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'saved/build/T4_ANDROID_INPUT_01'
CROSS=str(ROOT/'saved/toolchain/arm-eabi-4.8/bin/arm-eabi-')
STOP=0x1000000;A=0xc5000000;B=A+0x2000;REGS=A+0x4000;ALIAS=0xc6000000

def run(name,operation,expect_fault=False):
    folder=ROOT/'saved/build'/name
    sy={s[2]:int(s[0],16) for line in subprocess.check_output([CROSS+'nm',str(folder/'vmlinux')],text=True).splitlines() if len(s:=line.split())==3}
    uc=Uc(UC_ARCH_ARM,UC_MODE_ARM);uc.ctl_set_cpu_model(UC_CPU_ARM_CORTEX_A8)
    for a,n in [(0xc0000000,0x800000),(A,0x10000),(STOP,4096)]:uc.mem_map(a,n)
    uc.mem_write(0xc0008000,(folder/'Image.expected').read_bytes())
    backing=mmap.mmap(-1,4096);backing[:]=b'\x95'*4096
    ptr=ctypes.addressof(ctypes.c_ubyte.from_buffer(backing))
    uc.mem_map_ptr(ALIAS,4096,UC_PROT_ALL,ptr)
    uc.mem_map_ptr(0xffff0000,4096,UC_PROT_READ|UC_PROT_EXEC,ptr)
    def put(a,v):uc.mem_write(a,struct.pack('<I',v&0xffffffff))
    def get(a):return struct.unpack('<I',uc.mem_read(a,4))[0]
    put(ALIAS+0xff0,0);put(sy['vectors_page'],ALIAS)
    fault=[];notifiers=[];start=sy['__switch_to']
    assert get(start)&0xfffff000==0xe281c000
    save=get(start)&0xfff;assert get(start+4)&0xfffff000==0xe5923000
    tp=get(start+4)&0xfff
    def hook(uc,pc,size,user):
        if pc==sy['atomic_notifier_call_chain']:
            notifiers.append(pc);uc.reg_write(UC_ARM_REG_R0,0)
            uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
    def denied(uc,access,addr,size,value,user):
        fault.append({'PC':hex(uc.reg_read(UC_ARM_REG_PC)),'address':hex(addr),'access':'write to RX vector page'})
        return False
    uc.hook_add(UC_HOOK_CODE,hook);uc.hook_add(UC_HOOK_MEM_WRITE_PROT,denied)
    def verify(value):
        assert uc.reg_read(UC_ARM_REG_C13_C0_3)==value
        assert get(ALIAS+0xff0)==get(0xffff0ff0)==value
        assert bytes(uc.mem_read(ALIAS,0xff0))==b'\x95'*0xff0
        assert bytes(uc.mem_read(0xffff0ff4,12))==b'\x95'*12
    def set_tls(thread,value):
        put(REGS,value);uc.reg_write(UC_ARM_REG_CPSR,0xd3)
        uc.reg_write(UC_ARM_REG_SP,thread+0x1ff0);uc.reg_write(UC_ARM_REG_LR,STOP)
        uc.reg_write(UC_ARM_REG_R0,0xf0005);uc.reg_write(UC_ARM_REG_R1,REGS)
        uc.emu_start(sy['arm_syscall'],STOP,count=1000)
        assert uc.reg_read(UC_ARM_REG_PC)==STOP and uc.reg_read(UC_ARM_REG_R0)==0
        assert get(thread+tp)==value;verify(value)
    def switch(prev,nxt,value):
        put(nxt+tp,value)
        uc.mem_write(nxt+save,struct.pack('<10I',*[0]*8,nxt+0x1ff0,STOP))
        uc.reg_write(UC_ARM_REG_CPSR,0xd3);uc.reg_write(UC_ARM_REG_SP,prev+0x1ff0)
        uc.reg_write(UC_ARM_REG_LR,STOP)
        for r,v in [(UC_ARM_REG_R0,0x123456),(UC_ARM_REG_R1,prev),(UC_ARM_REG_R2,nxt)]:uc.reg_write(r,v)
        uc.emu_start(start,STOP,count=1000)
        assert uc.reg_read(UC_ARM_REG_PC)==STOP and uc.reg_read(UC_ARM_REG_R0)==0x123456
        assert uc.reg_read(UC_ARM_REG_SP)==nxt+0x1ff0;verify(value)
    try:
        if operation=='syscall':set_tls(A,0xb0011a48)
        else:switch(A,B,0)
        if not expect_fault:
            set_tls(A,0xb0011a48)
            switch(A,B,0xafd4d47c);switch(B,A,0xb0011a48)
            set_tls(A,0x46002000);switch(A,B,0x47004000);switch(B,A,0x46002000)
    except UcError:
        if not expect_fault:raise
    if expect_fault:
        assert len(fault)==1 and fault[0]['address']=='0xffff0ff0',fault
    else:assert not fault and len(notifiers)>=4
    assert any(lo==0xffff0000 and hi==0xffff0fff and prot==(UC_PROT_READ|UC_PROT_EXEC) for lo,hi,prot in uc.mem_regions())
    return {'operation':operation,'expected_failure':expect_fault,'faults':fault,'high_vector_permissions':'RX unchanged','shared_backing_page':True,'only_TLS_word_changed':not expect_fault,'thread_info_offsets':{'cpu_save':save,'tp_value':tp}}

old=[run('T4_ANDROID_UI_03',op,True) for op in ['switch','syscall']]
assert old[0]['faults'][0]['PC']=='0xc002a204'
new=[run('T4_ANDROID_INPUT_01',op) for op in ['switch','syscall']]
result={'UI03_hardware_failure_reproduced':old,'UI04_writable_alias':new,'mock':'atomic_notifier_call_chain only; no MMIO','ARM_cache_behavior':'requires hardware test','hardware':'pending'}
(OUT/'tls-arm-test.json').write_text(json.dumps(result,indent=2)+'\n')
print('TLS_PROTECTION_ARM_PASSED: exact UI03 PC=c002a204 reproduced; UI04 syscall/context switches synchronize TLS through RW alias; high vectors remain RX')
