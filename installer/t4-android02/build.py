#!/usr/bin/env python3
"""Package installer02 without altering the known-good installer01/MENU03."""
import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
OUT = ROOT / 'saved/build/T4_ANDROID_INSTALLER_02/T4-Android-Installer-02'


def build_identity():
    """Use the same versioned IOKit install-name as the proven ramdisk helpers."""
    support = OUT / 'source-support'
    support.mkdir(exist_ok=True)
    stubs = {
        'libIOKit.tbd': ('/System/Library/Frameworks/IOKit.framework/Versions/A/IOKit',
                         '_IORegistryEntryFromPath, _IORegistryEntryCreateCFProperty, _IOObjectRelease'),
        'libCoreFoundation.tbd': ('/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation',
                         '_CFStringCreateWithCString, _CFGetTypeID, _CFDataGetTypeID, _CFNumberGetTypeID, _CFDataGetLength, _CFDataGetBytePtr, _CFNumberGetValue, _CFRelease')}
    for name, (install_name, symbols) in stubs.items():
        (support / name).write_text('--- !tapi-tbd-v1\narchs: [ armv7 ]\nplatform: ios\ninstall-name: ' + install_name + '\nexports:\n  - archs: [ armv7 ]\n    symbols: [ ' + symbols + ' ]\n...\n')
    shutil.copy2(ROOT / 'chainload/untethered-oib02/libSystem.tbd', support / 'libSystem.tbd')
    obj = support / 'device-info.o'
    target = OUT / 'payload/device-info'
    temporary = target.with_suffix('.next')
    subprocess.run(['clang', '-target', 'armv7-apple-ios6.0', '-isysroot', '/', '-O2', '-fno-stack-protector',
                    '-Wall', '-Wextra', '-Werror', '-c', str(HERE / 'device-info.c'), '-o', str(obj)], check=True)
    subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/ld-classic', '-arch', 'armv7', '-iphoneos_version_min', '6.0',
                    '-e', '_main', '-L'+str(support), '-lSystem', '-lIOKit', '-lCoreFoundation',
                    '-o', str(temporary), str(obj)], check=True)
    subprocess.run(['codesign', '--force', '--sign', '-', '--identifier', 't4-device-info', '--timestamp=none',
                    str(temporary)], check=True, capture_output=True)
    os.replace(temporary, target)


def refresh_manifest():
    path = OUT / 'manifest.json'
    value = json.loads(path.read_text())
    value['name'] = 'T4_ANDROID_INSTALLER_02'
    value['revision'] = '02.4'
    value['files'] = {str(p.relative_to(OUT)): dict(size=p.stat().st_size, sha256=hashlib.sha256(p.read_bytes()).hexdigest())
                      for p in OUT.rglob('*') if p.is_file() and p != path and '__pycache__' not in p.parts}
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def main():
    if OUT.exists():
        raise SystemExit('Preserve existing package; use a new output for a revision.')
    old = ROOT / 'saved/build/T4_ANDROID_INSTALLER_01/T4-Android-Installer-01'
    shutil.copytree(old, OUT, ignore=shutil.ignore_patterns('__pycache__'))
    for file in HERE.iterdir():
        if file.is_file() and file.name != 'build.py':
            shutil.copy2(file, OUT / file.name)
    build_identity()
    template = ROOT / 'saved/build/T4_ANDROID_INSTALLER_02/template'
    shutil.copy2(template / 'OpeniBoot-menu.ibob.img3', OUT / 'payload/menu-template.img3')
    shutil.copy2(template / 'TEMPLATE.json', OUT / 'payload/menu-template.json')
    fixed = ROOT / 'saved/build/untethered-menu-03/install'
    manifest = json.loads((fixed / 'MANIFEST.json').read_text())
    (OUT / 'payload/base-images').mkdir()
    for name in manifest['minimal_order']:
        shutil.copy2(fixed / 'images' / name, OUT / 'payload/base-images' / name)
    (OUT / 'payload/base-images.json').write_text(json.dumps(dict(order=manifest['minimal_order']), indent=2)+'\n')
    support = OUT / 'generic-build';support.mkdir()
    for name in ['libSystem.tbd', 'libIOKit.tbd', 'libCoreFoundation.tbd']:
        shutil.copy2(ROOT / 'chainload/untethered-oib02' / name, support / name)
    subprocess.run(['clang', '-target', 'armv7-apple-ios6.0', '-isysroot', '/', '-O2', '-fno-stack-protector', '-I'+str(support), '-c', str(HERE/'apply-set-generic.c'), '-o', str(support/'apply.o')], check=True)
    target = OUT / 'payload/apply-set-generic'
    subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/ld-classic', '-arch', 'armv7', '-iphoneos_version_min', '6.0', '-e', '_main', '-L'+str(support), '-lSystem', '-lIOKit', '-lCoreFoundation', '-o', str(target), str(support/'apply.o')], check=True)
    subprocess.run(['codesign', '--force', '--sign', '-', '--timestamp=none', str(target)], check=True, capture_output=True)
    (OUT/'start.sh').chmod(0o755)
    refresh_manifest()
    print(OUT)


if __name__ == '__main__':
    main()
