#!/usr/bin/env python3
"""Assemble an owner-specific, standalone host installer from frozen MENU03."""
import os
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
OUT = ROOT / 'saved/build/T4_ANDROID_INSTALLER_01/T4-Android-Installer-01'
GOOD = ROOT / 'saved/releases/T4_UNTETHERED_MENU_03_成功版'


def main():
    if OUT.exists():
        raise SystemExit('Preserve the existing package; choose a new output for revisions.')
    OUT.mkdir(parents=True)
    def copy(src, relative):
        target = OUT / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, target)
    for name in ['start.sh', 'backend.py', 'README.md', 'tests.py', 'device-info.c']:
        copy(HERE / name, name)
    sources = {
        'payload/android.img3': GOOD / 'binaries/android.img3',
        'payload/devicetree-ios7.img3': GOOD / 'binaries/devicetree-ios7.img3',
        'payload/boot-set.pack': GOOD / 'installed-firmware-set/boot-set.pack',
        'payload/apply-set': GOOD / 'installed-firmware-set/io-probe/apply-set',
        'payload/LLB.img3': GOOD / 'installed-firmware-set/images/LLB.n81ap.RELEASE.img3',
        'payload/check-llb': ROOT / 'saved/build/untethered-oib-02/io-probe/check-llb',
        'provenance/FINAL-SUCCESS.json': GOOD / 'evidence/FINAL-SUCCESS.json',
        'provenance/REPRODUCTION.json': GOOD / 'evidence/REPRODUCTION.json',
        'provenance/firmware-manifest.json': GOOD / 'installed-firmware-set/MANIFEST.json',
        'provenance/firmware-build.json': GOOD / 'installed-firmware-set/BUILD-SET.json',
    }
    frozen = json.loads((GOOD / 'SHA256.json').read_text())
    for name, src in sources.items():
        if src.is_relative_to(GOOD):
            entry = frozen[str(src.relative_to(GOOD))]
            if hashlib.sha256(src.read_bytes()).hexdigest() != entry['sha256']:
                raise SystemExit('Frozen successful input changed: ' + str(src))
        copy(src, name)
    debug = OUT / 'source-support'
    debug.mkdir()
    for name in ['apply-set.c', 'check-llb.c', 'libSystem.tbd', 'libIOKit.tbd', 'libCoreFoundation.tbd']:
        shutil.copy2(ROOT / 'chainload/untethered-oib02' / name, debug / name)
    stubs = {
        'libIOKit.tbd': ('/System/Library/Frameworks/IOKit.framework/IOKit',
                         '_IORegistryEntryFromPath, _IORegistryEntryCreateCFProperty, _IOObjectRelease'),
        'libCoreFoundation.tbd': ('/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation',
                         '_CFStringCreateWithCString, _CFGetTypeID, _CFDataGetTypeID, _CFNumberGetTypeID, _CFDataGetLength, _CFDataGetBytePtr, _CFNumberGetValue, _CFRelease')}
    for name, (install_name, symbols) in stubs.items():
        (debug / name).write_text('--- !tapi-tbd-v1\narchs: [ armv7 ]\nplatform: ios\ninstall-name: ' + install_name + '\nexports:\n  - archs: [ armv7 ]\n    symbols: [ ' + symbols + ' ]\n...\n')
    obj = debug / 'device-info.o'
    binary = OUT / 'payload/device-info'
    subprocess.run(['clang', '-target', 'armv7-apple-ios6.0', '-isysroot', '/', '-O2', '-fno-stack-protector', '-Wall', '-Wextra', '-Werror', '-c', str(HERE / 'device-info.c'), '-o', str(obj)], check=True)
    subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/ld-classic', '-arch', 'armv7', '-iphoneos_version_min', '6.0', '-e', '_main', '-L' + str(debug), '-lSystem', '-lIOKit', '-lCoreFoundation', '-o', str(binary), str(obj)], check=True)
    subprocess.run(['codesign', '--force', '--sign', '-', '--timestamp=none', str(binary)], check=True, capture_output=True)
    files = {str(p.relative_to(OUT)): dict(size=p.stat().st_size, sha256=hashlib.sha256(p.read_bytes()).hexdigest())
             for p in sorted(OUT.rglob('*')) if p.is_file()}
    manifest = dict(name='T4_ANDROID_INSTALLER_01', ecid=os.environ.get('T4_ECID', '0x0000000000000000'), model='iPod4,1',
        dra_sha256='b1c9582c1b9862d60fb37ed73b0b55614b75c52e9d7e4480027b1565fbb0fd9e',
        profiles=[dict(id='kit-7.1.2-11D257-MENU03', version='7.1.2', build='11D257',
            kernel_path='/System/Library/Caches/com.apple.kernelcaches/kernelcache',
            kernel_sha256=['d400e375db09e4e3433f29a1c174009c34388e89699c7f031e338acbaf1703e7'])],
        runtime_files=[dict(source='payload/android.img3', destination='/boot/t4/android.img3'),
                       dict(source='payload/devicetree-ios7.img3', destination='/boot/t4/devicetree-ios7.img3')],
        files=files, device_test='Installer integration not yet tested on hardware; underlying MENU03 is hardware confirmed',
        persistent_firmware_install=True, exploit_changes=False, android_data='RAM-only')
    (OUT / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    (OUT / 'start.sh').chmod(0o755)
    print(OUT)


if __name__ == '__main__':
    main()
