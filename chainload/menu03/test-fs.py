#!/usr/bin/env python3
"""Execute the compiled ARM adapter against an independent iBoot API model.
Tests full-sized overlapping placement and fail-closed header/CRC behavior.
This does not prove that real iBoot filesystem/NAND hardware works.
"""
import hashlib,json,struct,zlib
from pathlib import Path
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_R9,UC_ARM_REG_PC,UC_ARM_REG_LR,UC_ARM_REG_SP,UC_ARM_REG_CPSR
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'saved/build/untethered-menu-03'
manifest=json.loads((OUT/'FS-BUILD.json').read_text());sym=manifest['symbols']
meta=json.loads((OUT/'ANDROID-BUNDLE.json').read_text());bundle=(OUT/'android.bundle').read_bytes();fs=(OUT/'fs.bin').read_bytes()
REGS=[UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3]
def cstr(u,a):
    b=bytes(u.mem_read(a,160));return b.split(b'\0',1)[0].decode()
def fresh():
    u=Uc(UC_ARCH_ARM,UC_MODE_ARM);u.mem_map(0x40000000,0x10000000);u.mem_map(0x5ff00000,0x50000)
    u.mem_write(sym['t4_fs_entry'],fs);u.reg_write(UC_ARM_REG_SP,0x4feff000);u.reg_write(UC_ARM_REG_LR,0x4ffff000)
    return u
def returned(u,value=0):
    u.reg_write(UC_ARM_REG_R0,value&0xffffffff);u.reg_write(UC_ARM_REG_PC,u.reg_read(UC_ARM_REG_LR))
def run_case(name,mode=2,damage=None):
    u=fresh();loaded=bytearray(bundle)
    dt=(OUT/'dt-ios7.bin').read_bytes()
    if damage=='header':loaded[0]^=1
    if damage=='payload':loaded[meta['records'][1]['offset']+123]^=1
    u.mem_write(sym['t4_mode'],struct.pack('<I',mode));statuses=[];called=[];jumped=[]
    def status(u,a,size,user):
        statuses.append(cstr(u,u.reg_read(UC_ARM_REG_R1)))
        # The captured Apple iBoot code uses r9 as caller-clobbered scratch
        # (e.g. 5ff1df34 has no save/restore). Generic ARM EABI differs here.
        u.reg_write(UC_ARM_REG_R9,0xa5a5a5a5);returned(u)
    u.hook_add(UC_HOOK_CODE,status,begin=sym['status'],end=sym['status'])
    # Independently calculate large-buffer CRCs on the host. The real compiled
    # CRC routine is exercised separately below on a known standard vector.
    def checksum(u,a,size,user):
        address=u.reg_read(UC_ARM_REG_R0);n=u.reg_read(UC_ARM_REG_R1)
        assert n<=len(bundle)
        returned(u,zlib.crc32(bytes(u.mem_read(address,n))))
    u.hook_add(UC_HOOK_CODE,checksum,begin=sym['crc'],end=sym['crc'])
    def api(u,a,size,user):
        r=[u.reg_read(x) for x in REGS];called.append(a)
        u.reg_write(UC_ARM_REG_R9,0xa5a5a5a5)
        if a==0x5ff15ef4:
            assert (cstr(u,r[0]),cstr(u,r[1]),r[2]) in [('boot-partition','0',0),('boot-ramdisk','',0),('boot-args','pio-error=0',0)]
            returned(u)
        elif a==0x5ff00a44:returned(u)
        elif a==0x5ff21c7c:
            dest=struct.unpack('<I',u.mem_read(r[1],4))[0];limit=struct.unpack('<I',u.mem_read(r[2],4))[0]
            assert struct.unpack('<I',u.mem_read(u.reg_read(UC_ARM_REG_SP),4))[0]==0
            if mode==1:
                assert cstr(u,r[0])=='/boot/boot/t4/devicetree-ios7.img3'
                assert dest==0x47f00000 and limit==0x100000 and r[3]==0x64747265
                data=bytearray(dt)
                if damage=='dt':data[0]^=1
            else:
                assert cstr(u,r[0])=='/boot/boot/t4/android.img3'
                assert dest==0x44000000 and len(loaded)<limit and r[3]==0x6b726e6c
                data=loaded
            u.mem_write(dest,bytes(data));u.mem_write(r[2],struct.pack('<I',len(data)));returned(u)
        elif a==0x5ff1cef0:
            assert r==[0,0x43000401,0,0];jumped.append(True);u.emu_stop()
        elif a==0x5ff19cc4:
            assert mode==1 and cstr(u,r[0])=='/boot/System/Library/Caches/com.apple.kernelcaches/kernelcache'
            assert bytes(u.mem_read(0x47f00000,len(dt)))==dt
            assert struct.unpack('<I',u.mem_read(0x5ff47f84,4))[0]==0x47f00000
            assert struct.unpack('<I',u.mem_read(0x5ff47f88,4))[0]==len(dt)
            u.mem_write(r[1],struct.pack('<I',0x40008000));u.mem_write(0x5ff47f98,struct.pack('<I',0x4fe00000));returned(u)
        elif a==0x5ff00a28:
            assert mode==1 and r[:2]==[0x40008000,0x4fe00000];jumped.append(True);u.emu_stop()
        else:raise AssertionError('Unexpected iBoot call '+hex(a))
    u.hook_add(UC_HOOK_CODE,api,begin=0x5ff00000,end=0x5ff4107f)
    u.emu_start(sym['t4_fs_entry']|1,0x4ffff000,count=200000000)
    if damage:
        assert not jumped and statuses[-1] in ['BUNDLE_HEADER_FAILED','PAYLOAD_CHECKSUM_FAILED','IOS7_DEVICETREE_CHECKSUM_FAILED']
    elif mode==3:
        assert not jumped and statuses[-1]=='LOCAL_ANDROID_BUNDLE_READ_VERIFIED'
    elif mode==1:
        assert jumped and statuses[-1]=='NATIVE_IOS_KERNEL_HANDOFF'
    else:
        assert jumped,'No native jump; last status='+str(statuses[-1:] or 'none')
        for r in meta['records']:
            expected=bytearray(Path(r['path']).read_bytes())
            if r['name']=='openiboot':struct.pack_into('<I',expected,0x18,0x43000421)
            actual=bytes(u.mem_read(r['destination'],r['size']))
            assert actual==expected,r['name']+' corrupted during overlapping placement'
        before=bytearray(fs);struct.pack_into('<I',before,sym['t4_mode']-sym['t4_fs_entry'],mode)
        assert bytes(u.mem_read(sym['t4_fs_entry'],len(fs)))==before
        assert bytes(u.mem_read(0x43000400,24))==(OUT/'bridges.bin').read_bytes()[:24]
        assert bytes(u.mem_read(0x43000420,12))==(OUT/'bridges.bin').read_bytes()[0x20:]
    return dict(name=name,passed=True,last_status=statuses[-1],native_jump=bool(jumped))
def main():
    u=fresh();u.mem_write(0x42000001,b'123456789');u.reg_write(UC_ARM_REG_R0,0x42000001);u.reg_write(UC_ARM_REG_R1,9)
    u.emu_start(sym['crc']|1,0x4ffff000,count=10000)
    assert u.reg_read(UC_ARM_REG_R0)==0xcbf43926
    results=[dict(name='Compiled ARM CRC32 known vector, unaligned input',passed=True)]
    for args in [('full-sized kernel/initrd/handoff/native overlap',2,None),('read-only probe',3,None),('corrupt header',2,'header'),('corrupt initrd',2,'payload'),('iOS7 DT cache and native kernel handoff',1,None),('corrupt iOS7 DeviceTree',1,'dt')]:
        r=run_case(*args);results.append(r);print(r,flush=True)
    for image,mode in [('iboot6-fs-service.raw',2),('iboot6-ios7-service.raw',1)]:
        u=fresh();raw=(OUT/image).read_bytes();u.mem_write(0x44000000,raw);u.reg_write(UC_ARM_REG_CPSR,0xd3)
        entry=struct.unpack_from('<I',raw,0x30c)[0]
        u.emu_start(0x44000000,entry&~1,count=2000000)
        assert struct.unpack('<I',u.mem_read(sym['t4_mode'],4))[0]==mode
        assert bytes(u.mem_read(sym['t4_fs_entry'],len(fs)))==raw[0x41080:0x41080+len(fs)]
        results.append(dict(name=image+' actual startup relocation and BSS clear',passed=True))
    # Execute Apple's actual cached-DeviceTree reader, rather than only the
    # model, to verify that the two pinned globals supply our target DT.
    u=fresh();raw=(OUT/'iboot6-fs-service.raw').read_bytes();u.mem_write(0x5ff00000,raw[:0x43000])
    u.mem_write(0x5ff47f84,struct.pack('<I',0x47f00000));u.mem_write(0x5ff47f88,struct.pack('<I',62824))
    u.reg_write(UC_ARM_REG_R0,0x4fe00000);u.reg_write(UC_ARM_REG_R1,0x4fe00004)
    u.emu_start(0x5ff15c7d,0x4ffff000,count=10000)
    assert u.reg_read(UC_ARM_REG_R0)==0 and struct.unpack('<2I',u.mem_read(0x4fe00000,8))==(0x47f00000,62824)
    results.append(dict(name='Actual native iBoot cached DeviceTree contract',passed=True))
    report=dict(adapter_sha256=hashlib.sha256(fs).hexdigest(),results=results,hardware_test=False)
    (OUT/'FS-OFFLINE-TESTS.json').write_text(json.dumps(report,indent=2)+'\n')
    print(str(len(results))+' ARM adapter tests passed; hardware status is recorded separately.',flush=True)
if __name__=='__main__':main()
