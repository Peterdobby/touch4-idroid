#!/usr/bin/env python3
"""Execute real loader/fixture instructions offline; this is NOT a USB boot test.

Unicorn does not model physical A4 cache/MMU/USB effects. No instructions are
patched, skipped, or replaced, including the fixture's MVA cache maintenance.
"""
import hashlib
import json
from pathlib import Path
import struct
import unicorn as uc
from unicorn import arm_const as arm

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'saved/build/chainload'
manifest = json.loads((OUT/'manifest.json').read_text())
native = (OUT/'openiboot-native.bin').read_bytes()
loader = (OUT/'t4-oib-loader.bin').read_bytes()
fixture = (OUT/'t4-oib-ram-fixture.bin').read_bytes()
ibss = (ROOT/'saved/build/iBSS.n81ap.raw').read_bytes()
syms = manifest['symbols']['fixture']
REGS = [getattr(arm, 'UC_ARM_REG_R'+str(i)) for i in range(13)]

def machine(cpsr=0x13):
    cpu = uc.Uc(uc.UC_ARCH_ARM, uc.UC_MODE_ARM)
    cpu.ctl_set_cpu_model(arm.UC_CPU_ARM_CORTEX_A8)
    cpu.mem_map(0x41000000, 0x100000)
    cpu.mem_map(0x44000000, 0x10000)
    cpu.mem_map(0x84000000, 0x40000)
    cpu.mem_write(0x84000000, ibss)
    cpu.reg_write(arm.UC_ARM_REG_CPSR, cpsr)
    cpu.reg_write(arm.UC_ARM_REG_SP, 0x8403f000)
    cpu.reg_write(arm.UC_ARM_REG_LR, 0x8403e000)
    for i, reg in enumerate(REGS):
        cpu.reg_write(reg, 0x55500000+i*0x101)
    return cpu

tests = []
for masks in (0, 0x80, 0x40, 0xc0):
    cpu = machine(0xa0000013 | masks)
    cpu.mem_write(0x44000000, loader)
    cpu.mem_write(0x41000000, native)
    registers_before = [cpu.reg_read(r) for r in REGS]
    before_cpsr = cpu.reg_read(arm.UC_ARM_REG_CPSR)
    writes = []
    cpu.hook_add(uc.UC_HOOK_MEM_WRITE, lambda u, a, p, n, v, d: writes.append((p,n)))
    cpu.emu_start(0x44000000, 0x41000000, count=4)
    assert cpu.reg_read(arm.UC_ARM_REG_PC) == 0x41000000
    assert cpu.reg_read(arm.UC_ARM_REG_CPSR) == before_cpsr
    assert cpu.reg_read(arm.UC_ARM_REG_SP) == 0x8403f000
    assert cpu.reg_read(arm.UC_ARM_REG_LR) == 0x8403e000
    assert [cpu.reg_read(r) for r in REGS[:12]] == registers_before[:12]
    assert cpu.reg_read(REGS[12]) == 0x41000000
    assert not writes
    tests.append({'name': f'12-byte loader CPSR mask {masks:#x}', 'passed': True,
                  'no_memory_writes': True, 'cpsr_sp_lr_preserved': True})

    cpu = machine(0xa0000013 | masks)
    cpu.mem_write(0x41000000, native)
    cpu.hook_add(uc.UC_HOOK_MEM_WRITE, lambda u, a, p, n, v, d: writes.append((p,n)))
    def stop_at_jump(u, address, size, data):
        if address == 0x8401496c:
            u.emu_stop()
    cpu.hook_add(uc.UC_HOOK_CODE, stop_at_jump)
    cpu.emu_start(0x41000000, 0, count=8)
    assert cpu.reg_read(arm.UC_ARM_REG_PC) == 0x8401496c, hex(cpu.reg_read(arm.UC_ARM_REG_PC))
    assert cpu.reg_read(arm.UC_ARM_REG_CPSR) & 0x20
    assert [cpu.reg_read(r) for r in REGS[:4]] == [0,0x41001000,0,0x8401496d]
    assert not writes
    tests.append({'name': f'unchanged wrapper ARM-to-Thumb mask {masks:#x}', 'passed': True})

def fixture_test(kind):
    cpu = machine(0x10 if kind == 'user-mode rejected' else 0x13)
    cpu.mem_write(0x41000000, fixture)
    if kind == 'wrong iBSS rejected':
        cpu.mem_write(0x8401496c, struct.pack('<I', 0))
    writes, trace, counts = [], [], {'instructions': 0}
    relocated_size = syms['relocated_end']-syms['relocated_begin']
    allowed = ((0x41000000, 0x41000000+len(native)),
               (0x44000000, 0x44000000+len(loader)),
               (0x44001000, 0x44001000+relocated_size))
    native_visits = 0
    def instruction(u, address, size, data):
        nonlocal native_visits
        counts['instructions'] += 1
        if address == 0x41000000:
            native_visits += 1
            trace.append('RAM fixture' if native_visits == 1 else 'unchanged native wrapper')
        if address == 0x44001000:
            trace.append('relocated RAM placement')
        if address == 0x44000000:
            trace.append('actual 12-byte loader')
            assert u.mem_read(0x41000000,len(native)) == native
        if address == 0x8401496c:
            trace.append('existing iBSS jump_to (Thumb)')
            u.emu_stop()
        if address == 0x8403e000:
            trace.append('returned without staging/boot')
            u.emu_stop()
    def write(u, access, address, size, value, data):
        assert any(lo <= address and address+size <= hi for lo,hi in allowed), hex(address)
        writes.append((address,size))
    cpu.hook_add(uc.UC_HOOK_CODE, instruction)
    cpu.hook_add(uc.UC_HOOK_MEM_WRITE, write)
    cpu.emu_start(0x41000000, 0, count=2000000)
    if kind == 'valid controlled iBSS':
        assert trace == ['RAM fixture', 'relocated RAM placement', 'actual 12-byte loader',
                         'unchanged native wrapper', 'existing iBSS jump_to (Thumb)'], trace
        assert cpu.mem_read(0x41000000,len(native)) == native
        assert cpu.mem_read(0x44000000,len(loader)) == loader
        assert cpu.mem_read(0x84000000,len(ibss)) == ibss
        assert cpu.reg_read(arm.UC_ARM_REG_SP) == 0x8403f000
        assert cpu.reg_read(arm.UC_ARM_REG_CPSR) & 0x20
        assert [cpu.reg_read(r) for r in REGS[:4]] == [0,0x41001000,0,0x8401496d]
    else:
        assert trace[-1] == 'returned without staging/boot'
        assert not writes
        assert cpu.reg_read(REGS[0]) == 0xe001
    tests.append({'name': kind, 'passed': True, 'trace': trace,
                  'instructions': counts['instructions'], 'ram_writes': len(writes)})

for kind in ('valid controlled iBSS', 'wrong iBSS rejected', 'user-mode rejected'):
    fixture_test(kind)

result = {'tests': tests, 'all_passed': True, 'hardware_success': False,
          'native_sha256': hashlib.sha256(native).hexdigest(),
          'loader_sha256': hashlib.sha256(loader).hexdigest(),
          'fixture_sha256': hashlib.sha256(fixture).hexdigest(),
          'limits': 'ARM instruction/data-path tests only. Real MMU mappings, cache effects, USB and iBSS teardown require hardware.',
          'test_source_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
(OUT/'ARM-TESTS.json').write_text(json.dumps(result, indent=2)+'\n')
print(f'ARM tests: {len(tests)} passed; native and iBSS unchanged; writes confined to declared RAM.')
print('Hardware USB/ACM success is NOT claimed by these tests.')
