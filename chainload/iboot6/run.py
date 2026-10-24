#!/usr/bin/env python3
"""Use the existing unmodified phase1 DFU RAM workflow for CPU compatibility."""
import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'saved/build/chainload-iboot6'
sys.path.insert(0,str(ROOT/'chainload'))
from build import check_protected
p=argparse.ArgumentParser(description=__doc__)
g=p.add_mutually_exclusive_group(required=True)
g.add_argument('--check',action='store_true')
g.add_argument('--boot',action='store_true')
args=p.parse_args()
sha=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()
def verify():
    check_protected()
    manifest=json.loads((OUT/'manifest.json').read_text())
    for name,expected in manifest['files'].items():
        if sha(OUT/name)!=expected:raise SystemExit('Build changed: '+name)
    for name,expected in manifest['sources'].items():
        if sha(Path(__file__).parent/name)!=expected:raise SystemExit('Source changed; rebuild: '+name)
    tests=json.loads((OUT/'ARM-TESTS.json').read_text())
    if not tests['all_passed'] or tests['files']!=manifest['files'] or tests['test_source_sha256']!=sha(Path(__file__).parent/'test-arm.py'):
        raise SystemExit('Run ARM test for this build first.')
verify()
if args.check:
    print('T4_IBOOT6_RAM_01 offline checks OK; hardware unconfirmed.');raise SystemExit(0)
logs=OUT/'logs';logs.mkdir(exist_ok=True)
stamp=datetime.now().strftime('%Y%m%d-%H%M%S')
result=dict(hardware_success=False,scope='isolated iBoot6 CPU/loader compatibility; not full DRV6',
            existing_phase1_workflow=True,persistent_writes=False)
rc=2
with (logs/(stamp+'.log')).open('wb') as log:
    def run(command):
        process=subprocess.Popen([str(x) for x in command],cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
        for line in iter(process.stdout.readline,b''):
            sys.stdout.buffer.write(line);sys.stdout.buffer.flush();log.write(line);log.flush()
        return process.wait()
    try:
        if subprocess.run([str(ROOT/'saved/build/chainload/acm-version'),'--absent']).returncode:
            raise RuntimeError('OpeniBoot already present; start from a fresh DFU session.')
        print('Using unchanged phase1 workflow; it may invoke the existing external DFU tool.',flush=True)
        rc=run([sys.executable,ROOT/'phase1/run.py','--boot','--file',OUT/'iboot6-ram-test-native.bin'])
        result['phase1_exit']=rc
        # A console timeout alone does not establish that the image failed.
        rc=run([ROOT/'saved/build/chainload/acm-version'])
        result['hardware_success']=rc==0
    except (RuntimeError,OSError) as error:
        result['error']=str(error);print(error);rc=2
    finally:
        verify()
        result['protected_unchanged_after_test']=True
        (logs/(stamp+'.json')).write_text(json.dumps(result,indent=2)+'\n')
        print('Log:',logs/(stamp+'.log'))
        print('Result:',logs/(stamp+'.json'))
raise SystemExit(rc)
