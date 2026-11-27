#!/usr/bin/env python3
"""N81AP RAM boot. --check is read-only; --boot explicitly runs the test."""
import argparse
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT/'tools'))
from native_image import validate_native, sha256
parser = argparse.ArgumentParser(description=__doc__)
group = parser.add_mutually_exclusive_group(required=True)
group.add_argument('--check', action='store_true')
group.add_argument('--boot', action='store_true')
variant = parser.add_mutually_exclusive_group()
variant.add_argument('--headless', action='store_true', help='skip display initialization in OpeniBoot')
variant.add_argument('--published', action='store_true', help='use the published binary with NAND init skipped')
variant.add_argument('--build', choices=['T4_DIAG_01','T4_MENU_01','T4_PUBLIC_MENU_01'], help='use a c5cee8c UI test build')
variant.add_argument('--file', type=Path, help='boot an N81 native wrapped image; raw payloads are rejected')
parser.add_argument('--kdfu', action='store_true', help='device is in kDFU (entered over SSH) instead of BootROM DFU; no exploit is run')
args = parser.parse_args()
IBSS = ROOT/('saved/build/iBSS.n81ap.go.kdfu.dfu' if args.kdfu else 'saved/build/iBSS.n81ap.go.dfu')
# Same patched plaintext; the kDFU variant is decrypted because the GID key is unavailable there.
IBSS_SHA = ('5f63b01ef747071e61bb6d3bf320b07d4dc1afbf1d4460ae18865e99240d9986' if args.kdfu else
            'e8b10d73a72fbca026161bd4d4f169992092d8c0eed022540c8072bb5f5ddfcc')
OUT = ROOT/('saved/build/'+args.build if args.build else 'saved/build/phase1-published' if args.published or args.file else 'saved/build/phase1-headless' if args.headless else 'saved/build/phase1')
# Validate the selected image before any device access, including --check --file.
image_path = (args.file if args.file else OUT/'openiboot-native.bin').resolve()
image_sha = None
if args.boot or args.file:
    try:
        image = image_path.read_bytes()
        metadata_path = Path(str(image_path)+'.json')
        metadata = json.loads(metadata_path.read_text()) if metadata_path.exists() else None
        validate_native(image, metadata)
        image_sha = sha256(image)
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.exit(2, 'Native image refused before USB access: '+str(error)+'\n')
irecovery = os.environ.get('IRECOVERY', shutil.which('irecovery') or '')
if not irecovery:
    raise SystemExit('irecovery missing')
log = None

def run(command, check=True):
    env = None
    libs = os.environ.get('T4_IRECOVERY_LIBS')
    if libs and str(command[0]) == irecovery:
        env = dict(os.environ, LD_LIBRARY_PATH=libs)
    result = subprocess.run([str(x) for x in command], stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, env=env)
    sys.stdout.buffer.write(result.stdout)
    sys.stdout.buffer.flush()
    if log:
        log.write(result.stdout); log.flush()
    if check and result.returncode:
        raise SystemExit(result.returncode)
    return result

def query(expected_ecid=None):
    result = run([irecovery, '-q'])
    fields = dict(line.split(': ', 1) for line in result.stdout.decode().splitlines() if ': ' in line)
    if (fields.get('CPID') != '0x8930' or fields.get('BDID') != '0x08' or
        fields.get('MODE') != 'DFU' or
        (fields.get('SRTG', '').startswith('iBoot') if args.kdfu else fields.get('SRTG') != 'iBoot-574.4')):
        raise SystemExit('Expected N81AP '+('kDFU' if args.kdfu else 'hardware DFU')+'; stopped before image upload')
    ecid = int(fields['ECID'].split()[0], 16)  # Linux irecovery appends "(decimal)"
    if expected_ecid is not None and ecid != expected_ecid:
        raise SystemExit('ECID changed; stopped')
    return fields, ecid

if args.check:
    query()
    raise SystemExit(0)
manifest = json.loads((OUT/'manifest.json').read_text())
for name, info in manifest['files'].items():
    if hashlib.sha256((ROOT/name).read_bytes()).hexdigest() != info['sha256']:
        raise SystemExit('Checksum mismatch: '+name)
if sha256(IBSS.read_bytes()) != IBSS_SHA:
    raise SystemExit('Native wrapper requires the pinned N81 4.1 patched iBSS')
saved = json.loads((ROOT/'saved/private/device.local.json').read_text())
expected_ecid = int(saved['ECID'], 0)
kit = Path(os.environ.get('LIK_PATH', '~/Legacy-iOS-Kit'))
pwnder = kit/'bin/macos/ipwnder'
if not args.kdfu and not pwnder.is_file():
    raise SystemExit('Set LIK_PATH to your Legacy-iOS-Kit directory')
logs = ROOT/'saved/logs'
logs.mkdir(exist_ok=True)
path = logs/((('native-file-' if args.file else args.build+'-') if args.file or args.build else 'phase1-'+('published-' if args.published else 'headless-' if args.headless else 'native-'))+datetime.now().strftime('%Y%m%d-%H%M%S')+'.log')
with path.open('wb') as log:
    info = ('Native image: '+str(image_path)+'\nSHA256(native): '+image_sha+'\n').encode()
    sys.stdout.buffer.write(info); sys.stdout.buffer.flush()
    log.write(info); log.flush()
    fields, ecid = query(expected_ecid)
    if not args.kdfu:
        if not fields.get('PWND'):
            run([pwnder, '-p'])
            time.sleep(0.5)
        fields, ecid = query(ecid)
        if not fields.get('PWND'):
            raise SystemExit('Independent PWND descriptor verification failed; no images sent')
    if sha256(image_path.read_bytes()) != image_sha:
        raise SystemExit('Native image changed during preparation; upload stopped')
    run([OUT/'load', hex(ecid), IBSS, image_path] + (['--kdfu'] if args.kdfu else []))
    # Only the new ACM round trip is success, never an upload exit code.
    result = run([OUT/'console'], check=False)
    print('Log:', path, flush=True)
    raise SystemExit(result.returncode)
