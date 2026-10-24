#!/usr/bin/env python3
"""Prepare live-context loader only. Never start/patch iBoot or an exploit."""
import hashlib,json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
SRC=Path(__file__).resolve().parent
OUT=ROOT/'saved/build/chainload-live-iboot6'
CROSS=str(ROOT/'saved/toolchain/arm-eabi-4.8/bin/arm-eabi-')
sys.path.insert(0,str(ROOT/'chainload'))
from build import check_protected
def sha(b):return hashlib.sha256(b).hexdigest()
def main():
    check_protected();OUT.mkdir(parents=True,exist_ok=True)
    iboot=(ROOT.parent/'touch4-idroid-untethered/build/untethered/T4_OIB_LOADER_01/iBoot.n81ap-10B500.raw').read_bytes()
    assert sha(iboot)=='d167d3303354296121da953ba8df62755f902932fccb8fdb29232bba1d057bda'
    native=(ROOT/'saved/build/phase1-published/openiboot-native.bin').read_bytes()
    (OUT/'openiboot-native.bin').write_bytes(native)
    (OUT/'jump-prefix.bin').write_bytes(iboot[0x1cef0:0x1cf00])
    (OUT/'cpu-prefix.bin').write_bytes(iboot[0x1eb80:0x1eb90])
    post=(ROOT/'chainload/iboot6/loader.S').read_text()
    prefix=(SRC/'live-prefix.S').read_text()
    assert post.count('_start:\n')==1
    combined=post.replace('_start:\n','_start:\n'+prefix+'\n.global post_quiesce\npost_quiesce:\n')
    (OUT/'combined.S').write_text(combined)
    def run(args):return subprocess.check_output([str(x) for x in args],cwd=OUT)
    run([CROSS+'as','-mcpu=cortex-a8','-o','loader.o','combined.S'])
    run([CROSS+'ld','--build-id=none','-Ttext=0x44000000','-e','_start','-o','t4-oib-live-iboot6.elf','loader.o'])
    run([CROSS+'objcopy','-O','binary','t4-oib-live-iboot6.elf','t4-oib-live-iboot6.bin'])
    image=(OUT/'t4-oib-live-iboot6.bin').read_bytes()
    assert image[0x1000:]==native
    (OUT/'loader.disasm').write_bytes(run([CROSS+'objdump','-d','t4-oib-live-iboot6.elf']))
    (OUT/'jump-to.disasm').write_bytes(run([CROSS+'objdump','-D','-b','binary','-m','arm','-M','force-thumb',
        '--adjust-vma=0x5ff00000','--start-address=0x5ff1cef0','--stop-address=0x5ff1cf2c',
        ROOT.parent/'touch4-idroid-untethered/build/untethered/T4_OIB_LOADER_01/iBoot.n81ap-10B500.raw']))
    result=dict(name='T4_LIVE_IBOOT6_01',entry='0x44000000 ARM',native_jump='0x5ff1cef1 Thumb',
        post_quiesce='0x44000100 ARM',hardware_success=False,
        note='Needs a real live controlled iBoot-1537.9.55 session. Do not boot using phase1 directly.',
        original_native_sha256=sha(native),files={p.name:sha(p.read_bytes()) for p in OUT.iterdir() if p.suffix in ('.bin','.elf')},
        sources={str(p.relative_to(ROOT)):sha(p.read_bytes()) for p in [SRC/'build.py',SRC/'live-prefix.S',ROOT/'chainload/iboot6/loader.S']})
    (OUT/'manifest.json').write_text(json.dumps(result,indent=2)+'\n')
    check_protected()
    print('Built:',OUT/'t4-oib-live-iboot6.bin')
    print('LIVE iBoot6 session required; not DFU/iBSS compatible; no device operation performed.')
if __name__=='__main__':main()
