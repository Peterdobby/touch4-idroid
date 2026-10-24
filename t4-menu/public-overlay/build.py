#!/usr/bin/env python3
"""Append UI to the proven public binary; never rebuild its hardware code."""
import hashlib,json,os,shutil,struct,subprocess,sys,shlex
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'tools'))
from native_image import pack_native
HERE=Path(__file__).resolve().parent
OUT=ROOT/'saved/build/T4_PUBLIC_MENU_01'
live='--live' in sys.argv[1:]
if live: OUT=OUT/'live'
base=0x45000000 if live else 0x44000
OUT.mkdir(parents=True,exist_ok=True)
source=Path('~/Downloads/openiboot_ipodtouch4g_0.3.bin')
original=source.read_bytes()
sha=lambda b:hashlib.sha256(b).hexdigest()
assert sha(original)=='61adbd378093bbd94f935fa16721c7d738e188ceb1c9090dd22c9d79a942ba8c'
cross=os.environ.get('CROSS',str(ROOT/'saved/toolchain/arm-eabi-4.8/bin/arm-eabi-'))
subprocess.run([cross+'gcc','-nostdlib','-fno-use-linker-plugin','-mcpu=cortex-a8',
 '-mthumb','-Os','-fno-builtin','-fno-unwind-tables','-fno-asynchronous-unwind-tables',
 '-Wl,-Ttext='+hex(base),'-Wl,-N','-Wl,--build-id=none','-Wl,-e,t4_public_main',
 '-I'+str(ROOT/'saved/sources/openiBoot-c5cee8c-ui/pcf'),str(HERE/'menu.c'),
 '-o',str(OUT/'menu.elf')],check=True)
elf=(OUT/'menu.elf').read_bytes()
entry,phoff=struct.unpack_from('<II',elf,24)
ps,pn=struct.unpack_from('<HH',elf,42)
headers=[struct.unpack_from('<8I',elf,phoff+i*ps) for i in range(pn)]
loads=[p for p in headers if p[0]==1 and p[5]]
end=max(p[2]+p[5] for p in loads)
assert min(p[2] for p in loads)==base
end=(end+3)&~3
if live:
    payload=bytearray(end-base)
    for p in loads:
        payload[p[2]-base:p[2]-base+p[4]]=elf[p[1]:p[1]+p[4]]
    (OUT/'menu.bin').write_bytes(payload)
    usb=ROOT/'saved/research/libusb-1.0.29'
    if (usb/'libusb/.libs/libusb-1.0.a').exists():
        flags=['-I'+str(usb/'libusb'),str(usb/'libusb/.libs/libusb-1.0.a'),
               '-framework','IOKit','-framework','CoreFoundation','-framework','Security']
    else:
        flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','libusb-1.0'],text=True))
    subprocess.run(['cc','-Wall','-Wextra','-Werror',str(HERE/'live.c'),'-o',str(OUT/'upload')]+flags,check=True)
    (OUT/'live.json').write_text(json.dumps({'entry':entry,'load':base,'sha256':sha(payload),
        'bytes':len(payload),'uploader_sha256':sha((OUT/'upload').read_bytes()),
        'base_sha256':sha(original)},indent=2)+'\n')
    print('Live RAM module:',OUT/'menu.bin','entry',hex(entry))
    sys.exit(0)
image=bytearray(end)
image[:len(original)]=original
for p in loads:
    assert p[2]>=base and p[1]+p[4]<=len(elf)
    image[p[2]:p[2]+p[4]]=elf[p[1]:p[1]+p[4]]
patches={0x30c:(0x3fb20,end),0x310:(0x437a0,end),
         0x39c04:(0x8209,entry),0x3f9e0:(0x18255,0x2269d)}
for off,(old,new) in patches.items():
    assert struct.unpack_from('<I',original,off)[0]==old
    struct.pack_into('<I',image,off,new)
changes=[i for i in range(len(original)) if original[i]!=image[i]]
assert all(any(off<=i<off+4 for off in patches) for i in changes)
# All public display/MIPI, task, framebuffer and USB function instructions stay
# byte-for-byte original. Only two relocation bounds, one GOT hook and the
# already-tested NAND-init callback are changed in the original file extent.
for lo,hi in [(0x364,0x30c00)]:
    assert image[lo:hi]==original[lo:hi]
(OUT/'openiboot.bin').write_bytes(image)
pack_native(OUT/'openiboot.bin', OUT/'openiboot-native.bin',
            elf_path=OUT/'native-jump.elf', cross=cross)
for name in ('load','console'):
    shutil.copy2(ROOT/'saved/build/phase1-published'/name,OUT/name)
files=[ROOT/'saved/build/iBSS.n81ap.go.dfu']+[OUT/n for n in ('openiboot.bin','openiboot-native.bin','load','console')]
m={'variant':'T4_PUBLIC_MENU_01','status':'built; hardware pending',
 'base_sha256':sha(original),'extension_entry':hex(entry),'relocation_end':hex(end),
 'original_extent_changed_bytes':changes,
 'patches':{hex(k):{'old':hex(v[0]),'new':hex(v[1])} for k,v in patches.items()},
 'files':{str(p.relative_to(ROOT)):{'sha256':sha(p.read_bytes()),'bytes':p.stat().st_size} for p in files}}
(OUT/'manifest.json').write_text(json.dumps(m,indent=2)+'\n')
assert sha(source.read_bytes())==m['base_sha256']
print('Original preserved; original hardware/USB instructions unchanged.')
print('Extension entry:',hex(entry),'Original extent changed bytes:',changes)
print('RAM image:',OUT/'openiboot-native.bin')
