#!/usr/bin/env python3
"""Rebuild an isolated N81AP console from the saved upstream archive; no USB."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT/'tools'))
from native_image import pack_native
HEADLESS = '--headless' in sys.argv[1:]
OUT = ROOT / ('saved/build/phase1-headless' if HEADLESS else 'saved/build/phase1')
SRC = OUT / 'openiBoot-master'
ARCHIVE_SHA = '4119be1b5747c01eb8c97c00765c912ab5ee1636939afe46028f8a8bf68e2b53'

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def replace(file, old, new):
    path = SRC / file
    data = path.read_text()
    if old not in data:
        raise SystemExit('Unexpected source: ' + file)
    path.write_text(data.replace(old, new))

def main():
    archive = ROOT / 'saved/downloads/openiBoot.zip'
    if sha(archive) != ARCHIVE_SHA:
        raise SystemExit('Upstream archive checksum mismatch')
    cross = os.environ.get('CROSS', str(ROOT / 'saved/toolchain/arm-eabi-4.8/bin/arm-eabi-'))
    scons = os.environ.get('SCONS', str(ROOT / 'tools/build-env/bin/scons'))
    subprocess.run([cross + 'gcc', '--version'], check=True)
    OUT.mkdir(parents=True, exist_ok=True)
    if not SRC.exists():
        with zipfile.ZipFile(archive) as z:
            z.extractall(OUT)
        replace('SConstruct', "henv.SConscript(['scons/Doxygen.SConscript'])", '')
        replace('SConstruct', 'docs = henv.Doxygen("Doxyfile")\nAlias("docs", docs)', '')
        replace('SConstruct', "'-Wall', '-Werror', '-O2'", "'-Wall', '-O2'")
        replace('scons/ARMEnvironment.SConscript', "'--nostdlib'", "'-fno-use-linker-plugin'")
        replace('scons/ARMEnvironment.SConscript', 'if not env.has_key("CROSS"):', 'if "CROSS" not in env:')
        replace('scons/ARMEnvironment.SConscript', "if env['ENV'].has_key(\"CROSS\"):", 'if "CROSS" in env["ENV"]:')
        replace('scons/Module.SConscript', "env['MODULES'].has_key(name)", "name in env['MODULES']")
        replace('scons/Module.SConscript', 'print "No such module %s." % name', 'print("No such module %s." % name)')
        (SRC / 'scons/Git.SConscript').write_text("def GetGitCommit():\n\treturn 'phase1'\nExport('GetGitCommit')\n")
        replace('plat-a4/SConscript', 'env = env.Clone()', "env = env.Clone()\nenv.Append(CCFLAGS=['-mcpu=cortex-a8'])\nenv.Append(ASPPFLAGS=['-mcpu=cortex-a8'])\nenv.Append(LINKFLAGS=['-mcpu=cortex-a8'])")
        replace('plat-a4/SConscript', "'h2fmi.c'", "'h2fmi-ramonly.c'")
        (SRC / 'plat-a4/h2fmi-ramonly.c').write_text('''/* No NAND driver in the RAM-only console. */
#include "openiboot.h"
void h2fmi_set_emf(uint32_t e, uint32_t i) { }
uint32_t h2fmi_get_emf(void) { return 0; }
void h2fmi_set_key(uint32_t e, void *k, uint32_t l, uint32_t s, uint32_t o) { }
''')
        replace('plat-a4/cdma.c', '#include "malloc.h"', '')
        if HEADLESS:
            replace('plat-a4/a4.c', '''if(!displaypipe_init()) {
\t\tframebuffer_setup();
\t\tframebuffer_setdisplaytext(TRUE);
\t\tlcd_set_backlight_level(1500);
\t}''', '/* Phase 1 headless: reach USB without initializing the display. */')
        # No IMG3 template is used by iPodTouch4G. Replace the obsolete host
        # xpwn executable with a checked ELF flattener, preserving BSS extent.
        (SRC / 'mk8900image/SConscript').write_text('''Import('*')
import struct
def flatten(target, source, env):
    data = open(str(source[0]), 'rb').read()
    if data[:6] != b'\\x7fELF\\x01\\x01':
        raise ValueError('Expected ELF32 little endian')
    entry, phoff = struct.unpack_from('<II', data, 24)
    size, count = struct.unpack_from('<HH', data, 42)
    headers = [struct.unpack_from('<8I', data, phoff+i*size) for i in range(count)]
    extent = max(p[2]+p[5]-entry for p in headers)
    if entry != 0 or not 0 < extent < 0x1000000:
        raise ValueError('Unexpected N81AP layout')
    image = bytearray(extent)
    for p in headers:
        if not p[4]:
            continue
        offset = p[2]-entry
        if offset < 0 or offset+p[4] > extent or p[1]+p[4] > len(data):
            raise ValueError('Invalid segment')
        image[offset:offset+p[4]] = data[p[1]:p[1]+p[4]]
    open(str(target[0]), 'wb').write(image)
    return 0
env.Append(BUILDERS={'Make8900Image': Builder(action=flatten)})
''')
        (SRC / '.phase1-ready').write_text('1\n')
    if not (SRC / '.phase1-ready').exists():
        raise SystemExit('Incomplete isolated source preparation; inspect build/phase1 first')
    env = dict(os.environ, CROSS=cross)
    env.pop('RAMTEST_AUTOSTART', None)
    subprocess.run([scons, '-Q', 'iPodTouch4G'], cwd=SRC, env=env, check=True)
    shutil.copy2(SRC / 'ipt_4g_openiboot.bin', OUT / 'openiboot.bin')
    pack_native(OUT/'openiboot.bin', OUT/'openiboot-native.bin',
                elf_path=OUT/'native-jump.elf', cross=cross)
    # Firmware is the already audited, offline-patched 4.1 iBSS, not regenerated.
    firmware = ROOT/'saved/build/iBSS.n81ap.go.dfu'
    if sha(firmware) != 'e8b10d73a72fbca026161bd4d4f169992092d8c0eed022540c8072bb5f5ddfcc':
        raise SystemExit('Patched iBSS mismatch')
    import shlex
    flags = shlex.split(subprocess.check_output(
        ['pkg-config', '--cflags', '--libs', 'libirecovery-1.0'], text=True))
    subprocess.run(['cc', '-Wall', '-Wextra', '-Werror', str(HERE/'load.c'),
                    '-o', str(OUT/'load')] + flags, check=True)
    usb = ROOT/'saved/research/libusb-1.0.29'
    if (usb/'libusb/.libs/libusb-1.0.a').exists():
        usbflags = ['-I'+str(usb/'libusb'), str(usb/'libusb/.libs/libusb-1.0.a'),
                    '-framework', 'IOKit', '-framework', 'CoreFoundation', '-framework', 'Security']
    else:
        usbflags = shlex.split(subprocess.check_output(
            ['pkg-config', '--cflags', '--libs', 'libusb-1.0'], text=True))
    subprocess.run(['cc', '-Wall', '-Wextra', '-Werror', str(HERE/'console.c'),
                    '-o', str(OUT/'console')] + usbflags, check=True)
    files = [firmware, OUT/'openiboot.bin', OUT/'openiboot-native.bin', OUT/'load', OUT/'console']
    manifest = {'status': 'built; hardware boot unconfirmed', 'headless': HEADLESS,
                'source_sha256': ARCHIVE_SHA, 'upstream_commit': '866562fdb1cfd019bcd77885c80fbf0af65d5c15',
                'upload_address': '0x41000000', 'openiboot_entry': '0x41001000',
                'linked_entry': '0x00000000', 'ibss_jump_to_thumb': '0x8401496d',
                'files': {str(p.relative_to(ROOT)): {'sha256': sha(p), 'bytes': p.stat().st_size} for p in files}}
    (OUT/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    print('Built:', OUT/'openiboot-native.bin')

if __name__ == '__main__':
    main()
