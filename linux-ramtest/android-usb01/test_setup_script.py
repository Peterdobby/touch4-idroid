#!/usr/bin/env python3
from pathlib import Path
import json,tempfile,subprocess,sys,shlex
HERE=Path(__file__).resolve().parent;OUT=HERE.parents[1]/'saved/build/T4_ANDROID_USB_01'
cases=[]
with tempfile.TemporaryDirectory(prefix='t4-usb-setup-test-') as temp:
 for tag,number,gadget,expected in [('valid','10:42',True,0),('wrong-major','8:0',True,1),('wrong-minor','10:999',True,1),('no-gadget','10:42',False,1)]:
  root=Path(temp)/tag;root.mkdir();base=root/'android0';base.mkdir();misc=root/'misc';misc.mkdir();(misc/'dev').write_text(number+'\n')
  if gadget:(base/'enable').touch()
  log=root/'setprop.log';bb=root/'bb';bb.write_text('#!'+sys.executable+'\n'+'''import sys,pathlib
cmd,*args=sys.argv[1:]
if cmd=='sleep':pass
elif cmd=='mknod':
 assert args[1:]==['c','10','42'];pathlib.Path(args[0]).touch(exist_ok=False)
else:raise AssertionError((cmd,args))
''');bb.chmod(0o755)
  prop=root/'setprop';prop.write_text('#!/bin/sh\nprintf "%s %s\\n" "$1" "$2" > '+shlex.quote(str(log))+'\n');prop.chmod(0o755)
  script=(HERE/'t4-usb-setup.sh').read_text().replace('/sys/class/android_usb/android0',str(base)).replace('/sys/class/misc/android_adb',str(misc)).replace('/dev/android_adb',str(root/'adbnode')).replace('/dev/kmsg',str(root/'kmsg')).replace('/sbin/busybox',str(bb)).replace('/system/bin/setprop',str(prop)).replace(' -c ',' -f ')
  p=subprocess.run(['/bin/sh','-c',script],timeout=5);assert p.returncode==expected,(tag,p.returncode)
  if not expected:
   assert (base/'functions').read_text()=='adb\n' and (base/'idVendor').read_text()=='18d1\n' and (base/'idProduct').read_text()=='0001\n'
   assert (base/'enable').read_text()=='1\n' and log.read_text()=='ctl.start adbd\n'
  else:assert not log.exists()
  cases.append({'case':tag,'exit':p.returncode})
report={'actual_shell_logic_cases':cases,'mock':'all sysfs/dev paths redirected to temporary files, character type modeled as regular file; mknod and setprop mocked; no real device operations','hardware':'pending'}
(OUT/'usb-setup-test.json').write_text(json.dumps(report,indent=2)+'\n');print('USB_SETUP_SCRIPT_PASSED: ADB-only attrs; original adbd start; missing device and invalid dev numbers refused')
