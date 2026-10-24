#!/usr/bin/env python3
"""Offline validation of the actual runtime patch table and HUD return."""
from pathlib import Path
import hashlib,json,re,struct,zlib

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'saved/build/T4_ANDROID_TOUCH_03'
BASE=ROOT/'saved/build/T4_ANDROID_TOUCH_01'
manifest=json.loads((OUT/'manifest.json').read_text())
for n,e in manifest['files'].items():
 b=(OUT/n).read_bytes()
 assert len(b)==e['bytes'] and hashlib.sha256(b).hexdigest()==e['sha256'],n
assert (OUT/'zImage').read_bytes()==(BASE/'zImage').read_bytes()
original=(OUT/'Image.expected').read_bytes()
patched=bytearray(original)
header=(OUT/'core-patches.h').read_text()
rows=[]
for line in header.splitlines():
 if line.startswith('{'):
  rows.append([int(n.rstrip('u'),0) for n in line.strip('{},').split(',')])
assert rows==manifest['kernel_runtime_patches']
assert len(rows)==int(re.search(r'CORE_PATCH_COUNT (\d+)u',header)[1])
for address,old0,old1,new0,new1 in rows:
 offset=address-0x8000
 assert struct.unpack_from('<2I',patched,offset)==(old0,old1)
 struct.pack_into('<2I',patched,offset,new0,new1)
assert patched==(OUT/'Image.instrumented').read_bytes()
assert zlib.crc32(patched)==int(re.search(r'IMAGE_INSTRUMENTED_CRC (\d+)u',header)[1])
va=int(manifest['hud_disabled']['virtual_address'],16)
offset=va-0xc0008000
baseline=(BASE/'Image.instrumented').read_bytes()
assert len(patched)==len(baseline)
assert all(a==b or offset<=i<offset+4 for i,(a,b) in enumerate(zip(baseline,patched)))
assert struct.unpack_from('<I',patched,offset)[0]==0xe12fff1e

# Execute the emitted ARM HUD entry, with no framebuffer or stack mapping.
# It must return immediately, preserve its input, and perform no memory write.
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_MEM_WRITE
from unicorn.arm_const import UC_ARM_REG_LR,UC_ARM_REG_PC,UC_ARM_REG_R0
uc=Uc(UC_ARCH_ARM,UC_MODE_ARM)
uc.mem_map(0xc0008000,(len(patched)+4095)&~4095)
uc.mem_write(0xc0008000,bytes(patched))
uc.mem_map(0x08000000,4096)
uc.reg_write(UC_ARM_REG_LR,0x08000000)
uc.reg_write(UC_ARM_REG_R0,0xdead0000)
writes=[]
uc.hook_add(UC_HOOK_MEM_WRITE,lambda _u,_a,p,n,v,_d:writes.append((p,n,v)))
uc.emu_start(va,0x08000000,count=4)
assert uc.reg_read(UC_ARM_REG_PC)==0x08000000
assert uc.reg_read(UC_ARM_REG_R0)==0xdead0000 and not writes
print('TOUCH03_BUNDLE_PASS: manifest, exact uploaded kernel, runtime patch preconditions/CRC, HUD returns without framebuffer access')
