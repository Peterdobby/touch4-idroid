#!/usr/bin/env python3
"""Offline CPU-contract experiment; no exploit build, firmware patch or USB."""
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
SRC = Path(__file__).resolve().parent
OUT = ROOT/'saved/build/chainload-iboot6'
CROSS = str(ROOT/'saved/toolchain/arm-eabi-4.8/bin/arm-eabi-')
sys.path.insert(0, str(ROOT/'chainload'))
from build import check_protected
sys.path.insert(0, str(ROOT/'tools'))
from native_image import pack_native

def sha(data):
    return hashlib.sha256(data).hexdigest()

def run(args):
    return subprocess.check_output([str(x) for x in args], cwd=OUT)

def main():
    check_protected()
    OUT.mkdir(parents=True, exist_ok=True)
    # Existing decrypted public firmware; no sibling build/exploit code is run.
    source = ROOT.parent/'touch4-idroid-untethered/build/untethered/T4_OIB_LOADER_01/iBoot.n81ap-10B500.raw'
    iboot = source.read_bytes()
    assert sha(iboot) == 'd167d3303354296121da953ba8df62755f902932fccb8fdb29232bba1d057bda'
    # Only the audited CPU routines; every other byte in the sparse blob is zero.
    spans = [(0x410,0x438),(0x1e61c,0x1e64c),(0x1eb80,0x1ebb0)]
    cpu = bytearray(0x1ebb0)
    for lo,hi in spans:
        cpu[lo:hi] = iboot[lo:hi]
    (OUT/'iboot6-cpu-only.bin').write_bytes(cpu)
    native = (ROOT/'saved/build/phase1-published/openiboot-native.bin').read_bytes()
    (OUT/'openiboot-native.bin').write_bytes(native)
    symbols = {}
    for name, src, address in [('t4-oib-iboot6-loader','loader.S',0x44000000),
                               ('iboot6-ram-stage','stage.S',0x41001000)]:
        run([CROSS+'as','-mcpu=cortex-a8','-o',name+'.o',SRC/src])
        run([CROSS+'ld','--build-id=none','-Ttext='+hex(address),'-e','_start','-o',name+'.elf',name+'.o'])
        run([CROSS+'objcopy','-O','binary',name+'.elf',name+'.bin'])
        text = run([CROSS+'nm','-n',name+'.elf']).decode()
        symbols[name] = {p[2]:int(p[0],16) for line in text.splitlines() if len(p:=line.split())==3}
        (OUT/(name+'.disasm')).write_bytes(run([CROSS+'objdump','-d',name+'.elf']))
    loader = (OUT/'t4-oib-iboot6-loader.bin').read_bytes()
    assert loader[0x1000:] == native
    assert (symbols['t4-oib-iboot6-loader']['bridge'] | 1) == 0x44000201
    wrapped = OUT/'iboot6-ram-test-native.bin'
    pack_native(OUT/'iboot6-ram-stage.bin', wrapped, cross=CROSS)
    write = lambda name,obj: (OUT/name).write_text(json.dumps(obj,indent=2)+'\n')
    write('manifest.json',dict(name='T4_IBOOT6_RAM_01',
        scope='Extracted iBoot6 CPU instructions + post-quiesce loader; NOT full live iBoot6 or DRV6 boot.',
        iboot_source=str(source),iboot_sha256=sha(iboot),cpu_spans=spans,
        original_native_sha256=sha(native),ram_wrapper_target_offset=0x18,
        ram_wrapper_target=0x44000201,raw_payload_unchanged=True,
        symbols=symbols,hardware_success=False,
        files={p.name:sha(p.read_bytes()) for p in OUT.iterdir() if p.suffix in ('.bin','.elf')},
        sources={p.name:sha(p.read_bytes()) for p in SRC.iterdir() if p.is_file()}))
    check_protected()
    print('Built:',wrapped)
    print('Original native input and protected Android/phase1 files unchanged.')
    print('RAM copy changes only wrapper literal at +0x18; raw OpeniBoot payload is identical.')

if __name__=='__main__':
    main()
