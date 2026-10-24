#!/usr/bin/env python3
"""Execute the real ARM CPU adapter/loader/wrapper/Thumb bridge, no skips."""
import hashlib,json,struct
from pathlib import Path
import unicorn as uc
from unicorn import arm_const as a
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'saved/build/untethered-menu-03'
def main():
    native=(OUT/'openiboot-native.bin').read_bytes();ram=(OUT/'menu-full-ram-test.bin').read_bytes()
    cpu=uc.Uc(uc.UC_ARCH_ARM,uc.UC_MODE_ARM);cpu.ctl_set_cpu_model(a.UC_CPU_ARM_CORTEX_A8)
    cpu.mem_map(0x41000000,0x100000);cpu.mem_map(0x44000000,0x100000)
    cpu.mem_write(0x44000000,ram);cpu.reg_write(a.UC_ARM_REG_CPSR,0x13);cpu.reg_write(a.UC_ARM_REG_SP,0x440ff000)
    sctlr=(15,0,0,1,0,0,0);actlr=(15,0,0,1,0,0,1)
    original=cpu.reg_read(a.UC_ARM_REG_CP_REG,sctlr)
    cpu.reg_write(a.UC_ARM_REG_CP_REG,(*sctlr,(original|0x800)&~0x1005))
    cpu.reg_write(a.UC_ARM_REG_CP_REG,(*actlr,0x100))
    cpu.emu_start(0x44000300,0x41001000,count=3000000)
    assert cpu.reg_read(a.UC_ARM_REG_PC)==0x41001000
    expected=bytearray(native);struct.pack_into('<I',expected,0x18,0x44000201)
    assert bytes(cpu.mem_read(0x41000000,len(native)))==expected
    assert [cpu.reg_read(x) for x in [a.UC_ARM_REG_R0,a.UC_ARM_REG_R1,a.UC_ARM_REG_R2,a.UC_ARM_REG_R3]]==[0,0,0,0]
    assert cpu.reg_read(a.UC_ARM_REG_CP_REG,sctlr)&0x1805==0
    assert cpu.reg_read(a.UC_ARM_REG_CP_REG,actlr)&0x100==0
    # The native loader requires SVC/IRQ masking; permission to mask FIQ also
    # depends on the processor's security state. Execute cpsid if unchanged.
    assert cpu.reg_read(a.UC_ARM_REG_CPSR)&0x9f==0x93
    assert not cpu.reg_read(a.UC_ARM_REG_CPSR)&0x20
    result=dict(passed=True,ram_test_sha256=hashlib.sha256(ram).hexdigest(),
        native_payload_exact=True,raw_entry='0x41001000',registers_r0_r3_zero=True,
        cpu_state_valid=True,instruction_skips=False,hardware_success=False,
        limits='Unicorn does not model physical A4 cache or display/USB effects')
    (OUT/'MENU-RAM-ARM-TEST.json').write_text(json.dumps(result,indent=2)+'\n')
    print('Full menu ARM entry/copy/bridge test passed; production native payload unchanged.')
if __name__=='__main__':main()
