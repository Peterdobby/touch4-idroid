#!/usr/bin/env python3
"""Read the EXISTING working iOS kernelcache via SSH. Host output only.
No install, restore, mount, remote helper upload or device file writes.
"""
import argparse
import datetime
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
PATHS = [
    '/System/Library/Caches/com.apple.kernelcaches/kernelcache',
    '/System/Library/Caches/com.apple.kernelcaches/kernelcache.release.n81',
    '/System/Library/Caches/com.apple.kernelcaches/kernelcache.release.n81ap',
]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--target', default='root@127.0.0.1')
    p.add_argument('--port', type=int, default=6414)
    a = p.parse_args()
    if not re.fullmatch(r'[A-Za-z0-9_.@:-]+', a.target) or a.target.startswith('-') or not 1 <= a.port <= 65535:
        p.error('Invalid SSH destination/port')
    with tempfile.TemporaryDirectory(prefix='t4-ios-read-') as temp:
        ssh = ['ssh', '-T', '-o', 'HostKeyAlgorithms=+ssh-rsa', '-o', 'ConnectTimeout=10',
               '-o', 'ControlMaster=auto', '-o', 'ControlPersist=60',
               '-o', 'ControlPath=' + temp + '/ssh', '-p', str(a.port), a.target]

        def read(command):
            r = subprocess.run(ssh + [command], stdout=subprocess.PIPE, timeout=120)
            if r.returncode:
                raise RuntimeError('SSH read failed (exit %d)' % r.returncode)
            return r.stdout

        try:
            machine = read('sysctl -n hw.machine').decode().strip()
            if machine != 'iPod4,1':
                raise RuntimeError('N81 identity not confirmed: ' + machine)
            metadata = read('uname -a; sysctl hw.machine hw.model; cat /System/Library/CoreServices/SystemVersion.plist')
            chosen = None
            for path in PATHS:
                reply = read("if test -r '" + path + "'; then echo FOUND; else echo MISSING; fi").decode().strip()
                if reply == 'FOUND':
                    chosen = path
                    break
            if chosen is None:
                raise RuntimeError('No readable kernelcache at standard paths; stop without installing anything')
            payload = read("cat '" + chosen + "'")
            size = len(payload)
            if not 1024 <= size <= 32 * 1024 * 1024:
                raise RuntimeError('Kernelcache read size outside 1 KiB..32 MiB')
            out = ROOT / 'saved/research/touch-bringup' / ('ios-working-kernel-' + datetime.datetime.now().strftime('%Y%m%d-%H%M%S'))
            out.mkdir(exist_ok=False)
            (out / 'kernelcache').write_bytes(payload)
            (out / 'ios-version.txt').write_bytes(metadata)
            manifest = {'machine': machine, 'source_path': chosen, 'size': size,
                        'sha256': hashlib.sha256(payload).hexdigest(),
                        'first16_hex': payload[:16].hex(), 'device_file_writes': False,
                        'note': 'Existing on-disk cache; compare version with uname before treating as the running kernel'}
            (out / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
            print(json.dumps(manifest, indent=2))
            print('Host output:', out)
        finally:
            subprocess.run(ssh[:-1] + ['-O', 'exit', a.target], stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL, timeout=15)


if __name__ == '__main__':
    try:
        main()
    except (OSError, RuntimeError, ValueError, subprocess.TimeoutExpired) as exc:
        raise SystemExit(str(exc))
