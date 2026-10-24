#!/usr/bin/env python3
"""TOUCH03: preserve the booted kernel and remove its diagnostic HUD in RAM.

Reuse TOUCH02's verified archive/handoff builder. The only extra kernel runtime
change is an entry return in t4_input_hud, guarded by its exact original words.
No kernel rebuild, LCD/MMIO initialization change, or USB/device access.
"""
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import struct
import zlib

ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
OUT=ROOT/'saved/build/T4_ANDROID_TOUCH_03'

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
 spec=importlib.util.spec_from_file_location('touch02_bundle',HERE.parent/'android-touch02/build.py')
 builder=importlib.util.module_from_spec(spec);spec.loader.exec_module(builder)
 # Retain the exact, user-confirmed Home/volume/Power layout.
 source_layout=HERE.parent/'android-touch02/t4-ram-keys.kl'
 builder.HERE=HERE;builder.NAME='T4_ANDROID_TOUCH_03'
 builder.require((HERE/'t4-ram-keys.kl').read_bytes()==source_layout.read_bytes(),'Button layout drift')
 # The uploaded/compressed kernel and symbol addresses remain byte-exact.
 # These two files explicitly contain the additional runtime HUD patch.
 builder.KERNEL_FILES=[n for n in builder.KERNEL_FILES if n not in ['Image.instrumented','core-patches.h']]
 baseline02=ROOT/'saved/build/T4_ANDROID_TOUCH_02'
 protected={str(p):sha(p) for p in baseline02.rglob('*') if p.is_file()}
 compile_original=builder.compile_handoff
 evidence={}
 def compile_handoff(out,variant,stem):
  if variant==builder.NAME and not evidence:
   symbols=builder.symbols(out/'vmlinux');va=symbols['t4_input_hud']
   builder.require(va==0xc0033640,'HUD symbol moved; inspect before patching')
   image=bytearray((out/'Image.instrumented').read_bytes());offset=va-0xc0008000
   original=(out/'Image.expected').read_bytes()
   words=struct.unpack_from('<2I',image,offset)
   builder.require(image[offset:offset+8]==original[offset:offset+8],'HUD already changed')
   builder.require(words[0]&0xffff0000==0xe92d0000,'Expected ARM function prologue')
   row=[va-0xc0000000,*words,0xe12fff1e,words[1]]
   struct.pack_into('<I',image,offset,0xe12fff1e) # bx lr; no framebuffer write.
   before=(out/'Image.instrumented').read_bytes()
   builder.require(all(a==b or offset<=i<offset+4 for i,(a,b) in enumerate(zip(before,image))),
                   'Unexpected runtime Image delta')
   (out/'Image.instrumented').write_bytes(image)
   header=(out/'core-patches.h').read_text()
   builder.require(header.count('};\n')==1,'Unexpected runtime patch table')
   header=header.replace('};\n','{'+','.join(hex(v)+'u' for v in row)+'},\n};\n',1)
   header,count=re.subn(r'(#define CORE_PATCH_COUNT )(\d+)(u)',
                       lambda m:m[1]+str(int(m[2])+1)+m[3],header)
   builder.require(count==1,'Missing runtime patch count')
   header,count=re.subn(r'(#define IMAGE_INSTRUMENTED_CRC )\d+u',
                       lambda m:m[1]+str(zlib.crc32(image))+'u',header)
   builder.require(count==1,'Missing runtime Image CRC')
   (out/'core-patches.h').write_text(header)
   evidence.update(symbol='t4_input_hud',virtual_address=hex(va),
                   original_words=[hex(w) for w in words],replacement='ARM bx lr',
                   runtime_patch=row,Image_bytes_changed=4,
                   scope='Skip diagnostic pixel overlay only; no LCD/USB/input/clock code changes')
  return compile_original(out,variant,stem)
 builder.compile_handoff=compile_handoff
 builder.main(OUT)
 for p,digest in protected.items():builder.require(sha(Path(p))==digest,'TOUCH02 baseline changed: '+p)
 builder.require(bool(evidence),'HUD patch was not generated')
 (OUT/'hud-disabled.json').write_text(json.dumps(evidence,indent=2)+'\n')
 manifest=json.loads((OUT/'manifest.json').read_text())
 manifest['kernel_runtime_patches'].append(evidence['runtime_patch'])
 manifest['hud_disabled']=evidence
 manifest['repair']='N81 active-low attention; checked N1 frame replay/recovery; retained power/keys/ADB; diagnostic HUD removed by guarded RAM entry return'
 manifest['status']='built offline; final fresh-boot hardware verification pending'
 manifest['success']='Record current physical touch/Home results separately; offline build is not a sustained hardware result'
 manifest['files']['hud-disabled.json']=builder.file_info(OUT/'hud-disabled.json')
 manifest['build_source_sha256'][str(Path(__file__).relative_to(ROOT))]=sha(Path(__file__))
 manifest['kernel_source_preserved']=True
 (OUT/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
 print('TOUCH03: inherited kernel unchanged; diagnostic HUD entry disabled in RAM')

if __name__=='__main__':main()
