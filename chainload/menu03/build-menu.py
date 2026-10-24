#!/usr/bin/env python3
"""Build real-route menu overlays and a post-quiesce ibob image, host only."""
import os
import hashlib,json,shutil,struct,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).resolve().parent
OUT=ROOT/'saved/build/untethered-menu-03';CROSS=str(ROOT/'saved/toolchain/arm-eabi-4.8/bin/arm-eabi-')
KIT=(Path(os.environ.get('T4_KIT_DIR', str(Path.home() / 'Legacy-iOS-Kit'))) / 'bin/macos')
sys.path.insert(0,str(ROOT/'chainload'));from build import check_protected
sys.path.insert(0,str(ROOT/'tools'));from native_image import pack_native
def sha(b):return hashlib.sha256(b).hexdigest()
def main():
    check_protected();fs=json.loads((OUT/'FS-BUILD.json').read_text())
    tests=json.loads((OUT/'FS-OFFLINE-TESTS.json').read_text())
    assert fs['adapter_sha256']==tests['adapter_sha256'] and all(x['passed'] for x in tests['results'])
    service=(OUT/'iboot6-ios7-service.raw').read_bytes()
    assert len(service)==0x43000 and len(service)%4==0
    assert struct.unpack_from('<I',service,fs['mode_offset'])[0]==1
    raw=(ROOT/'saved/build/phase1-published/openiboot.bin').read_bytes()
    assert struct.unpack_from('<3I',raw,0x3be1c)[2]==0x3051
    (OUT/'menu-config.h').write_text('#define SERVICE_SIZE %du\n#define MODE_OFFSET 0x%xu\n'%(len(service),fs['mode_offset']))
    (OUT/'menu-assets.S').write_text('.section .rodata.service,"a",%progbits\n.balign 4\n.global service_blob,service_end\nservice_blob:\n.incbin "iboot6-ios7-service.raw"\nservice_end:\n.section .note.GNU-stack,"",%progbits\n')
    variants={}
    for name,base,entry in [('live',0x45000000,'t4_menu_live'),('boot',0x44000,'t4_menu_main')]:
        elf=OUT/('menu-'+name+'.elf')
        subprocess.run([CROSS+'gcc','-nostdlib','-fno-use-linker-plugin','-mcpu=cortex-a8','-mthumb','-std=gnu99',
            '-Os','-fno-builtin','-fno-unwind-tables','-fno-asynchronous-unwind-tables','-Wall','-Wextra','-Werror',
            '-Wl,-Ttext='+hex(base),'-Wl,-N','-Wl,--build-id=none','-Wl,-e,'+entry,
            '-I'+str(OUT),'-I'+str(ROOT/'saved/sources/openiBoot-c5cee8c-ui/pcf'),
            str(HERE/'menu.c'),str(OUT/'menu-assets.S'),'-o',str(elf)],cwd=OUT,check=True)
        b=elf.read_bytes();e,phoff=struct.unpack_from('<II',b,24);ps,pn=struct.unpack_from('<HH',b,42)
        loads=[p for i in range(pn) if (p:=struct.unpack_from('<8I',b,phoff+i*ps))[0]==1 and p[5]]
        end=(max(p[2]+p[5] for p in loads)+3)&~3;assert min(p[2] for p in loads)==base
        image=bytearray(end-base)
        for p in loads:image[p[2]-base:p[2]-base+p[4]]=b[p[1]:p[1]+p[4]]
        symbols={p[2]:int(p[0],16) for line in subprocess.check_output([CROSS+'nm','-n',str(elf)],text=True).splitlines() if len(p:=line.split())==3}
        assert image[symbols['service_blob']-base:symbols['service_end']-base]==service
        (OUT/('menu-'+name+'.bin')).write_bytes(image)
        variants[name]=dict(base=base,entry=e,bytes=len(image),sha256=sha(image),symbols=symbols)
        if name=='boot':
            packed=bytearray(end);packed[:len(raw)]=raw;packed[base:]=image
            for off,old,new in [(0x30c,0x3fb20,end),(0x310,0x437a0,end),(0x39c04,0x8209,e)]:
                assert struct.unpack_from('<I',raw,off)[0]==old;struct.pack_into('<I',packed,off,new)
            assert packed[0x364:0x30c00]==raw[0x364:0x30c00]
            (OUT/'openiboot-menu.bin').write_bytes(packed)
            pack_native(OUT/'openiboot-menu.bin',OUT/'openiboot-native.bin',cross=CROSS)
    # Reuse the exact successful post-quiesce loader source, changing only its
    # embedded owned native image. No iBoot/exploit/signature patch tool runs.
    subprocess.run([CROSS+'gcc','-nostdlib','-fno-use-linker-plugin','-mcpu=cortex-a8','-marm',
        '-Wl,-Ttext=0x44000000','-Wl,-e,_start','-Wl,--build-id=none',
        str(ROOT/'chainload/iboot6/loader.S'),'-o',str(OUT/'menu-post-loader.elf')],cwd=OUT,check=True)
    subprocess.run([CROSS+'objcopy','-O','binary',str(OUT/'menu-post-loader.elf'),str(OUT/'menu-post-loader.bin')],check=True)
    assert (OUT/'menu-post-loader.bin').read_bytes()[4096:]==(OUT/'openiboot-native.bin').read_bytes()
    subprocess.run([str(KIT/'img3maker'),'-f',str(OUT/'menu-post-loader.bin'),'-o',str(OUT/'OpeniBoot-menu.ibob.img3'),'-t','ibob'],check=True,capture_output=True)
    ibob=(OUT/'OpeniBoot-menu.ibob.img3').read_bytes();assert len(ibob)<0xc0000
    old=json.loads((ROOT/'saved/build/untethered-oib-02/MANIFEST.json').read_text())
    old_size=(ROOT/'saved/build/untethered-oib-02/images/OpeniBoot.ibob.img3').stat().st_size
    total=old['minimal_bytes']-old_size+len(ibob);assert total<0x180000
    record=dict(status='BUILT_NOT_INSTALLED',variants=variants,ibob_size=len(ibob),ibob_sha256=sha(ibob),
        complete_firmware_set_bytes=total,capacity=0x180000,service_sha256=sha(service),
        original_hardware_instructions_preserved=True,protected_android_preserved=True,
        new_exploit_or_signature_patch=False,ios='Pinned to current Kit 7.1.2/11D257 DeviceTree',
        hardware_menu_test_pending=True,ios_boot_pending=True)
    (OUT/'MENU-BUILD.json').write_text(json.dumps(record,indent=2)+'\n')
    check_protected();print('Built real-route menu; not installed. ibob bytes:',len(ibob),'complete set bytes:',total)
    print('Live RAM entry:',hex(variants['live']['entry']))
if __name__=='__main__':main()
