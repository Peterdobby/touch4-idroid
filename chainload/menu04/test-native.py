#!/usr/bin/env python3
"""Execute the compiled mode4 loader and verify native API arguments in ARM."""
import json
import struct
import zlib
import argparse
from pathlib import Path
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_R9,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'saved/build/T4_ANDROID_INSTALLER_02/template'
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--target-raw',type=Path);args=parser.parse_args()
    report=json.loads((OUT/'FS-BUILD.json').read_text());sym=report['symbols'];code=(OUT/'fs.bin').read_bytes()
    # A real ARM image fixture. This verifies placement/API/CRC, not its hardware boot.
    raw=(args.target_raw or ROOT/'saved/build/untethered-menu-03/iboot6-inherited-ram.bin').read_bytes()
    results=[]
    for case in ['success','corrupt','missing_profile','wrong_size']:
        u=Uc(UC_ARCH_ARM,UC_MODE_ARM);u.mem_map(0x40000000,0x10000000);u.mem_map(0x5ff00000,0x50000)
        u.mem_write(sym['t4_fs_entry'],code);u.reg_write(UC_ARM_REG_SP,0x4feff000);u.reg_write(UC_ARM_REG_LR,0x4ffff000)
        for name,value in [('t4_mode',4),('t4_ios_size',0 if case=='missing_profile' else len(raw)),('t4_ios_crc',zlib.crc32(raw))]:u.mem_write(sym[name],struct.pack('<I',value))
        statuses=[];jump=[]
        def cstr(a):return bytes(u.mem_read(a,160)).split(b'\0',1)[0].decode()
        def returned(value=0):u.reg_write(UC_ARM_REG_R0,value);u.reg_write(UC_ARM_REG_R9,0xdeadbeef);u.reg_write(UC_ARM_REG_PC,u.reg_read(UC_ARM_REG_LR))
        def hook(u,address,size,user):
            r=[u.reg_read(x) for x in [UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3]]
            if address==sym['status']:statuses.append(cstr(r[1]));returned()
            elif address==sym['crc']:returned(zlib.crc32(bytes(u.mem_read(r[0],r[1]))))
            elif address==0x5ff15ef4:
                assert (cstr(r[0]),cstr(r[1]),r[2]) in [('boot-partition','0',0),('boot-ramdisk','',0)];returned()
            elif address==0x5ff00a44:returned()
            elif address==0x5ff21c7c:
                assert cstr(r[0])=='/boot/boot/t4/ios-iboot.img3' and r[3]==0x69626f62
                assert struct.unpack('<I',u.mem_read(r[1],4))[0]==0x44000000
                assert struct.unpack('<I',u.mem_read(u.reg_read(UC_ARM_REG_SP),4))[0]==0
                blob=bytearray(raw)
                if case=='corrupt':blob[128]^=1
                u.mem_write(0x44000000,bytes(blob));u.mem_write(r[2],struct.pack('<I',len(raw)-(4 if case=='wrong_size' else 0)));returned()
            elif address==0x5ff1cef0:
                assert r==[0,0x44000000,0,0] and bytes(u.mem_read(0x44000000,len(raw)))==raw
                jump.append(True);u.emu_stop()
            else:raise AssertionError(hex(address))
        u.hook_add(UC_HOOK_CODE,hook,begin=0x5ff00000,end=0x5ff4107f)
        for name in ['status','crc']:u.hook_add(UC_HOOK_CODE,hook,begin=sym[name],end=sym[name])
        u.emu_start(sym['t4_fs_entry']|1,0x4ffff000,count=1000000)
        assert bool(jump)==(case=='success'),(case,statuses)
        results.append(dict(case=case,passed=True,last_status=statuses[-1]))
    name='NATIVE-ARM-REAL-TARGET-TESTS.json' if args.target_raw else 'NATIVE-ARM-TESTS.json'
    (OUT/name).write_text(json.dumps(dict(hardware_test=False,raw_bytes=len(raw),target_entry_executed=False,results=results),indent=2)+'\n')
    print('4 compiled ARM native-iBoot handoff tests passed.')
if __name__=='__main__':main()
