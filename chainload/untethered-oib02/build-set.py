#!/usr/bin/env python3
"""Build a pinned complete-set updater on the host. No device connection."""
import hashlib,json,shutil,struct,subprocess,zlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'saved/build/untethered-oib-02'
def main():
    if (OUT/'APPLY-ATTEMPT.json').exists():
        raise SystemExit('An installed-test audit exists. Do not replace its pinned package/helper.')
    m=json.loads((OUT/'MANIFEST.json').read_text())
    assert m['minimal_bytes']<0x180000
    records={r['name']:r for r in m['images']}
    package=bytearray(struct.pack('<4I',0x4f423454,2,7,0))
    for i,name in enumerate(m['minimal_order']):
        b=(OUT/'images'/name).read_bytes();r=records[name]
        assert hashlib.sha256(b).hexdigest()==r['sha256']
        package+=struct.pack('<4I',0 if i==0 else 1,len(b),struct.unpack_from('<I',b,16)[0],zlib.crc32(b))
        package+=b;package+=bytes((-len(b))%4)
    (OUT/'boot-set.pack').write_bytes(package)
    build=OUT/'io-probe'
    build.mkdir(exist_ok=True)
    for stub in (ROOT/'chainload/untethered-oib02').glob('*.tbd'):
        shutil.copyfile(stub,build/stub.name)
    (build/'package.h').write_text('#define PACKAGE_SIZE %du\n#define PACKAGE_CRC 0x%08xu\n'%(len(package),zlib.crc32(package)))
    source=ROOT/'chainload/untethered-oib02/apply-set.c'
    subprocess.run(['clang','-target','armv7-apple-ios6.0','-O2','-fno-stack-protector','-I'+str(build),'-c',str(source),'-o',str(build/'apply-set.o')],check=True,capture_output=True)
    subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/ld-classic','-arch','armv7','-iphoneos_version_min','6.0','-e','_main','-L'+str(build),'-lSystem','-lIOKit','-lCoreFoundation','-o',str(build/'apply-set'),str(build/'apply-set.o')],check=True,capture_output=True)
    subprocess.run(['codesign','--force','--sign','-','--timestamp=none',str(build/'apply-set')],check=True,capture_output=True)
    record=dict(package_size=len(package),package_sha256=hashlib.sha256(package).hexdigest(),package_crc32='%08x'%zlib.crc32(package),helper_sha256=hashlib.sha256((build/'apply-set').read_bytes()).hexdigest(),order=m['minimal_order'],no_exploit_changes=True,device_writes=False)
    (OUT/'BUILD-SET.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record,indent=2))
if __name__=='__main__':main()
