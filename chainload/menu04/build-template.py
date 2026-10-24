#!/usr/bin/env python3
"""Build a generic target-iBoot menu template; no device operations."""
import hashlib
import importlib.util
import json
import shutil
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
OLD = ROOT / 'saved/build/untethered-menu-03'
OUT = ROOT / 'saved/build/T4_ANDROID_INSTALLER_02/template'


def module(name):
    spec = importlib.util.spec_from_file_location('menu04_' + name, ROOT / 'chainload/menu03' / (name + '.py'))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    m.OUT = OUT
    return m


def data_offset(image):
    offset = 20
    while offset < len(image):
        tag, size, length = struct.unpack_from('<3I', image, offset)
        if tag == 0x44415441:
            return offset + 12
        offset += size
    raise ValueError('No Image3 DATA')


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    if (OUT / 'TEMPLATE.json').exists():
        raise SystemExit('Preserve the existing built template.')
    for name in ['ANDROID-BUNDLE.json', 'android.bundle', 'iboot6-inherited-ram.bin']:
        shutil.copy2(OLD / name, OUT / name)
    fs = module('build-fs');fs.HERE = HERE;fs.main()
    tests = module('test-fs')
    tests.manifest = json.loads((OUT / 'FS-BUILD.json').read_text())
    tests.sym = tests.manifest['symbols']
    tests.meta = json.loads((OUT / 'ANDROID-BUNDLE.json').read_text())
    tests.bundle = (OUT / 'android.bundle').read_bytes()
    tests.fs = (OUT / 'fs.bin').read_bytes()
    tests.main()
    menu = module('build-menu');menu.HERE = HERE;menu.main()
    meta = json.loads((OUT / 'MENU-BUILD.json').read_text())
    service = meta['variants']['boot']['symbols']['service_blob']
    image = (OUT / 'OpeniBoot-menu.ibob.img3').read_bytes()
    patches = {}
    for field in ['t4_ios_size', 't4_ios_crc']:
        offset = data_offset(image) + 0x2000 + service + tests.sym[field] - 0x5ff00000
        assert struct.unpack_from('<I', image, offset)[0] == 0
        patches[field] = offset
    report = dict(name='T4_MENU04_TARGET_IBOOT_TEMPLATE', sha256=hashlib.sha256(image).hexdigest(),
                  bytes=len(image), patches=patches, mode=4, hardware_test=False,
                  original_android_unchanged=True,
                  target_device_tree='Retained in the host profile; keep the hardware-proven 10B500 firmware dtre')
    (OUT / 'TEMPLATE.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
