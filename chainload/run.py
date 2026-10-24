#!/usr/bin/env python3
"""Verify/build-independent controlled-RAM test. This never runs an exploit."""
import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'saved/build/chainload'
parser = argparse.ArgumentParser(description=__doc__)
mode = parser.add_mutually_exclusive_group(required=True)
mode.add_argument('--check', action='store_true', help='offline checks; no USB access')
mode.add_argument('--boot', action='store_true', help='use ALREADY controlled N81 DFU or explicitly named iBSS')
parser.add_argument('--ibss-already-running', action='store_true',
                    help='only when the pinned 4.1 go iBSS is ALREADY running in controlled Recovery')
args = parser.parse_args()
if args.ibss_already_running and not args.boot:
    parser.error('--ibss-already-running requires --boot')
manifest = json.loads((OUT/'manifest.json').read_text())
def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()
def verify():
    for name, expected in manifest['protected_inputs'].items():
        if sha(ROOT/name) != expected:
            raise SystemExit('Protected input mismatch: '+name)
    for name, info in manifest['files'].items():
        if sha(ROOT/name) != info['sha256']:
            raise SystemExit('Build output mismatch: '+name)
    for name, expected in manifest['sources'].items():
        if sha(ROOT/name) != expected:
            raise SystemExit('Source changed since build; rebuild first: '+name)
    arm = json.loads((OUT/'ARM-TESTS.json').read_text())
    if (not arm['all_passed'] or arm['loader_sha256'] != sha(OUT/'t4-oib-loader.bin') or
        arm['native_sha256'] != sha(OUT/'openiboot-native.bin') or
        arm['fixture_sha256'] != sha(OUT/'t4-oib-ram-fixture.bin') or
        arm['test_source_sha256'] != sha(ROOT/'chainload/test-arm.py')):
        raise SystemExit('Run the offline ARM tests for this build first.')
verify()
print('T4_OIB_CHAINLOAD_01: pinned image, loader, archive checks and ARM tests OK.', flush=True)
if args.check:
    print('OFFLINE_CHECK_OK (no USB operations; hardware boot not implied)')
    raise SystemExit(0)

logs = OUT/'logs'
logs.mkdir(exist_ok=True)
stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
log_path = logs/(stamp+'.log')
result = {'hardware_success': False, 'started_at': stamp, 'log': str(log_path),
          'manifest_sha256': sha(OUT/'manifest.json'), 'exploit_invoked': False,
          'storage_commands_sent': False, 'context': 'controlled-ibss' if args.ibss_already_running else 'controlled-dfu'}
exit_code = 2
with log_path.open('wb') as log:
    def run(command):
        process = subprocess.Popen([str(x) for x in command], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        for line in iter(process.stdout.readline, b''):
            sys.stdout.buffer.write(line); sys.stdout.buffer.flush()
            log.write(line); log.flush()
        return process.wait()
    try:
        if subprocess.run([str(OUT/'acm-version'), '--absent']).returncode != 0:
            raise RuntimeError('OpeniBoot is already present; a fresh loader boot cannot be distinguished. Nothing sent.')
        saved = json.loads((ROOT/'saved/private/device.local.json').read_text())
        ecid = int(saved['ECID'], 0)
        status = run([OUT/'controlled-ram', hex(ecid), ROOT/'saved/build/iBSS.n81ap.go.dfu',
                      OUT/'t4-oib-ram-fixture.bin', result['context']])
        if status:
            raise RuntimeError('Controlled RAM transport stopped; no hardware success claimed.')
        result['ram_transport_completed'] = True
        status = run([OUT/'acm-version'])
        result['hardware_success'] = status == 0
        if status:
            raise RuntimeError('RAM upload completed, but fresh USB/ACM version verification failed.')
        exit_code = 0
    except (RuntimeError, OSError) as error:
        message = str(error)+'\n'
        print(message, end='', file=sys.stderr)
        log.write(message.encode())
        result['error'] = str(error)
    finally:
        verify()
        result['protected_unchanged_after_test'] = True
        result_path = logs/(stamp+'.json')
        result_path.write_text(json.dumps(result, indent=2)+'\n')
        print('Result:', result_path)
        print('Log:', log_path)
raise SystemExit(exit_code)
