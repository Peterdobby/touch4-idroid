#!/usr/bin/env python3
"""Check live-entry ABI with explicitly MOCKED platform cleanup callbacks.
Actual CPU quiesce and every loader instruction execute without skips.
This does NOT validate live iBoot hardware cleanup or USB.
"""
import hashlib,json,struct
from pathlib import Path
import unicorn as uc
from unicorn import arm_const as a
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'saved/build/chainload-live-iboot6'
image=(OUT/'t4-oib-live-iboot6.bin').read_bytes()
native=(OUT/'openiboot-native.bin').read_bytes()
firmware=(ROOT.parent/'touch4-idroid-untethered/build/untethered/T4_OIB_LOADER_01/iBoot.n81ap-10B500.raw').read_bytes()
helpers=[0x5ff1ce38,0x5ff1c210,0x5ff1c194,0x5ff1d2b8]
results=[]
for case in ('valid ABI with mocked platform','wrong jump prefix','wrong CPU prefix','user mode'):
    cpu=uc.Uc(uc.UC_ARCH_ARM,uc.UC_MODE_ARM)
    cpu.ctl_set_cpu_model(a.UC_CPU_ARM_CORTEX_A8)
    for base,size in [(0x41000000,0x100000),(0x44000000,0x100000),(0x5ff00000,0x100000)]:cpu.mem_map(base,size)
    cpu.mem_write(0x44000000,image)
    cpu.mem_write(0x5ff00000,firmware)
    # Explicit test doubles only; firmware source and produced binaries untouched.
    for address in helpers:cpu.mem_write(address,bytes.fromhex('7047'))
    if case=='wrong jump prefix':cpu.mem_write(0x5ff1cef0,b'\0'*4)
    if case=='wrong CPU prefix':cpu.mem_write(0x5ff1eb80,b'\0'*4)
    cpu.reg_write(a.UC_ARM_REG_CPSR,0x10 if case=='user mode' else 0x13)
    cpu.reg_write(a.UC_ARM_REG_SP,0x5fff0000)
    cpu.reg_write(a.UC_ARM_REG_LR,0x5ffe0000)
    trace=[];writes=[]
    def code(u,address,size,data):
        names={0x5ff1cef0:'native live jump_to ABI',0x5ff1eb80:'original CPU quiesce',
               0x44000100:'post-quiesce loader',0x41000000:'RAM wrapper',
               0x44000200:'Thumb ABI bridge',0x41001000:'OpeniBoot raw ARM entry',0x5ffe0000:'guard returned'}
        if address in names:trace.append(names[address])
        if address==0x5ff1cef0:
            assert [u.reg_read(r) for r in [a.UC_ARM_REG_R0,a.UC_ARM_REG_R1,a.UC_ARM_REG_R2,a.UC_ARM_REG_R3]]==[0,0x44000100,0,0]
        if address in (0x41001000,0x5ffe0000):u.emu_stop()
    def write(u,access,address,size,value,data):
        assert any(lo<=address and address+size<=hi for lo,hi in [(0x41000000,0x41045000),(0x44000f00,0x44000f40),(0x5ffef000,0x5fff0000)]),hex(address)
        writes.append(address)
    cpu.hook_add(uc.UC_HOOK_CODE,code)
    cpu.hook_add(uc.UC_HOOK_MEM_WRITE,write)
    cpu.emu_start(0x44000000,0,count=1000000)
    if case=='valid ABI with mocked platform':
        assert trace==['native live jump_to ABI','original CPU quiesce','post-quiesce loader','RAM wrapper','Thumb ABI bridge','OpeniBoot raw ARM entry'],trace
        expected=bytearray(native);struct.pack_into('<I',expected,0x18,0x44000201)
        assert cpu.mem_read(0x41000000,len(native))==expected
        assert not cpu.reg_read(a.UC_ARM_REG_CPSR)&0x20
        assert [cpu.reg_read(r) for r in [a.UC_ARM_REG_R0,a.UC_ARM_REG_R1,a.UC_ARM_REG_R2,a.UC_ARM_REG_R3]]==[0,0,0,0]
    else:
        assert trace==['guard returned'] and not writes
        assert cpu.reg_read(a.UC_ARM_REG_R0)==0xe601
    results.append(dict(case=case,passed=True,trace=trace,writes=len(writes)))
report=dict(all_passed=True,tests=results,platform_helpers_mocked=[hex(x) for x in helpers],
            image_sha256=hashlib.sha256(image).hexdigest(),hardware_success=False,
            limits='Native jump ABI, real CPU instructions and loader only; 4 platform callbacks mocked. Not live hardware proof.')
(OUT/'ARM-TESTS.json').write_text(json.dumps(report,indent=2)+'\n')
print('4 tests passed; live ABI and rejection guards checked. Four platform callbacks mocked; hardware UNCONFIRMED.')
