#!/usr/bin/env python3
"""Rebuild the proven MENU03 in a NEW host folder without touching the device.

Uses the current project's pinned inputs and installed toolchain. Never rebuilds
in the installed/audited output directory and never runs staging/install tools.
"""
import argparse
import hashlib
import importlib.util
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
VERIFIED = ROOT / 'saved/build/untethered-menu-03'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    target = args.out.expanduser().resolve()
    if target.exists():
        parser.error('Output already exists. Choose a new folder to preserve all successful builds.')
    target.mkdir(parents=True)
    inherited = VERIFIED / 'iboot6-inherited-ram.bin'
    assert sha(inherited) == '2463b37f4bf375fa88f6958e25f07dd9a2b8f697aa9a6efad9a2c8291e116419'
    shutil.copy2(inherited, target / inherited.name)
    for name in ['build-android', 'build-fs', 'test-fs', 'build-menu', 'build-ram-menu', 'test-ram-menu']:
        spec = importlib.util.spec_from_file_location('menu03_rebuild_' + name, HERE / (name + '.py'))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.OUT = target
        if name == 'test-fs':
            module.manifest = json.loads((target / 'FS-BUILD.json').read_text())
            module.sym = module.manifest['symbols']
            module.meta = json.loads((target / 'ANDROID-BUNDLE.json').read_text())
            module.bundle = (target / 'android.bundle').read_bytes()
            module.fs = (target / 'fs.bin').read_bytes()
        module.main()
    filenames = ['android.img3', 'iboot6-fs-service.raw', 'iboot6-ios7-service.raw',
                 'fs.bin', 'menu-boot.bin', 'menu-live.bin', 'openiboot-native.bin',
                 'menu-post-loader.bin', 'OpeniBoot-menu.ibob.img3', 'menu-full-ram-test.bin']
    results = {name: dict(sha256=sha(target / name), matches_verified=sha(target / name) == sha(VERIFIED / name))
               for name in filenames}
    assert all(row['matches_verified'] for row in results.values()), 'Build differs; do not install'
    (target / 'REPRODUCTION.json').write_text(json.dumps(dict(
        status='MENU03_REPRODUCTION_EXACT', files=results, device_writes=False), indent=2) + '\n')
    print('MENU03_REPRODUCTION_EXACT:', target, flush=True)


if __name__ == '__main__':
    main()
