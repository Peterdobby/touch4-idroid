#!/usr/bin/env python3
"""Test host verifier parsing with a fixture adb process; no USB/server use."""
from pathlib import Path
import tempfile,subprocess,os,json
R=Path(__file__).resolve().parents[2];OUT=R/'saved/build/T4_ANDROID_ADB_01'
cases=[]
with tempfile.TemporaryDirectory(prefix='t4-adb-host-test-') as td:
 root=Path(td);(root/'tools/adb-host-adb01').mkdir(parents=True)
 (root/'tools/t4-adb-check.py').write_text((R/'tools/t4-adb-check.py').read_text())
 adb=root/'tools/adb-host-adb01/adb'
 adb.write_text('''#!/usr/bin/env python3
import sys,os
args=sys.argv[1:];mode=os.environ['T4_ADB_FIXTURE']
assert args[:2]==['-P','5037']
args=args[2:]
if args==['version']:print('fixture adb')
elif args==['devices','-l']:
 print('List of devices attached')
 print(('OTHER' if mode=='other' else 'T4RAMADB01')+'\\t'+('offline' if mode=='offline' else 'device'))
elif args[:3]==['-s','T4RAMADB01','shell']:
 assert args[3]=='echo T4_ADB_SHELL_OK; id; uname -r'
 print('missing shell' if mode=='no-shell' else 'T4_ADB_SHELL_OK\\nuid=0(root)\\n3.0.8')
else:raise AssertionError(args)
''');adb.chmod(0o755)
 for mode,exitcode in [('success',0),('offline',2),('other',2),('no-shell',3)]:
  # Keep generated log names distinct, without a real-time sleep.
  logs=root/'saved/logs'
  if logs.exists():
   for f in logs.iterdir():f.unlink()
  p=subprocess.run(['python3',str(root/'tools/t4-adb-check.py'),'--wait','0'],env={**os.environ,'T4_ADB_FIXTURE':mode},text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=5)
  assert p.returncode==exitcode,(mode,p.stdout)
  assert ('T4_ADB_SHELL_CONFIRMED' in p.stdout)==(mode=='success')
  cases.append({'case':mode,'exit':p.returncode})
(OUT/'host-check-test.json').write_text(json.dumps({'cases':cases,'hardware':'not accessed; fixture process only'},indent=2)+'\n');print('HOST_CHECK_PASS: expected serial + device state + actual shell marker required')
