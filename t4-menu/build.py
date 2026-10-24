#!/usr/bin/env python3
"""Build one c5cee8c RAM-only UI test. Never accesses USB."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT/'tools'))
from native_image import pack_native
SRC = ROOT/'saved/sources/openiBoot-c5cee8c-ui'
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('variant',choices=['T4_DIAG_01','T4_MENU_01'])
args = parser.parse_args()
variant = args.variant
out = ROOT/'saved/build'/variant
out.mkdir(parents=True,exist_ok=True)
commit = subprocess.check_output(['git','-C',str(SRC),'rev-parse','HEAD'],text=True).strip()
assert commit == 'c5cee8cc9e9b13784272550ab0938175cec1cdb5',commit
cross = os.environ.get('CROSS',str(ROOT/'saved/toolchain/arm-eabi-4.8/bin/arm-eabi-'))
scons = os.environ.get('SCONS',str(ROOT/'tools/build-env/bin/scons'))
env = dict(os.environ,CROSS=cross,T4_BUILD=variant)
subprocess.run([scons,'-Q','iPodTouch4G'],cwd=SRC,env=env,check=True)
# Old NOTYPE assembly symbols made the modern linker retain Thumb BL calls
# into ARM code. Require both correct metadata and actual interworking calls.
symbols=subprocess.check_output([cross+'readelf','-sW',str(SRC/'ipt_4g_openiboot')],text=True)
for name in ('ReadControlRegisterConfigData','CleanAndInvalidateCPUDataCache','EnableVFP'):
    assert any(' FUNC ' in line and line.rstrip().endswith(' '+name) for line in symbols.splitlines()),name
disasm=subprocess.check_output([cross+'objdump','-d',str(SRC/'ipt_4g_openiboot')],text=True)
arm_setup=disasm.split('<arm_setup>:',1)[1].split('\n\n',1)[0]
assert 'blx' in arm_setup and 'blx' in arm_setup.split('<CleanAndInvalidateCPUDataCache>',1)[0].splitlines()[-1]
for name in ('ipt_4g_openiboot','ipt_4g_openiboot.bin'):
    shutil.copy2(SRC/name,out/name)
shutil.copy2(SRC/'ipt_4g_openiboot.bin',out/'openiboot.bin')
blob = (out/'openiboot.bin').read_bytes()
for marker in (b'openiboot 0.3',b'c5cee8c',b'iPod Touch 4G',variant.encode()):
    assert marker in blob,marker
assert b'fmi: Initialized NAND memory!' not in blob
pack_native(out/'openiboot.bin', out/'openiboot-native.bin',
            elf_path=out/'native-jump.elf', cross=cross)
flags = shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','libirecovery-1.0'],text=True))
subprocess.run(['cc','-Wall','-Wextra','-Werror',str(ROOT/'phase1/load.c'),'-o',str(out/'load')]+flags,check=True)
usb = ROOT/'saved/research/libusb-1.0.29'
if (usb/'libusb/.libs/libusb-1.0.a').exists():
    usbflags=['-I'+str(usb/'libusb'),str(usb/'libusb/.libs/libusb-1.0.a'),
              '-framework','IOKit','-framework','CoreFoundation','-framework','Security']
else:
    usbflags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','libusb-1.0'],text=True))
subprocess.run(['cc','-Wall','-Wextra','-Werror',str(ROOT/'t4-menu/acm.c'),'-o',str(out/'console')]+usbflags,check=True)
firmware=ROOT/'saved/build/iBSS.n81ap.go.dfu'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert sha(firmware)=='e8b10d73a72fbca026161bd4d4f169992092d8c0eed022540c8072bb5f5ddfcc'
files=[firmware]+[out/n for n in ('openiboot.bin','openiboot-native.bin','load','console')]
manifest={'variant':variant,'upstream_commit':commit,'status':'built; UI hardware test pending',
          'nand_driver_linked':False,'filesystem_config_read':False,
          'files':{str(p.relative_to(ROOT)):{'sha256':sha(p),'bytes':p.stat().st_size} for p in files}}
(out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
print('Built:',out/'openiboot-native.bin')
