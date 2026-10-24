#!/usr/bin/env python3
"""Offline USB transport regressions; never loads libusb or accesses hardware."""
from pathlib import Path
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = ROOT / 'saved/build/T4_ANDROID_TOUCH_01/tests'
OUT.mkdir(parents=True, exist_ok=True)
program = OUT / 'test-upload-v2'
subprocess.run(['cc', '-Wall', '-Wextra', '-Werror', '-g',
                '-fsanitize=address,undefined', '-DT4_TEST_NAME="T4_ANDROID_TOUCH_01"',
                '-I' + str(ROOT / 'saved/research/libusb-1.0.29/libusb'),
                str(HERE / 'test_upload.c'), '-o', str(program)], check=True)
cases = [('good', '--boot'), ('good', '--stage')] + [
    (n, '--boot') for n in ['recover-ack', 'recover-out', 'bad-version',
                           'missing-ack', 'wrong-end', 'timeout', 'reset-fail',
                           'fresh-version-fail', 'bad-stage', 'bad-cmdline']]
logs = []
with tempfile.TemporaryDirectory(prefix='t4-upload-test-') as directory:
    paths = []
    for name, size in [('kernel', 1000), ('initrd', 4*1024*1024+84), ('helper', 8692)]:
        path = Path(directory) / name
        path.write_bytes((bytes(range(256)) * (size//256+1))[:size])
        paths.append(str(path))
    for scenario, mode in cases:
        result = subprocess.run([str(program), mode, *paths, '0x440006e9',
                                 '0x44000731', scenario], stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True, timeout=5)
        logs.append(f'{mode} {scenario}\n{result.stdout}')
        if result.returncode:
            print(result.stdout)
            raise SystemExit(result.returncode)
        print('PASS:', mode, scenario)
(OUT / 'upload-v2-regression.log').write_text('\n'.join(logs))
print('12 offline cases passed; actual USB recovery/boot remains unverified.')
