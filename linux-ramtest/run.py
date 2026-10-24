#!/usr/bin/env python3
"""Stage or request Linux from an already-running published OpeniBoot ACM."""
import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/'saved/build/T4_LINUX_RAM_02'
def main():
    p=argparse.ArgumentParser(description=__doc__)
    g=p.add_mutually_exclusive_group(required=True)
    g.add_argument('--check',action='store_true',help='offline checks only; no USB access')
    g.add_argument('--stage',action='store_true',help='upload fixed RAM payloads and validate; do not enter Linux')
    g.add_argument('--boot',action='store_true',help='stage, validate, then request native Linux handoff')
    p.add_argument('--build',choices=['T4_LINUX_RAM_02','T4_LINUX_DIAG_03','T4_LINUX_DIAG_04','T4_LINUX_DIAG_05','T4_LINUX_DIAG_06','T4_LINUX_DIAG_07','T4_LINUX_DIAG_08','T4_LINUX_DIAG_09','T4_LINUX_DIAG_10','T4_LINUX_DIAG_11','T4_LINUX_DIAG_12','T4_ANDROID_INIT_01','T4_ANDROID_INIT_02','T4_ANDROID_INIT_03','T4_ANDROID_INIT_04','T4_ANDROID_UI_01','T4_ANDROID_UI_02','T4_ANDROID_UI_03','T4_ANDROID_UI_04','T4_ANDROID_UI_05','T4_ANDROID_UI_06','T4_ANDROID_UI_07','T4_ANDROID_INPUT_01','T4_ANDROID_INPUT_02','T4_ANDROID_INPUT_03','T4_ANDROID_USB_01','T4_USB_ACM_01','T4_ANDROID_ADB_01','T4_ANDROID_TOUCH_01','T4_ANDROID_TOUCH_02','T4_ANDROID_TOUCH_03'],default='T4_LINUX_RAM_02')
    args=p.parse_args()
    out=ROOT/'saved/build'/args.build
    m=json.loads((out/'manifest.json').read_text())
    assert m['variant']==args.build
    sha=lambda b:hashlib.sha256(b).hexdigest()
    assert sha((ROOT/'saved/build/phase1-published/openiboot.bin').read_bytes())==m['baseline_sha256']
    for n,e in m['files'].items():
        assert Path(n).name==n
        assert sha((out/n).read_bytes())==e['sha256'],n
    entries=m['entries'];helper_size=m['files']['handoff.bin']['bytes']
    for addr in entries.values():assert 0x44000000<=addr<0x44000000+helper_size and addr&1
    selection='SELECTED_BUILD: '+args.build+'\n'
    selection+='MANIFEST: '+str(out/'manifest.json')+'\n'
    selection+='HANDOFF_SHA256: '+m['files']['handoff.bin']['sha256']+'\n'
    selection+='EXPECTED_STOP: '+str(m.get('intentional_stop') or 'no normal checkpoint halt')+'\n'
    print(selection,end='',flush=True)
    hardware = None
    evidence = out/'HARDWARE-RESULT.json'
    if evidence.exists():
        report = json.loads(evidence.read_text())
        verified_manifest = report.get('manifest_sha256') == sha((out/'manifest.json').read_bytes())
        result = report.get('confirmed', {})
        if verified_manifest:
            if result.get('ADB_shell_marker') and result.get('Android_ADB_device_state') == 'device':
                hardware = 'recorded physical Android ADB enumeration and shell execution'
            elif result.get('Linux_ACM_enumeration') and result.get('host_to_device_and_back_echo'):
                hardware = 'recorded physical ACM enumeration and bidirectional data; Android/ADB untested'
    if hardware:
        print('Offline hashes and RAM bounds OK. This exact build has '+hardware+'.',flush=True)
    else:
        print('Offline hashes and RAM bounds OK. Linux hardware status remains unconfirmed.',flush=True)
    if args.check:return 0
    logs=ROOT/'saved/logs';logs.mkdir(exist_ok=True)
    path=logs/('linux-ram-'+datetime.now().strftime('%Y%m%d-%H%M%S')+'.log')
    cmd=[str(out/'linux-usb'),'--boot' if args.boot else '--stage',
         str(out/'zImage'),str(out/'initramfs.cpio.gz'),str(out/'handoff.bin'),
         hex(entries['t4_linux_stage']),hex(entries['t4_linux_start'])]
    with path.open('wb') as log:
        log.write(selection.encode());log.flush()
        process=subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
        for chunk in iter(process.stdout.readline,b''):
            log.write(chunk);log.flush();sys.stdout.buffer.write(chunk);sys.stdout.buffer.flush()
        code=process.wait()
        if code:
            failure=f'[HOST] RAM boot utility exited with code {code}; boot is NOT confirmed.\n'
            log.write(failure.encode());log.flush();print(failure,end='',flush=True)
    print('Log:',path)
    return code
if __name__=='__main__':raise SystemExit(main())
