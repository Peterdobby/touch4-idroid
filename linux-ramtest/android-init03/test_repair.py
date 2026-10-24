#!/usr/bin/env python3
"""Check restored INIT01 hooks against the exact INIT02 kernel; offline only."""
import hashlib,json,struct,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'saved/build/T4_ANDROID_INIT_03';PREV=ROOT/'saved/build/T4_ANDROID_INIT_02'
m=json.loads((OUT/'manifest.json').read_text());original=(OUT/'Image.expected').read_bytes();im=bytearray(original)
for n,d in m['unchanged_inputs'].items():assert hashlib.sha256((OUT/n).read_bytes()).hexdigest()==d==hashlib.sha256((PREV/n).read_bytes()).hexdigest()
for a,b,c,d,e in m['kernel_runtime_patches']:
 assert struct.unpack_from('<2I',original,a-0x8000)==(b,c)
 struct.pack_into('<2I',im,a-0x8000,d,e)
assert im==(OUT/'Image.instrumented').read_bytes()
h=(OUT/'handoff.bin').read_bytes();u32=lambda b,p:struct.unpack_from('<I',b,p)[0]
nm=subprocess.check_output([str(ROOT/'saved/toolchain/arm-eabi-4.8/bin/arm-eabi-nm'),str(OUT/'handoff.elf')],text=True)
s={l[2]:int(l[0],16)-0x44000000 for line in nm.splitlines() if len(l:=line.split())==3}
for n in ['header_probe','enabled_probe','decompress_probe','decompressed_probe','putstr_probe','kernel_probe','core_probe','processor_probe','atags_return','pages_return','switched_probe','early_c_probe','printk_probe','native_console_entry','native_console_ready']:
 p=s[n];assert [u32(h,p+i) for i in [0,4,8,24,28,32]]==[0xe92d5fff,0xe10f0000,0xe92d0003,0xe8bd0003,0xe128f000,0xe8bd5fff],n
def literal(p):
 ins=u32(h,p);assert ins&0xff7f0000==0xe51f0000,hex(ins)
 return u32(h,p+8+((ins&0xfff) if ins&0x800000 else -(ins&0xfff)))
a=m['core_addresses']
assert literal(s['switched_entry'])==0x44010000
assert literal(s['switched_probe']+36)==a['CORE_SWITCHED']
assert literal(s['switched_probe']+40)==a['CORE_SWITCHED_DATA']
assert literal(s['switched_probe']+48)==a['CORE_SWITCHED_RESUME']
assert literal(s['early_c_probe']+40)==a['CORE_DEBUG_OBJECTS']
assert literal(s['debug_objects_return']+4)==a['CORE_DEBUG_RETURN']
assert literal(s['debug_objects_return']+8)==a['CORE_DEBUG_RESUME']
assert literal(s['printk_probe']+40)==a['CORE_ARCH_RETURN']
assert literal(s['printk_probe']+44)==a['CORE_SETUP_ARCH']
assert literal(s['native_console_entry']+52)==a['CORE_CONSOLE_INIT']
assert literal(s['native_console_ready']+36)==a['CORE_ARCH_R7_LITERAL']
assert literal(s['native_console_ready']+44)==a['CORE_ARCH_SANITY_RETURN']
assert literal(s['native_console_ready']+48)==a['CORE_SANITY_CHECK']
# Same replay/mapping path as INIT01; confirm it wasn't replaced by new logic.
assert (ROOT/'linux-ramtest/android-init03/diag_maps.h').read_bytes()==(ROOT/'linux-ramtest/android-init01/diag_maps.h').read_bytes()
assert (OUT/'zImage').read_bytes()==(PREV/'zImage').read_bytes()
assert len(h)<=0x8000
# Last patch prevents a second registration/self-link of the same printk console.
a,b,c,d,e=m['kernel_runtime_patches'][-1]
assert b>>24==0xeb and d==0xe1a00000 and c==e==0xe8bd4008
for p,d in m['protected_baselines'].items():assert hashlib.sha256(Path(p).read_bytes()).hexdigest()==d
print('REPAIR_LAYOUT_PASSED: exact INIT02 kernel/ramdisk; restored 16-24; dynamically validated calls; console registered once; prior builds preserved')
