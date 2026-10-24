#!/usr/bin/env python3
"""Run the actual shell selection logic in a temporary fixture; mock node/owner ops."""
from pathlib import Path
import tempfile,subprocess,sys,json,shlex
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];OUT=ROOT/'saved/build/T4_ANDROID_INPUT_02'
with tempfile.TemporaryDirectory(prefix='t4-input-node-test-') as tmp:
 t=Path(tmp);sysfs=t/'sys';dev=t/'dev';sysfs.mkdir();dev.mkdir();log=t/'ops.jsonl'
 fixtures={'event0':('t4-ram-keys','13:64'),'event1':('t4-ram-keys','13:65'),'event2':('other-device','13:66'),'event3':('t4-ram-keys','8:0'),'event4':('t4-ram-keys','13:128'),'eventx':('t4-ram-keys','13:67')}
 for name,(device,number) in fixtures.items():
  d=sysfs/name;(d/'device').mkdir(parents=True);(d/'device/name').write_text(device);(d/'dev').write_text(number+'\n')
 (dev/'event1').write_text('must not overwrite')
 d=sysfs/'input0';d.mkdir();(d/'name').write_text('t4-ram-keys');(d/'t4_pulse').touch()
 fake=t/'bb';fake.write_text('#!'+sys.executable+'\n'+f'''import sys,pathlib,json
args=sys.argv[1:];cmd=args[0]
with open({str(log)!r},'a') as f:f.write(json.dumps(args)+'\\n')
if cmd=='cat':sys.stdout.write(pathlib.Path(args[1]).read_text())
elif cmd=='mkdir':pathlib.Path(args[-1]).mkdir(parents=True,exist_ok=True)
elif cmd=='mknod':
 assert args[2:]==['c','13','64'];pathlib.Path(args[1]).touch(exist_ok=False)
elif cmd in ['chown','chmod']:
 assert pathlib.Path(args[-1]).parent==pathlib.Path({str(dev)!r})
else:raise AssertionError(args)
''');fake.chmod(0o755)
 script=(HERE/'t4-input-common.sh').read_text().replace('bb=/sbin/busybox','bb='+shlex.quote(str(fake))).replace('/sys/class/input',str(sysfs)).replace('/dev/input',str(dev))
 script+='\nscan_input_nodes\nphase=1\npulse_input\necho "NODES=$nodes"\n'
 result=subprocess.check_output(['/bin/sh','-c',script],text=True)
 assert 'NODES=1' in result and (d/'t4_pulse').read_text()=='1 1 1\n'
 assert (dev/'event1').read_text()=='must not overwrite'
 assert {p.name for p in dev.iterdir()}=={'event0','event1'}
 ops=[json.loads(l) for l in log.read_text().splitlines()]
 assert [x for x in ops if x[0]=='mknod']==[['mknod',str(dev/'event0'),'c','13','64']]
 assert ['chown','1000:1004',str(dev/'event0')] in ops and ['chmod','0660',str(dev/'event0')] in ops
report={'shell_fixture_passed':True,'only_target_evdev_major13_minors64_95':True,'wrong_major_minor_name_suffix_and_existing_regular_file_rejected':True,'owner_mode_intended':'1000:1004 0660','mock':'mknod/chown/chmod; all paths redirected to temporary directory; no real device nodes or ownership changed','hardware':'pending'}
(OUT/'node-script-test.json').write_text(json.dumps(report,indent=2)+'\n');print('NODE_SCRIPT_PASSED: target selection, permissions, rejection cases, pulse')
