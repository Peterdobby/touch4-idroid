#!/usr/bin/env python3
"""Execute actual setup shell with temporary RAM/sysfs/PTY service fixtures."""
from pathlib import Path
import json,tempfile,subprocess,sys,shlex
HERE=Path(__file__).resolve().parent;OUT=HERE.parents[1]/'saved/build/T4_ANDROID_ADB_01'
cases=[]
with tempfile.TemporaryDirectory(prefix='t4-adb-setup-') as temp:
 for tag,number,gadget,ptmx,mounted,expected in [('ready','10:42',True,'5:2',True,0),('mount-pty','10:42',True,'5:2',False,0),('wrong-major','8:0',True,'5:2',True,1),('wrong-minor','10:999',True,'5:2',True,1),('wrong-pty','10:42',True,'8:0',True,1),('no-gadget','10:42',False,'5:2',True,1)]:
  root=Path(temp)/tag;root.mkdir();base=root/'android0';base.mkdir();misc=root/'misc';misc.mkdir();(misc/'dev').write_text(number+'\n')
  (root/'pty-dev').write_text(ptmx+'\n');(root/'pts').mkdir();mounts=root/'mounts';mounts.write_text(('devpts '+str(root/'pts')+' devpts rw 0 0\n') if mounted else '')
  if gadget:(base/'enable').touch()
  log=root/'setprop.log';bb=root/'bb'
  bb.write_text('#!'+sys.executable+'\n'+'''import sys,pathlib
cmd,*args=sys.argv[1:]
root=pathlib.Path(__file__).parent
if cmd=='sleep':pass
elif cmd=='mkdir':pathlib.Path(args[-1]).mkdir(parents=True,exist_ok=True)
elif cmd=='grep':sys.exit(0 if ' devpts ' in pathlib.Path(args[-1]).read_text() else 1)
elif cmd=='mount':
 assert args==['-t','devpts','devpts',str(root/'pts')]
 (root/'mounts').write_text('devpts '+str(root/'pts')+' devpts rw 0 0\\n')
elif cmd=='mknod':
 assert args[1:] in [['c','10','42'],['c','5','2']]
 pathlib.Path(args[0]).touch(exist_ok=False)
else:raise AssertionError((cmd,args))
''');bb.chmod(0o755)
  prop=root/'setprop';prop.write_text('#!/bin/sh\nprintf "%s %s\\n" "$1" "$2" > '+shlex.quote(str(log))+'\n');prop.chmod(0o755)
  script=(HERE/'t4-usb-setup.sh').read_text()
  for a,b in [('/sys/class/android_usb/android0',str(base)),('/sys/class/misc/android_adb',str(misc)),('/sys/class/tty/ptmx/dev',str(root/'pty-dev')),('/dev/android_adb',str(root/'adbnode')),('/dev/ptmx',str(root/'ptmx')),('/dev/pts',str(root/'pts')),('/proc/mounts',str(mounts)),('/dev/kmsg',str(root/'kmsg')),('/sbin/busybox',str(bb)),('/system/bin/setprop',str(prop))]:script=script.replace(a,b)
  script=script.replace(' -c ',' -f ')
  proc=subprocess.run(['/bin/sh','-c',script],timeout=5);assert proc.returncode==expected,(tag,proc.returncode)
  if not expected:
   assert (base/'functions').read_text()=='adb\n' and (base/'idVendor').read_text()=='18d1\n' and (base/'idProduct').read_text()=='0001\n'
   assert (base/'iSerial').read_text()=='T4RAMADB01\n'
   assert (base/'enable').read_text()=='1\n' and log.read_text()=='ctl.start adbd\n'
   assert (root/'ptmx').exists() and ' devpts ' in mounts.read_text()
  else:assert not log.exists()
  cases.append({'case':tag,'exit':proc.returncode})
(OUT/'usb-setup-test.json').write_text(json.dumps({'cases':cases,'mock':'temporary files for all sysfs/dev/proc paths, mocked mknod/mount/setprop; no device operations','hardware':'pending'},indent=2)+'\n')
print('ADB_SETUP_PASS: ADB-only attrs, PTY prep, daemon start; invalid nodes and absent gadget refused')
