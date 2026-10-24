#!/usr/bin/env python3
"""Install the hardware-tested MENU03 boot image group from an existing SSH RD.

This performs persistent boot-firmware writes using the successful OIB02 Apple
API transaction. It does not erase/repartition, replace OS files, change NVRAM,
or build/trigger an exploit. Requires the current pinned iOS 7.1.2 profile.
"""
import argparse
import datetime
import hashlib
import importlib.util
import json
import plistlib
import shlex
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'saved/build/untethered-menu-03'
INSTALL = OUT / 'install'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def load(name):
    return json.loads((OUT / name).read_text())


def preflight(port):
    if (INSTALL / 'APPLY-ATTEMPT.json').exists():
        raise SystemExit('Preserve the existing audited attempt; do not retry blindly.')
    menu = load('MENU-BUILD.json')
    native = load('FULL-MENU-RAM-SUCCESS.json')
    android = load('FULL-MENU-ANDROID-SUCCESS.json')
    ios = load('IOS7-LOCAL-BOOT-SUCCESS.json')
    ui = load('MENU-USER-UI-CONFIRMED.json')
    assert native['status'] == 'PRODUCTION_MENU_NATIVE_RAM_BOOT_CONFIRMED'
    assert android['status'] == 'PRODUCTION_MENU_ANDROID_LOCAL_FILE_BOOT_CONFIRMED'
    assert ios['status'] == 'IOS_7_1_2_LOCAL_MENU_BOOT_CONFIRMED'
    assert ui['confirmed'] and len(ui['checks']) == 3
    assert native['menu_build']['ibob_sha256'] == android['ibob_sha256'] == ios['menu_build']['ibob_sha256'] == menu['ibob_sha256']
    assert sha((INSTALL / 'images/OpeniBoot.ibob.img3').read_bytes()) == menu['ibob_sha256']
    assert menu['complete_firmware_set_bytes'] < menu['capacity']
    tests = load('install/OFFLINE-TESTS.json')['results']
    assert len(tests) == 4 and all(row['pass_test'] for row in tests)
    spec = importlib.util.spec_from_file_location('menu03_protected', ROOT / 'chainload/build.py')
    baseline = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(baseline)
    baseline.check_protected()

    control = (OUT / '.ssh-control-path').read_text().strip()
    base = ['ssh', '-T', '-o', 'ControlPath=' + control, '-o', 'BatchMode=yes',
            '-o', 'ConnectTimeout=5', '-p', str(port), 'root@127.0.0.1']

    def remote(command):
        result = subprocess.run(base + [command], capture_output=True, timeout=50)
        if result.returncode:
            raise RuntimeError(result.stderr.decode(errors='replace'))
        return result.stdout

    mounts = remote('/sbin/mount')
    assert b'/dev/md0 on / ' in mounts and b'/dev/disk0s1s1 on /mnt1 ' in mounts
    assert remote('/mnt1/usr/sbin/sysctl -n hw.machine').strip() == b'iPod4,1'
    version = plistlib.loads(remote('/bin/cat /mnt1/System/Library/CoreServices/SystemVersion.plist'))
    assert (version['ProductVersion'], version['ProductBuildVersion']) == ('7.1.2', '11D257')
    kernel_sha = sha(remote('/bin/cat /mnt1/System/Library/Caches/com.apple.kernelcaches/kernelcache'))
    assert kernel_sha == ios['existing_kernel_sha256'], 'Installed kernel changed; do not install this profile'
    files = []
    for metadata in [load('STAGED.json'), load('IOS-STAGED.json')]:
        path = metadata['destination']
        data = remote('/bin/cat ' + shlex.quote(path))
        expected = metadata.get('sha256', metadata.get('image_sha256'))
        assert len(data) == metadata['bytes'] and sha(data) == expected
        files.append(dict(path=path, bytes=len(data), sha256=expected))
    record = dict(time=datetime.datetime.now().isoformat(),
                  status='EXACT_MENU_HARDWARE_EVIDENCE_AND_INSTALLED_FILES_VERIFIED',
                  ibob_sha256=menu['ibob_sha256'], installed_kernel_sha256=kernel_sha,
                  ios_version='7.1.2/11D257', runtime_files=files,
                  firmware_writes=False)
    (INSTALL / 'PREFLIGHT.json').write_text(json.dumps(record, indent=2) + '\n')
    print('Exact menu, both operating-system routes, and original installed files verified.', flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true', required=True)
    parser.add_argument('--port', type=int, default=6414)
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error('Invalid port')
    preflight(args.port)
    # Reuse the complete previously successful LLB-first transaction unchanged.
    # Its target directory is rebound here; the successful OIB02 remains intact.
    spec = importlib.util.spec_from_file_location('menu03_fullset_apply', ROOT / 'chainload/untethered-oib02/apply.py')
    backend = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(backend)
    backend.OUT = INSTALL
    backend.main()
    audit = INSTALL / 'APPLY-ATTEMPT.json'
    record = json.loads(audit.read_text())
    record['authorization'] = 'Owner requested untethered iOS/Android/Console menu and confirmed all three physical menu operations.'
    record['hardware_preflight'] = 'PREFLIGHT.json'
    audit.write_text(json.dumps(record, indent=2) + '\n')


if __name__ == '__main__':
    main()
