#!/usr/bin/env python3
"""Execute extracted CPU code and loader without replacing any instructions."""
import hashlib
import json
from pathlib import Path
import struct
import unicorn as uc
from unicorn import arm_const as a

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'saved/build/chainload-iboot6'
m=json.loads((OUT/'manifest.json').read_text())
native=(OUT/'openiboot-native.bin').read_bytes()
stage=(OUT/'iboot6-ram-stage.bin').read_bytes()
cpu=uc.Uc(uc.UC_ARCH_ARM,uc.UC_MODE_ARM)
cpu.ctl_set_cpu_model(a.UC_CPU_ARM_CORTEX_A8)
for base,size in [(0x41000000,0x100000),(0x43000000,0x100000),(0x44000000,0x100000),(0x84000000,0x40000)]:
    cpu.mem_map(base,size)
cpu.mem_write(0x41001000,stage)
ibss=(ROOT/'saved/build/iBSS.n81ap.raw').read_bytes()
cpu.mem_write(0x84000000,ibss)
cpu.reg_write(a.UC_ARM_REG_CPSR,0x13)
cpu.reg_write(a.UC_ARM_REG_SP,0x8403f000)
trace=[]
count={'instructions':0,'writes':0}
def code(u,address,size,data):
    count['instructions']+=1
    names={0x4301eb80:'original iBoot6 CPU quiesce (relocated)',
           0x4301e61c:'original iBoot6 cache routine (relocated)',
           0x44000000:'post-quiesce loader',0x41000000:'RAM-adapted native wrapper',
           0x44000200:'Thumb ABI bridge'}
    if address in names:trace.append(names[address])
    if address==0x41001000 and 'Thumb ABI bridge' in trace:
        trace.append('original OpeniBoot ARM raw entry')
        u.emu_stop()
def write(u,access,address,size,value,data):
    count['writes']+=1
    assert any(lo<=address and address+size<=hi for lo,hi in
               [(0x43000000,0x4301ebb0),(0x44000000,0x44046000),(0x41000000,0x41045000)]),hex(address)
cpu.hook_add(uc.UC_HOOK_CODE,code)
cpu.hook_add(uc.UC_HOOK_MEM_WRITE,write)
cpu.emu_start(0x41001000,0,count=3000000)
assert trace==['original iBoot6 CPU quiesce (relocated)',
               'original iBoot6 cache routine (relocated)','post-quiesce loader',
               'RAM-adapted native wrapper','Thumb ABI bridge','original OpeniBoot ARM raw entry'],trace
expected=bytearray(native)
struct.pack_into('<I',expected,0x18,0x44000201)
assert cpu.mem_read(0x41000000,len(native))==expected
assert cpu.mem_read(0x84000000,len(ibss))==ibss
assert [cpu.reg_read(r) for r in (a.UC_ARM_REG_R0,a.UC_ARM_REG_R1,a.UC_ARM_REG_R2,a.UC_ARM_REG_R3)]==[0,0,0,0]
assert not cpu.reg_read(a.UC_ARM_REG_CPSR)&0x20
result=dict(all_passed=True,trace=trace,counts=count,
    native_input_unchanged=True,raw_payload_byte_exact=True,ibss_unchanged=True,
    only_ram_wrapper_literal_changed=True,no_instruction_skips=True,hardware_success=False,
    files=m['files'],test_source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    limits='Entry assumes already quiesced iBSS context. Physical cache effects and live iBoot6/DRV6 handoff are NOT validated.')
(OUT/'ARM-TESTS.json').write_text(json.dumps(result,indent=2)+'\n')
print('PASS: original iBoot6 CPU instructions -> loader -> bridge -> original OpeniBoot ARM entry')
print('PASS: r0-r3 zero, payload exact, original iBSS unchanged, writes confined to declared RAM')
