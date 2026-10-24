#!/usr/bin/env python3
"""Prepare the user's published binary, with only its NAND init callback skipped.

The source file is never modified. No USB operations occur in this script.
The fixed offsets apply ONLY to the SHA256 pinned below.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT/'tools'))
from native_image import pack_native
OUT = ROOT/'saved/build/phase1-published'
source = Path(sys.argv[1] if len(sys.argv)>1 else '~/Downloads/openiboot_ipodtouch4g_0.3.bin')
original = source.read_bytes()
sha = lambda b: hashlib.sha256(b).hexdigest()
expected = '61adbd378093bbd94f935fa16721c7d738e188ceb1c9090dd22c9d79a942ba8c'
if sha(original) != expected:
    raise SystemExit('Unknown binary: fixed-offset patch refused')
u32 = lambda n: struct.unpack_from('<I',original,n)[0]
# init_modules @0x3ec loads .init_modules through GOT @0x39c0c.
# The table is [NULL, audiohw_init, pmu_init, h2fmi_init, accel_init,
# acm_start, NULL]. h2fmi_init @0x18254 is the source-matched NAND init.
assert u32(0x39c0c) == 0x3f9d4
assert [u32(i) for i in range(0x3f9d4,0x3f9f0,4)] == [
    0,0x2269d,0x13369,0x18255,0x227bd,0x22841,0]
assert original[0x18254:0x18264] == bytes.fromhex('f0 b5 5f 46 56 46 4d 46 44 46 f0 b4 8f 4b c3 b0')
# Existing Thumb no-op function: BX LR. Keep a non-NULL table entry so
# the later accel/ACM callbacks still run. A zero entry would stop traversal.
assert original[0x2269c:0x226a0] == bytes.fromhex('70 47 00 00')
patched = bytearray(original)
struct.pack_into('<I',patched,0x3f9e0,0x2269d)
changed = [i for i,(a,b) in enumerate(zip(original,patched)) if a!=b]
assert changed and all(0x3f9e0<=i<0x3f9e4 for i in changed)
OUT.mkdir(parents=True,exist_ok=True)
(OUT/'openiboot-original.bin').write_bytes(original)
(OUT/'openiboot.bin').write_bytes(patched)
cross = os.environ.get('CROSS',str(ROOT/'saved/toolchain/arm-eabi-4.8/bin/arm-eabi-'))
pack_native(OUT/'openiboot.bin', OUT/'openiboot-native.bin',
            elf_path=OUT/'native-jump.elf', cross=cross)
for name in ('load','console'):
    shutil.copy2(ROOT/'saved/build/phase1'/name,OUT/name)
files=[ROOT/'saved/build/iBSS.n81ap.go.dfu']+[OUT/n for n in (
    'openiboot-original.bin','openiboot.bin','openiboot-native.bin','load','console')]
manifest={'status':'prepared; hardware unconfirmed','published_source':str(source),
          'published_sha256':expected,'embedded_version':'0.3 c5cee8c for iPod Touch 4G',
          'patch':{'description':'skip automatic h2fmi_init; preserve remaining init callbacks',
                   'offset':'0x3f9e0','old_pointer':'0x18255','new_pointer':'0x2269d',
                   'changed_byte_offsets':changed},
          'files':{str(p.relative_to(ROOT)):{'sha256':sha(p.read_bytes()),'bytes':p.stat().st_size} for p in files}}
(OUT/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
assert sha(source.read_bytes()) == expected
print('Published binary prepared; original unchanged. Changed byte offsets:',changed)
print('RAM test image:',OUT/'openiboot-native.bin')
