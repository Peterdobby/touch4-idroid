#!/usr/bin/env python3
"""Build a RAM-only filesystem adapter around the captured existing iBoot6.
No exploit builder or signature patcher is invoked.
"""
import hashlib,json,struct,subprocess,sys,zlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
OUT=ROOT/'saved/build/untethered-menu-03'
CROSS=str(ROOT/'saved/toolchain/arm-eabi-4.8/bin/arm-eabi-')
sys.path.insert(0,str(ROOT/'chainload'))
from build import check_protected
def sha(b):return hashlib.sha256(b).hexdigest()
def main():
    check_protected()
    m=json.loads((OUT/'ANDROID-BUNDLE.json').read_text())
    raw=(ROOT.parent/'touch4-idroid-untethered/build/untethered/inputs/iBoot.n81ap-10B500.raw').read_bytes()
    inherited=(OUT/'iboot6-inherited-ram.bin').read_bytes()
    assert sha(raw)=='d167d3303354296121da953ba8df62755f902932fccb8fdb29232bba1d057bda'
    assert sha(inherited)=='2463b37f4bf375fa88f6958e25f07dd9a2b8f697aa9a6efad9a2c8291e116419'
    assert len(raw)==len(inherited)==0x43000
    # Reuse captured code and pristine initialized data. The owned adapter is
    # inserted only in the unused text/data alignment gap; the fsboot entry
    # routes into it before the old boot-ramdisk path can execute again.
    iboot=bytearray(inherited[:0x42000]+raw[0x42000:])
    assert struct.unpack_from('<I',raw,0x42004)[0]==0x5ff00ae5
    rows=[','.join(hex(r[k])+'u' for k in ['offset','size','destination','crc32'])
          for r in m['records']]
    (OUT/'bundle.h').write_text('#define BUNDLE_SIZE %du\nstatic const unsigned expected[4][4]={\n%s\n};\n'%
        (m['bundle_bytes'],',\n'.join('{'+r+'}' for r in rows)))
    table=[]
    for i in range(256):
        for _ in range(8):i=(i>>1)^(0xedb88320 if i&1 else 0)
        table.append(i)
    (OUT/'crc-table.h').write_text('static const unsigned crc_table[256]={'+','.join(hex(x)+'u' for x in table)+'};\n')
    dt_path=Path('~/Legacy-iOS-Kit/resources/patch/touch4-ios7/DeviceTree.n81ap.img3')
    dt_image=dt_path.read_bytes();off=20;dt=None
    while off<len(dt_image):
        tag,size,n=struct.unpack_from('<3I',dt_image,off)
        assert size>=12 and n<=size-12
        if tag==0x44415441:dt=dt_image[off+12:off+12+n]
        off+=size
    assert off==len(dt_image) and dt is not None and len(dt)==62824
    assert sha(dt)=='a9e8bd2d9fcee074cde348692e46773e3ff10e6f7007f572f071228ef151dada'
    (OUT/'dt-ios7.bin').write_bytes(dt)
    (OUT/'ios7.h').write_text('#define IOS7_DT_SIZE %du\n#define IOS7_DT_CRC 0x%08xu\n'%(len(dt),zlib.crc32(dt)))
    subprocess.run([CROSS+'gcc','-nostdlib','-fno-use-linker-plugin','-mcpu=cortex-a8','-mthumb',
                    '-Wl,-Ttext=0x43000400','-Wl,-e,_start','-Wl,--build-id=none',
                    str(HERE/'bridges.S'),'-o',str(OUT/'bridges.elf')],check=True)
    subprocess.run([CROSS+'objcopy','-O','binary',str(OUT/'bridges.elf'),str(OUT/'bridges.bin')],check=True)
    bridges=(OUT/'bridges.bin').read_bytes()
    assert len(bridges)==0x2c and bridges[0x20:]==bytes.fromhex('8c4600200021002200236047')
    (OUT/'bridges.h').write_text('\n'.join('static const unsigned char '+name+'[]={'+
        ','.join(hex(v) for v in bridges[a:a+size])+'};' for name,a,size in
        [('native_start_bytes',0,24),('native_bridge_bytes',0x20,12)])+'\n')
    # Apple iBoot's platform ABI treats r9 as volatile scratch; generic ARM
    # EABI GCC otherwise keeps live locals there across native iBoot calls.
    flags=['-mcpu=cortex-a8','-mthumb','-ffixed-r9','-std=gnu99','-Os','-ffreestanding','-fno-builtin',
           '-fno-unwind-tables','-fno-asynchronous-unwind-tables','-Wall','-Wextra','-Werror',
           '-I'+str(OUT),'-I'+str(ROOT/'saved/sources/openiBoot-c5cee8c-ui/pcf')]
    for name,source in [('fs','fs.c'),('fs-entry','fs-entry.S')]:
        subprocess.run([CROSS+'gcc',*flags,'-c',str(HERE/source),'-o',str(OUT/(name+'.o'))],check=True)
    elf=OUT/'fs.elf'
    subprocess.run([CROSS+'ld','--build-id=none','-T',str(HERE/'fs.ld'),'-o',str(elf),
                    str(OUT/'fs-entry.o'),str(OUT/'fs.o')],check=True)
    subprocess.run([CROSS+'objcopy','-O','binary',str(elf),str(OUT/'fs.bin')],check=True)
    symbols={p[2]:int(p[0],16) for line in subprocess.check_output([CROSS+'nm','-n',str(elf)],text=True).splitlines()
             if len(p:=line.split())==3}
    assert symbols['t4_fs_entry']==0x5ff41080
    adapter=(OUT/'fs.bin').read_bytes()
    assert len(adapter)<=0xf60 and set(raw[0x41080:0x42000])=={0}
    assert raw[0xae4:0xae8]==inherited[0xae4:0xae8]
    (OUT/'fs-route.S').write_text('.syntax unified\n.thumb\n.global _start\n_start:\n b.w 0x5ff41080\n')
    subprocess.run([CROSS+'gcc','-nostdlib','-fno-use-linker-plugin','-mcpu=cortex-a8','-mthumb',
                    '-Wl,-Ttext=0x5ff00ae4','-Wl,-e,_start','-Wl,--build-id=none',
                    str(OUT/'fs-route.S'),'-o',str(OUT/'fs-route.elf')],check=True)
    subprocess.run([CROSS+'objcopy','-O','binary',str(OUT/'fs-route.elf'),str(OUT/'fs-route.bin')],check=True)
    branch=(OUT/'fs-route.bin').read_bytes();assert len(branch)==4
    iboot[0xae4:0xae8]=branch
    iboot[0x41080:0x41080+len(adapter)]=adapter
    assert struct.unpack_from('<I',adapter,symbols['t4_mode']-symbols['t4_fs_entry'])[0]==2
    struct.pack_into('<I',iboot,0x42004,0x5ff41081)
    (OUT/'iboot6-fs-service.raw').write_bytes(iboot)
    ios=bytearray(iboot);struct.pack_into('<I',ios,symbols['t4_mode']-0x5ff00000,1)
    (OUT/'iboot6-ios7-service.raw').write_bytes(ios)
    (OUT/'IOS7-REFERENCE.json').write_text(json.dumps(dict(
        status='RAM_TEST_PENDING',system_version='7.1.2',build='11D257',
        kernelcache='/System/Library/Caches/com.apple.kernelcaches/kernelcache',
        devicetree_source=str(dt_path),devicetree_image_sha256=sha(dt_image),
        devicetree_flat_sha256=sha(dt),devicetree_flat_bytes=len(dt),
        filesystem_path='/boot/t4/devicetree-ios7.img3',native_dt_cache={'pointer':'0x5ff47f84','length':'0x5ff47f88'},
        image_sha256=sha(ios),other_ios_versions='Require matching DeviceTree and verified kernel path; not claimed compatible'),indent=2)+'\n')
    # No existing DRA or signature-check instruction is changed.
    for lo,hi in [(0,0xae4),(0xae8,0x41080)]:assert iboot[lo:hi]==inherited[lo:hi]
    record=dict(status='RAM_TEST_PENDING',captured_code_sha256=sha(inherited[:0x42000]),
       service_sha256=sha(iboot),adapter_sha256=sha((OUT/'fs.bin').read_bytes()),symbols=symbols,
       preserved_code_bytes=0x41070-4,mode_offset=symbols['t4_mode']-0x5ff00000,
       initialized_data='Reset from stock image to avoid stale heap/list pointers',
       new_control_change={'entry_hook':hex(0xae4),'callback':hex(0x42004),'target':hex(0x5ff41081),'purpose':'Owned boot dispatch; no exploit/signature code changes'},
       new_exploit_code=False,new_signature_patches=False,firmware_writes=False)
    record['native_abi']='r9 reserved in adapter; captured Apple functions can clobber r9 without saving it'
    (OUT/'FS-BUILD.json').write_text(json.dumps(record,indent=2)+'\n')
    check_protected();print('RAM filesystem adapter:',OUT/'fs.bin');print('Existing iBoot code reused byte for byte:',record['preserved_code_bytes'])
if __name__=='__main__':main()
