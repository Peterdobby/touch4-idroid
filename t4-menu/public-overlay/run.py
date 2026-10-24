#!/usr/bin/env python3
"""Load the UI once, then watch up to 120s for iOS/Home and request native boot.

Start from a fresh published RAM boot, not an already running menu task.
"""
from datetime import datetime
import hashlib,json,subprocess,sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
out=ROOT/'saved/build/T4_PUBLIC_MENU_01/live'
m=json.loads((out/'live.json').read_text())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert m['load']==0x45000000 and m['load']<=m['entry']<m['load']+m['bytes']
assert sha(out/'menu.bin')==m['sha256']
assert sha(out/'upload')==m['uploader_sha256']
assert sha(Path('~/Downloads/openiboot_ipodtouch4g_0.3.bin'))==m['base_sha256']
log=ROOT/'saved/logs'/('public-menu-live-'+datetime.now().strftime('%Y%m%d-%H%M%S')+'.log')
with log.open('wb') as f:
    p=subprocess.Popen([str(out/'upload'),str(out/'menu.bin'),hex(m['entry'])],
                       stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    for b in iter(p.stdout.readline,b''):
        f.write(b);f.flush();sys.stdout.buffer.write(b);sys.stdout.buffer.flush()
    result=p.wait()
print('Log:',log)
raise SystemExit(result)
