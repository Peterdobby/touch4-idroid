#!/usr/bin/env python3
"""Host-only immutable TOUCH03 bundle. Does not connect or install anything."""
import hashlib,json,os,struct,subprocess,sys,zlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
OUT=ROOT/'saved/build/untethered-menu-03'
sys.path.insert(0,str(ROOT/'chainload'))
from build import check_protected
sys.path.insert(0,str(ROOT/'tools'))
from native_image import pack_native
CROSS=str(ROOT/'saved/toolchain/arm-eabi-4.8/bin/arm-eabi-')
KIT=Path(os.environ.get('T4_KIT_DIR', str(Path.home() / 'Legacy-iOS-Kit')))
def sha(b):return hashlib.sha256(b).hexdigest()
def main():
    check_protected();OUT.mkdir(exist_ok=True)
    if (OUT/'STAGED.json').exists():raise SystemExit('Preserve the staged bundle; use a new build directory for revisions.')
    elf=OUT/'android-entry.elf'
    subprocess.run([CROSS+'gcc','-nostdlib','-fno-use-linker-plugin','-mcpu=cortex-a8','-mthumb',
      '-Os','-fno-builtin','-fno-unwind-tables','-fno-asynchronous-unwind-tables',
      '-Wl,-Ttext=0x44000','-Wl,-N','-Wl,--build-id=none','-Wl,-e,t4_android_entry',
      str(HERE/'android-entry.c'),'-o',str(elf)],check=True)
    e=elf.read_bytes();entry,phoff=struct.unpack_from('<II',e,24)
    ps,pn=struct.unpack_from('<HH',e,42)
    loads=[p for i in range(pn) if (p:=struct.unpack_from('<8I',e,phoff+i*ps))[0]==1 and p[5]]
    assert min(p[2] for p in loads)==0x44000
    end=(max(p[2]+p[5] for p in loads)+3)&~3
    old=(ROOT/'saved/build/phase1-published/openiboot.bin').read_bytes()
    raw=bytearray(end);raw[:len(old)]=old
    for p in loads:raw[p[2]:p[2]+p[4]]=e[p[1]:p[1]+p[4]]
    patches={0x30c:(0x3fb20,end),0x310:(0x437a0,end),0x39c04:(0x8209,entry)}
    for off,(before,after) in patches.items():
        assert struct.unpack_from('<I',old,off)[0]==before
        struct.pack_into('<I',raw,off,after)
    assert raw[0x364:0x30c00]==old[0x364:0x30c00]
    assert raw[0x2e3c:0x3030]==old[0x2e3c:0x3030]
    (OUT/'android-openiboot.bin').write_bytes(raw)
    pack_native(OUT/'android-openiboot.bin',OUT/'android-openiboot-native.bin',cross=CROSS)
    inputs=[('kernel',ROOT/'saved/build/T4_ANDROID_TOUCH_03/zImage',0x42000000),
      ('initrd',ROOT/'saved/build/T4_ANDROID_TOUCH_03/initramfs.cpio.gz',0x44800000),
      ('handoff',ROOT/'saved/build/T4_ANDROID_TOUCH_03/handoff.bin',0x44000000),
      ('openiboot',OUT/'android-openiboot-native.bin',0x41000000)]
    b=bytearray(4096); records=[]
    for name,path,dest in inputs:
        data=path.read_bytes();off=len(b)
        records.append(dict(name=name,path=str(path),offset=off,size=len(data),destination=dest,
                            crc32=zlib.crc32(data),sha256=sha(data)))
        b+=data;b+=bytes((-len(b))%4096)
    assert len(b)<0x03000000 # iBoot decoded buffer 44000000..47000000
    struct.pack_into('<4I',b,0,0x334d3454,3,len(records),len(b)) # T4M3
    for i,r in enumerate(records):
        struct.pack_into('<4I',b,16+i*16,*[r[k] for k in ['offset','size','destination','crc32']])
    struct.pack_into('<I',b,0xffc,zlib.crc32(b[:0xffc]))
    for r in records:
        assert b[r['offset']:r['offset']+r['size']]==Path(r['path']).read_bytes()
    (OUT/'android.bundle').write_bytes(b)
    subprocess.run([str(KIT/'bin/macos/img3maker'),'-f',str(OUT/'android.bundle'),
                    '-o',str(OUT/'android.img3'),'-t','krnl'],check=True,capture_output=True)
    image=(OUT/'android.img3').read_bytes();assert len(image)<0x03000000
    assert struct.unpack_from('<I',image,16)[0]==0x6b726e6c
    off=20; payload=None
    while off<len(image):
        tag,size,length=struct.unpack_from('<3I',image,off)
        assert size>=12 and length<=size-12
        if tag==0x44415441:payload=image[off+12:off+12+length]
        off+=size
    assert off==len(image) and payload==b
    m=dict(name='T4_UNTETHERED_MENU_03_ANDROID_BUNDLE',status='HOST_BUILT_NOT_BOOTED',
      boot_file='/boot/t4/android.img3',iboot_mounted_path='/boot/boot/t4/android.img3',
      bundle_bytes=len(b),bundle_sha256=sha(b),image_bytes=len(image),image_sha256=sha(image),
      records=records,entry=entry,protected_baseline_preserved=True,
      nand_driver_changes=False,exploit_changes=False,signature_check_changes=False,
      desktop_touch_keys_adb='Unmodified, user-confirmed TOUCH03 payloads; this loading route remains untested')
    (OUT/'ANDROID-BUNDLE.json').write_text(json.dumps(m,indent=2)+'\n')
    check_protected();print(json.dumps({k:m[k] for k in ['status','image_bytes','image_sha256','boot_file']},indent=2))
if __name__=='__main__':main()
