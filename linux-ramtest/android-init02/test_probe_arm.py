#!/usr/bin/env python3
"""Execute bootstrap/probe ARM ELFs with mocked syscalls; never execute Android on host."""
from pathlib import Path
import struct
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_INTR
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R7,UC_ARM_REG_SP

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'saved/build/T4_ANDROID_INIT_02'
def run(name,parent=1,exec_fails=False,connect_error=0):
    elf=(OUT/name).read_bytes();uc=Uc(UC_ARCH_ARM,UC_MODE_ARM)
    ph=struct.unpack_from('<I',elf,28)[0];size,count=struct.unpack_from('<HH',elf,42)
    segments=[struct.unpack_from('<8I',elf,ph+i*size) for i in range(count)]
    segments=[p for p in segments if p[0]==1 and p[5]]
    lo=min(p[2] for p in segments)&~4095
    hi=(max(p[2]+p[5] for p in segments)+4095)&~4095
    uc.mem_map(lo,hi-lo)
    for p in segments:uc.mem_write(p[2],elf[p[1]:p[1]+p[4]])
    uc.mem_map(0x1000000,0x10000);uc.reg_write(UC_ARM_REG_SP,0x1010000)
    logs=[];calls=[]
    def string(p):
        b=bytearray()
        for i in range(4096):
            c=uc.mem_read(p+i,1)[0]
            if not c:return b.decode()
            b.append(c)
        raise AssertionError('unterminated string')
    def syscall(uc,kind,data):
        n=uc.reg_read(UC_ARM_REG_R7)
        a,b,c=[uc.reg_read(r) for r in [UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2]]
        calls.append(n)
        if n==5:
            assert string(a)=='/dev/kmsg' and b==1;ret=3
        elif n==4:
            assert a==3 and c<256;logs.append(bytes(uc.mem_read(b,c)).decode());ret=c
        elif n==11:
            assert string(a)=='/android-init'
            argv=struct.unpack('<II',uc.mem_read(b,8))
            assert string(argv[0])=='/init' and argv[1]==0
            if not exec_fails:uc.emu_stop()
            ret=(-8)&0xffffffff
        elif n==14:
            assert string(a)=='/dev/kmsg' and b==0o20600 and c==0x10b;ret=0
        elif n==33:
            assert string(a) in ['/dev/.coldboot_done','/data/property'] and b==0;ret=0
        elif n==281:
            assert (a,b,c)==(1,1,0);ret=4
        elif n==283:
            assert a==4 and c==31 and bytes(uc.mem_read(b,2))==b'\x01\x00'
            assert string(b+2)=='/dev/socket/property_service';ret=connect_error&0xffffffff
        elif n==6:
            assert a==4;ret=0
        elif n==64:ret=parent
        elif n==20:ret=42
        elif n==162:
            assert struct.unpack('<II',uc.mem_read(a,8))==(5,0)
            uc.emu_stop();ret=0
        else:raise AssertionError(f'unexpected syscall {n}')
        uc.reg_write(UC_ARM_REG_R0,ret)
    uc.hook_add(UC_HOOK_INTR,syscall)
    uc.emu_start(struct.unpack_from('<I',elf,24)[0],0,count=100000)
    return ''.join(logs),calls

log,calls=run('init')
assert calls==[5,4,11] and 'BOOTSTRAP_EXEC' in log and 'SERVICE_REACHED' not in log
log,calls=run('init',exec_fails=True)
assert 'EXEC_FAILED' in log and '0xfffffff8' in log and 'SERVICE_REACHED' not in log
log,calls=run('t4-probe')
assert 'SERVICE_PARENT=0x00000001' in log and 'ANDROID_INIT_SERVICE_REACHED' in log
log,calls=run('t4-probe',parent=2)
assert 'UNEXPECTED_PARENT' in log and 'ANDROID_INIT_SERVICE_REACHED' not in log
print('ARM_PROBE_PASSED: PID1 exec path, failure reporting, PID1 service marker, wrong-parent refusal; no block syscalls')

log,calls=run('t4-probe',connect_error=-38)
assert 'ENVIRONMENT_CHECK_FAILED' in log and 'ENVIRONMENT_CONFIRMED' not in log
log,calls=run('t4-probe')
assert 'ANDROID_INIT_ENVIRONMENT_CONFIRMED' in log
print('PROBE_ARM_PASSED: bootstrap exec, failed exec, PID1 service, real environment checks and negative socket result')
